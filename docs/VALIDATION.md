# Validation record

What was actually run, what it returned, and what it does **not** establish. Every number here
was produced by a command in this repo on 2026-08-10; each command is given so it can be re-run.

Machine: Apple M2 Pro, MPS, no CUDA. `barannikov-work/.venv`, Python 3.11.

---

## 0. Current state — 2026-08-10, commit `b0c8fd9`+

Superseding every number further down, which is kept because the *progression* is the argument.

| | |
|---|---|
| baselines | **12/12 implemented**, none an alias, plus `random` |
| real-simulator runs | **13 of 13** (12 baselines + `random`), each with a checkpoint — but under protocol hash `7e674231852bca46`, which is **now superseded**. `env_patches` gained P4 and then P5, so the hash is `c0d7bc7c…`; those runs no longer pool with new ones. They were 3k-frame smoke runs, so nothing is lost — but do not mix them. |
| tests | **149** (148 passed, 1 skipped) · full `pytest tests` ~**115 s** |
| curated catalogue | **19/19 killed** — and now environment-independent (see §0.1) |
| unbiased sweep | seed 101, out of sample: **13/25 (52%)**, over a pool that finally includes `trainer_onpolicy.py` |
| remote | DataSphere `gt4.1` verified end to end: GL, CUDA, patches, protocol hash, throughput ([`../datasphere/README.md`](../datasphere/README.md)) |
| trainers | two — off-policy and on-policy — sharing one evaluator, logger, protocol and cadence |

### 0.04 Mutation evidence REFRESHED against the current tree (2026-08-10, late)

The catalogue and sweep results below at §0 were measured at 16:53; the last code change was
19:34, so they described a tree that no longer existed — P5, nine config fixes, the CTRL change and
four new tests all landed after. **Re-run on the current tree: curated catalogue 19/19 killed, 0
survived.** M15 and M17 — the two that were unkillable while Places365 is installed — now die by
the complementary tests added for exactly that. Unbiased sweep re-run on a fresh out-of-sample seed
(202) was still in progress at the time of writing.

**Memory, measured rather than assumed.** The replay buffer at `replay_capacity=100000` is
**1.97 GB**; a naive stacked-observation buffer would be **5.9 GB**, which is the payoff of decision
D7 (store single frames, stack on read). One full-scale run is therefore ~3–4 GB against 32 GB and
**does not swap**. The 3.3 GB of swap and 311k pageouts observed today came from *concurrency* —
two mutation suites at once, each with a pytest at ~1.6 GB, plus (before the SKIP fix) 1.6 GB tree
copies per mutant. Operational rule: one mutation suite at a time on this machine. Corollary for
remote: `gt4.1` has 31 GB, so packing four runs per box is ~14 GB — memory-feasible, which is what
the hyperparameter research recommended for CPU reasons.

### 0.05 FIRST NUMERICAL corroboration of the evaluator (2026-08-10)

Everything establishing our evaluator until now was **structural** — one stepping loop, an opaque
policy, a hashed protocol, tests that mutate labels and require identical numbers. None of that is
evidence the number agrees with an independent implementation.

`tools/crosscheck_against_rlvigen_eval.py` runs the same seeded random policy through
`rlgen.evaluate()` and through a transcription of RL-ViGen's own `eval.py::robo_eval` calling
`robo_make` **directly**, bypassing every line of `rlgen`. Door, `eval-easy`, scenes 0–9,
3 episodes each:

| | n | mean | sd | median |
|---|---|---|---|---|
| ours | **100** | 1.4764 | 1.3768 | 0.8834 |
| RL-ViGen's loop | **100** | 1.3706 | 1.1105 | 0.7895 |

difference **+0.1058**, SE of the difference **0.1769**, **|z| = 0.60**.

**Minimum detectable effect.** At n=100 per side the smallest difference this design would resolve
at |z|=2 is ≈0.354, about **24% of the mean**. So the defensible claim is: *our harness introduces
no systematic distortion larger than roughly a quarter of the mean.* Not "the two agree" — that
would be a null reported without its sensitivity.

