"""tools/nd_ln_parity.py: the Nd_ln-shaped read of our own results, computed alongside the full
protocol from the same episodes.csv rows -- never a second run, never a protocol change.

No real run exists yet (docs/dz-report-ru.md sec.1: zero training runs as of 2026-08-13), so every
number here is hand-verified against synthetic rows built directly from `tags.EPISODE_COLUMNS`, not
against a real evaluation. That is exactly the right amount of testing for a reporting tool with no
data to report on yet: prove the arithmetic before the day it matters, not after.
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rlgen import tags  # noqa: E402
from tools.nd_ln_parity import load_episodes, group_by_run, nd_ln_parity_row  # noqa: E402


def _row(*, mode, scene_id, ret, frames="100000", baseline="alda", task="Door", seed="0",
        episode_idx=0):
    d = {
        "baseline": baseline, "backbone": "sac", "task": task, "mode": mode,
        "scene_id": scene_id, "seed": seed, "frames": frames, "checkpoint": "ckpt.pt",
        "episode_idx": episode_idx, "return_raw": ret, "episode_len": 500,
        "terminated": False, "truncated": True, "success": "",
        "policy_mode": "deterministic", "protocol_hash": "deadbeef",
        "weights_source": "trained", "code_commit": "abc123",
    }
    return [d[c] for c in tags.EPISODE_COLUMNS]


def write_episodes_csv(path: str, rows: list[list]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(tags.EPISODE_COLUMNS)
        w.writerows(rows)


def test_scene0_and_full_protocol_means_diverge_when_scene0_is_unrepresentative():
    """The whole point of the tool: scene 0 alone can tell a different story from the 10-scene
    mean. Construct exactly that: scene 0 trains and evaluates well; scenes 1-2 are near zero on
    eval -- a realistic shape per DISCREPANCY_MATRIX.md's own measured Door numbers (~88 on scene
    0, 0.7-4.2 on scenes 1-9)."""
    rows = (
        [_row(mode="train", scene_id="0", ret=r) for r in (85.0, 91.0)]
        + [_row(mode="eval-easy", scene_id="0", ret=r) for r in (80.0, 90.0)]
        + [_row(mode="eval-easy", scene_id="1", ret=r) for r in (1.0, 2.0)]
        + [_row(mode="eval-easy", scene_id="2", ret=r) for r in (0.5, 1.5)]
    )
    grp = {"k": [dict(zip(tags.EPISODE_COLUMNS, r)) for r in rows]}
    out = nd_ln_parity_row(grp["k"], min_train_denominator=1.0)

    assert out["train_scene0_mean"] == pytest.approx(88.0)
    assert out["eval_scene0_mean"] == pytest.approx(85.0)
    assert out["n_eval_scene0_episodes"] == 2
    assert out["retention_nd_ln_parity"] == pytest.approx(85.0 / 88.0)

    # full-protocol eval mean pools all three scenes -- much lower, correctly
    assert out["eval_full_mean"] == pytest.approx((80 + 90 + 1 + 2 + 0.5 + 1.5) / 6)
    assert out["retention_full_protocol"] < out["retention_nd_ln_parity"], (
        "scene 0 was deliberately made the best-performing scene; the full-protocol retention "
        "must come out lower than the Nd_ln-parity (scene-0-only) retention, or the two views "
        "are not actually measuring what they claim to")


def test_retention_is_refused_not_printed_against_a_near_zero_denominator():
    """Same failure mode plot.py already declines to draw: a ratio against a near-zero training
    score is not a number, it is noise wearing a percentage sign."""
    rows = [_row(mode="train", scene_id="0", ret=0.05),
           _row(mode="eval-easy", scene_id="0", ret=0.5)]
    grp = [dict(zip(tags.EPISODE_COLUMNS, r)) for r in rows]
    out = nd_ln_parity_row(grp, min_train_denominator=1.0)
    assert out["retention_nd_ln_parity"] is None, (
        "a train-scene-0 mean of 0.05 is below the 1.0 floor and must not produce a ratio")
    assert out["train_scene0_mean"] == pytest.approx(0.05), (
        "the raw mean must still be reported -- only the RATIO is refused, not the measurement")


def test_missing_mode_or_scene_reports_none_rather_than_crashing_or_fabricating():
    """A group with only `train` rows (e.g. mid-training, before the first eval point) must not
    error, and must not report a fabricated eval number."""
    rows = [_row(mode="train", scene_id="0", ret=10.0)]
    grp = [dict(zip(tags.EPISODE_COLUMNS, r)) for r in rows]
    out = nd_ln_parity_row(grp, min_train_denominator=1.0)
    assert out["eval_scene0_mean"] is None
    assert out["eval_full_mean"] is None
    assert out["retention_nd_ln_parity"] is None
    assert out["retention_full_protocol"] is None
    assert out["train_scene0_mean"] == pytest.approx(10.0)


def test_group_by_run_separates_checkpoints_not_only_runs():
    """Two evaluations of the SAME (task, baseline, seed) at different training frame counts must
    be two separate groups -- pooling them would average across training progress, which is not a
    quantity anyone wants."""
    rows = [_row(mode="train", scene_id="0", ret=1.0, frames="50000"),
           _row(mode="train", scene_id="0", ret=2.0, frames="100000")]
    csv_rows = [dict(zip(tags.EPISODE_COLUMNS, r)) for r in rows]
    grouped = group_by_run(csv_rows)
    assert len(grouped) == 2, f"expected two distinct (task,baseline,seed,frames) groups, got {list(grouped)}"


def test_load_episodes_walks_the_real_directory_layout():
    """End-to-end through the actual file-reading path, not just the arithmetic helpers -- a run
    directory nested under the root, exactly as `rlgen.logging_.run_dir` lays it out."""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = os.path.join(tmp, "Door", "alda", "eval-easy-seed0")
        rows = [_row(mode="train", scene_id="0", ret=5.0),
               _row(mode="eval-easy", scene_id="0", ret=4.0)]
        write_episodes_csv(os.path.join(run_dir, "episodes.csv"), rows)

        loaded = load_episodes(tmp)
        assert len(loaded) == 2
        assert {r["mode"] for r in loaded} == {"train", "eval-easy"}


def test_main_refuses_to_report_success_on_an_empty_root(capsys):
    """A tool that finds nothing must say so loudly and exit non-zero -- the same rule
    `tools/verify_run_provenance.py` already follows, for the same reason."""
    from tools.nd_ln_parity import main
    with tempfile.TemporaryDirectory() as tmp:
        old_argv = sys.argv
        sys.argv = ["nd_ln_parity.py", tmp]
        try:
            rc = main()
        finally:
            sys.argv = old_argv
        assert rc != 0
        captured = capsys.readouterr()
        assert "FATAL" in captured.err
