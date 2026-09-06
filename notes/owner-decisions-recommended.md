# Current ratification batch — 2026-09-06 (read this section first)

Everything below this line is the 2026-09-05 document, unedited. It is **not** superseded wholesale
— §3 (estimands), §4 (seed policy), §5 (canary), and the later revisions are still this project's
live reasoning and are folded into the table below by reference rather than repeated. §1 (IBAC-SNI)
and §2 (shared evaluator validation) **are** stale: both predate CORRECTIONS #97 (the `door.xml`
evaluator-identity bug and its fix), the resulting schema-2 rework (`C96`), and the seven-family
`v170` re-validation wave — re-read those two sections as history, not as the current ask.

This batch exists because the recommended defaults below have sat written-but-unratified across
several sessions; it is the presentation pass this project's own plan calls for, not new analysis.
Full reasoning for each row lives at the cited location — this table is a pointer, not a summary
that could drift from it.

| # | item | recommended default | status | where |
|---|---|---|---|---|
| 1 | estimands frozen | declare-and-quantify the time-limit split (3 bootstrap/9 terminal, no direction claimed); retention as a floor-adjusted ratio, never raw | ratify | DECISION-SHEET A4/A5/A18; §3 below |
| 2 | seed policy frozen | fixed n=3 per reported row, no outcome-adaptive allocation | ratify | DECISION-SHEET A6/A28; §4 below |
| 3 | checkpoint rule frozen | endpoint-as-headline, trajectory descriptive, no selected-best column | ratify | DECISION-SHEET A7 |
| 4 | production scope frozen | Door alone; Lift a stated follow-on, not co-equal | ratify | DECISION-SHEET A33 |
| 5 | external RL-ViGen anchor | fleet's own drqv2 seeds falling inside RL-ViGen's published range (1–7) is the anchor; free, checked once production drqv2 seeds exist | ratify the criterion now, check later | DECISION-SHEET A9 |
| 6 | competence threshold | `MIN_DENOM_SUCCESS = 0.25`; OOD uses the same value, not a separate one | ratify | `scripts/regime_retention_report.py` |
| 7 | checkpoint storage vs. real disk | 35.5 GB projected (12 baselines × 3 seeds × 13 stamps) never confirmed against the actual production host's free disk — only against this laptop's 73.1 GB | needs one number from the real host | `plan_production.py::checkpoint_storage_gb` |
| 8 | scene comparisons unpaired (A21) | keep; state per-scene numbers as "scene+placement," not "scene" | ratify | DECISION-SHEET A21 |
| 9 | Places365 trains on validation split, not train (A22) | keep; declare in `CLAIMS-LEDGER.md`; external review 18 dissents (prefers reverting to train for max fidelity) — noted, not applied | ratify or override | DECISION-SHEET A22 |
| 10 | missing-run policy (A24) | rerun crashed seeds under the identical seed; no post-hoc replacement seeds; drop missing scenes rather than impute; report a method missing a seed at n=2, labelled | sign-off only — already merged into `EVAL-PROTOCOL.md` | DECISION-SHEET A24 |
| 11 | 66→25 primary comparisons (A25) | group by algorithmic mechanism, not source repository; full 66-matrix + all raw data remain computable regardless | ratify (presentation-only, changes nothing collected) | DECISION-SHEET A25 |
| 12 | `drq`/`dmc_gb` alpha dtype (C4) | declare the float32-vs-float64 asymmetry, don't harmonise | ratify | `docs/CONSTRUCTION.md#c4` |
| 13 | six baselines with no persisted training-observation record (C58) | declare as a per-family evidence-availability limitation in `CLAIMS-LEDGER.md`; don't build new logging pre-production | ratify or override | `docs/CONSTRUCTION.md#c58` |
| 14 | `ctrl`'s parameters match official code, not the paper table (C97, new 2026-09-06) | declare the paper↔code conflict; keep official-code production values; run the paper-table variant as a declared second arm only in the final frozen wave, not reactively | ratify | `docs/CONSTRUCTION.md#c97` |
| 15 | production canary order and design | `soda` at full 6e5, one seed, through the entire pipeline; predeclared abort condition (exceeds wall-clock ceiling or is killed → stop and re-plan, never silently retry) | ratify | §5 below |

