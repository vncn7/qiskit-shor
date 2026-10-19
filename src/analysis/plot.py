import os

import matplotlib

matplotlib.use("Agg")  # write files only, no window
import matplotlib.font_manager
import matplotlib.pyplot as plt


# font, axes and grid for all figures
def setup_style():
    matplotlib.font_manager.fontManager.addfont(
        os.path.join(os.path.dirname(__file__), "fonts", "lmroman10-regular.otf")
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


# save table as LaTeX
def to_table(path, caption, label, column_spec, header, rows):
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        rf"\begin{{tabular}}{{{column_spec}}}",
        r"\toprule",
        *header,
        r"\midrule",
        *rows,
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")


# save figure as pdf
def save(fig, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
