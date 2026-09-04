"""The PPO-family baselines and the second trainer they need.

THE CENTRAL TEST HERE is `test_on_policy_and_off_policy_runs_are_comparable`. Adding a second
training loop is the most dangerous thing done to this repo: the brief allows training to differ
("если это не противоречит каким то особенностям обучения алгоритма") but requires *evaluation*
to be identical, and two loops is two places for the evaluation to drift. So the property is
asserted directly -- same protocol hash, same tag set, same episode count, same x-axis.
"""
from __future__ import annotations

import json
import os
import tempfile

import numpy as np
import pytest
import torch

from rlgen import registry, tags
from rlgen.agents import assert_respects_deterministic
from rlgen.protocol import Protocol
from rlgen.trainer import TrainConfig, train
from rlgen.trainer_onpolicy import train_onpolicy

ON_POLICY = [n for n, s in registry.BASELINES.items() if getattr(s, "on_policy", False)]


def tiny():
    return Protocol(task="Door", total_frames=96, eval_every_frames=96, episodes_per_scene=1,
                    eval_scene_ids=(0,), horizon=8)


def cfg():
    return TrainConfig(device="cpu", backend="synthetic", save_every_frames=100000,
                       batch_size=8, replay_capacity=300, num_seed_frames=8,
                       update_every_frames=2, nstep=1)


#: Deliberately cheap. IDAAC's defaults (several PPO epochs, a value net and an order
#: discriminator with its own pair sampling) made two of these tests 118s and 105s -- 70% of the
#: whole suite's runtime for 96 frames of training. The tests are about the LOOP, not about
#: convergence, so the epoch counts are turned down to the minimum that still exercises every
#: branch. Anything that depends on the shipped values is tested separately and directly
#: (test_sweep_gaps.py::test_shipped_trainer_defaults_are_the_documented_ones).
HYPER = {"seed": 0, "num_steps": 32, "num_mini_batch": 2,
         "n_policy_phases": 2, "aux_epochs": 1,
         "epochs_policy": 1, "epochs_value": 1, "disc_batch_size": 8,
         "value_update_every": 1}


def scalars(d):
    return [json.loads(l) for l in open(os.path.join(d, "scalars.jsonl")) if l.strip()]


def test_the_brief_has_an_on_policy_baseline_at_all():
    assert set(ON_POLICY) == {"ppg", "ibac_sni", "idaac", "ctrl"}, ON_POLICY


@pytest.mark.parametrize("name", ON_POLICY)
def test_constructs_acts_and_respects_deterministic(name):
    p = Protocol(task="Door", total_frames=0)
    agent = registry.get(name).build(p, p.obs_shape, 7, "cpu", {"seed": 0})
    assert_respects_deterministic(agent, p.obs_shape)
    obs = np.random.default_rng(0).integers(0, 256, size=p.obs_shape, dtype=np.uint8)
    a = agent.act(obs, deterministic=True)
    assert a.shape == (7,) and a.dtype == np.float32 and np.all(np.abs(a) <= 1.0 + 1e-6)


@pytest.mark.parametrize("name", sorted(registry.runnable()))
def test_the_registry_and_the_agent_agree_about_being_on_policy(name):
    """Two places record "is this on-policy"; they must not be able to disagree.

    `train.py:117` routes on `spec.on_policy` from the registry. The adapter also carries an
    `on_policy` class attribute, and nothing read it -- an unbiased sweep flipped
    `PPOFamilyAdapter.on_policy = True` to False and the whole suite stayed green.

    The mutant was strictly equivalent, since the attribute was dead. That is the problem, not the
    defence: a duplicated fact that no one checks is one refactor away from being the one that
    gets believed. Rather than pin the literal, this forbids the two from drifting apart.
    """
    spec = registry.get(name)
    p = Protocol(task="Door", total_frames=0)
    agent = spec.build(p, p.obs_shape, 7, "cpu", {"seed": 0})
    assert bool(getattr(agent, "on_policy", False)) == bool(spec.on_policy), (
        f"{name}: registry says on_policy={spec.on_policy} but the built agent says "
        f"{getattr(agent, 'on_policy', False)} -- the trainer is chosen from the registry, so "
        f"whichever is wrong, one of them is lying to the next reader")


@pytest.mark.parametrize("name", ON_POLICY)
def test_the_off_policy_trainer_refuses_an_on_policy_agent(name):
    """Silently no-op'ing would collect frames and never learn; the curve would look merely bad."""
    p = Protocol(task="Door", total_frames=0)
    agent = registry.get(name).build(p, p.obs_shape, 7, "cpu", {"seed": 0})
    with pytest.raises(RuntimeError, match="on-policy"):
        agent.update(None, 0)


