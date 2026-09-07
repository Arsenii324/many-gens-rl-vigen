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

### A22 DECIDED AND IMPLEMENTED, 2026-09-07 — the upstream TRAIN split is the production value

Both arguments for keeping the validation split are gone (see the two entries below: the ordering
inference withdrawn, then the 105 GB cost shown to be ~21 GB). With nothing left holding it up, and
the deviation being learning-affecting for three baselines, the answer is the source's own split.

**Implemented, not merely recommended**, and shaped so it cannot be inherited by silence:

- `configure_places365_val.py` takes `--split {val,train}`. For `train` the faithful configuration
  is the ABSENCE of the rewrite — upstream's `use_val=False` already selects it — so the script
  keeps only its fallback hardening and drops the override.
- `run_probe.sh` reads `NATIVE_PLACES365_SPLIT`, default `val`. **Probes are unchanged**: a
  functional probe should not need a 21 GB asset to run.
- **Production refuses `val`** at FRAMES >= 600000 unless `NATIVE_PLACES365_ACCEPT_VAL=1` is set,
  which logs `NATIVE_PLACES365_DECLARED_DEVIATION`. So the fleet cannot run on the validation pool
  the way it would have until today — by nobody deciding.
- Both loader flavours take the same split in the same run; `soda` reads through `dmc_gb`'s own copy
  of the loader, and splitting them would have the two families overlaying from different
  distributions.

**What the owner still has to do, and it is an asset action rather than a decision**: provision
`places365standard_easyformat.tar` (~21 GB, 256x256 train+val, the package DMC-GB's README
instructs reproducers to download) and set `NATIVE_PLACES365_SPLIT=train`. Until then production is
refused rather than silently deviating. Ratification remains open in the formal sense; the
operational default is no longer "whatever the script happened to do".

### A22 CORRECTED AGAIN, 2026-09-07 (late) — the 105 GB premise is WRONG, and it was the last leg

**My own cost figure was false, and the decision rested on it.** The revision below withdrew the
"same split so ordering is unaffected" argument and said explicitly that the decision then stood on
the operational leg: 105 GB against a 477 MB asset, "infeasible for the rehearsal path entirely".

**The canonical asset is not the 105 GB high-resolution archive.** DMC-GB's own README instructs
reproducers to download **`places365standard_easyformat.tar`**, which the official Places365 page
describes as **256x256 train+val, easy directory structure, about 21 GB** — the same per-image
shape as the 36,500-image validation pool this project ships, so switching changes the sampling
population and nothing else. The high-resolution archive is irrelevant here because the loader
applies `RandomResizedCrop(image_size)` down to 84x84 immediately.

So the real choice was never "477 MB vs 105 GB". It is **477 MB vs ~21 GB**, and at that price the
"infeasible" leg collapses. With the ordering leg already withdrawn, **A22 now rests on nothing**.

**Recommendation, reversed: adopt the upstream train split before the payload freeze.**

- It is a **learning-affecting** deviation for `svea`, `sgqn` and `soda` — the augmentation
  distribution IS their mechanism — and this project's stated claim is twelve published
  implementations at their authors' own settings.
- The change is asset-and-flag only: extract `places365standard_easyformat.tar` where the config
  expects `places365_standard`, and restore `use_val=False` by dropping
  `configure_places365_val.py`'s rewrite. No model or augmentation-shape change; the loader already
  expects exactly that directory layout.
- **The window is now.** After the freeze it costs a new payload, a new evaluator wave, and re-running
  nine cells (three baselines x three seeds). Before it, it costs a download.

**Why this is the owner's call and not mine to land unilaterally**: it changes what three baselines
train against, and the 21 GB has to reach both the DataSphere path (as a job input) and the
production host. I have implemented every other open item at my best; this one I am flagging
instead of doing, because I have now been wrong about its cost once and the remedy is a decision
about assets rather than about code.

### A22 REVISED, 2026-09-07 — the "same split for everyone" half of the reasoning is withdrawn

**External review 21 #6 rejects the load-bearing sentence above, and it is right to.** The row
argued that because svea, sgqn and soda all draw from the same split, "the cross-baseline
comparison — the actual estimand — is unaffected." That does not follow. The three consume overlays
through different objectives: svea inside its stabilised critic loss, soda in an auxiliary
representation objective, sgqn combined with its saliency objective and drawing an extra overlay
per update (which is exactly why P19 was needed for sgqn alone). A change to the overlay
distribution can therefore move the three by different amounts, and "same image pool" implies
nothing about invariant ordering. **That argument is withdrawn; the decision stands on the other
two legs.**

**The operational leg, quantified rather than asserted.** Places365-Standard's train split is about
105 GB against the validation split's 477 MB (`rlgen-assets/places365-val.tgz`, the pinned asset
this project actually ships). Every DataSphere job takes its assets as a job input, so the train
split is not merely a "fresh multi-gigabyte download" — it is infeasible for the rehearsal path
entirely, and feasible on the production host only as a mounted local copy. Switching only where it
is feasible would make the augmentation distribution **platform-dependent**, which is strictly worse
than a uniform deviation: it would confound the renderer-parity work (C95) with an augmentation
change.

**The mechanism by which it could actually matter, stated so it is falsifiable.** The val split is
36,500 images (100 per class) against the train split's ~1.8M. A 600k-frame run draws far more
overlay batches than either pool has images, so both repeat; the val split repeats each image
roughly 50x more often. If overlay diversity is what makes the augmentation a regulariser, the
smaller pool is a weaker regulariser, and the three methods would be affected in proportion to how
central the overlay is to each — most for soda, least for svea. That is a prediction, not a
measurement, and nothing in this project measures it.

**Implemented default, unchanged: keep `use_val=True`, declared.** What changes is the honesty of
the label. `CLAIMS-LEDGER.md` must say these three are trained against a 36,500-image overlay pool
rather than the released 1.8M one, and that no claim of ordering-invariance under that change is
made — not that the change is harmless.

**Override cost, now that it is priced**: a 105 GB asset, a production-host-only path, and a re-run
of nine cells (three baselines x three seeds). Worth it only if parity with published
overlay-augmentation numbers becomes a goal, which `CLAIMS-LEDGER` currently forbids on other
grounds anyway.

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

**RECONCILED 2026-09-06 — the number this entry is missing may not be the number that matters.**
Checked whether δ (a margin on RAW RETURN above `R_floor`) is actually the operative competence
gate anywhere in the code that runs today. It isn't: `scripts/results_table.py`'s and
`scripts/regime_retention_report.py`'s own live denominator rule is
`mtr[scene] > floor_mean AND success_rate(scene) >= MIN_DENOM_SUCCESS (0.25)` — a plain floor
exceedance (no margin) combined with a **success-rate** threshold, not a return-margin one. And
`regime_retention_report.py`'s own comment states exactly why: a return-based check alone let a
policy scoring 1/20 on every scene — a shaped-reward plateau, never actually opening the door —
pass through and read as "retention of 0.947." That is precisely the failure mode δ was invented
to guard against, via a different (return-margin) mechanism that was never implemented because the
success-rate gate already closed the hole first, for a stronger reason: success is a direct,
task-defined signal, while return is dense, shaped, and exactly the quantity that can plateau
without task success. A return-margin gate is provably weaker at the one thing it exists to catch.

**My reading, offered as the "our best" operational answer rather than a further deferral**: the
success-rate gate (`MIN_DENOM_SUCCESS = 0.25`) IS this project's competence gate, already live,
already battle-tested against a real adversarial case, and should be treated as A23's actual
resolution rather than leaving δ dangling as a second, unimplemented mechanism answering the same
question worse. δ / `R_floor + δ` should be retired from the proposal rather than eventually
resolved. What remains genuinely open, and is the owner's: whether 0.25 is the right success-rate
threshold (a real, stateable number, unlike δ) — and whether train-regime success alone should gate
train-vs-OOD comparisons, or whether OOD-regime success needs its own, possibly different,
threshold. Not fixed here; noted as the narrower, better-posed question this reconciliation leaves.

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
- **Off-policy, differing in augmentation**: `drqv2`, `svea`, `sgqn`, `drq`, `rad`, `soda` — 6
  methods, 15 pairs, augmentation as the varying axis. **Corrected 2026-09-06 (external review 18,
  independently verified against the actual classes rather than taken on the review's word)**: this
  row previously said "all sharing a SAC backbone" — false for 3 of 6. `RL-ViGen-upstream/algos/
  drqv2.py::DrQV2Agent` and `svea.py::SVEAAgent` use `stddev_schedule` (a scheduled deterministic
  exploration noise) and have no `log_alpha`/entropy term anywhere — DDPG-style, not SAC.
  `sgqn.py::SGQNAgent(DrQV2Agent)` inherits that backbone directly. Only `drq.py::DrQAgent` among
  the RL-ViGen three is genuine SAC (`log_alpha`, `self.alpha.detach() * log_prob` in both actor and
  critic losses, `drq.py:213-323`). `rad`/`soda` (via `dmc_gb`'s `SAC` class, `sac.py:35`,
  `log_alpha` confirmed) are also genuine SAC. So the group is real and the augmentation axis is
  real, but the backbone is not uniform within it — declare, don't claim uniformity that isn't
  there, same rule this project applies everywhere else.
- **Off-policy, differing in representation learning**: `curl` (contrastive), `alda`
  (autoencoder + latent dynamics model, confirmed from its own optimizer set —
  `alda_trainer.py:105-109`: actor/critic/**ae**/**latent**/log_alpha) — 2 methods, 1 pair. Same
  correction applies: `curl.py::CURLAgent(DrQV2Agent)` is DDPG-style, not SAC; `alda` genuinely has
  `log_alpha` and is the only true SAC member of this pair.
- **Cross-group, best-in-group**: the winner of each of the three groups above against the other
  two — this is the comparison that actually answers the project's central question (does an
  on-policy regularizer, an augmentation choice, or a representation-learning approach generalize
  better), which "family" never could, since `rlvigen` alone bundles augmentation AND contrastive
  methods under one repository.

