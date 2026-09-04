"""PPG's rollout buffer.

**Base**: `_upstream_7295473/ppo.py:20-52` (`compute_gae`) for the advantage math, and this
project's shared on-policy trainer contract for the container shape. The reference's own
`roller.py` collects `(nenv, nstep)` segments across many parallel envs and hands them to
`compute_gae` as whole tensors; this project runs **one** env, so the container is per-step and
the recursion is written in the equivalent backward form. That is a container change, not a math
change, and it is checked rather than asserted: `tests/test_ppg_base_parity.py` runs the
reference's own `compute_gae` against this buffer on identical inputs.

**The reference's `first` flag is the inverse of a mask.** `compute_gae` takes
`first: (nenv, nstep+1)` marking episode *starts*, indexed one ahead of the reward — the same
information as `masks[t+1] = 1 - done[t]` here, written the other way round. Getting that
inversion wrong is a silent off-by-one in the bootstrap, so it is the thing the parity test
pins hardest.

**The one deliberate divergence** (`porting-directive.md` §4): truncation. PPG's reference is
Procgen, where episodes terminate; Door/Lift only ever time out. `insert()` folds
`gamma * truncated * V(final_obs)` into the stored reward, the project-wide P4 adaptation
(`docs/PREMISES.md`), so a time limit is not treated as a terminal state. Identical in intent to
`ibac_sni/storage.py`'s and independently cited here — buffers are never shared
(`porting-directive.md` §1).
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
        self.rewards = torch.zeros(T, N, 1, device=device)       # + boot value at truncation
        self.rewards_raw = torch.zeros(T, N, 1, device=device)   # never touched, for reporting
        self.returns = torch.zeros(T + 1, N, 1, device=device)
        self.masks = torch.ones(T + 1, N, 1, device=device)      # 0 at an episode end
        self.n_truncated = 0
        self.n_terminated = 0
        self.step = 0

    def init_obs(self, obs) -> None:
        self.obs[0].copy_(torch.as_tensor(obs, device=self.device))

    def insert(self, next_obs, action, logprob, value, reward, reward_raw,
               done, truncated, boot_value, gamma: float) -> None:
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
        """`compute_gae` (`ppo.py:20-52`), single-env backward form.

        `m = masks[t+1] = 1 - done[t]` is the reference's `first[t+1]` inverted; `vtarg` there is
        `adv + vpred`, which is `returns[t]` here.
        """
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
        """PPG normalises advantages inside its own minibatch loop
        (`ppo.py::learn`, via `tu.explained_variance` bookkeeping and the `adv` it passes on);
        this project normalises once per update, matching every other on-policy baseline here so
        the choice lands uniformly rather than selectively (`docs/STEP-ZERO.md` gate 3)."""
        adv = self.returns[:-1] - self.values[:-1]
        self.adv_std_prenorm = float(adv.std())
        if normalize:
            adv = (adv - adv.mean()) / (adv.std() + 1e-8)
        return adv

    def feed_forward_generator(self, advantages, mini_batch_size: int, drop_last: bool = True):
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
