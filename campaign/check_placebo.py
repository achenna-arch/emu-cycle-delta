"""Shows that a placebo moves functions and keeps every instruction of its base image."""
import argparse
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "_tools" / "sdk" / "zephyr-sdk-1.0.1" / "gnu" / "arm-zephyr-eabi" / "bin"
HEADER = re.compile(r"^([0-9a-f]{8}) <(.+)>:$")
LINE = re.compile(r"^\s*[0-9a-f]+:\t(?:[0-9a-f]{2,8} ?)+\s*\t(\S+)")


def functions(elf):
    """Returns symbol -> (address, mnemonics) for the text of an image."""
    dump = subprocess.run([BIN / "arm-zephyr-eabi-objdump.exe", "-d", "-j", "text", str(elf)],
                          check=True, capture_output=True, text=True).stdout
    table, name = {}, None
    for line in dump.splitlines():
        head = HEADER.match(line)
        if head:
            name = head.group(2)
            table[name] = (int(head.group(1), 16), [])
            continue
        hit = LINE.match(line)
        if hit and name:
            table[name][1].append(hit.group(1))
    return table


def same_code(base, other):
    """A short gap follows the last instruction: objdump prints its zeros as .word or movs."""
    return other[:len(base)] == base and set(other[len(base):]) <= {".word", "movs"}


def compare(base, other):
    """Counts the functions whose instructions differ, and the shifts of the others."""
    changed = [n for n in base if n not in other or not same_code(base[n][1], other[n][1])]
    changed += [n for n in other if n not in base]
    shifts = Counter(other[n][0] - base[n][0] for n in base if n in other)
    return changed, shifts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", type=Path)
    ap.add_argument("placebos", nargs="+", type=Path)
    args = ap.parse_args()
    base = functions(args.base)
    print(f"{args.base.stem}: {len(base)} functions")
    failed = 0
    for path in args.placebos:
        changed, shifts = compare(base, functions(path))
        moved = sum(n for shift, n in shifts.items() if shift)
        print(f"{path.stem}: changed {len(changed)}, moved {moved}, shifts {dict(sorted(shifts.items()))}")
        if changed:
            print("  " + " ".join(changed[:12]))
            failed = 1
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
