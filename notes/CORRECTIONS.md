# Corrections — claims made in these notes that were wrong

Every one of these is corrected *inline* in its source document, which means the pre-correction
wording is still findable and quotable. This page exists so a reader can check a claim against the
retraction list before repeating it.

**One of these already caused harm**: my 8× figure was written into `families.json`'s
`constants_note` by the concurrent session, overwriting text that was correct.

| # | the claim | status | what is actually true |
|---|---|---|---|
| 1 | **`ppg`'s rollout gap is 8×**, and `FAITHFULNESS.md`'s "65,536" is unsourceable | **WRONG** — propagated into `families.json` before correction | `README.md:34` documents `mpiexec -np 4`; 4 MPI × 64 envs × 256 = **65,536**; ours is 2,048. **32×.** The original table was right |
| 2 | "PPG gets nine auxiliary phases at 6e5, so the budget is sufficient" | **RETRACTED** | `n_pi=32` was never rescaled, so the phase fires every 65,536 frames instead of ~2.1M. That is a **symptom of the 32× rescaling**, not evidence of fidelity |
| 3 | Anchor T3 on **`drqv2`** | **SUPERSEDED** | Their published DrQ-v2 Door is 3.6 against a 1.82 floor — a broken evaluator, a floored policy and a correct reproduction all produce ~2. Anchor on **`sgqn` (391.4)** and **`svea` (268.8)** |
| 4 | **Adaptive seed allocation** — one seed everywhere, then concentrate | **WITHDRAWN** | Outcome-dependent sampling: an unlucky first seed classifies a method "floor" and it never earns more trials. Fixed 3 for every reported row |
| 5 | **Retention (eval ÷ train) as the headline** | **DEMOTED** | Not invariant to reward offsets, and Door's reward is shaped with a non-zero floor. Primary: `R_train`, `R_OOD`, **Δ**, success rate. Ratio secondary, competent baselines only |
| 6 | `(baseline, seed, regime, scene)` is "the smallest unit not internally correlated" | **WRONG** | All ten scene results share one trained policy. The outer replicate is the **training seed**: n = 3, not 600 |
| 7 | Bootstrap by resampling **seeds and scenes** | **WRONG** | That silently treats the ten certified scenes as a sample from a population. They are a fixed grid; resample whole seed-vectors |
| 8 | Cross-method **training-seed pairing** gives the statistical power | **OVERSTATED** | Pairing holds for regime, scene and placement — measurement noise. "Seed 1" for two different algorithms is not a common-random-number block |
| 9 | "35.5 GB of checkpoints **does not fit**" | **PREMISE WITHDRAWN** | Free disk was 73.1 GB, not ~30. The conclusion (evaluate in-container) stands on **C95** alone, which never needed the storage argument |
| 10 | `num_seed_frames` is **4000** in production | **UNVERIFIED** | A real job's composed config showed **600**. The base config says 4000; the composed config governs. The production value needs the composed config, not the template |
| 11 | "`runnable/idaac` and `runnable/ppg` are clean — `git status` shows nothing" | **UNFOUNDED** | `.gitignore:35` is `runnable/*/`; the parent repo does not track the clones. Empty output meant *not tracked*. Use `scripts/deviations.py` |
| 12 | Production calendar is **731 job-hours / 15.2 days** on two V100s | **INCOMPLETE, twice — and now SUPERSEDED, see `notes/PRODUCTION-CALENDAR.md`. Its env-construction term (28–168 h) implied 5–30 s per construction; the measured value is 0.6 s, i.e. 3.4 h, an overestimate of 8x to 50x** | Missing endpoint eval (40 h), contingency, and **20,160 env constructions** (28–168 h); also assumed no packing. Complete envelope **6.5–17 days**, realistically 7–11 — before the GPU-0 occupancy below |
| 13 | Two V100s are available for scheduling | **QUALIFIED** | `remote-infra.txt` shows **GPU 0 occupied** by another user (15.1 GB, 67%). With one GPU the campaign is roughly double |
| 14 | Gate `scheduler RAM invariant` **PASS** | **FALSE PASS, fixed** | It grepped the *cost model*, which does compare RAM; the surface that failed was the **submission path**, which `alda` bypassed by hand |
| 15 | Gate `source tree frozen` **PASS** on a packaged artifact | **FALSE PASS, fixed** | It read `git status`'s stdout and ignored the exit code, so a failing git read as a clean tree. Now fails closed |
| 16 | Applying the V100 host targets to `families.json` | **REVERTED** | The `replay_capacity` I edited was the **top-level** key; `family.py:222` reads the **production block** — a no-op leaving two disagreeing values. The `constants` edits *were* live and would have sent 16 processes to a 4-core probe tier |
| 17 | `FAITHFULNESS.md`'s table cited as current | **QUALIFIED** | Its summary is tagged **`[MIXED]`** by its own header. Two `high` rows are mischaracterised, one is superseded in half, one confirmed |
| 18 | R6: "12/12 genuine at 6e5" | **QUALIFIED** | The audit checked **symbol presence**. `svea` passes while feeding the wrong augmentation; `ctrl` would have passed while its loss raised `NameError`. Five are now `GENUINE (PRESENCE ONLY)` |

## The pattern, since it repeats

Most of these are one of two shapes:

- **Absence of a signal read as evidence of a state** — #11, #14, #15, and the payload checker's
  exit-code collision. An instrument that cannot run must never read as one that passed.
- **A number that looked right for two compensating wrong reasons** — #12 twice over. A figure that
  survives review because its errors cancel is the kind that fails in practice.

Both argue for the same discipline: **re-derive rather than adjust**, and state what a check reports
when it cannot run.

## Added 2026-09-05 (later)

| # | the claim | status | what is actually true |
|---|---|---|---|
| 19 | Reward shaping is **`[OURS]`** (`FAITHFULNESS.md:145`), so our returns may not share a scale with RL-ViGen's published numbers | **NOT MINE, BUT NEARLY ACTED ON** | `reward_shaping: true` is in RL-ViGen's own `envs/robosuiteVGB/cfg/robo_config.yaml`. It is theirs; we match it. The scales agree and **the T3 anchor stands**. I was one step from withdrawing a valid recommendation on the strength of a wrong provenance tag |

**The lesson is the same one as #1, in the other direction.** There I propagated my own wrong number
into a correct record; here I nearly withdrew a correct conclusion because a record was wrong.
**Check the code, not the table** — in both directions.

## Added 2026-09-05 (from reviews 6, 7 and 8)

| # | the claim | status | what is actually true |
|---|---|---|---|
| 20 | `FAITHFULNESS.md:808` — **"`vib_beta: 1e-4` matches CoinRun `[P]`"** | **WRONG IN THE EXECUTED CONFIGURATION** | `runnable/_launch/ibac_sni.sh` passed no `--beta`, so `torch_rl/scripts/train.py:99`'s default of **1.0** applied. `algos/ppo.py:118` adds `self.beta * kl` straight into the objective, so every ibac_sni run so far used a bottleneck penalty **10^4x** the CoinRun value the table claimed and **10^6x** the Multiroom one. Fixed to `--beta 1e-4`; pinned by `tests/test_ibac_beta_is_wired.py`. **The prior entropy pilots are not evidence about the corrected configuration** |
| 21 | My justification for the `ctrl` reward-units fix, first draft | **RIGHT FIX, WRONG EVIDENCE — caught before it landed** | I read `normalize_rewards=True` off `vec_env.py:25` and cited it. That is `ProcgenVecEnvCustom`; the class the evaluator actually imports is `RLViGenVecEnvCustom`, added by `runnable/_patches/ctrl.patch:686`, which is not in the clone's `vec_env.py` at all. The real class happens to carry the same default, so the fix stands — but I had cited a file that does not govern the code path, which is the exact error `CORRECTIONS` #17 and #19 are about |
| 22 | Review 8's **"CTRL's paired episode conditions are not actually paired"** | ~~NOT REPRODUCED~~ **[MY REFUTATION WAS WRONG — see #39. Reviews 8 and 9 were right.]** | The mechanism needs a running condition counter that a second `reset()` double-advances. `RLViGenVecEnvCustom` swallows `condition_seed` in `**_ignored`; the evaluator re-seeds `random` and `np.random` from `SeedSequence(seed, scene, episode_index)` before every measured reset, and a re-seed **overwrites** the stream, so discarded auto-resets cannot shift the measured placement |
| 23 | Review 8's / review 6's **"fix CTRL's JAX RNG leak"** | **MECHANISM TRUE, REMEDY REJECTED** | `ext/ctrl_public/train_ppo.py:193,202` has the identical key rebinding and steps the same test envs in the same place, so the advance is upstream's design and patching it would be OUR deviation. What was genuinely wrong was my own gate, which called a `np.random.get_state()` string search "RNG isolation"; it now states that only the PLACEMENT stream is isolated |

### The pattern this session added: **the measurement, not the thing measured**

Three times in one session I nearly drew a conclusion from a broken instrument of my own making:

- `grep -cE "^FAILED|failed"` against **colorized** pytest output returned 0, which read as "my new
  test does not catch the bug it was written for." The test was fine; the grep could not match past
  the escape codes.
- `$?` after `cmd | tail` reported the exit status of `tail`, which read as "the legacy-table
  refusal does not actually exit non-zero." It exits 2.
