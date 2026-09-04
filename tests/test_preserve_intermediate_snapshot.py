#!/usr/bin/env python3
"""`scripts/preserve_intermediate_snapshot.py` must copy exactly one run's 50k point — C68/C73.

This instrument decides whether a 100k cell also yields a 50k measurement, and every way it can be
wrong is silent. If it preserves a *pre-existing* run's snapshot, the project gains a "50k point"
that no live run produced. If it preserves the wrong seed or the wrong budget, two cells get mixed
under one name. If it overwrites an existing preserved copy, the earlier point is destroyed by the
tool whose whole purpose is not destroying it. None of those raise; all of them produce a plausible
file.

So this runs the real script as a subprocess against a temporary tree containing one dir that
*should* be preserved and four that should not, and checks all five outcomes. Any loosened filter
turns it red.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "preserve_intermediate_snapshot.py"

WANT = "17_action_repeat=1,num_train_frames=100000,seed=7,task@_global_=Door"
PRE_EXISTING = "09_action_repeat=1,num_train_frames=100000,seed=7,task@_global_=Door"
WRONG_SEED = "18_action_repeat=1,num_train_frames=100000,seed=1,task@_global_=Door"
WRONG_BUDGET = "19_action_repeat=1,num_train_frames=50000,seed=7,task@_global_=Door"
ALREADY_DONE = "20_action_repeat=1,num_train_frames=100000,seed=7,task@_global_=Lift"


def _write(d: pathlib.Path, name: str, body: bytes) -> pathlib.Path:
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_bytes(body)
    return p


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    root = tmp_path_factory.mktemp("exp_local")
    # Present BEFORE the instrument starts: its snapshot is already final and must be left alone.
    _write(root / "2026.08.20" / PRE_EXISTING, "snapshot.pt", b"OLD-RUN-ALREADY-FINISHED")

    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), "--root", str(root),
         "--match", "num_train_frames=100000", "--seed", "7",
         "--seconds", "25", "--interval", "0.4", "--stable-gap", "0.15"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(2.0)  # let it take its "seen before" census

    base = root / "2026.08.26"
    _write(base / WANT, "snapshot.pt", b"LIVE-RUN-50K-WEIGHTS")
    _write(base / WRONG_SEED, "snapshot.pt", b"OTHER-SEED")
    _write(base / WRONG_BUDGET, "snapshot.pt", b"OTHER-BUDGET")
    _write(base / ALREADY_DONE, "snapshot.pt", b"SECOND-SAVE")
    _write(base / ALREADY_DONE, "snapshot_50k_frames.pt", b"FIRST-SAVE-MUST-SURVIVE")

    out = proc.communicate(timeout=60)[0]
    return root, base, out


def test_the_live_run_is_preserved_byte_for_byte(run):
    _, base, out = run
    dest = base / WANT / "snapshot_50k_frames.pt"
    assert dest.exists(), f"the one snapshot it exists to keep was not copied.\n{out}"
    assert dest.read_bytes() == b"LIVE-RUN-50K-WEIGHTS", "copied, but not faithfully"


def test_a_pre_existing_run_is_never_preserved(run):
    """Copying this one would invent a 50k point no live run produced."""
    root, _, out = run
    assert not (root / "2026.08.20" / PRE_EXISTING / "snapshot_50k_frames.pt").exists(), (
        f"preserved a run that was already finished before the instrument started.\n{out}")


def test_the_wrong_seed_and_the_wrong_budget_are_skipped(run):
    _, base, out = run
    assert not (base / WRONG_SEED / "snapshot_50k_frames.pt").exists(), f"seed filter is dead.\n{out}"
    assert not (base / WRONG_BUDGET / "snapshot_50k_frames.pt").exists(), f"match filter is dead.\n{out}"


def test_an_existing_preserved_copy_is_not_overwritten(run):
    """The one destructive thing this tool could do, done by the tool built to prevent it."""
    _, base, out = run
    kept = (base / ALREADY_DONE / "snapshot_50k_frames.pt").read_bytes()
    assert kept == b"FIRST-SAVE-MUST-SURVIVE", (
        f"an already-preserved 50k point was overwritten by a later save.\n{out}")


def test_it_reports_exactly_one_preservation(run):
    _, _, out = run
    assert out.count("PRESERVED") == 1, f"expected exactly one preservation, got:\n{out}"