A first pass at n=30 gave difference +0.4464 (|z| = 1.35, MDE ≈44%). Quadrupling the sample cut the
difference to +0.1058 and the bound to 24%, which is the behaviour expected if the first gap was
sampling noise rather than a real offset. Both passes are recorded because the *progression* is
part of the evidence.

Command: `python tools/crosscheck_against_rlvigen_eval.py --episodes-per-scene 10`

It also says nothing about whether the protocol is the *right* one — that is `PREMISES.md` P4 and
a separate argument.

### 0.1 Three corrections to earlier numbers in this file

**The 60% sweep figure was inflated by a non-hermetic test.**
`test_the_plotter_draws_exactly_the_logged_values` computed its walk root as
`dirname(dirname(logdir))`, and since `logdir` sits *one* level below the fixture's temp
directory, that resolved to the machine's entire `$TMPDIR`. It discovered runs left by concurrent
processes and compared this run's logged values against another run's. `pytest tests` **is** the
mutation oracle, so a test that fails for unrelated reasons records a spurious KILL.

Caught in the act: seed 101 mutant 3 mutated `rlgen/replay.py` and was recorded killed by *the
plotter test* — which compares one run against itself and cannot legitimately detect a replay
change. On the hermetic tree, the same seed and the same mutation **survives**. Fixed, plus
`plot.discover` now refuses `$TMPDIR`, `/` and `$HOME` as logs roots.

**The sweep never mutated `rlgen/trainer_onpolicy.py`.** `TARGETS` was hand-written and never
gained the module — 34 of 465 mutable sites, 7.3% of the pool, unreachable since the day it was
created, while the number was described as a sweep over `rlgen/`. The figure was not wrong; its
stated scope was, which is worse. `TARGETS` is now derived from the package.

**The catalogue's score depended on whether Places365 was installed.** M15 and M17 are only
observable when the overlay dataset is *absent*, and the test guarding them skips when it is
present. So the catalogue read 19/19 before the dataset was fetched and 17/19 after, **with no
code change in between**. Both environments are now covered; verified by running those two mutants
alone and getting 2/2 killed, each by the newly added test.

### 0.2 Sweep seed 101 — survivors, triaged

12 survivors of 25. Triage matters more than the rate: a survivor is either a real gap or a
demonstrably equivalent mutant, and saying which is the point of the exercise.

| site | verdict |
|---|---|
| `agents.py:326` `on_policy = True` | **Equivalent, and a finding.** `train.py:117` routes on `spec.on_policy` from the registry; the adapter attribute is read by nothing. Two sources of truth, one dead. Now guarded by a consistency test rather than a pinned literal. |
| `replay.py:102` `hi = idx + frame_stack + 1` | **Boundary conservatism, not a defect.** Investigated by diffing the valid-index sets across five buffer configurations: the mutation admits a few extra transitions at the *oldest* end whose stacks are clamped-degenerate rather than corrupt. An attempt to kill it with a next-side content invariant failed, which is the evidence. The invariant was kept anyway — nothing else asserted the `next` side. |
| `registry.py:332` (hyperparameter default), `protocol.py:66` (subprocess timeout), `trainer.py:187` (a log format string), `trainer.py:222` (a schema version), `agents.py:132` (a dummy-observation bound) | **Equivalent or configuration.** Killing these would mean asserting literals, which measures nothing. |
| `registry.py:77` `@dataclass(frozen=True)` | Real but minor: registry specs being immutable is a design guarantee nothing tests. |
| `envs.py:153/170` (`self._checked`) | Not yet triaged. |
| `trainer_onpolicy.py:173` (LR schedule) | **Only reachable because of the TARGETS fix.** Not yet triaged. |

**What this does not establish**, unchanged and important: no baseline has been trained at
meaningful scale; PPG, IBAC-SNI and CTRL are verified structurally and *not* against published
returns; and the `logs/` produced so far are contaminated by the append defect in §0.3 and must be
regenerated before anything is aggregated from them.

### 0.3 `episodes.csv` accumulated across reruns

