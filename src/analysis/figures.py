import glob
import json
import os
import statistics as st

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager
import matplotlib.pyplot as plt

RESULTS = "results/20260911"
OUT = "src/analysis/exp1/figures"

CHIPS = [("kingston", "Kingston"), ("fez", "Fez"), ("marrakesh", "Marrakesh")]
LEVELS = [0, 1, 2, 3]

# a = 2, r = 4, 8 counting qubits: the ideal outcomes are 0, 64, 128 and 192.
PEAKS = ["00000000", "01000000", "10000000", "11000000"]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def runs(chip, mode, level):
    """All result files of one configuration, e.g. runs("fez", "hardware", 2)."""
    files = sorted(glob.glob(f"{RESULTS}/{chip}/*{mode}*opt{level}_*.json"))
    return [json.load(open(f)) for f in files]


def peak_probability(run):
    """Share of shots on the four ideal outcomes."""
    counts = run["results"]["counts"]
    return sum(counts.get(p, 0) for p in PEAKS) / sum(counts.values())


# Sanity check: the ideal simulation must put every shot on the ideal outcomes.
for path in glob.glob(f"{RESULTS}/*/*ideal*.json"):
    assert peak_probability(json.load(open(path))) > 0.999, (
        f"{path}: shots outside the peaks"
    )


# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------

# Latin Modern ships with the repository, so the figures look the same everywhere.
matplotlib.font_manager.fontManager.addfont(
    os.path.join(os.path.dirname(__file__), "fonts", "lmroman10-regular.otf")
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


def three_panels():
    """One panel per device, levels 0 to 3 on the x axis."""
    fig, axes = plt.subplots(1, 3, figsize=(6.2, 2.5), sharey=True)
    for ax, (_, name) in zip(axes, CHIPS):
        ax.set_title(name)
        ax.set_xticks(LEVELS)
        ax.set_xlabel("Optimisation level")
    return fig, axes


def save(fig, axes, name, columns):
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="lower center", ncol=columns, bbox_to_anchor=(0.5, 1.0)
    )
    fig.tight_layout()
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(f"{OUT}/{name}.pdf")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 1: peak probability, noise model vs. hardware (mean over five runs)
# ---------------------------------------------------------------------------

fig, axes = three_panels()
width = 0.38
for ax, (chip, _) in zip(axes, CHIPS):
    for shift, mode, colour, label in (
        (-width / 2, "noisy", "#d4d4d4", "Noise model"),
        (+width / 2, "hardware", "#2171b5", "Hardware"),
    ):
        means = [
            100 * st.mean(peak_probability(r) for r in runs(chip, mode, level))
            for level in LEVELS
        ]
        ax.bar(
            [level + shift for level in LEVELS],
            means,
            width,
            color=colour,
            edgecolor="none",
            label=label,
        )
axes[0].set_ylabel("Peak probability (%)")
axes[0].set_ylim(0, 100)
save(fig, axes, "success", columns=2)


# ---------------------------------------------------------------------------
# Figure 2: share of hardware shots on each ideal outcome (all five runs together)
# ---------------------------------------------------------------------------

segments = [
    ("Outcome 0", "#08306b"),
    ("Outcome 64", "#2171b5"),
    ("Outcome 128", "#6baed6"),
    ("Outcome 192", "#c6dbef"),
    ("Incorrect outcomes", "#e0e0e0"),
]


def outcome_shares(chip, level):
    """[share of 0, 64, 128, 192, incorrect] in percent, all five runs added up."""
    counts = {}
    for r in runs(chip, "hardware", level):
        for bits, n in r["results"]["counts"].items():
            counts[bits] = counts.get(bits, 0) + n
    total = sum(counts.values())
    on_peaks = [100 * counts.get(p, 0) / total for p in PEAKS]
    return on_peaks + [100 - sum(on_peaks)]


fig, axes = three_panels()
for ax, (chip, _) in zip(axes, CHIPS):
    shares = [
        outcome_shares(chip, level) for level in LEVELS
    ]  # one list of five values per level
    bottom = [0.0] * len(LEVELS)
    for j, (label, colour) in enumerate(segments):
        heights = [shares[i][j] for i in range(len(LEVELS))]
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
        bottom = [b + h for b, h in zip(bottom, heights)]
axes[0].set_ylabel("Share of shots (%)")
axes[0].set_ylim(0, 100)
save(fig, axes, "outcomes", columns=3)


# ---------------------------------------------------------------------------
# Figure 3: expected errors lambda = number of operations x mean error rate
# of the qubits and couplers in the layout. Decoherence is not included.
# ---------------------------------------------------------------------------

sources = [
    ("CZ gates", "#52514e"),
    ("Single-qubit gates", "#9a9994"),
    ("Readout", "#d6d5d0"),
]


def expected_errors(chip, level):
    """[CZ, single-qubit, readout] contribution to lambda for one configuration."""
    run = runs(chip, "hardware", level)[
        0
    ]  # circuit and calibration are the same in all five runs
    gates = run["circuit"]["transpiled"]["gate_counts"]
    cal = run["calibration"]
    return [
        gates["cz"] * st.mean(cal["gate_errors"]["cz"]),
        (gates["sx"] + gates.get("x", 0)) * st.mean(cal["gate_errors"]["sx"]),
        8 * st.mean(cal["qubits"]["readout_error"]),  # 8 measured counting qubits
    ]


fig, axes = three_panels()
for ax, (chip, _) in zip(axes, CHIPS):
    errors = [expected_errors(chip, level) for level in LEVELS]
    bottom = [0.0] * len(LEVELS)
    for j, (label, colour) in enumerate(sources):
        heights = [errors[i][j] for i in range(len(LEVELS))]
        ax.bar(
            LEVELS,
            heights,
            0.6,
            bottom=bottom,
            color=colour,
            edgecolor="white",
            lw=1,
            label=label,
        )
        bottom = [b + h for b, h in zip(bottom, heights)]
axes[0].set_ylabel(r"Expected errors $\lambda$")
save(fig, axes, "error_budget", columns=3)

print("Figures written to", OUT)
