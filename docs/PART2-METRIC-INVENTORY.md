# Part 2 — what each baseline actually emits, before anything is compared

Opened 2026-08-17, immediately after Part 1 made all twelve run. **This is an inventory, not a
plan.** Part 2's goal is that reported metrics sit on the same axes where that is meaningful; the
first thing that requires is knowing, per baseline, what quantity is emitted and against what.

Every row below was obtained by reading the emitting code in `runnable/<name>/`, not by reading a
README or inferring from a log line. Where I state a value is raw or normalised, the evidence is
the wrapper order or the accumulation site, and it is named.

## The null here is non-comparability  ·  [DURABLE]

Two numbers may be pooled only if they were produced the same way. Nothing in this file makes two
baselines comparable; it records which pairs already are, which are not, and what the difference
is. A conversion that is not stated is a join, and joins carry the burden of proof.

## 1. The y-axis: what the number is  ·  [LIVE]

| baseline | emitted key | accumulated where | raw or normalised |
|---|---|---|---|
| `rad`, `soda` | `eval/episode_reward`, `eval/episode_reward_test_env` | `src/train.py::evaluate` sums `reward` from `env.step` | **raw** — no reward wrapper in the stack |
| `alda` | `eval/episode_reward`, `…_distracting`, `…_color_hard` | `alda_trainer.py:544` sums `reward` | **raw** |
| `ppg` | `EpRewMean`, `EpLenMean` | `VecMonitor2.process` accumulates `lastrews` from `venv.observe()` | **raw** — PPG's `RewardNormalizer` lives inside `ppo.learn` and acts on the collected tensor, never on the env |
| `idaac` | `train/mean_episode_reward`, `test/mean_episode_reward` | baselines' `VecMonitor`, via `info['episode']['r']` | **raw**, and this needs the wrapper order: `VecMonitor` is constructed **first** and `VecNormalize(ob=False)` wraps it, so `VecNormalize`'s `venv` *is* `VecMonitor`. The monitor therefore sees pre-normalisation rewards |
| `ibac_sni` | `rreturn_mean/std/min/max` | `algos/base.py` `log_episode_reshaped_return` | **raw** whenever `reshape_reward is None`, which is what `scripts/train.py` passes |
| `ctrl` | `Eprew200` (ID), `Eprew0` (OOD) | vendored `VecMonitor`, same construction order as `idaac` | **raw** |
| RL-ViGen five | `episode_reward` (`R`) only — `SR` is a placeholder, see Finding 2 | `train.py::eval` sums `time_step.reward` | **raw** |

**Finding 1 — the returns are comparable in kind; the training signal is not.** `idaac` and
`ctrl` *train* on rewards divided by a running return-std (`VecNormalize`), while `rad`, `soda`,
`alda`, `ibac_sni` and the RL-ViGen five train on raw robosuite reward. `ppg` normalises inside
its own update. That is each set of authors' own choice, it changes learning dynamics, and it is
**not** something to equalise — erasing it would be a join. It belongs in the run card.

**Finding 2 — NO baseline currently reports success rate on robosuite, including RL-ViGen's
own five.** The `SR: 0.0000` in their logs is not a measurement. `logger.py:25` declares an
`('success_rate', 'SR', 'float')` column, but only `Workspace.habi_eval` — the **habitat** path —
ever calls `log('success_rate', …)`. The robosuite path goes through `Workspace.eval`, which
logs `episode_reward`, `episode_length`, `episode` and `step`, and never `success_rate`. `SR` is
the logger's default for a column nothing fills.

The first draft of this file claimed the opposite — that success sat in the info dict every
baseline discards. Checked rather than assumed, and it does not: `VGBWrapper.step` returns
`info` with exactly `['mode', 'scene_id']`, and `Gym2DMC.step` then discards `info` entirely on
the RL-ViGen path. Probed on a live env, not read off a grep.

**DONE, half of it: RL-ViGen patch P10** now puts `info['success'] = bool(self.env._check_success())`
in `VGBWrapper.step` — verified live, `info` keys are now `['mode', 'scene_id', 'success']`. The
seven non-RL-ViGen baselines reach the env through `robosuitevgb.utils.make_env` directly and so
receive it immediately, at **zero clone deviations**; consuming it still costs a line each at
their eval sites.

**RL-ViGen's own five needed a second patch, P11, and it took two attempts.** `Gym2DMC.step`
builds a 4-field `dm_env.TimeStep` and discards `info`; `wrappers/dmc.py`'s `ExtendedTimeStep`
has no `info` field (habitat has a **separate** one in `habi_wrapper.py` that does — exactly why
habitat could report SR and robosuite could not). The first P11 read `time_step.info`, was
applied, and was then **withdrawn**: on this path it would have logged a computed-looking `0.0`
forever, which is strictly worse than an obviously-unfilled `0.0000`.

The version that shipped exploits something checked rather than assumed: every wrapper between
`Gym2DMC` and the agent delegates unknown attributes — `ActionDTypeWrapper`,
`ActionRepeatWrapper`, `FrameStackWrapper`, `ExtendedTimeStepWrapper`, and dm_control's own
`action_scale.Wrapper`. So `Gym2DMC` sets `self.last_info` and the outermost env can read it,
with no change to the TimeStep type and no wrapper touched in between. Verified by forcing
`Door._check_success()` True at the bottom and reading `env.last_info['success']` at the top.

**The one place it is not exact**, written down rather than discovered later:
`ActionRepeatWrapper` calls the inner step k times, so `last_info` holds the last repeat's info
and a success achieved-then-lost inside a repeat is missed. At the declared protocol
`action_repeat=1` — which is also RL-ViGen's own Supplementary Table 2 for robosuite — k is 1 and
the question cannot arise.