Run directories are keyed by (task, baseline, mode-seed), so a re-run reused the path and the
logger appended, with nothing marking the boundary. `Door/drqv2` holds two runs at commits
`621ddfc` and `de879a0-dirty`; `Door/soda` holds six runs' worth of rows at frames=0 against three
at frames=1500 and 3000 — so a per-point mean averages a different number of runs at different x,
and any CI is too narrow because n is inflated by repeats. A new `RunLogger` opening a non-empty
`episodes.csv` now refuses; appending within one run is unchanged and pinned by a test.

## 1. Environment — six task × mode combinations

```bash
python setup/apply_patches.py --check && python setup/install_assets.py --check
```

| task | mode | obs | act | steps/s | regime reported |
|---|---|---|---|---|---|
| Door | train | `(9,84,84)` uint8 | `(7,)` | 100 | `train`, video_background `False` |
| Door | eval-easy | `(9,84,84)` uint8 | `(7,)` | 103 | `eval-easy`, `False` |
| Door | eval-hard | `(9,84,84)` uint8 | `(7,)` | 79 | `eval-hard`, `True` |
| Lift | train | `(9,84,84)` uint8 | `(7,)` | 110 | `train`, `False` |
| Lift | eval-easy | `(9,84,84)` uint8 | `(7,)` | 110 | `eval-easy`, `False` |
| Lift | eval-hard | `(9,84,84)` uint8 | `(7,)` | 82 | `eval-hard`, `True` |

Each env is asked for a mode and then **asserts** it was built in that mode. Unpatched upstream
fails this for every eval mode — see [`../setup/VENDORED.md`](../setup/VENDORED.md) P1.

`test_eval_modes_actually_look_different_from_train` additionally compares pixels: a regime that
is requested, reported, and visually identical to train would pass every other check while
measuring nothing.

---

## 2. Cross-validation: the random-policy floor, against an independent implementation

The strongest single piece of evidence in this document, because it is not a self-consistency
check. `../gen-rebuttal/vigen-idaac` measured these on the same benchmark with a codebase that
shares no line with this one.

```bash
python train.py --config random --task Door   # 100 eval episodes over 10 scenes + 10 train
python train.py --config random --task Lift
```

| | this repo | sibling project |
|---|---|---|
| Door, mean return | **1.535** (eval-easy, n=100) · 1.759 (train, n=10) | **1.69 ± 1.40** (n=100) |
| Door, sd | 1.247 | 1.40 |
| Door, success | **0 / 110** | **0 / 100** |
| Lift, mean return | **7.542** (n=100) | **7.80 ± 11.38** (n=100) |
| Lift, sd · median · max | 8.675 · **3.563** · **40.0** | 11.38 · **3.02** · **60.1** |
| Lift, success | **0 / 110** | **0 / 100** |

Measured *after* the warm-up-reset fix (§4.4). Before it, the same command gave Door 1.541 and
Lift 7.460: the fix removes a systematic effect on one episode in ten, and at these sample sizes
it moves the aggregate by well under a tenth of a standard deviation. It is worth having because
the effect is systematic, not because it changed this table.

Lift carries the signal. Its shaped reward pays `1 − tanh(10·d)` at every one of 500 steps, so a
random arm accumulates a large return without ever lifting the block — mean roughly double the
median, with a long right tail. Both implementations reproduce that shape and both report zero
successes. The means differ by 4%, inside sampling error for a distribution with that spread at
n = 100.

**Re-check this first** if anything in the environment stack changes.

---

## 3. Test suite

```bash
pytest tests -q          # 94 passed
```

| file | what it constrains |
|---|---|
| `test_eval_identity.py` | the structural R3 guarantees — one stepping loop, an evaluator blind to the algorithm, no tag literals, episode count and scenes and aggregation from the protocol only |
| `test_contract.py` | protocol hashing and validation, env seam, replay wrap safety, agent interface, registry, generated-file freshness, upstream patches |
| `test_trainer.py` | the training loop: eval scheduling, update cadence, checkpointing, weights provenance, budget, the negative-control path |
| `test_real_env.py` | the **real** simulator: contract, truncation, action repeat, raw reward, mode and scene verification, pixel difference between regimes, the success probe |
| `test_sweep_gaps.py` | what the unbiased sweep found unconstrained — replay index arithmetic, bootstrap intervals, registry reporting, the exploration schedule, shipped defaults |
| `test_plot_and_success.py` | the shared plotter: no per-baseline branch, jsonl/tfevents agreement, seed aggregation, refusal to plot nothing |

