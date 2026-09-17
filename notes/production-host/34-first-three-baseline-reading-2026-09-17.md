# 34. The first three-baseline same-axes reading — 2026-09-17

**This is a reading, not a result.** One seed per baseline against a policy that requires three.
Recorded because it is the first time the campaign's actual question has been answerable at all, and
because two things in it are worth checking before more compute is spent, not after.

## What was compared, and why it is allowed

`scripts/comparison_blocks.py` puts all three pairs among `{idaac, ibac_sni, ppg}` at **PRIMARY** for
RAW RETURN: they agree on every blocking axis — policy mode, frame stack, time limit, network input.
They are also exactly the three families that report SAMPLED return, so the estimand matches without
the `mode` pass being involved. Endpoint rows only, `eval_policy_mode = sample`, 11 scene sets × 4
regimes = 44 rows each.

| baseline | train | eval-easy | eval-medium | eval-hard | source |
|---|---|---|---|---|---|
| `ibac_sni` s101 | **82.18** | 42.78 | 29.42 | 37.02 | `card1-20260916-203537`, native pass, 44/44 |
| `idaac` s101 | 39.24 | 32.62 | 12.00 | 17.18 | `reeval-v214-idaac-endpoint__records.jsonl` |
| `ppg` s1 | 22.69 | 17.96 | 11.67 | 16.70 | `reeval-v214-ppg-endpoint__records.jsonl` |

## Two things the table says

**1. `eval-medium` scores below `eval-hard` in all three.** This was already recorded as a property
of the regime definitions rather than a per-baseline quirk — `eval-medium` alone sets
`except_robot=False`, so it is a different distribution and not a rung on a ladder. Three independent
baselines now show the same inversion, which is about as much support as a one-seed reading can give
a claim of that shape. Anyone who reads these four columns as a difficulty ordering will draw a wrong
conclusion, and the column order in this table invites exactly that.

**2. Train-time strength and generalisation do not line up.** `ibac_sni` is far the strongest on
`train` (82.18 against 39.24 and 22.69) and loses the most going to `eval-easy`:

    ibac_sni   82.18 -> 42.78   -48%
    ppg        22.69 -> 17.96   -21%
    idaac      39.24 -> 32.62   -17%

That is the shape the study exists to measure, so it should be the most suspected number here, not
the most quoted one. With n=1 it is equally consistent with a seed that happened to overfit.

## Update, 15:30 — a second idaac seed, and the headline does not survive it

`idaac` s102's native endpoint completed at 15:30, so one baseline now has **two seeds on identical
axes**: evaluator revision `1b092f97` on both, 20 episodes, frame 598,016, `sample` mode, 11 scene sets
× 4 regimes. The comparison is paired by scene set.

| regime | s101 | s102 | paired diff | sd of paired diff |
|---|---|---|---|---|
| train | 39.24 | **20.51** | −18.73 | 16.84 |
| eval-easy | 32.62 | 24.24 | −8.38 | 21.07 |
| eval-medium | 12.00 | 10.36 | −1.64 | 5.65 |
| eval-hard | 17.18 | 18.52 | +1.34 | 11.25 |

**The generalisation gap changes sign between seeds of the same baseline.** `idaac`'s train → eval-easy
change is **−17%** at seed 101 and **+18%** at seed 102. A 35-point swing from the seed alone is larger
than the entire spread this note ranked the three baselines on (−48%, −21%, −17%). So the claim above —
that `ibac_sni` generalises worst — is **not supported**: it sits inside the variation one baseline shows
across two seeds. This note had flagged that finding as the number to suspect rather than quote; the
second seed is the evidence that the suspicion was right.

Two things do survive:

- **eval-medium < eval-hard holds in both seeds** (12.00 < 17.18 and 10.36 < 18.52), consistent with the
  explanation that `eval-medium` alone sets `except_robot=False` and is a different distribution rather
  than a rung on a ladder. Four independent measurements now show it, across three baselines.
- **The per-scene variance is large.** The paired standard deviation is 17–21 on `train` and `eval-easy`
  against means of 20–40. Any claim at this depth needs the scene set as the unit of variation, not the
  episode, and more than one seed.

Provenance: s101 is `results/records/reeval-v214-idaac-endpoint__records.jsonl`. **s102's rows are not
yet collected** — the cell is still running its mode pass — and were read from a laptop copy of
`card1-20260916-213222/native-out/cells/idaac-s102/offline_eval_endpoint.jsonl`, fetched at 15:30. Their
evaluator revision was checked against the live tree and binds.

## What would make this a result

- **Three seeds each.** `idaac` s102 trained to completion on 2026-09-17 and its grid is partial;
  `ibac_sni` and `ppg` have one seed apiece. The n=3 policy is not a formality for a table whose
  headline is a ratio between two regimes.
- **Collection.** `ibac_sni` s101's rows are still in the cell's `native-out` and in the laptop copy
  under the session scratchpad; they are NOT in `results/records/` and NOT in the evaluator ledger.
  The revision was checked and binds (`9b2d17b4…`, equal to the live tree for `ibac_sni`), so
  collection is expected to succeed rather than hoped to.
- **The retention view.** Raw return blocks on four axes; retention blocks on none, and is the
  study's actual endpoint. This table is the more restricted of the two and should not be the one
  that gets reported.

## Provenance of the ibac column

All 44 rows name one checkpoint, `d0298c76…`, which is the retained `snapshot.pt` and byte-identical
to the trainer's `model.pt`. It is NOT byte-identical to `model_600064.pt`, but all 37 parameter
tensors are equal — see
[`results/evidence/ibac-endpoint-weights-equal-frame-600064`](../../results/evidence/ibac-endpoint-weights-equal-frame-600064/CLAIM.md).
So the endpoint measures the 600,064-frame policy, and `audit_record_frame_provenance.py` will still
grade these rows UNVERIFIABLE because it indexes by file hash.
