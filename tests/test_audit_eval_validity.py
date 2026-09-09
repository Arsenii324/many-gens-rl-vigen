"""The validity auditor must catch a summary that lies, a colliding id, and broken pairing.

Written after it found both on real data: 760 episode ids colliding across the endpoint's two
policy-mode passes, and eval-medium resampling its perturbation between passes in 62% of slots.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "audit_eval_validity.py"


def _run(p: pathlib.Path, *extra: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(SCRIPT), str(p), *extra],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def _row(regime="train", scene="0", frame=100, returns=(1.0, 3.0), ids=None, seeds=None,
         wits=None, mean=None, sd=None, mode="sample"):
    n = len(returns)
    return {"baseline": "b", "seed": 1, "frame": frame, "regime": regime, "scene_set": scene,
            "episodes": n, "episode_return_mean": 2.0 if mean is None else mean,
            "episode_return_sd": 1.4142135623730951 if sd is None else sd,
            "success_rate": 0.0, "phase": "offline-eval",
            "evaluator_scope": {"eval_scope": "endpoint", "eval_policy_mode": mode},
            "native": {"returns": list(returns), "episode_success": [0] * n,
                       "eval_episode_ids": ids or [f"b-s1-f{frame}-{regime}-sc{scene}-e{i}"
                                                   for i in range(n)],
                       "placement_condition_seeds": seeds or [10, 20][:n],
                       "placement_witnesses": wits or ["w0", "w1"][:n]}}


def _write(tmp_path, rows):
    p = tmp_path / "r.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def test_a_clean_file_passes(tmp_path):
    code, out = _run(_write(tmp_path, [_row()]), "--strict")
    assert code == 0, out
    assert "1. row summaries match their own raw episodes: PASS" in out
    assert "2. episode ids unique" in out and "PASS" in out


def test_a_summary_that_disagrees_with_its_own_episodes_fails(tmp_path):
    code, out = _run(_write(tmp_path, [_row(mean=99.0)]), "--strict")
    assert code == 1, out
    assert "episode_return_mean disagrees with its own returns" in out


def test_a_wrong_episode_count_fails(tmp_path):
    r = _row(); r["episodes"] = 7
    code, out = _run(_write(tmp_path, [r]), "--strict")
    assert code == 1, out
    assert "but 2 returns" in out


def test_colliding_episode_ids_fail(tmp_path):
    """The real defect: two policy-mode passes emit the same ids for different measurements."""
    a = _row(mode="sample")
    b = _row(mode="mode", returns=(5.0, 7.0), mean=6.0)
    code, out = _run(_write(tmp_path, [a, b]), "--strict")
    assert code == 1, out
    assert "2 duplicated" in out or "duplicated" in out


def test_broken_placement_pairing_fails(tmp_path):
    """placement_condition_seed omits the regime by design; differing seeds break the pairing."""
    a = _row(regime="train", seeds=[10, 20])
    b = _row(regime="eval-easy", seeds=[11, 21])
    code, out = _run(_write(tmp_path, [a, b]), "--strict")
    assert code == 1, out
    assert "placement seed identical across regimes" in out and "FAIL" in out


def test_reset_variation_is_reported_not_failed(tmp_path):
    """eval-medium resamples its perturbation by design; that is a limit, not a fault."""
    a = _row(regime="eval-medium", frame=100, wits=["x0", "x1"])
    b = _row(regime="eval-medium", frame=200, wits=["y0", "y1"])
    code, out = _run(_write(tmp_path, [a, b]), "--strict")
    assert code == 0, "reset variation must never fail the audit"
    assert "NOT paired" in out
    assert "100% vary" in out or "vary)" in out


def test_a_file_with_no_per_episode_detail_refuses(tmp_path):
    r = _row(); r["native"] = {}
    code, out = _run(_write(tmp_path, [r]))
    assert code == 2, out
    assert "NOT the same as nothing being wrong" in out
