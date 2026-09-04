Written 2026-09-04.

# Two cells at 100k — the first competent policy, and the first defined retention number

`scripts/preprod_table.py` was run over these jobs first and the output was discarded rather than
committed. It selects **one** regime per row, so `drqv2` appeared as a single floored eval number
with the training-regime row — the entire result — absent; and its standing prose explains a 10k
budget, which these are not. The generator is right for the pass it was built for. This note is
written by hand for these two cells.

## What ran

| job | baseline | frames | budget shape |
|---|---|---|---|
| `bt15e9v1k2ngmb71hnjn` | `drqv2` | 100,000 | 20 eval episodes every 25k, `CELL_TIMEOUT_SECONDS=12600` |
| `bt1lnh6b11u231cvh4ho` | `idaac` | 99,328 | idaac's own evaluator, 10 episodes |

Neither sets `RLVIGEN_EVAL_MODE`, so the eval regime is **eval-easy** (`runnable/_launch/rlvigen.sh:36`).
Both ran on the container under `egl` — the only platform on which their numbers mean anything
([C95](../CONSTRUCTION.md#c95)).

## `drqv2` — solves the training scene, retains ~nothing

| frames | train return | train success | eval-easy return | eval-easy success |
|---|---|---|---|---|
| 0 | 0.78 | 0.00 | 0.84 | 0.00 |
| 25,000 | 28.33 | 0.00 | 18.94 | 0.00 |
| 50,000 | 119.96 | 0.00 | 35.13 | 0.00 |
| 75,000 | **482.42** | **1.00** | 2.44 | 0.05 |
| 100,000 | **480.56** | **1.00** | 1.44 | 0.00 |

**Retention at the endpoint: 1.439 / 480.56 = 0.30%.**

Two things make this the most useful row the project has produced.

**The competence gate passes.** §3b #15's objection to any retention number was that a method which
never learns has gap ≈ 0 and reads as perfect generalization. Here the method plainly learns —
success 1.00 in the training regime, a return 264x the random floor — so the near-zero retention is
a result about generalization and not an artefact of incompetence. Every previous cell in this
project was floored in **both** regimes, where the ratio is undefined rather than small.

**The collapse is not "worse than random", it is "at the floor".** eval-easy 1.439 sits just under
[C55](../CONSTRUCTION.md#c55)'s 1.82, which invites the reading that the eval path is broken —
[C95](../CONSTRUCTION.md#c95) being the precedent for preferring that explanation. It survives the
check: `robosuitevgb/utils.py:67-104` sets `randomize_dynamics = False` in **every** branch, so the
regimes differ in colour, lighting, moving light and background and in nothing touching physics,
reward or the success test. A uniform-random policy ignores observations, so the floor is
regime-invariant and transfers to eval-easy unchanged; and 1.82 − 1.439 = 0.38 is far inside a
single episode's spread. The honest phrasing is **at the floor**.

**It is one seed.** It ranks nothing and supports no comparison between baselines.

## `idaac` — the shared evaluator's burden, now discharged

Its own evaluator reports `test/mean_episode_reward` **5.347** at 99,328 frames, success 0.000.
Our harness on the same checkpoint (`bt1ip5f8c6mqqm7fd2bn`, 20 episodes, eval-easy scene 0, CUDA)
reports **9.023** (sd 6.488); train regime 9.528 (sd 11.412).

Ratio 1.69x — which no band calls agreement. Dispersion says otherwise: their number is a mean of
**10** episodes of a stochastic policy, and the difference of +3.676 is **z = 1.46**, not
distinguishable at 95%. A one-sample interval on our 20 episodes alone would have said the reverse
(`[5.99, 12.06]` excludes 5.347), which is why `audit_shared_evaluator.py` now runs the two-sample
test rather than banding a point ratio. Verdict `CONSISTENT`, deliberately not `PASS`: the
reference publishes no spread, so ours stands in for it and the test is conservative about
declaring disagreement.

Both numbers are well clear of the floor, which is what the earlier attempt lacked — the
9,216-frame comparison (1.663 against 3.01) straddled it and could say nothing.

## What these two cells do and do not settle

- **Settle**: the pipeline produces competent policies at 100k; retention is computable; the shared
  evaluator agrees with `idaac`'s own within sampling error; the archive arithmetic for I3
  (296 MB/cell at 100k → ~1.5 GB at 6e5 → ~53 GB for 12x3, against ~30 GB free here).
- **Do not settle**: anything about ranking (one seed each), anything about the other ten
  baselines, and whether `drqv2`'s collapse is representative or a property of this single scene.
