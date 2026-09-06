# Decision sheet — everything waiting on you, in one pass

Written 2026-09-05. **Answer by exception**: every line has a researched best-judgment default.
That default is the choice this project implements, validates, and plans around—as if it were the
decision—rather than a plausible placeholder. An `OWNER` label records only that the owner has not
formally settled the choice; it does not suspend the work or downgrade the default's status as the
current technical recommendation. It becomes formally settled only when the owner accepts it
(explicitly or by a later recorded steer). Production launch and source freezing remain separate
gates.

Reasoning for each is in `notes/owner-decisions-recommended.md`; live status is
`python scripts/production_gates.py`.

---

## A. Decisions awaiting owner settlement

| # | question | my default | cost if you agree |
|---|---|---|---|
| **A1** | Run an IBAC-SNI pilot at the exact final config before committing it to the fleet? | **Yes — 100k, one seed.** We hold the 0.01 control at exactly 100k, so the contrast is free; any other budget throws it away | ~1 job-hour |
| **A2** | Apply PPG's auxiliary-KL fix (sum over action dim before mean)? | **Yes.** We used the identical argument to change `ibac_sni` twice; preserving the literal line is the *less* faithful choice once the tensor's rank changed | one line + a rerun of nothing (no PPG result is published) |
| **A3** | Headline generalisation quantity | **Success rate primary; `R_train`, `R_OOD`, `Δ = R_OOD − R_train` reported; retention ratio secondary and only for competent baselines.** A ratio is not offset-invariant and Door's reward is shaped with a non-zero floor | none |
| **A4** | P-C76 — what retention is measured over | **Report all three estimands; headline B** (appearance varied with geometry held fixed, aggregated over scenes). Only B isolates *visual* generalisation; C conflates appearance with scene shift while sounding like A | none — the grid already collects it |
| **A5** | Time-limit split (3 bootstrap / 9 terminal) | **Declare, do not harmonise.** Harmonising means editing 3 or 9 clones, which the null forbids. State the direction: on Door every episode ends by time limit, so the nine are systematically disadvantaged | none |
| **A6** | Seed policy | **Fixed 3 for every reported row, predeclared.** My earlier adaptive proposal was outcome-dependent sampling and I withdraw it. 5 would be better and costs ~853 job-h against 512 — so keep 3 and weaken the claim to match | none |
| **A7** | Checkpoint rule | **Endpoint is the headline; trajectory is descriptive; no selected-best column.** Anything else needs reserved validation episodes, equal candidate opportunity, and a per-seed/per-method choice, all decided in advance | none |
| **A8** | Merge the corrected statistical protocol into `EVAL-PROTOCOL.md`? | **Yes.** Outer unit = training seed (n=3, *not* 600 episode rows), scenes treated as a fixed grid, numeric competence threshold, missing-run policy | none |
| **A9** | Establish the external RL-ViGen anchor (C48) **before** the fleet? | **Yes.** All three reviews reached this independently. The current plan makes a production cell double as the anchor, which inverts the dependency — a fleet measured against an unvalidated pipeline cannot be repaired afterwards | ordering only, if the anchor cell is also a production cell |
| **A10** | Production canary | **`soda` at full 6e5, one seed, whole pipeline.** It is the longest projected cell (45 h), so it proves the envelope for everything else — **and if it passes it is not overhead, it is seed 1 of `soda`** | ~45 job-h, recovered if it passes |
| **A11** | Commit the tree now? | **Yes — one checkpoint commit of everything as-is.** Two agents' work is interleaved across ~48 paths with no commit since `12f6322`, which predates all review work. An ugly checkpoint beats an unrecoverable tangle | minutes |
| **A12** | Register rows for the three-review triage — me or Codex? | **Codex**, since it is actively editing `REGISTER.md` (168 → 169 while I worked). I will write them if you'd rather | none |

## B. What I do when you answer

- **A1, A10** — submit both jobs immediately; they are independent and can run in parallel under the
  4-job limit.
- **A2** — apply the one-line PPG change, invert the demonstrating test deliberately, and note it as
  a declared deviation.
- **A3–A8** — write the frozen protocol manifest, which is also gates "statistical protocol frozen"
  and "checkpoint rule frozen".
- **A11** — commit, which closes the "source tree frozen" gate and makes provenance real.

## C. Not blocked on you — in flight or with Codex

- `bt1gio1ng14k4o94dpie` — ALDA curve eval, SUCCESS; `run_scene_alda` is now exercised and
  evaluator-family coverage is 7/7. The earlier `bt1nmsbsf7u1o4618eks` attempt failed before
  training because the payload lacked the declared checkpoint key; it is retained as a diagnostic
  record, not as current state.
- With Codex, handed over and not waiting on a reply: the determinism asymmetry (it confounds
  `audit_shared_evaluator.py`), `eval_every_frames: null`, `xfail` for the deliberate docs failure,
  ctrl config binding, idaac evaluator device, the alda cadence descriptor gap, and the submit-time
  RAM invariant.

## D. What happens if you say nothing at all

Continue toward the documented defaults: keep the gate manifest current, fix and validate
mechanical defects, run bounded pre-production probes when they close a real readiness gap, and
keep the decision surface current. Do not call an owner default “settled,” launch the production
fleet, or create the source-freezing commit without the corresponding owner action.

---

## Revision, 2026-09-05 — A9 becomes free, and A4 is confirmed by the project's own frame

**A9 (external anchor).** I read RL-ViGen's published table
(`RL-ViGen-upstream/results/evaluation_score.xlsx`, sheet Robosuite) — `scripts/rlvigen_reference.py`
looks for it at a path absent from this tree, which is likely why it had never been read here.
Their published **DrQ-v2 Door eval-easy is 3.6** across seeds {3, 7, 4, 3, 1}, against our measured
random floor of 1.82. CURL 6.6, DrQ 14.0. **SVEA 268.8, SGQN 391.4, PIEG 387.2, SRM 337.2.**

So: **their own DrQ-v2 does not generalize on Door either** — and our 100k `drqv2` eval-easy of
**1.44** sits inside the lower end of their seed spread rather than 130× away from anything.

**Revised default for A9: do not commission an anchor run.** State T3 as *"`drqv2` Door eval-easy
falls within the published five-seed range 1–7"* and evaluate it against the production `drqv2`
seeds, which the fleet produces anyway. That converts A9 from a prerequisite costing a cell into a
**free acceptance test** — while still satisfying the ordering all three reviews asked for, because
the check is defined before the run rather than after. Full detail:
`notes/rlvigen-published-door-anchor.md`.

**One caveat that must be closed first, and it is a reading task, not a compute task:** the sheet's
units are not certified. `lift` rows are 0–3 while a random arm reportedly scores ~7.5 on Lift,
which does not fit a return reading. C45/C47 exist precisely because two figures were compared that
were never the same quantity — so confirm what these numbers *are* before quoting agreement.

