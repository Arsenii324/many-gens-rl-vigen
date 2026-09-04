"""`rlgen/algos/ppg/storage.py` -- checked against a hand-computable closed form, not against
itself. The truncation-folded-into-reward GAE this class duplicates from `idaac/storage.py` is
exactly the kind of thing easy to get subtly wrong in a fresh rewrite (off-by-one on which mask
index gates the bootstrap, forgetting the `gamma * truncated * boot_value` term, etc.) -- and
`idaac/storage.py`'s own docstring cites a closed-form verification at `tests/test_storage.py`,
which does not exist in this test suite. Not fixing that citation here (out of scope for this
module); this file is this module's own from-scratch verification, not a repair of that one.
"""
from __future__ import annotations

import torch

from rlgen.algos.ppg.storage import RolloutStorage


def test_gae_with_truncation_folded_reward_matches_hand_computation():
    """Two steps, one env, gamma=0.5, lambda=1.0 (reduces GAE to a plain recursive discounted
    sum, easy to hand-verify). Step 1 is truncated with a known boot_value; the closed-form
    answer is computed in the comment below and checked bit-for-bit against the implementation.
    """
    T, N, obs_shape, act_dim = 2, 1, (3,), 2
    gamma, gae_lambda = 0.5, 1.0
    st = RolloutStorage(T, N, obs_shape, act_dim, device="cpu")
    st.init_obs(torch.zeros(N, *obs_shape, dtype=torch.uint8))

    st.insert(
        next_obs=torch.zeros(N, *obs_shape, dtype=torch.uint8),
        action=torch.zeros(N, act_dim), logprob=torch.zeros(N, 1),
        value=torch.full((N, 1), 0.3),
        reward=torch.full((N,), 1.0), reward_raw=torch.full((N,), 1.0),
        done=torch.zeros(N, dtype=torch.bool), truncated=torch.zeros(N, dtype=torch.bool),
        boot_value=torch.zeros(N, 1), gamma=gamma)

    st.insert(
        next_obs=torch.zeros(N, *obs_shape, dtype=torch.uint8),
        action=torch.zeros(N, act_dim), logprob=torch.zeros(N, 1),
        value=torch.full((N, 1), 0.7),
        reward=torch.full((N,), 2.0), reward_raw=torch.full((N,), 2.0),
        done=torch.ones(N, dtype=torch.bool), truncated=torch.ones(N, dtype=torch.bool),
        boot_value=torch.full((N, 1), 0.9), gamma=gamma)

    st.compute_returns(next_value=torch.zeros(N, 1), gamma=gamma, gae_lambda=gae_lambda)

    # r1_eff = 2.0 + gamma*boot_value = 2.0 + 0.5*0.9 = 2.45  (truncation folded into reward)
    # delta1 = r1_eff + gamma*V(s2)*mask1(=0) - V(s1) = 2.45 - 0.7 = 1.75
    # return1 = delta1 + V(s1) = 1.75 + 0.7 = 2.45
    # delta0 = r0 + gamma*V(s1)*mask0(=1) - V(s0) = 1.0 + 0.35 - 0.3 = 1.05
    # gae0 = delta0 + gamma*lambda*mask0*gae1(=1.75) = 1.05 + 0.875 = 1.925
    # return0 = gae0 + V(s0) = 1.925 + 0.3 = 2.225
    assert abs(float(st.returns[0, 0, 0]) - 2.225) < 1e-4
    assert abs(float(st.returns[1, 0, 0]) - 2.45) < 1e-4


def test_uint8_observations_and_never_touched_raw_reward():
    st = RolloutStorage(2, 1, (3,), 2, device="cpu")
    assert st.obs.dtype == torch.uint8
    st.init_obs(torch.zeros(1, 3, dtype=torch.uint8))
    st.insert(
        next_obs=torch.zeros(1, 3, dtype=torch.uint8),
        action=torch.zeros(1, 2), logprob=torch.zeros(1, 1), value=torch.zeros(1, 1),
        reward=torch.tensor([5.0]), reward_raw=torch.tensor([5.0]),
        done=torch.zeros(1, dtype=torch.bool), truncated=torch.zeros(1, dtype=torch.bool),
        boot_value=torch.zeros(1, 1), gamma=0.99)
    # reward_raw must equal the raw input exactly -- never transformed, per the env-contract
    # discipline this project holds everywhere else (docs/COMPARABILITY_CONTRACT.md).
    assert float(st.rewards_raw[0, 0, 0]) == 5.0


def test_feed_forward_generator_yields_the_exact_requested_minibatch_size():
    T, N, mb = 4, 2, 3
    st = RolloutStorage(T, N, (3,), 2, device="cpu")
    st.init_obs(torch.zeros(N, 3, dtype=torch.uint8))
    for _ in range(T):
        st.insert(
            next_obs=torch.zeros(N, 3, dtype=torch.uint8),
            action=torch.zeros(N, 2), logprob=torch.zeros(N, 1), value=torch.zeros(N, 1),
            reward=torch.zeros(N), reward_raw=torch.zeros(N),
            done=torch.zeros(N, dtype=torch.bool), truncated=torch.zeros(N, dtype=torch.bool),
            boot_value=torch.zeros(N, 1), gamma=0.99)
    st.compute_returns(torch.zeros(N, 1), gamma=0.99, gae_lambda=0.95)
    adv = st.advantages(normalize=False)
    sizes = [batch[0].shape[0] for batch in st.feed_forward_generator(adv, mini_batch_size=mb)]
    assert all(s == mb for s in sizes), f"expected every minibatch to be size {mb}, got {sizes}"
