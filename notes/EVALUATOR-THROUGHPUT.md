# Evaluator throughput under the current evaluator is UNMEASURED

**[CORRECTED 2026-09-05, later the same night. The heading of this file used to read "The shared
evaluator got ~4x slower, and nothing was watching." That claim is WITHDRAWN — it was inferred from
a job with no logs, and the logs, once obtained, do not support it.]**

## What the evidence actually shows

`bt14het9mvpvvu8vatgo` ran 3729s against its own `timeout --foreground 3600s` and was **killed**.
A killed job's stdout is never collected — `download-files --with-logs` returns only `system.log`,
843 bytes — so **there is no evidence of what it spent the hour on.** Slow evaluation and a hung
bootstrap are equally consistent with what is observable, and I asserted the first without being
able to distinguish it from the second.

The follow-up, `bt1p4ei1s64o50oka946`, exited cleanly and therefore DID keep its log. It shows the
hour was not spent evaluating at all, because that job never evaluated anything:

    runnable/idaac/ppo_daac_idaac/envs.py:136
    RuntimeError: RL-ViGen adapter lost P3's applied regime read-back during construction

It died at env construction, ~88s after a ~600s bootstrap (a full `torch 2.3.1+cu121` install, 2891
log lines). **So its 688s says nothing about per-episode cost either**, and my "~56 s/episode" read
of it was wrong for the same reason as the first: dividing a wall-clock time by episodes that never
ran.

## What is measured, and still stands

| job | family | episodes | wall | s/episode |
|---|---|---|---|---|
| `bt1ip5f8c6mqqm7fd2bn` | idaac | 40 | 1022s | **~22** |
| `bt1rr9hodosm5sn09t1a` | drqv2 | 400 | 3593s | **~8.5** |

Both are SUCCESS jobs on **older payloads**. Nothing has yet measured throughput under the current
evaluator, because the two attempts to do so failed for unrelated reasons. That is the honest state:
**not a regression, an absence of measurement.**

## Why it still matters enough to measure deliberately

Evaluation configuration is uniform across all seven families, and the fleet is 36 cells.

Evaluation configuration is uniform across all seven families — 4 regimes x 10 scenes x 20 episodes
= **800 episodes per cell** — and the fleet is 12 baselines x 3 seeds = 36 cells:

    36 cells x 800 episodes = 28,800 evaluation episodes, for the ENDPOINT grid alone

| per-episode cost | source | endpoint grid |
|---|---|---|
| 9 s | measured, drqv2 (`bt1rr9hodosm5sn09t1a`) | **72 GPU-hours** |
| 25 s | measured, idaac (`bt1ip5f8c6mqqm7fd2bn`) | **200 GPU-hours** |
| 90 s | lower bound from the v100 failure | **720 GPU-hours** |

`CORRECTIONS.md` #12 budgets ~40 job-hours for endpoint evaluation. Even the healthy measured rates
overrun that by 2-5x once all four regimes and ten scenes are counted, which is a separate finding
worth its own look: **the calendar's evaluation term appears to have been costed against a smaller
grid than the descriptors now specify.**

And decision **A20**'s intermediate curve multiplies whichever number applies. At the reduced depth
A20 proposes (2 regimes x 3 scenes x 10 episodes x 12 stamps = 720 episodes per cell) the curve
roughly doubles the endpoint cost rather than adding 12x — which is the whole reason A20 recommends
that shape over a full grid per stamp.

**So the throughput question gates the schedule, not just one job.** Resolve it before the calendar
is quoted to anyone.


## The next measurement, and how to make it conclusive

`scripts/eval_grid.py` now honours `RLGEN_DETERMINISTIC_EVAL=0`, added so the determinism question
can be answered by a config change rather than by editing the evaluator between the two arms — which
would have changed the evaluator revision and made the arms incomparable for a second reason. The
value is stamped into every record as `torch_deterministic_algorithms`, so a row always says which
arm produced it.

Run the idaac functional job again now that the construction defect is fixed. If it completes near
22 s/episode there was never a regression; if it lands materially above, the A/B against
`RLGEN_DETERMINISTIC_EVAL=0` is the next step. **Do not quote a throughput figure until one of those
finishes** — this file exists partly as a record of what happens when you do.

---

## The reason no measurement existed: determinism has never worked on CUDA

