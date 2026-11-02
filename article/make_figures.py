# -*- coding: utf-8 -*-
"""Builds the figures of the article from the campaign tables."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))

from delta_metrics import THRESHOLD, layout_spread, pair_table  # noqa: E402
from exploratory import load, sweep  # noqa: E402
import figstyle  # noqa: E402
from figstyle import AXIS, INK, INK2, MUTED, SERIES, panel_label, plt  # noqa: E402

RESULTS = ROOT / "results"
OUT = ROOT / "article" / "figures"
IDENTICAL = ("A005 A006 A007 A009 A012 A014 A016 A017 A018 A019 A020 A021 A022 A023 A024 "
             "B000 B001 B002 B003 B004").split()
FROZEN = ["campaign_silicon_n1.csv", "campaign_renode.csv"]
EXTENSION = ["campaign_ext_silicon_n1.csv", "campaign_ext_renode.csv"]
HEAT_LIMIT = 8.0
BLUE, ORANGE, GREEN = SERIES[0], SERIES[1], SERIES[2]


def csvs(names):
    return [RESULTS / n for n in names if (RESULTS / n).exists()]


def useful():
    cells, floor = load(csvs(FROZEN + EXTENSION), IDENTICAL)
    return cells, floor, pair_table(cells, floor)


def box(ax, x, y, w, h, text, color=AXIS, weight="normal"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.015",
                                fc="white", ec=color, lw=1.0))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=6.7, color=INK, weight=weight)


def arrow(ax, a, b):
    ax.annotate("", xy=b, xytext=a, arrowprops={"arrowstyle": "-|>", "color": INK2, "lw": 0.9})


def fig_design():
    fig, ax = plt.subplots(figsize=(7.2, 2.7))
    ax.set_xlim(-0.01, 1.01)
    ax.set_ylim(0, 1)
    ax.axis("off")
    box(ax, 0.00, 0.38, 0.15, 0.28, "Commit pair\nparent and child\nof one change")
    box(ax, 0.20, 0.66, 0.22, 0.30, "nRF52840 ELF, four shifts\n0, 4, 8, 12 bytes\nsame bytes on both arms", BLUE)
    box(ax, 0.20, 0.06, 0.22, 0.26, "mps2/an385 ELF\none image per commit\nCortex-M3 timer", GREEN)
    box(ax, 0.48, 0.80, 0.23, 0.17, "nRF52840DK, FIT IoT-LAB\nDWT CYCCNT: cycles", BLUE)
    box(ax, 0.48, 0.54, 0.23, 0.17, "Renode\nDWT CYCCNT: instructions", ORANGE)
    box(ax, 0.48, 0.10, 0.23, 0.17, "QEMU, icount\ntimer ticks: instructions", GREEN)
    box(ax, 0.77, 0.62, 0.23, 0.28, "Delta per operation\nR1: as compiled\nR2: code effect over floor")
    box(ax, 0.77, 0.10, 0.23, 0.17, "Control: QEMU\nagainst Renode")
    arrow(ax, (0.155, 0.56), (0.195, 0.76))
    arrow(ax, (0.155, 0.48), (0.195, 0.22))
    arrow(ax, (0.425, 0.85), (0.475, 0.885))
    arrow(ax, (0.425, 0.76), (0.475, 0.63))
    arrow(ax, (0.425, 0.19), (0.475, 0.19))
    arrow(ax, (0.715, 0.885), (0.765, 0.81))
    arrow(ax, (0.715, 0.63), (0.765, 0.71))
    arrow(ax, (0.715, 0.19), (0.765, 0.19))
    arrow(ax, (0.60, 0.53), (0.765, 0.25))
    fig.savefig(OUT / "fig_design.png")
    plt.close(fig)


def fig_layout():
    cells, floor = load(csvs(FROZEN))
    table = layout_spread(cells).groupby("op")["spread"]
    order = table.median().sort_values().index
    y = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(4.9, 3.5))
    ax.hlines(y, 100 * table.min()[order], 100 * table.max()[order], color=AXIS, lw=1.6, label="Range over commits")
    ax.scatter(100 * table.median()[order], y, s=26, color=BLUE, zorder=3, label="Board, median over commits")
    ax.scatter(100 * floor[order], y, s=26, marker="|", color=ORANGE, zorder=3, linewidths=1.6, label="Placebo floor")
    ax.axvline(100 * THRESHOLD, color=INK2, lw=0.9, ls="--")
    ax.text(100 * THRESHOLD + 0.2, len(order) - 0.45, "2 %", fontsize=7.5, color=INK2)
    ax.set_yticks(y, order)
    ax.set_xlabel("Spread over four shifts of the same code (%)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    fig.savefig(OUT / "fig_layout.png")
    plt.close(fig)


def signed_log(values):
    return np.sign(values) * np.log10(1 + np.abs(values))


def fig_scatter():
    _, _, table = useful()
    fig, axes = plt.subplots(1, 2, figsize=(6.9, 3.1), sharey=False)
    ticks = [-50, -10, -2, 0, 2, 10, 50]
    for ax, column, label in ((axes[0], "delta_silicon", "Board delta as compiled, R1 (%)"),
                              (axes[1], "delta_code", "Board code effect, R2 (%)")):
        x, y = signed_log(100 * table["delta_renode"]), signed_log(100 * table[column])
        at_zero = table["delta_renode"] == 0
        ax.scatter(x[~at_zero], y[~at_zero], s=14, color=BLUE, alpha=0.8, linewidths=0, label="Renode moves")
        ax.scatter(x[at_zero], y[at_zero], s=14, color=ORANGE, alpha=0.8, linewidths=0, label="Renode exactly 0")
        low, high = signed_log(-100.0), signed_log(100.0)
        ax.plot([low, high], [low, high], color=MUTED, lw=0.8)
        edge = signed_log(2.0)
        for value in (-edge, edge):
            ax.axhline(value, color=AXIS, lw=0.8, ls="--")
            ax.axvline(value, color=AXIS, lw=0.8, ls="--")
        ax.set_xticks(signed_log(np.array(ticks, float)), [str(t) for t in ticks])
        ax.set_yticks(signed_log(np.array(ticks, float)), [str(t) for t in ticks])
        ax.set_xlabel("Renode instruction delta (%)")
        ax.set_ylabel(label)
    axes[0].legend(loc="upper left")
    panel_label(axes[0], "a")
    panel_label(axes[1], "b")
    fig.tight_layout()
    fig.savefig(OUT / "fig_scatter.png")
    plt.close(fig)


def fig_sweep():
    swept = sweep(useful()[2])
    fig, axes = plt.subplots(1, 2, figsize=(6.9, 2.5), sharey=True)
    for ax, name, title in ((axes[0], "built", "As compiled, R1"), (axes[1], "code", "Code effect, R2")):
        x = 100 * swept["threshold"]
        ax.plot(x, 100 * swept[f"c4_miss_{name}"], color=BLUE, marker="o", label="Missed")
        ax.plot(x, 100 * swept[f"c3_false_alarm_{name}"], color=ORANGE, marker="s", label="False alarms")
        ax.axvline(100 * THRESHOLD, color=INK2, lw=0.9, ls="--")
        ax.axhline(20, color=AXIS, lw=0.9)
        ax.set_title(title, loc="left")
        ax.set_xlabel("Emulator threshold (%)")
        ax.set_ylim(-3, 103)
    axes[0].set_ylabel("Share of cells (%)")
    axes[0].legend(loc="center right")
    panel_label(axes[0], "a")
    panel_label(axes[1], "b")
    fig.tight_layout()
    fig.savefig(OUT / "fig_sweep.png")
    plt.close(fig)


def fig_heat():
    _, _, table = useful()
    wide = 100 * table.pivot(index="pair", columns="op", values="delta_silicon")
    zero = table.pivot(index="pair", columns="op", values="delta_renode") == 0
    ops = wide.abs().sum().sort_values(ascending=False).index
    pairs = sorted(wide.index)
    wide, zero = wide.loc[pairs, ops], zero.loc[pairs, ops]
    cmap = LinearSegmentedColormap.from_list("div", [BLUE, "#f1f0ec", ORANGE])
    fig, ax = plt.subplots(figsize=(6.9, 6.2))
    image = ax.imshow(wide.to_numpy(), cmap=cmap, aspect="auto",
                      norm=TwoSlopeNorm(vcenter=0, vmin=-HEAT_LIMIT, vmax=HEAT_LIMIT))
    rows, cols = np.nonzero(zero.to_numpy() & (wide.to_numpy() != 0))
    ax.scatter(cols, rows, s=7, color=INK, linewidths=0, label="Board moves, Renode exactly 0")
    ax.set_xticks(np.arange(len(ops)), ops, rotation=55, ha="right")
    ax.set_yticks(np.arange(len(pairs)), pairs)
    ax.tick_params(length=0)
    ax.grid(visible=False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks(np.arange(-0.5, len(ops)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(pairs)), minor=True)
    ax.grid(which="minor", color="white", lw=1.2)
    ax.tick_params(which="minor", length=0)
    bar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02, extend="both")
    bar.set_label("Board delta as compiled (%)", color=INK2)
    bar.outline.set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.07), ncol=1)
    fig.savefig(OUT / "fig_heat.png")
    plt.close(fig)


def fig_mutants():
    table = pd.read_csv(RESULTS / "mutants_silicon.csv")
    fig, ax = plt.subplots(figsize=(4.2, 2.8))
    ax.plot([0, 34], [0, 34], color=MUTED, lw=0.9, label="One cycle per instruction")
    styles = {("sem.give", "alu"): (BLUE, "o"), ("sem.give", "load"): (BLUE, "s"),
              ("sem.wake", "alu"): (ORANGE, "o"), ("sem.wake", "load"): (ORANGE, "s")}
    for (op, kind), (color, marker) in styles.items():
        g = table[(table.op == op) & (table.kind == kind)]
        ax.plot(g["n"], g["added"], color=color, marker=marker, lw=1.2, label=f"{op}, {kind}")
    ax.set_xlabel("Instructions added")
    ax.set_ylabel("Cycles added, mean over shifts")
    ax.legend(loc="upper left")
    fig.savefig(OUT / "fig_mutants.png")
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    figstyle.setup()
    fig_design()
    fig_layout()
    fig_scatter()
    fig_sweep()
    fig_heat()
    fig_mutants()


if __name__ == "__main__":
    main()