- Reading a default off the wrong class (#21 above).

This is [SYNTHESIS](SYNTHESIS.md) Mechanism 1 turned on the auditor: **an instrument that cannot
run reads the same as one that ran and passed** — including the one-line instrument you type into a
shell. Every one of these was caught by looking at the raw output instead of the summary, which is
the only defence that worked.

| # | the claim | status | what is actually true |
|---|---|---|---|
| 24 | The exclusion filter in `audit_executed_hyperparameters.py` | **SILENTLY SWALLOWED REAL CLAIMS, TWICE** | Written to skip claims about the legacy `rlgen/` path, it first used a 400-character window and dropped `alda`'s claims **entirely** while cutting `sgqn`'s from four to one; narrowed to "the same sentence", it then mis-split on periods inside filenames (`configs/vigen.yaml`) and excluded seven claims. Both times the audit still reported a clean exit. Replaced with an **explicit two-entry `LEGACY_CLAIMS` table**, each with its reason printed in the report. **A heuristic that drops rows cannot be audited; a list can be argued with.** |
| 25 | "The idaac revalidation job has been executing for ~4 hours and should be cancelled" | **WRONG, and I nearly acted on it** | I was reading DataSphere's **UTC** timestamps against **MSK** local time. Created 01:29 UTC, checked at 02:09 UTC: **40 minutes**, comfortably inside its envelope. I was one step from cancelling a healthy job and discarding the spend, on an arithmetic error I could have caught by printing `date -u` — which is exactly what settled it |

| 26 | `scripts/deviations.py`'s **"BASELINE MISLABELLED"** warning, naming all six clones | **FALSE ALARM — no baseline is mislabelled** | It ran `git -C ext/<clone> log -1`, and **git walks UP when the directory is not itself a repository**. `ext/` has no `.git` and neither do the vendored copies inside it, so every lookup returned ccm-intro's own HEAD (`12f6322`) and the check reported six baselines as claiming a commit their source "is at" — against one unrelated commit, six times. Now verifies `rev-parse --show-toplevel` matches the directory first, and reports **UNCHECKABLE HERE** with an explicit note that a zero exit does not certify those claims |

**A third instance of the same shape, and the sharpest one.** #24 is the auditor's version of the
bug the auditor was built to find: I wrote an instrument to catch values that never reach the
process, and its filter stopped real claims from reaching the report. It exited 0 both times.
`SYNTHESIS` Mechanism 1 does not spare the instrument written to enforce it — the only defence that
worked was printing the full table and counting the rows, rather than trusting the exit code.

| # | the claim | status | what is actually true |
|---|---|---|---|
| 27 | `audit_comparability_seam.py`'s **`[UNITS] reward pipeline: UNIFORM`** | **WAS A FALSE UNIFORM, and its own docstring predicted why** | The axis derived the REPORTED units from each family's NATIVE evaluator and hardcoded `"raw"` for all twelve, while this file's own header says the final number is produced by `eval_grid.py`. So while `eval_grid`'s ctrl evaluator was summing the outermost `VecNormalize` reward, the axis reported the units uniform. The docstring had already named the exact hazard — *"reading the venv's reward instead of the monitor's silently changes the units of every number a baseline reports, and nothing raises"* — as prose, not as a check. Now derives both halves from `eval_grid.py`, and **verified non-vacuous** by reverting ctrl's flag and watching the axis go `SPLIT 2 ways` |
| 28 | My first fix for #27 | **PASSED ON ITS OWN COMMENT** | I derived ctrl's units by grepping `run_scene_ctrl`'s block for `normalize_rewards\s*=\s*False`. That block contains the **comment I wrote explaining the flag**, which carries the same string, so the check was satisfied by its own prose and reported UNIFORM against a reverted call. Now AST-based on the `RLViGenVecEnvCustom` call's keywords. **An audit that its own explanation can satisfy is worse than none, because it reads as evidence** |

### The budget class, added the same day

Job `bt14het9mvpvvu8vatgo` was killed by its own `timeout --foreground 3600s` — 3729s wall, exit 5,
no stdout to download — and **seven sibling configs carried the identical budget**. Nothing checked
that a config's timeout could fit the episode count it asked for. `scripts/audit_job_budgets.py` now
does, at per-family rates measured from completed jobs. My first version used one flat rate and
produced a **false FAIL on a config that had demonstrably succeeded**, which is the third instrument
of the day to report wrongly about work that was fine.

| # | the claim | status | what is actually true |
|---|---|---|---|
| 29 | "The shared evaluator got ~4x slower" (`EVALUATOR-THROUGHPUT-REGRESSION.md`, now `EVALUATOR-THROUGHPUT.md`) | **WITHDRAWN — asserted from a job with no logs** | `bt14het9mvpvvu8vatgo` was **killed** by its own timeout, and a killed job's stdout is never collected (`--with-logs` returns 843 bytes of `system.log`). Slow evaluation and a hung bootstrap are equally consistent with that. I then compounded it by dividing the follow-up job's 688s by 10 episodes to get "~56 s/episode" — that job died at env construction and ran **zero** episodes. Throughput under the current evaluator is **unmeasured**, which is a different statement from regressed |
| 30 | That the local venv should carry `numpy==1.26.4` | **WRONG, and I changed shared state on it** | That pin is in `requirements-native.txt`, which describes the **remote container**, not this machine's venv. The venv had **numpy 2.4.6** all along — visible in the "Gym does not support NumPy 2.0" warning present from the first run. I downgraded it, which broke idaac's local import (`ext/baselines/.../shmem_vec_env.py:17` uses `np.bool`, removed in 1.24 and restored in 2.0), then restored 2.4.6. **The trigger was an `uv pip install bottleneck` that silently took numpy with it** — a single-package install is not a single-package change |

### The shared-state lesson, which is the one I care about most tonight

I reached for `uv pip install` to unblock one local check, and it moved a **transitive pin** in an
environment other work depends on. Nothing verified the environment before or after; I noticed only
because a check that had been passing started failing. Two rules follow, and the second is the one
that would actually have prevented it:

1. Before installing anything into a shared venv, record the versions that matter (`numpy`, `torch`)
   and re-check them afterwards.
2. **A local convenience is not worth a shared mutation.** `alda`'s import was blocked by a broken
   `bottleneck` *before* I touched anything, so the install bought nothing and cost a numpy
   downgrade — and `docs/local-envs.md`'s stubbing recipe, which I had already used successfully for
   `dmc2gym` minutes earlier, was the right tool and leaves no trace.

| # | the claim | status | what is actually true |
|---|---|---|---|
| 31 | `torch.use_deterministic_algorithms(True)` makes the evaluator's kernels deterministic on CUDA (C70) | **NEVER TRUE ON CUDA, on any family** | The call succeeds and then **raises at the first CuBLAS operation** unless `CUBLAS_WORKSPACE_CONFIG` is set, and the `try/except` around the setting call cannot catch it because the error comes from the operation. `eval_across_scenes.py:146` does the same thing, so the rlvigen five carried it too. Every record stamped `deterministic_algorithms: true` from a **CPU** run was accurate; no CUDA run with it enabled ever completed. Fixed at module scope in both entry points |
| 32 | The idaac evaluator "ran" and its regime guard was sound | **BOTH FAMILIES USING THE NEW GUARD WERE UNRUNNABLE** | `idaac` raised on every construction (the guard read `_vigen_regime` off an object P3 never touches, because that adapter calls `make_env`, which P3 does not patch) and `ctrl` raised `UNVERIFIED` (its vector stack forwards no attributes). Neither was visible to the suite, because **no test constructed an environment**. Found by building every family's real env locally and running the real guard |
| 33 | The checkpoint loader moves the agent to the requested device | **TRUE ONLY FOR AGENTS THAT ARE NOT nn.Modules** | It walked `vars(agent)` for module attributes; `idaac` and `ppg` pickle an `nn.Module` directly, whose children live in `_modules`. `ppg` had an explicit branch keyed on the **family name**, so idaac — identical in shape — inherited the bug rather than the fix. Now keyed on `isinstance(agent, torch.nn.Module)` |

### The pattern these three share, which is the night's main finding

**Four defects were stacked in one job's path, each invisible until the one in front of it was
fixed**: payload contract, regime read-back, device placement, CuBLAS determinism. Every one of them
would have been found by a single job that ran to completion, and none of them by any amount of
reading. The suite was green throughout.

The corollary is uncomfortable and worth stating plainly: **a green suite plus a failing remote job
means the suite is testing the wrong layer.** Three of the four were in code that no test ever
executed against a real environment.

| # | the claim | status | what is actually true |
|---|---|---|---|
| 34 | `tests/test_rlvigen_reference.py` covers the published-reference reader | **NEVER RAN — 14 tests, all skipped, for the project's whole life** | Its module-level `skipif` tested `XLSX`, which is `_CANDIDATES[0]`: the vendored `RL-ViGen-upstream/results/evaluation_score.xlsx` that does not exist in this tree. The workbook was reachable all along through the asset tarball, which `_load_workbook` walks to. **This is the same hardcoded-path assumption that made `rlvigen_reference.py` itself print "absent" every time it ran** — the script was fixed earlier in this session and the test kept the old belief, so the fix went unexercised. Now skips only when NO candidate resolves; all 14 run and pass |

Its fixture had a second, quieter version of the same fault: it patched only
`scripts.rlvigen_reference.XLSX` while `_load_workbook` iterates `_CANDIDATES`, so once the module
stopped skipping, the parser would have read the **real** workbook while each test believed it was
reading its own synthetic one — passing for the wrong reason. The fixture now patches the candidate
list.

**Both halves are the night's recurring shape**: a check that cannot run reads exactly like a check
that ran and passed, and the skip line is as much a claim about the world as the assertion is.

| # | the claim | status | what is actually true |
|---|---|---|---|
| 35 | ~~**"Replay capped at 300k in a 600k run"**~~ **[THIS ENTRY IS ITSELF WRONG — see #36]** — that the cap discards half the experience. Carried by every RL-ViGen row in `CLAIMS-LEDGER`, by `production-readiness-by-class`, and independently repeated by external reviews 4, 6, 7 and 8 | **WRONG BY TWO ORDERS OF MAGNITUDE. The cap evicts ~0.4%, not 50%** | RL-ViGen uses **`action_repeat: 2`** (`cfgs/config.yaml:10`, and every agent config). `train.py:134` defines `global_frame = global_step * action_repeat`, and `utils.Until` returns `step < until // action_repeat` (`utils.py:72`), so a 600,000-**frame** budget is **300,000 agent steps**. `replay_storage.add()` runs once per agent step (`train.py:337`, immediately before `_global_step += 1`), plus one initial time step per episode. At a 500-step horizon that is `300,000 + 1,200 = 301,200` transitions against a **300,000** cap: **1,200 evicted, 0.40%.** |

### What this changes, and it is a lot for one arithmetic error

- **Five of twelve baselines lose a declared deviation.** The cap qualification on `drqv2`, `drq`,
  `svea`, `sgqn` and `curl` is not a real limitation at this budget; upstream's own default
  (`replay_buffer_size: 1000000`) is likewise never reached, so **300k and 1M are behaviourally
  identical here.**
- **The v100 profile's `replay_capacity: 1000000` override buys nothing and costs a great deal.**
  Using the schedule's own memory law (63,504 bytes per retained transition), 1M implies **62.4 GiB
  per cell** against 300k's **21.0 GiB** — which drops RL-ViGen packing on the 113 GiB production
  host from **five concurrent cells to one**. A 5x parallelism cost for a behavioural difference
  that does not exist at a 600k budget.
- **Four external reviews repeated it.** It was in the tree as a recorded fact, and every reviewer
  reasonably took it as one. That is the cost of a wrong entry in a register people trust.

**How it survived**: the number 300,000 was compared against the number 600,000, and both are real —
but they are in **different units**, frames against transitions, and `action_repeat` is the
conversion nobody applied. Exactly `SYNTHESIS` Mechanism 3, "a constant transplanted across a scope
change", with the scope change being a factor of two hiding in a config default.

| # | the claim | status | what is actually true |
|---|---|---|---|
| 36 | **Correction #35 itself** — that the replay cap evicts only 0.40% and is not a real deviation | **WRONG. #35 IS RETRACTED IN FULL; the original claim it "corrected" was right** | #35 computed from `action_repeat: 2` in `RL-ViGen-upstream/cfgs/config.yaml`. **`runnable/_launch/rlvigen.sh:78` passes `action_repeat=1`**, and line 61 states it is "NOT a preference, it is this project's declared protocol". So a 600,000-frame budget IS 600,000 agent steps, ~600,000 transitions are stored against a 300,000 cap, and **the cap discards roughly half the experience** exactly as `CLAIMS-LEDGER` originally said. `CLAIMS-LEDGER`, `faithfulness-reconciliation` and `production-readiness-by-class` have all been reverted; external reviews 4, 6, 7 and 8 were right |

### The same mistake twice in one night, and what it should change

#21 was: I read `normalize_rewards=True` off `ProcgenVecEnvCustom` when the class actually in use is
`RLViGenVecEnvCustom`. #35 is: I read `action_repeat: 2` off `cfgs/config.yaml` when the launcher
passes `action_repeat=1`. **Both times I took a value from the file that DECLARES it and never
opened the file that OVERRIDES it.**

The uncomfortable part is that this project already has an instrument for exactly this —
`scripts/audit_executed_hyperparameters.py`, written earlier the same night, whose entire purpose is
"does the value we claim reach the process?" **I did not run it on the number I was about to
publish.** A tool that is not reached for is worth no more than the check it replaced.

It also came within one message of doing damage: A31 told the concurrent agent to drop a host-profile
override on the strength of the wrong number, and that advice had to be retracted in A32 before it
was acted on. **A wrong correction is more dangerous than the wrong claim it corrects**, because it
arrives with the authority of having been checked.

### The instrument that already knew

`scripts/audit_comparability_seam.py` reports the `effective action repeat` axis as:

    1 (launcher override; shipped default is 2)     drqv2 drq svea sgqn curl

**It had the answer, in exactly those words, before I wrote #35 and while I was writing it.** I read
the config file instead of running the audit that exists to tell me what the config file does not
decide. The correction was published, propagated to four documents, and sent to the concurrent agent
as advice to change a host profile — all of it contradicting a line this repository prints on
demand.

Two things follow that are worth more than the arithmetic:

- **Consult the instruments before writing a correction**, not only before writing a claim. A
  correction carries more authority than the thing it corrects, so it deserves more checking, not
  less. `audit_executed_hyperparameters.py` and `audit_comparability_seam.py` both had jurisdiction
  here and neither was run.
- **The audit could not have caught it anyway, and now can.** It parsed only `--flag` form, so the
  RL-ViGen five's hydra `key=value` overrides — the very mechanism at issue — were invisible to it,
  and the five did not even resolve to their shared launcher. Both fixed, with launcher overrides
  now taking precedence over the config file, as hydra itself resolves them.

| # | the claim | status | what is actually true |
|---|---|---|---|
| 37 | **A37: "kernel non-determinism changes the numbers"** — that determinism-ON versus OFF explained the differing returns | **WRONG ATTRIBUTION. The flag is not the variable** | Your repeat run `bt1e78hbs4s946aje3q9` has byte-identical `evaluator_revision`, `payload_sha256`, `checkpoint_sha256` and `det=True` to `bt1baht74a35e6uq582c`, and **produced different returns** — the same 2 of 5 episodes, the same magnitudes. The second ON run is byte-identical to the OFF arm. So what the ON/OFF comparison measured was **run-to-run variance present with determinism enabled**, not an effect of the flag |
| 38 | That evaluation under a fixed revision is reproducible — the premise behind "the same checkpoint under the same revision gives the same number" | **FALSE for this evaluator** | Determinism governs torch kernels; **MuJoCo physics and EGL rendering produce the observations and are outside it**. The differing-episode pattern (0 and 2 differ, 1 sits unchanged between them) rules out RNG-stream divergence and fits threshold-sensitive episodes flipping on sub-ULP render differences — consistent with C70's note that Door is threshold-sensitive. Torch RNG is seeded for every family (`seed_the_placement_rng`), so it is not the cause |

**The lesson, and it is the sharpest one of the session.** A37 compared two runs that differed in a
flag, saw different numbers, and attributed the difference to the flag. **The missing control was a
repeat of the same arm** — the cheapest possible experiment, which I recommended to Codex in the
same message where I made the unsupported claim. Had I run it before publishing, the claim would
never have been written. Two conditions differing is not evidence about the condition until you know
what one condition does twice.

| # | the claim | status | what is actually true |
|---|---|---|---|
| 39 | **My #22 refutation of reviews 8 and 9** — that ctrl had no running condition counter and so could not be double-advanced | **WRONG. The counter exists and the defect was real** | I read `**_ignored` in `runnable/_patches/ctrl.patch`, which is a **stale snapshot**; the live clone passes `condition_seed` into `_SyncVecEnv`, whose `_reset_one` does `self._episode_indices[index] += 1` on **every** reset — and `step_wait` auto-resets on done. With the evaluator also resetting explicitly per episode, **measured episode *i* ran condition index 2*i*** while the record claimed *i*. ctrl was unpaired from every other family and its `placement_condition_seeds` were wrong. Fixed by resetting once and letting the auto-reset begin each episode — the idaac/ppg pattern. **Verified by instrumenting the live counter: 0 -> 1 -> 2 -> 3, one index per measured episode.** |

**Third time in one session that I read a declaration instead of the thing that runs** — after
`ProcgenVecEnvCustom` (#21) and `action_repeat` (#35/#36). Here the trap was a **patch file**: a
`.patch` under `runnable/_patches/` is a provenance snapshot, and I had spent part of the same night
proving those snapshots drift (five of six were stale). **I then used one as evidence about live
behaviour.** The clone is the artifact; the patch is a record of it.

| # | the claim | status | what is actually true |
|---|---|---|---|
| 40 | **"The evaluator is frozen, so validate now"** — my own plan, stated to the owner | **IT WAS NOT FROZEN, AND COULD NOT BE** | `families.json` was a revision member, and **two pending owner decisions live in it**: A14's host profiles and A20's `curve_eval_episodes`. So ratifying either would have moved the hash and voided every family validated beforehand. The revision had already moved twice in one day for that reason. Freezing was impossible while any decision stayed open, which made "freeze then validate" unachievable as stated |

**The cause was my own fix, one layer up.** I added `families.json` to the revision to close an
*under-sensitivity* hole — two materially different evaluator configurations could share one hash.
That reasoning was right. What it missed is that the hash was then doing **two jobs**: identifying
the evaluator as code, and identifying its configuration. Those change for different reasons and on
different schedules, and collapsing them made the stricter of the two govern both.

Fixed by splitting: `evaluator_code_revision` over the six code members, `evaluator_config_revision`
over `families.json`, and the combined `evaluator_revision` retained. Verified by executing it — a
descriptor edit moves config and combined, and **leaves code unchanged**. So a family validated
against the code stays validated through A14 and A20 ratification, while analysis can still refuse
to pool rows that disagree on either axis.

**The general lesson: a single identifier for two things that change on different schedules will be
governed by the faster-moving one**, and everything keyed to it inherits that churn.

## #41 — my budget auditor could not see the config shape I now use for everything

`audit_job_budgets.py` existed because a job was killed by its own `timeout` after paying for
provisioning. It parsed `OFFLINE_EVAL_EPISODES` only. When I later split the evaluation scopes and
introduced `ENDPOINT_EVAL_*`, every validation config written afterwards returned `None` from
`episodes_of` and hit `continue` — printing **nothing**, which on this report is indistinguishable
from passing. Three live configs were uncosted while the instrument exited 0.

It also charged nothing for the **training phase**, though every validation config trains 10k frames
before evaluating and that phase dominates the budget.

Fixed: both scopes parsed, training costed from measured per-family FPS, family recovered from
`CELLS=` when no `OFFLINE_EVAL_FAMILY` is present. Pinned by
`tests/test_budget_audit_sees_endpoint_scope.py`, including a regression that walks the live configs
on disk and fails if any evaluation is invisible to the auditor.

**And I immediately introduced the mirror error**: charging offline configs for a training phase
they never run, whose `FRAMES` is vestigial. Six historical configs turned red before I checked one.
That is a false ALARM — the safe direction, and still wrong. Gated on `OFFLINE_EVAL_SNAPSHOT`.

**Eight for eight.** Every instrument this project has audited was found wrong, including three
written to enforce this very rule.

## #42 — three output filters lied to me inside ten minutes

Submitting the two validation jobs, my `grep -oE "bt1[a-z0-9]{18,}"` matched nothing because the ID
carries 17 characters after `bt1`, not 18. Both jobs had been **created successfully**; I printed
`SUBMIT FAILED` for both and nearly resubmitted duplicates. Earlier the same session: a `grep -c
"^FAILED"` against colorized pytest output, and `$?` reading a pipeline's last stage.

The pattern is one thing, and it is the *same* pattern as #41 and as Mechanism 1: **a filter that
finds nothing reports the same thing as a filter over nothing.** The rule I keep relearning — read
the raw output, or read the authoritative ledger (`job list`), and never let a convenience filter
stand between me and whether an action happened.

## #43 — the memory check certified six of seven families by knowing nothing about them

`family.check_memory` did `if peak is None: continue`, and the caller then printed **"memory ok"**.
Only `alda` had a recorded `fixed_peak_gib`, so for the other six the check was a formality that
always passed. `ctrl` was certified for `gt4.1` that way and **SIGKILLed at 11.07 GiB**
(`bt1lhobnsq5lq4766np6`, status 137, 87 seconds).

Worse, `ctrl`'s descriptor **already declared `minimum_tier: gt4i.1`**, and `check_tier` would have
refused the config outright. Nothing called it: a hand-written cfg submitted with `datasphere
project job execute` never touches `job.sh`, where the checks live. `gate_scheduler_ram_invariant`
was PASSING the whole time, because it verifies that the submit script *contains* a check — and its
own comment says, in writing, that this is how alda was SIGKILLed the first time. I read that
comment while writing a different gate and still submitted three configs the same way.

Three jobs lost: ctrl (OOM), alda (cancelled once the arithmetic was checked — 15.73 GiB against a
14.5 GiB tier, already recorded), and rlvigen — which named `CELLS=rlvigen:1` when `rlvigen` is an
evaluator FAMILY whose baselines are drqv2/svea/drq/sgqn/curl. That one died in three minutes having
produced nothing.

Fixed: `check_memory` fails closed on an unmeasured family (with an explicit `--allow-unmeasured`
escape hatch, so the risk is attributable rather than inherited); ctrl's measured peak recorded from
the kill; `scripts/audit_submission_configs.py` reads the **configs themselves** for real cell names
and a tier the family fits; `gate_submission_configs_runnable` runs it. Eleven historical configs
are marked `# SUPERSEDED` — the default is LIVE, so forgetting to mark one is the safe direction.

**Certifying that a mechanism exists is not certifying that the path in use invokes it.**

## #44 — the tests written to catch swallowed defects swallowed defects

`test_family_env_smoke.py` and `test_family_regime_readback.py` wrapped construction and stepping in
`except Exception -> pytest.skip(...)`, eight sites. A `TypeError` from our own wrapper and a genuine
"this stack is not installed here" produced the **same green skip**. External review 9 asked for
exactly this and nothing had engaged with it.

The sting is that `START-HERE.md` already carries the caution — *"a skip line is a claim about the
world, exactly like an assertion"* — written after `test_rlvigen_reference.py` skipped for the
project's entire life on a false premise. I wrote that sentence and then left the same pattern in
the two tests whose whole purpose is catching what the suite cannot see.

Fixed: skip only for `ImportError`/`ModuleNotFoundError`/`FileNotFoundError`, or an error whose
message names a missing renderer; everything else raises. **On this machine all 12 now pass and
none skips** — so those eight skip lines were protecting nothing and hiding everything.

## #45 — I wrote a guard that could never fire, and a gate that certified it

Minutes after adding `gate_submission_configs_runnable` — whose entire lesson is *certifying that a
mechanism exists is not certifying that the path in use invokes it* — I added a production guard
that refuses to start a 6e5-frame run unless `NATIVE_HOST_PROFILE` is named, and tested it with:

    if [[ "${FRAMES:-10000}" -ge 600000 && -z "${NATIVE_HOST_PROFILE:-}" ]]

`run_probe.sh` **line 6** does `export NATIVE_HOST_PROFILE="${NATIVE_HOST_PROFILE:-datasphere}"`.
By the time the guard runs, several hundred lines later, the variable is always set. The condition
is unsatisfiable. The guard was dead code protecting the single failure mode that
`MIGRATION-T4-TO-V100.md` exists for.

**And both of my checks passed on it.** `gate_production_names_its_host` matched the text.
`test_the_gate_would_fail_without_the_guard` deleted the guard and confirmed the gate went red —
which proves the gate *reads the file*, and says nothing about whether the guard *works*. I wrote a
non-vacuity test for the wrong artefact and then believed it.

Found only by asking a different question: "does anything already set this variable?" — a grep I ran
for an unrelated reason.

Fixed: the runner now captures whether the **caller** named a host, before applying the default.
`tests/test_production_host_guard_fires.py` lifts both fragments out of the real script and
**executes them**, asserting exit 3 at 600000, exit 0 at 599999, and that a 10k probe is unaffected.

**The rule this earns, which is stronger than the one I had:** a test that a checker notices a
missing thing is not a test that the thing works. For any guard, run it — with the input it is
supposed to reject.

## #46 — the endpoint's depth fell back to the curve's

Closing A20 meant setting the curve's episode depth. The runner had:

    --episodes "${OFFLINE_EVAL_EPISODES:-${CURVE_EVAL_EPISODES:-20}}"

and the same nested fallback for `REGIMES` and `SCENES`. So whenever the endpoint's own variable was
unset — which is the default in every config that does not name it — the **endpoint measurement,
which carries the headline claim, would silently have taken the curve's depth and grid.** Setting
A20 to 3 would have quietly changed the endpoint from 20 episodes to 3.

The coupling ran in the damaging direction: a supporting figure's cost knob reaching into the
measurement that the whole campaign is for. It is the two-homes mechanism with a gradient — the two
homes were not equal, one silently overrode the other.

Fixed: each scope carries its own default (`curve` 3, `endpoint` 20), with no fallback between them.
That is what `--eval-scope` was introduced for, and the fallbacks predated it. Pinned by
`tests/test_endpoint_and_curve_scopes.py::test_the_endpoint_does_not_inherit_the_curves_depth_or_grid`,
which asserts the nesting is absent rather than asserting the current values — so re-introducing the
coupling fails even if the numbers change.

## #47 — every ctrl evaluation died at checkpoint load, and the freeze had to move

`eval_grid.py:817` built a JAX shape directly from the descriptor:

    fake_state = jnp.zeros((1, d["cluster_len"], 64, 64, 3))

`families.json` stores constants as **strings** — they become CLI flags — so JAX received
`(1, '10', 64, 64, 3)` and raised `Shapes must be 1D sequences of concrete values of integer type`.
Every sibling in the same function converts (`int(d["num_clusters"])`, `float(d["lr"])`); these two
did not.

**Training was unaffected**, which is why it survived everything: the failure is at checkpoint load,
so it needed a ctrl cell that trained to completion — and the first attempt was SIGKILLed by a tier
the descriptor already knew was too small. Two bugs deep, and the outer one hid the inner one.

**The frozen code revision moved**, deliberately:

    4a77df8be2c5a197...  ->  4bef9881a418c2d88a450d38a902bd3aa159d724a651741917935caa826435d2

A freeze that preserves a fatal defect is worth nothing. What the move costs is stated plainly: the
`drqv2` validation (`bt11auoe27bldreg229k`) was taken on the previous hash. **The diff is confined
to `_ctrl_train_state`, a function only the ctrl family executes**, so that validation remains
evidence about the drqv2 path — but it is now evidence about a hash the fleet will not run, and if
any claim turns on it, re-run it. Recorded rather than argued away.

Pinned by `tests/test_descriptor_values_are_converted.py`, which **scans** for the class rather than
the line, and whose own non-vacuity is tested: it is run against the code as it actually was and
required to flag it.

## #48 — I clobbered the evidence with my own extraction and nearly reported a system defect

Verifying alda's validation, I downloaded `records.jsonl` (7 rows: 3 training + 4 endpoint) and then
ran `tar xzf result.tgz` **in the same directory**. The archive contains its own `records.jsonl` —
the in-container training bundle, 3 rows, no endpoint — which **overwrote the downloaded file**.

I then reported "alda: SUCCESS but zero endpoint rows", called it a job that succeeds without
measuring anything, and spent four tool calls tracing a merge bug in `run_probe.sh` that does not
exist. The job log said `NATIVE_RECORDS_EMITTED 7 rows` the whole time.

**This is the fourth false negative from my own inspection today**, after `host_profile` (nested one
level down), the determinism stamp (nested two levels down, under a different key name) and the
submission grep whose quantifier was one character too greedy. The instruments were right every
time; my reading of them was wrong.

The rule, and it is now explicit: **download artifacts and extracted archives go in DIFFERENT
directories**, because they contain same-named files with different scopes — and a negative result
from my own inspection is a hypothesis, not a finding, until the producing side's own log agrees.

## #49 — a redundant, malformed override wasted one job

Added `NATIVE_EXTRA_OVERRIDES=procs=1` to the ibac_sni validation config defensively, without
checking two things first: the override is passed as raw argv tokens (`--procs 1`), not `key=value`,
so `train.py` rejected it (`unrecognized arguments: procs=1`); and it was unnecessary regardless —
`families.json`'s base descriptor already defaults `ibac_sni.procs` to **1**. Fixed by deleting the
line. Not generalized into an instrument: this is an authoring slip, not a class of defect the
project has hit twice.

## #50 — "35.5 GB, the whole fleet's checkpoint grid" is a different number, misattributed

`retention-and-eval-depth.md` states: *"At the measured sizes the whole fleet's grid is 35.5 GB on
a 50k stamp cadence."* Traced to its actual source: `claude-answers.md:1311` —
`600000 x 63504 = 35.5 GiB replay` — **the in-memory replay buffer size for ONE off-policy cell at
600k capacity**, not a checkpoint-retention total, and not fleet-wide. Two unrelated quantities
happened to land in the same ballpark and the second use copied the number without re-deriving it.

**The real number was never computed.** Nobody had run the arithmetic: real per-baseline checkpoint
size x 12 stamps x 3 seeds x 12 baselines. Measured now, from actual snapshot files already on disk
from tonight's validation jobs (bytes, single checkpoint):

| baseline | measured bytes | GiB / 12-stamp cell |
|---|---:|---:|
| drqv2 | 104,136,194 | 1.164 |
| alda | 103,939,926 | 1.162 |
| rad | 92,297,730 | 1.031 |
| svea | 69,809,490 | 0.780 |
| ctrl | 39,835,494 | 0.445 |
| ibac_sni | 27,611,533 | 0.309 |
| idaac | 5,031,594 | 0.056 |
| ppg | 5,027,918 | 0.056 |

**drq, sgqn, curl, soda were never run tonight and have no measured checkpoint size.** Estimated by
architectural analogy only (drq/sgqn/curl share drqv2's SAC-based agent class; soda shares rad's) --
stated as estimated, not measured, per this project's own convention:

    fleet total (measured 8 + estimated 4, 12 stamps, 3 seeds) ~= 28.6 GiB

**The conclusion happens to survive — checkpoint retention is still trivial against disk — but for
a different reason than stated, and by a smaller margin of certainty than "measured" implied.** The
same 35.5 GiB figure is separately and CORRECTLY the per-cell replay-buffer size in its original
context; it was never wrong, only reused somewhere it did not belong.

**Also found while measuring:** a patch-comment in `RL-ViGen-upstream/train.py` claims "3.4 GiB for
drqv2... per cell" for full 12-stamp retention. `1.164 GiB` measured here is ~3x smaller. Not
reconciled -- recorded as an open discrepancy between a code comment and a direct measurement,
which is itself the standard this project holds other claims to.

## #51 — a disk-safety fix moved the frozen hash again, correctly, because a patch anchor broke

While wiring `runnable/_shim/safe_checkpoint.py` into every family's checkpoint-write call (a
disk-full crash mid-write must never kill a multi-hour run, and a torn write must never corrupt the
checkpoint a resume or evaluator loads next), one edit landed inside a **frozen code member**:
`setup/apply_patches.py`'s `P18_REPL` anchor text included the exact `with snapshot.open('wb') as f:
torch.save(payload, f)` line I replaced in `RL-ViGen-upstream/train.py`. Editing the live clone
without updating the anchor left `test_upstream_patches_are_applied` reporting `P18 ANCHOR NOT
FOUND -- upstream changed, or hand-edited`, a genuine false negative on a real, correctly-applied
patch.

Fixed by updating `P18_REPL` to match the new code exactly (both the main and the stamped-copy
sites). `setup/apply_patches.py --check` now reports "the vendored tree matches its pinned commit
plus exactly the declared differences" across all 28 tracked patches — confirmed none of the other
six families' patches share an anchor with a safe_checkpoint edit site.

**Hash moved a third time tonight**, correctly: `4bef9881...` -> `6888d2a9836aaba3ff96476848606b2e92bb29eaebe602828eaa3e0077099698`.
Unlike CORRECTIONS #47 (a genuine behavioral bug), this move is a pure provenance/detection-text
fix with no runtime effect -- argued and tested (`tests/test_safe_checkpoint.py`'s ENABLES-class
self-tests: normal write is byte-identical to before; only the failure paths differ) rather than
assumed. Whether that argument is sufficient to avoid a full 7-family re-validation on this exact
hash, versus running one more confirming sweep, is recorded in `EVALUATOR-VALIDATION-STATUS.md`
once the in-flight jobs land.

## #52 — the disk-safety module had two bugs that would have crashed every real checkpoint write

Both found only because I insisted on a REAL remote proof job rather than trusting local unit
tests, exactly as argued to the user before submitting them.

1. **A keyword collision.** `safe_torch_save` hardcoded `label="torch.save"` while also forwarding
   a caller's own `label=...` through `**kwargs`. Every one of the eleven call sites wired tonight
   passes `label=` explicitly, so this raised `TypeError: got multiple values for keyword argument
   'label'` **unconditionally, on the very first checkpoint write, in six of seven families** (every
   site that goes through `safe_torch_save`; `ctrl`'s direct `safe_write` call was unaffected,
   which is exactly why it was the one proof job that succeeded). My own `test_safe_checkpoint.py`
   never caught it because its `torch_kwargs=...` test never also passed `label=` -- the one
   argument every real site actually supplies.

2. **A PYTHONPATH assumption.** Every site assumes `runnable/_shim` is on `PYTHONPATH`, true via
   the real launchers but not for `tests/test_datasphere_native_contract.py`'s own subprocess
   harness, which builds a minimal environment. `ModuleNotFoundError: No module named
   'safe_checkpoint'` — and, more importantly, **an import failure would have crashed training
   exactly the way this entire module exists to prevent**, the one self-referential failure mode I
   had not defended against.

Fixed: `kwargs.setdefault("label", ...)` closes (1). Every one of the eleven call sites now wraps
its import in `try/except ImportError`, falling back to plain `torch.save`/`open().write()` — so a
missing `_shim` degrades to the pre-tonight behavior rather than crashing. The test harness itself
now stubs `sys.modules["safe_checkpoint"]` rather than relying on `PYTHONPATH`, matching what a real
launcher actually provides. Pinned: a parametrized test that every site has an `ImportError` guard,
a test that executes a representative fallback with the real module genuinely blocked, and an exact
regression test reproducing bug (1)'s precise call shape.

**The pattern, stated plainly because it is now the second time tonight**: a module tested
thoroughly in isolation (four clean property tests) still shipped two defects that would have
failed on contact with its real callers, because the tests never called it exactly as the real call
sites do. Isolated unit tests of a shared helper are necessary and not sufficient; the callers'
actual invocation shape has to be in the test too, not assumed to match.

**Both required editing `setup/apply_patches.py` a second time** (P18's anchor now needs the
try/except form), moving the frozen code revision a fourth time. Since `apply_patches.py --check`
now reports every one of 28 patches consistent and every touched file parses, this is expected to be
the last hash move needed for tonight's disk-safety work specifically.

## #53 — a near-miss cancellation existed only in a compacted summary, not a durable file

Checked the full authoritative job list (`datasphere project job list`, all 77 jobs across this
project) against my own running account, prompted by the user asking directly whether any finish had
been missed. Every job resolved to an accounted-for cause **except one**: `bt1gm8cp0rp2ltv2b0aj`
("Recompute IDAAC agreement... closure-fixed retry"), `CANCELLED` at 2026-09-05T04:39:10.

This matches a near-miss narrated in this session's own inherited context summary — a UTC/MSK
timezone misreading that nearly led to cancelling a healthy job — but **grepping `CORRECTIONS.md`
for it returns nothing**. It was never actually written into the durable ledger; it existed only in
a compacted summary, which is exactly the class of gap #so far unrelated to A23-A25's chat-only
findings but structurally identical: something true and known, living nowhere a future reader (or a
future context-compaction) could find it.

No current consequence — `idaac` has since been independently, successfully re-validated multiple
times tonight (v105, then v119) on fresh regime/revision-checked records, so nothing rides on this
one cancelled job. Recorded for the ledger's own completeness, and as a second confirmed instance of
"say it once in chat/summary, never write it down" — the exact failure the A23-A25 exchange
diagnosed. Full job-list sweep found no other unaccounted-for finish.

## #54 — rlvigen's checkpoint cadence was stuck at a stale DataSphere disk limit on V100

Prompted by being asked directly whether "same points" across the 12 baselines was actually true, not
assumed. Traced the real mechanism (declarative `options`/`production` templates in
`families.json`, confirmed empirically against real executed commands from tonight's own validation
jobs for idaac and dmc_gb, both correctly wired) and found the one place it wasn't: **rlvigen's five
baselines** (`drqv2`/`svea`/`sgqn`/`curl`/`drq`) preserve an intermediate checkpoint every
**100,000** frames, while all six other families are at **50,000** -- 6 stamps vs 12 at 600k.

The 100k figure was a deliberate, correctly-reasoned DataSphere-container decision ("20.2 GiB free
in the container"), not an oversight in intent -- but a v100 host-profile override already exists
for this exact family (it overrides `replay_capacity`) and was simply never extended to this
setting, so it silently carried the DataSphere-era value onto a host where the reason for it no
longer applies: production runs on our own V100 disk, the decided policy is "retain every
checkpoint," and the real per-stamp cost is ~104 MB (measured) -- 12 stamps is ~1.16 GiB/cell,
nowhere near the container limit that justified 100k.

Fixed: `host_profiles.v100.production.preserve_snapshots = 50000` added, mirroring the existing
`replay_capacity` override on the same profile. Gated (`gate_checkpoint_cadence_matches_fleet`),
pinned non-vacuous against the pre-fix state.

**Everything else checked in this pass was correctly wired**, confirmed empirically from real
executed commands, not just declared: idaac's `--save_interval_frames`, dmc_gb's `--save_freq`,
ppg's `--save_mode all` (already fixed once before, for a different bug), alda's hardcoded 50k,
ctrl's frame-stamped msgpack. The "zero periodic training-time evaluation" for ppg/ibac_sni is
correctly not a gap: A20's offline checkpoint-based curve substitutes for it uniformly across all
twelve, which is the whole reason the evaluator is a separate harness from each family's native
training log.

## #55 — Codex mailbox Q18/Q19/Q20/Q21: three confirmed defects fixed, two handed off, one canary order corrected

Reviews 11/12 and Gemini found real, confirmed defects via Codex's independent tracing. Triaged and
acted on:

- **T3 (terminal checkpoint fail-closed)** — every `safe_torch_save` call site discarded its return
  value, so a failed write to a fixed-name checkpoint (idaac's `agent{}.pt`, ibac_sni's `model.pt`,
  rlvigen's `snapshot.pt`) could leave that name either missing or STALE while the job exited 0.
  Fixed at all five fixed/canonical-name sites: idaac's `_is_last` branch, ibac_sni (a genuinely
  NEW guaranteed post-loop final save was needed too -- the file had no code after its training
  loop at all, so there was never a deterministic final save regardless of interval alignment),
  rlvigen's `save_snapshot` (terminal-only, since the function is also called periodically from two
  other sites), alda and dmc_gb (step-stamped names, lower risk, still made to fail loudly at the
  point of failure rather than confusingly later). Periodic/intermediate saves at the same
  functions deliberately remain best-effort -- making them fail-closed too would reintroduce the
  crash risk `safe_checkpoint` exists to prevent. Pinned: `tests/test_terminal_checkpoint_fail_closed.py`.

- **T4 (`NATIVE_PRODUCTION` enforcement)** — a separate, pre-existing flag from my own
  `NATIVE_HOST_PROFILE_EXPLICIT` guard; nothing enforced it. A job could satisfy my guard (host
  named) while `NATIVE_PRODUCTION` was still unset, causing `apply_production_settings` to silently
  apply NOTHING and train a full 600k+ run at probe-scale cadence/replay the whole time. Extended
  the existing production-scale refusal to require both. Pinned in
  `tests/test_production_host_guard_fires.py`.

- **T8 (A20's 3-vs-5 contradiction)** — real, and mine: `families.json`'s `curve_eval_episodes: 5`
  in every family's `production` block silently overrode A20's decided 3, at the actual
  `production_env()` emission point, which I had not traced when I made the A20 decision. Fixed all
  seven families; fixed the test that had locked in 5 as correct.

**Handed to Codex, not duplicated**: T1 (IDAAC rollout-storage episode identity — it independently
traced the exact call chain, I have none), T2 (IBAC procs=16/worker RNG, already treated as its own
design-and-validation work), T7 (the cwd-sensitive pairing gate), T9 (regenerating
schedule/audit artifacts from the resolved V100 profile instead of the stale DataSphere one).

**One of my own prior recommendations corrected as a result**: the canary order (`idaac` first)
was internally contradictory while T1 is live — canarying a family with a known-live storage bug
tests the defect, not the pipeline. Reordered to `drqv2` first in `DECISION-SHEET.md` and
`NEXT-ACTIONS.md`, both updated rather than left stale.

## #56 — asymmetric wait window for terminal saves, and my own new import bug

Prompted directly: 5 minutes is a reasonable bound for losing one intermediate curve point, but a
thin margin for a human to notice a full disk and actually clear it before losing an entire
multi-hour-to-multi-day run's only reportable result. Added `TERMINAL_MAX_WAIT_SECONDS = 1800`
(30 min), applied only at the five fail-closed terminal sites from #55; periodic/intermediate saves
keep the original 300s bound.

**Introduced, and caught by my own test, a second instance of the exact `#52` pattern within the
same edit.** Adding `from safe_checkpoint import TERMINAL_MAX_WAIT_SECONDS` as a bare, separate
import statement at each site meant that if `safe_checkpoint` genuinely could not be imported, THIS
import would raise uncaught -- crashing exactly where the whole module exists to prevent a crash,
on the TERMINAL path specifically. Worse: my own `test_every_site_wraps_the_import_in_try_except_importerror`
had a false-negative flaw that let two of the five instances (idaac, ibac_sni) pass anyway, because
it counted `except ImportError:` occurrences GLOBALLY per file rather than checking each import's
own guard -- both files have unrelated import-compat shims elsewhere that inflated the count. Fixed
both: every site now imports `safe_torch_save` and `TERMINAL_MAX_WAIT_SECONDS` together in ONE
guarded statement with a matching fallback constant; the test now checks that each import line is
directly preceded by its own `try:`, not a file-wide count.

**Fifth and (for this specific edit sequence) final move of the frozen `apply_patches.py` P18
anchor** to match. `setup/apply_patches.py --check` confirms all 28 patches consistent afterward.

## #57 — "the terminal save is different" was structurally checked, not actually run

Asked directly: had I ensured the terminal-save fail-closed behavior was good for all five sites?
Honestly, no — four of five only had structural tests (the right-looking text exists near the right
call), not tests that execute the guard and observe it actually fire. Fixed by extracting each real
fragment (idaac, alda, rlvigen, dmc_gb) and `exec`-ing it with `safe_checkpoint` faked to fail,
confirming the `RuntimeError` genuinely raises, and separately that periodic/non-terminal calls at
the same functions genuinely do not raise on the identical failure.

**Caught immediately: my own fake `safe_checkpoint` module was missing `TERMINAL_MAX_WAIT_SECONDS`.**
`from safe_checkpoint import safe_torch_save, TERMINAL_MAX_WAIT_SECONDS` partially failed against
the incomplete fake, fell through to the real file's `except ImportError` fallback -- which always
succeeds -- so the first version of these tests could not have failed even if the real guard were
completely absent. Exactly the shape of #52 and #56: a test asserting a property it was not actually
exercising. All 17 tests (structural + functional) now pass for real.

## #58 — an undocumented V100 throughput override moved PPG off the one published continuous-control cadence

Found 2026-09-05 while answering a direct question about whether the recent external reviews raise
schedule-deviation concerns, and specifically by re-reading **review 11 §7** in the raw text rather
than through its triage summary.

PPG's defining auxiliary phase fires every `num_envs x nstep x n_pi` interactions. The reference
points, all verified in the tree rather than quoted:

| configuration | interactions per auxiliary phase | auxiliary phases in a 600k cell |
|---|---:|---:|
| literal Procgen PPG, single rank (`train.py:131` `num_envs=64`, `:135` `n_pi=32`, nstep 256) | 524,288 | ~1.1 |
| literal Procgen PPG, the 4-rank MPI setup review 11 assumed | 2,097,152 | 0 |
| **this project's base constants** (`families.json` ppg `num_envs: 8`, `nstep: 256`) | **65,536** | **~9.2** |
| IDAAC's continuous-control appendix PPG recipe (2048-step rollouts, one process, `n_pi=32`) | 65,536 | ~9.2 |
| **what the V100 profile actually configured** (`num_envs: 16`) | **131,072** | ~4.6 |

**The base configuration already matched the published continuous-control design point exactly.
The V100 host profile silently doubled the interval away from it.** It was the only value in any
of this file's V100 profiles carrying no `_reason`, and `MIGRATION-T4-TO-V100.md` does not mention
`num_envs` at all — so nothing recorded that a throughput override was also an algorithm-schedule
change.

**Review 11's magnitude is the worst-case reading and its finding still stands.** Its "16x more
frequent" compares against a 4-rank Procgen configuration; against the code's own single-process
default it is 4x. Either way the point survives, and survives for a reason the review did not have:
the deviation was not a considered adaptation, it was an unreasoned override on top of a base that
was already correct.

**Also note what "faithful" cannot mean here.** At 600k, literal Procgen PPG runs about one
auxiliary phase, or none under 4 ranks — PPG's defining mechanism would barely operate, and the
baseline would effectively be PPO wearing PPG's name. *Some* retiming is forced by the budget. The
question was only which reference to retime against, and the base config had already answered it.

**Fixed** by reverting the V100 override to 8, preserving `n_pi=32` — PPG's own defining constant —
rather than compensating by halving it. `tests/test_ppg_auxiliary_cadence.py` now pins the product
across *every* host profile (proven non-vacuous: restoring 16 fails it with
`131,072 != 65,536`). The cost is real and is not being hidden: 8 envs collect rollouts less in
parallel than 16, so PPG's wall-clock per cell rises. That trade is surfaced as **A26** rather than
settled here.

**Incidentally closes review 11 §24's stale-metadata item** for PPG: `min_frames: 2048` documents
"one iteration is num_envs x nstep", which was wrong under the 16-env profile and is correct again
at 8.

**What let this happen, in the class sense.** A host profile is allowed to override any constant,
and the file's convention of pairing each override with a `_reason` is a convention, not a check.
Throughput overrides and algorithm-schedule changes are the same edit here, and nothing distinguished
them. The new test is the narrow fix; the general one — a gate requiring every host-profile override
to carry a reason — is worth doing and is noted in NEXT-ACTIONS rather than built tonight.

## #59 — a red-green-tested fix that protects a code path production does not run

Found 2026-09-05 in the full-project audit. `docs/FAITHFULNESS.md:603-616` records ALDA's
update-to-data ratio being corrected from `1.0` to `0.25` after measured divergence, "pinned by
`tests/test_sweep_gaps.py::test_alda_utd_defaults_to_its_derived_faithful_value` and a second test
that builds through the real registry path ... both red-green verified".

**Both tests import `from rlgen import registry` and assert on `AldaConfig().utd`.** That is the
**retired** `rlgen/algos/alda` port. Production launches `runnable/alda`
(`datasphere/native/families.json:376-377`), which has no `utd` field anywhere and hardcodes the
update count as the literal `1` at `runnable/alda/trainers/alda_trainer.py:649`.

So the ratio in the code that will actually run is **1.0 updates per environment frame** — 4x
ALDA's design point, and the same value this project's own evidence recorded as divergent.

**What is proven and what is not.** Proven for our setup: the ratio is 1.0 where the design point
implies 0.25 (`action_repeat` is a dead knob on the robosuite path, effective 1; ALDA's own specs
use 4). Not proven: that `runnable/alda` on Door diverges — the divergence evidence is Lift, sibling
project, retired port. Strong prior, different task. Recorded as **A27**, with a cheap settling
probe named.

**The class.** A fix can be pinned by a real, red-green test that does not import the module
production launches. Nothing currently checks that the test pinning a value covers the executed
path, and this project moved from `rlgen/algos/*` to `runnable/*` for several families — so the
same shape can hide elsewhere. Filed for a mechanical check rather than fixed by inspection.

**How it was found:** by asking an axis question none of the sixteen tracked comparability axes
asks — not "what does one unit on the x-axis mean" (which `x_axis_accounting` answers correctly and
completely) but "how much learning happens per unit".

## #60 — the resolving-power sentence was for a plan that changed, and its arithmetic failed at the planned n

Found 2026-09-05 in the full-project audit, answering "will the reported results actually show the
true performance of the algorithms".

`docs/CONSTRUCTION.md:805-845` computes what a seed budget can resolve and marks one sentence as the
one to carry into any comparison: *"the five-seed plan resolves differences of about thirty percent,
not five points."* Two things were wrong with using it today.

**(1) The plan is three seeds, not five.** `production-schedule-v100.json` sets
`"seeds": [101, 102, 103]`. The prose headline — the quotable part — describes a design that is not
being run. The table's own n=3 row said 39.7%.

**(2) That row used the normal approximation, in the one regime where it fails.**
`scripts/plan_seed_budget.py` used `Z_80_POWER = 2.802` (1.960 + 0.842) for every n. At n = 3 per
arm, df = 2n-2 = 4 and the correct multiplier is `t(.975,4) + t(.80,4) = 3.717`. Recomputed:

| seeds/arm | was (z) | corrected (t) |
|---:|---:|---:|
| 3 | 39.7% | **52.7%** |
| 5 | 30.8% | 35.1% |
| 50 | 9.8% | 9.8% |

**The two agree at n=50 and diverge only at small n — the signature of a correct t-correction
rather than an arithmetic slip.** A 20% difference needs 13 seeds, not 12.

**Fixed:** `plan_seed_budget.py` now uses a t multiplier and solves the inverse by iteration (the
closed form with fixed z under-counts at small n). `tests/test_seed_budget.py`'s root-n test now
pins the sqrt(2/n) term at an explicit fixed multiplier — the raw law must NOT hold end to end any
more, or the correction would be inert — and a new test asserts the correction binds at n=3 and
vanishes by n=50. CONSTRUCTION.md corrected in place, keeping the original reasoning visible.

**So the operative sentence is: three seeds resolve differences of roughly fifty percent.** Both
inputs are floors in the same direction — the CV comes from a same-seed pair, so it excludes genuine
seed variation, and the t-correction only raises the requirement. Raised as **A28**; full working in
`notes/FINDING-resolving-power-at-n3.md`.

**Why it survived this long:** the number was correct when written, for the plan that existed then.
Nothing re-derives a documented constant when the plan it describes changes, and the seed count
changed in a different file than the analysis. That is the same shape as #58 (a V100 override
changing an algorithm's schedule with no reason recorded) — a value edited in one place silently
invalidating a conclusion written in another.

## #61 — the descriptor-value scanner was fine; nothing forced it to run before a remote job

Codex found and fixed (Q26): a second, distinct unconverted `d["cluster_len"]` use —
`scripts/eval_grid.py:829`, inside `_ctrl_train_state` — reached a real remote job
(`bt1s3hm3166ge2kgg93c`) and killed it at checkpoint load, the same shape as CORRECTIONS #47.

**Checked whether this is a scanner gap, per the standing "mend the system" instruction, before
concluding anything.** It is not: `tests/test_descriptor_values_are_converted.py` is a whole-file
AST scan of `eval_grid.py`, not a one-line patch for the original site, and its own
non-vacuity test (`test_the_scan_catches_the_bug_it_was_written_for`) proves it catches exactly
this shape. `_ctrl_train_state` is a different function from whatever #47 originally fixed, added
later. The scanner would have caught this instantly — **the gap is that nothing ran it between
that code being written and a job being submitted against it.** `production_gates.py`'s "release
suite green" gate explicitly runs only two fast checks and says so; there is no pre-submit hook
tying test execution to a remote job at all.

**Fixed the process gap, not the (already-correct) scanner.** Added the scanner
(0.4s, string-only, no I/O) as a third check in `gate_release_suite_green`. Verified non-vacuous by
breaking the fixed line, confirming the gate goes red (`FAIL ... descriptor values converted`), and
restoring it (`PASS`, confirmed by re-reading the file).

**The genuinely fixed instance of the class is now: any new numeric use of a string-typed
descriptor constant, anywhere in `eval_grid.py`, is caught by a gate that already runs on every
`production_gates.py` invocation — not just by the full suite, which nothing forces before a
remote submission.**

## #62 — three review-13 items marked as still-needed were already fixed; one fix had a stale docstring

Found 2026-09-05 reading review 13's raw text directly (not just through Codex's reconciliation),
per this project's own standing discipline of verifying against the executing tree.

- **§6 (production-override strictness)**: already fixed. `run_probe.sh:391-393` forces
  `strict=1` automatically at `FRAMES>=600000`, and a conflicting ambient override then aborts
  (`NATIVE_PRODUCTION_CONFLICT`, exit 3) rather than silently keeping it — exactly the behavior the
  review asked for. Tested (`test_production_host_guard_fires.py`, green).
- **§14 (IDAAC RuntimeError-vs-skip)**: already fixed. `test_family_regime_readback.py` routes
  through a shared `_absence_or_fail` classifier and carries its own regression test asserting "a
  generic IDAAC construction RuntimeError must not be converted into a skip". Green.
- **§3 (ALDA double environment/replay-buffer init)**: the CODE fix Codex applied
  (`_alda_trainer` in `scripts/eval_grid.py`, one `build(spec, replay_capacity=1, prefill=False)`
  call) is correct and tested (`test_alda_eval_memory.py`, green). Its DOCSTRING was not updated in
  the same edit and still asserted the exact false claim the review caught — "the allocation
  happens in training, which is never reached here". Fixed to describe what actually happens and
  why the kwargs avoid it.

Codex's own audit doc listed §6/§14 among "required engineering/empirical work before a fleet"
(item 4, "reconcile the remaining review-13 lifecycle items"). They are not required work; they are
done. Recorded here rather than editing that doc's conclusions, per this project's "keep the wrong
version visible, append the correction" convention. §13 (three-seed resolving power) independently
corroborates this session's own A28 finding (~50%, not ~30%) from a different derivation — a
useful cross-check, not a new finding.

## #63 — the canary's own budget floor was stale for the profile it exists to validate

Found 2026-09-05 reading review 14 §13 directly, then verified independently before fixing (ran
the exact scenario, confirmed the pre-fix behavior, per this project's non-vacuity discipline).

`idaac` and `ibac_sni`'s `min_frames` in `families.json` is "one full rollout" — `num_processes x
num_steps` (idaac) or `procs x frames_per_proc` (ibac_sni) — stored as a static number computed
from the BASE profile's process count (4 and 1 respectively). The V100 profile raises both (16 and
16), so one full rollout there is 4096 and 2048 frames, not the stored 1024 and 128. `check_budget`
never passed a profile through to `production()`, so a V100-profile canary submitted between the
stale and true floor — e.g. idaac at 2000 frames — would pass the check while completing **zero**
rollouts (`frames // num_steps // num_processes == 0`): training nothing, writing nothing
meaningful, and proving nothing about the profile it exists to validate. Not a production risk (a
real 600k run clears every floor trivially) — a **canary-validity** risk, which is worse in one
way: nothing about a correct 600k run would ever exercise the bug, so it would surface only if
someone ran the exact cheap, small-scale canary this project's own migration order calls for.

**Fixed:** `check_budget` now derives the floor from the RESOLVED profile's constants for the two
affected families (`ROLLOUT_QUANTUM_CONSTANTS`), falling back to the stored value for every other
family, whose floor is warmup-based and genuinely profile-independent. No CLI or shell-script
change was needed: `resolved_descriptor`'s `profile=None` already falls back to reading
`NATIVE_HOST_PROFILE` from the environment, which `run_probe.sh` already exports before both
`check-budget` call sites. Verified directly (not just by the new test): idaac at 1024 frames
passes on `datasphere`, fails on `v100` ("below its floor of 4096"), and passes at exactly 4096.
Same shape confirmed for `ibac_sni` (128 vs 2048). `tests/test_budget_floor_is_profile_aware.py`
proves the old bug shape would have passed and the fix now rejects it, for both families, without
raising the floor for the profile it was already correct for.

## #64 — the production SCHEDULE modeled IBAC-SNI's memory with a different, stale formula than the GATE that checks it

Found 2026-09-05, from the full suite (`test_v100_schedule_models_ibac_sni_resolved_process_tree_
not_one_worker_envelope`), immediately after independently verifying `family.check_memory`'s
process-tree model (17.91 GiB, CORRECTIONS entry on IBAC RAM this session) was correct.

`datasphere/native/plan_production.py`'s `cell_ram_gib()` — which populates
`production-schedule-v100.json`'s `cell_ram_gib_model` field, the number a human or a packing
decision would actually read — had its own, SEPARATE on-policy fallback: a static per-baseline
`ENVELOPE` lookup with no process-count awareness at all. `ibac_sni`'s entry was measured at
`procs=1` (3.10 GiB) and stayed 3.10 GiB in this function even once the resolved V100 profile asks
for `procs=16` (true requirement: 17.91 GiB, `family.check_memory`'s already-correct model). Same
underlying fact — IBAC's process-tree memory — computed twice, in two files, and only one of the
two copies had been fixed.

**Fixed:** `cell_ram_gib()` now takes the resolved `entry` (already available at its only
schedule-building call site) and, when `production.parallel_rollout_memory` is present, computes
`parent + procs*per_worker + margin` from THAT SAME field `family.check_memory` already reads —
one model, two consumers, rather than a second hardcoded copy. Regenerated
`production-schedule-v100.json`; `ibac_sni`'s row now reads `cell_ram_gib_model: 17.91`. Verified
the DataSphere/`plan_row` path (procs=1, where 3.10 GiB is the correct figure) is unaffected — all
of `test_intermediate_retention.py`, `test_production_schedule_not_stale.py`,
`test_production_gates.py` green.

**The class, again.** This is the third time this session a value existed correctly in one place
and stayed stale in a second, independent computation of the same fact (idaac's diff-size figures
in CORRECTIONS earlier tonight; the eval-cadence anchor scanner gap, #61). Worth a standing
suspicion whenever a number is "already fixed" — check whether anything ELSE computes the same
fact independently before considering it closed.

## #65 — a failed cell's manifest could report NATIVE_..._COMPLETED anyway

Found 2026-09-05, from a fresh read-only audit pass (relayed by the owner) pointing at
`run_probe.sh:1070-1071`, and independently reproduced against the already-existing (but until now
failing) test contract in `tests/test_datasphere_native_contract.py`.

`run_offline_eval "$out" || cell_status=1` and `run_cell_list ... || cell_status=1` both correctly
captured failure into `cell_status`, but the VERY NEXT line in both branches unconditionally
exported the COMPLETED marker regardless of `cell_status`. A failed evaluation or training run
could therefore produce a manifest indistinguishable from success by its own completion marker —
the most dangerous class of bug for a benchmark: a quiet failure that reads as a result. The
offline branch additionally blanked `FAILED_CELLS=""` unconditionally, discarding
`run_cell_list`'s own correctly-computed failure list.

**Fixed:** both branches now gate the marker on an `if ...; then / else` around the call, exporting
`FINAL_EVALUATION_MARKER` only on success and a new `FAILURE_MARKER` (`NATIVE_OFFLINE_EVAL_FAILED` /
`NATIVE_FINAL_EVALUATION_FAILED cells=$FAILED_CELLS`) on failure; `run_cell_list`'s own
`FAILED_CELLS` export is no longer overwritten. The manifest-generation Python heredoc now also
carries: `frames_requested` (top-level and per-cell, separate from each cell's `observed_endpoint`
parsed from its own log), `terminal_status`, and a per-cell `failure_marker` — and, critically, a
cell already known to be in `FAILED_CELLS` has its `final_evaluation_marker`/`observed_endpoint`
forced to `None` even if its log contains a real completion line from BEFORE it failed (training
saved, then endpoint evaluation died) — the log's own success text must not read as success once
the cell is known to have failed.

**Also fixed in the same pass:** `identify()` only parsed the real `--cells baseline:seed` spec
format; a caller building `NATIVE_CELLS` from already-formed `baseline-sSEED` identifiers (this
project's own manifest test fixture does exactly that) silently got a doubled identifier
(`ppg-s101-s1`) instead of the intended one, causing every manifest-test assertion on `cells[...]`
to KeyError. Now falls back to parsing the `-s` suffix when no colon is present.

All four affected tests (`test_manifest_distinguishes_requested_frames_from_realized_cell_endpoint`,
`test_failed_cell_manifest_has_no_completion_marker_and_keeps_failure_state`,
`test_runner_sets_completion_only_on_success_and_records_failure_marker`,
`test_run_manifest_reads_the_actual_per_cell_endpoint_marker`) pass; the full
`test_datasphere_native_contract.py` file is green.

**Process note, per the owner's suggestion this session:** two of these tests pin EXACT literal
text (a specific line's shape, a specific string boundary for a source-slicing split) rather than
runtime behavior — the same fragility class as the P18 patch anchor (broke 5 times) and the
eval_cadence/eval_state anchors (#61, and the ibac_sni anchor fixed alongside this entry). Added a
short comment at each such site naming the test that pins it, so a future edit is warned in the
source rather than discovered by a failing suite.

## #66 — the RLV evaluator's identity omitted a file it actually imports live

Found 2026-09-05, reading review 14 §9-adjacent finding (relayed by the owner from a fresh Codex
read-only audit pass) and verified directly before fixing: `scripts/eval_across_scenes.py:136`'s
`run_scene` does `import utils` live, resolving to `RL-ViGen-upstream/utils.py` (confirmed by the
surrounding `from wrappers.robo_wrapper import robo_make`, RL-ViGen's own import). That file is not
incidental utility code — it holds `eval_mode` (gates deterministic-vs-stochastic action sampling),
`TruncatedNormal` (the action distribution class), and `random_overlay`/`attribution_augmentation`/
`random_mask_freq_*` (the augmentation functions, which change what the policy sees). None of it
was in `FAMILY_RUNTIME_MEMBERS["rlvigen"]`, so an edit to it would not move
`evaluator_family_code_revision("rlvigen")` even though it changes what evaluation measures —
exactly the class of gap Codex's own newer per-family closure mechanism was built to close for
CTRL's `vec_env.py`, just not yet applied here.

**Fixed:** added `RL-ViGen-upstream/utils.py` to `FAMILY_RUNTIME_MEMBERS["rlvigen"]`, with a
mutation test (`test_live_rlvigen_utils_edit_moves_only_rlvigen_family_identity`) following the
exact pattern already proven for CTRL's equivalent fix — mutate the file, assert only `rlvigen`'s
identity moves, everyone else's stays put.

## #67 — a test's file pointer went stale when Codex's IBAC repair moved the code it checked

Found 2026-09-05, the last failure in a full-suite run otherwise clean after #58-#66.
`test_direct_rlvigen_adapters_hoist_construction_readback_without_stepping` still pointed at
`runnable/ibac_sni/torch_rl/utils/general.py`, which no longer contains the construction-readback
logic — Codex's Door-specific picklable-factory repair (procs=16 spawn support, per their own Q23
handoff) extracted env construction into a new module, `torch_rl/ibac_sni_runtime.py`. The three
checked string patterns (`"mode": getattr(base, "_mode", None)`, the scene_id equivalent,
`_vigen_regime = dict(applied_regime)`) are all present verbatim in the new file — this was a
stale pointer, not a regression. Updated the test's path with a comment naming why it moved.

## #68 — the raw-vs-clipped-action question is a shared mechanism, not a CTRL-specific one

Three independent external reviews (11, 12, 14) and Codex's own audit doc all named CTRL's
raw-vs-executed action as a "focused port question" without tracing the code. Traced it directly
(A30): `ctrl` samples from an unbounded `MultivariateNormalDiag`, no tanh-squash, no `log_std`
clamp, and its PPO update computes the action's log-probability on that same raw sample even though
`RL-ViGen-upstream/third_party/robosuite/robosuite/controllers/base_controller.py:120` clips the
action before it reaches the simulator.

**Checked whether this was CTRL-specific before writing it up as such — it is not.** `idaac`'s
`DiagGaussian`/`FixedNormal` and `ibac_sni`'s `Independent(Normal(...))` heads are the identical
shape (unbounded, unclamped), and all three build their Door environment through the same
`robo_wrapper.py` -> robosuite controller chain, so all three are clipped the same way before
execution. This is a consequence of authoring a continuous Gaussian head onto Procgen-lineage
algorithms that never had one — Procgen's categorical action space has no analogous clipping seam
at all — not something specific to CTRL's port.

Not fixed (a real algorithmic choice — tanh-squashing or a truncated-normal correction — requiring
the same ratification treatment as every other method-defining item tonight); recorded as **A30**,
broadened from its first CTRL-only draft, with the runbook's clip-rate/log_std diagnostics extended
to all three families rather than just CTRL.

## #69 — my own #68/A30 overstated a monitoring gap that doesn't exist, in the same session it was written

Self-caught while cross-checking the new A30 entry against `REGISTER.md`, minutes after writing it.
#68/A30 said CTRL, IDAAC and IBAC-SNI have no `log_std`/boundary monitoring and recommended adding
it. Checked before letting that stand: **all three already call `gaussian_policy_health` live**
(`ctrl`: `train_ppo.py:359`; `idaac`: `train.py:58,374,381`, logging `train/boundary_fraction`;
`ibac_sni`: confirmed by `REGISTER.md`'s 2026-09-04 entry, which used exactly this measurement to
catch ibac_sni's boundary_fraction crossing 0.50 by ~50k frames — already an open owner decision,
predating and independent of A30). The objective-correctness point (PPO computes `log_prob` on the
pre-clip action) is unaffected and still stands; only the "nobody watches for this" framing was
wrong, and it was wrong for all three families, not a nuance in one.

**What IS real, found in the same check**: `scripts/eval_provenance.py::action_diagnostics()`
computes the empirical counterpart (`action_clip_rate_coordinate/vector`, generic per family) and
has zero call sites anywhere in `scripts/` — built, correct-looking, never wired in. Corrected A30
and `PRODUCTION-RUNBOOK.md` in place (append-and-correct, not silent rewrite) rather than leaving
the wrong monitoring claim to be found later. Recorded as its own numbered entry rather than folded
into #68 so the self-correction is visible as its own event, per this project's own standard for
what a correction log is for.

## #70 — the A28 seed-resolving-power fix hadn't propagated to the two docs that cite it operationally

Found 2026-09-05 while checking whether the OWNER "statistical protocol frozen" gate had any
locally-fixable component. `docs/EVAL-PROTOCOL.md`'s own seed-licensing table (§4b) and
`docs/INTEGRATION-DELTA.md`'s C18 citation both still quoted the pre-A28 "~31% at five seeds"
figure — the exact number CORRECTIONS #60 already fixed in `CONSTRUCTION.md` and
`plan_seed_budget.py`, just not propagated to these two operational citations. Fixed both to state
the corrected ~53%-at-n=3 figure with a pointer back to A28/`FINDING-resolving-power-at-n3.md`.

Searched for every remaining citation of the stale figure before considering this closed (grep for
"~31%", "30.8%", "about thirty percent" across `docs/` and `notes/`) — the only other hits are
`CORRECTIONS.md` itself (historical, correctly presented as superseded) and this entry's own text.

## #71 — two more review-14 points the earlier triage pass had genuinely missed, found on a full re-read

The owner asked directly whether any review points had been silently skipped or treated as noise.
Re-read reviews 13 and 14 completely rather than by section-title triage. Two real, substantive
misses, both now fixed:

**§9 — CTRL's PPO and its clustering loss are not the same question, and A30 had collapsed them.**
`runnable/ctrl/algo.py` has a SEPARATE representation/clustering loss (`loss_cluster`, line 173),
distinct from the PPO losses, that also conditions on `action` — confirmed it receives the identical
raw stored action PPO uses (`extract_windows_vectorized(action, cluster_len)` windows the same
batch field). Review 14's actual point is sharper than A30's first draft: PPO's use of the raw
action is arguably CORRECT (importance sampling needs the sampled action's own log-probability);
the clustering objective's use of it is the genuinely questionable one, since it is modeling a
transition that physically used the executed (clipped) action. A30 corrected in place with this
distinction and the narrower, cheaper experiment review 14 actually proposed (vary only
`loss_cluster`'s action input, hold PPO fixed) rather than a vague "sensitivity study".

**§14 — `EVAL-PROTOCOL.md`'s own episode-count table survived a "superseded" label while still
reading as current.** The 50k-stamp cost table used 5/10/20 episode counts, and the sentence right
after it said "the 50k grid is already wired for every family" in the present tense — exactly the
contradiction the review named, even though "Superseded" appeared elsewhere on the same line. A20
decided 3, and every family runs 3. Reworded to state the current default explicitly and keep the
table only for its cost *shape*, not its counts.

Both were sections I had read the title of and cross-referenced against the T1-T30 table, but not
re-derived from the code myself before this pass. The lesson generalizes the same way #69 did:
matching a review point to an existing tracked item is not the same as verifying the tracked item's
resolution actually addresses what the review said.

## #72 — a gate fix I made minutes ago introduced a live false PASS; self-caught before it stood

Review 14 §23 said several OWNER gates carry stale detection logic reflecting decisions already
superseded by the operational default. Checked directly: `gate_seed_policy_frozen` unconditionally
described the OLD adaptive-allocation problem as if still live, even though `EVAL-PROTOCOL.md`
already states the fixed-n=3 default that replaced it. Fixed its message to describe the current
state (accurately, still OWNER — a written default is not a ratified one).

While fixing the sibling gate, found a second, real bug: `gate_checkpoint_rule_frozen`'s regex was
case-sensitive against a doc that capitalises sentence starts ("Endpoint is the headline"), so its
PASS branch was structurally unreachable — a permanently-stuck-OWNER gate regardless of real
ratification. Made the regex case-insensitive to fix that.

**That fix immediately produced a live false PASS**, caught by re-running the gate rather than
trusting the diff: the now-matching text sits under `EVAL-PROTOCOL.md`'s own "Current operational
defaults ... awaiting owner settlement" heading, so PASS reported was PASS not earned. This is
exactly the class of defect this project treats as the single most expensive kind (per
`test_production_gates.py`'s own file docstring, written after the scheduler-RAM false-pass
incident). Reverted the case-insensitive PASS branch entirely — this gate now always returns OWNER,
like `gate_seed_policy_frozen`, describing the documented default accurately without ever inferring
ratification from doc text alone.

Added `test_seed_policy_and_checkpoint_rule_gates_never_auto_pass_from_doc_text`, which pins both
gates at OWNER unconditionally. Proven non-vacuous: temporarily restored the false-PASS branch,
confirmed the test fails and names the exact gate, reverted, confirmed green again.

**Two lessons, not one.** First: a stale gate MESSAGE and a stale gate LOGIC BUG are different
defects needing different fixes — I initially treated them as the same thing. Second, and the one
worth generalizing: fixing an apparent bug in a detection regex can change WHICH inputs satisfy it,
and that is itself a behavior change requiring the same re-verification as any other — "the regex
was obviously broken" is not evidence that making it not-broken is safe. Re-ran the gate after the
fix, on the live document, before considering it done — which is what caught this in the same
message rather than a later one.

## #73 — my own A28 correction still overclaimed what a single same-seed pair supports

Full re-read of review 14, requested directly by the owner after asking whether any review points
had been silently skipped. §24 was already read and cross-referenced against A28 earlier tonight,
but only for its qualitative conclusion ("n=3 resolves only coarse effects") — not for its specific,
narrower objection: calling ~53%/~35% a "lower bound" or "floor" because "genuine seed-to-seed
variance cannot be smaller than backend-only noise" conflates two different claims. The DIRECTION of
that argument is structurally sound; the CV it starts from (17.4%) is a point estimate from ONE
same-seed pair, which carries real sampling uncertainty of its own — so the resulting number is not
"guaranteed," only "estimated under thin evidence, in a knowable direction." Fixed in
`FINDING-resolving-power-at-n3.md` and `EVAL-PROTOCOL.md` (the two places the word "floor"/"lower
bound" had been used this way); `DECISION-SHEET.md`'s A28 entry did not use this language and needed
no change.

Same lesson as #71 again: matching a review point to a tracked item, or even fixing the specific
thing it names, does not mean every claim adjacent to that item was checked. This is the third
review-14 point in one re-read pass that survived an earlier, less careful cross-reference.

## #74 — RAD/SODA's per-update metrics were thinner than the RL-ViGen five's for no algorithmic reason

Found 2026-09-05 auditing metrics richness across all twelve, prompted directly by the owner's
question of whether metrics are reported richly for all twelve at proper frequency — checked past
the four families already covered by the PART2-METRIC-INVENTORY work (idaac/ppg/ibac_sni/ctrl) into
the eight I had not re-verified tonight.

`runnable/dmc_gb/src/algorithms/sac.py` (shared by `rad` and `soda`) logs `train_critic/loss` and
`train_actor/loss` but computes — and never logs — `current_Q1`, `current_Q2`, `target_Q` in
`update_critic`, and `entropy`, `log_std`, `actor_Q` in `update_actor_and_alpha`. All six already
exist as local tensors at the point the existing `L.log(...)` calls sit; nothing needed computing
that wasn't already being computed for the loss itself. The RL-ViGen five's `drqv2.py` logs the
Q-value/entropy equivalents already (`critic_q1`, `critic_q2`, `critic_target_q`, `actor_logprob`,
`actor_ent`) — this was not a "some methods don't have this" case (the user's own stated framework
for real richness differences), it was dead computation with no logging call, the identical shape
to `action_diagnostics()` (#69) and PPG's unlogged `entropy` variable — a third instance of the
same class this session.

**Fixed**: added `train_critic/q1`, `train_critic/q2`, `train_critic/target_q`,
`train_actor/entropy`, `train_actor/log_std`, `train_actor/q` — pure additive `L.log(...)` calls on
tensors already in scope, no new computation, no control-flow change, nothing upstream of the
gradient touched. Verified the exact input type matches `Logger.log`'s handling
(`logger.py:105`: `if type(value) == torch.Tensor: value = value.item()`) — every added call passes
a `.mean()` result, the same shape as the pre-existing `critic_loss`/`actor_loss` calls.

**Honestly flagged, not glossed over**: `random_crop` (this same file's augmentation path, used by
both `rad` and `soda`) asserts `x.is_cuda`, so the real training loop cannot execute on this
CUDA-less Mac — this fix is verified by static/structural analysis (every referenced variable
provably in scope, the exact type-check path confirmed) rather than a live local run. Worth a cheap
smoke check on the next real `rad`/`soda` remote job rather than assumed correct from reading alone.

## #75 — independently re-derived C1 from raw code, converged exactly with prior work; one message-completeness gap found and fixed

Traced the Door truncation-bootstrap question from scratch (reading `RL-ViGen-upstream/wrappers/
robo_wrapper.py`'s `discount = 0.0` on every `done`, unconditionally) before knowing this project's
own prior finding existed. Converged on the exact file and line (`:42`) already cited by C1
("the largest comparability defect found", `docs/CONSTRUCTION.md#c1`) — a genuine independent
cross-validation of both the earlier finding and my own method.

**Checked before concluding anything was wrong**, twice: first worried C1's "OPEN" status might be
stale given `rlgen/protocol.py`'s `time_limit_handling` is already `"per-baseline"` — read the full
entry and found the false-certification half is explicitly marked "Done, 2026-08-19" further down,
which I had cut off on a first read. Not stale; I just hadn't read to the end. Second, worried C1
was invisible from `production_gates.py` (the tool this project treats as the primary "cannot go
stale" pre-launch check) — it is not invisible, `gate_estimands_frozen` already names the 3/9
split, just without noting that both the false-certification fix and the substantive "declare,
don't equalise" recommendation are already done, leaving only formal ratification.

**Fixed the one real gap**: enriched `gate_estimands_frozen`'s message to state both resolutions
explicitly, so a reader of `production_gates.py` alone (without also reading `CONSTRUCTION.md#c1`
in full) gets the accurate current state rather than an under-described "time-limit split exists"
line that reads more unresolved than it is.

**The lesson, stated once for the pattern**: two near-misses in one check, both from stopping a
read early rather than a wrong fact. Read the whole entry before concluding staleness, twice now
tonight (this one and A30's log_std correction) — worth remembering deliberately, not just noting.

## #76 — systematic search for more "fix lives only in rlgen" bugs: one found (already fixed), rest are false positives by design

The owner asked directly whether other bugs exist in the same shape as #59 (ALDA's UTD fix living
only in the retired `rlgen/` port, never reaching `runnable/alda`). Checked systematically rather
than by feel.

**Surface**: 37 test files import from `rlgen`. Narrowed to the 16 importing `rlgen.algos.*`
specifically (the retired per-algorithm reimplementations, as opposed to `rlgen.protocol`/`tags`,
which are live shared modules this project actively uses). All 16 have zero `runnable/` cross-
references — expected, not alarming: their naming (`_parity`, `_base_parity`, `_hermetic`) and
`test_reward_normalizer.py`'s own docstring confirm they test `rlgen/algos/*`'s fidelity to
published references, as this project's OWN, ABANDONED from-scratch reimplementation effort. That
is a different claim from "this verifies `runnable/`'s current behavior" — `runnable/*` are literal
clones of the real upstream repos, correct by construction for anything unpatched, not
reimplementations needing a hand-computed-closed-form check the way a from-scratch port does.

**The actually dangerous pattern, mechanized**: searched all of `rlgen/` for `FIXED 202`,
`CORRECTED 202`, `diverged`, `catastrophically wrong`, `was silently wrong` — the exact language a
deliberate cross-cutting fix would carry, matching #59's own comment style. Nine files hit. Checked
every one:

- `rlgen/algos/alda/config.py` (utd) — **#59, already fixed.**
- `rlgen/algos/idaac/config.py` (num_envs) — rlgen-internal dataclass/trainer consistency fix, `num_envs`
  is dead in rlgen's own trainer (hardcoded N=1); no `runnable/idaac` claim at all. Its `num_steps:
  2048` sibling value is genuinely useful prior art for T17 (the continuous-control design-point
  decision) but is already correctly tracked there, not a lost fix.
- `rlgen/algos/soda.py` (attribute-name typo, `soda_predictor` vs `predictor`) — a bug in rlgen's
  own PyTorch class hierarchy, unrelated to `runnable/dmc_gb`'s independently-written file.
- `rlgen/algos/ctrl/model.py` (Flax flatten/padding convention) — fixes rlgen's OWN from-scratch
  PyTorch reimplementation to match Flax's convention for a weight-transplant check;
  `runnable/ctrl` IS the Flax code, so it cannot have this bug by construction.
- `rlgen/trainer.py`, `rlgen/evaluate.py`, `rlgen/agents.py`, `rlgen/trainer_onpolicy.py`,
  `rlgen/algos/alda/metrics.py` — checked, none reference a value or mechanism with a `runnable/`
  counterpart that could be stale (mostly divergence-detection assertions and shared-harness fixes
  scoped to rlgen's own trainer loop).

**Conclusion**: #59 remains the only confirmed instance of this bug class, found by both systematic
search and targeted manual reading of every hit. Not exhaustively proven absent everywhere rlgen is
imported (37 files is a lot, and this checked the specific "deliberate fix" signature rather than
every line) — but the highest-risk subset (deliberate corrections, the exact shape that produced
#59) is now fully accounted for.

## #77 — the metric-inventory subagent found two major, verified gaps; one directly corrects a claim I made earlier tonight

Dispatched a Sonnet subagent to build a code-verified metric inventory across all twelve baselines
(the owner's suggestion, notes/METRIC-INVENTORY-VERDICT-2026-09-05.md, 494 lines). Verified its two
largest claims myself before trusting or reporting either, per this session's standing discipline.

**IDAAC: `agent.update()`'s own return tuple never logged.** `train.py:278-283` unpacks
`order_acc, order_loss, clf_loss, adv_loss, value_loss, action_loss, dist_entropy` from every
update across all three `--algo` variants; grepped the whole file and confirmed these seven names
appear NOWHERE else. IDAAC's two standard PPO losses and its own defining mechanism's diagnostics
(the order-classifier's accuracy and loss — literally what makes IDAAC "IDAAC") had zero visibility
for the entire run. A collapsed or inert auxiliary head would have produced a plausible-looking
curve with no signal anything was wrong. Fixed additively: each `--algo` branch now populates an
`_update_metrics` dict from values already computed for the gradient step, logged via the same
`logger.logkv` calls the file already uses elsewhere. Non-vacuous (proven by removing the logging
loop and confirming the new test fails, then restoring).

**ALDA: rich train-side metrics computed and unconditionally discarded — corrects my own claim
from earlier tonight.** I had confirmed `logging_info.setdefault(...).append(...)` calls for 14+
metrics and reported ALDA as "genuinely rich... even richer than dmc_gb's SAC." I saw the
computation and stopped there — I never checked whether the values reach a persistent sink.
`alda_trainer.py:629-639`: values are averaged, then `if self.use_wandb: wandb.log(...)`, then
**`self.logging_info.clear()` unconditionally, outside that if-block**. Production's actual
default is `use_wandb=False` (`runnable/alda/scripts/train.py:30`; `families.json` never overrides
it) and `alda_trainer.py` has no CSV/print/file-writing path of its own — confirmed by grepping the
whole file for any write call and finding none. So under the settings that actually run: every
train-side metric, including `train/episode_reward` itself, was computed and thrown away with zero
record, for the entire fleet. Fixed by writing the same dict to a local `train_metrics.jsonl`
(append-only, one line per log interval) whenever wandb is off, reusing the already-established
`self.exp_dir` attribute the same class already uses for checkpoints and videos. Non-vacuous
(proven the same way).

**The lesson, named directly because it is about my own work, not just the codebase's**: "I saw
the metric being computed" is not the same claim as "I saw the metric survive to a record", and I
conflated them once already tonight in a confident, unhedged statement to the owner. The fix for
the SYSTEM, not just the instance: from here, any future richness claim in this project should be
verified against the actual write path, not the computation, and the phrase "genuinely rich" should
carry the same evidentiary bar the project already holds every other claim to.

Full metric-inventory findings, including a same-name-different-quantity collision in `ibac_sni`
(its own `kl` vs this project's `approx_kl_k3`, printed near each other) and several
`PART2-METRIC-INVENTORY.md` corrections, are in `notes/METRIC-INVENTORY-VERDICT-2026-09-05.md` —
not yet independently re-verified by me line by line; the two above were the highest-stakes claims
and are now confirmed. The rest should be treated as a strong, code-grounded first pass pending the
same spot-verification these two received.

## #78 — tracking: subagent findings not yet independently verified (opened, not yet closed)

`notes/METRIC-INVENTORY-VERDICT-2026-09-05.md` (the dispatched subagent's report) named several
findings beyond the two verified and fixed in #77. Noting the remainder here explicitly so they are
not lost, per the owner's direct request, before attempting to verify them:

1. **`drq` architecture misclassification in `docs/PART2-METRIC-INVENTORY.md` Finding 6** — claimed:
   `drq`'s actor is actually SAC-family, not DrQv2-family, and the project's own P17 patch comment
   already knew this but it never propagated into the family table. NOT YET VERIFIED by me.
2. **`critic_loss` is allegedly 4 different formulas under one name across 8 of 12 baselines** —
   NOT YET VERIFIED. If true, this is a significant same-name-different-quantity case in the same
   class as the k2/k3 estimator mismatch PART2 already documents.
3. **A stale "`ctrl` is not wired" claim in PART2** — claimed it is now wired, conditionally. NOT
   YET VERIFIED against the current PART2 text or the current code.
4. **A PART2 claim about `clip_fraction`'s log-ratio formulation** that the subagent says does not
   survive reading `scripts/metrics.py` directly. NOT YET VERIFIED.

Subagent's own stated thin-evidence areas, also not yet independently checked: `ppg`'s
roller/eval accounting and `ctrl`'s `daac_ctrl` branch were its shallowest-covered areas; it never
executed any baseline, so every claim here is static-analysis-derived.

Verifying all four next, directly, in this same pass.

## #78 update — 2 of 4 verified and fixed; 2 remain, explicitly for post-compaction pickup

Status update on #78, written because context is about to auto-compact and this must survive that.

**DONE, verified directly against code (not trusted from the subagent), and fixed:**
1. `drq` architecture misclassification — CONFIRMED. `drq.py`'s `Actor.forward` builds its own
   `SquashedNormal`/`TanhTransform` (proper tanh-squashed density, numerically-stable Jacobian
   correction) — the SAC-family mechanism, not drqv2's `tanh(mu)` + `TruncatedNormal`. Fixed
   `docs/PART2-METRIC-INVENTORY.md` Finding 6: moved `drq` into the SAC row, noted it arrives
   independently (own code, not shared with rad/soda/alda).
2. `critic_loss` = 4 different formulas under 1 name — CONFIRMED, precisely, after my own first
   shallow check (surface MSE syntax only) wrongly found nothing. Read `svea.py:236-241` (folds in
   an augmented-view MSE before logging), `sgqn.py:169-172` (folds in a 0.9-weighted mask-
   consistency term), `drq.py:265-283` (dual-augmentation-averaged AND entropy-inclusive target),
   confirmed `curl` never overrides `update_critic` (identical to drqv2). Added as Finding 8 in
   `docs/PART2-METRIC-INVENTORY.md`, documented not resolved (each formula is that baseline's own
   authors' definition; pooling is the owner's call, matching the k2/k3 precedent).

**NOT YET DONE — pick these up first after compaction, in this order:**
3. **Stale "`ctrl` is not wired" claim in PART2** — the subagent's report
   (`notes/METRIC-INVENTORY-VERDICT-2026-09-05.md`) says PART2 has a claim that ctrl's C28
   diagnostics are unwired, and that this is now stale (ctrl is wired, conditionally). NOT checked
   against either the current PART2 text or the current `runnable/ctrl` code. Start by grepping
   PART2 for "ctrl" + "not wired"/"unwired", then verify against `runnable/ctrl/train_ppo.py`'s
   actual C28 emission state (recall: `docs/REGISTER.md`'s 2026-09-04 entry already describes ctrl
   C28 as validated end-to-end — cross-reference that before concluding PART2 is wrong).
4. **`clip_fraction`'s log-ratio formulation claim** — the subagent says a PART2 claim about how
   `clip_fraction` is computed does not survive reading `scripts/metrics.py` directly. NOT checked.
   Start by finding PART2's exact claim (likely in §6, near the k2/k3 discussion), then read
   `scripts/metrics.py`'s actual `clip_fraction`/`gaussian_boundary_fraction`-adjacent functions and
   compare formulas directly, the same way findings 1-8 above were each confirmed by reading code
   rather than trusting a description.

Both remaining items are bounded (one doc-claim-vs-code check each, same pattern as items 1-2
above); expect each to take a handful of targeted reads, not a large investigation.

## #79 — #78 item 3 verified and fixed: `ctrl`'s "not wired" claim was stale, with one real caveat found while checking it

Verified directly against `runnable/ctrl/algo.py` and `runnable/ctrl/train_ppo.py`, not trusted
from the subagent's report or from my own earlier read this session.

**CONFIRMED STALE, and fixed.** `docs/PART2-METRIC-INVENTORY.md`'s "`ctrl` is not wired" claim
(dated 2026-08-19) no longer matches the code. `algo.py:355-356` computes `clip_fraction` /
`approx_kl_k3` inside the jitted `loss_actor_and_critic`, threads them through its `has_aux`
return tuple (`:359`), `update_ppo` unpacks and accumulates them into `avg_metrics_dict`
(`:414`, `:426-427`), and `train_ppo.py:349-361` folds that dict into `renamed_dict` and reaches
a real `wandb.log(renamed_dict, step=FLAGS.num_envs * step)` call, which the offline shim
(`runnable/_shim/wandb.py`) persists to a JSONL sink — matching `docs/REGISTER.md`'s 2026-09-04
entry recording this as measured on a real job (`bt1ums2q8170s3cq5p9l`). Fixed the doc in place
(kept the original wrong text visible, appended the correction, matching this file's established
convention).

**One real narrowing found while verifying, and folded into the same fix rather than filed
separately**: this wiring lives ONLY in `loss_actor_and_critic` / `update_ppo` — the path taken
when `--algo` contains `"ppo"` (`ppo`, `ppo_ctrl`). `update_daac` (`algo.py:434+`, taken by
`daac` / `daac_ctrl`) has its own, separate loss functions and does not compute either
diagnostic — confirmed by reading its full body, not by absence of a grep hit. Production's
declared default is `ppo_ctrl` (`train_ppo.py:96`, `runnable/_launch/ctrl.sh`), so this does not
block anything currently planned, but a future `daac_ctrl` run would silently lack these two
columns. Documented as an explicit caveat in PART2 rather than left implicit — this is exactly
the class of thing C1's "declare, don't imply" standard is about, applied to a smaller case.

**Added `TestCtrlPpoBranchReachesWandbLog`** to `tests/test_c28_emissions.py` (6 tests): the
jitted loss computes both values, both leave it through the aux tuple, `update_ppo` accumulates
both, `update_daac` does NOT have them (pins the caveat so it cannot silently go stale the other
direction — if someone later adds these to `update_daac`, this test fails and forces the PART2
caveat to be removed too), the ppo-branch `metric_dict` reaches an actual `wandb.log` call
(not just a dict), and the production default `--algo` value takes the wired branch.

**Non-vacuity proved for the two assertions that were newly written (not restating an existing
pattern)**, each by injecting a targeted break, confirming the specific test fails with the
correct named message, then restoring from a backup and re-running the full file to confirm a
clean 23/23:
- Injected a fake `clip_fraction = 0` into `update_daac`'s body → `test_update_daac_does_not_have_the_same_diagnostics`
  failed with exactly the expected message. Restored.
- Removed the ppo-branch's `wandb.log(...)` call (targeted by slicing to the correct occurrence —
  the string is not unique, `update_cluster`'s branch has an identical call at a different line,
  and a first attempt using a bare count-based assert correctly refused to run against the wrong
  target rather than silently mutating the cluster branch instead) →
  `test_ppo_branch_metric_dict_reaches_a_real_wandb_log_call` failed. Restored.

This closes #78 item 3. Item 4 (`clip_fraction`'s log-ratio formulation claim vs `scripts/metrics.py`)
remains, next.

## #80 — #78 item 4 verified and fixed: `clip_fraction`'s "log-ratio for precision" claim was a real overclaim, and inverted for two of four baselines

This closes CORRECTIONS #78's tracking list. Verified against all four LIVE on-policy call sites
(`ppg`, `idaac`, `ibac_sni`, `ctrl`), not against `scripts/metrics.py` alone — which is where the
subagent's report said the claim breaks down, and it does.

**The claim** (`docs/PART2-METRIC-INVENTORY.md`, near the k2/k3 discussion): "`ppg` thresholds
`|ratio - 1| > clip_param` on the ratio, ours takes the log-ratio for precision at the extremes."

**Checked and found wrong in two independent ways:**
1. `scripts/metrics.py::clip_fraction(log_ratio, clip_eps)` does take a log-ratio argument, but
   internally does exactly one `exp()` call before comparing — mathematically and numerically
   identical to comparing an already-exponentiated ratio directly. No precision is gained; the
   "for precision at the extremes" framing describes a non-existent benefit of that function's
   signature choice.
2. More importantly, **none of the four live implementations call `scripts/metrics.py` at all**,
   and none compute clip_fraction from a log-ratio — all four (`ppg` ppo.py:146, `idaac`
   idaac.py:136, `ibac_sni` ppo.py:132-133, `ctrl` algo.py:355) compare the already-exponentiated
   `ratio`/`diag_ratio` directly. The claim did not describe what actually runs.

**A related, smaller asymmetry found while checking this, and folded into the same fix**: for
`approx_kl_k3` specifically, `ppg` and `ctrl` DO keep a log-ratio as the primary quantity
(`ppg`'s `logratio` is computed first, `ratio = exp(logratio)`; `ctrl`'s `log_ratio` is factored
out before `ratio = jnp.exp(log_ratio)`, per its own code comment) — but `idaac` and `ibac_sni` do
it the OPPOSITE way, holding `ratio` and deriving `torch.log(ratio)` FROM it
(`idaac.py:137`, `ppo.py:135`). This is the inverse of the retracted claim's direction, is a
round-trip through `exp`/`log` rather than carrying the original log-difference through, and is
not a correctness bug (the round-trip is close to identity for the well-conditioned ratios PPO
actually produces) — but it was previously undocumented and is now stated accurately.

**Fixed**: `docs/PART2-METRIC-INVENTORY.md`'s claim corrected in place (original text kept
visible, correction appended, per this file's established convention), with per-baseline
file:line evidence for all four.

**Added `TestClipFractionIsRatioBasedInAllFourLiveImplementations`** to `tests/test_c28_emissions.py`
(6 tests) pinning: all four `clip_fraction` sites use `ratio`/`diag_ratio` directly (not a
log-ratio), and the two `approx_kl_k3` sites (idaac, ibac_sni) that derive `log(ratio)` FROM
ratio rather than carrying a primary log-ratio through — so if any of these six facts changes,
the doc's correction goes stale loudly instead of silently. Also fixed this same test file's own
stale module docstring, found while editing it: it claimed C28 diagnostics were "wired --
currently `ibac_sni` only," despite the file already containing passing tests for `ppg`, `idaac`,
and `ctrl` — the same doc-vs-code drift class this whole session has been hunting, found in the
file whose entire job is to prevent it. All 30 tests in the file pass; `test_docs_integrity.py`
passes.

**This closes #78 in full — all 4 tracked subagent findings are now independently verified
against live code and fixed (not just matched to a description).** Of the subagent's own two
stated thin-coverage areas (ppg's roller/eval accounting, ctrl's daac_ctrl branch), the daac_ctrl
gap was directly surfaced and documented as part of #79's fix; ppg's roller/eval accounting was
not separately probed this pass and remains untouched — noted here rather than silently dropped.

## Housekeeping — clone-provenance patches resynced after the idaac/alda fixes

`scripts/refresh_clone_patches.py --check` caught `alda` and `idaac` as STALE after this
session's `runnable/idaac/train.py` and `runnable/alda/trainers/alda_trainer.py` edits (both
directly edit clone files that `runnable/_patches/*.patch` snapshots against `ext/`; any direct
edit to a cloned file makes its snapshot stale by construction). Regenerated both via
`scripts/refresh_clone_patches.py` (no `--check`); re-ran `--check` to confirm all six read
`current`. This is what caused background suite run `bvnlm7nah`'s two
`test_clone_patch_snapshots.py` failures — expected, mechanical fallout from editing a clone file
directly, not a new defect. The suite's third failure in that run
(`test_nd_ln_style_train.py::test_end_to_end_on_the_synthetic_backend_produces_a_real_episodes_csv`,
`RuntimeError: linalg_qr: MPS kernel failed with error code 0`) is unrelated to any change this
session made — re-ran in isolation and it passed cleanly, consistent with a transient MPS kernel
flake in `torch.nn.init.orthogonal_`, not a real regression. `nd_ln` is provenance-only scope
here, not touched by this session's work.

## #81 — real gap found and fixed: `scripts/results_table.py` had no guard for C1's 9-vs-3 split

Found while answering the owner's direct challenge on whether C1 is "actually good" or left as
formalism (full reasoning in `notes/FINDING-c1-does-the-asymmetry-cancel.md`). Checking whether
the standing DEFAULT ("declare it beside every result... never rank across it",
`CONSTRUCTION.md#c1`) is actually implemented, not just written down, surfaced a real, independent
bug: `results_table.py` carries explicit guards for several OTHER comparability defects (C17's
floor, C47/C55's denominator rule, C62's shaping ceiling, the seed-only resolution-floor column)
but had zero mechanism to detect or flag a table pooling rows across C1's time-limit-handling
split — despite C1 being rated the largest comparability defect in the project.

Not yet live-triggering: today's only populated `CELLS` entries (`drqv2`, `svea`, `drq`) are all
"terminal", so no mixing has happened. But `rad`/`soda`/`alda` (all three "bootstrap") are
explicitly listed in this same file's `ABSENT` dict as "not yet run at the 105k protocol" — i.e.
anticipated — so the first cell added for any of them would have silently mixed groups in the
`scene ret`/`regime ret`/`SR tr>ev` columns with zero warning.

**Fixed**: added `_time_limit_handling()` (reads `TIME_LIMIT_HANDLING` from `rlgen/protocol.py`'s
source text, same mechanism `audit_comparability_seam.py::truncation()` already uses), tagged each
row with `tl=TIME_LIMIT_HANDLING.get(name, "?")`, and added a check in `main()`: if the printed
rows ever span more than one `tl` group, print a named `WARNING (C1)` listing which baselines are
in which group, and fail `--strict`.

**Tests added** to `tests/test_results_table.py`: one synthesizes a two-group table via
monkeypatched `row`/`CELLS` (no real grids needed) and confirms the warning fires with both names
and `--strict` exits 1; one confirms a uniform-group table does not spuriously warn (regression
pin against today's real, uniform CELLS). Both pass; existing `@needs_results`-gated tests still
correctly skip in this tree.

**Non-vacuity proved**: broke the ppo-branch's `wandb.log` call and the `update_daac` isolation
independently in the CTRL work above (#79); for this fix specifically, injecting a fake
`clip_fraction` was the CTRL check — for THIS entry the equivalent break-test lives in #82 below,
done once for both table scripts together since they share the identical mechanism.

## #82 — same gap, more importantly, in `scripts/preprod_table.py` (the actual twelve-baseline production table)

`results_table.py` is explicitly labeled "LEGACY EXPLORATORY... not a production headline."
`preprod_table.py` is not — its own docstring says R3 (metrics on the same axes) is what it exists
to serve, and it already declares `ESTIMATOR` (sampled vs mode return) and `STACK` (C2's frame-
stack split) as columns printed beside every row, with a footer paragraph for each, "because a
bare column invites a comparison the data does not support." C1 was missing from this table
entirely too — no column, no footer paragraph — despite outranking both `ESTIMATOR` and `STACK` in
the project's own severity rating.

**Fixed**, matching this file's own established idiom (unconditional axis-declaration, not a
conditional warning like #81's fix in `results_table.py` — chosen because every OTHER axis
paragraph in this file is printed unconditionally, e.g. the ctrl-native-vs-offline paragraph
prints regardless of whether `ctrl` is even in the current job set):
- Added `TIME_LIMIT` (same source-text-read mechanism as #81).
- Added a `timelimit` column (header + separator + every row), between `stack` and `render`.
- Added an unconditional footer paragraph declaring the split, its severity rating, and the
  "rows may not be ranked across this column" rule — with an explicit named callout appended
  ("This table currently mixes both: ...") only when the actual printed rows span more than one
  group.

**New test file** `tests/test_preprod_table.py` (6 tests, `cells_of` monkeypatched so no real job
archives are needed): the `TIME_LIMIT` dict is checked against `rlgen/protocol.py`'s own source via
independent `exec()`, not imported and trusted; covers all 12 baselines with exactly the 2 expected
values and the exact `{rad, soda, alda}` bootstrap set; header/separator column counts match (the
concrete failure mode of adding a column and forgetting the separator, which produces a malformed
markdown table pytest would otherwise never notice); the uniform case does not spuriously claim
mixing; the mixed case names both groups explicitly; each row prints its own correct value.

**Non-vacuity proved**: temporarily replaced the `tl_present` computation with a hardcoded
single-group list inside a real two-group scenario — `test_a_mixed_time_limit_group_is_named_explicitly`
failed with exactly the expected assertion error. Restored from a backup copy; re-ran the full
6-test file to confirm a clean pass afterward.

Both #81 and #82 are additive-only: no existing row's printed number changed, no sort order
changed, no existing column removed. `test_docs_integrity.py` and the full suite both still pass.

## #83 — closed a second dormant drift risk found while fixing #82: `preprod_table.py`'s `STACK` was a hand-duplicated literal

While adding `TIME_LIMIT` to `preprod_table.py` (#82), checked whether the file's existing
`STACK` dict (C2's frame-stack axis, already declared as a column) had the same property that made
`TIME_LIMIT_HANDLING`'s pre-fix false-certification possible: a hand-typed per-baseline literal
that can silently drift from its source. It did — `STACK` was a literal, not read from
`rlgen/protocol.py`'s `OBSERVATION_GEOMETRY` (the actual source for both render size and frame
stack). Values matched exactly at the time of checking (verified: `{drqv2:3, svea:3, drq:3,
sgqn:3, curl:3, rad:3, soda:3, alda:3, ppg:1, idaac:1, ibac_sni:1, ctrl:1}` on both sides) — no
live bug, but a dormant one, in exactly the shape C1's own false-certification half already
demonstrated is real.

**Fixed**: `STACK` now derives from `OBSERVATION_GEOMETRY` via the same source-text-read
mechanism as `TIME_LIMIT`, rather than duplicating it. Added
`test_stack_dict_matches_rlgen_protocol_exactly` to `tests/test_preprod_table.py`, independently
re-deriving the expected dict via `exec()` on `protocol.py`'s own source (not importing and
trusting `pt.STACK`, which is the thing under test). Full local suite green except the one known
MPS `linalg_qr` flake in `test_nd_ln_style_train.py` (unrelated, confirmed flaky earlier this
session).

## #84 — third instance of the same staleness class, in `scripts/audit_eval_state.py`'s ppg entry

Found while cross-checking `preprod_table.py`'s `ESTIMATOR` dict (which marks `ppg: "SAMPLE"`)
against its own stated source, `scripts/audit_eval_state.py`. That file's `ppg` entry still read
`"policy_mode": "not chosen anywhere -- no evaluation code exists to read it from"` and
`"reusable": "ADAPT -- there is no eval loop..."` — describing a state from before
`runnable/_launch/ppg_eval.py` was written. Verified against the live file: `ppg_eval.py` exists,
builds its own venv via `get_venv`, reuses `Roller`/`VecMonitor2` (the authors' own rollout/
episode accounting), and calls `model.act` (line 71) — which samples, per the file's own docstring
("It samples; it does not take the mode... there is no deterministic-action path in this repo to
call instead"). So `ESTIMATOR`'s `"SAMPLE"` was already correct; only this audit's *description*
had drifted — no comparability decision was ever wrong, but the documented evidence for it was.

**Fixed**: updated the `ppg` entry's `policy_mode` and `reusable` fields to describe the current
`ppg_eval.py`-based evaluator, with a `[found stale and corrected 2026-09-06]` note matching this
file's own established convention for prior corrections on the same dict (idaac `[resolved
2026-09-03]`, ibac_sni `[resolved 2026-09-03]`, ctrl `[corrected 2026-09-04]`) — ppg's was simply
the one nobody had gone back to update.

**One mechanical bug introduced and self-caught while writing the fix**: `anchor`/`expect` are
checked LIVE by `tests/test_record_conventions.py::test_eval_state_audit_anchors_still_hold`,
which does `path, line = entry["anchor"].rsplit(":", 1)` — a bare `"anchor": "runnable/_launch/
ppg_eval.py"` with no `:line` suffix would raise `ValueError: not enough values to unpack` the
moment that test ran, not silently pass. Caught by running the test immediately rather than
trusting the edit; fixed to `"runnable/_launch/ppg_eval.py:71"` / `"expect": "act_fn=model.act"`,
anchored to the actual call site (`Roller(venv=venv, act_fn=model.act, ...)`), not the docstring
prose that merely mentions `PpoModel.act` by name. Verified: the anchor test passes, and running
the script itself now prints ppg's corrected, accurate one-line summary.

This is the third instance this session of "a doc/audit's prose description went stale after the
code it describes changed, and nothing forced it to be revisited" — after PART2's `ctrl`-not-wired
claim (#79) and its `clip_fraction` log-ratio claim (#80). All three were found by cross-checking a
document against the artifact it claims to describe, not by reading the document in isolation.

**A second, dependent staleness surfaced immediately by running the tests rather than trusting
the diff**: `test_the_two_baselines_needing_evaluator_work_are_named` asserted
`needs_work == {"ppg", "ctrl"}` — genuinely correct before this fix, genuinely wrong after, since
`ppg`'s `reusable` field no longer starts with `"ADAPT"`. Renamed to
`test_the_one_baseline_still_needing_evaluator_work_is_named`, updated to expect `{"ctrl"}` only,
with the docstring explaining why `ppg` dropped out. Both tests green now.

## #85 — a genuine test-precision bug, found while triaging collateral failures from Codex's active work

While verifying the full suite (in response to a direct challenge on whether earlier verification
claims were actually grounded), found 3 new failures. Two (`test_curve_eval_exists_is_gated_and_runs_after_retention`,
`test_finiteness_is_checked_before_paid_offline_evaluation`) read `datasphere/native/run_probe.sh`
directly and are Codex's own active-boundary territory — not touched, flagged to it via the
mailbox instead.

The third, `test_every_record_context_carries_the_scope`, traced fully: it asserted
`GRID.count('context = {"cell"') == GRID.count('"eval_scope": a.eval_scope')` (4 vs 5). All four
real record-context sites (`eval_grid.py` lines 1231/1245/1265/1291) already carry
`"eval_scope": a.eval_scope` on the very next line — verified directly, not inferred. The 5th
occurrence, at line 1166, is inside `canonical_evaluation_scope({...})`'s own input dict (Codex's
earlier evaluator-identity scope-resolution addition) and is not a record context at all. The
test's blind count-equality broke as a side effect of that unrelated, correct addition — the
underlying invariant it exists to protect was never actually violated.

**Fixed**: replaced the count comparison with a per-site check — find each of the 4
`context = {"cell"` occurrences by position, and assert `"eval_scope": a.eval_scope` appears
within 400 characters after each one. This can no longer be confounded by an unrelated occurrence
of the same substring elsewhere in the file, in either direction.

**Non-vacuity proved**: removed `"eval_scope": a.eval_scope` from the first of the four context
blocks only, confirmed the test fails with the correct, specific offset-identifying message,
restored from a backup, re-ran the full 7-test file clean.

Proposed this exact fix to Codex via the mailbox first (paths, failure, acceptance command, why no
overlap with its active `run_probe.sh`/`normalize_curves.py`/`summarize_result.py`/`contract.py`
boundary) before executing, per its explicit request for a disjoint next write boundary.

## #86 — A18 (floor-adjusted retention) was adopted, documented, and never implemented; now is

Found while doing a broader sweep for real ownership gaps rather than another one-off patch (the
owner directly challenged whether earlier "done and verified" claims were actually checked, and
separately whether scoped fixes add up to actual ownership). Checked whether `EVAL-PROTOCOL.md:23`'s
promise of "retention AND floor-adjusted retention" as reported metrics was actually kept.

It wasn't. `DECISION-SHEET.md`'s A18 (external review credit: Gemini's A4, the one useful
contribution from that report per this project's own triage) specifies the exact formula —
`retention = (R_OOD - R_floor) / (R_train - R_floor)` — and its own text said "Implemented in the
protocol notes, not yet in an emitter (no retention table is generated yet)." That caveat is
itself now stale: `results_table.py` generates a retention table (`regime`, `scene_ret`) and has
since before this session started, but nobody had gone back to add the floor-adjusted variant A18
called for. Confirmed via direct code read: `regime = st.mean(num) / st.mean(den)` and
`scene_ret = st.mean(held) / mtr[0]` are both plain ratios, no floor subtraction anywhere in the
file. `preprod_table.py` checked too and needed no change — it reports one regime's raw return per
row and has never formed a train-vs-eval ratio at all, so A18 doesn't apply to it.

**Fixed**: added `scene_ret_floor_adj` and `regime_floor_adj` to `row()`'s output in
`results_table.py`, computed per A18's formula, gated to REFUSE (print `None`/`"REFUSED"`, never a
misleading number) wherever the floor-adjusted denominator would not be positive — `scene_ret`'s
guard is explicit (`mtr[0] > floor_mean`); `regime`'s reuses the fact that `usable`/`common`
already requires every pooled scene's train mean to clear `floor_mean`, so the pooled mean does
too. Printed in a new "FLOOR-ADJUSTED RETENTION" section (plain-text and `--markdown` output both),
explicitly stated as reported *beside*, not replacing, plain retention, matching
`EVAL-PROTOCOL.md`'s own metrics row rather than picking one.

**Tests added**, verifying the formula itself rather than just that the code runs:
`test_floor_adjusted_retention_matches_the_a18_formula_by_hand` builds a synthetic grid with
scene0, held-out scenes, and eval-easy all deliberately different values, hand-computes the
expected floor-adjusted numbers, and checks `row()`'s actual output against them (a bug that
swapped num/den or forgot the floor on one side would still pass against a uniform-value fixture —
this one wouldn't). `test_floor_adjusted_scene_retention_refuses_at_or_below_the_floor` confirms
the refusal guard fires for both quantities when every scene sits at the floor. Non-vacuity proven
by injecting a "forgot to subtract the floor" bug into the implementation and confirming the first
test fails with the exact expected-vs-obtained mismatch, then restoring.

Updated `DECISION-SHEET.md`'s A18 entry to reflect this (original stale text kept visible per this
file's convention, correction appended above it) and noted precisely what remains a data-currency
question (is the floor grid on disk current) rather than a code gap.

## #87 — `results_table.py` never joined the "ONE home for the floor" fix (Q12); flagged, not fixed

Found continuing the ownership sweep (checking whether `floor_mean`, which #86's A18 fix now
leans on heavily, has the same "same fact computed twice" risk this project has already been
burned by once). It does.

**Confirmed, structurally, in this tree**: `scripts/rlvigen_reference.py` establishes
`DOOR_RANDOM_FLOOR` as the single canonical import for the Door random-policy floor, explicitly
because "on 2026-09-05 the number 1.82 was living in five places at once... Import this; do not
copy the literal" (Codex's Q12). `scripts/preprod_table.py` follows this. `scripts/results_table.py`
does **not** — it never imports `DOOR_RANDOM_FLOOR` anywhere; instead it loads its own
`random-floor__train.json` grid (`FLOOR = "random-floor"`, `load(FLOOR, "train")`) and computes
`floor_mean` locally. That grid is produced by an entirely separate pipeline
(`scripts/run_regime_retention.sh` → `scripts/eval_across_scenes.py --random-policy`), not by
`scripts/probe_floor.py` (which is what `DOOR_RANDOM_FLOOR`'s 1.842 comes from). Two independent
measurement pipelines for the same quantity, with no cross-check between them and no comment in
`results_table.py` acknowledging the divergence from the established single-home policy.

**Suggestive but NOT confirmed as a current live discrepancy**: the canonical tree
(`ccm-intro/projects/many-gens-rl-vigen`, ~2 weeks stale relative to this workspace, a separate
git history) happens to have an actual `random-floor__train.json` on disk, measured at n=200,
mean≈1.8102 — close to but distinct from the CURRENT 1.842 `DOOR_RANDOM_FLOOR`, and closer to
C55's own-cited SUPERSEDED 1.818. This tree has no such file at all (confirmed earlier:
`results/regime-retention-c69/` doesn't exist here), so I cannot confirm this number reflects
what `results_table.py` would actually load today — it might be regenerated fresh, or might not
be. Reporting the observation precisely rather than either dropping it or overclaiming it as a
proven live bug: it's evidence the risk is real, not proof the risk has already bitten.

**Not fixed.** Whether `results_table.py` should import `DOOR_RANDOM_FLOOR` directly (unifying
with `preprod_table.py`) or has a real reason to measure its own floor locally (e.g., tying the
control to the exact same evaluator harness as its own cells) is a design question this table's
own extensive docstring never addresses either way — silence, not a stated choice. Per this
project's own "declare, don't silently equalize or silently diverge" discipline (C1's own
precedent), this needs a decision and a comment, not a unilateral rewrite of a competence-gate
input from me. Flagging in `notes/DECISION-SHEET.md` rather than picking a side.

## #87 amendment — the same finding also covers `regime_retention_report.py`

Completing the sweep rather than stopping at the first file found: `scripts/regime_retention_report.py`
reads the identical `random-floor__{mode}.json` grids from the identical directories
(`results/regime-retention[-c69]/`) that `results_table.py` reads — confirmed by comparing
`RESULTS_C69`/`RESULTS_PRE` path constants directly. So there are exactly two measurement
mechanisms for the Door random-policy floor, not three: (A) the shared local-grid mechanism
(`run_regime_retention.sh` → `eval_across_scenes.py --random-policy`), consumed by both
`results_table.py` and `regime_retention_report.py`; (B) the canonical `DOOR_RANDOM_FLOOR`
constant (from `probe_floor.py`), consumed by `preprod_table.py` and `audit_shared_evaluator.py`.
A31 in `notes/DECISION-SHEET.md` updated to name both (A)-mechanism consumers, not just one.

## #88 — real, first-ever-exercised bug in Codex's evaluator-identity binding: macOS AppleDouble sidecars leaked into runtime-member hashes

Found the hard way: submitted the C95 renderer-parity probe (job `bt18a8fjl3qrp5jv50g6`, drqv2-s2
@ 100k on g1.1) and it failed at `datasphere/native/contract.py verify-evaluator-binding` with
`evaluator runtime member hash mismatch for rlvigen` — no detail beyond the family name. This is
production_gates.py's own "0/7 evaluator families validated on their CURRENT family closures"
OWNER item made concrete: the mechanism had never actually been exercised end to end before this
job, on any family.

**Root-caused rather than guessed at.** Exhausted every local hypothesis first — a fresh local
build's manifest matched a fresh recomputation exactly (0 diffs); extracting the pinned RL-ViGen
archive fresh and applying the current 28 patches in full isolation reproduced the baked-in hash
exactly (0 diffs); running the same editable `pip install -e RL-ViGen-upstream/envs/robosuiteVGB`
locally changed none of the hashed files. Everything reproducible on this machine matched. Rather
than keep guessing, added temporary diagnostic output to `verify_bindings` (print the exact
differing/extra keys instead of just raising) and resubmitted the identical job on `gt4i.1`
instead of `g1.1` (the failure happens before any GPU-specific step, so the cheaper tier answers
the same question) — job `bt1r24168a2h0dhdgplh`.

**The diagnostic output was unambiguous**: `only_in_actual(payload)=[]`, `differing_keys=[]`,
`only_in_expected(recomputed)` listed ~30 files, every one `._`-prefixed
(`._curl.py`, `.___init__.py`, `secant/envs/robosuite/._adapter.py`, etc.) — macOS AppleDouble
sidecar files (extended-attribute/resource-fork data). macOS's own `tar` silently folds these into
extended attributes on extraction, so they are invisible on this (and presumably any macOS)
development machine; GNU tar on the remote Linux container has no such concept and extracts them
as literal, ordinary files. `_runtime_tree_members`'s filter only checked file suffix
(`.py`/`.yaml`/`.yml`/`.xml`), and `._curl.py`'s suffix is still `.py`, so every AppleDouble
sidecar silently passed as if it were a real runtime member — inflating the REMOTE recomputation's
member set relative to what was baked into the payload on this (or any) macOS machine. This bug
could not have been caught by any test run so far, because every prior run of this code — local
development, unit tests, and the one prior evaluator-identity CI-style check — happened on macOS,
where the extra files never exist.

**Fixed**: `_runtime_tree_members` now also excludes any file whose basename starts with `._`.
Verified the fix directly: re-injected simulated AppleDouble files (binary content, `._curl.py`
and `.___init__.py`) into the isolated fresh-archive-plus-patches reconstruction and confirmed
they no longer appear in the recomputed member set (count stays at the correct 45, matching the
baked-in manifest exactly once the file itself was updated in both places).

**Added `test_runtime_tree_members_excludes_macos_appledouble_sidecar_files`** to
`tests/test_evaluator_identity_binding.py`, using real temp files (not a mock) with genuine binary
sidecar-like content. Non-vacuity proven: reverted the fix, confirmed the test fails with the
exact leaked-file names named in the assertion message, restored, re-ran clean.

**Cost of finding this**: two small jobs, ~9 minutes on g1.1 (~$0.41, reconciled) and a few
minutes on gt4i.1 for the diagnostic — real money, but this is exactly the kind of defect that
would otherwise have silently blocked every evaluator-family validation this project needs before
it can leave OWNER status on "shared evaluator validated," discovered locally-free investigation
having been exhausted first.

## #89 — `MIN_DENOM_SUCCESS = 0.25` was a second home for one number, in `results_table.py` beside `regime_retention_report.py`

Found during the surfaces-review sweep the owner asked for ("having an index of these"), the same
sweep that already found and centralized the `g1.1`→`gt4i.1` admission-tier mapping. Grepping for
suspicious repeated literals across `scripts/*.py` turned up `MIN_DENOM_SUCCESS = 0.25` defined
independently in both `scripts/results_table.py:97` and `scripts/regime_retention_report.py:67` —
the exact "two homes for one number" pattern `rlvigen_reference.py`'s own docstring names for Q12
(`DOOR_RANDOM_FLOOR`, five places, 2026-09-05) and CORRECTIONS #82/#83 (`STACK`,
`TIME_LIMIT_HANDLING`) already caught elsewhere. Each file's own test
(`test_results_table.py::…`, `test_regime_retention_report.py`) asserted its own copy equals 0.25
independently, so neither test could have caught the two drifting apart.

This one is not hypothetical: DECISION-SHEET.md A23 leaves "is 0.25 the right threshold, does OOD
need its own" explicitly open, so this constant is a live candidate for a future edit — exactly
the condition under which one-of-two-copies silently going stale actually happens.

**Fixed**: `regime_retention_report.py:67` carries the fuller derivation (the adversarial-re-check
story: a policy scoring 1/20 on every scene, never more, passed the old exactly-zero guard and
pooled into a 0.947 retention that read as robustness), so it is the authoritative home.
`results_table.py` now does `from scripts.regime_retention_report import MIN_DENOM_SUCCESS`
instead of redefining the literal.

**Non-vacuity proven**: temporarily changed `regime_retention_report.py`'s value to 0.31 and
confirmed `results_table.MIN_DENOM_SUCCESS` followed it to 0.31 (proving the import is live, not a
coincidental match), then restored 0.25 and reran `tests/test_results_table.py
tests/test_regime_retention_report.py` clean.

`CONTAMINATION_RATIO` (also in `regime_retention_report.py`) was checked at the same time and has
no duplicate elsewhere — left as is.

## #90 — `production_gates.py::gate_external_anchor`'s message was stale against DECISION-SHEET.md's own A9 revision

Found while grounding a reasoned lean for A33 (production scope) prompted a re-read of the other
still-OWNER gates for the same staleness class already caught in #84 (`audit_eval_state.py`'s ppg
entry). `gate_external_anchor` still said "nothing has reproduced a published RL-ViGen number...
Establishing the anchor BEFORE the fleet is the ordering all three reviews recommend" — the
ORIGINAL framing, from before DECISION-SHEET.md's "Revision, 2026-09-05 — A9 becomes free" section
closed exactly this question: read RL-ViGen's own published table (units certified as RETURNS,
C33/Q2, `notes/rlvigen-published-door-anchor.md`), found drqv2 Door eval-easy 3.6 across seeds
{3,7,4,3,1} (range 1-7), and redefined the anchor as a **free acceptance test** ("the fleet's own
drqv2 seeds should fall inside that published range") rather than a dedicated reproduction cell —
satisfying the reviews' ordering-before-the-fleet requirement without costing a job.

The live gate's message never caught up: it still read like the anchor was entirely unaddressed,
when the actual remaining work is only (a) ratifying that this counts as satisfying the reviews'
intent and (b) running the check once production drqv2 seeds exist — which is what the OWNER
status should describe.

**Fixed**: rewrote `gate_external_anchor`'s message to state the free-acceptance-test criterion
directly, cite its source, and narrow what's actually still open. Verified via
`tests/ -k "production_gates or gates"` (clean) and running `scripts/production_gates.py` directly
to confirm the printed message reads correctly.

## #91 — real, first-ever-exercised bug in this project's own 2026-09-05 ALDA train-metrics patch: a residual Tensor crashes `json.dumps`

Found via job `bt10p8oorc64302metk8`, the fresh functional-endpoint re-validation of `alda`
(submitted as part of closing "shared evaluator validated"). Training crashed at step 1500/10000:

    TypeError: Object of type Tensor is not JSON serializable

Traced to `runnable/alda/trainers/alda_trainer.py`'s `train()` loop. The averaging block just
above the crash site (**upstream, unmodified**):

```python
for k, v in self.logging_info.items():
    if isinstance(v, torch.Tensor):
        v = v.item()
    self.logging_info[k] = sum(v) / len(v)
```

only unwraps a bare-Tensor `v` before summing. `self.logging_info[k]` is actually built by
`logging_info.setdefault(key, []).append(value)` across many steps, so `v` here is a **list**;
`isinstance(v, torch.Tensor)` is always `False` for it. Several of ALDA's own metrics (critic
loss, alpha, gradient norms, VQ/commitment/reconstruction losses) append the raw tensor rather
than `.item()`-converting it first, so `sum(list_of_tensors) / len(list_of_tensors)` is Tensor
arithmetic and leaves a 0-d `torch.Tensor` sitting in `self.logging_info[k]` after "averaging."
`wandb.log()` tolerates a Tensor value silently; the plain `json.dumps()` this project's own
2026-09-05 patch added (`train_metrics.jsonl` persistence, so `use_wandb=False` production runs
keep a record instead of discarding every metric — see the patch's own comment in
`runnable/alda/trainers/alda_trainer.py:640-650`) does not. The bug has been latent in that patch
since the day it landed; nothing had exercised the exact log-interval/metric-value combination
that trips it until this job did.

The existing test, `tests/test_alda_train_metrics_persist_without_wandb.py`, could not have caught
this: every assertion in it was a source-text substring check (`"json.dumps(self.logging_info)"
in block`), never an execution of the code against data shaped like what the real training loop
produces. Same failure class as CORRECTIONS #85/#38's stale/vacuous tests, in a different file.

**Fixed**, scoped to the patch's own addition rather than upstream's averaging loop (declared
deviations from upstream stay minimal and attributable — the averaging loop's partial Tensor
handling is intentional upstream behavior, imperfect but not ours to silently extend):

```python
def _jsonable(value):
    if isinstance(value, torch.Tensor):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
_f.write(json.dumps(self.logging_info, default=_jsonable) + "\n")
```

Added two real, execution-based tests to replace the source-text-only ones:
`test_tensor_valued_metrics_serialize_without_crashing` (extracts the live `_jsonable` function's
actual source and execs it, so the test tracks the shipped code rather than a hand-copied
reimplementation that could drift) and `test_a_genuinely_unserializable_value_still_raises` (the
handler must not swallow every failure, only Tensors). **Non-vacuity proven**: reverted the
`default=` argument, confirmed `test_logging_info_is_persisted_when_wandb_is_off` fails with the
exact expected message, restored, reran clean.

Rebuilt `payload-v143-alda.tgz` and resubmitted as `cfg-alda-revalidate-v143.yaml` (job
`bt18gmov8nbfkkd117s6`).

## #92 — three tests broke against earlier-this-session's own legitimate changes, and only a full-suite run caught it

Found running `pytest tests/ -q` proactively before committing (the discipline this project keeps
re-learning: CORRECTIONS #88's timeout bug, the "is the structure ok?" full-gate-suite check, and
now this — a scoped test run after a targeted edit is not the same as the full suite, and this
session had been running scoped subsets after each individual fix). Three real regressions, all
caused by earlier-this-session commits that were each individually verified with a narrower test
run than the full suite:

1. **`test_submission_memory_preflight.py::test_job_submission_forwards_configured_extra_overrides_to_memory_check`**
   asserted the literal old inline mapping (`admission_tier="$tier"` / `admission_tier="gt4i.1"`)
   as source text in `job.sh`. Centralizing that mapping into
   `family.py::admission_tier_for` (this session, closing the #84-class duplication risk) removed
   both literals from `job.sh` — correctly; the test was checking a mechanism, not the behavior it
   existed to protect. **Fixed** by replacing the two stale text assertions with a real behavioral
   test, `test_g11_submission_resolves_the_admission_tier_before_the_memory_check`: submit a
   stubbed g1.1 config and confirm the memory check actually printed `on gt4i.1`, not `on g1.1`.
   Non-vacuity proven: reverted the `admission_tier_for` call to a bare `admission_tier="$tier"`
   and confirmed the new test fails with `unknown job tier: g1.1` (a real submission failure).
2. **`tests/test_v100_gpu_budget.py`**, three tests, all sized against the OLD
   `V100_BUDGET_CAP_MINUTES=120` before this session raised it to 240 (owner's explicit
   instruction). `test_g11_submit_refuses_a_reservation_over_the_cumulative_cap` hardcoded
   `"cap_minutes": 120` in its own state-file fixture, which `load_state()`'s consistency guard
   (added in the same cap-raise edit, and which the edit's own comment already anticipated this
   exact staleness) now refuses outright — failing one step before the cumulative-cap check it
   meant to test was ever reached. `test_g11_ambiguous_cloud_failure_retains_reservation_and_blocks_followup`
   used reservation sizes (100 + 30 = 130) that no longer exceed the new 240 cap, so the followup
   it expected to be refused now legitimately succeeds. `test_v100_budget_reconcile_updates_actual_elapsed_and_status_is_local`
   expected `remaining_minutes == 90.0` (120 - 30), now correctly 210.0 (240 - 30). **Fixed** by
   rescaling all three fixtures to the current cap (200+50 sizing preserves "genuinely exceeds",
   210.0 replaces 90.0) rather than reverting the cap.
3. **`tests/test_job_knobs_are_read.py::test_no_cfg_knob_is_dead`** flagged
   `NATIVE_V100_RESERVATION_MINUTES` (used in this session's two new V100 configs) as a dead knob
   because it's read entirely by `job.sh`'s own local submit-time preflight, which the test's
   `_in_job_surface()` deliberately never scans (job.sh runs on this machine before submission,
   never inside the job). Genuinely the same category as the existing `PLATFORM` allowlist
   (`RLVIGEN_ARCHIVE`, `RECORDS_OUT`, etc.), just never added when the knob was introduced.
   **Fixed** by adding it to `PLATFORM`, confirmed by grep that job.sh and the two v100 cfgs are
   its only readers.

All three are genuine "the fix was right, the test just didn't travel with it" gaps, not product
bugs — but each would have kept failing the full suite silently (or been discovered later, at a
worse time) had `pytest tests/ -q` not been run in full. `pytest tests/ -q` clean after all three
fixes (see full-suite run logged the same session).

## #93 — a fresh-agent adversarial review of the #90 ledger entries caught a real, precise gap: `ppg`'s `runtime_imports_checked: true` was earned on a false premise

Before treating the 5 new `validated_evaluator_families.json` entries as final, dispatched an
independent agent with no stake in the outcome to verify them from first principles rather than
trust the summary — exactly per the standing "don't self-grade your own validation pipeline"
concern. It confirmed 4 of 5 (`rlvigen`, `dmc_gb`, `idaac`, `ibac_sni`) clean on every mechanical
axis, and found one real defect in the fifth.

**The claim it disproved**: I had checked `runtime_imports_checked` by diffing each family's
`native.runtime_import_manifest.module_files` against `CODE_MEMBERS ∪ FAMILY_RUNTIME_MEMBERS[fam]
∪ RL-ViGen-upstream/ (archive-pinned) ∪ runnable/_shim/ (documented zero-repo-lines shim)`, and
called that exhaustive. It wasn't: `runnable/ppg/phasic_policy_gradient/train.py` appears in `ppg`'s
own manifest and falls outside every one of those four categories.

**Root cause, verified directly**: `runnable/ppg/phasic_policy_gradient/__init__.py` is exactly
`from .train import train_fn` — so importing the package AT ALL, for evaluation or training,
unconditionally executes `train.py`'s module body. `train.py` is in `evaluator_identity.py`'s
`_TRAINING_ONLY_RUNTIME_BASENAMES` (`{"train.py", "evaluate_ppo.py", "train_ppo.py",
"evaluate.py"}`) and is therefore excluded from `evaluator_family_code_revision`'s hashed closure —
confirmed: `evaluator_runtime_members(ROOT, "ppg")` does not contain it. The exclusion's own stated
rationale ("keep training drivers out, so checkpoint-writing changes do not relabel an evaluation
of already-saved bytes") is **false for `ppg` specifically**: the file is loaded into the live
evaluator process regardless of what's being run, so it is not safely excludable on that basis.

**Currently harmless, structurally real**: `train.py`'s module-level code is only imports plus
`def train_fn`/`def main`/an `if __name__ == '__main__':` guard — verified directly, no
side-effecting statement runs at import time. So this has not corrupted any measured number. But a
future edit to `train.py` (including something hoisted to module scope inside an existing function)
would change what the live evaluator process actually runs without moving
`family_code_revision["ppg"]`, which is exactly the failure mode this whole revision scheme exists
to prevent.

**Fixed the ledger honestly rather than patching the justification**: `ppg`'s
`runtime_imports_checked` set to `false` (was `true`), dropping `gate_shared_evaluator_validated`
from 5/7 to 4/7 — `ppg` now correctly reads "recorded but not paired+complete" rather than a
falsely-earned PASS. The mechanical fields (revisions, scope, pairing, diagnostics) all remain
correct and unchanged; only the one boolean whose justification didn't hold was touched.

**Left open, not fixed**: whether to (a) remove `train.py`/`evaluate_ppo.py`/`train_ppo.py`/
`evaluate.py` from `_TRAINING_ONLY_RUNTIME_BASENAMES` for families where the package `__init__.py`
imports them unconditionally (closing the gap but possibly reopening the very
checkpoint-relabeling problem the exclusion exists to prevent, if any of those FILES have real
training-only side effects on import elsewhere), or (b) audit each of the four excluded basenames
across all seven families for the same package-`__init__.py`-forces-import pattern and only carve
out entries proven safe. This is a genuine "our best judgment, still open" architectural question,
not a mechanical fix — recorded as DECISION-SHEET.md A34 rather than silently defaulted either way.

## #94 — found by Codex (mailbox Q39), independently verified: `NATIVE_HOST_PROFILE` is baked into every family's evaluator revision, even when the profile override is training-only

Codex flagged, while tracing why a ctrl/ppg revalidation might not be worth launching yet, that
`evaluator_identity.py` mixes `NATIVE_HOST_PROFILE` into the evaluator code/config revision digest
even though the current host-profile overrides are training rollout/replay parameters, not
evaluator behavior. Verified directly rather than taken on trust:

- `families.json`'s `rlvigen.host_profiles.v100` overrides exactly two fields: `replay_capacity`
  (training replay buffer sizing) and `preserve_snapshots` (training checkpoint-retention
  cadence). Both are training-loop parameters. The offline evaluator (`scripts/eval_grid.py`)
  loads an already-saved checkpoint and runs episodes — it never touches a replay buffer or a
  training checkpoint-save cadence.
- `evaluator_family_config_revision`'s hashed payload (`evaluator_identity.py:356`) includes
  `"host_profile": _selected_host_profile(root)` as a raw field **unconditionally**, regardless of
  whether the family in question even has a host-profile override that touches anything
  evaluation-relevant. `_digest_of` (used for `family_code_revision`/`evaluator_revision` too)
  separately appends the same host-profile string as a trailing hashed byte sequence.

**Consequence, stated explicitly because it wasn't yet**: every one of the 5 evaluator-family
ledger entries validated this session (#90, #93 — `rlvigen`, `dmc_gb`, `idaac`, `ibac_sni`, plus
`alda`) ran with `NATIVE_HOST_PROFILE` unset (default `"datasphere"`). Actual production requires
`NATIVE_HOST_PROFILE=v100` (`production_gates.py`'s "production names its host" gate). As currently
designed, computing any family's closure under `v100` will never match what was validated under
`datasphere` — not because the code differs in any way relevant to evaluation, but because the
profile *name* is hashed in directly. `gate_shared_evaluator_validated` is therefore structurally
unable to read "current" for a production run, for any family, regardless of how many revalidation
passes are run under the default profile.

**Not fixed here** — Codex is tracing the exact design fault and owns `evaluator_identity.py`;
this entry exists so the scope is on record: whatever the fix turns out to be, it invalidates and
requires revalidating all seven families' entries, not just the two (`ctrl`, `ppg`) still pending.
Not launching any further evaluator-family validation until that trace concludes, per Codex's
explicit request.

## #95 — `source-lock.json`'s recorded root commit named the LEGACY tree, not this repository at all (external review 15 §1)

Fixed and committed (`6d93300`) but never actually appended here — the ledger this project holds
itself to had a gap in its own discipline. Recording it now rather than leaving the commit message
as the only durable trace, since a reader of this file alone would have seen #94 and then #96 and
concluded #95 never happened.

`datasphere/native/source-lock.json`'s `nested_repository_commits.root` read
`f041f5e170368d298e9b5b60127faa10ba5364e5` — confirmed via `git cat-file -t` that this object does
not exist anywhere in this repository's history at all. It is the LEGACY
`ccm-intro/projects/many-gens-rl-vigen` tree's HEAD (branch `nd-ln-architecture-transition`), not
this recovery workspace's own history. `contract.py`'s `write_payload` copies this value verbatim
into every payload manifest without ever recomputing it, so every payload built before this fix
carried a root commit that could never be resolved in the repository the payload actually shipped
from.

**Fixed**: set to the current HEAD at fix time (`cea0991be313da900062a43831eee3d5d20544cb`).
**Added** `test_source_lock_root_commit_is_from_this_repository` (`tests/test_production_defaults.py`)
— deliberately checks the recorded root is a real, reachable ancestor of HEAD, not literal equality
(which no committed value could ever satisfy the instant it's committed, since HEAD moves past it
on the very next commit). Non-vacuity proven with the exact original bad value: fails with the
precise "not reachable" message, restored clean.

## #96 — the ctrl "in-progress, uncertain" caveat was a self-correction that turned out, on completion, to be simply wrong

Recorded because leaving a retracted-but-unconfirmed claim sitting in a handoff note is exactly the
"noted and moved past" failure mode this project's own discipline (per this entry's neighbors, and
`docs/local-envs.md`'s general convention of writing corrections down rather than quietly fixing
and moving on) exists to prevent.

**What I wrote, and had to retract under direct questioning**: *"ctrl's new schema-2 payload
freezes Codex's in-progress, uncommitted edits (477 lines) exactly as they stood when it went
offline — self-consistent, but not confirmed finished or tested."* Two things were conflated: (1)
`git status` showing `runnable/ctrl` as modified relative to its own nested repo's single
`PRISTINE` commit — which is the **permanent, normal state of all six baseline clones** (their
nested git history never advances past the pristine snapshot; every patch ever applied to them
shows as "uncommitted" forever, confirmed identical for `alda`/`dmc_gb`/`ibac_sni`/`idaac`/`ppg`)
— with (2) a separate, earlier belief that Codex was "actively editing ctrl live," never itself
re-checked against the diff content.

**Completed this session**: read all five changed files' diffs (`vec_env.py`, `algo.py`,
`buffer.py`, `models.py`, `train_ppo.py` — 477 inserted / 84 deleted lines total) end to end, the
same way a fresh reviewer would. Findings:

- Every dated marker found (`[OURS 2026-09-04]`, `[Claude 2026-09-02 09:35 MSK]`) is at least two
  days old at the time this was re-checked, not a live edit.
- The content is CTRL's continuous-action-space port (Procgen's `ctrl_public` is Categorical-only;
  RL-ViGen's Door is `Box(-1,1,(7,))`) plus a real upstream bug fix — `ctrl_public @ 7a118c8`
  ships two commented-out lines (`w_clust_target = l2_normalize(...)` and its use) that make its
  OWN `loss_cluster` raise `NameError` the first time `update_cluster` runs; this is not a porting
  defect, `ctrl_public` cannot execute its own algorithm as released. The two lines are
  un-commented with the reasoning stated inline.
- Several JAX/Flax API-drift fixes are clearly separated from algorithm changes and labeled as
  such (`jax.tree_multimap`→`jax.tree_util.tree_map`, `jax.ops.index_add`→`.at[].add`,
  `FrozenDict.copy(add_or_replace=...)`→plain-dict merge, `.split`→`jnp.split`), each with the
  API-version reasoning that makes the "semantics unchanged" claim checkable rather than asserted.
- `algo.py` adds `clip_fraction`/`approx_kl_k3` PPO diagnostics — exactly the re-open trigger
  DECISION-SHEET A30 already names for CTRL's raw-vs-executed-action question, wired through
  `jax.value_and_grad(..., has_aux=True)` in a way that is provably a read of the existing `ratio`
  computation, not a change to it.
- `train_ppo.py` redacts a live 40-character W&B API key upstream shipped hardcoded for the
  authors' own entity (cross-referenced to `docs/CONSTRUCTION.md#c16`), wires the shared
  `scripts/metrics.py::gaussian_policy_health` diagnostic used by three other baselines, and adds
  intermediate/terminal checkpointing with an explicit self-critical note that `evaluate_ppo.py`
  still cannot read a robosuite checkpoint from this format.
- `pytest tests/ -q -k "ctrl"` — 99 passed, 0 failed, re-run fresh (not trusted from memory).
- `python scripts/refresh_clone_patches.py --check` — reports `ctrl current`, i.e. the committed
  patch matches the clone's actual state exactly.

**Verdict**: this is finished, cross-referenced, deliberately-reasoned, tested work, not an
in-progress or uncertain state. The original caveat is retracted in full, not just in framing.
`notes/CURRENT-STATE-AND-RESPONSIBILITY.md`'s partial retraction is superseded by this entry.

## #97 — the 7-family schema-2 wave (v146-v152) landed 6/7 clean; `ctrl` reports an evaluator_revision that no local computation, past or present, produces

All seven jobs (`bt1s71ot06...` through `bt1mg9ens1...`) SUCCEEDED operationally: every family shows
`NATIVE_FINAL_EVALUATION_COMPLETED`, `non_finite: 0` on the terminal checkpoint, and physical pairing
(`scripts/audit_pairing_evidence.py`: 7 eligible comparisons, 0 unpaired, 0 lacking evidence — run in
two batches of 5+2 as jobs finished). Six families' reported `evaluator_revision` matches
`evaluator_family_revision(ROOT, family)` recomputed fresh, exactly — `rlvigen`, `dmc_gb`, `idaac`,
`alda`, `ppg`, `ibac_sni` are genuinely current and are now in `validated_evaluator_families.json`.

**`ctrl` does not, and the mismatch survived an unusually thorough attempt to explain it away as
something mundane.** All four of `ctrl`'s real `offline-eval` rows (train × 2 duplicate rows,
eval-easy × 2, the by-design rich/aggregate pair per regime) report `evaluator_revision`
`763de034c4ec...`, consistently — not a one-off fluke. Locally, `evaluator_family_revision(ROOT,
"ctrl")` computes `b7f687452b2d...`, and this is not a stale-tree artifact: it is bit-identical to
what `payload-v152-ctrl.tgz`'s own `payload_manifest.json` baked in at build time (`revision`,
`code_revision`, and `config_revision` fields all match a fresh recomputation exactly). Checked
exhaustively, not assumed:

- All 36 of `ctrl`'s hashed runtime-member files (its own 5 `.py` files, `door.xml`, every file
  under `runnable/_shim`, and the shared `RL-ViGen-upstream/envs/robosuiteVGB` members) — compared
  byte-for-byte between the manifest's baked hashes and a fresh local recomputation: **0 differ**.
- `door.xml` and the five `ctrl/*.py` files — diffed directly against the extracted payload
  archive's own copies: **byte-identical**.
- `evaluator_family_config_revision` is a pure hash of `{identity_schema, semantics, family,
  scope_fields}` — all four are static constants or the literal string `"ctrl"`; it cannot legally
  differ between environments given byte-identical `evaluator_identity.py` (confirmed identical via
  direct diff against the shipped payload).
- Manually recombined the manifest's own `code_revision` + `config_revision` by hand
  (`sha256(code + "\0" + config)`) and got `b7f687452b2d...` again — ruling out a bug in my
  verification script rather than in the mechanism.

So the value baked into the payload, the value recomputed from the current tree, and the value
recomputed from the extracted archive's own files all agree with each other and disagree with what
the remote job reported — for `ctrl` only, not for any of the six other families sharing the exact
same shared `RL-ViGen-upstream` closure members and the exact same `evaluator_identity.py`.

**Not resolved.** The mechanism this project already used to catch an analogous class of bug (#88,
macOS-vs-Linux tar extraction differences) required a diagnostic resubmission with temporary print
instrumentation comparing local and remote member sets directly — that is real, deliberate spend,
not something to do speculatively while investigating a single family's anomaly. Left as a genuine
open question rather than guessed at further. Candidates not ruled out: a DataSphere-side upload/
cache staleness for this specific payload filename (re-uploading under a fresh version number would
distinguish this from a real extraction-environment difference), or something specific to `ctrl`
being the only family whose closure names a *bare* directory (`runnable/_shim`, vs. every other
family's directly-named subdirectories or files) in a way that behaves differently at scan time on
the remote filesystem.

**Ledger left honest, not patched**: `validated_evaluator_families.json`'s `ctrl` entry now carries
the job's own reported `evaluator_revision` (`763de034c4ec...`) verbatim — this does not match
`evaluator_family_revision(ROOT, "ctrl")`, so `production_gates.py`'s own fail-closed check correctly
reads `ctrl` as "on a superseded revision, needs re-run" without any manual intervention. That framing
undersells the actual finding slightly (this isn't ordinary staleness — the local answer never
matched any point in time), which is why this entry exists: a bare re-run might reproduce the exact
same mismatch if the cause is systemic rather than a moved tree, and whoever re-runs it should know
that before spending a second job on the assumption that resubmitting alone fixes it.

**Not blocking**: the other six entries are real and current; `gate_shared_evaluator_validated` now
correctly reads 6/7, a genuine improvement from 0/7, not a number to distrust because of `ctrl`'s
anomaly.

## #97 amendment — root-caused and fixed: `door.xml` was hashed as source but is a runtime-regenerated artifact

Resolved via one deliberate diagnostic job rather than further guessing, after plain revalidation
(v153, a completely fresh payload archive) reproduced the identical anomalous value and ruled out
upload/cache staleness. `scripts/eval_grid.py` carried a temporary, opt-in block
(`NATIVE_DIAGNOSE_EVALUATOR_IDENTITY=1`) that hashes `ctrl`'s full runtime-member set live, on the
remote container, and prints it before exiting — job `bt1tnffd9m78e1t2uj0h` (4112 frames, the
minimum that clears `ctrl`'s own curve-measurement floor, so training actually ran before the
identity check).

**Of 36 hashed files, exactly one differed from the known-good local hash**: `runnable/ctrl/
door.xml` — remote `94e01f29...`, local `fcb09068...`. Every other member, including the five other
`ctrl/*.py` files and all shared `RL-ViGen-upstream/envs/robosuiteVGB` members, matched exactly.

**Root cause**: `door.xml` is not authored source — `scripts/deviations.py`'s own "untracked but
not counted" list already documents it as "a run artifact — a robosuite task model dumped at cwd
during a run." Robosuite writes its own resolved copy of this file to the working directory during
environment construction, which for a real cell happens *before* `eval_grid.py`'s offline
evaluation runs (training executes first). So by the time `evaluator_family_code_revision` re-hashes
`FAMILY_RUNTIME_MEMBERS["ctrl"]` from disk, `door.xml` has already been overwritten by *this specific
run's own robosuite construction* — the hash was never stable evaluator identity, it was whatever
byte-for-byte artifact the last environment construction happened to write. `door.xml` was the
*only* one of `ctrl`'s hashed members that is regenerated at runtime rather than fixed at code-change
time, which is exactly why it was the only one that ever differed.

**Fixed**: removed `"runnable/ctrl/door.xml"` from `FAMILY_RUNTIME_MEMBERS["ctrl"]`
(`evaluator_identity.py`). No test named it explicitly (checked directly, not assumed), so nothing
else needed updating. Verified: `pytest -k "evaluator_identity or evaluator_binding or ctrl"` clean;
`production_gates.py`'s only remaining fail is the expected uncommitted-source-tree flag for this
exact fix, pre-commit.

**Consequence**: `ctrl`'s evaluator revision changes again with this fix (removing a hashed member
changes the digest), so the v146-v152 wave's `ctrl` entry — already known-invalid from the original
anomaly — needs one more clean revalidation run against the corrected closure, not a fourth guess.
Not resubmitted in this entry; tracked as the immediate next step.

**Why this is worth stating plainly**: this is the second real, first-ever-exercised bug this
project's evaluator-identity mechanism has found by actually diffing a local computation against a
live remote one (the first was #88's AppleDouble sidecars). Both bugs are the same shape — a file
assumed static that a macOS-vs-Linux or code-vs-runtime boundary silently changes — found only
because someone insisted the mismatch be explained rather than revalidated around.
