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

## Order, and why this order

1. **idaac** — leanest on RAM of the on-policy three, and already the subject of the renderer work.
2. **ppg** — same disk and process count, slightly more RAM, and a *different* on-policy family, so
   a second pass tests the runner rather than re-testing one family.
3. **alda** — off-policy but only 12 GiB, so it exercises the replay path without the 48 GiB the
   drqv2/curl/drq group needs.

If all three complete, the untested remainder is the expensive half: the 48 GiB replay group, the
Places365 three, and the two 16-process families. Those are fleet decisions, not smoke tests.

## What is NOT settled by this note

VRAM. Only `idaac` (1204 MiB) and `ppg` (1588 MiB) have measured figures; the rest are unmeasured
and the `NATIVE_VRAM_CAP_MIB` cap is what bounds them in the meantime. A cap is a bound, not a
measurement, and `notes/production-host/19` §"what is not settled" applies here too.
