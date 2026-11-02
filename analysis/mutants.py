"""Positive control of protocol section 14: what one added instruction costs on the board."""
import argparse
import re

import numpy as np
import pandas as pd

BASE = "smoke"
LINES = ("sem.give", "sem.wake")
MUTANT = re.compile(r"^mut_([a-z]+)(\d+)$")


def added(rows):
    """Adds to the mean over the shifts, against the image without a mutant."""
    means = rows[rows["op"].isin(LINES)].groupby(["tag", "op", "pad"])["p50"].median()
    means = means.groupby(level=["tag", "op"]).mean()
    out = []
    for (tag, op), value in means.items():
        hit = MUTANT.match(tag)
        if hit:
            out.append({"kind": hit.group(1), "n": int(hit.group(2)), "op": op,
                        "added": value - means[(BASE, op)]})
    return pd.DataFrame(out).sort_values(["op", "kind", "n"], ignore_index=True)


def slopes(table):
    """Added units per added instruction, by least squares through the origin."""
    rows = []
    for (op, kind), g in table.groupby(["op", "kind"]):
        n = g["n"].to_numpy(float)
        rows.append({"op": op, "kind": kind,
                     "slope": float(n @ g["added"].to_numpy() / (n @ n))})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+", help="parse_log output of one platform")
    ap.add_argument("--table", help="also write the table to this CSV")
    args = ap.parse_args()

    rows = pd.concat([pd.read_csv(p) for p in args.csv], ignore_index=True)
    table = added(rows)
    if args.table:
        table.to_csv(args.table, index=False)
    print(table.to_string(index=False))
    print(slopes(table).to_string(index=False))


if __name__ == "__main__":
    main()
