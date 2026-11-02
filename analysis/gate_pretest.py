"""Evaluates gates P1 to P4 of protocol section 6 on parse_log output."""
import argparse
import sys

import numpy as np
import pandas as pd

CALIB_LOOPS = 1000
ALU_FLOOR = 900
INSTR_SLACK = 10
STABLE_SPREAD = 0.01
STABLE_SHARE = 0.80
RATIO_CV_MIN = 0.05


def same_image(silicon, renode):
    # Rows of several images would be pooled per operation below.
    images = {(tag, pad) for f in (silicon, renode) for tag, pad in zip(f["tag"], f["pad"])}
    if len(images) != 1:
        raise ValueError(f"the gates apply to one image, found {sorted(images)}")


def gates(silicon, renode):
    results = {}
    sil = silicon.groupby("op")["p50"]
    ren = renode.groupby("op")["p50"]
    sil_med, ren_med = sil.median(), ren.median()

    results["P1_counter_alive"] = (
        sil_med.get("calib.alu", 0) > ALU_FLOOR and ren_med.get("calib.alu", 0) > ALU_FLOOR)

    overhead = ren_med.get("clock.overhead", np.nan)
    in_band = [CALIB_LOOPS <= ren_med.get(op, np.nan) - overhead <= CALIB_LOOPS + INSTR_SLACK
               for op in ("calib.alu", "calib.load")]
    results["P2_renode_counts_instructions"] = all(in_band)

    ops = [o for o in sil_med.index if not o.startswith(("calib.", "clock."))]
    spread = (sil.max() - sil.min()) / sil_med
    results["P3_silicon_repeatable"] = bool((spread[ops] <= STABLE_SPREAD).mean() >= STABLE_SHARE)

    common = [o for o in ops if ren_med.get(o, 0) > 0]
    ratio = sil_med[common] / ren_med[common]
    results["P4_not_trivial"] = bool(ratio.std(ddof=1) / ratio.mean() >= RATIO_CV_MIN)

    detail = pd.DataFrame({"cycles": sil_med, "instructions": ren_med, "spread": spread})
    detail["ratio"] = detail["cycles"] / detail["instructions"]
    return results, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--silicon", required=True)
    ap.add_argument("--renode", required=True)
    args = ap.parse_args()

    silicon, renode = pd.read_csv(args.silicon), pd.read_csv(args.renode)
    same_image(silicon, renode)
    results, detail = gates(silicon, renode)
    print(detail.round(3).to_string())
    print()
    for name, ok in results.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
