#!/usr/bin/env python3
"""`scripts/verify_cells.py` must catch a cell whose two halves are not one experiment.

The table divides an `eval-easy` grid by a `train` grid and calls the ratio retention. That is only
retention if both grids evaluated the same weights under the same protocol with the regime as the
only difference. Nothing checked it before this — the table read `snapshot_md5` and printed it,
which is not the same as verifying the two agree.

Each test below breaks exactly one invariant on a synthetic pair and requires it to be reported.
A verifier that passes a broken pair is worse than none: it launders provenance.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("vc", ROOT / "scripts" / "verify_cells.py")
vc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vc)

GOOD = {
    "snapshot": None, "snapshot_md5": "a" * 32, "mode": "train", "episodes": 20,
    "seed": 0, "control_seed": 1, "action_repeat": 1, "task": "Door",
    "placement_seeded": True, "trained_step": 100000,
    "scenes": {str(i): {"returns": [1.0] * 20, "n_success": 0} for i in range(10)},
    "control": {"scene": 0, "returns": [1.0] * 20},
}


def write(tmp, tag, tr_over=None, ev_over=None):
    tr = copy.deepcopy(GOOD); tr.update(tr_over or {})
    ev = copy.deepcopy(GOOD); ev["mode"] = "eval-easy"; ev.update(ev_over or {})
    (tmp / f"{tag}__train.json").write_text(json.dumps(tr))
    (tmp / f"{tag}__eval-easy.json").write_text(json.dumps(ev))


@pytest.fixture
def grids(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "GRIDS", tmp_path)
    return tmp_path


def test_a_clean_pair_passes(grids):
    write(grids, "c")
    assert vc.check("x", 0, "100k", "c") == []


def test_different_weights_on_the_two_sides_is_caught(grids):
    """The one that would silently invalidate every retention number in the table."""
    write(grids, "c", ev_over={"snapshot_md5": "b" * 32})
    bad = vc.check("x", 0, "100k", "c")
    assert any("snapshot_md5 DIFFERS" in b for b in bad), bad


def test_a_regime_that_did_not_change_is_caught(grids):
    """RL-ViGen's own runner measured the training distribution twice (PART2 Finding 7)."""
    write(grids, "c", ev_over={"mode": "train"})
    assert any("not train/eval-easy" in b for b in vc.check("x", 0, "100k", "c"))


def test_a_pre_C69_grid_is_caught(grids):
    """Without seeded placement the two evaluations are not the same experiment (C69)."""
    write(grids, "c", tr_over={"placement_seeded": None})
    assert any("placement_seeded" in b for b in vc.check("x", 0, "100k", "c"))


def test_a_mislabelled_budget_is_caught(grids):
    """A 50k row built from a 100k checkpoint, or the reverse."""
    write(grids, "c", tr_over={"trained_step": 50000})
    assert any("labelled 100k but trained_step" in b for b in vc.check("x", 0, "100k", "c"))


def test_a_control_that_is_not_a_control_is_caught(grids):
    """If control_seed == seed the 'resolution floor' re-measures the same draw."""
    write(grids, "c", tr_over={"control_seed": 0})
    assert any("control_seed equals seed" in b for b in vc.check("x", 0, "100k", "c"))


def test_a_differing_protocol_is_caught(grids):
    write(grids, "c", ev_over={"episodes": 10})
    assert any("episodes differs" in b for b in vc.check("x", 0, "100k", "c"))


def test_differing_scene_sets_are_caught(grids):
    ev = copy.deepcopy(GOOD); ev["mode"] = "eval-easy"
    del ev["scenes"]["9"]
    (grids / "c__train.json").write_text(json.dumps(GOOD))
    (grids / "c__eval-easy.json").write_text(json.dumps(ev))
    assert any("scene sets differ" in b for b in vc.check("x", 0, "100k", "c"))


# [Claude 2026-09-04] The guard now names the directory these tests ACTUALLY need
# (results/regime-retention-c69, the retention grids), not the generic results/ parent. It was a
# PROXY -- "does results/ exist" standing in for "has anything been tabulated here" -- and it held
# only while results/ had exactly one use. On 2026-09-04 results/records/ and results/logs/ were
# added to retain returned job artifacts (R7, EVAL-PROTOCOL section 6), the parent came into
# existence for an unrelated reason, and these tests went from SKIPPED to FAILING against grids
# that have never existed in this tree. The failure was real information about the guard, not
# about the cells.
@pytest.mark.skipif(not (ROOT / "results" / "regime-retention-c69").is_dir(),
                    reason="no retention grids in this tree: nothing has been tabulated here")
def test_the_real_cells_pass_every_invariant():
    """The live claim: every tabulated number comes from the run it says it does."""
    bad = []
    for name, seed, budget, tag in vc._rt.CELLS:
        bad += [b for b in vc.check(name, seed, budget, tag) if "NOTE" not in b]
    assert not bad, "a tabulated cell fails a provenance invariant:\n  " + "\n  ".join(bad)
