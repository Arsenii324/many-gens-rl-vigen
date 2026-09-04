# instruction.md — what was inherited, what was decided, and why

Read this before changing anything. It is the map from **prior artifacts** — the supervisor's
brief, RL-ViGen upstream, the group's Procgen reference repo, the sibling ALDA/IDAAC project, and
the previous contents of this repo — to **what is in the tree now**, with the reason for each
step. It is written so that someone who has seen none of that history can act on the code without
re-deriving it.

Written 2026-08-10. Baseline of the previous state: commit `de879a0` (`git show de879a0:<path>`
retrieves anything deleted).

---

## 0. Status

| | |
|---|---|
| Benchmark | RL-ViGen **robosuite**, Door + Lift, pixel `(9,84,84)` uint8, action `(7,)` |
| Runs locally | yes — M2 Pro / MPS, 79–118 pixel-steps/s per env, no CUDA anywhere |
| Baselines implemented | **all 12** of the brief, plus `random` as the negative control |
| Data-gated | `svea`, `sgqn`, `soda` — their overlay augmentation needs Places365 *to train*; evaluating a checkpoint does not. `setup/fetch_overlay_dataset.sh` gets the **val** split (~2 GB, not the 24 GB train split); `train.py` refuses before writing anything if it is absent. |
| Trainers | two: off-policy (`rlgen/trainer.py`) and on-policy (`rlgen/trainer_onpolicy.py`) for PPG / IBAC-SNI / IDAAC. One evaluator, one logger, one protocol across both — asserted by `test_on_policy_and_off_policy_runs_are_comparable`. |
| Tests | `pytest tests` — counts live in [`docs/VALIDATION.md`](docs/VALIDATION.md), which is dated |
| Mutation | a curated catalogue **and** an unbiased random-operator sweep; scores and their progression in [`docs/VALIDATION.md`](docs/VALIDATION.md) |
| Verified end to end | `setup/install.sh` → `baselines/drqv2/train.sh Door 0 --smoke` → `plot.py` |
| Cross-validated | random-policy floor reproduces the sibling project's independent measurement on both tasks (§5b) |

**The four things to know first**

1. **The evaluator cannot see which algorithm it is running.** `evaluate(protocol, policy, ...)`
   takes `policy: Callable[[obs], action]`. That is the whole design; everything else follows.
2. **All twelve are implemented, none is an alias.** The registry status is read by `train.py`,
   by `plot.py` and by the doc generator, so nothing here can present a stub as a baseline.
   `ctrl` was an alias of `curl` until the paper was checked — it is PPO-based, and the old
   `class CTRLAgent(CURLAgent)` was a name-similarity mistake this repo had inherited. What is *not* claimed: that PPG and IBAC-SNI reproduce
   published returns — nobody has published either on RL-ViGen robosuite, so there is no number
   to reproduce (§5a, and the header of `rlgen/algos/onpolicy_ext.py`).
3. **Unpatched RL-ViGen silently evaluates on the training distribution.** See §3 P1. If
   `setup/apply_patches.py --check` fails, no number from the tree means anything.
4. **The curated mutation score is not the one to trust.** 17/17 measures the defects I thought
   of. The random operator sweep, which I did not design, scored **30%** against the same suite;
   getting it to **68%** is where most of the real defects were found (§5c).

---

## 1. What was inherited, and what happened to it

| Source | What it gave us | Status now |
|---|---|---|
| **Supervisor's brief** (chat message) | The requirement set. Verbatim in [`docs/TASK.md`](docs/TASK.md) §1, rendered in §2, turned into checkable criteria R1–R7 in §3. | The contract. |
| **RL-ViGen** `90d8b8c` | robosuite envs, the visual-regime machinery, and reference implementations of DrQ-v2 / SVEA / SGQN / CURL / DrQ. | Vendored, gitignored, **patched** (§3). Its algos are loaded by file path (§4). |
| **Group's Procgen reference** `~/Downloads/IBAC_SNI_torch` (= `train-procgen-pytorch` + one baseline) | The *layout* the supervisor is asking for, and the config mechanism. Also a live demonstration of the anti-pattern (§2). | Copied as a pattern, not as code (§2). |
| **Sibling project** `../gen-rebuttal/vigen-idaac` | The proven robosuite seam and its hard-won invariants: truncation from the horizon, raw-vs-normalised reward, one process per env, verify the mode at the seam. Also the measured random-policy floors and DZ's own eval protocol. | Reimplemented in `rlgen/envs.py` with the invariants carried across; **not** imported (§6). |
| **Previous contents of this repo** (`07c3f12`) | A 12-constructor adapter layer, a setting resolver, a protocol-audit database, five planning documents. | Reviewed in [`docs/REVIEW.md`](docs/REVIEW.md); deleted (§7). |

