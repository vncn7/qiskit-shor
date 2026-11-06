import glob
import json
import os
import statistics
from collections import Counter

import matplotlib.lines
import matplotlib.patches
import matplotlib.pyplot as plt

from plot import save, setup_style, to_table


# ---------------------------------------------------------------------------
# Constants and data
# ---------------------------------------------------------------------------

# the only place to add a measurement day
RESULT_DAYS = ["20260911", "20260924", "20261012", "20261027"]

# "20260911" -> "2026-09-11"
DAY_LABELS = {}
for day in RESULT_DAYS:
    DAY_LABELS[day] = f"{day[:4]}-{day[4:6]}-{day[6:]}"

DEVICES = [
    ("ibm_kingston", "Kingston"),
    ("ibm_fez", "Fez"),
    ("ibm_marrakesh", "Marrakesh"),
]

LEVELS = [0, 1, 2, 3]
IDEAL_OUTCOMES = [0, 64, 128, 192]
MEASURED_QUBITS = 8  # the counting register, its qubits come first in the layout

# device, level and day of the full outcome distribution
DISTRIBUTION_DEVICE = "ibm_kingston"
DISTRIBUTION_LEVEL = 3
DISTRIBUTION_DAY = "20261012"

# device and levels of the qubit layout figure, one colour per measurement day
LAYOUT_DEVICE = "ibm_kingston"
LAYOUT_LEVELS = [2, 3]
DAY_COLOURS = ["#0072B2", "#009E73", "#D55E00", "#E69F00", "#CC79A7", "#56B4E9"]

# files every day must have: 3 devices * 4 levels * 5 runs, 1 ideal run per level
EXPECTED_FILES = {"hardware": 60, "noisy": 60, "ideal": 4}

FIGURES_DIR = "results/experiment1/figures"
TABLES_DIR = "results/experiment1/tables"


# error out if a day is incomplete
def check_day(day):
    day_dir = f"results/experiment1/runs/{day}"
    if not os.path.isdir(day_dir):
        raise FileNotFoundError(f"{day}: folder {day_dir} does not exist")
    found = {}
    for mode in EXPECTED_FILES:
        found[mode] = len(glob.glob(f"{day_dir}/shor15_compiled_{mode}_*.json"))
    if found != EXPECTED_FILES:
        raise ValueError(f"{day}: expected {EXPECTED_FILES}, found {found}")


# all result files to one dict epr run
def load_runs():
    runs = []
    for day in RESULT_DAYS:
        check_day(day)
        for path in sorted(
            glob.glob(f"results/experiment1/runs/{day}/shor15_compiled_*.json")
        ):
            with open(path) as file:
                data = json.load(file)
            runs.append(
                {
                    "day": day,
                    "mode": data["execution"]["backend_mode"],
                    "device": data["execution"].get("backend_name"),
                    "level": data["execution"]["optimization_level"],
                    "counts": data["results"]["counts"],
                    "depth": data["circuit"]["transpiled"]["depth"],
                    "gate_counts": data["circuit"]["transpiled"]["gate_counts"],
                    "physical_qubits": data["circuit"]["transpiled"]["physical_qubits"],
                    "calibration": data.get("calibration"),
                }
            )
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


# positions of the 156 Heron r2 qubits: 8 rows of 16, connected by 4 bridge
# qubits between each pair of rows, based on the IBM topology diagram
def heron_positions():
    positions = {}  # {qubit: (x, y)}
    for row in range(8):
        for column in range(16):
            positions[20 * row + column] = (column, -2 * row)
    for gap in range(7):
        columns = [3, 7, 11, 15] if gap % 2 == 0 else [1, 5, 9, 13]
        for index, column in enumerate(columns):
            positions[20 * gap + 16 + index] = (column, -2 * gap - 1)
    return positions


# couplings of the chip: along each row and through the bridge qubits
def heron_couplings():
    couplings = []  # [(qubit, qubit)]
    for row in range(8):
        for column in range(15):
            couplings.append((20 * row + column, 20 * row + column + 1))
    for gap in range(7):
        columns = [3, 7, 11, 15] if gap % 2 == 0 else [1, 5, 9, 13]
        for index, column in enumerate(columns):
            bridge = 20 * gap + 16 + index
            couplings.append((20 * gap + column, bridge))
            couplings.append((bridge, 20 * (gap + 1) + column))
    return couplings


