"""SODA (Hansen & Wang, ICRA 2021, arXiv:2011.13389), transcribed from
`nicklashansen/dmcontrol-generalization-benchmark` (`src/algorithms/soda.py`,
`ext/dmcontrol-generalization-benchmark`, HEAD `ff9c0aa`).

Confirmed near-verbatim 2026-08-14 (`docs/ORIGINAL_LOCATIONS.md`/`docs/REGISTER.md`): differs from
the vendored original only in `.cuda()` -> `.to(self.device)` (device-agnosticism), the declared
crop-vs-shift protocol deviation in `update_soda` below (already documented inline, unchanged
here), and one bug this project found and fixed -- `train()`'s guard checked
`hasattr(self, 'soda_predictor')`, a name `__init__` never sets (it sets `self.predictor`), so the
guard was always false in the ORIGINAL too. See `train()` below for the fix and why the guard is
still needed, just on the right name.
"""
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from copy import deepcopy
import rlgen.algos.soda_utils as utils
import rlgen.algos.modules as m
from rlgen.algos.sac import SAC
import rlgen.algos.augmentations as augmentations


class SODA(SAC):
	def __init__(self, obs_shape, action_shape, args):
		super().__init__(obs_shape, action_shape, args)
		self.aux_update_freq = args.aux_update_freq
		self.soda_batch_size = args.soda_batch_size
		self.soda_tau = args.soda_tau

		shared_cnn = self.critic.encoder.shared_cnn
		aux_cnn = self.critic.encoder.head_cnn
		soda_encoder = m.Encoder(
			shared_cnn,
			aux_cnn,
			m.SODAMLP(aux_cnn.out_shape[0], args.projection_dim, args.projection_dim)
		)

		self.predictor = m.SODAPredictor(soda_encoder, args.projection_dim).to(self.device)
		self.predictor_target = deepcopy(self.predictor)

		self.soda_optimizer = torch.optim.Adam(
			self.predictor.parameters(), lr=args.aux_lr, betas=(args.aux_beta, 0.999)
		)
		self.train()

	def train(self, training=True):
		super().train(training)
		# FIXED 2026-08-14, CORRECTED SAME DAY: originally `hasattr(self, 'soda_predictor')`, a
		# name that is never set anywhere -- `__init__` sets `self.predictor` (line 27), not
		# `self.soda_predictor` -- so the guard was always false and `self.predictor.train(...)`
		# was never called explicitly. A guard is still needed, though, just not that one:
		# `SAC.__init__` (this class's own `super().__init__()`, sac.py:50) calls `self.train()`
		# on ITSELF before returning, and Python's dynamic dispatch resolves that to THIS
		# override -- at that point `SODA.__init__` has not yet reached the line that builds
		# `self.predictor`, so calling it unconditionally raises `AttributeError` (caught by the
		# full suite, not by the red-green check on the narrower fix alone -- see
		# docs/FAITHFULNESS.md's `soda` section). Guard on the correct name instead of removing
		# the guard.
		if hasattr(self, "predictor"):
			self.predictor.train(training)

	def compute_soda_loss(self, x0, x1):
		h0 = self.predictor(x0)
		with torch.no_grad():
			h1 = self.predictor_target.encoder(x1)
		h0 = F.normalize(h0, p=2, dim=1)
		h1 = F.normalize(h1, p=2, dim=1)

		return F.mse_loss(h0, h1)

	def update_soda(self, replay_buffer, L=None, step=None):
		x = replay_buffer.sample_soda(self.soda_batch_size)

		# PROTOCOL DEVIATION, DECLARED (many-gens-rl-vigen).
		# Upstream SODA renders at 100x100 and random-crops to 84x84, and asserted
		# `x.size(-1) == 100`. RL-ViGen's robosuite renders at 84x84, so there is nothing to crop
		# from; rendering at 100 for this baseline alone would change the observation for one row
		# of the table, which is the single thing this repo exists to prevent.
		# So the crop becomes a random SHIFT at the protocol's own resolution -- the same kind of
		# augmentation (a random translation), applied at 84. The overlay is unchanged.
		# Recorded in rlgen/registry.py and therefore in baselines/soda/README.md.
		from .rad import random_shift
		aug_x = x.clone()

		x = random_shift(x, pad=4)
		aug_x = random_shift(aug_x, pad=4)
		aug_x = augmentations.random_overlay(aug_x)

		soda_loss = self.compute_soda_loss(aug_x, x)
		
		self.soda_optimizer.zero_grad()
		soda_loss.backward()
		self.soda_optimizer.step()
		if L is not None:
			L.log('train/aux_loss', soda_loss, step)

		utils.soft_update_params(
			self.predictor, self.predictor_target,
			self.soda_tau
		)

	def update(self, replay_buffer, L, step):
		obs, action, reward, next_obs, not_done = replay_buffer.sample()

		self.update_critic(obs, action, reward, next_obs, not_done, L, step)

		if step % self.actor_update_freq == 0:
			self.update_actor_and_alpha(obs, L, step)

		if step % self.critic_target_update_freq == 0:
			self.soft_update_critic_target()

		if step % self.aux_update_freq == 0:
			self.update_soda(replay_buffer, L, step)
