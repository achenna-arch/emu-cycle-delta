"""Turns benchmark logs into one CSV row per operation and round."""
import argparse
import csv
import re
import sys
from pathlib import Path

FIELDS = ["platform", "tag", "pad", "boot", "round", "op",
          "n", "min", "p10", "p50", "p90", "max", "mean"]
PLACEBO = re.compile(r"_g(\d+)$")


def payload(line):
    # serial_aggregator prefixes lines with "timestamp;node;".
    return line.rstrip("\r\n").rsplit(";", 1)[-1]


def parse_lines(lines, platform):
    """Returns the rows of the boots that reach DONE, and the boot counts."""
    rows, pending, done, boot, rnd = [], [], 0, -1, 0
    tag, pad = None, None
    for raw in lines:
        text = payload(raw)
        # A reset cuts the line in progress and glues the next boot to it.
        cut = text.find("BENCH,", 1)
        parts = text[max(cut, 0):].split(",")
        if parts[0] == "BENCH" and len(parts) > 1:
            if parts[1] == "START":
                pending = []
                boot += 1
                tag, pad = parts[3], int(parts[4])
            elif parts[1] == "ROUND":
                rnd = int(parts[2])
            elif parts[1] == "DONE":
                rows += pending
                pending = []
                done += 1
            elif parts[1] == "ERROR":
                raise ValueError("firmware error: " + ",".join(parts[2:]))
        elif parts[0] == "R" and len(parts) == 9 and tag is not None:
            values = [int(v) for v in parts[2:]]
            pending.append([platform, tag, pad, boot, rnd, parts[1]] + values)
    return rows, done, boot + 1


def mark_placebo(rows, stem):
    """A placebo prints the banner of its base image, so its log name tells it apart."""
    hit = PLACEBO.search(stem)
    if hit:
        for row in rows:
            row[1] = f"{row[1]}/g{hit.group(1)}"
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+", type=Path)
    ap.add_argument("--platform", required=True, choices=["silicon", "renode", "qemu"])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    incomplete = 0
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for log in args.logs:
            with log.open(encoding="utf-8", errors="replace") as lines:
                rows, done, boots = parse_lines(lines, args.platform)
            if done < boots:
                print(f"dropped: {log} keeps {done}/{boots} boots", file=sys.stderr)
            if done == 0:
                incomplete += 1
            w.writerows(mark_placebo(rows, log.stem))
    return 1 if incomplete else 0


if __name__ == "__main__":
    sys.exit(main())
