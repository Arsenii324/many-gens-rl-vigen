"""The training loop.

WHY THIS FILE EXISTS. The unbiased operator sweep (`mutants/sweep.py`) found `rlgen/trainer.py`
almost entirely unconstrained: mutations to the seed-frame boundary, the update cadence, the
save cadence, the replay `add` arguments, the eval-scheduling arithmetic and the weights-source
fallback all SURVIVED the suite. The curated catalogue had not noticed, because I wrote the
catalogue and I had not thought about the trainer.

That is the whole argument for running a sweep you did not design: a curated 14/14 measures your
imagination, and the sweep measures the code.

Everything here runs on the `synthetic` backend, so it is fast and needs no simulator. Real-env
behaviour is covered separately in `test_real_env.py`.
"""
from __future__ import annotations

import csv
import json
import os
import tempfile

import pytest

from rlgen import tags
from rlgen.protocol import Protocol
from rlgen.trainer import TrainConfig, train


def tiny(**kw):
    d = dict(task="Door", total_frames=120, eval_every_frames=60, episodes_per_scene=1,
             eval_scene_ids=(0, 1), horizon=10, seed=0)
    d.update(kw)
    return Protocol(**d)


def cfg(**kw):
    d = dict(batch_size=4, replay_capacity=200, num_seed_frames=20, update_every_frames=2,
             nstep=1, save_every_frames=60, device="cpu", backend="synthetic")
    d.update(kw)
    return TrainConfig(**d)


def run(tmp, protocol=None, config=None, baseline="drqv2"):
    return train(protocol or tiny(), baseline, config or cfg(), {"seed": 0},
                 os.path.join(tmp, "run"), verbose=False)


