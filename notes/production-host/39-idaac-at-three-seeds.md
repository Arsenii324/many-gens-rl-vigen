# 39 — `idaac` at three seeds: the first complete baseline, and what it does and does not show

Written 2026-09-20 17:56 MSK by Claude, from `python scripts/production_reading.py --retention` run on
the records collected that evening (`card1-20260920-011652`, seed 103; seeds 101 and 102 collected
earlier). A reading, not a result: the owner asked for partial results to be analysed as they arrive.

| `idaac`, mode estimand, mean over ten scenes | s101 | s102 | s103 | mean | range | success |
|---|---|---|---|---|---|---|
| train | 32.91 | 29.58 | 41.61 | 34.70 | 29.58–41.61 | 0.000 |
| eval-easy | 31.08 | 28.03 | 43.84 | 34.31 | 28.03–43.84 | 0.002 |
| eval-medium | 13.56 | 17.58 | 33.39 | 21.51 | 13.56–33.39 | 0.005 |
| eval-hard | 15.13 | 25.61 | 16.68 | 19.14 | 15.13–25.61 | 0.010 |

Sampled estimand (its as-published one): train 32.00, eval-easy 31.49, eval-medium 16.69,
eval-hard 16.22; success ≤ 0.005.

## What it shows

- **No seed reaches competence.** Train-scene success is 0.000 / 0.000 / 0.000 (mode) against the
  0.25 gate, so the reader prints `DID NOT REACH COMPETENCE` and no retention ratio, correctly. The
  random floor is 1.84; returns near 35 are shaped reward for approaching the handle, not for opening
  the door. For scale: `drqv2` s101's own training log shows episode rewards near 487 by 590k
  frames (its evaluation is deferred — `CURRENT-STATE` §2).
- **Train vs eval-easy: no gap at three seeds** (−6 %, −5 %, +5 %). Note 34 read a −17 % gap at one
  seed and its sign flipped at two; at three it is noise around zero. The eval-easy regime does not
  hurt a policy that has not learned the task — which says little about generalisation, because
  there is no competence to lose.
- **eval-medium and eval-hard sit ~40 % below train** in the mean.

## What it takes back

- Note 34 and `CURRENT-STATE` §2 state that "`eval-medium` < `eval-hard` holds in both idaac
  seeds". Seed 103 reverses it (33.39 vs 16.68). At n = 3 that is a spread, not an ordering; it
  should not be quoted as a finding about the regimes.

## What it does not show

Anything about `idaac` as a method. 600,000 frames is 2.4 % of the 25M-step budget its paper
reports (`DECISION-SHEET.md` A46, corrected 2026-09-20), its learning rate is still at 40 % of its
initial value when training stops, and the design's identified across-method contrast is inside the
RL-ViGen five (`docs/RESEARCH-FRAME.md`), not here. The honest row is "did not reach competence at
the benchmark's budget", with this table beside it.

Provenance: `audit_record_frame_provenance.py` with the CELL directory as `--checkpoints`:
572 corroborated, 0 MISMATCHED, 26 training-log rows without a checkpoint — the same profile as
seed 102. (Pointing `--checkpoints` at the `checkpoints/` subfolder leaves the 88 endpoint rows
unverifiable, because the endpoint snapshot sits one level up.)
