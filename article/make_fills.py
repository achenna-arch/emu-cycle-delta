# -*- coding: utf-8 -*-
"""Writes every number and generated table of the article from the campaign tables."""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))

from delta_metrics import (BUILT, THRESHOLD, c5_share, cluster_ci, label_rows, layout_spread, negative_control,  # noqa: E402
                           pair_table, split_placebos, summary)
from exploratory import cell_classes, cost_of_instruction, layout_only, load, operation_table, sweep  # noqa: E402
from determinism import across_nodes, across_rounds, identical_pairs, kernel_rows  # noqa: E402
from mutants import added, slopes  # noqa: E402
import qemu_bridge  # noqa: E402

RESULTS = ROOT / "results"
TABLES = ROOT / "article" / "tables"
FILLS = ROOT / "article" / "manuscript" / "fills_auto.json"
IDENTICAL = ("A005 A006 A007 A009 A012 A014 A016 A017 A018 A019 A020 A021 A022 A023 A024 "
             "B000 B001 B002 B003 B004").split()
FROZEN = ["campaign_silicon_n1.csv", "campaign_renode.csv"]
EXTENSION = ["campaign_ext_silicon_n1.csv", "campaign_ext_renode.csv"]
DRY_RUN = ["A000", "A001"]
N_BOOT = int(os.environ.get("BOOT", 2000))


def csvs(names):
    return [RESULTS / n for n in names if (RESULTS / n).exists()]


def pct(x, digits=1):
    return f"{100 * x:.{digits}f}"


def interval(triple, scale=100, digits=1):
    value, low, high = triple
    return f"{scale * value:.{digits}f}", f"[{scale * low:.{digits}f}, {scale * high:.{digits}f}]"


