# The production host: read this entire directory before touching anything

`cds2` is a **university communal machine** with strict GPU and environment control, shared with
other people's running work. Nothing in this directory is advisory.

**Read every file here in full before any host action.** Not a skim, and not this README alone —
it is an index, not a summary. The per-file rules carry the specifics that make them enforceable,
and the specifics are where the harm is.

| file | what it governs |
|---|---|
| [`00-authority-and-scope.md`](00-authority-and-scope.md) | which machine, on whose authority, and what "documented" does NOT mean |
| [`01-connection.md`](01-connection.md) | Netbird, the address table, and what the guide does and does not say |
| [`02-absolute-prohibitions.md`](02-absolute-prohibitions.md) | the things that are never done, with no exception path |
| [`03-docker-discipline.md`](03-docker-discipline.md) | all work inside a container; what may be deleted and the proof required |
| [`04-resource-safety.md`](04-resource-safety.md) | GPU, VRAM, RAM, CPU, disk — assume none of it is free |
| [`05-privacy-and-non-alarm.md`](05-privacy-and-non-alarm.md) | what not to look at, and why looking is itself a hazard |
| [`06-before-any-action.md`](06-before-any-action.md) | the mandatory pre-action procedure |
| [`07-this-repo-s-own-hazards.md`](07-this-repo-s-own-hazards.md) | **specific dangerous defaults in OUR code**, read before running any of it |
| [`08-gpu-assignment-and-time.md`](08-gpu-assignment-and-time.md) | **the GPU assignment schedule**, and why every time must be stated in UTC+3 |
| [`09-standing-cautions.md`](09-standing-cautions.md) | the dense list — a floor for judgement, and one that must keep growing |
| [`10-resource-upper-bound-rule.md`](10-resource-upper-bound-rule.md) | **the upper-bound rule** — it subsumes much of `04`; VRAM now measured |
| [`11-host-state-2026-09-08.md`](11-host-state-2026-09-08.md) | **a read of the actual host, and its live blockers** — re-read before each session |
| [`12-incremental-bringup-plan.md`](12-incremental-bringup-plan.md) | **the rung-by-rung bring-up plan** — one new risk per step, reviewed before the next |
| [`13-how-the-operator-path-works.md`](13-how-the-operator-path-works.md) | what the wrapper actually does, and why the environment is rebuilt every cell |
| [`14-assets-and-environment-on-a-persistent-host.md`](14-assets-and-environment-on-a-persistent-host.md) | **what is transient and what accumulates** — `--rm` and the EXIT trap free almost everything; the per-cell disk table; the staging directory that was on an unchecked filesystem |
| [`15-what-fails-when.md`](15-what-fails-when.md) | **the abort ladder, invocation to first gradient step** — what a dry run proves for free, and the memory preflight that used to be skipped for hours |
| [`17-first-real-cell-plan.md`](17-first-real-cell-plan.md) | **the plan to the first real cell** — why `idaac`, the JAX 75%-preallocation hazard that threatened the neighbour, and the abort criterion at every step |
| [`18-the-watch-that-would-have-expired-first.md`](18-the-watch-that-would-have-expired-first.md) | **a near-miss with nothing failing** — both card watches were sized to expire before the cell reached the GPU, and both would have exited 0; plus why `--no-cache-dir` was right in its reasoning and wrong in its option set |
| [`19-environment-lifecycle-vs-run-lifecycle.md`](19-environment-lifecycle-vs-run-lifecycle.md) | **the structural fix behind 18** — `apt` is 71s and `pip` is over two hours, there are exactly TWO requirement sets across twelve baselines, and a read-only prebuilt venv freezes the environment by construction |
| [`16-host-work-log.md`](16-host-work-log.md) | **what was actually run on cds2, what it cost, the container recipes that worked, mistakes made — and the RAM/VRAM/disk contention arithmetic that blocks the GPU steps** |
| [`20-egl-renderer-problem-STATEMENT.md`](20-egl-renderer-problem-STATEMENT.md) | the EGL/llvmpipe failure, **RESOLVED 2026-09-09** — kept because the symptom recurs whenever a container loses the `graphics` driver capability |
| [`21-which-baselines-to-run-on-a-shared-card.md`](21-which-baselines-to-run-on-a-shared-card.md) | **which baselines are cheap enough to co-tenant**, measured rather than assumed |
| [`22-what-a-cell-actually-uses.md`](22-what-a-cell-actually-uses.md) | **what one cell actually costs on the card** — VRAM, cores, RAM, measured during the first idaac cell |
| [`23-the-first-complete-cell.md`](23-the-first-complete-cell.md) | the first cell on `cds2` to complete end to end |
| [`24-what-a-yield-actually-costs.md`](24-what-a-yield-actually-costs.md) | **a yield is not cheap** — the co-tenancy design assumed it was |
| [`25-a-production-cell-is-half-training.md`](25-a-production-cell-is-half-training.md) | a production cell is ~half training and half evaluation; budget the whole thing |
| [`26-the-vram-cap-never-reached-a-trainer.md`](26-the-vram-cap-never-reached-a-trainer.md) | **the per-process VRAM cap has never bound a trainer**, and why a cap is the wrong instrument |
| [`27-disk-not-vram-is-what-caps-parallelism.md`](27-disk-not-vram-is-what-caps-parallelism.md) | **disk headroom, not VRAM, is what limits how much runs at once** |
| [`28-eval-is-sixty-percent-of-a-cell.md`](28-eval-is-sixty-percent-of-a-cell.md) | evaluation is 60% of a cell, and it is the half that is hardest to read |
| [`29-two-drifts-a-self-yield-and-a-wrong-cost.md`](29-two-drifts-a-self-yield-and-a-wrong-cost.md) | **a whole-card job that yielded to itself**, plus three corrections to earlier notes |
| [`30-did-we-crowd-anyone-out.md`](30-did-we-crowd-anyone-out.md) | **the audit of what our cells took from co-tenants**, per cell, from the sampler |
| [`31-state-at-the-pause-2026-09-10.md`](31-state-at-the-pause-2026-09-10.md) | state at the owner's 24h pause |
| [`32-what-we-actually-have-2026-09-14.md`](32-what-we-actually-have-2026-09-14.md) | **full artifact audit** — what each run left behind, what "collected" means, and the two long runs worth re-measuring |
| [`33-what-we-actually-have-2026-09-16.md`](33-what-we-actually-have-2026-09-16.md) | **current state.** The re-evaluation landed (732 admissible rows, was 28); the seed discrepancy that makes the campaign count 1 of 36; the co-tenant arithmetic that decides a launch; three wrong VRAM numbers and two retracted claims |
| [34-first-three-baseline-reading-2026-09-17.md](34-first-three-baseline-reading-2026-09-17.md) | The first time three baselines could be put on the same axes: idaac, ibac_sni and ppg at PRIMARY for raw return. One seed each, so a reading and not a result. |
| [35-what-the-campaign-costs-at-measured-rates.md](35-what-the-campaign-costs-at-measured-rates.md) | What the remaining 32 cells cost at rates measured here, why the full 36-cell campaign cannot finish on this host, and which five cells I would run first. |
| [36-no-completed-cell-passes-the-competence-gate.md](36-no-completed-cell-passes-the-competence-gate.md) | Every 600k cell clears the random floor on shaped return and opens the door in ~0 of 200 episodes, so the protocol's own gate withholds every retention ratio. What the campaign can and cannot claim at this budget. |
| [37-what-a-cell-actually-costs-in-wall-clock.md](37-what-a-cell-actually-costs-in-wall-clock.md) | A retracted "96s" claim, and the real numbers from a completed cell: eval (curve + endpoint) costs roughly double the training time. Also the ppg checkpoint-cadence mechanism (`ppo.py:188`, two uncoordinated numbers combining via modular arithmetic) that a keyword search for "save" or "cadence" cannot find. |
| [38-the-memory-floor-does-not-protect-anyone-during-evaluation.md](38-the-memory-floor-does-not-protect-anyone-during-evaluation.md) | 2026-09-20: a labmate took a card to 1.9 GiB free, the observer wrote the yield sentinel, and our evaluating cell ignored it for 50 minutes — the poller exists only while TRAINING runs. Not fixed |

