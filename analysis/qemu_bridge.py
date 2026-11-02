"""Bridge of protocol section 14: do QEMU and Renode see the same instruction deltas?"""
import argparse

import numpy as np
import pandas as pd
from scipy import stats

from delta_metrics import BUILT, THRESHOLD, cells_from_rows, direction, label_rows

TICKS_PER_INSTRUCTION = 3.2
Q1_MIN = 0.90
Q2_MIN = 0.90


def instructions(rows):
    """QEMU prints timer ticks. Rounding removes the phase of the timer, at most one tick."""
    return rows.assign(p50=(rows["p50"] / TICKS_PER_INSTRUCTION).round())


def deltas(rows):
    cells = cells_from_rows(label_rows(rows))
    built = cells[cells["layout"] == BUILT]
    wide = built.pivot_table(index=["pair", "op"], columns="side", values="value")
    return wide["child"] / wide["parent"] - 1


def bridge(qemu, renode):
    table = pd.concat({"qemu": deltas(instructions(qemu)), "renode": deltas(renode)},
                      axis=1).dropna().reset_index()
    return table


def criteria(table, threshold=THRESHOLD):
    same = direction(table["qemu"], threshold) == direction(table["renode"], threshold)
    moved = (table["qemu"] != 0) | (table["renode"] != 0)
    out = {"n": len(table), "moved": int(moved.sum()), "q1": float(np.mean(same))}
    out["q2"] = float(stats.spearmanr(table.loc[moved, "qemu"], table.loc[moved, "renode"]).statistic)
    out["pass"] = out["q1"] >= Q1_MIN and out["q2"] >= Q2_MIN
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("qemu")
    ap.add_argument("renode")
    ap.add_argument("--table", help="also write the table to this CSV")
    args = ap.parse_args()

    renode = pd.read_csv(args.renode)
    renode = renode[renode["tag"].str.contains(":", regex=False)
                    & ~renode["tag"].str.contains("/g", regex=False)]
    table = bridge(pd.read_csv(args.qemu), renode)
    if args.table:
        table.to_csv(args.table, index=False)
    print(criteria(table))


if __name__ == "__main__":
    main()