Found 2026-09-05 by running the job rather than reading the code. `bt1s5a6pub9muqgcoil9` died at:

    RuntimeError: Deterministic behavior was enabled with either
    `torch.use_deterministic_algorithms(True)` or `at::Context::setDeterministicAlgorithms(true)`,
    but this operation is not deterministic because it uses CuBLAS and you have CUDA >= 10.2.
    ... you must set CUBLAS_WORKSPACE_CONFIG=:4096:8 or :16:8

**`use_deterministic_algorithms(True)` succeeds on CUDA and then raises at the first CuBLAS
operation** — any linear layer. The `try/except (ImportError, RuntimeError)` wrapped around the
setting call cannot catch it, because the error comes from the OPERATION, many frames later.

So from the day C70 landed until 2026-09-05, **no CUDA evaluation with determinism enabled could
complete**. This is not an idaac problem: `eval_across_scenes.py:146` enables determinism the same
way, so the RL-ViGen five carried the identical latent failure.

`CUBLAS_WORKSPACE_CONFIG=:4096:8` is now set at **module scope** in both entry points — it has to
precede CUDA initialisation, so setting it inside `main()` would be too late — and pinned by
`tests/test_cublas_determinism_config.py`, which also asserts it appears before any module-level
`import torch`.

### What this does to the throughput question

It removes the mystery. The two completed measurements (drqv2 ~8.5 s/episode, idaac ~22) come from
payloads **predating determinism**. Every attempt to measure throughput *since* has died before
finishing an episode — first on the payload contract, then the regime read-back, then device
placement, then this. There was never a regression to find; there was a chain of four defects, each
hidden behind the one in front of it.

**So the determinism A/B is now cheap and worth running**, because for the first time both arms can
actually execute: `RLGEN_DETERMINISTIC_EVAL=0` versus the default. The cost of determinism on this
workload is unknown, and it is a real cost — `:4096:8` disables the fast CuBLAS paths — so the
number decides whether option (a) "keep determinism and pay" is affordable at 28,800 episodes.

---

## 2026-09-05, later: the chain runs. `bt1aj1snkvadphens74o` SUCCEEDED.

**607 seconds wall, `NATIVE_OFFLINE_EVAL_COMPLETED`, 4 records** — 10 idaac episodes (5 per regime,
one scene) on CUDA, under the current evaluator, with all four defects fixed.

| field | value | why it matters |
|---|---|---|
| `diagnostics_available` | **True** | idaac's per-episode diagnostics reach the record on CUDA, not only locally |
| `determinism_backend` / `torch_deterministic_algorithms` | `torch` / **True** | **determinism working on CUDA for the first time since C70 landed** |
| `eval_episode_ids` | `idaac-s1-f100000-train-sc0-e0`, ... | the episode identifier the spec asked for is real |
| `_run_provenance` | present | offline rows now come home independently auditable |
| `evaluator_revision` | `8d5c1dd0b4b3` | stamped, and now covers `families.json` |

Returns, **for orientation only** — 5 episodes on one scene is not a discharge and must not be
quoted as one: train **15.13**, eval-easy **10.37**, against the re-measured floor of **1.842**. So
idaac at 100k is clearly above chance and shows a train/eval gap.

### Throughput: still not a clean number, and I am not going to infer one again

The job took 607s **including** a bootstrap that installs `torch==2.3.1+cu121` inside the container
— roughly 600s of the 688s that `bt1p4ei1s64o50oka946` spent before failing. Dividing 607 by 10
episodes would repeat exactly the mistake this document was rewritten to retract.

What can be said honestly: **a completed 10-episode evaluation fits inside the same envelope that a
job which never evaluated anything already occupied.** There is no sign of a throughput problem, and
there was never evidence of a regression — only four stacked defects.

`run_probe.sh` now echoes `NATIVE_OFFLINE_EVAL_BEGIN ... epoch=<t>` and
`NATIVE_OFFLINE_EVAL_SECONDS <n>` around the eval phase, so **the next run answers this by
subtraction rather than inference**. `run_endpoint_eval` does the same.

### The determinism A/B is now worth running, and only now

`cfg-idaac-determinism-off-v106.yaml` is prepared and deliberately **not** submitted until this
succeeded — an A/B between two broken arms measures nothing. Both arms can now execute, records
carry `torch_deterministic_algorithms` so the arms cannot be pooled by accident, and with the new
`NATIVE_OFFLINE_EVAL_SECONDS` marker the comparison is a subtraction of two numbers rather than a
reading of two wall clocks.

---

## ANSWERED, 2026-09-05: determinism is essentially free, and throughput is ~12 s/episode

