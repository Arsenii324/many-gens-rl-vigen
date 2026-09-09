#!/usr/bin/env python3
"""Record that a host cell exists, from its own config, before anyone needs its results.

    python scripts/record_host_run.py <fetched-run-dir> --status "training complete; curve running"
    python scripts/record_host_run.py <fetched-run-dir> --note "..." --dry-run

## Why

A cell that ran on the production host and was never collected is invisible to
`results/PRODUCTION-RUNS.md`, because that register is generated from `results/records/`. On
2026-09-09 the two most important runs this project had ever produced existed **only** on the host
and in one session's memory. If that session had ended, nothing in the repository would have said
they happened.

So the run's existence is recorded when it launches, separately from its results, and read from
**the cell's own `effective_config.json`** rather than typed — the same artifact the runner writes
and `audit_executed_hyperparameters.py` reads.

## What it will not do

**It never overwrites an existing entry for the same `run_id`.** A run id is the run directory
basename, unique per launch at second resolution; a second entry for one would mean either a
re-record (use `--update-status`) or two runs sharing a name, and silently replacing the first is
how a launch disappears.

**It records circumstances, not results.** Metrics come from the records, through the register.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "results" / "host-runs.jsonl"


def _entries() -> list[dict]:
    if not LEDGER.is_file():
        return []
    out = []
    for line in LEDGER.read_text(errors="replace").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def entry_from(run_dir: pathlib.Path, host: str, status: str, note: str | None) -> dict:
    cells = sorted((run_dir / "native-out" / "cells").glob("*/effective_config.json"))
    if not cells:
        cells = sorted(run_dir.glob("cells/*/effective_config.json"))
    if not cells:
        raise SystemExit(f"no cells/*/effective_config.json under {run_dir}. Nothing recorded — "
                         "which is NOT the same as nothing having run.")
    cfg = json.loads(cells[0].read_text())
    env = cfg.get("runner_environment", {}) or {}
    argv = cfg.get("argv", []) or []
    seed = None
    for i, a in enumerate(argv):
        if a == "--seed" and i + 1 < len(argv):
            seed = argv[i + 1]
            break
    return {
        "run_id": run_dir.name,
        "host": host,
        "card": int(run_dir.name[4]) if run_dir.name.startswith("card") else None,
        "family": cfg.get("family"),
        "baseline": cfg.get("baseline"),
        "cell": cfg.get("cell"),
        "seed": int(seed) if seed and seed.isdigit() else seed,
        "frames_requested": int(cfg.get("frames_requested") or 0) or None,
        "host_profile": cfg.get("host_profile"),
        "vram_cap_mib": int(env["NATIVE_VRAM_CAP_MIB"]) if env.get("NATIVE_VRAM_CAP_MIB") else None,
        "curve_eval_episodes": int(env["CURVE_EVAL_EPISODES"]) if env.get("CURVE_EVAL_EPISODES") else None,
        "endpoint_eval_episodes": int(env["ENDPOINT_EVAL_EPISODES"]) if env.get("ENDPOINT_EVAL_EPISODES") else None,
        "endpoint_policy_modes": env.get("ENDPOINT_EVAL_POLICY_MODES"),
        "cells_declared": env.get("CELLS"),
        "run_dir": f"~/rlvigen-runs/{run_dir.name}",
        "status": status,
        "recorded_by": "scripts/record_host_run.py, from the cell's own effective_config.json",
        **({"note": note} if note else {}),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_dir")
    ap.add_argument("--host", default="100.98.2.11")
    ap.add_argument("--status", default="launched")
    ap.add_argument("--note")
    ap.add_argument("--launched-msk", help="e.g. 2026-09-09T03:52; defaults to the id's timestamp")
    ap.add_argument("--update-status", action="store_true",
                    help="replace an existing entry's status/note rather than refusing")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    run_dir = pathlib.Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"not a directory: {run_dir}")
        return 2

    e = entry_from(run_dir, args.host, args.status, args.note)
    stamp = args.launched_msk
    if not stamp and "-" in run_dir.name:
        parts = run_dir.name.split("-")
        if len(parts) >= 3 and len(parts[1]) == 8 and len(parts[2]) >= 4:
            d, t = parts[1], parts[2]
            stamp = f"{d[:4]}-{d[4:6]}-{d[6:8]}T{t[:2]}:{t[2:4]}"
    e["launched_msk"] = stamp

    existing = _entries()
    same = [x for x in existing if x.get("run_id") == e["run_id"]]
    if same and not args.update_status:
        print(f"REFUSING: {e['run_id']} is already recorded in {LEDGER.relative_to(ROOT)}.")
        print("  A run id is unique per launch, so a duplicate means a re-record or two runs")
        print("  sharing a name. Replacing it silently is how a launch disappears.")
        print("  Use --update-status to change its status/note deliberately.")
        return 1

    if args.dry_run:
        print(json.dumps(e, sort_keys=True))
        return 0

    if same:
        out = [e if x.get("run_id") == e["run_id"] else x for x in existing]
        verb = "updated"
    else:
        out = existing + [e]
        verb = "recorded"
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in out))
    print(f"{verb} {e['run_id']} ({e.get('baseline')}, seed {e.get('seed')}) "
          f"-> {LEDGER.relative_to(ROOT)}")
    print("  Regenerate the register: python scripts/production_run_register.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
