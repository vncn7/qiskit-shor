import json
import os
from datetime import datetime

import qiskit
import qiskit_aer
import qiskit_ibm_runtime
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime import SamplerV2 as Sampler
from qiskit_ibm_runtime.fake_provider import FakeFez, FakeKingston, FakeMarrakesh


# Set by docker compose
BACKEND_MODE = os.environ.get("BACKEND_MODE", "ideal").lower()
BACKEND_NAME = os.environ.get("BACKEND_NAME", "ibm_kingston")
OPTIMISATION_LEVEL = int(os.environ.get("OPTIMISATION_LEVEL", "1"))
RUN_ID = os.environ.get("RUN_ID")

SEED_TRANSPILER = 1337  # same optimisation level --> same transpiled circuit

FAKE_BACKENDS = {
    "ibm_kingston": FakeKingston,
    "ibm_fez": FakeFez,
    "ibm_marrakesh": FakeMarrakesh,
}


# ---------------------------------------------------------------------------
# Backend selection and circuit transpilation
# ---------------------------------------------------------------------------


def get_fake_backend(name):
    return FAKE_BACKENDS[name]()


def get_hardware_backend(name):
    service = QiskitRuntimeService(
        channel="ibm_quantum_platform",
        token=os.environ["IBM_TOKEN"],
    )
    return service.backend(name)


# get backend or noise model
def get_backend():
    if BACKEND_MODE == "ideal":
        print("Running on: ideal AerSimulator")
        return AerSimulator(), None

    if BACKEND_MODE == "noisy":
        fake_backend = get_fake_backend(BACKEND_NAME)
        print(f"Running on noise model of: {fake_backend.name}")
        return AerSimulator.from_backend(fake_backend), fake_backend

    if BACKEND_MODE == "hardware":
        backend = get_hardware_backend(BACKEND_NAME)
        print(f"Running on hardware: {backend.name}")
        print(f"Calibration timestamp: {backend.properties().last_update_date}")
        return backend, None

    raise ValueError(f"Unknown BACKEND_MODE: {BACKEND_MODE}")


# circuit transpilation
def transpile_circuit(qc, backend):
    pm = generate_preset_pass_manager(
        backend=backend,
        optimization_level=OPTIMISATION_LEVEL,
        seed_transpiler=SEED_TRANSPILER,
    )
    return pm.run(qc)


# ---------------------------------------------------------------------------
# result file metadata
# ---------------------------------------------------------------------------


# Physical qubit of every circuit qubit, in circuit order
def get_physical_qubits(isa):
    if isa.layout is None:
        return None
    return isa.layout.final_index_layout()


# generate circuit metadata
def circuit_metadata(qc, isa):
    return {
        "original": {
            "num_qubits": qc.num_qubits,
            "depth": qc.depth(),
            "gate_counts": dict(qc.count_ops()),
        },
        "transpiled": {
            "depth": isa.depth(),
            "gate_counts": dict(isa.count_ops()),
            "physical_qubits": get_physical_qubits(isa),
        },
    }


# get calibration data for every physical qubit
def qubit_calibration(properties):
    qubits = []
    for index, parameters in enumerate(properties.qubits):
        values = {parameter.name: parameter.value for parameter in parameters}
        qubits.append(
            {
                "qubit": index,
                "T1_us": values.get("T1"),
                "T2_us": values.get("T2"),
                "readout_error": values.get("readout_error"),
                "operational": properties.is_qubit_operational(index),
            }
        )
    return qubits


# Error and length for single-qubit gates (sx, x) on every qubit
def single_qubit_gate_calibration(properties):
    gates = []
    for gate in properties.gates:
        if gate.gate not in ("sx", "x"):
            continue
        values = {parameter.name: parameter.value for parameter in gate.parameters}
        gates.append(
            {
                "gate": gate.gate,
                "qubit": gate.qubits[0],
                "gate_error": values.get("gate_error"),
                "gate_length_ns": values.get("gate_length"),
                "operational": properties.is_gate_operational(gate.gate, gate.qubits),
            }
        )
    return gates