**A4 (headline estimand B) — confirmed, and no longer my opinion.** `RESEARCH-FRAME.md` states the
question as *"how much performance each retains when the visuals change"*, and names the identified
clean contrast as **within-method, across-regime**. [C81](../docs/CONSTRUCTION.md#c81) shows the
random-policy floor is byte-identical across train and eval-easy (200/200 episodes), so the regimes
differ **only** at the observation. That is exactly estimand B — regime varied, scene held fixed.
Estimand C additionally varies scene, which is a geometry manipulation the project has never
certified as clean.

**A3 (metric) gains a constraint from the same source.** If the *reference itself* publishes DrQ-v2
at 3.6 on Door, a near-floor eval number is the **expected published outcome** for that method. The
competence rule must not classify a faithfully reproduced published failure as an implementation
defect — report `R_train` (480.6, plainly competent) alongside and let the eval number stand.

---

## Revision 2, 2026-09-05 — the owner's own answers, folded in

**A2 is no longer open: Codex applied the PPG fix** (`ppg.py:203`,
`kl.sum(-1).mean() if kl.ndim > 1 else kl.mean()`). It is the change I recommended and review 2
favoured, and the reasoning in its comment is correct — but it was queued for your explicit yes and
is now decided by action. Noted so the record is accurate rather than to reopen it.

**A3 superseded by your steer — report everything; the headline is provisional.** You said the
deliverable is a good evaluation of the twelve with *all kinds of metrics reported*, that you do not
want to settle on only some, and that a headline should not be a permanent choice you cannot revisit
after the runs. That is compatible with the statistical concern, and the reconciliation is precise:

- **Compute and publish the full metric × method matrix** — `R_train`, `R_OOD`, `Δ`, success rate,
  ratio and floor-adjusted ratio, per regime and per scene. Complete reporting is the *opposite* of
  selective reporting, so a post-hoc change of which metric leads is harmless: every alternative is
  on the page and a reader can see them.
- **What must still be fixed in advance is not the metric but the *comparison set and the rules***:
  the competence threshold, the missing-run policy, and either a named set of primary comparisons or
  a commitment to publish the whole pairwise matrix. Review 3's worry is not "the headline changed",
  it is "sixty-six noisy comparisons were scanned and the attractive ones narrated".
- So: **headline = provisional and re-settable; rules = frozen.** With everything reported, choosing
  a different headline later is presentation, not selection bias.

**A9/A10 rescoped by your infra note.** Production is another V100 with Docker and a Linux
environment of our choice — not DataSphere. Therefore the tier table, RAM invariant, grant
arithmetic and the 45 h `soda` wall-clock worry are **preproduction concerns** protecting the probes
we still run here; they are not production constraints. What transfers is per-cell hours, memory
footprints, and C95 — which becomes *tractable*: we control the image, so match the validated
renderer by construction, pin the digest, and reproduce one known cell (drqv2 100k train 480.6)
before the fleet.

**New, and yours: is Lift in scope?** You mention "Door, and possibly Lift". Every constant in this
project is Door's — the 1.82 floor, the certified ten scenes, the 500-step horizon, the published
anchor table. Lift needs each re-derived, not reused (a random arm reportedly scores ~7.5 there).
It is now a gate rather than a footnote.

---

## Revision 3, 2026-09-05 — A1's criterion was unfalsifiable; redesigned

My original A1 rule ("include if any success, or return clearly above the 1.82 floor") **could not
distinguish a broken configuration from too short a run**, and the second is the likelier reading:
`drqv2` reaches train success 1.00 by ~75k but is off-policy and sample-efficient, while `ibac_sni`
is on-policy PPO on one 64×64 frame with Procgen-lineage relatives tuned for millions of frames. An
absolute threshold at 100k tests the budget, not the fix.

**Revised: judge the pilot against the control we already hold at exactly 100k**
(`bt1i1s0j8qhbal67gjnn`, `entropy_coef=0.01`). The question becomes *did changing the coefficient
change the trajectory* — answerable at 100k because the comparison is like-for-like.

1. policy scale stays flat, where the control climbed 0.0026 → 1.4472;
2. train-regime return shows a positive trend, where the control sat at 2–4 throughout;
3. any success events — a bonus, not a requirement.

(1)+(2) → into the fleet, reported honestly including a possible floor-level eval score, **which is
what RL-ViGen's own published DrQ-v2/CURL/DrQ do on Door** (3.6 / 6.6 / 14.0 against a 1.82 floor).
(1) only → run the bottleneck ablation, or hold 0.01 and report a faithful floor row, before
spending three production seeds. (1) fails → the diagnosis is wrong; spend nothing.

**Explicitly not tested:** whether `ibac_sni` solves Door at 6e5. That is the production run's
question, and conflating the two is what made the first rule unfalsifiable.

**Full recommendations, all now researched rather than asserted:**
`notes/owner-decisions-recommended.md`, `notes/retention-and-eval-depth.md`,
`notes/record-completeness-spec.md`, `notes/rlvigen-published-door-anchor.md`.

---

## A13 (new, 2026-09-05) — the production shape in CALENDAR time, which nobody had converted

Every cost figure this project carries is DataSphere's, in RUB and grant units. On our own V100s the
currency is **days**, and that had not been computed. Training plus intermediate eval, 4 regimes ×
10 scenes, 5 episodes per intermediate stamp:

| shape | train h | eval h | total | 1 V100 | 2 V100s |
|---|---:|---:|---:|---:|---:|
| **6e5 × 3 seeds, 50k grid** | 601 | 130 | **731** | 30.5 d | **15.2 d** |
| 6e5 × 3, 100k grid | 601 | 70 | 671 | 28.0 d | 14.0 d |
| 3e5 × 3 | 301 | 70 | 371 | 15.4 d | 7.7 d |
| 6e5 × 1 seed | 200 | 43 | 244 | 10.2 d | 5.1 d |
| 1e5 × 3 | 100 | 30 | 130 | 5.4 d | 2.7 d |

**These are T4-derived.** Every FPS figure was measured on `gt4.1` (T4). A V100 is typically
1.5–2× a T4 for fp32, which would put 6e5 × 3 at **10.2 d (1.5×) or 7.6 d (2×) on two GPUs**. That
factor is **assumed, not measured**, and it swings the schedule by a factor of two.

### Recommended default

**6e5 × 3 seeds on two V100s — plan for ~2 weeks, expect ~8–15 days.** The shape is not chosen for
cost, it is forced by two independent constraints that happen to agree: **6e5 is the budget
RL-ViGen's published Door numbers were produced at**, so the T3 anchor comparison is only direct
there; and **3 seeds is the minimum that supports any ranking claim**. Cutting either breaks
something the project needs.

### The ordering, which matters more here than the total

1. **Measure the V100/T4 throughput factor first**, with one short cell, the moment access exists.
   A two-week plan resting on an assumed 2× is not a plan. This costs under an hour.
2. **Run the longest cells first** — `soda` (45 h), `rad` (24 h), `sgqn` (22 h). If the envelope
   breaks, it breaks on day 1–3 rather than day 12. This is the canary argument, and on a
   calendar-bound campaign it is stronger than it was on a billed one.
3. **The `ibac_sni` pilot runs in parallel early** — about one job-hour, and it gates whether three
   seeds of that baseline are worth spending at all.
4. **Retain intermediate checkpoints throughout.** This converts the failure mode: a campaign
   interrupted on day N still yields a complete curve up to N for every cell that finished, instead
   of nothing. On a two-week run that is the difference between a setback and a restart.

### What changes if two weeks is too long

The honest options are **3e5 × 3** (7.7 d on two GPUs) or **6e5 × 1** (5.1 d), and they fail
differently. 3e5 keeps the ranking claim but breaks the direct anchor comparison, since their
published numbers are at 6e5. 6e5 × 1 keeps the anchor but supports **no ranking whatsoever** — it
is a screening run, and the third review is explicit that a one-seed result must never be
substituted into a final table. **If the calendar is the binding constraint, prefer 3e5 × 3 and
state that the anchor is indicative rather than direct** — losing a comparison is recoverable,
losing the replication unit is not.

### A13 CORRECTED — my first figure was incomplete in three ways

Checking my own arithmetic rather than restating it:

**1. I omitted the endpoint evaluation entirely.** A13 counted training + *intermediate* eval only.
The endpoint grid (20 episodes × 4 regimes × 10 scenes × 12 × 3) is another **40 h**.

**2. No contingency.** Failed cells, reruns, setup. At a conventional 15%:

    training                 601 h
    intermediate eval (5ep)  130 h
    endpoint eval (20ep)      40 h   <- was missing
    subtotal                 772 h
    +15% contingency         887 h   = 37.0 d on 1 GPU, 18.5 d on 2   (T4-derived)

**3. I assumed two GPUs means two concurrent cells. It does not, and the correction runs in our
favour.** VRAM per baseline is small — `sgqn` is the largest at **7.1 GiB**, most are 1.6–3 GiB — so
a 16 GB V100 can host **two to four cells at once**. The binding constraint is **host RAM**, where
`alda` alone needs 14.73 GiB (measured).

This project has already measured the cost of packing: **retention 0.658** at 10k on `gt4i.1`, i.e.
co-located cells each run at ~66% speed, so two per GPU yields ~1.32× throughput rather than 2×.
Two V100s, two-way packed: `887 / (2 × 1.32) ≈ 337` T4-equivalent hours ≈ **14 days**, and at an
assumed 1.5× V100 advantage ≈ **9.4 days**.

**Corrected bottom line: plan two weeks, expect 9–14 days on two V100s with two-way packing** —
against the 15.2 days I first quoted, which was simultaneously too optimistic (missing 40 h of
endpoint eval and any contingency) and too pessimistic (assuming no packing). The two errors
partially cancelled, which is exactly why the number needed rechecking rather than adjusting.

**Still assumed and worth measuring on day one:** the V100/T4 throughput factor, and whether the
production host's RAM permits two-way packing given `alda`'s 14.73 GiB. Both are one short cell each.

### A13 COMPLETE — every term, each labelled by how well it is known

My second pass was still missing a term, and it is not small: **environment construction**.
`eval_grid` builds an env per (regime, scene), so the fleet performs
`14 stamps × 4 regimes × 10 scenes × 12 baselines × 3 seeds` = **20,160 env constructions**. At
5–30 s each — robosuite is not fast to build — that is **28–168 h**, which my model omitted entirely.
It is partly offset by an error in the other direction: I priced evaluation at *training* FPS, but
evaluation has no backward pass and should run perhaps 2× faster per step.

**The complete envelope, 6e5 × 3 seeds, 50k grid, on two V100s with two-way packing:**

| eval speed | env build | total (T4-equiv) | 2 GPUs packed | V100 @1.5× | @2× |
|---|---|---:|---:|---:|---:|
| = training FPS | 5 s | 919 h | 14.5 d | 9.7 d | 7.3 d |
| = training FPS | 30 s | 1080 h | 17.1 d | 11.4 d | 8.5 d |
| 2× training FPS | 5 s | 822 h | 13.0 d | 8.6 d | 6.5 d |
| 2× training FPS | 30 s | 983 h | 15.5 d | 10.3 d | 7.8 d |

**Answer: 6.5–17 days, with the realistic band ~7–11 days.**

### What is measured, what is modelled, what is unknown

**Measured on real jobs:** per-baseline training FPS (T4); checkpoint sizes (**~28.6 GiB fleet-wide
at a 50k grid, corrected 2026-09-05 — CORRECTIONS #50; the prior "35.5 GB" was a different cell's
replay buffer, misattributed**);
packing retention **0.658**; `alda` host RAM **14.73 GiB**; VRAM per baseline (max `sgqn` 7.1 GiB, so
VRAM is not the packing constraint — host RAM is).

**Modelled, with the assumption stated:** eval throughput (1–2× training FPS); env construction
(5–30 s); contingency (15%).

**Unknown, and the first two are cheap to settle:** the **V100/T4 factor** — assumed 1.5–2×, and it
swings the schedule more than everything else combined; whether the production host's RAM permits
two-way packing; and the real env-construction time.

**The one measurement that collapses most of the uncertainty** is not a training run at all: time a
single offline evaluation of an existing checkpoint on the production box — one checkpoint, four
regimes, ten scenes. That yields the V100 factor, the env-construction cost and the eval throughput
in one shot, in minutes rather than hours, and turns this table into a single row.

---

## A14 (new, and I think the highest-leverage item on this sheet) — do we match upstream parallelism?

**The finding.** Nine of twelve baselines carry a resource-forced learning-dynamics adaptation, each
verified against the clone's own declared default:

| baseline | source | production | reduction |
|---|---|---|---:|
| `ppg` | 4 MPI × 64 envs (`README.md:34`, `train.py:27`) | 1 × 8 | **32×** |
| `idaac` | 64 processes (`arguments.py:62`) | 4 | **16×** |
| `ibac_sni` | 16 procs (`scripts/train.py:41`) | 1 | **16×** |
| `ctrl` | 64 envs (`train_ppo.py:86`) | 16 | **4×** |
| RL-ViGen five | ~1M replay | 300k cap (`families.json:90`) | evicts half the run |

For synchronous on-policy methods the environment count is not a throughput knob — it sets the batch
distribution and the update cadence per collected frame. Two external reviews independently rate
this the largest remaining class of criticism.

**Why it is a decision and not a defect: every one of these was forced by DataSphere.** The replay
cap's own recorded reason is explicit — uncapped is 38.8 GiB and no allowed tier holds it (`gt4i.1`
gives ~27 GiB) — and 4–8 cores is why 8, 4, 1 and 16 environments were chosen. **Production is a
V100 box with Docker and a Linux environment of your choice.**

