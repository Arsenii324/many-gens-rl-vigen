"""A host run's existence must be recorded from its own config, and never silently replaced.

On 2026-09-09 the two most important runs this project had produced existed only on the production
host and in one session's memory. Nothing in the repository said they had happened.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "record_host_run.py"


def _run(*args: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=str(ROOT))
    return proc.returncode, proc.stdout + proc.stderr


def _rundir(tmp_path: pathlib.Path, name="card0-20260101-010203") -> pathlib.Path:
    d = tmp_path / name / "native-out" / "cells" / "idaac-s101"
    d.mkdir(parents=True)
    (d / "effective_config.json").write_text(json.dumps({
        "family": "idaac", "baseline": "idaac", "cell": "idaac-s101",
        "frames_requested": "600000", "host_profile": "v100",
        "argv": ["x", "--seed", "101"],
        "runner_environment": {"NATIVE_VRAM_CAP_MIB": "4096", "CURVE_EVAL_EPISODES": "3",
                               "ENDPOINT_EVAL_EPISODES": "20",
                               "ENDPOINT_EVAL_POLICY_MODES": "native,mode", "CELLS": "idaac:101"},
    }))
    return tmp_path / name


def test_the_entry_is_derived_from_the_cells_own_config(tmp_path):
    code, out = _run(str(_rundir(tmp_path)), "--dry-run")
    assert code == 0, out
    e = json.loads(out.strip().splitlines()[-1])
    assert e["baseline"] == "idaac" and e["seed"] == 101
    assert e["frames_requested"] == 600000 and e["vram_cap_mib"] == 4096
    assert e["endpoint_policy_modes"] == "native,mode"
    assert e["launched_msk"] == "2026-01-01T01:02", "the timestamp comes from the run id"
    assert "effective_config.json" in e["recorded_by"]


def test_dry_run_writes_nothing(tmp_path):
    ledger = ROOT / "results" / "host-runs.jsonl"
    before = ledger.read_text() if ledger.is_file() else None
    code, _ = _run(str(_rundir(tmp_path)), "--dry-run")
    assert code == 0
    after = ledger.read_text() if ledger.is_file() else None
    assert after == before


def test_a_run_dir_with_no_cell_config_refuses(tmp_path):
    d = tmp_path / "card0-20260101-010203"
    (d / "native-out").mkdir(parents=True)
    code, out = _run(str(d), "--dry-run")
    assert code != 0
    assert "NOT the same as nothing having run" in out


def test_the_real_ledger_has_both_production_cells():
    entries = [json.loads(l) for l in
               (ROOT / "results" / "host-runs.jsonl").read_text().splitlines() if l.strip()]
    ids = {e["run_id"] for e in entries}
    assert "card0-20260909-035152" in ids, "the first complete production cell must be recorded"
    assert "card0-20260909-115331" in ids
    for e in entries:
        assert e.get("status"), f"{e['run_id']} has no status"
        assert e.get("run_dir"), f"{e['run_id']} has no run_dir"


def test_every_ledger_run_id_is_unique():
    entries = [json.loads(l) for l in
               (ROOT / "results" / "host-runs.jsonl").read_text().splitlines() if l.strip()]
    ids = [e["run_id"] for e in entries]
    assert len(ids) == len(set(ids)), f"duplicate run_id in host-runs.jsonl: {ids}"


def test_the_register_lists_the_uncollected_runs():
    text = (ROOT / "results" / "PRODUCTION-RUNS.md").read_text()
    assert "Runs on the production host not yet collected" in text
    assert "card0-20260909-035152" in text
    assert "have produced no record file here" in text
