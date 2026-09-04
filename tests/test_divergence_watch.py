#!/usr/bin/env python3
"""`scripts/watch_divergence.py` must call a NaN run dead, and must never call a blind one healthy.

[C57](../docs/CONSTRUCTION.md#c57) found a run that diverged to NaN, trained 70 000 more frames,
and wrote a snapshot of 7.4M NaNs. Its conclusion was that divergence was invisible in every
artifact this project kept — true of the artifacts it had, whose `train.csv` header is
`buffer_size,episode,episode_length,episode_reward,fps,frame,step,total_time` and carries no loss
column at all.

`use_tb=True`, turned on afterwards, added `actor_loss`/`critic_loss`/`critic_q1` to that file, and
they go literally `nan` on the first bad update. On 2026-08-26 a `drqv2` run was NaN at frame
**7 000, 5.9 minutes in**, and ran 64 more minutes because nothing read the column. This is what
reads it.

The dangerous direction is the second test: a run whose log *cannot* show divergence must report
BLIND, never OK. Returning OK there converts an absence of evidence into a clean bill of health.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("wd", ROOT / "scripts" / "watch_divergence.py")
wd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wd)

RICH = "actor_ent,actor_loss,critic_loss,critic_q1,episode_reward,frame"
POOR = "buffer_size,episode,episode_length,episode_reward,fps,frame,step,total_time"


def run_dir(tmp_path: pathlib.Path, header: str, rows: list[str]) -> pathlib.Path:
    d = tmp_path / "170000_seed=7,num_train_frames=105000"
    d.mkdir(parents=True, exist_ok=True)
    (d / "train.csv").write_text("\n".join([header, *rows]) + "\n")
    return d


def test_a_nan_loss_is_reported_dead(tmp_path):
    d = run_dir(tmp_path, RICH, ["6.4,nan,nan,nan,0.68,7000"])
    code, why = wd.inspect(d)
    assert code == wd.DEAD, f"a nan loss was not called dead: {why}"
    assert "7000" in why, "the report does not say which frame it died at"


def test_a_healthy_log_is_ok(tmp_path):
    d = run_dir(tmp_path, RICH, [f"6.4,-0.1,0.01,0.13,{3.0 + i},{1000 * i}" for i in range(1, 8)])
    code, why = wd.inspect(d)
    assert code == wd.OK, why


def test_a_log_without_loss_columns_is_BLIND_not_ok(tmp_path):
    """The one that matters. `drq` is always this, by C57's own tb regression.

    A run whose log cannot show divergence must not be reported healthy — that turns "we could not
    look" into "we looked and it was fine", which is the failure this repository's null is about.
    """
    d = run_dir(tmp_path, POOR, ["49500,99,500,0.68,11.5,49500,49500,3826"])
    code, why = wd.inspect(d)
    assert code == wd.BLIND, f"an unwatchable log reported {code}: {why}"
    assert "check_checkpoint_finite" in why, "BLIND does not point at the fallback instrument"


def test_the_c57_tell_is_reported_but_is_not_fatal(tmp_path):
    """Constant return with finite losses is a collapsed policy, not a NaN one. Say so, don't fail.

    C57's indirect tell — standard deviation 0.00 across episodes — also fires for a policy that
    merely stopped exploring. Treating it as fatal would kill runs that are only unpromising, a
    judgement this instrument has no standing to make.
    """
    d = run_dir(tmp_path, RICH, [f"6.4,-0.1,0.01,0.13,0.68,{500 * i}" for i in range(1, 21)])
    code, why = wd.inspect(d)
    assert code == wd.OK, "a collapsed-but-finite policy must not be reported as diverged"
    assert "C57's indirect tell" in why, "the C57 tell fired and was not mentioned"


def test_a_missing_or_empty_log_is_not_an_error(tmp_path):
    """A run that has not written a row yet is not evidence of anything."""
    d = tmp_path / "empty"
    d.mkdir()
    assert wd.inspect(d)[0] == wd.OK


def test_a_half_written_row_does_not_crash_the_watcher(tmp_path):
    """train.csv is appended to live; a poll can land mid-write."""
    d = run_dir(tmp_path, RICH, ["6.4,-0.1,0.01,0.13,3.0,1000", "6.4,-0.1,"])
    assert wd.inspect(d)[0] in (wd.OK, wd.DEAD)


def test_the_preserver_refuses_a_snapshot_from_a_diverged_run(tmp_path, monkeypatch):
    """Composition: preserving a NaN checkpoint files 100 MB of NaNs under a measurement's name.

    This happened — the 2026-08-26 drqv2 seed-7 run's 50k snapshot was preserved while every one
    of its parameters was NaN. The preserver delegates the judgement rather than reimplementing
    it, so the two instruments cannot drift apart.
    """
    spec = importlib.util.spec_from_file_location(
        "pres", ROOT / "scripts" / "preserve_intermediate_snapshot.py")
    pres = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pres)

    d = run_dir(tmp_path, RICH, ["6.4,nan,nan,nan,0.68,7000"])
    assert pres.WD.inspect(d)[0] == pres.WD.DEAD, (
        "the preserver's view of divergence disagrees with the watcher's — they have drifted")
