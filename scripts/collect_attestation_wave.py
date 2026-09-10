#!/usr/bin/env python3
"""Collect whichever v212 attestation cells have finished, and populate the ledger for each.

    python scripts/collect_attestation_wave.py                 # collect what is ready
    python scripts/collect_attestation_wave.py --dry-run       # report, install nothing

Written after doing it by hand for four families, because the manual sequence is where the mistakes
were: finding the real output directory (`launch-card-cell.sh` OVERRIDES `NATIVE_OUT_HOST_DIR`, so
the delivery is under `rlvigen-runs/card0-<stamp>/native-out`, not under the directory the caller
named), copying `records_delivery.jsonl` rather than `records.jsonl`, and remembering that
`populate_evaluator_ledger.py` refuses a record whose revision is not the live one -- which is the
most valuable thing it does and must never be worked around.

It REFUSES a family whose cell did not report `NATIVE_CELL_COMPLETED`. A cell that yielded, failed
or was reaped has records describing a run that did not finish, and this project's rule is that an
instrument which could not run must never read as one that ran.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HOST = "varaksin_as@100.98.2.11"
WAVE = "~/rlvigen-runs/attest-v212"
FAMILIES = ("idaac", "ppg", "alda", "ibac_sni", "ctrl", "rlvigen", "dmc_gb")


def ssh(command: str) -> str:
    proc = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", HOST, command],
                          capture_output=True, text=True, timeout=180)
    return proc.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--families", default=",".join(FAMILIES))
    args = parser.parse_args()

    installed = refused = 0
    for family in [f.strip() for f in args.families.split(",") if f.strip()]:
        log = f"{WAVE}/{family}.log"
        markers = ssh(f"grep -aoE 'NATIVE_(CELL_COMPLETED|CELL_FAILED|CELL_YIELDED)[^=]*' {log} 2>/dev/null | tail -3")
        if not markers.strip():
            print(f"  {family:10} no log yet -- not run")
            continue
        if "NATIVE_CELL_COMPLETED" not in markers:
            state = markers.strip().splitlines()[-1].strip()
            print(f"  {family:10} REFUSING: {state}")
            refused += 1
            continue
        out = ssh(f"grep -aoE 'cell output[^:]*: \\S+' {log} 2>/dev/null | tail -1 | awk '{{print $NF}}'").strip()
        if not out:
            print(f"  {family:10} REFUSING: completed but no cell-output directory in the log")
            refused += 1
            continue
        target = ROOT / "results" / "records" / f"attest-v212-{family}__records.jsonl"
        if args.dry_run:
            print(f"  {family:10} would install from {out}")
            continue
        copy = subprocess.run(
            ["scp", "-q", "-o", "BatchMode=yes", f"{HOST}:{out}/records_delivery.jsonl", str(target)],
            capture_output=True, text=True, timeout=600)
        if copy.returncode != 0 or not target.is_file():
            print(f"  {family:10} REFUSING: could not fetch records_delivery.jsonl from {out}")
            refused += 1
            continue
        rows = len([line for line in target.read_text().splitlines() if line.strip()])
        populate = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "populate_evaluator_ledger.py"),
             family, f"attest-v212-{family}"],
            capture_output=True, text=True, timeout=300)
        ok = populate.returncode == 0 and "Do NOT write this entry" not in populate.stdout
        print(f"  {family:10} {rows:4d} rows  ledger={'written' if ok else 'REFUSED'}")
        if not ok:
            print("      " + (populate.stdout or populate.stderr).strip().splitlines()[-1])
            refused += 1
        else:
            installed += 1

    print(f"\n{installed} installed, {refused} refused.")
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
