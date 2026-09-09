# 21 — Which baselines to run on a shared card, and why, measured

**2026-09-09.** The plan is three sequential single-seed runs on card 0, each leaner than a
production cell, to prove the chain before committing the fleet. This note records which three and
on what evidence, because "pick a lean one" is otherwise a matter of taste.

## The constraints, as stated

Avoid: Places365 (a ~45 GiB asset), replay-buffer-heavy families, high process counts (e.g. 16),
high VRAM, high RAM, and anything simply slow.

## Measured, from the project's own tools

`family.py disk-requirement --frames 600000 --profile v100 --ceil-total`, `families.json`
constants and profile overrides, and the RAM figures already recorded there.

| baseline | procs (v100) | RAM peak GiB | disk GiB @600k | Places365 | verdict |
|---|---|---|---|---|---|
| **idaac** | 1 | 3.17 | **9** | no | **run 1** — in progress |
| **ppg** | 1 | 4.2 | **9** | no | **run 2** |
| ibac_sni | **16** | 1.97 | 10 | no | excluded: v100 override raises `procs` 1 → 16, a whole-host CPU job |
| **alda** | 1 | 14.73 | 12 | no | **run 3** |
| rad | 1 | — | 29 | no | heavier disk; keep in reserve |
| drqv2 / curl / drq | 1 | — | **48** | no | excluded: replay snapshots dominate |
| svea / sgqn / soda | 1 | — | — | **YES** | excluded: Places365 |
| ctrl | **16** | — | — | no | excluded: `procs` 16, and the JAX stack needs its own environment |

Host for scale: **125 GiB RAM (113 available), 16 cores**, two V100-32GB. So alda's 14.73 GiB is
comfortable and ibac_sni's 16 processes would take the whole machine's CPU.

## Provenance, which turned out to select the same three

The owner is more interested in the baselines **RL-ViGen did not ship** than in the ones it did.
`families.json` settles which is which: a `repository` of `runnable/<name>` marks a baseline this
project added; an empty one marks a baseline that comes from RL-ViGen itself.

| added by this project | shipped by RL-ViGen |
|---|---|
| `idaac`, `ppg`, `ibac_sni`, `ctrl`, `alda` | `drqv2`, `svea`, `sgqn`, `curl`, `drq`, `rad`, `soda` |

Of the five added baselines, two are excluded on measurement alone — `ibac_sni` and `ctrl` both run
`procs=16` under the v100 profile. The remaining three are exactly `idaac`, `ppg` and `alda`, which
is the order below. The preference and the resource constraints happen to agree here; where they
disagree in future, this table is what makes the disagreement visible.

## Order, and why this order

1. **idaac** — leanest on RAM of the on-policy three, and already the subject of the renderer work.
2. **ppg** — same disk and process count, slightly more RAM, and a *different* on-policy family, so
   a second pass tests the runner rather than re-testing one family.
3. **alda** — 12 GiB, and the third of the added baselines that is runnable within the constraints.
   It exercises a different code path again without the 48 GiB the drqv2/curl/drq group needs.

If all three complete, the untested remainder is the expensive half: the 48 GiB replay group, the
Places365 three, and the two 16-process families. Those are fleet decisions, not smoke tests.

## What is NOT settled by this note

VRAM. Only `idaac` (1204 MiB) and `ppg` (1588 MiB) have measured figures; the rest are unmeasured
and the `NATIVE_VRAM_CAP_MIB` cap is what bounds them in the meantime. A cap is a bound, not a
measurement, and `notes/production-host/19` §"what is not settled" applies here too.


## Revision, 2026-09-09 — at smoke-test scale the disk table does not discriminate

The disk figures above are at **600k frames**. Recomputed at the **10k** these validation runs
actually use:

| baseline | disk @10k | disk @600k | origin |
|---|---|---|---|
| idaac | **9 GiB** | 9 GiB | added |
| ppg | **9 GiB** | 9 GiB | added |
| alda | **9 GiB** | 12 GiB | added |
| drqv2 | **9 GiB** | 48 GiB | RL-ViGen-native |
| rad | **9 GiB** | 29 GiB | RL-ViGen-native |
| curl / drq | **9 GiB** | 48 GiB | RL-ViGen-native |

Every one of them is 9 GiB at 10k. The 48 GiB that excluded the replay group is entirely the
600k-frame checkpoint-and-replay footprint, and it does not exist at this scale. **So disk excludes
nothing here**, and the exclusions that survive are Places365 (svea/sgqn/soda) and `procs=16`
(ibac_sni/ctrl) — both of which hold at any scale.

### This changes the order, because a validity check is worth more than a preference

The owner wants run-priority on the added baselines, and *also* wants to see a baseline that
succeeds on the original RL-ViGen reach real SR/reward here — as evidence that our harness is not
subtly broken. Those are different questions and the second is the more dangerous one to leave
unanswered: every added baseline could run cleanly and still tell us nothing about whether our Door
setup can produce learning at all.

Revised order:

1. **idaac** — added. In progress.
2. **ppg** — added.
3. **drqv2** — RL-ViGen-native, and the canonical one. **The validity check.** At 10k it costs the
   same 9 GiB as everything else, so it is nearly free to run and is the only one of these that
   comes with an external expectation of what success looks like.
4. **alda** — added, if there is time.

A non-degenerate result from (3) is what licenses trusting (1) and (2). If `drqv2` learns nothing
here, the added baselines learning nothing would be uninterpretable.


## Second revision, 2026-09-09 — production runs go one at a time

The packing recommendation is withdrawn for production scale (see note 22): two cells at 600k took
29910 MiB of 32494 and the memory floor stopped them. Production runs are therefore **sequential,
one cell per launch**, with `NATIVE_VRAM_CAP_MIB=4096` — measured as roughly `budget / 3`, since a
solo cell runs about three processes (2019 + 308 + 308 MiB).

### The queue

| # | cell | frames | origin | why |
|---|---|---|---|---|
| 1 | `idaac:101` | 600000 | added | **running** since 2026-09-09 02:5x |
| 2 | `ppg:1` | 600000 | added | second added on-policy family; VRAM ~8 GiB uncapped, so watch the cap |
| 3 | `drqv2:1` | 600000 | **RL-ViGen-native** | the validity check: an algorithm with an external expectation of success |
| 4 | `alda:1` | 600000 | added | third added baseline, if the card is free |

`ppg` is second rather than third because it is the other *added* on-policy family and the owner
asked for run-priority there. `drqv2` follows immediately because a non-degenerate result from a
baseline RL-ViGen itself ships is what licenses believing the added ones — if `drqv2` learns
nothing here, the added baselines learning nothing would be uninterpretable.

**`ppg` needs its cap checked before launch.** It measured **8207 MiB uncapped** while `idaac`
measured 2019. At `NATIVE_VRAM_CAP_MIB=4096` the cap would now genuinely bind it, and a cap that
binds a trainer which wants twice that will OOM rather than throttle. Either measure `ppg` solo at
a cap it fits under, or raise the cap for that cell alone and accept the larger share. This is the
direct consequence of the cap having never worked until today: every previous `ppg` run was
uncapped, so no evidence exists about how it behaves under one.
