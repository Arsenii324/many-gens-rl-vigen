Written 2026-09-04.

# What the reported number depends on — every term, derived from its definition

## Why this file exists, and why it is not another checklist

[`EVAL-PROTOCOL.md`](EVAL-PROTOCOL.md) says how evaluation is *run*.
[`EVALUATOR-DELTA.md`](EVALUATOR-DELTA.md) compares our evaluator to each baseline's own.
`scripts/audit_comparability_seam.py` checks axes mechanically. All three grew **by accretion** —
someone noticed an axis, it got derived. That is how the `rad`/`soda` crop sat in five documents
for eighteen days without reaching the axis machinery, and it is why the seam audit's own summary
refuses to output "comparable": *"a fact about the list, not about the twelve"*.

This file is the other direction. It starts from **what the number is** and enumerates every term
that must be pinned for it to be well-defined, so the list is a consequence of the definition
rather than of anyone's memory. A term nobody has examined is then **visible as a gap in a
derivation**, not absent from a list.

**The number.** For baseline *b*, the reported quantity is a ratio of two means:

> **R(b) = Ê[G | eval regime] ÷ Ê[G | train regime]**, where
> **Ê[G | ·] = (1/N) Σᵢ Σₜ r(sₜ, aₜ)** over N episodes of the *saved* policy π_b.

Everything below is a term in that expression. Nothing below is optional: each one, if it differs
between two baselines and is not declared, makes their two R values different quantities.

**Status vocabulary.** **UNIFORM** — same for all twelve, established. **DECLARED SPLIT** — differs,
recorded, survivable by declaring it. **UNITS SPLIT** — differs in a way that changes what the
number *means*; must be removed or converted. **OPEN** — decision outstanding. **UNEXAMINED** — the
term is identified and nobody has checked it; this is the column that matters.

---

## I. The policy π_b — which weights act, and how