Two items from §1/§2 below still need a fresh ask, restated for the current tree rather than
answered as originally written:

- **IBAC-SNI competence** — §1's entropy-coefficient pilot logic and predeclared criteria (the
  redesigned, differential version near the end of this file) still hold; what changed is that the
  *real* competence pilot needs `procs=16` at the final process geometry on the production host, per
  this session's later plan — §1's 100k pilot is a cheaper, still-valid precursor, not a
  replacement for it.
- **Shared evaluator validation** — §2's "confounded instrument, discharge on production
  checkpoints" reasoning is superseded by CORRECTIONS #97/`C96`: the ledger schema itself was
  rebuilt (family-specific static closures, canonical scope revisions), and the live count is 0/7
  validated on the *current* closure (six families' `v170` re-validation succeeded functionally;
  `ctrl` failed at the DataSphere platform level, under separate investigation). The actual open
  ask is Q47's governing rule: one final validation wave against the genuinely frozen tree, not
  iteratively — nothing for the owner to ratify here beyond that sequencing, which is already
  agreed.

---

# The five decisions that are yours — with a researched default for each

Written 2026-09-05, after both external reviews and the gate pass (`scripts/production_gates.py`).
Every recommendation below is argued from evidence in this tree, and each states what would falsify
it. **None is applied.** They are defaults awaiting a yes, which is not the same as settled.

Ordering principle used throughout: this project's stated priorities — fidelity to the null (each
repository running its own `train.py`), duplication-free, honest claims over convenient ones, and a
deliverable that a supervisor can read without being misled.

---

## 1. IBAC-SNI competence — **run one 100k pilot at the exact final configuration**

**The situation.** `entropy_coef=0` demonstrably removes the σ runaway: log_std flat at 0.033 over
25k where the 0.01 control reached 0.538 at the same frame. But the replacement configuration has
~25k frames of evidence, a noisy windowed return hint (17.78 and 11.04 against the 1.82 floor), and
**zero success events**. Absence of explosion is not evidence of learning.

**Recommendation: pilot at 100,000 frames, one seed, at the exact intended settings** — impala head,
`entropy_coef=0`, β=1.0, `sni_type vib`, `use_bottleneck`, the production observation geometry.

**Why 100k specifically, and why it is nearly free.** We already hold the 0.01 control *at exactly
100k* (`bt1i1s0j8qhbal67gjnn`). Choosing any other budget throws that comparison away; choosing 100k
buys a like-for-like contrast for the price of one cell. At ibac_sni's measured throughput this is
roughly one job-hour.

**Predeclare the decision rule**, so the pilot cannot be read after the fact:

> Include `ibac_sni` in the ranked table if the pilot shows **either** any success events, **or** a
> train-regime return clearly above the 1.82 floor with a stable policy scale. Otherwise report it
> as a floor row with the mechanism explained, and exclude it from ranking claims.

**What would change this:** if you would rather not spend a cell, the honest alternative is to run
production and report `ibac_sni` as a floor row regardless — but then the entropy deviation buys
nothing, and holding 0.01 would be more faithful.

---

## 2. Shared evaluator validation — **fix the confound first, then discharge on production checkpoints**

