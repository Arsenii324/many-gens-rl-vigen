"""Per-update rollout buffer for CTRL's PPO/actor-critic phase. Duplicated from
`idaac/storage.py` (via `ibac_sni/storage.py`'s and `ppg/storage.py`'s own duplications), not
imported -- buffers are explicitly named in `porting-directive.md` §1 as never shared
("identical code under different parameters is a different object, not the same object
differently configured").

Same reasoning as `ppg`/`ibac_sni`'s own storage: the uint8-observation and
truncation-folded-into-reward corrections are environment-contract properties (robosuite
Door/Lift's fixed horizon means every episode end is a truncation), not any one paper's
algorithm. CTRL's own reference (`ext/ctrl_public/buffer.py::calculate_gae`) has no
truncation-vs-termination distinction either (`docs/REGISTER.md`, 2026-08-14: one `done` flag,
no separate `truncated` -- confirmed genuinely a Procgen-family property, not something CTRL
specifically chose against) -- re-deriving from it directly would reintroduce the same bug this
duplication exists to avoid.

This class handles the PPO/actor-critic rollout only (`num_steps` samples). The SSL/cluster
loss's sliding-window extraction over this same rollout (`extract_windows_vectorized` in the
reference) is CTRL-specific and lives in `algo.py`, not here -- this buffer's job is identical to
every other on-policy module's, and duplicating that identical job is the point; the part that
differs per baseline belongs in `algo.py`.

What's dropped, same as `ppg`/`ibac_sni`: `episode_id`/`ep_step`/`sample_order_pairs`/
`_pair_purity`/`advantage_time_correlation` -- IDAAC's own order-pair-discriminator and
time-correlation diagnostics, which CTRL's algorithm has no use for at all.
"""
from __future__ import annotations

import torch
from torch.utils.data.sampler import BatchSampler, SubsetRandomSampler


class RolloutStorage:
    def __init__(self, num_steps: int, num_envs: int, obs_shape, act_dim: int, device):
        T, N = num_steps, num_envs
        self.T, self.N, self.device = T, N, device
        self.obs = torch.zeros(T + 1, N, *obs_shape, dtype=torch.uint8, device=device)
        self.actions = torch.zeros(T, N, act_dim, device=device)
        self.logprobs = torch.zeros(T, N, 1, device=device)
        self.values = torch.zeros(T + 1, N, 1, device=device)
        self.rewards = torch.zeros(T, N, 1, device=device)        # + boot value at truncation
        self.rewards_raw = torch.zeros(T, N, 1, device=device)    # never touched, for reporting
        self.returns = torch.zeros(T + 1, N, 1, device=device)
        self.masks = torch.ones(T + 1, N, 1, device=device)       # 0 at an episode end
        self.n_truncated = 0
        self.n_terminated = 0
        self.step = 0

    def init_obs(self, obs) -> None:
        self.obs[0].copy_(torch.as_tensor(obs, device=self.device))

    def insert(self, next_obs, action, logprob, value, reward, reward_raw,
               done, truncated, boot_value, gamma: float) -> None:
        """`boot_value` is V(final_observation); read only where `truncated`. Identical formula
        to `idaac/storage.py::insert` -- same environment, same correctness requirement."""
        t = self.step
        assert t < self.T, f"rollout already full ({t}/{self.T})"
        d = done.float().unsqueeze(-1)
        r = reward.unsqueeze(-1) + gamma * truncated.float().unsqueeze(-1) * boot_value

        self.obs[t + 1].copy_(next_obs)
        self.actions[t].copy_(action)
        self.logprobs[t].copy_(logprob)
        self.values[t].copy_(value)
        self.rewards[t].copy_(r)
        self.rewards_raw[t].copy_(reward_raw.unsqueeze(-1))
        self.masks[t + 1].copy_(1.0 - d)
        self.n_truncated += int(truncated.sum())
        self.n_terminated += int((done.bool() & ~truncated.bool()).sum())
        self.step = t + 1

    def compute_returns(self, next_value, gamma: float, gae_lambda: float) -> None:
        """Plain GAE. No bad_masks: truncation is already folded into the reward at insert().
        Matches `buffer.py::calculate_gae`'s recursion exactly (`gae = delta + discount *
        gae_lambda * (1-done) * gae`), modulo the truncation-fold this project's environment
        needs and CTRL's own Procgen reference does not."""
        assert self.step == self.T, f"rollout only {self.step}/{self.T} full"
        self.values[-1].copy_(next_value)
        gae = torch.zeros_like(self.values[0])
        for t in reversed(range(self.T)):
            m = self.masks[t + 1]
            delta = self.rewards[t] + gamma * self.values[t + 1] * m - self.values[t]
            gae = delta + gamma * gae_lambda * m * gae
            self.returns[t] = gae + self.values[t]

    def after_update(self) -> None:
        self.obs[0].copy_(self.obs[-1])
        self.n_truncated = self.n_terminated = 0
        self.step = 0

    def advantages(self, normalize: bool = True):
        adv = self.returns[:-1] - self.values[:-1]
        self.adv_std_prenorm = float(adv.std())
        if normalize:
            adv = (adv - adv.mean()) / (adv.std() + 1e-5)
        return adv

    def feed_forward_generator(self, advantages, mini_batch_size: int, drop_last: bool = True):
        """Yields (obs, act, old_logprob, old_value, return, adv) minibatches, flattened over
        (T, N). `mini_batch_size` directly, matching `ppg`/`ibac_sni/storage.py`'s own
        convention -- CTRL's own reference (`algo.py::update_ppo`) takes a minibatch COUNT and
        divides internally (`size_minibatch = size_batch // n_minibatch`); `ctrl/algo.py`
        computes the equivalent size explicitly before calling this, so the actual per-step batch
        SIZE used for training matches the reference either way -- this is an API-convention
        difference, not a behavioral one."""
        B = self.T * self.N
        sampler = BatchSampler(SubsetRandomSampler(range(B)), mini_batch_size, drop_last=drop_last)
        obs_f = self.obs[:-1].reshape(B, *self.obs.shape[2:])
        act_f = self.actions.reshape(B, -1)
        lp_f = self.logprobs.reshape(B, 1)
        v_f = self.values[:-1].reshape(B, 1)
        ret_f = self.returns[:-1].reshape(B, 1)
        adv_f = advantages.reshape(B, 1)
        for idx in sampler:
            i = torch.as_tensor(idx, device=self.device)
            yield obs_f[i], act_f[i], lp_f[i], v_f[i], ret_f[i], adv_f[i]
