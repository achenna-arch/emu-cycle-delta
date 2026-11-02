"""Draws commit pairs by the written rule of protocol section 4."""
import argparse
import csv
import random
import re
import subprocess
from pathlib import Path

SCOPE = ["kernel/", "include/zephyr/kernel", "arch/arm/core/cortex_m/"]
HOT = re.compile(
    r"^kernel/(sched|sem|mutex|thread|queue|msg_q|events|condvar|stack|kheap)\.c$"
    r"|^kernel/include/"
    r"|^arch/arm/core/cortex_m/.*(swap|exc_exit)"
)
SEED = 20261030


def git(repo, *args):
    out = subprocess.run(["git", "-C", str(repo), *args], check=True,
                         capture_output=True, text=True, encoding="utf-8")
    return out.stdout


def in_scope(path):
    return any(path.startswith(prefix) for prefix in SCOPE)


def population(repo, rev_range):
    """Yields (sha, parent, subject, files) for non-merge first-parent commits, oldest first."""
    log = git(repo, "log", "--first-parent", "--reverse", "--format=%H%x09%P%x09%s",
              rev_range, "--", *SCOPE)
    for line in log.splitlines():
        sha, parents, subject = line.split("\t", 2)
        parents = parents.split()
        if len(parents) != 1:
            continue
        names = git(repo, "show", "--name-only", "--format=", sha).split()
        yield sha, parents[0], subject, [n for n in names if in_scope(n)]


def draw(commits, n_hot, n_other, seed=SEED):
    """Returns ordered reserve lists: failed builds take the next entry of their stratum."""
    hot = [c for c in commits if any(HOT.search(f) for f in c[3])]
    other = [c for c in commits if not any(HOT.search(f) for f in c[3])]
    rng = random.Random(seed)
    rng.shuffle(hot)
    rng.shuffle(other)
    rows = []
    for stratum, pool, quota in (("A", hot, n_hot), ("B", other, n_other)):
        for rank, c in enumerate(pool):
            rows.append({"pair": f"{stratum}{rank:03d}", "stratum": stratum,
                         "selected": int(rank < quota), "child": c[0], "parent": c[1],
                         "subject": c[2]})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--range", required=True, help="for example v4.3.0..<frozen sha>")
    ap.add_argument("--hot", type=int, default=24)
    ap.add_argument("--other", type=int, default=6)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    rows = draw(list(population(args.repo, args.range)), args.hot, args.other)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    picked = sum(r["selected"] for r in rows)
    print(f"{len(rows)} eligible commits, {picked} selected")


if __name__ == "__main__":
    main()