**The original observation stands.** The env `VGBWrapper` wraps *is* a
robosuite `Door`, which has `_check_success()` — verified live, returns `False` on a fresh step.
Success is sparse, task-defined and unit-free, which is exactly what Door's dense unnormalised
return is not. So the highest-value Part 2 item is an **RL-ViGen patch** in the P1–P9 family (it became P10) —
one line in `VGBWrapper.step` putting `info['success'] = self.env._check_success()` — which
makes it available to all twelve at once, at **zero per-baseline deviation**, the same way P6
turned out to be the general key for render size. Consuming it still costs a line per baseline
at the eval site, and `Gym2DMC` would additionally have to stop dropping `info`.

### Success rate as delivered, 2026-08-17

**All twelve now emit it.** All use ONE convention, stated in each seam: **an episode is a
success if `_check_success()` held at any step**. The alternative — the flag at the final step,
which RL-ViGen's habitat path uses — differs whenever a policy achieves the goal and loses it,
which on Door means opening the door and letting it swing back. Chosen, not defaulted into.

| baseline | key | verified |
|---|---|---|
| `rad`, `soda` | `eval/success_rate`, `eval/success_rate_test_env` (`SR`/`SRTEST` in the console) | ran, prints |
| `alda` | `eval/success_rate{,_color,_distracting}` | ran, prints |
| `idaac` | `test/success_rate` | ran, prints |
| `ctrl` | `SR_ID`, `SR_OOD` | ran, prints |
| `ibac_sni` | `SR` in its own log line | ran, prints |
| `ppg` | `EpSuccessMean` — **train distribution only**, it has no eval env | ran, prints |
| RL-ViGen five | `success_rate` (`SR`), via P11 | forced-success probe; full run below |

**Every one of these currently reads 0.000, and that is a measurement, not a placeholder.** The
difference is checked, not asserted: `tests/test_success_metric.py` forces
`Door._check_success()` to return True at the bottom of the stack and requires the flag to reach
the caller through P10 and the whole wrapper chain. A test that only asserted "False for an
untrained agent" would pass just as happily against a hard-coded False — which is exactly the
trap `SR: 0.0000` had already set once.

Two bugs were found by refusing to accept a plausible number. `ibac_sni`'s log line printed
`SR 0.093` — impossible for a mean over 0/1 values with one env. Cause: upstream's format string
had 17 placeholders against 18 data items, so `.format(*data)` had been silently dropping `kl`
all along; appending success made "SR" display `kl`. Both are printed now, so the counts are
equal and the discard cannot return unnoticed. And in `ppg`, the obvious implementation — reading
success off the `info` already recorded with each `Episode` — is wrong: `VecMonitor2` samples that
info when `first` is set, i.e. AFTER the reset, so it describes the next episode.

### Finding 6 — three different action distributions, not one

Checked while verifying that the four authored Gaussian heads are safe against
`Box(-1, 1, (7,))`. They are: robosuite's `base_controller.scale_action` does
`np.clip(action, self.input_min, self.input_max)` before scaling, so an out-of-range sample is
clipped by the environment — the standard PPO arrangement, where `log_prob` is taken on the
unclipped sample.

The first draft of this finding claimed an 8/4 split matching the frame-stack one. That was
inferred from lineage rather than read, and it is wrong. Tracing each actor gives **three**
families:

| family | baselines | mechanism |
|---|---|---|
| **SAC squashed Gaussian** | `rad`, `soda`, `alda`, `drq` | `squash()` applies `tanh` to the *sample* and corrects `log_pi` by `log(1 - tanh²)` — `alda/models/sac.py:31`, dmc_gb's `modules.py`. **`drq` independently, not by shared code**: `RL-ViGen-upstream/algos/drq.py`'s own `Actor.forward` builds `SquashedNormal(mu, std)` from its OWN `TanhTransform`, with the same numerically-stable Jacobian correction (`2*(log 2 - x - softplus(-2x))`). A proper density on the box, in all four cases. |
| **DrQv2 squashed mean + truncated noise** | `drqv2`, `svea`, `sgqn`, `curl` | `mu = torch.tanh(mu)` then `utils.TruncatedNormal(mu, std)` (`drqv2.py` `Actor.forward`). `svea`/`sgqn`/`curl` have no `tanh` of their own — they subclass `DrQV2Agent` and reuse its `Actor`. Exploration noise is *clipped*, not squashed. |
| **Unsquashed Gaussian, bounded only by the env** | `ppg`, `idaac`, `ibac_sni`, `ctrl` | the four authored heads. Mass outside the box is folded onto the boundary by robosuite's clip while the policy's own likelihood still treats it as interior. |

**Corrected 2026-09-05** — the first version of this table put `drq` in the DrQv2 row on lineage
(same repository, same launcher family) rather than on mechanism. Read directly: `drq.py` defines
its OWN `SquashedNormal`/`TanhTransform` (a proper tanh-squashed density, matching the SAC family's
construction), completely independent of `drqv2.py`'s `Actor` — it does not subclass `DrQV2Agent`
the way `svea`/`sgqn`/`curl` do. This was already known and stated correctly elsewhere in this
project: the P17 patch comment (`setup/apply_patches.py`) explains `drq`'s `actor_logprob` is "the
Monte-Carlo entropy of a squashed policy... not the analytic Gaussian entropy drqv2/svea/sgqn/curl
report under that name" — the fact was on record, it had just not propagated into this table. Four
families by lineage, three by mechanism.

