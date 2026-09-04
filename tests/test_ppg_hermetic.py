"""`rlgen/algos/ppg/model.py` -- the dual-network PPG model, checked against the same class of
property the IBAC-SNI hermetic tests check: gradient reachability, deterministic-act purity, and
(specific to PPG's dual-network design) that `net.value()`'s fast path returns exactly the same
thing as `forward()`'s `vpred_true` -- a real, checkable consistency property since they're
computed via two different code paths (one recomputes `pi_enc` needlessly if wrong, one doesn't).
"""
from __future__ import annotations

import torch

from rlgen.algos.ppg.model import PPGPolicy, logp

OBS_SHAPE = (9, 84, 84)
ACT_DIM = 7


def _net_and_obs(seed: int = 0, batch: int = 4):
    torch.manual_seed(seed)
    net = PPGPolicy(OBS_SHAPE, ACT_DIM)
    obs = torch.randint(0, 256, (batch, *OBS_SHAPE), dtype=torch.uint8)
    return net, obs


def test_forward_shapes():
    net, obs = _net_and_obs()
    dist, vtrue, vaux = net(obs)
    assert dist.mean.shape == (4, ACT_DIM)
    # (B,), not (B,1): the reference's heads end in `[..., 0]` (`ppg.py:150,153`), so the
    # trailing singleton is dropped. The discarded construction kept it; this expectation was
    # updated to the reference's shape, not the other way round.
    assert vtrue.shape == (4,)
    assert vaux.shape == (4,)


def test_value_fast_path_matches_forwards_vpred_true_exactly():
    """`net.value()` deliberately skips computing pi_feat -- if it accidentally read from the
    wrong encoder, this is the check that would catch it."""
    net, obs = _net_and_obs()
    net.eval()
    with torch.no_grad():
        _dist, vtrue, _vaux = net(obs)
        v_only = net.value(obs)
    assert torch.equal(v_only, vtrue)


def test_every_parameter_receives_a_gradient():
    net, obs = _net_and_obs()
    act = torch.rand(4, ACT_DIM) * 2 - 1
    dist, vtrue, vaux = net(obs)
    loss = logp(dist, act).mean() + vtrue.mean() + vaux.mean()
    loss.backward()
    missing = [n for n, p in net.named_parameters() if p.requires_grad and p.grad is None]
    assert not missing, f"parameters never reached by any loss term: {missing}"


def test_deterministic_act_is_a_pure_function_of_obs():
    net, obs = _net_and_obs()
    net.eval()
    with torch.no_grad():
        a1, lp1 = net.act(obs, deterministic=True)
        a2, lp2 = net.act(obs, deterministic=True)
    assert torch.equal(a1, a2)
    assert torch.equal(lp1, lp2)


def test_pi_and_vf_encoders_are_genuinely_separate_modules():
    """arch="dual" means no shared parameters between the policy and value encoders at all --
    the exact property that distinguishes this from arch="shared", which the shared core
    (onpolicy_ext.py) effectively forced by giving PPG no separate value_net."""
    net, _obs = _net_and_obs()
    pi_ids = {id(p) for p in net.pi_enc.parameters()}
    vf_ids = {id(p) for p in net.vf_enc.parameters()}
    assert pi_ids.isdisjoint(vf_ids), "pi_enc and vf_enc must not share any parameter tensors"
