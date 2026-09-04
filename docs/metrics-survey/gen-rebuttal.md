# Exhaustive Metric Inventory: `gen-rebuttal`

This document provides a complete, exhaustive inventory of every metric computed, logged, plotted, evaluated, or defined across the codebase and documentation of `/Users/a2mogus/build-projs/ccm-intro/projects/gen-rebuttal` (including the IDAAC port in `vigen_idaac`, the ALDA/QLAE port in `vigen_alda`, RL-ViGen baselines in `algos/`, evaluation protocols, diagnostic probes in `probes/`, and markdown specifications).

---

## 1. Complete Metric Inventory

### 1.1 Environment & Rollout Health Diagnostics (`vigen_idaac/metrics.py`, `vigen_idaac/train.py`, `vigen_idaac/envs.py`)

#### `obs/mean`
- **Definition**: `float(o.mean())` where `o = obs_u8.float()`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:27`
- **Question Answered**: Baseline tracking of raw pixel observation magnitude in range $[0, 255]$.
- **Algorithm Family**: Any
- **Caveat**: Informational baseline only; cannot detect dark rendering if offset by bright pixels.

#### `obs/std`
- **Definition**: `float(o.std())` where `o = obs_u8.float()`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:27`
- **Question Answered**: E2 detector: black or degenerate render detection (alarm threshold: abort if $< 1.0$).
- **Algorithm Family**: Any
- **Caveat**: Critical invariant; never downgraded during initial warmup updates.

