import glob
import json

RESULTS_DIR = "results/20260923"

# (device name in the file names, name printed in figures and tables)
DEVICES = [
    ("ibm_kingston", "Kingston"),
    ("ibm_fez", "Fez"),
    ("ibm_marrakesh", "Marrakesh"),
]

OPTIMISATION_LEVELS = [0, 1, 2, 3]

# The circuit factors 15 with base a = 2, whose period is r = 4.
# The counting register has 8 qubits, so it can show 2^8 = 256 outcomes.
# Without noise it only shows the multiples of 256 / r = 64:
IDEAL_OUTCOMES = [0, 64, 128, 192]
MEASURED_QUBITS = 8

# Qiskit stores an outcome as a bit string: 64 -> "01000000".
IDEAL_BITSTRINGS = [format(outcome, "08b") for outcome in IDEAL_OUTCOMES]


def load_runs(mode, device, level):
    device_part = "" if device is None else f"_{device}"
    pattern = f"{RESULTS_DIR}/shor15_compiled_{mode}{device_part}_opt{level}_*.json"
    return [json.load(open(path)) for path in sorted(glob.glob(pattern))]


def peak_probability(run):
    counts = run["results"]["counts"]  # {bit string: number of shots}
    shots_on_ideal = sum(counts.get(bits, 0) for bits in IDEAL_BITSTRINGS)
    all_shots = sum(counts.values())
    return shots_on_ideal / all_shots


def pooled_counts(runs):
    pooled = {}
    for run in runs:
        for bits, shots in run["results"]["counts"].items():
            pooled[bits] = pooled.get(bits, 0) + shots
    return pooled


def working_gate_errors(gates, gate_name, only_on_qubits=None):
    errors = []
    for gate in gates:
        if gate["gate"] != gate_name or gate["gate_error"] == 1:
            continue
        # single-qubit gates have "qubit", two-qubit gates have "qubits"
        gate_qubits = gate["qubits"] if "qubits" in gate else [gate["qubit"]]
        if only_on_qubits is not None and not set(gate_qubits) <= only_on_qubits:
            continue
        errors.append(gate["gate_error"])
    return errors
