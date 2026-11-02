"""Determinism checks of protocol section 14: identical pairs, nodes, boots and rounds."""
import argparse

import pandas as pd

from delta_metrics import CONTROL_LINES, cells_from_rows, label_rows

KEYS = ["tag", "pad", "op"]


def kernel_rows(paths):
    rows = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    return rows[~rows["op"].str.startswith(CONTROL_LINES)]


def identical_pairs(rows, pairs):
    """Every cell of a pair with identical code must give the same value on both sides."""
    labelled = rows[rows["tag"].str.contains(":", regex=False) & ~rows["tag"].str.contains("/g", regex=False)]
    cells = cells_from_rows(label_rows(labelled))
    cells = cells[cells["pair"].isin(pairs)]
    wide = cells.pivot_table(index=["pair", "layout", "op"], columns="side", values="value")
    return {"cells": len(wide), "nonzero": int((wide["parent"] != wide["child"]).sum())}


def across_nodes(reference, others):
    base = reference.groupby(KEYS)["p50"].median()
    out = {}
    for name, rows in others.items():
        other = rows.groupby(KEYS)["p50"].median()
        shared = base.index.intersection(other.index)
        out[name] = {"cells": len(shared), "different": int((base[shared] != other[shared]).sum())}
    return out


def across_rounds(rows):
    """Cells whose median moves between boots or rounds, largest first."""
    g = rows.groupby(KEYS)["p50"]
    table = pd.DataFrame({"low": g.min(), "high": g.max(), "median": g.median(), "lines": g.size()})
    table["spread"] = (table["high"] - table["low"]) / table["median"]
    moved = table[table["spread"] > 0].sort_values("spread", ascending=False)
    return len(table), moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--node1", nargs="+", required=True)
    ap.add_argument("--node2", nargs="+", default=[])
    ap.add_argument("--node3", nargs="+", default=[])
    ap.add_argument("--identical", nargs="+", required=True, help="pairs with identical code")
    ap.add_argument("--table", help="also write the cells that move to this CSV")
    args = ap.parse_args()

    rows = kernel_rows(args.node1)
    print("identical pairs", identical_pairs(rows, args.identical))
    others = {name: kernel_rows(paths) for name, paths in (("node2", args.node2), ("node3", args.node3)) if paths}
    print("across nodes", across_nodes(rows, others))
    total, moved = across_rounds(rows)
    print("image cells", total, "moving between boots or rounds", len(moved))
    print(moved.head(15).round(4).to_string())
    if args.table:
        moved.to_csv(args.table)


if __name__ == "__main__":
    main()
