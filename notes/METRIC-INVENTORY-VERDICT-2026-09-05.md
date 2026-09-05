# Metric inventory verdict — 2026-09-05

Scope: for each of the twelve baselines, what is actually logged, at what cadence, under what
formula, and where a name collides with another baseline's (or the same baseline's own) different
quantity. This extends `docs/PART2-METRIC-INVENTORY.md` (read in full, 508 lines) and
`docs/CONSTRUCTION.md` C28 (read in full) — it does not repeat what they already established
(success-rate delivery, frame-stack 8/4 split, the three action-distribution families, the
ppg k2-vs-k3 precedent) except where a re-read of the live code changes or corrects those claims.

Every row below is from reading the emitting code directly, tonight, in this pass. Where I am
repeating a PART2 claim rather than re-deriving it, it is marked. `$MG` =
`many-gens-rl-vigen`; all paths are relative to it unless absolute.

The orchestrating session's own finding tonight (`runnable/dmc_gb/src/algorithms/sac.py`:
`current_Q1`/`current_Q2`/`target_Q` and `entropy`/`log_std`/`actor_Q` computed and never logged,
now fixed) is the template for most of what follows: it is one instance of a pattern that recurs,
at larger scale, in `idaac` and `alda`.

---

## 1. `rad`, `soda` — `runnable/dmc_gb/src/algorithms/{sac,rad,soda}.py`

Both inherit `SAC.update_critic` / `SAC.update_actor_and_alpha` unchanged; `rad.py` adds nothing;
`soda.py` adds `update_soda`. Re-verified against the CURRENT file state (post-fix), not assumed.

| metric | logged? | cadence / condition | formula (file:line) | collisions |
|---|---|---|---|---|
| `train_critic/loss` | Y | every update (`agent.update` called every step once `step >= init_steps`) | `F.mse_loss(Q1,target_Q)+F.mse_loss(Q2,target_Q)`, `target_Q = r + not_done·γ·(min(tQ1,tQ2) − α·log_pi)` — soft/entropy-regularised — `sac.py:93-95` | **False cognate** with `drqv2`/`svea`/`sgqn`'s `critic_loss` (no entropy term there). True cognate with `alda`'s `critic_loss` (identical formula). See Cross-cutting #2. |
| `train_critic/q1`, `q2`, `target_q` | Y (fixed tonight) | every update | `current_Q1.mean()`, `current_Q2.mean()`, `target_Q.mean()` — `sac.py:103-105` | Same *kind* of quantity (mean Q over the sampled minibatch) as `drqv2`-family's `critic_q1/q2/target_q`, but the target includes the entropy term here and does not there — the Q-values themselves are comparable, the target is not. |
| `train_actor/loss` | Y | every `actor_update_freq` steps (=2 typically) | `(α·log_pi − actor_Q).mean()` — `sac.py:116,119` | — |
| `train_actor/entropy` | Y (fixed tonight) | every `actor_update_freq` steps | `0.5·dim·(1+ln 2π) + Σ log_std` — **entropy of the pre-tanh Gaussian, ignoring the tanh-squash Jacobian** — `sac.py:120-121,128` | **False cognate** with `drqv2`-family's `actor_ent` (see Cross-cutting #6). True cognate with `alda`'s `train/actor_entropy` (byte-identical formula). |
| `train_actor/log_std` | Y (fixed tonight) | every `actor_update_freq` steps | `log_std.mean()` — `log_std` is a **state-dependent** network output, bounded via `tanh`-rescale into `[log_std_min, log_std_max]` (`modules.py:196-200`), not a hard clamp | Compare to `idaac`/`ppg`/`ibac_sni`/`ctrl`'s `mean_log_std`, which is a **state-independent global bias** — see Cross-cutting #8. |
| `train_actor/q` | Y (fixed tonight) | every `actor_update_freq` steps | `min(actor_Q1,actor_Q2).mean()` | — |
| `train_alpha/loss`, `train_alpha/value` | Y | every `actor_update_freq` steps, only if `update_alpha` (always True on this call path) | standard SAC dual-ascent on `log_alpha` — `sac.py:138,142` | — |
| `train/aux_loss` (soda only) | Y | every `aux_update_freq` steps | `F.mse_loss(normalize(h0),normalize(h1))`, SODA's predictor-vs-target-encoder consistency — `soda.py:47,65` | Name collides with the *console format string's* generic `AUXLOSS` column (`logger.py:13`); not a cross-baseline collision since only `soda` populates it. |
| `eval/episode_reward{,_test_env}`, `eval/success_rate{,_test_env}` | Y | every `eval_freq` steps, at episode boundary | raw sum of `env.step` reward; success = `_check_success()` held at any step | Matches project-wide convention (PART2 §1). |
| `target_network_divergence` | **N — never computed** | — | — | Confirmed absent by direct grep (`target.*diverg`, `param_distance`) across all of `runnable/`, not just this baseline — re-verified myself, matches PART2. |