---

## 4. Mutation testing — two numbers, and why both are reported

### 4.1 Curated catalogue — 14/14

```bash
python mutants/run.py
```

Fourteen hand-written defects in `rlgen/`, each a claim that the suite catches it. All killed.

**This number alone is close to meaningless.** I wrote the mutants and I wrote the tests that
catch them, so it measures what I thought of. It is reported for completeness and because the
catalogue documents *which specific failures* the repo is defended against — that part is
genuinely useful, and the entries are the ones that would produce a wrong table rather than a
crash.

The runner begins by checking that an **unmutated** copy passes. Without that, a catalogue could
report 100% purely because the copied tree does not run — which is the exact shape of the
verification this repo replaced (`run_mutants.py` replaced `agent.act` with a function exhibiting
the defect and asserted three lines later that it did; its "100%, 60/60" would have held against
an empty test suite).

### 4.2 Unbiased operator sweep — the number that matters

```bash
python mutants/sweep.py -n 40 --seed 1     # in-sample after fixes
python mutants/sweep.py -n 40 --seed 7     # out-of-sample
```

Mutation sites picked uniformly at random over the AST of `rlgen/`, with no regard for coverage.

| measurement | kill rate |
|---|---|
| **before** any sweep-driven test (suite had just scored 14/14 curated) | **12/40 — 30%** |
| after, seed 1 — *in-sample*, these survivors were fixed | see §4.3 |
| after, seed 7 — **out-of-sample**, never inspected | see §4.3 |

The out-of-sample number is the honest estimate. Re-running the seed you tuned against is an
in-sample score and flatters the result the same way the curated 14/14 does.

#### Seed 202, out-of-sample, 2026-08-10: **7/25 killed (28%)**, 18 survivors — all triaged

Run after the `ext/` SKIP fix and the `TARGETS`-derived-from-package fix, so the pool includes
`trainer_onpolicy.py`. **Do not read 28% against seed 101's 52% as a regression.** At n=25 the
binomial standard error near p=0.4 is ~10pp, so the two are ~2.4 SE apart — this design cannot
resolve a difference that size, and no code that either sweep covers changed between them. If the
seed-to-seed spread matters for a claim, raise n; at n=25 the estimate is worth ±20pp, not ±2pp.

Triage of all 18, by hand (the runner refuses to classify them, by design):

| survivors | verdict |
|---|---|
| `replay.py:101,102,104,106` (4) — the `if self._full:` write-head window | **Equivalent-or-benign.** Verified empirically: shifting `lo` back or `hi` forward yields a **strict subset** of the correct valid set, and every existing assertion is a per-index property that a subset satisfies trivially. `hi+1` is an **exact** equivalent mutant at the tested geometry. Measured across four geometries, the real window admits **0** corrupted transitions (sound) while over-excluding 6–8 safe ones (deliberately conservative), so no two-sided test can pin these without hardcoding the literal window width — which `test_sweep_gaps.py` explicitly declines to do. |
| `envs.py:239,257`, `agents.py:132` (3) | **Test-double / verification-helper code** that lives inside the production package. `SyntheticEnv`'s target and reward shaping, and the determinism-probe's random observation — mutating them preserves the property each exists to exercise. |
| `agents.py:228` — `tgt is not None and hasattr(...)` | **Equivalent under all real inputs** (every saved key maps to a live module, so `and`/`or` coincide). But it surfaced something real: `load_state_dict` **silently skipped keys it did not recognise**, so a stale checkpoint would load *partially* with no error. For a repo built against silent failure that is the wrong default. **FIXED 2026-08-14** — all three sites (`DrQV2Adapter`, `SacAdapter`, `PPOFamilyAdapter`) now raise `KeyError` on a mismatched key, red-green verified across all three; `AldaAdapter` needed no fix, its `load_state_dict` already indexes by explicit key and raises naturally. `tests/test_pipeline_integrity.py::test_load_state_dict_refuses_a_mismatched_checkpoint_instead_of_loading_it_partially`. |
| `logging_.py:57` (`getsize(...) > 0`), `logging_.py:107` (`sort_keys`), `trainer.py:65` (`verbose` default), `agents.py:346` (`batch_size` default), `tags.py:19` (`SCHEMA_VERSION`), `trainer_onpolicy.py:86,93` (7) | **Equivalent or cosmetic.** A real `episodes.csv` always exceeds 1 byte, so `>0` vs `>1` cannot differ; the rest are defaults that every call site overrides, or serialisation ordering. |
| **`trainer_onpolicy.py:173` (2)** — `learner.set_lr(min(1.0, frames / max(1, total_frames)))` | **A REAL COVERAGE GAP — but be precise about the two mutants.** `linear_lr_decay` defaults to **`True`** (`rlgen/algos/idaac/config.py:58`), so this line sets the learning rate of every on-policy arm (`idaac`, `ppg`, `ibac_sni`, `ctrl`) via `lr * max(0.0, 1 - frac_done)`, and **nothing in the suite touched `set_lr`, `param_groups` or `linear_lr_decay`** — the whole anneal was unpinned. The *specific* survivors, though, are plausibly **equivalent**: the call site clamps with `min(1.0, ...)` and `set_lr` clamps again with `max(0.0, ...)`, so a mutation of either guard is masked by the other. **CLOSED 2026-08-10** by two tests in this file, red-green verified (halving the anneal slope and rescaling the call-site fraction each turn them red). They pin the schedule because it is load-bearing and untested — not because they kill these two mutants. |

