"""Runs one QEMU image under icount until the benchmark ends, and writes its UART to a log.

With -icount shift=7 one instruction takes 128 ns, or 3.2 ticks of the 25 MHz timer read by
the image. Deltas are ratios, so the scale does not matter.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QEMU = ROOT / "_tools" / "sdk" / "zephyr-sdk-1.0.1" / "hosttools" / "qemu" / "qemu-system-arm.exe"
ARGS = ["-machine", "mps2-an385", "-cpu", "cortex-m3", "-nographic", "-vga", "none",
        "-net", "none", "-monitor", "none", "-icount", "shift=7,align=off,sleep=off"]


def run(elf, log, limit=120):
    log.parent.mkdir(parents=True, exist_ok=True)
    log.unlink(missing_ok=True)
    # QEMU refuses a drive letter after file:, so the log is named from its folder.
    proc = subprocess.Popen([str(QEMU), *ARGS, "-kernel", str(elf.resolve()),
                             "-serial", f"file:{log.name}"], cwd=log.parent,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    stop = time.monotonic() + limit
    try:
        while time.monotonic() < stop and proc.poll() is None:
            time.sleep(0.5)
            if log.exists() and "BENCH,DONE" in log.read_text(errors="replace"):
                return 0
        return 1
    finally:
        proc.kill()
        proc.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("elf", type=Path)
    ap.add_argument("log", type=Path)
    ap.add_argument("--limit", type=int, default=120, help="wall clock seconds")
    args = ap.parse_args()
    return run(args.elf, args.log, args.limit)


if __name__ == "__main__":
    sys.exit(main())