**What I need from you is one fact, not a decision: the production host's core count and RAM.**

- **Many cores and ~40+ GiB** → match upstream (`ppg` 4×64, `idaac` 64, `ibac_sni` 16, `ctrl` 64,
  replay 1M). That **deletes two `high` fidelity ratings and one adaptation touching five
  baselines**, and converts the largest reviewer criticism into a non-issue. It also changes the
  throughput model, so A13's calendar estimate would need recomputing — probably downward, since
  more parallel envs collect frames faster when CPU allows.
- **Constrained host** → keep the current values, and they become *declared* target adaptations with
  a stated reason, which is defensible but must be in the write-up's limitations rather than a
  footnote.

**My default if you say nothing: keep current values and declare them**, because I cannot verify the
host. But I would not freeze the production configuration before asking, since the answer changes
what the configuration *should be* — not merely how fast it runs. It is the cheapest question on
this sheet and the one with the largest consequence.

### A14 ANSWERED by `notes/remote-infra.txt` — partially, and the partial part matters

**Measured host:** 16 cores (2×8 Xeon Gold 6154 @3.0GHz, 1 thread/core), **113 GB available RAM**,
**2× Tesla V100-SXM2-32GB**. Note **GPU 0 is already occupied** by another user's process
(15.1 GB, 67% util); **GPU 1 is free**.

**RAM removes one adaptation outright.** The 300k replay cap existed solely because no DataSphere
tier held the 38.8 GiB an uncapped cell needs (`gt4i.1` ≈ 27 GiB). With 113 GB, **one uncapped cell
fits comfortably and two fit at 77.6 GiB**. So the source-scale ~1M buffer is affordable, and the
"evicts the first half of a 600k run" adaptation across five baselines can simply go away.

**Cores answer the parallelism question unevenly** — 16 cores, and robosuite stepping is CPU-bound:

| baseline | source | current | reachable on 16 cores | gap |
|---|---:|---:|---:|---|
| **`ibac_sni`** | 16 procs | 1 | **16** | **16× → CLOSED, exactly matches upstream** |
| `idaac` | 64 | 4 | 16 | 16× → 4× |
| `ppg` | 4 MPI × 64 = 256 | 8 | 16 | 32× → 16× |
| `ctrl` | 64 | 16 | 16 | 4× (already at the ceiling) |

So `ibac_sni` can match its source **exactly**, and `idaac`/`ppg` improve substantially but cannot
match — 16 cores will not host 64 or 256 robosuite environments.

**Implemented, then reverted, and the reason is worth stating.** I applied all four values, then
found two problems with my own change: the replay key I edited was the **top-level** one while
`family.py:222` reads the **production block** — so the change was a no-op that left two
`replay_capacity` values disagreeing in one file — and the `constants` edits *were* live, meaning
**DataSphere probes would inherit 16 processes on a 4-core tier and a 38.8 GiB buffer against a
27 GiB ceiling, failing exactly as `alda` did.** Reverted to probe-safe values; targets recorded in
the explicit `families.json` `v100` host profile.

**Standing default, unchanged in substance:** these are the production configuration, to be applied
**together, at migration**, with the throughput model recomputed — more environments collect frames
faster, so A13's calendar likely improves. They are not applied now because the descriptor serves
both the probe fleet and production, and there is no per-target override.

**One operational fact that affects A13 directly: GPU 0 is in use by someone else.** A13 assumed two
free V100s. If only GPU 1 is available the campaign is roughly twice as long — 18–28 days rather
than 9–14. **Worth confirming whether GPU 0 frees up before scheduling.**

---

## Revision, 2026-09-05 (later) — from reviews 6, 7 and 8

Evidence for each item is in [`review-6-7-8-triage.md`](review-6-7-8-triage.md). Three rows change
and two are added. All are **implemented**; all remain open for your ratification.

### A1 is superseded — the existing IBAC evidence does not describe the configuration we would run

Two independent reasons, both found after A1 was written:

1. **The VIB coefficient was wrong by 10,000x.** `runnable/_launch/ibac_sni.sh` passed no `--beta`,
   so the branch default of 1.0 applied, while `FAITHFULNESS.md:808` recorded `vib_beta: 1e-4` as
   ours and matching CoinRun. beta multiplies the bottleneck KL that *is* the IBAC mechanism.
   **Fixed to `--beta 1e-4`.** A penalty 10^4 too strong is a plausible mechanism for a policy that
   neither diverges nor learns — exactly what the pilots recorded — so the beta defect is a live
   candidate explanation for the competence question A1 exists to answer.
2. **`procs=1` is not the production configuration.** The explicit `v100` profile sets `procs=16`,
   which changes rollout size, minibatch count and updates-per-frame. Review 7 is right that A14
   must be applied **before** A1's pilot, or the pilot measures a different algorithm.

**Consequence:** the prepared `cfg-c61-entropy-v80.yaml` **must not be launched as written** — it
pins `payload-v67.tgz`, which predates both the beta fix and the payload-contract fix, and it probes
stability at 25k rather than competence. And the earlier entropy pilots must not be cited as
evidence about the corrected configuration.

**Also note the tier ceiling:** `procs=16` does not fit `gt4.1`'s usable memory envelope, but it
does fit the high-memory `gt4i.1` envelope for a bounded functional smoke, as now shown by
`bt1djai23kme336auat4`. **The final-configuration IBAC competence pilot remains a production-host
job** because the project's production host is the V100 and the DataSphere smoke is only 4,096
frames; a beta-corrected pilot at `procs=1` would measure a different rollout geometry and is not
the A1 pilot.

### A5 — the direction is withdrawn, the difference is kept

A5 said the nine terminal-at-horizon methods "are systematically disadvantaged." Review 7 is right
that this is a directional judgement without a controlled ablation. If Door's 500 steps *define* a
finite-horizon episodic task, zeroing the value target at the endpoint is the coherent treatment,
not an error; bootstrapping is natural only if the horizon is an artificial truncation of a
continuing MDP. Evaluation is itself a fixed 500-step episodic score, which if anything favours the
finite-horizon reading.

**Revised wording:** *methods retain their native time-limit semantics; three bootstrap and nine
terminate, so their learning targets differ near the horizon.* Report the difference, drop the
direction, unless someone runs the ablation.

### A17 (new) — IBAC-SNI's VIB coefficient: `--beta 1e-4`

**Implemented.** CoinRun's value, which is the branch this configuration already follows (the trunk
is `--model_type impala`, ported from IBAC-SNI's own CoinRun branch per C3), and the value
FAITHFULNESS already claimed. The alternative reading — 1e-6, the Multiroom value — would follow the
`torch_rl` branch the bottleneck implementation comes from. **This is a real fork and it is yours:**
the port is a hybrid of the authors' two implementations, so either lineage can be argued. I took
CoinRun because the trunk and the recorded fidelity claim both point there.

Not fixed, and not fixable without authoring: `--nr-samples 12` has no equivalent in `torch_rl`
(we draw a single VIB sample) and the latent is this branch's 64-d against CoinRun's 256-d. The
honest description stays **"an authored hybrid continuous-action IBAC-SNI adaptation."**

### A18 (new) — subtract the random floor before forming any retention ratio

**CORRECTED 2026-09-06 — implemented in an emitter now, was stale.** `scripts/results_table.py`
computes `scene_ret_floor_adj`/`regime_floor_adj` per this exact formula, printed in a dedicated
"FLOOR-ADJUSTED RETENTION" section beside (not replacing) plain retention, matching
`EVAL-PROTOCOL.md:23`'s own metrics-reported row ("retention AND floor-adjusted retention").
Refuses (prints REFUSED, not a number) wherever the floor-adjusted denominator would not be
positive. `preprod_table.py` needed no equivalent change: it reports one regime's raw return per
row and never formed a train-vs-eval ratio to begin with, floor-adjusted or otherwise. Tests in
`tests/test_results_table.py` verify the formula by hand against a synthetic grid (not just that
it runs), and the refusal guard; both proven non-vacuous. See `notes/CORRECTIONS.md` #86.

The "still to do" note below (re-measure the floor under the current evaluator) is a data-currency
question, not a code one now: `results_table.py`'s `floor_mean` is whatever floor grid is actually
loaded for a given run, not a hardcoded literal, so the formula is automatically as current as
whatever floor measurement is on disk when the table runs.

**Implemented in the protocol notes, not yet in an emitter** (no retention table is generated yet).
`CORRECTIONS.md` #5 established that a ratio is not invariant to reward offsets and that Door's
reward is shaped with a non-zero floor; it demoted the metric but never gave the repair. The repair
is to form the ratio on floor-subtracted quantities:

    retention = (R_OOD - R_floor) / (R_train - R_floor),   R_floor = 1.818

using the **200-episode** floor (C55), not the 25-episode 1.633 (C17) — those are the same quantity
at two sample sizes and `scripts/rlvigen_reference.py` was reporting the weaker one while its own
comment cited the stronger. It now reports 1.818 and stamps the sample size.

Credit where due: this repair is the one genuinely useful contribution of the Gemini report (its
A4). Its A9 — anchoring on the published DrQ-v2 3.6 — must **not** be actioned; see the triage.

**Still to do before this is real:** re-measure the floor under the current evaluator, as reviews 7
and 8 both ask. It is cheap and it pairs with the drqv2 renderer re-measurement.

### A19 (new) — PPG's `n_pi`: the auxiliary cadence has no faithful setting at a 600k budget

All three of reviews 6, 7 and 8 raise this and none of them can resolve it, because it is a genuine
fork rather than a defect. `scripts/audit_executed_hyperparameters.py` classifies it as
**DEFAULTED** — nobody passes `--n_pi`, and the clone's default of 32 happens to equal what
FAITHFULNESS claims. True only by luck, and the luck is beside the point:

