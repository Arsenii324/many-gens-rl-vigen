"""Tests written to close gaps that the UNBIASED sweep found, not gaps I predicted.

`mutants/sweep.py -n 40 --seed 1` scored **12/40 (30%)** against the suite as it stood after the
curated catalogue scored 14/14. That gap is the point: a catalogue I wrote, with tests I wrote,
measures my imagination. The sweep picks sites uniformly at random over the AST and found whole
modules unconstrained -- the replay index arithmetic, the bootstrap interval, the registry's
reporting, and the exploration-schedule plumbing in the adapter.

Each test below names the surviving mutant it kills. Nothing here was written before the sweep
ran; that ordering is deliberate and is what makes the second measurement meaningful.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

from rlgen import registry, tags
from rlgen.evaluate import _reduce, bootstrap_ci
from rlgen.protocol import Protocol
from rlgen.replay import FrameReplay
from rlgen.trainer import TrainConfig


# ============================================================== replay index arithmetic
# survivors: replay.py:83 (_stack boundary), :89, :95, :97, :100 (_valid_indices window)
def filled(cap=60, ep_len=9, n_eps=12, fs=3, nstep=2):
    rb = FrameReplay(capacity=cap, frame_shape=(3, 6, 6), act_dim=2, frame_stack=fs,
                     nstep=nstep, discount=0.5, seed=0)
    for ep in range(n_eps):
        rb.start_episode()
        for t in range(ep_len):
            # Encode (episode, step) in the pixels so a spliced or misaligned stack is visible.
            f = np.full((3, 6, 6), (ep * 16 + t) % 251, dtype=np.uint8)
            rb.add(f, np.full(2, 0.1 * ep, np.float32), float(t), done=(t == ep_len - 1))
    return rb


def test_valid_indices_never_returns_a_transition_spanning_the_write_head():
    """Kills replay.py:95/:97/:100. Transitions near the write head have a `next` that newer,
    unrelated data has already overwritten; sampling them trains on spliced trajectories."""
    rb = filled()
    valid = rb._valid_indices()
    assert valid.size > 0, "no sampleable transitions at all -- the window excluded everything"
    for i in valid:
        j = int((i + rb.nstep) % rb.capacity)
        assert rb._episode[i] == rb._episode[j] >= 0, \
            f"index {i} spans an episode boundary at nstep={rb.nstep}"
        # distance from the write head, forward around the ring
        d = (int(rb._idx) - int(i)) % rb.capacity
        assert d > rb.nstep, f"index {i} is within nstep of the write head (distance {d})"


def test_the_next_observation_of_every_sampled_transition_is_intact():
    """The exclusion window's whole purpose, asserted on the `next` side.

    An unbiased sweep (seed 101) narrowed `hi = (self._idx + self.frame_stack + 1)` to
    `... - 1` and the suite stayed green. The existing write-head test only bounds distance
    FORWARD of the head (`(idx - i) % cap > nstep`); nothing constrained the other edge, where a
    transition's `next` observation is built from slots the head has already reused.

    Rather than pin the literal `+ 1`, this asserts the property the window exists to guarantee:
    every frame of both `obs(i)` and `obs(i + nstep)` must still carry the episode and the
    consecutive step numbers it had when written. `filled()` encodes `(ep * 16 + t) % 251` into
    the pixels precisely so that overwritten data is visible rather than merely suspected.
    """
    rb = filled()
    valid = rb._valid_indices()
    assert valid.size > 0, "no sampleable transitions at all"
    for i in valid:
        i = int(i)
        j = int((i + rb.nstep) % rb.capacity)
        for who, k in (("obs", i), ("next_obs", j)):
            st = rb._stack(k)
            vals = [int(st[3 * b].flat[0]) for b in range(rb.frame_stack)]
            eps, steps = [v // 16 for v in vals], [v % 16 for v in vals]
            assert len(set(eps)) == 1, \
                f"{who} at index {k} spans episodes {sorted(set(eps))} -- overwritten data"
            for a, b in zip(steps, steps[1:]):
                assert b - a in (0, 1), \
                    f"{who} at index {k} has non-consecutive steps {steps} -- overwritten data"
        # obs and next_obs must belong to the SAME episode, nstep apart.
        assert rb._episode[i] == rb._episode[j], f"transition {i}->{j} crosses an episode"
        s_i = int(rb._frames[i].flat[0]) % 16
        s_j = int(rb._frames[j].flat[0]) % 16
        assert s_j - s_i == rb.nstep, (
            f"transition {i}->{j} claims to be {rb.nstep} steps apart but the stored frames are "
            f"{s_j - s_i} apart -- the `next` slot was reused by the write head")


def test_stack_walks_back_exactly_frame_stack_frames_within_one_episode():
    """Kills replay.py:83. The stack must be consecutive frames of ONE episode, newest last."""
    rb = filled()
    for i in rb._valid_indices()[:40]:
        st = rb._stack(int(i))
        vals = [int(st[3 * k].flat[0]) for k in range(rb.frame_stack)]
        # newest frame is the last block and equals the frame stored at i
        assert vals[-1] == int(rb._frames[i].flat[0])
        # Pixel value encodes (ep * 16 + t) % 251 with ep_len = 9 < 16, so the episode index and
        # the within-episode step are both recoverable. Every block must come from ONE episode,
        # and the steps must be consecutive and non-decreasing (repeats only at an episode start).
        eps, steps = [v // 16 for v in vals], [v % 16 for v in vals]
        assert len(set(eps)) == 1, f"stack at index {i} spans episodes {sorted(set(eps))}"
        for a, b in zip(steps, steps[1:]):
            assert b - a in (0, 1), f"stack steps {steps} are not consecutive at index {i}"


def test_nstep_return_and_discount_are_what_they_claim():
    """Kills replay.py:89 and pins the arithmetic the trainer's targets depend on."""
    rb = FrameReplay(capacity=200, frame_shape=(3, 4, 4), act_dim=1, frame_stack=1,
                     nstep=3, discount=0.5, seed=0)
    rb.start_episode()
    for t in range(60):
        rb.add(np.full((3, 4, 4), t % 250, np.uint8), np.zeros(1, np.float32), float(t),
               done=False)
    _o, _a, rew, disc, _n = rb.sample(32)
    assert disc.shape == rew.shape == (32, 1)
    # discount after nstep steps of gamma=0.5 is 0.125, always
    assert np.allclose(disc, 0.5 ** 3)
    # r_t + 0.5 r_{t+1} + 0.25 r_{t+2} for consecutive integer rewards t, t+1, t+2
    # = t(1 + .5 + .25) + (.5 + .5) = 1.75 t + 1.0
    for k in range(32):
        r = float(rew[k, 0])
        t = (r - 1.0) / 1.75
        assert abs(t - round(t)) < 1e-4, f"n-step return {r} is not of the expected form"


