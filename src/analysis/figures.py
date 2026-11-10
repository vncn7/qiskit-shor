import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from plot import save, setup_style


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# resource estimates for breaking RSA-2048 or ECC-256 with Shor's algorithm
# (year, physical qubits, target, architecture, label, label offset in points,
# assumes non-local connectivity)
# values read from Cain et al. 2026, Fig. 1b, except the last three; replace every
# value by the number from the original paper and add the bib key as a comment;
# TODO check the connectivity flag of every entry against Cain et al., Fig. 1b
ESTIMATES = [
    (2010, 6.5e8, "RSA", "sc", "Jones\net al.", (8, 0), False),  # TODO jones_2012
    (2014, 1.0e9, "RSA", "sc", "Fowler\net al.", (8, 0), False),  # TODO fowler_2012
    (
        2017,
        2.3e8,
        "RSA",
        "sc",
        "O'Gorman\nand Campbell",
        (-8, 0),
        False,
    ),  # TODO ogorman_2017
    (
        2019,
        1.8e8,
        "RSA",
        "sc",
        "Gheorghiu\nand Mosca",
        (8, 0),
        False,
    ),  # TODO gheorghiu_2019
    (
        2019,
        7.0e7,
        "ECC",
        "sc",
        "Gheorghiu\nand Mosca",
        (-8, 0),
        False,
    ),  # same paper, ECC-256
    (2019, 2.0e7, "RSA", "sc", "Gidney\nand Ekerå", (8, -3), False),  # TODO gidney_2021
    (2025, 5.0e7, "ECC", "sc", "Dallaire-\nDemers et al.", (-8, 0), False),  # TODO
    (2025, 2.0e7, "RSA", "na", "Zhou\net al.", (8, 0), True),  # TODO
    (
        2025,
        9.0e5,
        "RSA",
        "sc",
        "Gidney",
        (-8, 4),
        False,
    ),  # gidney_2025: 897 864
    (2025, 5.0e5, "ECC", "sc", "Babbush\net al.", (-8, -6), False),  # TODO
    (2026, 1.1e6, "RSA", "na", "Webster\net al.", (8, 0), True),  # TODO
    (2026, 1.0e5, "RSA", "sc", "Webster\net al.", (8, 0), True),  # TODO
    (
        2026,
        2.3e4,
        "RSA",
        "cat",
        "Alice\nand Bob",
        (8, 3),
        True,
    ),  # alice_bob_2026: 22 593
    (
        2026,
        1.9e4,
        "ECC",
        "ion",
        "IonQ",
        (-8, 0),
        True,
    ),  # ionq_2026: 19 397
    (
        2026,
        13255,
        "RSA",
        "na",
        "Cain\net al.",
        (8, -9),
        True,
    ),  # cain_2026: 13 255 -> 10.48550/arXiv.2603.28627
    (
        2026,
        11961,
        "ECC",
        "na",
        "",
        (0, 0),
        True,
    ),  # cain_2026: 11 961 -> 10.48550/arXiv.2603.28627
]

ARCHITECTURES = [
    ("sc", "superconducting", "#0072B2"),
    ("na", "neutral atoms", "#009E73"),
    ("ion", "trapped ions", "#D55E00"),
    ("cat", "cat qubits", "#CC79A7"),
]
COLOUR = {}
for key, _, colour in ARCHITECTURES:
    COLOUR[key] = colour

MARKER = {"RSA": "s", "ECC": "o"}

FIGURES_DIR = "results/other"


# ---------------------------------------------------------------------------
# estimates.pdf: resource estimates over time
# ---------------------------------------------------------------------------


def figure_estimates():
    fig, ax = plt.subplots(figsize=(6.2, 3.4), layout="constrained")

    # one marker per estimate, shape by target, colour by architecture
    for year, qubits, target, arch, label, offset, non_local in ESTIMATES:
        ax.plot(
            year,
            qubits,
            MARKER[target],
            ms=7,
            mfc=COLOUR[arch],
            mec="black",
            mew=0.5,
            zorder=3,
        )
        if label:
            ax.annotate(
                label + ("*" if non_local else ""),
                (year, qubits),
                xytext=offset,
                textcoords="offset points",
                fontsize=7.5,
                ha="left" if offset[0] > 0 else "right",
                va="center",
                linespacing=0.95,
            )

    ax.set_yscale("log")
    ax.set_ylim(3e3, 3e9)
    ax.set_xlim(2008.5, 2028.5)
    ax.set_xticks([2010, 2014, 2018, 2022, 2026])
    ax.set_xlabel("Year")
    ax.set_ylabel("Physical qubits")

    # full frame as in Cain et al., horizontal grid as in the other figures,
    # minor ticks off after the log scale is set, which would re-enable them,
    # then one small tick per year on the x axis
    for side in ["top", "right"]:
        ax.spines[side].set_visible(True)
    ax.grid(True, axis="y", which="major")
    ax.minorticks_off()
    ax.set_xticks(range(2009, 2029), minor=True)

    # legend: shapes first, then colours, then the connectivity note
    handles = [
        Line2D(
            [],
            [],
            marker="s",
            ls="none",
            mfc="white",
            mec="black",
            mew=0.5,
            ms=7,
            label="RSA-2048",
        ),
        Line2D(
            [],
            [],
            marker="o",
            ls="none",
            mfc="white",
            mec="black",
            mew=0.5,
            ms=7,
            label="ECC-256",
        ),
    ]
    for key, name, colour in ARCHITECTURES:
        handles.append(Patch(facecolor=colour, label=name))
    handles.append(
        Line2D(
            [],
            [],
            marker="$*$",
            ls="none",
            color="black",
            ms=5,
            mew=0,
            label="assumes non-local connectivity",
        )
    )
    ax.legend(
        handles=handles,
        loc="lower left",
        fontsize=7.5,
        frameon=True,
        edgecolor="#8a8985",
        fancybox=False,
        ncol=1,
    )
    save(fig, f"{FIGURES_DIR}/estimates.pdf")


# ---------------------------------------------------------------------------
# Write everything
# ---------------------------------------------------------------------------

setup_style()
figure_estimates()

print("Written to", FIGURES_DIR)