**Net:** 1 real test gap (the on-policy LR anneal), 1 real code defect found incidentally
(`load_state_dict` swallowing unknown keys), 16 equivalent-or-cosmetic. That ratio is what a
mature suite should look like on an unbiased sweep — the number to watch is *which* survivors are
real, not the headline percentage.

**What the first 30% localised**, all of it real:

- `rlgen/trainer.py` had **no tests at all** — seed-frame boundary, update cadence, save cadence,
  the replay `add` arguments, the weights-source fallback;
- `rlgen/replay.py`'s index arithmetic (`_valid_indices`, the `_stack` boundary);
- `bootstrap_ci`'s percentile arithmetic;
- `registry.status_table`;
- and the sharpest: mutating the truncation comparison in **`RoboEnv`** survived, while the
  identical mutation in `SyntheticEnv` was killed — every test ran on the synthetic backend, so
  the real environment's own logic was never executed. A synthetic backend that lets the real one
  go untested is the same failure this repo exists to prevent, in miniature.

### 4.3 What the sweep actually bought, in order

| # | when | measurement | note |
|---|---|---|---|
| 1 | suite had just scored 14/14 curated | **12/40 (30%)** seed 1 | the first honest number |
| 2 | after `test_trainer.py`, `test_real_env.py`, `test_sweep_gaps.py` (79 tests) | **14/40 (35%)** seed 1 | **+2 only** — see below |
| 3 | after fixing what the *survivor list* actually said | **24/40 (60%)** seed 23, out-of-sample | |
| 4 | after three more targeted fixes (89 tests) | **see §4.5** seed 41, out-of-sample | |

**Row 2 is the lesson.** Thirty-three new tests moved the kill rate by two. I had written tests
for the *modules* the sweep named, not for the *specific mutants* it produced — which is a
different and much weaker thing. Reading the survivor list line by line, and fixing what each line
actually said, is what moved 35% → 60%.

### 4.4 Defects the validation found, that nothing else did

Every one of these was found by trying to break the repo, not by trying to finish it.

- **A dataset dependency that fails late.** Smoke-running a *second* baseline (`svea` on Lift)
  died at the first gradient step: SVEA's overlay augmentation needs Places365 (~24 GB). By then
  the frame-0 evaluation had already written a protocol card, an `episodes.csv` and a tensorboard
  file — a directory indistinguishable from a run that could finish. Now declared in the registry
  (`data_requirements`), surfaced in the generated README, and gated by a **preflight** that runs
  before an env is built. Verified: `svea` refuses in 2 s and writes zero artifacts; `drqv2` is
  unaffected. SGQN needs it too.
