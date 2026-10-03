import os
import statistics

import matplotlib

matplotlib.use("Agg")  # write files only, no window
import matplotlib.font_manager
import matplotlib.patheffects
import matplotlib.pyplot as plt

from calculations import (
    DEVICES,
    IDEAL_OUTCOMES,
    OPTIMISATION_LEVELS,
    RESULT_DAYS,
    calibration_medians,
    day_label,
    hardware_calibration,
    mean_expected_errors,
    noise_model_calibration,
    peak_per_day,
    pooled_counts,
    select,
)

FIGURES_DIR = "results/experiment1/figures"
TABLES_DIR = "results/experiment1/tables"

GREY = "#d4d4d4"
DARK_GREY = "#8a8985"
BLUE = "#2171b5"
INK = "#0b0b0b"

matplotlib.font_manager.fontManager.addfont(
    os.path.join(os.path.dirname(__file__), "..", "fonts", "lmroman10-regular.otf")
)

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Latin Modern Roman", "CMU Serif", "DejaVu Serif"],
        "mathtext.fontset": "cm",
        "font.size": 10,
        "axes.titlesize": 10,
        "legend.fontsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "axes.edgecolor": DARK_GREY,
        "xtick.color": DARK_GREY,
        "ytick.color": DARK_GREY,
        "xtick.labelcolor": INK,
        "ytick.labelcolor": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": "#e4e3df",
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "legend.frameon": False,
        "savefig.bbox": "tight",
    }
)


# One panel per device, side by side with a shared y axis
def device_panels(xlabel="Optimisation level"):
    # constrained layout: the legend fits in one row directly above the panels
    fig, axes = plt.subplots(
        1, 3, figsize=(6.2, 2.5), sharey=True, layout="constrained"
    )
    for ax, (_, name) in zip(axes, DEVICES):
        ax.set_title(name)
        ax.set_xlabel(xlabel)
        ax.set_xticks(OPTIMISATION_LEVELS)
    return fig, axes


# One stacked bar per optimisation level. segments lists (key, label, colour)
# from bottom to top, values_per_level holds one {key: height} per level.
def stacked_bars(ax, segments, values_per_level, edge_width):
    bottom = [0.0] * len(OPTIMISATION_LEVELS)
    for key, label, colour in segments:
        heights = [values[key] for values in values_per_level]
        ax.bar(
            OPTIMISATION_LEVELS,
            heights,
            0.6,
            bottom=bottom,
            color=colour,
            edgecolor="white",
            lw=edge_width,
            label=label,
        )
        # the next segment starts on top of this one
        bottom = [b + h for b, h in zip(bottom, heights)]


# One legend for the whole figure, above the panels
def legend_above(fig, handles, labels, max_columns=5):
    # "outside" makes constrained layout reserve the space above the panels;
    # more entries than fit in one row wrap into a second one
    fig.legend(
        handles, labels, loc="outside upper center", ncol=min(len(labels), max_columns)
    )


# Writes the figure as <name>.pdf and closes it
def save_figure(fig, name):
    os.makedirs(FIGURES_DIR, exist_ok=True)
    fig.savefig(f"{FIGURES_DIR}/{name}.pdf")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 1 (success.pdf): peak probability, noise model vs. hardware
#
# Mean over all days (a day is the mean of its five runs). The spread over
# the days is not drawn; it is listed in success.tex.
# ---------------------------------------------------------------------------


# success.pdf
def plot_peak_probability():
    fig, axes = device_panels()
    for ax, (device, _) in zip(axes, DEVICES):
        for mode, colour, line_style, label in (
            ("noisy", DARK_GREY, "--", "Noise model"),
            ("hardware", BLUE, "-", "Hardware"),
        ):
            means = [
                statistics.mean(peak_per_day(mode, device, level))
                for level in OPTIMISATION_LEVELS
            ]
            ax.plot(
                OPTIMISATION_LEVELS,
                means,
                marker="o",
                ls=line_style,
                lw=1.2,
                markersize=5.5,
                color=colour,
                markeredgecolor="white",
                markeredgewidth=0.6,
                label=label,
                zorder=2,
            )
        ax.set_xlim(-0.35, 3.35)
    axes[0].set_ylabel("Peak probability (%)")
    axes[0].set_ylim(0, 100)
    legend_above(fig, *axes[0].get_legend_handles_labels())
    save_figure(fig, "success")


