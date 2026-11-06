import glob
import json
import statistics
from collections import Counter

import matplotlib.pyplot as plt

from plot import save, setup_style, to_table


# ---------------------------------------------------------------------------
# Constants and data
# ---------------------------------------------------------------------------

RUNS_DIR = "results/experiment2/runs"

# one folder per mitigation setting of the hardware runs
FOLDERS = ["raw", "twirling", "dd", "both"]

# (name, folder, source): source is the part of the results the share is taken from,
# "quasi_probabilities" = counts after the M3 readout correction
CONFIGURATIONS = [
    ("none", "raw", "counts"),
    ("PT", "twirling", "counts"),
    ("DD", "dd", "counts"),
    ("PT+DD", "both", "counts"),
    ("M3", "raw", "quasi_probabilities"),
    ("all", "both", "quasi_probabilities"),
]

# all runs are on one device and one optimisation level
DEVICE_NAME = "Kingston"
LEVEL = 2

IDEAL_OUTCOMES = [0, 64, 128, 192]
MEASURED_QUBITS = 8  # the counting register, its qubits come first in the layout

# runs every day must have in every folder
RUNS_PER_DAY = 5

FIGURES_DIR = "results/experiment2/figures"
TABLES_DIR = "results/experiment2/tables"


# "2026-10-19T09:01:28.796047" -> "20261019"
def day_of(timestamp):
    return timestamp[:10].replace("-", "")


# the measurement days, found from the timestamps of the result files
RESULT_DAYS = []
for folder in FOLDERS:
    for path in glob.glob(f"{RUNS_DIR}/{folder}/shor15_compiled_hardware_*.json"):
        with open(path) as file:
            day = day_of(json.load(file)["timestamp"])
        if day not in RESULT_DAYS:
            RESULT_DAYS.append(day)
RESULT_DAYS.sort()

# "20261019" -> "2026-10-19"
DAY_LABELS = {}
for day in RESULT_DAYS:
    DAY_LABELS[day] = f"{day[:4]}-{day[4:6]}-{day[6:]}"


# error out if a day is incomplete
def check_day(runs, day):
    expected = {}
    found = {}
    for folder in FOLDERS:
        expected[folder] = RUNS_PER_DAY
        found[folder] = 0
    for run in runs:
        if run["day"] == day:
            found[run["folder"]] += 1
    if found != expected:
        raise ValueError(f"{day}: expected {expected}, found {found}")


# all result files to one dict per run
def load_runs():
    runs = []
    for folder in FOLDERS:
        for path in sorted(
            glob.glob(f"{RUNS_DIR}/{folder}/shor15_compiled_hardware_*.json")
        ):
            with open(path) as file:
                data = json.load(file)
            runs.append(
                {
                    "day": day_of(data["timestamp"]),
                    "folder": folder,
                    "counts": data["results"]["counts"],
                    # only the runs in raw and both have them
                    "quasi_probabilities": data["results"].get("quasi_probabilities"),
                    "gate_counts": data["circuit"]["transpiled"]["gate_counts"],
                    "physical_qubits": data["circuit"]["transpiled"]["physical_qubits"],
                    "calibration": data["calibration"],
                }
            )
    for day in RESULT_DAYS:
        check_day(runs, day)
    return runs


# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------


# share = 100 * shots on the given outcomes / all shots
def share(counts, outcomes=IDEAL_OUTCOMES):
    hits = 0
    for outcome in outcomes:
        hits += counts.get(
            format(outcome, "08b"), 0
        )  # convert outcomes to 8-bit binary strings to match the keys in counts
    return 100 * hits / sum(counts.values())


# share for quasi-probabilities = 100 * sum of the values on the given outcomes
# The values of a run already sum to 1, negative values are included as they are
def quasi_share(quasi_probabilities, outcomes=IDEAL_OUTCOMES):
    total = 0
    for outcome in outcomes:
        total += quasi_probabilities.get(format(outcome, "08b"), 0)
    return 100 * total


# ideal share of a run, from its counts or from its quasi-probabilities
def ideal_share(run, source):
    if source == "counts":
        return share(run["counts"])
    return quasi_share(run["quasi_probabilities"])