**Cadence subtlety, confirmed by reading `logger.py` and `train.py` together:** `L.log()` accumulates
into an `AverageMeter` on every call; `L.dump(step)` — which writes the JSON row and **clears every
meter** — fires only inside `if done:` (episode boundary), so every train-side number in
`train.log` is a **mean over the whole episode's updates since the last dump**, not a per-update
value. Separately, **console printing is gated by `FORMAT_CONFIG['rl']['train']`**
(`logger.py:7-20`), which lists only `episode, step, duration, episode_reward, actor_loss,
critic_loss, aux_loss` — none of the six metrics fixed tonight (`q1,q2,target_q,entropy,log_std,q`)
ever reach the console/stdout log, only the JSON file. "Reaches a record" is true for all of them
(the JSON file is a record); "visible without opening the JSON" is false for six of nine train-side
keys. This is the same shape as the pre-2026-08-20 RL-ViGen bug (C57, see Cross-cutting #9) where a
metric present in the dict but absent from the *print* format was effectively invisible for 70,000
frames of a NaN divergence — here it is visible in the file, but only because the fix explicitly
put it under keys `L.log()` already writes to file regardless of the console format list.

---

## 2. `alda` — `runnable/alda/trainers/alda_trainer.py` (+ `third_party/alda/models/sac.py`)

**This is the largest finding in this pass, and it overturns tonight's own earlier claim that alda
is "the richest-logged baseline."** That claim is true of what alda's trainer *computes*; it is
false — nearly the opposite — of what reaches a record, because of exactly the failure class the
brief asked me to hunt: computed, aggregated, and then dropped, silently, every `log_every` steps,
for the entire life of every alda run this project can launch.

The actual model code (`third_party/alda/models/sac.py`, resolved via the launcher's `ln -sfn`
into `ALDA_MODELS_PATH`, **not** the vendored `dmcontrol_generalization_benchmark/src/algorithms/`
copy that `alda_trainer.py` never imports) is the same SAC-squashed-Gaussian family as `rad`/`soda`:
same `squash()`, same `gaussian_logprob`, same `tanh`-rescaled state-dependent `log_std`, same
entropy formula. Verified line-for-line identical to `dmc_gb`'s `modules.py` `Actor.forward`.

| metric | logged? | cadence / condition | formula (file:line) | collisions |
|---|---|---|---|---|
| `train/critic_loss` | **N — computed, discarded** | accumulated every update into `self.logging_info` (`alda_trainer.py:357`), averaged every `log_every=500` steps (`:630-633`), then `wandb.log(...)` **only if `self.use_wandb`** (`:636`) — and `runnable/_launch/alda.sh` passes **`--use_wandb False`** unconditionally — then `self.logging_info.clear()` (`:639`) regardless. No other sink exists for this key. | same formula as `dmc_gb` SAC (`sac.py:93-95` shape) — `alda_trainer.py:354-355` | Would be a true cognate with `rad`/`soda`'s `train_critic/loss` if it reached a record; it does not. |
| `train/actor_loss`, `train/actor_entropy`, `train/alpha_loss`, `train/alpha_value` | **N — same discard** | same as above | same formulas as `dmc_gb` SAC — `alda_trainer.py:375-392` | `train/actor_entropy` formula is byte-identical to `rad`/`soda`'s `train_actor/entropy` — but neither reaches a record for alda, so the "same quantity" fact is moot in practice. |
| `alda/total_loss`, `commitment_loss`, `quantization_loss`, `bce_loss`, `psnr` | **N — same discard** | same | ALDA's own auxiliary latent-model losses — `alda_trainer.py:483-488` | Singleton to alda; no cross-baseline collision, but this is ALDA's own algorithmic contribution (the quantized-latent autoencoder) and none of its diagnostics survive. |
| `grad_norms/critic_max`, `actor_max`, `encoder_max`, `decoder_max` | **N — same discard**, AND gated off by default (`log_grad_norm: bool = False`, `alda_trainer.py:33`) — double-gated | — | — | — |
| `train/episode_reward` | **N — same discard** | `alda_trainer.py:621` | raw episode return | This means alda's **training-curve return itself** — not just its diagnostics — never reaches a record. Only `eval/episode_reward{,_distracting,_color}` survives, via a separate path (below). |
| `eval/episode_reward{,_distracting,_color}`, `eval/success_rate{,_distracting,_color}` | **Y** | every `eval_n_steps=10,000` steps, at episode boundary, 10 episodes/regime | printed via `logger.info(...)` directly (`alda_trainer.py:562-563`) — **this is a second, independent emission path from `self.logging_info`**, using Python's `logging` module rather than the `wandb.log`/`logging_info` mechanism | Confirmed against the project's own parser: `datasphere/native/normalize_curves.py`'s `read_alda` uses `ALDA_LINE = re.compile(r"alda: (eval/[a-z_]+): ([-\d.]+)")` (`:284`) — it matches **only** lines starting `alda: eval/`, i.e. exactly and only these eight keys. Nothing from `self.logging_info` is ever parsed back. |

**Root cause, precisely:** `alda_trainer.py:602-639`'s `train()` loop populates `self.logging_info`
unconditionally (every `update_critic`/`update_actor_and_alpha`/`update_alda` call), reduces it to
a per-key mean every `log_every` steps (`:630-633`), and the **only consumer of that reduced dict**
is `if self.use_wandb: wandb.log(self.logging_info)` (`:636-637`). `.clear()` (`:639`) runs whether
or not the `if` fired. `runnable/_launch/alda.sh`'s only invocation of `scripts/train.py` passes
`--use_wandb False` on both its branches (with and without `--spec_overrides`). This was already
half-documented in PART2's 2026-09-04 correction ("alda writes no sink at all" because
`--use_wandb False`) — **but that correction was about the offline wandb-JSONL sink specifically,
and did not say what I am saying here: the discard happens one layer up, inside `alda_trainer.py`
itself, before wandb is even reached, and it swallows `train/episode_reward` along with every
diagnostic.** PART2's framing ("alda's metrics reach the record set through its console log") is
true only for the eight `eval/*` keys; it is silent on the rest, and reading it without checking
`alda_trainer.py:628-639` directly would leave the false impression that alda's per-update
diagnostics simply weren't inventoried yet, rather than that they are computed and destroyed on a
fixed 500-step cycle for the run's entire duration.

---

## 3. RL-ViGen five — `drqv2`, `svea`, `sgqn`, `curl`, `drq` (`RL-ViGen-upstream/algos/*.py`, `train.py`, `logger.py`)

