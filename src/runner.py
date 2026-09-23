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
OPTIMIZATION_LEVEL = int(os.environ.get("OPTIMIZATION_LEVEL", "1"))
RUN_ID = os.environ.get("RUN_ID")
SEED_TRANSPILER = 1337  # to get same transpiled circuits per opt level


FAKE_BACKENDS = {
    "ibm_kingston": "FakeKingston",
    "ibm_fez": "FakeFez",
    "ibm_marrakesh": "FakeMarrakesh",
}


QUBIT_PARAMETERS = (
    "readout_error",
    "T1",
    "T2",
)  # Calibration parameters used in the analysis


def get_fake_backend(name):
    from qiskit_ibm_runtime import fake_provider

    return getattr(fake_provider, FAKE_BACKENDS[name])()


def get_service():
    from qiskit_ibm_runtime import QiskitRuntimeService

    return QiskitRuntimeService(
        channel="ibm_quantum_platform",
        token=os.environ["IBM_TOKEN"],
    )


def get_hardware_backend(name):
    return get_service().backend(name)


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
        "transpiled": {
            "depth": isa.depth(),
            "gate_counts": dict(isa.count_ops()),
            "physical_qubits": get_physical_qubits(isa),
        },
    }


def qubit_calibration(properties):
    qubits = []

    for index, parameters in enumerate(properties.qubits):
        values = {
            parameter.name: parameter.value
            for parameter in parameters
            if parameter.name in QUBIT_PARAMETERS
        }

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


def build_metadata(
    qc,
    isa,
    backend,
    counts,
    shots,
    optimization_level,
    timestamp,
):
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

    if RUN_ID is not None:
        metadata["execution"]["run_id"] = int(RUN_ID)

    if BACKEND_MODE != "ideal":
        metadata["execution"]["backend_name"] = BACKEND_NAME

    return metadata


def add_backend_details(metadata, noise_backend, isa, job):
    if noise_backend is None:
        return

    if BACKEND_MODE == "hardware":
        properties = job.properties()
        metadata["execution"]["job_id"] = job.job_id()
    else:
        properties = noise_backend.properties()
        metadata["execution"]["noise_model"] = noise_backend.name

    metadata["calibration"] = {
        "calibration_timestamp": properties.last_update_date.isoformat(),
        "qubits": qubit_calibration(properties),
        "single_qubit_gates": single_qubit_gate_calibration(properties),
        "two_qubit_gates": two_qubit_gate_calibration(properties),
    }


def write_result(metadata, name, timestamp):
    date_folder = timestamp.strftime("%Y%m%d")
    result_dir = os.path.join("results", date_folder)
    os.makedirs(result_dir, exist_ok=True)

    optimization_level = metadata["execution"]["optimization_level"]

    filename_parts = [
        name,
        BACKEND_MODE,
    ]

    if BACKEND_MODE != "ideal":
        filename_parts.append(BACKEND_NAME)

    filename_parts.append(f"opt{optimization_level}")

    # RUN_ID is only present for batch runs from experiment.sh
    if RUN_ID is not None:
        filename_parts.append(f"run{RUN_ID}")

    # Hardware runs additionally use the IBM job ID
    if BACKEND_MODE == "hardware":
        filename_parts.append(metadata["execution"]["job_id"])

    # Timestamp is always included
    filename_parts.append(timestamp.strftime("%H%M%S"))

    basename = "_".join(filename_parts)
    filepath = os.path.join(result_dir, basename + ".json")

    # The timestamp only resolves to seconds, so runs started in parallel
    # can produce the same name. Mode "x" fails instead of overwriting.
    duplicate = 1

    while True:
        try:
            with open(filepath, "x") as file:
                json.dump(metadata, file, indent=4)
            break
        except FileExistsError:
            filepath = os.path.join(result_dir, f"{basename}_dup{duplicate}.json")
            duplicate += 1

    print(f"Results saved to: {filepath}")


def run(
    qc,
    shots=1024,
    optimization_level=OPTIMIZATION_LEVEL,
):
    if len(qc.cregs) != 1:
        raise ValueError("Runner expects exactly one classical register")

    backend, noise_backend = get_backend()

    isa = transpile_circuit(
        qc,
        backend,
        optimization_level,
    )

    sampler = Sampler(mode=backend)
    job = sampler.run([isa], shots=shots)

    if BACKEND_MODE == "hardware":
        print(f"Job ID: {job.job_id()}")

    counts = job.result()[0].data[qc.cregs[0].name].get_counts()

    timestamp = datetime.now()

    metadata = build_metadata(
        qc,
        isa,
        backend,
        counts,
        shots,
        optimization_level,
        timestamp,
    )

    add_backend_details(
        metadata,
        noise_backend,
        isa,
        job,
    )

    write_result(
        metadata,
        qc.name,
        timestamp,
    )

    return counts, isa
