import glob
import json
import statistics
from collections import Counter


RESULT_DAYS = [
    "20260911",
    "20260923",
    "20260924",
]

DEVICES = [
    ("ibm_kingston", "Kingston"),
    ("ibm_fez", "Fez"),
    ("ibm_marrakesh", "Marrakesh"),
]

OPTIMISATION_LEVELS = [0, 1, 2, 3]
IDEAL_OUTCOMES = [0, 64, 128, 192]
MEASURED_QUBITS = 8

# Qiskit stores an outcome as a bit string: 64 -> "01000000".
IDEAL_BITSTRINGS = [format(outcome, "08b") for outcome in IDEAL_OUTCOMES]


# convert date format: "20260923" -> "2026-09-23"
def day_label(day):
    return f"{day[:4]}-{day[4:6]}-{day[6:]}"


# returns percentage of correct outcomes
def peak_probability(counts):
    all_shots = sum(counts.values())
    correct_shots = 0
    for bitstring in IDEAL_BITSTRINGS:
        correct_shots += counts.get(bitstring, 0)

    return 100 * correct_shots / all_shots


def read_run(path, day):
    with open(path) as file:
        data = json.load(file)
    execution = data["execution"]
    counts = data["results"]["counts"]
    transpiled = data["circuit"]["transpiled"]

    return {
        "day": day,
        "mode": execution["backend_mode"],
        "device": execution.get("backend_name"),
        "level": execution["optimization_level"],
        "counts": counts,
        "peak": peak_probability(counts),
        "depth": transpiled["depth"],
        "gate_counts": transpiled["gate_counts"],
        "physical_qubits": transpiled["physical_qubits"],
        "calibration": data.get("calibration"),
    }


def load_runs():
    runs = []
    for day in RESULT_DAYS:
        for path in sorted(glob.glob(f"results/{day}/shor15_compiled_*.json")):
            runs.append(read_run(path, day))
    return runs


RUNS = load_runs()


# The runs that have all the given values, e.g.
# select({"mode": "hardware", "device": device, "level": level})
def select(wanted):
    runs = []
    for run in RUNS:
        matches = True
        for field, value in wanted.items():
            if run[field] != value:
                matches = False
        if matches:
            runs.append(run)
    return runs


# ---------------------------------------------------------------------------
# Measured success
# ---------------------------------------------------------------------------


# Peak probability in percent per day: the mean over the runs of that day
def peak_per_day(mode, device, level):
    means = []
    for day in RESULT_DAYS:
        runs = select({"mode": mode, "device": device, "level": level, "day": day})
        means.append(statistics.mean(run["peak"] for run in runs))
    return means


# Counts of several runs added up: {bit string: number of shots}
def pooled_counts(runs):
    pooled = Counter()
    for run in runs:
        pooled.update(run["counts"])
    return pooled


# ---------------------------------------------------------------------------
# Expected errors from the calibration data
# ---------------------------------------------------------------------------


# Errors of all working gates of one type, optionally only on the given qubits
def working_gate_errors(gates, gate_name, only_on_qubits=None):
    errors = []
    for gate in gates:
        # IBM reports an error of exactly 1 for a gate that is out of order
        if gate["gate"] != gate_name or gate["gate_error"] == 1:
            continue
        # single-qubit gates have "qubit", two-qubit gates have "qubits"
        gate_qubits = gate["qubits"] if "qubits" in gate else [gate["qubit"]]
        if only_on_qubits is not None and not set(gate_qubits) <= only_on_qubits:
            continue
        errors.append(gate["gate_error"])
    return errors


# Expected number of errors per shot of one run, split into CZ gates,
# single-qubit gates and readout: every gate count times the mean error of
# that gate type on the qubits the circuit uses, plus the readout error of
# every measured qubit
def expected_errors(run):
    calibration = run["calibration"]  # whole device
    gate_counts = run["gate_counts"]

    # the counting register comes first in the circuit, so the first
    # MEASURED_QUBITS physical qubits are the measured ones
    layout = set(run["physical_qubits"])
    measured = set(run["physical_qubits"][:MEASURED_QUBITS])

    cz_errors = working_gate_errors(calibration["two_qubit_gates"], "cz", layout)
    sx_errors = working_gate_errors(calibration["single_qubit_gates"], "sx", layout)
    readout_errors = [
        qubit["readout_error"]
        for qubit in calibration["qubits"]
        if qubit["qubit"] in measured
    ]

    # X gates are priced at the SX error: on these devices an X is an SX
    # pulse of double length and the calibration lists the same error for both.
    single_qubit_gates = gate_counts["sx"] + gate_counts.get("x", 0)
    return {
        "cz": gate_counts["cz"] * statistics.mean(cz_errors),
        "single_qubit": single_qubit_gates * statistics.mean(sx_errors),
        "readout": sum(readout_errors),  # one readout per measured qubit
    }


# Expected errors per shot on hardware, the mean over the days. Circuit and
# calibration are the same in all runs of a day, so one run per day is enough.
def mean_expected_errors(device, level):
    per_day = []
    for day in RESULT_DAYS:
        first_run = select(
            {"mode": "hardware", "device": device, "level": level, "day": day}
        )[0]
        per_day.append(expected_errors(first_run))
    return {
        "cz": statistics.mean(errors["cz"] for errors in per_day),
        "single_qubit": statistics.mean(errors["single_qubit"] for errors in per_day),
        "readout": statistics.mean(errors["readout"] for errors in per_day),
    }


# ---------------------------------------------------------------------------
# Calibration of a whole device
# ---------------------------------------------------------------------------


# The calibration all hardware runs of a device share on one day
def hardware_calibration(device, day):
    runs = select({"mode": "hardware", "device": device, "day": day})
    timestamps = {run["calibration"]["calibration_timestamp"] for run in runs}
    assert len(timestamps) == 1, f"{device} {day}: several calibrations {timestamps}"
    return runs[0]["calibration"]


# The calibration of the noise model. It is a fixed snapshot of the device,
# the same in every noisy run, so the first one is enough.
def noise_model_calibration(device):
    return select({"mode": "noisy", "device": device})[0]["calibration"]


# One number per quantity: the median over all qubits (T1, T2, readout) or
# over all gates (SX and X, CZ) of the device. The median is used because a
# few very bad qubits would pull a mean far off. Left out: qubits without a
# value for that quantity, gates that are out of order.
def calibration_medians(calibration):
    qubits = calibration["qubits"]
    single_qubit_gates = calibration["single_qubit_gates"]

    def median_of(key):
        return statistics.median(
            qubit[key] for qubit in qubits if qubit[key] is not None
        )

    return {
        "T1_us": median_of("T1_us"),
        "T2_us": median_of("T2_us"),
        "readout": median_of("readout_error"),
        "single_qubit": statistics.median(
            working_gate_errors(single_qubit_gates, "sx")
            + working_gate_errors(single_qubit_gates, "x")
        ),
        "cz": statistics.median(
            working_gate_errors(calibration["two_qubit_gates"], "cz")
        ),
    }