# ---------------------------------------------------------------------------
# Figure 2 (outcomes.pdf): how the hardware shots split over the outcomes
#
# The blue segments together are the hardware peak probability. A short line
# across each bar marks the peak probability of the noise model (mean over the
# days, as in success.pdf), so both can be compared directly.
# ---------------------------------------------------------------------------

OUTCOME_SEGMENTS = [
    (0, "Outcome 0", "#08306b"),
    (64, "Outcome 64", "#2171b5"),
    (128, "Outcome 128", "#6baed6"),
    (192, "Outcome 192", "#a3d0f5"),  # saturated enough to stand apart from the grey
    ("incorrect", "Incorrect outcomes", "#e0e0e0"),
]


# Share of shots on each ideal outcome, plus the rest, in percent
def hardware_outcome_shares(device, level):
    runs = select({"mode": "hardware", "device": device, "level": level})
    counts = pooled_counts(runs)
    all_shots = sum(counts.values())
    shares = {}
    for outcome in IDEAL_OUTCOMES:
        shares[outcome] = 100 * counts.get(format(outcome, "08b"), 0) / all_shots
    shares["incorrect"] = 100 - sum(shares.values())  # every other outcome
    return shares


# outcomes.pdf
def plot_outcome_shares():
    fig, axes = device_panels()
    for ax, (device, _) in zip(axes, DEVICES):
        shares = [
            hardware_outcome_shares(device, level) for level in OPTIMISATION_LEVELS
        ]
        stacked_bars(ax, OUTCOME_SEGMENTS, shares, edge_width=0.5)

        noise_model = [
            statistics.mean(peak_per_day("noisy", device, level))
            for level in OPTIMISATION_LEVELS
        ]
        ax.hlines(
            noise_model,
            [level - 0.38 for level in OPTIMISATION_LEVELS],
            [level + 0.38 for level in OPTIMISATION_LEVELS],
            colors="#52514e",
            lw=1.0,
            label="Noise model",
            zorder=3,
            # white outline, so the line stays visible on the dark segments
            path_effects=[
                matplotlib.patheffects.Stroke(linewidth=2.2, foreground="white"),
                matplotlib.patheffects.Normal(),
            ],
        )
    axes[0].set_ylabel("Share of shots (%)")
    axes[0].set_ylim(0, 100)
    # matplotlib lists the noise model line first; move it behind the outcomes.
    # six entries: two rows of three
    handles, labels = axes[0].get_legend_handles_labels()
    legend_above(fig, handles[1:] + handles[:1], labels[1:] + labels[:1], max_columns=3)
    save_figure(fig, "outcomes")


# ---------------------------------------------------------------------------
# Figure 3 (distribution.pdf): the measured distribution over all 256 outcomes
#
# Hardware, the five runs of a day pooled, for the device and level that fail
# in an unexpected way. The ideal outcomes are marked; the most frequent
# outcomes are labelled with their value, so a systematic shift of the peaks
# can be read off directly.
#
# distribution.pdf shows one day; distribution_all_days.pdf has one panel per
# day and shows that the shift differs between the days.
# ---------------------------------------------------------------------------

OUTCOME_DEVICE = "ibm_kingston"
OUTCOME_LEVEL = 3
OUTCOME_DAY = "20260924"  # the day shown in the main text
LABELLED_PEAKS = 4  # how many of the most frequent outcomes get a label


# Share of shots in percent for every outcome 0 .. 255
def outcome_shares(device, level, day):
    runs = select({"mode": "hardware", "device": device, "level": level, "day": day})
    counts = pooled_counts(runs)
    all_shots = sum(counts.values())
    return [
        100 * counts.get(format(outcome, "08b"), 0) / all_shots
        for outcome in range(256)
    ]