Three MECHANISM families, three different induced action distributions, and the third is the only
one whose likelihood disagrees with what the environment actually executes. All are the respective
authors' designs; none is a porting artifact; and, as with frame stacking, no rescaling of a
reported number touches it.

## 2. The x-axis: what the number is plotted against  ·  [LIVE]

| baseline | emitted x | unit | action repeat |
|---|---|---|---|
| `rad`, `soda` | `step` (train loop counter) | env steps | 1, via `--action_repeat 1` |
| `alda` | trainer step | env steps | 1, in `specs/train_alda_robosuite_door.yaml` |
| `ppg` | `Misc/InteractCount` | env interactions = `num_envs × nstep × iters` | none in the stack |
| `idaac` | `train/total_num_steps` = `(j+1)·num_processes·num_steps` | env steps | none |
| `ibac_sni` | `frames` | env frames = `procs × frames_per_proc × updates` | none |
| `ctrl` | printed `num_envs · step` | env steps | none |
| RL-ViGen five | `F` (frame) and `S` (step) | `F = S × action_repeat` | **was 2**, now 1 — see below |

**Finding 3 — a live defect, found and fixed on 2026-08-17.** RL-ViGen's `cfgs/config.yaml` sets
`action_repeat: 2`, no robosuite task file overrides it, and `robo_make` really does apply it
(`ActionRepeatWrapper`). So the five ran at 2 while the other seven ran at 1: same wall of frames,
half the policy decisions, and an x-axis off by a factor of two. It also contradicts RL-ViGen's
**own** Supplementary Table 2 ("Action repeat — Robosuite: 1, otherwise: 2") and this project's
declared `Protocol.DEFAULT_ACTION_REPEAT = 1`. `runnable/_launch/rlvigen.sh` now passes
`action_repeat=1`; verified by the log going from `F: 1000 | S: 500` to `F: 1000 | S: 1000`.

With that fixed, **every baseline's x-axis is env frames**, and the remaining differences are
granularity (per-update vs per-episode) rather than unit.

## 3. Evaluation regimes actually reachable per baseline  ·  [LIVE]

RL-ViGen's held-out axis is the visual regime — `train`, `eval-easy`, `eval-medium`, `eval-hard`
— not a level split. What each baseline can currently report:

| baseline | regimes in one run | mechanism |
|---|---|---|
| `rad`, `soda` | train + one `--eval_mode` | its own `test_env` |
| `alda` | train + eval-easy + eval-hard | its own three-env trainer |
| `idaac` | train + eval-easy | `test.py::evaluate`, `RLVIGEN_EVAL_MODE` |
| `ctrl` | train + train(ID) + eval-easy | its own three envs |
| `ibac_sni` | one per *training* run, but **its own `scripts/evaluate.py`** measures a saved model in any regime | `RLVIGEN_MODE` + `--save-interval` |
| `ppg` | train + any regime, via `runnable/_launch/ppg_eval.py` | its own `Roller`/`VecMonitor2` over a saved checkpoint |
| RL-ViGen five | train + a held-out regime **only since patch P12** — before it, both envs were `train` | its own `eval()`, now given a mode |

**Finding 4 — neither `ppg` nor `ibac_sni` reports a generalisation gap from a single training
run**, which is a property of the authors' scripts, not of our integration. Both are now closed,
by different routes, and looking rather than assuming is what separated them:

- **`ibac_sni` already ships `scripts/evaluate.py`**, which loads a saved model and runs it. It
  builds its env with the same `gym.make(args.env)` call `train.py` uses, so the *same* one-line
  seam applies — 6 added lines, no new evaluation loop, and the measurement is made by the
  **authors' own tool**. Train with `--save-interval`, then run `evaluate.py` under
  `RLVIGEN_MODE=eval-easy`. **Done and verified**: one saved policy, two regimes, R ≈ 0.690/0.722
  on `train` and 0.690/0.720 on `eval-easy` (an untrained policy after 700 frames — the point is
  that the comparison exists, not its value).

  Getting there uncovered two upstream bugs that make this path impossible as shipped, neither
  specific to RL-ViGen: `train.py`'s save block calls `preprocess_obss.vocab.save()`, and `vocab`
  exists only on the MiniGrid branch of `get_obss_preprocessor` — so `--save-interval` crashes on
  **any** non-MiniGrid env, i.e. this repo cannot checkpoint an image env at all. And
  `utils/agent.py` converts actions to numpy **only `if torch.cuda.is_available()`**, so on a
  CPU-only machine `get_actions` returns torch Tensors; harmless for MiniGrid, whose `step()`
  takes an int-like, and fatal for a Box env — it surfaces from inside robosuite's OSC controller
  as `TypeError: Concatenation operation is not implemented for NumPy arrays`.
- **`ppg` has no eval entry point at all** — confirmed by reading the package: `train.py` trains,
  `graph.py` plots CSVs, `LogSaveHelper` does `th.save(self.model, ...)`, and the only `load` in
  the whole package is a comment in `impala_cnn.py`. So the gap had to be closed by something we
  write.

  `runnable/_launch/ppg_eval.py` is that, and it lives **outside the clone** — zero deviations,
  the ledger stays an honest account of what was done to the original. It reuses everything that
  could bias a number: `get_venv` (the same guarded branch training uses), `Roller` and
  `VecMonitor2` (PPG's own rollout and episode accounting), and `PpoModel.act` (the policy's own
  sampling path). What is ours is the loop that stops after N episodes.

  **Verified**: one checkpoint, `train` → 1.1829, `eval-easy` → 0.9825, success rate reported,
  episode length 500 in both. It samples rather than taking the distribution's mode, because this
  repo offers no deterministic-action path — stated in the file, since a Gaussian's mean would
  give a different and usually higher number.