---

## 2. The Procgen reference: what was copied, and what was deliberately not

`~/Downloads/train-procgen-pytorch_example` and `~/Downloads/IBAC_SNI_torch` are **two forks of
the same upstream** (`joonleesky/train-procgen-pytorch`), and the supervisor pointed at them as
the pattern for this brief.

*Correction to a first reading of them:* they are **not** a clean before/after pair. `_example`
carries its own unrelated local modifications — a `find_principal_component` method, a
`noise_amplitude` parameter, and an `experiments/<algo>/<env>.sh` layout that the IBAC copy does
not have — so the diff between them is not "what adding a baseline costs". Everything below was
re-checked against the IBAC copy directly rather than read off that diff.

**Copied — the layout.** One file per baseline next to the others; a shared `common/`; a single
hyperparameter file; per-launch `.sh` scripts; a `logs/<benchmark>/<env>/<algo>/<run>/` tree. The
IBAC baseline is contained in two new files — `agents/ppo_ibac.py` and `common/policy_ibac.py` —
plus a config entry and a dispatch branch in `train.py`; `logger.py`, `storage.py` and `model.py`
are untouched. That containment is the readability requirement, implemented rather than asserted.
Our equivalents: `baselines/<x>/`, `rlgen/`, `configs/vigen.yaml`,
`logs/<benchmark>/<task>/<baseline>/<mode>-seed<n>/`.

**Copied — the config mechanism, which is better than what I first proposed.** The launch script
names a *hyperparameter set*, not an algorithm (`--param_name easy-200-ibac`), and `train.py`
reads the algorithm out of it (`algo = hyperparameters.get('algo', 'ppo')`, then a branch on it).
`easy-200-ibac` is `easy-200` plus exactly three keys — `beta`, `sni`, `sni_lambda` — and of the
eighteen shared keys, **seventeen are byte-identical**; the eighteenth is `algo` itself, which is
the selector rather than a hyperparameter. **Equal training conditions become the default a baseline must opt
out of, key by key, in a diffable file.** `configs/vigen.yaml` does this, and
`tools/gen_baselines.py` prints each baseline's deviation set into its README so a reviewer sees
the whole opt-out at a glance.

**Deliberately NOT copied — where the eval lives.** `bigfish.sh` promises *"Eval и логирование
идентичны LSP (`Eval/avg_reward`, `Eval/std_reward` каждый 5-й rollout)"*. The code does not
deliver that:

- the eval loop is inside `agents/ppo_ibac.py:160-203`;
- `agents/ppo.py` has **zero** eval-related lines — the baseline IBAC-SNI is compared against
  never evaluates at all;
- `common/logger.py` records only training statistics; the shipped `logs/` contain no eval curve;
- the eval env is rebuilt inside the agent with `VecNormalize(..., ob=False)` — so the reported
  number is a **normalised** return under a name that reads like a raw one;
- and with `num_levels=0`, i.e. the **full** level distribution including the training levels.

Two protocol axes set invisibly in one agent file, and an eval convention hand-matched to a
different repo by copying. This is the failure the brief's `!ВАЖНО!` paragraph legislates against,
occurring inside the group's own reference — and it is the strongest argument for the structural
form of the requirement: **the evaluator must not be able to see which algorithm it is running.**

---

## 3. RL-ViGen: five patches, two of them load-bearing

Full detail in [`setup/VENDORED.md`](setup/VENDORED.md). Applied by `setup/apply_patches.py`,
which is idempotent, refuses to guess if an anchor moved, and has a `--check` mode wired into the
test suite.