# Expected errors per shot, estimated from the calibration data
#
#   expected_errors = CZ part + single-qubit part + readout part
#
#   CZ part           = number of CZ gates   * mean CZ error on the used qubits
#   single-qubit part = number of SX+X gates * mean SX error on the used qubits
#   readout part      = sum of the readout errors of the 8 measured qubits
#
# X gates count as SX gates (IBM lists the same error for both)
# A gate error == 1 -> means broken and left out
def expected_errors(run):
    calibration = run["calibration"]
    gate_counts = run["gate_counts"]
    used_qubits = set(run["physical_qubits"])
    measured_qubits = set(
        run["physical_qubits"][:MEASURED_QUBITS]
    )  # the first 8 qubits (counting register) are measured, so readout errors are only relevant here

    # mean CZ error on the used qubits
    cz_errors = []
    for gate in calibration["two_qubit_gates"]:
        is_cz = gate["gate"] == "cz"
        is_working = gate["gate_error"] != 1
        is_used = set(gate["qubits"]) <= used_qubits
        if is_cz and is_working and is_used:
            cz_errors.append(gate["gate_error"])
    mean_cz_error = statistics.mean(cz_errors)

    # mean SX error on the used qubits
    sx_errors = []
    for gate in calibration["single_qubit_gates"]:
        is_sx = gate["gate"] == "sx"
        is_working = gate["gate_error"] != 1
        is_used = gate["qubit"] in used_qubits
        if is_sx and is_working and is_used:
            sx_errors.append(gate["gate_error"])
    mean_sx_error = statistics.mean(sx_errors)

    # readout errors of the measured qubits
    readout_errors = []
    for qubit in calibration["qubits"]:
        if qubit["qubit"] in measured_qubits:
            readout_errors.append(qubit["readout_error"])

    # the three parts of error expected per shot
    n_cz = gate_counts["cz"]
    n_single = gate_counts["sx"] + gate_counts.get("x", 0)

    return {
        "cz": n_cz * mean_cz_error,
        "single_qubit": n_single * mean_sx_error,
        "readout": sum(readout_errors),
    }


# T1, T2, readout and all working gates (SX/X, CZ). Median over the qubits of the chip, ignoring broken gates (error == 1)
def calibration_medians(calibration):

    # T1 of every qubit that has a value
    t1_values = []
    for qubit in calibration["qubits"]:
        if qubit["T1_us"] is not None:
            t1_values.append(qubit["T1_us"])

    # T2 of every qubit that has a value
    t2_values = []
    for qubit in calibration["qubits"]:
        if qubit["T2_us"] is not None:
            t2_values.append(qubit["T2_us"])

    # readout error of every qubit that has a value
    readout_errors = []
    for qubit in calibration["qubits"]:
        if qubit["readout_error"] is not None:
            readout_errors.append(qubit["readout_error"])

    # error of every working SX or X gate
    single_qubit_errors = []
    for gate in calibration["single_qubit_gates"]:
        if gate["gate"] in ("sx", "x") and gate["gate_error"] != 1:
            single_qubit_errors.append(gate["gate_error"])

    # error of every working CZ gate
    cz_errors = []
    for gate in calibration["two_qubit_gates"]:
        if gate["gate"] == "cz" and gate["gate_error"] != 1:
            cz_errors.append(gate["gate_error"])

    return {
        "T1_us": statistics.median(t1_values),
        "T2_us": statistics.median(t2_values),
        "readout": statistics.median(readout_errors),
        "single_qubit": statistics.median(single_qubit_errors),
        "cz": statistics.median(cz_errors),
    }


# ---------------------------------------------------------------------------
# share_per_day.tex: share of ideal outcomes per day and configuration
# ---------------------------------------------------------------------------


