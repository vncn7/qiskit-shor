import json
import os
from datetime import datetime

import qiskit
import qiskit_aer
import qiskit_ibm_runtime
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import SamplerV2 as Sampler


BACKEND_MODE = os.environ.get("BACKEND_MODE", "ideal").lower()
BACKEND_NAME = os.environ.get("BACKEND_NAME", "ibm_kingston")

# Sabre layout/routing is stochastic; a fixed seed makes the transpiled circuit
# deterministic. The simulator itself is deliberately NOT seeded so that
# repeated runs yield independent samples (needed for error bars).
SEED_TRANSPILER = 1337

FAKE_BACKENDS = {
    "ibm_kingston": "FakeKingston",
    "ibm_fez": "FakeFez",
    "ibm_marrakesh": "FakeMarrakesh",
}

# Per-qubit calibration parameters to collect from the backend properties.
# T1/T2 come in microseconds, readout_error is a dimensionless probability.
QUBIT_PARAMETERS = ("readout_error", "T1", "T2")


def get_backend():

    if BACKEND_MODE == "ideal":
        print("Running on: ideal AerSimulator")
        return AerSimulator(), None

    if BACKEND_MODE == "noisy":
        from qiskit_ibm_runtime import fake_provider

        fake_backend = getattr(
            fake_provider,
            FAKE_BACKENDS[BACKEND_NAME],
        )()

        print(f"Running on noise model of: {fake_backend.name}")

        return AerSimulator.from_backend(fake_backend), fake_backend

    if BACKEND_MODE == "hardware":
        from qiskit_ibm_runtime import QiskitRuntimeService

        service = QiskitRuntimeService(
            channel="ibm_quantum_platform",
            token=os.environ["IBM_TOKEN"],
        )

        backend = service.backend(BACKEND_NAME)

        print(f"Running on hardware: {backend.name}")
        print(f"Calibration timestamp: {backend.properties().last_update_date}")

        return backend, backend

    raise ValueError(f"Unknown BACKEND_MODE: {BACKEND_MODE}")


def transpile_circuit(qc, backend, optimization_level):

    pm = generate_preset_pass_manager(
        backend=backend,
        optimization_level=optimization_level,
        seed_transpiler=SEED_TRANSPILER,
    )

    return pm.run(qc)


def get_physical_qubits(isa):
    # Physical qubits the circuit ends up on; None on the ideal simulator, which
    # has no coupling map and therefore no layout.

    if isa.layout is None:
        return None

    return isa.layout.final_index_layout()


def circuit_metadata(qc, isa):

    return {
        "original": {
            "num_qubits": qc.num_qubits,
            "depth": qc.depth(),
            "gate_counts": dict(qc.count_ops()),
        },
        # No num_qubits here: on real/fake backends isa.num_qubits is the full
        # chip width, physical_qubits carries the meaningful info.
        "transpiled": {
            "depth": isa.depth(),
            "gate_counts": dict(isa.count_ops()),
            "physical_qubits": get_physical_qubits(isa),
        },
    }


def get_calibration(properties, isa):
    """Raw calibration values of the physical qubits the circuit runs on.
    T1/T2 are in us, readout_error and gate_error are dimensionless probabilities.
    Aggregation (mean/min/max, histograms) happens in the analysis, not here."""

    if properties is None:
        return None

    physical_qubits = set(get_physical_qubits(isa))

    qubits = {name: [] for name in QUBIT_PARAMETERS}

    for qubit in physical_qubits:
        for parameter in properties.qubits[qubit]:
            if parameter.name in QUBIT_PARAMETERS:
                qubits[parameter.name].append(parameter.value)

    # Keyed by gate name (e.g. "sx", "cz"), so 1q/2q gates stay distinguishable.
    gate_errors = {}

    for gate in properties.gates:
        if not all(qubit in physical_qubits for qubit in gate.qubits):
            continue

        for parameter in gate.parameters:
            if parameter.name == "gate_error":
                gate_errors.setdefault(gate.gate, []).append(parameter.value)

    return {"qubits": qubits, "gate_errors": gate_errors}


def build_metadata(qc, isa, backend, counts, shots, optimization_level, timestamp):

    metadata = {
        "experiment": qc.name,
        "timestamp": timestamp.isoformat(),
        "versions": {
            "qiskit": qiskit.__version__,
            "qiskit_aer": qiskit_aer.__version__,
            "qiskit_ibm_runtime": qiskit_ibm_runtime.__version__,
        },
        "execution": {
            "backend_mode": BACKEND_MODE,
            "backend": backend.name,
            "shots": shots,
            "optimization_level": optimization_level,
            "seed_transpiler": SEED_TRANSPILER,
        },
        "circuit": circuit_metadata(qc, isa),
        "results": {
            "counts": counts,
        },
    }

    if BACKEND_MODE != "ideal":
        metadata["execution"]["backend_name"] = BACKEND_NAME

    return metadata


def add_backend_details(metadata, noise_backend, isa, job):
    # Enrich the metadata in place with noise-model, calibration and, on real
    # hardware, the job identifiers.

    if noise_backend is None:
        return

    properties = noise_backend.properties()

    if BACKEND_MODE == "noisy":
        metadata["execution"]["noise_model"] = noise_backend.name

    calibration = get_calibration(properties, isa)

    if calibration:
        metadata["calibration"] = calibration

    if BACKEND_MODE == "hardware":
        metadata["execution"]["job_id"] = job.job_id()
        metadata["execution"]["calibration_timestamp"] = (
            properties.last_update_date.isoformat()
        )


def write_result(metadata, name, timestamp):

    os.makedirs("results", exist_ok=True)

    filename_parts = [name, BACKEND_MODE]

    if BACKEND_MODE != "ideal":
        filename_parts.append(BACKEND_NAME)

    filename_parts.append(timestamp.strftime("%Y%m%d_%H%M%S"))

    filepath = os.path.join("results", "_".join(filename_parts) + ".json")

    with open(filepath, "w") as file:
        json.dump(metadata, file, indent=4)

    print(f"Results saved to: {filepath}")


def run(qc, shots=1024, optimization_level=1):

    if len(qc.cregs) != 1:
        raise ValueError("Runner expects exactly one classical register")

    backend, noise_backend = get_backend()

    isa = transpile_circuit(qc, backend, optimization_level)

    sampler = Sampler(mode=backend)
    job = sampler.run([isa], shots=shots)

    if BACKEND_MODE == "hardware":
        print(f"Job ID: {job.job_id()}")

    counts = job.result()[0].data[qc.cregs[0].name].get_counts()

    timestamp = datetime.now()

    metadata = build_metadata(
        qc, isa, backend, counts, shots, optimization_level, timestamp
    )
    add_backend_details(metadata, noise_backend, isa, job)

    write_result(metadata, qc.name, timestamp)

    return counts, isa