- **P1 — `make_env` ignored its caller's `mode`.** Every environment was built as `train`
  regardless of the request, so train and eval render identically and the generalisation gap is
  **zero by construction** — a plausible-looking clean result, not a crash. The sibling project
  ran with this defect, in their words, *"for the whole project until now"*. `rlgen/envs.py` now
  **asserts** the regime it was given matches the one it asked for, and
  `test_eval_modes_actually_look_different_from_train` additionally compares pixels, because a
  regime that is requested, reported and visually identical would pass the assertion.
- **P2 — the background video was loaded for every mode, and `assets/video/train/` does not
  exist.** Upstream's robosuite path does not run in train mode out of the box
  (`ValueError: negative dimensions are not allowed`). `video_buf` is read only by `eval-hard`,
  so the load is now guarded.
- **P3 — `robo_make` dropped `mode` and the resolved regime was unreachable.** Threaded through
  and hoisted onto the outermost wrapper, which is what makes P1's assertion possible.

**robosuite must be RL-ViGen's fork, installed editable.** Both call themselves `1.4.0` and differ
in 761 files; the eval modes need 40 `Custom*` textures that only the fork has; and a wheel build
drops the assets because `setup.py` declares no `package_data`. **mujoco must be 2.3.7**: on 3.x,
`train` runs and every eval mode raises `AttributeError: 'MjModel' object has no attribute
'tex_rgb'` — a failure confined to the path whose numbers get published.

---

## 4. Decisions, with the alternative that was rejected

| # | Decision | Why, and what was rejected |
|---|---|---|
| **D1** | **Benchmark = RL-ViGen robosuite, Door + Lift.** | The previous repo had ten baselines on DMC `walker_walk` and two (IDAAC, ALDA) on robosuite with a different protocol — *not one benchmark*, so no eval-code fix could have made them comparable. robosuite was chosen over DMC because it runs here (verified), because the sibling project's ports, measured floors and DZ's own protocol are all defined on it, and because `dm_control` is not even installed. Rejected: keeping both as "two tracks" — it defers the decision and doubles the surface. |
| **D2** | **The evaluator takes an opaque callable.** | Review discipline decays; a missing parameter does not. Rejected: an `evaluate(agent, ...)` with a code-review rule against branching — which is exactly what the Procgen reference has, and it did not hold. |
| **D3** | **Absent baselines are declared `absent`, never stubbed.** | A stub gets a row in a table. `ctrl` is declared an alias of `curl` and is labelled `ctrl (= curl)` on every figure. Rejected: implementing six algorithms badly to make the matrix look full — the previous repo's `class RAD(SAC): pass` and `ppg.py` with no `update()` are what that produces. |
| **D4** | **Budget in environment frames, `action_repeat` folded in.** | "Steps" means agent steps in some codebases and simulator steps in others; the resulting factor-of-N errors are the most common defect in RL tables. `action_repeat=1` here, stated rather than inherited — RL-ViGen's `cfgs/config.yaml` defaults to 2 and no task config overrides it. |
| **D5** | **Aggregation is the mean, not IQM.** | **The decision stands; the original reasoning did not survive review (2026-08-10).** It argued that IQM trims the successful tail of a bimodal *per-scene* distribution, citing mean > IQM in 82% of the sibling's evaluations, ratio 1.418. That is a level error: IQM aggregates over **runs** (task x seed), never over episodes within a run, so episode-level bimodality does not bear on it and nobody proposes trimming episodes. Mean within a run is simply correct. What statistic to use *across* runs is a separate question, open until there is more than one seed. The statistic is in the protocol and in the hash either way, so a run using another one is incomparable rather than quietly different. |
| **D6** | **The gap is an absolute difference, never a ratio.** | A ratio against a near-zero training score produced a published "131.3% retention" off a denominator of 0.11 in the sibling project. Normalised quantities require a measured floor and a gate; that is analysis, not a default figure. |
| **D7** | **Replay stores single frames and stacks on read.** | Storing stacked observations costs 31 GB for a 500k-frame run; single frames cost a third. The sibling project made the same change (140 GB → 23.3 GB). The hazard is the ring wrap splicing two episodes into one stack; two guards, and a test that drives the buffer past capacity twice and checks every sampled stack frame by frame. |
| **D8** | **Superseded code deleted, not moved to `legacy/`.** | A `legacy/` directory is context rot: it is read, trusted, and edited. Git history at `de879a0` holds all of it and §7 says what is where. |
| **D9** | **Baseline `train.sh` and `README.md` are generated from the registry.** | Seven hand-written near-identical launch scripts are seven places to drift, and drift in a launch script is invisible until a run finishes with the wrong budget. Generated files are committed (the use case is "clone and run"), and a test regenerates and diffs so a stale one fails the build. |
| **D10** | **Upstream algos are imported by file path.** | `algos/__init__.py` is `from algos import pieg`, and `pieg.py` imports `hydra` and `torchvision`; the natural import made five of twelve baselines unconstructible on a machine without them. |

