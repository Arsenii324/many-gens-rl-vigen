"""Rollout buffer: uint8 observations, truncation-corrected GAE, episode-aware order pairs.

Three deliberate departures from [IK] RolloutStorage / IDAAC's fork, each with a reason.

CHANGE 1 -- observations are uint8, not float32.
  Upstream allocates float32 because the encoder divides by 255 inside the network. At
  9x84x84 with T=256, N=8 that is 0.52 GB, and IDAAC keeps a second copy for the order
  pairs. uint8 makes it 0.13 GB. [F:R6]

CHANGE 2 -- truncation is folded into the reward, not handled by bad_masks.
  Robosuite Door/Lift are fixed-horizon with no early termination, so EVERY episode end is
  a truncation. [IK]'s use_proper_time_limits path zeroes the GAE at truncation, discarding
  the transition; the branch IDAAC's Procgen fork almost certainly runs has no bad_masks at
  all, which drops the bootstrap entirely. We do the standard correct thing:
      r_t <- r_t + gamma * V(s_final),  then treat the step as terminal.
  [F:D4]. Verified against a closed-form two-segment GAE in tests/test_storage.py.

CHANGE 3 -- order pairs are episode-aware.
  The paper defines the discriminator on "two observations from the same trajectory" (p5).
  [IK]'s generator flattens (T,N,...) and samples uniformly, so any pair construction built
  on it crosses environment and episode boundaries. [F:D2, F:R4]

Indexing convention, used everywhere: a flat index into a (T, N) tensor is `t * N + n`,
which is what `.view(T*N, ...)` produces. tests/test_storage.py pins this.
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
        self.rewards = torch.zeros(T, N, 1, device=device)        # normalized, + boot value
        self.rewards_raw = torch.zeros(T, N, 1, device=device)    # never touched by the normalizer
        self.returns = torch.zeros(T + 1, N, 1, device=device)
        self.masks = torch.ones(T + 1, N, 1, device=device)       # 0 at an episode end
        self.episode_id = torch.zeros(T + 1, N, dtype=torch.long, device=device)
        self.ep_step = torch.zeros(T, N, dtype=torch.long, device=device)
        self._ep_counter = torch.zeros(N, dtype=torch.long, device=device)
        self.n_truncated = 0
        self.n_terminated = 0
        self.step = 0

    # ------------------------------------------------------------------ #
    def init_obs(self, obs) -> None:
        self.obs[0].copy_(torch.as_tensor(obs, device=self.device))

    def insert(self, next_obs, action, logprob, value, reward, reward_raw,
               done, truncated, boot_value, gamma: float) -> None:
        """`boot_value` is V(final_observation); it is only read where `truncated`."""
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
        # Written together with obs[t+1], before the step counter moves. IDAAC's fork writes
        # its labels *after* the increment, skewing them by one index and clobbering the
        # first entry on wrap-around -- see [F:B4]. Do not reproduce that.
        self.episode_id[t + 1] = self.episode_id[t] + done.long()
        self.ep_step[t] = self._ep_counter
        self._ep_counter = (self._ep_counter + 1) * (1 - done.long())
        self.n_truncated += int(truncated.sum())
        self.n_terminated += int((done.bool() & ~truncated.bool()).sum())
        self.step = t + 1

    def compute_returns(self, next_value, gamma: float, gae_lambda: float) -> None:
        """Plain GAE. No bad_masks: truncation is already folded into the reward."""
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
        # masks[0] is deliberately NOT carried: compute_returns reads masks[t+1] for
        # t in 0..T-1, i.e. masks[1..T], so masks[0] can never affect anything. Carrying it
        # implied a dependency that does not exist (BUGHUNT Pass F: inert code is a lie about
        # what the system does). obs[0] and episode_id[0] ARE read, and are carried.
        self.episode_id[0].copy_(self.episode_id[-1])
        self.n_truncated = self.n_terminated = 0
        self.step = 0

    # ------------------------------------------------------------------ #
    def advantages(self, normalize: bool = True):
        """[IK] normalizes over the WHOLE rollout once per update, not per minibatch, and the
        DAAC advantage head regresses onto that normalized quantity. Kept as upstream."""
        adv = self.returns[:-1] - self.values[:-1]
        self.adv_std_prenorm = float(adv.std())          # detector D3 in RUNBOOK
        if normalize:
            adv = (adv - adv.mean()) / (adv.std() + 1e-5)
        return adv

    def feed_forward_generator(self, advantages, num_mini_batch: int):
        B = self.T * self.N
        assert B >= num_mini_batch
        mb = B // num_mini_batch
        sampler = BatchSampler(SubsetRandomSampler(range(B)), mb, drop_last=True)
        obs_f = self.obs[:-1].reshape(B, *self.obs.shape[2:])
        act_f = self.actions.reshape(B, -1)
        lp_f = self.logprobs.reshape(B, 1)
        v_f = self.values[:-1].reshape(B, 1)
        ret_f = self.returns[:-1].reshape(B, 1)
        adv_f = advantages.reshape(B, 1)
        for idx in sampler:
            i = torch.as_tensor(idx, device=self.device)
            yield obs_f[i], act_f[i], lp_f[i], v_f[i], ret_f[i], adv_f[i]

    def sample_order_pairs(self, batch_size: int, max_rounds: int = 8):
        """Flat indices i, j into T*N (i = t*N + n), same env, same episode, t_i != t_j.
        label = 1 iff s_i came first. Returns (obs_i, obs_j, label, same_episode_frac)."""
        N, T = self.N, self.T
        I, J, L = [], [], []
        got = 0
        for _ in range(max_rounds):
            k = batch_size * 2
            n = torch.randint(0, N, (k,), device=self.device)
            t1 = torch.randint(0, T, (k,), device=self.device)
            t2 = torch.randint(0, T, (k,), device=self.device)
            ok = (self.episode_id[t1, n] == self.episode_id[t2, n]) & (t1 != t2)
            n, t1, t2 = n[ok], t1[ok], t2[ok]
            I.append(t1 * N + n)
            J.append(t2 * N + n)
            L.append((t1 < t2).float())
            got += int(n.numel())
            if got >= batch_size:
                break
        i = torch.cat(I)[:batch_size]
        j = torch.cat(J)[:batch_size]
        lbl = torch.cat(L)[:batch_size].unsqueeze(-1)
        assert i.numel() >= max(1, batch_size // 2), (
            f"only {i.numel()}/{batch_size} same-episode pairs after {max_rounds} rounds; "
            "episodes are shorter than expected -- check the horizon")
        # _pair_purity is detector D4: 1.0 by construction, measured anyway so a future
        # refactor cannot quietly reintroduce cross-episode pairs.
        flat = self.obs[:-1].reshape(T * N, *self.obs.shape[2:])
        return flat[i], flat[j], lbl, self._pair_purity(i, j)

    def _pair_purity(self, i, j) -> float:
        """Fraction of sampled pairs that really are same-env, same-episode. RUNBOOK D4."""
        N = self.N
        ti, ni = i // N, i % N
        tj, nj = j // N, j % N
        same_env = ni == nj
        same_ep = self.episode_id[ti, ni] == self.episode_id[tj, nj]
        return float((same_env & same_ep).float().mean())

    # ------------------------------------------------------------------ #
    def advantage_time_correlation(self, adv_pred_flat) -> float:
        """Pearson corr(A_hat(s_t,a_t), step-within-episode), the other half of I1.

        IDAAC Table 2 claims the *advantage* shows no dependence on the episode step while
        the value does -- that asymmetry is the mechanism. Logging only corr(V,t) cannot
        distinguish "the mechanism is working" from "there is no time signal to remove".
        """
        return _pearson(adv_pred_flat.reshape(-1).float(), self.ep_step.reshape(-1).float())

    def value_time_correlation(self) -> float:
        """Pearson corr(V(s_t), step-within-episode). The scalar form of IDAAC Fig. 16-19 /
        Table 2: a shared-network agent is claimed to learn a near-linear V(t), which is the
        time-to-go memorization that hurts generalization. Robosuite is fixed-horizon with no
        time in the observation, so this is the direct test of whether IDAAC's mechanism is
        live here at all. [F:I1] -- costs nothing, log it every update."""
        return _pearson(self.values[:-1].reshape(-1).float(), self.ep_step.reshape(-1).float())


def _pearson(a: torch.Tensor, b: torch.Tensor) -> float:
    a = a - a.mean()
    b = b - b.mean()
    d = a.norm() * b.norm()
    return float((a @ b) / d) if float(d) > 0 else 0.0
