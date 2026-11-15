import os

import matplotlib

matplotlib.use("Agg")  # write files only, no window
import matplotlib.font_manager
import matplotlib.pyplot as plt

# blue palette for bars, dark to light
BAR_BLUES = ["#2171B5", "#6BAED6", "#BDD7E7"]


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


# save table as LaTeX; with a width (e.g. \textwidth) as tabular* of that width,
# with a tabcolsep (e.g. 4pt) with that column spacing in this table only
def to_table(
    path, caption, label, column_spec, header, rows, width=None, tabcolsep=None
):
    if width is None:
        begin = rf"\begin{{tabular}}{{{column_spec}}}"
        end = r"\end{tabular}"
    else:
        begin = rf"\begin{{tabular*}}{{{width}}}{{{column_spec}}}"
        end = r"\end{tabular*}"
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
    ]
    if tabcolsep is not None:
        lines.append(rf"\setlength{{\tabcolsep}}{{{tabcolsep}}}")
    lines += [
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        begin,
        r"\toprule",
        *header,
        r"\midrule",
        *rows,
        r"\bottomrule",
        end,
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


# values behind a figure as text next to the PDF: figure.pdf -> figure.txt
def save_values(path, values):
    txt_path = os.path.splitext(path)[0] + ".txt"
    with open(txt_path, "w") as file:
        # one block per dict, one line per entry
        for name, entries in values.items():
            file.write(f"{name}\n")
            for key, value in entries.items():
                file.write(f"  {key}: {rounded(value)}\n")
            file.write("\n")


# round all numbers in nested dicts and lists to 3 decimals
def rounded(value):
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            result[key] = rounded(item)
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.append(rounded(item))
        return result
    return value