`n_pi` counts *policy phases between auxiliary phases*, so the auxiliary phase fires every
`n_pi x (num_envs x n_steps)` frames. Upstream that is `32 x (4 MPI x 64 x 256) = 2.10M`. Ours is
`32 x (8 x 256) = 65,536`, and at the production-host target of 16 envs it becomes `131,072`.

| configuration | frames per auxiliary phase | auxiliary phases in a 600k run |
|---|---|---|
| upstream (4 MPI x 64 envs) | 2.10M | **0** |
| ours today (8 envs) | 65,536 | ~9 |
| production target (16 envs) | 131,072 | ~4 |

**Upstream at this budget would never reach its first auxiliary phase.** So "preserve `n_pi=32`" and
"preserve the auxiliary cadence" are incompatible, and there is no third option that is faithful to
both. The three coherent choices:

1. **Keep `n_pi=32`** and report that our PPG runs an auxiliary-phase-dominated regime upstream
   never experienced at this horizon.
2. **Rescale `n_pi`** to preserve the cadence in global frames — at which point the mechanism that
   distinguishes PPG from PPO barely runs, or does not run at all, inside 600k.
3. **Give PPG a different horizon**, abandoning the equal-frame-budget comparison for that row.

**My default: (1), declared.** It is what the tree already does, it keeps the frame budget uniform
across twelve baselines, and the alternative silently converts PPG into PPO for the length of the
study. But (1) means the row must be named **"a continuous-action port of PPG, retimed"** in every
table — which `CLAIMS-LEDGER` already says — and it means the PPG result cannot be read as evidence
about published PPG. None of the three is a canonical reproduction; the only unacceptable outcome is
choosing one without saying so.

The same argument applies, less sharply, to `idaac` (16x) and `ctrl` (4x), where rollout size sets
the update geometry but no single constant carries the whole mechanism.

### A20 (new) — intermediate evaluations are not scheduled, only made possible

**[SUPERSEDED 2026-09-05: they ARE scheduled now — `production_env()` enables both scopes
and the runner runs them with separate settings. See the RESTATED and REVISED sections
below; this heading records the state when the defect was found.]**

Checkpoint retention is solved for all seven families: the RL-ViGen five keep their intermediate
saves through patch P18, `ibac_sni` writes `model_<frames>.pt` beside the fixed `model.pt`
(`train.py:320`), and the rest write per-stamp files natively. Cadence is a uniform 50,000.

**But nothing evaluates them.** `run_curve_eval` is opt-in behind `CURVE_EVAL=1`
(`run_probe.sh:195`), and `CURVE_EVAL=1` appears only in alda probe configs — never in
`production-schedule.json`. So a production cell as scheduled today produces **one** evaluation, at
the endpoint, and eleven unevaluated checkpoints.

Nothing is lost that cannot be recovered — the weights are retained, so any stamp can be evaluated
later — but "we have a training curve" would not be true of the records, and the requirement that
intermediate evaluation be available is not met by retention alone.

The reason it is off by default is cost, and the cost is real: a full grid per stamp is
`12 stamps x 4 regimes x 10 scenes x 20 episodes = 9,600` episodes per cell against the endpoint's
800 — roughly **12x the evaluation budget of the entire campaign**.

**My default: schedule intermediate evaluation, but not at the endpoint's depth.** The endpoint is
the headline (A7) and the curve is descriptive, so the curve does not need the full grid:

- **endpoint**: 4 regimes x 10 scenes x 20 episodes, unchanged — this is the reported number;
- **intermediate stamps**: `train` and `eval-easy` only, scenes {0, 4, 9}, 10 episodes — enough to
  show whether learning happened and whether the generalisation gap moved, at about
  `12 x 2 x 3 x 10 = 720` episodes per cell, under **1x** the endpoint cost rather than 12x;
- **retain the weights regardless**, so a fuller curve remains recoverable without retraining.

This is a genuine fork and the alternative is defensible: evaluate nothing intermediate, keep the
weights, and decide later once the endpoint results say which cells are interesting. That is
cheaper and loses nothing permanent — **but it means the first look at any learning curve happens
after the campaign, which is exactly when a discovered problem is most expensive.**

### A20 REVISED, 2026-09-05 — I withdraw my own reduced-grid default

Raised by Codex (Q9): my A20 default (`train,eval-easy` x scenes {0,4,9} x 10 episodes) conflicts
with `retention-and-eval-depth.md`, which recommends the **full 4-regime x 10-scene grid at 5
episodes**, every 50k. **The newer recommendation is better and I am adopting it**, for a reason my
version missed entirely.

**Commensurability.** A trajectory measured on a *subset* of regimes and scenes is not the same
quantity as the endpoint measured on all of them. Under my default you could not say "the endpoint
is the final point of this curve" — they would be two different estimands sharing an axis, and the
one place a reader will most want to connect them is exactly where they could not be connected.
Keeping 4 x 10 and spending the saving on fewer episodes per stamp preserves that.

It is also better coverage per regime than mine: `10 scenes x 5 episodes = 50` episodes per regime
per stamp, against my `3 x 10 = 30`.

**What it costs, stated plainly**, because it is more than I proposed and the owner should see the
real number:

| product | per cell | fleet (36 cells) |
|---|---|---|
| endpoint, 4 x 10 x 20 | 800 | 28,800 |
| trajectory, 12 stamps x 4 x 10 x 5 | 2,400 | 86,400 |
| **total** | **3,200** | **115,200 episodes** |

So the curve is **3x the endpoint**, not the ~1x my version claimed. That is the honest price of a
curve you can actually put the endpoint on.

**If that is too much, reduce EPISODES, never the grid.** Dropping to 3 episodes per stamp costs
51,840 fleet episodes and keeps the curve commensurable; dropping regimes or scenes saves less and
breaks the property the curve exists for. **Retention of the weights is the real insurance either
way** — a stamp evaluated shallowly can always be re-evaluated deeply later, and one never evaluated
can too, so the only irreversible choice here is discarding checkpoints.

Codex holds the operational default in `families.json` / `family.py`; this sheet now agrees with it.

### A20 RESTATED, 2026-09-05 — "whether" was never the decision; depth is

**The framing was wrong and the owner was right to push on it.** There is no real option not to
evaluate intermediate checkpoints: the project retains them at 50k precisely so a curve exists, a
learning curve is table stakes for reporting an RL result, and `retention-and-eval-depth.md` already
assumes one. What I actually found was that the curve **was never scheduled** — `CURVE_EVAL=1`
appears in no production config. That is a **defect**, now fixed, not a choice to put to anyone.

**What genuinely remains open is depth, and only one term of it is free:**

| parameter | value | how free is it? |
|---|---|---|
| frequency | every 50,000 frames (12 stamps) | **not free** — `train.py:309` gates the RL-ViGen five on `global_step % int(5e4)`, hardcoded. The others were aligned to it so stamps are comparable |
| regimes x scenes | 4 x 10, same as the endpoint | **not free** — a curve on a subset is a different estimand from the endpoint, so it could not be plotted with it |
| episode length | 500 steps | **not free** — the protocol horizon |
| seeds | 3, giving 3 curves | **not free** — A6 |
| **episodes per (regime, scene) per stamp** | **5** | **the only free parameter** |