# ---------------------------------------------------------------------------
# transpiled.tex: depth and gate counts of the transpiled circuit per level
# ---------------------------------------------------------------------------


def table_transpiled(runs):
    # 1. collect: values of all hardware runs per level
    values = {}  # {level: {"depth": [...], "cz": [...], ...}}
    for level in LEVELS:
        values[level] = {"depth": [], "cz": [], "sx": [], "x": [], "rz": []}
    for run in runs:
        if run["mode"] != "hardware":
            continue
        values[run["level"]]["depth"].append(run["depth"])
        for gate in ["cz", "sx", "x", "rz"]:
            values[run["level"]][gate].append(run["gate_counts"].get(gate, 0))

    # 2. calculate: min and max per cell, one number if all runs agree
    rows = []
    for level in LEVELS:
        cells = []
        for key in ["depth", "cz", "sx", "x", "rz"]:
            low = min(values[level][key])
            high = max(values[level][key])
            if low == high:
                cells.append(f"${low}$")
            else:
                cells.append(f"${low}$--${high}$")
        rows.append(f"{level} & " + " & ".join(cells) + " \\\\")

    # 3. write
    to_table(
        f"{TABLES_DIR}/transpiled.tex",
        caption="Size of the transpiled circuit per optimisation level",
        label="tab:exp1_transpiled",
        column_spec=r"@{}l*{5}{c}@{}",
        header=[r"Optimisation level & Depth & CZ & SX & X & RZ \\"],
        rows=rows,
    )


# ---------------------------------------------------------------------------
# exp1_outcomes.pdf: share of hardware shots per ideal outcome, noise model as line
# ---------------------------------------------------------------------------


def figure_outcomes(runs):
    # 1. collect: pool the counts of the hardware runs per device and level over all days,
    #    share of the hardware and noise model runs per device, level and day
    hardware_counts = {}  # {(device, level): Counter}
    hardware_shares = {}  # {(device, level, day): [share per run]}
    noisy_shares = {}  # {(device, level, day): [share per run]}
    for run in runs:
        key = (run["device"], run["level"])
        if run["mode"] == "hardware":
            if key not in hardware_counts:
                hardware_counts[key] = Counter()
            hardware_counts[key].update(run["counts"])
            day_key = (run["device"], run["level"], run["day"])
            if day_key not in hardware_shares:
                hardware_shares[day_key] = []
            hardware_shares[day_key].append(share(run["counts"]))
        if run["mode"] == "noisy":
            day_key = (run["device"], run["level"], run["day"])
            if day_key not in noisy_shares:
                noisy_shares[day_key] = []
            noisy_shares[day_key].append(share(run["counts"]))

    # 2. calculate: share per ideal outcome from the pooled counts, the rest is incorrect;
    #    hardware spread: standard deviation of the daily means of the ideal share
    #    (same runs and shots every day, so pooled share = mean of the daily means);
    #    noise model: mean of the runs of a day, then mean over the days
    segments = {}  # {(device, level): {0: ..., 64: ..., 128: ..., 192: ..., "incorrect": ...}}
    for key, counts in hardware_counts.items():
        shares = {}
        for outcome in IDEAL_OUTCOMES:
            shares[outcome] = share(counts, [outcome])
        shares["incorrect"] = 100 - sum(shares.values())
        segments[key] = shares
    spread = {}  # {(device, level): sd of the daily means}
    noise_model = {}  # {(device, level): share}
    for device, _ in DEVICES:
        for level in LEVELS:
            hardware_day_means = []
            for day in RESULT_DAYS:
                hardware_day_means.append(
                    statistics.mean(hardware_shares[(device, level, day)])
                )
            spread[(device, level)] = statistics.stdev(hardware_day_means)
            day_means = []
            for day in RESULT_DAYS:
                day_means.append(statistics.mean(noisy_shares[(device, level, day)]))
            noise_model[(device, level)] = statistics.mean(day_means)

    # 3. write
    bar_segments = [
        (0, "Outcome 0", "#08306b"),
        (64, "Outcome 64", "#2171b5"),
        (128, "Outcome 128", "#6baed6"),
        (192, "Outcome 192", "#a3d0f5"),
        ("incorrect", "Incorrect outcomes", "#e0e0e0"),
    ]
    fig, axes = plt.subplots(
        1, 3, figsize=(6.2, 2.5), sharey=True, layout="constrained"
    )
    for ax, (device, name) in zip(axes, DEVICES):
        ax.set_title(name)
        ax.set_xlabel("Optimisation level")
        ax.set_xticks(LEVELS)

        bottom = [0.0] * len(LEVELS)
        for key, label, colour in bar_segments:
            heights = []
            for level in LEVELS:
                heights.append(segments[(device, level)][key])
            ax.bar(
                LEVELS,
                heights,
                0.6,
                bottom=bottom,
                color=colour,
                edgecolor="white",
                lw=0.5,
                label=label,
            )
            new_bottom = []
            for b, h in zip(bottom, heights):
                new_bottom.append(b + h)
            bottom = new_bottom

        # ideal share = top of the four ideal segments, SD across days centred on the bar,
        # above the noise model line (higher zorder)
        ideal_tops = []
        errors = []
        for level in LEVELS:
            ideal_tops.append(100 - segments[(device, level)]["incorrect"])
            errors.append(spread[(device, level)])
        ax.errorbar(
            LEVELS,
            ideal_tops,
            yerr=errors,
            fmt="none",
            ecolor="black",
            capsize=2,
            capthick=0.6,
            lw=0.6,
            label="SD across days",
            zorder=4,
        )

        # noise model as a thin line as wide as the bar, above the bars, below the error bars
        lines = []
        for level in LEVELS:
            lines.append(noise_model[(device, level)])
        ax.hlines(
            lines,
            [level - 0.30 for level in LEVELS],
            [level + 0.30 for level in LEVELS],
            colors="#9a9994",
            lw=1.2,
            linestyles="solid",
            label="Noise model",
            zorder=3.5,
        )

    axes[0].set_ylabel("Share of shots (%)")
    axes[0].set_ylim(0, 100)
    # matplotlib lists the line first, so sort the legend by label:
    # outcomes, incorrect outcomes, noise model, SD across days
    handles, labels = axes[0].get_legend_handles_labels()
    handle_by_label = {}
    for handle, label in zip(handles, labels):
        handle_by_label[label] = handle
    legend_labels = []
    for _, label, _ in bar_segments:
        legend_labels.append(label)
    legend_labels.append("Noise model")
    legend_labels.append("SD across days")
    legend_handles = []
    for label in legend_labels:
        legend_handles.append(handle_by_label[label])
    fig.legend(
        legend_handles,
        legend_labels,
        loc="outside upper center",
        ncol=4,
    )
    save(fig, f"{FIGURES_DIR}/exp1_outcomes.pdf")


