"""Builds a mutant of protocol section 4: N known instructions in k_sem_give."""
import argparse
import re
import subprocess
from itertools import product
from pathlib import Path

from build_image import ROOT, build

ZEPHYR = ROOT / "_tools" / "zp" / "zephyr"
TARGET = ZEPHYR / "kernel" / "sem.c"
ANCHOR = re.compile(r"(void z_impl_k_sem_give\(struct k_sem \*sem\)\s*\{)")
BODY = {
    "alu": 'adds r3, r3, #0',
    "load": 'ldr r3, [sp]',
}


def inject(source, kind, n):
    asm = f'\n\t__asm__ volatile(".rept {n}\\n{BODY[kind]}\\n.endr\\n" : : : "r3", "cc", "memory");\n'
    patched, hits = ANCHOR.subn(lambda m: m.group(1) + asm, source)
    if hits != 1:
        raise SystemExit(f"anchor found {hits} times in {TARGET}")
    return patched


def make(kind, n, pad, out):
    original = TARGET.read_text(encoding="utf-8")
    try:
        TARGET.write_text(inject(original, kind, n), encoding="utf-8")
        print(build(f"mut_{kind}{n}", pad, out))
    finally:
        TARGET.write_text(original, encoding="utf-8")
    state = subprocess.run(["git", "-C", str(ZEPHYR), "status", "--porcelain", "kernel/sem.c"],
                           capture_output=True, text=True).stdout
    if state.strip():
        raise SystemExit("kernel/sem.c was not restored")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=sorted(BODY), nargs="+", required=True)
    ap.add_argument("--n", type=int, nargs="+", required=True)
    ap.add_argument("--pad", type=int, nargs="+", default=[0])
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "elf")
    args = ap.parse_args()

    for kind, n, pad in product(args.kind, args.n, args.pad):
        if not (args.out / f"mut_{kind}{n}_p{pad}.config").exists():
            make(kind, n, pad, args.out)


if __name__ == "__main__":
    main()
