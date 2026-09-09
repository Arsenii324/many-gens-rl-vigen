# Eval validity: what these numbers support, and the two defects found by reading the records

**2026-09-09**, from `results/records/card0-20260909-035152__records.jsonl` — 518 rows carrying
per-episode detail. Everything below comes from artifacts already in hand; **no run was spent to
learn any of it**.

`eval_grid.py` records, per episode: `returns`, `episode_success`, `eval_episode_ids`,
`placement_condition_seeds`, `placement_witnesses` (a hash of the reset observation). Nothing had
read them.

## What holds

**Row summaries match their own raw episodes.** All 518. `episode_return_mean`,
`episode_return_sd`, `episodes` and `success_rate` each equal what that row's own `returns` and
`episode_success` say, to 1e-6. A summary disagreeing with its own data is the cheapest possible
error and nothing was checking for it.

**Placement is paired across regimes.** `placement_condition_seed(seed, scene, index)` deliberately
omits the regime, so every regime replays the same 200 initial conditions. Verified: 200 of 200
(scene, index) slots carry one seed across all four regimes and all frames. **This is what makes
train-vs-eval a paired comparison** — the difference is the perturbation, not the starting state.

## Defect 1 — `eval-medium` and `eval-hard` are NOT paired across passes

The reset observation cannot be influenced by the policy, so for a given (regime, scene, index) it
must be identical in every pass. Measured:

| regime | slots whose reset varies | randomisation (`robosuitevgb/utils.py:67-90`) |
|---|---:|---|
| `train` | **0 / 200** | none |
| `eval-easy` | **0 / 200** | colour + lighting, `except_robot=True` |
| `eval-hard` | 21 / 200 (10 %) | + `moving_light`, `video_background` |
| `eval-medium` | **125 / 200 (62 %)** | + `moving_light`, **`except_robot=False`** |

At the endpoint's two policy-mode passes on the **same checkpoint**: **122 of 200 `eval-medium`
slots and 15 of 160 `eval-hard` slots saw different pixels**, against **0 of 200** for `train` and
`eval-easy`.

**This is probably not a bug.** RL-ViGen's regimes are *distributions* over visual conditions and
sampling them is the intent. But it settles what may be claimed:

- **`train` and `eval-easy` are paired** — same placements, same pixels. A difference between them is
  attributable to the regime alone. **The eval-easy result stands**: 0.8 σ, no detectable cost.
- **`eval-medium` and `eval-hard` are not paired.** Their numbers carry perturbation variance *on top
  of* episode variance, so they are noisier than their episode counts imply, and **a paired
  comparison is not available for them at all**.

**This retracts a finding.** I recorded the `eval-medium` mode-vs-sample gap (14.32 against 11.55,
3.6 σ) as a real, unexplained policy-mode effect. It is not: those two passes measured **different
visual conditions in 61 % of slots**. Withdrawn.

## Defect 2 — episode ids are not unique, and the ids' own comment claims they are

`eval_episode_ids` are built as `{baseline}-s{seed}-f{frame}-{regime}-sc{scene}-e{index}`, with the
comment *"Composite rather than a counter so it stays stable under re-runs and unique across the
fleet."*

**They omit `eval_policy_mode`.** Measured: 2,120 distinct ids, **760 duplicated — every one of them
an `endpoint/mode` row colliding with an `endpoint/sample` row — and all 760 pairs report different
returns.** The id names two distinct measurements, so it is not an identifier.

Harmless today because nothing joins on it. Not harmless the moment anything does, which is exactly
what an episode id is for.

**Fix:** include `eval_scope` and `eval_policy_mode` in the id. `scripts/eval_grid.py` is a
`CODE_MEMBER`, so this moves every family's evaluator revision.

## Batch the revision-moving fixes into ONE bump

Three changes now want an evaluator-revision move. Landing them separately costs three
re-attestations of seven families; landing them together costs one.

| change | why | member |
|---|---|---|
| episode id gains scope + policy mode | ids are not unique (above) | `scripts/eval_grid.py` (CODE) |
| `ppg` `nminibatch` clamp | executed config is not the declared one | `runnable/ppg/…` (FAMILY_RUNTIME) |
| write a frame-0 checkpoint | no family has a measured random floor | family runtimes |

**Precondition for all three: `ppg`'s cell must be collected first.** Editing any of them now makes
the in-flight cell's records stale against the live revision, and
`populate_evaluator_ledger.py` would refuse them.

**Already landed and needing no bump**, because `run_probe.sh` is in no member set: the terminal
checkpoint is now stamped `snapshot_<frame>.pt`, which takes endpoint frame provenance from
0 corroborated to all of them.

## What is reportable today

- **`train` and `eval-easy` returns, and the gap between them.** Paired, deterministic, self-consistent.
- **`eval-medium` / `eval-hard` returns as regime means** — with the perturbation variance stated,
  and **no paired claim** built on them.
- **Every row's mean/sd/count**, which match their own raw episodes.
- **Frame labels** for curve rows (corroborated) and, from the next run, endpoint rows too.
- **Not** episode-level joins, until the id carries the policy mode.
