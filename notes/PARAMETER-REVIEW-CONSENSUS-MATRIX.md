# Per-parameter consensus across all external reviews

**What this is.** One reconciliation of every significant parameter of all twelve baselines against
every external review the project has received — 27 files (`notes/ai-review-*.md`,
`notes/ai-recommendation-*.md`, `notes/ai-help-*.md`, plus `notes/gemini-ai-review-2-take-critically.md`).
Produced 2026-09-08 by a subagent instructed to read all of them and reconcile, rather than to
report a value per parameter.

**Why it is framed as DISPOSITIONS and not as values.** Asking "what number should this be" was
rejected as the wrong question: several reviews' actual position is *keep the value and declare it
unfaithful*, which no number can express. Every row below therefore resolves to one of:

  - **KEEP THE VALUE** — and what must be disclosed alongside it
  - **CHANGE THE VALUE** — and to what, on whose authority
  - **DEMOTE THE CLAIM** — the value is fine, the provenance sentence attached to it is too strong
  - **MEASURE FIRST** — no review can settle it from sources; it needs an arm
  - **NOT ADDRESSED** — nobody has ever examined it

**How to read the review numbering.** Reviews 2–15 are sequential re-audits of the same tree, each
seeing a more-fixed codebase; a criticism in review 5 may be answered by a fix visible to review 12.
Reviews 17–21 are source-fidelity audits reading primary papers. Reviews 23–26 are targeted
verifications. **Later reviews supersede earlier ones on the same point**, and several explicitly
retract their own earlier positions — those retractions are the most valuable content here.

**Status of the claims below.** This is a reading of the reviews, not an independent verification of
each claim. Where this project has since verified or corrected an item, a `> VERIFIED` or
`> CORRECTED` note is inserted inline beneath it. Per the workspace rule: verify before repeating,
including your own earlier claims.

---

## CONTRADICTIONS AND OPEN DISPUTES, most important first

### 1. `ibac_sni`/`ctrl` frame_stack: a decision exists that the code does not yet implement

**Current code value**: `rlgen/protocol.py` `OBSERVATION_GEOMETRY["ibac_sni"] = (64, 1)`,
`OBSERVATION_GEOMETRY["ctrl"] = (64, 1)` — still single-frame.

**Decided value** (`notes/DECISION-SHEET.md` A40-REVISED-2, 2026-09-08): `frame_stack=3` for all
twelve. The chain A40 → A40-REVISED → A40-REVISED-2:

- A40 (owner-raised): keeps 1 for both, demotes 4 of 6 on-policy cross-comparisons to descriptive.
- A40-REVISED (after `ai-help-26-external.md`): reverses for `ibac_sni` only, citing the authors'
  own `config.py:140` comment — *"No frame stack is necessary if PAINT_VEL_INFO = 1"* — with CoinRun
  defaulting `PAINT_VEL_INFO=1`. Keeps `ctrl` at 1 because `runnable/ctrl/train_ppo.py:160` passes
  `paint_vel_info=False`, so 1 frame is judged CTRL's real trained condition.
- A40-REVISED-2: reverses again for `ctrl` — the `paint_vel_info` framing was the wrong
  justification entirely. CTRL's clustering objective operates on temporal windows over rollout
  timesteps (`algo.py:90`, `algo.py:539`), not on stacked channels, so there is no methodological
  stake in frame count; single-frame is Procgen's environment convention, not CTRL's method — the
  same reasoning that moved `idaac`/`ppg` to 3.

Independently verified by the reviewing agent: `runnable/ctrl/vec_env.py:23` defaults
`paint_vel_info=True`, but `runnable/ctrl/train_ppo.py:160` overrides it to `False` for the actual
trainer — confirming that `ai-help-26`'s "velocity painted" justification for CTRL is factually
wrong even though its bottom line (3 frames) is judged correct for a different reason.

**Disposition: CHANGED to 3 for `ibac_sni` and `ctrl`. IMPLEMENTED 2026-09-08** — see
DECISION-SHEET "A40 REVISED-2 and A43 — IMPLEMENTED". Both stacks had to be authored; neither
baseline had any stacking mechanism on the Door path at all.

> CORRECTED 2026-09-08: A40-REVISED-2's cost estimate was wrong twice. It is not "one literal in
> `model.py`". Neither `ctrl` nor `ibac_sni` has ANY frame-stacking mechanism on the Door path:
> `runnable/ctrl/vec_env.py` `RLViGenVecEnvCustom` takes `c,h,w` straight from the env's `rgb` space
> with no stacking wrapper anywhere in `_SyncVecEnv`→`VecMonitor`→`VecNormalize`; and
> `runnable/ibac_sni/torch_rl/ibac_sni_runtime.py:50-56` is a plain observation wrapper with no
> stacking. CoinRun's `VecFrameStack` (`main_utils.py:19-20`) is NOT on this path. **Both need
> authored stacking**, not a channel-count edit. Eval inherits it for free: `eval_grid.py:734` and
> `:1003-1022` construct through those same two constructors.

Reviews: `ai-help-16.md` (3 for `idaac`/`ppg`, source-backed via `raileanu21a-supp.pdf` §E);
`ai-help-26-external.md` (3 for all twelve); reviews 2 §5 and nearly every review 2–21 name the
1-vs-3 split as a comparability confound without resolving it.

### 2. `idaac` `order_loss_coef`: a 100x fidelity gap — fixed in code, not yet validated by a run

**Pre-fix ("IDAAC-P")**: `order_loss_coef=0.001` (Procgen argparse default).
**Current** (`families.json` `idaac.constants`): `order_loss_coef: "0.1"` — already changed.

Review 15 §4, source-checked against `ext/idaac/raileanu21a-supp.pdf` §E:

> *"current Door IDAAC's `order_loss_coef=0.001` against the authors' own published
> continuous-control `alpha_i=0.1` — a 100x difference in the weight of IDAAC's defining invariance
> objective."*

Reviews 11–15 and review 17 independently corroborate the same recipe (1 process, 2048 steps, 32
minibatches, 10 PPO epochs, gamma=.99, entropy=0, lr=3e-4, value_freq=32, adv_loss_coef=0.1,
order_loss_coef=0.1, 3 frames, linear LR decay over the literal 1M env steps).