Either way this adds a checkpoint-selection rule to the protocol — `Protocol.checkpoint_selection`
already has a slot for it, and it is currently unstated for these two.

### Finding 7 — RL-ViGen's own runner did not measure generalisation on robosuite at all

`Workspace.setup` built both envs with **identical arguments**:

    self.train_env = robo_make(name=..., action_repeat=..., frame_stack=..., seed=...)
    self.eval_env  = robo_make(name=..., action_repeat=..., frame_stack=..., seed=...)

Neither passes `mode`, so both fall back to `robo_config.yaml`'s `mode: train`. The eval env was
a second copy of the train env, and **all five of RL-ViGen's own baselines reported no
generalisation gap** — the benchmark's runner measured the training distribution twice.

This is the same failure **P1** was written for, and P1's note states it outright: *"a caller
asking for eval-easy silently received a train env and measured generalisation on the training
distribution."* P1 fixed the callee, P3 threaded `mode` through `robo_make`, and this caller used
neither. **P12** passes `RLVIGEN_EVAL_MODE`, defaulting to `None` — `robo_make`'s own default, so
an unset variable reproduces upstream byte for byte. Verified: the log now prints
`Now the mode is train` and `Now the mode is eval-easy`, two envs instead of two copies.

It also changes how `scripts/collect_metrics.py` must read those logs, and that is the reason it
reads the regime out of the log rather than assuming it: labelling the second env `eval-easy`
when it was actually `train` would have manufactured a generalisation gap from two measurements
of one distribution.

### Finding 8 — `critic_loss` is four different formulas under one name, across 8 of 12 baselines

Found 2026-09-05 auditing metric richness project-wide, then independently re-verified line by
line before trusting it — the first check (matching only the top-level `F.mse_loss(Q1,target_Q) +
F.mse_loss(Q2,target_Q)` syntax) found nothing wrong, because that surface line is in fact shared;
the divergence is in what feeds `target_Q` and what gets folded in afterward.

| baseline(s) | formula actually logged under `critic_loss` |
|---|---|
| `drqv2`, `curl` | plain twin-Q MSE, `target_Q = reward + discount·min(tQ1,tQ2)` — no entropy term, no augmentation. `curl` never overrides `update_critic`, so this is the identical formula, not a cognate. |
| `svea` | `critic_loss = 0.5·(critic_loss + aug_loss)` — the plain MSE **averaged with** a second MSE computed against the strongly-augmented observation (`svea.py:236-241`). The value logged is not the plain MSE; the reassignment happens before the `metrics['critic_loss'] =` line. |
| `sgqn` | `critic_loss += 0.9·(mse(Q1,masked_Q1) + mse(Q2,masked_Q2))` (`sgqn.py:169-172`) — the plain MSE plus a mask-consistency term, likewise folded in before logging. |
| `drq` | `target_Q = (target_Q + target_Q_aug)/2`, where `target_Q_aug` includes `− self.alpha·log_prob_aug` (`drq.py:265-283`) — dual-augmentation-averaged **and** entropy-inclusive, since `drq` is SAC-family (Finding 6). |
| `rad`, `soda`, `alda` | SAC's own entropy-regularised target, `target_Q = r + not_done·γ·(min(tQ1,tQ2) − α·log_pi)` (`sac.py:88-91`) — same shape as `drq`'s target before its augmentation-averaging, no augmentation term. |