def test_capacity_is_respected_and_len_saturates():
    rb = filled(cap=40, ep_len=5, n_eps=20)
    assert len(rb) == 40 and rb._full


# ============================================================== bootstrap interval
# survivor: evaluate.py:130 (percentile index arithmetic)
def test_bootstrap_ci_brackets_the_estimate_and_respects_alpha():
    rng = np.random.default_rng(0)
    xs = (rng.normal(10.0, 2.0, size=200)).tolist()
    point = _reduce(xs, "mean")
    lo, hi = bootstrap_ci(xs, key="k", n=2000, alpha=0.05, how="mean")
    assert lo < point < hi, f"CI [{lo}, {hi}] does not bracket the point estimate {point}"
    # A 95% interval on n=200 normal(10, 2) has half-width ~1.96*2/sqrt(200) ~= 0.28
    assert 0.2 < (hi - lo) / 2 < 0.45, f"implausible half-width {(hi - lo) / 2}"
    wide = bootstrap_ci(xs, key="k", n=2000, alpha=0.5, how="mean")
    assert (wide[1] - wide[0]) < (hi - lo), "alpha=0.5 did not give a narrower interval than 0.05"


def test_bootstrap_ci_is_reproducible_and_key_dependent():
    xs = list(range(50))
    assert bootstrap_ci(xs, key="a") == bootstrap_ci(xs, key="a")
    assert bootstrap_ci(xs, key="a") != bootstrap_ci(xs, key="b")


def test_bootstrap_ci_uses_the_same_reduction_as_the_point_estimate():
    """A mean point estimate with a median-bootstrap interval is a different quantity."""
    xs = [0.0] * 40 + [100.0] * 10          # mean 20, median 0
    mlo, mhi = bootstrap_ci(xs, key="k", n=1500, how="mean")
    dlo, dhi = bootstrap_ci(xs, key="k", n=1500, how="median")
    assert mlo > 5.0 and dhi < 5.0, f"mean CI {mlo, mhi} and median CI {dlo, dhi} did not separate"


def test_bootstrap_ci_declines_to_answer_on_one_sample():
    lo, hi = bootstrap_ci([1.0], key="k")
    assert np.isnan(lo) and np.isnan(hi)


# ============================================================== registry reporting
# survivor: registry.py:247 (status_table construction)
def test_status_table_lists_every_brief_baseline_with_its_status():
    t = registry.status_table()
    lines = t.splitlines()
    assert lines[0].split()[:2] == ["baseline", "status"]
    for n in ("random",) + registry.BRIEF_BASELINES:
        row = [ln for ln in lines if ln.split() and ln.split()[0] == n]
        assert len(row) == 1, f"{n} appears {len(row)} times in the status table"
        assert registry.get(n).status in row[0]
    assert "MISSING" not in t


def test_runnable_is_exactly_the_implemented_and_alias_entries():
    assert set(registry.runnable()) == {
        n for n, s in registry.BASELINES.items() if s.status in ("implemented", "alias")}
    for n in registry.runnable():
        assert registry.get(n).build is not None, f"{n} is runnable but has no builder"


# ============================================================== adapter exploration schedule
# survivors: agents.py:69 (self._step), :128 (helper obs)
def test_eval_action_is_independent_of_the_training_step():
    """`step` drives the exploration-noise schedule, which must not touch a deterministic eval.

    If it did, the same checkpoint would score differently depending on when it was evaluated.
    """
    p = Protocol(task="Door", total_frames=0)
    obs = np.random.default_rng(0).integers(0, 256, size=p.obs_shape, dtype=np.uint8)
    for name in ("drqv2", "svea"):
        agent = registry.get(name).build(p, p.obs_shape, 7, "cpu", {"seed": 0})
        agent.set_step(0)
        a0 = agent.act(obs, deterministic=True)
        agent.set_step(499_999)
        a1 = agent.act(obs, deterministic=True)
        assert np.allclose(a0, a1), f"{name}: deterministic action moved with the training step"


def test_stochastic_action_does_depend_on_the_schedule():
    """The converse: if `step` changed nothing at all, the schedule would be dead code."""
    p = Protocol(task="Door", total_frames=0)
    obs = np.random.default_rng(1).integers(0, 256, size=p.obs_shape, dtype=np.uint8)
    agent = registry.get("drqv2").build(p, p.obs_shape, 7, "cpu", {"seed": 0})
    early = np.stack([(agent.set_step(0), agent.act(obs, deterministic=False))[1]
                      for _ in range(24)])
    late = np.stack([(agent.set_step(400_000), agent.act(obs, deterministic=False))[1]
                     for _ in range(24)])
    assert early.std(axis=0).mean() > late.std(axis=0).mean() * 1.5, (
        f"exploration noise did not shrink along the schedule: "
        f"early sd {early.std(axis=0).mean():.4f}, late sd {late.std(axis=0).mean():.4f}")