So A20 is one number: **episodes per stamp**, a variance-versus-cost trade. At 5 it is 2,400
episodes per cell; the fleet cost depends on env construction, which is **not yet measured** —
288 GPU-h if construction is free, 384 GPU-h at 40 s per construction, because the trajectory grid
is construction-heavy (480 constructions per cell against the endpoint's 40).

**Measure that first.** One job at 4 regimes x 10 scenes x **1** episode is construction-dominated
and, against the existing 2x1x5 point, solves both terms. Setting the depth before that number
exists is guessing.

### A14 — a concrete target value, replacing the profile's 1,000,000

**[APPLIED 2026-09-05: Codex set the v100 profile to 620,000. The table below compares
the options as they stood when the recommendation was made; see the STATUS section
further down for the current default.]**

The mechanism is Codex's host-profile selector and it is the right one. On the **replay value**
specifically, 1,000,000 is more than needed and the excess is expensive:

    action_repeat=1 (rlvigen.sh:78), so 600,000 frames = 600,000 agent steps
    stored = 600,000 + 1,200 episode-initial time steps = 601,200 transitions

| cap | GiB/cell | RL-ViGen cells in 113 GiB | evicts? |
|---|---|---|---|
| 300,000 (current) | 21.0 | **5** | yes, ~50% |
| **620,000 (proposed)** | **40.0** | **2** | **no** |
| 1,000,000 (was the profile; now the retained option) | 62.4 | **1** | no |

**620,000 is fully faithful — the buffer never evicts — at two-thirds the memory of 1M, and it
doubles host packing.** 1M buys nothing at a 600k budget and only starts to matter if the frame
budget later exceeds ~1M.

Note what A14 does **not** close even at v100: `idaac` reaches 16 processes against a source 64, and
`ppg` 16 envs against a source 256. Only `ibac_sni` (16 procs, source 16) becomes source-faithful.

### A14 — STATUS: 620,000 is the operational default, awaiting your ratification

Codex applied it to the explicit `v100` profile on 2026-09-05 (the DataSphere-safe 300k base is
untouched, so probes are unaffected). This is no longer a proposal; it is **what a v100-profile run
will do unless you say otherwise.**

**Why 620,000.** Door has no early termination and `action_repeat=1`, so 600,000 training frames
produce at most 600,000 transitions plus ~1,200 reset entries. 620,000 is therefore **non-evicting
with headroom** — fully faithful — while keeping **two-cell packing** on the measured 113 GiB host.

| cap | GiB/cell | RL-ViGen cells in 113 GiB | evicts? |
|---|---|---|---|
| 300,000 (DataSphere base, unchanged) | 21.0 | 5 | yes, ~50% |
| **620,000 (v100 default)** | **40.0** | **2** | **no** |
| 1,000,000 (the option below) | 62.4 | 1 | no |

**The option you retain:** keep 1,000,000 if you want headroom for a **future larger frame budget**.
It is behaviourally identical to 620,000 at 600k frames and only begins to matter above ~620k
frames; the cost is halving RL-ViGen host packing, one cell instead of two. That is the whole trade
— there is no fidelity difference at this budget, only future-proofing against a budget change
nobody has proposed.

**What A14 still does not close**, at either value: `idaac` reaches 16 processes against a source
64, `ppg` 16 envs against a source 256. Only `ibac_sni` (16 procs, source 16) becomes
source-faithful. `CLAIMS-LEDGER` keeps those two qualifications.

### A10 REFINED, 2026-09-05 — canary `idaac` then `drqv2`, not `soda` first

A10 picks `soda` because it is the longest cell (~54 h with its endpoint grid) and therefore "proves
the envelope for everything else". **The envelope has two parts and soda is the expensive way to
prove either of them.**

| candidate | train + endpoint | cell RAM | what it proves |
|---|---|---|---|
| **`idaac`** | **7.5 h** | 2.9 GiB | the **pipeline at production length** |
| **`drqv2`** | **9.1 h** | **21.0 GiB** | the **RAM envelope**, at the same scale as soda's 20.4 |
| `soda` | **54.0 h** | 20.4 GiB | the same RAM envelope, plus a 51-hour wall-clock |

**Proposed order:**

1. **`idaac` at 600k (~7.5 h).** It is the cheapest cell and the one family already validated
   end-to-end on the current evaluator, so **any failure here is duration-related rather than
   family-related** — which is exactly what a canary is for. The duration-dependent risks are real
   and none has ever been exercised: twelve checkpoints accumulating on disk, the replay buffer
   reaching its cap for the first time, reloading a genuine 600k checkpoint, and the endpoint grid
   running on a real endpoint rather than a 100k one.
2. **`drqv2` at 600k (~9.1 h).** Same RAM class as soda at a sixth of the cost, and — as A10 itself
   argues for soda — **if it passes it is not overhead, it is seed 1 of drqv2.**

**Finding a pipeline defect after 7.5 hours instead of 54 is the whole argument.** Last night's four
stacked defects each surfaced only when something ran, and each was found in a ~10-minute job; the
same logic scales.

**What this leaves unproven, deliberately:** soda's 51-hour wall-clock. That is a *timeout* question,
not a pipeline question, and it is better answered by the per-cell timeout the runner already
applies than by spending 54 hours to discover it. If the owner wants it proven, run soda as its own
seed 1 **after** the two above pass — at which point it is production, not a canary.

**CAVEATED 2026-09-05, from `review-11-12-gemini-triage.md` T15**: recommending `idaac` first is
**internally contradictory while T1 is live** — reviews 11/12 independently traced a real defect in
IDAAC's rollout-storage episode identity (`_LevelSeed.step()` attaches the pre-reset episode id to
terminal `info`; `DummyVecEnv` replaces the terminal observation with the auto-reset one; `train.py`
reads the stale id; `IDAACRolloutStorage.insert()` advances `self.step` before writing
`levels[self.step + 1]`). Canarying a family with a known-live storage-identity bug tests the
defect, not the pipeline. **Order now: `drqv2` first, `idaac` only after T1 is repaired and
verified with a real VecEnv→trainer→storage integration test** (not the current wrapper-only test,
which does not establish the storage invariant). Handed to Codex, mailbox Q18(a) — it independently
traced the exact call chain and has the deeper context; not something I am also working on.

### A21 (new) — scene comparisons are UNPAIRED; the regime contrast is not affected

Raised by an external reviewer. `placement_condition_seed` is
`SeedSequence([eval_seed, scene_id, episode_index])`, so **scene_id is inside the seed** and scene 0
episode 3 runs a different physical placement from scene 1 episode 3. Any per-scene comparison
therefore mixes the scene change with a different placement draw.

**What is NOT affected, verified empirically rather than argued.** The seed does not contain the
regime, so the same scene under different regimes gets identical placements. From
`bt1baht74a35e6uq582c`'s records:

    train     / scene 0   [246415859, 1095573727, 3771752622, 172242467, 1682051426]
    eval-easy / scene 0   [246415859, 1095573727, 3771752622, 172242467, 1682051426]   identical

**So the project's primary contrast — within-method, across-regime retention — is properly paired
and unharmed.** This is the contrast `CLAIMS-LEDGER` calls "the identified clean contrast", and it
survives intact.

**What IS affected:** per-scene heterogeneity claims. `proposal-inference-and-checkpoint-selection.md:33`
reports "visual-generalisation heterogeneity across scenes" and
`owner-decisions-recommended.md:84` speaks of the within-scene effect aggregated. Those quantities
currently carry scene **and** placement variation together.

**The fork, and it is a genuine trade rather than a bug:**

1. **Keep `scene_id` in the seed (current).** Each scene draws independent placements, so a regime's
   20 episodes x 10 scenes sample **200 distinct placements** — better coverage of the placement
   distribution, which is what the aggregated headline estimand actually wants. Cost: scene
   comparisons are unpaired and must be reported as scene+placement.
2. **Drop `scene_id` from the seed.** All scenes share one placement sequence, so scene contrasts
   are paired and scene is isolated. Cost: only **20 distinct placements** per regime instead of
   200, which raises the variance of the aggregate the headline depends on.
3. **Both**: keep the current 20 for coverage and add a small paired block (say 5 episodes with
   scene_id dropped) purely for the scene contrast. Costs 25% more evaluation.

**My default: (1) plus an explicit caveat**, because the headline estimand aggregates over scenes
and benefits from the wider placement coverage, while the scene-heterogeneity claim is secondary and
descriptive. **But it must then be stated that way** — "scene 9 scored lowest" currently means
"scene 9 with its own placements scored lowest", and no document says so.

If per-scene heterogeneity is meant to be a *finding* rather than a description, take (3).

### A14 CORRECTION, 2026-09-05 — `ibac_sni procs=16` was NOT achievable as the code stood

Raised by external review 9, verified, and it **contradicts what I wrote in the A14 status above.**
I said "only `ibac_sni` becomes source-faithful (16 procs, source 16)". It is in fact **the one
target that cannot be applied at all.**

The descriptor already records the measurement, from job `bt1q6jd096m3re2n7jp2`:

> procs is 1, and that is now MEASURED rather than assumed. With 2 it dies at `torch_rl.PPOAlgo`'s
> parallel env setup with **EOFError** -- a worker process that never came up. MuJoCo GL contexts do
> not survive a fork ... the same is true on Linux with EGL. **An environment constraint rather than
> a choice.**

And `torch_rl/scripts/train.py:110` does not merely inherit the platform default — it **forces**
it: `multiprocessing.set_start_method("fork")`. `utils/penv.py` then spawns workers with bare
`Process(...)`. So a fork it is, and EGL contexts do not survive one.

**Consequences, and the first is operational:**

1. **The v100 profile's `ibac_sni: procs 16` would fail at startup**, not degrade. If A14 is
   ratified as written, that cell dies in its parallel-env setup.
2. **A1's pilot "at the exact final config" cannot be run at `procs=16`** — so the sequencing I
   endorsed (apply A14, then pilot) is impossible for this family until the fork issue is resolved.
3. **`ibac_sni` keeps its rollout deviation** — 1 x 128 = 128 against the repository's 16 x 128 =
   2,048 — and `CLAIMS-LEDGER` must keep saying so.

**The candidate fix, and why it is a decision rather than a patch:** change the forced start method
to `spawn`. `CONSTRUCTION.md:2501` records that other families' workers survive precisely because
they are "`multiprocessing.spawn`, not `fork`". But spawn **re-imports and re-pickles**: `penv.py`
passes live env objects into `Process(target=worker, args=(remote, env))`, and those must then be
picklable, which a MuJoCo env may well not be. So this is a real port with a real chance of failing
for a second reason — **worth one bounded experiment, not a one-line change.**

**Historical disposition of this correction:** the experiment was still pending when this section
was written. The following update supersedes its "cannot run" conclusion; it is kept because it
records the original failure and why the spawn/factory repair was necessary.

### A14 — a second fork-dependent problem, and why one fix addresses both