Four distinct formulas, one shared record-column name, across eight of the twelve baselines that
emit it at all. None is wrong — each is that baseline's own authors' definition of their own
critic objective, and `svea`'s/`sgqn`'s extra terms are literally what makes them SVEA and SGQN
rather than plain DrQ-v2. The finding is that a plotted `critic_loss` column pooling any two of
these compares different objectives under one label, the same shape as this document's own k2/k3
and `ibac_sni` `kl`/`approx_kl_k3` findings (§6) — reported here rather than resolved, because the
resolution (report each as its own column, or a project-chosen name distinct from the authors')
is the owner's to make, not a default to apply silently.

## 4. The observation is NOT common, in two independent ways  ·  [LIVE]

Genuinely shared: robosuite `Door`, Panda, OSC_POSE, horizon 500, action repeat 1, `scene_id 0`,
RGB. Those are `rlgen/protocol.py` fields and `tests/test_contract.py` pins them.

**Finding 5 — frame stacking splits the twelve 10/2, and this is the largest comparability gap
found so far.** Checked per seam rather than assumed from the protocol:

**Corrected 2026-09-07:** PPG now joins IDAAC in the stacked column for the selected main path.
Both use the IDAAC-authors' published DMC continuous-control comparator geometry, with a real
9-channel train/eval path. PPG's source qualification remains explicit: this is not OpenAI PPG's
primary-source canonical environment; it is the authors' comparator adapted to this project.
The released one-frame path remains available only through explicit `frame_stack=1`.

| stacked (3 frames, 9 channels) | single frame (3 channels) |
|---|---|
| `rad`, `soda` (`FrameStack` in dmc_gb's `make_env`) | `ibac_sni` |
| `alda` (`FrameStack(_e, frame_stack)` in its own branch) | `ctrl` |
| `drqv2`, `svea`, `sgqn`, `curl`, `drq` (`FrameStackWrapper`, cfg `frame_stack: 3`) | — |
| `idaac` and `ppg` (`FrameStack` in both train/eval adapters) | — |

The split is not an attempt to equalise observations. `ibac_sni` and `ctrl` retain released
one-frame Procgen geometry. IDAAC uses a direct source-backed continuous-control precedent.
PPG uses the same DMC comparator because no primary continuous-control PPG configuration exists;
this is a declared design-point adaptation, not a claim of canonical PPG reproduction.

But the consequence is not cosmetic. On a robot manipulation task, a single frame is
**velocity-blind** — the gripper's motion is unobservable, and the policy sees a strictly smaller
state. Comparing a 9-channel agent with a 3-channel one on Door is comparing two different
POMDPs, not two algorithms.

**`Protocol.DEFAULT_FRAME_STACK = 3` remains only a fallback.** Production records use the
per-baseline geometry and explicit evaluator override, so a C1 checkpoint cannot be evaluated
under C2 metadata by accident.

**Render resolution is a second, independent split, deliberately.** `rad`/`soda` see an 84 crop of a 100
render, `alda`/`ppg`/`idaac`/`ibac_sni` render 64, the RL-ViGen five render 84 — each its own
paper's resolution, which is what lets their encoders and augmentations run unmodified (P6). It
is a genuine difference in field of view and in input dimensionality, and no conversion makes it
go away. The options are: accept it and say so on every plot; force one resolution and accept
that some baselines then run outside their published configuration (RAD becomes SAC at 84, SODA
refuses to run at all); or report both. **Undecided, and it is the first thing Part 2 must
decide**, because it changes what every subsequent number means.

## 5. Order of work this implies  ·  [CURRENT-STATE]

> **Status re-checked 2026-08-26 — items 1 and 2 are DONE, and this list had not said so.**
> Item 1 was completed the day it was written (patches P10/P11; §1's own "Success rate as
> delivered" subsection records it, so the document contradicted itself for nine days). Item 2 is
> also done: `rlgen/protocol.py` now carries `OBSERVATION_GEOMETRY` per baseline, `frame_stack`
> and `image_size` default to `None` and resolve per baseline, and
> `tests/test_observation_geometry.py` (25 assertions, green) checks them against the launchers.
> **Items 3 and 4 remain open and are both the owner's**, not work anyone can take: item 3 is the
> resolution/frame-stack decision this file calls *"the first thing Part 2 must decide"*, and it is
> [`PREMISES.md`](PREMISES.md) P4/P6 territory. Item 5 is unstarted and gated on 3.
>
> Two things learned by re-checking rather than trusting the list, both worth more than the status
> itself: a numbered "order of work" ages faster than the findings above it, because findings are
> statements about code and an order is a statement about intent; and this file is **the reasoning
> of record** for what every metric is — on 2026-08-26 its reward-normalisation and frame-stack
> facts were re-derived from scratch by someone who had not read it, and only agreed with it by
> luck. `scripts/audit_comparability_seam.py` now exists as the automated check that these facts
> have not drifted, and its header says it is not an independent authority.

1. **Success rate for all twelve.** ✅ **DONE 2026-08-17** (P10 + P11) — see §1's "Success rate as
   delivered". Not currently emitted by anything (§1 Finding 2), but
   reachable via one RL-ViGen patch plus one consuming line per baseline. It is the only
   unit-free, task-defined quantity available, and Door's dense return is neither. Do this
   before anything else — but note it is a small deviation in each clone, not free.
2. **Fix `Protocol.frame_stack`** so it stops certifying 3 for the four single-frame baselines
   (§4 Finding 5). This is a correctness bug in the contract, not a design question, and it is
   the only item here that makes an already-emitted card false.
   ✅ **DONE** — `OBSERVATION_GEOMETRY` in `rlgen/protocol.py` resolves `frame_stack` and
   `image_size` per baseline; `DEFAULT_FRAME_STACK` survives but its comment now reads *"TRUE FOR
   8 OF THE 12 BASELINES ONLY"* and points at the per-baseline field. Verified 2026-08-26.
3. **Decide the resolution and frame-stack questions** (§4). They gate the meaning of every
   comparison, and frame stack is the harder of the two: it changes what is observable, not just
   the sampling of it.
4. **Decide the eval story for `ppg` and `ibac_sni`** (§3), choosing between a checkpoint pass
   and a clone deviation, and record which.
5. Only then: a common emission format. Not a common training harness — that is the join Part 1
   exists to avoid.

## 6. The family-tier diagnostics ([C28](CONSTRUCTION.md#c28)): coverage declared before wiring  ·  [LIVE]

Added 2026-08-19, and **corrected the same day** — the correction is the more useful half.

The first version of this section said the five quantities in `scripts/metrics.py` are logged by
no baseline, "verified, not assumed". The verification searched for our **names**
(`clip_fraction`, `approx_kl`, …) and found zero. Searching for the **quantities** instead gives a
different answer:

| quantity | already emitted on a live path? |
|---|---|
| clip fraction | **yes, `ppg`** — `runnable/ppg/phasic_policy_gradient/ppo.py:108` — `diags["clipfrac"] = (th.abs(ratio - 1) > clip_param).float().mean()` |
| approximate KL | **yes, `ppg`** — `ppo.py:109` — `diags["approxkl"] = 0.5 * (logratio ** 2).mean()` |
| explained variance | **yes, `ppg`** — `ppo.py:48` — `logger.logkv` of `tu.explained_variance` as `VFStats/EV` |
| effective sample size | no — genuinely absent everywhere |
| target-network divergence | no — genuinely absent everywhere |

`ibac_sni` also computes `clipfrac_train` / `approxkl_run` and friends, but only in
`runnable/ibac_sni/coinrun/coinrun/ppo2.py`, the TensorFlow coinrun tree its launcher never
touches. Not live, so it does not count.

**Searching for a name instead of a quantity is exactly the failure this document's
§Reconciliation warns about, committed while writing the section that cites it.** Worth leaving in
view: the whole point of that section is that two implementations of one quantity rarely agree on
a name, and the check I ran assumed they would.

**And the correction immediately produces the real problem.** `ppg`'s `approxkl` is Schulman's
**k2** — `0.5 * (log r)^2`, biased. Our `metrics.py::approx_kl` defaults to **k3** —
`(r - 1) - log r`, unbiased and non-negative, chosen for exactly the reason its docstring gives
(a KL that can print negative is unusable as an early-stopping trigger). So wiring k3 into the
other three baselines and leaving `ppg`'s k2 in place would put **two different estimators in one
column under one name**. That is the defect, and it is now the first decision C28 has to make
rather than something discovered from a surprising row later:

- adopt k3 everywhere and **change `ppg`'s existing emission** (a clone deviation, and a real one
  — it alters a number the authors' code already prints), or
- adopt k2 everywhere to match `ppg` and accept a biased, sign-unstable estimator, or
- emit both under distinct names and never pool them.

**The third is the right one, and it is cheaper than it sounds.** Leave `ppg`'s `approxkl`
exactly as its authors wrote it — it is their number, on their name, and this project's null is
that the reference is authoritative about the algorithm. Add k3 *beside* it, under our own name,
in all four on-policy baselines including `ppg`. Then the comparison-bearing column is k3 across
four baselines computed one way, `ppg` keeps emitting what it always emitted, and no existing
number changes. The cost is one extra scalar per baseline, which is the cheapest thing on this
page.

**Measured, once both were live in `ppg`:** `Opt/approxkl` 0.0197 (theirs, k2) against
`Opt/approx_kl_k3` 0.0193 (ours, k3), on the same update. **They agree to about 2%** — which is
the argument, not a reassurance. Two estimators that disagree by an order of magnitude would be
caught by the first person to read the column; two that agree to a few percent produce a
plausible number and are caught by nobody.

The same shape applies to clip fraction: add ours, do not edit theirs. It also means C28 touches
`ppg` **additively** — no clone deviation that alters a printed value, which would otherwise have
been the first ENABLES-class change made for a diagnostic rather than for a result.

**CORRECTED 2026-09-05 — this overstated the difference; the live code does not do what it says.**
The same question, smaller, was claimed to apply to clip fraction: `ppg` thresholds
`|ratio - 1| > clip_param` on the ratio, "ours takes the log-ratio for precision at the extremes."
Checked against all four live implementations rather than against `scripts/metrics.py` alone (the
subagent's report flagged this claim as not surviving that read; it does not):

`scripts/metrics.py::clip_fraction(log_ratio, clip_eps)` does accept a log-ratio argument and
internally does `r = np.exp(lr)` before comparing — but that is one `exp()` call, the same single
operation any caller needs to turn a log-ratio into a ratio in the first place. It buys no
precision over comparing an already-exponentiated `ratio` directly, because both paths compute the
identical floating-point `exp()` once. The claimed benefit would only be real if some caller formed
`ratio` a *different*, lossier way (e.g. dividing two separately-exponentiated probabilities) —
none of the four do.

More to the point: **none of the four live, inline implementations call `scripts/metrics.py` at
all**, and none compute `clip_fraction` from a log-ratio:
- `ppg` (`ppo.py:146`, the authors' own, pre-existing, untouched): `th.abs(ratio - 1) > clip_param`.
- `idaac` (`idaac.py:136`): `torch.abs(ratio - 1.0) > self.clip_param`.
- `ibac_sni` (`ppo.py:132-133`): `torch.abs(diag_ratio - 1.0) > self.clip_eps`.
- `ctrl` (`algo.py:355`): `jnp.abs(ratio - 1.0) > clip_eps`.

All four compare the already-exponentiated ratio. `scripts/metrics.py`'s function is a reference
implementation (used for tests and offline recomputation), not the thing running in any of the
four training loops, and its own formula reduces to the identical comparison once its one internal
`exp()` call is accounted for — it is not a different, more precise quantity.

The **k3 estimator** (`approx_kl_k3`) is the one place a real, smaller version of this asymmetry
does exist, and it runs the OPPOSITE direction from the retracted claim: `ppg` (`logratio` is
already the primary variable, `((ratio - 1) - logratio)`) and `ctrl` (`log_ratio` is factored out
*before* `ratio = exp(log_ratio)`, per its own code comment) both keep the log-ratio as the primary
quantity. `idaac` and `ibac_sni` do it the other way — they hold `ratio` and derive
`torch.log(ratio)` *from* it (`idaac.py:137`, `ppo.py:135`), which is a round-trip through `exp`
then `log` rather than carrying the original log-difference through. This is the inverse of what
the retracted sentence claimed, is small (a round-trip through `exp`/`log` is close to identity for
well-conditioned inputs), and is not a correctness bug — it is now stated accurately instead of
guessed at.

C28 is READY, so the wiring is a slot rather than a decision. **The declaration is not**, and it
comes first: wiring a quantity into whichever baselines happen to expose the right local variable
is exactly how a quantity becomes **Accidental**, this contract's defect class. The structural
split is **4/8 by algorithm family** (`ppg`, `idaac`, `ctrl`, `ibac_sni` — the same four as
Finding 5 originally, by coincidence of shared Procgen lineage, not the same fact any more now
that Finding 5 itself reads 9/3) — four on-policy PPO-family clones that compute an importance
ratio against a clipped surrogate, eight off-policy actor-critics carrying a target network. Both
halves were checked in code, not inferred from the method names.

| quantity | coverage class | subset, and the structural property fixing it |
|---|---|---|
| `clip_fraction` | **Subfamily** | `ppg`, `idaac`, `ctrl`, `ibac_sni` — requires a clipped surrogate; meaningless where no ratio is formed |
| `approx_kl` | **Subfamily** | same four — computed from old/new log-ratios that only an on-policy update has |
| `effective_sample_size` | **Subfamily** | same four — a property of importance weights |
| `explained_variance` | **Subfamily** | same four — needs V(s) against a Monte-Carlo return. An off-policy Q against a TD target shares the *name* and is a different quantity; extending it there needs a reconciliation, not a call site |
| `target_network_divergence` | **Subfamily** | the other eight — requires a target network to diverge from |

**What this means for what C28 buys, stated plainly: none of the five is Universal, so none of
them is comparison-bearing across the twelve.** They are diagnostics within a family — they make
a surprising run explicable, and they do not make two families more comparable. That is still
worth having before expensive runs, for the reason C28 gives (observability added afterwards
cannot explain a run that already happened), but it is a smaller claim than "more metrics".

The `explained_variance` row is the one to watch. It is the only one with an off-policy analogue
tempting enough to wire under the same name, and doing so would produce two honestly-named
numbers that are not the same quantity — the failure this document's §Reconciliation exists to
name.

**A live instance of exactly this, found 2026-09-05 auditing metric richness across all twelve.**
`ibac_sni`'s own log line prints `kl` and `approx_kl_k3` four tokens apart
(`torch_rl/scripts/train.py:250-262`). They are not the same quantity and neither is a typo of the
other: `kl` is the information-bottleneck term (`self.acmodel.compute_train`'s VIB KL between the
encoder posterior and the standard-normal prior, weighted by `beta` in the loss — the mechanism
IBAC-SNI is named for) while `approx_kl_k3` is this project's own PPO trust-region diagnostic
(old-vs-new policy KL, the k3 estimator, C28). Both names are correct and neither should be
renamed — `kl` is upstream's own header, `approx_kl_k3` is already under this project's own name,
which is the resolution this section already recommends for exactly this shape of collision. Noted
here because the two sitting on one line, unlabelled beyond their column header, is the specific
condition under which a reader confuses them — not a defect in either number.

### Status, 2026-08-19: three of four wired

`ibac_sni`, `ppg` and `idaac` emit `clip_fraction` and `approx_kl_k3`, each verified against a
real run (values in the commits). **All three changes are additive** — nothing the authors' code
already prints changes, every computation is under `no_grad`, and no signature moves.

**"Additive" is measured, not asserted.** `ibac_sni` was re-run at seed 1 after the wiring and its
log compared against the pre-edit run of the same seed, on the ORIGINAL fields only (H, V, pL,
vL, kl, SR): **21 of 21 logged updates identical**. A diagnostic that perturbs the update it
observes is worse than no diagnostic, and `no_grad` in the source is an argument that it does not
— this is the check. The same comparison has not been run for `ppg` (whose additions sit in an
existing `no_grad` block) or `idaac`, and should be before either is trusted the same way.

`idaac` looked like the exception and was not. Its `update` returns a positional tuple that
`train.py` unpacks, so adding two metrics *there* would have been a coordinated change across two
files. Storing them on the agent and reading them where `train.py` already logs keeps the change
the same shape as the other two. The first plan was more invasive than the problem required.

**CORRECTED 2026-09-05 — `ctrl` IS wired; this claim is stale.** As of 2026-08-19 this was
accurate: `ctrl`'s loss was a jitted JAX function with no threading. Verified against the live
code: `algo.py:355-356` computes `clip_fraction`/`approx_kl_k3` inside the jitted PPO update,
threads them out through its return tuple (`:414`), accumulates them (`:426-427`), and
`train_ppo.py:349-361` folds the returned dict into `renamed_dict` and reaches a real
`wandb.log(...)` call — which the offline shim (`runnable/_shim/wandb.py`) writes to a persistent
JSONL sink, matching `docs/REGISTER.md`'s 2026-09-04 entry recording this as measured on a real job
(`bt1ums2q8170s3cq5p9l`). Unconditional for the two PPO-family diagnostics; the *continuous-head*
diagnostics (`log_std`/`boundary_fraction`, same lines) are conditional on a `log_std` leaf
existing, which is correct — Procgen's discrete head has none.

**One real narrowing, so this does not overclaim past what was checked**: the wiring lives in
`loss_actor_and_critic` / `update_ppo`, the function `--algo` values `ppo` and `ppo_ctrl` call.
`update_daac` (`algo.py:434+`, used by `daac` and `daac_ctrl`) has its own, separate loss
functions and does **not** compute `clip_fraction`/`approx_kl_k3` — its `avg_metrics_dict` never
gets those keys, so a `daac_ctrl` run's `wandb.log` call reaches the same sink with two fewer
columns, silently. This project's declared default is `ppo_ctrl` (`train_ppo.py:96`,
`runnable/_launch/ctrl.sh`), so production is covered; a future run under `--algo=daac_ctrl`
would not be, and should not be assumed to inherit this fix without re-checking.

### Where the four on-policy call sites are, and the one that is not mechanical

Located 2026-08-19 by reading, so the wiring is a slot rather than a search. Each goes through
the baseline's **own** logger; there is no shared emission path and adding one would be the join
Part 1 exists to avoid.

| clone | ratio is already computed at | how it logs |
|---|---|---|
| `ppg` | `runnable/ppg/phasic_policy_gradient/ppo.py:91` — `logratio = newlogp - logp` | `logger.logkv` / `logkv_mean`, its own module |
| `idaac` | `runnable/idaac/ppo_daac_idaac/algo/idaac.py:108` — `ratio = torch.exp(action_log_probs -` | `update()` returns a tuple of epoch means; `train.py` prints them — so a new metric changes a function signature, not just a call |
| `ibac_sni` | `runnable/ibac_sni/torch_rl/torch_rl/torch_rl/algos/ppo.py:82` — `ratio = torch.exp(dist.log_prob(sb.action) - sb.log_prob)` | a `logs` dict returned from `update_parameters` |
| `ctrl` | `runnable/ctrl/algo.py:298` — `ratio = jnp.exp(log_prob - log_pi_old)`, JAX and jitted | metrics must be returned out of the jitted function; the others can be computed in place |

**Two of these citations were wrong on the first pass, in the same way.** `ctrl`'s ratio is at
`algo.py:298`, not the 263 I first wrote (that is the loss signature); and `idaac`'s live module
under `--algo idaac` is `algo/idaac.py`, not the `algo/daac.py` I first cited — `daac.py` is the
DAAC variant the launcher never selects. Both errors came from citing the first file `grep`
returned without confirming which one the *launcher* reaches. That is the same live-path
discipline the seed audit needed for ALDA, and it has now cost twice in one document.

**`ibac_sni` is not mechanical, and the reason is already on the record.** SNI computes *two*
ratios — `ratio_r` from the run (acting) distribution and `ratio_t` from the train distribution,
`runnable/ibac_sni/torch_rl/torch_rl/torch_rl/algos/ppo.py:99-100` (`ratio_r = torch.exp(dist_run.log_prob(sb.action) - sb.log_prob)`) — so "the clip fraction" is ambiguous for this baseline in exactly the way its
entropy already is (§1: `Loss/entropy` is a 50/50 mix of two passes, and the reason two honestly
named entropies are not one quantity). Wiring whichever ratio is nearest to hand is how the
quantity becomes Accidental.

The declared choice, to be made once and written here rather than discovered later from a
surprising number: **the acting distribution (`ratio_r`)**, because that is the one whose analogue
the other three baselines compute — a clip fraction is a statement about the policy that
generated the data. If the train-pass ratio is wanted too it is a *second, differently named*
quantity, Singleton to `ibac_sni`, never folded into the same column.

---

## What now reaches the record set — 2026-09-04  ·  [LIVE]

This inventory describes what each baseline *computes*. Until today it did not say which of that
survives to a record, and the two are not the same set. Three gaps were closed and one was found
and left open.

**1. Per-episode success, everywhere** (`scripts/eval_grid.py`, all seven evaluator families).
Records carried a success *count*; they now carry `native.episode_success`, a 0/1 list aligned
index-for-index with `native.returns`. Not a new measurement — the same `succeeded` variable, kept
per episode instead of collapsed — so no loop behaviour, RNG draw or env interaction changed. It
buys the question the count cannot answer, *what did the episodes that succeeded score*, which on
Door separates opening the door from banking shaped reaching reward. Declared as
[`EVALUATOR-DELTA`](EVALUATOR-DELTA.md) **E6**.

**2. The metrics that reached no file at all** (`normalize_curves.py::read_wandb_sink`).
`ctrl` builds a full `metric_dict` and passes it to `wandb.log` without ever printing it; its
stdout carries four numbers. These are now read back from the offline sink
`runnable/_shim/wandb.py` has been writing since 2026-09-03.

> **Correction, same day: this paragraph first said "`alda` is the same shape. Both are now read
> back", and only `ctrl` is true.** Three things have to line up for the sink to reach a record and
> alda fails the first: (a) the baseline must actually call `wandb.log` — `runnable/_launch/alda.sh`
> passes **`--use_wandb False`**, so alda writes no sink at all; (b) `families.json` must list
> `wandb_offline.jsonl` as a retained curve — ctrl does, alda does not; (c) the family's
> `artifact_root` must be the directory the shim writes to, which is `run_dir` — ctrl's is exactly
> `{run_dir}`, alda's is `{run_dir}/alda_robosuite_door/seed_{seed}`, so even a descriptor line
> would have searched the wrong directory. **alda's metrics reach the record set through its console
> log (`read_alda`), which is the path it already had.** Written down because the original sentence
> was plausible, unverified, and would have been read as coverage that does not exist.

**Keys are verbatim and nothing
is promoted to a shared column** — `ctrl`'s `ep_return_200` is `Eprew200`, the trailing window
[`COMPARABILITY_CONTRACT`](COMPARABILITY_CONTRACT.md) §5d already declares a different estimand,
and mapping it to `episode_return_mean` would bury that difference while making tables look more
complete.

**3. C61 policy health, on all four continuous heads rather than two.** `idaac` and `ibac_sni`
called `scripts/metrics.py::gaussian_policy_health`; `ppg` and `ctrl` now do too. The completion
produced a comparability finding rather than four matching columns: **`ppg` clamps and the other
three do not**, so its shared keys are computed on the clamped values (the policy that acted) and
its raw parameter gets `train/log_std_raw_mean` and `train/log_std_clamped_fraction` of its own. A
bound clamp is the C61 failure occurring with no logged number moving, and that fraction is the
event made visible.

**Still open — `ppg`'s and `ibac_sni`'s eval records are thin.** `read_ppg`'s eval branch parses
three numbers out of stdout and puts none of them in `native`; `read_ibac_sni`'s eval line yields
four. Neither baseline logs its eval to a file, so unlike `ctrl` there is no sink to read, and
closing these means either printing more (a clone deviation) or evaluating them offline through
`eval_grid.py`, which produces the richer record by construction. The second is the direction
[`EVAL-PROTOCOL`](EVAL-PROTOCOL.md) §1 already proposes, so this gap is an argument for that
proposal rather than an independent task — recorded here so it is not rediscovered as a surprise.
