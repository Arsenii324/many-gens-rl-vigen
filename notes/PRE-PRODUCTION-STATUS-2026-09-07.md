# Pre-production status, 2026-09-07 — what is finished, what is not, and what "not" costs

> **Current superseding update, 2026-09-07:** runtime geometry certification landed in `b19d12c`.
> This intentionally supersedes the v185 evaluator attestations; the v186 seven-family wave is
> in flight, so the v185 33-pass statement below is historical until v186 is reviewed.

> **Superseding update:** A36 is now resolved: the operational PPG default is 1 process ×
> 2048 steps, chosen after the matched 1×2048 / 8×256 gt4i.1 probe. The final seven-family
> evaluator wave has completed successfully against the resulting tree: all seven endpoint
> artifacts were returned, structurally checked, copied into `results/validation/`, and entered
> into the ledger. The live gate now accepts **7/7 current evaluator attestations**. The old
> A36/wave wording below is retained as a dated historical snapshot, not current state.

Written to answer one question directly: **can the 36-cell production fleet be released?** No, and
this page says exactly why, with the evidence for each item rather than a status word.

`scripts/production_gates.py` reads **33 pass / 0 fail / 8 owner**. "No mechanical failures remain"
is a true statement about the instruments and a misleading one about readiness, which is why this
page exists beside it.

## Historical snapshot before the A36 decision (2026-09-07, late)

**One blocker left, and its evidence is in hand.** Codex's PPG geometry probe
`bt1hoiefp159flmrv7hj` (1x2048, 65,536 frames = one auxiliary cycle) completed SUCCESS, and it ran
the matched 8x256 control on the same tier, which removes the gt4i.1-vs-gt4.1 confound that would
otherwise have decided the question on the tier rather than the geometry. **What remains is reading
the two arms and deciding A36**, then freezing and running ONE validation wave covering all seven
families.

Everything else on this page is unchanged and still true. Since it was written, recommendation 22
was audited (thirteen of sixteen requirements met; the three that were not are fixed) and four
launch surfaces were reconciled with the practice settled that day -- including one wrong number,
the campaign budget, which lacked the deterministic second endpoint pass and moves 876 -> 893 GPU-h.

## One decision has a deadline, and it is the only one that does

**Places365 (A22) must be settled BEFORE the payload freeze, not with the other ratifications.**
Every other open item changes a status; this one changes what `svea`, `sgqn` and `soda` train
against. My own cost figure for it was wrong: I priced the upstream train split at 105 GB, and the
canonical DMC-GB asset is `places365standard_easyformat.tar` at **~21 GB**, same 256x256 per-image
shape as the validation pool now shipped. Both legs the decision stood on are gone — the ordering
argument was withdrawn earlier the same day, and the cost argument is void. Adopting it after the
freeze costs a payload, a wave and nine reruns; before it, a download.

## The short answer

Three things block release, and they are different in kind:

1. **One source decision must close before the evaluator closure can be frozen** — A36's geometry,
   whose probe and control have both now run; down from two:
   the policy-mode override landed the same day it was found. Until A36's geometry answer arrives, a
   validation wave would have to be re-run, so no wave should be run. **All seven attestations are
   now superseded**, not two, because the policy-mode change touches the shared evaluator; that does
   not change the plan, since one wave covers seven families either way.
2. **Four things need the production host**, which no agent here can reach. They are ordered and
   commanded in `RUNNING-ON-PRODUCTION-HOST.md` §0 and `MIGRATION-T4-TO-V100.md`.
3. **Seven decisions need the owner's ratification.** Each already has an implemented default that
   the code runs today; ratification changes their formal status, not the fleet's behaviour.

## 1. The freeze blockers — two, and both are ours

| item | what is open | why it blocks the freeze |
|---|---|---|
| **A36 — PPG rollout geometry** | `raileanu21a-supp.pdf` §E specifies `1 process x 2048 steps`; this port runs `8 x 256`. Same 2048 samples per update and the same 65,536-interaction auxiliary cadence, different GAE truncation and trajectory geometry. | Changing it edits `runnable/ppg`, which is in ppg's hashed runtime closure. Handed to Codex (A83/A85) as one bounded gt4i.1 probe against the known 8x256 rate. |
| ~~**A25 addendum — evaluation policy mode**~~ **CLOSED same day** | Was: the fleet's only UNITS-class split, with two of three fixed cross-group pairs crossing it. | `eval_grid.py` now takes `--policy-mode {native,mode}`, default `native`. All four sampling families honour it and the record stamps the mode that actually ran. It moved all seven attestations, which is why it had to land BEFORE the wave rather than after. |

