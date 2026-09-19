"""The production wrappers must not let a slow baseline train under an unverified 12h default.

`train-production-cell-v5.sh` and `-v6.sh` both default `CELL_TIMEOUT_SECONDS` to 43200 (12h) via
`TIMEOUT_S`. Seven of the twelve baselines are scheduled to train longer than that on the
DataSphere T4 tier (`datasphere/native/production-schedule.json`'s `solo_hours_per_seed_gt4_1`) --
V100 throughput is UNMEASURED for all of them, so a T4-tier hour is the best number available, not
a promise. Only `idaac`, `ppg` and `ibac_sni` have a MEASURED sub-12h V100 training time
(`notes/OPERATOR-GUIDE.md` §4c.1). `svea` was launched with the bare 12h default on 2026-09-19 and
would have been cut near 430k/600k frames with no warning.

Both wrappers now refuse (exit 2, before `launch-card-cell.sh` is ever invoked) when `TIMEOUT_S` is
unset and the baseline is not one of the three measured-fast ones -- including a baseline the
embedded schedule table does not know at all. When `TIMEOUT_S` IS set, any value is accepted, but
one below the baseline's scheduled seconds prints a loud warning and continues.

These tests stub out `datasphere/native/launch-card-cell.sh` itself -- a path the wrapper `cd`s to
`~/rlvigen-work/repo` and then calls directly (not something on PATH) -- so nothing here launches a
container or touches the real host, and record its argv/environment to prove it was (or was not)
reached.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
V5 = ROOT / "datasphere" / "native" / "host-scripts" / "train-production-cell-v5.sh"
V6 = ROOT / "datasphere" / "native" / "host-scripts" / "train-production-cell-v6.sh"
SCHEDULE = ROOT / "datasphere" / "native" / "production-schedule.json"
WRAPPERS = [V5, V6]

STUB_LAUNCH_CARD_CELL = """#!/bin/sh
{
  echo "ARGV: $*"
  env
} > "$STUB_RECORD"
exit 0
"""


def _sandbox(tmp_path: pathlib.Path) -> tuple[dict, pathlib.Path]:
    home = tmp_path
    repo = home / "rlvigen-work" / "repo"
    (repo / "datasphere" / "native").mkdir(parents=True)
    stub = repo / "datasphere" / "native" / "launch-card-cell.sh"
    stub.write_text(STUB_LAUNCH_CARD_CELL)
    stub.chmod(0o755)
    # v6 refuses if this is missing; v5 hardcodes the same path but never checks it, so creating
    # it is harmless there and required here.
    (home / "rlvigen-work" / "payload-v214-stub.tgz").write_bytes(b"")
    record = tmp_path / "stub-record.txt"
    env = dict(os.environ)
    env.update({
        "HOME": str(home),
        "FAMILY": "stub", "SEED": "1",
        "STUB_RECORD": str(record),
    })
    return env, record


def _run(wrapper: pathlib.Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(wrapper)], env=env,
                          capture_output=True, text=True, timeout=30)


@pytest.mark.skipif(not (V5.exists() and V6.exists()), reason="wrapper script(s) missing")
@pytest.mark.parametrize("wrapper", WRAPPERS, ids=["v5", "v6"])
def test_a_slow_unmeasured_baseline_refuses_without_timeout_s(wrapper, tmp_path):
    """svea has no measured sub-12h V100 time: refuse, and never reach launch-card-cell.sh."""
    env, record = _sandbox(tmp_path)
    env["BASELINE"] = "svea"
    result = _run(wrapper, env)
    combined = result.stdout + result.stderr
    assert result.returncode == 2, combined
    assert "REFUSING" in combined, combined
    assert not record.exists(), "launch-card-cell.sh must never be invoked"


@pytest.mark.skipif(not (V5.exists() and V6.exists()), reason="wrapper script(s) missing")
@pytest.mark.parametrize("wrapper", WRAPPERS, ids=["v5", "v6"])
def test_a_measured_fast_baseline_keeps_todays_default_byte_for_byte(wrapper, tmp_path):
    """idaac (and ppg, ibac_sni) must launch with CELL_TIMEOUT_SECONDS=43200, exactly as today."""
    env, record = _sandbox(tmp_path)
    env["BASELINE"] = "idaac"
    result = _run(wrapper, env)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert record.exists(), combined
    body = record.read_text()
    assert "CELL_TIMEOUT_SECONDS=43200" in body, body
    assert "WARNING" not in combined, combined


@pytest.mark.skipif(not (V5.exists() and V6.exists()), reason="wrapper script(s) missing")
@pytest.mark.parametrize("wrapper", WRAPPERS, ids=["v5", "v6"])
def test_an_explicit_timeout_above_schedule_is_accepted_without_warning(wrapper, tmp_path):
    env, record = _sandbox(tmp_path)
    env["BASELINE"] = "svea"
    env["TIMEOUT_S"] = "90000"          # svea's scheduled seconds is 60048
    result = _run(wrapper, env)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    body = record.read_text()
    assert "CELL_TIMEOUT_SECONDS=90000" in body, body
    assert "WARNING" not in combined, combined


@pytest.mark.skipif(not (V5.exists() and V6.exists()), reason="wrapper script(s) missing")
@pytest.mark.parametrize("wrapper", WRAPPERS, ids=["v5", "v6"])
def test_an_explicit_timeout_below_schedule_is_accepted_with_a_warning(wrapper, tmp_path):
    env, record = _sandbox(tmp_path)
    env["BASELINE"] = "svea"
    env["TIMEOUT_S"] = "3600"           # well below svea's scheduled 60048s
    result = _run(wrapper, env)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    body = record.read_text()
    assert "CELL_TIMEOUT_SECONDS=3600" in body, body
    assert "WARNING" in combined, combined


@pytest.mark.skipif(not (V5.exists() and V6.exists()), reason="wrapper script(s) missing")
@pytest.mark.parametrize("wrapper", WRAPPERS, ids=["v5", "v6"])
def test_an_unknown_baseline_refuses_without_timeout_s(wrapper, tmp_path):
    env, record = _sandbox(tmp_path)
    env["BASELINE"] = "not-a-real-baseline"
    result = _run(wrapper, env)
    combined = result.stdout + result.stderr
    assert result.returncode == 2, combined
    assert "REFUSING" in combined, combined
    assert not record.exists()


def _embedded_schedule(wrapper: pathlib.Path) -> dict[str, int]:
    text = wrapper.read_text()
    table = {}
    for m in re.finditer(r"^\s*([a-z0-9_]+)\)\s*echo\s+(\d+)\s*;;", text, re.MULTILINE):
        table[m.group(1)] = int(m.group(2))
    return table


@pytest.mark.skipif(not (V5.exists() and V6.exists() and SCHEDULE.exists()),
                    reason="wrapper script(s) or schedule missing")
def test_the_embedded_schedule_matches_production_schedule_json():
    """The wrappers cannot read the JSON on the host, so this is what stops the copy drifting."""
    schedule = json.loads(SCHEDULE.read_text())
    expected = {row["baseline"]: round(float(row["solo_hours_per_seed_gt4_1"]) * 3600)
                for row in schedule["rows"]}
    for wrapper in WRAPPERS:
        embedded = _embedded_schedule(wrapper)
        assert embedded, f"no embedded schedule table found in {wrapper}"
        assert embedded == expected, (
            f"{wrapper.name} has drifted from {SCHEDULE.name}:\n"
            f"  embedded: {sorted(embedded.items())}\n"
            f"  JSON:     {sorted(expected.items())}")
    assert _embedded_schedule(V5) == _embedded_schedule(V6), "v5 and v6 tables disagree"
