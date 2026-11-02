"""Exploratory analyses announced in protocol section 5, reported as such in the article."""
import argparse

import numpy as np
import pandas as pd
from scipy import stats

from delta_metrics import (BUILT, THRESHOLD, cells_from_rows, criteria, label_rows, layout_spread,
                           pair_table, placebo_floor, split_placebos)

THRESHOLDS = [0, 0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05]


def load(paths, without=()):
    rows = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    rows, placebos = split_placebos(rows)
    floor = placebo_floor(rows[rows.platform == "silicon"], placebos[placebos.platform == "silicon"])
    pairs = rows[rows["tag"].str.contains(":", regex=False)]
    cells = cells_from_rows(label_rows(pairs))
    return cells[~cells["pair"].isin(without)], floor


def sweep(table):
    """The emulator threshold moves, the two references stay as defined at 2 %."""
    keep = ["c3_false_alarm_built", "c4_miss_built", "c3_false_alarm_code", "c4_miss_code"]
    return pd.DataFrame([{"threshold": t, **{k: criteria(table, t)[k] for k in keep}}
                         for t in THRESHOLDS])


def cost_of_instruction(cells, table):
    """Cycles gained per instruction gained, as compiled, where Renode sees a change."""
    built = cells[cells.layout == BUILT]
    wide = built.pivot_table(index=["pair", "op"], columns=["platform", "side"], values="value")
    gained = wide["silicon"]["child"] - wide["silicon"]["parent"]
    added = wide["renode"]["child"] - wide["renode"]["parent"]
    out = pd.DataFrame({"cycles": gained, "instructions": added}).reset_index()
    out = out[out["instructions"] != 0]
    return out.assign(per_instruction=out["cycles"] / out["instructions"])


def operation_table(cells, table, floor):
    """One row per operation: weight, cost, sensitivity to layout, and what Renode misses."""
    base = cells[(cells.layout == BUILT) & (cells.side == "parent")]
    base = base.pivot_table(index=["pair", "op"], columns="platform", values="value")
    out = pd.DataFrame({"cycles": base["silicon"].groupby("op").median(),
                        "instructions": base["renode"].groupby("op").median()})
    out["cycles_per_instruction"] = (base["silicon"] / base["renode"]).groupby("op").median()
    out["layout_spread"] = layout_spread(cells).groupby("op")["spread"].median()
    out["floor"] = floor
    moved = table[table["truth_built"] != 0]
    missed = moved[moved["delta_renode"].abs() < THRESHOLD]
    out["moved"] = moved.groupby("op").size().reindex(out.index, fill_value=0)
    out["missed"] = missed.groupby("op").size().reindex(out.index, fill_value=0)
    changed = table[table["delta_silicon"] != 0]
    error = (changed["delta_silicon"] - changed["delta_renode"]).abs()
    out["changed"] = changed.groupby("op").size().reindex(out.index, fill_value=0)
    out["median_error"] = error.groupby(changed["op"]).median()
    return out.reset_index()


def cell_classes(table):
    """Splits the cells that move on the board by what Renode says about them."""
    changed = table[table["delta_silicon"] != 0]
    delta, built = changed["delta_renode"], changed["delta_silicon"]
    return {"changed": len(changed), "renode_zero": int((delta == 0).sum()),
            "same_sign": int((np.sign(delta) == np.sign(built)).sum()),
            "opposite_sign": int((delta * built < 0).sum())}


def layout_only(table):
    """Cells past 2 % as compiled that Renode misses, split by the reference R2."""
    moved = table[table["truth_built"] != 0]
    missed = moved[moved["delta_renode"].abs() < THRESHOLD]
    return {"moved": len(moved), "missed": len(missed),
            "missed_below_floor": int((missed["truth_code"] == 0).sum()),
            "missed_above_floor": int((missed["truth_code"] != 0).sum())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+", help="parse_log output of both platforms")
    ap.add_argument("--without", nargs="*", default=[], help="pairs left out")
    ap.add_argument("--prefix", required=True, help="prefix of the CSV outputs")
    args = ap.parse_args()

    cells, floor = load(args.csv, args.without)
    table = pair_table(cells, floor)
    swept = sweep(table)
    ops = operation_table(cells, table, floor)
    cost = cost_of_instruction(cells, table)
    swept.to_csv(f"{args.prefix}_sweep.csv", index=False)
    ops.to_csv(f"{args.prefix}_ops.csv", index=False)
    cost.to_csv(f"{args.prefix}_cost.csv", index=False)

    print(swept.round(4).to_string(index=False))
    print(ops.round(4).to_string(index=False))
    print("classes", cell_classes(table))
    print("layout_only", layout_only(table))
    print("cost median", cost["per_instruction"].median(), "cells", len(cost),
          "quartiles", cost["per_instruction"].quantile([0.25, 0.75]).tolist())
    rho = stats.spearmanr(ops["cycles_per_instruction"], ops["median_error"], nan_policy="omit")
    print("h5 cycles per instruction against median error, spearman", rho.statistic)
    rho = stats.spearmanr(ops["layout_spread"], ops["median_error"], nan_policy="omit")
    print("h5 layout spread against median error, spearman", rho.statistic)


if __name__ == "__main__":
    main()