**Consequence, and it is the sequencing rule (Q47)**: `alda` and `ppg` attestations are already
superseded by today's step-0 guard and LR-decay changes. One wave, after both blockers close, against
the frozen tree. Not before.

## 2. Host-bound — reachable only from `cds2`

Ordered as `RUNNING-ON-PRODUCTION-HOST.md` §0 orders them. Nothing here is undecided; all four are
measurements that cannot be taken from this machine.

1. **Renderer/container parity (C95, R_A/R_B).** The strongest stop. Records show ~131.5 versus
   ~13.85 on the same checkpoint under a renderer change — larger than any effect this project
   measures. `preflight_production_host.sh` explicitly does NOT cover this and says so on every run.
2. **CTRL's 64-environment memory.** The v100 profile restores 64 envs; its 54.28 GiB is a linear
   extrapolation from a measured 16-env 13.57 GiB. `family.py check_memory` now REFUSES to pack
   anything beside a cell whose figure is an extrapolation.
3. **IBAC-SNI competence at `procs=16`.** Runnability is proven; learning is not. Its own OWNER gate
   says so.
4. **One staged 600k DrQ-v2 canary**, all the way through fresh reload, the full offline grid,
   record normalisation and statistics.

**V100 throughput is unmeasured for training AND evaluation.** `production-schedule-v100.json`
reports `UNMEASURED_ON_V100` rather than guessing, and `PRODUCTION-CALENDAR.md` is explicitly
T4-class throughout — including the evaluation rates measured today, which are gt4.1-basis.

## 3. Owner ratifications — seven, each with a default already running

`python scripts/open_decisions.py` is the live list. None of these changes what the code does today;
each changes whether that behaviour is formally settled: estimands, seed policy, checkpoint rule,
production scope (Door), the external RL-ViGen anchor, Places365's split (A22, whose
"same split so ordering is unaffected" reasoning was **withdrawn** today), and PPG's identity (A36's
frozen half).

## 4. What today changed, so the next reader knows which claims are new

Eleven defects, all invisible at the 10k-probe scale every prior measurement came from, all biting
at production length. Full detail in `CORRECTIONS.md #99`, `review-20-21-accounting.md` and the
commits; the list matters because it is the evidence for how much of "pre-production finished" was
untested rather than wrong.

- **Online evaluation was never disabled at step 0** for eight baselines, advancing Door's placement
  stream differently per family under a manifest saying it was off. The gate could not see it: it
  read the descriptor, not the executed path.
- **Checkpoints were not durable.** Every family writes under `{run_dir}`; only `retain` moves them
  to the mounted output, after training. A killed container lost the run.
- **`resources.json` was written only after the process exited** — no memory record during a run,
  none at all if the container died, and ~97,000 samples held in the sampler's RAM.
- **Packed cells had no GPU assignment** and would both have landed on `cuda:0`.
- **`check_memory` excluded the replay it guards** — 5.33 GiB certified where the schedule said
  38.78 — had no `v100` tier, and was never called by the runner.
- **The submit-time memory check was budget-blind**, sizing a 10k probe against a 600k buffer.
- **PPG lacked the linear LR decay its own identity requires**, and my first freeze chose the wrong
  identity; §E settled it against the configuration we already ran.
- **`idaac`'s decay is ours, from the paper** — absent from `ext/idaac/train.py` — which needed the
  governing principle written down rather than left as an inconsistency with PPG.
- **Two comparability axes were missing**: learning-rate schedule, and evaluation policy mode.
- **"No table pools the two" was unenforced**; `preprod_table.py` pooled the UNITS split silently.
- **A 165 GPU-h estimate rested on a placeholder** for six of twelve baselines, when the measurement
  already existed inside completed jobs.

Two of my own fixes broke something and were caught — one by the full suite (retention thinning that
thinned `rlvigen` twice), one by verifying the fix's own default (which silently restored the
sentinel it removed). Both are recorded rather than quietly repaired.

## What would make this page say yes

The freeze blockers close; one validation wave runs green against the frozen tree; the four
host-bound measurements come back and the schedule is recomputed from them; the canary completes its
whole chain; the owner ratifies or overrides the seven. In that order — each depends on the one
before it.