# ============================================================== shipped trainer defaults
# survivors: trainer.py:35, :41 (dataclass defaults every test overrides)
def test_shipped_trainer_defaults_are_the_documented_ones():
    """Tests override these, so a change to the SHIPPED value is invisible to every other test --
    and the shipped value is what a real run uses."""
    c = TrainConfig()
    assert (c.batch_size, c.nstep, c.discount) == (256, 3, 0.99)
    assert (c.replay_capacity, c.num_seed_frames, c.update_every_frames) == (100_000, 4_000, 2)
    assert c.save_every_frames == 50_000 and c.backend == "robosuite"


def test_device_resolution_prefers_accelerators_but_reports_what_it_got():
    assert TrainConfig(device="cpu").resolve_device() == "cpu"
    assert TrainConfig(device="auto").resolve_device() in ("cuda", "mps", "cpu")


# ============================================================== found by running a 2nd baseline
def test_a_baseline_missing_its_dataset_is_refused_before_anything_is_written():
    """SVEA's overlay augmentation needs Places365 and only asks at the FIRST GRADIENT STEP.

    Found by smoke-running a second baseline: the frame-0 evaluation had already written a
    protocol card, an episodes.csv and a tensorboard file before the run died. A directory that
    looks like a run must not be left by a run that could never finish.
    """
    import os
    import tempfile
    from rlgen.trainer import train

    # The skip condition must NOT come from the code under test. An earlier version skipped when
    # `check_data_requirements` returned nothing -- so inverting the `not present()` check inside
    # that very function made this test SKIP instead of FAIL, and pytest exited 0. The mutation
    # survived. A skip guard derived from the system under test is a vacuous check; this one is
    # derived from the filesystem instead.
    import json
    cfg = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(registry.__file__))),
                       "RL-ViGen-upstream", "cfgs", "aug_config.cfg")
    dataset_on_disk = False
    if os.path.exists(cfg):
        for d in json.load(open(cfg, encoding="utf-8")).get("datasets", []):
            # train OR val -- val is the declared ~2 GB alternative
            if any(os.path.isdir(os.path.join(d, "places365_standard", p_))
                   for p_ in ("train", "val")):
                dataset_on_disk = True
    if dataset_on_disk:
        pytest.skip("places365 really is installed here, so the preflight cannot fire")

    # The registry must AGREE with that independent observation.
    problems = registry.check_data_requirements("svea")
    assert problems, ("places365 is not on disk, but check_data_requirements reports no problem "
                      "-- the presence check is inverted or short-circuiting")
    assert registry.check_data_requirements("drqv2") == [], "false positive on a baseline with no data needs"

    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "run")
        p = Protocol(task="Lift", total_frames=10, eval_every_frames=10, episodes_per_scene=1,
                     eval_scene_ids=(0,), horizon=4)
        with pytest.raises(SystemExit) as e:
            train(p, "svea", TrainConfig(device="cpu", backend="robosuite"), {}, d, verbose=False)
        assert "places365" in str(e.value) and "update()" in str(e.value)
        assert not os.path.exists(d), "the refused run left artifacts behind"


def test_every_declared_dataset_has_a_working_presence_check():
    for name, (desc, present) in registry.DATASETS.items():
        assert isinstance(desc, str) and len(desc) > 40, f"{name}: description too thin"
        assert isinstance(present(), bool), f"{name}: presence check did not return a bool"


# ------------------------------------------------------------------------------------------
# The two tests below exist because the mutation score turned out to depend on AMBIENT MACHINE
# STATE, which makes it not a measurement.
#
# `test_svea_refuses_to_start_without_places365` above skips when the dataset is genuinely on
# disk -- correctly, since the preflight cannot fire when there is nothing missing. But that left
# M17 (invert the presence check) and M15 (disable the preflight) with NOTHING able to observe
# them on a machine where Places365 is installed. The curated catalogue read 19/19 before the
# dataset was fetched and 17/19 after, with no code change in between.
#
# So each of these covers the environment the other cannot:
#   dataset PRESENT -> the no-false-positive test below fires, and kills M17
#   dataset ABSENT  -> the refusal test above fires, and kills M17
#   either way      -> the trainer test below fires, and kills M15
# ------------------------------------------------------------------------------------------
def test_a_baseline_whose_data_IS_present_is_cleared_to_train():
    """The presence check must not produce FALSE POSITIVES either.

    Inverting `if not present():` makes a baseline whose data is installed report a missing
    dataset and refuse to train. On a machine with Places365 that is the only observable
    consequence of the inversion, and nothing was looking for it.

    The skip guard is derived from the filesystem, never from `check_data_requirements` -- a skip
    condition read off the system under test is how the defect disables the test that catches it.
    """
    import json
    cfg = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(registry.__file__))),
                       "RL-ViGen-upstream", "cfgs", "aug_config.cfg")
    on_disk = False
    if os.path.exists(cfg):
        for d in json.load(open(cfg, encoding="utf-8")).get("datasets", []):
            if any(os.path.isdir(os.path.join(d, "places365_standard", p_))
                   for p_ in ("train", "val")):
                on_disk = True
    if not on_disk:
        pytest.skip("places365 is not installed here; the absence case is covered above")

    for name in registry.runnable():
        needs = registry.get(name).data_requirements
        if "places365" in needs:
            assert registry.check_data_requirements(name) == [], (
                f"{name} needs places365, places365 IS on disk, and the registry still reports a "
                f"problem -- the presence check is inverted")


def test_the_trainer_refuses_when_the_registry_reports_missing_data(monkeypatch):
    """The trainer's preflight must act on whatever the registry reports, and leave nothing behind.

    Environment-independent ON PURPOSE. It replaces `check_data_requirements` wholesale rather
    than depending on a dataset being absent, so it exercises the trainer's *response* on any
    machine. Disabling the preflight (`if problems:` -> `if False:`) then shows up as a run that
    starts, writes a protocol card and an episodes.csv, and leaves a directory indistinguishable
    from a real run's.

    It patches a DIFFERENT function than the presence check, so it cannot mask an inverted check.
    """
    import tempfile
    from rlgen.trainer import TrainConfig, train

    # `rlgen.trainer` does `from . import registry` INSIDE the function, so there is no
    # module-level attribute to patch -- the name is resolved on the registry module itself at
    # call time. Patch it there.
    monkeypatch.setattr(registry, "check_data_requirements",
                        lambda name: ["places365 is not installed (simulated)"])
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "run")
        p = Protocol(task="Lift", total_frames=10, eval_every_frames=10, episodes_per_scene=1,
                     eval_scene_ids=(0,), horizon=4)
        with pytest.raises(SystemExit) as e:
            train(p, "drqv2", TrainConfig(device="cpu", backend="synthetic"), {}, d, verbose=False)
        assert "places365" in str(e.value)
        assert not os.path.exists(d), "a refused run left a directory that looks like a real one"


