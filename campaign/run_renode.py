"""Runs one image in Renode and writes its UART output to a log file."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RENODE = ROOT / "_tools" / "renode" / "renode_1.17.0-portable" / "renode.exe"
SCRIPT = ROOT / "campaign" / "renode" / "bench.resc"


def run(elf, log, seconds=60, port=1234):
    log.parent.mkdir(parents=True, exist_ok=True)
    log.unlink(missing_ok=True)
    commands = (f'$elf=@{elf.resolve().as_posix()}; $log=@{log.resolve().as_posix()}; '
                f'$runtime="{seconds}"; include @{SCRIPT.as_posix()}')
    return subprocess.run([str(RENODE), "--disable-gui", "--plain", "--port", str(port), "-e", commands],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=600)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("elf", type=Path)
    ap.add_argument("log", type=Path)
    ap.add_argument("--seconds", type=int, default=60, help="emulated seconds")
    args = ap.parse_args()
    done = run(args.elf, args.log, args.seconds)
    tail = (done.stdout + done.stderr).strip().splitlines()[-15:]
    print("\n".join(tail))
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
