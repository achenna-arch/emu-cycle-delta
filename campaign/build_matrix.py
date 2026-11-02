"""Builds every image of the selected pairs. Only a side that fails to compile is logged for
replacement: a git or west failure stops the run, so an outage cannot change the sample.
A finished image is never built again, so a stopped run resumes where it was."""
import argparse
import csv
import subprocess
from pathlib import Path

from build_image import ROOT, build
from build_placebo import make, placebo_path

ZEPHYR = ROOT / "_tools" / "zp" / "zephyr"
PADS = list(range(0, 16, 4))
MODULES = ["cmsis", "cmsis_6", "hal_nordic"]
RANKS = list(range(1, 9))
PLACEBO_PAIRS = {"A": 5, "B": 1}
QEMU_BOARD = "mps2/an385"


def git(*args):
    done = subprocess.run(["git", "-C", str(ZEPHYR), *args], capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout.strip()


def checkout(sha, attempts=3):
    git("checkout", "--quiet", "--detach", sha)
    for _ in range(attempts):
        done = subprocess.run(["west", "update", "--narrow", "-o=--depth=1", *MODULES],
                              cwd=ZEPHYR.parent, capture_output=True, text=True)
        if done.returncode == 0:
            return
        print(done.stderr[-2000:])
    raise SystemExit(f"west update failed at {sha}")


def read_failed(path):
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as f:
        return {r["pair"] for r in csv.DictReader(f)}


def sample(rows, failed):
    """Keeps each stratum at its quota: a failed pair gives way to the next of the draw."""
    out = []
    for stratum in ("A", "B"):
        pool = [r for r in rows if r["stratum"] == stratum]
        quota = sum(r["selected"] == "1" for r in pool)
        out += [r for r in pool if r["pair"] not in failed][:quota]
    return out


def placebo_tags(chosen):
    """The parents of the first pairs of each stratum, in draw order."""
    tags = []
    for stratum, count in PLACEBO_PAIRS.items():
        pool = [r for r in chosen if r["stratum"] == stratum]
        tags += [f"{r['pair']}:parent" for r in pool[:count]]
    return tags


def missing(tag, args, ranks):
    stem = tag.replace(":", "_")
    pads = [p for p in args.pads if not (args.out / f"{stem}_p{p}.config").exists()]
    gaps = [r for r in ranks if not placebo_path(args.out, tag, r).with_suffix(".config").exists()]
    qemu = args.qemu and not (args.qemu / f"{stem}_p0.config").exists()
    return pads, gaps, qemu


def build_side(tag, sha, args, ranks):
    """Returns False if the target image of this commit does not compile."""
    pads, gaps, qemu = missing(tag, args, ranks)
    if not (pads or gaps or qemu):
        return True
    checkout(sha)
    try:
        for i, pad in enumerate(pads):
            build(tag, pad, args.out, pristine=i == 0)
        if gaps:
            make(tag, gaps, args.out, args.draws)
    except subprocess.CalledProcessError as err:
        with args.failures.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([*tag.split(":"), sha, err.returncode])
        print(f"failed: {tag}", flush=True)
        return False
    if qemu:
        try:
            build(tag, 0, args.qemu, board=QEMU_BOARD, pristine=True)
        except subprocess.CalledProcessError as err:
            print(f"no QEMU image for {tag}: {err.returncode}", flush=True)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "elf")
    ap.add_argument("--qemu", type=Path, help="also build one QEMU image per commit, kept here")
    ap.add_argument("--pads", type=int, nargs="+", default=PADS)
    ap.add_argument("--placebos", action="store_true", help="add the placebos of section 3")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many pairs")
    ap.add_argument("--failures", type=Path, default=ROOT / "results" / "build_failures.csv")
    ap.add_argument("--draws", type=Path, default=ROOT / "results" / "placebo_draws.csv")
    ap.add_argument("--final", type=Path, help="write the pairs kept to this CSV")
    args = ap.parse_args()

    with args.pairs.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    start = git("rev-parse", "HEAD")
    finished = set()
    try:
        while True:
            chosen = sample(rows, read_failed(args.failures))
            if args.limit:
                chosen = chosen[:args.limit]
            row = next((r for r in chosen if r["pair"] not in finished), None)
            if row is None:
                break
            with_gaps = placebo_tags(chosen) if args.placebos else []
            for side in ("parent", "child"):
                tag = f"{row['pair']}:{side}"
                if not build_side(tag, row[side], args, RANKS if tag in with_gaps else []):
                    break
            finished.add(row["pair"])
    finally:
        checkout(start)

    if args.final:
        with args.final.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(chosen)


if __name__ == "__main__":
    main()
