"""Pull calibration data from IBM backends.

Usage:
    python src/calibration.py [backend ...]

Defaults to ibm_kingston, ibm_fez and ibm_marrakesh. Reads live hardware
by default; BACKEND_MODE=noisy uses the fake backends' calibration
snapshot instead, like the runner does.

Writes one JSON per backend with the raw data to results/calibration/.
"""

import json
import os
import sys
from datetime import datetime

from runner import QUBIT_PARAMETERS, get_fake_backend, get_hardware_backend


BACKEND_MODE = os.environ.get("BACKEND_MODE", "hardware").lower()
DEFAULT_BACKENDS = ("ibm_kingston", "ibm_fez", "ibm_marrakesh")
RESULT_DIR = os.path.join("results", "calibration")


def get_backend(name):
    if BACKEND_MODE == "hardware":
        return get_hardware_backend(name)

    if BACKEND_MODE == "noisy":
        return get_fake_backend(name)

    raise ValueError(f"Unsupported BACKEND_MODE for calibration: {BACKEND_MODE}")


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


def fetch_calibration(name, timestamp):
    backend = get_backend(name)
    properties = backend.properties()

    print(f"{backend.name}: calibration from {properties.last_update_date}")

    return {
        "backend": backend.name,
        "backend_mode": BACKEND_MODE,
        "fetched": timestamp.isoformat(),
        "calibration_timestamp": properties.last_update_date.isoformat(),
        "num_qubits": backend.num_qubits,
        "qubits": qubit_calibration(properties),
        "two_qubit_gates": two_qubit_gate_calibration(properties),
    }


def write_json(calibration, timestamp):
    filename = f"{calibration['backend']}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(RESULT_DIR, filename)

    with open(filepath, "w") as file:
        json.dump(calibration, file, indent=4)

    print(f"Raw calibration saved to: {filepath}")


def main(backends):
    timestamp = datetime.now()
    os.makedirs(RESULT_DIR, exist_ok=True)

    for name in backends:
        write_json(fetch_calibration(name, timestamp), timestamp)


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT_BACKENDS)