def table_share_per_day(runs):
    # 1. collect: share per run by configuration and day
    shares = {}  # {(configuration, day): [share per run]}
    for name, folder, source in CONFIGURATIONS:
        for run in runs:
            if run["folder"] != folder:
                continue
            key = (name, run["day"])
            if key not in shares:
                shares[key] = []
            shares[key].append(ideal_share(run, source))

    # 2. calculate: mean and standard deviation over the runs of a day
    cells = {}  # {(configuration, day): "$mean \pm sd$"}
    for key, values in shares.items():
        cells[key] = (
            f"${statistics.mean(values):.1f} \\pm {statistics.stdev(values):.1f}$"
        )

    # 3. write: one row per day, configurations as columns
    rows = []
    for day in RESULT_DAYS:
        row = [DAY_LABELS[day]]
        for name, _, _ in CONFIGURATIONS:
            row.append(cells[(name, day)])
        rows.append(" & ".join(row) + " \\\\")
    configuration_columns = []
    for name, _, _ in CONFIGURATIONS:
        configuration_columns.append(name)
    to_table(
        f"{TABLES_DIR}/share_per_day.tex",
        caption="Experiment 2: Ideal share per measurement day and configuration",
        label="tab:exp2_share_per_day",
        column_spec=rf"@{{\extracolsep{{\fill}}}}l*{{{len(CONFIGURATIONS)}}}{{c}}@{{}}",
        header=[
            rf" & \multicolumn{{{len(CONFIGURATIONS)}}}{{c}}{{Ideal share $S$ (\%)}} \\",
            rf"\cmidrule(l){{2-{1 + len(CONFIGURATIONS)}}}",
            "Day & " + " & ".join(configuration_columns) + " \\\\",
        ],
        rows=rows,
        width=r"\textwidth",
    )


# ---------------------------------------------------------------------------
# calibration.tex: calibration medians per day
# ---------------------------------------------------------------------------


def table_calibration(runs):
    # 1. collect: per day the calibration of the raw runs (all runs of a day share it)
    calibrations = {}  # {day: calibration}
    for run in runs:
        if run["folder"] != "raw":
            continue
        day = run["day"]
        if day in calibrations:
            same = (
                calibrations[day]["calibration_timestamp"]
                == run["calibration"]["calibration_timestamp"]
            )
            assert same, f"{day}: several calibrations"
        else:
            calibrations[day] = run["calibration"]

    # 2. calculate: medians over the chip
    medians = {}  # {day: {"T1_us": ..., ...}}
    for day, calibration in calibrations.items():
        medians[day] = calibration_medians(calibration)

    # 3. write
    rows = []
    for day in RESULT_DAYS:
        m = medians[day]
        rows.append(
            f"{DAY_LABELS[day]} & {m['T1_us']:.0f} & {m['T2_us']:.0f}"
            f" & {m['readout']:.4f} & {m['single_qubit']:.5f} & {m['cz']:.4f} \\\\"
        )
    to_table(
        f"{TABLES_DIR}/calibration.tex",
        caption="Experiment 2: Calibration data per measurement day",
        label="tab:exp2_calibration",
        column_spec=r"@{\extracolsep{\fill}}l*{5}{c}@{}",
        header=[
            r" & & & \multicolumn{3}{c}{Error rate} \\",
            r"\cmidrule(l){4-6}",
            r"Day & $T_1$ (\si{\micro\second}) & $T_2$ (\si{\micro\second}) & Readout & SX, X & CZ \\",
        ],
        rows=rows,
        width=r"\textwidth",
    )


# ---------------------------------------------------------------------------
# outcomes.pdf: mean share of ideal outcomes per configuration, one panel per day
# ---------------------------------------------------------------------------


def figure_outcomes(runs):
    # 1. collect: share per run by configuration and day
    shares = {}  # {(configuration, day): [share per run]}
    for name, folder, source in CONFIGURATIONS:
        for run in runs:
            if run["folder"] != folder:
                continue
            key = (name, run["day"])
            if key not in shares:
                shares[key] = []
            shares[key].append(ideal_share(run, source))

    # 2. calculate: mean and standard deviation over the runs of a day
    means = {}  # {(configuration, day): mean}
    spread = {}  # {(configuration, day): sd of the runs}
    for key, values in shares.items():
        means[key] = statistics.mean(values)
        spread[key] = statistics.stdev(values)

    # 3. write
    names = []
    for name, _, _ in CONFIGURATIONS:
        names.append(name)
    positions = list(range(len(CONFIGURATIONS)))
    fig, axes = plt.subplots(
        1,
        len(RESULT_DAYS),
        figsize=(6.2, 2.25),
        sharey=True,
        layout="constrained",
        squeeze=False,  # always a list of panels, even for one day
    )
    axes = axes[0]
    for ax, day in zip(axes, RESULT_DAYS):
        ax.set_title(DAY_LABELS[day])
        ax.set_xticks(positions)
        ax.set_xticklabels(names, fontsize=7)  # at 9 pt "PT+DD" runs into its neighbours

        heights = []
        errors = []
        for name in names:
            heights.append(means[(name, day)])
            errors.append(spread[(name, day)])
        ax.bar(
            positions,
            heights,
            0.6,
            color="#2171b5",
            edgecolor="white",
            lw=0.5,
        )
        ax.errorbar(
            positions,
            heights,
            yerr=errors,
            fmt="none",
            ecolor="black",
            capsize=2,
            capthick=0.6,
            lw=0.6,
        )

    axes[0].set_ylabel("Share of shots (%)")
    axes[0].set_ylim(0, 100)
    save(fig, f"{FIGURES_DIR}/outcomes.pdf")


