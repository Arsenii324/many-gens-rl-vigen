# If production goes wrong, which judgement was it?

Nine gates read OWNER. Each is a decision taken to the best available reasoning and **deliberately
not closed in code**, so that it stays visible if the fleet's results look wrong. Leaving a
decision open is only useful if someone can act on it later, which needs three things per row: the
symptom that would indict it, the cheapest test that settles it, and what it costs to change.

That is what this page is. It is written **before** any production result exists, so that no
symptom gets matched to a convenient explanation after the fact.

**How to use it.** Something looks wrong in the fleet's numbers. Find the symptom below, run the
named test, and it either indicts the judgement or clears it. If nothing here matches, the cause is
not one of the nine open decisions and the fault is elsewhere — which is itself worth knowing.

---

## 1. `ibac_sni competence`

**The judgement.** `--beta 1e-4` with `procs=16` is admissible on the strength of a spawn/EGL
smoke plus a historical 25k `procs=1` cell in which `entropy_coef=0` removed a runaway. Runnability
is proven; competence at the exact production settings is not.

**Symptom that would indict it.** `ibac_sni` returns sit at or below the random floor (1.842 on
Door, C55) across all three seeds, or its losses are non-finite, or its action diagnostics show a
collapsed or saturated policy.

**Cheapest test.** One `procs=16` cell at the production settings, long enough to show a rising
train-regime return rather than merely the absence of an explosion. Read the curve records, not the
endpoint. Predefine the criterion as *non-degenerate learning* — finite losses, non-collapsed
action distribution, some separation from the floor — **not** a target score. A method that is
faithfully implemented and simply performs badly is a result, not a defect.

**Cost of changing later.** Re-running `ibac_sni`'s three seeds only. It shares no closure member
with the other eleven, so nothing else is invalidated.

## 2. `shared evaluator validated`

**The judgement.** A family counts as validated when one cell of it completes end to end under the
current closure and its record's `evaluator_revision` equals the live one.

**Symptom.** Any record whose `evaluator_revision` does not match the tree that reported it; two
seeds in one row carrying different closures; a family attested through a baseline that does not
exercise the paths production uses (the v194 lesson: `drqv2` and `rad` never touch Places365, so
attesting through them says nothing about `svea`/`sgqn`/`soda`).

**Cheapest test.** `python3 scripts/production_gates.py` for the headline, then
`python3 scripts/audit_row_closure.py --strict`, which refuses a row pooling two closures.

**Cost of changing later.** One short wave per affected family. Cheap, and the reason the rule
"once a wave starts, no closure member changes" exists — breaking it cost a whole generation on
2026-09-07.

## 3. `estimands frozen`

**The judgement.** Time-limit handling splits 3 bootstrap / 9 terminal, declared rather than
equalised; retention is reported with the random floor subtracted, because a raw return ratio is
not invariant to reward offsets and Door's reward has a non-zero floor.

**Symptom.** Retention values clustering suspiciously near 1.0; a bootstrap-handling baseline
ranking anomalously against terminal-handling ones specifically on the longest episodes; two
baselines with near-identical raw returns showing very different retention.

**Cheapest test.** `python3 scripts/audit_comparability_seam.py --host-profile v100` and read the
time-limit axis; then recompute retention with and without the floor subtraction and see whether
the ordering moves. If it does, the floor treatment is load-bearing and must be stated in the
caption, not the appendix.

**Cost of changing later.** None to the runs — this is an analysis-time choice over records that
already carry everything needed. Recompute and restate.

## 4. `seed policy frozen`

**The judgement.** Fixed n=3 per reported row, allocated in advance, with no outcome-dependent
addition of seeds.

**Symptom.** Any request to "add a seed" to a cell whose result was surprising. That request is the
symptom; the harm is the selection it introduces, and it does not show up in the numbers.

**Cheapest test.** Not a test — a rule. If a seed is added, it must be added to **every** cell in
the comparison, and the fact recorded. `scripts/audit_row_closure.py` shows what each row actually
pooled.

**Cost of changing later.** Linear in the fleet: one extra seed across twelve baselines is roughly
a third of the campaign again. This is the expensive one to reopen, which is why it is fixed in
advance.

## 5. `production canary`

**The judgement.** The first production DrQ-v2 seed *is* the canary and counts as that seed, if the
whole chain completes under the frozen tree.

**Symptom.** Anything that only appears after hours: disk exhaustion, a checkpoint that does not
reload in a fresh process, a packaging step that truncates, replay that does not fit, an endpoint
grid that never runs because training consumed the wall clock.

**Cheapest test.** The canary itself, read as a *chain* rather than a score: train → durable
intermediate checkpoints → terminal checkpoint → package and retrieve → **reload in a fresh
process** → full endpoint grid → curve records → normalization → delivery classification. A 10k
smoke re-tests none of the parts that only fail after hours.

**Cost of changing later.** If the canary fails, whatever it reveals is a defect to fix, and its
seed is re-run. If it passes, it is a production seed and cost nothing extra.

## 6. `external RL-ViGen anchor`

**The judgement.** RL-ViGen's own published Door table (drqv2 eval-easy 3.6 across seeds
{3,7,4,3,1}, range 1–7, RETURNS not success rates) is the external anchor, and the criterion —
fixed before the fleet runs — is that our drqv2 seeds fall **inside that published range**, not
that they reproduce 3.6.

**Symptom.** Our drqv2 seeds falling outside 1–7 on eval-easy.

**Cheapest test.** Free: read it off the drqv2 seeds the fleet produces anyway. Nothing extra is
scheduled for it.