---

## 5. What is guaranteed by a test rather than by intention

Each row is a property the brief requires and a mechanism that fails the build when it stops
holding. This is the part worth checking first if you doubt anything here.

| Property | Test |
|---|---|
| Exactly one eval stepping loop in the tree | `test_exactly_one_eval_stepping_loop` (AST walk) |
| The evaluator has no algorithm-bearing parameter | `test_evaluate_cannot_see_the_algorithm` |
| …and provably ignores its label parameters | `test_evaluate_ignores_the_label_parameters` (same policy, two labels, identical numbers) |
| No logging-key literal outside `tags.py` | `test_no_tag_literals_outside_tags_module` |
| Every runnable baseline emits the required tags | `test_every_runnable_baseline_emits_the_required_tags` |
| Episode count comes only from the protocol | `test_episode_count_comes_only_from_the_protocol` |
| Evaluation runs on the scenes it was given | `test_evaluate_uses_exactly_the_scenes_it_was_given` |
| The reported statistic is the declared one | `test_aggregation_follows_the_protocol` |
| Two protocols cannot share a log | `test_logger_refuses_to_mix_two_protocols_in_one_run` |
| No protocol constant is hardcoded outside `protocol.py` | `test_no_protocol_value_is_hardcoded_outside_this_module` |
| Fixtures are derived from the factory, not declared | `test_obs_shape_is_derived_from_the_factory_not_declared` |
| Frame stacks never splice episodes after a ring wrap | `test_stacked_frames_never_cross_an_episode_boundary_after_wrap` |
| Every baseline honours `deterministic` | `test_every_runnable_baseline_respects_the_deterministic_flag` |
| Aliases are declared and labelled | `test_aliases_are_declared_and_labelled` |
| The vendored upstream is patched | `test_upstream_patches_are_applied` |

**The mutation catalogue is the check on the checks.** `mutants/run.py` copies the tree, edits a
file under `rlgen/`, and runs `pytest tests` unchanged. 14/14 are killed. It earned its keep during
the build: `M4-action-repeat-ignored` **survived**, because every episode-length test ran at
`action_repeat=1` where `horizon // action_repeat == horizon` and the defect is invisible. The
missing test was written, and the mutant now dies.

A run also begins by checking that an **unmutated** copy passes — without that, a catalogue could
report 100% purely because the copied tree does not run, which is the class of vacuous
verification the previous `run_mutants.py` embodied (it replaced `agent.act` with a function that
exhibited the defect and asserted three lines later that it did; its "100%, 60/60" would have held
against an empty suite).

---

## 5a. Every baseline: what existed before, and whether it was used

Asked directly: were the historical implementations any good, or were they skipped? Per baseline,
with what was actually in the tree at `de879a0` and the verdict.

