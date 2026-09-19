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
import datetime
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
    # The cell's own top-level `seed` first: argv spelling differs per family (`--seed 101` for the
    # on-policy families, hydra's `seed=101` for rlvigen), and a None seed mis-keys the attempt
    # ledger, which groups on (baseline, seed).
    seed = str(cfg["seed"]) if cfg.get("seed") is not None else None
    for i, a in enumerate(argv):
        if seed is not None:
            break
        if a == "--seed" and i + 1 < len(argv):
            seed = argv[i + 1]
        elif isinstance(a, str) and a.startswith("seed="):
            seed = a.split("=", 1)[1]
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
        # [Claude 2026-09-09, review B3] A status is a SNAPSHOT. Without a timestamp beside it a
        # reader next week sees a confident present-tense claim about a run that finished or died
        # hours later. It cannot stop a stale status misleading, but it stops it doing so silently.
        "status_as_of": datetime.datetime.now(datetime.timezone.utc)
                        .replace(microsecond=0).isoformat(),
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

    # [Claude 2026-09-16] A status update must not require the run directory. Every field this
    # script derives comes from the cell's own effective_config.json, which lives ON THE HOST -- so
    # `--update-status` demanded a directory that is never present on the laptop, and the one
    # operation the ledger exists for (moving a run off `running` to a terminal status) could not be
    # performed from where the operator sits. audit_attempt_ledger --strict fails on exactly that
    # missing terminal status, so the check and the tool disagreed.
    #
    # When the entry already exists, its derived fields were recorded at launch and are not in
    # question; only status, note and status_as_of are. Update those in place and leave the rest
    # untouched. Refuse when the entry does NOT exist: without the config there is nothing to
    # derive a new entry from, and inventing one would put an unsourced row in the ledger.
    if args.update_status and not run_dir.is_dir():
        existing = _entries()
        prior = [x for x in existing if x.get("run_id") == run_dir.name]
        if not prior:
            print(f"REFUSING: {run_dir.name} is not in {LEDGER.relative_to(ROOT)}, and without")
            print("  its run directory there is no effective_config.json to derive an entry from.")
            print("  Record it from the directory first, or fetch the directory.")
            return 2
        updated = dict(prior[-1])
        updated["status"] = args.status
        updated["status_as_of"] = (datetime.datetime.now(datetime.timezone.utc)
                                   .replace(microsecond=0).isoformat())
        if args.note:
            updated["note"] = args.note
        updated["recorded_by"] = (prior[-1].get("recorded_by", "") +
                                  "; status updated by scripts/record_host_run.py --update-status "
                                  "without the run directory, which is on the host")
        if args.dry_run:
            print(json.dumps(updated, sort_keys=True))
            return 0
        out = [updated if x.get("run_id") == run_dir.name else x for x in existing]
        LEDGER.write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in out))
        print(f"updated {run_dir.name} -> status={args.status}")
        print("  Derived fields were left as recorded at launch; only status/note/status_as_of moved.")
        print("  Regenerate the register: python scripts/production_run_register.py")
        return 0

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