**Cost of changing later.** None. But note what a miss would mean: two of RL-ViGen's own three
comparison methods (CURL 6.6, DrQ 14.0) do not reproduce 3.6 either, and a random policy alone can
reach 6.93 on our floor measurement — so a value inside the range is weak evidence of correctness,
and a value outside it is strong evidence of a problem. Asymmetric on purpose.

## 7. `checkpoint rule frozen`

**The judgement.** Endpoint-as-headline; the trajectory is descriptive; there is no selected-best
column.

**Symptom.** A baseline whose curve peaks well before the endpoint and declines — under this rule
it is reported at its (worse) endpoint, and someone will want to report its peak instead.

**Cheapest test.** The curve records already show it. Look at whether any baseline's endpoint sits
far below its own maximum.

**Cost of changing later.** A selected-best column cannot be added honestly after the fact: it
needs **reserved validation episodes** the current protocol does not collect, equal candidate
opportunity across methods, and a per-seed vs per-method choice made in advance. Adding it later
means re-running the evaluation grid with reserved episodes. This is the row most likely to be
argued about after seeing results, which is exactly why it is fixed now.

## 8. `production renderer verified`

**The judgement.** The production host is a V100 with Docker and a Linux environment of our
choosing, so renderer parity is tractable by construction: build the image to match the renderer
validated here (`MUJOCO_GL=egl`), pin its digest into `source-lock.json`, and reproduce one known
cell.

**Symptom.** The same checkpoint scoring differently on the production host than here. The
project's own history has a same-checkpoint discrepancy of roughly 131.5 versus 13.85 under a
renderer/platform change, so this is not hypothetical.

**Cheapest test.** The three-step probe, in this order, because it is the only order that does not
confound: (a) re-measure a retained checkpoint **here**, on the CURRENT evaluator → R_A; (b)
measure the same checkpoint, evaluator and container **on the production host** → R_B; (c) compare.
Platform is then the only changed factor. Do **not** compare against the archived drqv2 100k 480.6
— that number predates per-episode condition seeding, deterministic kernels and strict regime
verification, so a mismatch would confound renderer with evaluator revision, which is the one thing
the probe exists to separate. Cheaper still as a first cut: render a few fixed-seed observations on
both hosts and compare them directly, which localizes a mismatch to the renderer before any policy
is blamed.

**Cost of changing later.** Catastrophic if skipped and wrong: the checkpoints would survive a
renderer mismatch but **every number computed from them would not**. Do it before the fleet.

## 9. `production scope frozen (Door / +Lift)`

**The judgement.** Door alone for this production run; Lift is a stated follow-on, not co-equal
scope.

**Symptom.** A reviewer asking for a second task to support a generalization claim — a reasonable
ask this fleet cannot answer.

**Cheapest test.** None needed; the constraint is known. Adding Lift means re-deriving every
constant for it: its own random floor (6.562 exists but only over 25 episodes against Door's 200),
its own certified scene set, its own horizon, and its own published-anchor relationship — which is
already flagged as an unexplained anomaly Door does not share
(`notes/faithfulness-reconciliation.md`).

**Cost of changing later.** A second full campaign, plus the re-derivation above. The honest
framing in the write-up is one task, deliberately, with the constants that task required.

---

## Frame stack — CLOSED, and the axis is gone (A40 REVISED-2, implemented 2026-09-08)

**Superseded.** This section used to record the judgement that `ctrl` and `ibac_sni` stay at
`frame_stack=1` and that the four straddling on-policy pairs are demoted to descriptive. Both
baselines now stack 3, the split is 12/0, and `scripts/comparison_blocks.py` reports **3 primary
on-policy pairs instead of 1**. Nothing here is an open decision any more; it is kept because the
reasoning is the template for the axes that remain open.

**Why it moved.** Single-frame was never either method's decision. It is Procgen's environment
convention: CoinRun paints velocity into the observation (`config.py:140` — *"No frame stack is
necessary if PAINT_VEL_INFO = 1"*), and CTRL's clustering objective operates over rollout
timesteps (`algo.py:90,539`), not stacked channels. Neither condition survives the move to Door,
where both policies were simply velocity-blind.

**What it cost, against three wrong estimates.** Not "one channel literal", not "a literal plus a
config value": **neither baseline had any stacking mechanism at all** on the Door path. Both stacks
are authored, plus a preprocessor gate that demanded exactly 3 channels, plus a trunk whose input
width was hardcoded. The estimate was only corrected by tracing the path — three times.

**The symptom that would still indict the new value.** `ctrl` or `ibac_sni` diverging or collapsing
where they previously merely underperformed, or either failing the runtime geometry assertion.
Both now run authored code on a path that has never trained with it.

**Cheapest test, and it is required before three production seeds:** one short cell each, read for
non-degenerate learning rather than a score. A43 fixes the disambiguation in advance, because
`ibac_sni` changed twice: **revert its `lr` first** (a one-line config revert) and re-pilot; if the
failure survives that, it is the stack.

**Cost of changing back.** `families.json` and `rlgen/protocol.py` for the declaration, and the
clone patches for the code. Cheap in code and expensive in claims: reverting returns the on-policy
group to 1 primary pair.

## The one that is not on this list

**R3, `metrics on the same axes`, reads NOT MET and is not an OWNER gate — it is a stated research
limitation.** The evaluation-policy-mode axis splits 9 deterministic / 3 sampling. The owner has
ruled that this is acceptable because each family's rule is its own published one, and that ruling
is recorded in `notes/SAME-AXES-VERDICT.md` together with the per-family verification it depends
on and the one family (`ppg`) where that verification is weakest. The consequence is decided in
advance: rank within a block, never across, and say so in the caption.

If cross-block numbers are ever needed, the deterministic secondary pass exists
(`--policy-mode mode`, implemented and reachable for the three sampling families) at about 3% of
campaign cost. It is deliberately not scheduled.