| baseline | what existed at `de879a0` | verdict |
|---|---|---|
| `drqv2` | RL-ViGen's own, plus a byte-identical dead copy | **used** — upstream's, loaded by file path |
| `svea` | as above | **used** — upstream's |
| `sgqn` | as above | **used** — upstream's (needs `captum`, undeclared upstream) |
| `curl` | as above | **used** — upstream's |
| `drq` | upstream's, plus a local copy that **did not parse** (unclosed paren, `drq.py:211`) | **used** — upstream's; the broken copy deleted |
| `ctrl` | `class CTRLAgent(CURLAgent)` with an empty `__init__` | **skipped — it was MISLABELLED.** CTRL is Cross-Trajectory Representation Learning (Mazoure et al., ICLR 2022): a **PPO**-based method with a self-supervised objective over trajectory pairs. Someone had assumed CTRL ≈ CURL from the name. Rewritten on the shared PPO core |
| `rad` | `class RAD(SAC): pass` — the name, none of the method | **skipped as an implementation, reused as a backbone.** Its `sac.py`/`modules.py`/`augmentations.py` neighbours are a genuine SAC stack, so those were recovered and RAD's actual contribution (augmenting the replay batch) written on top |
| `soda` | `soda.py` with a real `compute_soda_loss` / `update_soda` and a SODA predictor | **used** — the only one of the six "absent" baselines whose previous code was substantively correct |
| `ppg` | `PPGAgent(nn.Module)`: a DrQ-v2 encoder/actor/critic, an unused `aux_critic`, and `act()`. **No `update`, no rollout buffer, no clipped surrogate, no phasic phase.** Separately, `cleanrl_ppg.py` — real PPG, but `Categorical`, `ProcgenEnv`, 64×64 NHWC | **both skipped, for different reasons.** The first has no training rule at all; the second is a correct implementation of a *different* benchmark's PPG and cannot run on continuous 7-DoF robosuite. Rewritten on the shared PPO core |
| `ibac_sni` | `VIBEncoder` + `IBACSNIAgent`, **no `update`** | **skipped** — same reason. Written from the paper; DZ's attached Procgen port could be read but not reused |
| `idaac` | full package, but its imports name the sibling project's package | **used** — copied and re-pointed |
| `alda` | full package, same import problem | **used** — copied and re-pointed |

Two patterns worth naming. Where the previous work produced a **network** it was usually fine;
where it needed a **training rule** it usually produced only the network and a name. And every
file that could not run was still importable and still registered, so nothing announced the gap —
which is why `status` is now machine-readable and `train.py` refuses on it.

## 5b. Cross-validation against an independent measurement

The strongest evidence that the whole stack is wired correctly is not a test — it is that this
codebase, written from scratch, reproduces a number that a *different* codebase measured on the
same benchmark. The random-policy floor is the right quantity for it: it exercises env
construction, the reward path, episode termination and aggregation, and it depends on no training.

100 evaluation episodes over 10 scenes, deterministic-irrelevant (the policy is uniform):

| | this repo | sibling project (`../gen-rebuttal/vigen-idaac`, independent implementation) |
|---|---|---|
| Door | mean **1.54** (eval-easy) / 1.74 (train), 0/110 success | mean **1.69** ± 1.40, 0/100 success |
| Lift | mean **7.46**, sd 8.61, median 3.50, max 40.0, 0/110 success | mean **7.80** ± 11.38, median 3.02, max 60.1, 0/100 success |

Lift is the informative one. Its shaped reward pays `1 − tanh(10·d)` at every one of 500 steps, so
a random arm accumulates a large return without ever lifting the block — a heavily right-skewed
distribution with mean ≫ median. Both implementations reproduce that shape: mean roughly double
the median, a tail reaching into the tens, and **zero successes**. The two means differ by 4%,
well inside the sampling error of a distribution with that spread at n=100.

This is the number to re-check first if anything about the environment stack is ever changed.

## 5c. How the tests were themselves tested — and why the first answer was wrong

`mutants/run.py` (curated, 17 mutants) scores **17/17**. Taken alone that number is close to
meaningless: I wrote the mutants *and* the tests that catch them, so it measures my imagination.

`mutants/sweep.py` removes me from the loop. It picks mutation sites uniformly at random over the
AST of `rlgen/` — comparison-boundary flips, arithmetic swaps, boolean-connective swaps,
small-integer perturbation, dropped negations — with no regard for whether any test covers them.
Run against the suite as it stood after the curated catalogue passed 14/14 at the time, it scored:

> **12/40 — 30%.**

Whole modules were unconstrained. `rlgen/trainer.py` had no tests at all: the seed-frame boundary,
the update cadence, the save cadence, the replay `add` arguments and the weights-source fallback
all survived. `rlgen/replay.py`'s index arithmetic, `bootstrap_ci`'s percentile arithmetic and
`registry.status_table` were untested. And — the sharpest one — mutating the truncation comparison
in **`RoboEnv`** survived while the identical mutation in `SyntheticEnv` was killed, because every
test ran on the synthetic backend and the real environment's own logic was never executed.

