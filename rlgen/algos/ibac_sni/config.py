"""IBAC-SNI's hyperparameters, each carrying its source (`porting-directive.md` §2).

Source tags:
  [CR]   `ext/IBAC-SNI/coinrun/coinrun/{config,ppo2,policies}.py` + that repo's `README.md`
         headline run commands. The authors' own code and their own reproduction commands.
  [TR]   `ext/IBAC-SNI/torch_rl/{bottleneck,model}.py` — the authors' own PyTorch path.
  [BASE] `joonleesky/train-procgen-pytorch` @ `1678e4a`, the PPO host this baseline runs in.
         Vendored at `_upstream_1678e4a/`.
  [DZ]   `~/Downloads/IBAC_SNI_torch/.../hyperparams/procgen/config.yml`, the `easy-ibac` block.
         **Wiring only** — DZ's port is a Construction, not a transcription
         (`_upstream_1678e4a/PROVENANCE.md`), so it settles key *names*, never semantics.
  [RLV]  `configs/vigen.yaml`'s `ibac_sni:` block — this project's launch-time overrides.
  [CA]   Continuous-adaptation reasoning that applies identically to every Gaussian-headed
         on-policy baseline in this project, so it is set the same way in all four.
  [OURS] Not in any source; chosen here, with the reason stated.

**Rewritten 2026-08-16.** The previous version sourced its IBAC-specific values `[DZ]` — i.e.
from a third party's re-derivation — while the authors' own release sat unread in `ext/IBAC-SNI`.
Four values changed as a result; each is marked **CHANGED** below with what it was.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Config:
    # ---- PPO core: the host's own values, which coincide with CoinRun's ---------------------
    lr: float = 5.0e-4                   # [CR] config.py:100-106 `lr=5e-4`, never overridden by
                                         # any headline README command. [DZ]'s `easy-ibac` block
                                         # independently sets `learning_rate: 0.0005`, and the
                                         # [BASE] `easy-200` block likewise. Three sources agree.
                                         # **CHANGED** from 2.5e-4, which was `agents/ppo.py`'s
                                         # constructor default — a value no config block uses.
    linear_lr_decay: bool = True         # [BASE] `agents/ppo.py::train` calls `adjust_lr` every
                                         # update; `misc_util.py:33-37` is `lr*(1 - t/max_t)`
    clip_param: float = 0.2              # [CR] `train_agent.py:42-53` hardcodes `cliprange=f*0.2`
    max_grad_norm: float = 0.5           # [BASE]/[DZ] `grad_clip_norm: 0.5`
    value_loss_coef: float = 0.5         # [BASE]/[DZ] `value_coef: 0.5`
    entropy_coef: float = 0.0            # [CA] the reference's own is 0.01, tuned for a 1-D
                                         # Categorical's entropy; it does not transfer to a 7-D
                                         # diagonal Gaussian's SUMMED entropy, which is unbounded
                                         # above. Set identically in `idaac`, `ppg` and `ctrl`
                                         # (checked directly, all four are 0.0) — changing it here
                                         # alone would confound the very comparison this project
                                         # exists to make.
                                         # **CONSEQUENCE, declared not buried:** at 0.0 the
                                         # entropy term drops out of the loss, so SNI's
                                         # entropy-mixing half (`ppo2.py:106-107`) is inert and
                                         # only the policy-gradient mixing is live. See
                                         # `docs/FAITHFULNESS.md`.
    epochs_policy: int = 3               # [CR] `config.py` `ppoeps=3`; [BASE]/[DZ] `epoch: 3`
    num_mini_batch: int = 8              # [CR] `nmb=8`; [BASE]/[DZ] `mini_batch_per_epoch: 8`.
                                         # **CHANGED** from 32, which was `[OURS]` and matched no
                                         # source — all three references say 8.
    grad_accum_steps: int = 1            # [OURS] the host accumulates
                                         # `batch_size / mini_batch_size` minibatches before
                                         # stepping (`agents_ppo.py:65-69`). At this project's
                                         # scale (`num_steps=2048`, ONE env) one minibatch already
                                         # fits, so the ratio is 1. Stated rather than inherited.
    normalize_adv: bool = True           # [BASE]/[DZ] `normalize_adv: True`

    # ---- encoder ----------------------------------------------------------------------------
    hidden_dim: int = 256                # [BASE] `ImpalaModel.fc` is `out_features=256`
    image_size: int = 84                 # [OURS] this project's target; see `model.py` edit E1

    # ---- the information bottleneck ---------------------------------------------------------
    ib_dim: int = 256                    # [CR] `policies.py:57` `tf.layers.dense(out, 256*2)`
                                         # split in half -> a 256-d latent. ([TR] uses 64, for
                                         # MiniGrid; CoinRun is the procedural-level setting this
                                         # host matches.)
    vib_beta: float = 1.0e-4             # [CR] README headline runs: `--beta 0.0001`. [RLV] sets
                                         # the same. Note the unit — see `scale_offset` below and
                                         # `policy.py::info_loss_bits`: the reference's KL is in
                                         # BITS, so this beta only means what the paper meant if
                                         # the KL is divided by ln 2.
    scale_offset: float = -5.0           # [CR] `policies.py:58`
                                         # `NormalWithSoftplusScale(mu, rho - 5.0)` — std starts
                                         # at ~softplus(-5) = 0.0067, i.e. near-deterministic.
                                         # **CHANGED**: the discarded module used
                                         # `exp(clamp(log_sigma, -10, 2))`, which starts at std=1
                                         # (~150x noisier at init) and has a zero-gradient plateau
                                         # that softplus does not. Neither first-party path clamps.
    nr_samples: int = 12                 # [CR] README headline runs: `--nr-samples 12`
                                         # (`config.py:53-54` defaults to 1; the paper's runs
                                         # override it). Cheap here: the CNN and the bottleneck
                                         # each run once and only the two small heads see 12x
                                         # (`policies.py:72-76`). **CHANGED** from an implicit 1.
    policy_head_init_scale: float = 1.0  # [CR] `policies.py:140`
                                         # `_matching_fc(h, 'pi', ..., init_scale=1.0)` wins under
                                         # `reuse=tf.AUTO_REUSE` over the later `0.01` at `:164`,
                                         # because `train_model` is built first (`ppo2.py:63`).
                                         # Recorded with both readings in `docs/REGISTER.md`:
                                         # possibly deliberate, possibly an AUTO_REUSE artefact —
                                         # what the code does is not in doubt.
    l2_weight: float = 1.0e-4            # [CR] every headline README run passes `--l2 0.0001`
                                         # (`config.py:133-134` defaults to 0.0). The term is
                                         # `sum_w ||w||^2 / 2` over non-bias params
                                         # (`ppo2.py:116,128`), added to the loss at `:153`.
                                         # **NEW** — the discarded module had no L2 term at all.
    sni: bool = True                     # [CR] `--sni`; [RLV]
    init_log_std: float = -1.0           # [CA] baselines' `DiagGaussianPdType.pdfromlatent`,
                                         # which `make_pdtype` (`policies.py:123`) would reach for
                                         # a Box space, uses `zeros_initializer()` -> std = 1.0.
                                         # This project uses -1.0 in ALL FOUR on-policy baselines
                                         # (checked directly) because std=1 on robosuite's [-1,1]
                                         # action box saturates the clip at initialisation. A
                                         # deliberate, uniform deviation from the reference:
                                         # uniform means it lands as a systematic offset on every
                                         # baseline rather than selectively on this one
                                         # (`docs/STEP-ZERO.md` gate 3).

    # ---- reward normalization (`docs/REGISTER.md`, 2026-08-14; unchanged, already verified) --
    normalize_reward: bool = True        # [BASE] `train.py:77` `hyperparameters.get(
                                         # 'normalize_rew', True)`; `config.yml` sets it True in
                                         # every block. `common/storage.py:110-114` separately
                                         # reads a raw `env_reward` stashed into `infos`
                                         # (`procgen_wrappers.py:327`) for reporting — the
                                         # reference's own train/measurement split.
    gamma: float = 0.99                  # [RLV] `configs/vigen.yaml`. Coincides with, but is not
                                         # derived from, `VecNormalize`'s own default.
                                         # ([CR]'s own gamma is 0.999; [RLV] overrides for this
                                         # project's 500-step horizon.)
    reward_clip: float = 10.0            # [BASE] `procgen_wrappers.py:312` `cliprew` default

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}
