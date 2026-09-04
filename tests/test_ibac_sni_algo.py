"""`ibac_sni`'s learner: the update loop's own invariants.

**Rewritten 2026-08-16** for the base-first rebuild. Self-consistency only; the checks against
the actual reference and the actual base live in `tests/test_ibac_sni_base_parity.py`.

`test_sni_disabled_still_produces_a_valid_update` was deleted, not ported: `sni=False` is now
refused outright, because the reference's non-SNI branch aliases `pd_run` to `pd_train`
(`policies.py:186-189`) rather than merely skipping the mix. A test asserting that an unsupported
configuration "produces a valid update" was asserting that something wrong ran without complaint.
"""
from __future__ import annotations

import numpy as np
import pytest
import torch

from rlgen.algos.ibac_sni.algo import Learner, NonFiniteLoss
from rlgen.algos.ibac_sni.config import Config

OBS_SHAPE, ACT_DIM, DEV = (9, 84, 84), 7, torch.device("cpu")


def _learner(**over):
    torch.manual_seed(0)
    cfg = Config()
    cfg.nr_samples = 3          # keep the test cheap; the mechanism is unchanged
    cfg.num_mini_batch = 4
    for k, v in over.items():
        setattr(cfg, k, v)
    return Learner(cfg, OBS_SHAPE, ACT_DIM, DEV)


def _filled_storage(L, T=16):
    S = L.storage_cls(T, 1, OBS_SHAPE, ACT_DIM, DEV)
    obs = torch.randint(0, 256, (1, *OBS_SHAPE), dtype=torch.uint8)
    S.init_obs(obs)
    for t in range(T):
        with torch.no_grad():
            a, lp = L.policy.act(obs, deterministic=False)
            v = L.value_of(obs)
        nxt = torch.randint(0, 256, (1, *OBS_SHAPE), dtype=torch.uint8)
        done = t == T - 1
        r = L.normalize_reward(float(np.random.randn()), done)
        S.insert(nxt, a, lp, v, torch.tensor([r]), torch.tensor([r]),
                 torch.tensor([float(done)]), torch.tensor([float(done)]),
                 torch.zeros(1, 1), L.cfg.gamma)
        obs = nxt
    with torch.no_grad():
        nv = L.value_of(obs)
    S.compute_returns(nv, L.cfg.gamma, 0.95)
    return S


def test_every_parameter_moves_after_one_update():
    L = _learner()
    before = {n: p.detach().clone() for n, p in L.policy.named_parameters()}
    L.update(_filled_storage(L), 0)
    frozen = [n for n, p in L.policy.named_parameters() if torch.equal(before[n], p.detach())]
    assert not frozen, f"parameters unchanged by an update: {frozen}"


def test_gradient_accumulation_defers_the_optimizer_step():
    """`agents_ppo.py:101-106`: step only on an accumulation boundary.

    With `grad_accum_steps` larger than the number of minibatches in the whole update, no
    boundary is ever reached and NOTHING may move. That is the base's own behaviour, and it is
    the only way to tell accumulation is real rather than decorative.
    """
    L = _learner(grad_accum_steps=10_000, epochs_policy=1, num_mini_batch=2)
    before = {n: p.detach().clone() for n, p in L.policy.named_parameters()}
    L.update(_filled_storage(L), 0)
    moved = [n for n, p in L.policy.named_parameters() if not torch.equal(before[n], p.detach())]
    assert not moved, f"stepped despite never reaching an accumulation boundary: {moved}"


def test_update_reports_the_info_and_l2_terms_separately():
    """Both are real terms in `ppo2.py:153`; folding them into the total would hide them."""
    L = _learner()
    out = L.update(_filled_storage(L), 0)
    assert out["Loss/info_bits"] > 0.0
    assert out["Loss/l2"] > 0.0
    assert all(np.isfinite(v) for v in out.values())


def test_beta_zero_removes_the_information_term_from_the_gradient():
    """A knob that changes a reported number but not the gradient would be decoration.

    `vib_beta=0` must leave the bottleneck's own `encode` layer with a gradient that comes only
    from the policy/value path -- checked by comparing against a run where beta is large.
    """
    def grad_norm(beta):
        # `grad_accum_steps` is set past any reachable boundary on purpose: `update()` zeroes the
        # gradients on every optimizer step, so with the normal schedule there would be nothing
        # left to measure afterwards and this test would compare 0.0 against 0.0 and pass
        # vacuously. Suppressing the step leaves the accumulated gradient intact.
        L = _learner(vib_beta=beta, epochs_policy=1, num_mini_batch=2, grad_accum_steps=10_000)
        torch.manual_seed(1)
        np.random.seed(1)
        S = _filled_storage(L, T=8)
        L.update(S, 0)
        return sum(float(p.grad.norm()) for p in L.policy.bottleneck.parameters()
                   if p.grad is not None)
    assert grad_norm(0.0) != pytest.approx(grad_norm(1.0), rel=1e-3)


def test_sni_false_is_refused_not_silently_run():
    with pytest.raises(NotImplementedError, match="sni=False"):
        _learner(sni=False)


def test_non_finite_loss_aborts_rather_than_poisoning_the_weights():
    L = _learner()
    S = _filled_storage(L)
    S.returns[:] = float("nan")
    before = {n: p.detach().clone() for n, p in L.policy.named_parameters()}
    with pytest.raises(NonFiniteLoss):
        L.update(S, 0)
    assert all(torch.equal(before[n], p.detach()) for n, p in L.policy.named_parameters()), \
        "weights moved before the non-finite loss was caught"


def test_lr_decays_linearly_per_the_bases_adjust_lr():
    """`misc_util.py:33-37`: `lr = init_lr * (1 - t/max_t)`."""
    L = _learner()
    assert L.set_lr(0.0) == pytest.approx(L.cfg.lr)
    assert L.set_lr(0.5) == pytest.approx(L.cfg.lr * 0.5)
    assert L.set_lr(1.0) == pytest.approx(0.0)