- **An operator-precedence bug that disabled a guard.** `self._idx - 1 % self.capacity` parses as
  `self._idx - 1`, which is `-1` when `_idx == 0` — so the replay ring-wrap guard switched *itself
  off* at exactly the moment it exists for. Found by re-reading; the sweep corroborated it
  independently, because a mutation of that line survived precisely because the line was a no-op.
- **A first-episode measurement artifact.** Chasing down a reproducibility claim I had asserted
  but never measured showed robosuite's *first* reset after construction draws from a different
  distribution than later ones — with a zero policy on Door, ~45% higher return (0.0251 vs 0.0172
  at horizon 6; 0.0846 vs 0.0583 at horizon 20). `evaluate()` builds one env per scene, so
  **episode 0 of every scene was systematically off** — a tenth of the data at the default
  `episodes_per_scene=10`, invisible in any curve. Fixed with a discarded warm-up reset.
- **A test that did not test what it said.** The first test written for that warm-up compared two
  *fresh* envs, which are identical with or without the fix. It passed either way; mutant
  `M16-no-warmup-reset` survived and caught it. It now compares consecutive episodes of the *same*
  env, and kills M16.
- **A test the defect itself disabled.** The preflight test skipped when
  `check_data_requirements` returned nothing — so inverting the presence check *inside that
  function* made the test **skip instead of fail**, and pytest exited 0. A skip condition derived
  from the system under test is a vacuous check. The guard now reads the filesystem directly, and
  the registry is asserted to agree with it (`M17`).
- **A catalogue that caught its own drift.** `M13`'s anchor was the line the precedence fix
  changed. The runner **refused to run** rather than silently skipping the mutant — which is the
  behaviour that keeps a catalogue from quietly measuring 13 things while reporting 14.

Also fixed: `git_commit` cached (two subprocesses per `Protocol()`); the accepted-and-ignored
`resume` parameter removed rather than documented; `captum` added to `requirements.txt`;
`install.sh` clears a stale `build/` that breaks the editable install.

### 4.5 The stopping rule

Fixing a survivor makes the seed that found it **in-sample**, so a re-run of that seed is no
longer an honest estimate. Three rounds were run, each on a seed whose survivors had never been
looked at:

| seed | kill rate | what happened next |
|---|---|---|
| 1 | 12/40 → 14/40 | in-sample after the first round of fixes; retired |
| 23 | **24/40 (60%)** | three survivors triaged and fixed → seed 23 retired |
| 41 | **22/40 (55%)** | five survivors triaged and fixed → seed 41 retired |
| 57 | **see below** | measured on the shipped state, and **not fixed against** |

The rule adopted: measure on a fresh seed, triage and fix, then measure again on another fresh
seed — and stop when the last measurement describes the shipped code. Seed 57 is that
measurement. Its survivors are listed in §5 as open items rather than fixed, because fixing them
would invalidate the only number in this document that describes what is actually committed.

Roughly half of every survivor list is **equivalent mutants** — a perturbed constant inside an
error message, a widened safety margin, a default that every caller overrides, or a mutation of
`SyntheticEnv`, which lives in `rlgen/envs.py` but is test instrumentation. Those cannot be killed
by any suite, so the true sensitivity is higher than the raw rate; how much higher is not
something a script should guess, which is why the survivors are printed with their diffs.

### 4.6 Final numbers — the shipped state

```bash
pytest tests -q                    # 94 passed
python mutants/run.py              # 17/17 killed
python mutants/sweep.py -n 40 --seed 57
```

| | |
|---|---|
| test suite | **94 passed** (includes real-robosuite coverage) |
| curated catalogue | **17/17** — every named defect caught |
| **unbiased sweep, seed 57, fresh** | **27/40 — 68%** |

Progression across the four seeds: **30% → 55% → 60% → 68%**. Seed 57 was measured on exactly the
committed state and was **not** fixed against.

**Its 13 survivors, triaged by hand.** Two are worth naming as real gaps; the rest are equivalent
or narrow. They are recorded here rather than fixed — see the stopping rule in §4.5.

*Real, and worth a future test:*

- **`rlgen/agents.py:98` — checkpoint loading is never exercised.** `DrQV2Adapter.load_state_dict`
  has no test, because nothing in the suite loads a checkpoint back. The repo *writes* checkpoints
  and verifies their contents, but never round-trips one through `load_state_dict` and re-scores
  it. For a benchmark whose whole output is checkpoints, that is the most substantial remaining
  gap.