Codex ran the B arm as `bt1e81rq286p23d3l4l9` and the marker added for this purpose reported it
directly, so this is a measurement rather than an inference:

    === NATIVE_EVAL_DETERMINISM_DISABLED by RLGEN_DETERMINISTIC_EVAL=0 ===
    === NATIVE_OFFLINE_EVAL_SECONDS 120 ===

| arm | job | wall | eval phase | s/episode |
|---|---|---|---|---|
| determinism **off** | `bt1e81rq286p23d3l4l9` | 602s | **120s** (measured) | **12.0** |
| determinism **on** | `bt1aj1snkvadphens74o` | 607s | ~125s (inferred: no marker in that payload) | ~12.5 |

**Determinism costs about 4%, which is within the noise of two single runs.** That makes sense once
stated: this workload is dominated by MuJoCo physics and EGL rendering, not by the CuBLAS GEMMs that
`CUBLAS_WORKSPACE_CONFIG=:4096:8` slows down. The visual encoder is small and runs once per step.

### Consequences

1. **Keep determinism.** Option (a) from the decision above — "keep it and pay" — turns out to cost
   almost nothing, so the confound it removes is bought cheaply. `RLGEN_DETERMINISTIC_EVAL` stays as
   a lever, but the default should remain on.
2. **There was never a throughput regression.** 12 s/episode sits between drqv2's 8.5 and idaac's
   22 from the older payloads. The "4x slowdown" I claimed and withdrew was four stacked defects,
   none of which was slow — they simply prevented anything from finishing.
3. **The endpoint grid is affordable**: 28,800 episodes at 12 s is **96 GPU-hours**, against
   `CORRECTIONS` #12's ~40 job-hour budget for endpoint evaluation. Still over, but by ~2.4x rather
   than the 18x the withdrawn figure implied — and A20's 50k trajectory grid at 86,400 episodes adds
   ~288 GPU-hours, which is the number that actually needs the owner's attention.

---

## The cost model closes, 2026-09-05: construction 0.6s, episode ~12s

The open term was env construction, and it turns out to be measurable without buying anything.
Timed locally on the M2 Pro against the real `robosuitevgb.make_env`:

    env construction   0.6s (median of 3)
    stepping           ~8s per 500-step episode (local CPU/glfw)

Local timings do not transfer to the container, but they do not have to — **they close the two
remote equations**, which is what makes them credible:

| job | shape | measured | implied episode cost at C=0.6s |
|---|---|---|---|
| `bt1e81rq286p23d3l4l9` (idaac) | 2 constructions + 10 episodes | 120s | **11.9s** — matches the measured 12 |
| `bt1rr9hodosm5sn09t1a` (drqv2) | 40 constructions + 400 episodes | ~3111s | **7.7s** — matches the historical 8.5 |

Both families reconcile at the same construction cost, which is what a correct model looks like.