# ---------------------------------------------------------------------------
# distribution_all_days.pdf: distribution over all 256 outcomes without mitigation,
# one panel per day
# ---------------------------------------------------------------------------


def figure_distribution(runs, days, path):
    # 1. collect: pool the counts of the five raw runs per day
    counts_per_day = {}  # {day: Counter}
    for day in days:
        counts_per_day[day] = Counter()
    for run in runs:
        if run["folder"] != "raw" or run["day"] not in counts_per_day:
            continue
        counts_per_day[run["day"]].update(run["counts"])

    # 2. calculate: share per outcome 0..255, the four most frequent outcomes, highest value
    shares_per_day = {}  # {day: [share per outcome]}
    peaks_per_day = {}  # {day: [the four most frequent outcomes]}
    highest = 0
    for day in days:
        shares = []
        for outcome in range(256):
            shares.append(share(counts_per_day[day], [outcome]))
        shares_per_day[day] = shares
        highest = max(highest, max(shares))

        peaks = []
        remaining = list(range(256))
        for _ in range(4):
            best = remaining[0]
            for outcome in remaining:
                if shares[outcome] > shares[best]:
                    best = outcome
            peaks.append(best)
            remaining.remove(best)
        peaks_per_day[day] = peaks

    # 3. write
    fig, axes = plt.subplots(
        len(days),
        1,
        # 1.485 per panel + 0.345 for the x-axis label: a panel is equally high
        # for any number of days
        figsize=(6.2, 1.485 * len(days) + 0.345),
        sharex=True,
        sharey=True,
        layout="constrained",
        squeeze=False,  # always a list of panels, even for one day
    )
    axes = axes[:, 0]
    for ax, day in zip(axes, days):
        shares = shares_per_day[day]
        for outcome in IDEAL_OUTCOMES:
            ax.axvline(outcome, color="#d4d4d4", lw=0.8, zorder=1)
        ax.bar(range(256), shares, width=1, color="#2171b5", zorder=2)
        ax.set_title(
            f"{DEVICE_NAME}, optimisation level {LEVEL}, {DAY_LABELS[day]}",
            loc="left",
        )
        for outcome in peaks_per_day[day]:
            ax.annotate(
                str(outcome),
                (outcome, shares[outcome]),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                fontsize=7,
                color="#0b0b0b",
            )
        ax.set_ylabel("Share of shots (%)")

    axes[-1].set_xlabel("Measured outcome")
    axes[-1].set_xlim(-4, 259)  # room for the label on outcome 0
    axes[-1].set_xticks(IDEAL_OUTCOMES + [255])
    # fixed y-axis, the same in experiment 1 and 2 (the ideal circuit gives 25 % per outcome)
    assert highest < 25, "a peak does not fit on the y-axis"
    axes[0].set_ylim(0, 25)
    axes[0].set_yticks([0, 10, 20])
    save(fig, path)


# ---------------------------------------------------------------------------
# Write everything
# ---------------------------------------------------------------------------

setup_style()
runs = load_runs()

table_share_per_day(runs)
table_calibration(runs)
figure_outcomes(runs)
figure_distribution(runs, RESULT_DAYS, f"{FIGURES_DIR}/distribution_all_days.pdf")

print("Written to", FIGURES_DIR, "and", TABLES_DIR)
