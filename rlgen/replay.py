"""Replay buffer that stores single frames and stacks on read.

WHY NOT THE OBVIOUS THING. Storing the stacked observation costs
`capacity * 3 * frame_stack * 84 * 84` bytes -- 31 GB for a 500k-frame Door run at frame_stack 3.
Storing single frames and reconstructing the stack from indices costs a third of that. The sibling
project made exactly this change and went from 140 GB to 23.3 GB, which is the difference between
a run that fits on a rented GPU box and one that does not.

The hazard the design has to survive is the RING WRAP: once the buffer is full, index `i-1` may
belong to a *different, older* episode than index `i`, and naively stacking across that boundary
splices two unrelated trajectories into one observation. Two guards:

  * every frame carries its episode id, and a stack that would cross an episode boundary repeats
    the oldest valid frame instead (the same convention the env's own FrameStackWrapper uses at
    episode start);
  * indices whose stack window straddles the write head are excluded from sampling entirely.

`tests/test_replay.py` drives the buffer past capacity and asserts, frame by frame, that every
sampled stack comes from one episode. That test is red-green verified: reverting either guard
makes it fail.
"""
from __future__ import annotations

import numpy as np


class FrameReplay:
    def __init__(self, capacity: int, frame_shape: tuple, act_dim: int, frame_stack: int,
                 *, discount: float = 0.99, nstep: int = 3, seed: int = 0):
        if len(frame_shape) != 3 or frame_shape[0] != 3:
            raise ValueError(f"frame_shape {frame_shape} must be (3, H, W): the buffer stores "
                             f"single RGB frames and stacks on read")
        self.capacity = int(capacity)
        self.frame_stack = int(frame_stack)
        self.nstep = int(nstep)
        self.discount = float(discount)
        self._frames = np.zeros((self.capacity, *frame_shape), dtype=np.uint8)
        self._actions = np.zeros((self.capacity, act_dim), dtype=np.float32)
        self._rewards = np.zeros((self.capacity,), dtype=np.float32)
        self._episode = np.full((self.capacity,), -1, dtype=np.int64)
        self._done = np.zeros((self.capacity,), dtype=bool)
        self._idx = 0
        self._full = False
        self._ep = 0
        self._rng = np.random.default_rng(seed)

    def __len__(self) -> int:
        return self.capacity if self._full else self._idx

    @property
    def obs_shape(self) -> tuple:
        return (3 * self.frame_stack, *self._frames.shape[2:])

    def start_episode(self) -> None:
        self._ep += 1

    def add(self, frame: np.ndarray, action: np.ndarray, reward: float, done: bool) -> None:
        """`frame` is the LATEST single frame (3,H,W) uint8, not the stack."""
        f = np.asarray(frame)
        if f.dtype != np.uint8:
            raise TypeError(f"frame dtype {f.dtype}; the buffer stores uint8 and normalisation "
                            f"happens in the agent")
        if f.shape != self._frames.shape[1:]:
            raise ValueError(f"frame shape {f.shape}, expected {self._frames.shape[1:]}")
        i = self._idx
        self._frames[i] = f
        self._actions[i] = np.asarray(action, dtype=np.float32)
        self._rewards[i] = float(reward)
        self._episode[i] = self._ep
        self._done[i] = bool(done)
        self._idx = (i + 1) % self.capacity
        self._full = self._full or self._idx == 0

    def _stack(self, i: int) -> np.ndarray:
        """Frames [i-frame_stack+1 .. i], clamped at the episode start. Never crosses episodes."""
        ep = self._episode[i]
        out = np.empty(self.obs_shape, dtype=np.uint8)
        j = i
        for k in range(self.frame_stack - 1, -1, -1):
            out[3 * k:3 * k + 3] = self._frames[j]
            prev = (j - 1) % self.capacity
            # Stop walking back at an episode boundary or at the newest written frame.
            # NOTE the parentheses: `self._idx - 1 % self.capacity` parses as
            # `self._idx - (1 % capacity)` = `self._idx - 1`, which is -1 when _idx == 0 and
            # therefore never equals any index -- the guard silently switched itself off at
            # exactly the moment the ring wraps. Found by adversarial re-reading, not by a test;
            # `test_stack_guard_holds_at_the_wrap_boundary` now pins it.
            newest = (self._idx - 1) % self.capacity
            if self._episode[prev] == ep and prev != newest:
                j = prev
        return out

    def _valid_indices(self) -> np.ndarray:
        n = len(self)
        if n < self.frame_stack + self.nstep + 2:
            return np.empty(0, dtype=np.int64)
        idx = np.arange(n)
        # Exclude the window around the write head: those transitions have a `next` that has been
        # overwritten by newer data from a different episode.
        if self._full:
            lo = (self._idx - self.frame_stack - self.nstep - 1) % self.capacity
            hi = (self._idx + self.frame_stack + 1) % self.capacity
            if lo < hi:
                idx = idx[(idx < lo) | (idx > hi)]
            else:
                idx = idx[(idx < lo) & (idx > hi)]
        # n-step target must stay inside one episode
        ok = []
        for i in idx:
            j = (i + self.nstep) % self.capacity
            if self._episode[i] == self._episode[j] and self._episode[i] >= 0:
                ok.append(i)
        return np.asarray(ok, dtype=np.int64)

    def sample(self, batch_size: int):
        """-> obs, action, reward_nstep, discount_nstep, next_obs  (all np arrays)."""
        valid = self._valid_indices()
        if valid.size == 0:
            raise RuntimeError(
                f"replay has {len(self)} frames but no sampleable transition. Fill it before "
                f"the first update (num_seed_frames), or reduce nstep/frame_stack.")
        picks = self._rng.choice(valid, size=batch_size, replace=True)
        obs = np.stack([self._stack(int(i)) for i in picks])
        nxt = np.stack([self._stack(int((i + self.nstep) % self.capacity)) for i in picks])
        act = self._actions[picks]
        rew = np.zeros(batch_size, dtype=np.float32)
        disc = np.ones(batch_size, dtype=np.float32)
        for b, i in enumerate(picks):
            for k in range(self.nstep):
                j = int((i + k) % self.capacity)
                rew[b] += disc[b] * self._rewards[j]
                # Door/Lift never terminate early, so `done` here is a time limit, and the
                # bootstrap is kept -- discounting is NOT zeroed. Treating a time limit as a
                # terminal state biases every value estimate downward.
                disc[b] *= self.discount
        return obs, act, rew[:, None], disc[:, None], nxt

    def as_iterator(self, batch_size: int):
        """DrQ-v2-family agents call `next(replay_iter)` and expect torch tensors."""
        import torch
        while True:
            obs, act, rew, disc, nxt = self.sample(batch_size)
            yield (torch.as_tensor(obs), torch.as_tensor(act), torch.as_tensor(rew),
                   torch.as_tensor(disc), torch.as_tensor(nxt))


