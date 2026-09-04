"""`ibac_sni`'s policy: internal self-consistency.

**Rewritten 2026-08-16** for the base-first rebuild. These test the module against *itself* —
shapes, gradient reachability, purity — which is real but weak: they would pass equally well on
an implementation of the wrong algorithm. Everything that checks the module against something
external lives in `tests/test_ibac_sni_base_parity.py`, and the distinction is deliberate
(`docs/RIGOR.md`, the vacuous-test failure modes).

Four tests were deleted rather than ported, because they pinned behaviour the rebuild removed as
wrong: they asserted the discarded construction's `sample=True/False` two-call API, its
`exp(clamp(log_sigma))` bottleneck, its `sni_lambda` mixing, and that `sni=False` produced a valid
update. Keeping them would have re-enforced the exact divergences the rebuild exists to fix — a
green suite defending a defect. See `docs/INTEGRATION-DELTA.md` I1, I2, I7.
"""
from __future__ import annotations

import pytest
import torch

from rlgen.algos.ibac_sni.config import Config
from rlgen.algos.ibac_sni.model import ImpalaModel
from rlgen.algos.ibac_sni.policy import IBACPolicy

OBS_SHAPE, ACT_DIM = (9, 84, 84), 7


def _policy(nr_samples=4):
    torch.manual_seed(0)
    cfg = Config()
    embedder = ImpalaModel(in_channels=OBS_SHAPE[0], image_size=cfg.image_size)
    return IBACPolicy(embedder, recurrent=False, action_size=ACT_DIM,
                      ib_dim=cfg.ib_dim, nr_samples=nr_samples,
                      scale_offset=cfg.scale_offset, init_scale=cfg.policy_head_init_scale)


def _obs(b=5):
    return torch.randint(0, 256, (b, *OBS_SHAPE), dtype=torch.uint8)


def test_forward_returns_the_references_four_pieces_with_the_right_shapes():
    """`pd_train` (mixture), `pd_run` (deterministic), one value, one scalar info loss."""
    p, x = _policy(nr_samples=4), _obs(5)
    pd_train, pd_run, value, info = p(x)
    assert pd_train.batch_shape == (5,) and pd_train.event_shape == (ACT_DIM,)
    assert pd_run.batch_shape == (5,) and pd_run.event_shape == (ACT_DIM,)
    # the mixture really is over nr_samples components, not collapsed to one
    assert pd_train.component_distribution.batch_shape == (5, 4)
    assert value.shape == (5,)
    assert info.dim() == 0, "info_loss is a scalar -- it is summed over dims and meaned over batch"


def test_info_loss_is_deterministic_and_independent_of_the_sampling():
    """`policies.py:61-67`: the KL is analytic, from (mu, sigma), computed once. It must not
    depend on which z's were drawn, or the SNI split would be leaking into the IB term."""
    p, x = _policy(), _obs()
    p.eval()
    with torch.no_grad():
        _a, _b, _v, i1 = p(x)
        _a, _b, _v, i2 = p(x)
    assert torch.allclose(i1, i2, atol=1e-6)


def test_every_parameter_receives_a_gradient():
    """A parameter with no gradient is a wiring bug that no shape assertion catches."""
    p, x = _policy(), _obs()
    pd_train, pd_run, value, info = p(x)
    a = pd_run.sample()
    loss = pd_train.log_prob(a).mean() + pd_run.log_prob(a).mean() + value.mean() + info
    loss.backward()
    missing = [n for n, q in p.named_parameters() if q.grad is None or not torch.isfinite(q.grad).all()]
    assert not missing, f"no/non-finite gradient reached: {missing}"


def test_deterministic_act_is_a_pure_function_of_the_observation():
    """`act(deterministic=True)` takes `pd_run.mean` -- no sampling anywhere on that path."""
    p, x = _policy(), _obs()
    p.eval()
    with torch.no_grad():
        a1, lp1 = p.act(x, deterministic=True)
        a2, lp2 = p.act(x, deterministic=True)
    assert torch.allclose(a1, a2, atol=1e-6) and torch.allclose(lp1, lp2, atol=1e-6)


def test_stochastic_act_actually_varies():
    """Guards the opposite failure: a `deterministic=False` path that silently isn't."""
    p, x = _policy(), _obs()
    p.eval()
    with torch.no_grad():
        a1, _ = p.act(x, deterministic=False)
        a2, _ = p.act(x, deterministic=False)
    assert not torch.allclose(a1, a2, atol=1e-6)


def test_act_shapes_match_the_trainer_contract():
    """`trainer_onpolicy.py` expects `(action, logprob)` with logprob keeping a trailing 1."""
    p, x = _policy(), _obs(3)
    with torch.no_grad():
        a, lp = p.act(x, deterministic=False)
    assert a.shape == (3, ACT_DIM) and lp.shape == (3, 1)


def test_recurrent_is_refused_rather_than_silently_wrong():
    """Declared exclusion (`__init__.py`): no config block in the reference enables it."""
    cfg = Config()
    embedder = ImpalaModel(in_channels=OBS_SHAPE[0], image_size=cfg.image_size)
    with pytest.raises(NotImplementedError):
        IBACPolicy(embedder, recurrent=True, action_size=ACT_DIM)
