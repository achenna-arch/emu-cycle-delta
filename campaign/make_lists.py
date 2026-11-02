"""Writes the image lists of protocol section 14: all images on one node, a drawn 10 % on two more."""
import argparse
import csv
import math
import random
from pathlib import Path

from build_matrix import PADS, RANKS, placebo_tags

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261030
SHARE = 0.10
KINDS = ["alu", "load"]
SIZES = [4, 8, 16, 32]


def images(pairs, pairs_only=False):
    out = [f"{r['pair']}_{side}_p{pad}" for r in pairs for side in ("parent", "child") for pad in PADS]
    if pairs_only:
        return out
    out += [f"{tag.replace(':', '_')}_g{rank}" for tag in placebo_tags(pairs) for rank in RANKS]
    out += [f"mut_{kind}{n}_p{pad}" for kind in KINDS for n in SIZES for pad in PADS]
    out += [f"smoke_p{pad}" for pad in PADS]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=Path, default=ROOT / "results" / "pairs_final.csv")
    ap.add_argument("--elves", type=Path, default=ROOT / "results" / "elf")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "lists")
    ap.add_argument("--pairs-only", action="store_true", help="section 15: no placebos, mutants or smoke")
    args = ap.parse_args()

    with args.pairs.open(encoding="utf-8") as f:
        names = images(list(csv.DictReader(f)), args.pairs_only)
    absent = [n for n in names if not (args.elves / f"{n}.elf").exists()]
    if absent:
        raise SystemExit(f"{len(absent)} images missing, first {absent[0]}")

    rng = random.Random(SEED)
    rng.shuffle(names)
    repeated = names[:math.ceil(len(names) * SHARE)]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "all.txt").write_text("\n".join(names) + "\n", encoding="ascii", newline="\n")
    (args.out / "repeated.txt").write_text("\n".join(repeated) + "\n", encoding="ascii", newline="\n")
    print(f"{len(names)} images, {len(repeated)} repeated")


if __name__ == "__main__":
    main()
