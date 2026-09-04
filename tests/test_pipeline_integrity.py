"""End-to-end integrity of the evaluation pipeline: raw episodes -> logged scalar -> plotted point.

WHY THIS IS THE DEEPEST CHECK IN THE SUITE. Everything else verifies a stage. This verifies the
JOINS between stages, which is where a benchmark silently diverges: `episodes.csv` is the raw
artifact every post-hoc question is answered from, `scalars.jsonl` / tensorboard is what the
plotter draws, and the protocol card is what a reader believes. If the number in the second is
not the aggregate of the first under the statistic named in the third, then the published curve
and the released data disagree — and the released data is the one people will re-analyse.

Nothing here trusts a value computed by the code under test: each assertion recomputes the
statistic from the raw rows and compares.
"""
from __future__ import annotations

import csv
import json
import os
import statistics as st
import tempfile

import pytest

from rlgen import tags
from rlgen.protocol import Protocol
from rlgen.trainer import TrainConfig, train


def _run(tmp, **over):
    p = Protocol(task="Door", total_frames=120, eval_every_frames=60, episodes_per_scene=3,
                 eval_scene_ids=(0, 1, 2), horizon=10, **over)
    c = TrainConfig(batch_size=8, replay_capacity=300, num_seed_frames=8, update_every_frames=2,
                    nstep=1, save_every_frames=100000, device="cpu", backend="synthetic")
    return p, train(p, "drqv2", c, {"seed": 0}, os.path.join(tmp, "r"), verbose=False)