> VERIFIED 2026-09-08 against the primary source, not the reviews. `ext/idaac/raileanu21a-supp.pdf`
> §E states verbatim: *"for DAAC and IDAAC, we ran the same hyperparameter search as for Procgen
> and found that **E_V = 9, N_π = 32, α_a = 0.1, and α_i = 0.1** worked best across all
> environments"*, and separately *"10 ppo epochs, 0.0 entropy coefficient, 0.0003 learning rate,
> and 32 minibatches… γ = 0.99, λ = 0.95… 2048 steps, 1 process, value loss coefficient 0.5, and
> linear rate decay over 1 million environment steps"*, and *"3 stacked frames as observations"*.
>
> `α_i = 0.1` is `order_loss_coef`, so the 100x correction is right. The sentence names FOUR
> values and `families.json` sets three, which looked like a gap: **E_V is not missing**.
> `--value_epoch` already defaults to `9` in `runnable/idaac/ppo_daac_idaac/arguments.py:134`, as
> do `--gae_lambda` (0.95) and `--value_loss_coef` (0.5). Every value the supplement states is
> either set explicitly or already the code's default, so the C2 recipe is COMPLETE — checked
> rather than assumed, because this is the project's highest-stakes paper-derived claim and
> A41 EXTENDED had just shown three reviews misquoting a different paper.
>
> (Upstream curiosity, harmless: the `--value_epoch` and `--value_freq` help strings are swapped.)

**Disposition: CHANGED, per source — but MEASURE FIRST on the outcome.** `families.json`'s own note:
*"NOT YET VALIDATED by a full-length training run"*. A pilot at both P and C1 reached 0.0 success at
245,760 frames (`notes/CLAIMS-LEDGER.md`), not treated as settling it, per the Q47 anti-reactive
rule.

### 3. `idaac` reward normalization during training — NEW, raised by no review

`runnable/idaac/ppo_daac_idaac/envs.py:198`: `venv = VecNormalize(venv=venv, ob=False)`. The
vendored `VecNormalize.__init__` (`ext/baselines/baselines/common/vec_env/vec_normalize.py:10`)
defaults `ob=True, ret=True, clipob=10., cliprew=10., gamma=0.99`. Passing only `ob=False` leaves
**`ret=True`** — IDAAC trains on a running-std-normalized, ±10-clipped reward, not raw Door reward,
with a return-normalization discount separate from the PPO `--gamma` and surfaced nowhere.

Same shape as the frame-stack defect: Procgen rewards are large, unbounded and level-dependent, so
normalizing is standard there; Door's shaped, bounded, dense reward has no comparable justification,
and nobody asked whether the transplant holds. Review 2 §29 raises the *general* point (*"Several
on-policy Procgen-derived families normalize rewards"*) without naming this mechanism or value.
Review 6/Gemini's "Reward Normalization Fixed" is a different, already-fixed CTRL **evaluator** bug
(item 11).

> VERIFIED 2026-09-08 (both halves):
> - The training claim is real. `envs.py:198` passes only `ob=False`; `ret=True` stands.
> - **The units half is already closed and the finding must not be read as a measurement defect.**
>   `eval_grid.py:534-541` documents exactly this: the stack is `DummyVecEnv -> VecMonitor ->
>   VecNormalize`, the monitor sits INSIDE the normalizer, and the evaluator reads
>   `info['episode']['r']` — the raw episode return — not `step()`'s reward. That was found by
>   measurement (22.4 against the run's own logged 1.55, a 14x error) and fixed. Reported idaac
>   numbers are in raw Door units.
>
> So this is a **training-dynamics** disclosure item, not a units one, and that was then checked on
> every surface a number reaches rather than inferred from the one that was already known:
>
> | surface | idaac | ppg | ctrl |
> |---|---|---|---|
> | endpoint eval | `info['episode']['r']`, monitor inside normaliser | — | explicit `normalize_rewards=False` |
> | training curve | `test.py` appends `info['episode']['r']` | `EpRewMean` from roller stats gathered at `ppo.py:272`, **before** the normaliser touches `seg["reward"]` at `:274` | `Eprew200` averages `info['r']` from `info.get('episode')` |
>
> All raw. The axis is now `rlgen/protocol.py::REWARD_NORMALIZATION`, 3/9, over a set **disjoint**
> from time-limit handling's 3/9 — so "the three that differ" is ambiguous without naming which,
> and `tests/test_axis_tables_cover_the_same_fleet.py` asserts both sets so a change to either
> cannot pass silently.

**Disposition: MEASURE FIRST / DISCLOSE — not a units defect.**

### 4. SGQN/SVEA `feature_dim=50` vs RL-ViGen's published `256`, and SGQN's `aux_lr`

**Current**: `RL-ViGen-upstream/cfgs/sgqn_config.yaml:33` and `svea_config.yaml` hard-code
`feature_dim: 50`; `sgqn_config.yaml:54` sets `aux_lr: 1e-4`; `sgqn.py:172` hard-codes the
critic-consistency weight as a bare `0.9` multiplier, not exposed as a parameter; `sgqn_quantile: 0.93`.

RL-ViGen's own supplementary Table 2, quoted in DECISION-SHEET A41 (2026-09-08):

> *"Feature dim — DrQ(v2), CURL: 50, otherwise: 256… every shipped config hard-codes
> `feature_dim: 50`… So `svea` and `sgqn` run a 5x narrower encoder-to-head bottleneck than the
> benchmark's own table specifies."*

Reviews 19 and 20 raised this independently; reviews 17/18/20 separately flag SGQN's quantile
(paper 0.90 vs shipped 0.93) and consistency weight (paper 0.70 vs shipped 0.90). Review 17
recommends **changing** to the paper's values; review 20 recommends **declaring** either as a named
variant without picking a "correct" one.

**A41's resolution — KEEP THE VALUE, disclose, under a stated general rule**: *"follow the SHIPPED
CODE, and declare every disagreement with the paper. The single exception is a value the paper
states FOR THIS TASK where the code's value is a generic default written for another one."* Under
that rule `action_repeat=1` is taken from the paper (task-specific to Robosuite; the shipped `2` is
a DMC leftover), while `feature_dim` and `aux_lr` stay at the shipped 50 / 1e-4 — upstream ships no
robosuite launch script, so the CLI overrides behind their published Robosuite table are not
recoverable.

Quantile and hardcoded consistency weight were **not enumerated in A41's table**, and resolved by
inference from its rule rather than by a recorded decision.

> CLOSED 2026-09-08 by reading the paper, and **the reviews' premises are both wrong**. See
> DECISION-SHEET "A41 EXTENDED". SGQN's Table 3 states ρ = **0.95** (Walker walk/stand, Finger
> spin) and **0.98** (Cartpole, Ball in cup) — not the 0.90 that reviews 17, 19 and 20 all report
> — and it is explicitly a per-task value the authors chose by inspecting each environment's
> foreground/background pixel ratio. The consistency weight λ appears only symbolically, in
> `L_Q(θ) + λ L_C(θ)`; the paper assigns it **no value anywhere**, so reviews 17, 18 and 20's
> "paper 0.70" has no source in it. The only `0.7` in the document is a performance number in
> Table 6.
>
> The resolution is unchanged — keep the shipped 0.93 and 0.9 — but is now source-backed rather
> than inferred, and the required DISCLOSURE changes: not "we deviate from the paper's 0.90/0.70",
> but "SGQN's quantile is a per-task parameter that nobody has tuned for Door".
>
> For anyone re-checking: `ext/papers-sorted/SGQN/SGQN_openreview.pdf` is an OpenReview landing
> page, not the paper. The paper is
> `ext/_duplicates/baseline_resources__04_sgqn__paper_arxiv_2209.09203.pdf`.

### 5. Time-limit handling (3 bootstrap / 9 terminal) — the project's own instance of the pattern

`rlgen/protocol.py:364-369`'s own comment:

> *"three… are exactly the SAC-family clones descended from Yarats' dmcontrol code, which carried
> the fix. The nine… do not… for which every episode in Procgen genuinely IS a termination — so
> their authors were right for Procgen and are wrong here, purely because the environment changed
> underneath them."*

**Current**: `rad`, `soda`, `alda` bootstrap; the other nine zero the bootstrap.

**DISPUTED then converged.** Review 2 §6 calls it *"the largest unresolved algorithmic-comparability
problem"*. Reviews 8/9/10 push back — *"If the 500-step horizon defines the benchmark's finite
episodic task, zeroing the value target at the endpoint is a perfectly coherent finite-horizon
objective… I would not state categorically that terminal handling is 'wrong'"* — and this softer
reading is what the project adopted (A5 revised): *"methods retain their native time-limit
semantics… Report the difference, drop the direction."*

**Disposition: KEEP THE VALUE, disclose, DEMOTE the directional claim.** No review dissents after 8.

### 6. CTRL hyperparameters (`cluster_len`, `temp`, `k`, `myow_k`, `lr_ctrl`, `epoch_ppo`)

**Current**, verified against `runnable/ctrl/train_ppo.py`'s `absl.flags` defaults (families.json
overrides only `cluster_len`, `n_minibatch_ctrl`, `num_envs`): `cluster_len=10`, `temp=0.1`, `k=1`,
`myow_k=1`, `lr_ctrl=1e-4`, `lr=5e-4`, `gamma=0.999`, `entropy_coeff=0.01`, `epoch_ppo=3`,
`embedding_type="concat"`, `n_att_heads=2` — all identical to released-code defaults.

