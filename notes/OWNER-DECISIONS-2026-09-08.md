# The ten OWNER gates, made decision-ready

Written 2026-09-08. Every gate below is a decision, not a repair — `production_gates.py` reads
**35 pass, 0 fail, 10 owner** and says so: *"No mechanical failures remain."*

They are not equivalent. **Four need a signature on a default that is already implemented and
enforced. Four need work that costs money or time. Two need one measurement each.** Sorting them
that way is the point of this file.

---

## A. Ratifications — the default is built, enforced, and documented; it needs your name

Nothing is blocked by these except the formality. If you disagree with a default, that is a design
change and a different conversation.

| # | gate | the default in force | where it lives |
|---|---|---|---|
| 4 | seed policy frozen | fixed **n=3** for every reported row, no outcome-dependent allocation | `EVAL-PROTOCOL.md` |
| 8 | checkpoint rule frozen | **endpoint-as-headline**, trajectory descriptive, no selected-best column | `EVAL-PROTOCOL.md` |
| 10 | production scope frozen | **Door**, and every constant is Door's — the 1.842 random floor, the ten certified scenes, the 500-step horizon | `families.json`, C55 |
| 7 | external RL-ViGen anchor | answered without a dedicated cell: RL-ViGen's published Robosuite table gives drqv2 Door eval-easy **3.6** across seeds {3,7,4,3,1} | C48 |

**On #4 there is now evidence you did not have this morning, and it cuts against the default.**
The seedvar job measured eval-easy at **cv 0.55**, giving a 95% interval of **[−2.98, 19.26]** on a
mean of 8.14 — *it includes zero*. At 100k, three seeds cannot distinguish drqv2's eval-easy
performance from nothing. That is an upper bound on the noise, not the production figure, and it is
the only measurement of between-seed variance this project has. **n=3 is unproven, not refuted.**
Widening costs 12 cells per extra seed. See `notes/seed-variance-at-100k.md`.

## B. Needs one measurement each

| # | gate | what would close it | cost |
|---|---|---|---|
| 2 | shared evaluator validated | re-attest **`dmc_gb` only** — its revision moved from `0d060c1b` to `827f2d85` when the Places365 worker fix landed | ~1.2 h DataSphere, **~250 RUB** |
| 1 | ibac_sni competence | a `procs=16` V100 cell showing non-degenerate learning — finite losses, non-collapsed action distribution, separation from the 1.842 floor. **Not a target score** | one cell; `ibac_sni` is a whole-host CPU job at procs=16 |

**#2 is deliberately not fired.** This project's rule is to accumulate fixes and validate once
against the final frozen tree, rather than a wave per change. If more clone edits are coming, this
should ride with them. It does **not** block the `idaac` card-0 cell.

## C. Needs real work, and one of them is the biggest unknown in the project

| # | gate | what it actually needs |
|---|---|---|
| 6 | **production canary** | The chain — train → checkpoint → clean reload → full offline grid → records → statistics — **has never run end to end at production length for any family.** Longest real cell is 5.1 h; a 600k soda cell is projected at 45 h. |
| 5 | environment manifest | The image is digest-pinned and requirements hashed, but the job still runs `apt-get`/`pip` inside it, so the **executed** environment is not frozen and two jobs from one digest can differ. Closing it by construction means a baked image with no runtime package mutation. |
| 9 | production renderer verified | C95. The owner ruled the production host is ours to configure, which makes this tractable by construction rather than a hazard to discover — but the R_A/R_B comparison against a real checkpoint has not been run. |
| 3 | estimands frozen | P-C76. The time-limit split is 3 bootstrap / 9 terminal. The false-certification half is fixed; the substantive half has a reasoned recommendation (declare and quantify) and needs a ruling. |

**#6 is the one to think hardest about.** Every baseline fits `gt4i.1` at the **full 600k budget on
the base profile** — the campaign moved to `cds2` because the **v100 profile's** larger settings do
not fit a DataSphere tier, which is a different axis from length. So #6 could be closed on
DataSphere for `idaac` at ~4.79 h of training plus the grid, **roughly 1300–1700 RUB**, contending
with nobody. Or on `cds2` for free, contending with a co-tenant.

---

## What is NOT on this list

Everything mechanical. The wrapper refuses an unnamed GPU, an uncapped VRAM request, a
too-small disk, an unverified mirror device, a tmpfs staging directory, a profile with no memory
tier, and concurrent cells whose peaks would not fit. The payload verifies at contract 16. The
sources reconstruct and verify on Linux. The suite runs. Those were repairs and they are done.
