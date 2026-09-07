# Faithfulness: each algorithm against its canonical source

> ## READ §5 FIRST — it is the current triage; §0–§4 are the analysis it triages
>
> **This banner replaces two wrong ones written on 2026-08-27** ([C82](CONSTRUCTION.md#c82)). The
> first said *"every 'Ours' claim below describes the retired `rlgen/` port"*; the second kept that
> shape with a per-section table. **Both were reached without reading the file**, by counting
> `rlgen/` references, and both were wrong about the most important thing: **this file already has
> a place that carries the current state.** §5 is *"Re-triaged again 2026-08-24"* — clone-era — and
> it explicitly resolves, re-opens or excludes the items in §0–§4, citing clone paths
> (`idaac/ppo_daac_idaac/arguments.py`, `ppg/phasic_policy_gradient/ppo.py`,
> `ibac_sni/coinrun/coinrun/config.py`, `ctrl/train_ppo.py`) and clone-era register entries. A grep
> for `runnable/` returns zero because §5 writes those paths **without the prefix** — which is how
> the count misled twice.
>
> **What is actually true of the two eras:**
>
> - **§0a, §2, §3's `drq`, §6 are LIVE.** The `rlgen/` port only ever mediated the *seven*
>   non-native baselines; the five RL-ViGen natives ran, and still run, upstream's own `train.py`
>   out of `RL-ViGen-upstream/` — which §2 states in its own first line.
> - **§4's structural findings are HISTORY, and they are the reason the approach changed.** They
>   describe `rlgen/algos/onpolicy_ext.py`, our re-derived on-policy core — PPG with one shared
>   value head, IBAC-SNI's critic seeing the SNI-mixed pass, CTRL missing `L_clust`. **The clone
>   move discharged all of them**, verified 2026-08-27: `runnable/ppg` ships `PhasicValueModel`,
>   `vf_true` and a separate `aux_lr` optimiser; `runnable/ibac_sni` ships the `bot_mean`
>   deterministic pass; `runnable/ctrl` ships the clustering. This section is the record of the
>   port's fidelity debt and of that debt being paid — not a backlog.
> - **§4's hyperparameter values are PORT-ERA and now inverted.** `idaac` runs **γ 0.999 / rollout
>   256 / lr 5e-4** from its own `arguments.py`; `ctrl` and `ppg` also run 0.999. No launcher
>   overrides any of it, and `configs/vigen.yaml` is read by **nothing live**. **This re-opens two
>   of §5's own resolutions**: item 2 ("rollout was never 256 — it is 2048") and item 3 ("gamma was
>   never a live disagreement") were both settled against the port, and the clone move reversed
>   both.
> - **Two sentences are false in both eras**: *"no real training has been run in this project yet"*
>   and *"Zero real training runs exist yet, so nothing has trained wrong silently."*
>   `runnable/idaac/models/` holds three checkpoints. The second licenses an inaction over the
>   unnormalised-reward divergence, so its premise being false matters even though the conclusion
>   may survive for a reason it does not give ([C76](CONSTRUCTION.md#c76): the clones **do**
>   normalise).
>
> **So there is no twelve-baseline re-derivation owed.** What is genuinely open is what §5 already
> says is open — its items 5, 6, 9, 10 — plus items 2 and 3 re-opened above. Item 9 (the entropy
> coefficient against a 7-D Gaussian rather than Procgen's 15-way categorical, measured) is §5's
> own "largest untracked fidelity gap now known", and it is the owner's.
>
> Per-clone deviations, with diff counts against each PRISTINE commit, live in
> [`RUNNABLE-ORIGINALS.md`](RUNNABLE-ORIGINALS.md) §"Deviations, per clone".

Companion to [`PREMISES.md`](PREMISES.md), which does the same job for the benchmark and the
launch surface. Canonical facts were established from papers and author-released repositories in
August 2026; every divergence below is stated with the source that establishes it.

> **Before quoting any baseline here, run `python scripts/handicaps.py`.** This file records what
> *diverges* — a value we set differently, a component we authored. It does **not** record what was
> left alone and still costs the method something, because a handicap produces no diff for this
> file's own rule to admit ([`SYSTEM.md`](SYSTEM.md) names this as structural, not an oversight).
>
> The gap is not hypothetical and this pointer exists because of one case. **`idaac`'s section below
> says nothing about its instance-invariance loss being inert on this target** — yet
> [C49](CONSTRUCTION.md#c49) measured `level_seed` decodable at **0.125, exactly chance**, against
> `scene_id` at **1.000**, so the order classifier's "same instance" and "different instance" pairs
> are two samples from one distribution ([C50](CONSTRUCTION.md#c50)). A reader who came here to ask
> "is `idaac`'s number fair to call IDAAC's result?" would leave without meeting the single largest
> reason it might not be.
>
> Handicaps are not evenly spread — `idaac` and `ibac_sni` carry four each, `rad`/`soda`/`alda`
> one — so the per-baseline view answers a question this file's per-algorithm sections cannot.

## Source tags  ·  [DURABLE]

Borrowed from the sibling project's `config.py`, whose rule — *no number without a source tag* —
is the right one:

| tag | meaning |
|---|---|
| `[P]` | the paper (table or text) |
| `[C]` | the author-released code, where it disagrees with `[P]` |
| `[RLV]` | RL-ViGen's port, which is what we actually run for five baselines |
| `[OURS]` | not in any source. Chosen here. **This is the tag that matters.** |

---

## 0. Summary  ·  [MIXED]

**"Faithful" is ambiguous for four of the twelve before we do anything**, because the paper and the
official code disagree: CURL (5 hyperparameters), SODA (aux lr), RAD (batch size, three ways),
SGQN (dead args + a hardcoded coefficient). A single answer — paper or repo — should be chosen and
stated once. This is `PREMISES.md` Q5 and it is unresolved.

| baseline | source of our implementation | headline divergence | severity |
|---|---|---|---|
| `drqv2` | `[RLV]` upstream | replay 1e5 vs 1e6 (retracted, see below); **stddev schedule is resolved only in a composed probe, not yet certified for production** | **open** |
| `svea` | `[RLV]` upstream | **uses SODA's overlay, not SVEA's random convolution**; DrQ-v2-based not SAC-based | **high** |
| `sgqn` | `[RLV]` upstream | **`aux_lr` = 1e-4 vs canonical 3e-4 — 3x on the shared encoder; the catastrophic 0.3 value is repaired, but canonical fidelity is not exact** | **medium** |
| `curl` | `[RLV]` upstream | DrQ-v2-based, not SAC; lr 1e-4 vs 1e-3; paper/code disagree 5 ways | **high** |
| `drq` | `[RLV]` upstream | lr 1e-4 vs 1e-3; **n-step FIXED 2026-08-10 (was 3 vs 1-step)** | low-medium |
| `rad` | ours, on a recovered SAC | n-step 3 vs 1-step; `random_shift` not paper's crop/translate | medium |
| `soda` | recovered from history | official DMC-GB launcher and active production launcher use `[P]` 3e-4; generic argparse default `[C]` is 1e-3 but is not effective in production | low |
| `alda` | sibling port | **faithful**; benchmark extrapolated (DMControl-GB → robosuite) | low |
| `idaac` | sibling port | per-environment rollout **256 matches `[P]`**; `num_processes=4` vs upstream 64, so **16x fewer parallel environments**; 8-sample minibatches | **high** |
| `ppg` | ours, shared PPO core | per-environment rollout **256 matches `[P]`**; four-MPI-worker upstream run has global 65,536-sample updates, while our one-worker `num_envs=8` run has 2,048 (**32x lower effective batch**); lr 1e-4 vs 5e-4; **continuous head has no reference** | **high** |
| `ibac_sni` | ours, shared PPO core | β and λ match `[P]`; **continuous head has no reference** | medium |
| `ctrl` | ours, shared PPO core | **the released code had `L_clust` lines commented out; this project restored them so the algorithm executes.** The current path uses nearest-neighbour positives; the remaining implementation quirk is inherited from the released code | **medium** |

**Reconciliation note, 2026-09-05.** The two on-policy rollout entries above describe parallelism,
not trajectory length: both retain the upstream per-environment 256-step rollout, while using fewer
environments per update for the available pre-production hardware. `FIXED` elsewhere in this file
means “no longer catastrophic,” not “matches the canonical reference”; the table above is the
current wording. The `ctrl` restoration is an executable repair, while its nearest-neighbour
construction is inherited and remains a fidelity item to verify, not a claim that `L_clust` is
absent.

---

## 0a. The benchmark's paper and the benchmark's code are different experiments  ·  [LIVE]

Verified 2026-08-10 **from primary sources on both sides**: paper rows read directly out of
`rlvigen_neurips_supplementary.pdf` (Appendix C, cross-checked against arXiv 2307.10224v3 — every
cell below confirmed verbatim, not transcribed second-hand); code rows by reading the vendored tree
here. The config changes made on 2026-08-10 rested on a second-hand transcription until this check;
they are now confirmed.

Three details the direct read added:
- Table 6's Door learning-rate cell reads simply **`1e-4`** — the "(all algos)" gloss was ours, and
  accurate, but it is not paper text.
- **5 seeds and 95% CIs are stated in the MAIN PAPER §4, not the supplementary**: *"For each task,
  we evaluate over 5 random seeds and report the mean scores and 95% confidence intervals."* Worth
  knowing if the supplementary is being treated as the sole authority.
- `rlvigen_2304.08479.pdf` in `ext/` is **not an earlier RL-ViGen draft** — it is *"Towards Robust
  Prompts on Vision-Language Models"*, an unrelated paper. Nothing should be derived from it. That
  is the **third** mislabelled-artifact incident today, after ALDA (2001.01046) and CTRL
  (2502.03492); the base rate is high enough that every citation deserves a content check. **Every "leave it alone, it is the benchmark"
argument has to say *which* RL-ViGen.**

| knob | paper (Table 2/6) | shipped code | ours | verdict |
|---|---|---|---|---|
| `action_repeat` (robosuite) | **1** | `config.yaml: 2`, and **neither `Door.yaml` nor `Lift.yaml` overrides it** | **1** | **we match the paper; their code contradicts their own table** — a factor of 2 on every frame budget |
| n-step, DrQ | **1** | `drq_config.yaml: nstep 1` | **1** | **FIXED 2026-08-10** (`drq: nstep: 1`). Table 2 reads "N-step return — DrQ: 1, otherwise: 3", which is now matched exactly |
| n-step, others | 3 | 3 | 3 | consistent |
| replay capacity | 1e7 | `config.yaml: 1000000` | **1e5** | **RETRACTED as a finding.** RL-ViGen's replay is disk-backed (one `.npz` per episode; only `max_size // num_workers` in RAM), so 1e7 is a nominal cap, not a tensor. Our 1e5 equals SECANT's robosuite value exactly and sits inside DrQ-v2's Meta-World band of 1e5-4e5. Not a deviation worth fixing. |
| `feature_dim` | **50** for DrQ-v2/CURL, **256** otherwise | `config.yaml: 50`, `Door.yaml`/`Lift.yaml`: 50 | 50 for all | code contradicts the paper; SVEA/SGQN get a 5x smaller bottleneck than published |
| `lr` (Door) | 1e-4 all algos | `config.yaml: 1e-4` | 1e-4 | consistent |
| training frames | **Door 6e5, Lift 8e5** | — | 5e5 | **the budget does have a source, and we are below it** |
| discount, hidden dim, frame stack | 0.99 / 1024 / 3 | same | same | consistent |
| **reward shaping** | **never stated** | `envs/robosuiteVGB/cfg/robo_config.yaml: reward_shaping: true` | `True` | **matches RL-ViGen's shipped code.** The paper leaves the choice unstated; that is a documentation gap, not an `[OURS]` intervention. Dense shaping is what makes a random arm accumulate return without success. |
| **batch size, target tau** | **never stated** for robosuite | — | 256 / 0.01 | **CONFIRMED ABSENT** — decide-and-record items, not look-it-up items. |
| **stddev schedule** | **Door `linear(1.0,0.1,100000)`, Lift `linear(1.0,0.1,500000)`** | `cfgs/task/easy.yaml` / `medium.yaml` | **was `...,500000)` on a Door base — FIXED 2026-08-10 to `100000`** | **previously listed here as "never stated"; that was wrong.** Table 6's `Level` row (Door **Easy**, Lift **Medium**) is not an eval difficulty — it selects a *training preset*: `easy.yaml` = `num_train_frames 1.1e6` + `linear(1.0,0.1,100000)`, `medium.yaml` = `3.1e6` + `linear(1.0,0.1,500000)`. See below. |

Four consequences worth stating plainly:

1. **Our `action_repeat=1` was chosen on internal reasoning and turns out to match the paper**
   (`instruction.md` D4). Their shipped default of 2 does not — and `robo_make` really does apply
   it (`wrappers/robo_wrapper.py:124`), so a stock RL-ViGen robosuite run is off its own table by
   2x on every budget. Note the value is **not** in `robo_config.yaml`; `rlgen/protocol.py` now
   names Table 2 as its source so nobody "corrects" it back to 2.
2. ~~**Our DrQ n-step is a genuine defect of ours.**~~ **FIXED 2026-08-10** — `drq: nstep: 1`.
   It was a real instance of the shared-base problem: `nstep` is a shared trainer key, so DrQ
   silently inherited 3.
3. **`total_frames: 500000` is no longer sourceless** — Table 6 gives Door 6e5 and Lift 8e5. Note
   these do not reconcile cleanly with the task presets (`easy.yaml` 1.1e6, `medium.yaml` 3.1e6);
   on the agent-step axis canonical Door is ~550k against our 500k, so **Door is close and Lift is
   the real shortfall**. Do not silently pick one number (`PREMISES.md` Q2).
4. **The exploration schedule was a live, systematic defect — the only one Table 6 exposed.** We
   ran upstream's **medium** preset (`linear(1.0,0.1,500000)`) on a **Door** base with a 500k
   budget, so noise finished annealing exactly at the final frame and every DrQ-v2-family arm
   trained at near-maximal action noise throughout. That biases the comparison toward whichever
   methods tolerate high action noise — systematic, not noise. The schedule's argument is **agent
   steps, not frames** (`train.py:118`: `global_frame = global_step * action_repeat`, and
   `agent.act(obs, self.global_step, ...)`); upstream robosuite runs `action_repeat=2` and we run
   1, so in agent steps canonical Door is 1.1e6/2 = **550k** against our **500k**. `100000` is
   therefore a *match*, not a rescale — and proportional rescaling independently gives
   0.182 x 500k = 91k, within 10%. Fixed to `linear(1.0,0.1,100000)`; a Lift config must override
   it back to 500000.

**Read Table 6 as a table, not with grep.** There is an *Adroit* table (Tables 5) whose tasks are
`Door, Pen, Hammer` — Adroit Door is **not** robosuite Door — and `pdftotext -layout` misaligns its
value column by one row. Tables 2 and 6 were confirmed **identical** in both the NeurIPS
supplemental and arXiv v3, so nothing here rests on one extraction. (`ext/rl_vigen/RL-ViGen_ A
Reinforcement Learning Benchmark for Visual.pdf` is a saved **OpenReview web page**, not the paper;
cite `rl-vigen_v3_2307.10224.pdf` or the supplemental.)

**A useful negative result.** The supplemental contains exactly five hyperparameter tables —
Table 2 (common), 3 (CARLA), 4 (Habitat), 5 (Adroit), 6 (Robosuite) — and **no per-algorithm
table**. So for SVEA, SODA, RAD, PIE-G and the rest, RL-ViGen documents *only* what Tables 2 and 6
carry. There is nothing further to find there, and everything else must come from each method's own
paper/code, as the sections below do. This closes Brief A §1–2 from first-hand material.

**Still open from Table 6, for Lift specifically** (nothing is wrong today — we have no Lift config
— but these become wrong the moment one is added): `Learning Rate — Lift: DrQ(v2), CURL: 1e-4,
otherwise: 8e-5` (our `base.lr: 1e-4` would be wrong for ten of twelve arms), and the `medium`
exploration/budget preset. Note RL-ViGen groups `DrQ(v2), CURL` against everything else **twice** —
here and in `feature_dim` — so both should be decided together.

## 1. What is true of all twelve  ·  [LIVE]

**None of these methods was published on robosuite 7-DoF manipulation.** Eight are
DMControl/DMControl-GB locomotion methods; four are Procgen discrete-action methods. Every
hyperparameter is therefore *mapped*, never *inherited*.

Of the four DMC-GB methods that did evaluate manipulation at all: RAD never did; SVEA used a
Kinova Gen3 restricted to a **2-D action space** with the environment code **never released**;
SODA likewise, unreleased; only SGQN released manipulation code (an xArm7), and shipped it with
author-admitted broken files. **So there is no public precedent for any of these methods on a
full 7-DoF continuous manipulation task.**

**The Procgen four are discrete-action in every released implementation.** PPG's Gaussian branch
is a dead stub that raises `ValueError`; a user who tried a `Box` action space (Issue #3, 2021)
was never answered. IBAC-SNI hard-raises on non-`Discrete`. IDAAC's paper reports continuous DMC
results in Appendix E, but **that code was never open-sourced**, and its first author has publicly
cautioned that DAAC "was quite difficult to tune" outside procedural, variable-length settings.

**The action head, now that the repos are local (2026-08-10).** `rraileanu/idaac`'s shipped
`distributions.py` contains **only** `FixedCategorical` / `Categorical` — no Gaussian at all. So
IDAAC's continuous head is not in its released code; it is inferred from Kostrikov's
`pytorch-a2c-ppo-acktr-gail`, which the paper states it builds on, and whose convention is
`AddBias(torch.zeros(...))` — a state-independent, **zero-initialised** log-std, i.e. **σ₀ = 1.0**,
unbounded Normal, no tanh, log-prob summed over dims.

Ours is `DiagGaussianHead(init_log_std=-1.0)` → **σ₀ = 0.368**, otherwise matching (state-
independent `nn.Parameter`, plain `Normal`, no squash, `.sum(-1)`). So one number differs, and it
is `[OURS]` and previously undeclared. It is arguably the better choice — our actions are clipped
to [-1, 1], and σ₀ = 1.0 saturates most samples at the clip — but that is a defence, not a source,
and it should be recorded as a deviation rather than discovered later.

> **Our continuous action head for `ppg`, `ibac_sni` and `ctrl` is original engineering with no
> reference implementation to check against.** The encoder, the PPO core and each method's
> auxiliary machinery can be checked against primary sources; the action distribution cannot. That
> should be said in any write-up rather than left implicit.

**Frame stacking**: released Procgen geometry remains one frame for `ibac_sni` and `ctrl`.
IDAAC uses its authors' DMC continuous-control recipe with three frames. PPG uses that same
authors' DMC comparator as its selected continuous-control adaptation; this does not claim the
OpenAI PPG primary source specifies DMC. Both adapters preserve explicit `frame_stack=1` for
historical C1 checkpoints. RL-ViGen-native five, RAD/SODA, and ALDA retain their native
three-frame paths. Structurally different solution to partial observability.

**Truncation vs. termination — verified from robosuite's own source, not merely repeated.** Three
places in this repo assert "Door/Lift never terminate early" (`replay.py`'s `SacView` docstring,
`trainer_onpolicy.py`'s bootstrap comment, `rlgen/envs.py::RoboEnv.step`'s hardcoded
`terminated = False`) — three repetitions of one claim is not three independent checks of it, and
this project has already found the same wrong sentence copied across files more than once this
session. Traced to the actual source instead (2026-08-14): `RL-ViGen-upstream/wrappers/
robo_wrapper.py`'s `Gym2DMC.step` sets `discount=0.0`/`StepType.LAST` on the underlying gym `done`,
but `rlgen/envs.py::RoboEnv.step` does not read that discount at all — it derives `truncated`
purely from its own step counter against `steps_per_episode` and hardcodes `terminated = False`.
Whether that is faithful to what robosuite itself does turns on robosuite's own `done` computation,
vendored at `RL-ViGen-upstream/third_party/robosuite/robosuite/environments/base.py:433`:
`self.done = (self.timestep >= self.horizon) and not self.ignore_done` — no reference to
`_check_success()` anywhere in that line. `environments/manipulation/door.py` and `lift.py` both
call `_check_success()` only inside `reward()` (a shaping bonus), and neither overrides
`_post_action`/`done`. **So robosuite's own Door and Lift genuinely never terminate early by
construction** — success changes the reward, never `done` — and `rlgen/envs.py`'s
`terminated = False` is a faithful reduction of that fact, not a convenient simplification that
happens to match by luck. This is why `replay.py::FrameReplay.sample` never zeroes the discount on
`done` and `SacView.sample` hardcodes `not_done = 1`: with no true terminal state anywhere in this
benchmark, always bootstrapping is the only correct behaviour, not an approximation of one.
`rlgen/trainer_onpolicy.py`'s GAE bootstrap (`if truncated: boot = learner.value_of(...)`) rests on
the same fact and is correct for the same reason.

---

## 2. The DrQ-v2 family — `drqv2`, `svea`, `sgqn`, `curl`  ·  [LIVE]

All four are RL-ViGen's own implementations, loaded by file path. So the faithfulness question is
about **RL-ViGen's port**, not about our code.

### `drqv2` — DrQ-v2 (Yarats et al., ICLR 2022, arXiv:2107.09645)

The reference arm, and the one `base` is tuned for. `lr 1e-4` `[P]`, `feature_dim 50` `[P]`,
`hidden_dim 1024` `[P]`, `critic_target_tau 0.01` `[P]`, `stddev_clip 0.3` `[P]`,
`update_every_steps 2` `[P]`, `nstep 3` `[P]`, `batch 256` `[P]`, `num_seed_frames 4000` `[P]`.

Two divergences, both `[OURS]`:
- **replay capacity 1e5**, where DrQ-v2 uses **1e6** (only `quadruped_run` drops to 1e5). Ours is
  DrQ **v1**'s value. At 500k frames a 1e5 buffer holds the most recent 20% and evicts the rest.
- **`stddev_schedule: linear(1.0,0.1,500000)`** is DrQ-v2's **medium-tier** string, whose budget is
  3.1M frames — noise finishes annealing at 16% of training. Paired with our 500k budget it
  finishes at the last frame, so the agent never trains under low noise. See `PREMISES.md` P7.

DrQ-v2's repo is the **best-behaved** of all sources here: it ships per-task YAMLs that reproduce
the paper without undocumented CLI overrides.

**Pipeline audit, 2026-08-14**: `self.aug` (`RandomShiftsAug`) is called only inside `update()`;
`.act()` never references it, and separately, `eval_mode=True` selects `dist.mean` — a value
structurally independent of the exploration-noise schedule argument — so there are two independent
guarantees against training-time noise leaking into eval, not just one. No reward transform beyond
raw `target_Q = reward + discount*target_V`. Clean.

### `svea` — SVEA (Hansen et al., NeurIPS 2021, arXiv:2107.00644)

**Two divergences, and the first is substantial.**

1. **Wrong strong augmentation.** Canonical SVEA's strong augmentation is **random convolution**.
   RL-ViGen's `algos/svea.py` imports and applies **`random_overlay`** — which is *SODA's*
   augmentation, offered in the SVEA paper only as a comparison variant.
   **This is why our `svea` declares a Places365 requirement at all: canonical SVEA needs no
   external dataset.** It also means `svea` and `soda` now share an augmentation source rather than
   contrasting two different ones — which weakens the comparison they were included to make.

   > **Challenged 2026-08-25 by an external reviewer, and the wording survives — but read the
   > qualifier, because they missed it and so might the next reader.** Their objection: SVEA's
   > contribution is the *objective* (Q-targets on unaugmented observations) applied on top of a
   > choice of augmentation, and the SVEA paper itself reports overlay among its augmentations —
   > so calling overlay "SODA's" overstates the divergence. **The clause above already concedes
   > exactly that** ("offered in the SVEA paper only as a comparison variant"), so the two positions
   > are compatible; the reviewer read the first half of the sentence as the whole claim. They
   > flagged their own point as recollection rather than a lookup, and it has **not** been checked
   > against the SVEA paper by either side.
   >
   > What is worth taking from it is that this item is filed as "substantial" while its actual
   > content is "upstream picked the paper's secondary augmentation over its headline one." The two
   > consequences asserted above — the Places365 dependency, and `svea`/`soda` sharing a source —
   > hold under either reading and are the load-bearing part. Divergence 2 (DrQ-v2 base, not SAC)
   > is untouched by the objection and is the larger of the two.
2. **Different base learner.** Canonical SVEA is `class SVEA(SAC)`. RL-ViGen's is DrQ-v2-based.
   Two different "SVEA" numbers exist in the literature for exactly this reason; the registry
   already records this and labels the backbone.

**Checked and cleared**: Hansen's repo carried a ~15-month regression — **both commits verified
directly in the cloned repo** (`35a1eed`, 2022-09-10, *"fixed next_obs aug"*, which switched
`sample_drq()` to `sample_svea()`; `ff9c0aa`, 2024-01-03, *"fix subtle discrepancy in svea aug"*) —
where `random_shift` stopped being applied to `next_obs`,
contradicting the paper's Algorithm 1. RL-ViGen was published inside that window, so this was a
live hypothesis. **Refuted**: `svea.py:296` is `next_obs = self.aug(next_obs.float())`. Its loss
form `0.5 * (critic_loss + aug_loss)` is also exactly α=β=0.5 `[P]`.

**Pipeline audit, 2026-08-14**: `.act()` is a byte-for-byte copy of `drqv2.py`'s and never touches
`self.aug`/`random_overlay` — both live only inside `update()`. Clean. One cosmetic finding: `svea.py`
defines its own `class Encoder` (a copy of `drqv2.py`'s 4-layer encoder) that `SVEAAgent.__init__`
never instantiates (it builds `SharedCNN` instead) — dead code, zero runtime effect, not worth
removing on its own but worth knowing so a future reader doesn't mistake it for what SVEA actually
runs.

### `sgqn` — SGQN (Bertoin et al., NeurIPS 2022, arXiv:2209.09203)

#### Active production null — RL-ViGen released-code profile, not Table 6

The live launcher is `runnable/_launch/rlvigen.sh`, which runs RL-ViGen's own Hydra
`train.py` with `cfgs/sgqn_config.yaml`. It **does not** use the retired `rlgen/` adapter
discussed in the historical note below. Therefore the actual primary profile is:

| quantity | RL-ViGen Door/Lift Table 6 | active released-code profile | where the active value reaches computation |
|---|---:|---:|---|
| attribution quantile | `.90` | **`.93`** | `cfgs/sgqn_config.yaml` → `SGQNAgent.quantile` → attribution mask |
| attribution optimizer LR | `8e-5` | **`1e-4`** | `cfgs/sgqn_config.yaml` → `Adam(attribution_predictor.parameters())` |
| optimizer first beta | not the Table-6 field | **`.99`** | `cfgs/sgqn_config.yaml` → attribution optimizer |
| critic consistency coefficient | `.7` | **`.9`, hard-coded** | `algos/sgqn.py::update_critic` |

This is a **named RL-ViGen released-code variant**, not a source-exact reproduction of the
published Door/Lift table. The current one-run-per-algorithm campaign does **not** schedule a
paper-profile arm; its values must not silently replace the released-code null. In particular,
`.7` would require a declared code patch because the release exposes no configuration field for
that loss coefficient. The active values above are pinned by the composed-config test, and the
row's report label is
`SGQN (RL-ViGen released-code profile)`.

> ### Historical retired-port investigation (2026-08-10) — not the production path
>
> An external deep-research pass verified RL-ViGen's **paper** tables verbatim but could not
> retrieve a single line of its **source** (GitHub, jsDelivr, Software Heritage and code-search
> mirrors all robots-blocked). We have the source vendored, so the code side is now closed. It
> does not agree with the paper, and the shipped default agrees with nothing.
>
> | knob | paper (Table 6, Door/Lift) | `cfgs/sgqn_config.yaml` | constructor default | canonical | retired `rlgen/` path |
> |---|---|---|---|---|---|
> | `aux_lr` | **8e-5** | **1e-4** | **0.3** | 3e-4 | **0.3** |
> | `sgqn_quantile` | **0.9** | **0.93** | **0.95** | 0.95 | **0.95** |
>
> **Upstream never runs at 0.3.** Its own `train.py` builds the agent through hydra, so
> `sgqn_config.yaml` supplies `aux_lr: 1e-4`. The `0.3` is a dead constructor default — a trap, not
> a value anyone used. (`scripts/train.sh` does define `aux_lr=8e-5` matching the paper, but the
> lines that would pass it are **commented out**, and that script targets `env=dmc` anyway.)
>
> **The retired adapter hit the trap because it bypassed Hydra.** `load_upstream_module()` loaded
> the class by file path and constructed it directly with its own kwargs; its config never named
> `aux_lr` for `sgqn`, so the constructor default stood. That was real for that retired path and
> latent for the release; it is not a statement about the active launcher.
>
> That retired path was changed to **8e-5** / `.9`, the paper's Robosuite values. This history
> does not choose the active released-code profile or establish that it generated Table 6.

> ### Historical critical finding
> Canonical SGQN uses **`aux_lr = 3e-4`** for the attribution-predictor optimizer.
> RL-ViGen's `algos/sgqn.py:120` defaults to **`aux_lr = 0.3`** — a factor of **1000**, consistent
> with a decimal slip from `3e-4`.
>
> **[CORRECTION 2026-09-05 — THIS FIX IS NOT ON THE PRODUCTION PATH.]** Everything in the block
> below is true of the legacy `rlgen/` package path, which loads `configs/vigen.yaml` through
> `rlgen/registry.py`. **Production does not run that path.** `runnable/_launch/rlvigen.sh:23`
> selects a WHOLE upstream config file (`CFG="${AGENT}_config"`) and runs RL-ViGen's own `train.py`
> on it -- which is the project's null, "each original repository running its own train.py", so it
> is the correct thing to run. The consequence is that the EXECUTED values for `sgqn` are
> RL-ViGen's, from `RL-ViGen-upstream/cfgs/sgqn_config.yaml`:
>
> | parameter | this block claims | production actually runs |
> |---|---|---|
> | `aux_lr` | 8.0e-5 | **1e-4** (`sgqn_config.yaml:54`) |
> | `sgqn_quantile` | 0.9 | **0.93** (`:56`) |
> | `aux_beta` | 0.9 | **0.99** |
>
> The catastrophic `aux_lr = 0.3` constructor default IS still avoided on the production path,
> because RL-ViGen's own config overrides it -- so the danger this block was written about is
> genuinely absent. What is wrong is only the claim about WHICH value we run.
> `notes/CLAIMS-LEDGER.md` already said 1e-4 and was right; this block is the stale one.
> Surfaced by `scripts/audit_executed_hyperparameters.py`.
>
> We inherited it. **FIXED 2026-08-10**: `configs/vigen.yaml` now sets `aux_lr: 8.0e-5` and
> `sgqn_quantile: 0.9`, and `rlgen/registry.py` passes `sgqn_quantile` through (without that, the
> config could not reach the knob at all). Verified on the constructed agent via
> `tools/dump_constructed_hyperparams.py`.
>
> Nothing crashed. **And the reason it matters is stronger than "the attribution head cannot
> learn"** — see the next block.

> ### What `aux_lr` actually trains: the SHARED ENCODER
> `AttributionPredictor` holds the encoder **as a submodule, by reference**, in both codebases:
>
> ```python
> # RL-ViGen-upstream/algos/sgqn.py:108   (canonical: SGQN/DMC/src/algorithms/modules.py:343)
> class AttributionPredictor(nn.Module):
>     def __init__(self, action_shape, encoder):
>         self.encoder = encoder          # <-- the shared encoder
> ```
>
> and RL-ViGen constructs it with the agent's own encoder (`sgqn.py:125`); canonical passes
> `self.critic.encoder`. So `Adam(self.attribution_predictor.parameters(), lr=aux_lr)`
> **optimises every encoder parameter at `aux_lr`**, while actor and critic read from that same
> encoder and are optimised at `lr=1e-4`.
>
> `aux_lr` is therefore not a peripheral knob — it is the rate at which the saliency objective
> reshapes the representation both heads consume. That *is* "saliency-**guided**". A dead default
> of `0.3` meant the shared encoder was being driven at ~3000x canonical while the rest of the
> agent read from it, with a bounded BCE loss that never produces a NaN and an env that keeps
> stepping. This is the sharpest instance in the repo of the silent-failure class the audit exists
> to catch.
>
> **Not** the mechanism an external research pass proposed ("exploding covariance,
> `Sigma -> inf`, in the Gaussian policy"): the aux optimiser never touches the actor, and
> `binary_cross_entropy_with_logits` on a detached mask cannot diverge that way. The failure is
> representation corruption, not policy-head blow-up. Do not repeat the covariance story.
>
> *Method note:* tracing only the predictor's **forward call sites** suggests it is a dangling
> diagnostic head (its output feeds its own loss and, in canonical, TensorBoard images — the mask
> that reaches the critic comes from critic **gradients**, `compute_attribution`). That reading is
> wrong, and would have argued for reverting a correct fix. **Parameter ownership, not output use,
> decides what a learning rate touches.**

The consistency-loss weight is worth stating carefully, because three sources give three values:

| | value | note |
|---|---|---|
| canonical `sgsac.py:67` | **0.5** | gated by `if self.consistency:` |
| **RL-ViGen `algos/sgqn.py:172`** | **0.9** | ungated, hardcoded — **this is what we run** |
| RL-ViGen supplementary Table 6 | **0.7** (Door, Lift) | 0.5 for CARLA (Table 3) |

RL-ViGen publishes a "SGQN critic weight" that **is not a parameter anywhere in their release** —
`algos/sgqn.py:120` takes only `(aux_lr, aux_beta, sgqn_quantile, **kwargs)` and `sgqn_config.yaml`
has no such key. Nobody running their code can reproduce their table. We instantiate their
`SGQNAgent` directly, so we inherit **0.9** exactly as any RL-ViGen user does.

**The active rule:** the released-code null keeps every value it actually ships; no upstream
algorithm literal is edited merely to align a paper table. The current campaign has no
paper-profile arm. The critic coefficient is a loss literal, so changing it would require a
declared patch and a source-to-loss test. Nothing in the active row should imply that Table 6
values were silently applied.

Also dead in canonical: `attrib_coeff`, `svea_contrastive_coeff`, `svea_norm_coeff` are defined in
argparse and **read by no loss**.

Canonical quantile is per-domain — the paper's own table (LaTeX source, `sgqn_arxiv.tex`) gives
**0.95** (Walker walk, Walker stand, Finger spin) and **0.98** (Cartpole, Ball in cup); the DMC
argparse default is 0.90 and the `robot_env` variant uses 0.95 under a different flag
(`sgsac_quantile`). RL-ViGen's constructor defaults to 0.95 and its `sgqn_config.yaml` to 0.93 —
neither matching Table 6's 0.9 for Door/Lift. Attribution method is Captum's `GuidedBackprop`
`[P]`, which matches.

**Canonical SGQN did not tune any of this.** From the paper's own source: *"no fine-tuning of
hyperparameters (learning rates, quantile threshold, etc.) was performed whatsoever."* Its table
also lists a separate SSL optimiser at `Adam(lr=3e-4)` and `N_SL = 2` (our `aux_update_freq: 2`
matches). That provenance explains the Table-6 `8e-5`; the active null nevertheless remains the
released code's complete `1e-4` profile, which is the one predeclared campaign configuration.

**`aux_beta` was the same trap as `aux_lr` above, one knob over, found on the 2026-08-14 pipeline
audit.** `SGQNAgent.__init__(self, aux_lr=0.3, aux_beta=0.9, sgqn_quantile=0.95, ...)`
(`RL-ViGen-upstream/algos/sgqn.py:120`) — unlike `curl`'s registration
(`rlgen/registry.py:356`, `defaults={"aux_lr": 1e-4, "aux_beta": 0.99}`), `sgqn`'s registration
passes no `defaults` dict at all, and `configs/vigen.yaml`'s `sgqn:` block never named `aux_beta`
— so it silently ran on the constructor default with no config path able to reach it, structurally
identical to the `aux_lr=0.3` trap this section already documents in detail. The difference this
time: **the value itself was fine.** 0.9 matches both canonical SGQN's own argparse default
(`ext/SGQN/DMC/src/arguments.py:53`, `ext/SGQN/robot_env/src/arguments.py:58`) and the paper's
stated SSL optimiser (`Adam(lr=3e-4, β1=0.9, β2=0.999)`, `sgqn_arxiv.tex:1246`). So this was an
unrecorded *coincidence*, not a verified decision — the config could have drifted the shared
encoder's momentum on the next unrelated refactor to `SGQNAgent`'s signature and nothing would
have caught it. **[CORRECTION 2026-09-05: that fix, like the `aux_lr` one above, is on the legacy
`rlgen/` path. Production runs `runnable/_launch/rlvigen.sh`, i.e. RL-ViGen's own train.py on
`cfgs/sgqn_config.yaml`, where `aux_beta` is 0.99 -- RL-ViGen's own value, and the correct thing to
run under this project's null. The coincidence argument below still holds for the legacy path.]**
Fixed by adding an explicit `aux_beta: 0.9` line to `configs/vigen.yaml`'s `sgqn:`
block (changes no behaviour — the number was already 0.9) and two tests: one asserting the yaml
file itself sets the key (`test_sgqn_yaml_sets_aux_beta_explicitly`, red-green verified — a test
built from the real yaml value alone could not have caught this, since that value equals the
constructor default it was silently falling back to), and one proving the forwarding mechanism
carries an arbitrary value through the real registry build path
(`test_sgqn_registry_build_path_forwards_aux_beta_when_present`, uses 0.42 specifically because it
cannot coincide with any default). Both in `tests/test_sweep_gaps.py`.

### `curl` — CURL (Laskin, Srinivas, Abbeel, ICML 2020, arXiv:2004.04136)

**Faithfulness is ill-defined here even before our port**, because paper and code disagree on five
values: batch 512 `[P]` vs 32/128 `[C]`; encoder EMA τ 0.05 `[P]` vs 0.005 `[C]`; alpha lr 1e-4
`[P]` vs 1e-3 `[C]`; critic τ 0.01 `[P]` vs 0.005 `[C]`; init temperature 0.1 `[P]` vs 0.01 `[C]`.

On top of that: canonical CURL is SAC-based; RL-ViGen's `CURLAgent` subclasses **DrQ-v2**. So ours
is a third variant. Its lr is 1e-4 (from `base`) where canonical is **1e-3**.

CURL's contrastive loss is **not** a weighted sum with the RL loss — the code runs *alternating*
optimizer steps on a shared encoder. Our `aux_lr`/`aux_beta` knobs describe a mechanism the
original does not have in that form.

**Interpretation caveat that belongs next to any CURL row we report**: RAD (NeurIPS 2020, sharing
four authors with CURL) and DrQ independently show plain augmentation matches or beats CURL, so
the field's reading is that CURL's gains come mostly from the random crop rather than from the
contrastive objective.

**Pipeline audit, 2026-08-14**: `.act()` inherited unmodified from `drqv2.py`, no augmentation
reachable from it — clean, same as every other baseline in this family. Unlike `sgqn` (above),
`curl`'s `aux_beta` **is** correctly threaded (`registry.py:327`'s `defaults` dict, matching
`RL-ViGen-upstream/cfgs/curl_config.yaml` exactly) — the config-reachability check `sgqn` failed,
`curl` passes.

---

## 3. The SAC family — `drq`, `rad`, `soda`, `alda`  ·  [MIXED]

### `drq` — DrQ (Yarats/Kostrikov/Fergus, ICLR 2021, arXiv:2004.13649)

SAC-based, `K=2/M=2` augmentation averaging hardcoded `[P]`. Our `init_temperature 0.1` `[P]`,
`log_std_bounds [-5,2]` `[P]`, `hidden_depth 2` `[P]` are correct.

One live `[OURS]` divergence: **lr 1e-4 where canonical is 1e-3** (10x low — `drq` is built through
the DrQ-v2 builder, so it inherits DrQ-v2's rate). ~~n-step 3 where DrQ is 1-step TD~~ **FIXED
2026-08-10** (`drq: nstep: 1` — see the knob table above and §0a): this line still called it a
live divergence until 2026-08-14, contradicting the knob table 30 lines above it in the same file.
Re-verified directly against the real launch path, not just the doc: `configs/vigen.yaml`'s `drq:`
block sets `nstep: 1`, `train.py` puts `nstep` in `TRAINER_KEYS` (so it reaches `TrainConfig`, not
silently dropped into `hyper`), and `rlgen/trainer.py` builds `FrameReplay(..., nstep=cfg.nstep,
...)` from that same config — every real `drq` launch runs 1-step TD, matching the paper. Fourth
instance this session of one stale claim surviving in one place after being corrected in another
(episodes-reproducibility ×3, `load_state_dict` triage ×1, this ×1) — grepping for a defect's
description keeps missing restatements of its conclusion elsewhere in the same document.

Note the upstream repo ships `batch_size 128` while the paper says 512, and ships no per-task
configs — so "DrQ defaults" do not reproduce DrQ's paper.

### `rad` — RAD (Laskin et al., NeurIPS 2020, arXiv:2004.14990)

Canonical augmentation is **crop** (walker-walk) or **translate** (everything else), rendering
100×100 → 84×84. Ours is `rad_augmentation: random_shift`, declared in the config as a deviation
with the 100→84 note — **`[OURS]`, and correctly labelled as such**.

`[OURS]` divergence: **n-step 3; RAD has no n-step parameter anywhere in its codebase** (1-step TD
only).

RAD's own reproducibility record is poor and worth knowing: batch size disagrees three ways (paper
512, argparse 32, shipped script 128); the `translate` augmentation used for most headline results
**was missing from the initial code release**; `image_size` conventions are inverted between crop
and translate and undocumented; Issue #17 ("cannot reproduce") is still open.

**Pipeline audit, 2026-08-14**: `RAD` doesn't override `select_action`/`sample_action` (inherited
from `SAC` unmodified, no augmentation there); the only augmentation call site is `RAD.update()`,
reachable only from `.update()`, never `.act()` — confirmed clean of the IBAC-SNI class of
train/eval leak. No reward transform anywhere in `rad.py`. Worth flagging as informational, not a
bug: `rlgen/algos/soda_utils.py::ReplayBuffer` (the vendored reference class) bakes
`random_crop`/`random_shift` directly into its own `sample()` — but that class is never
instantiated anywhere in `rlgen/` (the real path is `rlgen/replay.py::FrameReplay`/`SacView`,
which applies no augmentation). A future reader grepping `soda_utils.py` could mistake its
`sample()` for the live path; it is not.

### `soda` — SODA (Hansen & Wang, ICRA 2021, arXiv:2011.13389)

**Our closest match in this family.** `soda_tau 0.005` `[P]`, `soda_batch_size 256` `[P]`,
`aux_update_freq 2` `[P]` all correct. Our aux lr is 1e-3, which follows the **repo** `[C]`; the
paper says 3e-4 `[P]`. Pick one and state it (Q5).

Implementation detail worth preserving if this is ever rewritten: SODA's auxiliary encoder is a
**live reference to the critic's encoder**, not a copy — only the momentum target is a deepcopy. A
reimplementation using a separate copy diverges from official behaviour.

`[OURS]`: n-step 3 vs 1-step.

**Pipeline audit, 2026-08-14** (preprocessing/reward/postprocessing sweep): augmentation
(`random_shift` + `random_overlay`) lives only inside `update_soda()`, reachable exclusively from
`.update()` — confirmed no path from `SacAdapter.act()` reaches it, so the IBAC-SNI class of
train/eval augmentation leak does not recur here. No reward transform anywhere in `soda.py`.
**Found and FIXED**: `SODA.train(self, training)` gated `self.predictor.train(training)` behind
`hasattr(self, 'soda_predictor')` — that attribute is never set anywhere (the real one, set in
`__init__`, is `self.predictor`), so the guard was always false and the call never ran. Confirmed
numerically inert rather than left unfixed on that basis alone: `self.predictor.encoder`'s
`shared_cnn`/`head_cnn` are the *same live objects* as `self.critic.encoder`'s (already documented
above), so they were already correctly toggled via `self.critic.train(training)`; the only
submodule that was stuck at its construction-time `training=True` was `SODAPredictor.mlp`'s
`BatchNorm1d`, which is exercised exclusively inside `update_soda()` (training-only, never called
from eval) — so being permanently in train mode there is behaviourally identical to being
explicitly re-set to it before every training call. Fixed anyway: `rlgen/algos/soda.py`'s `train()`
now calls `self.predictor.train(training)` directly, no guard needed since the attribute is always
set.

### `alda` — ALDA (Batra & Sukhatme, ICML 2025, arXiv:2410.07441)

> **The identity question is resolved.** DZ's brief cites arXiv **2001.01046** — *Adversarial-Learned
> Loss for Domain Adaptation* (AAAI 2020), an **image-classification** paper with no agents or
> environments. Our port implements arXiv **2410.07441**, *Associative Latent DisentAnglement*,
> which is a genuine visual-RL generalization method. They are unrelated papers sharing an acronym.
> **The port is right and the brief's citation is an error** — one to raise with DZ, not a decision
> for us.

Canonical: SAC base (SVEA-derived codebase), QLAE with a softmax associative-memory quantizer,
latent dim 12, 12 codebook values, temperature β=100, weight decay 0.1, **batch 128, actor/critic/
encoder/decoder lr 1e-3, γ 0.99, frame stack 3**, on DMControl-GB.

Our `AldaConfig` matches on lr, batch, discount and frame stack — **faithful**, and it carries
source tags already. The extrapolation is the benchmark: ALDA has never been evaluated on robosuite.

**Historical retired-port finding — not a production `runnable/alda` setting.**
`AldaConfig.utd` defaulted to `1.0`; the field's own comment derived a *physics-substep* rate of
`0.25` when action repeat changes from the paper's 4 to RL-ViGen's 1. That derivation does not
mean the source replay ratio was 0.25: one source action-repeat-4 transition is still one replay
item. The default was never corrected to match that comment, and nothing in
`configs/vigen.yaml`'s `alda:` block overrode it, so every launch would have run at the higher
physics-substep rate. This is not a hypothetical: `rlgen/algos/alda/{nets,config,agent,metrics}.py` are
byte-identical to the sibling gen-rebuttal project's `vigen_alda/` (verified by `diff`), which ran
this exact configuration on real GPUs. Its `STATE.md` D1: `utd=1.0` diverged 3 Lift runs across 2
seeds by ~141k frames (`critic/loss > 1e8`, Q above the reward ceiling, policy entropy collapsing
negative); `utd=0.25` cleared 220k on both seeds with `critic/loss` in `[0.46, 0.68]`. Corrected to
`0.25`, pinned by `tests/test_sweep_gaps.py::test_alda_utd_defaults_to_its_derived_faithful_value`
and a second test that builds through the real registry path
(`test_alda_registry_launch_path_actually_carries_the_faithful_utd`), both red-green verified.

The preceding result belongs to the retired `rlgen/algos/alda` port. Production launches
`runnable/alda`, whose current loop performs one learner update per newly collected Door replay
transition and has no `utd` field. Review 14 corrected the denominator: a source action-repeat-4
transition is still one replay item, not four. Therefore `0.25` is not a source-fidelity
restoration for the production path. The Lift/retired-port divergence remains a useful stability
prior; a Door sensitivity probe at 1.0 versus 0.25 is required before changing the operational
default, and any change should be labelled a target-specific adaptation.

Also corroborated: the same sibling project independently confirmed `action_repeat=1` and the
truncation-bootstrapping fix (`not_done=1` at the horizon, never at `d=1`) — both already present
here, inherited with the vendored files.

**Checked, corrected twice, and resolved — the sibling's R20 does NOT apply here, but only because
of a mechanism nobody had actually measured until now.** First pass: `VGBWrapper.seed()`
(`vgb_wrapper.py:371`) is never called anywhere in this repo, robosuite's `deterministic_reset` is
unconditionally `False`, and I wrote that placement was therefore unseeded exactly as it was in
gen-rebuttal before their fix. **That was also wrong** — I had not checked how `evaluate()` itself
calls the environment. It does: `rlgen/evaluate.py:245` calls `np.random.seed(s)` — with `s` a
deterministic, protocol-derived value from `_episode_seed` — immediately before every
`env.reset()`, for every episode of every scene. That function's own docstring claimed this does
**not** achieve byte-reproducibility and cited a named test as evidence
(`test_real_env_episodes_vary_but_are_not_byte_reproducible`). **That test did not exist anywhere
in the repo** — the claim had been written, not measured, and it was also wrong: measured directly
on the real backend (`tests/test_real_env.py::test_real_env_reseeded_episode_reproducibility`, new
2026-08-13), re-seeding to the same value before reset gives a byte-identical episode, and a
different seed reliably diverges. So this repo already has the property gen-rebuttal's R20 fix
exists to provide — evaluating the same checkpoint twice reproduces the same numbers — via a
different, finer-grained mechanism (per-episode rather than per-worker seeding), that had simply
never been checked. `evaluate.py`'s docstring corrected to state the true, now-measured behaviour.

Kept as a methodological note rather than trimmed: two consecutive wrong guesses about the SAME
question, in the SAME paragraph, before checking the actual call path — worth leaving visible as a
concrete instance of "an argued property is not a measured one," the exact rule gen-rebuttal's own
R20 entry states about its own prior mistake on this identical question.

**Pipeline audit, 2026-08-14**: ALDA uses **no image augmentation at all** — grepped `agent.py`,
`nets.py`, `config.py`, `metrics.py` for every augmentation-shaped name used elsewhere in this repo
(`random_shift`/`random_crop`/`random_overlay`/`random_conv`/`aug(`/`self.aug`); zero hits outside
comments. Its regularisation is the VQ-VAE reconstruction/commitment loss, not augmentation, so
the IBAC-SNI class of train/eval leak this audit specifically hunted for has no mechanism to occur
through here. The one thing that IS train/eval-sensitive — `AldaAgent.act()` explicitly toggles
`self.eval()`/restores prior mode around every forward pass, belt-and-suspenders on top of the
outer `agent.train(False)` bracket in `rlgen/trainer.py` — is provably a numerical no-op: every
normalisation layer in ALDA's vendored networks is `GroupNorm`/`LayerNorm` (no `BatchNorm`/
`Dropout` anywhere), and the code's own comment at `agent.py:401-404` already says so. Preprocessing
consistency between `act()` and `update_from_batch()` also checked directly: both paths go through
the identical `preprocess`/`_fold`/`compute_embeddings` chain on the same uint8 contract enforced
at `rlgen/envs.py`'s boundary; no divergent assumption found.

---

## 4. The PPO family — `idaac`, `ppg`, `ibac_sni`, `ctrl`  ·  [MIXED]

All four share `rlgen/trainer_onpolicy.py`, and therefore share `PREMISES.md` P9: exactly one
environment (`num_envs=1`, hardcoded by the trainer, not a config choice — see
`rlgen/trainer_onpolicy.py`'s own docstring).

**Port-era audit trail (historical; superseded by the clone-era entries below).** **CORRECTED
2026-08-13 — the two paragraphs this replaces were wrong, and traceably so: both read
`IdaacConfig`'s bare dataclass defaults instead of the launch config that every real run actually
uses.** That is the identical mistake the on-policy family's own `test_contract.py::KNOWN_LR_DROPS`
exists to catch for `lr` — a value can be silently different between "what the dataclass says" and
"what a real build constructs" — and it went unnoticed here for the same reason: nobody built the
agent and read the constructed config back before writing the claim down. Corrected by doing that.

- **Rollout size in the discarded port.** `configs/vigen.yaml` overrides `num_steps: 2048` in
  **all four** of `idaac:`, `ppg:`, `ibac_sni:` and `ctrl:` — that port ran a 2048-sample rollout,
  not 256. With
  IDAAC's `num_mini_batch=32` that is **64 samples per minibatch**, matching Appendix E's own "32
  minibatches of a 2048 rollout = 64 samples each" exactly, not the "8 samples" previously claimed.
  Verified two ways: `IdaacConfig`'s own dataclass default is now corrected to `num_steps=2048`
  (so it stops lying about a real run), and independently, directly against the real
  `RolloutStorage` tensor a training loop populates
  (`tests/test_sweep_gaps.py::test_idaac_real_minibatch_size_matches_appendix_e...`), which would
  catch a wrong answer even if the config lied again.
- **`gamma` in the discarded port.** All four yaml blocks explicitly set `gamma: 0.99`, not
  Procgen's `0.999` — verified by reading `configs/vigen.yaml` directly rather than either
  family's dataclass default. **The two port-era families already optimised the same discount**;
  there was never a live divergence here, only a stale reading of it.

The properties on `IdaacConfig` that computed from `num_envs` (`rollout_size`, `minibatch_size`,
`total_updates`) inherited a `num_envs=8` default from the sibling gen-rebuttal project, where it
IS wired to a real `SubprocVecEnv` — here nothing reads it, so those properties were silently 8×
the real values. Not load-bearing (`feed_forward_generator` derives its batch size from the real
storage tensor, never from these properties — see above), but corrected anyway: `num_envs` now
defaults to `1`, matching what the trainer actually runs.

- **In the discarded port, `normalize_reward` is declared `True` (the default, for all four
  methods) and does NOTHING.**
  Found 2026-08-14 while auditing this project's own pipeline for preprocessing/reward/truncation
  differences, not by inspecting `idaac/config.py` in isolation. `IdaacConfig.normalize_reward:
  bool = True` and `reward_clip: float = 10.0` are copied verbatim from gen-rebuttal's
  `vigen_idaac/config.py` (same values, same `[T3]`/`[IK]` comments), and `RolloutStorage.rewards`
  (`idaac/storage.py:40`) is itself commented `# normalized, + boot value`. **None of that is
  true here.** Grepped the whole `rlgen/` tree for `normalize_reward`/`reward_clip`/
  `RunningMeanStd`: the only hits are the two config declarations and one docstring reference in
  `metrics.py` — no code anywhere reads either field. `RolloutStorage.insert` writes
  `self.rewards[t]` straight from the raw per-step `reward` passed in from
  `trainer_onpolicy.py`, itself straight from `env.step()` — unnormalised, unclipped, at every
  layer. **Confirmed by checking WHY, not just THAT**: gen-rebuttal's own `envs.py` has a real,
  working implementation — `_RewardBookkeeping`/`RunningReturnStd`
  (`gen-rebuttal/vigen-idaac/vigen_idaac/envs.py:36-109`), Welford-tracking the running variance of
  the *discounted return* (not the raw reward) and applying `reward / sqrt(ret_rms.var + 1e-8)`
  clipped to `±reward_clip`, matching `[IK]`'s (Kostrikov's pytorch-a2c-ppo-acktr-gail)
  `VecNormalize.ret_rms` exactly. It lives in gen-rebuttal's ENVIRONMENT WRAPPER, not in
  `algo.py`/`storage.py`/`config.py` — so when this repo's own registry note says "algorithm files
  copied from ../gen-rebuttal/vigen-idaac," the copy brought the config dataclass (defaults
  included) but not the environment-layer mechanism those defaults describe, because this repo's
  `rlgen/envs.py` is an unrelated, from-scratch robosuite wrapper with no equivalent. **Not yet
  fixed.** Consequence: PPO/GAE value-function training is known to be sensitive to reward scale,
  and VecNormalize's return normalization is a standard, often load-bearing stabiliser in the
  reference implementations `idaac`/`ppg`/`ibac_sni`/`ctrl` are all built on — training all four
  on raw, unnormalised Door/Lift reward is a real, presently-live divergence from what their own
  declared configuration (and the paper lineage it cites) says should happen, not a cosmetic one.
  That was true only of the discarded port-era state. The clone-era runners have since produced
  real training artifacts; this reward-normalisation divergence must therefore be treated as a
  live configuration fact and reported with any result, not as a hypothetical pre-run warning.

### `idaac` — IDAAC (Raileanu & Fergus, ICML 2021, arXiv:2102.10330)

The only one of the four with *any* continuous-control precedent — Appendix E, DMControl, whose
code was **never released**. That column specifies γ **0.99**, rollout **2048**, lr **3e-4**, 10
PPO epochs, E_V=9, N_π=32, α_a=0.1, α_i=0.1.

**Current clone-era execution (2026-09-05):** γ **0.999**, per-environment rollout **256**, and
lr **5e-4** come from the live launch path. The 256-step trajectory length matches the released
per-environment default; the production accommodation is `num_processes=4` rather than the
released 64, so each update has 1,024 rather than 16,384 samples. This is a parallelism/batch-
diversity divergence, not a shortened trajectory. The older paragraph below is retained as a
port-era audit trail and must not be read as the current clone configuration.

Also independently corroborated by the sibling gen-rebuttal project, which shares this exact port
(`registry.py`: "Algorithm files copied from ../gen-rebuttal/vigen-idaac"). That project ran real
GPU training at this configuration and found the trust-region violation Appendix E's literal
`E_pi=10` produces at this rollout size (`clipfrac` climbing 0.12→0.56 over 10 updates) — which is
exactly why `kl_early_stop`/`target_kl` exist here (`[F:R16]`, `config.py`). It also found and fixed
the Gaussian action-head init (unsquashed mean, σ=1 too wide for `[-1,1]` actions — our
`init_log_std=-1.0`, `mean_head_gain=0.01` match its fix) and an over-wide order discriminator with
non-canonical init (our `disc_hidden=0` = IDAAC's own linear default, xavier conv init — match its
fix). None of those three had to be independently re-discovered here; they arrived with the ported
files. The old γ=0.99/rollout=2048 claim belongs to the discarded port configuration. The live
clone configuration is the one stated above; its evidence and unresolved transfer question are
tracked in the production records and `notes/faithfulness-reconciliation.md`, rather than being
inferred from this historical port paragraph.

The first author has publicly stated DAAC "was quite difficult to tune" on DMC and recommends
procedural, variable-length environments instead — a direct, author-sourced caution about
transferability to a fixed-task manipulation benchmark.

Reproducing IDAAC's own headline numbers requires `--use_best_hps` (per-game tuned values); the
checked-in defaults are "best overall" and two separate issues report failure to reproduce without
it.

### `ppg` — PPG (Cobbe et al., ICML 2021, arXiv:2009.04416)

**Correct**: `n_policy_phases: 32` = N_π `[P]`, `aux_epochs: 6` = E_aux `[P]`,
`aux_beta_clone: 1.0` = β_clone `[P]`, γ 0.999 `[P]`, λ 0.95 `[P]`, rollout length 256 `[P]`.

**Current clone-era execution (2026-09-05):** the released `train.py` default is `num_envs=64`
per MPI worker with per-environment rollout length 256. The repository's documented invocation
launches four MPI workers whose gradients synchronize, so the effective upstream update batch is
`4*64*256 = 65,536`. The production port uses one worker and `num_envs=8`, or 2,048 samples:
a **32x reduction in effective batch** while retaining the exact per-environment rollout. Its lr
is 1e-4 vs 5e-4 `[P]`, and its continuous head has no released reference. The smaller batch
changes gradient noise and the number of updates; it is not a shortened trajectory.

Worth recording: PPG's released code has **no gradient clipping at all**, and its
`RewardNormalizer` uses γ=0.99 internally while the GAE/value path uses 0.999 — two discount
factors coexisting in one run, in the official implementation.

Interpretation caveat: **"PPG Reloaded" (ICML 2023)** disputes the original causal explanation,
arguing the gains come from policy regularization and data diversity rather than the phasic
dual-network structure per se.

**Pipeline audit, 2026-08-14 — a structural finding, not a hyperparameter one.**
`PPGLearner.__init__` forces `cfg.algo = "ppo"` (`rlgen/algos/onpolicy_ext.py`), which in the
shared `Learner.__init__` means the single shared-trunk head (`self.value_net` stays `None` —
verified directly: `Learner.__init__` only constructs a separate `ValueNet` `if cfg.algo != "ppo"`,
`idaac/algo.py`). **So this implementation has exactly one network and one value head, used for
both the main PPO phase's value loss AND the "auxiliary phase's" value loss** — `v_aux =
self.policy.value(obs[sl])` (`onpolicy_ext.py:101`) routes through the identical
`value_from_feat(encode(...))` → same `self.aux` `nn.Linear` the main phase already trained every
minibatch of every policy phase. PPG's actual mechanism gives the value function a genuinely
separate, more-frequently-updated network, and the auxiliary phase distils FROM that into the
policy trunk under KL protection; with one shared head there is nothing decoupled to distil from —
the aux phase re-fits the same head to targets (`storage.returns`) it was already fit to during the
ordinary policy phase, protected by the same `aux_beta_clone` KL term. The class's own docstring
("distils the value function into the policy network's auxiliary head") presupposes two things;
there is one. Not yet decided whether/how to change this — it is a real architectural gap under
otherwise-matching hyperparameters (§ above), not something to silently patch. A genuine
decoupled-value-network PPG would be a more involved change than a config fix; flagging for a
decision rather than building it unprompted.

Smaller, separately real: the auxiliary phase's minibatch loop
(`for _ in range(self.aux_epochs): for i in range(0, n, mb)`, `onpolicy_ext.py:96-97`) iterates the
identical fixed-index partition, in the same order, on every one of the 6 `aux_epochs` — no
reshuffle between epochs, unlike the main phase's `feed_forward_generator`
(`idaac/storage.py:111-124`), which builds a fresh `SubsetRandomSampler` every call. Standard
multi-epoch SGD reshuffles per epoch to decorrelate minibatch composition across passes; this
doesn't.

**CONFIRMED 2026-08-14, upgraded from "plausible" to a real divergence** — `ext/phasic-policy-
gradient/phasic_policy_gradient/ppg.py` was read in full this session for the first time (only
`reward_normalizer.py` had been checked before). `learn()`'s aux-phase loop (`ppg.py:262-276`)
calls `aux_train` once per aux epoch, and `aux_train` (`ppg.py:178-201`) calls
`make_minibatches(segs, mbsize)` fresh every time — which does `th.randperm(len(envs_segs))`
internally (`ppg.py:171`), a new permutation on every call. The reference reshuffles every aux
epoch; this repo's current implementation does not. No longer "no reference exists to check
against" — one does, and it disagrees with what's here.

Also found in the same reading pass, not previously documented at all: the reference's aux phase
trains on THREE loss terms, not two — `pol_distance` (the KL-clone term this repo's
`aux_beta_clone` already implements), `vf_aux` (train a small head attached to the *policy's own*
encoder to predict the value target — what this repo currently calls "the auxiliary phase"), and
**`vf_true`** — the aux phase *also* continues training the separate value network itself
(`ppg.py:110-115`), which this repo's implementation does not do at all, on top of not having a
separate value network to train in the first place (the dual-network gap, above). The reference
also uses its own separate Adam optimizer for the aux phase (`aux_lr`, `ppg.py:239`), not the
policy phase's optimizer. All three are now `docs/REGISTER.md` entries, not built yet.

### `ibac_sni` — IBAC-SNI (Igl et al., NeurIPS 2019, arXiv:1910.12911)

**Our best-sourced PPO-family entry.** `vib_beta: 1e-4` matches CoinRun `[P]`; `sni_lambda: 0.5`
matches the paper's explicit recommendation for IBAC/VIB `[P]`.

Two things to check our implementation against, which the canonical record makes precise:
- **β is per-benchmark, not universal**: 1e-3 (toy), 1e-6 (Multiroom), 1e-4 (CoinRun). Taking the
  CoinRun number to a new benchmark is a choice, not an inheritance.
- **SNI's mechanics**: `G^SNI = λ·G_AC(π̄^r, π̄, V̄) + (1−λ)·G_AC(π̄^r, π, V̄)` — the critic is
  **always** the deterministic V̄ in both terms; only the policy-gradient numerator alternates
  between the deterministic mean-policy and the noisy sample. SNI never injects noise into the
  value loss.

**RESOLVED 2026-08-13, CORRECTED 2026-08-14 — a wrong finding replaced a right one; both are kept
here because the mistake is instructive.** `VIB.forward(feat, sample)` and `encode_with_vib`
(`rlgen/algos/onpolicy_ext.py`) match DZ's own reference
(`~/Downloads/IBAC_SNI_torch/train-procgen-pytorch/common/policy_ibac.py`) formula-for-formula:
same `mu`/`log_sigma` heads, identical `[-10.0, 2.0]` clamp, identical `z = mu + std*eps` vs
`z = mu` dual pass, identical KL. That part was always right.

**What I got wrong 2026-08-13**: I read `ValueNet`'s class definition, saw it carries its own
`ImpalaEncoder`, and concluded IBAC-SNI's critic uses it — "the critic never sees the bottleneck at
all." **That was never checked against `cfg.algo`.** `IBACSNILearner.__init__` sets
`cfg.algo = "ppo"` (`onpolicy_ext.py:162`), and `Learner.__init__`
(`algos/idaac/algo.py:39,44-47`) only constructs a separate `ValueNet` `if cfg.algo != "ppo"` — for
`"ppo"` it stays `None`. `value_of` then calls `self.policy.value(obs)`, which is
`value_from_feat(self.encode(obs))` — **`self.encode` IS the VIB-patched method.** So the critic
was never architecturally separate; it was reading the exact SAME single forward pass as the
policy, via the SAME `feat` that `Learner.update()`'s shared training loop computes once per
minibatch (`algo.py:96,106`: `lp, ent, feat = self.policy.evaluate(obs, act)` then
`v = self.policy.value_from_feat(feat)`).

**What was actually wrong, found by tracing that shared loop precisely**: during TRAINING that
single `feat` is `encode_with_vib`'s SNI-mixed, noise-injected pass — so the critic trained on
literally the same noisy representation as the policy, which is **more** entangled with the noise
than any of three independent references allow, not less. All three — original TF CoinRun
(`ext/IBAC-SNI/coinrun/coinrun/policies.py:149-161`), the authors' own PyTorch port
(`ext/IBAC-SNI/torch_rl/model.py`, `self.critic(bot_mean)` under SNI), and DZ's Procgen port
(`policy_ibac.py`'s `_heads(z,...)`) — route the value head through the **deterministic** bottleneck
pass specifically, with the original TF code's own comment stating why: *"Use deterministic value
function for both as VIB for regression seems like a bad idea."*

**FIXED 2026-08-14.** `encode_with_vib` now stashes the deterministic pass as a side effect
(`self._last_z_clean`, computed in the same forward call so no extra encoder pass is needed), and
`self.policy.value_from_feat` is separately patched to substitute it for whatever `feat` the shared
core computed the value from — so the policy loss keeps seeing the SNI-mixed pass and the value
loss now always sees the deterministic one, matching all three references. Verified black-box
(`tests/test_onpolicy.py::test_ibac_value_head_never_sees_the_noisy_or_sni_mixed_pass`): before the
fix, three calls to `value_of` at the identical observation in training mode returned three
different numbers (`-0.260, 0.719, -0.056` — measured, not a made-up illustration); after the fix
they are identical, and a gradient still reaches `self.vib`'s parameters through the deterministic
path, so the value loss still trains the shared/bottleneck weights, exactly as every reference does.

The general lesson, worth keeping: **`grep`-level "does class X get used" is not the same claim as
"does this code path route through X" — the routing is decided by a runtime flag
(`cfg.algo`) three layers away from the class definition, and only tracing the actual call chain
the shared training loop executes settles it.**

Also: the released code only ever implements λ ∈ {0, 0.5, 1}; exposing λ as a continuous knob
builds something the original never supported. And `nr_samples` defaults to 1 in code while the
paper's best CoinRun results use 12.

**No continuous-action reference exists anywhere, including DZ's.** `policy_ibac.py`'s action head
is `Categorical(logits=...)` (`:53`), hardcoded for Procgen's discrete `action_size` — confirmed by
reading the file, not inferred from its file name. `Normal` is imported and used **only** for the
VIB latent `z`, never for an action distribution. So the Gaussian action head in
`rlgen/algos/idaac/model.py` (shared by all four PPO-family baselines, IBAC-SNI included) is
re-derived, not ported from anywhere — matching what `rlgen/algos/onpolicy_ext.py`'s own docstring
already said ("Reference read but not reused... the rest is re-derived for a continuous policy"),
now confirmed by reading the reference itself rather than trusting the file path's name.

Note on the literature: essentially every "IBAC-SNI baseline" number in later Procgen papers traces
back through UCB-DrAC's re-run at ~24× smaller compute than the original.

### `ctrl` — CTRL (Mazoure et al., ICLR 2022, arXiv:2106.02193)

Identity **confirmed**: Cross-Trajectory Representation Learning, PPO-based, official code
`bmazoure/ctrl_public` in **JAX** (so any PyTorch version is necessarily a reimplementation).
Confirms CTRL is unrelated to CURL on every axis — the previous repo's `CTRLAgent(CURLAgent)` was
wrong on base learner, objective, and what counts as a positive pair.

Canonical objective: Sinkhorn-Knopp online clustering (`L_clust`) + a MYOW-style cross-cluster
predictive loss (`L_pred`), applied to the **encoder only**, with the policy head updated by the
separate PPO loss.

**Port-era audit trail (historical):** the following structural-divergence list was found by
reading the discarded `rlgen/algos/onpolicy_ext.py` port. It is not the current `runnable/ctrl`
implementation. In the live clone, `loss_cluster` is present and its gradient is applied; the
project restored the released code's commented-out executable lines, and the nearest-neighbour
positive path is inherited from the released repository. Current clone-era wording is in the
summary table above and `notes/faithfulness-reconciliation.md`.

0. **FIXED** — the invented `ctrl_coef` is gone. `pseudocode.tex:57` reads
   `L_CTRL = L_clust + L_pred`, a plain sum with no scalar, and the official repo has separate
   `update_ppo` / `update_daac` / `update_cluster` functions whose only coefficient is PPO's own
   `critic_coeff`. Removed from config and code.

1. **A loss term is missing.** The paper's objective is `L_CTRL = L_clust + L_pred`, and
   Sinkhorn-Knopp clustering is itself a **loss**. Ours replaces it with EMA k-means centroids in
   buffers with no gradient, so `L_clust` does not exist and only `L_pred` survives. The old
   docstring called this "the same role with a simpler update rule" — true of the *assignment*,
   false of the *objective*.
2. **Positives come from the wrong partition.** The paper draws them from **neighbouring**
   clusters — cross-cluster prediction is the entire point of the MYOW-style term. Our `update`
   draws from the **same** cluster (`idx = (assign == c)`, then a permutation of `idx`). The
   docstring said "nearby partition"; the inline comment said "SAME partition"; the code does the
   latter. **Small to fix, and fixing it would make the objective the published one.**
3. **The SSL step shares the policy optimizer** — and the paper source shows exactly how wrong
   that is. `pseudocode.tex` lines 59 and 64 run **two optimizers over disjoint parameter sets**:
   `Adam(φ, ψ_clust, θ_clust, θ_pred, ψ_pred; L_CTRL)` for the encoder and auxiliary predictors,
   and `Adam(π, V^π; L_RL)` for policy and value. **The policy parameters are not in the SSL
   update at all.** Ours puts them in the same optimizer.
4. **`_embed_windows` has no episode-boundary guard — NOT a divergence from CTRL's own reference,
   corrected 2026-08-14.** Found 2026-08-13, lost from active context across a compaction,
   recovered and re-confirmed against the current code 2026-08-14, then **mischaracterized a second
   time** on that same recovery pass by framing it as a bug relative to something CTRL's reference
   guards against. It doesn't. `CTRLLearner._embed_windows` (`rlgen/algos/onpolicy_ext.py`)
   partitions the whole flattened rollout (`storage.obs[:-1].reshape(-1, ...)`) into fixed
   `ctrl_window`-sized windows **by raw index** — no `episode_id` or `done` check anywhere in the
   windowing. The comparison drawn here previously was to `storage.py`'s order-pair sampling for
   IDAAC, which *is* hardened against this failure shape — but that is the wrong reference point.
   **Checked directly against the actual primary source while reading `algo.py` for the hermetic
   module (`ext/ctrl_public/algo.py:90-95`, `extract_windows_vectorized`)**:
   ```python
   def extract_windows_vectorized(array, window_size):
       max_timestep = array.shape[0] - window_size
       sub_windows = (0 + np.expand_dims(np.arange(window_size), 0) +
                      np.expand_dims(np.arange(max_timestep + 1), 0).T)
       return array[sub_windows]
   ```
   This takes only `array` and `window_size` — no `done`/episode signal reaches it at all, and it
   produces sliding (stride-1, overlapping) windows purely by index, the same shape of construction
   as this repo's `_embed_windows`. **CTRL's own official implementation has the identical
   property**: it does not guard windows against spanning an episode boundary either. So this is not
   a case where the reference does something ours fails to do — the reference's own authors made
   the same choice (or never considered it, which the directive treats the same way: nothing settles
   the form beyond what the code does). Faithfully matching this behavior is the no-worse-than-
   reference default (`porting-directive.md` §0); *adding* a guard the paper's own code doesn't have
   would be a deliberate, declared improvement beyond the reference, not a bug fix — and needs its
   own justification (episode lengths here vs. Procgen's) if made, per §4's adaptation-branch-point
   discipline, not silent inclusion in the hermetic port. Left unguarded in the hermetic CTRL module
   by default; whether to deviate is an open, not-yet-decided branch point, tracked in
   `docs/REGISTER.md`, not a defect to close.

`ctrl_clusters` is **not a free parameter, and the constraint is looser than previously stated
here.** **CORRECTED 2026-08-13**: with the real rollout (`num_steps=2048`, `configs/vigen.yaml`'s
`ctrl:` block, not the 256 dataclass default this paragraph previously read) and `ctrl_window=8`,
`_embed_windows` yields `2048 // 8 = 256` embeddings per update, and `configs/vigen.yaml` sets
`ctrl_clusters: 32` — 8 points per cluster on average, thin but workable. Partitioning 256 points
into the paper's 200 clusters (~1.3/cluster) is thin rather than literally degenerate, which it
would have been at the stale 32-points reading; 32 clusters is a real choice made against that,
not a forced one. The cluster count is still downstream of the rollout size, which is downstream
of the `num_envs=1` constraint (`PREMISES.md` P9) — that part stands.

Every one of our CTRL knobs is `[OURS]`:

| knob | `[P]` | ours | factor |
|---|---|---|---|
| clusters | **200** | `ctrl_clusters: 32` | 6× fewer |
| clustering timesteps | T = 2 sampled timesteps | `ctrl_window: 8` | a different quantity |
| samples per epoch | 8192 (32 envs × 256) | 2048 (one env × 2048; corrected 2026-08-13, was stated as 256) | 4× fewer, not 32× |
| lr | 5e-4 | 1e-4 | 5× lower |
| aux loss weight | **none published** — encoder and policy are separate update targets | `ctrl_coef: 0.1` | we invented a coefficient for a combination the paper does not express as a weighted sum |

---

## 5. What would raise fidelity most, per unit of work  ·  [CURRENT-STATE]

**Re-triaged 2026-08-13** — three of the original six items were resolved by fixes already applied
(in this session or earlier), not by new work below; kept here with their resolution stated so the
list stays honest about what changed and why, rather than quietly shrinking.

**Re-triaged again 2026-08-24.** Items 1–8 are unchanged and none of them was resolved in the
interval. Items 9–11 are added from findings made since; §5's admission test is the one this whole
document is keyed to — *would this baseline's number be fair to call that method's result?* — so
several real findings of the last ten days are deliberately **not** here, listed at the end with
the reason, because "absent" and "overlooked" must not read the same.

~~1. `sgqn` `aux_lr` → 3e-4.~~ **RESOLVED, differently than proposed.** Set to `8.0e-5` — RL-ViGen's
own Table 6 value for Door/Lift specifically, not canonical `3e-4`, which is DMC-locomotion-tuned
and which the paper's own text says was never tuned at all ("no fine-tuning of hyperparameters ...
was performed whatsoever"). 8e-5 is the only value anyone tuned *on this benchmark*. See §2 above.

~~2. PPO-family rollout ("8-sample minibatches").~~ **RESOLVED — was never true.** The rollout is
2048 (one environment, `num_steps=2048`), not 256; the "8 samples" reading came from the dataclass
default rather than the launch config. See §4.

~~3. Decide `gamma`.~~ **RESOLVED — was never a live disagreement.** All four PPO-family configs
already set `gamma: 0.99` in `configs/vigen.yaml`; the doc previously compared the wrong (default)
value against the off-policy family and reported a gap that did not exist in any real run. See §4.

4. ~~**Decide `nstep` per family**, still open. 1-step for the seven whose originals are 1-step, or
   declare 3 a deliberate protocol constant and say so.~~ **RESOLVED 2026-08-24 — the question was
   ill-posed for the clone path, which is why it survived three re-triages without moving.** It
   asked for one decision across twelve baselines about a knob that only five of them have, and
   used one name for two different quantities. See [C66](CONSTRUCTION.md#c66).

   - **The five natives already have a per-algorithm value, and it is upstream's own.** The clone
     runs RL-ViGen's hydra configs directly: `drq_config.yaml:21` `nstep: 1`, and `config.yaml:22`,
     `curl_config.yaml:21`, `sgqn_config.yaml:21`, `svea_config.yaml:21` all `nstep: 3`. That is
     exactly the "1 for DrQ, 3 otherwise" split of RL-ViGen's Table 2, reached without anyone
     deciding anything — the null supplies it.
   - **Four of the seven others have no such knob at all**: `ctrl`, `rad`, `soda` and `alda` contain
     no `nstep` anywhere.
   - **The remaining three use the name for a different quantity**, so "1-step or 3-step" is not a
     question that can be asked of them: `idaac/ppo_daac_idaac/storage.py:206` is a per-env *step
     counter* tensor feeding IDAAC's steps-remaining head; `ppg/phasic_policy_gradient/ppo.py:33`
     unpacks `nenv, nstep = reward.shape`, the *rollout length*; `ibac_sni/coinrun/train_agent.py:45`
     passes `nsteps=Config.NUM_STEPS` into baselines-PPO, also a rollout length. None is an n-step
     TD bootstrap.

   The 1-vs-3 framing was correct for the superseded `rlgen/` port, where `nstep` was a **shared
   trainer key** (`configs/vigen.yaml:32`) that one value had to satisfy for everybody — the
   shared-base problem item 2 above records. The clone has no shared trainer, so the knob is not
   shared and there is nothing to decide.
5. ~~**`ctrl_clusters` → 200, or confirm 32 as the deliberate choice.**~~ **DISSOLVED IN THE CLONE
   ERA, 2026-09-04 — same shape as item 4 above.** The choice existed because the port read
   `configs/vigen.yaml`'s `ctrl_clusters: 32` against the paper's 200. **The clone has no such
   config**, and `runnable/ctrl/train_ppo.py:91` declares `flags.DEFINE_integer("num_clusters",
   200, ...)` — so upstream's own default *is* the paper's value, our launcher overrides nothing,
   and `scripts/eval_grid.py`'s `CTRL_DEFAULTS` reconstructs at 200 to match. Nothing to decide and
   no deviation to declare; the 32 was the port's. (Checked because a mismatch here would not be
   cosmetic: flax `from_bytes` fills a *target*, so reconstructing the cluster head at the wrong
   count would fail to load or load mis-shaped.)
   The prior analysis stands on its own terms and is kept: 256 real embeddings/update, so 200
   clusters is thin (~1.3 points each) rather than degenerate.
6. ~~**Answer Q5 once**: faithful to paper, or to repo. It changes `curl`, `soda` and `rad`.~~
   **ANSWERED BY CONSTRUCTION IN THE CLONE ERA, 2026-09-04.** The port had to choose, because it
   re-implemented and every constant was therefore authored. **The clone era's null is each
   original repository running its own `train.py`**, so the repo's value is what runs unless
   someone changes it — and any move toward a paper value is an authored deviation that
   `INTEGRATION-DELTA.md` would have to carry and justify one by one. The question is not open, it
   is settled the other way by the decision to stop porting. What remains is the *reporting*
   obligation: where a repo value differs from its paper, that is a fact about the baseline worth
   stating beside its number, not a knob for us to turn.
7. ~~`ibac_sni`'s value network never sees the information bottleneck.~~ **WRONG DIAGNOSIS,
   CORRECTED 2026-08-14 — see §`ibac_sni` below for the full account.** `cfg.algo="ppo"` means
   IBAC-SNI never constructs a separate `ValueNet` at all; the critic already shared the identical
   forward pass as the policy. The real, verified defect was the opposite shape: the critic was
   seeing *too much* of the noise (the SNI-mixed pass), where every one of three independent
   references (original TF, the authors' own torch port, DZ's port) routes it through the
   deterministic pass specifically. **FIXED.**
8. **CTRL remains the one on-policy baseline with no independent verification available anywhere**
   — not from a sibling project (gen-rebuttal covers only `idaac` and `alda`), not from DZ (his
   reference covers only `ibac_sni`). Every fix applied to it this session (§`ctrl` above) came
   from re-reading the paper's own LaTeX source and the official JAX repo, both now local in `ext/`
   — there is no second, independently-run implementation to cross-check training dynamics
   against, unlike every other baseline in this table.

9. **Decide the entropy coefficient for the four PPO-family baselines — the largest untracked
   fidelity gap now known.** `idaac`, `ppg`, `ibac_sni` and `ctrl` all inherit `0.01`, verified at
   `idaac/ppo_daac_idaac/arguments.py:35`, `ctrl/train_ppo.py:46`,
   `ibac_sni/coinrun/coinrun/config.py:104`, `ppg/phasic_policy_gradient/ppo.py:131`. Their authors
   tuned that against Procgen's **15-way categorical**, whose entropy is bounded by
   `ln 15 = 2.708`. Here it multiplies a **7-D Gaussian**, `7 × ½ln(2πe) = 9.933` at `σ=1` — the
   same coefficient against a term **3.67×** larger, so the exploration pressure these four run
   under is not the pressure their papers report. **Nothing in any diff shows it, because no line
   changed**; it is a divergence created entirely by the target's action space.

   *Measured, so the size is known rather than feared*: a 60k-step `idaac` run moved every one of
   the seven `logstd` components up from exactly 0.0 (to +0.0103…+0.0481, mean `σ` 1.0252), and
   [C6](CONSTRUCTION.md#c6)'s boundary fraction with it, 0.3173 → **0.3293**. Direction as
   predicted, magnitude small **at a budget that is 0.24% of IDAAC's own 25M steps**, and the
   gradient `∂H/∂log σ = 7` is constant, so it does not self-limit the way a categorical's does.
   **Work unit:** one decision, then either nothing or a four-line change. **Whose:** the owner's —
   rescaling a hyperparameter the authors tuned is precisely the kind of change this document
   exists to make visible.

10. **Say what `ctrl` and `ppg` rows can be, given neither can produce a checkpoint as published.**
    > **Evidence added 2026-09-04, decision still the owner's.** Both now DO produce a loadable
    > checkpoint, by a terminal save this project added and declared — so the question shifts from
    > *can a row exist* to *what may it be called*. `ppg`'s was verified to hold **trained** weights,
    > not the construction-time file this item's premise warns about: `pi_logstd` mean 0.00090310
    > against its own `progress.csv` logging 0.000819 at the same frame, i.e. one update further on,
    > which is what a save taken after the last update looks like. `ctrl`'s terminal save loads and
    > was evaluated offline (36.699 on its 2,560-frame checkpoint). **What is still true** is the
    > part that makes this a fidelity item rather than logistics: neither upstream would have
    > produced these files, so a `ctrl` or `ppg` row rests on our save, and `ctrl`'s reported number
    > remains a different estimand (`COMPARABILITY_CONTRACT` §5d) until `evaluate_ppo.py` is adapted.
    `ctrl/train_ppo.py:12` is `# from flax.training import checkpoints`, commented out — and it is
    **upstream's own line**, confirmed identical in `git show HEAD:train_ppo.py` at the pinned
    `ctrl_public @ 7a118c8`; it also ships an `evaluate_ppo.py` that restores a checkpoint its
    trainer cannot write. `ppg` saves only when `LogSaveHelper`'s `ic_per_save > 0`, a name that
    occurs nowhere outside `phasic_policy_gradient/log_save_helper.py` and that no launcher sets.
    `idaac` writes only at `j == num_updates - 1`. This is a fidelity item, not merely a logistics
    one: a row that can only ever be an end-of-run number is a different claim from one carrying a
    curve, and the table must say which it is per baseline rather than presenting both as alike.
    **Work unit:** a sentence per baseline, or two ENABLES-class deviations. **Whose:** the
    deviations are the owner's; the sentence is not.

11. **Verify a run's training distribution before attributing its number to a method.** The `drqv2`
    checkpoints behind this project's only measured retention were trained on pixels matching
    `eval-easy` scene 0 (per-pixel corr **0.942**) rather than the `train` scene 0 their config
    declares (**0.607**, nearly the worst of twenty conditions) — [C54](CONSTRUCTION.md#c54). A
    number from such a run is not unfair to DrQ-v2 because DrQ-v2 was implemented wrongly; it is
    unfair because **the run was not the experiment the row claims**. The control is decisive:
    a checkpoint with per-episode verified provenance scores **424.52 with 20/20 successes** on
    `train` scene 0 where the contested one scores **3.06 with 0/20**. **Work unit:** already
    built — `scripts/watch_training_frames.py` plus `scripts/classify_drift_frames.py`, attached by
    `scripts/run_cell.sh`. **Whose:** mine, and it is now default for every new cell. The residual
    is that **six of twelve baselines record nothing to verify against**
    ([C58](CONSTRUCTION.md#c58)), so for those the check cannot be run at all — which is a
    disclosure the results table has to carry.

**Considered and deliberately excluded**, so their absence is not read as an oversight:

- [C56](CONSTRUCTION.md#c56) (two robosuite envs in one process do not render independently) —
  real and reproducible, but it is a property of *our measuring apparatus*, not of any baseline's
  correspondence to its paper. Its per-scene readings were checked and this project never reads a
  damaged env.
- [C57](CONSTRUCTION.md#c57) (a run diverged to NaN and continued for 70,000 frames) — about run
  validity and our silence about it, not about fidelity to a source. A dead checkpoint is not an
  unfaithful implementation of DrQ-v2; it is not an implementation of anything.
- The `drq` TensorBoard regression — `algos/drq.py:328` calls `entropy()` on a `SquashedNormal`
  under `if self.use_tb:`, which torch does not implement. It is a genuine upstream defect, but it
  lives entirely in a logging branch and changes no number, so it cannot make `drq`'s result
  unfair to DrQ. It costs `drq` its tensorboard artifact and nothing else.
- `curl` cannot run under the MPS shim — a platform limit already recorded in
  [C52](CONSTRUCTION.md#c52), and one that makes `curl`'s row *absent* rather than unfaithful.

---

## 6. From the peer-review record and SECANT (2026-08-10, late session)  ·  [DURABLE]

Eleven OpenReview PDFs plus SECANT's paper and supplementary arrived after the four research
passes — all of them material **every** pass was robots-blocked from.

### 6.1 RL-ViGen's own reviewers pressed on exactly our question

Reviewer **WGQU**, verbatim: *"re-implementing RL algorithms correctly is very hard… before i feel
comfortable using a new implementation of an algorithm… I like to see proof that the
re-implementation matches the original implementation."*

The authors answered with a **fidelity table** giving deltas against published scores:
**PIE-G +5, SGQN +25, SVEA −11.** So RL-ViGen itself reports reproducing SVEA *worse* than
published — which is independent corroboration that the SVEA row is the shakiest of the five we
inherit (we already found it uses SODA's `random_overlay` instead of canonical random convolution).

**CURL and DrQ were deliberately altered**, verbatim: *"we do not utilize a target encoder and
remove the update of momentum parameters related to the encoder… The agents trained with original
code implementation fail to gain any performance in quadruped-run, quadruped-walk these 2 tasks,
while our implementation can gain comparable results."* So RL-ViGen's CURL is not CURL-with-a-
different-backbone; its momentum encoder — the mechanism CURL is named for — is **removed**. Our
`curl` row should say so.

**The Program Chair left three conditions unresolved at decision time**: a CARLA weather-config bug
of uncertain origin; an SVEA reproduction discrepancy in CARLA-easy (56 vs the cited number); and a
demand for **raw per-seed scores**, which were not public at review time.

Two protocol facts only the thread gives:
- RL-ViGen uses a **stratified bootstrap** CI (confirmed by the PC), not a plain percentile CI.
- Its cross-environment aggregate is **min–max normalised**:
  `agg = (1/n) Σ (score_env_i / max_score_env_i) × 100`. Per-task returns stay raw, so this does
  not conflict with our "never normalised" rule — but it means **their headline aggregate and our
  per-task numbers are different quantities**, and must not be compared directly.

### 6.2 RL-ViGen's config confirms the reward setting; SECANT explains its effect

**`reward_shaping: True` is not `[OURS]`: RL-ViGen's own
`envs/robosuiteVGB/cfg/robo_config.yaml` sets `reward_shaping: true`.** SECANT §5.2 independently
describes the same dense-reward setting: *"We use the Franka Panda
robot model with operational space control, and train with **task-specific dense reward**."*
Supplementary §2.2: *"All environments add an extra positive reward upon task completion, in
addition to the dense reward shaping."* And for our task specifically — Door is *"shaped by the
distance between the door handle and the robot arm, and the rotation angle of the door handle."*

That is the mechanism behind our random-policy floor: a distance-shaped per-step reward is exactly
what lets a random arm accumulate return without ever succeeding. **It also strengthens the case
for promoting success rate to the headline metric** (`STATUS-AGAINST-THE-GOAL.md` §3b item 1).

SECANT's robosuite hyperparameters (Supplementary Table 1), for comparison with ours:

| | SECANT | ours |
|---|---|---|
| input | 9×**168×168** | 9×**84×84** |
| frame stack / γ / episode length | 3 / 0.99 / 500 | same |
| training steps | 800K | 500K (RL-ViGen Table 6 says Door 6e5, Lift 8e5) |
| replay / batch | 100K / **512** | 100K / **256** |
| actor, critic, log-α lr | **1e-3** (1e-4 for peg-in-hole) | 1e-3 SAC family, 1e-4 DrQ-v2 family |
| critic target update freq | **4** | 2 |
| feature dim | 50 | 50 |
| **action repeat** | **never stated** — only *"control frequency… 20Hz"* | 1 |
| eval | 10 variations × 10 episodes = 100, **5 seeds, mean ± SD** | 100 episodes, 1 seed so far |

Note the eval-statistic mismatch: SECANT reports mean ± **standard deviation**; RL-ViGen uses a
stratified bootstrap CI. Two different protocols — do not sanity-check one against the other.

### 6.3 CORRECTION to DR_1's Stage 3: do NOT diff against SECANT's robosuite fork

DR_1 recommended diffing our `third_party/robosuite` against SECANT's fork
(`wangguanzhi/robosuite`) rather than PyPI, on the grounds that the PyPI comparison
over-attributes SECANT's changes to RL-ViGen. **That advice is wrong, and cloning the fork shows
why**: SECANT's fork is robosuite **1.0.0**; RL-ViGen vendors **1.4.0**. Four minor versions apart.
A diff between them is dominated by the version gap (154 files differing, 236 present only in
RL-ViGen), and isolates nothing.

RL-ViGen did **not** fork SECANT's robosuite. It vendors robosuite 1.4.0 and modifies that. So the
*original* comparison — ours against PyPI robosuite **1.4.0**, same version — is the one that
isolates RL-ViGen's changes, and the "761 files" figure stands as the right kind of measurement.

SECANT is also **silent** on what its own fork changed: neither its paper nor its supplementary
mentions forking robosuite at all. So that provenance is undocumented at the source, not merely
undocumented by RL-ViGen.

### 6.4 The peer-review record, per method — only what changes a decision

**DrQ — checked and CLEARED, but it was worth checking.** DrQ's authors told a reviewer, verbatim:
*"RAD is a strict subset of our method and can be instantiated by using DrQ[K=1,M=1]."* If
RL-ViGen's DrQ ran at K=M=1 it would **be RAD**, and two of our twelve rows would be the same
algorithm under different names. Read directly: `algos/drq.py:277` is
`target_Q = (target_Q + target_Q_aug) / 2` (K=2) and lines 281–286 sum the critic loss over both
the clean and augmented views (M=2). **Genuine DrQ[K=2,M=2]. The rows are distinct.**

**SVEA — the strongest external corroboration of our own doubts.** Reviewer UP5u (score 4, reject)
argued the reported gains are confounded: *"SVEA uses encoder arch that consists of 11 conv layers,
while DrQ only uses 4… replay buffer of SVEA is 500K, while DrQ's 100K… SVEA virtually increases
the batch size by factor of 2… These discrepancies alone could result in a drastic difference in
performance and can render the empirical study to be invalid."* The meta-review confirms this was
never fully closed. Combined with RL-ViGen's own fidelity table reporting **SVEA −11** against
published, this row deserves the most caution of the five we inherit.
*Good news for one of our knobs*: authors state they *"do not find our algorithm to be very
sensitive to alpha/beta… recommend constant 0.5/0.5"*, which is what RL-ViGen uses.
*Still open*: **no reviewer ever discussed the choice of strong augmentation**, so RL-ViGen's
substitution of overlay for random convolution is untested in either direction.

**DrQ-v2 — its own cross-domain transfer is an unresolved doubt.** Reviewer ncsH: *"It isn't clear
how the proposed sample efficiency and speed improvements could generalize beyond the DM control
suite without further adjustments"*, and after the rebuttal: *"the authors raised good points but
they don't justify any change to my initial assessment."* Never resolved with evidence. **`base` is
DrQ-v2's hyperparameter set and DrQ-v2's own reviewers doubted it transfers off DMControl.**
Two specifics that land on us:
- The exploration-stddev schedule **scales with difficulty tier** (easy 100k, medium 500k, hard
  2M). We use the *medium* string at a 500k budget — confirming `PREMISES.md` P7 from the review
  record, not just from the config files.
- DrQ-v2's only manipulation-tagged task is **Reach Duplo**, and it is **sparse**-reward. Our task
  is dense-shaped. There is no dense-reward manipulation precedent in its tuning at all.

**ALDA — a live comparability problem, conceded by its authors.** *"Our method trains solely on the
unmodified DMC environment and is periodically evaluated on DMCGB environments, testing
**extrapolative** generalization. In contrast, methods like SVEA apply random transformations…
making their generalization results more representative of **interpolative** generalization."*
**So ALDA's published wins over SVEA/RAD-family methods are not measuring the same quantity**, and
putting them side by side in one table without saying so repeats the error. Our protocol trains all
arms identically, which *removes* the asymmetry — but the point must be made explicitly, because a
reader who knows ALDA's paper will assume it is still present.
Also: **no reviewer or author ever names ALDA's backbone** (no mention of SAC, DrQ, DrQ-v2 or DDPG
anywhere in the thread), so RL-ViGen's DrQ-v2/DDPG port has no author-endorsed precedent. And on
manipulation, the authors say it is future work in a *behaviour-cloning* setting, not RL.

**RAD.** The meta-review asked for *"10+"* seeds because *"the difference between methods may not be
statistically significant"* at 3–4 — relevant to our own seed decision. Reviewer R2 argued the
result *"is more because it helps convolutional neural nets than anything to do with RL"*. Nobody
raised the CURL-crop-versus-contrastive confound in RAD's thread.

**SGQN — NO review material exists.** Its OpenReview page is a landing page with "0 Replies";
NeurIPS did not publish threads. **The `aux_lr` question cannot be settled from the literature at
all** — it is code-and-tables only, which is exactly how we settled it. Worth recording so nobody
goes looking again.

### 6.5 The on-policy family: a second arm whose condition fails, and a reviewer who described our exact task

**IBAC-SNI — SNI's benefit is conditional, and the condition does not hold here.** Authors, in
rebuttal: *"SNI becomes necessary on more complex environments like Coinrun (right) where SNI is
critical for SOTA performance (note e.g. that **multiroom has no 'catastrophic' actions that end
the episode**)."* Robosuite `Door`/`Lift` run to a fixed 500-step horizon with **no early
termination at all** — structurally the Multiroom case, not the CoinRun case. **So SNI, like
IDAAC's instance-invariance, has no reason to help in our setting by its own authors' criterion.**
That is now two of the four on-policy arms.

Two more from the same thread:
- **β does not transfer.** Best value is 1e-6 for Multiroom, 1e-4 for CoinRun, 1e-3 for the toy
  task — two orders of magnitude across domains. We use 1e-4, the CoinRun value, which is a
  *choice* and not an inheritance.
- **IBAC alone does not prevent overfitting**: *"IBAC does not prevent overfitting by itself… but
  does lead to faster learning."* The paper's headline numbers combine IBAC with weight decay and
  data augmentation. A single-regulariser row is not what the paper reports.
- Reviewer 1 observed IBAC may *overtake* IBAC-SNI given longer training, and the authors did not
  refute it — so the SNI gain may be a training-speed effect rather than an asymptotic one.

**CTRL — a reviewer described our task and named the failure mode.** Reviewer 7TDG: *"Consider a
scenario where a robot arm needs to pick up a particular object on a table. Each time the robot
performs its task, the surface of the table will randomly change its color… maximizing
L_clust + L_pred might learn an encoder that **only encodes the color information**."* The authors
concede the boundary case: distinguishing behaviourally-different-but-visually-similar trajectories
is *"Not impossible, but they require learning a far more complicated transformation."*
**That is our benchmark, described by a reviewer three years early** — RL-ViGen's whole premise is
randomising exactly those surface appearances on a manipulation task.
Also: the authors' own cluster-count heuristic is **biased toward under-clustering** by their own
admission, and `T=2` means they are *"only clustering transitions"*, not trajectories — confirmed by
both reviewer and authors.

**A budget finding that applies to the whole on-policy family.** CTRL's authors, explaining why
their DAAC reproduction contradicts IDAAC's paper: *"The relative ordering of PPO vs DAAC comes
from the fact that our results are on 8M, which produces a different ordering of baselines from
25M."* **DAAC/IDAAC's advantage over plain PPO is not robust to a reduced training budget** — and we
run 500k frames, far below both 8M and 25M. A weak or inverted IDAAC row at our budget would be
consistent with the literature rather than evidence of a bug.

### 6.6 GSF — collected, identified, and NOT a baseline

`ext/papers-sorted/GSF/` is *"Improving Zero-Shot Generalization in Offline Reinforcement Learning
using Generalized Similarity Functions"* (Mazoure, Kostrikov, Nachum, Tompson), **ICLR 2022 —
rejected**. Not an acronym collision; the folder is correctly named.

**It is not a candidate baseline**, for three structural reasons, code-verified rather than
inferred: it is **offline** RL (CQL plus contrastive representations, trained on a fixed 5M-
transition dataset, no online interaction), its actions are **discrete 16-way categorical**
(`gsf.py` hardcodes `discrete_actions=True`), and it evaluates only on the authors' own custom
"offline Procgen" benchmark. Its `MixtureGuassianPolicy` is dead code inherited from a shared
internal codebase and never exercised.

Most likely collected by association — same lead author as the real CTRL paper, same
"zero-shot generalization" phrasing. Recording the verdict so nobody re-opens it.

---

## 7. What "evaluation" means per baseline, measured 2026-09-02/03  ·  [DURABLE]

Answering this file's own question — *would this baseline's number be fair to call that method's
result?* — needed facts nobody had enumerated. `scripts/audit_eval_state.py` and
`audit_eval_cadence.py` hold them with a file:line for each and a `--check` that fails when one
moves. What changes a fidelity judgement:

| baseline | policy read at evaluation | training-time evaluation | its own evaluator, on this target |
|---|---|---|---|
| `drqv2` `svea` `drq` `sgqn` `curl` | **mode** (`dist.mean`) | periodic, eval-easy ×10 scenes + train-regime scene 0 | usable |
| `rad` `soda` | **mode** (`mu`) | periodic, **two** regimes (`env` and `test_env`) | usable |
| `alda` | **mode** (`mu`) | periodic, **three** regimes — and the only baseline that builds `eval-hard` | usable, and the richest |
| `idaac` | **SAMPLE** (`dist.sample()`) | periodic, one regime, cadence in *updates* | usable |
| `ppg` | not chosen anywhere | **none** | no eval code at all — a loop is missing, not a policy |
| `ibac_sni` | see `scripts/evaluate.py` | **none** in training, by upstream's design | usable, separate by design |
| `ctrl` | discrete-only as shipped | **continuous**, two test envs stepped inside the loop | **must be repointed** |

**Three of these bear directly on fidelity.**

**`idaac` samples where nine others take the mode.** `model.py:332` is
`def act(self, inputs, deterministic=False)` and `test.py:53` calls `act(obs)` without the flag.
That is IDAAC's own choice and faithful to it — but a return produced by sampling and one produced
by a mode are different estimators, and pooling them into one column would be a comparability
error of ours, not of theirs. The axis now rides on every record as
`conventions.eval_policy_mode`.

**`ctrl`'s shipped evaluator cannot read our checkpoints, and that is not upstream's fault.**
`evaluate_ppo.py:67-74` selects actions with `logits.argmax(1)` or `jax.random.categorical` — a
categorical over discrete actions, correct for Procgen. Door's action space is measured
`(7,)` float32 in `[-1, 1]`, and the continuous head **this project authored** emits a mean and a
log-std. The evaluator is discrete because the algorithm was; the mismatch is ours. It is also
cheap to resolve: `algo.py:40-61` already has a `select_action` returning a distribution and
taking `pi.mode()` or `pi.sample()`, correct for either space, and it is what training uses.

**`ppg`'s number would have been an untrained policy's.** `LogSaveHelper` saves in its own
`__init__`, before any gradient step, whenever `ic_per_save > 0` — and that defaults to 100,000.
Any run shorter than that retains only the construction save. Caught by arithmetic rather than by
a gate: entropy of a diagonal Gaussian depends only on σ, the run logged `Opt/entropy` 9.936886,
and `log_std = 0` gives exactly 9.932570. A terminal save now runs after `learn()`.

**And one that is not per-baseline.** Two `drqv2` cells log ~480 on the training distribution and
evaluate at 6.8 and 18.4 from their own snapshots, while a 6,000-frame cell reproduces exactly.
Until that is settled no number from this project is fair to call any method's result — see the
register entry of 2026-09-02 and `PRODUCTION-READINESS.md`'s banner.
