"""Evaluates gate G2 of protocol section 6 on the parse_log output of one node."""
import argparse
import sys

import pandas as pd

from delta_metrics import code_delta, placebo_floor, split_placebos

BASE = "smoke"
MUTANTS = ["mut_alu32", "mut_load32"]
LINES = ["sem.give", "sem.wake"]
SHIFTS = [0, 4, 8, 12]


def shifts(rows, tag):
    """Cells of one commit, one column per shift. A missing shift is an error."""
    part = rows[(rows["tag"] == tag) & rows["pad"].isin(SHIFTS)]
    table = part.groupby(["op", "pad"])["p50"].median().unstack("pad")
    if sorted(table.columns) != SHIFTS:
        raise ValueError(f"{tag} lacks a shift: {sorted(table.columns)}")
    return table


def gate(rows):
    """Compares reference R2 of each mutant with the placebo floor of the line."""
    plain, marked = split_placebos(rows)
    floor = placebo_floor(plain, marked)
    base = shifts(plain, BASE)
    out = []
    for tag in MUTANTS:
        mutant = shifts(plain, tag)
        for op in LINES:
            delta = code_delta(base.loc[op], mutant.loc[op])
            out.append({"mutant": tag, "op": op, "delta": delta, "floor": floor[op],
                        "clears": delta > floor[op]})
    return pd.DataFrame(out), floor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+", help="parse_log output, one file per node")
    args = ap.parse_args()

    passed = True
    for path in args.csv:
        table, floor = gate(pd.read_csv(path))
        print(path)
        print(table.round(4).to_string(index=False))
        print((floor * 100).round(2).sort_values(ascending=False).to_string())
        passed = passed and bool(table["clears"].all())
    print("PASS  G2" if passed else "FAIL  G2")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
