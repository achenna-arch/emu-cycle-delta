"""Builds placebo images: the code of a base image, plus a gap after one function.

A commit moves what follows the code it changes. A placebo moves it the same way and adds no
instruction, so its deltas measure the layout noise of a commit. The gap is set at link time
from the map of the base image, so that nothing is compiled again.
"""
import argparse
import csv
import random
import re
from pathlib import Path

from build_image import BOARD, ROOT, build

GAPS = list(range(2, 18, 2))
SEED = 20261030
ARCH = "libarch__arm__core__cortex_m.a("
KERNEL = "libkernel.a("
OUTPUT = re.compile(r"^text\s+0x")
INLINE = re.compile(r"^ (\.\S+)\s+0x[0-9a-f]+\s+(0x[0-9a-f]+)\s+(\S.*)$")
NAME_ONLY = re.compile(r"^ (\.\S+)$")
WRAPPED = re.compile(r"^\s+0x[0-9a-f]+\s+(0x[0-9a-f]+)\s+(\S.*)$")
MEMBER = re.compile(r"([^/\\]+\.a)\(([^)]+)\)$")


def text_sections(map_path):
    """Returns the input sections that fill the text output section, in link order.

    bench_pad is listed even when empty, because main takes its address.
    """
    lines = map_path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = next(i for i, line in enumerate(lines) if OUTPUT.match(line))
    stop = next(i for i in range(start + 1, len(lines)) if re.match(r"^\S", lines[i]))
    items = []
    for i in range(start + 1, stop):
        hit = INLINE.match(lines[i])
        if hit:
            name, size, source = hit.groups()
        else:
            only = NAME_ONLY.match(lines[i])
            tail = WRAPPED.match(lines[i + 1]) if only else None
            if not tail:
                continue
            name, size, source = only.group(1), tail.group(1), tail.group(2)
        if int(size, 16) or name == ".text.bench_pad":
            items.append((name, source.strip()))
    return items


def pattern(name, source):
    """Writes one input section as a linker script pattern that fits only that section."""
    hit = MEMBER.search(source)
    origin = f"*{hit.group(1)}:{hit.group(2)}" if hit else f"*{Path(source).name}"
    return f"{origin}({name})"


def layout_text(items, cut, gap):
    """Lists the sections up to cut in link order, then adds the gap."""
    body = [f"  {pattern(*item)}" for item in items[:cut + 1]]
    if gap:
        body.append(f"  . = . + {gap};")
    return "text :\n{\n" + "\n".join(body) + "\n}\n"


def draw(items, tag, rank):
    """Draws a function and a gap, reproducibly for a tag and a rank.

    The hot kernel functions come first in the kernel, so few kernel cuts move them. Odd ranks
    cut in the Cortex-M code ahead of the kernel, even ranks in the kernel.
    """
    rng = random.Random(f"{SEED}:{tag}:{rank}")
    library = ARCH if rank % 2 else KERNEL
    pool = [i for i, item in enumerate(items) if library in item[1]]
    return rng.choice(pool), rng.choice(GAPS)


def placebo_path(out, tag, rank):
    return out / f"{tag.replace(':', '_')}_g{rank}.elf"


def layouts_dir():
    path = ROOT / "_tools" / "build" / BOARD.replace("/", "_") / "layouts"
    path.mkdir(exist_ok=True)
    return path


def base_sections(tag, out):
    """Builds the image as compiled, which leaves its map in the build folder."""
    build(tag, 0, out)
    workdir = ROOT / "_tools" / "build" / BOARD.replace("/", "_")
    items = text_sections(workdir / "b" / "zephyr" / "zephyr.map")
    print(f"{len(items)} text sections")
    return items


def make(tag, ranks, out, draws):
    """Builds the placebos of the commit currently checked out."""
    items = base_sections(tag, out)
    new = not draws.exists()
    with draws.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new:
            writer.writerow(["tag", "rank", "section", "gap"])
        for rank in ranks:
            cut, gap = draw(items, tag, rank)
            stem = placebo_path(out, tag, rank).stem
            path = layouts_dir() / f"{stem}.ld"
            path.write_text(layout_text(items, cut, gap), encoding="ascii")
            print(build(tag, 0, out, layout=path, stem=stem))
            writer.writerow([tag, rank, items[cut][0], gap])
            f.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--ranks", type=int, nargs="+", default=[])
    ap.add_argument("--identity", action="store_true", help="rewrite the link order, no gap")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "elf")
    ap.add_argument("--draws", type=Path, default=ROOT / "results" / "placebo_draws.csv")
    args = ap.parse_args()

    if args.identity:
        items = base_sections(args.tag, args.out)
        stem = f"{args.tag.replace(':', '_')}_identity"
        path = layouts_dir() / f"{stem}.ld"
        path.write_text(layout_text(items, len(items) - 1, 0), encoding="ascii")
        print(build(args.tag, 0, args.out, layout=path, stem=stem))
        return
    make(args.tag, args.ranks, args.out, args.draws)


if __name__ == "__main__":
    main()
