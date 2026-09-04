"""RAD -- Reinforcement Learning with Augmented Data (Laskin et al. 2020, arXiv:2004.14990).

RAD is SAC plus a data augmentation applied to the observations sampled from the replay buffer.
There is no auxiliary loss and no architectural change; the augmentation IS the method. The
previous implementation in this repo was `class RAD(SAC): pass` -- the name with none of the
content, which at train time is plain SAC (docs/REVIEW.md F6).

PROTOCOL DEVIATION, DECLARED. The paper's strongest augmentation is `random_crop`: render at
100x100 and crop to 84x84. RL-ViGen's robosuite renders at 84x84 directly, so there is nothing to
crop from -- `random_crop(x, size=84)` on an 84x84 image is the identity. Rendering at 100 instead
would change the observation for THIS baseline only, which breaks the one thing the whole repo
exists to protect.

So RAD uses `random_shift` (reflection-pad by 4, then crop back to 84), the translation
augmentation RL-ViGen's own DrQ-v2 uses at this resolution. It is the same *kind* of augmentation
-- a random translation -- at the resolution the shared protocol fixes. This is recorded in the
registry notes and therefore in `baselines/rad/README.md`, so a reader comparing against the
published RAD numbers knows which variant produced ours.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F

from . import augmentations
from .sac import SAC


def random_shift(x, pad: int = 4):
    """Random translation by up to `pad` pixels, torch-native.

    `augmentations.random_shift` needs kornia; this is the same operation with the bilinear-grid
    formulation RL-ViGen's own DrQ-v2 uses (`RandomShiftsAug`), so RAD and the DrQ-v2-family
    baselines are translated by the identical procedure and the comparison is not confounded by
    two different implementations of "random shift".
    """
    n, c, h, w = x.size()
    assert h == w, f"random_shift expects square observations, got {h}x{w}"
    x = F.pad(x, (pad,) * 4, mode="replicate")
    eps = 1.0 / (h + 2 * pad)
    arange = torch.linspace(-1.0 + eps, 1.0 - eps, h + 2 * pad,
                            device=x.device, dtype=x.dtype)[:h]
    arange = arange.unsqueeze(0).repeat(h, 1).unsqueeze(2)
    base_grid = torch.cat([arange, arange.transpose(1, 0)], dim=2)
    base_grid = base_grid.unsqueeze(0).repeat(n, 1, 1, 1)
    shift = torch.randint(0, 2 * pad + 1, size=(n, 1, 1, 2),
                          device=x.device, dtype=x.dtype)
    shift *= 2.0 / (h + 2 * pad)
    return F.grid_sample(x, base_grid + shift, padding_mode="zeros", align_corners=False)


class RAD(SAC):
    #: name -> callable(tensor) -> tensor. `random_shift` is the declared default; the others are
    #: available so the choice can be varied deliberately rather than by editing code.
    AUGMENTATIONS = {
        "random_shift": lambda x: random_shift(x, pad=4),
        "random_conv": augmentations.random_conv,
        "identity": augmentations.identity,
    }

    def __init__(self, obs_shape, action_shape, args):
        super().__init__(obs_shape, action_shape, args)
        name = getattr(args, "rad_augmentation", "random_shift")
        if name not in self.AUGMENTATIONS:
            raise ValueError(f"unknown rad_augmentation {name!r}; "
                             f"have {sorted(self.AUGMENTATIONS)}")
        self.augmentation_name = name
        self._aug = self.AUGMENTATIONS[name]

    def update(self, replay_buffer, L, step):
        obs, action, reward, next_obs, not_done = replay_buffer.sample()

        # THE method: augment both the observation and its successor, with independent draws.
        # Both, because the critic target is computed from next_obs and an un-augmented target
        # would make the augmentation a one-sided perturbation of the Bellman backup.
        obs = self._aug(obs)
        next_obs = self._aug(next_obs)

        self.update_critic(obs, action, reward, next_obs, not_done, L, step)
        if step % self.actor_update_freq == 0:
            self.update_actor_and_alpha(obs, L, step)
        if step % self.critic_target_update_freq == 0:
            self.soft_update_critic_target()