Three test files were written in response, *after* seeing the survivors: `tests/test_trainer.py`,
`tests/test_real_env.py` (which runs the real simulator), and `tests/test_sweep_gaps.py`.

**And the first round barely worked.** Thirty-three new tests moved the score from 12/40 to
**14/40**. I had written tests for the *modules* the sweep named rather than for the *specific
mutants* it produced — a different and much weaker thing. Reading the survivor list line by line,
and fixing what each line actually said, is what took it to **68% out-of-sample**. If there is
one transferable lesson here, it is that "the sweep says module X is untested, so I wrote tests
for module X" does not work.

**The stopping rule.** Fixing a survivor makes the seed that found it in-sample, so re-running
that seed is no longer an honest estimate. Four seeds were used: 1 (30% → retired), 23 (60% →
three fixes → retired), 41 (55% → five fixes → retired), and a final fresh seed measured on the
shipped state and *not* fixed against. Its survivors are recorded in
[`docs/VALIDATION.md`](docs/VALIDATION.md) §5 as open items, because fixing them would invalidate
the only number that describes what is actually committed.

Two honest limits on the sweep, which is why survivors are printed with their diffs rather than
just counted:

- **Equivalent mutants cannot be killed by anyone.** Perturbing a constant inside an error message,
  or a bound that is never reached, changes no behaviour. Counting them as failures understates
  sensitivity; a script must not decide which is which, so triage is by hand.
- **`SyntheticEnv` lives in `rlgen/envs.py` but is test instrumentation.** Mutations to it are
  mutations to the instrument, not to the system under test.

## 6. Why the sibling project's code was reimplemented, not imported

`../gen-rebuttal/vigen-idaac/vigen_idaac/envs.py` is a mature seam with four invariants worth
having, and they were carried across verbatim in intent: truncation derived from the known horizon
(the env's `discount` cannot be used — `ExtendedTimeStepWrapper` turns the terminal `0.0` back
into `1.0`); raw reward never touched by a normaliser; one process per env (`GlobalHydra.clear()`
on every construction, and the GL backend must be chosen before mujoco is imported); and the mode
verified at the seam rather than trusted.

It was not imported because doing so is what broke the previous repo: `algos/alda/train.py` still
says `from vigen_idaac.envs import SubprocVecEnv`, a package that does not exist in this tree, so
both ALDA entry points fail at import. A benchmark repo that depends on a sibling checkout is not
cloneable, which is requirement R7.

The two projects should stay related by *documented invariants*, not by a path.

---

## 7. What was deleted, and where to find it

All at `de879a0`. Retrieve with `git show de879a0:<path>`.

| Deleted | Why | Anything worth keeping |
|---|---|---|
| `rlgen-vigen/` | Twelve agent constructors behind one `act()`, plus copies of five upstream algos that nothing imported (four byte-identical, one — `drq.py:211` — with an unclosed paren that made it the only first-party file in the repo that did not parse). Superseded by `rlgen/registry.py`. | The adapter idea; reimplemented. |
| `rlgen-core/` | 5-field `Protocol` and a setting resolver for cross-benchmark name collisions. The resolver is good code, and this repo is single-layer (RL-ViGen modes), so it has nothing to resolve. | `rlgen-core/data/{audit,axes,benchmarks}.yaml` — a 23-record protocol-audit database. Real research data, belonging to the paper track, not to a benchmark repo. |
| `01`–`05_*.md` | The protocol-audit *paper* project. `05_repo_architecture.md` deferred `rlgen-vigen` to "only if there is time" and its matrix listed algorithms that do not overlap with seven of the twelve implemented. | `05` predicted the exact failure this rebuild fixes ("the repos drift apart"). |
| `run_mutants.py` | Not mutation testing (§5). | The mutant *ideas*, generalised into `mutants/catalogue.py`. |
| `test_eval_invariants.py` | `DummyEnv` hand-declared `(3,84,84)`; the pipeline produces `(9,84,84)`. It tested a shape that never occurs. | The invariant list, now derived from the real factory. |
| `test_normalization.py` | Zero `assert`, zero `sys.exit` — exits 0 whether 0/8 or 8/8 pass. | — |
| `audit_*.py`, `resolve_setting.py`, `protocol_variance.py` | `resolve_setting.py` and `audit_tools.py` computed their data path one directory too high and had never worked; `audit_param_counts.py` printed `Total Parameters: 0` with no warning for exactly the three agents it was written to special-case. | — |
| `fix_*.py` | Four one-shot source rewriters with no idempotence guard. Replaced by `setup/apply_patches.py`, which has one. | — |
| `submit_kaggle.sh` | The repo's only `.sh`; both branches called `python -m rlgen_vigen.eval` — it never trained anything. Its `--episodes 100` also disagreed with `eval.py`'s default of 3. | — |
| `results/` | Six files, four data rows, two empty. Every row was a randomly-initialised network, emitted alongside a card asserting `checkpoint_selection: final`. | Nothing. It is the artifact most likely to mislead. |
| `third_party/rl-iter` | An embedded git repo, which breaks clones. | The IBAC-SNI reference is `~/Downloads/IBAC_SNI_torch`. |

