import os
import statistics

import matplotlib

matplotlib.use("Agg")  # write files only, no window
import matplotlib.font_manager
import matplotlib.pyplot as plt

from experiment_data import (
    DEVICES,
    IDEAL_BITSTRINGS,
    MEASURED_QUBITS,
    OPTIMISATION_LEVELS,
    load_runs,
    peak_probability,
    pooled_counts,
    working_gate_errors,
)

OUTPUT_DIR = "src/analysis/experiment1/figures"


# ---------------------------------------------------------------------------
# Sanity check: without noise, every shot must give an ideal outcome.
# If not, the circuit or the list of ideal outcomes is wrong.
# ---------------------------------------------------------------------------

for level in OPTIMISATION_LEVELS:
    for run in load_runs("ideal", None, level):
        assert peak_probability(run) > 0.999, f"level {level}: shots outside the peaks"


# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------

GREY = "#d4d4d4"
BLUE = "#2171b5"

# Latin Modern ships with the repository (src/analysis/fonts), so the figures
# look the same everywhere.
matplotlib.font_manager.fontManager.addfont(
    os.path.join(os.path.dirname(__file__), "..", "fonts", "lmroman10-regular.otf")
)

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["CMU Serif", "Latin Modern Roman", "DejaVu Serif"],
        "mathtext.fontset": "cm",
        "font.size": 10,
        "axes.titlesize": 10,
        "legend.fontsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "axes.edgecolor": "#8a8985",
        "xtick.color": "#8a8985",
        "ytick.color": "#8a8985",
        "xtick.labelcolor": "#0b0b0b",
        "ytick.labelcolor": "#0b0b0b",
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


def device_panels(layout=None):
    fig, axes = plt.subplots(1, 3, figsize=(6.2, 2.5), sharey=True, layout=layout)
    for ax, (_, name) in zip(axes, DEVICES):
        ax.set_title(name)
        ax.set_xticks(OPTIMISATION_LEVELS)
        ax.set_xlabel("Optimisation level")
    return fig, axes


def stacked_bars(ax, segments, values_per_level, edge_width):
    bottom = [0.0] * len(OPTIMISATION_LEVELS)
    for j, (label, colour) in enumerate(segments):
        heights = [values[j] for values in values_per_level]
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


def legend_above_and_save(fig, axes, name, columns):
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="lower center", ncol=columns, bbox_to_anchor=(0.5, 1.0)
    )
    fig.tight_layout()
    save(fig, name)


def save(fig, name):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fig.savefig(f"{OUTPUT_DIR}/{name}.pdf")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 1 (success.pdf): peak probability, noise model vs. hardware
# ---------------------------------------------------------------------------


def mean_peak_probability(mode, device, level):
    probabilities = [peak_probability(run) for run in load_runs(mode, device, level)]
    return 100 * statistics.mean(probabilities)


def plot_peak_probability():
    fig, axes = device_panels()
    bar_width = 0.38
    for ax, (device, _) in zip(axes, DEVICES):
        # two bars per level: noise model left of the tick, hardware right of it
        for offset, mode, colour, label in (
            (-bar_width / 2, "noisy", GREY, "Noise model"),
            (+bar_width / 2, "hardware", BLUE, "Hardware"),
        ):
            ax.bar(
                [level + offset for level in OPTIMISATION_LEVELS],
                [mean_peak_probability(mode, device, level) for level in OPTIMISATION_LEVELS],
                bar_width,
                color=colour,
                edgecolor="none",
                label=label,
            )
    axes[0].set_ylabel("Peak probability (%)")
    axes[0].set_ylim(0, 100)
    legend_above_and_save(fig, axes, "success", columns=2)


# ---------------------------------------------------------------------------
# Figure 2 (outcomes.pdf): how the hardware shots split over the outcomes
# ---------------------------------------------------------------------------

OUTCOME_SEGMENTS = [
    ("Outcome 0", "#08306b"),
    ("Outcome 64", "#2171b5"),
    ("Outcome 128", "#6baed6"),
    ("Outcome 192", "#a3d0f5"),  # saturated enough to stand apart from the grey
    ("Incorrect outcomes", "#e0e0e0"),
]


def hardware_outcome_shares(device, level):
    counts = pooled_counts(load_runs("hardware", device, level))
    all_shots = sum(counts.values())
    shares = [100 * counts.get(bits, 0) / all_shots for bits in IDEAL_BITSTRINGS]
    shares.append(100 - sum(shares))  # every other outcome is incorrect
    return shares


def plot_outcome_shares():
    # constrained layout: the legend fits in one row directly above the panels
    fig, axes = device_panels(layout="constrained")
    for ax, (device, _) in zip(axes, DEVICES):
        shares = [hardware_outcome_shares(device, level) for level in OPTIMISATION_LEVELS]
        stacked_bars(ax, OUTCOME_SEGMENTS, shares, edge_width=0.5)
    axes[0].set_ylabel("Share of shots (%)")
    axes[0].set_ylim(0, 100)
    handles, labels = axes[0].get_legend_handles_labels()
    # "outside" makes constrained layout reserve the space above the panels
    fig.legend(handles, labels, loc="outside upper center", ncol=5, frameon=False)
    save(fig, "outcomes")


# ---------------------------------------------------------------------------
# Figure 3 (error_budget.pdf): expected number of errors per shot
# ---------------------------------------------------------------------------

ERROR_SEGMENTS = [
    ("CZ gates", "#52514e"),
    ("Single-qubit gates", "#9a9994"),
    ("Readout", "#d6d5d0"),
]


def expected_errors(device, level):
    # circuit and calibration are the same in all five runs: take the first
    run = load_runs("hardware", device, level)[0]
    gate_counts = run["circuit"]["transpiled"]["gate_counts"]
    layout = set(run["circuit"]["transpiled"]["physical_qubits"])
    calibration = run["calibration"]  # whole device

    cz_errors = working_gate_errors(calibration["two_qubit_gates"], "cz", layout)
    sx_errors = working_gate_errors(calibration["single_qubit_gates"], "sx", layout)
    readout_errors = [
        qubit["readout_error"]
        for qubit in calibration["qubits"]
        if qubit["qubit"] in layout
    ]

    single_qubit_gates = gate_counts["sx"] + gate_counts.get("x", 0)
    return [
        gate_counts["cz"] * statistics.mean(cz_errors),
        single_qubit_gates * statistics.mean(sx_errors),
        MEASURED_QUBITS * statistics.mean(readout_errors),
    ]


def plot_error_budget():
    fig, axes = device_panels()
    for ax, (device, _) in zip(axes, DEVICES):
        errors = [expected_errors(device, level) for level in OPTIMISATION_LEVELS]
        stacked_bars(ax, ERROR_SEGMENTS, errors, edge_width=1)
    axes[0].set_ylabel(r"Expected errors $\lambda$")
    legend_above_and_save(fig, axes, "error_budget", columns=3)


plot_peak_probability()
plot_outcome_shares()
plot_error_budget()
print("Figures written to", OUTPUT_DIR)