#### `obs/frac_zero`
- **Definition**: `float((obs_u8 == 0).float().mean())`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:28`
- **Question Answered**: E2 detector: fraction of all-zero pixels in observation batch (alarm threshold: abort if $> 0.95$).
- **Algorithm Family**: Any
- **Caveat**: High fraction indicates blank/black render pipeline failure; never downgraded during warmup.

#### `obs/interframe_absdiff`
- **Definition**: `float((frames[:, 1:] - frames[:, :-1]).abs().mean())` where `frames = o.view(o.shape[0], C // 3, 3, *o.shape[2:])` (for $C \ge 6$ and $C \pmod 3 == 0$)
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:32`
- **Question Answered**: E3 detector: stale frame stack detection (alarm threshold: warn if $< 10^{-6}$).
- **Algorithm Family**: Any with frame-stacked visual inputs
- **Caveat**: Only computed when channel dimension $C \ge 6$; detects if frame stack buffer stopped advancing or was re-filled with identical static frames.

#### `act/abs_mean`
- **Definition**: `float(a.abs().mean())` where `a = actions.float()`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:39`
- **Question Answered**: Mean absolute magnitude of actions sent to the environment.
- **Algorithm Family**: Any (continuous action spaces)
- **Caveat**: Informational tracking of policy action scale.

#### `act/saturation_frac`
- **Definition**: `float((a.abs() > 0.99).float().mean())` where `a = actions.float()`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:40`
- **Question Answered**: E4 / S1 detector: fraction of actions saturating the action box boundary $[-1, 1]$ (alarm threshold: warn if $> 0.5$).
- **Algorithm Family**: Any (continuous action spaces)
- **Caveat**: High saturation indicates either unbounded network head initialization or policy collapse into a constant bang-bang controller.

#### `act/std_across_batch`
- **Definition**: `float(a.std(dim=0).mean())` where `a = actions.float()`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:41`
- **Question Answered**: S1 detector: action diversity across parallel rollout workers; catches constant/degenerate policy collapse.
- **Algorithm Family**: Any (continuous action spaces)
- **Caveat**: Computed in `metrics.action_health`, but omitted from `EXPECTED_KEYS` and `analyze.py`.

#### `env/steps_per_worker_min`
- **Definition**: `float(s.min()) if s.numel() else 0.0` where `s = torch.as_tensor(steps_delta).float()`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:70`
- **Question Answered**: Minimum environment steps taken by any vectorized worker in the rollout.
- **Algorithm Family**: Any (vectorized environments)
- **Caveat**: Informational only, NOT a detector. Structurally incapable of detecting a stalled worker in a lock-step synchronous `SubprocVecEnv` because all workers advance together or the pipe raises.

#### `env/episodes_per_worker_min`
- **Definition**: `float(e.min()) if e.numel() else 0.0` where `e = torch.as_tensor(episodes_delta).float()`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:71`
- **Question Answered**: Minimum completed episodes completed by any worker in the rollout.
- **Algorithm Family**: Any (vectorized environments)
- **Caveat**: Informational only.

#### `env/episode_imbalance`
- **Definition**: `float((e.max() - e.min()) / e.max())` where `e = torch.as_tensor(episodes_delta).float()` (when `float(e.max()) > 0`)
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:80`
- **Question Answered**: Ratio of worker episode completion spread to max completed episodes over per-rollout deltas.
- **Algorithm Family**: Any (vectorized environments)
- **Caveat**: **Explicitly documented as misleading and unfireable once workers are phase-staggered (FINDINGS F8, metrics.py:45-80, analyze.py:88-90)**: in any single rollout, some workers finish an episode and others do not (max=1, min=0), causing the ratio to saturate to 1.0 on every row of healthy runs while being unable to distinguish dead workers. Replaced by `env/episode_spread_cum`.

#### `env/episode_spread_cum`
- **Definition**: `float(c.max() - c.min())` where `c = torch.as_tensor(episodes_cum).float()`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:89`
- **Question Answered**: E6 detector: difference between maximum and minimum cumulative episodes completed across workers (threshold: warn if $> 1.5$).
- **Algorithm Family**: Any (vectorized environments)
- **Caveat**: By construction, for any set of worker phase offsets, healthy cumulative counts differ by at most 1. Unbounded divergence indicates a dead/stalled worker.

#### `env/distinct_init_obs_frac`
- **Definition**: `(len(set(init_obs_hashes)) / n) if n else 1.0` where `n = len(init_obs_hashes)`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:97`
- **Question Answered**: E7 detector: fraction of unique initial observation hashes across parallel environment workers (alarm threshold: warn if $< 1.0$).
- **Algorithm Family**: Any (vectorized environments)
- **Caveat**: Shared initial observations indicate duplicate environment seeds, which silently collapses $N$ parallel workers to 1.

---

### 1.2 Policy, Value & Representation Diagnostics (IDAAC / PPO / DAAC)

#### `v/explained_variance`
- **Definition**: `float(1.0 - (r - v).var() / var)` where `r = returns.flatten().float(), v = values.flatten().float(), var = r.var()` (returns `0.0` if `var < 1e-12`)
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:101-108`, `vigen-idaac/vigen_idaac/algo.py:252`
- **Question Answered**: O3 detector: proportion of return variance explained by value function predictions (1 - Var[R - V]/Var[R]). Perfect predictor = 1.0, mean predictor = 0.0, worse than mean < 0.0.
- **Algorithm Family**: On-policy / actor-critic (PPO, DAAC, IDAAC)
- **Caveat**: Highly erratic during first updates (warmup needed). If explained variance never reaches $> 0.0$ in the second half of training, the value network is not learning.

#### `pi/approx_kl`
- **Definition**: `float(((ratio - 1) - logratio).mean())` where `logratio = lp - old_lp`, `ratio = logratio.exp()`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:113`, `vigen-idaac/vigen_idaac/algo.py:98-99, 164-165`
- **Question Answered**: O2 detector: Schulman's $k_3$ unbiased, non-negative, minimum-variance estimator of $D_{KL}(\pi_{\text{old}} \| \pi_{\text{new}})$.
- **Algorithm Family**: On-policy (PPO, DAAC, IDAAC)
- **Caveat**: Strictly non-negative. Used for epoch-level KL early stopping when update mean exceeds `target_kl`.

#### `pi/clipfrac`
- **Definition**: `float(((ratio - 1).abs() > clip_param).float().mean())`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:114`, `vigen-idaac/vigen_idaac/algo.py:164-166`
- **Question Answered**: Fraction of rollout transitions where importance sampling ratio is truncated by PPO clipping boundary $[1-\epsilon, 1+\epsilon]$.
- **Algorithm Family**: On-policy (PPO, DAAC, IDAAC)
- **Caveat**: Diagnostic of trust-region boundary pressure.

#### `pi/ratio_max`
- **Definition**: `float(ratio.max())` where `ratio = (lp - old_lp).exp()`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:115`, `vigen-idaac/vigen_idaac/algo.py:167, 230-235`
- **Question Answered**: Peak importance sampling probability ratio across all minibatches in an update.
- **Algorithm Family**: On-policy (PPO, DAAC, IDAAC)
- **Caveat**: Stored as max across minibatches, not an average.

#### `grad_norm/{name}` (`policy_enc`, `dist_head`, `aux_head`, `value`, `disc`)
- **Definition**: `math.sqrt(sum(p.grad.detach().pow(2).sum() for p in mod.parameters() if p.grad is not None))`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:128`, `vigen-idaac/vigen_idaac/algo.py:145-146, 158, 213`
- **Question Answered**: O4 detector: per-module unclipped $L_2$ gradient norms.
- **Algorithm Family**: Modular actor-critic architectures
- **Caveat**: **Must be evaluated immediately after each module's own backward step and before clipping (algo.py:135-144)**. Evaluating globally after policy backward mislabels stale value gradients and discarded discriminator confusion gradients.

#### `mag/v_loss`
- **Definition**: `float(abs(v_loss))`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:140, 229`, `vigen-idaac/vigen_idaac/train.py:294`
- **Question Answered**: O9 detector: absolute magnitude of value loss (alarm threshold: abort if $> 10^6$).
- **Algorithm Family**: Actor-critic
- **Caveat**: Catches multi-order divergence (e.g. $10^{18}$ explosion) where losses remain finite.

#### `mag/adv_std_prenorm`
- **Definition**: `float(abs(adv_std_prenorm))`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:140, 230`, `vigen-idaac/vigen_idaac/train.py:295`
- **Question Answered**: O9 detector: magnitude of unnormalized advantage standard deviation (abort if $> 10^4$).
- **Algorithm Family**: Actor-critic
- **Caveat**: Detects advantage scale divergence.

#### `mag/ep_return_norm`
- **Definition**: `float(abs(float(storage.rewards.sum(0).mean())))`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:140, 231`, `vigen-idaac/vigen_idaac/train.py:296`
- **Question Answered**: O9 detector: magnitude of normalized return sum over rollout (abort if $> 10^5$).
- **Algorithm Family**: Actor-critic with normalized rewards
- **Caveat**: Detects runaway reward accumulation.

#### `mag/value_pred`
- **Definition**: `float(abs(float(storage.values[:-1].abs().max())))`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:140, 232`, `vigen-idaac/vigen_idaac/train.py:297`
- **Question Answered**: O9 detector: peak absolute value predicted by value network (abort if $> 10^5$).
- **Algorithm Family**: Actor-critic
- **Caveat**: Detects value function explosion.

#### `health/nonfinite`
- **Definition**: `float(sum(int((~torch.isfinite(t)).sum()) for t in tensors if t is not None and torch.is_tensor(t)))`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:143-149`, `vigen-idaac/vigen_idaac/algo.py:126, 192, 245`
- **Question Answered**: O5 detector: count of non-finite (NaN / Inf) elements across loss tensors.
- **Algorithm Family**: Any
- **Caveat**: When non-zero, `algo.py` immediately raises `NonFiniteLoss` before row logging, so logged values on completed updates are always 0.0.

#### `health/losses_all_finite`
- **Definition**: `1.0` (set when execution passes all loss computation blocks without raising)
- **File:Line**: `vigen-idaac/vigen_idaac/algo.py:246`
- **Question Answered**: Explicit indicator that all loss backward passes succeeded with finite values.
- **Algorithm Family**: Any
- **Caveat**: Constant 1.0 on completed updates.

#### `disc/acc`
- **Definition**: `float(((disc_logit > 0).float() == label).float().mean())`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:159`, `vigen-idaac/vigen_idaac/algo.py:162`
- **Question Answered**: O7 detector: order discriminator classification accuracy on trajectory pairs.
- **Algorithm Family**: Representation / invariant RL (IDAAC)
- **Caveat**: If accuracy $> 0.90$ in the second half of training, the discriminator has overwhelmed the encoder and the invariance objective is inert; healthy training hovers near chance ($0.50$).

#### `disc/logit_abs_mean`
- **Definition**: `float(disc_logit.abs().mean())`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:160`
- **Question Answered**: Average confidence magnitude of discriminator logits.
- **Algorithm Family**: Representation (IDAAC)
- **Caveat**: Computed in helper function, but not added to logging dict in `algo.py`.

#### `disc/enc_loss`
- **Definition**: `float(encoder_confusion_loss(disc_output))` where `encoder_confusion_loss(logits) = -0.5 * log_sigmoid(logits) - 0.5 * log_sigmoid(-logits)`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:161`, `vigen-idaac/vigen_idaac/algo.py:122-124`, `vigen-idaac/vigen_idaac/model.py:206-210`
- **Question Answered**: $L_E$ encoder confusion / invariance loss pushing discriminator to chance ($D=0.5$).
- **Algorithm Family**: Representation (IDAAC)
- **Caveat**: Theoretical minimum is $\log 2 \approx 0.6931$. If loss sits at $\log 2$ from step 0, discriminator is learning nothing.

#### `disc/enc_loss_minus_log2`
- **Definition**: `float(enc_loss - math.log(2.0))`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:162`
- **Question Answered**: Excess encoder confusion loss above theoretical chance floor.
- **Algorithm Family**: Representation (IDAAC)
- **Caveat**: Computed in helper, but omitted from `algo.py` logging accumulator.

#### `disc/loss`
- **Definition**: `float(F.binary_cross_entropy_with_logits(z, lbl).detach())`
- **File:Line**: `vigen-idaac/vigen_idaac/algo.py:154, 161`
- **Question Answered**: Binary cross-entropy loss for order discriminator optimization.
- **Algorithm Family**: Representation (IDAAC)
- **Caveat**: Trained strictly on detached encoder features.

#### `disc/pair_purity`
- **Definition**: `float((same_env & same_ep).float().mean())` where `same_env = ni == nj` and `same_ep = episode_id[ti, ni] == episode_id[tj, nj]`
- **File:Line**: `vigen-idaac/vigen_idaac/storage.py:156-164`, `vigen-idaac/vigen_idaac/algo.py:120`, `vigen-idaac/vigen_idaac/metrics.py:224`
- **Question Answered**: D4 detector: fraction of sampled order pairs drawn from the exact same environment worker and episode trajectory (abort if $< 1.0$).
- **Algorithm Family**: Representation (IDAAC)
- **Caveat**: Sampling across episode boundaries violates the mathematical foundation of IDAAC.

#### `adv_head/corr`
- **Definition**: Pearson correlation `float((p @ t) / d)` between advantage prediction `p = a_pred - a_pred.mean()` and target `t = adv_t - adv_t.mean()` where `d = p.norm() * t.norm()`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:165-172`, `vigen-idaac/vigen_idaac/algo.py:115`
- **Question Answered**: O8 detector: tracking correlation between predicted advantage head output and normalized GAE advantage target.
- **Algorithm Family**: Actor-critic with auxiliary advantage head (DAAC, IDAAC)
- **Caveat**: Catches miswired advantage heads (e.g. incorrect action scale or discrete one-hot paths left in continuous domains) where MSE falls while correlation stays at zero.

#### `adv/loss`
- **Definition**: `float(F.mse_loss(a_pred, adv_t).detach())`
- **File:Line**: `vigen-idaac/vigen_idaac/algo.py:112-114`
- **Question Answered**: Mean squared error loss for auxiliary advantage head regression.
- **Algorithm Family**: DAAC, IDAAC
- **Caveat**: Regresses on whole-rollout normalized advantages.

#### `adv/std_prenorm`
- **Definition**: `float(adv.std())` where `adv = returns[:-1] - values[:-1]`
- **File:Line**: `vigen-idaac/vigen_idaac/storage.py:105-106`, `vigen-idaac/vigen_idaac/algo.py:248`, `vigen-idaac/vigen_idaac/metrics.py:223`
- **Question Answered**: D3 detector: standard deviation of raw pre-normalization GAE advantages (abort if $< 10^{-6}$).
- **Algorithm Family**: On-policy actor-critic
- **Caveat**: Standard deviation $< 10^{-6}$ indicates value function predicts constant or returns collapsed.

#### `pi/pg_loss`
- **Definition**: `float((-torch.min(ratio * adv_t, torch.clamp(ratio, 1 - clip_param, 1 + clip_param) * adv_t).mean()).detach())`
- **File:Line**: `vigen-idaac/vigen_idaac/algo.py:102, 168`
- **Question Answered**: PPO clipped surrogate policy gradient loss.
- **Algorithm Family**: On-policy (PPO, DAAC, IDAAC)
- **Caveat**: Minibatch average.

#### `pi/entropy`
- **Definition**: `float(ent.mean().detach())` where `ent` is closed-form diagonal Gaussian entropy
- **File:Line**: `vigen-idaac/vigen_idaac/algo.py:97, 103, 169`
- **Question Answered**: Action distribution exploration entropy.
- **Algorithm Family**: Continuous policy
- **Caveat**: Summed over action dimensions.

#### `pi/log_std_mean`
- **Definition**: `float(self.policy.dist_head.log_std.mean())`
- **File:Line**: `vigen-idaac/vigen_idaac/algo.py:249`, `vigen-idaac/vigen_idaac/metrics.py:240-241`
- **Question Answered**: O1 detector: mean Gaussian log standard deviation (warn if $< -3.0$ [collapse] or $> 1.0$ [blow-up]).
- **Algorithm Family**: Continuous policy
- **Caveat**: Policy collapse makes policy prematurely deterministic and stops exploration.

#### `pi/log_std_min`, `pi/log_std_max`
- **Definition**: `float(self.policy.dist_head.log_std.min())`, `float(self.policy.dist_head.log_std.max())`
- **File:Line**: `vigen-idaac/vigen_idaac/algo.py:250-251`
- **Question Answered**: Minimum and maximum log standard deviation across individual action dimensions.
- **Algorithm Family**: Continuous policy
- **Caveat**: Detects dimensional collapse hidden by mean.

#### `pi/epochs_ran`
- **Definition**: `float(epochs_ran)`
- **File:Line**: `vigen-idaac/vigen_idaac/algo.py:174, 182, 230-235`
- **Question Answered**: Number of PPO policy optimization epochs executed before early exit.
- **Algorithm Family**: On-policy PPO
- **Caveat**: Integer per-update fact, not divided by minibatch count.

#### `pi/kl_early_stopped`
- **Definition**: `float(stopped_early)` (1.0 if epoch KL exceeded `target_kl`, else 0.0)
- **File:Line**: `vigen-idaac/vigen_idaac/algo.py:179, 183, 230-235`
- **Question Answered**: Binary flag indicating whether policy optimization was truncated early to preserve the trust region.
- **Algorithm Family**: On-policy PPO
- **Caveat**: Checked per epoch, not per minibatch.

#### `v/loss`
- **Definition**: `(acc["v/loss"] / n_val) if n_val else float("nan")` where `vl = 0.5 * (ret - v).pow(2).mean()` (or clipped loss)
- **File:Line**: `vigen-idaac/vigen_idaac/algo.py:107-109, 191, 216, 238`
- **Question Answered**: Value function regression loss against empirical GAE return targets.
- **Algorithm Family**: Actor-critic
- **Caveat**: **Must be NaN (not 0.0) when value network does not train on that update ($N_\pi > 1$)**; averaging 0.0 into curves falsely dilutes loss.

#### `v/value_updated`
- **Definition**: `float(n_val > 0)`
- **File:Line**: `vigen-idaac/vigen_idaac/algo.py:247`
- **Question Answered**: Binary flag indicating whether value parameters were updated on this step.
- **Algorithm Family**: DAAC, IDAAC (separate value schedule $N_\pi$)
- **Caveat**: Enables downstream consumers to filter active value updates.

#### `v/return_std`
- **Definition**: `float(storage.returns[:-1].std())`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:288`
- **Question Answered**: Standard deviation of GAE returns in rollout.
- **Algorithm Family**: On-policy actor-critic
- **Caveat**: Required for exact mathematical advantage consistency check.

#### `diag/corr_V_t`
- **Definition**: `_pearson(self.values[:-1].reshape(-1).float(), self.ep_step.reshape(-1).float())`
- **File:Line**: `vigen-idaac/vigen_idaac/storage.py:175-181`, `vigen-idaac/vigen_idaac/algo.py:253`
- **Question Answered**: IDAAC scientific mechanism metric: Pearson correlation between value predictions $V(s_t)$ and episode step $t$.
- **Algorithm Family**: Representation / actor-critic (IDAAC / DAAC / PPO)
- **Caveat**: Tests whether value network learns linear time-to-go memorization on fixed-horizon tasks with no explicit time feature.

#### `diag/corr_A_t`
- **Definition**: `storage.advantage_time_correlation(torch.cat(preds))` = `_pearson(adv_pred_flat.reshape(-1).float(), self.ep_step.reshape(-1).float())`
- **File:Line**: `vigen-idaac/vigen_idaac/algo.py:254, 258-270`, `vigen-idaac/vigen_idaac/storage.py:166-174`
- **Question Answered**: IDAAC scientific mechanism metric: Pearson correlation between predicted advantage $\hat{A}(s_t, a_t)$ and episode step $t$.
- **Algorithm Family**: Representation / actor-critic (IDAAC / DAAC)
- **Caveat**: IDAAC claims $\text{corr}(A,t) \approx 0$ while $\text{corr}(V,t) \gg 0$. Computed only on diagnostic updates.

#### `diag/is_diag_update`
- **Definition**: `float(diag)` (1.0 if update is diagnostic update, else 0.0)
- **File:Line**: `vigen-idaac/vigen_idaac/algo.py:255`
- **Question Answered**: Binary indicator for diagnostic metric computation.
- **Algorithm Family**: Any
- **Caveat**: Binary flag.

---

### 1.3 Cross-Field Invariant & Theoretical Prediction Metrics

#### `consistency/trunc_per_end`
- **Definition**: `float(tr) / max(float(ends), 1.0)` where `tr = row.get("ep/truncated")`, `ends = row.get("ep/ends_this_rollout")`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:187-190, 234`
- **Question Answered**: Consistency detector: ratio of truncations to episode completions (abort if $> 1.5$).
- **Algorithm Family**: Any
- **Caveat**: In robosuite Door/Lift every episode end is a truncation; caught a 500x bug where truncation was set true on every step.

#### `consistency/expected_ends`
- **Definition**: `float(steps) / float(ep_len)` where `steps = row.get("rollout/frames")`, `ep_len = row.get("ep/length")`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:191-193`
- **Question Answered**: Theoretical expected number of episode ends in rollout based on rollout length and mean episode duration.
- **Algorithm Family**: Any
- **Caveat**: Informational cross-check against actual ends.

#### `consistency/adv_identity_relerr`
- **Definition**: `abs(float(a) - pred) / pred` where `pred = rs * math.sqrt(max(0.0, 1.0 - ev))`, `a = adv/std_prenorm`, `rs = v/return_std`, `ev = v/explained_variance`
- **File:Line**: `vigen-idaac/vigen_idaac/metrics.py:206-212, 238`
- **Question Answered**: Exact mathematical identity test: $\sigma_{\text{adv\_prenorm}} \equiv \sigma_{\text{return}} \sqrt{1 - EV}$ (abort if relative error $> 10^{-3}$).
- **Algorithm Family**: Actor-critic
- **Caveat**: Exact mathematical identity holding to floating point precision ($10^{-7}$). Catches stale value buffers, mismatched evaluation slices, or swapped networks.

#### `init/pi_entropy`
- **Definition**: `float(act_dim * 0.5 * math.log(2 * math.pi * math.e) + log_std.sum())`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:110`, `vigen-idaac/vigen_idaac/predictions.py:93`
- **Question Answered**: Theoretical vs empirical policy entropy at initialization prior to update 0.
- **Algorithm Family**: Continuous policy
- **Caveat**: Gated at startup: if empirical entropy deviates from derivation, training aborts before spending GPU hours.

#### `init/pi_log_std_mean`
- **Definition**: `float(self.policy.dist_head.log_std.mean())` at initialization
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:113`, `vigen-idaac/vigen_idaac/predictions.py:94`
- **Question Answered**: Verification of initial log standard deviation matching `cfg.init_log_std`.
- **Algorithm Family**: Continuous policy
- **Caveat**: Checked at update 0.

---

### 1.4 Training Progress & Performance Metrics

#### `ep/return_raw`
- **Definition**: `float(np.mean(list(ep_returns_raw)[-50:])) if ep_returns_raw else float("nan")` (or 0.0)
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:274`, `vigen-idaac/vigen_alda/train.py:514`
- **Question Answered**: Trailing mean (window 50) of unnormalized, raw environment episode returns during training.
- **Algorithm Family**: Any
- **Caveat**: Lags policy changes due to trailing window; on Lift bimodal returns distort mean. Must never be confused with `rollout/reward_norm_sum`.

#### `rollout/reward_norm_sum`
- **Definition**: `float(storage.rewards.sum(0).mean())`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:278`
- **Question Answered**: Sum of normalized, value-bootstrapped rewards over rollout steps.
- **Algorithm Family**: Any with reward normalization
- **Caveat**: **Explicitly cautioned (FINDINGS R5, train.py:275-277)**: rollouts are `num_steps` (256) long whereas episodes are `horizon` (500) long; must NOT be compared against `ep/return_raw`.

#### `ep/length`
- **Definition**: `float(np.mean(list(ep_lengths)[-50:])) if ep_lengths else float("nan")`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:279`, `vigen-idaac/vigen_alda/train.py:515`
- **Question Answered**: Trailing mean episode length in environment steps.
- **Algorithm Family**: Any
- **Caveat**: On fixed-horizon tasks with no early termination, must equal `horizon / action_repeat` (e.g. 500.0). Deviation indicates environment bug.

#### `ep/warmup_skipped`
- **Definition**: `int(n_warmup_skipped)`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:282`
- **Question Answered**: Count of initial worker episode fragments discarded during warmup / phase staggering.
- **Algorithm Family**: Vectorized environments
- **Caveat**: Should reach `num_envs` and freeze; continuing increase means real episodes are being discarded.

#### `ep/count`
- **Definition**: `int(venv.book.episodes_per_worker.sum())` / `len(ep_returns)`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:283`, `vigen-idaac/vigen_alda/train.py:516`
- **Question Answered**: Total cumulative episodes completed during training.
- **Algorithm Family**: Any
- **Caveat**: Tracks cumulative training experience count.

#### `ep/truncated`
- **Definition**: `storage.n_truncated` = `int(truncated.sum())`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:284`, `vigen-idaac/vigen_idaac/storage.py:76`
- **Question Answered**: Count of episode truncations in rollout buffer.
- **Algorithm Family**: Any
- **Caveat**: Fixed horizon environments should show 100% of terminations as truncations.

#### `ep/terminated`
- **Definition**: `storage.n_terminated` = `int((done.bool() & ~truncated.bool()).sum())`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:284`, `vigen-idaac/vigen_idaac/storage.py:77`
- **Question Answered**: Count of true task terminations (success/failure before horizon).
- **Algorithm Family**: Any
- **Caveat**: Must be 0 for Door/Lift (which have no early termination); positive value indicates early termination bug.

#### `ep/ends_this_rollout`
- **Definition**: `int(de.sum())` where `de` is episode end delta tensor
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:285`
- **Question Answered**: Number of episodes completed across all workers in current rollout.
- **Algorithm Family**: Vectorized environments
- **Caveat**: Used in `consistency/trunc_per_end`.

#### `rollout/frames`
- **Definition**: `cfg.rollout_size` ($T \times N$)
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:285`
- **Question Answered**: Total environment steps collected per rollout.
- **Algorithm Family**: On-policy
- **Caveat**: Static per config.

#### `rew/raw_mean`
- **Definition**: `float(storage.rewards_raw.mean())`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:286`
- **Question Answered**: Mean step reward before normalization across rollout transitions.
- **Algorithm Family**: Any
- **Caveat**: Unscaled step reward.

#### `rew/raw_max`
- **Definition**: `float(storage.rewards_raw.max())`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:287`
- **Question Answered**: Maximum single-step raw reward observed in rollout.
- **Algorithm Family**: Any
- **Caveat**: High values indicate reward spikes.

#### `update_idx`
- **Definition**: `int(update)`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:260`
- **Question Answered**: Sequential optimization update counter.
- **Algorithm Family**: Any
- **Caveat**: Invariant: `frames == (update + 1) * rollout_size * action_repeat`. Discontinuities indicate lost logging rows (I4 check).

#### `frames`
- **Definition**: `(update + 1) * cfg.rollout_size * cfg.action_repeat` / total environment frames
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:260`
- **Question Answered**: Environment interaction frame counter (accounting for action repeat).
- **Algorithm Family**: Any
- **Caveat**: Canonical x-axis for sample efficiency comparisons.

#### `opt/lr`
- **Definition**: `float(lr)`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:260`
- **Question Answered**: O6 detector: current optimizer learning rate.
- **Algorithm Family**: Any
- **Caveat**: Must decay monotonically if linear decay is enabled.

#### `time/fps`
- **Definition**: `round(cfg.rollout_size * cfg.action_repeat / max(collect_s + update_s, 1e-9), 1)`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:267-268`, `vigen-idaac/vigen_alda/train.py:517`
- **Question Answered**: True end-to-end throughput (collection + learner) in environment frames per second.
- **Algorithm Family**: Any
- **Caveat**: **Explicitly corrected from collection-only fps (FINDINGS R23, train.py:261-266)**: collection-only fps overstated throughput by 2.09x and produced 2x wrong ETAs.

#### `time/collect_fps`
- **Definition**: `round(cfg.rollout_size * cfg.action_repeat / max(collect_s, 1e-9), 1)`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:269-270`
- **Question Answered**: Environment rollout collection throughput isolated from learner backward/update time.
- **Algorithm Family**: Any
- **Caveat**: Does not measure optimization overhead.

#### `time/collect_s`
- **Definition**: `round(collect_s, 2)`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:271`
- **Question Answered**: Wall-clock seconds spent in environment stepping per update cycle.
- **Algorithm Family**: Any
- **Caveat**: Used for learner fraction calculation.

#### `time/update_s`
- **Definition**: `round(update_s, 2)`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:272`
- **Question Answered**: Wall-clock seconds spent in neural network forward/backward/optimizer steps.
- **Algorithm Family**: Any
- **Caveat**: Direct profiling of learner computation.

#### `time/learner_frac`
- **Definition**: `round(update_s / max(collect_s + update_s, 1e-9), 3)`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:273`
- **Question Answered**: Fraction of total training wall-clock time consumed by gradient updates vs environment collection.
- **Algorithm Family**: Any
- **Caveat**: Tracks compute bottleneck (GPU learner vs CPU/OpenGL rendering).

#### `time/eta_hours`
- **Definition**: `(cfg.total_frames - frames) / max(1e-9, fps) / 3600.0`
- **File:Line**: `vigen-idaac/vigen_alda/train.py:518`
- **Question Answered**: Estimated remaining job training time in hours.
- **Algorithm Family**: Any
- **Caveat**: Accurate only when using end-to-end FPS.

#### `health/alarms`
- **Definition**: `len(fired)` from `M.check_alarms(row)` / `metrics.detect(row)`
- **File:Line**: `vigen-idaac/vigen_idaac/train.py:320`, `vigen-idaac/vigen_alda/train.py:536`
- **Question Answered**: Count of active health check threshold violations on the current update.
- **Algorithm Family**: Any
- **Caveat**: Any abort-level alarm terminates the run.

#### `wall_seconds`
- **Definition**: `round(time.time() - self._t0, 1)`
- **File:Line**: `vigen-idaac/vigen_idaac/logging_.py:165`
- **Question Answered**: Elapsed wall-clock time from run initialization.
- **Algorithm Family**: Any
- **Caveat**: Inserted automatically into every logged CSV row.

---

### 1.5 ALDA & SAC Representation Metrics (`vigen_alda/agent.py`, `vigen_alda/buffer.py`, `vigen_alda/metrics.py`)

#### `actor/alpha`
- **Definition**: `float(self.alpha.detach())` where `alpha = log_alpha.exp()`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:431`, `vigen-idaac/vigen_alda/metrics.py:58-65`
- **Question Answered**: SAC entropy temperature coefficient $\alpha$.
- **Algorithm Family**: Off-policy actor-critic (SAC / ALDA)
- **Caveat**: Abort if $> 50.0$ (entropy dominates return, policy becomes random); warn if $< 10^{-5}$ (alpha collapses, policy becomes prematurely deterministic).

#### `actor/alpha_loss`
- **Definition**: `float(alpha_loss.detach())` where `alpha_loss = (-self.log_alpha * (log_pi + self.target_entropy).detach()).mean()`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:423, 432`
- **Question Answered**: Loss optimizing entropy temperature $\alpha$ toward `target_entropy = -act_dim`.
- **Algorithm Family**: Off-policy actor-critic (SAC)
- **Caveat**: Auto-tuning loss.

#### `actor/loss`
- **Definition**: `float((self.alpha.detach() * log_pi - min(q1, q2)).mean().detach())`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:417, 430`
- **Question Answered**: SAC policy objective (entropy-augmented policy loss).
- **Algorithm Family**: Off-policy actor-critic
- **Caveat**: Evaluated with reparameterized actions.

#### `actor/entropy_gauss`
- **Definition**: `float(gauss_entropy.detach().mean())` where `gauss_entropy = 0.5 * (1.0 + math.log(2.0 * math.pi)) * act_dim + log_std.sum(-1)`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:410, 433`
- **Question Answered**: Closed-form entropy of unconstrained base Gaussian before Tanh squash.
- **Algorithm Family**: Continuous policy
- **Caveat**: Pre-squash entropy.

#### `actor/neg_log_pi`
- **Definition**: `float((-log_pi).detach().mean())`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:411, 434`, `vigen-idaac/vigen_alda/metrics.py:142-147`
- **Question Answered**: Empirical entropy of Tanh-squashed policy action distribution ($-\mathbb{E}[\log \pi(a|s)]$).
- **Algorithm Family**: Continuous policy (SAC)
- **Caveat**: Warn if $< \text{target\_entropy} - 4.0$ (entropy collapse indicating temperature controller is lagging behind policy collapse).

#### `actor/log_std`
- **Definition**: `float(log_std.detach().mean())`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:435`
- **Question Answered**: Mean log standard deviation of actor Gaussian head.
- **Algorithm Family**: Continuous policy
- **Caveat**: Bounded between `log_std_bounds` $[-5, 2]$.

#### `actor/std_min`
- **Definition**: `float(log_std.detach().exp().min())`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:448`
- **Question Answered**: Minimum standard deviation across action dimensions in current batch.
- **Algorithm Family**: Continuous policy
- **Caveat**: Identifies near-zero exploration in specific action joints.

#### `actor/mu_saturated_frac`
- **Definition**: `float((mu_t.abs() > 0.99).float().mean())` where `mu_t = torch.tanh(mu)`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:444`
- **Question Answered**: Fraction of deterministic mean action components saturating the action boundary $[-1, 1]$.
- **Algorithm Family**: Continuous policy (Tanh-Gaussian)
- **Caveat**: Diagnostic for mean action slamming into bounds.

#### `actor/mu_abs_mean`
- **Definition**: `float(mu_t.abs().mean())`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:445`
- **Question Answered**: Average absolute value of squashed policy mean action.
- **Algorithm Family**: Continuous policy
- **Caveat**: Tracks mean action magnitude.

#### `actor/pi_saturated_frac`
- **Definition**: `float((pi.detach().abs() > 0.99).float().mean())`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:446`
- **Question Answered**: Fraction of sampled actions saturating the action boundary $[-1, 1]$.
- **Algorithm Family**: Continuous policy
- **Caveat**: Diagnostic for exploration action saturation.

#### `critic/loss`
- **Definition**: `float(F.mse_loss(q1, target_q) + F.mse_loss(q2, target_q))`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:339, 357`
- **Question Answered**: Twin Q-critic Bellman regression loss against clipped double-Q target.
- **Algorithm Family**: Off-policy actor-critic (SAC)
- **Caveat**: Abort if $> 10^8$.

#### `critic/q1`, `critic/q2`
- **Definition**: `float(q1.detach().mean())`, `float(q2.detach().mean())`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:358-359`, `vigen-idaac/vigen_alda/metrics.py:31, 157-164`
- **Question Answered**: Mean predicted Q-value for critic 1 and critic 2.
- **Algorithm Family**: Off-policy actor-critic (SAC)
- **Caveat**: Abort if $|Q| > 10^5$. Warn on value overestimation if $Q_1 > 4.0 \times \text{return}$ after return improvements have plateaued.

#### `critic/target_q`
- **Definition**: `float(target_q.mean())` where `target_q = reward + not_done * gamma * (min(q1_target, q2_target) - alpha * log_pi_next)`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:335, 360`
- **Question Answered**: Mean TD target value for critic regression.
- **Algorithm Family**: Off-policy actor-critic (SAC)
- **Caveat**: Abort if $|target\_q| > 10^5$.

#### `critic/q_gap`
- **Definition**: `float((q1 - q2).detach().abs().mean())`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:361`, `vigen-idaac/vigen_alda/metrics.py:177-180`
- **Question Answered**: Mean absolute divergence between twin critics $|Q_1 - Q_2|$.
- **Algorithm Family**: Off-policy actor-critic (SAC)
- **Caveat**: Warn if $> 100.0$; decorrelation between twin critics usually precedes runaway critic divergence.

#### `critic/td_error`
- **Definition**: `float(td.mean())` where `td = 0.5 * (target_q - q1).detach().abs() + 0.5 * (target_q - q2).detach().abs()`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:364-366`
- **Question Answered**: Mean absolute Bellman temporal difference error.
- **Algorithm Family**: Off-policy actor-critic
- **Caveat**: Core objective error metric for value learning.

#### `critic/td_error_max`
- **Definition**: `float(td.max())`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:367`
- **Question Answered**: Maximum single-sample TD error in batch.
- **Algorithm Family**: Off-policy actor-critic
- **Caveat**: Detects outlier exploding transition targets before batch mean moves.

#### `critic/target_q_std`
- **Definition**: `float(target_q.std())`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:368`
- **Question Answered**: Standard deviation of target Q values across batch.
- **Algorithm Family**: Off-policy actor-critic
- **Caveat**: Zero target variance indicates value collapse.

#### `critic/q_over_ceiling`
- **Definition**: `float(q1.mean()) / q_ceiling` where `q_ceiling = (raw_max / (1.0 - gamma)) if gamma < 1.0 else float("inf")`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:382-388`
- **Question Answered**: Ratio of critic Q-value prediction to theoretical maximum infinite-horizon discounted return ceiling $\frac{R_{\max}}{1 - \gamma}$.
- **Algorithm Family**: Off-policy actor-critic
- **Caveat**: $> 1.0$ indicates physically impossible overestimation given max observed rewards.

#### `alda/total_loss`
- **Definition**: `float(total.detach())` where `total = recon + cfg.commitment_coef * commitment + cfg.quantization_coef * quantization`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:489`
- **Question Answered**: Total autoencoder loss (reconstruction + commitment + quantization).
- **Algorithm Family**: Representation (ALDA / QLAE)
- **Caveat**: Abort if $> 10^6$.

#### `alda/recon_bce`
- **Definition**: `float(recon.detach())` (Binary cross entropy on normalized pixels $[0, 1]$)
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:482, 490`, `vigen-idaac/vigen_alda/metrics.py:68-72`
- **Question Answered**: Pixel reconstruction binary cross entropy loss.
- **Algorithm Family**: Representation (ALDA / SAC+AE)
- **Caveat**: Warn if after 200k frames recon BCE is still $> 0.69$ ($\ln 2 pprox 0.6931$ is chance / no-information level).

#### `alda/commitment`
- **Definition**: `float(commitment.detach().mean())` where `commitment = F.mse_loss(z_cont, z_q.detach())`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:483, 491`
- **Question Answered**: Encoder commitment loss to discrete codebook vectors.
- **Algorithm Family**: Representation (ALDA / QLAE)
- **Caveat**: 0.0 for continuous latent model.

#### `alda/quantization`
- **Definition**: `float(quantization.detach().mean())` where `quantization = F.mse_loss(z_cont.detach(), z_q)`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:484, 492`
- **Question Answered**: Codebook vector learning loss toward encoder latents.
- **Algorithm Family**: Representation (QLAE with `train_codebook=True`)
- **Caveat**: 0.0 when codebook is fixed (ALDA default).

#### `alda/recon_mse`
- **Definition**: `float(mse)` where `mse = F.mse_loss(rec_sig, target_sig)`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:495, 497`
- **Question Answered**: Mean squared error of reconstructed image pixels.
- **Algorithm Family**: Representation (ALDA / SAC+AE)
- **Caveat**: Diagnostic reconstruction quality metric.

#### `alda/psnr`
- **Definition**: `float(10.0 * torch.log10(1.0 / mse.clamp_min(1e-12)))`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:496`
- **Question Answered**: Peak Signal-to-Noise Ratio (dB) of autoencoder pixel reconstruction.
- **Algorithm Family**: Representation (ALDA / SAC+AE)
- **Caveat**: Logarithmic reconstruction fidelity scale ($10 \log_{10} \frac{1}{\text{MSE}}$).

#### `latent/z_abs_mean`
- **Definition**: `float(z_cont.abs().mean())`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:511`
- **Question Answered**: Mean absolute magnitude of continuous encoder latent representation.
- **Algorithm Family**: Representation (ALDA / QLAE / SAC+AE)
- **Caveat**: Scales with learned representations.

#### `latent/z_std`
- **Definition**: `float(z_cont.std())`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:512`
- **Question Answered**: Standard deviation of continuous latent activations.
- **Algorithm Family**: Representation
- **Caveat**: Zero variance indicates latent collapse.

#### `latent/frac_outside_unit`
- **Definition**: `float((z_cont.abs() > 1.0).float().mean())`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:513`, `vigen-idaac/vigen_alda/metrics.py:85-115`
- **Question Answered**: Fraction of encoder latent values outside $[-1, 1]$ codebook range.
- **Algorithm Family**: Representation (ALDA associative memory / QLAE)
- **Caveat**: **Explicitly called misleading if taken alone (ALDA.md, metrics.py:85-115)**: (1) Meaningless for SAC+AE (`continuous`), which is unbounded by design. (2) For QLAE with learned codebooks (`train_codebook=True`), codebook scale grows to $pprox 7.5$, so $> 1.0$ is not saturation. (3) On training data with fixed unit codebook, high fraction + dead codes indicates saturation loss; on `eval-easy` test data, rise is the OOD association mechanism working as intended.

#### `latent/usage_entropy`
- **Definition**: `float(np.mean(ent))` where `ent = -sum(p * log(p))` over codebook discrete selection empirical frequencies
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:529`, `vigen-idaac/vigen_alda/metrics.py:73-80`
- **Question Answered**: Shannon entropy of codebook discrete entry usage across batch.
- **Algorithm Family**: Representation (ALDA / QLAE)
- **Caveat**: Warn if $< 0.05 \times \text{usage\_entropy\_max}$ (codebook collapse to single codes).

#### `latent/usage_entropy_max`
- **Definition**: `float(np.log(n_vals))` (maximum possible entropy for uniform codebook usage)
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:530`
- **Question Answered**: Theoretical upper bound on codebook usage entropy ($\ln K$).
- **Algorithm Family**: Representation (ALDA / QLAE)
- **Caveat**: Fixed reference scale.

#### `latent/dead_codes_frac`
- **Definition**: `dead / float(v.numel())` where `dead` is count of codebook entries unselected by any sample in batch
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:531`, `vigen-idaac/vigen_alda/metrics.py:81-83`
- **Question Answered**: Fraction of codebook discrete slots never retrieved in batch.
- **Algorithm Family**: Representation (ALDA / QLAE)
- **Caveat**: Warn if $> 0.90$.

#### `latent/softmax_max_weight`
- **Definition**: `float(attn.max(dim=-1).values.mean())` in associative memory lookup
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:534-535`
- **Question Answered**: Average peak softmax attention weight in associative memory lookup.
- **Algorithm Family**: Representation (ALDA associative memory)
- **Caveat**: $1.0$ indicates hard 1-hot nearest neighbor snapping; lower values indicate soft interpolation.

#### `latent/codebook_absmax`
- **Definition**: `float(v.abs().max())` where `v` is codebook embedding tensor
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:536`, `vigen-idaac/vigen_alda/metrics.py:103-108`
- **Question Answered**: Maximum absolute value in the latent codebook tensor.
- **Algorithm Family**: Representation (ALDA / QLAE)
- **Caveat**: Distinguishes fixed unit codebook ($\le 1.5$) from learned expanding codebook ($> 7.0$).

#### `params/trunk`, `params/history`, `params/decoder`, `params/actor`, `params/critic`, `params/latent`
- **Definition**: `sum(p.numel() for p in module.parameters())`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:234-239`
- **Question Answered**: Total parameter count per sub-network component in ALDA agent.
- **Algorithm Family**: Any modular agent
- **Caveat**: Static architectural diagnostic.

#### `grad/trunk_from_critic`
- **Definition**: `float(torch.stack(gt).sum().sqrt()) if gt else 0.0`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:344`
- **Question Answered**: $L_2$ gradient norm backpropagated from Q-critic loss into the shared visual trunk encoder.
- **Algorithm Family**: Representation / actor-critic with shared encoder
- **Caveat**: Zero if critic gradients through encoder are detached.

#### `grad/critic`, `grad/trunk`, `grad/decoder`, `grad/history`, `grad/actor`, `grad/latent`
- **Definition**: `math.sqrt(sum(p.grad.pow(2).sum() for p in module.parameters() if p.grad is not None))`
- **File:Line**: `vigen-idaac/vigen_alda/agent.py:354, 596-598`, `vigen-idaac/vigen_alda/metrics.py:165-175`
- **Question Answered**: Raw $L_2$ gradient norm per component in ALDA agent without gradient clipping.
- **Algorithm Family**: Off-policy actor-critic
- **Caveat**: ALDA applies NO gradient clipping (unlike IDAAC/PPO). Warn if $> 10^4$ (exploding gradients where only Adam step normalization bounds updates).

#### `buf/size`
- **Definition**: `int(len(self))`
- **File:Line**: `vigen-idaac/vigen_alda/buffer.py:208`
- **Question Answered**: Current number of valid transitions stored in replay buffer.
- **Algorithm Family**: Off-policy (replay buffer)
- **Caveat**: Sampleable transitions.

#### `buf/episodes_ended`
- **Definition**: `int(len(self.final_frames))`
- **File:Line**: `vigen-idaac/vigen_alda/buffer.py:208`
- **Question Answered**: Count of completed episode boundary transitions stored in buffer.
- **Algorithm Family**: Off-policy
- **Caveat**: Used for next-state reconstruction at episode boundaries.

#### `buf/wrapped`
- **Definition**: `int(self.wrapped.any())`
- **File:Line**: `vigen-idaac/vigen_alda/buffer.py:209`
- **Question Answered**: Indicator whether circular buffer write head has reached capacity and wrapped to index 0.
- **Algorithm Family**: Off-policy
- **Caveat**: **Explicitly clarified in code comments (buffer.py:201-206)**: `wrapped == 1` means write head reached position 0; it does NOT mean transitions were evicted until `total_added > capacity`.

#### `buf/evicted`
- **Definition**: `max(0, int(self.total_added) - int(self.capacity))`
- **File:Line**: `vigen-idaac/vigen_alda/buffer.py:207, 210`
- **Question Answered**: Exact number of transitions evicted/overwritten in circular replay buffer.
- **Algorithm Family**: Off-policy
- **Caveat**: ALDA paper uses 1M buffer for 500k steps and never evicts; any positive value indicates deviation from paper setup.

#### `buf/frac_full`
- **Definition**: `float(len(self)) / float(self.capacity)`
- **File:Line**: `vigen-idaac/vigen_alda/buffer.py:211`
- **Question Answered**: Fraction of replay buffer capacity utilized $[0, 1]$.
- **Algorithm Family**: Off-policy
- **Caveat**: Buffer filling progress.

#### `ep/best_return`
- **Definition**: `max(ep_returns)`
- **File:Line**: `vigen-idaac/vigen_alda/train.py:526`
- **Question Answered**: Best trailing raw episode return observed so far.
- **Algorithm Family**: Any
- **Caveat**: High-water mark for training return.

#### `ep/frames_since_best`
- **Definition**: `frames - best_ret_frames`
- **File:Line**: `vigen-idaac/vigen_alda/train.py:527`, `vigen-idaac/vigen_alda/metrics.py:130-135`
- **Question Answered**: Elapsed training frames since the last improvement in best return.
- **Algorithm Family**: Any
- **Caveat**: Used to detect policy learning plateaus ($> 35\%$ of total budget with no improvement after $50\%$ frames).

---

### 1.6 Evaluation Protocol, Generalization & Aggregation Metrics (`evaluate.py`, `report.py`, `probes/*.py`, `ext/alda/Nd_ln.py`)

#### `iqm` (Interquartile Mean)
- **Definition**: `float(np.mean(np.sort(a)[a.size // 4: a.size - a.size // 4])) if a.size >= 4 else float(a.mean())`
- **File:Line**: `vigen-idaac/vigen_idaac/evaluate.py:193-194`, `vigen-idaac/vigen_idaac/report.py:38-43`, `vigen-idaac/vigen_alda/evaluate.py:128-129`
- **Question Answered**: Robust central tendency metric trimming top and bottom 25% of episode returns.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: **Extensively analyzed and critiqued across code/docs (FINDINGS I5, STATE.md B32, ALDA.md:1768, PROTOCOL-DIFF.md:368-398, results_table.py:149-167)**:
  - Robust on skewed, bimodal distributions like Lift training (grasp vs fail).
  - But on `eval-easy` 10-scene evaluation pools, trimming the top 25% drops the few solved scenes entirely, severely understating transfer (mean/IQM is 1.10–4.54x). Demoted from rebuttal headline to internal robustness metric.

#### `iqm_ci`
- **Definition**: Percentile bootstrap CI on IQM over $B = 10,000$ resampled episode arrays: `(quantile(stats, 0.025), quantile(stats, 0.975))` where `stats = boot[:, lo_i:hi_i].mean(axis=1)`
- **File:Line**: `vigen-idaac/vigen_idaac/report.py:46-58`
- **Question Answered**: 95% confidence interval capturing evaluation sampling noise for a fixed policy checkpoint.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Measures episode evaluation noise only; does NOT describe seed variance across training runs.

#### `mean` (Deterministic Return Mean)
- **Definition**: `float(a.mean())` where `a` is array of all deterministic episode returns
- **File:Line**: `vigen-idaac/vigen_idaac/evaluate.py:189`, `vigen-idaac/vigen_alda/evaluate.py:126`
- **Question Answered**: Average deterministic return across all evaluated episodes/scenes.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Outlier-sensitive on bimodal Lift task; unweighted mean over 10 scenes.

#### `median` (Episode Return Median)
- **Definition**: `float(np.median(a))`
- **File:Line**: `vigen-idaac/vigen_idaac/evaluate.py:190`, `vigen-idaac/vigen_alda/evaluate.py:127`
- **Question Answered**: 50th percentile of episode returns.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Collapses to 0.0 on sparse tasks when success rate is $< 50\%$.

#### `std` (Episode Return Standard Deviation)
- **Definition**: `float(a.std())`
- **File:Line**: `vigen-idaac/vigen_idaac/evaluate.py:189`, `vigen-idaac/vigen_alda/evaluate.py:126`
- **Question Answered**: Dispersion / spread of individual episode returns.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Standard deviation implies a Gaussian distribution which does not exist for bimodal grasp/fail tasks.

#### `per_scene_mean`
- **Definition**: `{int(k): float(np.mean(v)) for k, v in per_scene.items() if v}`
- **File:Line**: `vigen-idaac/vigen_idaac/evaluate.py:195`, `vigen-idaac/vigen_alda/evaluate.py:131`
- **Question Answered**: Breakdown of mean return for each individual visual scene ID (0..9).
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Reveals large inter-scene variance (up to 419x spread across scenes in eval-easy).

#### `per_scene_returns`
- **Definition**: `{int(k): [float(x) for x in v] for k, v in per_scene.items()}`
- **File:Line**: `vigen-idaac/vigen_idaac/evaluate.py:200`, `vigen-idaac/vigen_alda/evaluate.py:133`
- **Question Answered**: Complete raw list of episode returns partitioned per scene ID.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Source data for all downstream bootstrap CIs and parity conversions.

#### `det_stoch_ratio`
- **Definition**: `float(det_mean) / stoch_mean`
- **File:Line**: `vigen-idaac/vigen_idaac/evaluate.py:170`, `vigen-idaac/vigen_alda/evaluate.py:110`, `vigen-idaac/probes/det_stoch_table.py:47-48`
- **Question Answered**: FINDINGS D23 detector: ratio of deterministic mean-action return to stochastic sampled-action return.
- **Algorithm Family**: Evaluation-protocol / continuous actor-critic
- **Caveat**: **Key finding (FINDINGS D23, ALDA.md:766-795, evaluate.py:173-184)**: If $< 0.5$, policy mean action is significantly worse than sampled actions; reported deterministic score severely misrepresents how the policy actually trained. Very noisy at low sample count ($n < 8$ episodes).

#### `stochastic_mean`
- **Definition**: `float(np.mean(srets))` over `stochastic_check` episodes
- **File:Line**: `vigen-idaac/vigen_idaac/evaluate.py:152`, `vigen-idaac/vigen_alda/evaluate.py:100`
- **Question Answered**: Mean return achieved by sampling actions from the stochastic policy distribution.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Evaluated on subset of episodes ($n=8$) to keep overhead low.

#### `retention` / `Protocol Retention`
- **Definition**: `100.0 * eval_easy_mean_10scenes / train_mean_scene0` (or `eval_iqm / train_iqm * 100.0`)
- **File:Line**: `vigen-idaac/vigen_idaac/report.py:103`, `vigen-idaac/probes/results_table.py:217`, `vigen-idaac/probes/retention_ci.py:65`
- **Question Answered**: Percentage of training performance retained when evaluating in out-of-distribution visual test environment (`eval-easy`).
- **Algorithm Family**: Evaluation-protocol / generalization
- **Caveat**: **Crucial denominator caveats (STATE.md B31, results_table.py:86-99, random_floor_gate.py:50-74)**:
  - Must use train scene-0 as denominator because agents trained only on scene 0 appearance; using 10-scene train mean turns denominator into a generalisation measure and produces false $>100\%$ ratios (e.g. 93.9% vs true 0.9%).
  - Must be gated against random-policy floor: if denominator is indistinguishable from random policy, retention is mathematically undefined.

#### `Alt.version Retention` / `dz_retention`
- **Definition**: `100.0 * eval_easy_mean_scene0 / train_mean_scene0` (first 10 episodes on scene 0)
- **File:Line**: `vigen-idaac/vigen_alda/eval_dz.py:54-67`, `vigen-idaac/probes/results_table.py:184-185`, `ext/alda/Nd_ln.py:625-645`
- **Question Answered**: Supervisor / DZ baseline retention reduction reproducing 1-scene, 10-episode mean evaluation protocol.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: High sampling variance (relative standard error ~64% across scenes) because it relies on a single scene.

#### `mean_step_reward` (DZ / Alt.version metric)
- **Definition**: `mean_reward / mean_length if mean_length > 0 else 0.0`
- **File:Line**: `vigen-idaac/vigen_alda/eval_dz.py:62`, `ext/alda/Nd_ln.py:644`
- **Question Answered**: Average reward per environment step in evaluation episodes.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: **Ratio of means, NOT mean of per-episode ratios (eval_dz.py:37-38)**; differs when episode lengths vary.

#### `mean_length` (DZ / Alt.version metric)
- **Definition**: `float(np.mean(all_lengths))`
- **File:Line**: `vigen-idaac/vigen_alda/eval_dz.py:61`, `ext/alda/Nd_ln.py:643`
- **Question Answered**: Mean episode length under DZ evaluation protocol.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Sampled over 10 episodes.

#### `mean_reward` (DZ / Alt.version metric)
- **Definition**: `float(np.mean(all_rewards))`
- **File:Line**: `vigen-idaac/vigen_alda/eval_dz.py:60`, `ext/alda/Nd_ln.py:642`
- **Question Answered**: Mean raw episode return on scene 0 over 10 episodes.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Evaluated only on scene 0.

#### `ratio_ci` / `mean_ratio_ci`
- **Definition**: Bootstrapped confidence interval on ratio $b / a \times 100$ over $nb=2000$ resamples with per-row deterministic CRC32 seeding
- **File:Line**: `vigen-idaac/probes/results_table.py:35-73`
- **Question Answered**: 95% bootstrap confidence interval on retention ratio.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Must seed per row with CRC32 to ensure deterministic, order-independent reproduction; hash() is non-deterministic across processes.

#### `random_floor_mean`
- **Definition**: `float(np.mean(returns))` for uniform random action policy
- **File:Line**: `vigen-idaac/probes/random_floor.py:59`, `vigen-idaac/probes/random_floor_gate.py:23-38`
- **Question Answered**: Negative control: baseline expected return of an untrained uniform random policy (measured: Door = 0.000, Lift = 0.002 / ~7.80 on dense).
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Essential baseline for gating whether an agent has learned before computing retention ratios.

#### `learned_threshold`
- **Definition**: 97.5th percentile of $n$-episode random policy mean bootstrap distribution ($nb=4000$)
- **File:Line**: `vigen-idaac/probes/random_floor_gate.py:50-74`
- **Question Answered**: Statistical hypothesis test threshold for whether training return is significantly greater than random policy ($p < 0.025$).
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Sample-size dependent ($O(1/\sqrt{n})$ shrinkage).

#### `is_learned`
- **Definition**: `st.mean(train_scene0_episodes) > learned_threshold(task, len(train_scene0_episodes))`
- **File:Line**: `vigen-idaac/probes/random_floor_gate.py:76-80`
- **Question Answered**: Boolean gate determining whether a run cleared random chance and can be assigned a valid retention ratio.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: If false, published retention is marked `undefined`.

#### `ratio_scene_expansion` (Protocol ablation metric)
- **Definition**: `our_mean_10s / alt_mean_s0` (10-scene mean / scene-0 mean)
- **File:Line**: `vigen-idaac/probes/protocol_ablation.py:65`
- **Question Answered**: Protocol ablation: isolated effect of expanding from 1 scene to 10 scenes (Axis E1).
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Median 0.785 on eval-easy (scene 0 lands ~21.5% below 10-scene mean on median).

#### `ratio_iqm_vs_mean` (Protocol ablation metric)
- **Definition**: `our_iqm_10s / our_mean_10s` (10-scene IQM / 10-scene mean)
- **File:Line**: `vigen-idaac/probes/protocol_ablation.py:66`
- **Question Answered**: Protocol ablation: isolated effect of IQM vs Mean aggregation on 10 scenes (Axis E3).
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Median 1.418 on eval-easy (Mean is 41.8% above IQM due to right-skewed successes).

#### `combined_ratio` (Protocol ablation metric)
- **Definition**: `our_iqm_10s / alt_mean_s0`
- **File:Line**: `vigen-idaac/probes/protocol_ablation.py:67`
- **Question Answered**: Total ratio between Our Protocol (10-scene IQM) and Alt.version Protocol (1-scene Mean).
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Median is ~1.0 solely because Axis E1 (0.785) and Axis E3 (1.418) cancel each other out ($0.785 \times 1.418 \approx 1.11$).

#### `subset_relative_error`
- **Definition**: `abs(subset_mean - full10_mean) / full10_mean`
- **File:Line**: `vigen-idaac/probes/scene_subset_error.py:53`
- **Question Answered**: Relative estimation error when evaluating on a subset of scenes (e.g. 2 scenes vs 10 scenes).
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Quantifies risk of fast "lean" evaluation jobs.

#### `subset_rank_correlation`
- **Definition**: Spearman rank correlation between checkpoint scores under subset vs full 10 scenes
- **File:Line**: `vigen-idaac/probes/scene_subset_error.py:62`
- **Question Answered**: Whether a subset of scenes preserves checkpoint rankings during checkpoint sweeps.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Evaluates rank preservation for stride selection.

#### `eval_seconds`
- **Definition**: `round(time.time() - t0, 1)` for checkpoint evaluation pass
- **File:Line**: `vigen-idaac/vigen_idaac/evaluate.py:249`, `vigen-idaac/vigen_alda/evaluate.py:172`
- **Question Answered**: Wall-clock seconds required to evaluate one policy checkpoint.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Profiling metric.

---

### 1.7 RL-ViGen Baseline Algos & Logger Metrics (`algos/*.py`, `logger.py`, `train.py`, `eval.py`)

#### `train/episode_reward`, `eval/episode_reward`
- **Definition**: `AverageMeter.value()` of accumulated episode returns
- **File:Line**: `vigen-idaac/logger.py:18, 24, 38`
- **Question Answered**: Standard episode return in RL-ViGen benchmark baselines.
- **Algorithm Family**: Any
- **Caveat**: Base logger metric.

#### `eval/success_rate`
- **Definition**: Binary completion rate $SR = \frac{1}{N}\sum \mathbb{I}(\text{success})$
- **File:Line**: `vigen-idaac/logger.py:25`, `vigen-idaac/train.py:189`, `vigen-idaac/eval.py:223`
- **Question Answered**: Binary task completion rate in robosuite environments.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Extremely sparse for complex manipulation (Lift/Door); fails to capture shaped continuous reward progress.

#### `train/episode_length`, `eval/episode_length`
- **Definition**: Mean episode step count
- **File:Line**: `vigen-idaac/logger.py:17, 23`
- **Question Answered**: Average episode duration.
- **Algorithm Family**: Any
- **Caveat**: Base logger metric.

#### `train/buffer_size`
- **Definition**: `len(replay_buffer)`
- **File:Line**: `vigen-idaac/logger.py:19`
- **Question Answered**: Replay buffer transition count in off-policy baselines.
- **Algorithm Family**: Off-policy
- **Caveat**: Replay buffer tracking.

#### `train/fps`
- **Definition**: Steps per second during training in RL-ViGen baselines
- **File:Line**: `vigen-idaac/logger.py:19`
- **Question Answered**: Baseline throughput.
- **Algorithm Family**: Any
- **Caveat**: Base logger metric.

#### `train/total_time`, `eval/total_time`
- **Definition**: Elapsed time formatted as timedelta
- **File:Line**: `vigen-idaac/logger.py:20, 25`
- **Question Answered**: Total execution time string.
- **Algorithm Family**: Any
- **Caveat**: Formatted display string.

#### `batch_reward`
- **Definition**: `reward.mean().item()` across sample batch
- **File:Line**: `vigen-idaac/algos/curl.py:137`, `drq.py:355`, `drqv2.py:249`, `pieg.py:322`, `sgqn.py:228`, `srm.py:45`, `svea.py:307`
- **Question Answered**: Mean step reward in minibatch sampled from replay buffer.
- **Algorithm Family**: Off-policy (CURL, DrQ, DrQ-v2, PIEG, SGQN, SRM, SVEA)
- **Caveat**: Sampled transition reward, not episode return.

#### `critic_target_q`
- **Definition**: `target_Q.mean().item()`
- **File:Line**: `vigen-idaac/algos/drq.py:287`, `drqv2.py:192`, `pieg.py:260`, `sgqn.py:175`, `svea.py:245`
- **Question Answered**: Mean target Q-value in double-Q critic update for RL-ViGen baselines.
- **Algorithm Family**: Off-policy actor-critic
- **Caveat**: Target network prediction.

#### `critic_q1`, `critic_q2`
- **Definition**: `current_Q1.mean().item()`, `current_Q2.mean().item()`
- **File:Line**: `vigen-idaac/algos/drq.py:288-289`, `drqv2.py:193-194`, `pieg.py:261-262`, `sgqn.py:176-177`, `svea.py:246-247`
- **Question Answered**: Mean predicted Q-values from critic heads 1 and 2.
- **Algorithm Family**: Off-policy actor-critic
- **Caveat**: Bellman regression predictions.

#### `critic_loss`
- **Definition**: `critic_loss.item()` (MSE / Huber loss on Bellman error)
- **File:Line**: `vigen-idaac/algos/drq.py:290`, `drqv2.py:195`, `pieg.py:263`, `sgqn.py:178`, `svea.py:248`
- **Question Answered**: Critic loss in RL-ViGen baselines.
- **Algorithm Family**: Off-policy actor-critic
- **Caveat**: Standard critic loss.

#### `actor_loss`
- **Definition**: `actor_loss.item()`
- **File:Line**: `vigen-idaac/algos/drq.py:324`, `drqv2.py:224`, `pieg.py:292`, `svea.py:277`
- **Question Answered**: DDPG / SAC policy gradient loss.
- **Algorithm Family**: Off-policy actor-critic
- **Caveat**: Optimizes expected Q-value.

#### `actor_logprob`
- **Definition**: `log_prob.mean().item()`
- **File:Line**: `vigen-idaac/algos/drq.py:325`, `drqv2.py:225`, `pieg.py:293`, `svea.py:278`
- **Question Answered**: Mean log probability of policy actions.
- **Algorithm Family**: Continuous policy
- **Caveat**: Log probability under Gaussian distribution.

#### `actor_ent`
- **Definition**: `dist.entropy().sum(dim=-1).mean().item()`
- **File:Line**: `vigen-idaac/algos/drq.py:326`, `drqv2.py:226`, `pieg.py:294`, `svea.py:279`
- **Question Answered**: Entropy of Gaussian policy action distribution.
- **Algorithm Family**: Continuous policy
- **Caveat**: Summed across action dimensions.

#### `curl_loss`
- **Definition**: `curl_loss.item()` (contrastive InfoNCE loss)
- **File:Line**: `vigen-idaac/algos/curl.py:106`
- **Question Answered**: Contrastive representation learning loss between query and positive key image crops.
- **Algorithm Family**: Representation / contrastive RL (CURL)
- **Caveat**: Specific to CURL baseline.

---

### 1.8 Upstream Script & External Reference Metrics (`ext/alda/Nd_ln.py`)

#### `train_metrics/episode_return`, `train_metrics/episode_length`, `train_metrics/episode_step_reward`
- **Definition**: `float(rewards.sum())`, `int(lengths)`, `episode_return / episode_length`
- **File:Line**: `ext/alda/Nd_ln.py:648-650`
- **Question Answered**: Training episode return, length, and step reward logged by Alt.version's `Nd_ln.py`.
- **Algorithm Family**: Off-policy (ALDA / SAC)
- **Caveat**: Logged to W&B in upstream script.

#### `train_metrics/smoothed_episode_return`, `train_metrics/smoothed_episode_length`, `train_metrics/smoothed_episode_step_reward`
- **Definition**: Exponential moving average (alpha = 0.05) of training episode return, length, step reward
- **File:Line**: `ext/alda/Nd_ln.py:651-653`
- **Question Answered**: Smoothed training metrics for live W&B tracking.
- **Algorithm Family**: Off-policy
- **Caveat**: EMA smoothed curves.

#### `train_metrics/mean_reward`
- **Definition**: `float(mean_reward)` across evaluation episodes
- **File:Line**: `ext/alda/Nd_ln.py:654`
- **Question Answered**: Evaluation mean reward logged to W&B in `Nd_ln.py`.
- **Algorithm Family**: Evaluation-protocol
- **Caveat**: Upstream evaluation metric.

#### `losses/q_loss`, `losses/q1_values`, `losses/q2_values`, `losses/critic_total_loss`, `losses/disc_loss_vs_target`, `losses/crosscov_loss`, `losses/noncausal_loss`, `losses/lambda_loss`
- **Definition**: Various ALDA loss components in `ext/alda/Nd_ln.py:756-785`
- **File:Line**: `ext/alda/Nd_ln.py:756-785`
- **Question Answered**: ALDA disentanglement and critic loss terms logged to W&B in upstream `Nd_ln.py`.
- **Algorithm Family**: Representation (ALDA)
- **Caveat**: Specific to upstream Nd_ln.py implementation.

#### `losses/actor_loss`, `losses/alpha`, `losses/alpha_loss`
- **Definition**: SAC actor and temperature losses in `Nd_ln.py:795-802`
- **File:Line**: `ext/alda/Nd_ln.py:795-802`
- **Question Answered**: Policy and temperature values logged to W&B.
- **Algorithm Family**: Off-policy SAC
- **Caveat**: Upstream logging keys.

#### `performance/SPS`, `performance/memory_usage_gb`
- **Definition**: `num_steps / elapsed_time`, process RSS memory in GB
- **File:Line**: `ext/alda/Nd_ln.py:808-812`
- **Question Answered**: Execution steps per second and memory consumption.
- **Algorithm Family**: Any
- **Caveat**: Profiling metrics in upstream script.

#### `replay_buffer/size_steps`, `replay_buffer/size_transitions`, `replay_buffer/size_gb`
- **Definition**: Buffer size in steps, transitions, and memory footprint
- **File:Line**: `ext/alda/Nd_ln.py:815-817`
- **Question Answered**: Buffer tracking diagnostics in `Nd_ln.py`.
- **Algorithm Family**: Off-policy
- **Caveat**: Upstream buffer stats.

---

### 1.9 Doc-Only Metrics & Theoretical Constructs

#### `generalization_gap`
- **Definition**: $G = \text{Train Performance} - \text{Eval Performance}$ (or $1.0 - \text{Retention}$)
- **File:Line**: `research-brief.md:118`, `vigen-idaac/FINDINGS.md:61-75 (B7)`, `vigen-idaac/PROTOCOL-DIFF.md:19`, `vigen-idaac/AXES.md:1-50`
- **Question Answered**: Quantifies performance degradation when testing on out-of-distribution visual scenes vs training visual scene.
- **Algorithm Family**: Evaluation-protocol / generalization
- **Caveat**: **Documented in FINDINGS B7**: In upstream RL-ViGen, `mode` was not forwarded to the environment wrapper, so `eval-easy` rendered identically to `train`, causing the measured generalization gap to be identically 0.0 by construction.

#### `disentanglement_metric` / `modularity_score` / `compactness` / `explicitness`
- **Definition**: Mutual Information Gap (MIG) / Eastwood & Williams (2018) disentanglement metrics: $\text{Modularity} = \frac{1}{D}\sum_{i=1}^D (1 - \frac{\sum_{j \ne j^*} I(z_i; c_j)^2}{(D-1) I(z_i; c_{j^*})^2})$, $\text{Compactness} = \frac{1}{K}\sum_{j=1}^K (1 - \frac{\sum_{i \ne i^*} I(z_i; c_j)^2}{(K-1) I(z_{i^*}; c_j)^2})$
- **File:Line**: `ext/alda/arXiv-2410.07441v1/iclr2025_conference.tex:320-350`, `ext/alda/qwen_ai/AI_Qwen_Research_1.md:53-70`, `vigen-idaac/ALDA.md:40-70`
- **Question Answered**: Measures whether individual latent dimensions correspond 1-to-1 with underlying ground-truth generative factors (position, color, lighting).
- **Algorithm Family**: Representation (ALDA)
- **Caveat**: Doc-only in this codebase; requires ground truth environmental state factor labels $c_j$ which are inaccessible in pixel-only robosuite benchmarks. Replaced in this project by empirical probes (`latent/usage_entropy`, `latent/frac_outside_unit`, latent traversals).

#### `latent_traversal_divergence`
- **Definition**: $\Delta(z_i) = \mathbb{E}_{s}[ \| \text{Decoder}(z + \delta e_i) - \text{Decoder}(z) \| ]$
- **File:Line**: `ext/alda/arXiv-2410.07441v2/main.tex:210-235`, `ext/alda/qwen_ai/AI_Qwen_Research_1.md:53`
- **Question Answered**: Qualitative and quantitative probe of single-dimension latent traversals to verify localized visual attribute variation.
- **Algorithm Family**: Representation (ALDA)
- **Caveat**: Doc-only / visual figure generation; evaluated by plotting latent traversal sweeps across codebook dimensions.

---

## List A: Computed But Never Logged or Reported

These metrics are fully evaluated in Python functions, but their returned values are discarded, dropped from logging dictionaries, omitted from storage/CSV writers, or absent from all downstream reporting pipelines:

1. **`disc/logit_abs_mean`**
   - *Computed*: `vigen-idaac/vigen_idaac/metrics.py:160` inside `adversary_health`.
   - *Why Unlogged*: In `vigen_idaac/algo.py:162`, the trainer only pulls `["disc/acc"]` from the dict returned by `adversary_health`. `disc/logit_abs_mean` is discarded and never added to `acc`, `row`, or `log.csv`.
2. **`disc/enc_loss_minus_log2`**
   - *Computed*: `vigen-idaac/vigen_idaac/metrics.py:162` inside `adversary_health`.
   - *Why Unlogged*: Never extracted into `acc` or `row` in `vigen_idaac/algo.py`; omitted from `log.csv` and W&B.
3. **`act/std_across_batch`**
   - *Computed*: `vigen-idaac/vigen_idaac/metrics.py:41` inside `action_health`.
   - *Why Unlogged*: `train.py:223` calls `row.update(M.action_health(...))`, but `act/std_across_batch` was excluded from `EXPECTED_KEYS` (`metrics.py:272-288`), has no alarm threshold in `ALARMS`, is never read in `analyze.py`, and is not reported in any table or plot.
4. **`consistency/expected_ends`**
   - *Computed*: `vigen-idaac/vigen_idaac/metrics.py:193` inside `consistency`.
   - *Why Unlogged*: Inserted into `row` by `train.py:292`, but never checked in `ALARMS` or `analyze.py`, and omitted from all result summaries.
5. **`env/steps_per_worker_min` & `env/episodes_per_worker_min`**
   - *Computed*: `vigen-idaac/vigen_idaac/metrics.py:70-71`.
   - *Why Unlogged/Unused*: Explicitly documented as "kept, informational, NOT a detector" (`metrics.py:59-60`); never attached to an alarm or evaluated in `analyze.py`.
6. **`critic/target_q_std`**
   - *Computed*: `vigen-idaac/vigen_alda/agent.py:368`.
   - *Why Unlogged/Unused*: Added to `log` dict in `agent.py`, but omitted from `vigen_alda/metrics.py:detect()` and never analyzed in any probe or plot.
7. **`critic/td_error_max`**
   - *Computed*: `vigen-idaac/vigen_alda/agent.py:367`.
   - *Why Unlogged/Unused*: Computed in `agent.py`, but never checked by any detector threshold or consumed by probe scripts.

---

## List B: Logged But Never Consumed by Any Analysis or Plot

These metrics are written to `log.csv`, W&B, or evaluation JSON artifacts, but are never read by `analyze.py`, `report.py`, any script in `probes/*.py`, or test verification scripts:

1. **`adv/loss`** (`vigen_idaac/algo.py:114`): Logged every update, but `analyze.py` checks `adv/std_prenorm` and `adv_head/corr` instead; never plotted.
2. **`disc/loss`** (`vigen_idaac/algo.py:161`): Logged every update, but `analyze.py` checks `disc/acc` and `disc/pair_purity`; never plotted in final rebuttal figures.
3. **`pi/pg_loss`** (`vigen_idaac/algo.py:168`): Logged to CSV, but omitted from `analyze.py` verification checks and all figure scripts.
4. **`pi/log_std_min` & `pi/log_std_max`** (`vigen_idaac/algo.py:250-251`): Logged to CSV, but `analyze.py` checks only `pi/log_std_mean`.
5. **`diag/corr_A_t`** (`vigen_idaac/algo.py:254`): Computed on diagnostic updates and logged to CSV/W&B, but `analyze.py:171-177` and rebuttal figures evaluate only `diag/corr_V_t`.
6. **`diag/is_diag_update`** (`vigen_idaac/algo.py:255`): Binary logging flag; never read by any analysis script.
7. **`health/losses_all_finite`** (`vigen_idaac/algo.py:246`): Static 1.0 indicator; never checked downstream.
8. **`actor/alpha_loss`** (`vigen_alda/agent.py:432`): Logged in ALDA training, but probe scripts track `actor/alpha` directly.
9. **`actor/log_std`** (`vigen_alda/agent.py:435`): Logged in ALDA training, but `plot_collapse.py` checks `actor/std_min` and `actor/mu_saturated_frac`.
10. **`alda/quantization`** (`vigen_alda/agent.py:492`): Logged in ALDA/QLAE, but probe scripts track `alda/recon_bce` and `latent/usage_entropy`.
11. **`alda/recon_mse`** (`vigen_alda/agent.py:497`): Logged in ALDA, but downstream figures plot `alda/recon_bce`.
12. **`alda/total_loss`** (`vigen_alda/agent.py:489`): Logged in ALDA, but analysis focuses on individual reconstruction and Q losses.
13. **`critic/q2`** (`vigen_alda/agent.py:359`): Twin Q2 logged to CSV, but plots and alarms examine `critic/q1` and `critic/q_gap`.
14. **`latent/z_abs_mean` & `latent/z_std`** (`vigen_alda/agent.py:511-512`): Logged to CSV, but probe scripts monitor `latent/frac_outside_unit` and `latent/codebook_absmax`.
15. **`latent/softmax_max_weight`** (`vigen_alda/agent.py:534`): Logged to CSV, but omitted from `alda_report.py` and rebuttal figures.
16. **`buf/size` & `buf/episodes_ended`** (`vigen_alda/buffer.py:208`): Buffer state summaries logged to CSV, but omitted from all downstream plots.
17. **`buf/wrapped`** (`vigen_alda/buffer.py:209`): Logged to CSV, but `buf/evicted` is the authoritative metric consumed.
18. **`ep/best_return`** (`vigen_alda/train.py:526`): High-water mark logged to CSV, but never plotted directly.
19. **`time/eta_hours`** (`vigen_alda/train.py:518`): Displayed in stdout heartbeat, logged to CSV, but never consumed by post-run analysis.
20. **`time/collect_s` & `time/update_s`** (`vigen_idaac/train.py:271-272`): Raw second counts logged to CSV, but analysis reads the derived `time/learner_frac` and `time/fps`.
21. **`rew/raw_max`** (`vigen_idaac/train.py:287`): Logged to CSV, but never checked by `analyze.py` or plotted.

---

## List C: Metrics Documented as Misleading, Biased, or Conditionally Invalid

This list details every instance where project code, docstrings, or markdown documentation explicitly critiques a metric as misleading, biased, unfireable, or conditionally invalid:

1. **`env/episode_imbalance` — Misleading detector / 100% false alarm rate under phase staggering**
   - *Where Documented*: `vigen-idaac/vigen_idaac/metrics.py:45-80`, `vigen-idaac/vigen_idaac/analyze.py:88-90`, `vigen-idaac/FINDINGS.md:1356-1386 (F8)`.
   - *Why Misleading*: Once environment workers are staggered across episode phases (R18), in every rollout some workers finish an episode and others do not ($\max=1, \min=0$). The ratio saturates to exactly $1.0$ across all logged rows of healthy runs. Because a dead worker produces the exact same $1.0$, the metric had zero discriminating power, constantly crying wolf on healthy runs while unable to detect true worker death. Replaced by `env/episode_spread_cum`.
2. **`env/worker_imbalance` (from step counts) — Structurally dead / unfireable detector**
   - *Where Documented*: `vigen-idaac/vigen_idaac/metrics.py:45-54`.
   - *Why Misleading*: Computed from worker step counts in a synchronous vectorized environment (`SubprocVecEnv`). Because lock-step workers step exactly together or raise a pipe error, the step delta variance across workers was $0.0$ in every row. `analyze.py` falsely reported the E6 check as "ok" across thousands of updates, mistaking an unfireable detector for a verified healthy system.
3. **`time/fps` (Collection-Only Formulation) — Misleading 2.09x throughput overstatement**
   - *Where Documented*: `vigen-idaac/vigen_idaac/train.py:261-266`, `vigen-idaac/FINDINGS.md:607-620 (R23)`.
   - *Why Misleading*: When calculated as `rollout_size / collect_s`, it excluded the neural network optimization time (which accounts for ~50% of the wall-clock time). This overstated true training speed by 2.09x (logging 195 fps instead of actual 93 fps), corrupting all ETA predictions and making toy architectures appear only 6% cheaper than full models. Corrected to end-to-end FPS `rollout_size / (collect_s + update_s)`.
4. **`iqm` (Interquartile Mean) on `eval-easy` Episode Pools — Biased against transfer / systematically discards generalization signal**
   - *Where Documented*: `vigen-idaac/STATE.md:643-670 (B32)`, `vigen-idaac/PROTOCOL-DIFF.md:368-398`, `vigen-idaac/ALDA.md:1768`, `vigen-idaac/probes/results_table.py:149-167`.
   - *Why Misleading/Biased*: `eval-easy` return distributions across 10 scenes are bimodal and heavily right-skewed: an agent scores near 0 on most scenes and genuinely solves 1–2 scenes (e.g. per-scene returns: `[0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 6.2, 44.3]`). IQM trims the bottom and top 25% of the pooled episodes — thereby discarding precisely the successful transfer episodes. Measured `Mean / IQM` on `eval-easy` is $1.10 - 4.54\times$. Mean sits $41.8\%$ above IQM on median (Axis E3 systematic bias). Demoted from headline to internal robustness check.
5. **10-Scene Aggregate in `train` Mode as Retention Denominator — Conceptually corrupt denominator**
   - *Where Documented*: `vigen-idaac/STATE.md:476, 740-770 (B31)`, `vigen-idaac/probes/results_table.py:86-99`.
   - *Why Misleading*: Training environments never passed `scene_ids`, defaulting to `[0]*num_envs` (`envs.py:265`), so agents trained strictly on scene 0's appearance. The other 9 train scenes are visually distinct configurations never seen during training. Evaluating 10 scenes in `train` mode is already measuring visual generalization. Dividing `eval-easy` by 10-scene train mean computes a ratio of two generalization failures (e.g. `qlae-Door-s0` gave $0.80 / 0.85 = 93.9\%$ retention when true training performance on scene 0 was $87.98$, giving an honest retention of **0.9%**). Correct denominator must be scene 0.
6. **Retention Ratio Without Random-Policy Floor Gating — Conditionally invalid / illusory retention on unlearned policies**
   - *Where Documented*: `vigen-idaac/probes/random_floor.py:1-25`, `vigen-idaac/probes/random_floor_gate.py:50-74`, `vigen-idaac/probes/results_table.py:203-216`.
   - *Why Misleading*: Retention $\frac{\text{eval}}{\text{train}}$ is meaningless when the training denominator cannot be distinguished from an untrained random policy (e.g. `alda-Lift-s1` trained to return 0.11 where a random policy scores 7.80, producing an illusory "131.3%" retention). Retention must be marked `undefined` whenever training return fails to clear `learned_threshold` ($p < 0.025$ above random floor).
7. **Single-Scene (Scene 0) Evaluation Protocol (`Alt.version`) — High variance / sampling noise**
   - *Where Documented*: `vigen-idaac/PROTOCOL-DIFF.md:343-398`, `vigen-idaac/EVAL-PARITY.md:168-192`.
   - *Why Misleading*: Evaluating only scene 0 yields a relative standard error of $\sim 64\%$ of the 10-scene mean on `eval-easy` (spread across scenes reaches 419x within the same checkpoint). Sampling only scene 0 lands $21.5\%$ below the 10-scene mean on median (Axis E1 sampling noise).
8. **`det_stoch_ratio < 0.5` (Deterministic vs Stochastic Action Discrepancy) — Reported score misrepresents trained policy**
   - *Where Documented*: `vigen-idaac/FINDINGS.md:D23`, `vigen-idaac/ALDA.md:766-795`, `vigen-idaac/vigen_idaac/evaluate.py:173-184`.
   - *Why Misleading*: Benchmark protocols evaluate the deterministic policy ($\mu(s)$), but for continuous Tanh-Gaussian policies, $\mu(s)$ can score dramatically lower than sampled actions $\pi(a|s)$ (measured ratios down to 0.33 vs 1.20). When `det_stoch_ratio < 0.5`, the reported score misdescribes the agent's learned capabilities.
9. **`latent/frac_outside_unit` (Univariate Interpretation) — Misleading without latent architecture and codebook context**
   - *Where Documented*: `vigen-idaac/vigen_alda/metrics.py:85-115`, `vigen-idaac/ALDA.md:1639`.
   - *Why Misleading*: (1) In continuous latent models (SAC+AE), latents are unbounded by design; $> 1.0$ fired false alarms within 5k frames. (2) In QLAE with learned codebooks (`train_codebook=True`), the codebook expands to $\approx 7.8$, so $> 1.0$ is not saturation. (3) On training data with a fixed unit codebook, high fraction + dead codes indicates capacity loss; on test data (`eval-easy`), a rise is the OOD associative retrieval mechanism functioning as designed.
10. **Critic Q1 Overestimation Ratio (`q1 / ret` Early in Training) — False alarm during policy improvement**
    - *Where Documented*: `vigen-idaac/vigen_alda/metrics.py:149-156`.
    - *Why Misleading*: Q-values estimate discounted infinite-horizon future returns, so $Q_1 \gg \text{return}$ (e.g. 10x) is normal and expected early in training while the policy is actively improving. It is only pathological if returns have stalled/plateaued and Q-values continue to diverge.
11. **`health/nonfinite > 0` as a Logged Row Alarm — Structurally unreachable in logs**
    - *Where Documented*: `vigen-idaac/vigen_idaac/algo.py:126-128, 240-245`.
    - *Why Misleading*: Any non-finite loss immediately raises `NonFiniteLoss` exception before `row` construction, so the logged CSV field is always 0.0. The logged field cannot catch NaNs post-hoc; the exception is the true detector.
12. **Global Module `grad_norm/*` — Stale and misattributed gradient norms**
    - *Where Documented*: `vigen-idaac/vigen_idaac/algo.py:135-144`.
    - *Why Misleading*: Measuring all module gradient norms after policy backward misattributed stale value gradients from prior updates to `grad_norm/value` and discarded confusion gradients to `grad_norm/disc`. Each module must be measured immediately after its own backward.
13. **`eval/success_rate` (Binary Success Rate) — Insufficient and uninformative on continuous manipulation**
    - *Where Documented*: `vigen-idaac/RL-ViGen-README.md`, `vigen-idaac/FINDINGS.md:I5`, `CONTEXT.md`.
    - *Why Misleading*: Binary 0/1 success rates discard shaped distance/reach/grasp progress on robosuite Lift and Door, providing zero gradient or diagnostic visibility into partial task competency.