# Error and length of every two-qubit gate
def two_qubit_gate_calibration(properties):
    gates = []
    for gate in properties.gates:
        if len(gate.qubits) != 2:
            continue
        values = {parameter.name: parameter.value for parameter in gate.parameters}
        gates.append(
            {
                "gate": gate.gate,
                "qubits": list(gate.qubits),
                "gate_error": values.get("gate_error"),
                "gate_length_ns": values.get("gate_length"),
                "operational": properties.is_gate_operational(gate.gate, gate.qubits),
            }
        )
    return gates


# The calibration section of the result file
def calibration_metadata(properties):
    return {
        "calibration_timestamp": properties.last_update_date.isoformat(),
        "qubits": qubit_calibration(properties),
        "single_qubit_gates": single_qubit_gate_calibration(properties),
        "two_qubit_gates": two_qubit_gate_calibration(properties),
    }


# Everything that goes into the result file
def build_metadata(qc, isa, backend, fake_backend, job, counts, shots, timestamp):
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
            # key kept as is so old and new result files have the same layout
            "optimization_level": OPTIMISATION_LEVEL,
            "seed_transpiler": SEED_TRANSPILER,
        },
        "circuit": circuit_metadata(qc, isa),
        "results": {
            "counts": counts,
        },
    }
    execution = metadata["execution"]

    if RUN_ID is not None:
        execution["run_id"] = int(RUN_ID)

    if BACKEND_MODE != "ideal":
        execution["backend_name"] = BACKEND_NAME

    # Calibration: the device's at the time of the job, or the noise model's
    if BACKEND_MODE == "hardware":
        execution["job_id"] = job.job_id()
        metadata["calibration"] = calibration_metadata(job.properties())
    elif BACKEND_MODE == "noisy":
        execution["noise_model"] = fake_backend.name
        metadata["calibration"] = calibration_metadata(fake_backend.properties())

    return metadata


# ---------------------------------------------------------------------------
# Result file
# ---------------------------------------------------------------------------


# results/<date>/<experiment>_<mode>[_<device>]_opt<level>[_run<id>][_<job id>]_<time>.json
def result_path(metadata, timestamp):
    result_dir = os.path.join("results", timestamp.strftime("%Y%m%d"))
    execution = metadata["execution"]

    parts = [metadata["experiment"], BACKEND_MODE]
    if BACKEND_MODE != "ideal":
        parts.append(BACKEND_NAME)
    parts.append(f"opt{execution['optimization_level']}")
    if RUN_ID is not None:
        parts.append(f"run{RUN_ID}")
    if BACKEND_MODE == "hardware":
        parts.append(execution["job_id"])
    parts.append(timestamp.strftime("%H%M%S"))

    return os.path.join(result_dir, "_".join(parts) + ".json")


# "x": never overwrite a result, fail instead
def write_result(metadata, timestamp):
    filepath = result_path(metadata, timestamp)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "x") as file:
        json.dump(metadata, file, indent=4)
    print(f"Results saved to: {filepath}")


# Entry point for the circuit python scripts
# Transpiles, runs and saves the circuit; returns the counts and the transpiled circuit
def run(qc, shots=1024):
    if len(qc.cregs) != 1:
        raise ValueError("Runner expects exactly one classical register")

    backend, fake_backend = get_backend()
    isa = transpile_circuit(qc, backend)

    job = Sampler(mode=backend).run([isa], shots=shots)
    if BACKEND_MODE == "hardware":
        print(f"Job ID: {job.job_id()}")
    counts = job.result()[0].data[qc.cregs[0].name].get_counts()

    timestamp = datetime.now()
    metadata = build_metadata(
        qc, isa, backend, fake_backend, job, counts, shots, timestamp
    )
    write_result(metadata, timestamp)
    return counts, isa
