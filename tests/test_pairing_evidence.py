"""Pairing evidence needs a current evaluator identity as well as placements.

The retained archive intentionally preserves measurements made before the evaluator began
stamping its revision.  They remain useful historical evidence, but cannot discharge a
current-evaluator claim: neither the placement schema nor the code that collected it can be
identified.  In particular, a legacy pair must not turn the production gate green merely because
its two serialized placements happen to agree.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pairing_evidence", ROOT / "scripts" / "audit_pairing_evidence.py")
PAIRING = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PAIRING)


def _row(regime: str, revision: str | None, *, diagnostics: bool = True) -> dict:
    native = {}
    if diagnostics:
        native["episode_diagnostics"] = [{"initial_placement": {"pos": [1, 2, 3]}}]
        native["placement_witnesses"] = [f"image-in-{regime}"]
    row = {
        "phase": "offline-eval", "regime": regime, "baseline": "idaac", "seed": 1,
        "scene_set": 0, "native": native,
    }
    if revision is not None:
        row["evaluator_revision"] = revision
    return row


def _write(tmp_path, *rows: dict) -> pathlib.Path:
    path = tmp_path / "records.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return path


def test_unstamped_legacy_pair_is_excluded_not_counted_as_current_evidence(tmp_path, capsys):
    path = _write(tmp_path, _row("train", None), _row("eval-easy", None))

    assert PAIRING.audit([str(path)]) == 0
    output = capsys.readouterr().out
    assert "0 eligible cross-regime comparisons" in output
    assert "1 legacy/ineligible group" in output
    assert "NOT a pass" in output


def test_current_unwitnessed_pair_remains_a_real_missing_evidence_failure(tmp_path, capsys):
    path = _write(tmp_path, _row("train", "a" * 64, diagnostics=False),
                  _row("eval-easy", "a" * 64, diagnostics=False))

    assert PAIRING.audit([str(path)]) == 0
    output = capsys.readouterr().out
    assert "1 lacking physical evidence" in output
    assert "0 legacy/ineligible groups excluded" in output


def _aggregate_row(regime: str, revision: str) -> dict:
    # A genuinely multi-scene aggregate: distinct scene_set from any per-scene row, and no
    # per-episode diagnostics by design (it is a pooled summary, not new evidence). Found for
    # real by the C95 R_A re-measurement (v178, ten scenes) -- it does not share a scene_set with
    # any single-scene row, so the existing "prefer the rich row" dedup never sees it.
    return {
        "phase": "offline-eval", "regime": regime, "baseline": "drqv2", "seed": 2,
        "scene_set": "0,1,2,3,4,5,6,7,8,9", "evaluator_revision": revision,
        "native": {"aggregate_over_scenes": list(range(10))},
    }


def test_multiscene_aggregate_is_pooled_not_counted_as_missing_evidence(tmp_path, capsys):
    path = _write(tmp_path, _aggregate_row("train", "b" * 64), _aggregate_row("eval-easy", "b" * 64))

    assert PAIRING.audit([str(path)]) == 0
    output = capsys.readouterr().out
    assert "0 eligible cross-regime comparisons" in output
    assert "0 lacking physical evidence" in output
    assert "1 pooled/ineligible groups excluded" in output
    assert "NOT a pass" in output