**The situation.** [Corrected 2026-09-05: **zero** burdens are discharged under the current
evaluator revision; drqv2 was exempted by inattention rather than argument, since the reasons
for suspending idaac's are family-agnostic.] As written: 2 of 12 burdens are discharged. It is tempting to spend pre-production compute
discharging the other ten. I recommend against that, for two reasons found in this tree.

**First, the instrument is currently confounded.** `torch.use_deterministic_algorithms(True)` is
enforced **only** in `eval_across_scenes.py:110`, not in the seven-family grid. Door's success is
threshold-sensitive — that is why [C70](../docs/CONSTRUCTION.md#c70) added the call. So part of any
disagreement `audit_shared_evaluator.py` reports may be nondeterminism rather than a real
difference. **Discharging burdens with a confounded instrument produces confident wrong answers.**

**Second, a burden cannot be discharged on a floored policy.** Agreement between two numbers that
both straddle the 1.82 floor is not agreement about anything — the register already records exactly
this for one comparison. At 10k every baseline is floored, so pre-production discharge attempts are
mostly unbuyable.

**Recommendation, in this order:** (a) equalise determinism across both evaluators; (b) discharge
each burden **on that baseline's production endpoint checkpoint**, which is competent by
construction if the budget is right; (c) publish no ranked claim for a baseline whose burden is
still undischarged, and say so in the row rather than in a footnote.

This costs no extra compute — the production run creates the competent policies anyway.

---

## 3. Estimands — **freeze three, and stop trying to compress them into one ratio**

Three separate decisions travel together here.

### 3a. P-C76 / what retention is measured over

The second review is right that there are three different questions, and the grid already collects
enough per-scene data to answer all three:

| | question | denominator | numerator |
|---|---|---|---|
| **A** | appearance robustness on trained geometry | scene 0, train appearance | scene 0, randomised appearance |
| **B** | appearance robustness, geometry held fixed | scene *s*, train appearance | scene *s*, randomised appearance, aggregated over *s* |
| **C** | joint appearance + scene shift | scene 0, train appearance | all scenes, randomised appearance |

**Recommendation: report all three; make B the headline.** The project's research question is
*visual* generalisation, and **B is the only one that isolates it** — it varies appearance with
geometry held fixed, then aggregates the within-scene effect. A is B's special case at *s*=0. C
conflates appearance shift with geometry shift and is the one most likely to be misread, because a
scene-0 denominator against a ten-scene numerator *sounds* like A while measuring C.

This also dissolves R3 as a blocker: R3 fails because one UNITS axis disagrees, and reporting the
estimands separately removes the need to pick one.

### 3b. Time-limit semantics (3 bootstrap / 9 terminal — verified exactly)

Harmonising means editing either three clones or nine, which the null forbids. **Recommendation:
declare the difference; do NOT state a direction.** On Door every episode ends by time limit, so
the treatment matters for all twelve — but which treatment is *correct* depends on what the
500-step horizon means, and that is a modelling choice the benchmark does not settle. If the
horizon defines a finite-horizon episodic task, zeroing the value target at the endpoint is the
coherent treatment; if it is an artificial truncation of a continuing MDP, bootstrapping is. Since
evaluation is itself a fixed 500-step episodic score, the finite-horizon reading is at least as
defensible.

**[Corrected 2026-09-05, external review 7.]** This paragraph previously read that the nine "are
systematically disadvantaged in value estimation, and the three that bootstrap are the ones doing
it correctly." That is a directional judgement and no controlled ablation supports it. The
defensible sentence is: *methods retain their native time-limit semantics; three bootstrap and nine
terminate, so their learning targets differ near the horizon.* The difference still belongs in the
caption, and it is still a reason the twelve-way comparison carries Tier-2 language (see §5).

### 3c. The retention metric itself

A raw return ratio is **not invariant to reward offsets**, and Door's reward is dense, shaped, and
has a non-zero floor — so a constant shaping offset moves "retention" without any behavioural
change. The competence gate stops the worst pathology but not this one.

**Recommendation:** **success rate is the headline** — offset-invariant and behaviourally meaningful.
Report dense return alongside it, and where a dense ratio is wanted use the **floor-adjusted** form

    (R_eval − R_floor) / (R_train − R_floor),        R_floor = 1.82 (C55)

applied only where the denominator is safely above floor. This matches your "try all" instruction
while making the headline the quantity that survives scrutiny.

---

## 4. Seed policy — **fixed three for every reported row, predeclared**

**The adaptive allocation was my default and it was wrong.** "One seed everywhere, then concentrate
seeds where the comparison is live" is outcome-dependent sampling: a method with an unlucky first
seed is classified floor and never earns the trials that would have corrected it.

**Recommendation: a fixed minimum of three training seeds for every row that appears in the main
comparison, decided now and not revisited after seeing results.** Five would be better for ranking
and is not affordable — 6e5 × 5 would be ~853 job-hours against 512 — so the honest move is to keep
three and **weaken the claim to match**, rather than keep the claim and hope.

With n=3: report intervals and effect sizes, not p-values; make the **training seed the outer unit**
(not the 600 episode rows, which are clustered by seed and scene); and exploit the C69 pairing —
every baseline sees identical placements, so cross-baseline comparisons should be **paired**, which
is where the usable precision actually lives. Full detail in
`notes/proposal-inference-and-checkpoint-selection.md`.

An exploratory single seed remains fine for screening engineering viability. It must never be
substituted into the final table.

---

## 5. Production canary — **make the canary a real production cell: `soda`, 6e5, one seed**

**The situation.** The full shape — train → checkpoint → clean reload → offline grid → records →
statistics — has never run end to end at production length. The longest real cell so far is 5.1 h;
a 6e5 `soda` cell is projected at **45 h**. Wall-clock ceiling, memory at length, and concurrent
checkpoint writes are all unknown at that scale, and `alda` has already been killed by a tier
ceiling the cost model had predicted.

**Recommendation: run `soda` at the full 6e5, one seed, through the entire pipeline, as the canary.**

The reason to choose `soda` is that it is the **worst case on the axis that is actually unknown** —
45 projected job-hours, the longest cell in the fleet. If it survives, the envelope is proven for
everything else. And the reason this is the cheap option rather than the expensive one: **a canary
that passes is not overhead — it is seed 1 of `soda`**, a real production row. It only costs
anything if it fails, which is precisely when you want to have spent it.

Pair it with `ctrl` at 6e5 only if you want the JAX runtime de-risked at length too (~17 h); the two
together are ~12% of the fleet cost.

**Predeclare the abort condition:** if the canary exceeds the platform wall-clock ceiling, or is
killed, production stops and the shape is re-planned rather than retried. Silently retrying a failed
seed would create survivorship bias.

---

## What I would do with the answers

Given yes on all five, the launch order is: equalise determinism → freeze the estimands and seed
policy in one immutable manifest → ibac_sni pilot and `soda` canary in parallel → then the fleet.
The two port gates (`ppg` KL, and whether `idaac`'s repaired `level_seed` needs a rerun of anything
already measured) are separate and also yours; both are demonstrated in
`tests/test_port_semantics_defects.py`.

---

# Revisions after the third external review (2026-09-05)

That review read this document and the inference proposal and corrected both. Where it changed a
recommendation above, the change is here rather than silently edited in.

### §3c superseded — retention is demoted below a *difference*

I recommended success rate as headline plus a floor-adjusted retention. Keep the first; demote the
second. **Primary: `R_train`, `R_OOD`, `Δ = R_OOD − R_train`, and success rate.** Retention as a
ratio is **secondary and only for competent baselines**. A difference has no denominator, so it
cannot explode near the floor, and a failed agent reads as a failed agent instead of producing an
interesting-looking percentage. If a log-ratio is used anywhere, the rule for zero or non-positive
returns must be stated — "use the log scale" is not a specification.

### §1 gains a predeclared number

The competence gate said "not distinguishable from the floor", which is undefined and contradicts
the no-p-values rule. **Recommended concrete form:** competent if the per-seed mean return exceeds
`1.82 + δ` in **at least 2 of 3 seeds**, with `δ` fixed before the fleet runs. Raw train and OOD
scores are always reported regardless; suppressing a *ratio* must never look like suppressing a
*result*.

### New requirement, cheap and I endorse it: record the placement

Every episode row should carry an `eval_episode_id` **and a hash of the realized initial Door
placement**. Pairing then becomes *auditable* rather than inferred from RNG theory, stream
divergence becomes detectable the moment it happens, and reanalysis can pair episodes without
reconstructing RNG state. This project has already had one RNG-stream asymmetry; this is the
instrument that would have caught it immediately.

### ALDA — the tier diagnosis and evaluator coverage are confirmed

`bt1s7mph7hp31qcr1ilb` **completed on gt4i.1**, peaking at **14.73 GiB** against gt4.1's 14.5 GiB
usable. That is the diagnosis confirmed to within a quarter of a gigabyte: the earlier SIGKILL was
the tier ceiling, not a dependency fault. **ALDA must be pinned to `gt4i.1` in the production
schedule.**

The follow-up cadence probe `bt1gio1ng14k4o94dpie` completed successfully with stamps at 2,500,
5,000 and 7,500 and 15 returned records. `run_scene_alda` is therefore exercised on real
checkpoints and family coverage is **7/7**. The earlier no-stamp result remains useful as the
failure record that motivated the corrected ALDA cadence descriptor; it is no longer an open gap.

**And the class-level fix the reviewer proposes is right:** encode a scheduler invariant —
*requested RAM ≥ measured fixed peak + explicit margin* — so a tier that cannot fit a family fails
at submission time instead of relying on someone noticing that the cost model and the production
schedule disagree. The data to enforce it already exists (`ALDA_FIXED_GIB`, the tier table's
`usable_ram_gib`, and now a measured 14.73 GiB peak).

### What did not change

The IBAC-SNI pilot recommendation (§1) is unchanged and the third review independently reaches it:
`0.01 ⇒ runaway` and `0.0 ⇒ scale controlled` are established; `0.0 ⇒ learns Door` is not, and those
are different claims. It also **drops** the VIB-vs-update-count ablation as a production blocker,
agreeing that state-independent `log_std` makes the entropy term degenerate — so `entropy_coef=0`
removes less of IBAC than its name suggests. That ablation stays worthwhile and stops being a gate.

---

# A1 redesigned (2026-09-05) — the criterion must be differential, not absolute

**The flaw in what I first proposed.** My rule was *"include `ibac_sni` if the pilot shows any
success events, or a train-regime return clearly above the 1.82 floor"*. That rule cannot do its
job: if the pilot returns neither, the result is equally consistent with **"the configuration is
broken"** and with **"100k frames is far too short for an on-policy PPO method on Door"** — and the
second is the more likely reading. `drqv2` reaches train success 1.00 by ~75k, but it is off-policy
and sample-efficient; `ibac_sni` is on-policy PPO on a single 64×64 frame, and its Procgen-lineage
relatives are tuned for millions of frames. An absolute threshold at 100k tests the budget, not the
fix.

**The redesign: compare against the control we already own, at the same budget.**

We hold the `entropy_coef=0.01` run at **exactly 100k** (`bt1i1s0j8qhbal67gjnn`). So the pilot's
question is not *"did it solve Door?"* but *"did changing the coefficient change the trajectory?"* —
which is answerable at 100k precisely because the comparison is like-for-like.

**Predeclared criterion, all three read against the control:**

1. **Policy scale stays controlled** — `mean_log_std` flat rather than the control's monotone
   0.0026 → 1.4472. *(Already established at 25k; the pilot extends it to 100k.)*
2. **Train-regime return shows a positive trend** where the control showed none (it sat at 2–4
   throughout while its entropy climbed 9.95 → 20.03).
3. **Any success events at all** — a bonus, not a requirement.

**Decision rule:**

- **(1) and (2) hold** → `ibac_sni` enters the fleet. Report it honestly, including the possibility
  of a floor-level eval score, which is what RL-ViGen's *own published* DrQ-v2, CURL and DrQ do on
  Door (3.6, 6.6, 14.0 against a 1.82 floor). A floor eval number is a publishable result here, not
  a defect.
- **(1) holds, (2) does not** → the fix stopped the runaway but did not produce learning. That is
  the case for the mechanistic ablation (0.01 with the bottleneck off) before spending three
  production seeds — or for holding 0.01 and reporting `ibac_sni` as a faithful floor row.
- **(1) fails** → the diagnosis is wrong and nothing should be spent on the fleet for this baseline
  until it is understood.

**What this explicitly does NOT test:** whether `ibac_sni` can solve Door at 6e5. That is a
production question the production run answers. Conflating it with the pilot is what made the first
version of this rule unfalsifiable.