# ---------------------------------------------------------------------------
# exp1_error_budget.pdf: expected errors per shot (lambda) on hardware
# ---------------------------------------------------------------------------


def figure_error_budget(runs):
    # 1. collect: first hardware run per device, level and day
    #    (all runs of a day share circuit and calibration)
    first_runs = {}  # {(device, level, day): run}
    for run in runs:
        if run["mode"] != "hardware":
            continue
        key = (run["device"], run["level"], run["day"])
        if key not in first_runs:
            first_runs[key] = run

    # 2. calculate: lambda per day, then mean over the days;
    #    spread: standard deviation of the daily sums
    budget = {}  # {(device, level): {"cz": ..., "single_qubit": ..., "readout": ...}}
    spread = {}  # {(device, level): sd of the sum}
    for device, _ in DEVICES:
        for level in LEVELS:
            per_day = []
            for day in RESULT_DAYS:
                per_day.append(expected_errors(first_runs[(device, level, day)]))
            means = {}
            for key in ["cz", "single_qubit", "readout"]:
                values = []
                for errors in per_day:
                    values.append(errors[key])
                means[key] = statistics.mean(values)
            budget[(device, level)] = means
            day_sums = []
            for errors in per_day:
                day_sums.append(sum(errors.values()))
            spread[(device, level)] = statistics.stdev(day_sums)

    # 3. write
    bar_segments = [
        ("cz", "CZ gates", "#52514e"),
        ("single_qubit", "Single-qubit gates", "#9a9994"),
        ("readout", "Readout", "#d6d5d0"),
    ]
    fig, axes = plt.subplots(
        1, 3, figsize=(6.2, 2.5), sharey=True, layout="constrained"
    )
    for ax, (device, name) in zip(axes, DEVICES):
        ax.set_title(name)
        ax.set_xlabel("Optimisation level")
        ax.set_xticks(LEVELS)

        bottom = [0.0] * len(LEVELS)
        for key, label, colour in bar_segments:
            heights = []
            for level in LEVELS:
                heights.append(budget[(device, level)][key])
            ax.bar(
                LEVELS,
                heights,
                0.6,
                bottom=bottom,
                color=colour,
                edgecolor="white",
                lw=0.5,
                label=label,
            )
            new_bottom = []
            for b, h in zip(bottom, heights):
                new_bottom.append(b + h)
            bottom = new_bottom

        # bottom is now the top of the stack = mean of the daily sums
        errors = []
        for level in LEVELS:
            errors.append(spread[(device, level)])
        ax.errorbar(
            LEVELS,
            bottom,
            yerr=errors,
            fmt="none",
            ecolor="black",
            capsize=2,
            capthick=0.6,
            lw=0.6,
            label="SD across days",
        )

    axes[0].set_ylabel(r"Circuit fault rate $\lambda$")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside upper center", ncol=4)
    save(fig, f"{FIGURES_DIR}/exp1_error_budget.pdf")


