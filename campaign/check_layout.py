"""Shows that padding shifts the kernel and leaves its instructions unchanged."""
import argparse
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "_tools" / "sdk" / "zephyr-sdk-1.0.1" / "gnu" / "arm-zephyr-eabi" / "bin"
SYMBOLS = ["z_impl_k_sem_give", "z_impl_k_mutex_lock", "z_swap_irqlock", "main", "now"]


def symbols(elf):
    out = subprocess.run([BIN / "arm-zephyr-eabi-nm.exe", "-S", str(elf)], check=True,
                         capture_output=True, text=True).stdout
    table = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 4:
            table[parts[3]] = (int(parts[0], 16), int(parts[1], 16))
    return table


def body_digest(elf, name, table):
    """Hashes a function's bytes, so identical code gives identical digests."""
    start, size = table[name]
    dump = subprocess.run([BIN / "arm-zephyr-eabi-objdump.exe", "-d", "--no-show-raw-insn",
                           f"--start-address={start & ~1}", f"--stop-address={(start & ~1) + size}",
                           str(elf)], check=True, capture_output=True, text=True).stdout
    ops = [line.split("\t", 2)[1] for line in dump.splitlines() if "\t" in line and ":" in line]
    return hashlib.sha1(" ".join(ops).encode()).hexdigest()[:10]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("elfs", nargs="+", type=Path)
    args = ap.parse_args()
    for elf in args.elfs:
        table = symbols(elf)
        cells = []
        for name in SYMBOLS:
            if name in table:
                cells.append(f"{name}=0x{table[name][0]:05x}/{body_digest(elf, name, table)}")
        print(elf.stem, " ".join(cells))


if __name__ == "__main__":
    main()