- **`rlgen/trainer.py:152` — `deterministic=False` during experience collection.** Flipping it to
  `True` would collect data from the deterministic policy and destroy exploration. The trainer
  tests run at budgets too small for that to change any assertion.

*Equivalent, or narrow enough that a test would be noise:* `SyntheticEnv`'s reward expression
(×2 — instrumentation, not the system under test); `bootstrap_ci`'s and `FrameReplay`'s keyword
defaults, which every caller overrides; the `-dirty` suffix in `git_commit`, whose exception
handler swallows the mutation; the wallclock sign in `logging_`; a widened index margin in
`_valid_indices`; the `terminated or truncated` break in `run_episode`, which the `max_steps`
bound makes unreachable; and two `boolconst` flips on already-covered branches.

---

## 5. What these numbers do **not** establish

- **No baseline has been trained to convergence.** What is verified is the pipeline: a smoke run
  through the identical code path on the real simulator, plus the suites above. No claim is made
  about any algorithm's performance.
- **Equivalent mutants cannot be killed by any suite.** Perturbing a constant inside an error
  message, or a bound never reached, changes no behaviour. Survivors are printed with their diffs
  so each can be triaged by hand as *real gap* or *equivalent*; a script must not decide.
- **`SyntheticEnv` lives in `rlgen/envs.py` but is test instrumentation.** Mutating it mutates the
  instrument, not the system under test.
