"""Builds one image of the benchmark and archives its ELF and resolved config."""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOARD = "nrf52840dk/nrf52840"


def build(tag, pad, out, board=BOARD, pristine=False, layout=None, stem=None):
    tools = ROOT / "_tools"
    workdir = tools / "build" / board.replace("/", "_")
    workdir.mkdir(parents=True, exist_ok=True)
    overlay = workdir / "bench_overlay.conf"
    overlay.write_text(f'CONFIG_BENCH_TAG="{tag}"\nCONFIG_BENCH_PAD_BYTES={pad}\n', encoding="ascii")

    cmd = ["west", "build", "-b", board, "-s", str(ROOT / "fw"), "-d", str(workdir / "b"),
           "-p", "always" if pristine else "auto", "--",
           # West passes this with backslashes, which some commits hand to a CMake macro unescaped.
           f"-DWEST_TOPDIR={(tools / 'zp').as_posix()}",
           f"-DEXTRA_CONF_FILE={overlay.as_posix()}",
           f"-DBENCH_LAYOUT={layout.as_posix() if layout else ''}"]
    env = os.environ.copy()
    subprocess.run(cmd, cwd=tools / "zp", env=env, check=True)

    out.mkdir(parents=True, exist_ok=True)
    stem = stem or f"{tag.replace(':', '_')}_p{pad}"
    shutil.copy(workdir / "b" / "zephyr" / "zephyr.elf", out / f"{stem}.elf")
    shutil.copy(workdir / "b" / "zephyr" / ".config", out / f"{stem}.config")
    return out / f"{stem}.elf"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--pad", type=int, default=0)
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "elf")
    ap.add_argument("--board", default=BOARD)
    ap.add_argument("--pristine", action="store_true")
    args = ap.parse_args()
    if args.pad % 4:
        sys.exit("padding must be a multiple of 4")
    print(build(args.tag, args.pad, args.out, args.board, args.pristine))


if __name__ == "__main__":
    main()