# <name>.pdf for the given days, one panel per day
def plot_outcome_distribution(days, name):
    fig, axes = plt.subplots(
        len(days),
        1,
        figsize=(6.2, 1.4 * len(days) + 0.6),
        sharex=True,
        sharey=True,
        layout="constrained",
        squeeze=False,  # always a list of panels, even for one day
    )
    axes = axes[:, 0]
    device_name = dict(DEVICES)[OUTCOME_DEVICE]
    shares_per_day = [
        outcome_shares(OUTCOME_DEVICE, OUTCOME_LEVEL, day) for day in days
    ]

    for ax, day, shares in zip(axes, days, shares_per_day):
        # ideal outcomes as thin guide lines behind the data
        for outcome in IDEAL_OUTCOMES:
            ax.axvline(outcome, color=GREY, lw=0.8, zorder=1)

        ax.bar(range(256), shares, width=1, color=BLUE, zorder=2)
        ax.set_title(
            f"{device_name}, optimisation level {OUTCOME_LEVEL}, {day_label(day)}",
            loc="left",
        )

        most_frequent = sorted(range(256), key=lambda o: shares[o], reverse=True)
        for outcome in most_frequent[:LABELLED_PEAKS]:
            ax.annotate(
                str(outcome),
                (outcome, shares[outcome]),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                fontsize=7,
                color=INK,
            )
        ax.set_ylabel("Share of shots (%)")

    axes[-1].set_xlabel("Measured outcome")
    axes[-1].set_xlim(-4, 259)  # room for the label on outcome 0
    axes[-1].set_xticks(IDEAL_OUTCOMES + [255])
    # same scale on every day, with room for the label on the highest peak
    highest = max(max(shares) for shares in shares_per_day)
    axes[0].set_ylim(0, 5 * (highest // 5 + 1))
    save_figure(fig, name)


# ---------------------------------------------------------------------------
# Figure 4 (error_budget.pdf): expected number of errors per shot
#
# Mean over the days; the calibration and hence the budget differ per day.
# ---------------------------------------------------------------------------

ERROR_SEGMENTS = [
    ("cz", "CZ gates", "#52514e"),
    ("single_qubit", "Single-qubit gates", "#9a9994"),
    ("readout", "Readout", "#d6d5d0"),
]


# error_budget.pdf
def plot_error_budget():
    fig, axes = device_panels()
    for ax, (device, _) in zip(axes, DEVICES):
        errors = [mean_expected_errors(device, level) for level in OPTIMISATION_LEVELS]
        stacked_bars(ax, ERROR_SEGMENTS, errors, edge_width=1)
    axes[0].set_ylabel(r"Expected errors $\lambda$")
    legend_above(fig, *axes[0].get_legend_handles_labels())
    save_figure(fig, "error_budget")


# ===========================================================================
# Tables (LaTeX, tabularx with booktabs)
# ===========================================================================


# A complete LaTeX table as one string
def latex_table(caption, label, column_spec, header, rows):
    return "\n".join(
        [
            r"\begin{table}[h]",
            r"\centering",
            rf"\caption{{{caption}}}",
            rf"\label{{{label}}}",
            rf"\begin{{tabularx}}{{\textwidth}}{{{column_spec}}}",
            r"\toprule",
            *header,
            r"\midrule",
            *rows,
            r"\bottomrule",
            r"\end{tabularx}",
            r"\end{table}",
        ]
    )


# "mean ± standard deviation" as a LaTeX math cell
def mean_and_deviation(values):
    return f"${statistics.mean(values):.1f} \\pm {statistics.stdev(values):.1f}$"


# Writes the table as <name>.tex
def save_table(text, name):
    os.makedirs(TABLES_DIR, exist_ok=True)
    with open(f"{TABLES_DIR}/{name}.tex", "w", encoding="utf-8") as file:
        file.write(text + "\n")


# ---------------------------------------------------------------------------
# Table 1 (transpiled.tex): size of the transpiled circuit
#
# Depth and gate counts of the circuit the hardware ran, per optimisation
# level. The transpiler adapts the circuit to each device and calibration, so
# a number can differ between devices and days; then the range "min--max" is
# shown.
# ---------------------------------------------------------------------------

TRANSPILED_GATES = ["cz", "sx", "x", "rz"]


# "$5$" if all values are equal, else "$min$--$max$"
def value_or_range(values):
    low, high = min(values), max(values)
    return f"${low}$" if low == high else f"${low}$--${high}$"


# One table row: depth and gate counts seen for a level, over all devices and days
def transpiled_row(level):
    runs = select({"mode": "hardware", "level": level})
    cells = [value_or_range([run["depth"] for run in runs])]
    for gate in TRANSPILED_GATES:
        cells.append(value_or_range([run["gate_counts"].get(gate, 0) for run in runs]))
    return f"{level} & " + " & ".join(cells) + " \\\\"


# transpiled.tex
def transpiled_table():
    return latex_table(
        caption="Experiment 1: size of the transpiled circuit per optimisation level",
        label="tab:exp1_transpiled",
        column_spec=r"@{}l*{5}{>{\centering\arraybackslash}X}@{}",
        header=[r"Optimisation level & Depth & CZ & SX & X & RZ \\"],
        rows=[transpiled_row(level) for level in OPTIMISATION_LEVELS],
    )


# ---------------------------------------------------------------------------
# Table 2 (success.tex): peak probability
#
# The numbers behind success.pdf, in percent. For the hardware the mean and
# standard deviation over the days (a day is the mean of its five runs). The
# noise model does not change between the days, so it gets its mean over all
# runs.
# ---------------------------------------------------------------------------


# success.tex
def success_table():
    rows = []
    for device, name in DEVICES:
        if rows:
            rows.append(r"\addlinespace")  # a little space between the devices
        for level in OPTIMISATION_LEVELS:
            hardware = mean_and_deviation(peak_per_day("hardware", device, level))
            noise_model = statistics.mean(peak_per_day("noisy", device, level))
            device_cell = name if level == OPTIMISATION_LEVELS[0] else ""
            rows.append(
                f"{device_cell} & {level} & {hardware} & {noise_model:.1f} \\\\"
            )

    return latex_table(
        caption="Experiment 1: peak probability in percent on hardware (mean and standard "
        f"deviation over {len(RESULT_DAYS)} days) and on the noise model",
        label="tab:exp1_success",
        column_spec=r"@{}p{1.8cm}p{0.9cm}*{2}{>{\centering\arraybackslash}X}@{}",
        header=[r"Device & Level & Hardware (mean $\pm$ SD) & Noise model \\"],
        rows=rows,
    )


# ---------------------------------------------------------------------------
# Table 3 (calibration.tex): calibration per day
#
# The medians of calibration_medians() per device and day; the last row of
# each device is the noise model.
# ---------------------------------------------------------------------------


# One table row of calibration medians
def calibration_row(device_cell, source, medians):
    return (
        f"{device_cell} & {source} & {medians['T1_us']:.0f} & {medians['T2_us']:.0f}"
        f" & {medians['readout']:.4f} & {medians['single_qubit']:.5f} & {medians['cz']:.4f} \\\\"
    )


# calibration.tex
def calibration_table():
    rows = []
    for device, name in DEVICES:
        if rows:
            rows.append(r"\addlinespace")  # a little space between the devices
        for index, day in enumerate(RESULT_DAYS):
            device_cell = name if index == 0 else ""
            medians = calibration_medians(hardware_calibration(device, day))
            rows.append(calibration_row(device_cell, day_label(day), medians))
        medians = calibration_medians(noise_model_calibration(device))
        rows.append(calibration_row("", "Noise model", medians))

    return latex_table(
        caption="Experiment 1: calibration data of the hardware per day and of the noise model",
        label="tab:exp1_calibration",
        column_spec=r"@{}p{2.2cm}p{2.4cm}*{5}{>{\centering\arraybackslash}X}@{}",
        header=[
            r" & & & & \multicolumn{3}{c}{Error rate} \\",
            r"\cmidrule(l){5-7}",
            r"Device & Day & $T_1$ (\si{\micro\second}) & $T_2$ (\si{\micro\second}) & Readout & SX, X & CZ \\",
        ],
        rows=rows,
    )


# ===========================================================================
# Write everything
# ===========================================================================

plot_peak_probability()
plot_outcome_shares()
plot_outcome_distribution([OUTCOME_DAY], "distribution")
plot_outcome_distribution(RESULT_DAYS, "distribution_all_days")
plot_error_budget()

save_table(transpiled_table(), "transpiled")
save_table(success_table(), "success")
save_table(calibration_table(), "calibration")

print("Written to", FIGURES_DIR, "and", TABLES_DIR)
