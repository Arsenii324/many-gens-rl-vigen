"""The reconstruction gate must actually go red.

[Claude 2026-09-08] `gate_source_reconstruction_verifies` was added AFTER the condition it detects
had already been repaired, so it went straight to PASS and had never been observed failing. Against
this project's own standard -- "each has been made to actually fail when it should" -- that is
indistinguishable from a gate that cannot fail, which is the shape of `audit_row_closure.py`
comparing against a string `contract.py` could not emit.

So this corrupts the manifest, watches the gate turn FAIL, and restores it.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

LOCK = ROOT / "setup" / "source-reconstruction.json"


@pytest.fixture
def restored_lock(tmp_path):
    backup = tmp_path / "lock.json"
    shutil.copy2(LOCK, backup)
    yield
    shutil.copy2(backup, LOCK)


def _gate():
    import importlib
    module = importlib.import_module("production_gates")
    importlib.reload(module)
    return module.gate_source_reconstruction_verifies()


def test_it_passes_on_the_real_tree():
    status, detail = _gate()
    assert status == "PASS", detail


def test_it_fails_when_a_closure_hash_stops_matching(restored_lock):
    data = json.loads(LOCK.read_text())
    data["families"]["ctrl"]["expected_tree_hash"] = "0" * 64
    LOCK.write_text(json.dumps(data, indent=2) + "\n")
    status, detail = _gate()
    assert status == "FAIL", (status, detail)
    assert "no longer describes the trees" in detail


def test_it_fails_when_a_patch_hash_stops_matching(restored_lock):
    data = json.loads(LOCK.read_text())
    data["families"]["ctrl"]["patch_sha256"] = "0" * 64
    LOCK.write_text(json.dumps(data, indent=2) + "\n")
    status, _ = _gate()
    assert status == "FAIL"