@pytest.mark.slow
@pytest.mark.parametrize("name", ON_POLICY)
def test_training_actually_moves_the_parameters(name):
    """A loop that runs and learns nothing produces a full set of artifacts and a flat curve."""
    with tempfile.TemporaryDirectory() as t:
        p, c = tiny(), cfg()
        before = registry.get(name).build(p, p.obs_shape, 7, "cpu", {"seed": 0})
        w0 = {k: v.detach().clone()
              for k, v in before.learner.policy.state_dict().items() if v.dtype.is_floating_point}
        d = train_onpolicy(p, name, c, dict(HYPER), os.path.join(t, name), verbose=False)
        sd = torch.load(os.path.join(d, "checkpoint.pt"), map_location="cpu", weights_only=False)
        w1 = sd["agent"]["policy"]
        moved = sum(1 for k, v in w0.items()
                    if k in w1 and not torch.allclose(v, w1[k].float(), atol=0))
        assert moved > 0, f"{name}: not one policy parameter changed after training"
        ups = max(s.get(tags.TRAIN_UPDATES, 0) for s in scalars(d))
        assert ups > 0, f"{name}: no updates were recorded"


def test_ibac_bottleneck_is_silent_at_eval_and_noisy_in_training():
    """SNI's noise is a TRAINING construct. Sampling it at eval makes `policy_mode: deterministic`
    on the protocol card a false statement -- which is how this was originally shipped."""
    p = Protocol(task="Door", total_frames=0)
    agent = registry.get("ibac_sni").build(p, p.obs_shape, 7, "cpu", {"seed": 0})
    obs = np.random.default_rng(1).integers(0, 256, size=p.obs_shape, dtype=np.uint8)
    det = np.stack([agent.act(obs, deterministic=True) for _ in range(5)])
    assert np.allclose(det[0], det), "the bottleneck is still injecting noise at eval"
    stoch = np.stack([agent.act(obs, deterministic=False) for _ in range(8)])
    assert stoch.std(axis=0).mean() > 0, "training mode injects no noise at all"


def test_ibac_value_head_never_sees_the_noisy_or_sni_mixed_pass():
    """FIXED 2026-08-14. `Learner.update()` (the shared PPO core) computes one `feat` per obs and
    reuses it for both the policy loss and `value_from_feat(feat)`. Before this fix, `feat` during
    TRAINING was `encode_with_vib`'s SNI-mixed (noise-injected) pass, so the critic trained on the
    same noisy representation as the policy -- unlike three independent reference implementations
    (original TF CoinRun, the authors' own torch port, DZ's Procgen port), which all route the
    value head through the DETERMINISTIC bottleneck pass specifically, with the original code's own
    comment stating why: "VIB for regression seems like a bad idea."

    Tested black-box, without reaching into private attributes: `value_of` is deterministic in
    `sample=True` (noise-injecting) territory, i.e. in TRAINING mode, at a fixed observation and
    fixed weights. Before the fix this would have been false -- `torch.randn_like` draws fresh
    noise on every call, so two calls at the identical obs would have differed.
    """
    p = Protocol(task="Door", total_frames=0)
    agent = registry.get("ibac_sni").build(p, p.obs_shape, 7, "cpu", {"seed": 0})
    learner = agent.learner
    assert learner.policy.training, "this test must run in TRAINING mode, where the noisy pass "\
        "would otherwise be live -- eval mode already forces the deterministic branch"

    obs = torch.as_tensor(
        np.random.default_rng(2).integers(0, 256, size=(1, *p.obs_shape), dtype=np.uint8))
    v1 = learner.value_of(obs)
    v2 = learner.value_of(obs)
    v3 = learner.value_of(obs)
    assert torch.allclose(v1, v2) and torch.allclose(v2, v3), (
        f"value_of gave different results across repeated calls at the SAME observation while "
        f"training ({v1.item():.6f}, {v2.item():.6f}, {v3.item():.6f}) -- the value head is "
        f"reading a noise-injected pass again")

    # And the fix must not have silently detached the value head from the trainable bottleneck --
    # a gradient must still flow into the VIB bottleneck's parameters through the deterministic
    # branch, exactly as it did (via the noisy branch) before this fix, and exactly as every
    # reference implementation's V still trains the shared/bottleneck parameters.
    #
    # UPDATED 2026-08-16 for the base-first rebuild. The property under test is unchanged and is
    # now the reference's own, read directly from it: `policies.py:161` sets
    # `vf_run = vf_train = fc(h_vf, 'v', 1)` -- the value head reads ReLU(mu), which is
    # deterministic but still downstream of the bottleneck's trainable `encode` layer, so V must
    # still train those parameters. Only the API moved: one `forward(obs)` returning
    # `(pd_train, pd_run, value, info_loss)`, and the bottleneck is `learner.policy.bottleneck`.
    # (The 2026-08-14 note this replaces referred to `learner.policy.vib` and a `sample=` flag,
    # both of which belonged to the discarded construction -- see docs/INTEGRATION-DELTA.md.)
    for p_ in learner.policy.parameters():
        p_.grad = None
    _pd_train, _pd_run, v, _info = learner.policy(obs)
    v.sum().backward()
    vib_grad_norms = [p_.grad.abs().sum().item()
                      for p_ in learner.policy.bottleneck.parameters() if p_.grad is not None]
    assert vib_grad_norms and any(g > 0 for g in vib_grad_norms), (
        "no gradient reached the VIB bottleneck's parameters through the deterministic value "
        "path -- the value loss must not be disconnected from the bottleneck, only from its NOISE")


