"""Runs every image of a folder in one emulator, skipping the logs already complete."""
import argparse
import time
from pathlib import Path

import run_qemu
import run_renode

ATTEMPTS = 3


def complete(log):
    return log.exists() and "BENCH,DONE" in log.read_text(encoding="utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("emulator", choices=["renode", "qemu"])
    ap.add_argument("elves", type=Path, help="folder of images")
    ap.add_argument("logs", type=Path, help="folder of logs")
    ap.add_argument("--match", default="*.elf")
    ap.add_argument("--list", type=Path, help="only the images named in this file")
    ap.add_argument("--seconds", type=int, default=30, help="emulated seconds under Renode")
    ap.add_argument("--port", type=int, default=1234, help="Renode monitor port, one per instance")
    args = ap.parse_args()

    if args.list:
        elves = [args.elves / f"{name}.elf" for name in args.list.read_text(encoding="ascii").split()]
    else:
        elves = sorted(args.elves.glob(args.match))

    failed = []
    for elf in elves:
        log = args.logs / f"{elf.stem}.log"
        if complete(log):
            continue
        start = time.monotonic()
        for attempt in range(ATTEMPTS):
            if args.emulator == "renode":
                run_renode.run(elf, log, args.seconds, args.port)
            else:
                run_qemu.run(elf, log)
            if complete(log):
                break
            print(f"incomplete: {elf.stem}, attempt {attempt + 1}", flush=True)
        else:
            failed.append(elf.stem)
        print(f"{elf.stem} {time.monotonic() - start:.1f} s", flush=True)
    print(f"failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