## The rule that comes before the others

**If you do not know an upper bound on what you will occupy, do not run it. If anything else is on
the GPU, CPU, RAM or disk — theirs, or not certainly yours, or even certainly yours — and you are
not sure the remainder covers your whole run, do not run yours.** Peaks combine, and CUDA OOM
happens at the combined peak, not at typical usage. [`10`](10-resource-upper-bound-rule.md).

**VRAM, as of 2026-09-16: six of seven families ARE measured** — this paragraph previously said the
opposite and blocked on it. See [`33`](33-what-we-actually-have-2026-09-16.md) §2 for the table.
Two things still bite:

- **`ibac_sni` is the one family with no measurement**, and three different figures for it were
  quoted as fact in a single day, one of which was a colleague's memory read through a defective
  instrument. A ~6.6 GiB lower bound survived that, and it was right: ibac_sni is now
  **measured 2026-09-16 at 7,421 MiB** — 2,199 compute plus 5,222 non-compute (EGL), on an exclusive card at steady state. See `33` section 3b.
- **`ctrl` at 32,435 MiB exceeds a 32,494 MiB card once the 4,000 MiB floor is added**, so it cannot
  satisfy floor-plus-peak at all. It needs an empty card and an explicit decision about the floor.

And the rule has a precondition nobody wrote down: **before a number decides anything, find where it
was produced.** An estimate written in a code comment is indistinguishable from a measurement six
hours later, and this is exactly how the ~15 GiB ibac_sni figure entered two agents' reasoning.

## The three that override everything else

1. **All work happens strictly inside a Docker container.** Install into the container, never the
   host. See `03`.
2. **Never install, update, change or remove anything on the host** — no `apt-get`, `brew`, `pip`
   outside a container, no conda, no drivers, no package manager of any kind. See `02`.
3. **Never cause another user's process to fail.** Not by OOM, not by CUDA OOM, not by filling a
   disk, not by taking every core, not by claiming a GPU someone is using. See `04`.
4. **Use only the GPU assigned to you, on the machine and day it was assigned.** Idle is not free,
   and a similar name is not the same machine. See `08`.
5. **No list here is complete.** `09` is a floor for judgement, not its boundary, and it is meant to
   grow — a new hazard gets added in the same commit as its fix.

## If something blocks

A GPU is occupied, RAM is tight, a path is unreadable, a permission is missing — **that is a stop,
not a puzzle**. Do not work around it. It may encode context nobody wrote down. Report it and wait.
Losing time to a block is cheap; the alternative is not.

## The standing bias

When an action is uncertain, the resolution is always *verify by reading, then act* — never *run
it and see*. A tight debugging loop or a "temporary" step is a reason to be **more** careful, not
less. This project has already shipped several instruments that silently did nothing; on a shared
machine the same class of mistake takes someone else's job down with it.
