# -*- coding: utf-8 -*-
"""Shared matplotlib style for both papers: validated default categorical palette in fixed order,
one-hue sequential ramp, recessive grid, thin marks, 300 dpi PNG."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
MODEL_LABEL = {"qwen2.5-7b": "Qwen2.5-7B", "qwen3-8b": "Qwen3-8B", "llama3.1-8b": "Llama-3.1-8B",
               "granite3.3-8b": "Granite-3.3-8B", "olmo2-7b": "OLMo-2-7B", "qwen2.5-14b": "Qwen2.5-14B"}
MODELS = list(MODEL_LABEL)
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*"]


def setup():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 8.5, "axes.titlesize": 9, "axes.labelsize": 8.5,
        "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "axes.labelcolor": INK2, "axes.titlecolor": INK,
        "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
        "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "legend.fontsize": 7.5,
        "lines.linewidth": 1.8, "lines.markersize": 4.5, "figure.facecolor": "white", "axes.facecolor": "white",
        "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.04,
    })


def panel_label(ax, s):
    ax.text(-0.13, 1.04, s, transform=ax.transAxes, fontsize=9.5, fontweight="bold", color=INK, va="bottom")