External review 10 (#6) found a defect that only bites at `procs>1`, so it is dormant today and
would arrive with the v100 profile:

**Forked workers inherit the parent's NumPy RNG state.** Door's placement sampler uses the
process-global `np.random.uniform` (C69), not a per-wrapper `RandomState`, and `ParallelEnv` forks
workers from a parent that has already been globally seeded. On Linux `fork`, children inherit that
state — so **several workers can begin with identical physical-placement streams even though their
constructor seed integers differ.** At 16 workers that collapses much of the physical diversity the
parallelism is supposed to buy. Distinct seed arguments are not proof, because they do not govern
the RNG that actually chooses the door position.

**The useful observation is that this and the startup blocker share a root.** Switching
`train.py:110` from `set_start_method("fork")` to `"spawn"` would address both:

- **the EGL failure**, because a spawned child builds its own GL context rather than inheriting a
  dead one — which is why `CONSTRUCTION.md:2501` records other families' workers surviving;
- **the RNG collapse**, because a spawned child re-imports and re-seeds rather than inheriting the
  parent's stream.

So the one bounded experiment already proposed for A14 answers both questions. **It is still not a
one-line change** — `penv.py` passes live env objects into `Process(...)`, which spawn must pickle,
and a MuJoCo env may not be picklable.

**And the verification must be physical, not nominal**: run a real multi-worker integration test and
compare the *realized* `initial_placement` across workers. `scripts/audit_pairing_evidence.py`
already does that comparison shape for regimes and is the natural place to extend.

### A14 UPDATE, 2026-09-05 — the 16-process experiment succeeds on the high-memory tier

`bt1djai23kme336auat4` ran the repaired Door path with `procs=16` on `gt4i.1`: all workers were
constructed under `spawn`, the cell reached `NATIVE_FINAL_EVALUATION_COMPLETED frame=4096`, emitted
records, and exited 0. Resource sampling observed 20 processes and 19.25 GiB maximum summed HWM
against 27 GiB usable RAM. The machine-readable evidence is
`results/validation/ibac_sni-procs16-v125.json`; `production_gates.py` now consumes it.

This closes the specific fork/pickling/worker-memory runnability concern. It does **not** establish
the production V100 renderer, V100 throughput, a 600k learning result, or competence. The V100
profile therefore remains `procs=16` (not 1), DataSphere `gt4.1` rejects that profile before
submission, and `gt4i.1` is a functional-smoke tier rather than the production target.

---

## A22 — Places365 overlay augmentation is drawn from the VALIDATION split

**Raised**: external review 2 (item 2-14), re-raised by reviews 9 and 10, and confirmed live
2026-09-05: `datasphere/native/configure_places365_val.py:34-35` rewrites the upstream
`_load_places(..., use_val=False)` to `use_val=True`.

**Why it matters**: svea, sgqn and soda are overlay-augmentation methods. The augmentation
distribution *is* their mechanism, not a detail of their input pipeline. Training against the
validation split instead of the train split changes the images those three methods learn to be
invariant to, and it is a **learning-affecting** deviation rather than a platform one.

**Status before today: tracked by nothing.** Not in this sheet, not in `REGISTER.md` with a
C-number, not in `open_decisions.py`, not a gate. The project's first triage confirmed it as real
and it then fell off every surface — which is worse than an open decision, because an open decision
is at least counted. This row exists so it is counted.

**Default I will act on**: keep `use_val=True`, and declare it as a recorded deviation for the three
affected baselines in `CLAIMS-LEDGER.md`. Reason: the split is a fixed, documented, reproducible
image set; all three affected baselines use the SAME split, so the cross-baseline comparison — the
actual estimand — is unaffected; and the alternative costs a fresh multi-gigabyte download plus a
re-run of every augmentation-dependent cell. What it forecloses is comparability against *published*
SODA/SVEA numbers, which `CLAIMS-LEDGER` already forbids on other grounds.

**Override if**: you want any claim of parity with published overlay-augmentation results, in which
case the train split must be used and those cells re-run.

### A20 DECIDED, 2026-09-05 — 3 episodes per stamp

**The blocking condition is gone.** A20 said "measure env construction first; setting the depth
before that number exists is guessing." It has been measured: **0.6 s**, i.e. 3.4 GPU-h across all
20,160 constructions in the campaign (`PRODUCTION-CALENDAR.md:14`). Construction is free, so the
two-term uncertainty collapses and the trajectory cost is strictly linear in the one free parameter:

    per cell   = 12 stamps x 4 regimes x 10 scenes x E episodes x 12 s
    fleet (36 cells = 12 baselines x 3 seeds):

    | E | GPU-h | share of the 601 h training budget | episodes per (stamp, regime) |
    |---|-------|------------------------------------|------------------------------|
    | 1 |    58 |  10% |  10 |
    | 2 |   115 |  19% |  20 |
    | **3** | **173** (+3.4 construction = **176** total, as PRODUCTION-CALENDAR states it) | **29%** | **30** |
    | 5 |   288 |  48% |  50 |

**Decision: E = 3.** Reasoning, and it turns on what the curve is *for*:

- The curve's job is the **shape** of learning and a sanity check on checkpoint selection. It carries
  no inferential claim — the headline estimand is the endpoint grid, which stays at 20 episodes per
  (regime, scene). Spending 48% of the training budget on a supporting figure is the wrong trade.
- Scenes aggregate within a stamp, so E=3 gives **30 episodes per (stamp, regime)** — comfortably
  enough to see a trend through the measured noise floor (0.77% on `train`), which is what a curve
  must resolve.
- E=5 costs 115 GPU-h more, ~5 extra days of packed wall-clock, to move each point from 30 to 50
  episodes. That buys precision the curve does not need and the endpoint already provides.

**Reversible, and cheaply**: this is a runner knob (`CURVE_EVAL_EPISODES`), not a code member, so it
does not touch the frozen evaluator revision and can be raised per-cell if a curve comes back too
noisy to read. It is set at 3 rather than left unset because an unset knob is how `CURVE_EVAL=1`
came to appear in no production config at all.

### A23 STILL OPEN, 2026-09-05 (twice revised) — δ, the competence-threshold offset

`proposal-inference-and-checkpoint-selection.md` §1.5 says "δ fixed now" and never states a number.

**First version** (δ = 0.5, "half an SD, round and pre-registerable"): a plausible number standing
in for analysis. **Second version** (δ = 2×SE ≈ 0.40, from the floor's measured SD 2.839 over the
200-episode endpoint depth): the SE mechanism was sound — confirmed by reading the actual frozen
loop, `scripts/eval_grid.py:944-947` (`for regime in regimes: for scene in scenes:`, unconditional,
so train genuinely gets 10 scenes × 20 episodes = 200) — **but the input fed into it was wrong, and
unchecked.** 2.839 is the *random* policy's episode-to-episode SD (C55). The competence gate is
about a *trained, near-floor* policy, and nothing established those two variances are similar.

**Checked, not assumed, this time**: pulled real episode returns from three of tonight's own
10k-frame (very undertrained, near-floor) validation runs, train regime:

    ctrl      n=5  SD 4.025
    ibac_sni  n=5  SD 4.505
    idaac     n=5  SD 9.099

All three exceed 2.839 by 1.5-3x. n=5 is too small to trust any single one of these numbers, but the
direction is a real finding: a partially-trained policy's variance is not the random floor's
variance, and using the latter understated δ by roughly half. Redoing the same SE arithmetic against
this range (SD 5-7 as a rough central estimate, 2xSE) gives **δ in 0.7-1.0**, not 0.40.

**Left genuinely open, not merely reopened for form's sake**: n=5 samples cannot responsibly produce
a new precise number — replacing 0.40 with another single confident-looking figure would repeat the
exact mistake just found. What would actually resolve this: a real measurement of episode-to-episode
variance from a policy deliberately held near the floor (e.g. an entropy-killed control, or the same
one already used for A1's IBAC pilot) at an episode count large enough to trust, run before the
fleet. **Until that exists, treat δ as bounded in roughly [0.4, 1.0] rather than settled at a point**,
and prefer the higher end if a single operating value is needed now — a stricter competence bar that
wrongly excludes a modest performer is a smaller cost than a lenient one that certifies noise.

### A24 DECIDED, 2026-09-05 — the missing-run policy

§1.7 names the questions and does not answer them. **Corrected from "proposal" to "decided"**: unlike
A23/A25, each answer here follows from a stated principle I'd defend the same way on a different day,
not from picking a plausible-sounding number. Persisted as the operating default per the standing
instruction that a genuinely-best-judgment call gets implemented, not left as a bare unratified line:

- A crashed seed is **rerun under the identical seed integer** (preserves the n=3 design rather than
  introducing an unplanned fourth seed) — principle: don't let a crash silently change the design.
- Replacement seeds chosen after seeing results are **forbidden** — principle: don't let seen
  results choose the sampling.
- A scene missing for one seed is **dropped from that seed's aggregate**, not imputed, and the row
  is flagged — principle: report absence as absence, never repair it into a number.
- A method missing an entire seed **stays in the table at n=2, explicitly labelled** — never
  silently promoted to read as n=3 — same principle as above, applied at the method level.

Reversible at zero cost (it constrains reporting/analysis conduct, not code or a running fleet) if
the owner prefers different answers to any of the four.

### A25 DECIDED, 2026-09-05 (revised) — the primary comparison set

66 pairwise comparisons exist across twelve baselines; §1.7 asks either to name the primary set in
advance or publish the full matrix. **The first version of this row grouped by evaluator FAMILY
(`rlvigen`/`dmc_gb`/`idaac`/...) — which is which repository the code came from, not what
scientific question a comparison inside that group would answer.** That conflation is why it was
honestly flagged as weak. Redone by algorithmic mechanism instead:

- **On-policy PPO, differing in what regularizes it**: `idaac` (adversarial dynamics
  discriminator), `ibac_sni` (VIB bottleneck + SNI), `ppg` (auxiliary-phase distillation), `ctrl`
  (clustering + temporal contrastive) — 4 methods, 6 pairs.
- **Off-policy SAC, differing in augmentation**: `drqv2`, `svea`, `sgqn`, `drq`, `rad`, `soda` — 6
  methods, 15 pairs, all sharing a SAC backbone with augmentation as the varying axis.
- **Off-policy SAC, differing in representation learning**: `curl` (contrastive), `alda`
  (autoencoder + latent dynamics model, confirmed from its own optimizer set —
  `alda_trainer.py:105-109`: actor/critic/**ae**/**latent**/log_alpha) — 2 methods, 1 pair.
- **Cross-group, best-in-group**: the winner of each of the three groups above against the other
  two — this is the comparison that actually answers the project's central question (does an
  on-policy regularizer, an augmentation choice, or a representation-learning approach generalize
  better), which "family" never could, since `rlvigen` alone bundles augmentation AND contrastive
  methods under one repository.

**25 named primary comparisons** (6+15+1+3), down from 66; full matrix published as supplementary.
The remaining open choice is genuinely a value judgment, not unfinished analysis: whether to group
by mechanism (as here) is itself an assumption about what makes methods "comparable," and a
differently-motivated axis (e.g. frame-stack presence, or estimator type) could be argued instead.

**Stated explicitly, because the user asked whether this row's framing quietly pulls toward
aggregated reporting at the expense of raw retention — a fair question, and the answer needed
writing down rather than assumed:** this row governs presentation emphasis ONLY. It changes which
comparisons a human reader sees called out first; it changes nothing about what is collected or
kept. Verified against real records tonight, repeatedly, not asserted from memory: every retained
row already carries full per-episode arrays (`returns`, `episode_success`, `episode_diagnostics`,
`placement_condition_seeds`, per-episode `eval_episode_ids`) under `native`, never a pre-reduced
mean. That is the property the owner's own instruction demands
(`retention-and-eval-depth.md`: *"report richly so any aggregation or hypothesis check can be
post-hoc"*), and it is orthogonal to A25: all 66 pairwise comparisons, and any other regrouping by
any other axis, remain fully computable from that same raw data with **no GPU and no rerun**,
regardless of which 25 get called "primary" for a table someone reads first. Naming primary
comparisons is a curation choice about what to emphasize when writing something up; it is not, and
must never become, a decision about what to measure or retain.

Persisted as the operating default per the same standing rule as A23/A24.

---

**Standing gap this session found in its own practice, 2026-09-05**: both this row and A23–A25
above were stated in a chat response and NOT written here until the user asked whether an
exhaustive "flag up" surface exists. It does — this file, plus `CORRECTIONS.md` for what's already
fixed, plus a production_gates.py entry for anything mechanically checkable (see "ctrl v100 profile
restored") — but only if a finding actually gets routed into it. Going forward: nothing substantive
stays in a chat response only; it goes into a file in the same turn it's said.

**A second pass caught that "awaiting ratification" was itself applied uniformly across A23–A25
when the three don't share an epistemic status.** A24 was upgraded first. A23 and A25 were then
**redone rather than left as weak proposals** — the user's own correction: parking a question as
"your decision" is only right when the second-layer answer has genuinely been worked to its best,
not whenever more rigor was possible but skipped. The comparison set (A25) now groups by algorithmic
mechanism, confirmed against each baseline's actual optimizer set, rather than by which repository
the code happened to come from — that redo held up and is DECIDED.

**A23 did not hold up on a third look, and stayed open for the right reason this time.** The
SE-based *method* was sound, but a THIRD pass — prompted by the user asking "are you sure, was this
hasty" — found the *input* fed into it (the random-policy floor's SD) was never checked against the
thing it was standing in for (a trained, near-floor policy's SD), and a direct check against tonight's
own data showed those two variances differ by 1.5-3x. That is now recorded above as genuinely open,
bounded rather than pointed, with what would actually resolve it stated. **The lesson this adds,
on top of the first one**: redoing a rushed answer once does not guarantee the redo itself was not
also rushed — each pass needs its own check, and "I did more work than last time" is not the same
claim as "this is now right."

### A26 OPEN, 2026-09-05 — PPG's auxiliary cadence versus its wall-clock

**Acted on already** (the "at our best" layer): the V100 profile's `num_envs: 16` override is
reverted to the base `8`, restoring `8 x 256 x n_pi=32 = 65,536` interactions per auxiliary phase —
exactly the cadence of the only published continuous-control PPG design point (IDAAC's
continuous-control appendix). Full derivation and the four reference configurations: CORRECTIONS #58.

**Why this is the default I set rather than a question I held open.** Two of the standing
preferences in this workspace point the same way: fidelity wins over speed in a baseline rebuild,
and an unreasoned override is not a decision. The 16-env value carried no recorded reason, and the
base it overrode was already correct against the applicable reference.

**What is genuinely yours to rule on: the throughput cost.** Eight parallel envs collect rollouts
more slowly than sixteen, so PPG's wall-clock per cell rises — by how much is not measured, because
V100 throughput has not been measured at all yet (that is migration-order step 1). Three ways to go:

1. **Keep 8** (acted on). Faithful to the published continuous-control cadence; PPG costs more
   wall-clock. Recommended.
2. **Keep 8, and drop PPG's budget** so its wall-clock matches the others. Rejected unless you ask:
   it would put PPG on a different x-axis from the other eleven, which is the axis this whole
   protocol exists to hold common.
3. **Return to 16 and declare it.** Defensible *if written down* — 131,072 is still between the two
   published references, not outside them. But it is a worse position than (1) for no scientific
   gain, and it re-opens exactly the attack surface review 11 §7 identified.

**What would change my recommendation:** a measured V100 throughput number showing PPG at 8 envs
cannot finish inside the fleet's time envelope. That measurement does not exist yet, so (1) stands.

**Not affected:** `n_pi=32` stays at PPG's own default under every option above. Halving it would
also restore the cadence arithmetically, and is the one move I would argue against in all cases —
it changes PPG's defining constant to compensate for a host setting.

### A27 OPEN, 2026-09-05 — the off-policy update-to-data ratio, and `alda` in particular

**The measurement** (full derivation and evidence: [`FINDING-update-to-data-ratio.md`](FINDING-update-to-data-ratio.md)):
the first version of this finding used the wrong denominator. An action-repeat transition is one
replay item even when it represents several simulator substeps. The five RL-ViGen baselines run at
**0.5 learner updates per newly collected replay transition** because `update_every_steps=2`;
`rad`, `soda` and `alda` run at approximately **1.0**. RAD/SODA/ALDA still differ in simulator
substeps per transition (source 4 versus Door 1), which is a separate declared design-point axis.

**Two separable questions, and I am not treating them alike.**

**(a) The cross-family confound — declare it.** At 600k frames the five take ~300k gradient updates
and `rad`/`soda`/`alda` take ~600k. That is what "faithful to each source at a common frame budget"
costs, and it is defensible — but it is undeclared today, and a reader ranking these twelve cannot
currently see that one group got twice the optimisation. My default: **declare it as a seventeenth
comparability axis and carry it in the report's caveats**, rather than equalise it (equalising would
make every family unfaithful to its own source, which is worse).

**(b) `alda` specifically — this remains a stability experiment, not a source-ratio correction.**
`docs/FAITHFULNESS.md:603-616` records that this project already found `utd=1.0` *diverged* (3 Lift
runs, 2 seeds, `critic/loss > 1e8` by ~141k frames) and fixed it to `0.25`, pinned by two red-green
tests. **Both tests import `rlgen` — the retired port. Production launches `runnable/alda`, which
has no `utd` field at all and hardcodes one update per environment step.** The fix never reached the
code that runs. Review 14 corrected the denominator: a source action-repeat-4 transition is one
replay item, so `.25` is not implied by replay fidelity.

**Operational default while this remains open: keep `runnable/alda` at one update per newly collected
Door transition, and run a target-specific 1.0-versus-0.25 stability/competence probe before the
fleet.** If Door requires 0.25, record it as a target-specific adaptation, not as restoration of
the source replay ratio.

**Why I did not just apply it**, unlike today's PPG cadence fix: there, a correct base config had
been broken by an unreasoned override and reverting restored a published design point. Here there is
no correct base to restore, the change edits a training loop rather than a profile, and it materially
changes `alda` (and possibly `rad`/`soda`) results. That makes it method-defining, and this project's
own triage says method-defining values close only after being researched, implemented, **and still
surfaced for ratification**. This is the surfacing.

**What would change the default:** a predeclared Door 1.0-versus-0.25 probe showing a clear
stability or competence advantage at matched transitions. The old Lift/retired-port result is a
strong stability prior, not a Door fidelity proof.

**The counter-reading, fairly stated:** the previous note treated simulator frames as replay samples
and called 1.0 a 4x source replay ratio; that was wrong. The remaining argument for testing 0.25 is
empirical stability on a different task/port, not source fidelity. Report learner updates per new
replay transition and simulator substeps per transition separately.

### A28 OPEN, 2026-09-05 — three seeds, and what the fleet can therefore claim

**The measurement** (working: [`FINDING-resolving-power-at-n3.md`](FINDING-resolving-power-at-n3.md)):
the production plan is n = 3 (`production-schedule-v100.json`, `seeds: [101, 102, 103]`), and three
seeds resolve relative differences of **~53%**, not the ~31% the project's own carried sentence
states — that sentence was written for a five-seed plan, and the table behind it used the normal
approximation in the one regime where it fails. Corrected in CONSTRUCTION.md and in
`plan_seed_budget.py`.

**This is not a request to buy more seeds.** 3 -> 5 moves 52.7% -> 35.1% for +67% compute, and 35%
is still above most differences anyone would want to report. The honest options:

1. **Keep n = 3 and bound the claims** (recommended). The fleet then answers "does this method
   generalize, and roughly how much" well, and "does A beat B" only for large gaps. Costs nothing;
   requires the report to say so.
2. **n = 5.** A real improvement and it is what the reference specifies, but it does not reach the
   effect sizes that separate close methods, and it is +67% compute on the largest budget line.
3. **Fewer baselines, more seeds, same compute.** 12x3 = 36 cells; 7x5 = 35. This is the only option
   that actually buys resolving power without buying compute — at the cost of scope. I do not
   recommend it unprompted (the twelve-baseline breadth is the project's stated contribution), but
   it is the option that trades the right currency and it should be refused deliberately rather than
   never considered.

**What would change the analysis, and is cheap:** every number rests on ONE same-seed pair (C41).
`docs/ASSURANCE.md:57` already lists between-seed variance as a known gap with a first measurement
launched 2026-08-29. Finishing that measurement improves the estimate more than any arithmetic —
CONSTRUCTION.md says so itself.

**Interacts with A23** (the competence threshold δ) and with the 66-pairwise-comparison warning in
`proposal-inference-and-checkpoint-selection.md:98`. All three are the same underlying issue: what
a three-seed design is permitted to say.

### A29 OPEN, 2026-09-05 — idaac's and ppg's regular-phase update density versus Procgen

**The measurement** (full derivation: [`FINDING-on-policy-update-density.md`](FINDING-on-policy-update-density.md)):
extending A27's question to the four on-policy families. `ibac_sni` and `ctrl`, once on their V100
profiles restoring full upstream parallelism (16 and 64 envs, both upstream's own defaults), match
their source's regular-phase gradient-steps-per-frame **exactly**. `idaac` (16 vs upstream 64 envs)
and `ppg` (8 vs upstream 64/4x64) do not — both take the same `epochs x minibatches` per rollout as
upstream while collecting a smaller rollout, so their density runs **4x** (idaac) and **8x-32x**
(ppg) above source. This is a different axis from PPG's auxiliary-phase cadence (A26, already
corrected) — it is the ordinary PPO update, not the auxiliary phase.

**Why this is forced, not chosen.** A single V100 cannot run Procgen's ~64 parallel envs' worth of
*robosuite/MuJoCo* simulation the way Procgen's cheap procedurally-generated 2D levels allow — the
same shape of constraint that already forces some retiming of PPG's auxiliary phase at a 600k
budget. Some deviation here is unavoidable; the question is only whether it is declared.

**My default: declare it, do not compensate.** Recommending against raising `num_mini_batch` or
lowering `ppo_epoch`/`n_epoch_pi` to force a 1x match — that invents an untested hyperparameter
combination, the same reasoning already applied when this project declined to equalise the
off-policy replay ratio. Declared now as a comparability-seam axis
(`updates_per_env_frame`) and should be carried into the report alongside idaac's and ppg's
already-declared Procgen-vs-continuous-control geometry limitation (review 11 §7/§8, T16/T17).

**What would change this:** if idaac or ppg is shown to diverge or over-fit at production scale in
a way plausibly attributable to update density (watch `clip_fraction`/`approx_kl_k3`, both wired
for idaac since 2026-08-19), that would argue for the T16/T17 continuous-control design points
instead — which independently also use different rollout geometry — rather than for hand-tuning
epochs/minibatches in isolation.

### A30 OPEN, 2026-09-05 — three families' PPO objectives use the pre-clip action, not just CTRL's

**Traced, not just flagged** (reviews 11/12/14 and Codex's audit all named this as a CTRL-specific
"focused port question" without tracing the actual code path; done now, and it turns out broader
than any of them said). `runnable/ctrl/algo.py` samples an action from
`tfd.MultivariateNormalDiag(loc=logits, scale_diag=jnp.exp(self.log_std))` — an **unbounded**
Gaussian, no tanh-squash — passes that RAW sample to `env.step(action)` (`algo.py:78`), and
separately stores it for the PPO update, which computes `pi.log_prob(action[:, 0])`
(`algo.py:297`) against that SAME raw, stored action. But
`RL-ViGen-upstream/third_party/robosuite/robosuite/controllers/base_controller.py:120` clips the
action to `[input_min, input_max]` before it is actually applied to the simulator — **the action
whose log-probability enters the PPO ratio is not the action the environment executed whenever the
sample falls outside the controller's bounds.**

**Checked whether this is CTRL-specific, since three independent reviews only named CTRL. It is
not.** `idaac`'s `DiagGaussian`/`FixedNormal` (`ppo_daac_idaac/distributions.py:81-100`) is the
identical shape — unbounded mean/logstd, no squash, no clamp, action sampled via `actor_critic.act`
and stored raw for its own PPO update. `ibac_sni`'s head (`torch_rl/model.py:281`,
`Independent(Normal(x, self.log_std.exp()), 1)`) is the same again. All three build their Door
environment through the same `RL-ViGen-upstream/wrappers/robo_wrapper.py` -> robosuite controller
chain, so all three are clipped the same way before execution. **This is a shared consequence of
authoring a continuous Gaussian head onto Procgen-lineage algorithms that never had one, not a
CTRL port defect** — Procgen's own categorical action space has no analogous clipping seam at all.

**Why this is not merely theoretical**: `log_std`/`logstd` in all three has **no clamp anywhere in
any of the three files**. This is the identical unconstrained mechanism this project already found
pathological for `ibac_sni` alone (entropy climbing 9.95→20.03,
`PRODUCTION-RUNBOOK.md`'s "finite but useless policy" row) — an unbounded Gaussian whose σ can grow
samples further outside the action box as training proceeds, which is exactly when the
raw-vs-clipped divergence would be largest and least visible (a finite checkpoint, a plausible loss
curve, and a policy whose PPO gradient is computed against actions it never took) for whichever of
the three that happens to.

**What I am NOT doing**: correcting this by tanh-squashing the policy or computing the
log-probability of the clipped action (via a truncated-normal or change-of-variables correction).
Either is a real algorithmic change to CTRL's action-space handling — a method-defining choice
review 14 §9 also declined to prescribe ("if distinct, run a small sensitivity/diagnostic
comparison" — not "fix it"). Preserving the official port's behavior is also independently
defensible: it is what the released JAX code does.

**Recommended default: leave all three ports as-is, but watch `log_std`/`logstd` for CTRL and
IDAAC with the same vigilance already specified for `ibac_sni`**, and add the same per-step
action-coordinate clip-rate diagnostic the five RL-ViGen natives already have (`PRODUCTION-
RUNBOOK.md`) to all three continuous-Gaussian ports — none has it today, and it is the one number
that would show whether this is a 2% correction or a dominant one, for each of the three
independently (their action dimensionality and log_std initialization differ). Added to the
runbook for all three, not just CTRL.

**What would change this**: a cheap diagnostic run showing a high clip rate correlated with
`log_std` growth would make this a live-defect candidate (A27/A29-style), not just a declared
risk — the same evidentiary bar this project has already held every other design point to tonight.

**Refined 2026-09-05, review 14 §9 — my first draft treated "the objective uses the raw action" as
one undifferentiated problem. It is two, with different verdicts.** Traced
`runnable/ctrl/algo.py:173,552-553`: CTRL has a SEPARATE representation/clustering loss
(`loss_cluster`), distinct from the PPO losses, which also conditions on `action` — and it receives
the identical raw, stored action from the same rollout batch as PPO does (confirmed:
`extract_windows_vectorized(action, cluster_len)` windows the same batch field).

- **For PPO, using the raw action is arguably CORRECT, not a bug**: the importance-sampling ratio
  needs the log-probability of the action the policy actually SAMPLED, not a post-hoc clipped
  version — this is standard practice, not specific to this port.
- **For the clustering/representation objective, the case is weaker**: it is modeling
  `(s_t, a, r_t, s_{t+1})` as a transition, and the transition that actually occurred used the
  EXECUTED (clipped) action, not the raw one. Using raw there is a more specifically questionable
  choice than PPO's use of it.

This means my operational default (leave the port as-is) is right for PPO's own use of the action,
but the clustering loss's use of it is a narrower, more targeted question than "the CTRL port has a
raw-vs-clipped issue." Review 14's recommended experiment is correspondingly narrower and cheaper
than a full sensitivity study: hold PPO fixed, vary only `loss_cluster`'s action input (raw vs
executed), and compare. Not run tonight — it needs one short controlled comparison, not tracing —
but it is now the correctly-scoped next step, not the vaguer "run a sensitivity study" this entry
first suggested.

**CORRECTED 2026-09-05, same session, before this entry was even read back by anyone — checked
against the live tree rather than left standing.** The recommendation above ("watch log_std... add
the clip-rate diagnostic... none has it today") was WRONG about the monitoring, not about the
objective. Checked and found: `gaussian_policy_health`/`boundary_fraction` is **already live** for
all three — `ctrl` calls it at `train_ppo.py:359`, `idaac` at `train.py:58,374,381` (logs
`train/boundary_fraction`), and `ibac_sni` obviously does too, because `docs/REGISTER.md`'s
2026-09-04 entry used it to measure ibac_sni's boundary_fraction crossing 0.50 at ~50k frames
against idaac's 0.024 at the same budget — a real, already-caught instance of exactly this
pathology, already sitting as its own open owner decision (entropy_coeff for ibac_sni alone) in
`REGISTER.md`, independent of and earlier than this entry.

**What is real and still stands**: the PPO objective itself computes `log_prob` on the RAW,
pre-clip action, and no amount of MONITORING boundary_fraction changes that computation. Measuring
the drift and correcting the objective for it are different things; only the first exists.

**What actually was missing, found while checking this on 2026-09-05**: `scripts/eval_provenance.py`'s
`action_diagnostics()` computed the exact empirical clip-rate fields
(`action_clip_rate_coordinate`, `action_clip_rate_vector`, `action_raw_executed_l1`) generically
for any family, but had **zero call sites anywhere in `scripts/`**. It was built and never wired
into a record path. **Closed 2026-09-06**: the seven-family offline evaluator now observes the
adapter-to-environment action boundary and emits `native.policy_action_diagnostics` per scene row.
This is measurement only; controller-internal torque clipping remains explicitly outside the
observed scope, and the old objective/fidelity warning is unchanged.

### A31 OPEN, 2026-09-06 — `results_table.py`'s floor never joined the single-home fix (Q12)

`scripts/rlvigen_reference.py::DOOR_RANDOM_FLOOR` is the declared single home for the Door
random-policy floor, established after the same number lived in five places at once (Q12).
`scripts/preprod_table.py` imports it correctly. `scripts/results_table.py` and
`scripts/regime_retention_report.py` do not — both measure the floor locally, from the identical
`random-floor__{mode}.json` grids in `results/regime-retention[-c69]/`, produced by a separate
pipeline (`run_regime_retention.sh` → `eval_across_scenes.py --random-policy`), never
`probe_floor.py` (the source of `DOOR_RANDOM_FLOOR`'s 1.842). Neither file's comments explain or
defend the divergence from the established policy; it looks like Q12's sweep simply never reached
either.

A stale, cross-tree data point (the ~2-week-old canonical `ccm-intro` tree's own copy of this
grid, mean≈1.8102 over 200 episodes — closer to C55's superseded 1.818 than the current 1.842)
suggests this isn't only a theoretical risk, but I cannot confirm that number reflects what this
workspace would measure today; full detail and that caveat in `CORRECTIONS.md` #87.

**Options**:
1. Import `DOOR_RANDOM_FLOOR` in `results_table.py` and `regime_retention_report.py` too, dropping
   the shared local measurement both currently use. Consistent with the established policy; loses
   whatever value (if any) came from measuring the floor via the exact same harness as their own
   cells.
2. Keep the local measurement, but say so explicitly in both files — a comment stating they
   deliberately tie their competence gate to this evaluator pipeline rather than the canonical
   constant, and why. Consistent with this project's "declare, don't silently diverge" discipline.
3. Leave silent. Not defensible — matches exactly the failure Q12 was raised to prevent.

**My reading**: (1), unless someone can state a real reason for (2) — `results_table.py` is
explicitly "LEGACY EXPLORATORY," and `regime_retention_report.py` is drqv2-only, so neither has an
obvious reason to use a different, less-measured (20 vs 200 episodes, per the shell driver's own
flag) floor than the table meant to supersede them. But this changes a competence-gate input in
comparison-bearing tables, so it is yours to decide, not mine to silently pick.
