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
| 1 | **Checkpoint frame** | **UNIFORM IN RETENTION, not in exact x-values** — all twelve now retain a terminal checkpoint and intermediate stamps on the 50k production grid. Rollout quanta mean intermediate saves can land near the requested boundary, and exact executed endpoints differ slightly; the endpoint is therefore the common reporting choice, while the complete trajectory remains reconstructible. | [`EVAL-PROTOCOL`](EVAL-PROTOCOL.md) §4, measured 2026-09-04 |
| 2 | **Checkpoint integrity** | UNIFORM — every cell runs `family.py check-finite`; [C57](CONSTRUCTION.md#c57) is the run that motivated it (NaN training continued for 70k frames). | per-cell gate |
| 3 | **Which modules act** (online vs EMA / target / momentum) | **VERIFIED, all twelve (2026-09-04).** Every baseline acts with its *online* actor/encoder; no EMA, target or momentum network is on any action path. **And nothing normalises OBSERVATIONS at eval** — the one place it could have bitten is `idaac`, whose checkpoint literally stores `[actor_critic, envs.ob_rms]`; `VecNormalize` is built with `ob=False` (`envs.py`, and `ctrl/vec_env.py:44,611` likewise), so the saved statistics were never applied and dropping them is correct rather than lucky. | `algos/drqv2.py:164-172`, `train.py:352-357`; `idaac/train.py:251-254`; `tests/test_record_conventions.py::test_no_baseline_normalises_observations_at_eval` |
| 4 | **Action rule** (mode vs sample) | DECLARED SPLIT — **4 sample** (`idaac`, `ibac_sni`, `ppg`, `ctrl`) / **8 mode**. | seam audit, `reported estimator` |
| 5 | **Module train/eval state at action time** | **VERIFIED INERT, all twelve (2026-09-04)** — and inert is not the same as identical, so the conditions are pinned by tests rather than trusted. No train/eval-sensitive layer is instantiated on *any* action path: `ppg`'s `ImpalaCNN` takes `batch_norm=False` and is never passed True; `ibac_sni`'s `nn.BatchNorm2d` sits behind `--use_bn` (default False) under `model_type='default2'` (default `'default'`); `rad`/`soda`/`alda` have `BatchNorm1d` only inside SODA's aux `SODAMLP`; `idaac`, `ctrl` and the RL-ViGen five instantiate none. `idaac` additionally shares one `evaluate()` between `train.py` and `test.py`, so its two evaluators cannot disagree. | `tests/test_record_conventions.py::test_batchnorm_stays_off_the_action_path_in_ppg_and_ibac_sni`; [`EVALUATOR-DELTA`](EVALUATOR-DELTA.md) |
| 6 | **Step-dependence of the action rule** | **VERIFIED inert, all twelve (2026-09-04).** Only the RL-ViGen five take a step at all — `act(obs, step, eval_mode=True)` computes `stddev = schedule(step)` and then returns `dist.mean`, so the schedule cannot reach an eval action. The other seven take no step in their action signatures (`select_action(obs)`, `act(inputs)`, `get_actions`, `select_action(params, ...)`), so "evaluate this checkpoint" is well-defined without also fixing a step. | `algos/drqv2.py:167-171`; the seven action calls in `scripts/eval_grid.py` |

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
| 17 | **Eval env vs train env construction** | **VERIFIED, all twelve (2026-09-04).** In every family the eval env comes from the *same constructor* as the training env and differs only in the regime/scene arguments: the five fall back to `robo_config.yaml` (`mode: train`, `scene_id: 0`) — so **the retention denominator really is the training distribution**; `ctrl` builds all three envs from one `_mk` lambda at one seed; `ibac_sni`'s `evaluate.py` and `train.py` use an identical `make_rlvigen_env(env, seed + 10000*i)`; `alda` uses one `_build(_mode)`; `idaac` one `make_rlvigen_venv`; `ppg`'s training call simply omits `mode`/`scene_id` and takes the same defaults ours passes explicitly. **The dmc_gb distinction is now reproduced too**: `train` uses `seed`, while every non-train evaluation regime uses the upstream `seed + 42` test-environment offset. | `train.py:78,92-95`; `robo_config.yaml:31`; `dmc_gb/src/train.py:78-95`; `eval_grid.py:dmc_eval_seed`; `ctrl/train_ppo.py:130-141`; `ibac_sni/.../evaluate.py:55-57` |

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

**The gaps were concentrated, and three of the four are now closed.** This file first reported
terms 3, 5, 6 and 17 — *which weights act, in what mode, with what step-dependence, in what env* —
as verified only for the RL-ViGen five. Naming them as one block made them one afternoon's reading
rather than five unrelated questions, and **3, 5 and 6 are now verified across all twelve**: online
weights everywhere, no observation normalisation at eval, no mode-sensitive layer on any action
path, no step-dependence outside the five where it is inert. **Term 17 is now closed too**: every family builds its eval env from the same constructor as its
training env, differing only in regime and scene — which is the property the whole comparison
assumes and nothing had checked. It surfaced one real difference, `dmc_gb`'s `seed + 42` eval
offset; the shared evaluator now applies that offset for non-train regimes and keeps the train
seed unchanged.

**Two of those verifications found the answer was "safe for a reason, not by luck", which is the
distinction worth keeping.** `idaac`'s checkpoint carries observation statistics that our evaluator
ignores — correct only because `ob=False`. `ppg` and `ibac_sni` ship BatchNorm that would break a
batch-size-1 evaluator — off only because two flags default False. Both facts are now asserted by
tests, because a verification that rests on a default is a verification with an expiry date.

**One term is a UNITS split and it is the deliverable's blocker.** Term 9 alone is why R3 reads NOT
MET. Everything else either agrees or is declarable.

**Two terms were verified today that could have invalidated results silently** — term 17 (the
denominator really is the training distribution) and term 19 (both aggregations are pooled). Both
were assumed true by everything built on them, and neither had been checked.

**What this file does not do.** It cannot certify that the enumeration is complete; a derivation
from a definition covers what the definition names, and the definition is itself a choice. The
honest limit is the seam audit's: this removes ways two numbers could differ, and is not evidence
that the ways nobody derived are absent.
