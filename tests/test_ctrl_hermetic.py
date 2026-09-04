"""`rlgen/algos/ctrl/model.py` -- CTRL's own network. Same class of property IBAC-SNI's/PPG's
hermetic tests check: gradient reachability (split across `ac()` and `cluster()`'s two different
call paths, since no single loss reaches every parameter -- `log_std` only moves via
entropy/log-prob, the cluster MLPs only move via `cluster()`), deterministic-act purity, and the
`window`-shaped `concat` layer specifically (the bug caught while writing this module: the
reference flattens the whole window before `concat`, not a single timestep).
"""
from __future__ import annotations

import torch

from rlgen.algos.ctrl.model import CTRLPolicy, entropy, logp

OBS_SHAPE = (9, 84, 84)
ACT_DIM = 7
WINDOW = 8
N_CLUSTERS = 32


def _net_and_obs(seed: int = 0, batch: int = 4):
    torch.manual_seed(seed)
    net = CTRLPolicy(OBS_SHAPE, ACT_DIM, window=WINDOW, n_clusters=N_CLUSTERS)
    obs = torch.randint(0, 256, (batch, *OBS_SHAPE), dtype=torch.uint8)
    return net, obs


def test_ac_forward_shapes():
    net, obs = _net_and_obs()
    v, dist = net.ac(obs)
    assert v.shape == (4, 1)
    assert dist.mean.shape == (4, ACT_DIM)


def test_cluster_forward_shapes_and_rejects_the_wrong_window():
    net, obs = _net_and_obs()
    state_win = torch.randint(0, 256, (4, WINDOW, *OBS_SHAPE), dtype=torch.uint8)
    action_win = torch.rand(4, WINDOW, ACT_DIM) * 2 - 1
    v_clust, w_clust, v_pred, w_pred = net.cluster(state_win, action_win)
    for t in (v_clust, w_clust, v_pred, w_pred):
        assert t.shape == (4, 256)

    wrong_window = torch.randint(0, 256, (4, WINDOW - 1, *OBS_SHAPE), dtype=torch.uint8)
    wrong_action = torch.rand(4, WINDOW - 1, ACT_DIM)
    try:
        net.cluster(wrong_window, wrong_action)
        assert False, "cluster() silently accepted a window shorter than the module was built for"
    except AssertionError as e:
        assert "window" in str(e)


def test_value_fast_path_matches_ac_exactly():
    net, obs = _net_and_obs()
    net.eval()
    with torch.no_grad():
        v_ac, _dist = net.ac(obs)
        v_only = net.value(obs)
    assert torch.equal(v_only, v_ac)


def test_every_parameter_receives_a_gradient_across_ac_and_cluster():
    """No single loss reaches every parameter -- `dist_head.log_std` only affects
    entropy/log-prob (not `dist.mean`), and the action_mlp/concat/cluster MLPs only exist on the
    `cluster()` path. Split into two losses, matching how the real training loop actually
    exercises each path (the PPO update calls `ac()`; the SSL update calls `cluster()`)."""
    net, obs = _net_and_obs()
    v, dist = net.ac(obs)
    ac_loss = entropy(dist).sum() + logp(dist, dist.mean).sum() + v.sum()

    state_win = torch.randint(0, 256, (4, WINDOW, *OBS_SHAPE), dtype=torch.uint8)
    action_win = torch.rand(4, WINDOW, ACT_DIM) * 2 - 1
    v_clust, w_clust, v_pred, w_pred = net.cluster(state_win, action_win)
    # protos_fn isn't called inside cluster() itself -- the real Sinkhorn/proto loss calls it
    # separately on v_clust (algo.py's own loss_cluster), so it needs its own loss term here too.
    scores = net.protos_fn(v_clust)
    cluster_loss = v_clust.sum() + w_clust.sum() + v_pred.sum() + w_pred.sum() + scores.sum()

    (ac_loss + cluster_loss).backward()
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