# ============================================================== found by adversarial re-reading
def test_stack_guard_holds_at_the_wrap_boundary():
    """`self._idx - 1 % cap` parses as `self._idx - 1`, which is -1 when _idx == 0.

    -1 equals no index, so the guard switched itself off at exactly the moment the ring wraps.
    Driven to _idx == 0 precisely, then every stack is checked for episode purity.
    """
    fs, cap = 3, 24
    rb = FrameReplay(capacity=cap, frame_shape=(3, 4, 4), act_dim=1, frame_stack=fs, nstep=1)
    ep_len = 6
    for ep in range(cap // ep_len):                      # exactly fills the ring: _idx wraps to 0
        rb.start_episode()
        for t in range(ep_len):
            rb.add(np.full((3, 4, 4), ep * 16 + t, np.uint8), np.zeros(1, np.float32), 0.0,
                   done=(t == ep_len - 1))
    assert rb._idx == 0 and rb._full, f"test did not reach the wrap boundary (_idx={rb._idx})"
    for i in range(cap):
        st = rb._stack(i)
        eps = {int(st[3 * k].flat[0]) // 16 for k in range(fs)}
        assert len(eps) == 1, f"stack at index {i} spans episodes {sorted(eps)} at the wrap"


def test_done_flags_coincide_with_episode_boundaries():
    """`_done` is stored and not read by sampling; the episode id subsumes it because Door and
    Lift never terminate early. Rather than carry unchecked state, assert the redundancy."""
    rb = FrameReplay(capacity=100, frame_shape=(3, 4, 4), act_dim=1, frame_stack=2, nstep=1)
    ep_len = 7
    for ep in range(6):
        rb.start_episode()
        for t in range(ep_len):
            rb.add(np.zeros((3, 4, 4), np.uint8), np.zeros(1, np.float32), 0.0,
                   done=(t == ep_len - 1))
    n = len(rb)
    for i in range(n - 1):
        boundary = rb._episode[i] != rb._episode[i + 1]
        assert bool(rb._done[i]) == boundary, (
            f"index {i}: done={rb._done[i]} but episode boundary={boundary} -- the two have "
            f"diverged, so `_done` is no longer redundant and must be used in sampling")


def test_replay_rejects_a_bad_frame_shape_at_construction():
    """The constructor's `len(shape) != 3 or shape[0] != 3` guard was untested."""
    for bad in [(9, 8, 8), (3, 8), (3, 8, 8, 8), (1, 8, 8)]:
        with pytest.raises(ValueError, match="must be"):
            FrameReplay(capacity=10, frame_shape=bad, act_dim=1, frame_stack=1)
    FrameReplay(capacity=10, frame_shape=(3, 8, 8), act_dim=1, frame_stack=1)   # valid


def test_bootstrap_percentile_indices_are_the_right_ones():
    """Pins the index arithmetic itself, not just that the interval looks plausible."""
    xs = list(range(1000))
    lo95, hi95 = bootstrap_ci(xs, key="k", n=4000, alpha=0.05, how="mean")
    lo80, hi80 = bootstrap_ci(xs, key="k", n=4000, alpha=0.20, how="mean")
    assert lo95 < lo80 < hi80 < hi95, (
        f"alpha=0.05 must bracket alpha=0.20: got 95%=[{lo95:.2f},{hi95:.2f}] "
        f"80%=[{lo80:.2f},{hi80:.2f}]")
    # mean of 0..999 is 499.5; the bootstrap SE is sd/sqrt(n) = 288.7/31.6 = 9.13
    assert abs((lo95 + hi95) / 2 - 499.5) < 3.0
    assert 1.8 < (hi95 - lo95) / (2 * 9.13) < 2.2, "95% half-width is not ~1.96 SE"


def test_train_scene_ids_default_is_scene_zero():
    """It defines what 'generalisation' means for every number in the table, and no test pinned it."""
    p = Protocol(task="Door")
    assert p.train_scene_ids == (0,)
    assert set(p.eval_scene_ids) == set(range(10))
    assert p.eval_includes_train_scenes is True, (
        "training scene 0 is inside eval_scene_ids, so this flag must say so")


def test_std_is_reported_for_exactly_two_episodes():
    """`len(rets) > 1` guards the std. At exactly 2 episodes an off-by-one reports 0.0 --
    a confidence interval of zero width on the smallest sample that has one."""
    from rlgen.evaluate import EpisodeRecord, summarize
    p = Protocol(task="Door", total_frames=0, episodes_per_scene=2, eval_scene_ids=(0,))

    def rec(v):
        return EpisodeRecord(baseline="x", backbone="y", task="Door", mode="eval-easy",
                             scene_id=0, seed=0, frames=0, checkpoint="", episode_idx=0,
                             return_raw=v, episode_len=1, terminated=False, truncated=True,
                             success=None, policy_mode="deterministic",
                             protocol_hash=p.hash(), weights_source="w", code_commit="c")

    # BOTH branches. `summarize` has two identical std guards -- one for the eval curve and one
    # for the train curve -- and a mutation that hit only the train one survived because this test
    # originally checked eval alone. Two copies of a guard need two checks.
    out = summarize([rec(1.0), rec(3.0)], p, "eval-easy")
    assert out[tags.EVAL_RETURN_MEAN] == pytest.approx(2.0)
    assert out[tags.EVAL_RETURN_STD] == pytest.approx(1.0), (
        "std of [1, 3] must be 1.0; a zero here means the two-episode case fell through the guard")
    assert summarize([rec(5.0)], p, "eval-easy")[tags.EVAL_RETURN_STD] == 0.0

    tr = summarize([rec(1.0), rec(3.0)], p, p.train_mode)
    assert tr[tags.TRAIN_EVAL_RETURN_MEAN] == pytest.approx(2.0)
    assert tr[tags.TRAIN_EVAL_RETURN_STD] == pytest.approx(1.0), (
        "the train curve's std guard is off by one; it is a separate copy of the same line")
    assert summarize([rec(5.0)], p, p.train_mode)[tags.TRAIN_EVAL_RETURN_STD] == 0.0


def test_bootstrap_interval_width_matches_the_nominal_coverage():
    """Pins the percentile INDEX arithmetic tightly enough that perturbing it fails.

    A coverage-only check cannot tell a correct interval from a too-WIDE one -- both cover the
    truth often enough, so a mutation of the index expression slipped through. The WIDTH is
    compared against its analytic value instead: for a normal sample the half-width of a
    (1-alpha) percentile interval is z(1-alpha/2) * sd/sqrt(n). Perturbing `alpha / 2` to
    `alpha / 3` turns the nominal 50% interval into a 66.7% one -- a 44% width error, which this
    band rejects and a coverage count does not.
    """
    from scipy.stats import norm
    rng = np.random.default_rng(7)
    n_obs = 400
    for alpha, tol in ((0.05, 0.12), (0.50, 0.12)):
        ratios = []
        for k in range(25):
            xs = rng.normal(0.0, 1.0, size=n_obs)
            lo, hi = bootstrap_ci(xs.tolist(), key=f"a{alpha}k{k}", n=1500, alpha=alpha)
            se = xs.std(ddof=1) / np.sqrt(n_obs)
            ratios.append((hi - lo) / 2 / se)
        got, want = float(np.mean(ratios)), float(norm.ppf(1 - alpha / 2))
        assert abs(got - want) / want < tol, (
            f"alpha={alpha}: interval half-width is {got:.3f} SE, expected z={want:.3f} SE. "
            f"The percentile index arithmetic does not match the nominal coverage.")


# ============================================================== seed-41 survivors, triaged real
def test_shipped_protocol_defaults_are_the_documented_ones():
    """Every test overrides these, so a change to the SHIPPED value is invisible to all of them --
    and the shipped value is the one a real run uses and a protocol card publishes."""
    p = Protocol(task="Door")
    assert (p.episodes_per_scene, p.eval_every_frames, p.total_frames) == (10, 50_000, 500_000)
    assert p.n_eval_episodes == 100
    assert (p.image_size, p.frame_stack, p.action_repeat, p.horizon) == (84, 3, 1, 500)
    assert (p.aggregation, p.policy_mode, p.metric) == (
        "mean", "deterministic", "episode_return_raw_undiscounted")
    assert p.schema_version == 1, "a schema bump must be deliberate; it changes every hash"


def test_protocol_round_trips_through_dict():
    """`from_dict` restores tuples from the JSON lists `write_json` produces. Untested until the
    sweep mutated its `and` to an `or`."""
    a = Protocol(task="Lift", seed=3, eval_scene_ids=(0, 2, 4), train_scene_ids=(1,))
    b = Protocol.from_dict(a.to_dict())
    assert b == a and b.hash() == a.hash()
    assert isinstance(b.eval_scene_ids, tuple) and b.eval_scene_ids == (0, 2, 4)
    assert isinstance(b.train_scene_ids, tuple) and b.train_scene_ids == (1,)

    # A PARTIAL dict is the case that separates `and` from `or` in the tuple-restoring guard:
    # with `or`, a key that is absent short-circuits into `kw[k]` and raises KeyError. A complete
    # dict never reaches that branch, which is why the round-trip above cannot see the difference.
    c = Protocol.from_dict({"task": "Door", "seed": 5})
    assert c.task == "Door" and c.seed == 5
    assert c.eval_scene_ids == Protocol().eval_scene_ids, "defaults were not preserved"
    assert Protocol.from_dict({}).task == Protocol().task


def test_a_fresh_replay_is_not_full():
    rb = FrameReplay(capacity=8, frame_shape=(3, 4, 4), act_dim=1, frame_stack=1)
    assert len(rb) == 0 and rb._full is False
    for i in range(8):
        rb.add(np.zeros((3, 4, 4), np.uint8), np.zeros(1, np.float32), 0.0, False)
        assert len(rb) == i + 1
    assert rb._full is True and len(rb) == 8


def test_update_count_increments_by_one_per_update():
    """`n_updates` is published as `train/n_updates`; an increment of 2 doubles a reported number
    while every curve still looks fine."""
    import os
    import tempfile
    from rlgen.trainer import TrainConfig as TC
    from rlgen.trainer import train
    with tempfile.TemporaryDirectory() as tmp:
        p = Protocol(task="Door", total_frames=40, eval_every_frames=40, episodes_per_scene=1,
                     eval_scene_ids=(0,), horizon=5)
        c = TC(batch_size=4, replay_capacity=100, num_seed_frames=10, update_every_frames=2,
               nstep=1, save_every_frames=100, device="cpu", backend="synthetic")
        d = train(p, "drqv2", c, {"seed": 0}, os.path.join(tmp, "r"), verbose=False)
        import json
        ups = [json.loads(l)[tags.TRAIN_UPDATES] for l in open(os.path.join(d, "scalars.jsonl"))
               if tags.TRAIN_UPDATES in json.loads(l)]
        # frames 10..40 inclusive, every 2nd frame -> exactly 16 updates
        expected = len([f for f in range(1, 41) if f >= 10 and f % 2 == 0])
        assert max(ups) == expected, f"n_updates={max(ups)}, expected exactly {expected}"


@pytest.mark.slow   # builds a real robosuite env (backend="robosuite"), not synthetic
def test_preflight_does_not_fire_for_a_baseline_with_no_data_needs():
    """`problems and backend != "synthetic"` mutated to `or` refuses EVERY real-backend run.

    An earlier version of this test recomputed the condition in Python, which of course does not
    notice a change to the trainer's copy of it -- the mutant survived. The only way to test a
    guard is to go through the code that contains it, so this runs a genuinely tiny real-robosuite
    training run and requires it to get past the preflight.
    """
    import tempfile
    from rlgen.envs import UPSTREAM
    from rlgen.trainer import TrainConfig as TC
    from rlgen.trainer import train
    if not os.path.isdir(UPSTREAM):
        pytest.skip("RL-ViGen-upstream not present")
    assert registry.check_data_requirements("drqv2") == []
    with tempfile.TemporaryDirectory() as tmp:
        p = Protocol(task="Door", total_frames=2, eval_every_frames=1000, episodes_per_scene=1,
                     eval_scene_ids=(0,), horizon=2)
        c = TC(batch_size=2, replay_capacity=50, num_seed_frames=100, update_every_frames=2,
               nstep=1, save_every_frames=1000, device="cpu", backend="robosuite")
        d = train(p, "drqv2", c, {"seed": 0}, os.path.join(tmp, "r"), verbose=False)
        assert os.path.exists(os.path.join(d, "episodes.csv")), (
            "the preflight refused a baseline that needs no data")


# ============================================================ found by a real-simulator run
def test_every_overlay_implementation_follows_the_observation_device():
    """The same defect existed in TWO copies of `random_overlay`, and fixing one hid the other.

    RL-ViGen's `utils.py` returns `imgs.cuda()` unconditionally (patch P4). `rlgen/algos/
    augmentations.py` is a SEPARATE vendored copy that SODA imports, and it had the same bug.
    After P4, SVEA and SGQN came back green while SODA still died on the real simulator with
    "found at least two devices, mps:0 and cpu" -- fix-the-instance-not-the-class, exactly as
    docs/RIGOR.md section 4 describes it.

    Both copies are checked here, by source, because the failure needs a GPU/MPS machine to
    reproduce and CI may not have one.
    """
    import re
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    checked = 0
    for rel in ("rlgen/algos/augmentations.py",
                "RL-ViGen-upstream/utils.py"):
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        src = open(path, encoding="utf-8").read()
        if "def random_overlay" not in src:
            continue
        checked += 1
        assert not re.search(r"return\s+imgs\.cuda\(\)", src), (
            f"{rel}: `_get_places_batch` returns imgs.cuda() unconditionally; every overlay "
            f"baseline dies at its first update on a non-CUDA machine")
        assert re.search(r"imgs\.to\(|_places_device", src), (
            f"{rel}: the overlay batch is never moved to the observation's device")
    assert checked == 2, (
        f"expected to check two independent copies of random_overlay, checked {checked} -- if a "
        f"copy moved, this test stopped guarding it")


# ============================================================== the on-policy learning-rate anneal
# Survivors, unbiased sweep seed 202: `rlgen/trainer_onpolicy.py:146` twice --
#     learner.set_lr(min(1.0, frames / max(1, protocol.total_frames)))
#
# `linear_lr_decay` defaults to True (rlgen/algos/idaac/config.py:58), so this line sets the
# learning rate of EVERY on-policy arm -- idaac, ppg, ibac_sni, ctrl -- on every update, via
# `lr * max(0.0, 1.0 - frac_done)`. Nothing in the suite touched `set_lr`, `param_groups` or
# `linear_lr_decay`, so the whole schedule could be rescaled silently. A learning rate is not
# something you notice from a return curve: a wrong anneal looks like a method that trains poorly.
#
# On the survivors themselves: `set_lr` clamps with `max(0.0, ...)` and the call site clamps with
# `min(1.0, ...)`, so the two guards are REDUNDANT and a mutation of either alone is masked by the
# other. Some of the seed-202 survivors here are therefore equivalent mutants. These tests pin the
# anneal because it is load-bearing and untested, not because they kill those two specific mutants.

@pytest.mark.parametrize("frac,keep", [(0.0, 1.0), (0.25, 0.75), (0.5, 0.5),
                                       (1.0, 0.0), (1.5, 0.0)])
def test_on_policy_lr_anneals_linearly_and_clamps_at_both_ends(frac, keep):
    """UPDATED 2026-08-14 (docs/REGISTER.md): was `registry.get("ppg")`. `ppg` is now its own
    hermetic module (`rlgen/algos/ppg/`), and its `set_lr` is a deliberate, verified no-op --
    PPG's own reference has no LR decay anywhere (grepped `adjust_lr`/`lr_decay`/`scheduler`
    across `ppg.py`/`ppo.py`/`train.py`, zero matches). Testing linear annealing against a
    baseline that doesn't anneal isn't a stale assumption to patch around, it's the wrong
    baseline for this property -- switched to `idaac`, which genuinely anneals and genuinely
    owns `policy_opt`/`value_opt`/`disc_opt`. PPG's own no-op `set_lr` has its own dedicated test:
    `tests/test_ppg_algo.py::test_set_lr_is_a_no_op_matching_the_reference_having_no_decay`.
    """
    p = Protocol(task="Door", total_frames=0)
    agent = registry.get("idaac").build(p, p.obs_shape, 7, "cpu", {"seed": 0})
    learner = agent.learner
    base = float(learner.cfg.lr)
    returned = learner.set_lr(frac)

    assert returned == pytest.approx(base * keep), (
        f"set_lr({frac}) returned {returned}, expected lr*{keep} = {base * keep}")

    # The returned value is worthless if the optimizers did not actually receive it.
    seen = [g["lr"] for name in ("policy_opt", "value_opt", "disc_opt")
            for g in getattr(getattr(learner, name, None), "param_groups", [])]
    assert seen, "no optimizer param_groups found -- this test stopped checking anything"
    for lr in seen:
        assert lr == pytest.approx(base * keep), (
            f"set_lr({frac}) returned {returned} but an optimizer holds {lr}")


def test_the_trainer_feeds_set_lr_a_monotone_fraction_of_the_budget():
    """The call site, not just the setter: `frac_done` must run 0 -> 1 over the budget.

    Pins `frames / total_frames`. If that expression is rescaled, every on-policy arm silently
    trains on a different schedule while every curve still looks plausible.

    UPDATED 2026-08-14 (docs/REGISTER.md): was baseline="ppg", spying on `idaac_algo.Learner.
    set_lr`. Since `ppg` became its own hermetic module, it never calls that method at all --
    `seen` stayed empty and the test failed, correctly, once the two stopped being the same
    class. The property under test (does the trainer's own `frames/total_frames` computation
    reach `set_lr` correctly) is about the TRAINER's call site, not about PPG specifically --
    switched to baseline="idaac", which still genuinely goes through `idaac_algo.Learner`.
    """
    import tempfile
    from rlgen.algos.idaac import algo as idaac_algo
    from rlgen.trainer_onpolicy import train_onpolicy

    seen, original = [], idaac_algo.Learner.set_lr

    def spy(self, frac_done):
        seen.append(float(frac_done))
        return original(self, frac_done)

    idaac_algo.Learner.set_lr = spy
    try:
        p = Protocol(task="Door", total_frames=96, eval_every_frames=96, episodes_per_scene=1,
                     eval_scene_ids=(0,), horizon=8)
        c = TrainConfig(device="cpu", backend="synthetic", save_every_frames=100000,
                        batch_size=8, replay_capacity=300, num_seed_frames=8,
                        update_every_frames=2, nstep=1)
        hyper = {"seed": 0, "num_steps": 32, "num_mini_batch": 2, "epochs_policy": 1,
                 "epochs_value": 1, "disc_batch_size": 8, "value_update_every": 1}
        with tempfile.TemporaryDirectory() as t:
            train_onpolicy(p, "idaac", c, hyper, os.path.join(t, "idaac"), verbose=False)
    finally:
        idaac_algo.Learner.set_lr = original

    assert seen, "set_lr was never called during an on-policy run -- the anneal is not wired up"
    assert all(0.0 <= f <= 1.0 for f in seen), f"frac_done left [0, 1]: {seen}"
    assert seen == sorted(seen), f"frac_done is not monotone non-decreasing: {seen}"
    assert max(seen) == pytest.approx(1.0), (
        f"frac_done never reached 1.0 by the end of the budget (max {max(seen)}) -- the learning "
        f"rate never finishes annealing, which is exactly the bug this file already found in the "
        f"exploration schedule")


# ============================================================== ALDA's update-to-data ratio
# Found while cross-checking against the sibling gen-rebuttal project, which shares ALDA's exact
# port (`rlgen/algos/alda/{nets,config,agent,metrics}.py` are byte-identical to
# `gen-rebuttal/vigen-idaac/vigen_alda/{same names}.py`) and ran real GPU training on it.
#
# That project's STATE.md D1 measured, not argued: `utd=1.0` diverged 3 Lift runs across 2 seeds
# by ~141k frames (critic/loss > 1e8, Q above the reward ceiling, policy entropy collapsing);
# `utd=0.25` cleared 220k on both seeds with critic/loss in [0.46, 0.68]. `AldaConfig.utd`'s own
# comment already derived 0.25 as ALDA's design point translated to action_repeat=1 -- but the
# comment was attached to a default of 1.0, and nothing in configs/vigen.yaml's `alda:` block
# overrode it, so the wrong value was live. Fixed 2026-08-13.
def test_alda_utd_defaults_to_its_derived_faithful_value():
    from rlgen.algos.alda.config import AldaConfig
    assert AldaConfig().utd == pytest.approx(0.25), (
        "AldaConfig.utd's default has drifted from 0.25 -- the sibling gen-rebuttal project "
        "measured 1.0 diverging ALDA's critic on Lift within ~141k frames (STATE.md D1); read "
        "that comment before changing this back")


def test_alda_registry_launch_path_actually_carries_the_faithful_utd():
    """The dataclass default is necessary but not sufficient: `configs/vigen.yaml`'s `alda:`
    block, or a builder that silently drops the key (test_contract.py's KNOWN_LR_DROPS is exactly
    that failure mode for `lr`), could still override it back to something else without this
    test noticing. Build through the real registry path -- what `train.py` actually calls."""
    from rlgen import registry
    from rlgen.protocol import Protocol
    import yaml

    root = os.path.dirname(os.path.dirname(os.path.abspath(registry.__file__)))
    p = Protocol(task="Door", total_frames=0)
    with open(os.path.join(root, "configs", "vigen.yaml"), encoding="utf-8") as f:
        alda_cfg = yaml.safe_load(f)["alda"]
    hyper = {k: v for k, v in alda_cfg.items() if k not in ("baseline",) and k != "<<"}
    agent = registry.get("alda").build(p, p.obs_shape, 7, "cpu", {**hyper, "seed": 0})
    assert agent._m.cfg.utd == pytest.approx(0.25), (
        f"the constructed ALDA agent carries utd={agent._m.cfg.utd}, not 0.25 -- something "
        f"between configs/vigen.yaml and the registry build path is overriding the faithful "
        f"default")


# ============================================================== IDAAC's vectorization fields
# Found in the same cross-check. `rlgen/trainer_onpolicy.py` runs exactly one environment
# (`RolloutStorage(num_steps, 1, ...)`, the "1" a literal) and always will until the seam is
# vectorized -- see that file's own docstring. `IdaacConfig.num_envs` was inherited from the
# sibling gen-rebuttal project, where it IS wired to a real `SubprocVecEnv`; here nothing reads
# it, so `rollout_size`/`minibatch_size`/`total_updates` were silently computing values 8x the
# real ones. Not load-bearing -- `storage.feed_forward_generator` derives its minibatch size from
# the real stored tensor, not from these properties -- but "config lies about what it ran" is
# exactly the class of defect this project exists to catch, so the defaults were corrected to
# match reality rather than left as a cosmetic drift. Fixed 2026-08-13.
def test_idaac_vectorization_fields_match_what_the_trainer_actually_runs():
    from rlgen.algos.idaac.config import Config
    cfg = Config()
    assert cfg.num_envs == 1, (
        "IdaacConfig.num_envs no longer matches rlgen/trainer_onpolicy.py, which runs exactly "
        "one environment (RolloutStorage(..., 1, ...), a literal). If real vectorization was "
        "wired up, this test should be updated to match -- but check the trainer first")
    assert cfg.num_steps == 2048, (
        "configs/vigen.yaml's `idaac:` block overrides num_steps to 2048 at every real launch; "
        "the dataclass default should match so constructing Config() directly (as tests and "
        "future scripts will) reflects a real run")
    assert cfg.rollout_size == cfg.num_envs * cfg.num_steps == 2048, (
        "rollout_size should now equal the real per-update sample count")


def test_idaac_real_minibatch_size_matches_appendix_e_regardless_of_the_cfg_properties():
    """The property that actually matters -- verified against the REAL storage tensor
    `feed_forward_generator` reads from, not against `cfg.minibatch_size` (which could itself be
    wrong even after the fix above, e.g. if num_mini_batch drifts). Appendix E: '32 minibatches of
    a 2048 rollout = 64 samples each.'"""
    import torch
    from rlgen.algos.idaac.storage import RolloutStorage
    from rlgen.algos.idaac.config import Config

    cfg = Config()
    storage = RolloutStorage(cfg.num_steps, 1, (9, 84, 84), 7, torch.device("cpu"))
    storage.init_obs(torch.zeros((1, 9, 84, 84), dtype=torch.uint8))
    for i in range(cfg.num_steps):
        boot = torch.zeros((1, 1))
        storage.insert(torch.zeros((1, 9, 84, 84), dtype=torch.uint8),
                       torch.zeros((1, 7)), torch.zeros((1, 1)), torch.zeros((1, 1)),
                       torch.tensor([0.0]), torch.tensor([0.0]),
                       torch.tensor([1.0 if i == cfg.num_steps - 1 else 0.0]),
                       torch.tensor([0.0]), boot, 0.99)
    sizes = set()
    adv = torch.zeros((cfg.num_steps, 1, 1))
    for obs_b, act_b, lp_b, v_b, ret_b, adv_b in storage.feed_forward_generator(
            adv, cfg.num_mini_batch):
        sizes.add(obs_b.shape[0])
    assert sizes == {64}, (
        f"real minibatch sizes were {sizes}, not {{64}} -- Appendix E specifies 64 samples per "
        f"minibatch (32 minibatches of a 2048 rollout)")


# ================================================================== sgqn's aux_beta reachability
# Found on the 2026-08-14 pipeline audit: unlike `curl`, `sgqn`'s registry.build passes no
# `defaults` dict, and `configs/vigen.yaml`'s `sgqn:` block never set `aux_beta` -- so it silently
# ran on SGQNAgent's own constructor default (0.9) with no config path able to reach or override
# it. The value itself was fine (0.9 matches both canonical SGQN's argparse default and the paper's
# stated Adam beta1), but that was an unrecorded coincidence, not a verified decision -- the exact
# same shape of gap `aux_lr`'s dead 0.3 default was, before it was found to be catastrophically
# wrong. Fixed by adding an explicit `aux_beta: 0.9` line to `configs/vigen.yaml`'s `sgqn:` block;
# this test builds through the real registry path (what `train.py` actually calls) rather than
# trusting the yaml file to be read correctly, mirroring
# `test_alda_registry_launch_path_actually_carries_the_faithful_utd` above.
def test_sgqn_yaml_sets_aux_beta_explicitly():
    """`SGQNAgent`'s own constructor default (0.9) equals the value this repo wants, so a test
    that only checks the CONSTRUCTED agent's final beta1 cannot tell "reached via config" apart
    from "silently fell back to the constructor default" -- that coincidence is exactly what let
    this go unreached for however long it did. This checks the yaml file's own parsed contents
    directly instead: the key must be present, not merely the right number by luck."""
    import yaml

    root = os.path.dirname(os.path.dirname(os.path.abspath(registry.__file__)))
    with open(os.path.join(root, "configs", "vigen.yaml"), encoding="utf-8") as f:
        sgqn_cfg = yaml.safe_load(f)["sgqn"]
    assert "aux_beta" in sgqn_cfg, (
        "configs/vigen.yaml's sgqn: block no longer sets aux_beta explicitly -- it would silently "
        "fall back to SGQNAgent's own constructor default again, an unrecorded coincidence rather "
        "than a verified decision (see docs/FAITHFULNESS.md's sgqn section)")


def test_sgqn_registry_build_path_forwards_aux_beta_when_present():
    """Complements the yaml-contents test above: proves the FORWARDING mechanism
    (`_drqv2_family`'s `extra` whitelist in rlgen/registry.py) actually carries `aux_beta` from
    `hyper` into the constructed agent. Uses a value (0.42) that cannot coincide with any
    constructor default, so this is sensitive regardless of what SGQNAgent's own default happens
    to be -- unlike a test built from the real yaml value, which currently equals that default."""
    from rlgen.protocol import Protocol

    p = Protocol(task="Door", total_frames=0)
    agent = registry.get("sgqn").build(p, p.obs_shape, 7, "cpu", {"aux_beta": 0.42, "seed": 0})
    betas = agent._agent.aux_optimizer.param_groups[0]["betas"]
    assert betas[0] == pytest.approx(0.42), (
        f"the constructed SGQN agent's aux_optimizer carries beta1={betas[0]}, not the 0.42 "
        f"passed via hyper -- aux_beta is not reaching the constructor through the registry "
        f"build path")