---

## 8. Known gaps — stated, not hidden

- **Six baselines are absent.** `ppg`, `rad`, `ibac_sni` and `soda` need work this rebuild did not
  do; `idaac` and `alda` need their imports re-pointed and their evaluation routed through
  `rlgen/evaluate.py`. `rlgen/registry.py` says what each needs. The matrix is *incomplete and
  says so*, which is the only honest state for it.

  This was a deliberate choice over the alternative. Four of the six could have been made to
  *appear* in the table cheaply — a `class RAD(SAC): pass`, a PPG-named DrQ-v2 actor — and that is
  precisely what the previous repo did and what `docs/REVIEW.md` F5–F7 record. A baseline that is
  not the algorithm it is named after does more damage in a comparison table than a missing row,
  because a missing row is visible.

- **Two upstream algorithms are shipped and deliberately not registered.** RL-ViGen also ships
  `algos/pieg.py` (PIE-G, 335 lines) and `algos/srm.py` (SRM, 57 lines), both real implementations
  that would register as cheaply as SVEA or SGQN did. Neither is in the supervisor's brief, so
  neither is here. Recorded because "upstream has it and the repo does not" otherwise reads as an
  oversight; it is scope discipline, and reversing it is a two-line change to
  `rlgen/registry.py`.
- **No real training run has been done.** What is verified is the pipeline: a smoke run through
  the identical code path on the real environment, and the whole test and mutation suite. Full
  runs (500k frames × baselines × tasks × seeds) are remote work; see `docs/compute.md`.
- **Success rate is recorded only when robosuite exposes `_check_success`,** and is `None`
  otherwise. It is never synthesised from a return threshold: that would be a different quantity
  under the same name.
- **Evaluation is sequential.** 100 episodes × 500 steps at ~100 steps/s is ~8 minutes per eval
  point. Parallelising it is safe in principle (episodes are independent) but must preserve
  record-for-record identity, so it needs the equivalence test before it is worth doing.
- **Checkpoint loading is never exercised.** The repo writes checkpoints and verifies their
  contents, but nothing round-trips one through `DrQV2Adapter.load_state_dict` and re-scores it.
  For a benchmark whose output *is* checkpoints, this is the most substantial remaining test gap.
  Named by the final sweep; see `docs/VALIDATION.md` §4.6.
- **The mutation catalogue covers 17 specific defects.** Anything outside it is unmeasured — which
  is why the unbiased sweep exists, and why its survivors are listed rather than counted.
- **Seeds.** One seed per configuration so far. The brief does not specify a count; the Procgen
  reference uses 3; the sibling project found 2 insufficient to separate methods. `docs/TASK.md`
  §6 Q7 proposes 5.

## 8b. Known defect: the on-policy trainer overshoots the frame budget

Found by reading the results table after the first full real-simulator sweep, not by a test.

Off-policy runs stop at exactly `total_frames`; on-policy runs stop at the end of the **rollout
that crosses it**. With `total_frames=3000` and `num_steps=256` the PPO-family baselines finish at
**3072** frames while the others finish at 3000. Every run still carries the same protocol hash,
so `plot.py` puts them in one panel — and their final points sit at different x.