# ---------------------------------------------------------------------------
# exp1_distribution.pdf, exp1_distribution_all_days.pdf: distribution over all 256 outcomes,
# Kingston level 3, one panel per day
# ---------------------------------------------------------------------------


def figure_distribution(runs, days, path):
    # 1. collect: pool the counts of the five hardware runs per day
    counts_per_day = {}  # {day: Counter}
    for day in days:
        counts_per_day[day] = Counter()
    for run in runs:
        if run["mode"] != "hardware" or run["device"] != DISTRIBUTION_DEVICE:
            continue
        if run["level"] != DISTRIBUTION_LEVEL or run["day"] not in counts_per_day:
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
            f"{dict(DEVICES)[DISTRIBUTION_DEVICE]}, optimisation level {DISTRIBUTION_LEVEL}, {DAY_LABELS[day]}",
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
# exp1_layout_days.pdf: qubits used on Kingston per day at levels 2 and 3
# ---------------------------------------------------------------------------


def figure_layout(runs):
    # 1. collect: physical qubits of the first hardware run per level and day
    #    (all runs of a day share the circuit)
    layouts = {}  # {(level, day): [physical qubits]}
    for run in runs:
        if run["mode"] != "hardware" or run["device"] != LAYOUT_DEVICE:
            continue
        key = (run["level"], run["day"])
        if run["level"] in LAYOUT_LEVELS and key not in layouts:
            layouts[key] = run["physical_qubits"]

    # 2. calculate: which days use each qubit and each coupling,
    #    a day is stored as its index in RESULT_DAYS
    positions = heron_positions()
    couplings = heron_couplings()
    qubit_days = {}  # {(level, qubit): [day index]}
    coupling_days = {}  # {(level, (qubit, qubit)): [day index]}
    for level in LAYOUT_LEVELS:
        for qubit in positions:
            days_using = []
            for index, day in enumerate(RESULT_DAYS):
                if qubit in layouts[(level, day)]:
                    days_using.append(index)
            qubit_days[(level, qubit)] = days_using
        for a, b in couplings:
            days_using = []
            for index, day in enumerate(RESULT_DAYS):
                layout = layouts[(level, day)]
                if a in layout and b in layout:
                    days_using.append(index)
            coupling_days[(level, (a, b))] = days_using

    # 3. write
    fig, axes = plt.subplots(
        1, len(LAYOUT_LEVELS), figsize=(7.5, 3.0), layout="constrained"
    )
    radius = 0.28
    for ax, level in zip(axes, LAYOUT_LEVELS):
        # the chip in grey
        for a, b in couplings:
            (x1, y1), (x2, y2) = positions[a], positions[b]
            ax.plot([x1, x2], [y1, y2], color="#c8c8c8", lw=1.0, zorder=1)
        # used couplings, split lengthwise if several days share one
        for a, b in couplings:
            days_using = coupling_days[(level, (a, b))]
            (x1, y1), (x2, y2) = positions[a], positions[b]
            n = len(days_using)
            for k, index in enumerate(days_using):
                offset = (k - (n - 1) / 2) * (0.16 / n)
                if y1 == y2:
                    ax.plot(
                        [x1, x2],
                        [y1 + offset, y2 + offset],
                        color=DAY_COLOURS[index],
                        lw=2.4 / n,
                        zorder=2,
                        solid_capstyle="butt",
                    )
                else:
                    ax.plot(
                        [x1 + offset, x2 + offset],
                        [y1, y2],
                        color=DAY_COLOURS[index],
                        lw=2.4 / n,
                        zorder=2,
                        solid_capstyle="butt",
                    )

        for qubit, (x, y) in positions.items():
            days_using = qubit_days[(level, qubit)]
            if not days_using:
                ax.add_patch(
                    plt.Circle(
                        (x, y), radius, fc="white", ec="#b0b0b0", lw=0.5, zorder=3
                    )
                )
                continue
            n = len(days_using)
            for k, index in enumerate(days_using):
                start = 90 + 360 * k / n
                end = 90 + 360 * (k + 1) / n
                ax.add_patch(
                    matplotlib.patches.Wedge(
                        (x, y),
                        radius,
                        start,
                        end,
                        fc=DAY_COLOURS[index],
                        ec="none",
                        zorder=4,
                    )
                )
            ax.add_patch(
                plt.Circle((x, y), radius, fc="none", ec="black", lw=0.5, zorder=5)
            )
        ax.set_xlim(-0.7, 15.7)
        ax.set_ylim(-14.7, 0.7)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(f"Optimisation level {level}", y=-0.1, fontsize=10)

    # legend: one dot per day
    handles = []
    for index, day in enumerate(RESULT_DAYS):
        handles.append(
            matplotlib.lines.Line2D(
                [],
                [],
                marker="o",
                ls="none",
                ms=6,
                mfc=DAY_COLOURS[index],
                mec="black",
                mew=0.5,
                label=DAY_LABELS[day],
            )
        )
    fig.legend(handles=handles, loc="outside upper center", ncol=len(RESULT_DAYS))
    save(fig, f"{FIGURES_DIR}/exp1_layout_days.pdf")