**Construction is 0.25% of the endpoint grid and 1% of the trajectory grid.** It is not a term worth
planning around, and the earlier "20,160 env constructions = 28-168h" figure (CORRECTIONS #12) is
inconsistent with this by two orders of magnitude — it should be re-derived or withdrawn.

### The evaluation cost table, no longer a range

| product | episodes/cell | h/cell | fleet (36 cells) |
|---|---|---|---|
| endpoint, 4 x 10 x 20 | 800 | 2.67 | **96 GPU-h** |
| trajectory @ 3 episodes/stamp | 1,440 | 4.88 | **176 GPU-h** |
| **trajectory @ 5 episodes/stamp** | 2,400 | 8.08 | **291 GPU-h** |
| trajectory @ 10 episodes/stamp | 4,800 | 16.08 | 579 GPU-h |

So **A20's one free parameter now has a price list**, and the during-training evaluation protocol is
determined rather than pending: 50k frequency (hardcoded upstream), 4 regimes x 10 scenes
(commensurability), 500-step episodes, 3 seeds, and episodes-per-stamp chosen from the table above.

---

## The A/B is complete, both arms instrumented: determinism costs NOTHING

Codex ran the A arm on the current payload, so for the first time both arms carry the
`NATIVE_OFFLINE_EVAL_SECONDS` marker and the comparison is a subtraction of two measurements rather
than a reading of two wall clocks:

| arm | job | measured eval phase | record stamp |
|---|---|---|---|
| determinism **ON** | `bt1baht74a35e6uq582c` | **118 s** | `torch_deterministic_algorithms = True` |
| determinism **OFF** | `bt1e81rq286p23d3l4l9` | **120 s** | `NATIVE_EVAL_DETERMINISM_DISABLED` |

**118 against 120 — the deterministic arm is nominally FASTER, which simply means the difference is
inside the noise of two single runs.** The earlier estimate of "about 4%" came from comparing a
measured phase against an inferred one; with both measured, the honest answer is **no measurable
cost at all**.

That is what the workload predicts once stated plainly: this evaluation is MuJoCo physics and EGL
rendering, and `CUBLAS_WORKSPACE_CONFIG=:4096:8` only constrains GEMM kernels that a small visual
encoder barely touches.

### Settled

- **Keep `torch.use_deterministic_algorithms(True)` on.** It removes a real confound — mixing
  deterministic and backend-selected kernels across a discharge comparison — and it is free.
  `RLGEN_DETERMINISTIC_EVAL=0` stays as a diagnostic lever, not a production option.
- **Per-episode cost is 11.8 s** (118 s / 10 episodes), consistent with the 12 s used throughout
  `PRODUCTION-CALENDAR.md`. No revision needed there.
- **The question that opened this file is closed.** There was never a throughput regression: there
  were four stacked defects, none of them slow, and two wall-clock inferences of mine that were
  wrong for the same reason twice.

## And the part the timing comparison does NOT show: determinism changes the NUMBERS

Codex was right to bound its own result — 118 s against 120 s "does not establish return
invariance". It doesn't, and the returns turn out to be the more important half.

The two arms are **provably the same experiment apart from the flag**:

    evaluator_revision  4ad7d3b878ada2a6   identical
    payload_sha256      e06eed737db4       identical
    checkpoint_sha256   23207b30454b       identical

and their episode returns are **not** identical:

| cell | returns identical? |
|---|---|
| `eval-easy` / scene 0 | yes |
| **`train` / scene 0** | **NO — 2 of 5 episodes differ** |

    ON : [9.176979, 9.283772, 8.120473, 29.987989, 18.481642]
    OFF: [9.401473, 9.283772, 8.478366, 29.987989, 18.481642]
    max |diff| = 0.358

**So kernel non-determinism is not neutral for this measurement.** The same checkpoint, same seed,
same placement conditions, same code produced different episode returns on 2 of 5 episodes, by up to
0.358 on returns of 8-30 — roughly 4% on the affected episodes, against a random-policy floor of
1.842.

**This is the confound C70 was added to remove, now measured instead of assumed** — and it is a far
better argument for determinism than the timing was. It costs nothing (118 vs 120 s) and it demonstrably
changes numbers when absent.

**What is still NOT established, stated precisely:**

- **That determinism makes runs reproducible.** Showing ON differs from OFF is not the same as
  showing ON repeats itself; that needs **two ON runs of the same cell** compared for exact equality.
  It is a ~10-minute job and it is the natural next measurement.
- **That the magnitude generalises.** One family, one scene, five episodes. `idaac` samples its
  policy, so some of this variance may be policy sampling interacting with kernel order rather than
  kernel order alone — the mode-taking families may differ.

---

## THE REPRODUCIBILITY TEST FAILS: determinism does not make evaluation repeatable

Codex ran the repeat I proposed (`bt1e78hbs4s946aje3q9`). **Two runs with byte-identical
configuration produced different returns.**

    evaluator_revision 4ad7d3b878ad | payload e06eed737d | checkpoint 23207b3045 | det=True   -- both runs

    train / scene 0
      v107   (ON) : [9.176979, 9.283772, 8.120473, 29.987989, 18.481642]
      repeat (ON) : [9.401473, 9.283772, 8.478366, 29.987989, 18.481642]
      OFF         : [9.401473, 9.283772, 8.478366, 29.987989, 18.481642]

Episodes 0 and 2 differ; 1, 3 and 4 are identical. **And the second ON run is byte-identical to the
determinism-OFF arm.**

### This retracts A37 and the claim in the section above it

I wrote that "kernel non-determinism changes the numbers" on the strength of ON differing from OFF.
**That attribution is wrong.** Two ON runs differ from each other by exactly the same amount, and one
ON run matches OFF exactly, so the flag is not the variable. What the earlier comparison actually
measured was **run-to-run variance, which exists with determinism enabled.**

### What is actually going on, stated as far as the evidence goes

The differing-episode pattern rules out an RNG-stream divergence: a diverged stream would change
every episode after the divergence point, and here episode 1 sits unchanged **between** two changed
ones. That is the signature of **specific episodes flipping at a threshold**, which fits C70's note
that Door is threshold-sensitive.

`torch.use_deterministic_algorithms(True)` governs torch kernels. It does not govern **MuJoCo physics
or EGL rendering**, and those produce the observations. A sub-ULP difference in a rendered frame is
enough to flip a marginal episode — and only a marginal one, which is why three of five are stable.

**Torch RNG is not the cause**: `seed_the_placement_rng` calls `torch.manual_seed` and
`cuda.manual_seed_all` for every family including idaac.

### What this changes for pre-production, and it is not small

1. **A discharge comparison cannot require exact equality.** It needs a predeclared numerical
   tolerance, and that tolerance must be at least the run-to-run variance measured here.
2. **The variance must be quantified before it is budgeted.** One pair of runs on one cell shows
   2 of 5 episodes moving by up to 0.358. That is an anecdote, not a variance estimate.
   **Three or more repeats of one cell** would give one, and it is a ~10-minute job each.
3. **It argues for episode count, not against determinism.** Keep determinism on — it is free and it
   removes one source — but the reported number's stability comes from averaging enough episodes,
   not from bit-reproducibility that this evaluator does not have.
4. **`RESULTS-VALIDITY`'s standard needs restating**: "the same checkpoint under the same revision
   gives the same number" is **false as an expectation**, and no comparison should be built on it.

### Measuring the variance, 2026-09-05 (Claude, after Codex ran out of quota)

Two replicates submitted — `bt1aseskh66dnv9i3qe5` and `bt1dpq4tnemmkvp3sccg`, configs
`cfg-idaac-variance-r112/r113.yaml`. Both are **field-identical** to
`cfg-idaac-determinism-repeat-v111` (payload-v106, same checkpoint, same seed,
`RLGEN_DETERMINISTIC_EVAL=1`) because the point is to vary nothing.

With the two existing ON runs that makes **four replicates of one configuration**, which converts
"two runs disagreed by 0.358" from an anecdote into a variance estimate.

**Why this and not a family revalidation.** Revalidating a family under the current revision
(`a8664a7f98dc`) would have to be redone once **A17** (beta) or **A20** (curve depth) is ratified,
because both change `families.json`, which is a revision member. The variance number does not
depend on the revision in that way and is needed regardless: reviews 7 and 8 both require the
shared-evaluator discharge to agree "within a predeclared Monte-Carlo tolerance", and **that
tolerance must exceed this number**. Measuring it now is the one job that cannot be invalidated by
a pending decision.

## The variance, measured: 0.12 on a cell mean of 15.1 — and one cell is perfectly reproducible

Four replicates of one configuration (`bt1baht74a35e6uq582c`, `bt1e78hbs4s946aje3q9`,
`bt1aseskh66dnv9i3qe5`, `bt1dpq4tnemmkvp3sccg`) — identical payload, checkpoint, seed, revision and
`RLGEN_DETERMINISTIC_EVAL=1`:

| cell | per-run cell means | spread | sd |
|---|---|---|---|
| `eval-easy` / scene 0 | 10.3737 x4 — **byte-identical** | **0.0000** | 0.0000 |
| `train` / scene 0 | 15.0102, 15.1266, 15.1235, 15.1235 | **0.1165** | 0.0572 |

**0.77% of the cell mean, on 5 episodes.**

Two things this shows that two runs could not:

1. **The instability is episodic, not per-run noise.** Three of the four runs agree *exactly*;
   `bt1baht74a35e6uq582c` is the lone outlier, and only on two of five episodes. This is consistent
   with specific marginal episodes flipping, not with a diffuse numerical jitter.
2. **A whole cell can be perfectly reproducible.** `eval-easy` repeated byte-for-byte four times.
   So the evaluator is deterministic in the ordinary case and occasionally flips a threshold-
   sensitive episode — which matches C70's characterisation of Door.

### The tolerance this licenses

A discharge comparison on a **5-episode** cell must tolerate at least **0.12 absolute / ~0.8%**.
The production endpoint uses **20 episodes per (regime, scene)**, where the same per-episode
instability is averaged over four times as many episodes, so the cell-mean tolerance there should be
smaller — but **that has not been measured and should not be extrapolated**; the same reasoning that
produced two withdrawn wall-clock claims applies.

**This also retires my A37 framing for good.** The ON/OFF difference I attributed to determinism was
`bt1baht74a35e6uq582c` being the outlier of four, not the flag doing anything. The OFF arm agrees
with the three-run majority.