class SacView:
    """Presents a `FrameReplay` with the interface the SAC-family agents expect.

    `sac.py` and `soda.py` are the original implementations, and they call
    `replay_buffer.sample()` with no arguments and `replay_buffer.sample_soda(n)`. Rather than
    edit those files to match this repo's buffer -- which would make every future diff against
    the reference harder to read -- the buffer is adapted to them.

    `not_done` is ALWAYS 1. Door and Lift have no early termination, so every episode end is a
    time limit, and a time limit must be bootstrapped through rather than treated as terminal.
    Zeroing it there is the classic silent downward bias on every value estimate.
    """

    def __init__(self, replay: "FrameReplay", batch_size: int, device, float_obs: bool = True):
        """`float_obs` because the two SAC-descended families disagree, legitimately.

        `sac.py`/`soda.py` normalise inside their encoder and expect float tensors. ALDA asserts
        `obs.dtype == torch.uint8` on entry and normalises itself -- a contract check worth
        keeping, not working around. So the view converts or does not, and the caller says which;
        neither agent is edited to suit the other.
        """
        self._r, self._bs, self._device = replay, batch_size, device
        self._float = float_obs

    def _to(self, x):
        import torch
        return torch.as_tensor(x, device=self._device)

    def _obs(self, x):
        t = self._to(x)
        return t.float() if self._float else t

    def sample(self):
        import torch
        obs, act, rew, disc, nxt = self._r.sample(self._bs)
        not_done = torch.ones((self._bs, 1), dtype=torch.float32, device=self._device)
        return (self._obs(obs), self._to(act), self._to(rew).float(),
                self._obs(nxt), not_done)

    def sample_soda(self, batch_size):
        """Observations only, for the auxiliary loss. Float, on device, un-normalised."""
        obs, _a, _r, _d, _n = self._r.sample(batch_size)
        return self._to(obs).float()