@pytest.mark.slow   # two real end-to-end training loops (off-policy drqv2 + on-policy ppg)
def test_on_policy_and_off_policy_runs_are_comparable():
    """THE test. Two training loops, one evaluation: same protocol hash, same tags, same x-axis.

    The brief permits training to differ where the algorithm requires it and requires evaluation
    to be identical. Two loops is two places for evaluation to drift, so the property is measured
    rather than asserted in a comment.
    """
    with tempfile.TemporaryDirectory() as t:
        p, c = tiny(), cfg()
        off = train(p, "drqv2", c, {"seed": 0}, os.path.join(t, "off"), verbose=False)
        on = train_onpolicy(p, "ppg", c, dict(HYPER), os.path.join(t, "on"), verbose=False)

        import csv
        def rows(d):
            with open(os.path.join(d, "episodes.csv"), encoding="utf-8") as f:
                return list(csv.DictReader(f))

        a, b = rows(off), rows(on)
        assert {r["protocol_hash"] for r in a} == {r["protocol_hash"] for r in b} == {p.hash()}, \
            "the two trainers produced different protocols; their numbers are not comparable"
        assert {int(r["frames"]) for r in a} == {int(r["frames"]) for r in b}, \
            "the two trainers evaluated at different frame counts"
        assert len(a) == len(b), f"different episode counts: {len(a)} vs {len(b)}"
        assert {r["policy_mode"] for r in a} == {r["policy_mode"] for r in b}

        ta = {k for s in scalars(off) for k in s if k != "frames"}
        tb = {k for s in scalars(on) for k in s if k != "frames"}
        required = set(tags.EVAL_TAGS) | set(tags.TRAIN_EVAL_TAGS) | {tags.GAP_ABSOLUTE}
        missing_a, missing_b = required - ta, required - tb
        ignorable = {tags.EVAL_SUCCESS_RATE, tags.TRAIN_EVAL_SUCCESS_RATE}
        assert not (missing_a - ignorable), f"off-policy run missing {missing_a - ignorable}"
        assert not (missing_b - ignorable), f"on-policy run missing {missing_b - ignorable}"


@pytest.mark.slow
@pytest.mark.parametrize("name", ON_POLICY)
def test_the_budget_is_a_hard_stop_not_a_rollout_boundary(name):
    """R4 is "the same training length for everyone", so `total_frames` must mean the same thing
    for both trainers.

    On-policy collection used to run to the end of the rollout that crossed the budget, finishing
    at 3072 frames where the off-policy loop finished at 3000 -- same protocol hash, one panel,
    final points at different x. Found by reading the results table, not by a test:
    `test_the_budget_is_honoured_exactly` covered only the off-policy loop.

    A budget deliberately NOT a multiple of `num_steps` is used, so the old behaviour cannot pass.
    """
    import csv
    with tempfile.TemporaryDirectory() as t:
        p = Protocol(task="Door", total_frames=100, eval_every_frames=100, episodes_per_scene=1,
                     eval_scene_ids=(0,), horizon=8)
        assert p.total_frames % 32 != 0, "the budget must not be a multiple of num_steps"
        d = train_onpolicy(p, name, cfg(), dict(HYPER), os.path.join(t, name), verbose=False)
        with open(os.path.join(d, "episodes.csv"), encoding="utf-8") as f:
            frames = {int(r["frames"]) for r in csv.DictReader(f)}
        assert max(frames) == p.total_frames, (
            f"{name}: finished at {max(frames)} frames, budget was {p.total_frames}")