| # | term | status | established by |
|---|---|---|---|
| 1 | **Checkpoint frame** | **OPEN, and newly constrained** — the intersection of checkpoint frames across the twelve is the **endpoint alone**; four families save terminal-only. A cross-baseline *curve* is not producible. | [`EVAL-PROTOCOL`](EVAL-PROTOCOL.md) §4, measured 2026-09-04 |
| 2 | **Checkpoint integrity** | UNIFORM — every cell runs `family.py check-finite`; [C57](CONSTRUCTION.md#c57) is the run that motivated it (NaN training continued for 70k frames). | per-cell gate |
| 3 | **Which modules act** (online vs EMA / target / momentum) | **VERIFIED for the RL-ViGen five** — `act()` uses the *online* encoder and actor, and `save_snapshot` pickles the whole agent, so the object restored offline is the object that acted. **UNEXAMINED for the other seven.** | `algos/drqv2.py:164-172`, `train.py:352-357` |
| 4 | **Action rule** (mode vs sample) | DECLARED SPLIT — **4 sample** (`idaac`, `ibac_sni`, `ppg`, `ctrl`) / **8 mode**. | seam audit, `reported estimator` |
| 5 | **Module train/eval state at action time** | **PARTIAL** — the five use `utils.eval_mode`; `rad`/`soda` now do too (fixed 2026-09-04, previously a bare `no_grad`). **UNEXAMINED for `alda`, `idaac`, `ppg`, `ctrl`, `ibac_sni`.** Inert unless a train/eval-sensitive layer sits on the action path — `modules.SODAMLP`'s `BatchNorm1d` shows that is one instantiation away. | [`EVALUATOR-DELTA`](EVALUATOR-DELTA.md) |
| 6 | **Step-dependence of the action rule** | **VERIFIED inert for `drqv2`** — `act()` computes `stddev = schedule(step)`, but `eval_mode` returns `dist.mean`, so the schedule cannot reach an eval action. **UNEXAMINED for the rest**; any baseline whose eval action depends on a training-step schedule would make "evaluate this checkpoint" ill-defined without also fixing the step. | `algos/drqv2.py:167-171` |

## II. The environment — what the policy acts in

| # | term | status | established by |
|---|---|---|---|
| 7 | **Task and horizon** | UNIFORM — Door, 500 steps, every episode ends by time limit. | seam audit |
| 8 | **Regime reachable in one run** | DECLARED SPLIT, 7 ways. | seam audit |
| 9 | **Scene set** | **UNITS SPLIT — the only one.** Seven evaluate scene 0 alone; the five sweep ten. This *is* R3 and P-C76. | seam audit; `scripts/requirements.py` |
| 10 | **Placement RNG** | DECLARED — door placement comes from the **global** numpy RNG ([C69](CONSTRUCTION.md#c69)). Ours seeds per eval; **theirs does not** (`set_seed_everywhere` runs once, at `train.py:47`), so their during-train evals are not reproducible from a checkpoint. Not a bias — both sample the same distribution. | corrected 2026-09-04 |
| 11 | **Renderer** | FORCED — `egl` in-container; a container-trained policy read 12–14× low locally ([C95](CONSTRUCTION.md#c95)). | C95 |
| 12 | **Render size and crop** | DECLARED SPLIT — 84 / 64 / 100, **and** `rad`/`soda` see an 84 *centre crop of a 100 frame*, a different field of view rather than a different resolution. | seam audit, `crop policy` |
| 13 | **Frame stack** | DECLARED SPLIT — 3×8, 1×4. Deliberately not equalised ([C2](CONSTRUCTION.md#c2)). | seam audit |
| 14 | **Action repeat** | UNIFORM at 1, reached four ways. | seam audit |
| 15 | **Observation layout and scaling** | DECLARED SPLIT, 5 ways. | seam audit |
| 16 | **Action bounds / clipping** | DECLARED SPLIT — 3 induced distributions. | seam audit, PART2 Finding 6 |
| 17 | **Eval env vs train env construction** | **VERIFIED for the RL-ViGen five 2026-09-04** — `train_env = robo_make(...)` passes no `mode` and no `scene_id`, falling back to `robo_config.yaml` (`mode: train`, `scene_id: 0`), which is exactly what the retention denominator is built as. **The denominator's claim to be "the training distribution" holds.** **UNEXAMINED for the other seven.** | `train.py:78,92-95`; `robo_config.yaml:31` |

## III. The estimator — how episodes become a number

| # | term | status | established by |
|---|---|---|---|
| 18 | **N, and its allocation across scenes** | DECLARED — ours sets N *per scene*; **theirs divides N across scenes** (`per = num_eval_episodes // len(scenes)`), so at the shipped default of 10 a during-train per-scene value is **one episode**. | `train.py:152` |
| 19 | **Aggregation** | **UNIFORM, verified 2026-09-04** — both form a **pooled** mean (theirs `total_reward / n` over all scenes; ours concatenates then means). Mean-of-means would differ if per-scene counts were unequal; neither does it. | `train.py:192-194`; `eval_grid.py:624` |
| 20 | **Success definition** | UNIFORM — `_check_success`, **any step**, patch P11's convention. | seam audit |
| 21 | **Return accumulation** | UNIFORM — all twelve *report* raw return; three normalise for the learner only, settled by wrapper order. | REGISTER 2026-09-02 |
| 22 | **Dispersion** | NEW 2026-09-04 — records carry per-episode returns **and** per-episode success flags, so intervals and success-conditioned returns are computable rather than approximated. | E6 |

## IV. The comparison — what the ratio is against

| # | term | status | established by |
|---|---|---|---|
| 23 | **Denominator** | **OPEN — P-C76 / R3.** Currently train regime, scene 0, deliberately not swept. | `RESEARCH-FRAME.md` |
| 24 | **Floor and competence gate** | ESTABLISHED — 1.82 ([C55](CONSTRUCTION.md#c55)), and **regime-invariant**: `randomize_dynamics = False` in every branch, so regimes differ only in appearance and a random policy scores the same in all of them. | verified 2026-09-04 |
| 25 | **Seeds, and what a count licenses** | DEFAULT SET — adaptive spending; 1 seed licenses existence/floor claims only. | [`EVAL-PROTOCOL`](EVAL-PROTOCOL.md) §4b |

## V. Provenance — whether the number can be trusted or repeated

| # | term | status | established by |
|---|---|---|---|
| 26 | **Determinism** | DECLARED, **ours not upstream's** — `torch.use_deterministic_algorithms(True)` ([C70](CONSTRUCTION.md#c70)). | EVALUATOR-DELTA E2 |
| 27 | **Platform recorded** | UNIFORM — `native.recorded_on` on every record, so a C95 violation is mechanically findable. | `normalize_curves.record` |
| 28 | **Instrument identity** | **2 of 12 discharged** (`drqv2` PASS, `idaac` CONSISTENT). Ten baselines' numbers would come from an instrument not yet shown to measure what theirs does. | `scripts/audit_shared_evaluator.py` |

---

## What this derivation says that the accreted lists did not

**The gaps are concentrated, not scattered.** Terms 3, 5, 6 and 17 — *which weights act, in what
mode, with what step-dependence, in what env* — are **verified for the RL-ViGen five and partly for
`dmc_gb`, and unexamined for `alda`, `idaac`, `ppg`, `ctrl`, `ibac_sni`.** That is one coherent
piece of work on five families, not five unrelated questions, and it is the same five whose
evaluator rows in `EVALUATOR-DELTA` are thin. **It is also the cheapest remaining work in this
project: it is reading, not compute.**

**One term is a UNITS split and it is the deliverable's blocker.** Term 9 alone is why R3 reads NOT
MET. Everything else either agrees or is declarable.

**Two terms were verified today that could have invalidated results silently** — term 17 (the
denominator really is the training distribution) and term 19 (both aggregations are pooled). Both
were assumed true by everything built on them, and neither had been checked.

**What this file does not do.** It cannot certify that the enumeration is complete; a derivation
from a definition covers what the definition names, and the definition is itself a choice. The
honest limit is the seam audit's: this removes ways two numbers could differ, and is not evidence
that the ways nobody derived are absent.
