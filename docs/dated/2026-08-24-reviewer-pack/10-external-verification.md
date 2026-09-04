# 10 — External verification: what held, what was already known, what was wrong

**Written 2026-08-25. Dated snapshot, not a living document.** It records one external review pass
against the public upstream repository and this project's response to it. Claims here were
re-verified locally before being accepted; where they were not, that is stated.

The reviewer had access only to the public `gemcollector/RL-ViGen` repository, its vendored
`third_party/robosuite`, and its shipped paper/spreadsheet. They had **no access** to this
project's code, checkpoints, `results/`, or register. That boundary matters for reading what
follows: they could check "what does upstream do", never "what does our clone do".

## The finding that mattered

**Object placement was never seeded, and the defect is ours, not upstream's.** Confirmed, extended,
fixed, and recorded as [C69](../../CONSTRUCTION.md#c69).

The reviewer observed that `robosuite/utils/placement_samplers.py` draws from bare `np.random`
(lines 167, 183, 196, 198) with no `random_state`, and proposed it as a candidate mechanism for the
replicate variance. Verified. They then flagged that they could not find a call site for
`VGBWrapper.seed()` and asked us to run the grep ourselves.

**The grep gave a sharper answer than the hypothesis.** `train.py:47` and `eval.py:54` *do* seed
global numpy via `utils.set_seed_everywhere` (`utils.py:38`), so upstream's own training and
evaluation paths are seeded. **`scripts/eval_across_scenes.py` — our own offline evaluator, and the
source of every retention number this project reports — never did.** So the reviewer's "upstream
may have a gap" turned out to be "we have a gap upstream does not."

Measured across three processes at identical `seed=0`, `scene_id=0`, `mode=train`: the door body
moved `x = -0.128117 / -0.112590 / -0.120571`, ~1.6 cm, the sampler's full declared range. Seeding
global numpy first collapses all three onto `[-0.116047, -0.358795, 1.1]`. End-to-end through
`run_scene`, returns went from `[2.265003, 0.748782]` vs `[1.650736, 0.712101]` to bit-identical.
One line, mutation-verified.

**What it cost us:** [C67](../../CONSTRUCTION.md#c67)'s central reading. That entry treated the
19/200-vs-28/200 replicate as the project's *measured evaluation-noise floor* and concluded that
seed variation and evaluation noise "have not been separated". The 47% was our unseeded placement.
A floor is planned around; a bug is removed. That correction is the single most valuable thing this
review produced, and it came from someone who could not see the file containing the defect.

## Confirmed, and useful as independent corroboration

Each of these already existed in the register; the value is that they were re-derived from upstream
by someone with no sight of our notes.

- **Door's reward structure and the 250 ceiling** ([C62](../../CONSTRUCTION.md#c62)) — `door.py`
  `_check_success()` at line 423 (`hinge_qpos > 0.3`, non-latched) and `reward()` at line 205.
  The reviewer was careful to state they verified the *algebra*, not that a policy empirically
  saturates near 250. That distinction is correct and we should keep it.
- **The published Door-Easy numbers** — per-seed cells from `results/evaluation_score.xlsx`
  reproducing 3.6 / 6.6 / 14.0 exactly, and cross-checked against the paper's Figure 19 aggregate
  to confirm "(Easy)" is the condition we call `eval-easy`. That cross-check is more than
  [C31](../../CONSTRUCTION.md#c31) had.
- **The 12× budget** — Table 6 gives Door `int(6e5)`; 6e5 / 5e4 = 12.
- **SGQN shipped-vs-paper** ([C64](../../CONSTRUCTION.md#c64)) — `1e-4`/`0.93` shipped against
  Table 6's `8e-5`/`0.9`. Independently confirmed on both sides.
- **`TASK_RANDOM_SEED["Door"]`** — `train` is `[100]*10`, `eval-easy` is ten distinct seeds. We
  additionally closed their open caveat: **all ten** train texture entries are single-valued, not
  just the ~6 they viewed.

## Already known — not new, though the reframing is

**`feature_dim` 50-shipped vs 256-in-paper** is recorded at [`FAITHFULNESS.md`](../../FAITHFULNESS.md):71
and is open decision 2 in [`STATUS-AGAINST-THE-GOAL.md`](../../STATUS-AGAINST-THE-GOAL.md):121.

**But the conclusion drawn from it is new and is now folded into
[C64](../../CONSTRUCTION.md#c64).** The reviewer's point is that upstream's shipped defaults and
upstream's published numbers are two *different configurations*, and the repository ships no bridge:
`RL-ViGen-upstream/scripts/` contains `train.sh` (a DMC example), `eval.sh` (CARLA), `carlatrain.sh`,
`habitrain.sh`, `locoeval.sh`, `locodmc_eval.sh` — **no robosuite launcher**, and no shell script in
the repo mentions `env=robosuite`. Verified.

So "match the paper" was never a well-defined option. That converts C64's recommendation from an
appeal to the founding rule into an argument from reproducibility, and it changes the honest
sentence in any write-up to: *no run of the shipped repository is comparable to their published
curve, because that curve came from a configuration the repository does not contain.*

## Where the review was wrong, or did not apply

- **Success counting (their B3).** They worried that if our evaluator reads `info['success']` once
  at episode end, a door that opened and later swung shut would not count — a real hazard, since
  `_check_success()` is non-latched. **It does not apply**: `scripts/eval_across_scenes.py:166`
  does `succeeded = succeeded or bool(...)` *inside* the step loop. We latch. They correctly
  flagged this as something they could not check.
- **The `±50%` resolution estimate they reason from is void**, through no fault of theirs — it is
  C67's number, and C69 withdraws it.
- **Their B5 (SVEA's augmentation) is explicitly labelled recollection, not a lookup**, and we have
  not checked it either. It stays open, correctly flagged by them as a prior rather than a finding.

## What this says about the process

The most valuable finding in this review came from **someone who could not see the defective file**,
reasoning from upstream's structure to a hypothesis about ours, and then handing us a two-minute
grep rather than a conclusion. The project's own instruments had every opportunity to find it: the
grids record a `seed` field, the evaluator was written here, and
[C41](../../CONSTRUCTION.md#c41) had already flagged run-to-run variance as a live concern. Nothing
looked, because a `seed` field reads as evidence that seeding happened.

That is the same shape [`SYSTEM.md`](../../SYSTEM.md) names as this project's signature failure —
a defect at a *join* between two individually-correct things — with a new instance: the join between
"we passed a seed" and "the thing that varies was seeded by it".