Why it matters: R4 is "the same training length for everyone", and 3072 != 3000. At smoke scale
the error is 2.4%; at 500k frames with the same rollout length it is 0.05%, so this does not
invalidate a full run. It does mean the FINAL point of an on-policy curve is not frame-matched to
an off-policy one, and a frame-matched comparison is exactly what the brief asks for.

Two honest fixes, neither applied yet:
  * truncate the last rollout so collection stops on the budget (changes the last update's batch
    size, which is a real if small algorithmic change); or
  * round `total_frames` down to a multiple of `num_steps * action_repeat` at Protocol
    construction and record the rounded value in the card, so the budget a run reports is the
    budget it ran.

The second is preferable: it makes the protocol state the truth rather than making the trainer
approximate it. `test_the_budget_is_honoured_exactly` currently covers only the off-policy loop,
which is why this was invisible.

## 9. Open questions for the supervisor

In [`docs/TASK.md`](docs/TASK.md) §6, ten of them, ordered by how much work the answer changes.
The four that block real runs:

1. **We do NOT have the group's reference evaluation.** This was got wrong once and is worth
   stating precisely, because a whole document was built on the error.

   `../gen-rebuttal/ext/alda/Nd_ln.py` is a single-file ALDA training script that DOES run on
   RL-ViGen robosuite (`from robosuitevgb import make_env`, task Door, separate train/eval modes)
   and is group-authored — it carries Russian comments, so it is not the ALDA paper authors'
   code. The sibling project's `vigen_alda/eval_dz.py` transcribes its eval block
   (`Nd_ln.py:593-665`) line-accurately and calls that "DZ's evaluation protocol".

   **It is not.** The repo owner has confirmed that `Nd_ln.py` is *not* offered as an example of
   good RL-ViGen evaluation. So `eval_dz.py` implements *a* protocol from *a* script — 10 episodes
   on scene 0, reduced by mean — and not the group's reference. Our own protocol (100 episodes
   over 10 scenes, mean, raw undiscounted return) is therefore **ours**, declared in the protocol
   card, and is not a reproduction of anyone's reference.

   Checked exhaustively: **neither `~/Downloads` example touches RL-ViGen at all.** Both
   `IBAC_SNI_torch` and `train-procgen-pytorch_example` are pure Procgen — no occurrence of
   `robosuite`, `vigen`, `Door`, `Lift` or `scene_id` anywhere in either tree — and their eval
   concepts (`num_levels=0`, `start_level`, `distribution_mode`, `VecNormalize` on returns) have
   no RL-ViGen analogue, because RL-ViGen's axes are `scene_id` and visual `mode`. They are good
   examples of *layout*, of the config mechanism, and of the IBAC-SNI algorithm. They are not
   examples of RL-ViGen evaluation.

   And the owner reports that `Nd_ln.py` is not faithful even to the ALDA paper.

   **So there is no endorsed reference evaluation for this benchmark, from any source.** Our
   protocol is therefore built from the requirement rather than copied from an example: raw
   undiscounted return, 100 episodes over 10 scenes, mean, deterministic policy, every field
   stated in the protocol card and hashed. That is a *stronger* position than matching an
   unendorsed script, but it must be said out loud rather than implied — a reader who assumes we
   reproduced someone's reference would be wrong.

   The brief's action item — *"Для Арсения: Обсудить eval на RL Vigen + дать эталонный код"* —
   is still **open**, and so is Arsenii's reported "косяк". Both are worth one message.
2. **Which ALDA?** The brief cites `arXiv:2001.01046`; the sibling project ports
   Batra & Sukhatme `arXiv:2410.07441`. Different papers, and only one makes the existing port
   reusable.
3. **Held-out or full-distribution evaluation?** We train on scene 0 and evaluate on all ten,
   which *includes* the training scene — stated in the protocol as
   `eval_includes_train_scenes: true`. The Procgen reference evaluates on the full distribution
   too. Whichever is chosen must be the same for all twelve.
4. **What is "LSP"?** The reference's `bigfish.sh` says its logging is "identical to LSP". If LSP
   is the group's reference baseline, its tag names are the standard `rlgen/tags.py` should adopt,
   and we should be handed that repo rather than re-deriving the convention from a shell comment.
