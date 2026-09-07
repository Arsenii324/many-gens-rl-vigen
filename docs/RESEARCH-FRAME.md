# Research frame — what is given, what is manipulated, and what the design can actually support

> **Scope of this file.** There is a scope and there is a supervisor, but no tight instruction to
> work from — so the question below is a **reading**, reconstructed from
> `docs/STATUS-AGAINST-THE-GOAL.md` and refined in discussion, held with judgement rather than
> authority. Nothing here states definitively what was asked for. The analysis is conditional on
> the reading: if it changes, the identifiability arguments change with it.

`CONSTRUCTION.md` tracks the *construction*: what differs, who chose it, what was decided. It
does not say which of those items **threaten the research claim**, or whether the work being done
is building toward the question at all. That is this file.

## The question, as this project already states it

> Take twelve visual-RL generalization algorithms, train them under one protocol on one
> benchmark, and measure how much performance each **retains** when the visuals change.
> — `docs/STATUS-AGAINST-THE-GOAL.md`

Two words in that sentence carry the whole design, and they pull in opposite directions.

**"retains"** is fortunate, and I think under-appreciated. A retention endpoint —
eval ÷ train, or eval − train — makes **each method its own control**. That is the single most
important structural fact about this design, and it is what rescues it. See below.

**"one protocol"** is, as written, **not true**, and `CONSTRUCTION.md` is the list of ways it is
not. That is not a failure of execution: it is forced by the fidelity stance, because imposing
one protocol would mean editing the methods until they stopped being the published methods. But
the sentence should be read as *one benchmark, one task, one budget, one evaluation regime set* —
**not** one frame stack, one discount, one learning rate, one time-limit convention.

> **Note on what is actually converging.** The convergence this project builds is at the
> **presentation level** — the metrics the twelve report being on one scale and meaning the same
> thing — not at the protocol level. Editing the methods' protocols toward each other is *not* on
> the table now: the current work is not settled, N→N+1 means the next step is not knowable from
> here, and this project was built against *unify* and for *hermetic* deliberately. Stated
> because reading "one protocol" as a requirement is what produced the harness integration that
> had to be superseded.
>
> **And the null that follows.** A number is not only a number — it carries the system that
> produced it. **Two numbers from different systems are not the same quantity until shown to
> be.** That is the null here, and it is the same stance as "the original repository running its
> own `train.py`" applied one level up: the burden is on demonstrating comparability, never on
> suspecting incomparability.
>
> Env-derived quantities are the strongest case for it, because the *environment* defines them
> rather than the algorithm — reward, and the gaps built from it, are commonly the same across
> systems and visibly so. But "commonly" is not "by construction". They still depend on
> collection and presentation matching: warm-up, normalisation, truncation and termination, how
> an episode is counted and how it ends. Those are exactly the items
> [`CONSTRUCTION.md`](CONSTRUCTION.md) records, which is what makes that register the companion
> to this note rather than a separate concern.

## The four buckets

| Bucket | What is in it | Why |
|---|---|---|
| **GIVEN** — held fixed, deliberately not controlled | Each method's own hyperparameters, architecture, loop, buffer, augmentation, action distribution | Fidelity. The null is the original repository running its own `train.py`; equalising these would produce twelve things that are no longer the published methods. |
| **MANIPULATED** — the independent variables | (a) **method identity**, twelve levels · (b) **evaluation regime**, four levels (`train`, `eval-easy`, `eval-medium`, `eval-hard`) | These are what the experiment varies on purpose. |
| **MEASURED** — dependent variables | success rate (primary, unit-free) · episode return (dense, scale-arbitrary) · **retention** (the actual endpoint) | `docs/PART2-METRIC-INVENTORY.md` |
| **CONFOUNDED** — varies *with* a manipulated variable but is not the thing being studied | frame stack · time-limit handling · discount · learning rate · action distribution · render resolution · input range · reward normalisation | Every one of these is an `INHERITED` item in `CONSTRUCTION.md`. |

## The collinearity problem, stated plainly

**Method identity is perfectly collinear with its entire configuration.** Not approximately —
*by construction*, r = 1. Choosing `ppg` selects the declared DMC-comparator main profile: three
frames, γ=0.99, lr 3e-4, unless explicit legacy C1 overrides are used. It remains an unsquashed
Gaussian, 64×64 input, reward normalisation, and truncation-as-termination, all at once, with no
independent variation anywhere in the design.

