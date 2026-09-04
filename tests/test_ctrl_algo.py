"""`rlgen/algos/ctrl/algo.py::Learner` -- end-to-end, including the pieces a shape check can't
reach: does the target network EMA in the direction the reference's formula actually specifies
(tau=0.95 moves the target MOSTLY to online, not the reverse -- an easy sign/direction bug), does
the update actually move parameters, and are the two online-only-computed-never-consumed heads
(w_clust_mlp, w_pred_mlp -- `docs/REGISTER.md`, 2026-08-14: confirmed a property of the reference
itself, not a bug here) correctly UNMOVED rather than accidentally wired into some loss.
"""
from __future__ import annotations

import types

import torch

from rlgen.algos.ctrl.algo import Learner, _sinkhorn
from rlgen.algos.ctrl.storage import RolloutStorage

OBS_SHAPE = (9, 84, 84)
ACT_DIM = 7


def _cfg(**overrides):
    base = dict(
        lr=5e-4, lr_ctrl=1e-4, linear_lr_decay=False, max_grad_norm=0.5, gamma=0.99,
        gae_lambda=0.95, clip_param=0.2, value_loss_coef=0.5, entropy_coef=0.0,
        num_mini_batch=4, epochs_policy=1, hidden_dim=256, init_log_std=-1.0,
        ctrl_window=4, ctrl_clusters=4, ctrl_cluster_momentum=0.95, lr_cluster_epochs=1,
        n_minibatch_ctrl=2, temp=0.1, sinkhorn_k=1, myow_k=1, myow_reg=1.0,
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


def _rollout(learner, T=32, device="cpu"):
    storage = RolloutStorage(T, 1, OBS_SHAPE, ACT_DIM, device)
    obs = torch.randint(0, 256, (1, *OBS_SHAPE), dtype=torch.uint8)
    storage.init_obs(obs)
    with torch.no_grad():
        for t in range(T):
            a, lp = learner.policy.act(storage.obs[t], deterministic=False)
            v = learner.value_of(storage.obs[t])
            nxt = torch.randint(0, 256, (1, *OBS_SHAPE), dtype=torch.uint8)
            done = torch.zeros(1, dtype=torch.bool)
            truncated = torch.zeros(1, dtype=torch.bool)
            if t == T - 1:
                done[:] = True
                truncated[:] = True
            reward = torch.rand(1)
            boot_value = learner.value_of(nxt) if truncated.any() else torch.zeros(1, 1)
            storage.insert(nxt, a, lp, v, reward, reward.clone(), done, truncated,
                           boot_value, gamma=0.99)
        next_value = learner.value_of(storage.obs[-1])
    storage.compute_returns(next_value, gamma=0.99, gae_lambda=0.95)
    return storage


def test_update_moves_every_parameter_that_the_reference_itself_would_move():
    torch.manual_seed(0)
    learner = Learner(_cfg(), OBS_SHAPE, ACT_DIM, "cpu")
    before = {n: p.clone() for n, p in learner.policy.named_parameters()}
    row = learner.update(_rollout(learner), update_idx=0)
    assert row["health/nonfinite"] == 0.0

    unmoved = [n for n, p in learner.policy.named_parameters() if torch.equal(p, before[n])]
    # w_clust_mlp/w_pred_mlp (ONLINE copies): confirmed by direct grep of algo.py that the
    # reference itself never consumes bare w_clust/w_pred anywhere past the unpacking line --
    # only w_clust_target/w_pred_target (TARGET copies) are read. This is a property of the
    # reference, not a bug -- these must NOT move.
    expected_unmoved = {n for n in before if n.startswith("_w_clust_mlp.") or n.startswith("_w_pred_mlp.")}
    assert set(unmoved) == expected_unmoved, (
        f"unmoved set changed shape -- either a real parameter stopped receiving gradient "
        f"(investigate) or w_clust_mlp/w_pred_mlp unexpectedly moved (investigate the loss "
        f"wiring): got {set(unmoved)}, expected {expected_unmoved}")


def test_target_network_moves_mostly_to_online_at_the_launch_default_tau():
    """tau=0.95 means new_target = 0.95*online + 0.05*old_target -- the target ends up much
    closer to online than to its own previous value. A flipped-sign transcription
    (new_target = 0.05*online + 0.95*old_target) would leave the target almost unchanged
    instead -- this test distinguishes the two."""
    torch.manual_seed(0)
    learner = Learner(_cfg(ctrl_cluster_momentum=0.95), OBS_SHAPE, ACT_DIM, "cpu")
    online_before = learner.policy.encoder.fc.weight.clone()
    target_before = learner.target.encoder.fc.weight.clone()
    # Perturb the online encoder so before/after target movement is unambiguous.
    with torch.no_grad():
        learner.policy.encoder.fc.weight.add_(1.0)
    learner._target_update(tau=0.95)
    target_after = learner.target.encoder.fc.weight

    dist_to_online = (target_after - learner.policy.encoder.fc.weight).abs().mean()
    dist_to_old_target = (target_after - target_before).abs().mean()
    assert dist_to_online < dist_to_old_target, (
        "at tau=0.95 the target should end up close to the (perturbed) online weights, not "
        "close to its own previous value -- looks like the EMA direction is flipped")


def test_target_hard_copies_fc_v_dist_head_protos_not_ema():
    torch.manual_seed(0)
    learner = Learner(_cfg(), OBS_SHAPE, ACT_DIM, "cpu")
    with torch.no_grad():
        learner.policy.fc_v.weight.add_(1.0)
        learner.policy.protos.weight.add_(1.0)
    learner._target_update(tau=0.01)  # tiny tau: EMA'd params should barely move
    assert torch.equal(learner.target.fc_v.weight, learner.policy.fc_v.weight)
    assert torch.equal(learner.target.protos.weight, learner.policy.protos.weight)


def test_sinkhorn_output_is_a_valid_per_sample_assignment_distribution():
    """`sinkhorn`'s final step (`algo.py:166`, `Q = Q / sum(Q, axis=0, keepdims=True)`) normalizes
    COLUMNS of the pre-transpose Q (indexed by sample) to sum to 1, then transposes -- so in the
    RETURNED (n_samples, n_clusters) matrix, it's ROWS that sum to 1 (each sample's soft
    assignment over clusters is a valid distribution), not columns. Verified against the formula
    by hand before writing this assertion, not assumed."""
    torch.manual_seed(0)
    scores = torch.randn(6, 3)
    q = _sinkhorn(scores, temp=0.1, k=3)
    assert q.shape == scores.shape
    assert torch.all(q >= 0)
    row_sums = q.sum(dim=1)
    assert torch.allclose(row_sums, torch.ones_like(row_sums), atol=1e-4)


def test_set_lr_is_a_no_op_matching_the_reference_having_no_decay():
    learner = Learner(_cfg(lr=5e-4), OBS_SHAPE, ACT_DIM, "cpu")
    assert learner.set_lr(0.0) == learner.set_lr(1.0) == 5e-4
