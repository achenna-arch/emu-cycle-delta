"""Primary analysis of protocol section 5.

Input: rows with columns pair, side, layout, platform, op, value, where value
is one cell, the median over rounds of the p50 of an operation in one image.
"""
import argparse

import numpy as np
import pandas as pd
from scipy import stats

THRESHOLD = 0.02
N_BOOT = 2000
SEED = 20261030
BUILT = 0
PLACEBO = "/g"
OUTSIDE_HOT_PATH = "B"
CONTROL_LINES = ("calib.", "clock.")


def label_rows(rows):
    """Adds pair and side from the pair:side tag of the firmware banner."""
    parts = rows["tag"].str.split(":", expand=True)
    if parts.shape[1] != 2 or parts.isna().any(axis=None):
        raise ValueError("expected tags of the form pair:side")
    return rows.assign(pair=parts[0], side=parts[1])


def cells_from_rows(rows):
    """Reduces labelled parse_log rows to cells of the kernel operations."""
    keys = ["pair", "side", "pad", "platform", "op"]
    rows = rows[~rows["op"].str.startswith(CONTROL_LINES)]
    out = rows.groupby(keys, as_index=False)["p50"].median()
    return out.rename(columns={"pad": "layout", "p50": "value"})


def split_placebos(rows):
    marked = rows["tag"].str.contains(PLACEBO, regex=False)
    return rows[~marked], rows[marked]


def rigid_envelope(rows, tags):
    """Largest spread of each operation across the shifts of one commit."""
    cells = rows[rows["tag"].isin(tags)].groupby(["tag", "pad", "op"])["p50"].median()
    g = cells.groupby(level=["tag", "op"])
    spread = (g.max() - g.min()) / g.median()
    return spread.groupby(level="op").max()


def placebo_floor(rows, placebos):
    """Largest relative move of each operation, from a placebo or across the shifts."""
    cells = placebos.groupby(["tag", "op"], as_index=False)["p50"].median()
    built = rows[rows["pad"] == BUILT].groupby(["tag", "op"])["p50"].median()
    bases = cells["tag"].str.split(PLACEBO, regex=False).str[0]
    base = built.reindex(pd.MultiIndex.from_arrays([bases, cells["op"]])).to_numpy()
    if np.isnan(base).any():
        raise ValueError("a placebo has no image as compiled")
    moved = pd.Series(np.abs(cells["p50"].to_numpy() / base - 1)).groupby(cells["op"].to_numpy()).max()
    return pd.concat([moved, rigid_envelope(rows, bases.unique())], axis=1).max(axis=1)


def code_delta(parent, child):
    """Reference R2: the change of the mean over the shifts."""
    return np.mean(child) / np.mean(parent) - 1


def direction(delta, threshold=THRESHOLD):
    return np.where(np.abs(delta) < threshold, 0, np.sign(delta)).astype(int)


def pair_table(cells, floor=None):
    """One row per pair and operation. delta_silicon is reference R1, delta_code reference R2."""
    rows = []
    for (pair, op), g in cells.groupby(["pair", "op"]):
        rec = {"pair": pair, "op": op}
        for platform, h in g.groupby("platform"):
            built = h[h["layout"] == BUILT].groupby("side")["value"].median()
            if {"parent", "child"} <= set(built.index):
                rec[f"delta_{platform}"] = built["child"] / built["parent"] - 1
            if platform == "silicon":
                rec["delta_code"] = code_delta(h.loc[h.side == "parent", "value"],
                                               h.loc[h.side == "child", "value"])
        rows.append(rec)
    table = pd.DataFrame(rows).dropna(subset=["delta_silicon", "delta_renode"]).reset_index(drop=True)
    table["truth_built"] = direction(table["delta_silicon"])
    if floor is not None:
        limit = table["op"].map(floor)
        if limit.isna().any():
            raise ValueError("an operation has no placebo floor")
        above = table["delta_code"].abs() > limit
        table["truth_code"] = np.where(above, np.sign(table["delta_code"]), 0).astype(int)
    return table