| Method | frames | truncation | γ | lr | action dist. | render |
|---|---|---|---|---|---|---|
| `rad`, `soda` | 3 | **bootstraps** | 0.99 | 1e-3 | SAC squashed | 100→84 |
| `alda` | 3 | **bootstraps** | 0.99 | — | SAC squashed | 64 |
| `drqv2 svea sgqn curl drq` | 3 | zeroes | 0.99 | 1e-4 | DrQv2 trunc. | 84 |
| `ppg`, `idaac`, `ctrl` | **1** | zeroes | **0.999** | 5e-4 | unsquashed + clip | 64 |
| `ibac_sni` | **1** | zeroes | 0.99 | 7e-4 | unsquashed + clip | 64 |

The consequence is not subtle and it is not fixable by more seeds or more episodes:

> **No observed difference between two methods can be attributed to the algorithm**, because the
> algorithm never varies independently of seven other things. This is the standard
> unidentifiability of collinear predictors, and the honest statement is *"this design cannot
> separate them"* — not a smaller p-value.

## What the design *can* support, and what it cannot

### ✅ Identified — the clean contrast

**Within-method, across-regime.** Hold the method completely fixed — every confound with it — and
vary only the evaluation regime. This is a proper controlled comparison, and it is *the
generalization question*. `probe_regimes.py` has now established that the regimes genuinely
differ at the input (6–7× the within-regime control, [C19](CONSTRUCTION.md#c19)), so the
manipulation is real rather than nominal.

**Strengthened 2026-08-27, and the strengthening is the other half of the same claim.** C19 says
the regimes differ *at the input*. What it could not say is that they differ **only** there. That
is now shown: the deterministic random-policy floor is **byte-identical across `train` and
`eval-easy` — 200/200 episodes**, with both modes verified applied
([C81](CONSTRUCTION.md#c81)). A random policy's actions do not depend on the observation, and
after [C69](CONSTRUCTION.md#c69) the placement RNG is seeded, so the trajectory is fully
determined by the action sequence and the initial state. Identical returns therefore mean the
regime perturbs **neither the dynamics, nor the initial state, nor the reward**.

So the manipulation is *purely visual*, and a trained policy's regime gap is attributable to the
observation alone rather than to a quietly different environment. That closes the confound this
design is most exposed to, and it is not an argument — it is 200 equalities. **Before C69 it was
unavailable**: the pre-C69 floors read 1.82 against 1.85, and that gap was RNG noise which would
have read as the regime slightly perturbing the physics.

### ✅ Identified, and larger than previously stated — across-method, WITHIN the five natives

**Added 2026-08-27.** The collinearity argument above is correct across families and **does not
apply inside the RL-ViGen five**, which nobody had checked. Two independent measurements:

- **`scripts/audit_comparability_seam.py` restricted to the natives: 0 of 12 axes split.** Seven
  split across the twelve — truncation, render resolution, frame stack, action distribution,
  observation layout, regimes-per-run, and the one UNITS split, the evaluation scene set — and
  **not one of them splits within the five.** They share the evaluator, the estimator, the scene
  sweep, the horizon, the reward pipeline and the success definition.
- **Their hydra configs are identical on every shared key**: `frame_stack: 3`, `discount: 0.99`,
  `batch_size: 256`, `lr: 1e-4`, `feature_dim: 50`, and `action_repeat` overridden to 1 for all
  five by the same launcher line. The **only** difference is `nstep` — `drq_config.yaml: 1` against
  3 for the rest — and that is DrQ's own published value (RL-ViGen Table 2: *"N-step return — DrQ:
  1, otherwise: 3"*), a property of the method rather than a porting artifact.

**So for `drqv2`, `svea`, `sgqn` and `curl` the confounds this document lists as collinear with
method identity are held FIXED, and the contrast is identified.** The table above puts all five in
one row for exactly this reason; what had not been drawn is the consequence — *r* = 1 between
method and configuration is a statement about the twelve, not about these four.

**What this does not license.** The methods still differ in their own auxiliary machinery — SVEA's
augmentation and Q-target scheme, CURL's contrastive head, SGQN's saliency objective — and that
*is* the method, not a confound. It also does not turn one seed into a result: identification is a
property of the design, and the sample is still one run per cell.

**First use, and the direction is not the obvious one** ([C81](CONSTRUCTION.md#c81)): at 100k on
Door, `drqv2` reaches **439.75** on the trained scene and retains **22.9%** across the scene axis;
`svea` reaches **234.36** and retains **59.7%**. The weaker arm on the training distribution is
the stronger one off it — which is what an augmentation-based generalization method is for, and
which a table reporting only train-regime return would have inverted.

**Bears directly on P-C76**, the branch point recorded below under *"The endpoint is defined by a sweep only one instrument performs"*.
Its option 3 — report retention for the five natives and the regime gap for all twelve as two
separately named quantities — is stronger than it looked when written: the five are not merely the
ones with a scene sweep, they are a subgroup with **no derived comparability split of any kind**.

### ⚠️ Weakly identified — usable with a stated caveat

**Across-method comparison of retention.** Because retention divides each method by its own
train-regime performance, the confounds cancel *to first order*: a method's frame stack, lr and
discount affect numerator and denominator alike.

They do **not** cancel to second order, and that residue must be stated: a confound can
**interact** with the regime shift. A single-frame method may degrade under visual perturbation
differently from a three-frame one *for reasons about frames, not about the algorithm* — and
frame count is exactly one of the confounds. So a retention ranking is evidence about **published
methods as shipped**, not about algorithmic ideas.

Also blocked on [C18](CONSTRUCTION.md#c18): retention is a ratio, and a ratio over a near-zero
denominator is unstable — `RIGOR.md:113-117`. If train-regime success is ≈ 0, retention is
undefined and the endpoint does not exist. ~~**This is currently unknown and is the reason
[C17](CONSTRUCTION.md#c17) (the floor/ceiling probe) outranks the sweep.**~~

**Measured 2026-08-20 ([C55](CONSTRUCTION.md#c55)), and the fear was correct.** The floor is
**1.82** on Door — a uniform random policy, 400 episodes, zero successes in any of them — so the
denominator is not near-zero, it is near-*floor*, which is worse: it looks like a number. And
train-regime **success** really is 0: the `drqv2` 50k checkpoint scores 0 successes in 200
episodes across all ten train scenes, so **SR retention for that checkpoint does not exist**,
exactly as this paragraph predicted it might not.

What survives is return retention, and only where the denominator clears the floor *and* the
policy solves the task at all. `scripts/regime_retention_report.py` enforces both and prints
`AT-CHANCE` or `UNSOLVED-DENOMINATOR` instead of a ratio otherwise. The endpoint is therefore
narrower than this document assumed when it was written: it exists per checkpoint, not per
method, and a method with no solving checkpoint contributes no retention number rather than a
small one.

### ❌ Not supported by this design

- *"Algorithm mechanism A causes better generalization."* Confounded, unidentifiable.
- *"Frame stacking helps/hurts visual generalization."* Would require varying frame stack
  **within** a method. Nothing in the current design does.
- Any per-method ranking read as a statement about the algorithmic **idea** rather than about the
  released implementation at its authors' settings.

## The claim to actually make

*This claim shape and the argument for it are specific to the **retention** endpoint. Other
endpoints require their own analysis and are not covered here — a generalization gap, for
instance, is its own subject with its own established practice and its own fidelity
difficulties, and should be built properly rather than folded in as a variant of this one.*

> On RL-ViGen robosuite Door/Lift, at a fixed budget, **these twelve published implementations,
> run at their authors' own settings**, retain the following fractions of train-regime
> performance under three visual perturbation regimes.

> **The claim says "these twelve" and the instrument reaches five — 2026-08-26.**
> [C72](CONSTRUCTION.md#c72): the retention endpoint is produced by `scripts/eval_across_scenes.py`,
> which reads RL-ViGen's native agent interface and therefore only `drqv2`, `svea`, `sgqn`, `curl`
> and `drq`. The other seven cannot be put through it whatever their training produces, and zero of
> their own evaluators sweeps the scene axis. **So the claim as worded is not currently
> supportable**, and the honest version names five implementations, not twelve — or the design
> acquires seven more evaluators, which is the deferred decision in C72. This is a gap between what
> this document promises and what exists, and it belongs here rather than only in the register.

That is defensible, it is what the design measures, and it is genuinely useful — it is a
reproduction-and-comparison result, which the field is short of. It is **not** a claim about
which algorithmic mechanism generalises, and the write-up should not be allowed to drift into
sounding like one.

**This also decides two open items.** [C1](CONSTRUCTION.md#c1) and [C2](CONSTRUCTION.md#c2) ask
whether to equalise time-limit handling and frame stack. Under the claim above the answer is
**no — equalising would break the claim**, because the methods would no longer be as shipped. The
right move is to *declare and quantify* them. If instead the intended claim were about
mechanisms, equalising would be mandatory and the whole design would need rebuilding. **Decide
the claim, and C1/C2 follow from it** rather than being decided on their own.

## The reported endpoint (2026-08-18, logged retroactively 2026-08-19)

Logged late, and the lateness is the point: `scripts/decisions.py` was written on 2026-08-19 and
immediately found this decision recorded only as prose inside a resolved register entry, where it
could not be enumerated. It had already stopped being findable as a decision.

**P-C33 — return is the reported endpoint** (register [C33](CONSTRUCTION.md#c33))

| §4 field | |
|---|---|
| **Structural property of the original the mechanism depends on** | RL-ViGen reports episodic return on robosuite; success rate is not emitted by its own code at all |
| **What the target actually offers** | Both, once P10/P11 exist — but they are different quantities, and Door's return is dense and scale-arbitrary while success is sparse and task-defined |
| **Options** | (1) return as the reported endpoint, success retained as a second emission; (2) success rate as the endpoint, which is unit-free but at n=10 gives a Wilson interval of [0, 0.278]; (3) report both as co-equal, which invites readers to pick whichever is favourable per baseline |
| **Choice** | **(1), owner, 2026-08-18.** Success rate is not deleted; it is emitted and reported beside return, but return is the endpoint the comparison is keyed to |
| **What would show the choice was wrong** | Return proving unreadable without its floor — [C17](CONSTRUCTION.md#c17) requires the random-policy floor beside every reported return, and a table that omits it makes return meaningless. Also: if success rate at the production budget separates baselines that return does not, the endpoint choice would be discarding the signal |

## What a row means, given that a third of them do not reproduce (2026-08-19)

[C52](CONSTRUCTION.md#c52) measured that `sgqn`, `drq`, `idaac` and `alda` produce different
trajectories from the same seed, and that `ppg` cannot be asked. That changes what the claim above
can say per baseline, so it is settled here rather than in the register.

**P-C52 — report distributions, not runs** (register [C52](CONSTRUCTION.md#c52))

| §4 field | |
|---|---|
| **Structural property of the original the mechanism depends on** | Nothing in the reference; this is a property of the measurement, and the reference is not authoritative about measurement |
| **What the target actually offers** | Seven baselines reproduce at a fixed seed; four do not; `ppg` has no seed knob and no step budget. A "row" therefore means a re-runnable number for seven and a draw from a distribution for four |
| **Options** | (1) report distributions and say which baselines are which; (2) pin the reproducible configuration for those that have one — `drq` and `sgqn` reproduce on CPU at 5.8× and ~5× the wall-clock — and report runs; (3) hold results until every baseline reproduces, which for `idaac` and `alda` needs clone deviations they may not survive |
| **Choice** | **(1), owner, 2026-08-19.** It costs nothing, is true regardless of what is done later, and does not foreclose (2). Averaging over seeds is unaffected: each run is still a draw, and every cross-seed control fired |
| **What would show the choice was wrong** | A reader treating the four as re-runnable because the table did not say otherwise — i.e. the disclosure failing to travel with the number. The table, not this document, is where it has to appear |

This does **not** license the reverse reading: irreproducibility is not evidence the four are
worse, only that a single cell of theirs cannot be recovered. Their between-seed variance is
unmeasured, and [C18](CONSTRUCTION.md#c18)'s budget was derived from a `drqv2` pair and does not
transfer to them.

## Drift check — is the current work serving the question?

Honest accounting, because this is where meticulous projects fail quietly.

| | |
|---|---|
| **Infrastructure** — can twelve methods be run and compared at all? | Essentially complete, verified, 412 tests |
| **Instrument** — are the metrics right, and do they have the properties claimed? | Complete for what exists; measured rather than argued |
| **Evidence** — does any result exist? | ~~**None. Zero training runs beyond smoke.**~~ **Stale. As of 2026-08-26: five trained checkpoints, four verified cells, fourteen deterministic evaluation grids.** One cell yields a retention number (`drqv2` seed 6, 0.003); three reach a shaping plateau without opening the door. See [`STAGES.md`](STAGES.md). |

The last stretch has been provenance, audit and instrument work. That is **prerequisite** to the
question, not evidence for it — and this project's own status doc makes the same call: *"we could
have produced a full twelve-row table a week ago, and several of its rows would have been
meaningless."* That justification is real. It stops being real the moment the instrument is good
enough, and the risk from here is polishing rather than measuring.

> **Gate passed, 2026-08-20.** [C17](CONSTRUCTION.md#c17)/[C55](CONSTRUCTION.md#c55) measured the
> floor at **1.82** on Door, and the finding did change the plan rather than confirm it: the
> denominator is near-*floor* rather than near-zero, which looks like a number, and the guards in
> `regime_retention_report.py` exist because of it. The paragraph below is kept as the reasoning
> that set the gate.

**The gate I would set:** the next substantive work should be [C17](CONSTRUCTION.md#c17) — the
floor and ceiling — because it can show the endpoint does not exist at the affordable budget, and
that finding would change the plan rather than confirm it. Further instrument work should wait
behind it.

## The endpoint is defined by a sweep only one instrument performs (2026-08-26)

[C76](CONSTRUCTION.md#c76)'s seam audit derived eleven axes on the architecture that runs. Ten
agree, or split only in ways this claim already declares and quantifies. **One does not, and it is
the axis the endpoint is made of**, so it is settled here rather than in the register.

`scripts/eval_across_scenes.py` sweeps ten scenes, nine of them held out, and reports a mean over
that sweep. **All seven** non-native evaluators build their env with `scene_id=0` and vary only the
visual regime — `idaac` `envs.py:101`, `ibac_sni` `general.py:74`, `rad`/`soda` through `dmc_gb`'s
`wrappers.py:23`, `alda` `alda_trainer.py:142`, `ctrl` and `ppg` by taking the same default. So a
native's number is *mean return over ten scenes* and every other baseline's is *mean return at
scene 0*. Those are different estimands. This is [C72](CONSTRUCTION.md#c72) stated as what it
always was: not a gap in coverage that more runs would close, but a disagreement about what the
reported quantity is.

**P-C76 — what the retention endpoint is measured over** (register [C76](CONSTRUCTION.md#c76))

| §4 field | |
|---|---|
| **Structural property of the original the mechanism depends on** | RL-ViGen's held-out axis is the visual regime, not a scene split. No baseline's own evaluator sweeps scenes, because none of their originals had a scene axis to sweep — Procgen varies levels, DMC-GB varies backgrounds |
| **What the target actually offers** | robosuite exposes `scene_id`, and [C46](CONSTRUCTION.md#c46) measured that scenes 1–9 separate from scene 0 in observation space. Only this project's instrument uses it; adding it to a clone is a per-baseline deviation, in seven places |
| **Options** | (1) give the seven evaluators a scene sweep — closes the split, costs a deviation in each clone and re-opens the faithfulness ledger for seven baselines; (2) redefine the endpoint to the regime axis alone, at `scene_id=0`, which every baseline can already produce and which is also RL-ViGen's own held-out axis — cheapest, and discards the scene evidence [C46](CONSTRUCTION.md#c46) established; (3) report retention for the five natives and the regime gap for all twelve, as two separately named quantities never pooled |
| **Choice** | **NOT MADE — the owner's.** Recorded as a branch point rather than resolved, because every option changes what the headline number means, and (2) in particular would retire a measurement already taken. [`PREMISES.md`](PREMISES.md) P4 is where the evaluation-protocol rung sits |
| **What would show the choice was wrong** | For (1): the added sweep proving to be the deviation that breaks a clone's fidelity claim, so that a comparable number costs an incomparable algorithm. For (2): the regime axis at one scene failing to separate baselines that the scene axis does — the manipulation going nominal, which [C19](CONSTRUCTION.md#c19) only ruled out for a *random* policy at the *input* level. For (3): readers pooling the two anyway, which is the same disclosure-does-not-travel failure P-C52 names |

**Until this is decided, no cross-baseline retention table can be emitted**, because there is no
single quantity for its column to hold. Nothing else in the plan is blocked by it: the five natives'
cells are well defined under every option, which is why production continues while it is open.

## What would make this frame wrong

- If the actual question *is* about mechanisms, then the confounding above is not a caveat but a
  design failure, and the correct response is a within-method ablation, not a twelve-method
  table. See the scope tag at the top: the formulation here is a working one.
- If train-regime success is ≈ 0 for all twelve at the affordable budget, retention is undefined
  and the endpoint must change — to return, to a shaped-progress measure, or to a different task.
- If the eval regimes turned out not to differ, the manipulation would be nominal. Measured and
  ruled out ([C19](CONSTRUCTION.md#c19)) — at the *input* level and for a *random* policy.
  **Both halves now hold at the outcome level too** ([C81](CONSTRUCTION.md#c81)): the random
  policy's returns are byte-identical across the regimes, 200/200, so the regimes differ in the
  observation and in *nothing else*. The caveat this line used to carry is discharged; what
  remains open is the opposite question — whether the gap a *trained* policy shows is
  method-specific, which needs more than one baseline.