def episodes(d):
    with open(os.path.join(d, "episodes.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def scalars(d):
    out = []
    with open(os.path.join(d, "scalars.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


@pytest.fixture(scope="module")
def trained():
    with tempfile.TemporaryDirectory() as tmp:
        yield run(tmp)


def test_evaluations_land_on_the_scheduled_frames_and_only_there(trained):
    """Eval points must be at 0 and every `eval_every_frames`, with no duplicates.

    The first implementation evaluated at frame 1 rather than 0, and evaluated the final
    checkpoint twice -- which silently doubled the episode count of the last point and made its
    interval narrower than the protocol says it is.
    """
    frames = sorted({int(r["frames"]) for r in episodes(trained)})
    assert frames == [0, 60, 120], frames
    per_point = {}
    for r in episodes(trained):
        per_point.setdefault((int(r["frames"]), r["mode"]), 0)
        per_point[(int(r["frames"]), r["mode"])] += 1
    for (f, mode), n in per_point.items():
        expected = 1 if mode == "train" else 2      # 1 train scene, 2 eval scenes, 1 ep each
        assert n == expected, f"{mode}@{f}: {n} episodes, expected {expected}"


def test_both_curves_are_produced_at_every_eval_point(trained):
    modes = {(int(r["frames"]), r["mode"]) for r in episodes(trained)}
    for f in (0, 60, 120):
        assert (f, "train") in modes and (f, "eval-easy") in modes


def test_training_actually_updates_the_agent(trained):
    """`n_updates` must grow. A trainer that never calls update still produces curves."""
    ups = [(s["frames"], s.get(tags.TRAIN_UPDATES)) for s in scalars(trained)
           if tags.TRAIN_UPDATES in s]
    assert ups, "no update count was ever logged"
    assert ups[0][1] == 0
    assert ups[-1][1] > 0, "the agent was never updated"
    assert ups[-1][1] >= (120 - 20) / 2 * 0.5, f"suspiciously few updates: {ups[-1][1]}"


def test_no_updates_before_the_seed_frames_are_collected(trained):
    first = next(s for s in scalars(trained) if tags.TRAIN_UPDATES in s)
    assert first["frames"] == 0 and first[tags.TRAIN_UPDATES] == 0


def test_checkpoint_is_written_and_carries_its_protocol(trained):
    import torch
    p = os.path.join(trained, "checkpoint.pt")
    assert os.path.exists(p)
    sd = torch.load(p, map_location="cpu", weights_only=False)
    assert set(sd) >= {"agent", "protocol", "frames", "n_updates"}
    assert sd["frames"] == 120
    assert sd["protocol"]["task"] == "Door"
    assert sd["agent"], "checkpoint has an empty agent state dict"


def test_every_row_states_where_its_weights_came_from(trained):
    """No row may be silent about provenance -- the previous repo evaluated untrained nets and
    labelled the output `checkpoint_selection: final`."""
    for r in episodes(trained):
        assert r["weights_source"], "empty weights_source"
        assert r["weights_source"].startswith(("in_memory@", "checkpoint:", "random_init"))
        assert r["code_commit"], "empty code_commit"
    # The value must track the frame count, not be a constant.
    assert len({r["weights_source"] for r in episodes(trained)}) == 3


def test_the_protocol_card_is_written_before_any_number(trained):
    for f in ("protocol_card.md", "protocol.json"):
        assert os.path.exists(os.path.join(trained, f))
    card = open(os.path.join(trained, "protocol_card.md"), encoding="utf-8").read()
    hashes = {r["protocol_hash"] for r in episodes(trained)}
    assert len(hashes) == 1 and hashes.pop() in card


def test_the_gap_is_derived_centrally_at_every_point(trained):
    from rlgen import tags
    got = {s["frames"] for s in scalars(trained) if tags.GAP_ABSOLUTE in s}
    assert got == {0, 60, 120}
    for s in scalars(trained):
        if tags.GAP_ABSOLUTE in s and tags.EVAL_RETURN_MEAN in s:
            pass  # the two are written by separate calls; consistency is checked below
    per_frame = {}
    for s in scalars(trained):
        per_frame.setdefault(s["frames"], {}).update(s)
    for f, d in per_frame.items():
        assert d[tags.GAP_ABSOLUTE] == pytest.approx(
            d[tags.TRAIN_EVAL_RETURN_MEAN] - d[tags.EVAL_RETURN_MEAN], rel=1e-9)


def test_the_budget_is_honoured_exactly():
    with tempfile.TemporaryDirectory() as tmp:
        d = run(tmp, protocol=tiny(total_frames=90, eval_every_frames=45))
        assert max(int(r["frames"]) for r in episodes(d)) == 90


def test_seed_frames_gate_the_first_update():
    """Raising num_seed_frames above the budget must yield zero updates, not a crash."""
    with tempfile.TemporaryDirectory() as tmp:
        d = run(tmp, config=cfg(num_seed_frames=1000))
        ups = [s[tags.TRAIN_UPDATES] for s in scalars(d) if tags.TRAIN_UPDATES in s]
        assert max(ups) == 0


def test_a_non_trainable_baseline_is_refused_rather_than_silently_run():
    """`ctrl` is a declared alias, so it has no training rule of its own.

    This test used to name `ppg`, which was `absent`. PPG is now implemented, and the test failing
    for that reason is the registry doing its job -- a status is machine-readable precisely so the
    suite notices when one changes.
    """
    from rlgen import registry
    from rlgen.registry import BaselineSpec
    # Every baseline in the brief is now implemented, so there is no natural non-trainable one to
    # point at. The refusal is still the guard that keeps a stub out of a results table, so it is
    # tested against a temporarily registered spec rather than deleted for lack of a subject.
    assert all(registry.get(n).trainable or registry.get(n).status == "alias"
               for n in registry.BRIEF_BASELINES)
    registry.BASELINES["__probe__"] = BaselineSpec(
        name="__probe__", method="probe", backbone="none", status="absent", paper="-",
        notes="temporary, registered by a test")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(SystemExit) as e:
                train(tiny(), "__probe__", cfg(), {}, os.path.join(tmp, "x"), verbose=False)
            assert "status" in str(e.value)
    finally:
        registry.BASELINES.pop("__probe__", None)


def test_the_negative_control_trains_nothing_but_still_reports_a_floor():
    """`random` has total_frames=0: no loop iterations, and still a full measured floor."""
    with tempfile.TemporaryDirectory() as tmp:
        d = train(tiny(total_frames=0), "random", cfg(), {"seed": 0},
                  os.path.join(tmp, "run"), verbose=False)
        rows = episodes(d)
        assert rows, "the negative control produced no episodes"
        assert {int(r["frames"]) for r in rows} == {0}
        ups = [s[tags.TRAIN_UPDATES] for s in scalars(d) if tags.TRAIN_UPDATES in s]
        assert max(ups) == 0