Review 17 reads the paper's LaTeX appendix and recommends **changing** to `num_envs=32, epoch=1,
lr_ctrl=5e-4, cluster_len=2, k=3, temperature=0.3`. Review 18 calls it "the clearest paper/source
disagreement" but stops short. Review 19 **retracts its own earlier position**: *"My previous
response said, essentially, 'paper table wins; switch CTRL.' That was too categorical… I recommend
two named configurations: `CTRL-release`, `CTRL-paper`… Do not choose between the two by Door
performance."* Review 20: *"I do NOT recommend changing CTRL… Keep it. Just call the result
`CTRL-release-Door`."* Review 21 concurs on `cluster_len=10`.

**Disposition: DISPUTED — review 17 (change) vs 18→19→20→21 (keep, declare); later reviews win, and
the unchanged code matches them.** No dedicated DECISION-SHEET entry exists; it is resolved by the
general declare-don't-invent convention plus inaction. **Worth a formal entry.**

> RESOLVED 2026-09-08 by reading the paper — see DECISION-SHEET A45, which now gives it the formal
> entry this asked for. **Review 17's numbers were right, every one of them**: Table 2 states
> `num_envs=32, n_epochs=1, learning rate 5e-4 for RL AND representation, T=2, k=3, β=0.3`. That
> matters because review 19 later called its own "paper table wins" position *"too categorical"*
> and retracted it — the retraction was right for its stated reason (a paper↔code conflict is not
> settled by preferring the paper), not because the numbers were wrong.
>
> The values are unchanged, under A41: Table 2 is a Procgen table and A41's exception covers a
> value the paper states *for this task*. What changed is that every deviation is now enumerated
> from the primary source in the provenance string, including one nobody had named — the paper
> gives a SINGLE learning rate covering representation learning, so the released `lr_ctrl=1e-4`
> contradicts its own paper by 5x on CTRL's defining objective.

### 7. IBAC-SNI's VIB/SNI mechanism — identified, never implemented, structurally can't be

Verified: `runnable/ibac_sni/torch_rl/scripts/train.py` has **no `--nr-samples`, `--l2`, or `-uda`
flag at all** — not unset, absent from this branch's argparse. `--beta` defaults `1.0` (launcher
fixes `1e-4`). `--lr` defaults `7e-4`, never overridden. `--entropy-coef` fixed to `0.0`.

Review 19, tracing the CoinRun C++ source: *"It is not random shift, overlay, color jitter or
standard DrQ augmentation. It draws a random number of randomly sized, randomly located solid-color
rectangular blotches."* And on sampling: *"a high-fidelity continuous adaptation should not merely:
1. draw 12 latent samples, 2. average them, 3. run one Gaussian policy… The closest continuous
analogue is a uniform mixture of 12 Gaussian action policies."* Reviews 17, 18, 20 concur on the
missing pieces (256-d vs 64-d latent; 1 sample vs 12; no L2=1e-4).

**Disposition: was KEEP + DISCLOSE as an authored hybrid. HALF OF IT WAS WRONG.**

> CORRECTED 2026-09-08 (DECISION-SHEET A47). The latent dimension was **not** a missing flag — it
> was `model.py:212`, a literal — and the literal means opposite things on the two branches this
> port hybridises: in `torch_rl`'s MiniGrid setting the embedding is *itself* 64, so
> `Bottleneck(embedding, 64)` is a **1.0x identity width with no dimensional squeeze at all**;
> A37 then moved the port onto CoinRun's 2048-d IMPALA trunk and the width did not follow, making
> it a **32x** squeeze against CoinRun's own **8x**. Now `256` on the impala trunk, `64` kept on
> the MiniGrid path where it is correct.
>
> The **sampling half stands**: `--nr-samples` exists in neither branch's argparse here, and a
> faithful continuous adaptation is a uniform mixture of 12 Gaussian policies (review 19's reading
> of the CoinRun source) — real new code, not a constant.
>
> Worth separating, because the two had been filed together for weeks and one of them was a
> one-line change hiding behind the one that is not.

### 8. PPG `aux_lr=3e-4`: weakly sourced, still open

**Current**: `families.json` `ppg.constants.aux_lr = "3e-4"`, matching the policy `lr`.

Review 18: *"the continuous-control source states a learning rate of 3e-4, but OpenAI PPG has
distinct primary and auxiliary optimizer rates. I would confidently change the policy-side LR to
3e-4; I would not give the same level of confidence to `aux_lr=3e-4`."* Review 19 repeats it more
strongly; review 20: *"The scientifically clean options are: find the IDAAC authors' exact
continuous-control implementation/config; or retain OpenAI's `aux_lr=5e-4`… or keep `3e-4` but mark
it as an adaptation/interpretation. Do not pick based on the Door pilot result."*

**Disposition: was DISPUTED / OPEN. RESOLVED 2026-09-08 — CHANGED to 5e-4** (DECISION-SHEET A44).

> Reviews 19 and 20 were right and the resolution is stronger than either proposed. The supplement
> searched **"the learning rate", singular**, over `[1e-4, 3e-4, 7e-4, 1e-3]`, and its PPG-specific
> search covers only `N_pi/E_pi/E_V/E_aux/beta_clone` — no learning rate. OpenAI's release has
> **two separate flags**, `--lr` and `--aux_lr`, *both* defaulting to `5e-4`
> (`phasic_policy_gradient/train.py:36-37`). So running the authors' own recipe means passing
> `--lr 3e-4` and leaving the auxiliary optimizer alone: `5e-4` is not a fallback default, it is
> what their described procedure produces.
>
> It also violated A41, the project's own rule — the exception for a paper value was being applied
> to a value the paper does not contain. `lr` stays 3e-4, which the supplement does state.

### 9. Places365 split: reviews converge on train; the sheet flip-flopped; the code enforces train

A22's entries are contradictory in reading order (implemented-train, then reversed-to-train,
then "keep `use_val=True`"). Resolved by reading code, per the project's own rule:
`configure_places365_val.py`'s docstring states *"`train` is the decided production value"*;
`run_probe.sh:1267-1278` defaults probes to `val` but **refuses to launch at ≥600,000 frames unless
`places_split == train`** (`REFUSING: production scale with Places365 split 'val'.`) absent an
explicit `NATIVE_PLACES365_ACCEPT_VAL=1` deviation marker.

Reviews 2 §14, 9, 10, 14 flag the substitution; 17–21 all recommend train, review 20 rating it P0:
*"'all three affected baselines use the SAME split, so the cross-baseline comparison is unaffected'
— That conclusion does not follow."*

**Disposition: CHANGED to `train`; code enforces it at production scale.** Provisioning the real
~1.8M-image archive on the host is an asset action, not a decision.

### 10. CTRL evaluation policy mode: sampling → deterministic — found, verified, fixed

**Current** (`datasphere/native/evaluator_identity.py:169-172`): `FAMILY_EVAL_POLICY_MODE =
{"rlvigen": "mode", "dmc_gb": "mode", "alda": "mode", "ctrl": "mode", "idaac": "sample",
"ppg": "sample", "ibac_sni": "sample"}`.

Wrong until review 24 found it. Review 24, on `runnable/ctrl_public/evaluate_ppo.py`:

> *"Its released `evaluate_ppo.py` explicitly invokes `select_action(..., greedy=True)`, and the
> greedy branch is `logits.argmax(1)`. So using the stochastic training/reporting path as evidence
> for evaluation semantics was indeed the wrong provenance target."*

Review 23 independently confirms the same three upstream facts against the pinned repos.
**Disposition: CHANGED, source-verified, resolved.**

---

## Per-baseline, per-parameter matrix

### `drqv2` (RL-ViGen native, DDPG/DrQ-v2 backbone)

- **lr / decay**: `lr=1e-4`, constant. Not disputed.
- **Exploration-noise schedule** (distinct from LR — reviewers sometimes conflate them):
  `stddev_schedule: 'linear(1.0,0.1,100000)'`, inherited from `cfgs/task/easy.yaml` via `Door.yaml`'s
  `defaults: [easy, _self_]`. Decays to floor at 100k frames, flat for the remaining 500k. Gemini
  review states it correctly; **no review examines whether a 100k schedule inside a 600k budget is
  sensible — NOT ADDRESSED.**
- **gamma**: `0.99`. Not disputed.
- **Replay / warmup**: production (V100) `620,000`, non-evicting for ≤601,200 transitions;
  DataSphere base `300,000` (evicting). `num_seed_frames=4000`. Reviews 2, 4, 9, 11–15 flagged the
  300k base; **resolved** once the V100 profile's 620k was adopted — review 11: *"I would not block
  DrQ-v2/DrQ/CURL/SVEA/SGQN over this anymore."* Reviews 17/19/20 add that "behaviorally equivalent"
  must be scoped to the 600k horizon, not blanket. **KEEP, scope the equivalence claim.**
- **action_repeat**: `1` for Robosuite (paper-sourced override of the DMC-default `2`). This is the
  case A41 cites as correct paper-over-code.
- **Time-limit**: terminal (item 5).
- **Eval policy mode**: `mode`. Not disputed.
- **Observation scaling**: `obs/255.0 - 0.5` (`algos/drqv2.py:64`), range [-0.5, 0.5]. Not discussed
  specifically by any review.
- **UTD**: `update_every_steps=2` → 0.5 updates per transition (A27's corrected measurement).
- **Budget**: 600,000 frames exactly.
- **Seeds**: 3 fixed (101/102/103), predeclared. Reviews 2, 3, 9 wanted 5; A28's resolving-power
  analysis (corroborated by 9/11–15) settled on 3 with **bounded claims**. **DEMOTE THE CLAIM,
  KEEP n=3.**
- Used as canary/anchor (A10 revised; reviews 6/9/12/15/20/21 independently recommend it) — a rare
  point of total agreement.

### `svea` (RL-ViGen's SVEA on a DrQ-v2 backbone, NOT canonical SAC-based SVEA)

- **Identity**: reviews 17–20 agree this is not canonical SVEA. Gemini: *"`svea.py:12-298` imports
  and applies SODA's Places365 natural image overlay, not random convolution! Furthermore, it is
  built on a DrQ-v2 trunk rather than SAC… Must be cited as 'RL-ViGen's SVEA', never canonical
  SVEA."* `families.json`'s provenance string already says exactly this. **KEEP, already disclosed.**
- **feature_dim**: `50` vs the paper's `256` — item 4. **KEEP, disclose.**
- **lr / discount / nstep**: `1e-4` / `0.99` / `3`, same as `drqv2`. Not disputed.
- **Places365 split**: train — this is where the split matters mechanistically.

### `sgqn` (RL-ViGen, saliency-guided regularizer on DrQ-v2)

- **quantile / consistency weight / aux_lr / feature_dim**: `0.93` / hardcoded `0.9` (`sgqn.py:172`,
  not a parameter) / `1e-4` / `50`. Paper table: `0.90 / 0.70 / 8e-5 / 256`. **feature_dim and
  aux_lr resolved by A41: KEEP shipped, disclose. Quantile and consistency weight were NOT in
  A41's table** — closed 2026-09-08 by A41 EXTENDED, which found the paper says 0.95/0.98 per task
  (not 0.90) and gives the consistency weight no value at all. Same resolution, source-backed.
- **Fixed history**: Gemini notes an earlier `aux_lr = 0.3` (1000x canonical). Verified:
  `sgqn.py:120`'s signature default IS `aux_lr=0.3`; the shipped config overrides to `1e-4`.
  **SUPERSEDED.**
- **P19 Places365 worker count**: review 2 §15 calls the "changes how images are fetched, never
  which images or in what order" claim *"unproven, not… a known bug"*. **NOT ADDRESSED since;
  MEASURE FIRST if it matters** (seeded image-hash comparison).

### `curl` (RL-ViGen's single-encoder CURL, NOT canonical two-encoder CURL)

- **Identity**: unanimous 17–20 that this is a deliberate RL-ViGen departure (single encoder, not
  online/target). `families.json` provenance already says so. **KEEP, disclosed.**
- **feature_dim**: `50` — and here `50` IS the paper's stated value for CURL. **No deviation.**
- Rest as `drqv2`.

### `drq` (RL-ViGen's DrQ)

- **nstep**: `1`, matching canonical DrQ and RL-ViGen's own table. **KEEP.**
- **lr**: `1e-4` (RL-ViGen's robosuite default) vs canonical DrQ's `~1e-3`. **KEEP THE VALUE,
  relabel as `DrQ-RLViGen`** — reviews 17, 19, 20.
- **Fixed defect worth recording**: env-patch `P17-drq-actor-entropy-crash` — the actor crashed
  logging `dist.entropy()` on a `SquashedNormal`, so `drq` could not train at all. Named by no
  review; real, source-verified, fixed.

### `rad` (DMCGB's RAD, not the original RAD codebase)

- **Observation geometry**: renders 100x100, random-crops to 84 for training, center-crops for eval
  — source-faithful; forcing native 84 makes the crop a no-op by RAD's own `crop_max<=0` guard.
  **KEEP the mechanism**; reviews 17/19/20 want the identity disclosed as `RAD-DMCGB`, since DMCGB's
  standardized architecture differs from the original RAD lineage.
- **Time-limit**: bootstraps (`dmc_gb/src/train.py:149`). Source-faithful.
- **UTD**: ~1.0 update per new transition. A27's corrected reading; review 14 shows this is *closer*
  to source than the earlier "cut to 0.25 for action-repeat parity" proposal. **RESOLVED, KEEP.**
- **Replay**: uncapped (`capacity=args.train_steps`), deliberate. Not disputed.
- **Eval mode**: `mode`, DMCGB's own convention.

### `soda` (official DMCGB implementation)

- **aux_lr**: **the clearest single fixed defect found by review 19.** The generic parser defaults
  `1e-3` (`arguments.py:50`); the algorithm-specific official launch script
  (`runnable/dmc_gb/scripts/soda.sh:3`) overrides `--aux_lr 3e-4`. Review 19: *"I previously
  accepted the project's reasoning that 'the official code uses 1e-3, while the paper says 3e-4.'
  That reasoning is wrong."* **Current: `3e-4`. CHANGED, source-verified, resolved** — and review 19
  promotes "generic parser default vs algorithm-specific launch script" into a general precedence
  rule for the rest of the project.
- **Places365 split**: train. SODA's auxiliary objective is the most Places-sensitive of the three.
- **Time-limit**: bootstraps. **Replay**: uncapped.
- Longest training cell in the fleet (~45-51h at 600k).

### `alda` (official ALDA, adapted to Door)

- **UTD**: `utd: float = 1.0`. The most-revisited parameter in the sequence. Reviews 11–15, 17–21
  converge: **keep 1.0 as source-primary**; the divergence evidence was measured on Lift, on the
  retired `rlgen` port, so it is a stability prior, not a fidelity correction. Review 14 overturns
  the earlier "reduce to 0.25" proposal as mathematically wrong: *"An action-repeat transition is
  one replay item even when it represents several simulator substeps."* **A27 closes it with a
  measurement**: an ALDA-P (`utd=1.0`) pilot at 150k succeeded with no divergence, so the paired
  ALDA-C (`utd=0.25`) arm was cancelled as uninformative. **MEASURED, then KEPT** — with the caveat
  (15, 21) that a production seed diverging past 150k reopens it.
- **Replay**: `buffer_capacity: 1_000_000` (source default). Not disputed.
- **Frame stack**: 3, matches source (`num_latents=12, values_per_latent=12, beta=100, 64x64`).
- **Time-limit**: bootstraps (`alda_trainer.py:655`).
- **Fixed evaluator bug** (review 13): `_alda_trainer()` called `build()` twice, allocating ~11.44
  GiB of replay buffer at every evaluation. Fixed: `trainer.build(spec, replay_capacity=1,
  prefill=False)`. **SUPERSEDED.**
- **Budget**: single-voice concern (review 18) that ALDA's source horizon is 500k against the
  common 600k, recommending predeclaring both.

  > ADDRESSED 2026-09-08 (DECISION-SHEET A46), and review 18 was right — every shipped
  > `ext/ALDA_Official/specs/*.yaml` sets `n_train_steps: 500_000`; only the trainer dataclass says
  > 1M. It also **generalises**, which is why it was worth chasing a single voice: `rad`/`soda`
  > default to `'500k'` too and SGQN's own paper says 500,000, while the RL-ViGen natives' horizon
  > is 1.1M, `idaac`/`ppg`'s is 1M, CTRL's is 8M and IBAC-SNI's is 160M. The common 600k therefore
  > lands between **0.375% and 120%** of each method's own horizon — a 320x spread that reads as
  > uniformity in the phrase "600,000 frames, all twelve".
  >
  > Declared, not equalised (equalising means 160M frames for one baseline). The 500k stamp is
  > retained for the four that overshoot — the 50k cadence gives it free — as a source-horizon
  > reference, deliberately NOT a second headline column, since per-baseline horizons differ and
  > selecting per baseline is what gate 7 forbids.
  >
  > One concrete consequence fell out: `idaac` and `ppg` decay their learning rate linearly to zero
  > over the literal 1M steps and stop at 600k, so both end at **40% of their initial rate**,
  > having never annealed.

### `idaac` (authors' code; production config is the DMC continuous-control recipe "C2")

- **Full C2 recipe**, source-backed against `raileanu21a-supp.pdf` §E and matching
  `families.json.idaac.constants`: `num_processes=1`, `num_steps=2048`, `num_mini_batch=32`,
  `ppo_epoch=10`, `lr=3e-4`, `gamma=0.99`, `entropy_coef=0`, `value_freq=32`, `adv_loss_coef=0.1`,
  `order_loss_coef=0.1`, `frame_stack=3`, linear LR decay over the **literal** 1,000,000 env steps
  (not rescaled to the 600k budget). This replaced the Procgen-parser "P" config that reviews 2–12
  were auditing — **their criticisms of P are moot except as history**; reviews 14, 15, 17-processed,
  18–21 all endorse C2.
- **value_freq**: `1` (P) → `32` (C2), source-backed.
- **Episode identity (`level_seed`)**: a real defect traced by reviews 11 and 12, which *executed*
  the storage code with a synthetic transition to demonstrate corruption concretely (review 11:
  *"idx 3 obs 100 level 10 nstep 2"* — a new-episode observation carrying the old episode's level).
  Confirmed **fixed** by 14, 15, 17-processed, 19, 20, 21. **SUPERSEDED.**
- **Reward normalization**: item 3. **NEW.**
- **Eval mode**: `sample`, verified against upstream `test.py`'s bare `actor_critic.act(obs)` by
  reviews 23 and 24. **KEEP.**
- **`level_seed` semantics**: review 18 argued an episode ID is not Procgen's persistent level ID
  and may make the invariance objective incoherent; **review 19 retracts it**: *"After re-reading
  the paper, that objection was mostly wrong… an episode-scoped unique ID is actually a principled
  translation."*
- **num_processes**: `1` under C2 — no longer a capacity knob; the `v100 num_processes: 16` host
  override was removed.

### `ppg` (OpenAI PPG, borrowing selected values from the IDAAC authors' DMC comparator)

- **Rollout geometry**: `num_envs=1`, `nstep=2048` — **CHANGED from 8x256, resolved by measurement
  (A36 RESOLVED)**. Reviews 17–20 point out 8x256 and 1x2048 preserve sample count (2048) and
  auxiliary cadence (65,536 with `N_pi=32`) but are **not the same geometry** — review 20: *"With
  8x256, GAE/rollout cuts occur every 256 environment steps in eight simultaneous trajectories.
  With 1x2048, the collection process is one long stream… That changes bootstrap boundaries at
  rollout truncation, temporal correlation, the distribution of per-update episode phases."* The
  project then measured: 8x256 gives 78.54 IPS against 1x2048's 59.44, worth ~+8.3 GPU-h against a
  ~893 GPU-h campaign, under 1%. **Adopted 1x2048.**
  > **[Claude 2026-09-10] A36 also made `nminibatch` inexpressible, and four reviews missed it.**
  > Reviews 17-20 compared the two geometries on sample count, auxiliary cadence, GAE boundaries and
  > temporal correlation. None asked whether `nminibatch` still *runs*. `minibatch_optimize` splits
  > the LEADING axis (`Roller.singles_to_multi`: "(batch, time)"), so `ntrain = num_envs`. At
  > **8x256** the declared `nminibatch=8` fits exactly. At **1x2048** the declared 32 is clamped to
  > **1**, silently, with a warning that printed 293 times on `card0-20260909-115331` while the cell
  > recorded `--nminibatch 32`. The axis that mattered was expressibility, and no review had a row
  > for it. Resolved: `nminibatch: 1` declared, the clamp made fatal, and the arithmetic showing 1
  > is the *correct* value (it matches PPG's released density and per-step batch size exactly) is in
  > [`ppg-clip-is-inert-and-that-is-forced.md`](ppg-clip-is-inert-and-that-is-forced.md).
- **Identity / LR decay**: a source-traced reversal within one day (A36's three "IDENTITY FROZEN"
  sub-entries): frozen as "no decay, because OpenAI PPG has none", then corrected on
  `raileanu21a-supp.pdf` §E's literal sentence — *"We use gamma = 0.99… and linear rate decay over
  1 million environment steps. Following this grid search, we used the best values found for all the
  methods… For PPG… Npi = 32, Epi = 1, EV = 1, Eaux = 6, betaclone = 1"* — noting PPG's own listed
  search covers only those five, **all already equal to PPG's released defaults**, so nothing in it
  overrides the shared grid's decay. **Current: linear decay over the literal 1M env steps
  (`--lr_decay_env_steps`).** Review 21 declined to prescribe decay and instead prescribed freezing
  the identity; the project's later self-correction supersedes that caution.
- **frame_stack**: 3; `--frame_stack 1` retained as an explicit legacy ablation ("C1").
- **n_pi=32**: untouched in every revision; every review agrees the *geometry* is the free variable,
  not `n_pi`. **CONSENSUS.**
- **aux_lr**: DISPUTED/OPEN — item 8.
- **entcoef=0**: source-backed, and independently corroborated by the project's own `ibac_sni`
  finding (C61) that a categorical-Atari-tuned entropy coefficient inflates entropy on a continuous
  Gaussian.
- **Auxiliary KL reduction**: real fixed defect. `kl.mean()` over a 7-D Gaussian KL diluted the
  clone constraint ~7x. Review 2 §7: *"Literal source-line preservation is therefore less faithful
  to the original mechanism."* Fixed to `kl.sum(-1).mean()`. **SUPERSEDED** — a good example of
  overriding "preserve the literal line" with "preserve the mathematical role".
- **Eval mode**: `sample`, with an epistemic downgrade from reviews 23/24: OpenAI's release has **no
  dedicated evaluation runner**, so sampling-at-eval cannot be proven as upstream's evaluation
  convention (unlike IDAAC/CTRL). **DEMOTE THE CLAIM** — the current comment already does.
- **Reward normalization**: `RewardNormalizer` in `ppo.py:202` is OpenAI's own design. Not flagged
  by any review, unlike IDAAC's (item 3), which is Procgen boilerplate rather than PPG's mechanism.

### `ibac_sni` (authored hybrid of the authors' `torch_rl` and CoinRun implementations)

- **beta**: **the most consequential fixed defect in the project.** The launcher passed no `--beta`,
  silently taking `torch_rl`'s `1.0` while the documentation believed `1e-4`. Gemini names it first
  (*"a bottleneck penalty of 1.0 completely collapsed the latent representation"*); review 9
  quantifies: *"10,000x the CoinRun value; 1,000,000x the GridWorld value"*. **Current `1e-4`.
  SUPERSEDED.**
- **entropy_coef**: `0.0`, fixed from a categorical-Atari-tuned `0.01`. Measured evidence: at `0.01`,
  `mean_log_std: 0.0026 → 1.4472`, entropy `9.95 → 20.03`, zero successes. Reviews 9 and 10 add the
  mechanism independently: `log_std` is a **global, state-independent** parameter, so
  `H[q(a|z)] = sum log sigma_i + C` **does not depend on `z`** — zeroing it removes less of IBAC's
  representation mechanism than the name suggests. **CONSENSUS, KEEP at 0, disclose as a
  continuous-action adaptation.**
- **VIB latent dim / samples / L2 / UDA**: item 7. Flags absent from the branch, so no launcher can
  close it. **KEEP + DISCLOSE, unresolved engineering gap.**
- **procs**: `1` (base) → `16` (V100). A real arc where reviews disagreed and each was right about
  the state it saw:
  - Reviews 6–14: `procs=16` **unrunnable**. `fork` inherits live MuJoCo/EGL contexts, dying with
    `EOFError` even at `procs=2` (job `bt1q6jd096m3re2n7jp2`); and forked workers would inherit the
    parent's seeded NumPy state, collapsing placement diversity. Traced independently by 9–14.
  - Review 15 (and its "-processed" twin): **fixed** — *"workers can receive environment factories,
    child workers use `spawn`, environments are constructed in the child instead of inheriting live
    MuJoCo/EGL contexts, and each worker gets an independent seed… a real `procs=16`, 4,096-frame
    functional run completed successfully."*
  - **Disposition: CHANGED (engineering), MEASURE FIRST (science).** Runnability resolved;
    competence at the final configuration is not. Review 15: *"I would require meaningful learning…
    before paying for three 600k seeds."* **Pilot result not yet recorded.**
- **lr**: `7e-4`, `torch_rl`'s own default, never overridden. **NOT ADDRESSED by any review** — every
  review examines `beta` and `entropy_coef`; none asks whether a rate tuned for `torch_rl`'s
  MiniGrid/GridWorld PPO suits the continuous Door port on an IMPALA trunk. A plausible further
  instance of the transplant pattern.
- **Architecture**: CoinRun's IMPALA trunk (`--model_type impala`), replacing a MiniGrid-style
  hybrid. Reviews 8, 9 confirm this as a real source-justified improvement.
- **Eval mode**: `sample`, per the `torch_rl` evaluator's `--argmax` default (`false` →
  `dist.sample()`), with review 23's caveat that this is verified *for the `torch_rl` lineage this
  hybrid draws from*, not universally.

### `ctrl` (authors' released JAX code, restored to run its commented-out clustering path)

- **Parallelism**: `16` (DataSphere) → `64` (V100, the released default). Source-constrained:
  `algo.py:517-520`'s `size_batch = num_envs * (n_steps - cluster_len + 1) // 2` must divide by
  `n_minibatch_ctrl`; `families.json` records the empirical failure at `num_envs=4`
  (`bt1qgrrl5dcpn07jcq40`: *"cannot reshape array of shape (494,) into shape (-1, 61)"*) forcing 16
  as the smallest workable value.
- **cluster_len, temp, k, myow_k, lr_ctrl, epoch_ppo**: released defaults — item 6.
- **gamma**: `0.999` (released default). Not disputed specifically; one component of the
  cross-family gamma confound review 2 §30 names generically.
- **Native reward normalization**: `normalize_rewards=False` in the evaluator, fixed from a bug where
  it defaulted `True` and reported *"clipped normalized returns"* in place of raw Door reward.
  **SUPERSEDED** — units, not learning dynamics, were wrong.
- **Double-reset evaluator bug**: fixed. `_SyncVecEnv` auto-resets on `done`; the evaluator also
  called `env.reset()` before every measured episode, consuming twice the placement conditions and
  desynchronizing recorded indices `0,1,2,…` from the physical `0,2,4,…`. Traced by 9, 10, 11;
  confirmed fixed by 12–15 with regression tests on the index sequence.
- **Online-eval RNG isolation**: twice-revised. Reviews 5, 6, 9, 10 call the JAX-key advancement a
  **bug** (*"Restoring NumPy does not restore JAX's functional RNG state"*). Review 11
  **reclassifies** it: *"the gate explicitly recognizes this exact fact… and treats the JAX-key
  advancement as behavior inherited from upstream CTRL, while isolating only the Door-placement
  NumPy stream. I therefore do not classify that as a current defect… the choice is conscious rather
  than hidden."* Review 21 concurs. **KEEP, disclose precisely.**
- **Raw-vs-executed action in the clustering objective**: unresolved and correctly scoped. PPO
  legitimately uses the raw pre-clip sample (needed for the ratio); the separate clustering loss
  (`algo.py:173,552-553`) also conditions on it rather than on the executed (clipped) action.
  Review 2 §30: *"For PPO, using the raw action is arguably CORRECT… For the clustering objective,
  the case is weaker: it is modeling (s_t, a, r_t, s_{t+1}) as a transition, and the transition that
  actually occurred used the EXECUTED action."* Reviews 11–15, 17, 19, 20 re-raise it; all prescribe
  **MEASURE FIRST**. `action_diagnostics()` (clip rate, raw-vs-executed L1) was found built but not
  wired to a record path by review 2, then wired in 2026-09-06. **No review reports running the
  comparison. Open.**
- **Eval mode**: `mode` — item 10.
- **Checkpoint self-description**: fixed. The evaluator used to rebuild a Flax `TrainState` from a
  hardcoded `CTRL_DEFAULTS` dict duplicating production hyperparameters; review 2 §11: *"Flax
  `from_bytes` needs the target structure… the checkpoint is therefore not self-describing"*. Now
  reconstructs from the checkpoint-bound family descriptor. **SUPERSEDED.**

---

## Parameters no review has ever addressed

These are the highest-value rows here: not disputes, but places nobody has looked.

1. ~~**`ibac_sni`'s `lr=7e-4`** — `torch_rl`'s GridWorld-tuned default, never re-examined.~~
   **CLOSED 2026-09-08 (DECISION-SHEET A43): changed to 5e-4.** The port runs CoinRun's IMPALA
   trunk (A37's decided lineage) at MiniGrid's learning rate — a pairing nobody chose. The
   authors' own two branches disagree: `torch_rl/scripts/train.py:45` defaults `7e-4` constant,
   `coinrun/config.py:105` defaults `5e-4` with linear decay (`train_agent.py:52`). The rate moved
   to the architecture's lineage; the decay did NOT, because `torch_rl` has no scheduler at all and
   authoring one on an already-authored hybrid whose competence is unproven is a second unvalidated
   change. Declared as a deviation from the CoinRun lineage, beside the 64-d latent and single VIB
   sample A37 already declares.
2. **`idaac`'s reward normalization at the mechanism level** — the `ob=False`/`ret=True` call, its
   `cliprew=10`, and its internal `gamma=0.99`. Only ever raised as a generic "some families
   normalize reward" (review 2 §29). See item 3 and its verification note.
3. ~~**`sgqn`'s `sgqn_quantile` and hardcoded `0.9` consistency weight** under A41's rule.~~
   **CLOSED 2026-09-08 (DECISION-SHEET A41 EXTENDED), and the premise was wrong**: the paper says
   ρ = 0.95/0.98 *per task*, not 0.90, and assigns the consistency weight no value at all. Kept at
   the shipped values, now source-backed. Reading the paper also cost nothing and confirmed
   `OBSERVATION_GEOMETRY["sgqn"]` against its Table 3 (84x84x3, 3 stacked frames).
4. **Observation input scaling across the on-policy families** — `drqv2`-lineage `obs/255-0.5`
   ([-0.5, 0.5]); `idaac` `obs/255` ([0, 1]); `ppg`'s ImpalaCNN scales by `255.0`. A genuine numeric
   input-range difference no review examines; review 2 §5/§37 touches only resolution and frame
   stack.

   > VERIFIED 2026-09-08, and it is NOT an axis. All twelve were enumerated rather than the three:
   > `RL-ViGen-upstream/algos/drqv2.py:64` `obs/255.0 - 0.5` for the RL-ViGen five;
   > `runnable/dmc_gb/src/algorithms/modules.py:88` `x/255.`; `runnable/idaac/.../envs.py:89,103`;
   > `runnable/ppg/.../impala_cnn.py:165` `scale_ob=255.0`;
   > `runnable/ibac_sni/torch_rl/ibac_sni_runtime.py:56`; `runnable/alda/.../alda_trainer.py:512`;
   > `runnable/ctrl/algo.py:176,265,287,317` `state.astype(jnp.float32) / 255.`.
   >
   > **No baseline feeds raw 0-255** — which was the outcome that would have mattered, since it
   > would make activations two orders of magnitude larger at initialisation. The whole difference
   > is a constant additive shift of 0.5 on five baselines, and a constant shift of the input to a
   > convolution with a learnable bias is absorbed EXACTLY: shifting `x` by `c` changes `Wx + b` by
   > `Wc`, a per-channel constant the bias already represents. It changes initialisation-time
   > activation statistics and nothing about the function class.
   >
   > Recorded so the next review that notices the `- 0.5` does not have to re-derive this. It is
   > not in `BLOCKING_AXES` and should not be.
5. **P19's Places365 worker-count change** — flagged *unproven* by review 2 §15, never revisited.

   > MEASURED 2026-09-08 on the real fixture, and the claim is **true as stated but incomplete**.
   > At `num_workers` 0 vs 2 with one seed: identical file list, identical order, identical sampled
   > indices — so "never which images or in what order" holds. But the pixels differ (first-batch
   > max absolute difference 0.9686, mean 0.2052), because `RandomResizedCrop` and
   > `RandomHorizontalFlip` execute inside the workers, whose RNG is seeded from
   > `base_seed + worker_id`.
   >
   > Not a fidelity or comparability defect: a different random crop of the same image, drawn in
   > the same order from the same pool, is the same draw process. It does mean a seed is only
   > bit-reproducible at a FIXED worker count — and `RLVIGEN_PLACES_WORKERS` was a dial that
   > nothing read, forwarded, or recorded. `run_probe.sh` now pins and stamps it
   > (`NATIVE_PLACES365_LOADER`), and `run_on_production_host.sh` forwards it.
6. ~~**CTRL's `ema_ctrl=0.95` and `myow_reg=1`** — never checked against the paper.~~ **CLOSED
   2026-09-08 (DECISION-SHEET A45): neither appears in the paper at all.** Table 2 has no row for
   either and the text never mentions them, so the released defaults are the only source and they
   stand on the same footing as `cluster_len`. Nothing to check them against is a finding, not a
   gap.
7. ~~**ALDA's `init_steps=1000` warmup** and its relation to the 600k budget.~~ **CHECKED
   2026-09-08, nothing to do.** `runnable/alda/trainers/alda_trainer.py:52` is `init_steps: int =
   1000`, byte-identical to the official `ext/ALDA_Official/trainers/alda_trainer.py:50`. It is
   0.17% of the 600k budget, so it cannot matter at production scale — it mattered only as the
   `min_frames` floor it is already recorded as.

   > One nuance worth having on the record, because it touches `utd` — the most re-litigated
   > parameter in the whole corpus. At `step == init_steps` the trainer runs a **catch-up burst of
   > `init_steps` updates in one step** (`alda_trainer.py:692-694`), source-faithful and
   > deliberately outside the `utd` accumulator, which governs only the steady-state rate. So
   > "ALDA runs ~1.0 updates per transition" is true of the steady state and not of the first
   > 1,000 steps, where it runs 1,000 in one. Immaterial over 600k, but a reader reconciling
   > A27's UTD arithmetic against a training log would otherwise find an unexplained spike.
8. **PPG's decay applied to the *auxiliary* optimizer** — `--lr_decay_env_steps` decays policy,
   value AND auxiliary optimizers (`ppg.py:284-290`).

   > CONSIDERED 2026-09-08 under A44's logic and deliberately NOT changed. The two questions have
   > different answers, and the difference is the point.
   >
   > A44 moved `aux_lr` back to `5e-4` because the *rate* is recoverable: OpenAI ships `--lr` and
   > `--aux_lr` as separate flags at the same default, the supplement searched one rate, so the
   > authors' own procedure leaves the auxiliary flag untouched.
   >
   > The *schedule* is recoverable for neither optimizer. OpenAI's PPG has **no decay at all**
   > (`lr_decay_env_steps=None` is the released constant-rate behaviour), so the supplement's
   > "linear rate decay over 1 million environment steps" is an addition its authors made and did
   > not describe. Decaying both optimizers and decaying only the PPO one are both inventions.
   >
   > Where nothing is recoverable, editing authored code buys no fidelity — it only changes which
   > invention is on record. A36's choice stands, declared as **authored** rather than
   > source-backed. "The source is silent so keep the shipped value" (A44) and "the source is
   > silent and there is no shipped value either" (here) are different situations, and conflating
   > them is how a project talks itself into a change that gains nothing.