# ---------------------------------------------------------------------------
# share_per_day.tex: share of ideal outcomes on hardware per device, level and day
# ---------------------------------------------------------------------------


def table_share_per_day(runs):
    # 1. collect: share per hardware run by device, level and day
    shares = {}  # {(device, level, day): [share per run]}
    for run in runs:
        if run["mode"] != "hardware":
            continue
        key = (run["device"], run["level"], run["day"])
        if key not in shares:
            shares[key] = []
        shares[key].append(share(run["counts"]))

    # 2. calculate: mean and standard deviation over the runs of a day
    cells = {}  # {(device, level, day): "$mean \pm sd$"}
    for key, values in shares.items():
        cells[key] = (
            f"${statistics.mean(values):.1f} \\pm {statistics.stdev(values):.1f}$"
        )

    # 3. write: one row per device and day, levels as columns, so more days
    #    make the table longer, not wider
    rows = []
    for device, name in DEVICES:
        if rows:
            rows.append(r"\midrule")
        for day in RESULT_DAYS:
            device_cell = name if day == RESULT_DAYS[0] else ""
            row = [device_cell, DAY_LABELS[day]]
            for level in LEVELS:
                row.append(cells[(device, level, day)])
            rows.append(" & ".join(row) + " \\\\")
    level_columns = []
    for level in LEVELS:
        level_columns.append(f"Level {level}")
    to_table(
        f"{TABLES_DIR}/share_per_day.tex",
        caption="Experiment 1: Ideal share per measurement day",
        label="tab:exp1_share_per_day",
        column_spec=rf"@{{\extracolsep{{\fill}}}}ll*{{{len(LEVELS)}}}{{c}}@{{}}",
        header=[
            rf" & & \multicolumn{{{len(LEVELS)}}}{{c}}{{Ideal share $S$ (\%)}} \\",
            rf"\cmidrule(l){{3-{2 + len(LEVELS)}}}",
            "Device & Day & " + " & ".join(level_columns) + " \\\\",
        ],
        rows=rows,
        width=r"\textwidth",
    )


# ---------------------------------------------------------------------------
# lambda_per_day.tex: circuit fault rate on hardware per device, level and day
# ---------------------------------------------------------------------------