- **The sweep samples 40 sites.** It is an estimate with real sampling error, not a census.
- ~~Real-environment episodes are not byte-reproducible.~~ **WRONG, CORRECTED 2026-08-14.** This
  claim was written, not measured, and cited a test (`test_real_env_episodes_vary_but_are_not_
  byte_reproducible`) that never existed anywhere in the repo. Measured directly on the real
  backend: re-seeding `np.random` to the same value before `env.reset()` DOES give a byte-identical
  episode (`test_real_env.py::test_real_env_reseeded_episode_reproducibility`), confirmed stable
  across two independent process runs; a different seed reliably diverges. See
  `docs/FAITHFULNESS.md` §`alda` and `rlgen/evaluate.py::_episode_seed`'s docstring, both
  corrected the same day. This copy of the claim survived that correction until this pass found it
  — third location carrying the same stale sentence, after `rlgen/evaluate.py` and
  `FAITHFULNESS.md`; grepping for one symptom (a defect's name) does not find every restatement of
  its CONCLUSION, which is the lesson to carry forward, not just this one fix.
- **Weight initialisation was NOT seeded anywhere, for any baseline, until 2026-08-14 — found by a
  differential test, not by inspection.** `protocol.seed` was always threaded through to every
  agent as `hyper["seed"]`, and it genuinely does control the environment (episode selection,
  reproducible evaluation — see above) and `RandomAgent`'s own policy. It did **not** control
  neural network weight initialisation for any of the other eleven baselines: neither
  `rlgen/trainer.py::train` nor `rlgen/trainer_onpolicy.py::train_onpolicy` ever called
  `torch.manual_seed`. Measured directly: two agents built from the identical declared seed, in
  the same process, produced different actions from an identical observation
  (`test_off_policy_training_is_reproducible_from_a_declared_seed` reproduces this as a red-green
  pair in `tests/test_contract.py`). A seeding utility already existed
  (`rlgen/algos/soda_utils.py::set_seed_everywhere`, vendored from SODA's own script) with **zero
  callers anywhere in the repo** the whole time. **Fixed**: both trainers now seed
  torch/numpy/random from `protocol.seed` before agent construction. Verified two ways: the same
  seed now gives byte-identical checkpoints (module weights AND optimiser state, checked
  recursively, not just the top-level tensors a naive comparison would stop at), and different
  seeds still diverge (`test_different_seeds_still_produce_different_weights` — the fix must not
  have collapsed every seed to one, which would be a worse bug than the one it replaced).
  **Consequence for anything trained before this fix landed**: none exists yet (zero real training
  runs, `docs/dz-report-ru.md` §1), so nothing needs to be re-run or reinterpreted — this was
  caught before it could produce an unreproducible published number, which is the reason it is
  worth recording prominently rather than folding into a one-line changelog entry.
- **Six of twelve baselines are absent**, and one is a declared alias. The matrix is incomplete
  and says so in machine-readable form.
- **Checkpoints are weights-only, and this is a deliberate choice, not a gap.** Raised on a deep
  review pass (2026-08-14) after noticing `rlgen/algos/alda/config.py`'s `total_frames` comment
  ("launch [Lift] at 1.1M first and extend by resume") and no corresponding code anywhere —
  neither `rlgen/trainer.py::train` nor `rlgen/trainer_onpolicy.py::train_onpolicy` loads an
  existing checkpoint before training. **Checked against the sibling `gen-rebuttal` project and
  the owner directly, rather than assumed.** `gen-rebuttal`'s own `--resume`
  (`vigen-idaac/vigen_alda/train.py`) was not built as a designed feature: it exists because a run
  was launched on cloud compute for a fixed step count, the checkpoint was downloaded afterward,
  the replay buffer was not, and continuing training from there required a warm restart as an
  operational necessity, not a plan. The owner's judgement, given that history: eval-only
  checkpoints are the right scope, and checkpointing a full replay buffer (`buffer_capacity:
  1_100_000` — 21.2 kB/step, tens of GB per run, see `alda/config.py`'s own sizing comment) would
  be undesirable regardless of whether resume is wanted. So the honest framing is not "a feature
  we haven't built yet" but "a feature that, on reflection, this project does not want" — the same
  weights-only checkpoint this repo already writes is what `gen-rebuttal`'s own `--resume` reduces
  to once the buffer is excluded, since a resume without the buffer is a warm restart in either
  design. `AldaAgent`'s unused `optimizer_state_dict`/`load_optimizer_state_dict`
  (`rlgen/algos/alda/agent.py:633-639`) and `CTRLLearner.register_centroids` not being captured by
  `PPOFamilyAdapter`'s generic reflection (`rlgen/agents.py`) are both still accurately described
  as dead/incomplete, but neither is now something to build toward — they would only matter for a
  feature this project has decided not to have.

---

## `ibac_sni` after the base-first rebuild — first end-to-end run, 2026-08-16

The rebuild (`docs/INTEGRATION-DELTA.md`) replaced the whole policy API. The suite was green
across that change, which is **not** the same claim as the training loop working — a module can
pass every unit test and fail to train. Run before replicating the pattern on `ppg`, `alda` and
`idaac`, so that a defect in the *pattern* would be found once rather than four times.

```
bash baselines/ibac_sni/train.sh Door 0 --smoke
[train] done: 3,000 frames, 11 updates, 378s
[eval ]  1,536 frames | train  0.949  | eval-easy 10.620
[eval ]  3,000 frames | train 22.333  | eval-easy 14.796
```

**What this establishes:** the module constructs through the real registry path, collects rollouts
through the shared trainer, completes 11 updates without a non-finite loss, checkpoints, and is
evaluated across all 10 scenes in both `train` and `eval-easy` modes. Exit 0. The two specific
risks flagged before the run — `nr_samples=12` making updates unaffordable, and
`softplus(rho-5.0)` starting the encoding near-deterministic and doing something degenerate —
**neither appeared**.

**What this does NOT establish, and the gap is wide.** These are 3,000-frame numbers: ~1/300th of
one real baseline-seed. Nothing about learning, sample efficiency, or the correctness of the
IBAC-SNI mechanism follows from them. The `train`-vs-`eval-easy` figures at this budget are noise
around a random policy, not a generalization gap — an untrained policy on Door produces returns in
this range, and reading a gap into 1-episode-per-scene evaluations at 3k frames would be exactly
the design-with-no-sensitivity error `docs/RIGOR.md` warns about. The algorithm's tier is
unchanged at **T4**.

**Throughput, stated with its confound:** 378s wall-clock covers 3,000 training frames *plus* two
full 10-scene evaluations (~10,000 further env steps), so the ~7.9 frames/s this implies is not
comparable to `docs/compute.md`'s 12.16 fps training figure and should not be used for budgeting.