def criteria(table, threshold=THRESHOLD):
    """C1 and C2 over all cells of R1, without a filter. C3 and C4 on each reference."""
    delta = table["delta_renode"].to_numpy()
    built = table["delta_silicon"].to_numpy()
    changed = built != 0
    out = {"n": len(table), "changed": int(changed.sum())}
    out["renode_zero_share"] = float(np.mean(delta[changed] == 0)) if changed.any() else np.nan
    out["c1_sign_agreement"] = (float(np.mean(np.sign(delta[changed]) == np.sign(built[changed])))
                                if changed.any() else np.nan)
    if np.ptp(delta) > 0 and np.ptp(built) > 0:
        out["c2_spearman"] = float(stats.spearmanr(delta, built).statistic)
    else:
        out["c2_spearman"] = np.nan

    call = direction(delta, threshold)
    called = call != 0
    for name in ("built", "code"):
        if f"truth_{name}" not in table:
            continue
        truth = table[f"truth_{name}"].to_numpy()
        moved = truth != 0
        out[f"moved_{name}"] = int(moved.sum())
        out[f"c3_false_alarm_{name}"] = float(np.mean(truth[called] == 0)) if called.any() else np.nan
        out[f"c4_miss_{name}"] = float(np.mean(call[moved] != truth[moved])) if moved.any() else np.nan
    if "truth_code" in table:
        moved = table["truth_code"].to_numpy() != 0
        out["c1_sign_code"] = (float(np.mean(np.sign(delta[moved]) == table["truth_code"].to_numpy()[moved]))
                               if moved.any() else np.nan)
    return out


def layout_spread(cells, platform="silicon"):
    keys = ["pair", "side", "op"]
    g = cells[cells.platform == platform].groupby(keys)["value"]
    spread = (g.max() - g.min()) / g.median()
    return spread.rename("spread").reset_index()


def c5_share(cells, threshold=THRESHOLD):
    spread = layout_spread(cells)
    per_op = spread.groupby("op")["spread"].median()
    return float((per_op > threshold).mean())


def negative_control(table, strata):
    """Share of cells above the floor among the pairs outside the hot path."""
    outside = table[table["pair"].map(strata) == OUTSIDE_HOT_PATH]
    return float((outside["truth_code"] != 0).mean()) if len(outside) else np.nan


def cluster_ci(table, fn, n_boot=N_BOOT, seed=SEED):
    """Percentile interval from resampling whole pairs."""
    rng = np.random.default_rng(seed)
    groups = {k: g for k, g in table.groupby("pair")}
    names = list(groups)
    values = []
    for _ in range(n_boot):
        pick = rng.choice(len(names), size=len(names), replace=True)
        # A pair drawn twice stays two pairs for the statistics that group by pair.
        boot = pd.concat([groups[names[i]].assign(pair=k) for k, i in enumerate(pick)],
                         ignore_index=True)
        values.append(fn(boot))
    values = np.array(values, dtype=float)
    return tuple(np.nanpercentile(values, [2.5, 97.5]))


def summary(cells, floor=None, n_boot=N_BOOT):
    table = pair_table(cells, floor)
    point = criteria(table)
    report = {}
    for name, value in point.items():
        if name[:2] in ("c1", "c2", "c3", "c4"):
            low, high = cluster_ci(table, lambda t, key=name: criteria(t)[key], n_boot=n_boot)
            report[name] = (value, low, high)
        else:
            report[name] = value
    report["c5_layout_share"] = (c5_share(cells), *cluster_ci(cells, c5_share, n_boot=n_boot))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+", help="parse_log output of both platforms")
    ap.add_argument("--table", help="also write the pair table to this CSV")
    ap.add_argument("--strata", help="pairs CSV, to report the negative control")
    ap.add_argument("--without", nargs="*", default=[], help="pairs left out of the criteria")
    args = ap.parse_args()

    rows = pd.concat([pd.read_csv(p) for p in args.csv], ignore_index=True)
    rows, placebos = split_placebos(rows)
    floor = None
    if len(placebos):
        floor = placebo_floor(rows[rows.platform == "silicon"],
                              placebos[placebos.platform == "silicon"])
    pairs = rows[rows["tag"].str.contains(":", regex=False)]
    cells = cells_from_rows(label_rows(pairs))
    cells = cells[~cells["pair"].isin(args.without)]
    table = pair_table(cells, floor)
    if args.table:
        table.to_csv(args.table, index=False)
    for name, value in summary(cells, floor).items():
        print(name, value)
    if args.strata and floor is not None:
        strata = pd.read_csv(args.strata).set_index("pair")["stratum"]
        print("negative_control", negative_control(table, strata))


if __name__ == "__main__":
    main()
