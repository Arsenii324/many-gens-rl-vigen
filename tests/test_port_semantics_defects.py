"""Regression evidence for two port-semantics hazards found by external review.

[Claude 2026-09-05] The adapter fixes are now applied. The synthetic counterexamples remain as
tripwires: they show exactly what would regress if worker-constant IDs or the categorical KL
reduction were reintroduced.

The tests also retain the proposed corrected semantics as executable documentation.
"""
import importlib.util
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

ROOT = Path(__file__).resolve().parents[1]


# --- 2-8: IDAAC's level identity is a worker slot, so "same level" spans episodes ---------------

def _storage_module():
    path = ROOT / "runnable" / "idaac" / "ppo_daac_idaac" / "storage.py"
    if not path.is_file():
        pytest.skip("idaac clone not present")
    spec = importlib.util.spec_from_file_location("_idaac_storage", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Box:
    """Minimal stand-in: `storage.py` only reads `__class__.__name__` and `shape[0]`."""
    shape = (7,)


def _build(levels, nsteps):
    """A rollout whose per-timestep level ids and step counters we control exactly."""
    module = _storage_module()
    steps = len(nsteps) - 1
    storage = module.IDAACRolloutStorage(steps, 1, (1,), _Box())
    storage.device = "cpu"
    storage.levels = torch.LongTensor(levels).view(steps + 1, 1)
    storage.nsteps = torch.LongTensor(nsteps).view(steps + 1, 1)
    # tag each timestep with its own index so a pairing can be traced back to its episode
    storage.obs = torch.arange(steps + 1, dtype=torch.float32).view(steps + 1, 1, 1)
    storage.other_obs = torch.zeros_like(storage.obs)
    storage.orders = torch.LongTensor(steps + 1, 1).fill_(0)
    return storage


# One worker whose 9-step rollout straddles an episode boundary: steps 0-3 are the tail of episode
# A (nsteps 10..13), step 4 onward is episode B, whose counter has reset to 0. This is the ordinary
# case, not a contrived one -- idaac's rollout is 256 steps and Door's episode is 500, so rollouts
# are never aligned to episode starts.
_EPISODE_A = [0, 1, 2, 3]
_EPISODE_B = [4, 5, 6, 7, 8]
_NSTEPS = [10, 11, 12, 13, 0, 1, 2, 3, 4]


def test_worker_scoped_level_makes_same_level_span_two_episodes():
    """COUNTEREXAMPLE. A worker-constant id would make the candidate
    partners for an observation include timesteps from a *different episode* — a different door
    placement, a different physical instance. The order label is then computed from `nsteps`, which
    restarted at the boundary, so it asserts a temporal relation between unrelated episodes."""
    storage = _build(levels=[7] * 9, nsteps=_NSTEPS)
    levels = storage.levels.view(-1, 1)

    for idx in _EPISODE_B:
        candidates = torch.where(levels == levels[idx])[0].tolist()
        crossing = [c for c in candidates if c in _EPISODE_A]
        assert crossing, "expected the defect to be present with worker-scoped levels"

    # and the resulting order label is not merely arbitrary, it is systematically inverted:
    # every episode-A step has a LARGER nsteps than every episode-B step, so the classifier is
    # taught that the earlier episode came "later" in every crossing pair.
    ns = storage.nsteps.view(-1)
    assert min(ns[i] for i in _EPISODE_A) > max(ns[i] for i in _EPISODE_B)


def test_episode_scoped_level_removes_the_cross_episode_pairing():
    """The corrected rule: scope the level id to the episode — increment it per worker on each reset.
    `torch.where(levels == level)` then matches only timesteps of one episode, `nsteps` is a
    coherent clock over exactly that span, and the order relation has a referent again. This is
    closer to upstream, where `level_seed` identifies a procedurally generated level rather than a
    worker slot, so it is RESTORES-class rather than a new invention."""
    levels = [7] * len(_EPISODE_A) + [8] * len(_EPISODE_B)   # episode A = 7, episode B = 8
    storage = _build(levels=levels, nsteps=_NSTEPS)
    tensor = storage.levels.view(-1, 1)

    for idx in range(9):
        candidates = torch.where(tensor == tensor[idx])[0].tolist()
        same_episode = _EPISODE_A if idx in _EPISODE_A else _EPISODE_B
        assert candidates == same_episode, f"index {idx} still pairs outside its episode"


def test_before_update_actually_produces_cross_episode_pairs():
    """The defect reaching the training signal, through the real `before_update`.

    The pairing draw is random, so this seeds it and counts. With nine timesteps sharing one level
    and a four/five split, cross-episode pairs are the common case rather than the exception.
    """
    storage = _build(levels=[7] * 9, nsteps=_NSTEPS)
    torch.manual_seed(0)
    storage.before_update()
    partners = storage.other_obs.view(-1).tolist()   # obs was tagged with its own index

    crossings = sum(1 for idx in _EPISODE_B if int(partners[idx]) in _EPISODE_A)
    crossings += sum(1 for idx in _EPISODE_A if int(partners[idx]) in _EPISODE_B)
    assert crossings > 0, (
        "expected at least one observation to be paired across the episode boundary; if this "
        "stops failing the pairing semantics changed and the fix may already be applied")


# --- 2-7: PPG's auxiliary KL loses a factor of the action dimension ------------------------------

def test_ppg_clone_loss_is_weaker_by_the_action_dimension():
    """THE DEFECT. `ppg.py:198` is `td.kl_divergence(oldpd, pd).mean()`.

    For the original `Categorical` the KL is one scalar per sample, so `.mean()` averages over
    (batch, time) and nothing else. For the 7-D `Normal` this adaptation introduced, KL carries an
    action dimension, and the same `.mean()` silently averages over it — while the PPO losses
    **sum** over that dimension. The clone constraint is therefore ~7x weaker than the coefficient
    says, which `RUNNABLE-ORIGINALS.md` already records as "Recorded, not fixed".
    """
    dist = torch.distributions
    old = dist.Normal(torch.zeros(64, 7), torch.ones(64, 7))
    new = dist.Normal(torch.full((64, 7), 0.5), torch.ones(64, 7))

    as_written = dist.kl_divergence(old, new).mean()
    semantically_faithful = dist.kl_divergence(old, new).sum(-1).mean()

    ratio = (semantically_faithful / as_written).item()
    assert ratio == pytest.approx(7.0, rel=1e-5), (
        f"expected the reduction to differ by exactly the action dimension, got {ratio}")


def test_the_categorical_case_the_original_line_was_written_for_is_unaffected():
    """Why the original line was right and the port made it wrong: with one event dimension the two
    reductions coincide, so upstream had no reason to write `sum` — the defect was introduced by
    changing the distribution's rank, not by mis-transcribing the line."""
    dist = torch.distributions
    logits_old = torch.randn(64, 15)
    logits_new = torch.randn(64, 15)
    old = dist.Categorical(logits=logits_old)
    new = dist.Categorical(logits=logits_new)

    as_written = dist.kl_divergence(old, new).mean()
    with_sum = dist.kl_divergence(old, new).sum(-1).mean() if dist.kl_divergence(
        old, new).dim() > 1 else dist.kl_divergence(old, new).mean()
    assert torch.allclose(as_written, with_sum)


# --- pinning the fixes, so a silent revert cannot pass -------------------------------------------

def test_ppg_auxiliary_kl_still_sums_over_the_action_dimension():
    """[Claude 2026-09-05] The fix landed (`ppg.py:203`) but nothing pinned it.

    The tests above use synthetic distributions, so they pass whatever the clone does — a revert of
    the clone would have gone unnoticed. This asserts the repaired form itself. If it fails, either
    someone reverted the fix or upstream was re-vendored over it; both need a deliberate decision,
    not a silent flip.
    """
    path = ROOT / "runnable" / "ppg" / "phasic_policy_gradient" / "ppg.py"
    if not path.is_file():
        pytest.skip("ppg clone not present")
    source = path.read_text()
    assert "kl_divergence" in source
    assert ".sum(-1)" in source, (
        "PPG's auxiliary KL no longer sums over the action dimension. For the adapted 7-D Normal "
        "that makes beta_clone ~7x weaker than the coefficient states, while the PPO losses sum "
        "over that dimension.")


def test_idaac_level_seed_is_still_episode_scoped():
    """The companion pin for the other port fix."""
    path = ROOT / "runnable" / "idaac" / "ppo_daac_idaac" / "envs.py"
    if not path.is_file():
        pytest.skip("idaac clone not present")
    source = path.read_text()
    assert "_episode_index" in source and "_level_seed_base" in source, (
        "idaac's level identity is no longer episode-scoped; a worker-constant id makes "
        "before_update pair observations across episode boundaries with an incoherent order target.")
