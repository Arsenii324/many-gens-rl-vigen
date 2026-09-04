"""IBAC-SNI's rollout buffer.

**Re-anchored 2026-08-16, and kept rather than rebuilt.** This file's provenance was previously
stated as "Duplicated from `idaac/storage.py`" — i.e. anchored to another baseline's buffer, with
no claim relating it to IBAC-SNI's own base at all. The base was then read directly
(`_upstream_1678e4a/common_storage.py`, `common/storage.py` @ `1678e4a`) and this buffer's
semantics turn out to match it on every load-bearing point:

| | base (`common/storage.py`) | here |
|---|---|---|
| GAE delta | `(rew + gamma*V[i+1]*(1-done[i])) - V[i]` (`:56`) | `rewards[t] + gamma*V[t+1]*m - V[t]` |
| GAE recursion | `A = gamma*lmbda*A*(1-done[i]) + delta` (`:57`) | `gae = delta + gamma*lam*m*gae` |
| returns | `return_batch = adv_batch + value_batch[:-1]` (`:67`) | `returns[t] = gae + values[t]` |
| adv norm | once, globally, in `compute_estimates` (`:68-69`) | once, in `advantages()` |
| minibatches | `BatchSampler(SubsetRandomSampler(range(B)), mbs, drop_last=True)` (`:78-80`) | identical |

`m = masks[t+1] = 1 - done_at_step_t`, so the two mask indexings agree exactly. **This is not an
argument — it is a test**: `tests/test_ibac_sni_base_parity.py` runs the base's own
`Storage.compute_estimates` and this buffer on the same random rollout and asserts the advantages
and returns agree to floating point. That converts the whole table above from prose into an
artefact (`docs/STEP-ZERO.md` gate 2).

**The one deliberate divergence**, `porting-directive.md` §4: truncation. The base has no
truncation-vs-termination distinction — Procgen episodes terminate, they do not time out — so
transcribing it literally would treat every Door/Lift time limit as a terminal state and bias
every value estimate downward. `insert()` folds `gamma * truncated * V(final_obs)` into the
stored reward instead. This is the project-wide P4 adaptation (`docs/PREMISES.md`), independently
corroborated against `ALDA_Official`'s own trainer, which implements the general form
(`docs/REGISTER.md`, 2026-08-15). The parity test above therefore runs with `truncated=0`
throughout, where the two are supposed to agree; a separate case asserts they *diverge* exactly as
predicted when truncation fires, so the adaptation is pinned rather than merely described.

Not imported from any other baseline: `porting-directive.md` §1 names buffers as never shared.
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
        """Plain GAE. No bad_masks: truncation is already folded into the reward at insert()."""
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
        """Normalised ONCE, globally — `common/storage.py:68-69`, not per minibatch.

        The epsilon is `1e-8`, the base's own (`:69`). It was `1e-5` until 2026-08-16, inherited
        from `idaac/storage.py` when this file was anchored there; the base-parity test below
        fails on that difference, which is how it was found. Small, but it is a divergence from
        the base with nothing behind it, and `porting-directive.md` §4 has no room for an
        unexplained constant.
        """
        adv = self.returns[:-1] - self.values[:-1]
        self.adv_std_prenorm = float(adv.std())
        if normalize:
            adv = (adv - adv.mean()) / (adv.std() + 1e-8)
        return adv

    def feed_forward_generator(self, advantages, mini_batch_size: int, drop_last: bool = True):
        """Yields (obs, act, old_logprob, old_value, return, adv) minibatches, flattened over
        (T, N). `mini_batch_size` directly (not `num_mini_batch`, unlike `idaac/storage.py`) --
        the training loop needs an exact batch size to compute its own gradient-accumulation
        schedule against, matching DZ's reference's own `mini_batch_size`-first convention
        (`common/storage.py::fetch_train_generator`)."""
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