**25 named primary comparisons** (6+15+1+3), down from 66; full matrix published as supplementary.

### A25 ADDENDUM, 2026-09-07 (later the same day) — the fixed cross-group pairs cross the fleet's only UNITS split

**Found by adding `evaluation policy mode` to `audit_comparability_seam.py`, which had never carried
it, and then checking what the addition implies for the contrast I froze this morning.**

`scripts/eval_grid.py` — the evaluator that produces every reported number — deliberately
reproduces each family's OWN action rule (`evaluator_identity.FAMILY_EVAL_POLICY_MODE`): `mode` for
the eight RL-ViGen/dmc_gb/alda baselines, `sample` for the four Procgen-lineage on-policy ones
(`idaac`, `ppg`, `ibac_sni`, `ctrl`). That is faithful, and the records carry
`conventions.eval_policy_mode` precisely "so no table pools the two".

**But it is a UNITS split** — E[return | a = argmax π] and E[return | a ~ π] are different
estimands, and for a converged Gaussian head the second is lower in expectation and higher in
variance. By `audit_comparability_seam.py`'s own rule a UNITS split "has to be removed or converted
before the numbers can be compared at all", unlike a CONDITIONS split which can be declared and
quantified. **It is now the fleet's only UNITS split**, the evaluation-scene-set one having been
closed earlier.

**And this morning's A25 revision walked straight into it.** Two of the three fixed cross-group
pairs I froze — `idaac` vs `svea`, and `idaac` vs `curl` — put a sampling reporter against a
mode-taking one. Any difference between them confounds the mechanism the pair exists to isolate
with the evaluation rule. The winner-versus-winner problem I fixed this morning was a statistical
one; this is a measurement one, and it is worse, because no amount of care in the analysis removes
it.

**Implemented default: evaluate the four stochastic families in BOTH modes at the endpoint, report
their native mode as the headline, and use the mode-taking pass for any cross-group contrast.**

- **Cost, priced rather than waved at**: four baselines x three seeds = twelve cells, each an extra
  800-episode endpoint grid at ~11 s/episode = 2.4 h, so **~29 GPU-h against a campaign total near
  865** — about 3%. That converts an incommensurability into a measured quantity, and it also
  answers a question worth having: how much of any on-policy-versus-off-policy gap is the
  evaluation rule rather than the method.
- **Why not standardise on `mode` outright**: it would silently replace each family's own reporting
  path with ours, which is the deviation `EVALUATOR-DELTA.md` exists to prevent, and it would make
  every number non-comparable with the family's own published values.
- **Why not just declare it**: a declaration is the right treatment for a CONDITIONS split. This one
  changes what the number IS, and the primary contrasts cross it.

**IMPLEMENTED the same day.** `eval_grid.py` now takes `--policy-mode {native,mode}`, defaulting to
`native` so every existing record's production path is unchanged. All four sampling families honour
it: `idaac` through `act(..., deterministic=True)`, `ctrl` through `select_action(..., sample=False)`,
`ibac_sni` through its `Agent`'s `argmax` positional, and `ppg` through a wrapper in OUR harness
rather than an edit to `runnable/ppg` — its `PpoModel.act` calls `pd.sample()` and the repo ships no
deterministic path, so the wrapper takes `pd.mean` (the mode of the `torch.distributions.Normal`
its continuous head builds). The record stamps the mode that ACTUALLY ran, plus an
`eval_policy_mode_source` saying which of the two it was: stamping the native rule while the
override was in force would make the record assert the one thing it exists to certify.
`tests/test_policy_mode_override.py` pins all four call sites and the record stamp.

**This moved all seven attestations**, as predicted — `eval_grid.py` is a shared `CODE_MEMBER`. That
is the argument for having done it BEFORE the wave rather than after: one wave covers seven families
whether or not this change is in it, so landing it first costs nothing and landing it later costs a
second wave. The freeze now waits only on A36's geometry answer.

**Superseded 2026-09-07 (later): both premises of this entry moved.** `ctrl`'s own evaluation rule
was corrected to `mode` (its released evaluator is greedy — `evaluate_ppo.py:84`), so the split
this entry called 8/4 is 9/3 with `ctrl` on the deterministic side, and the "four stochastic
families" plan above is now three (`idaac`, `ppg`, `ibac_sni`). The owner then ruled the residual
split acceptable and directed "no secondaries" (A39 below): the both-modes pass described above is
implemented and reachable but was never scheduled or run. See `notes/SAME-AXES-VERDICT.md` for the
full account and the ruling.

### A25 REVISED, 2026-09-07 — the cross-group contrast is no longer winner-versus-winner

**External review 21 #10, and it is right.** The "cross-group, best-in-group" row above selects the
empirically best method in each group and then compares those three. That is post-selection
inference: the selected method's advantage is inflated by the selection itself, and predeclaring
*that you will select the winner* does not remove the bias — it only makes it honest. At n=3, with
this project's own resolving-power analysis saying close rankings are poorly resolved, the winner
of a 6-method group is frequently the luckiest rather than the best.

**Implemented default, replacing that row with two things that are not the same as each other:**