def reading(tag, cells, floor, strata=None):
    """Point values and intervals of one reading, keyed by tag."""
    table = pair_table(cells, floor)
    report = summary(cells, floor, n_boot=N_BOOT)
    out = {f"{tag}_N": report["n"], f"{tag}_CHANGED": report["changed"], f"{tag}_PAIRS": table["pair"].nunique(),
           f"{tag}_ZERO": pct(report["renode_zero_share"])}
    for key, name in (("c1_sign_agreement", "C1"), ("c3_false_alarm_built", "C3R1"), ("c4_miss_built", "C4R1"),
                      ("c3_false_alarm_code", "C3R2"), ("c4_miss_code", "C4R2"), ("c1_sign_code", "C1R2"),
                      ("c5_layout_share", "C5")):
        out[f"{tag}_{name}"], out[f"{tag}_{name}_CI"] = interval(report[key])
    out[f"{tag}_C2"], out[f"{tag}_C2_CI"] = interval(report["c2_spearman"], 1, 2)
    out[f"{tag}_MOVED_R1"] = report["moved_built"]
    out[f"{tag}_MOVED_R2"] = report["moved_code"]
    classes, only = cell_classes(table), layout_only(table)
    out[f"{tag}_RENODE_ZERO_N"] = classes["renode_zero"]
    out[f"{tag}_SAME_SIGN_N"] = classes["same_sign"]
    out[f"{tag}_OPPOSITE_N"] = classes["opposite_sign"]
    out[f"{tag}_MISSED_N"] = only["missed"]
    out[f"{tag}_MISSED_BELOW_FLOOR"] = only["missed_below_floor"]
    out[f"{tag}_MISSED_ABOVE_FLOOR"] = only["missed_above_floor"]
    moved = table[table["truth_built"] != 0]
    missed = moved[moved["delta_renode"].abs() < THRESHOLD]
    out[f"{tag}_MISSED_AT_ZERO"] = int((missed["delta_renode"] == 0).sum())
    out[f"{tag}_R1_ABOVE_FLOOR"] = int((moved["truth_code"] != 0).sum())
    out[f"{tag}_R1_BELOW_FLOOR"] = int((moved["truth_code"] == 0).sum())
    out[f"{tag}_R1_BELOW_FLOOR_SHARE"] = pct((moved["truth_code"] == 0).mean())
    out[f"{tag}_R1_WRONG_SIGN_R2"] = int(((moved["truth_code"] != 0) & (np.sign(moved["delta_silicon"]) != moved["truth_code"])).sum())
    code = table[table["truth_code"] != 0]
    out[f"{tag}_CODE_RENODE_ZERO"] = int((code["delta_renode"] == 0).sum())
    out[f"{tag}_CODE_PAIRS"] = code["pair"].nunique()
    words = ["None", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"]
    count = int((code["delta_renode"] == 0).sum())
    out[f"{tag}_CODE_RENODE_ZERO_WORD"] = words[count] if count < len(words) else str(count)
    changed = table[table["delta_renode"] != 0]
    out[f"{tag}_RENODE_MOVES"] = len(changed)
    out[f"{tag}_RENODE_MOVES_PAIRS"] = changed["pair"].nunique()
    agree = np.sign(changed["delta_renode"]) == np.sign(changed["delta_code"])
    out[f"{tag}_RENODE_SIGN_R2"] = pct(agree.mean())
    called = table[table["delta_renode"].abs() >= THRESHOLD]
    out[f"{tag}_CALLS"] = len(called)
    out[f"{tag}_FA_R1_N"] = int((called["truth_built"] == 0).sum())
    out[f"{tag}_FA_R2_N"] = int((called["truth_code"] == 0).sum())
    out[f"{tag}_FA_R2_R1SAME"] = int(((called["truth_code"] == 0)
                                      & (called["truth_built"] == np.sign(called["delta_renode"]))).sum())
    out[f"{tag}_RENODE_SMALL"] = int(((table["delta_renode"] != 0) & (table["delta_renode"].abs() < THRESHOLD)).sum())
    out[f"{tag}_MISSED_NONZERO"] = out[f"{tag}_MISSED_N"] - out[f"{tag}_MISSED_AT_ZERO"]
    if len(missed):
        worst = missed.loc[missed["delta_silicon"].abs().idxmax()]
        out[f"{tag}_MISS_MAX_CELL"] = f"`{worst['op']}` in {worst['pair']}"
    zero_code = table[(table["truth_code"] != 0) & (table["delta_renode"] == 0)]
    out[f"{tag}_CODE_ZERO_LIST"] = cells_text(zero_code, "delta_code")
    silent =table.groupby("pair").filter(lambda g: (g["delta_silicon"] == 0).all() and (g["delta_renode"] == 0).all())
    out[f"{tag}_SILENT_LIST"] = ", ".join(sorted(silent["pair"].unique()))
    out[f"{tag}_SILENT_N"] = silent["pair"].nunique()
    table[(table["truth_code"] != 0) & (table["delta_renode"] == 0)].to_csv(
        RESULTS / "exploratory" / f"{tag}_code_effect_renode_zero.csv", index=False)
    out[f"{tag}_MISS_MAX"] = pct(missed["delta_silicon"].abs().max(), 2) if len(missed) else "0"
    blind = table.groupby("pair").filter(lambda g: (g["delta_renode"] == 0).all() and (g["truth_built"] != 0).any())
    out[f"{tag}_BLIND_PAIRS"] = blind["pair"].nunique()
    out[f"{tag}_BLIND_LIST"] = ", ".join(sorted(blind["pair"].unique()))
    if strata is not None:
        out[f"{tag}_NEG_CONTROL"] = pct(negative_control(table, strata))
    return out, table


def signed(x, digits=2):
    return f"{100 * x:+.{digits}f}".replace("-", "−")


def cells_text(frame, column):
    items = [f"`{r['op']}` in {r['pair']} ({signed(r[column])} %)" for _, r in frame.iterrows()]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else "none"


def pair_rows(table):
    rows = []
    for pair, g in table.groupby("pair"):
        rows.append({"Pair": pair, "Cells that move": int((g["delta_silicon"] != 0).sum()),
                     "Past 2 %": int((g["truth_built"] != 0).sum()),
                     "Largest move (%)": f"{100 * g['delta_silicon'].abs().max():.2f}",
                     "Renode moves": int((g["delta_renode"] != 0).sum()),
                     "Renode past 2 %": int((g["delta_renode"].abs() >= THRESHOLD).sum()),
                     "R2 over floor": int((g["truth_code"] != 0).sum())})
    return pd.DataFrame(rows)


def markdown(frame, caption, note=None):
    head = "Table: " + caption + "\n| " + " | ".join(str(c) for c in frame.columns) + " |\n|" + "---|" * len(frame.columns) + "\n"
    body = "\n".join("| " + " | ".join(str(v) for v in row) + " |" for row in frame.to_numpy())
    return head + body + "\n" + (f"Note: {note}\n" if note else "")


def write_table(name, text):
    TABLES.mkdir(exist_ok=True)
    (TABLES / f"table_{name}.md").write_text(text, encoding="utf-8")


def op_rows(ops):
    frame = pd.DataFrame({
        "Operation": ops["op"].map(lambda s: f"`{s}`"),
        "Cycles": ops["cycles"].map(lambda v: f"{v:,.0f}"),
        "Instructions": ops["instructions"].map(lambda v: f"{v:,.0f}"),
        "Cycles per instruction": ops["cycles_per_instruction"].map(lambda v: f"{v:.2f}"),
        "Layout spread (%)": ops["layout_spread"].map(lambda v: f"{100 * v:.1f}"),
        "Floor (%)": ops["floor"].map(lambda v: f"{100 * v:.1f}"),
        "Past 2 %": ops["moved"], "Missed": ops["missed"]})
    order = ops["layout_spread"].to_numpy().argsort()[::-1]
    return frame.iloc[order]


def main():
    fills = {}
    pairs = pd.read_csv(RESULTS / "pairs.csv")
    fills.update(POP_TOTAL=len(pairs), POP_A=int((pairs["stratum"] == "A").sum()),
                 POP_B=int((pairs["stratum"] == "B").sum()))
    fills.update(F_IDENTICAL=len(IDENTICAL), F_USEFUL=30 - len(IDENTICAL))
    screen = pd.read_csv(RESULTS / "screening.csv")["result"].value_counts()
    total = int(screen.sum())
    fills.update(SCREEN_TOTAL=total, SCREEN_KEPT=int(screen["changed"]), SCREEN_SAME=int(screen["same"]),
                 SCREEN_FAILED=int(screen["failed"]),
                 SCREEN_YIELD=pct(screen["changed"] / (screen["changed"] + screen["same"])))
    nrf = len((RESULTS / "lists" / "all.txt").read_text().split())
    extended = RESULTS / "lists_ext" / "all.txt"
    nrf += len(extended.read_text().split()) if extended.exists() else 0
    fills.update(N_NRF=f"{nrf:,}", N_QEMU=60 + len((RESULTS / "lists_ext" / "qemu.txt").read_text().split()))

    strata = pd.concat([pd.read_csv(RESULTS / "pairs_final.csv"),
                        pd.read_csv(RESULTS / "pairs_extended.csv")]).set_index("pair")["stratum"]
    cells_f, floor = load(csvs(FROZEN))
    frozen, table_f = reading("F", cells_f, floor, strata)
    fills.update(frozen)
    cells_w, _ = load(csvs(FROZEN), DRY_RUN)
    fills.update(reading("FW", cells_w, floor)[0])
    cells_u, floor_u = load(csvs(FROZEN + EXTENSION), IDENTICAL)
    if not floor_u.equals(floor):
        raise SystemExit("the extension changed the floor")
    useful, table_u = reading("U", cells_u, floor, strata)
    fills.update(useful)
    cells_v, _ = load(csvs(FROZEN + EXTENSION), IDENTICAL + DRY_RUN)
    fills.update(reading("UW", cells_v, floor)[0])
    table_u.to_csv(RESULTS / "table_useful.csv", index=False)

    write_table("pairs", markdown(pair_rows(table_u), "What the board and Renode report for each useful pair, as compiled",
                                  "Cells out of 17. Largest move in absolute value. R2 over floor counts cells of the code effect above the floor."))
    ops = operation_table(cells_u, table_u, floor)
    write_table("ops", markdown(op_rows(ops), "Operations on the useful reading",
                                "Cycles and instructions are medians of the parent images as compiled. Past 2 % and Missed count cells on R1."))
    ops.to_csv(RESULTS / "exploratory" / "useful_ops.csv", index=False)
    swept = sweep(table_u)
    swept.to_csv(RESULTS / "exploratory" / "useful_sweep.csv", index=False)
    for t in (0.0, 0.01, 0.02, 0.05):
        row = swept[swept["threshold"] == t].iloc[0]
        label = f"{int(t * 1000):03d}"
        fills[f"SW{label}_MISS"], fills[f"SW{label}_FA"] = pct(row["c4_miss_built"]), pct(row["c3_false_alarm_built"])
        fills[f"SW{label}_MISS_R2"], fills[f"SW{label}_FA_R2"] = pct(row["c4_miss_code"]), pct(row["c3_false_alarm_code"])

    cost = cost_of_instruction(cells_u, table_u)
    fills.update(COST_MEDIAN=f"{cost['per_instruction'].median():.2f}", COST_N=len(cost),
                 COST_Q1=f"{cost['per_instruction'].quantile(0.25):.2f}",
                 COST_Q3=f"{cost['per_instruction'].quantile(0.75):.2f}")
    from scipy import stats
    fills["H5_CPI_RHO"] = f"{stats.spearmanr(ops['cycles_per_instruction'], ops['median_error'], nan_policy='omit').statistic:.2f}"
    fills["H5_LAYOUT_RHO"] = f"{stats.spearmanr(ops['layout_spread'], ops['median_error'], nan_policy='omit').statistic:.2f}"
    spread_f = layout_spread(cells_f)
    fills["OPS_OVER_2"] = int((spread_f.groupby("op")["spread"].median() > THRESHOLD).sum())
    fills["SPREAD_MAX"] = pct(spread_f["spread"].max(), 1)
    fills["SPREAD_MAX_OP"] = f"`{spread_f.loc[spread_f['spread'].idxmax(), 'op']}`"
    kernel_floor = floor[~floor.index.str.startswith(("calib.", "clock."))]
    if len(kernel_floor) != 17:
        raise SystemExit("expected a floor for 17 operations")
    fills["FLOOR_MIN"], fills["FLOOR_MAX"] = pct(kernel_floor.min(), 1), pct(kernel_floor.max(), 1)
    fills["FLOOR_MEDIAN"] = pct(kernel_floor.median(), 1)
    fills["FLOOR_OVER_2"] = int((kernel_floor > THRESHOLD).sum())
    top = ops.sort_values(["missed", "layout_spread"], ascending=False).head(4)
    fills["OPS_MOST_MISSED"] = ", ".join(f"`{o}`" for o in top["op"])
    fills["OPS_MOST_MISSED_N"] = int(top["missed"].sum())
    low = ops[ops["layout_spread"] <= THRESHOLD]
    fills["OPS_LOW_SPREAD"] = ", ".join(f"`{o}`" for o in low["op"])
    fills["OPS_LOW_SPREAD_MISSED"] = int(low["missed"].sum())
    fills["OPS_LOW_SPREAD_MOVED"] = int(low["moved"].sum())

    silicon = kernel_rows(csvs(["campaign_silicon_n1.csv", "campaign_ext_silicon_n1.csv"]))
    same = identical_pairs(silicon, IDENTICAL)
    fills.update(DET_CELLS=f"{same['cells']:,}", DET_NONZERO=same["nonzero"], DET_ASBUILT=same["cells"] // 4)
    others = {"n2": kernel_rows(csvs(["campaign_silicon_n2.csv", "campaign_ext_silicon_n2.csv"])),
              "n3": kernel_rows(csvs(["campaign_silicon_n3.csv", "campaign_ext_silicon_n3.csv"]))}
    nodes = across_nodes(silicon, others)
    fills.update(NODE_CELLS=f"{nodes['n2']['cells']:,}", NODE_DIFF=nodes["n2"]["different"] + nodes["n3"]["different"])
    image_cells, moved = across_rounds(silicon)
    fills.update(ROUND_CELLS=f"{image_cells:,}", ROUND_MOVED=len(moved), ROUND_MAX=pct(moved["spread"].max(), 2))

    rows = pd.concat([pd.read_csv(p) for p in csvs(FROZEN + EXTENSION)], ignore_index=True)
    plain, _ = split_placebos(rows)
    renode = plain[plain["platform"] == "renode"]
    renode = renode[~renode["op"].str.startswith(("calib.", "clock."))]
    labelled = renode[renode["tag"].str.contains(":", regex=False)]
    shifts = labelled.groupby(["tag", "pad", "op"])["p50"].median().groupby(level=["tag", "op"])
    fills["RENODE_SHIFT_CELLS"] = f"{len(shifts):,}"
    fills["RENODE_SHIFT_MOVED"] = int((shifts.max() != shifts.min()).sum())

    silicon_rows = pd.read_csv(RESULTS / "campaign_silicon_n1.csv")
    table = added(silicon_rows)
    write_table("mutants", markdown(
        table.pivot_table(index=["op", "kind"], columns="n", values="added").round(2).reset_index().rename(
            columns={"op": "Operation", "kind": "Family"}), "Cycles added on the board by the injected mutants",
        "Mean over the four shifts, against the same image without a mutant. Renode adds exactly N instructions in every cell."))
    for _, row in slopes(table).iterrows():
        fills[f"SLOPE_{row['op'].split('.')[1].upper()}_{row['kind'].upper()}"] = f"{row['slope']:.2f}"

    qemu = pd.concat([pd.read_csv(p) for p in csvs(["campaign_qemu.csv", "campaign_ext_qemu.csv"])], ignore_index=True)
    plain_renode = plain[plain["platform"] == "renode"]
    plain_renode = plain_renode[plain_renode["tag"].str.contains(":", regex=False)]
    bridge = qemu_bridge.bridge(qemu, plain_renode)
    bridge.to_csv(RESULTS / "qemu_bridge_all.csv", index=False)
    done = qemu_bridge.criteria(bridge)
    fills.update(Q_N=len(bridge), Q_MOVED=done["moved"], Q1=f"{done['q1']:.3f}", Q2=f"{done['q2']:.3f}",
                 Q_PASS="pass" if done["pass"] else "fail")
    delta = bridge[(bridge["qemu"] != 0) | (bridge["renode"] != 0)]
    from delta_metrics import direction
    fills["Q_MOVED_SAME"] = int((direction(delta["qemu"]) == direction(delta["renode"])).sum())
    odd = delta[direction(delta["qemu"]) != direction(delta["renode"])]
    fills["Q_EXCEPTIONS"] = "; ".join(f"`{r['op']}` in {r['pair']}, {signed(r['qemu'])} % under QEMU and "
                                      f"{signed(r['renode'])} % under Renode" for _, r in odd.iterrows())

    FILLS.write_text(json.dumps(fills, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(fills, indent=0, ensure_ascii=False))


if __name__ == "__main__":
    main()
