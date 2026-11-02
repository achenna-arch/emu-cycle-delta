"""Extension of protocol section 15: walks the frozen draw of stratum A past the sample and keeps
the pairs whose code changes for this target. Every pair looked at is logged, so a stopped run
resumes where it was and the yield of the rule can be published."""
import argparse
import csv
import shutil
import subprocess
from pathlib import Path

from build_image import ROOT
from build_matrix import PADS, build_side, checkout, git, read_failed
from check_placebo import BIN

STRATUM = "A"
QUOTA = 15
CHANGED = "changed"
SAME = "same"
FAILED = "failed"
FIELDS = ["pair", "result"]


def text_bytes(elf):
    """The firmware tag sits in rodata, so this section is the code alone."""
    out = elf.with_suffix(".text.bin")
    subprocess.run([BIN / "arm-zephyr-eabi-objcopy.exe", "-O", "binary", "-j", "text", str(elf), str(out)],
                   check=True)
    data = out.read_bytes()
    out.unlink()
    return data


def read_screen(path):
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return {r["pair"]: r["result"] for r in csv.DictReader(f)}


def log_screen(path, pair, result):
    fresh = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if fresh:
            writer.writerow(FIELDS)
        writer.writerow([pair, result])


def screen(row, args):
    """Builds the p0 image of both sides and compares their code."""
    pair = row["pair"]
    first = argparse.Namespace(pads=[0], out=args.screen_elves, qemu=None, failures=args.failures,
                               draws=None)
    for side in ("parent", "child"):
        if not build_side(f"{pair}:{side}", row[side], first, []):
            return FAILED
    parent, child = (text_bytes(args.screen_elves / f"{pair}_{side}_p0.elf") for side in ("parent", "child"))
    return SAME if parent == child else CHANGED


def complete(row, args):
    """Adds the other shifts and the QEMU images of a kept pair."""
    pair = row["pair"]
    full = argparse.Namespace(pads=PADS, out=args.out, qemu=args.qemu, failures=args.failures, draws=None)
    for side in ("parent", "child"):
        for suffix in (".elf", ".config"):
            name = f"{pair}_{side}_p0{suffix}"
            shutil.copy(args.screen_elves / name, args.out / name)
        if not build_side(f"{pair}:{side}", row[side], full, []):
            raise SystemExit(f"{pair}:{side} compiled at p0 and failed at another shift")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=Path, default=ROOT / "results" / "pairs.csv")
    ap.add_argument("--final", type=Path, default=ROOT / "results" / "pairs_final.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "elf")
    ap.add_argument("--qemu", type=Path, default=ROOT / "results" / "elf_qemu")
    ap.add_argument("--screen-elves", type=Path, default=ROOT / "results" / "elf_screen")
    ap.add_argument("--screen", type=Path, default=ROOT / "results" / "screening.csv")
    ap.add_argument("--failures", type=Path, default=ROOT / "results" / "build_failures_ext.csv")
    ap.add_argument("--frozen-failures", type=Path, default=ROOT / "results" / "build_failures.csv")
    ap.add_argument("--extended", type=Path, default=ROOT / "results" / "pairs_extended.csv")
    ap.add_argument("--quota", type=int, default=QUOTA)
    args = ap.parse_args()

    with args.pairs.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    with args.final.open(encoding="utf-8") as f:
        sampled = {r["pair"] for r in csv.DictReader(f)}
    skipped = sampled | read_failed(args.frozen_failures)
    pool = [r for r in rows if r["stratum"] == STRATUM and r["pair"] not in skipped]

    done = read_screen(args.screen)
    args.screen_elves.mkdir(parents=True, exist_ok=True)
    start = git("rev-parse", "HEAD")
    try:
        for row in pool:
            kept = sum(result == CHANGED for result in done.values())
            pair = row["pair"]
            if pair in done:
                if done[pair] == CHANGED:
                    complete(row, args)
                continue
            if kept >= args.quota:
                break
            done[pair] = screen(row, args)
            log_screen(args.screen, pair, done[pair])
            print(f"screened {pair}: {done[pair]}, kept {sum(r == CHANGED for r in done.values())}", flush=True)
            if done[pair] == CHANGED:
                complete(row, args)
    finally:
        checkout(start)

    kept = [r for r in pool if done.get(r["pair"]) == CHANGED]
    with args.extended.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(kept)
    print(f"{len(done)} pairs screened, {len(kept)} kept")


if __name__ == "__main__":
    main()
