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
tier, and concurrent cells whose peaks would not fit. The payload verifies at contract 19. The
sources reconstruct and verify on Linux. The suite runs. Those were repairs and they are done.


## Evidence added 2026-09-08 (late) — no status flipped

Three of the items above now have host evidence they did not have when the table was written. None
of them changes status; the point of recording this is that the evidence exists and where it is.

**Item 9, production renderer verified.** The ruling was that the host is ours to configure, "which
makes this tractable by construction rather than a hazard to discover". A hazard was nevertheless
discovered, and it is the one that matters: the first cell to get past `pip` died with
`RuntimeError: software EGL renderer: llvmpipe (LLVM 15.0.7, 256 bits)`. Docker's `--gpus` sets
`NVIDIA_DRIVER_CAPABILITIES=compute,utility`, and nothing in this repo had ever added `graphics` —
the capability that installs `libEGL_nvidia`. Measured on the host, same image and card: default →
no `libEGL_nvidia`; `compute,utility,graphics` → `libEGL_nvidia.so.580.126.09`. DataSphere set it
for us, so no previous job could have revealed it. Fixed in `run_on_production_host.sh`.

This does **not** close item 9. R_A/R_B renderer parity is still unmeasured, and the finding
sharpens why it matters: the host can render with a *different renderer entirely* and, without
`run_probe.sh`'s check, would have done so silently. Item 9 is now better founded, not resolved.

**Item 5, environment manifest.** The gap was that `apt-get`/`pip` run inside the job, so the
executed environment is not frozen. Measured: `apt` 71 s, `pip` over two hours, 1710 MB per cell,
discarded every time. `datasphere/native/build-env.sh` now builds a per-requirement-set environment
that is mounted **read-only**, which freezes the pip half by construction rather than by intention;
every verification failure refuses rather than falling back to `pip`. `apt` still runs at run time,
so this is half the gap, and `notes/production-host/19` says so rather than claiming closure.
**Adopting it for the fleet is an owner decision** — it changes how every cell runs.

**Item 6, production canary.** Still never run end to end. The 2026-09-08 attempt reached the
renderer check and stopped there, which is progress on the bootstrap half and no progress on the
chain itself.