**Correction to PART2 Finding 6, verified by reading the actor architecture of all five, not four
plus an inference:** `drq` does **not** belong in the "DrQv2 squashed mean + truncated noise"
family PART2's table places it in. Its `Actor` (`algos/drq.py:135-152`) builds a genuine
`SquashedNormal` (`TransformedDistribution` with a `TanhTransform`, `algos/drq.py:83-113`) from a
**learned, state-dependent** `log_std` bounded by `tanh`-rescale (`:149-152` — the identical
mechanism to `dmc_gb`/`alda`'s SAC actor), with a learned entropy temperature `alpha`/`log_alpha`
and `target_entropy` (`:200-210`). `self.stddev_schedule` / `self.stddev_clip` are stored
(`:197-198`) but **never read anywhere else in the file** — confirmed by grep, zero further
references — vestigial constructor-signature plumbing carried over from a shared factory call, not
used by `drq`'s actual actor. `drq` architecturally belongs with `rad`/`soda`/`alda`, not with
`drqv2`/`svea`/`sgqn`/`curl`. **The project's own code already knows this and says so more
precisely than PART2's table does**: a `P17` patch comment inside `drq.py:326-334` explicitly
states the actor "returns a SquashedNormal ... which has no closed-form entropy" and that
`-actor_logprob` is "the Monte-Carlo entropy of a squashed policy, not the analytic Gaussian
entropy drqv2/svea/sgqn/curl report under that name" — this correction was made at the point-fix
level in 2026 but never propagated back into Finding 6's family table.

| metric | logged? | cadence | formula (file:line) | collisions |
|---|---|---|---|---|
| `critic_target_q`, `critic_q1`, `critic_q2` (all five) | Y | every `update_every_steps` (all five compute `metrics` only when `step % update_every_steps == 0`, else return `{}`) | `target_Q.mean()`, `Q1.mean()`, `Q2.mean()` on the **unaugmented, unmasked** obs/action in every case, including `svea`/`sgqn` — `drqv2.py:191-194`, `svea.py:244-247`, `sgqn.py:174-177` (`sgqn`'s `Q1,Q2` are pre-mask), `curl`/`drq` inherit or duplicate the same shape | **True cognate** across all five for the Q-value readouts themselves (same formula, same obs). See next row for why `critic_loss` is not. |
| `critic_loss` (all five) | Y | same | **Four different formulas under one name** — see Cross-cutting #2 for the full breakdown: `drqv2` plain MSE (no entropy term); `svea` = `0.5·(unaug MSE + strong-overlay-aug MSE)` (`svea.py:236-239`); `sgqn` = base MSE `+ 0.9·(mse(Q1,maskedQ1)+mse(Q2,maskedQ2))` (`sgqn.py:169-172`); `curl`/`drq` inherit `drqv2`'s or compute their own dual-augmentation-averaged, entropy-inclusive version (`drq.py:274-283`, since `drq` is SAC-family) | **False cognate**, the single widest-reaching one found (8 of 12 baselines if `rad`/`soda`/`alda` are folded in — see Cross-cutting #2). |
| `actor_loss` (all five) | Y | same | `-Q.mean()` (drqv2/svea/sgqn/curl, deterministic) vs `(α·log_prob − Q).mean()` (drq, SAC-style) | Two different objectives under one name, tracking the architecture split above. |
| `actor_logprob` (all five) | Y | same | `dist.log_prob(action).sum(-1)` — for drqv2/svea/sgqn/curl, `dist` is `TruncatedNormal(pyd.Normal)`, which **does not override `log_prob`**, so this is the base untruncated Normal's density evaluated at a sample that was separately noise-clipped (`stddev_clip`) and hard-clamped to the box (`_clamp`, `utils.py:112-115`) — the number is not the log-density of the distribution that actually produced the executed action. For `drq`, `log_prob` is the exact `SquashedNormal` (TransformedDistribution) density, correctly accounting for the tanh Jacobian. | See Cross-cutting #6. |
| `actor_ent` (drqv2, svea, sgqn, curl — **not** drq, deliberately removed by patch P17) | Y | same | `dist.entropy().sum(-1)` where `dist = TruncatedNormal(mu, std)`, `std = ones_like(mu) * schedule(step)` — **a scalar broadcast from a deterministic, non-learned exploration-noise schedule, identical for every state and every batch element at a given step.** Entropy of `Normal(mu,std)` does not depend on `mu`, so this number is a **pure, precomputable function of `step` alone**, carrying zero information about the learned policy. | **False cognate, high severity** — see Cross-cutting #6. Contrast with `train_actor/entropy` (rad/soda/alda) and `mean_log_std`/`entropy` (idaac/ppg/ibac_sni/ctrl), both of which move with training. |
| `batch_reward` (all five) | Y | same | `reward.mean()` over one **replay-buffer minibatch** (drqv2/svea/sgqn) or the just-sampled batch (curl/drq) — **not** an episode return | Minor false-cognate risk against `episode_reward`; see Cross-cutting #13. |
| `curl_loss` (curl only) | Y | inherits `update()`, calls `update_curl` every update | `F.cross_entropy(logits, arange(B))`, InfoNCE-style — `curl.py:97,106` | Singleton. |
| `eval/episode_reward` (`R`), `eval/success_rate` (`SR`), `train_regime_reward`, `train_regime_success` | Y | every `eval_every_frames`, via `_eval_regime`/`_eval_single` (P14) | — | Matches PART2 exactly; re-verified `train.py:143-227`, no change. |
| `aug_Q1`, `aug_Q2` (svea) | **N — computed, dropped** | every update | `self.critic(aug_obs, action)` — used to build `aug_loss` (folded into `critic_loss`) but never logged on their own — `svea.py:236-238` | Minor: means SVEA's critic-loss decomposition (how much of the loss comes from the augmented-view term vs the clean term) is not separately inspectable, only the summed `critic_loss`. |
| `aux_loss` from `update_aux` (sgqn) | **N — never returned, never logged, not even computed under any diagnostic gate** | every update, unconditionally | `F.binary_cross_entropy_with_logits(attrib, mask)` in `compute_attribution_loss` — `sgqn.py:151-155,191-198,242` — `update_aux` has **no `return` statement at all**, so the loss value is discarded the instant the function returns | See Cross-cutting #5 — this is SGQN's own defining auxiliary task (attribution-consistency), computed and backpropagated every update, entirely invisible in any log. |
| `target_network_divergence` | **N — never computed**, all five | — | — | Confirmed absent, matches PART2/dmc_gb. |

**Cadence:** `logger.log_metrics(metrics, frame, ty='train')` fires **every update** (every step once
past `num_seed_frames`), feeding a `MetersGroup` exactly like `dmc_gb`'s; `dump()` — which writes
the CSV row and clears meters — fires only at episode end (`train.py:289-299`, `time_step.last()`).
So every train-side CSV row is a **per-episode mean over however many updates fell in that
episode**, matching the dmc_gb cadence shape exactly. Console printing is gated by
`COMMON_TRAIN_FORMAT` (`logger.py:19-23`: `frame, step, episode, episode_length, episode_reward,
buffer_size, fps, total_time`) — **none** of the RL diagnostics (`critic_loss`, `actor_ent`, etc.)
ever print; they reach only `train.csv`. This is the exact mechanism C57 (`docs/CONSTRUCTION.md`)
already burned once: before 2026-08-20 `use_tb` defaulted such that these dict entries were never
even populated (they are gated by `if self.use_tb:` inside every one of the five `update()`
methods), so `train.csv` itself carried only the common columns and a NaN divergence in
`critic_loss` went unnoticed for 70,000 frames. `runnable/_launch/rlvigen.sh:68-76` now forces
`use_tb=True` for exactly this reason — confirmed still in effect, re-read tonight.

---

## 4. `idaac` — `runnable/idaac/train.py`, `ppo_daac_idaac/algo/{idaac,daac}.py`

**Second-largest finding in this pass.** `algo/idaac.py::update()` returns a 7-tuple —
`(order_acc_epoch, order_loss_epoch, clf_loss_epoch, adv_loss_epoch, value_loss_epoch,
action_loss_epoch, dist_entropy_epoch)` (`idaac.py:191-194`) — computed fresh every training
iteration `j` (every call to `agent.update(rollouts)`, unconditional, not gated by any interval).
`train.py:278-279` destructures all seven into local variables. **Grepped the whole file: none of
the seven names appear anywhere else.** They are computed, unpacked, and dropped, every iteration,
for the run's entire duration — across all three `--algo` variants this file supports (`ppo`,
`daac`, `idaac`; confirmed the same shape in `algo/daac.py:140-141`'s 4-tuple return and its
matching unused destructuring at `train.py:281`). This includes the standard PPO **value loss** and
**clipped policy-surrogate loss** — not just IDAAC's own novel order-classifier/advantage-loss
diagnostics — so a reader of `idaac`'s log never sees either of the two most basic PPO losses.

| metric | logged? | cadence / condition | formula (file:line) | collisions |
|---|---|---|---|---|
| `value_loss`, `action_loss`, `dist_entropy` | **N — computed every iteration, never logged** (all three `--algo` variants) | `train.py:278-283` destructures, never re-referenced | `value_loss`: PPO2 clipped `0.5·max((v−ret)²,(v_clip−ret)²)` — `idaac.py:167-173`. `action_loss`: clipped surrogate `-min(r·A, clip(r,1±ε)·A)` — `idaac.py:108-113`. `dist_entropy`: `self.actor_critic.evaluate_actions(...)`'s returned entropy, presumably the acting distribution's `.entropy()` (Gaussian, global `log_std` bias — see below) | `value_loss`'s formula is a **true cognate** of `ibac_sni`'s and `ctrl`'s `value_loss` (same PPO2 clip shape) — see Cross-cutting #14 — but since it never reaches a record here, the cognate relationship is moot in practice, same as `alda`'s dead `critic_loss`. |
| `order_acc`, `order_loss`, `clf_loss`, `adv_loss` | **N — same discard** | `idaac.py:59-194` | IDAAC's own instance-order classifier accuracy/BCE-loss and advantage-prediction loss — the algorithm's defining mechanism | Singleton; no cross-baseline collision, but this is IDAAC's central algorithmic contribution and none of it reaches a record. |
| `train/clip_fraction`, `train/approx_kl_k3` | **Y**, but see cadence note | `j % log_interval == 0 and len(episode_rewards) > 1` (`train.py:339,364-366`) | `clip_fraction = mean(\|ratio−1\|>clip_param)` (`idaac.py:135-136`) — **identical formula** to `ppg`'s native `clipfrac` and to `scripts/metrics.py::clip_fraction` once the latter's log-ratio input is exponentiated (see Cross-cutting #10). `approx_kl_k3 = mean((ratio−1)−log ratio)` — algebraically identical to `scripts/metrics.py::approx_kl(...,"k3")`. | Genuinely comparable to `ppg`'s and `ibac_sni`'s equivalents (same k3 estimator, same clip-fraction threshold) — a rare confirmed **true** cognate. |
| `train/sigma_mean`, `train/mean_log_std`, `train/boundary_fraction` | Y, same gate | same gate as above | `_policy_health(logstd._bias)` where `logstd` is a plain `AddBias(zeros)` — a **global, state-independent** scalar-per-action-dim parameter, no clamp (`train.py:376-381`) | See Cross-cutting #8: same function (`gaussian_policy_health`) as `ppg`/`ibac_sni`/`ctrl`, but a categorically different kind of input than `rad`/`soda`/`alda`/`drq`'s per-state, per-batch `log_std`. |
| `train/mean_episode_reward`, `test/mean_episode_reward`, `test/success_rate` | Y | same gate | `info['episode']['r']` via baselines' `VecMonitor`; success = `_check_success()` any-step, matching project convention | — |
| `target_network_divergence` | N/A — no target network (on-policy) | — | — | — |

**Cadence, precisely, and this is a genuine finding of its own:** `clip_fraction`/`approx_kl_k3`
are recomputed as an **epoch-mean inside `update()`** every single iteration
(`clip_fraction_epoch /= num_policy_updates`, `idaac.py:141-144`), then **overwritten** on
`self.last_clip_fraction`/`self.last_approx_kl_k3` every iteration regardless of whether that
iteration's value will ever be read. `train.py` only *reads* those attributes once every
`log_interval` iterations. So the logged number is the epoch-mean of the **single most recent
update before the log boundary**, not a mean over the `log_interval`-many updates that occurred
since the last log — a **point sample of a window, not a window average**. This is the same shape
as `ibac_sni`'s cadence (Cross-cutting #9) and differs from `dmc_gb`/RL-ViGen's true running-mean
cadence.

---

## 5. `ppg` — `runnable/ppg/phasic_policy_gradient/{ppo,ppg,train,distr_builder,minibatch_optimize}.py`

Confirmed `PART2`'s claim that `ppg`'s continuous head uses a **state-independent** `log_std`
(`ppg.py:113-116`, `pi_logstd` is `nn.Parameter(zeros(pi_outsize))`, broadcast onto every batch
element — `ppg.py:154`), and that it is the only one of the four PPO-family baselines that
**clamps** it (`distr_builder.py:31`, `.clamp(-5.0, 2.0).exp()`).

| metric | logged? | cadence | formula (file:line) | collisions |
|---|---|---|---|---|
| `Opt/approxkl` (native) | Y | `epoch_stats[-1]` — mean over **all minibatches of the last epoch** of `train_pi`/`train_pi_and_vf` this iteration (`minibatch_optimize.py:56-69`, `dict_mean` over `mb_dicts`, not a last-minibatch snapshot — corrected from an initial misreading of `epoch_stats[-1]` during this pass) | Schulman **k2**: `0.5·(log ratio)²` — `ppo.py:147` | **False cognate** with `Opt/approx_kl_k3` right beside it — already the canonical example in PART2/CONSTRUCTION C28, re-verified unchanged. |
| `Opt/approx_kl_k3` (ours) | Y | same | k3: `(ratio−1)−log ratio` — `ppo.py:153` | True cognate with `idaac`'s and `ibac_sni`'s `approx_kl_k3` (identical formula). |
| `Opt/clipfrac` | Y | same | `mean(\|ratio−1\|>clip_param)` — `ppo.py:146` | True cognate with `idaac`'s `clip_fraction` (see Cross-cutting #10) — **identical formula**, contrary to PART2's suggestion of a log-ratio-based difference. |
| `Opt/entropy` | Y | same | `sum_nonbatch(pd.entropy()).mean()`, `pd = Normal(mu, clamp(logstd,-5,2).exp())` — `ppo.py:137`, `distr_builder.py:27-32` | Same closed-form as `diag_gaussian_entropy` since `log_std` is state-independent (entropy is a constant given the parameter, batch-averaging is a no-op in expectation). **Not the same measurement instant** as `train/entropy` below — see note. |
| `train/entropy`, `train/mean_log_std`, `train/sigma_mean`, `train/boundary_fraction` | Y | **once per rollout iteration**, inside `compute_advantage`, called **before** that iteration's optimizer steps run (`ppo.py:87-95`) | `_policy_health(clamped log_std)` — same function as `idaac`/`ibac_sni`/`ctrl` | Same formula as `Opt/entropy` above, but a **pre-update snapshot** (parameter value at the end of the *previous* iteration) vs `Opt/entropy`'s **post-most-of-this-iteration** snapshot (last epoch's minibatch mean, i.e. after several gradient steps have already moved `log_std`). Not a bug, but a real point-in-time mismatch a naive diff between the two columns would not explain. |
| `train/log_std_raw_mean`, `train/log_std_clamped_fraction` | Y | same | raw (unclamped) parameter mean; fraction of components where `raw != clamped` — `ppo.py:93-95` | Singleton to `ppg` (the only clamping baseline of the four) — this is exactly the C61 "silent saturation" signal, correctly separated from the clamped-value keys per the file's own comment. |
| `scaled/pol_distance`, `unscaled/pol_distance` (aux phase) | Y | every aux-phase minibatch, `n_aux_epochs=6` full passes | **`td.kl_divergence(oldpd, pd)`** — the exact closed-form KL between two full Gaussian policies (old vs. new, post-PPO-phase) — `ppg.py:203-204,211-212` | **A third, unrelated "KL" in the same baseline** — see Cross-cutting #12. Not an importance-ratio estimate at all; a distributional distance between two policies (a "how far did the policy move during the whole PPO phase" question), not "how far is this update's ratio from 1." |
| `unscaled/vf_aux`, `unscaled/vf_true` (aux phase) | Y | same | `0.5·(vpredaux−vtarg)²`, `0.5·(vpredtrue−vtarg)²` — `ppg.py:121-123` | — |
| `loss_pi`, `loss_vf` (via `diags.update({f"loss_{k}":...})`) | Y | every PPO-phase update | `losses["vf"] = vfcoef·(vpred−vtarg)².mean()` — **plain, unclipped MSE**, no PPO2 value-clip term at all | **False cognate** against `idaac`/`ibac_sni`/`ctrl`'s clipped value loss — see Cross-cutting #14. |
| `VFStats/EV` | Y | every rollout iteration | `explained_variance(vpred, vtarg)` via `tu.explained_variance` (ppg's own, not `scripts/metrics.py`'s — not re-verified for numeric identity in this pass, see thin-evidence) | — |
| `EpRewMean`, `EpLenMean`, `EpSuccessMean`, `Misc/InteractCount` | Y (per PART2, not re-derived here) | via `Roller`/`VecMonitor2`, `LogSaveHelper` | — | Not re-read this pass; relying on PART2's Finding 4/6 characterization (train-distribution only, no eval env). |

---

## 6. `ibac_sni` — `runnable/ibac_sni/torch_rl/{scripts/train.py, torch_rl/torch_rl/algos/ppo.py, model.py, bottleneck.py}`

**Single highest-severity same-name-different-quantity finding in this whole pass**, and it is
*within one baseline's own adjacent log columns*, not just across baselines.

`logs["kl"]` (native to this repo, `algos/ppo.py:169-173`) is **not** a policy-update KL at all.
Traced through `self.acmodel.compute_train(sb.obs)` → `self.encode(obs)`
(`model.py:260-274,297-309`): under this project's actual launch flags (`--use_bottleneck
--sni_type vib`, `runnable/_launch/ibac_sni.sh:134`), `kl = torch.sum(reg_layer(embedding)[2],
dim=1)` where `reg_layer` is a `Bottleneck` (`bottleneck.py:20-45`) computing
`kl_divergence(Normal(mu, softplus(std)), Normal(0,1))` per latent dimension, summed — the
**variational-information-bottleneck KL** between the stochastic encoder's posterior and a
standard-normal prior, downweighted in the loss by `beta=1e-4` (`ppo.py:118`,
`runnable/_launch/ibac_sni.sh:113-134`, a value the launcher's own comment calls "a REPAIR, not a
new choice"). **Depending on flags this project does not use by default, `kl` can instead be an L2
penalty on activations (`use_l2a`: `kl = sum(bot**2)`, `model.py:268`) or an identical-zero
placeholder (`sni_type='dropout'`/`None`: `kl = torch.Tensor([0])`, `model.py:270`)** — so even
within `ibac_sni`'s own native code, "kl" denotes three structurally different objects depending on
a config flag, and **none of the three is a policy-trust-region divergence**.

This project's own C28 addition then logs `approx_kl_k3` — a genuine importance-ratio PPO KL — in
the **same printed line**, one column later. Confirmed at the literal format-string level:

```
"U {} | F {:06} | FPS {:04.0f} | D {} | rR:μσmM {:.2f} {:.2f} {:.2f} {:.2f} | F:μσmM {:.1f} {:.1f} {} {} | H {:.3f} | V {:.3f} | pL {:.3f} | vL {:.3f} | ∇ {:.3f} | kl {:.3f} | SR {:.3f} | clipf {:.3f} | kl3 {:.4f}"
```
(`scripts/train.py:289`) — a reader sees `kl` and `kl3` four tokens apart on one console line and
has every reason to assume `kl3` is a refined estimate of `kl`. It is not: they are not estimates
of the same divergence, and one of them (`kl`) is not always even a KL divergence.

| metric | logged? | cadence | formula (file:line) | collisions |
|---|---|---|---|---|
| `kl` (native) | Y | `update % log_interval == 0`, single most-recent-update snapshot (see cadence note) | VIB bottleneck KL (see above); NOT a policy KL | **False cognate, highest severity found** — see Cross-cutting #1. |
| `clip_fraction`, `approx_kl_k3` (ours) | Y | same gate | over `diag_ratio` — **the acting distribution's ratio** (`ratio_r` when `sni_type='vib'`, since SNI computes two: `ratio_r` from `dist_run`/acting, `ratio_t` from `dist_train`; `ppo.py:99-104`, declared choice per PART2 §6, re-verified unchanged) | True cognate with `idaac`'s and `ppg`'s (identical formula). |
| `entropy` (`H` in console) | Y | same | `sni_type='vib'`: **`(dist_run.entropy() + dist_train.entropy())/2`** — a 50/50 mix of the acting and training passes' entropies (`ppo.py:96`); `sni_type=None/dropout`: single `dist.entropy()` (`:79`) | Confirms PART2's existing claim unchanged; re-derived directly rather than trusted. |
| `value`, `policy_loss`, `value_loss`, `grad_norm` | Y | same | `value_loss`: PPO2 clipped, `0.5·max((v−ret)²,(v_clip−ret)²)` — `ppo.py:88-91` | `value_loss` **true cognate** with `ctrl`'s and `idaac`'s (unlogged) `value_loss` — same formula, see Cross-cutting #14. |
| `sigma_mean`, `mean_log_std`, `boundary_fraction` | Y, gated `if getattr(acmodel,"log_std",None) is not None` | same | `_policy_health(acmodel.log_std)`, global unclamped bias | Same function as `idaac`/`ppg`/`ctrl`; unclamped (only `ppg` clamps). |
| `success_rate` | Y | same | mean of a 0/1 indicator, any-step convention | — |

**Cadence:** identical shape to `idaac` — `algo.update_parameters()` runs every iteration and
internally averages over `self.epochs × minibatches` (`numpy.mean(log_entropies)` etc., `ppo.py:
41-176`), but the **print/CSV/TB write** only happens every `log_interval` updates
(`scripts/train.py:231-232`), using whichever `logs` dict resulted from the single most recent
`update_parameters()` call — again a point sample of the window's last update, not a mean over the
window. CSV header/row (`scripts/train.py:296-303`) and optional TensorBoard (`:305-307`) both
receive the full field list, so nothing here is print-only-invisible the way `dmc_gb`'s extra
fields are — this baseline's completeness (once past the `kl`/`kl3` naming hazard) is good.

---

## 7. `ctrl` — `runnable/ctrl/{train_ppo.py, algo.py, models.py}` (JAX)

**Correction to PART2's 2026-08-19 claim "`ctrl` is not wired [for C28]."** As of the current code,
it is: `algo.py::loss_actor_and_critic` (used by `update_ppo`, the path the launcher's default
`--algo ppo_ctrl` actually takes — confirmed via `train_ppo.py:96` `flags.DEFINE_enum("algo",
"ppo_ctrl", ...)`) computes and returns `clip_fraction`/`approx_kl_k3` as part of its aux tuple
(`algo.py:340-350`), explicitly commented `[OURS] C28`, and `update_ppo` forwards both into
`avg_metrics_dict` (`:411-412`), which `train_ppo.py:347-360` folds into the dict passed to
`wandb.log`. This is either a later patch that was never back-ported into PART2's §6 prose, or
that prose is simply stale — either way, the document as it stands overstates ctrl's gap.

**But the wiring is conditional in a way worth stating precisely:** the sibling loss function
`loss_actor_and_gae` (used by `update_daac`, reachable via `--algo daac_ctrl` per the launcher's
own comment `# the repo also ships ppo / daac / daac_ctrl`) computes the identical `ratio`
(`algo.py:293-295`) but its return tuple (`:305`) has **no** `clip_fraction`/`approx_kl_k3` at all.
Under the project's actual default flag this does not bite — but the diagnostic is not
structurally guaranteed the way `idaac`'s/`ibac_sni`'s is; it would silently vanish under
`--algo=daac_ctrl` despite `algo.py` "having" the wiring. Not exercised or re-verified against an
actual `daac_ctrl` run in this pass (see thin-evidence).

| metric | logged? | cadence | formula (file:line) | collisions |
|---|---|---|---|---|
| `total_loss`, `value_loss`, `loss_actor`, `ent` | Y | every rollout (`step % (n_steps+1)==0`) | `value_loss`: PPO2 clipped, same shape as `ibac_sni`/`idaac` — `algo.py:270-273`. `ent = pi.entropy().mean()`, `pi` a `tfd.MultivariateNormalDiag` over a **global, state-independent** `log_std` param (`models.py:129,179,254,322`), unclamped. | `value_loss` true cognate with `ibac_sni`. `ent` architecture matches `idaac`/`ppg`/`ibac_sni`'s global-bias family, not `rad`/`soda`/`alda`/`drq`'s per-state family. |
| `clip_fraction`, `approx_kl_k3` | Y (default algo only — see above) | same | identical k3/ratio-threshold formulas to `idaac`/`ppg`/`ibac_sni` | True cognate, conditional on `--algo` containing `"ppo"`. |
| `proto_loss`, `myow_loss` (CTRL's own clustering objective) | Y | same rollout cadence, separate `wandb.log` call gated on `"ctrl" in FLAGS.algo` (true by default) | from `update_cluster`/`loss_cluster` — `algo.py:526-585` | Singleton; fully forwarded, no drop found. |
| `sigma_mean`, `mean_log_std`, `boundary_fraction`, etc. (`train/*`) | Y, gated on `_find_log_std(params)` returning non-None | same | `_policy_health` — same function as the other three PPO-family baselines — `train_ppo.py:355-360` | Same collision class as above. |
| `Eprew200` (`ep_return_200`), `ep_return_all`, console `Eprew0`/`SR_ID`/`SR_OOD` | Y (console: only these 4, per PART2, re-confirmed) | every rollout | `ep_return_200` = rolling `info['r']` over the ID-eval buffer; matches PART2's characterization of `Eprew200` as a **trailing-window** estimator, distinct from `episode_return_mean` | Already correctly kept un-pooled per `COMPARABILITY_CONTRACT` §5d (PART2, not re-derived). |
| `target_network_divergence` | N/A — no target network in the PPO path; `update_cluster` does have a target network (`train_state_target`, EMA via `state_update`, `train_ppo.py:335`) but no divergence metric is computed for it either | — | — | Confirmed absent by the same repo-wide grep as the off-policy baselines. |

**Everything logged here reaches the offline wandb-JSONL sink** (`runnable/_shim/wandb.py`,
consumed by `datasphere/native/normalize_curves.py::read_wandb_sink`, per PART2's 2026-09-04
update) — I did not find a computed-but-dropped case in `ctrl` at the level `alda`/`idaac`/`sgqn`
have one. The console print remains only the 4 numbers PART2 already documented.

---

## Cross-cutting findings, ranked by how likely to mislead a cross-baseline comparison

1. **`ibac_sni`'s own `kl` vs. this project's `approx_kl_k3`, printed on the same line, four tokens
   apart (`kl {:.3f} | SR {:.3f} | clipf {:.3f} | kl3 {:.4f}`).** `kl` is a variational-bottleneck
   KL (encoder posterior vs. standard-normal prior, `bottleneck.py:41-43`) — an architecture-level
   representation regularizer — not a policy-update trust-region diagnostic, and under different
   (non-default) flags it degrades to an L2-activation penalty or a literal constant zero, still
   under the same name. `approx_kl_k3` is a genuine PPO importance-ratio KL. These are not two
   estimators of one quantity; they are two unrelated statistical objects. Highest severity because
   the naming juxtaposition (`kl`, `kl3`) actively invites the wrong inference, in the *same*
   baseline's *same* log line — no cross-baseline join is even required to be misled.

2. **`critic_loss` as a literal shared record-column name across the off-policy family — at least
   four distinct formulas, spanning 8 of 12 baselines' lineage.** `rad`/`soda` (`sac.py:93-95`) and
   `alda` (same formula, though currently unlogged) include the SAC entropy term
   `−α·log_pi` in the target; `drqv2` (`:191`) does not (deterministic target); `svea` (`:236-239`)
   averages the loss over an unaugmented and a strongly-augmented view; `sgqn` (`:169-172`) adds a
   `0.9×` masked-consistency penalty on top of the base MSE; `drq`/RL-ViGen (`:274-283`) — being
   architecturally SAC-family, per the Finding-6 correction above — averages two augmented views
   **and** includes the entropy term. A plotted "critic_loss" column pooling any two of these is
   pooling different loss functions, not different hyperparameter settings of the same one. (The
   Q-value readouts `critic_q1/q2/target_q` are a **true** cognate across the DrQv2-lineage four —
   only the loss diverges, not the Q-values — worth stating so this finding isn't overstated.)

3. **`idaac`'s `agent.update()` return tuple — `value_loss`, `action_loss`, `dist_entropy`,
   `order_acc`, `order_loss`, `clf_loss`, `adv_loss` — computed every iteration across all three
   `--algo` variants (`ppo`/`daac`/`idaac`) and never logged.** Confirmed by exhaustive grep: none
   of the seven names appear anywhere in `train.py` after their destructuring assignment
   (`:278-283`). This drops not just IDAAC's own novel diagnostics (the order-classifier and
   advantage-loss terms that are the algorithm's defining mechanism) but the two most standard PPO
   quantities there are — the value loss and the clipped policy-surrogate loss. A reader of
   `idaac`'s log sees `clip_fraction`/`approx_kl_k3`/policy-health/episode-reward/success-rate but
   never either primary loss term.

4. **`alda`, under its actual launch configuration (`--use_wandb False`), computes and then
   discards essentially all of its train-side diagnostics, including `train/episode_reward`
   itself.** `self.logging_info` is populated every update, reduced to a per-key mean every
   `log_every=500` steps, and `.clear()`-ed regardless of whether `wandb.log` fired
   (`alda_trainer.py:628-639`). Confirmed against the project's own `read_alda` parser
   (`datasphere/native/normalize_curves.py:284`, matching only `alda: eval/...` lines) that no
   other sink exists. This directly inverts an earlier characterization of `alda` as this
   project's richest-logged baseline for anything on the train axis — it is rich in computation and
   nearly empty in what survives to a record; only the eight `eval/*` keys (printed via a
   *different* code path, `logger.info` at `:562-563`) reach anything durable.

5. **`sgqn`'s `update_aux` computes its own defining auxiliary loss and has no `return` statement
   at all** (`sgqn.py:191-198`, called at `:242`) — the attribution-consistency BCE loss that makes
   SGQN what it is is computed, backpropagated, and immediately unreachable, every update, with no
   diagnostic gate even attempting to catch it.

6. **`drqv2`/`svea`/`sgqn`/`curl`'s `actor_ent` is not a measurement of the learned policy at all.**
   `TruncatedNormal(pyd.Normal)` (`RL-ViGen-upstream/utils.py:105-126`) overrides only `.sample()`;
   `.entropy()` and `.log_prob()` resolve to the base `Normal`'s closed forms, evaluated at
   `std = ones_like(mu) * schedule(step)` — a **deterministic, non-learned, state-independent**
   scalar that depends only on the training step via a fixed decay schedule. Entropy of
   `Normal(mu,std)` does not depend on `mu`, so `actor_ent` is a precomputable function of `step`
   alone and carries **no information about the trained policy whatsoever** — a categorically
   different kind of "entropy" than `rad`/`soda`/`alda`'s (learned, state-dependent) or
   `idaac`/`ppg`/`ibac_sni`/`ctrl`'s (learned, but state-independent — still moves with training).
   `actor_logprob` inherits the same issue for `log_prob`: evaluated under the untruncated base
   Normal at a sample that was separately noise-clipped and box-clamped, so it is not the
   log-density of the distribution that actually produced the executed action. (`drq` is exempt —
   its `SquashedNormal` correctly has no closed-form entropy and the project's own P17 patch
   already removed `actor_ent` for it, with a comment explaining exactly this distinction — that
   fix just never propagated into PART2's family table; see baseline §3 above.)

7. **PART2-METRIC-INVENTORY.md's own claim about `clip_fraction`'s log-ratio vs. ratio formulation
   does not survive a direct read of the code.** `scripts/metrics.py::clip_fraction(log_ratio, ...)`
   immediately computes `r = np.exp(log_ratio)` and thresholds `|r-1| > eps` (`:271-272`) — the
   identical comparison as thresholding a ratio directly; there is no reformulation (e.g. an
   asymmetric log-space band) that would behave differently at the tail, contrary to the prose's
   "can disagree on the tail, which is the region the metric exists to watch." Separately, `idaac`'s
   actually-wired `clip_fraction` (`idaac.py:135-136`) is a **local reimplementation** — `|ratio -
   1| > clip_param` on the ratio directly — not a call into `scripts/metrics.py` at all, and it is
   bit-for-bit the same formula `ppg`'s native `clipfrac` uses. As implemented today, there is no
   daylight between "ppg's" and "ours" clip_fraction.

8. **`gaussian_policy_health`'s inputs are architecturally two different kinds of quantity across
   the eight baselines that call variants of it.** `idaac`/`ppg`/`ibac_sni`/`ctrl` all pass a
   single **global, state-independent** bias/parameter vector — deterministic given the current
   weights, no batch-sampling variance, identical for every observation. `rad`/`soda`/`alda`/`drq`'s
   analogous `log_std`/entropy is the **mean over a minibatch of a state-conditional network
   output** — has genuine sampling variance and reflects what the policy does differently across
   different states. A "log_std" or "entropy" column from the first group is a fixed scalar per
   training step; from the second, it is a sampled statistic. Neither is wrong, but plotting them
   on the same axis treats a parameter as if it were an estimator.

9. **Cadence and aggregation are not uniform across the twelve, in a way that affects what
   "the same metric, more/less noisy" would mean.** `dmc_gb` (`rad`/`soda`) and the RL-ViGen five
   accumulate a running **mean** across every per-update call between episode-boundary dumps (an
   `AverageMeter`, cleared on dump) — a true per-episode average. `idaac` and `ibac_sni` instead
   overwrite a `self.last_*`/`logs` value every update and only *read* it every `log_interval`
   updates — a **point sample of the most recent update**, not a window mean. `ppg` logs the mean
   over the **last epoch's** minibatches once per rollout iteration (`epoch_stats[-1]`, itself
   already a true per-epoch mean via `dict_mean`). `ctrl` logs every rollout via `wandb.log`, no
   console echo for anything but 4 numbers. Pooling "clip_fraction, logged once per iteration"
   across `idaac` and `ppg` without accounting for this would compare a last-update snapshot to a
   full-epoch average. (Historical cost of getting this wrong, already on record:
   `docs/CONSTRUCTION.md` C57 — RL-ViGen's own `critic_loss` sat in a dict but off the console
   format list before 2026-08-20, and a NaN divergence ran unnoticed for 70,000 frames because the
   only place it would have been visible was never read.)

10. **`ctrl` is wired for `clip_fraction`/`approx_kl_k3`** (`algo.py::loss_actor_and_critic`,
    feeding `update_ppo`) **contrary to PART2 §6's "ctrl is not wired" claim**, dated 2026-08-19 and
    apparently not updated since. The wiring lives only in the `update_ppo` code path (the
    project's actual default, `--algo ppo_ctrl`) — the sibling `update_daac`/`loss_actor_and_gae`
    path computes the same `ratio` but does not return either diagnostic, so they would silently
    disappear under `--algo=daac_ctrl` despite the file "having" the feature.

11. **Three unrelated "KL"s live inside `ppg`'s own single run.** `Opt/approxkl` (k2, biased,
    PPO-phase, Schulman's estimator on the current minibatch's importance ratio), `Opt/approx_kl_k3`
    (k3, unbiased, same phase, this project's addition), and `scaled/pol_distance` /
    `unscaled/pol_distance` (aux phase, `td.kl_divergence(oldpd, pd)` — an **exact closed-form**
    KL between the full pre-aux-phase and post-PPO-phase Gaussian policies, not an importance-ratio
    estimate of anything). Lower severity than #1 because the names differ enough (`approxkl` vs.
    `pol_distance`) that a careless reader is less likely to conflate them — but it is the same
    hazard shape, worth flagging alongside #1 rather than treating #1 as unique to `ibac_sni`.

12. **Minor: RL-ViGen five's `batch_reward` is a per-transition mean over one replay-buffer
    minibatch, not a per-episode return** — a different aggregation level than `episode_reward`,
    and while the name itself telegraphs the difference reasonably well, it is worth stating
    explicitly since both keys can appear in the same `train.csv` row.

13. **Positive control — not every same-concept metric is a false cognate.** `value_loss` across
    `ibac_sni`, `ctrl`, and `idaac`'s (unlogged) computation is the **identical** PPO2 clipped-value
    formula (`0.5·max((v−ret)², (v_clip−ret)²)`) in all three — a genuine true cognate. `ppg`'s
    `losses["vf"]` is the outlier: a **plain, unclipped MSE**, with no clip term at all
    (`ppo.py:143`). So among the four PPO-family baselines, value-loss estimators are 3-clipped /
    1-unclipped — a real but smaller-scale version of finding #2's shape, included here to show the
    off-policy `critic_loss` divergence (4 distinct formulas) is not simply "everything always
    differs" — the PPO family's shared losses mostly do agree.

---

## WHERE MY EVIDENCE IS THIN

Read carefully — this is where the important verification effort should go, not the inventory
tables above (which are read-the-code-directly claims, cited to file:line, and I am confident in
them at the level a second reading of the same lines would confirm).

- **I did not run any of the twelve baselines.** Every formula above is read from source, not
  observed in an actual training log. The one numeric cross-check I rely on
  (`Opt/approxkl` 0.0197 vs `Opt/approx_kl_k3` 0.0193, ~2% agreement) is **PART2's own measured
  number, not one I re-measured myself** — I am repeating it, not re-deriving it.

- **The idaac finding (value_loss/action_loss/dist_entropy/order_acc/order_loss/clf_loss/adv_loss
  never logged) is the single highest-stakes new claim in this report.** I verified it by
  exhaustive grep showing zero further references to those seven names in `train.py` after their
  destructuring assignment, cross-checked against both `algo/idaac.py`'s and `algo/daac.py`'s
  return signatures and against `runnable/_patches/idaac.patch` (to confirm no patch adds a sink I
  missed). I did not additionally rule out some indirect mechanism (a monkeypatch, a debugger hook)
  intercepting those locals — this seems very unlikely given ordinary Python semantics, but I note
  it because of how much weight this finding carries.

- **`ctrl`'s `daac_ctrl` algo path** (`loss_actor_and_gae`/`update_daac`) — I read its return
  signature (`algo.py:305`, no clip_fraction/approx_kl_k3) but did **not** trace
  `train_ppo.py`'s full handling of that branch as carefully as the default `ppo_ctrl` path, and did
  not run it. My claim that the diagnostics "would silently vanish" under `--algo=daac_ctrl` is a
  direct reading of the return tuple, not a traced/executed confirmation.

- **JAX/`jax.jit`/`jax.lax.scan` numerics in `ctrl`** — read from the traced Python source only.
  I did not execute or inspect the actual jaxpr/XLA-compiled behavior; floating-point rounding
  under fusion is asserted from source-level reasoning, not measured. Given this project runs `ctrl`
  on CPU-backed JAX (no `jax-metal`, per `runnable/_launch/ctrl.sh`'s own comment), this is probably
  low-risk, but it is unverified by me.

- **`ppg`'s MPI-rank semantics** (`comm.allgather`, `dict_mean` across ranks in
  `minibatch_optimize.py:65`) — I did not check whether this project's launcher runs `ppg` under
  more than one MPI rank; if it does, `Opt/*` values are already a cross-rank mean on top of the
  cross-minibatch mean I described, which I did not verify either way.

- **`ibac_sni`'s `bottleneck.py::Bottleneck`** — I confirmed `model.py::encode()` routes to
  `self.reg_layer(embedding)` when `use_bottleneck=True` and that this returns `(bot_mean, bot,
  kl)`, and I read `Bottleneck.forward`'s body directly. I did **not** read `model.py`'s `__init__`
  in full to triple-check that `self.reg_layer` is unconditionally a `Bottleneck` instance (rather
  than, say, a different class under some other flag combination this project doesn't use) — the
  VIB-KL characterization is solid for the project's actual launch flags (`--use_bottleneck
  --sni_type vib`), less certain for combinations I did not check.

- **`runnable/idaac/ppo_daac_idaac/algo/daac.py`** — read only its `update()` return shape
  (confirming it has the same "computed, never logged" issue), not the file end-to-end; I am
  relying on PART2's characterization ("the DAAC variant the launcher never selects") for why this
  is lower-priority, and did not independently re-verify that the launcher truly never selects it
  beyond reading the launch script's default `--algo` handling once.

- **`ppg`'s `Roller`/`VecMonitor2`/`log_save_helper.py`** (`EpRewMean`, `EpLenMean`,
  `EpSuccessMean`, `Misc/InteractCount`) and **`ibac_sni`'s `scripts/evaluate.py`** (the offline
  evaluator PART2's Finding 4 describes) — **not re-read in this pass at all.** Everything I say
  about them is inherited from PART2 without independent re-derivation.

- **`dmc_gb`'s `replay_buffer`/`env/wrappers.py`** (reward accumulation across frame-stacking,
  action-repeat interaction with reward summation) — not examined; my `rad`/`soda` coverage is
  limited to `algorithms/*.py` + `logger.py` + `train.py`'s main loop.

- **RL-ViGen's `habi_eval` (habitat) path** — not examined at all in this pass; out of scope since
  this project's actual runs are robosuite-only, flagged only so it isn't mistaken for "checked and
  clean."

- **Baselines given only a genuinely deep pass in this session, for the record:** all twelve got at
  least the update()/logging-call-site level of reading. The **shallowest** relative to the others
  were `ppg`'s roller/eval-episode accounting (inherited from PART2, not re-derived) and `ctrl`'s
  `daac_ctrl` branch (return-signature read only, not traced through `train_ppo.py`). Every other
  claim above — including all seven cross-cutting findings ranked 1–6 — was verified by reading the
  actual emitting code end to end in this session, not inferred from a name or inherited from a
  prior document.