def table_lambda_per_day(runs):
    # 1. collect: first hardware run per device, level and day
    #    (all runs of a day share circuit and calibration)
    first_runs = {}  # {(device, level, day): run}
    for run in runs:
        if run["mode"] != "hardware":
            continue
        key = (run["device"], run["level"], run["day"])
        if key not in first_runs:
            first_runs[key] = run

    # 2. calculate: lambda = sum of the CZ, single-qubit and readout parts
    cells = {}  # {(device, level, day): "$lambda$"}
    for key, run in first_runs.items():
        cells[key] = f"${sum(expected_errors(run).values()):.2f}$"

    # 3. write: one row per device and day, levels as columns
    rows = []
    for device, name in DEVICES:
        if rows:
            rows.append(r"\midrule")
        for day in RESULT_DAYS:
            device_cell = name if day == RESULT_DAYS[0] else ""
            row = [device_cell, DAY_LABELS[day]]
            for level in LEVELS:
                row.append(cells[(device, level, day)])
            rows.append(" & ".join(row) + " \\\\")
    level_columns = []
    for level in LEVELS:
        level_columns.append(f"Level {level}")
    to_table(
        f"{TABLES_DIR}/lambda_per_day.tex",
        caption="Experiment 1: Circuit fault rate per measurement day",
        label="tab:exp1_lambda_per_day",
        column_spec=rf"@{{\extracolsep{{\fill}}}}ll*{{{len(LEVELS)}}}{{c}}@{{}}",
        header=[
            rf" & & \multicolumn{{{len(LEVELS)}}}{{c}}{{Circuit fault rate $\lambda$}} \\",
            rf"\cmidrule(l){{3-{2 + len(LEVELS)}}}",
            "Device & Day & " + " & ".join(level_columns) + " \\\\",
        ],
        rows=rows,
        width=r"\textwidth",
    )


# ---------------------------------------------------------------------------
# calibration.tex: calibration medians per device and day, plus the noise model
# ---------------------------------------------------------------------------


def table_calibration(runs):
    # 1. collect: per device and day the calibration of the hardware runs (all runs of a day
    #    share it), per device the calibration of the noise model (fixed snapshot)
    calibrations = {}  # {(device, source): calibration}
    for run in runs:
        if run["mode"] == "hardware":
            key = (run["device"], DAY_LABELS[run["day"]])
        elif run["mode"] == "noisy":
            key = (run["device"], "Noise model")
        else:
            continue
        if key in calibrations:
            same = (
                calibrations[key]["calibration_timestamp"]
                == run["calibration"]["calibration_timestamp"]
            )
            assert same, f"{key}: several calibrations"
        else:
            calibrations[key] = run["calibration"]

    # 2. calculate: medians over the chip
    medians = {}  # {(device, source): {"T1_us": ..., ...}}
    for key, calibration in calibrations.items():
        medians[key] = calibration_medians(calibration)

    # 3. write
    rows = []
    for device, name in DEVICES:
        if rows:
            rows.append(r"\midrule")
        sources = []
        for day in RESULT_DAYS:
            sources.append(DAY_LABELS[day])
        sources.append("Noise model")
        for index, source in enumerate(sources):
            m = medians[(device, source)]
            device_cell = name if index == 0 else ""
            rows.append(
                f"{device_cell} & {source} & {m['T1_us']:.0f} & {m['T2_us']:.0f}"
                f" & {m['readout']:.4f} & {m['single_qubit']:.5f} & {m['cz']:.4f} \\\\"
            )
    to_table(
        f"{TABLES_DIR}/calibration.tex",
        caption="Experiment 1: Calibration data per measurement day",
        label="tab:exp1_calibration",
        column_spec=r"@{\extracolsep{\fill}}ll*{5}{c}@{}",
        header=[
            r" & & & & \multicolumn{3}{c}{Error rate} \\",
            r"\cmidrule(l){5-7}",
            r"Device & Day & $T_1$ (\si{\micro\second}) & $T_2$ (\si{\micro\second}) & Readout & SX, X & CZ \\",
        ],
        rows=rows,
        width=r"\textwidth",
    )


# ---------------------------------------------------------------------------
# Write everything
# ---------------------------------------------------------------------------

setup_style()
runs = load_runs()

table_transpiled(runs)
figure_outcomes(runs)
figure_error_budget(runs)
figure_distribution(runs, [DISTRIBUTION_DAY], f"{FIGURES_DIR}/exp1_distribution.pdf")
figure_distribution(runs, RESULT_DAYS, f"{FIGURES_DIR}/exp1_distribution_all_days.pdf")
figure_layout(runs)
table_share_per_day(runs)
table_lambda_per_day(runs)
table_calibration(runs)

print("Written to", FIGURES_DIR, "and", TABLES_DIR)