1. **A fixed, pre-named representative per group, chosen on scientific grounds and frozen now,
   before any production outcome exists.**
   - On-policy PPO group → **`idaac`**. The group's most-cited method and the only one with
     published continuous-control evidence at this scale (its own supplement's DMC experiments),
     so it is the member whose behaviour a reader can situate.
   - Off-policy-by-augmentation group → **`svea`**. The canonical "augmentation done right"
     method of the group, and the one whose mechanism the group is named for. `drqv2` is
     deliberately NOT the representative: it is the no-augmentation control and appears in the
     within-group pairs as such.
   - Representation-learning group → **`curl`**. The canonical contrastive method; `alda` is the
     autoencoder+latent-dynamics member and the pair's second arm.
   These three give **3 fixed cross-group pairs**, selected without reference to any outcome.
2. **A group-level aggregate contrast** as the headline for "does the mechanism class matter",
   which avoids member selection entirely and answers that question more directly than any single
   member can. Reported with the within-group spread beside it, so a reader can see whether the
   class difference is larger than the variation inside a class — which at n=3 it very often will
   not be, and saying so is the point.

**Winner-versus-winner is retained but demoted**: reported in the supplementary matrix, labelled
explicitly as post-selected and descriptive, never as a primary contrast and never with an
inferential claim attached. It is genuinely informative as a description of what happened; it is
not evidence about which mechanism is better.

Count is unchanged at 25 (6 + 15 + 1 + 3), because the three cross-group pairs are now fixed rather
than outcome-selected. Presentation-only, like the row it revises: nothing about what is collected
or retained changes, and this is reversible at zero cost if the owner prefers a different
representative or a different aggregation.
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
the same **sample count and auxiliary-phase interaction cadence** as the only published
continuous-control PPG design point (IDAAC's continuous-control appendix, `1 x 2048 x n_pi=32`).
**Corrected 2026-09-06 (external reviews 17/18, independently reasoned through rather than taken on
either review's word)**: this row previously said "exactly the cadence," which overclaims. `8x256`
and `1x2048` agree on total samples/update and interactions/auxiliary-phase, but not on rollout
geometry: eight independent 256-step fragments give GAE/bootstrap boundaries every 256 steps in
eight parallel trajectories, while one 2048-step stream gives boundaries every 2048 steps across
several concatenated Door episodes (horizon 500) in one trajectory — a real difference in temporal
correlation and bootstrap placement, not a cosmetic one. Full derivation and the four reference
configurations: CORRECTIONS #58.

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

### A27 — the utd=0.25 arm is CANCELLED as uninformative, 2026-09-07

**I resubmitted it and then cancelled it an hour later, and the reasoning is worth keeping because
the mistake is a common one: running the arm that completes the design rather than the arm that
changes a decision.**

What happened: external review 21 #8 asks for the bounded utd stability check before committing
three 600k ALDA seeds. Checking whether it had run found ALDA-P (`utd=1.0`, source-faithful) at
SUCCESS and ALDA-C (`utd=0.25`) at ERROR — killed in seconds by a stale payload predating `utd`'s
arrival in `AldaConfig`. I rebuilt the payload and resubmitted (`bt1gbubmmh61itfnvm5t`, ~4.8 h).

**Then asked whether it was actually needed, and it is not.** Trace what each arm decides:

- **ALDA-P at 150k already succeeded**, so `utd=1.0` does not diverge on Door within a quarter of
  the production budget. That is the only arm the production decision turns on, and it has run.
- **ALDA-C would tell us whether `0.25` also works** — but we are not running `0.25`. Under this
  project's fidelity-first rule, `utd=1.0` is the author's own setting and stands. Even in the
  branch where `1.0` diverged, the finding would be *reported*, not repaired by silently switching
  to a value no ALDA paper specifies; C57 already establishes that a diverged run is detected at
  retention rather than hidden.
- **The residual worry — divergence appearing after 150k — is not addressed by the C arm either.**
  Only a longer P run would speak to that, and the production seed IS that run, with
  `check-finite` at retention and `watch_divergence.py` available live.

So the C arm cost ~5 GPU-hours to produce information that changes no action. Cancelled at
`EXECUTING`. **A27's status is unchanged**: the update-to-data ratio remains a declared
comparability axis (`updates_per_env_frame` in `audit_comparability_seam.py`), production runs
`utd=1.0`, and the historical Lift instability stays recorded as what it is — a measurement on the
retired `rlgen` port at a different task, not evidence about `runnable/alda` on Door.

**What would make the C arm worth running after all**: a production ALDA seed diverging. At that
point `0.25` becomes a candidate repair and the comparison has a decision attached to it.

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

### A31 IMPLEMENTED OPERATIONAL DEFAULT, 2026-09-07 — differentiated per file, not one option for both

Re-checked both files' actual code before picking, rather than trusting "my reading" above at face
value — and that reading turns out right for one file, wrong for the other:

- **`results_table.py`: option 1.** Now imports `DOOR_RANDOM_FLOOR`/`DOOR_RANDOM_FLOOR_EPISODES`
  (plus a new `DOOR_RANDOM_FLOOR_SUCCESSES = 0` constant added to `rlvigen_reference.py` for the
  same reason) via the identical helper `preprod_table.py` already used, and no longer loads its
  own `random-floor` grid at all — confirmed no other use of that grid remained in the file.
  `tests/test_results_table.py`'s old "missing floor → refuse" test tested a failure mode that no
  longer exists (an imported literal cannot be "missing" the way a grid file could) — replaced with
  a test that the floor value is exactly the canonical constant, not a second measurement.
- **`regime_retention_report.py`: option 2, not option 1.** This file's floor is measured through
  the *exact same* harness (`eval_across_scenes.py --random-policy`) as its own reported cells, and
  it needs the full per-episode distribution (sd, per-scene success counts) for its own output —
  `DOOR_RANDOM_FLOOR` exposes only a scalar mean. A canonical-constant swap here would cost either
  the same-harness guarantee or the distribution data; neither loss is the clean win it was for
  `results_table.py`'s simpler mean-only use. Declared explicitly in a code comment at
  `FLOOR_TAG`'s definition — this *is* the real, code-level reason for (2) that "my reading" above
  called unlikely to exist, not a restatement of the original guess.

**Status stays OPEN, not RESOLVED** — per this project's own two-layer convention (see also
A17/A18/A35/A36): the operational default is now implemented and defensible per-file, but which
file gets which treatment is still a judgment call, ratification-pending like before.

### A32 DECIDED, 2026-09-06 — the statistical-inference framework §1.1-1.4 propose

`notes/proposal-inference-and-checkpoint-selection.md` was drafted 2026-09-04, corrected by a
third external review on 2026-09-05 (the review caught four real errors in the first draft, all
fixed in the current text), and then left unmerged into `EVAL-PROTOCOL.md` "to avoid colliding
with concurrent work; merge it there when ownership is settled." That deferred the *merge*, not
just the *formal ratification* — meaning the operational document a reader would actually check
never reflected this project's own best analysis. Per the standing rule (A24/A25): a genuinely
best-judgment call gets implemented and persisted, not left sitting in a side file because formal
sign-off is pending. Adopting §§1.1-1.4 as the operational default, unchanged from the proposal
(already reviewed and corrected once; found no weakness in it worth re-deriving):

- **§1.1 Unit of analysis**: the training seed is the only outer replicate (n=3). Ten scenes and
  four regimes are analysis cells computed from one trained policy, never treated as independent
  replicates. Scene-level heterogeneity is still reported, descriptively.
- **§1.2 Scenes are a fixed grid, not a sample**: the ten certified scenes are prescribed by the
  protocol, not drawn from a population nothing in this project defines. Bootstrap resamples whole
  training-seed vectors (all ten scenes travel with a resampled seed); scenes themselves are never
  independently resampled.
- **§1.3 Reporting convention at n=3**: every headline value shows all three seed-level points
  individually, their mean, and their SD/range — never an interval alone, and never a p-value.
- **§1.4 What is and is not paired**: common evaluation placements (C69) pair regime/scene/episode
  measurement noise within one trained policy. They do **not** establish cross-method
  training-seed pairing — "seed 1" for two different algorithms shares an integer, not a
  common-random-number block, since the algorithms consume RNG differently. Compare distributions
  of three independently trained policies per method; use shared placements only to denoise each
  of those three numbers, never to claim a paired cross-method test.

§1.6 (placement-hash pairing) is not adopted here because it is already implemented and verified —
`production_gates.py`'s "placement provenance" gate (PASS) confirms every record carries an
episode id and a realized-placement witness. §1.7 (pre-registration, missing-run policy) is
already decided as A24/A25. §2 (primary-outcome ordering) already matches
`EVAL-PROTOCOL.md`'s own metrics-reported row. §3 (checkpoint selection) already matches this
project's operational default in `EVAL-PROTOCOL.md` §4, though its winner's-curse/equal-
opportunity reasoning is worth reading in full if a selected-best column is ever proposed. This
entry closes the one genuinely unmerged remainder: §§1.1-1.4.

Reversible at zero cost, same as A24/A25: this constrains reporting/analysis conduct, not a
running fleet or committed code path.

### A33 OPEN, 2026-09-06 — production scope: Door alone, or Door + Lift?

`production_gates.py::gate_production_scope_frozen` has stood OWNER since it was written with no
recorded lean — flagged during this session's surfaces-review sweep as exactly the kind of open
item that should carry a reasoned default rather than sit silent. The owner's own words framed it
as "Door, and possibly Lift" (`notes/claude-answers.md`), which already reads as Door-primary,
Lift-optional rather than a coin flip; this entry makes that explicit and states why.

**What Lift would cost, concretely — it is not a free row-add.** Every constant this project has
certified is Door's: the random-policy floor at **200 paired episodes** (1.842, C55), the ten
certified evaluation scenes, the 500-step horizon, and the published-anchor reasoning
(`notes/rlvigen-published-door-anchor.md`). Lift's own floor exists
(`scripts/rlvigen_reference.py::OUR_RANDOM["lift"]`, mean 6.562) but only at **25 episodes**
(`RANDOM_EPISODES["lift"]`) — an order of magnitude less rigorous than Door's, not yet re-measured
to Door's standard. The ten-scene certification, per-scene evaluation grid and anchor-table
reasoning would all need their own Lift-specific derivation from scratch; none of it transfers.

**Lift also carries an open, unexplained anomaly Door does not.** RL-ViGen's own published Lift
values for `drqv2`/`curl`/`drq` (0.2–2.0) sit *below* our measured Lift random-policy floor
(6.56), while SVEA (43.0) and PIEG (96.4) sit far above it —
`notes/faithfulness-reconciliation.md`'s own words: "remains **unexplained**, but Lift is not the
scoped task." Door has no equivalent open puzzle: its anchor comparison is reasoned through and
its floor/published-value relationship is coherent (`notes/rlvigen-published-door-anchor.md`).
Scoping-in a task whose own baseline behavior isn't yet understood, on top of an already-long
OWNER backlog (external anchor, production canary, seed/checkpoint ratification), is a real cost
against focus, not just compute.

**My reading**: Door alone for this production run. State Lift explicitly as a follow-on
extension once Door's fleet has reported, not a co-equal scope item now — consistent with how the
owner's own phrasing already weighted it, and with the actual state of Lift's calibration
evidence. Left OWNER because it is a scope call, not a mechanical fix; formal ratification (or a
stated override) is what would flip `gate_production_scope_frozen`.

### A34 DECIDED (option 1 applied), 2026-09-06 — `ppg`'s `train.py` is training-only by name but not by load path

**Closed, not just answered.** Commit `f1ac905` ("Close #94: evaluator identity schema 2") applied
option 1 below as part of the same schema-2 bump: `FAMILY_RUNTIME_MEMBERS["ppg"]` now includes
`runnable/ppg/phasic_policy_gradient/train.py`, verified by mutation test
(`tests/test_family_evaluator_revision.py`, `_mutate_bytes` on that exact path) and by a live check
that editing `ppg`'s `train.py` moves only `ppg`'s `code_revision`, no other family's. The commit
message says so explicitly ("Also closes CORRECTIONS #93/DECISION-SHEET A34"), but this entry's own
header was never updated to match — found on a second, closer read of this sheet rather than taken
on the header's word. **Consequence for the ledger**: any `ppg` validation run against the current
tree can now honestly earn `runtime_imports_checked: true`; the false-premise problem #93 found no
longer applies. The analysis below is kept for the record of how the fix was chosen, not as a live
open question.

Found by an independent adversarial review of the fresh evaluator-validation ledger (CORRECTIONS
#93). `evaluator_identity.py`'s `_TRAINING_ONLY_RUNTIME_BASENAMES` excludes `train.py`,
`evaluate_ppo.py`, `train_ppo.py`, `evaluate.py` from every family's hashed code-revision closure,
on the stated rationale that they're training drivers whose edits shouldn't relabel an evaluation
of already-saved checkpoint bytes. For `ppg` specifically that rationale is false:
`runnable/ppg/phasic_policy_gradient/__init__.py` is exactly `from .train import train_fn`, so
importing the package AT ALL — evaluation included — unconditionally executes `train.py`'s module
body. The file is genuinely loaded by the live evaluator process without being part of what
`family_code_revision["ppg"]` hashes.

**Scope, checked directly rather than assumed**: grepped every `__init__.py` under `runnable/` for
an import of any of the four excluded basenames. Only `ppg`'s does this — `evaluate_ppo.py`,
`train_ppo.py`, `evaluate.py` are not imported by any package `__init__.py` anywhere, and `train.py`
only by `ppg`'s own. This is a `ppg`-specific gap, not a systemic one across the seven families.

**Currently harmless**: `train.py`'s module-level code is only imports plus `def train_fn`/`def
main`/an `if __name__ == '__main__':` guard — no side-effecting statement runs at import time, so
this has not corrupted any measured number to date. It is a structural gap, not an active defect:
a future edit to `train.py` would change what the live evaluator runs without moving `ppg`'s code
revision.

**Options**:
1. Remove `train.py` specifically from `ppg`'s exclusion (make the basename list per-family, or
   add `runnable/ppg/phasic_policy_gradient/train.py` to `FAMILY_RUNTIME_MEMBERS["ppg"]`
   explicitly). Closes the gap for `ppg`; does not touch the other six families' closures at all.
2. Leave it, documented as an accepted, currently-inert risk, and re-check after any future
   `train.py` edit rather than pre-emptively closing it.
3. Generalize: make the exclusion self-verifying (skip excluding a basename only when nothing in
   the family's own package unconditionally imports it), closing the same class of gap for any
   future family/file combination, not just this one instance.

**Why this is left OWNER rather than just fixed**: any change to `evaluator_identity.py`'s
`CODE_MEMBERS`/`FAMILY_RUNTIME_MEMBERS`/exclusion logic moves EVERY family's `family_code_revision`
simultaneously (it's a shared file), which would immediately invalidate the four families just
independently verified as current (`rlvigen`, `dmc_gb`, `idaac`, `ibac_sni` — CORRECTIONS #90/#93)
and require re-running their validation jobs again. That is a real cost to spend deliberately, not
a side effect to absorb while fixing something else. `ppg`'s ledger entry is left honest in the
meantime: `runtime_imports_checked: false`, `gate_shared_evaluator_validated` correctly reads 4/7
rather than a falsely-earned 5/7.

**My reading**: option 1 — narrowest fix, zero blast radius on the other six families' revisions,
closes the actual gap found. Worth doing in the same pass as `ppg`'s next validation re-run (it
needs one anyway, since this entry is currently unvalidated), not as a standalone edit that forces
an otherwise-unneeded re-verification of the four families that already passed.

### A35 OPEN, 2026-09-06 (analysis completed same entry) — IDAAC's design point: the exact pilot spec, not just "run a comparison"

Promoted from `notes/review-11-12-gemini-triage.md`'s T17 (`"DESIGN-POINT DECISION, after T1"`,
deliberately deferred until IDAAC's episode-identity bug was fixed) and sharpened by external
review 15 §4, which names the single most consequential number in this project's whole
fidelity surface: current Door IDAAC's `order_loss_coef=0.001` against the authors' own published
continuous-control `alpha_i=0.1` — a **100x** difference in the weight of IDAAC's defining
invariance objective. T1 (the episode-identity bug) is now fixed (external review 15 §3
independently confirms it), so T17's precondition is satisfied and this pilot is unblocked.

**Marked ANALYSIS INCOMPLETE, not just OPEN**, per the standing distinction: this is not a decision
awaiting the owner's ratification of an already-finished "our best" answer — the "our best" answer
(the exact pilot design) had never actually been produced before this entry. "Run a comparison" is
not that answer; the parameter table below is.

**Current Door IDAAC ("IDAAC-P"), read directly from source, not from the review's summary:**
`runnable/idaac/ppo_daac_idaac/arguments.py` argparse defaults (all left at their upstream/Procgen
values — nothing here overrides them) plus `families.json`'s three constants:

| parameter | value | source |
|---|---|---|
| `num_processes` | 4 (16 under `NATIVE_HOST_PROFILE=v100`) | `families.json` constant, A14-class owner decision (2026-09-02: 64 upstream envs don't fit a T4) |
| `num_steps` | 256 | `families.json` constant |
| `num_mini_batch` | 8 | `families.json` constant |
| `gamma` | .999 | argparse default |
| `entropy_coef` | .01 | argparse default |
| `lr` | 5e-4 | argparse default |
| `ppo_epoch` | 1 | argparse default |
| `value_epoch` | 9 | argparse default |
| `value_freq` | 1 | argparse default |
| `adv_loss_coef` | .25 | argparse default |
| `order_loss_coef` | .001 | argparse default |
| frame stack | 1 | `rlgen/protocol.py::OBSERVATION_GEOMETRY["idaac"] = (64, 1)` — a protocol-level constant, not an argparse flag |
| LR schedule | none — flat | no decay mechanism exists anywhere in this port; confirmed by reading `train.py` and the full argparse, not inferred |

**CORRECTED 2026-09-06, before building any config from this table**: this entry originally read
frame stack as "3, pending a code change" — engineering-cost framing only. Re-checked against
`docs/CONSTRUCTION.md#c2`'s own already-documented finding, which this entry should have cross-
referenced the first time: stacking frames for IDAAC specifically is not a fidelity trade, it is
**structurally incoherent** with the auxiliary adversarial objective (see the table row below).
Frame stack is now held at 1 for both arms; nothing else in this table changes.

**CORRECTED AGAIN, 2026-09-06, same day — the correction above is empirically contradicted by the
paper it invokes, checked against the vendored primary source, not a summary.**
`ext/idaac/raileanu21a-supp.pdf` §E ("DeepMind Control Suite Experiments"), read directly via
`pdftotext`: *"We also use 3 stacked frames as observations... for DAAC and IDAAC, we ran the same
hyperparameter search as for Procgen and found that EV = 9, Nπ = 32, αa = 0.1, and αi = 0.1 worked
best across all environments... our methods outperform the baselines on these continuous control
tasks."* This is the authors' own full IDAAC method (adversarial order-prediction head included,
`αi = 0.1` is exactly this table's `order_loss_coef` headline value) run **with** 3-frame stacking,
reported as outperforming baselines — direct empirical evidence against C2's theoretical
incoherence claim for this specific case, not merely a different opinion. C2's mechanism-level
reasoning (a stack embeds motion the discriminator's objective tries to erase) may still describe a
real pressure on the representation, but the authors' own DMC result says it does not prevent the
method from working. Frame stack is restored to **3** for IDAAC-C, matching Appendix E exactly.

**Not corrected reactively into the currently-running pilot** (`bt1djeamji7gilgnndft`, submitted
before this check) — restarting it would be exactly the reactive-resubmission pattern Q47 asks this
project to stop. Its frame_stack=1 result is not wasted: it becomes the "1" arm of the frame_stack
∈ {1, 3} ablation this same source material (`notes/ai-help-16.md`, an external consultation
independently reaching the same frame_stack=3 conclusion, now checked against the primary source
rather than taken on its own word) recommends running anyway — "whether temporal information is
actually needed on Door, or whether stacking primarily adds distractor information" is a real
question, not a consolation prize. **A frame_stack=3 arm (IDAAC-C2) is the next pilot to build**,
in the frozen final wave per Q47, not before. No code/config/remote action taken on this finding
per Q48's explicit "no code, config, payload, or remote action is requested from you here."

**Proposed IDAAC-C (minimally Door-adapted continuous-control design)**, changing only what the
published continuous-control recipe (review 15 §4, citing the paper's Appendix E) actually
specifies, holding everything else at IDAAC-P's value so the comparison isolates the recipe rather
than introducing untested combinations:

| parameter | IDAAC-P (current) | IDAAC-C (proposed) | reasoning |
|---|---|---|---|
| `num_processes` | 4 | **1** | Confirmed directly against `ext/idaac/raileanu21a-supp.pdf` §E ("2048 steps, 1 process"), not just review 15's summary — this table's other rows originally cited review 15 alone and were corrected the same way once the frame-stack question forced a primary-source read. Unlike the Procgen case (64 envs genuinely don't fit), 1 robosuite/MuJoCo instance has no forcing constraint against it |
| `num_steps` | 256 | **2048** | Same source, same sentence ("2048 steps"), confirmed directly |
| `num_mini_batch` | 8 | **32** | Same source: the DMC-wide grid search "found... 32 minibatches to work best across these environments" — this is the shared base value, not the method-specific `Nπ=32` two rows below (the two happen to coincide numerically; confirmed as two distinct findings in the source, not one) |
| `gamma` | .999 | **.99** | Same source, same sentence ("γ = 0.99") |
| `entropy_coef` | .01 | **0** | Same source: grid search "found... 0.0 entropy coefficient" |
| `lr` | 5e-4 | **3e-4** | Same source: grid search "found... 0.0003 learning rate" |
| `value_freq` | 1 | **32** | Confirmed directly: "for DAAC and IDAAC, we ran the same hyperparameter search as for Procgen and found that EV = 9, Nπ = 32, αa = 0.1, and αi = 0.1 worked best" — `Nπ` here is IDAAC's own method-specific finding, not borrowed from PPG's cadence by analogy as the original version of this row assumed |
| `adv_loss_coef` | .25 | **.1** | Same sentence: `αa = 0.1`, confirmed directly |
| `order_loss_coef` | .001 | **.1** | Same sentence: `αi = 0.1`, confirmed directly — the headline 100x finding |
| frame stack | 1 | **3 — restored, see the second correction above** | `ext/idaac/raileanu21a-supp.pdf` §E, checked directly: the authors' own DMC continuous-control experiments run the full IDAAC method (including the adversarial order-prediction head, `αi=0.1`) with 3 stacked frames and report it outperforming baselines. This empirically contradicts the `docs/CONSTRUCTION.md#c2`-based "structurally incoherent" reasoning this row previously used to hold frame stack at 1. Not applied to the already-running pilot (Q47: no reactive resubmission) — an `IDAAC-C2` arm at frame_stack=3 is the next pilot to build, in the frozen final wave |
| `ppo_epoch` | 1 | **10** | `raileanu21a-supp.pdf` §E, same passage: the DMC-wide grid search ("learning rate in [1e-4,3e-4,7e-4,1e-3], minibatches in [8,16,32,64], entropy in [0,1e-2,1e-3,1e-4], ppo epochs in [3,5,10,20]") found 10 ppo epochs, 0.0 entropy, 3e-4 lr, 32 minibatches best "across these environments," applied as the DMC-wide base before DAAC/IDAAC's own additional search (`EV=9, Nπ=32, αa=0.1, αi=0.1`) layers on top. Resolves what the previous row left as "not resolved, do not invent a number" — this is read from the source, not guessed |
| LR schedule | flat | **linear decay over 1M env steps, confirmed used, still not implemented in this port** | Same source, same passage: "linear rate decay over 1 million environment steps" is stated as part of the shared DMC recipe, not a maybe. This strengthens rather than changes the prior reading — the port genuinely has no code path for it (checked `train.py` and the full argparse), so it stays declared-not-implemented, but it is now confirmed a real omission from the published recipe rather than an unclear one |
| everything else (`clip_param`, `gae_lambda`, `max_grad_norm`, `eps`, `alpha`) | upstream default | **unchanged** | Review 15 does not name a continuous-control value for these; declare-don't-invent applies here as it does everywhere else in this project |

**Pilot sizing, not full production**: review 15 calls this a "bounded pilot," explicitly distinct
from a full 600k x 3-seed commitment. My reading: one seed each of IDAAC-P and IDAAC-C at a budget
long enough to distinguish "learns" from "doesn't" on Door — the project's own existing bracket
convention (C60-style, checkpoints at 50k multiples) applied to a ~200k-300k frame ceiling, not
600k. Extend only if the two arms are still close at that point and the question remains open.

**Decision rule, revised 2026-09-06 (external review 18's methodological point, accepted)**:
the previous rule below let Door performance decide which arm gets *called* the source-faithful
IDAAC ("if C reaches competence, make it primary; if not, keep P"). Review 18's objection is
correct and sharper than this project's own earlier framing: that conflates two different
questions — which variant is the source-fidelity target (a provenance fact, decidable from the
paper alone, independent of any Door result) and which variant should be the headline production
comparison (an empirical, reportable outcome). Collapsing them means a reader cannot tell "IDAAC
generalized poorly" from "we relabeled IDAAC as whichever adaptation happened to learn Door,"
exactly review 18's phrasing. **Split them:**
- **Source-fidelity designation, decided now, independent of any pilot result**: once a `C2` arm
  exists matching the published DMC recipe in full (frame_stack=3, `ppo_epoch=10`, the rest of
  A35's table), *that* arm — not whichever arm happens to win — is the one entitled to be called
  IDAAC's source-faithful Door port. This does not wait on Door performance.
  - `IDAAC-P` (Procgen-parser defaults ported to Door) and `IDAAC-C1` (the partial recipe already
    piloted, frame_stack=1/`ppo_epoch=3`) are both **adaptations**, not competing fidelity claims —
    neither is entitled to the "faithful" label regardless of which learns Door better.
- **Headline production comparison, still empirically gated**: among whichever arms are actually
  run at production length, report the one(s) that reach competence as the headline number(s), and
  report a competence failure as a documented negative finding, not a discarded attempt — this half
  of the original rule stands unchanged, it just no longer also decides the fidelity label.

**Original rule (superseded by the split above, kept for the record)**: if IDAAC-C learns Door at
least as well as IDAAC-P (competence, not exact parity — same success-rate gate as elsewhere,
`MIN_DENOM_SUCCESS`), make IDAAC-C primary for the full seed fleet; if it fails outright, keep
IDAAC-P primary and report IDAAC-C's result as a documented negative finding; if both are
affordable, run and report both.

**Left OWNER**: whether to spend the compute on this pilot at all, and the exact frame ceiling —
those are resource-allocation calls. Everything above the line is not a decision waiting on
anyone; it is the actual pilot specification, ready to become a config the moment someone (me or
the owner) decides to spend the cycles.

**PILOT RESULT, 2026-09-06**: both arms landed. Neither reaches the pre-registered competence bar
(`MIN_DENOM_SUCCESS=0.25`) at this pilot's 245760-frame budget — idaac-p and idaac-c1 both 0.0
success rate in both regimes, despite idaac-c1's raw return running 6-9x higher. Full numbers,
the decision-rule reading, and why this is not read as "C failed": `notes/CLAIMS-LEDGER.md`, "A35/
A36 pilot arms." Not treated as settling C1-vs-C2 or extending this pilot — see that entry.

**IMPLEMENTED, 2026-09-06 (Q55): this is now the actual production default, not just a specified
target.** The frame-stack implementation gap this entry's own C2 arm was waiting on is closed
(A65, C98) — a real `FrameStack` wrapper in `make_rlvigen_venv`, `VecPyTorchProcgen`'s
observation-space declaration and transpose heuristic made channel-count-aware, a real
`update_linear_schedule` for the paper's linear LR decay. Per Q55's one-predeclared-main-run
constraint, the full table above (frame_stack 3, `ppo_epoch` 10, `lr` 3e-4, `gamma` .99,
`entropy_coef` 0, `value_freq` 32, `adv_loss_coef`/`order_loss_coef` .1, `num_processes` 1,
`num_steps` 2048, `num_mini_batch` 32, LR decay over the literal 1M steps) is now
`families.json`'s idaac production config, replacing the Procgen-parser P defaults entirely — the
IDAAC-C1 vs C2 distinction this entry maintained throughout no longer applies going forward: there
is one idaac config now, and it is C2. **Not yet validated by a full-length training run** — see
the PILOT RESULT above, which tested part of this recipe at a short budget and is evidence toward
this direction, not proof of it. Verified locally: env construction, forward pass through the real
network, multi-step rollout, multi-env parallel construction, and the LR-schedule's exact math.

### A36 IDENTITY FROZEN — CORRECTED, 2026-09-07 (second pass, same day) — PPG **is** the IDAAC DMC comparator

**The freeze below is WRONG and is kept because the correction is the useful part.** It reasoned
from the identities as described in review 21 rather than from the supplement itself. Reading
`ext/idaac/raileanu21a-supp.pdf` §E directly settles it in the other direction:

> "To find the best hyperparameters, we ran a grid search over the learning rate ... We found 10
> ppo epochs, 0.0 entropy coefficient, 0.0003 learning rate, and 32 minibatches to work best ... We
> use γ = 0.99, λ = 0.95 ..., 2048 steps, 1 process, value loss coefficient 0.5, and **linear rate
> decay over 1 million environment steps. Following this grid search, we used the best values found
> for all the methods.** ... **For PPG**, we ran the same hyperparameter search as the one performed
> in the original paper for Procgen and found Nπ = 32, Eπ = 1, EV = 1, Eaux = 6, and βclone = 1 to
> be the best."

Two facts follow, and together they are decisive:

1. **PPG's own listed search covers only Nπ, Eπ, EV, Eaux, βclone — and all five equal PPG's
   released defaults** (`train.py:29,30,43,44,45`: `n_epoch_pi=1`, `n_epoch_vf=1`, `n_aux_epochs=6`,
   `n_pi=32`, `beta_clone=1.0`). So nothing in PPG's search overrides the shared grid, and the
   shared grid includes the decay.
2. **This port already runs the shared grid and already contradicts PPG's own release in every
   value the two identities dispute**:

| value | PPG's release | §E's shared grid | what we run |
|---|---|---|---|
| `lr` | 5e-4 | **3e-4** | **3e-4** |
| `aux_lr` | 5e-4 | (the same searched rate) | **3e-4** |
| `gamma` | .999 | **.99** | **.99** |
| `nminibatch` | 8 | **32** | **32** |
| `entcoef` | .01 | **0** | **0** |
| linear decay | none | **1e6 env steps** | **none → NOW SET** |
| geometry | 64 envs x 4 MPI ranks | **1 process x 2048 steps** | 8 x 256 |

We were the comparator in every disputed value while missing the one setting that identity
requires. That is precisely the "sits between two identities" review 21 #7 named, and the earlier
freeze resolved it by *asserting* the other identity rather than by checking which one the
configuration already was.

**Implemented**: `--lr_decay_env_steps` added to PPG's `train.py`/`ppg.py`/`ppo.py`, decaying the
policy, value AND auxiliary optimizers linearly on environment steps, and set to 1000000 in the
descriptor — the same literal horizon `idaac` uses, from the same sentence, so both members of that
comparison group now share the schedule instead of splitting on it. Default `None` leaves PPG's
released constant-rate behaviour byte-identical for anything that does not ask for the DMC recipe.

### A36 RESOLVED, 2026-09-07 — 1x2048 adopted; the identity is now complete

Codex ran both arms at 65,536 frames — one auxiliary cycle in each geometry — on the **same tier**,
which is what makes the comparison decide geometry rather than tier: **8x256 gives 78.54 IPS,
1x2048 gives 59.44**, both with 32 curve rows and no endpoint grid. The faithful geometry is 32%
slower.

**Priced**: PPG's production cost is 5.9 h/seed x 3 seeds = 17.7 GPU-h, so 32% is **+8.3 GPU-h
against a campaign near 893 — under 1%.** Adopted. Paying under one percent to stop being the
comparator in name while departing from it in the one place left is the whole of the decision, and
the difference is not merely speed: eight 256-step trajectories advantage-estimated independently
is not one 2048-step trajectory, so GAE truncation and trajectory geometry were the scientific
content at stake.

`MEASURED_FPS_GT4_1["ppg"]` moves 28.14 -> 21.3, carried across by the same-tier RATIO (0.757)
rather than by substituting a gt4i.1 absolute into a gt4.1 dict. **A36 is closed and the last
freeze blocker with it.**

**Superseded by the entry above: the rollout geometry.** §E says 1 process x
2048 steps; this port runs 8 x 256. Both give 2048 samples per update and the same
65,536-interaction auxiliary cadence, but not the same GAE truncation or trajectory geometry —
eight 256-step trajectories advantage-estimated independently is not one 2048-step trajectory.
`idaac` already runs the §E geometry exactly (`num_processes=1`, `num_steps=2048`). My
recommendation is to match it, and the reason it is not simply done here is measurable rather than
doctrinal: one environment instead of eight changes throughput by an unmeasured factor, and
`plan_production`'s ppg row is already flagged `UNMEASURED_ON_V100`. **This belongs in the step-2
throughput calibration on the production host: measure 1x2048, then adopt it.** Recorded as the
last remaining item of A36 rather than left implied.

**Consequence**: `runnable/ppg` is in ppg's hashed runtime closure, so ppg's evaluator attestation
is now superseded along with alda's. Both belong in the single final validation wave (Q47).

### A36 IDENTITY FROZEN — SUPERSEDED BY THE ENTRY ABOVE, 2026-09-07 — PPG is OpenAI PPG with borrowed values, not the IDAAC comparator

**External review 21 #7 asks for exactly one thing: stop sitting between two identities.** It is
right that the wording did, and the provenance string was the worse half of it — it read
"continuous-action port of PPG using the IDAAC-authors' DMC comparator profile", which claims the
identity that *requires* linear LR decay, while the port does not implement it.

**Frozen as: OpenAI PPG's released code, adapted to continuous-action Door, borrowing selected
continuous-control values from IDAAC's DMC supplement.** Under that identity:

- **Constant LR is correct, not a missing setting.** OpenAI PPG itself uses a constant learning
  rate; the linear decay over 1e6 environment steps belongs to the IDAAC authors' DMC experiment,
  which is a different artefact. `idaac` implements the decay because `idaac` IS that artefact.
- **The 8x256 rollout is a declared adaptation.** It preserves 2048 samples per update and the
  65,536-interaction auxiliary cadence — the two quantities that define PPG's phasic structure —
  and does NOT preserve the 1x2048 GAE truncation and trajectory geometry. Both halves are now in
  the provenance string rather than only the first.

**Why this identity rather than the other**, since either is internally consistent:
`RESEARCH-FRAME.md`'s claim is twelve *published implementations* run at their authors' own
settings. OpenAI PPG is a published implementation; the IDAAC-authors' PPG comparator is a
third-party baseline inside someone else's paper. Adopting the comparator identity would make this
cell a reimplementation of another group's baseline rather than the method's own release — a
different project from the one the frame describes. The borrowed values are the minimum needed to
make PPG expressible on a continuous-action target at all, and they are enumerated rather than
implied.

**What would overturn this**: a decision that cross-comparability with IDAAC's own published DMC
comparator matters more than each method running its own release. That would require adding the
decay and the 1x2048 geometry, and re-running PPG's cells.

### A36 OPEN, 2026-09-06 (analysis completed same entry) — PPG's design point: the remaining recipe gap, specified

T16's cadence half is closed (A26: `n_pi` now matches the continuous-control reference exactly).
Its other half — `notes/review-11-12-gemini-triage.md`'s own words, "the broader
hyperparameter-recipe comparison (lr, entropy coef, epochs)... remains a genuine open design
point, not touched" — had never had a concrete spec either. Sharpened by external review 15 §2.

**Current operational Door PPG C2**, read from `datasphere/native/families.json`'s production
descriptor and the reachable CLI flags in `runnable/ppg/phasic_policy_gradient/train.py`:

| parameter | value | source |
|---|---|---|
| `num_envs` | 8 | `families.json` constant (A26: matches the continuous-control 2048-sample rollout at `nstep=256`) |
| `nstep` | 256 | `families.json` constant |
| `gamma` | **.99** | production descriptor `--gamma`, source-backed DMC comparator value |
| `lr` / `aux_lr` | **3e-4 / 3e-4** | production descriptor `--lr` / `--aux_lr`, source-backed DMC comparator values |
| `nminibatch` | **32** | production descriptor `--nminibatch`, source-backed DMC comparator value |
| `n_epoch_pi` / `n_epoch_vf` | 1 / 1 | `train_fn` default |
| `n_pi` | 32 | `train_fn` default — already matches (A26) |
| `entcoef` (entropy) | **0** | production descriptor `--entcoef`, source-backed DMC comparator value |
| frame stack | 1 (historical C1) | **3 — implemented in train and evaluator adapters** | `rlgen/protocol.py::OBSERVATION_GEOMETRY["ppg"] = (64, 3)`; explicit `--frame_stack 1` evaluates legacy C1 |

**A relevant fact this project already established independently, not from review 15**: C61
(`docs/CONSTRUCTION.md#c61`) measured that `ibac_sni` — a sibling Procgen-lineage port — applies a
categorical-Atari-tuned entropy coefficient to a continuous Gaussian action distribution and gets
entropy *inflation*, not the intended regularization, because the coefficient was never re-derived
for a 7-D Gaussian's unbounded entropy. `ppo.py`'s own comment at the entropy computation site
cross-references this exact concern for PPG. This is independent evidence — not just published
precedent — that a Procgen-categorical-derived entropy coefficient is suspect on this port
specifically, which strengthens rather than merely parallels review 15's ask.

**Historical PPG-C proposal (superseded as an active branch on 2026-09-07)**:

| parameter | PPG-P (current) | PPG-C (proposed) | reasoning |
|---|---|---|---|
| `gamma` | .999 | **.99** | Published continuous-control value (review 15 §2), confirmed 2026-09-06 against `ext/idaac/raileanu21a-supp.pdf` §E directly: γ=0.99 is stated as the shared DMC-experiment base all methods in that section (including PPG) were run under |
| `lr` / `aux_lr` | 5e-4 | **3e-4** | Published value, same source confirmation: the DMC-wide grid search found 3e-4 best "across these environments" |
| `nminibatch` | 8 | **32** | Published value, same confirmation (32 minibatches, DMC-wide grid-search result) |
| `entcoef` | .01 | **0** | Published value, independently corroborated by C61's measured categorical-to-Gaussian entropy-coefficient failure on the sibling `ibac_sni` port |
| frame stack | 1 (historical C1 pilot) | **3 — implemented and smoke-tested** | IDAAC-authors' DMC comparator geometry; PPG primary source does not specify DMC, so this remains a declared adaptation. `frame_stack=1` stays explicit for C1 |
| `num_envs` / `nstep` | 8 / 256 | **unchanged** | A26 already established this matches the continuous-control rollout cadence; do not re-litigate a closed axis inside a different pilot |
| `n_epoch_pi`, `n_epoch_vf`, `n_aux_epochs`, `beta_clone`, `clip_param`, `kl_penalty` | upstream default | **unchanged** | Review 15 does not name continuous-control values for these; declare-don't-invent |

**Historical pilot sizing and decision rule**: identical shape to A35's, **including the 2026-09-06 split**
(source-fidelity designation decided from the recipe alone, independent of any Door result; the
empirically-gated headline-primary choice is separate and unchanged) — one seed each, bounded
budget (~200k-300k frames). PPG-P (Procgen-parser defaults) and PPG-C (this pilot's frame_stack=1
partial recipe) are both adaptations; neither the fidelity label nor "PPG-C wins if it reaches
competence" collapse into one decision any more, for the same reason review 18 gave for A35 — and
doubly so here, since (per the same review) the continuous-control recipe itself is a *third-party*
DMC comparator config from the IDAAC authors, not OpenAI's own PPG design, so "PPG-C is the
authors' own design" already overstated whose authorship it is. Given both pilots share the same
episode budget and Door setup, running A35 and A36 as one combined job batch (one extra seed's
worth of compute each, not two separate campaigns) is the efficient shape if the
owner authorizes spending on either.

**Left OWNER**: same as A35 — whether and when to spend the compute. The spec above is not
waiting on anyone.

**PILOT RESULT, 2026-09-06**: both arms landed. ppg-p has the only nonzero success rate in this
whole pilot round (0.2 train, still under the 0.25 bar); ppg-c is 0.0 in both regimes despite a
higher raw return (47.0 vs 33.6 train). Full numbers and reading: `notes/CLAIMS-LEDGER.md`, "A35/
A36 pilot arms."

### A36 IMPLEMENTED OPERATIONAL DEFAULT, 2026-09-07 — PPG C2 frame-stack path is live

The earlier PPG-C pilot intentionally used one frame and historical Procgen-shaped parameters.
The selected main PPG path now passes the source-backed comparator settings (`gamma=.99`,
`lr=3e-4`, `aux_lr=3e-4`, `nminibatch=32`, `entcoef=0`, `frame_stack=3`) through
`families.json` -> `train.py` -> `get_venv`; the shared evaluator passes the same stack into its
PPG environment. The wrapper smoke constructs both 9-channel C2 and explicit 3-channel C1 paths.
This is the IDAAC-authors' DMC comparator, not a claim that OpenAI PPG's primary source specifies
DMC. Formal owner ratification remains open; no second production branch is scheduled.

### A37 OPEN, 2026-09-06 (analysis completed same entry) — IBAC-SNI's lineage: picking one, not just naming the hybrid

`docs/FAITHFULNESS.md` already states plainly that current IBAC-SNI is "an authored hybrid
continuous-action IBAC-SNI adaptation" — honest, not hidden. External review 15 §7 sharpens the
consequence: the current port combines a CoinRun-style IMPALA visual trunk with the PyTorch/
GridWorld-side bottleneck implementation, which is neither source faithfully. If it performs at
the floor, a reviewer's fair reading is "this hybrid is weak," not "the original mechanism is
weak" — and this project cannot currently rebut that, because no coherent single-lineage version
exists to compare against.

**My reading, stated now rather than left as "choose a coherent lineage" (itself just a
restatement of the problem)**: commit to the CoinRun/visual lineage as the reference, not the
PyTorch/GridWorld one. Reasons: (1) Door is a genuinely visual task, so the visual-line bottleneck
design (built for pixel observations) is the architecturally relevant precedent, not the
GridWorld-derived one; (2) this project has already ported `--beta 1e-4` (A17) *from* the CoinRun
line specifically, so partially committing to that lineage is already the de facto direction, not
a fresh fork; (3) `docs/FAITHFULNESS.md`'s own trunk lineage note (`--model_type impala`) already
follows CoinRun.

**What this does not resolve**: A17's own stated gap — `--nr-samples 12` has no equivalent in
`torch_rl` (this port draws a single VIB sample against CoinRun's multi-sample bottleneck), and
the latent dimension is this branch's 64-d against CoinRun's 256-d. Picking the lineage doesn't
manufacture the missing sampling/dimensionality parity; it commits to a stated target so any
future gap is measured against ONE reference rather than an ambiguous blend of two. Whether to
spend implementation effort closing the sampling/dimensionality gap itself is a separate, larger
question than this entry answers — recorded here as the honest boundary of what "picking a
lineage" actually settles.

**Left OWNER**: whether IBAC-SNI's competence pilot (already OWNER on `production_gates.py`, and
separately blocked on the actual production host per A1's revision) should be run against the
CoinRun-lineage target parameters specifically, once that pilot is otherwise unblocked. The lineage
choice itself is not a resource question, so it did not need to wait — only the pilot execution
does.

### A38 DECIDED, 2026-09-06 — evaluator-validation-before-fidelity-pilots sequencing, and the real cost of the schema-2 wave

Raised as an open sequencing risk in `notes/CURRENT-STATE-AND-RESPONSIBILITY.md`'s unknown-knowns
hunt: enormous infrastructure investment (evaluator-identity schema, record-delivery fix,
validation ledger) happened before A35-A37's fidelity pilots, which could change which baseline
variant is worth validating. Worked through rather than left flagged.

**The cost premise was wrong first.** Codex's quoted 4,324.32 RUB / 21h figure for the seven-family
schema-2 wave (mailbox Q43) is arithmetically correct as a worst-case ceiling (seven configs' 3h
timeouts, summed serially, at the two tiers' published rates) but is not the expected cost. Six of
the seven families already ran this exact job shape under schema 1; their real `job get` timestamps
sum to ~518.75 RUB (measured for six, one family estimated from its own separately-measured
training time), and they ran in parallel — real wall-clock was the slowest single job, ~31 minutes,
not 21 serial hours. Full derivation: `notes/claude-answers.md` A54. This matters for the
sequencing question because "wasted spend if the pilots change the recipe first" was implicitly
weighted against a ~4,300 RUB number; against the real ~520 RUB, a possible future re-validation is
not a meaningful sunk cost either way.

**The sequencing question itself**: evaluator-identity validation tests **harness correctness** —
does `eval_grid.py` read a checkpoint and compute the declared metrics correctly, using a cheap
10k-frame checkpoint only as a vehicle — not *which* hyperparameters a family should train with.
A35-A37 changing `idaac`/`ppg`/`ibac_sni`'s recipe would not falsify anything this wave measures;
at most it would require a revalidation pass later if the change touches a hashed runtime-closure
file, which the schema already demands for any future code change regardless of cause.

**The stronger argument runs the other way.** This validation effort already caught three real
bugs in the exact code path a fidelity pilot would also execute: the macOS AppleDouble sidecar leak
(CORRECTIONS #88), the alda Tensor-JSON crash (#91), and ppg's false `runtime_imports_checked`
claim (#93). Running an A35/A36/A37 pilot before this validation would have risked hitting the same
latent bugs inside a pilot run instead — worse, because a pilot burns the larger 200-300k frame
budget and confounds "the hyperparameter change did this" with "the harness was broken."

**Decision: no re-ordering.** Evaluator validation first, fidelity pilots second is kept as the
sequence — not because it already happened that way, but because the validation is a precondition
for trusting a pilot's result, not a competing use of the same budget. Submitting the v146-v152
wave is a real-money action and still needs the owner's explicit go-ahead per this project's
spend-authorization convention; this entry settles the *ordering* question, not the authorization.

### A39 DECIDED (operational), 2026-09-07 — the forced-mode pass gets NO ledger entry shape

**The question**, left open when `--policy-mode mode` was implemented: wave configs attest the
NATIVE scope only. If a forced-mode pass ever ran, would its record need its own attestation? That
is a second entry shape in `validated_evaluator_families.json`, not a flag, so it is a decision to
take deliberately rather than discover while building a cross-group table.

**The decision: no second shape. The ledger attests the native scope, and only that.**

**Why this is now the cheap answer rather than a deferral.** Two things settled it on 2026-09-07:

1. **The owner ruled the 9/3 policy-mode split acceptable and scheduled no secondary pass**
   (`notes/SAME-AXES-VERDICT.md`). A ledger shape for records nobody will produce is speculative
   machinery, and speculative machinery in the attestation path is exactly what should not exist —
   the ledger's whole value is that a reader can say what each entry certifies.
2. **`ctrl` no longer needs the pass at all.** Its native rule IS the mode, so for one of the four
   families that motivated the question, the forced pass and the native pass are the same
   measurement.

**What this costs, and how it is paid if the decision is wrong.** If a cross-block contrast ever
becomes necessary, the forced-mode records would exist without an attestation covering their
scope. That is recoverable and bounded: `evaluator_scope_revision` is already stamped on every row
and already distinguishes a `mode` scope from a `native` one — the canonicaliser admits both
(`evaluator_identity.py`, `policy_mode not in (family_eval_policy_mode(family), "mode")`). So the
evidence to build the second shape later is being recorded now, whether or not the shape exists.
Adding it later is a schema addition over records that already carry the field, not a re-run.

**What would overturn it.** A decision to report any cross-block ranking. That would make the
forced pass load-bearing, and a load-bearing measurement must be attested like any other.

**Status: OPERATIONAL DEFAULT, not ratified.** No gate reads this, nothing is removed, and
`--policy-mode mode` stays implemented and reachable. The dormancy is the decision; the capability
is retained precisely so the decision is reversible.

### A40 (new) — frame stack is inherited by OMISSION for `ctrl` and `ibac_sni`, and four of the six on-policy pairs straddle it

**Raised by the owner, 2026-09-08**, pushing back on the reviews' own disposition. The reviews are
right on the facts and I think the DECISION they reach is too weak. Review 2: *"The frame-stack
difference is more serious than the resolution difference... method identity is perfectly
confounded with observation information."* Review 20 rates it P2 and prescribes *"Keep
source-faithful primary; disclose."* That prescription assumes there is a source position to be
faithful to. **For these two baselines on this axis, there is not.**

**The state.** 10 of 12 stack three frames. `ctrl` and `ibac_sni` use one, because Procgen serves
one RGB frame and their authors never faced a task where the choice arises. `idaac` and `ppg` are
also Procgen-origin — they are at three because IDAAC's own paper ships a continuous-control (DMC)
profile that specifies it, and PPG is that paper's comparator (A36). So within the on-policy
group, two baselines got a published continuous-control recipe and two did not.

**Why "source-faithful" does not describe what we are doing here.** This project has ALREADY
authored a continuous-control adaptation for both: `runnable/ctrl/models.py:172` says it outright
— *"Categorical is upstream's exact expression; MultivariateNormalDiag is the added path."* We gave
them a Gaussian head for a 7-DoF action space their authors never targeted, because the port
demanded a decision the originals never made. Frame stack is the same class of decision on the
observation side. Keeping 1 does not preserve an authorial choice; it imports the ABSENCE of one,
and then lets the resulting velocity-blindness be read as a property of the method.

The project already recognises this exact pattern on a third axis and calls it a defect, not a
condition: `rlgen/protocol.py`'s time-limit note — nine baselines treat the limit as terminal,
*"which is right for Procgen, where episodes genuinely terminate, and wrong"* here (C1, rated the
largest comparability defect found). Three structurally identical situations, three different
treatments: action space **adapted**, time limit **declared as a defect**, frame stack **declared
as a condition**.

**What it costs, concretely.** Of the on-policy group's 6 pairs, **4 straddle the frame-stack
split**: `idaac`–`ibac_sni`, `idaac`–`ctrl`, `ppg`–`ibac_sni`, `ppg`–`ctrl`. Only `idaac`–`ppg`
(both 3) and `ibac_sni`–`ctrl` (both 1) are clean. A reader comparing `ctrl` against `idaac` cannot
separate the regulariser from the observability.

**DECISION (operational default, not ratified): keep frame_stack=1 for those two, and demote the
four straddling pairs from PRIMARY to DESCRIPTIVE.**

Same treatment the policy-mode split already gets: rank within a block, not across it. The
on-policy group's primary claims become `idaac`–`ppg` and `ibac_sni`–`ctrl`; the four cross-stack
pairs are reported with the confound named in the caption, not in an appendix.

**Why not equalise to 3 instead** — the alternative I considered and rejected, with its price:
it would need a Procgen ImpalaCNN input change for both (9 channels, the same change `idaac` and
`ppg` received), a fresh pilot for each, and it would push `ctrl`'s memory further into territory
that is *already* only a linear extrapolation (54.28 GiB at `num_envs=64`, never measured — see
`families.json`, and `family.py` already refuses to pack against an estimate). Tripling the
observation stack before that figure is measured is the wrong order of operations. Equalising is
also itself a deviation, so it does not buy fidelity — it buys comparability at the price of both
compute and a second unproven configuration.

**What would overturn this.** A measured `ctrl` 64-env memory figure with headroom, plus a decision
that the on-policy group's cross-stack comparisons are load-bearing for the paper's claim. Then
equalising to 3 becomes worth its pilot cost.

**Status: OPERATIONAL DEFAULT.** No gate reads this, and A25's primary set is prose rather than
code, so this changes what is CLAIMED, not what is computed. The demotion is the substantive part
and it costs no compute — which is why it should happen before results exist rather than after
someone reads a cross-stack ranking.


### A40 REVISED, 2026-09-08 — the source evidence reverses half of it: `ibac_sni` should stack 3, `ctrl` should not

**A40 above is superseded in its conclusion and in its costing.** Both corrections came from being
pushed on it: the owner questioned the stated cost, and `notes/ai-help-26-external.md` supplied
source evidence I did not have. What follows is checked against our own vendored tree.

**Correction 1 — the cost was overstated.** A40 said equalising needs "an ImpalaCNN input change
for both". Wrong:

- `ppg` already runs `frame_stack=3` on an ImpalaCNN whose input channels are shape-derived
  (`phasic_policy_gradient/impala_cnn.py`, `curshape[0]`). A frame-stacked ImpalaCNN is not
  hypothetical here; it is already running.
- `ctrl` uses Flax `nn.Conv` (`runnable/ctrl/models.py:35,61`), which infers input channels. **No
  channel change at all.**
- `ibac_sni` is the only one with a hardcoded literal: `torch_rl/model.py:62`,
  `nn.Conv2d(3, 32, (2, 2))` -> 9. **One number.**

**Correction 2 — and it reverses the decision for `ibac_sni`.** A40 argued single-frame was
"inherited by omission". For `ibac_sni` the truth is stronger and points the other way: its authors
made single-frame *conditional on something Door does not provide*.
`runnable/ibac_sni/coinrun/coinrun/config.py:140`, directly above `frame_stack` defaulting to 1:

> "No frame stack is necessary if PAINT_VEL_INFO = 1"

and `config.py:110` smart-defaults `PAINT_VEL_INFO` to 1 for `GAME_TYPE == 'standard'` (CoinRun,
their benchmark, `config.py:77`), with no override in their run scripts. **CoinRun paints the
agent's velocity into the pixels.** Door does not paint anything. So running `ibac_sni` at
`frame_stack=1` on Door does not preserve their design — it removes the velocity channel their
design explicitly relies on, and then reads the resulting handicap as a property of VIB+SNI.

**`ctrl` is NOT the same case, and `ai-help-26` gets this one wrong.** It groups both as
"deliberately one frame, with velocity painted". `ctrl`'s wrapper *default* is
`paint_vel_info=True` (`runnable/ctrl/vec_env.py:23`) — but its own trainer overrides it:
`runnable/ctrl/train_ppo.py:160` passes `paint_vel_info=False`. CTRL therefore trained
single-frame **without** painted velocity. Velocity-blindness was its actual operating condition,
so keeping `frame_stack=1` for `ctrl` is faithful, and changing it would be our deviation.

**DECISION (operational default, not ratified):**

| baseline | frame stack | why |
|---|---|---|
| `ibac_sni` | **1 -> 3** | its authors' stated precondition for 1 (painted velocity) is unmet on Door; 3 restores what they assumed, and is the faithful port |
| `ctrl` | **1, unchanged** | trained at 1 with `paint_vel_info=False`; 1 is its real condition |

**What this buys.** `ibac_sni` at 3 becomes block-compatible with `idaac` and `ppg` (same stack,
same `sample` policy mode, same terminal time-limit handling), so the on-policy group's primary
pairs go from **1** (`idaac`-`ppg` alone) to **3**. That is a real gain in claimable science for
one changed literal plus a pilot. `ctrl` remains a singleton block and is honestly reported as
having no primary comparison.

**Sequencing — this does NOT happen now.** `frame_stack` lives in `families.json`, a
`CONFIG_MEMBER`, so changing it moves every family's evaluator revision and would invalidate the
v196 wave that is running as this is written. It also changes learning, so it needs its own pilot,
and `ctrl`'s 64-env memory is still an unmeasured extrapolation. Order: finish the wave, then the
`ibac_sni` change plus a pilot, then re-attest `ibac_sni` only.

**What would overturn it.** Evidence that Door's observation already carries velocity (it does
not — no painting exists in robosuite), or a decision that `ibac_sni`'s published CoinRun numbers
must remain comparable to ours, which they are not in any case (different task, different action
space, authored Gaussian head).