def _episodes(d):
    with open(os.path.join(d, "episodes.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _scalars(d):
    per = {}
    with open(os.path.join(d, "scalars.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                per.setdefault(int(r.pop("frames")), {}).update(r)
    return per


@pytest.fixture(scope="module")
def run():
    with tempfile.TemporaryDirectory() as tmp:
        yield _run(tmp)


def test_every_logged_scalar_is_the_aggregate_of_the_raw_rows(run):
    """THE join. `eval/return_mean` must equal the mean of the eval episodes at that frame count,
    under the statistic the protocol declares — recomputed here from episodes.csv."""
    protocol, d = run
    rows, sc = _episodes(d), _scalars(d)
    assert rows and sc
    for frames, vals in sc.items():
        for mode, mean_tag, std_tag in (
                (protocol.eval_mode, tags.EVAL_RETURN_MEAN, tags.EVAL_RETURN_STD),
                (protocol.train_mode, tags.TRAIN_EVAL_RETURN_MEAN, tags.TRAIN_EVAL_RETURN_STD)):
            if mean_tag not in vals:
                continue
            raw = [float(r["return_raw"]) for r in rows
                   if int(r["frames"]) == frames and r["mode"] == mode]
            assert raw, f"{mode}@{frames}: scalar logged but no episodes written"
            assert vals[mean_tag] == pytest.approx(st.mean(raw), rel=1e-9), (
                f"{mean_tag}@{frames} = {vals[mean_tag]} but episodes.csv means "
                f"{st.mean(raw)} over {len(raw)} rows")
            if std_tag in vals and len(raw) > 1:
                assert vals[std_tag] == pytest.approx(st.pstdev(raw), rel=1e-9)


def test_episode_counts_match_what_the_protocol_card_promises(run):
    protocol, d = run
    rows = _episodes(d)
    card = open(os.path.join(d, "protocol_card.md"), encoding="utf-8").read()
    assert f"episodes_per_scene: {protocol.episodes_per_scene}" in card
    for frames in {int(r["frames"]) for r in rows}:
        ev = [r for r in rows if int(r["frames"]) == frames and r["mode"] == protocol.eval_mode]
        assert len(ev) == protocol.n_eval_episodes == \
            len(protocol.eval_scene_ids) * protocol.episodes_per_scene
        per_scene = {}
        for r in ev:
            per_scene[int(r["scene_id"])] = per_scene.get(int(r["scene_id"]), 0) + 1
        assert set(per_scene) == set(protocol.eval_scene_ids)
        assert set(per_scene.values()) == {protocol.episodes_per_scene}, (
            f"uneven episodes per scene at {frames}: {per_scene}")


def test_the_gap_is_the_difference_of_the_two_recomputed_means(run):
    protocol, d = run
    rows, sc = _episodes(d), _scalars(d)
    for frames, vals in sc.items():
        if tags.GAP_ABSOLUTE not in vals:
            continue
        tr = [float(r["return_raw"]) for r in rows
              if int(r["frames"]) == frames and r["mode"] == protocol.train_mode]
        ev = [float(r["return_raw"]) for r in rows
              if int(r["frames"]) == frames and r["mode"] == protocol.eval_mode]
        assert vals[tags.GAP_ABSOLUTE] == pytest.approx(st.mean(tr) - st.mean(ev), rel=1e-9)


def test_the_plotter_draws_exactly_the_logged_values(run):
    """The last join: what `plot.py` puts on the y-axis is what was logged, not a re-derivation.

    HERMETIC, DELIBERATELY. This walked `dirname(dirname(d))`, and since `logger.logdir` is
    `<tmp>/r` -- one level below the fixture's directory, not two -- that expression resolved to
    the machine's entire $TMPDIR. The test therefore discovered every run any other process had
    left in temp, flattened them together in `drawn`, and compared this run's logged values
    against whichever run happened to be enumerated last.

    That made it flaky, and the flakiness landed in the mutation oracle: sweep seed 101 recorded a
    `rlgen/replay.py` mutant as "killed by test_the_plotter_draws_exactly_the_logged_values" -- a
    test that compares one run against itself and cannot legitimately detect a replay change. A
    non-hermetic test in the oracle inflates every kill rate, so this is a measurement bug, not
    only a test bug.

    Two changes: walk the fixture's own directory, and pin the number of runs discovered. `assert
    runs` was true for any count >= 1, which is exactly why contamination was silent.
    """
    import sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, ROOT)
    import plot
    protocol, d = run
    runs = plot.discover(os.path.dirname(d))
    assert len(runs) == 1, (
        f"expected exactly the one run just written, found {len(runs)}: "
        f"{[r['dir'] for r in runs]}")
    series = plot.aggregate(runs, tags.EVAL_RETURN_MEAN)
    assert len(series) == 1, f"one run must aggregate to one series key, got {list(series)}"
    sc = _scalars(d)
    drawn = {f: v for key, s in series.items() for f, v in s.items()}
    for frames, vals in sc.items():
        if tags.EVAL_RETURN_MEAN in vals:
            assert frames in drawn, f"logged point at {frames} never reached the plotter"
            assert drawn[frames][0] == pytest.approx(vals[tags.EVAL_RETURN_MEAN], rel=1e-9)


def test_a_second_run_cannot_silently_append_to_a_finished_one(run):
    """Re-running a baseline lands in the SAME directory, and used to concatenate.

    Run directories are keyed by (task, baseline, mode-seed), so a re-run reuses the path. The
    logger appended, and nothing in `episodes.csv` marked where one run ended and the next began.
    Real damage in this repo's own logs: `Door/drqv2` held two runs at different commits, and
    `Door/soda` held six runs' worth of rows at frames=0 against three at frames=1500 and 3000 --
    so a per-point mean averaged different numbers of runs at different x.
    """
    from rlgen.logging_ import RunLogger
    protocol, d = run
    with pytest.raises(FileExistsError, match="earlier run"):
        RunLogger(d, protocol, baseline="drqv2", tensorboard=False)


def test_appending_within_one_run_still_works(run):
    """The refusal must not break the normal case: one logger, many eval points, one file."""
    protocol, d = run
    rows = _episodes(d)
    frames = sorted({int(r["frames"]) for r in rows})
    assert len(frames) > 1, ("a single run must still write several eval points to one file; "
                             f"got only {frames}")


def test_every_row_carries_the_provenance_needed_to_re_analyse_it(run):
    """The released artifact has to stand alone: a reader must be able to tell, per episode, which
    protocol, which weights and which code produced it."""
    protocol, d = run
    for r in _episodes(run[1]):
        assert r["protocol_hash"] == protocol.hash()
        assert r["weights_source"] and r["code_commit"]
        assert r["policy_mode"] == protocol.policy_mode
        assert r["task"] == protocol.task
        assert int(r["episode_len"]) == protocol.steps_per_episode
        assert r["truncated"] == "True" and r["terminated"] == "False"


def test_columns_are_exactly_the_declared_schema(run):
    with open(os.path.join(run[1], "episodes.csv"), encoding="utf-8") as f:
        header = next(csv.reader(f))
    assert tuple(header) == tags.EPISODE_COLUMNS, (
        "episodes.csv header drifted from rlgen/tags.py:EPISODE_COLUMNS; every post-hoc script "
        "reads by column name")


# ============================================================ the gap the sweep named
@pytest.mark.parametrize("name", ["drqv2", "rad", "alda", "ppg", "idaac"])
def test_a_checkpoint_round_trips_and_reproduces_its_score(name):
    """The repo's OUTPUT is checkpoints, and nothing round-tripped one until now.

    `mutants/sweep.py` named `DrQV2Adapter.load_state_dict` as untested: the repo wrote
    checkpoints, verified their contents, and never loaded one back. A checkpoint that cannot be
    restored is not a result -- every published number would be unreproducible from the artifact
    that is supposed to carry it.

    Restores into a FRESHLY BUILT agent (not the one that saved) and requires the deterministic
    policy to be identical, which is the property a re-evaluation depends on.
    """
    import numpy as np
    import torch
    from rlgen import registry
    from rlgen.agents import policy_for

    p = Protocol(task="Door", total_frames=0)
    spec = registry.get(name)
    saver = spec.build(p, p.obs_shape, 7, "cpu", {"seed": 0})
    obs = np.random.default_rng(3).integers(0, 256, size=p.obs_shape, dtype=np.uint8)
    before = policy_for(saver, True)(obs)

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "c.pt")
        torch.save({"agent": saver.state_dict()}, path)
        # a different seed, so an identical action cannot come from identical initialisation
        loader = spec.build(p, p.obs_shape, 7, "cpu", {"seed": 99})
        assert not np.allclose(before, policy_for(loader, True)(obs)), (
            f"{name}: two independently built agents already agree; this test could not detect a "
            f"no-op load")
        loader.load_state_dict(torch.load(path, map_location="cpu", weights_only=False)["agent"])
        after = policy_for(loader, True)(obs)

    assert np.allclose(before, after, atol=1e-5), (
        f"{name}: a restored checkpoint does not reproduce the saved policy "
        f"({before} vs {after}) -- every number from a reloaded checkpoint would be wrong")


@pytest.mark.parametrize("name", ["drqv2", "rad", "idaac"])
def test_load_state_dict_refuses_a_mismatched_checkpoint_instead_of_loading_it_partially(name):
    """FIXED 2026-08-14. `DrQV2Adapter`/`SacAdapter`/`PPOFamilyAdapter.load_state_dict` used to
    skip any key with no matching live submodule and report nothing -- flagged by the unbiased
    mutation sweep, recorded but not applied until now (docs/VALIDATION.md sec.4.2). A checkpoint
    saved by a differently-shaped agent (a renamed submodule, a version drift across a code
    change) would load PARTIALLY, leaving the unmatched piece at its random init, with no error
    anywhere in the chain.

    One real key is renamed here, rather than an invented one, so this is exactly the failure a
    code change that renames a submodule would trigger.
    """
    from rlgen import registry

    p = Protocol(task="Door", total_frames=0)
    spec = registry.get(name)
    agent = spec.build(p, p.obs_shape, 7, "cpu", {"seed": 0})
    sd = agent.state_dict()
    assert sd, f"{name}: state_dict() is empty -- this test cannot corrupt anything meaningful"

    real_key = next(iter(sd))
    real_value = sd.pop(real_key)  # popped BEFORE the dict literal below, so it is actually
                                   # renamed, not merely duplicated alongside the original key
    corrupted = {**sd, "this_submodule_does_not_exist": real_value}
    with pytest.raises(KeyError, match="this_submodule_does_not_exist"):
        agent.load_state_dict(corrupted)
