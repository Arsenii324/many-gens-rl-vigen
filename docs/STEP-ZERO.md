# Step zero — the practice before any code, and how claims must be shaped to survive

> ## Handoff, 2026-08-29 — READ THE FIRST ITEM BEFORE TRUSTING A GREEN SUITE
>
> ### 0. RESOLVED — the 25 failures were my own test polluting `sys.modules` ([C90](CONSTRUCTION.md#c90))
>
> **`2fdc161f` was committed on a red suite.** The command chained `pytest` and `git commit`
> unconditionally, so the commit ran regardless of the result — a process failure, not a code one,
> and mine.
>
> **What was observed:** `25 failed, 949 passed, 5 errors`, with
> `tests/test_real_env.py::test_real_env_reseeded_episode_reproducibility` raising
> `rlgen.envs.ContractError: the env did not report a regime. setup/apply_patches…`.
>
> **Cause, established 2026-08-29 and it was not contention.** `tests/test_eval_loop_measurement.py`
> — written the same day — injects fake `wrappers`/`utils` modules into `sys.modules` and never
> removed them, so every later test that built a real environment got the stub. Fixed with an
> `autouse` fixture that restores them; **full suite now exits 0.**
>
> **The trap worth carrying forward**, because it nearly closed the investigation: re-running
> `tests/test_real_env.py` **alone** passed 25/25, which reads as "environmental, not real". For a
> test that pollutes global state that is *green in isolation and red in company by construction* —
> narrowing the scope cannot see the bug and argues against looking further. What settled it was
> **widening**: re-running the whole suite under the same live-run conditions and watching the
> failure reproduce.
>
> **And it would have been intermittent.** `pytest-randomly` is installed; this session used
> `-p no:randomly` throughout, which is the only reason the failure was deterministic and findable.
> Under the default random order it would flicker between runs — the shape that gets filed as
> flakiness and never fixed.
>
> ### 1. What landed, and what it is worth
>
> The night's work was **verification of existing results**, not new ones, plus three downstream
> findings. All of it is in [`ASSURANCE.md`](ASSURANCE.md), which sorts every claim by the
> **mechanism** that assures it — read that before quoting any number.
>
> - **`scripts/verify_cells.py`** (new, 9 tests): 8 provenance invariants per cell — same weights
>   on both sides of the ratio, regime genuinely different, same protocol, same scenes, post-C69
>   seeding, budget label matching `trained_step`, real control seed. **All five cells: 0
>   failures.**
> - **`tests/test_eval_loop_measurement.py`** (new): the gap `ASSURANCE.md` found. The evaluator's
>   eight tests all checked **aggregation**; nothing checked that a recorded return equals the sum
>   of emitted rewards. Now three properties, three mutants killed — and closing it exposed a
>   **defect in my own test** (a reward sequence ending in `0.0` let a dropped-terminal-reward
>   mutant survive).
> - **[C87](CONSTRUCTION.md#c87)**: first same-quantity comparison with RL-ViGen's published table.
>   Ordering reproduces; `drq` within 16%. **Not** [C48](CONSTRUCTION.md#c48) — that runs *their*
>   evaluator, still undone.
> - **[C88](CONSTRUCTION.md#c88)**: scene difficulty is method-dependent (ρ = +0.758 between the
>   DrQ arms; `svea` with neither).
> - **[C89](CONSTRUCTION.md#c89)**: under the shift the **trained** scene becomes the worst, 14–53×,
>   in all three arms — and all seven non-native evaluators are pinned to `scene_id=0`, so they
>   would report the shift's worst case. **This is the sharpest input to [P-C76](RESEARCH-FRAME.md)
>   and makes its option 2 much worse than it looked.**
> - **C62's ceiling falsification-tested**: 240 scene-grids, 311 high-return episodes, 0 violations.
> - **The floor** re-measured after `verify_cells` found it recorded no `placement_seeded` — an
>   unwritten field, not a seeding failure. Re-run 19 h later: **400/400 byte-identical**. v2
>   promoted, v1 kept as `random-floor-v1-preserved__*`.
>
> ### 2. In flight
>
> **`drqv2` seed 8 at 105k**, launched 2026-08-29 12:41 — **the first measurement of between-seed
> variance**, which is the caveat on every number this project reports. At frame 19 000 when this
> was written, healthy, ~1.3 h remaining. When it lands: evaluate both regimes into
> `results/regime-retention-c69/` as `drqv2-s8-105k-at100k__{train,eval-easy}`, add the row to
> `CELLS` in `scripts/results_table.py`, and compare against seed 7 — **that comparison is the
> single most valuable number still missing.**
>
> ### 3. The honest state of quality
>
> [`ASSURANCE.md`](ASSURANCE.md) §"How this work was done" lists the eight things I got wrong this
> session, what each cost, and whether it is now **prevented** by an instrument or merely **known**.
> Six of eight share one shape: *a cheap operation stood in for an expensive one and nothing said
> so*. Two remain only remembered, not enforced — the concurrency rule, and re-reading a
> load-bearing document rather than grepping it. **The red suite above is a ninth, and it is not
> yet on that list because its cause is unresolved.**

> ## Handoff, 2026-08-27 — a result exists, the instruments that were decorative now run, and the reading rules changed
>
> **Read this, then the 08-26 block below it.** Nothing there is retracted; this is what changed.
>
> ### 1. There is a real endpoint number now
>
> [C81](CONSTRUCTION.md#c81). `drqv2` seed 7 at 105k, paired within one run:
> **regime retention 0.003 [0.002, 0.005] at 100k, 0.019 [0.012, 0.028] at 50k** — *more training
> made retention worse* while train-regime skill rose ×1.41. Uncontaminated (passes
> [C65](CONSTRUCTION.md#c65)'s screen, unlike every archived checkpoint), deterministic,
> verified finite, mode-verified, both drops an order of magnitude below their own resolution
> floors.
>
> **The control that matters more than the number:** the random-policy floor is **byte-identical
> across `train` and `eval-easy`, 200/200 episodes**. The regime shift perturbs neither dynamics,
> nor initial state, nor reward — it is **purely visual**, so a trained policy's gap is
> attributable to the observation alone. Unavailable before [C69](CONSTRUCTION.md#c69).
>
> ### 1b. And the first CROSS-BASELINE comparison, which is what the project is for
>
> [C83](CONSTRUCTION.md#c83). Same budget, same evaluator, both uncontaminated:
>
> | @100k Door | trained scene | scene retention | **regime retention** | usable scenes |
> |---|---|---|---|---|
> | `drqv2` | **439.75** | 22.9% | **0.003** [0.002, 0.005] | 3/10 |
> | `svea` | 234.36 | **59.7%** | **0.428** [0.318, 0.558] | **9/10** |
>
> **The weaker arm where it trained is the stronger one off it.** A table reporting only
> train-regime return would have ranked them backwards — which is exactly what a retention
> endpoint exists to prevent. Both gaps clear their own resolution floors. One seed each, one task,
> one budget; the two arms pool over *different* scene sets (9 vs 3), which is a real caveat.
>
> **And these two are comparable in a way the twelve are not**: the seam audit splits on **0 of 12
> axes within the five natives**, whose hydra configs are identical on every shared key. The
> collinearity that makes across-method comparison weakly identified does not apply inside that
> subgroup — see [`RESEARCH-FRAME.md`](RESEARCH-FRAME.md).
>
> ### 1c. THREE baselines now, and the ranking inverts ([C86](CONSTRUCTION.md#c86))
>
> **Historical within-run diagnostic, not a current headline table.** It now requires
> `python scripts/results_table.py --legacy-exploratory`: episode-bootstrap intervals do not
> quantify training-seed uncertainty, and the retained rows predate the current evaluator revision.
> The values below are preserved as the dated observation that motivated the protocol, not as a
> production comparison.
>
> | @100k | trained scene | scene ret. | **regime ret.** | usable | SR train→eval |
> |---|---|---|---|---|---|
> | `drqv2` | **439.75** | 22.9% | 0.003 | 3/10 | 29.5% → 0.5% |
> | `drq` | 378.85 | 13.4% | 0.051 | 3/10 | 16.0% → 1.0% |
> | `svea` | 234.36 | **59.7%** | **0.428** | **9/10** | 50.0% → 19.5% |
>
> **`svea` is last on the scene it trained on and first on both retention axes.** A table of
> train-regime return would rank these three exactly backwards. The two retention axes also
> *disagree* on `drqv2` vs `drq`, and that is reported rather than averaged away.
>
> Limits are the same size as the result: one seed each, rows pool over **different** scene sets
> (3/3/9), `svea`@50k is REFUSED rather than zero, `drq` has no 50k pair, and `drq`'s seed-only
> control is 23.6% — five times the others'.
>
> ### 1d. Verified, and taken downstream (2026-08-29)
>
> **The results were checked, not asserted.** `scripts/verify_cells.py` — the layer beneath the
> table and the retention report, which did not exist — confirms per cell that both regimes used
> the **same weights** (`snapshot_md5` identical, file still hashing to it), that the regime
> genuinely differed, same protocol, same scene set, post-[C69](CONSTRUCTION.md#c69) seeding, the
> budget label matching `trained_step`, and a real control seed. **All five cells and the floor
> pass; 0 invariant failures.** Its one first-run finding was the floor's unrecorded
> `placement_seeded` — an unwritten field, not a seeding failure — and re-measuring it 19 hours
> later returned **400/400 episodes byte-identical**.
>
> **Three downstream findings, in descending order of how much they should change what you do:**
>
> - **[C89](CONSTRUCTION.md#c89) — under `eval-easy` the TRAINED scene becomes the worst one, in
>   all three arms.** Held-out ÷ scene 0 inverts from 0.13–0.60× under `train` to **14–53×** under
>   the shift. **The seven non-native evaluators are all pinned to `scene_id=0`**, so the regime
>   gap they would report is measured where the shift is most destructive — systematically its
>   worst case. This makes [P-C76](RESEARCH-FRAME.md)'s **option 2** much worse than it looked.
> - **[C88](CONSTRUCTION.md#c88) — scene difficulty is method-dependent.** `drqv2` and `drq`
>   rank-correlate **+0.758** on which scenes are hard; `svea` correlates with neither. So
>   averaging over scenes is **not** a neutral marginalisation, and scene 0 is additionally the
>   least discriminating single scene — all three handle it well under `train`.
> - **[C87](CONSTRUCTION.md#c87) — first same-quantity comparison with RL-ViGen's published
>   table.** The ordering reproduces (`svea` > `drq` > `drqv2`) and `drq` lands within **16%** at a
>   sixth of the budget. **Not** [C48](CONSTRUCTION.md#c48)'s reproduction — this runs *our*
>   evaluator. And their `drqv2` (3.6) is twice the measured floor while their `drq` (14.0) is
>   7.7×, so two of their own natives barely solve Door Easy either.
>
> The table now carries Wilson intervals for success rates and bootstrap CIs for scene retention;
> the three arms' scene-retention intervals do **not** overlap. All of it bounds **within-run**
> noise — between-seed variance is unmeasured everywhere, one seed per cell.
>
> ### 2. Three instruments were decorative and now are not
>
> - **Mutation testing had never once run** ([C80](CONSTRUCTION.md#c80)). Its sanity gate failed
>   every time, on three "the copy is not a faithful environment" causes, and reported them as
>   *citation defects*. Fixed; 31 mutants, M25–M31 all killed on first use.
> - **Divergence was readable in the live log for six days and nothing read it**
>   ([C79](CONSTRUCTION.md#c79)). `run_cell.sh` now attaches `watch_divergence.py` by default.
> - **A native run launched at exactly N never saves at N** ([C77](CONSTRUCTION.md#c77)).
>   `run_cell.sh`'s documented default would have produced **zero checkpoints for every future
>   cell**. Cells now run at 105 000 for a 100k checkpoint.
>
> ### 3. The reading rules changed, because three wrong claims came from one habit
>
> [C82](CONSTRUCTION.md#c82). All three were written about `FAITHFULNESS.md` in one day, all three
> from **concluding out of a proxy for reading** — a `grep '^## '` map, then a reference count.
> The worst asserted the file did not know the clone tree existed; its §5 is a clone-era re-triage
> that resolves and re-opens everything above it.
>
> - **`##` headings in scoped documents now carry an era tag** — `LIVE`, `PORT-ERA`, `HISTORY`,
>   `DURABLE`, `MIXED`, `CURRENT-STATE` (at most one, meaning *read this first*), optional `-U`
>   for *believed, not verified by reading*. `scripts/check_section_scope.py --strict`. **A tag
>   never licenses discarding a claim unread** — `PORT-ERA` sections routinely carry durable
>   research about papers.
> - **Check the VALUE a claim asserts, not the path it cites.** A dead citation beside a true
>   number is a broken link, not a wrong claim.
> - **Look for the document's own latest-state section before writing a banner over it.** Scoped
>   appending edits put the newest answer at the END.
> - **Separate the sentence, the reasoning, and the disposition a claim licenses.** Only the first
>   is cheap to check; only the third decides whether anything must be done.
>
> ### 4. What that thread found, which is the opposite of what it started as
>
> `FAITHFULNESS.md` §4's structural findings — PPG with one shared value head, IBAC-SNI's critic
> seeing the SNI-mixed pass, CTRL missing `L_clust` — describe **our re-derived on-policy core**,
> and **the clone move discharged every one of them** (verified: `runnable/ppg` ships
> `PhasicValueModel`/`vf_true`/a separate `aux_lr`; `runnable/ibac_sni` ships `bot_mean`;
> `runnable/ctrl` ships the clustering). That section is the record of the port's fidelity debt
> being paid, **not a backlog**. There is no twelve-baseline re-derivation owed.
>
> ### 5. Running, queued, and what is the owner's
>
> **Running:** `svea` seed 1's four retention grids. **Queued:** `drq` seed 1 at 105k — **alone**,
> it is the heaviest native. **Note `svea`@50k is already refusable**: scene 0 scores 62.0 with
> 2/20 successes against a *seed-only* control of 38.5, so the seed effect rivals the scene effect
> and the denominator is under the 0.25 rule. That is [C73](CONSTRUCTION.md#c73) again — 50k is
> below the threshold — and the instrument refusing is it working.
>
> **The owner's, and nothing here is blocked on more measurement:**
> [P-C76](RESEARCH-FRAME.md) (what the retention endpoint is measured over — the one UNITS split,
> and no cross-baseline table can be emitted until it is decided), `FAITHFULNESS.md` §5's items
> 5/6/9/10 (item 9, the entropy coefficient against a 7-D Gaussian rather than Procgen's 15-way
> categorical, is its own "largest untracked fidelity gap" and is measured),
> [C64](CONSTRUCTION.md#c64), [C68](CONSTRUCTION.md#c68), and the register's standing judgement
> queue.

> ## Handoff, 2026-08-26 — the measurements were not reproducible, and two documents were about the wrong system
>
> **Read this before the 08-24 block below it.** Nothing in that block is retracted, but three
> things it takes for granted have since been shown false, and one of them invalidates any number
> computed before 08-25.
>
> **1. The evaluator was not deterministic, and nothing in this repository noticed.** Two defects,
> found in sequence:
>
> - **[C69](CONSTRUCTION.md#c69)** — `scripts/eval_across_scenes.py` seeded the environment but
>   never the *global* `np.random`, which is what robosuite's `UniformRandomSampler` draws from.
>   Two evaluations recording **the same `seed` field** placed the door ~1.6 cm apart. A second
>   source sits at `robot.py:131`: initial joint pose carries σ = 0.02 rad of noise from the same
>   unseeded stream. Fixed by calling `utils.set_seed_everywhere(seed)` *before* `robo_make`.
> - **[C70](CONSTRUCTION.md#c70)** — even seeded, torch's runtime kernel selection moved episodes
>   across Door's `hinge_qpos > 0.3` success threshold: the same checkpoint, same seed, same scene
>   scored **372.34** and **6.01** on two runs. Fixed by `torch.use_deterministic_algorithms(True)`.
>   The honest scope: 19 of 20 scene-grids then came out identical, residual ~0.2 %,
>   outcome-preserving — **not** bit-for-bit, and the entry says so.
>
> **All 14 grids were re-derived deterministically into `results/regime-retention-c69/`.** No
> conclusion moved. `svea`'s train successes doubled (6 → 12) and are still refused by the
> denominator rule. `scripts/regime_retention_report.py --archive auto|c69|pre-c69` announces which
> set it read; **`auto` means the deterministic set**. Any number quoted from the pre-C69 archive
> is a measurement of a lottery.
>
> **This is the second time an instrument was green while the seam beneath it was broken**, and it
> is why the project `CLAUDE.md` now opens with the blind-spot pass rather than with the layout.
>
> **2. `COMPARABILITY_CONTRACT.md` §1–§10 audit the *retired* `rlgen/` port — 31 references, and
> until 08-26 nothing said so.** Its argument rests on *"every baseline's environment interaction
> … goes through `rlgen/envs.py`'s construction path"* plus four shared adapters. The null became
> the clone on 08-17; there is no shared construction path and there are no adapters, so that
> evidence does not transfer. The head of the file now carries the warning. **This matters because
> `TASK.md` R3 names that document as carrying its burden** — so R3's evidence was, for nine days,
> a document about a system that no longer runs.
>
> **R3 itself was relaxed by the owner on 08-26**, from *"код эвалюэйшена должен быть ИДЕНТИЧЕН у
> всех бейзлайнов"* to **"evaluation code should produce metrics that are fully on the same axes
> and directly comparable"**. It is still graded **NOT MET**, and **DZ has not agreed the
> relaxation** — it amends a verbatim supervisor line, so it is the owner's to carry, not this
> project's to assume.
>
> **The replacement evidence is `scripts/audit_comparability_seam.py`** (built 08-26,
> mutation-verified). It reports **2 of 4 axes uniform** on the architecture that actually runs:
> horizon agrees at 500; action repeat agrees *in value* (all twelve at 1) but is reached four
> different ways, two through a knob passed and never read; truncation splits **3 bootstrap / 9
> terminal** ([C1](CONSTRUCTION.md#c1)); render resolution splits **100 / 84 / 64**
> ([C5](CONSTRUCTION.md#c5)). It ends by **naming the axes it does not cover** — reward collection
> and normalisation, what an episode counts as for an on-policy vs off-policy learner, success
> definition, observation channel order, frame-stack depth. Absence from that list is evidence
> nobody has derived it, not evidence of agreement. **Do not read a clean run as "the metrics are
> comparable"; the script says so itself and it means it.**
>
> **3. The retention endpoint reads five checkpoints, not twelve** ([C72](CONSTRUCTION.md#c72)) —
> and zero of the other seven baselines' evaluators sweep the scene axis at all. The claim reaches
> five of twelve. `RESEARCH-FRAME.md`'s drift table said "zero runs"; that was stale and is
> corrected.
>
> **THE FIRST CLEAN ENDPOINT NUMBER EXISTS (08-27).** [C81](CONSTRUCTION.md#c81). `drqv2` seed 7
> at 105k, uncontaminated, deterministic, verified finite, mode-verified, paired within one run:
> **regime retention 0.003 [0.002, 0.005] at 100k and 0.019 [0.012, 0.028] at 50k** — so **more
> training made retention worse** while train-regime skill rose ×1.41. Both drops are an order of
> magnitude below their own resolution floors, and neither trips [C65](CONSTRUCTION.md#c65)'s
> contamination screen, unlike every archived checkpoint.
>
> **And the control that matters more than the number:** the deterministic random-policy floor is
> **byte-identical across `train` and `eval-easy`, 200/200 episodes**, both modes verified applied.
> The regime therefore perturbs *neither dynamics, nor initial state, nor reward* — the shift is
> **purely visual**, so a trained policy's gap is attributable to the observation alone. That
> discharges a caveat [`RESEARCH-FRAME.md`](RESEARCH-FRAME.md) had carried in two places, and it
> was unavailable before [C69](CONSTRUCTION.md#c69), whose floors differed by RNG noise alone.
>
> **What is running as this was written (relaunched 08-26 22:10).** `drqv2` seed 7 and `svea`
> seed 1 at **105 000 frames** — [C73](CONSTRUCTION.md#c73)'s 100k budget plus the tail
> [C77](CONSTRUCTION.md#c77) proves is needed to reach the 100k save at all. The first attempt at
> exactly 100 000 is what found C77: it ran 3.5 h and produced only a 50k checkpoint. `drq` seed 1
> waits on the two-concurrent-render cap. Each is paired with `scripts/preserve_intermediate_snapshot.py`, which
> copies the 50k snapshot the run is about to overwrite, so **every cell yields its own within-run
> 50k/100k comparison** — turning C73's `n = 1`-and-contaminated pairing into `n = 4`. Cells land in
> `results/cell-*-100k` via `run_cell.sh`'s new `CELL_DIR` override, which exists so a 100k re-run
> cannot write its provenance frames into the 50k cell of the same seed.
>
> **Operational facts that cost time, recorded so they cost it once.**
>
> - **NEVER launch a native baseline at an exact multiple of 50 000 frames** —
>   [C77](CONSTRUCTION.md#c77), and it cost 3.5 h before it was understood. The save at
>   `train.py:309` is inside `if time_step.last():` at the **top** of a `while step < until` loop,
>   so at the end of the episode landing on step N the while-test fails first and the loop exits
>   **before** the save. A run launched at N saves at every multiple of 50k *strictly below* N and
>   never at N. `run_cell.sh` now raises such a budget to `N + 5000` and says so; ask it with
>   `bash scripts/run_cell.sh --effective-frames <baseline> <frames>`. **The comment that used to
>   sit there claimed the opposite** — *"the default is therefore 50000, not 55000: same
>   checkpoint"* — and its default would have produced zero checkpoints for every future cell.
>   The lesson generalises: [C68](CONSTRUCTION.md#c68) got the *cadence* right and then inferred
>   the *boundary* from it. A cadence and a termination condition are different facts about one
>   loop, and the first does not give you the second.
> - **A diverged run is now visible from its LIVE log, and `run_cell.sh` watches for it by
>   default** — [C79](CONSTRUCTION.md#c79). Since `use_tb=True` went on (08-20), `train.csv`
>   carries `actor_loss`/`critic_loss`, which go literally `nan` on the first bad update; for six
>   days nothing read them. A `drqv2` run was NaN at **frame 7 000, 5.9 minutes in**, and ran 64
>   more minutes. `scripts/watch_divergence.py --match <substring>` covers a batch. It **reports,
>   never kills**, and says **BLIND** rather than "healthy" when the log has no loss columns —
>   `drq` always, and every non-native baseline, which `run_cell.sh` now prints a NOTE about.
>   After [C70](CONSTRUCTION.md#c70) divergence is a lottery: the same seed 7 diverged on one run
>   and reached return 475 on another, so expect it again.
> - **Two concurrent runs is an upper bound, not a safe number** — amended in
>   [`../../../docs/local-envs.md`](../../../docs/local-envs.md) on 2026-08-27. `svea` + `drq`,
>   *inside* the cap, took swap to **14.6 GB of 15.4 GB** and grew the swap file from 2 GB to
>   15.4 GB. `drq` is the heaviest native (49.6 M parameters); `svea` carries seven ~0.4 GB child
>   processes, so its tree is ~3.2 GB rather than the 2.2 GB one `ps` line shows. **Count the
>   memory tree, not the runs.** The swap file *does* shrink back once the jobs exit (24 GB → 2 GB
>   within hours, corrected 08-27 — an earlier version of this line said it does not), but the
>   **writes have already happened**, so a recovered `vm.swapusage` is not evidence the episode was
>   harmless. Run `drq` alone.
> - **A monitor whose exit condition depends on a time-windowed `find` never exits.** A watch loop
>   used `find … -newermt "-90 minutes"` to locate the live run directory, and its break condition
>   required a milestone that window had to match. As the loop ran, the window slid past the
>   directory's mtime, the milestones stopped firing, and the monitor outlived its subject by
>   hours — deferring a goal check-in each time. **A time-relative filter inside a persistent loop
>   goes blind as time passes.** Resolve the target once before the loop, or key the break on the
>   process count alone. Same family as [C79](CONSTRUCTION.md#c79)'s lesson that a watcher with a
>   timeout is a watcher that stops watching.
> - **`/usr/bin/cp`, `/usr/bin/cat` and `/usr/bin/ls` do not exist on this machine.** They are in
>   `/bin/`. A `cp`-based backup/restore failed *silently* and left a doc mutated.
> - **`mapfile` needs bash 4; macOS ships 3.2.** Use `while IFS= read -r`.
> - `pytest.ini` already sets `-q`, so passing another `-q` silences the summary line you were
>   about to read.
> - **Do not run system cleanups.** On an `ENOSPC` the answer is to measure and report, not to
>   delete: the 08-26 one was diagnosed by the owner as swap from *another* parallel ML run, and
>   this project's 7.3 GB was never the cause. Own scratch may be removed only when both the target
>   *and the deletion command* are proven safe.
>
> **The stance that produced the most rework this session**, worth inheriting: three wrong
> conclusions came from grepping a load-bearing document instead of reading it, each one chasing
> something the file had already settled. `SYSTEM.md` now separates **routing** (grep is fine) from
> **relying** (read the whole file), and the project `CLAUDE.md` lists what must be read in full.

> ## Handoff, 2026-08-24 — production started; the binding constraint is not what anyone expected
>
> **Where things stand.** Six finite checkpoints exist (was zero on 08-20). Four are cells built
> by [`scripts/run_cell.sh`](../scripts/run_cell.sh) with per-episode verified provenance:
> `drqv2` seeds 6 and 7, `svea` seed 1, `drq` seed 1. **Only one of them yields a retention
> number** — the rest never learned the task well enough for a denominator to mean anything
> ([C55](CONSTRUCTION.md#c55)).
>
> **The constraint that governs planning.** The window that yields a *measurable* cell is narrower
> than the one that yields a *finite* checkpoint. Below ~50k frames most baselines have no skill to
> retain; both runs that reached 120k diverged to NaN ([C57](CONSTRUCTION.md#c57)); checkpoints only
> exist at all past 50k ([C60](CONSTRUCTION.md#c60)). And **a run cannot be triaged from its return
> curve** — `drqv2` seed 7 ends training at 169.8 looking healthy and evaluates to 0/200 successes,
> because robosuite's Door pays shaping reward to a policy that never opens the door. Budget per
> cell is *run + grid*, and seeds are needed to **obtain** a cell, not to error-bar one.
>
> **Compute, verified this session and not what the docs said.** Yandex DataSphere is **alive**
> under a project the docs did not have: **`bt12q57tmrs03pnt8drc`** (`arsen4ikvar-datasphere-project`);
> the recorded `bt14qn4u9t3n09nfjoqu` is dead (403). Needs `GRPC_DNS_RESOLVER=native`, and its CLI
> buries output under gRPC fork noise on stderr. **Kaggle cannot run cells at all** — cp312 admits
> no mujoco 2.x, so `MjModel.tex_rgb` is missing and only the `train` regime is reachable
> ([C29](CONSTRUCTION.md#c29)). Routing: [`compute.md`](compute.md) →
> `../../docs/compute-yandex-datasphere.md`.
>
> **Locally: at most two concurrent rendering runs.** Three sent swap to 10.1 GB of 11.3 with 54M
> swapouts; the runs' own RSS was 2.2 GB — it is *wired* GPU memory, not resident. Recorded in
> `../../docs/local-envs.md`, with the check to run *before* starting a third.
>
> **Per-baseline blockers, all recorded:** `ctrl` and `ppg` cannot checkpoint as published
> ([C60](CONSTRUCTION.md#c60)); `curl` cannot run under the MPS shim and needs CUDA; `drq` runs only
> with `use_tb=False`, a regression I introduced by turning TensorBoard on for R7
> ([INTEGRATION-DELTA](INTEGRATION-DELTA.md), P-TB); `sgqn` is ~11h per cell locally.
>
> **Late additions, 2026-08-24 ~16:00 — read these, they change readings above.**
>
> - **[C62](CONSTRUCTION.md#c62) is the most consequential thing here.** Door's reward is an
>   `if/elif`: an open door pays exactly 1.0 and *no* shaping, everything else pays ≤0.5/step, so
>   **250 is the maximum return with the door never opening**. Any mean above 250 proves a success.
>   Our 79–115 plateaus are 32–46% of a ceiling reachable without the hinge moving. And the
>   comparison we had never made: their Door Easy `drqv2` is **3.6**; ours at 50k **eval-easy** is
>   **3.49**. We had been comparing our *train*-regime 115 against their *Easy*-regime 3.6 — a
>   category error. Bears directly on [C48](CONSTRUCTION.md#c48).
> - **Open anomaly, not explained:** `snapshot_100k_frames__eval-easy` pools 131.05 with 63/200
>   successes and 43 episodes >250, against their published 3.6 at 12× the budget. So *"we are
>   under-trained relative to them"* is **not** what the evidence says. Investigate before using
>   either number to explain the other.
> - **[INTEGRATION-DELTA](INTEGRATION-DELTA.md)'s per-baseline tag counts are for the superseded
>   `rlgen/` port, not the clones.** Audited `alda`+`idaac` by `git diff` against their PRISTINE
>   commits: **36 authored hunks, 4 tagged, 89% missing**. `M4` (`init_log_std=-1.0`) likewise
>   describes the port only — clone-era `idaac`/`ibac_sni`/`ctrl` all init at 0.0.
> - **Three audit flags are recorded there but not yet register entries**, and each needs a
>   decision: `idaac`'s `_LevelSeed` comment asserts a claim [C49](CONSTRUCTION.md#c49) measured
>   false, with no tag in the code pointing at it; `idaac`'s eval env reuses training env #0's seed
>   *and* `scene_id=0`, so held-out-ness rests entirely on colour/lighting randomisation; and
>   `model.py:379-383` now forwards `num_actions` into `PolicyResNetBase`, which upstream never
>   did — inert for Procgen only because every game has 15 actions, and there is no assert.
>
> **Later, 2026-08-24 — the 100k anomaly above is CLOSED, and three entries were added.**
>
> - **The "open anomaly" two bullets up is [C54](CONSTRUCTION.md#c54), not a new finding.** Do not
>   re-investigate it. The 131.05 is high because that checkpoint's `eval-easy` grid is measuring a
>   regime it plausibly *trained* in. Folded into [C37](CONSTRUCTION.md#c37), which now also carries
>   the mechanism: their published 3.6 is **1.4% of the shaping ceiling of 250**, so their run never
>   approached the handle, and our curve *crosses* their number between 50k (3.49) and 100k (131.05).
> - **[C65](CONSTRUCTION.md#c65) — the general screen. Use it before believing any retention
>   number.** All eight grids split by the *sign* of the train→eval change: four fresh cells below 1
>   (0.030–0.877), three archived checkpoints above (1.887–2.786), **random policy at 1.02** as the
>   control. `regime_retention_report.py` now refuses an above-1 ratio outright.
>   **The trap, which cost real time: this is the ALL-SCENE pooled ratio, not the POOLED retention
>   the same tool prints.** They disagree in sign — `snapshot_100k_frames` is 2.513 all-scene and
>   **0.010** on the guarded subset. My first implementation keyed the alarm to the guarded number
>   and was silent on all three contaminated checkpoints while passing its own tests.
> - **[C63](CONSTRUCTION.md#c63) — do not quote C54's `−0.887` distance↔return correlation.** It
>   reads **−0.374** one checkpoint later on the same run, with identical distances. Its falsifier
>   was run: the collapse is checkpoint-specific, not regime-specific, so the correlation is a
>   signature of an *under-trained* policy. C54's conclusion is untouched — it rests on the two
>   extremes, which both reproduce at 100k.
> - **[C64](CONSTRUCTION.md#c64) — `sgqn` does not run at the hyperparameters `FAITHFULNESS.md`
>   says.** That file's "ours" column (`aux_lr` 0.3 / quantile 0.95) describes the retired `rlgen/`
>   port. The clone reads upstream hydra → `cfgs/sgqn_config.yaml:54,56` → **1e-4 / 0.93**, and the
>   8e-5 fix sits in `configs/vigen.yaml:82`, which no run reaches. Needs your decision: upstream's
>   shipped value (the null) or the paper's Table 6. **Not corrected in the doc yet, deliberately** —
>   writing "ours = 1e-4" would fossilise one option as decided.
>
> **Owner decisions taken 2026-08-26 — these change the contract, not just the register.**
>
> - **[`TASK.md`](TASK.md) R3 is relaxed** from *"evaluation code must be IDENTICAL"* to
>   **"metrics fully on the same axes and directly comparable"**. This amends a **verbatim
>   supervisor line** and is **not yet agreed by DZ**. It dissolves [C53](CONSTRUCTION.md#c53)
>   (resolved) and makes per-baseline evaluators contract-compliant.
> - **R3 is still NOT MET.** Seven per-baseline parsers read numbers; they do not *demonstrate*
>   one axis. [`COMPARABILITY_CONTRACT.md`](COMPARABILITY_CONTRACT.md)'s per-baseline audit is the
>   work. `scripts/requirements.py` still grades **key-identity**, so its "NOT MET" is right for the
>   wrong reason — rewriting that predicate is the concrete next step.
> - **The metric model is TIERED**, and this is the intended design, not a concession: **common**
>   (return, success — all twelve) / **family** (`explained_variance`, `clip_fraction`, contrastive
>   loss, continuous-head entropy) / **individual**. It is [C28](CONSTRUCTION.md#c28) +
>   [`PART2-METRIC-INVENTORY.md`](PART2-METRIC-INVENTORY.md) §6. **A test asserting one global
>   canonical tag set encodes the wrong model** — R5 currently asks for roughly that, and R5 is
>   deferred until the table's shape is settled.
> - **[C72](CONSTRUCTION.md#c72): the null is option 3** — report the five natives, state the seven
>   have no comparable endpoint. Adaptation is permitted, hermetic-first, but the bar is *"confidently
>   declare same-axis based on all circumstances that take effect, not only name some reasons why
>   it'd be compatible"*. **Pricing option 1 means seven evaluators PLUS per-baseline comparability
>   evidence; the second half is the larger one.**
> - **Compute: Docker is prior art, not new work.** `nvidia/cuda:12.2.2-runtime-ubuntu22.04` is
>   already used by `datasphere/cfg-probe.yaml:18`; `gen-rebuttal` uses `cudagl` and `opengl`
>   variants. All are py≤3.11, so `mujoco==2.3.7` installs from a wheel and a container matches this
>   machine. The old *"a custom image is not worth building"* note was a DataSphere **speed**
>   argument and does not apply.
> - **Run state:** the `svea` 100k run died on `ENOSPC` (see below) leaving a valid
>   `_global_step=50000` checkpoint. `results/regime-retention-c69/` holds 14 deterministic grids.
>
> **Docs read IN FULL as of 2026-08-26** (so the next session need not re-verify, and knows what is
> *not* covered): `SYSTEM.md`, `PROJECT-INDEX.md`, `CLAUDE.md`, `RUNNABLE-ORIGINALS.md`,
> `RESEARCH-FRAME.md`, most of `TASK.md`. **Not yet read whole and load-bearing:**
> `COMPARABILITY_CONTRACT.md` (now carries R3), `RIGOR.md`, `FAITHFULNESS.md` §4.

> **[C75](CONSTRUCTION.md#c75) — the class, and the thing most worth carrying into a new session.**
> Twelve methods formulated for three other domains (DMControl, DMControl-GB, Procgen) are being run
> on a fourth. When a method's formulation is bound to a quantity the target changes — an action
> distribution, a resolution, a control rate, a notion of "instance", a reward scale — **nothing
> errors; the meaning shifts silently.** Seven members are already recorded
> ([C2](CONSTRUCTION.md#c2), [C3](CONSTRUCTION.md#c3), [C5](CONSTRUCTION.md#c5),
> [C6](CONSTRUCTION.md#c6), [C61](CONSTRUCTION.md#c61), [C74](CONSTRUCTION.md#c74),
> [C50](CONSTRUCTION.md#c50)) and **every one was stumbled on rather than derived.**
>
> C75 lists five axes that have **not** been checked — rate, episode structure, reward scale, batch
> semantics, and the hyperparameter face `PREMISES.md` P6 already names. If you are looking for
> something to find, look there first; it is the only place in this project with a *predicted*
> yield rather than a hoped-for one.
>
> **[C74](CONSTRUCTION.md#c74)** is its sharpest member: six baselines carry a mechanism that needs
> to tell instances apart, on a target where only `idaac`'s has been *measured* (absent, at chance).
> The other five are reasoned, not checked, and each needs a different probe.

> **[C69](CONSTRUCTION.md#c69) + [C70](CONSTRUCTION.md#c70) — READ FIRST, it invalidates a conclusion from the day before and
> changes what every pre-2026-08-25 grid means.** `UniformRandomSampler`
> (`third_party/robosuite/robosuite/utils/placement_samplers.py:167,183,196,198`) places the door
> from **bare global `np.random`** — it holds no `random_state`. The `seed` we thread through
> `robo_make` reaches `VGBWrapper.random_state`, which drives **textures/colour/lighting only**.
> Upstream's `train.py:47` and `eval.py:54` seed global numpy via `set_seed_everywhere`;
> **`scripts/eval_across_scenes.py` never did.** Measured: the door moved ~1.6 cm across three
> processes at identical `seed=0`. Fixed by one line in `run_scene`, mutation-verified.
>
> - **[C67](CONSTRUCTION.md#c67)'s "evaluation-noise floor" is WITHDRAWN.** The 47% success-count
>   spread was this bug, not irreducible noise. Do not plan seed counts around it.
> - **Grids now carry `placement_seeded: true`**; the retention report flags any grid lacking it as
>   not reproducible. *Caveat:* `results/reseed-check/100k__eval-easy__reseeded_A.json` **is**
>   reseeded but predates the marker, so its absence there is not evidence of the defect.
> - **Second consequence, verified:** evaluation resets draw from the *same* global stream as
>   training resets, so `seed` names a training run only for a **fixed eval schedule**. P14 changed
>   the eval loop from one env to ten, so pre-P14 and post-P14 runs at "the same seed" sit on
>   different placement streams.
> - **[C70](CONSTRUCTION.md#c70): seeding alone was NOT enough.** Two reseeded runs of one grid still
>   disagreed — scene 1, episodes 12–14, one reading **372.34** against **6.01**, with episodes 0–11
>   and 15–19 bit-identical. Not the RNG (the re-convergence proves the stream is intact), not
>   threads (`set_num_threads(1)` still diverges), not rendering (frame md5s match across
>   processes). It is **torch's runtime CPU-kernel selection**, ~1e-7 in the actor's output, which
>   Door's `hinge_qpos > 0.3` threshold turns into a whole episode. Fixed by
>   `torch.use_deterministic_algorithms(True)` in `run_scene`; three processes then agree exactly.
>   **On this task there is no negligible numerical difference** — retire that argument.
> - **The missing instrument now exists**: `tests/test_eval_path_determinism.py` runs the evaluator
>   in two processes and asserts identical episodes. `audit_seed_control.py` is *static* and its own
>   docstring disclaims exactly this; `probe_determinism.py` covers **training** only. Nobody had
>   ever pointed a determinism check at our own evaluator.
>
> **[C68](CONSTRUCTION.md#c68) — a planning rule, read this before choosing any budget.
> On the robosuite path a snapshot is written ONLY at exact multiples of 50 000 steps, and there is
> NO end-of-run save.** `train.py:268-269` looks like an every-eval save but sits inside
> **`habi_eval()`** — the habitat path, never called here. The robosuite path calls `eval()`
> (`train.py:143`), which saves nothing; the only write is `train.py:309-310`. So **a budget that
> is not a multiple of 50k silently discards its tail**: the archived 120k run's `snapshot.pt`
> reports `_global_step=100000`, losing 19 500 frames including its NaN collapse, and every `55000`
> cell yields a `50000` checkpoint — which is why `cell55k` names a budget its file does not hold.
> `save_snapshot()` also always writes the one name `snapshot.pt`; `snapshot_50k_frames.pt` and
> `snapshot_100k_frames.pt` are **our** copies, not upstream's.
>
> **Kaggle is NOT exhausted — it was an undated assumption.** `26.12h` of `30.00h` used, **3.88h
> left, refreshing 2026-08-29 00:00:00**, account `arsen4ikvar`. `train` regime is usable; **eval
> regimes are not** (needs mujoco 2.x for `MjModel.tex_rgb`, no cp312 wheel, Kaggle is py3.12 —
> [C29](CONSTRUCTION.md#c29)). GL/EGL is *not* the blocker: RAD trained end-to-end on a real T4. Use
> `machine_shape: NvidiaTeslaT4`; `enable_gpu` alone gives a P100 that Kaggle's torch cannot use.
> `kaggle quota` is broken client-side — recipe and root cause in
> [`compute.md`](compute.md) and `../../docs/compute-kaggle.md`. **The `kaggle` package lives in
> `/Users/a2mogus/anaconda3/bin/python`, not in either project venv.**
>
> **A 100k run died on `OSError: [Errno 28] No space left on device`, 2026-08-26.** The volume was
> at **96% (34 GB free)** and this project accounts for only **7.3 GB** of it, so the cause was
> **outside the project** — the owner's diagnosis is swap pressure from another parallel ML run on
> the same machine. This is the disk-side twin of the two-concurrent-render cap already recorded
> below.
>
> **The rule: do NOT clean shared or pre-existing state.** Not caches you did not create, not
> `__pycache__`, not old runs. Measure (`df -h`, `sysctl vm.swapusage`, `du -sh` on the project),
> report, propose — and stop. A resource symptom seen from inside one project is usually caused by
> something outside it, so cleaning from here destroys local evidence without touching the cause.
>
> **What saved the run is worth knowing**: [C68](CONSTRUCTION.md#c68)'s cadence means a native
> training run that dies partway still leaves the last 50k-multiple checkpoint. The dead `svea`
> 100k run left a valid `_global_step=50000` snapshot. **Check for one before assuming a crashed
> run produced nothing.**
>
> **Two shell traps on this machine, hit twice each:** `/usr/bin/cp` and `/usr/bin/cat` **do not
> exist** — use `/bin/cp`, `/bin/cat`. A backup-then-restore built on `/usr/bin/cp` fails silently
> and leaves the mutated file in place, which is how a red-green check nearly left `PROJECT-INDEX.md`
> corrupted. Also `pytest-timeout` is not installed, so `--timeout` is rejected.
>
> **New: [`docs/dated/`](dated/README.md) for point-in-time documents.** Snapshots get **one** index
> row for the folder and none individually, so the index stops growing per report. Two live there
> now — an adversarial review of the claim-bearing docs (7 findings, C64 came from it) and an
> outside-reviewer brief. A test requires each file to carry `Written YYYY-MM-DD` **in its prose**,
> recursively, because a filename does not survive being pasted out of.
> - **`FAITHFULNESS.md` §5 is current again** (items 9–11 added, four findings excluded *with
>   stated reasons*). Its open item 4 — **`nstep` per family** — has now survived **three**
>   re-triages unchanged; a one-line decision affecting seven baselines that keeps being outlived
>   by findings which arrived later and got resolved first.
>
> **Operational facts that cost time to rediscover:**
>
> - Use **`datasphere/`** (project root), *not* `compute/datasphere/` — the latter is superseded
>   and now says so. Root version verified 2026-08-10 with a protocol hash equal to the laptop's,
>   uses **`gt4i.1`** (interruptible, cheaper) for training, and pins torch via
>   `--index-url .../cu121` because an unpinned torch pulls a CUDA-13 wheel the T4 driver cannot
>   use. Project id **`bt12q57tmrs03pnt8drc`**.
> - **Three CLI schema tightenings are new since 08-10** and will hit the root setup too: `type`
>   is mandatory in the env block; `main.py` must have the `__main__` guard (**load-bearing** —
>   the CLI *imports* the file, so top-level job code would run locally); and full-line comments
>   in `requirements.txt` are rejected.
> - **A custom Docker image is not worth building** — measured: pip is 285 s, and for a job that
>   returns a retention number (train + grid ≈ 56 min) that is **8.5%**. Only worth revisiting if
>   many *short* jobs become the pattern, where it is 27.7%.
> - **Cap local rendering runs at two** (`../../docs/local-envs.md`) and check
>   `sysctl vm.swapusage` *before* starting a third.
>
> **The failure mode to guard against, evidenced FOUR times this week.** Re-deriving something the
> register already records: the chance floor ([C17](CONSTRUCTION.md#c17) had measured it),
> `curl`'s MPS failure ([C52](CONSTRUCTION.md#c52) names the exact error string), and the
> collector's layout assumption — twice. **Before investigating any failure, grep the register for
> its error string.** That single habit would have saved more time this week than any instrument
> added to it.
>
> ## Handoff, 2026-08-17 — THE APPROACH CHANGED. Read this, then `docs/RUNNABLE-ORIGINALS.md`.
>
> **The null is now the original repository, cloned, running its own `train.py`.** Duplication
> across baselines is free; any *join* is work and carries the burden of proof. The port under
> `rlgen/algos/` is **superseded** — it still exists and its provenance facts are still true, but
> it is not the deliverable. `scripts/state.py` reports on it and says so in its first line of
> output; `scripts/deviations.py` is the ledger that matters now.
>
> **Where things stand.** All twelve baselines train on RL-ViGen robosuite by running their own
> entry points. 34 files, +917/−125 (602 non-comment) across six clones, plus RL-ViGen patches
> P1–P20 (no P16 — the ids are not contiguous). Part 2 (metrics on the same axes) is open, with an inventory and six findings in
> `docs/PART2-METRIC-INVENTORY.md`; success rate is delivered for all twelve.
>
> **The section below is the 2026-08-16 handoff, kept as-is.** It describes the port-era state and
> is left unedited on purpose: it is accurate about what happened then, and rewriting a superseded
> handoff to look current is exactly the failure `docs/SYSTEM.md` opens with. Read it as history.

> ## Handoff, 2026-08-16 (historical) — the port era
>
> **This file is not ground truth. It is the best current draft of a practice, and it has been
> wrong in specific, recorded ways** — it dropped three of `DISCIPLINE_IMPOSED`'s four Anchors; it
> re-derived a pipeline that already existed in that file's Appendix A instead of starting from it;
> it asserted a singular "one legitimate sink" while diagnosing exactly that error elsewhere; it
> had a self-contradiction between a prerequisite and §3d for one commit. Every one of those was
> caught by someone checking the artifact, not by the document defending itself.
>
> **So: live-correct it.** If a rule here disagrees with what the code, the reference, or the
> territory actually shows — the territory wins, amend the rule in place with the case that broke
> it (§8's loop), and date it. Deviating in a case this file does not fit is correct behaviour,
> not violation. Treat every claim here as argument-shaped (§5) until re-derived. The standard is
> `porting-directive.md`; this is procedure, and procedure is falsifiable.
>
> **Facts first, and do not restate them here:**
> `python scripts/state.py` — base terms with the working tree actually opened, and measured
> descent per reference. `python scripts/check_citations.py` — 427 citations, 0 broken as of
> 2026-08-16. `python scripts/greenmark.py` — whether the last green suite run still covers this
> tree. All three are floors under the *mechanical* half only; each states in its own docstring
> what it structurally cannot see, and those blind spots are where everything that mattered
> actually lived.
>
> **Done since the last handoff:** `ibac_sni` rebuilt base-first **and smoke-run end to end**
> (3,000 frames, 11 updates, exit 0 — a green suite over a replaced policy API is not a training
> loop). `ppg` rebuilt base-first, descent 0% -> 37%, carrying **the project's first real T1**:
> both sides PyTorch, so a weight transplant works, plus an **init-parity** check because T1 is
> structurally blind to initialisation (a mutation walked straight through it — STEP-ZERO's T1
> definition is amended in place to say so). `alda` audited and its 0% flag **withdrawn**: it is a
> renamed reimplementation of the reference's own `AssociativeLatent` main path, the `ctrl`
> situation rather than the `ibac_sni` one — deliberately not rebuilt.
>
> **Start here: `idaac`, base-first from `ext/idaac` (`rraileanu/idaac` @ `2fe3020`).** Verified
> first-party, clean tree. It settles the encoder, storage and the PPO/DAAC/IDAAC losses — but
> **not the policy head**: `ppo_daac_idaac/distributions.py` ships only `Categorical`. Related
> open item: `[IK]`, the reference `idaac`'s continuous head cites as what it deviates *from*, is
> **not on this disk**.
>
> **Then, in order:** the emission inventory (deferred until the modules stopped changing — they
> now have), which `COMPARABILITY_CONTRACT.md`'s head names as the open item under a framework
> whose null is **non-comparability**; `ctrl`'s tier past the encoder; and the joint K layer,
> which no baseline can be declared ready for alone.
>
> **Distrust first:** `docs/FAITHFULNESS.md` §ppg is stale (it still says this repo has no
> separate value network; that stopped being true 2026-08-14). Four of my own claims were
> falsified within an hour of writing them today — all by one command I had not run.
>
> **The null is reset to the imported state** (gate 1). Keeping any line of an existing module is
> a decision to argue and record, not a default earned by the code existing and passing tests.
>
> **This paragraph used to name that base wrongly, in three ways at once, and the gates below
> caught all three on first contact with the artifact — before any code was written.** It said the
> base was `~/Downloads/train-procgen-pytorch_example/`, "clean, remote-verified", with a 5-file
> delta. In fact: the remote *is* verified but the **working tree is dirty** (` M agents/ppo.py`,
> ` M train.py`, untracked `experiments/`) — *remote-verified* had been read as
> *working-tree-clean*; the modified `agents/ppo.py` is an unrelated noise-injection experiment
> that **does not even parse**; and the delta is **4 files, not 5**, because DZ's `agents/ppo.py`
> is byte-identical to upstream and only looked modified when diffed against the dirty tree.
> **Corrected base term: `joonleesky/train-procgen-pytorch` @ `1678e4a`, extracted with
> `git show`** — reachable, parses, genuinely pristine.
>
> **And a fourth thing, which changes the shape of the work rather than just a path:** DZ's
> `ppo_ibac.py`/`policy_ibac.py` were about to be treated as the reference. They are a
> **Construction** — a re-derivation from the paper. The authors' own release
> (`ext/IBAC-SNI`, `microsoft/IBAC-SNI` @ `6b3a58b`) is on this disk and ships **its own PyTorch
> bottleneck** (`torch_rl/bottleneck.py`), so the usual "the only PyTorch version available wins"
> argument does not apply. DZ's delta supplies the **wiring**; `ext/IBAC-SNI` supplies the
> **semantics**. Full evidence: `docs/REGISTER.md`, 2026-08-16.
>
> **Ordering correction, made against my own earlier claim in this same session:** I argued the
> contract/K layer should come first because it would give the rebuild a conformance target. That
> was wrong — only the *constructive* contract layer yields a test, and that one is deliberately
> deferred (§11.4); the *descriptive* pass produces prose, which is no target at all. So `ibac_sni`
> first. Recorded rather than silently reversed.

## Context, definitions, stance — read before the gates; the gates are unusable without it

**The situation.** Twelve independently-authored RL algorithms, ported onto one benchmark
(RL-ViGen robosuite, Door/Lift) so their generalization numbers sit on one axis. Three frameworks,
two action spaces, two benchmark lineages, twelve separate papers with twelve separate references.
The target is fixed and known in advance: 84×84×9 uint8 observations, 7-DoF continuous actions,
horizon 500, `action_repeat=1`, `num_envs=1`, every episode ending by truncation.

**The deliverable is not working code.** It is a defensible claim that no baseline was handicapped
relative to a minimal faithful integration of its own reference. Code that runs and produces
plausible numbers is the *easy* part and is not the thing being delivered.

**Definitions the gates depend on:**

- **base term** — computed from facts, never chosen: *reachable* (on disk ∧ executes here),
  *unreachable-framework* (on disk ∧ cannot execute here), *unreachable-nonexistent* (no such
  reference exists anywhere).
- **transcription / adaptation / construction** — what settles a file's form: one reference at a
  stated commit; a transcription plus a named changed surface; or nothing settling it. Writing an
  equivalent from having read the reference is a **construction even when the result is faithful**.
- **T1–T4** — forward agreement under transplanted weights; single-step gradient agreement;
  distributional agreement on the reference's own domain; structural accounting only. T4 is a
  permitted outcome; undeclared is not.

  **T1 has a structural blind spot, and it is not a nuance — amended 2026-08-16 after a mutation
  walked straight through it.** Transplanting weights *overwrites the initialisation*, so T1
  verifies the forward arithmetic and is blind, by construction, to how the network you actually
  start training was built. Caught red-green on `ppg`: mutating `CnnDownStack.firstconv` to take
  the per-stack `scale` (the reference gives it the default; only the residual blocks get the
  scale) left the transplant test **green**. Initialisation is a real part of a method — PPG's
  normalized-fan-in scheme is nothing like the xavier its neighbour uses — so where the reference
  is executable, pair T1 with an **init-parity** check: construct both under one seed and compare
  the tensors. Cheap, and it catches a class T1 cannot see. Where it is *not* executable, say the
  tier is T1-forward-only rather than letting "T1" imply more than it does.
- **uniform vs selective failure** — whether a defect in a shared thing lands identically on
  everything it serves (a systematic offset, visible) or differently per consumer (invisible).
- **mechanical vs argument-shaped claim** — a remote, a commit, a formula read from a file, versus
  a justification, a summary, or a prior conclusion.
- **N / M / K** — the scoped edits over a copied base; the minimal adaptations where the target
  differs from the reference's setting; the reporting/contract additions that put all twelve on one
  axis. Readiness in **K is joint** and cannot be established for one baseline alone.

**Stance — the part that is a posture, not a derivation:**

- **Fidelity beats convenience, every time.** A slower or uglier construction that matches its
  reference beats an elegant one that does not.
- **Disjoint by default.** Sharing is earned per-component against evidence, never assumed viable
  pending disproof. Integration pressure is absorbed at the contract layer and nowhere else.
- **The reference is authoritative about the algorithm, never about the measurement.** Its
  normalizer stays; its logging does not.
- **A finding outranks the plan.** Step N dictates step N+1 — a discovery halts what was scheduled,
  and that is the process working rather than a deviation to minimise.
- **Code is cheap; information is everything.** Discarding working, tested code whose provenance is
  wrong is a normal move, not a loss.
- **Honest exhaustion beats manufactured completeness.** Spending the budget with the trace still
  open is a result: cap the tier, name the gap, report it there.
- **Correctness belongs at the point where the edit meets the original — not downstream of it.**
  An element whose correctness can only be shown *after* it is written has already cost what it
  was going to cost, and a passing test records that the leak has not been seen yet rather than
  that it is absent. Write the edit so its correctness is visible against the reference; then test
  it anyway, because that argument is itself a claim. This is not "never write what you cannot
  derive" — some things have no original to derive from, and naming that gap is the correct move.

## The gates — the operative part; everything below is evidence for these

Seven restrictions. **The rest of this file is not additional rules — it is the instances that
produced these, kept so you can tell when a gate misfires.** If you internalise the gates you can
re-derive the practice; if a gate and a situation disagree, the situation is evidence, so amend the
gate and date it.

0. **Before gate 1 can be answered, open the tree.** *(Added 2026-08-16. There are steps before
   step zero; this is one.)* A base term is not a fact until the working tree has been
   **looked at**, not just identified: `git status --porcelain` (working tree, not `git remote -v`
   alone), every file parsed, the commit recorded. `remote-verified` and `working-tree-clean` are
   different properties and only the first was ever checked — the tree recorded as this project's
   `ibac_sni` base is dirty and its `ppo.py` raises `SyntaxError`. **That claim was written the
   same day it was found wrong** (`git log -S`, both files, 2026-08-16), so this is not decay and
   the fix is not to distrust the standard — it is to add the step whose absence caused it.
   Diagnosis discipline in general: "we skipped a step" and "the guidance is wrong" are different
   failures, and reaching for the second when the first explains the evidence licenses rewriting
   things that are not implicated.

1. **No file is written for a baseline until its base term is stated as a *fact*** — is the
   reference on disk, does it execute in this repo — and **if it is reachable, the file starts as a
   copy.** Cost of vendoring is a note, never a reclassification.

   **Copy the FILE, then justify each removal — not "copy what the module needs".**
   *(Added 2026-08-16.)* A filter is unavoidable: a hermetic module cannot absorb a whole repo,
   and the launcher, logging and env layers really are replaced by the harness. But its correct
   form is **"remove what the harness replaces, keep everything algorithmic"** — a filter between
   *layers*, applied at *file* granularity, and recorded. Applied instead by feel at *class*
   granularity inside a file, it stops being a protocol step and becomes a stream of silent
   authored decisions, which is backwards: **duplication is the null and every omission carries
   the burden of proof.** The original runs; copying costs nothing.

   The failure this records: `idaac`'s `OrderDiscriminator` was hand-written from a docstring
   that correctly *described* `LinearOrderClassifier` — ten lines of the reference, in a file
   already vendored into this repo. Re-derivation where a copy was available, committed inside a
   base-first rebuild. `NNBase` went the same way, inlined as a property on three classes because
   it looked like avoidable duplication.

   **The null is the imported state, and preserving existing code is the deviation.**
   *(Sharpened 2026-08-16, and it inverts the burden of proof.)* When a module already exists and
   a reachable base is found, the default is not "rebuild informed by what is there" — it is
   **reset: the module *is* the base, plus edits.** Every line that survives from a prior
   construction is a **decision**, argued and recorded in `docs/INTEGRATION-DELTA.md`, not a
   default kept because it exists and passes tests. Sometimes that decision is right: a real
   defect found against the original is information worth carrying (it is *cheaper* to keep the
   finding than to rediscover it). But it must be carried as a **stated back-merge with a reason**,
   never as code silently left in place. Written the weak way round, "discard unless useful" reads
   as "keep unless clearly harmful", and the thing being preserved is exactly the artifact whose
   provenance is in question.
2. **No tier is claimed without a runnable artifact that produces it.** "Verified" with no pytest
   node that actually collects is not a claim.
3. **Nothing is shared between baselines unless its failure would be *uniform* across everything
   it serves.** Uniform wrongness shows up as a systematic offset; selective wrongness shows up as
   nothing.
4. **No inherited claim is used as settled.** Docs, prior sessions, and my own earlier output are
   argument-shaped: re-derive when load-bearing. Where a record and the artifact disagree, the
   artifact wins.

   **Extended 2026-08-16: a claim about what you just did is not privileged either.** The gate was
   written for *inherited* claims and missed the shorter loop. Two defects in one rebuild came
   from the same place: a docstring stating a verified component had been "carried forward
   verbatim" when it had been retyped from its own description (dropping an episode reset, so a
   discounted return accumulated across every boundary), and a note stating the rebuild closed a
   gap the discarded module had already closed. Both were written minutes after the action they
   described, by the one who took it. **Intent is not evidence.** If a claim is about code —
   yours, five minutes old, in front of you — it is checkable by one command, and the cost of
   that command is always lower than the cost of the claim being wrong in a document that outlives
   the session. `git show` and `diff` are the two that would have caught these.
5. **No "done" without its scope stated** — what it covers and what it does not. Readiness that is
   *joint* (the reported-metric axis across twelve) is never claimed per-baseline.
6. **No finding is held in context only.** Record when noticed — dated, cited — before it is
   repaired or understood.
7. **No "nothing left to check" without a breadth pass** — enumerate the whole category rather than
   searching for what you expect to find.

What each generates, so the derivation is checkable rather than asserted: **1** → the inventory,
reading the original, copy-first, minimal scoped edits (§§3–4b). **2** → weight-transplant parity,
red-green, mutation testing (§6, §9). **3** → golden-vs-reverse-path, why the harness is legitimate
and a shared PPO core was not (§10). **4** → claim shape, compaction survival, map-vs-territory
(§§2, 5). **5** → the observation→artifact spectrum, why "9 of 12 correct" was malformed (§7).
**6** → the register and the refinement loop (§8). **7** → the discovery instruments and their
honest yields (§8).

**Status: standing practice + open questions. Not a mechanism.** Nothing here is enforced by a
test yet, deliberately — description precedes enforcement (§11.4), and §6 states exactly which
parts a mechanism could ever catch. `porting-directive.md`
(workspace root) is the standard and wins on any disagreement; this file is the *procedure* that
produces artifacts satisfying it, plus the claim-shaping rules that keep the procedure's results
legible after a context compaction.

Written 2026-08-16 after a review that found five same-shaped failures in one session.

**Where this sits among the other documents.** [`porting-directive.md`](../../../docs/porting-directive.md)
is the **standard** — properties the artifact and its claims must have; it deliberately specifies
outcomes, not procedures, and wins on any disagreement.
[`DISCIPLINE_IMPOSED.md`](DISCIPLINE_IMPOSED.md) is the **trace** — where a rule was first arrived
at and the instance that motivated it; session-scoped, so it is both over-specific in places and
gappy in others, and is the wrong artifact to operate from. **This file is the procedure**: what
to do, in what order, with the reasons attached so you can tell when a step does not apply. §4b
deliberately re-states three constraints that also live in `DISCIPLINE_IMPOSED`'s Anchors — that
is recovery into the operational doc, not a competing copy; where they differ, this file is the
one being maintained. Findings go to [`REGISTER.md`](REGISTER.md); argument-meaning decisions go to
[`DECISION_LOG.md`](DECISION_LOG.md); reference locations to
[`ORIGINAL_LOCATIONS.md`](ORIGINAL_LOCATIONS.md).

## 0. Routing — what to read at which decision point

Sections are organised by topic; this is the index by *decision*.

**It is an index, not a trigger, and the distinction matters.** For an agent with a large context
window, retrieval is not the bottleneck — this session is the proof: `porting-directive.md` was in
context, §0's *"before a file is written, name what it is"* had been read, and a construction was
still written where a copy was available. The rule did not fail to be *found*; it failed to
*activate*, because the question never surfaced as a decision while a build was in flow. No table
fixes that. What has actually fired reliably here is execution (a suite going red, twice, on
staleness nobody remembered to check) and external challenge (three of five findings). Docs
improve the *quality of judgement once consulted*; they do not cause consultation. Read this table
as making the decision points nameable, not as making them fire.

| You are about to… | Read | Because |
|---|---|---|
| start work on a baseline | §3, §4 | identity and base term decide construction order, and both are cheap to skip |
| write or modify a file | §4, §4b | is the base reachable; is this edit scoped, cited, and minimal |
| **introduce anything shared between two or more baselines** | **§10** | the golden path is visible at decision time and the reverse path is not; this is the section that exists to overcome that |
| record, assert, or document something | §5, §7 | mark where the claim sits on observation→artifact; do not promote a position it did not earn |
| resume after a context compaction | §5, §2, then `REGISTER.md` | compaction strips hedges — treat every inherited claim as argument-shaped until re-derived |
| decide how much rigour this deserves | §9 | the *kind* of step changes with budget, not just the amount |
| conclude that nothing is left to check | §8 | a checklist cannot cover unknown unknowns; these are the instruments that actually surfaced them |
| reconcile a doc that disagrees with the code | §2 | the territory wins; the record is what failed five times |
| act on a finding nobody has recorded | §8 loop, `REGISTER.md` | a rule without its motivating instance becomes overprescription later |

**What this document cannot decide for you.** Every rule here is stated with the instance that
motivated it, and that is deliberate: the instance is what lets you tell when the rule does not
apply. The calls below are *structurally* yours — no amount of further specification would move
them, and a version of this file that pretended otherwise would be overprescription:

- **Is this shared thing's failure uniform or selective?** (§10's test) — requires modelling how a
  defect would *manifest*, per consumer. The list in `porting-directive.md` §1 names instances, not
  the boundary.
- **How much of a dependency subgraph to vendor**, when the reference's file pulls in edges that
  are dead here. Copy-first says start from the base; it does not say where the base ends.
- **When the budget is spent** (§9's stopping rule) — "exhaustion is a result" only helps once you
  have judged that the trace is not closing.
- **Which claims are load-bearing** enough to carry §5's four fields. Applying them to everything
  is theatre; applying them to nothing is how the five failures in §2 happened.
- **Whether a repeat is the same failure shape** or a coincidence (§8). Only the second occurrence
  of a *shape* is evidence about the process.
- **Whether a match on a prohibition list is the real thing.** A shared `utils.py` of pure
  functions and a shared stateful `Learner` both "share code"; only one is the failure.

If a rule here and the situation in front of you disagree, the situation is the evidence — amend
the rule in place with the case that broke it (§8's loop). The standard is
`porting-directive.md`; this is procedure, and procedure is falsifiable.

---

## 1. Why step zero is the leverage point

Twelve baselines must report on one axis. That demand has to be absorbed somewhere, and there is
exactly **one legitimate *kind* of sink: the harness/contract layer.**

*Kind*, not count — this file committed the same assumed-topology error it diagnoses in §10a(c),
and it is corrected here rather than quietly. What must be common is the **reported metric axis**.
How many components sit below it — one harness, two (this project already runs `trainer.py` and
`trainer_onpolicy.py`, correctly, because on-policy and off-policy differ in loop shape), or more
along an axis nobody has needed yet — is **derived from what the baselines require, not decided in
advance**. Each component is legitimate on §10's test independently: uniform failure across
everything *it* serves.

If that sink is not defined before baselines are written, the pressure finds an illegitimate one —
a shared object *among* the baselines. Then the relation inverts: baseline #7 is fitted to the
shared thing rather than to its own reference, and every later baseline inherits decisions no
paper made. That is `onpolicy_ext.py`'s entire history. It was not a coding mistake; it was the
predictable consequence of integration pressure with no sanctioned sink.

**Step zero's product is therefore not knowledge about the twelve. It is the contract — so that
there is nothing else for the pressure to deform.**

## 2. The failure behind the failures

> The explore step is executed against **the record** instead of **the territory**.

Five instances, one session, five different documents:

| Claim, as recorded | Territory |
|---|---|
| `rad`: "not vendored; clone it if RAD's numbers ever matter" | clones in ten seconds; re-read three times, never tested |
| `alda`: "byte-identical to the audited port" | true of `agent.py`; `buffer.py` **does not exist**; `config.py` differs 37 lines |
| "Kaggle is exhausted" | undated, never re-checked; account demonstrably active |
| `ctrl/model.py`: "transcribed from Flax to PyTorch" | written *before* anything was transcribed; two structural bugs |
| my own completion ledger: "9 of 12 correct" | conflated a per-baseline property with a joint one |

Two of these produced a **missing artifact**; three produced a **wrong claim**; one produced a
**wrong construction**. Same root. `rad`-missing and `ppg`-rewritten-instead-of-copied are *the
same defect on two surfaces*, which is why "do step zero properly" is one fix and not two.

The framing that names it best (Shihipar, *Finding your unknowns*): **map vs territory.** Docs are
the map. The repos are the territory. Every failure above is a map read in place of a territory.

## 3. The per-baseline procedure

Run **per baseline**, before any file is written for it. Not once globally — the global version is
what produced a table that looked complete while `rad` was absent.

**Scope — full pass or targeted read.** These are not a checklist to run in full every time. Each
item below is indexed by *what it settles*, and you read the item whose question you actually
have. The **full pass** is warranted when starting a baseline, or when its base term is unknown or
being re-derived. A **targeted read** is correct when verifying one specific claim — re-reading all
six to answer "does this baseline normalize reward?" is waste, and treating the list as mandatory
is the overprescription this scoping note exists to prevent. What is *not* optional at either
scope: reading the artifact rather than a note about it (§2).

**Prerequisite, once per project — not per baseline.** The target is fixed and shared, so this is
read once and cited thereafter; re-deriving it twelve times is pure cost. RL-ViGen's env
constructor, its `eval.py`, and the protocol constants (10 scenes × 10 trials); robosuite's
horizon/termination semantics, which settle that *every* episode end here is a truncation; and the
pinned target: 84×84×9, 7-DoF, horizon 500, `action_repeat=1`, `num_envs=1`. Everything below
assumes this is already known — most adaptation surfaces (§ table in the interim report) are
derivable from it before any reference is opened.

**3a. Establish identity — from the artifact, never the folder name**
- `git remote -v`; record it
- `HEAD` hash + date; `git describe --tags`
- gap between HEAD date and paper date → drift risk
- **when there is no `.git`** — true of DZ's IBAC-SNI port, and of anything hand-delivered — say so
  explicitly rather than skipping the step: identity then rests on a diff against a *base whose*
  identity is verifiable (3c), and that substitution is itself the finding to record

**3b. Read the original**
- train entry point: the loss assembly and optimizer construction, not the whole file
- eval entry point — **or establish there is none** (a real finding: `ppg` and `ibac_sni`'s
  references have no eval mechanism at all, so this project's generalization question is one
  their authors' code never posed)
- policy head → action space; encoder → obs shape and where normalization happens
- buffer/rollout storage → transition alignment, discount handling, n-step
- argparse/config defaults → the hyperparameters that actually run, not the paper's table

**3c. Third-party ports**
- locate them; identify *their* base; **diff port against base** — that isolates someone else's
  already-scoped edits and hands you the N term for free (this is exactly what DZ's IBAC-SNI port
  over `joonleesky/train-procgen-pytorch` provides, and it sat unused for a session)

**3d. Blind-spot pass, per baseline**
Explicitly ask what would not occur to me here. This is the only instrument for *unknown knowns*
(rules so obvious to the person who holds them that they never get written — copy-first was one)
and *unknown unknowns* (`rad` being one clone away; a clean upstream sitting in `~/Downloads`).
Neither is reachable by re-reading documentation, by construction.

## 4. Base-term triage — computed from facts, not chosen

The classification decides construction **order**. It must not be a judgement call, because
judgement boundaries are where pressure lands: facing a costly vendoring, the cheap escape is not
dishonesty but *sincere reclassification*.

Record **facts**:

```
reference_on_disk      : bool     # does the path exist
reference_language     : str      # python / jax / tf
executes_in_this_repo  : bool     # can this repo import and run it
vendoring_cost_note    : str      # free text — a NOTE, never part of the classification
```

Derive the state:

| Derived state | Condition | Construction order |
|---|---|---|
| reachable | on disk ∧ executes here | **copy verbatim, then scoped edits.** Cost is a note, not an exemption |
| unreachable-framework | on disk ∧ ¬executes here | construction + declared tier substitution (e.g. T1 weight transplant) |
| unreachable-nonexistent | ¬on disk, and none exists anywhere | construction; scrutiny against the paper's stated method — no substitute possible |

Writing an equivalent implementation from having read the reference is a **construction even when
the result is faithful**, and is classified and justified as one. `porting-directive.md` §0 states
the outcome ("most of this work is transcription"); this is the order that produces it.

### 4b. The N edits — carried forward from `DISCIPLINE_IMPOSED` Anchors 1–3

**Recovered by a regression pass 2026-08-16**, which found that this document had restated Anchor
1's *"start with original"* while dropping the other three constraints it bundles. That omission
is itself an instance of §2: I read my own new document as covering the ground, instead of
checking it against the established one.

> **Read `DISCIPLINE_IMPOSED.md` Appendix A before treating this section as the procedure.**
> Found 2026-08-16 by reading that file in full rather than in fragments: its Appendix A already
> contains a seven-stage pipeline — *(0)* locate ground truth mechanically, *(1)* state the
> contract not the type, *(2)* enumerate every interaction site to a named trusted boundary,
> *(3)* surface every default sourced or `[OURS]`, *(4)* make the smallest edit stages 0–3
> license, *(5)* re-verify by red-green with the exact mutation re-applied, *(6)* record the
> semantic assumption once, dated. §3 and §4b here are substantially a **re-derivation of that
> pipeline**, written without consulting it — the same start-from-scratch-instead-of-from-the-
> existing-artifact failure this document exists to prevent, committed while writing it. Appendix A
> is the origin and is more complete on stages 1–3; genuinely new here are §4's facts-derived
> triage, §5 compaction, §7 the foundation spectrum, §8 discovery instruments, §9 budget tiers, and
> §10 golden/reverse path.

**Minimal edits.** Each edit over the copied base is individually scoped, individually cited, and
does one thing. No surrounding cleanup, no opportunistic refactor, no renaming for hygiene — the
directive's §3 is explicit that rewriting reference code for tidiness is divergence. The count of
edits is a reportable number: "base + 3 edits" is a claim a reader can check; "ported and cleaned
up" is not. Salvage-not-preserve when an architecture turns out wrong: keep the information,
discard the class hierarchy, rebuild minimally per baseline rather than patch the shared thing
further.

**Contracts of arguments.** Reading the reference means reading what each argument *means*, not
its type: is this reward normalized or raw; is this flag a count or a size; does this counter
include pre-training collection; are parallel environments aggregated; does this `done` mean
episode boundary or zero bootstrap. Python will let a float be a float wherever one is expected
and says nothing about which of these it is. Every such meaning that a new edit assumes, changes,
or fixes belongs in `DECISION_LOG.md` — and the same reading is what the descriptive contract pass
(open question 4) consists of. Concrete instance from this project: `num_mini_batch` as a *count*
passed positionally into a parameter expecting a *size*, which did not crash and silently ran 64
minibatches of 32 instead of 32 of 64.

**Contract ≠ code, and this is the version most easily missed** (from `DISCIPLINE_IMPOSED` §1,
recovered 2026-08-16): **byte-identical shared code can carry different effective contracts for
different callers**, because each caller silently relies on something the others never exercised.
Verifying a shared unit against caller A says nothing about a property caller B assumes. The
instance: `Learner.update()` was verified for IDAAC's own usage, while
`PPGLearner._auxiliary_phase()` read `storage.obs`/`storage.returns` *after* calling it — depending
on a **post-call state guarantee** IDAAC's own code and tests had no reason to exercise. Same
bytes, unverified new contract, invisible to "the base class already works." So when a new consumer
attaches to any shared code, the thing to check is **what it assumes about state after the call**,
not whether the code is the same.

**Default assumptions are load-bearing.** The defaults *we* choose — not the reference's — decide
numbers, and an unexamined one is a decision nobody made. `action_repeat` 4→1 silently quadruples
the replay ratio; a config field declared and never read (`normalize_reward = True` with no
implementation) reads as configured while doing nothing; a value inherited from a sibling project's
dataclass is a choice imported without its context. Every default is either sourced or marked
`[OURS]` with the reason — the directive's §2 makes an unsourced hyperparameter a build failure,
and this is the practice that satisfies it.

## 5. Claim shape — what compaction destroys

Compaction does not merely lose information. **It strips hedges**, because summarization optimizes
for assertion density. Qualifications are exactly what a summarizer drops as noise.

**Observed in this project, not hypothesized:** the CTRL episode-boundary finding was discovered
2026-08-13, lost across a compaction, and rediscovered 08-14 **wrong** — recorded as a divergence
from the reference when the reference has the identical property. The rediscovery came back *more
confident and less correct*. That is the mechanism, measured.

Consequences:

- **Prose does not survive.** Three paragraphs of careful qualification summarize to "we did X
  carefully." **Structured literals do** — `base_term = "reachable"` has no more-flattering
  adjacent phrasing.
- Every load-bearing claim carries four fields: **type · scope · method · date.**
  - *type* — mechanical (a remote, a commit, a formula read from a file: verify once, carries
    forward) vs argument-shaped (a docstring's justification, a prior conclusion, **my own output
    from earlier in the same session**: re-derive whenever load-bearing)
  - *scope* — what it covers. "CTRL is T1-verified" is false; "CTRL's Impala encoder is
    T1-verified at 84×84, concat mode" is true. Scope is the first thing a summary drops
  - *method* — how it was checked; "read it" and "ran it" are different claims
  - *date*
- **Typing buys selective re-derivation.** Re-verifying everything after a compaction is
  impossible; trusting everything is what happened. Type is what makes the middle policy possible.

## 6. What a mechanism could catch, and what it cannot

Honest boundary, so the mechanism is never read as broader coverage than it has.

**Catchable mechanically** (designed here, deliberately not built — see §11.4):
- a baseline with no provenance record at all
- a tier asserted with no runnable evidence node (`tier = "T1"` without a pytest node id that is
  actually collected)
- a baseline in the `reachable`-but-not-copied state
- growth of the violation list (no-new-debt), rather than a hard red that would sit permanently
  red and be normalized — which is exactly how a real GLFW failure survived a whole session of
  being "verified as unrelated"

**Not catchable, practice only:**
- prose claims in documents — four of this session's five failures. No test reads English
- a blind-spot pass that was skipped
- whether the reference was actually *read* rather than its docstring skimmed

**Design constraints learned adversarially:**
- the record lives on `BaselineSpec` in `registry.py` — the one place all 12 are enumerated, and
  the only home that covers the 5 baselines with no module of their own
- generated status page + a `--check`, reusing the pattern that already caught stale docs twice
  here — a green test surfaces nothing, so memory must come from a generated artifact and the
  interrupt from its check

## 7. Foundation — a spectrum from observation to artifact, and knowing where you stand on it

Foundation has a property ordinary work does not: **once built, it cannot be argued away.** Code
is right or wrong and stays arguable; an artifact either exists or does not. That asymmetry is
what makes foundation worth prioritizing over output that merely looks like progress.

Applied as a selection rule — when two moves would settle the same question, prefer the one whose
*product is checkable by inspection*:

| Foundation (existence is the claim) | Not foundation (a claim about quality) |
|---|---|
| the 12 originals cloned on disk | "we have good coverage of the references" |
| the closed `~/Downloads` inventory table | "we looked around and found nothing" |
| a diff of DZ's port against its clean base | "DZ's changes are small and understood" |
| a passing T1 weight-transplant test | "the encoder is faithful" |
| `reference_on_disk`, `executes_in_this_repo` | "the base is effectively unreachable" |
| a dated register row | "we're aware of that" |

**But this is a spectrum, not a side to pick — and the table above is misleading if read as
"always prefer the left column."** Foundation is *built from* information, and information is
acquired incrementally: by reading a reference end to end, by research excursions, by delve-offs
that produce no code. You cannot start at the right column. Every artifact in it was a provisional
observation first.

The real progression:

```
raw observation → provisional claim → checked claim → artifact (needs no claim)
```

Each position is legitimate. **The error is never *being* on the left; it is presenting a
left-hand position as a right-hand one.** CTRL's "transcribed from Flax to PyTorch" docstring was
not wrong to exist — it was wrong to be stated at artifact-confidence while sitting at
provisional-observation. §5's four fields (type · scope · method · date) are exactly the marker of
*where on this line a claim currently sits*; that is their job, and it is why they complement
rather than compete with foundation.

Two consequences that would be lost by simply "preferring artifacts":

- **Research excursions are the mechanism of foundation, not a detour from it.** Reading a
  reference for an hour and writing nothing has moved information rightward even with zero
  artifacts produced. Refusing to record anything below artifact grade discards exactly the
  in-flight information that compaction destroys.
- **Staying left is sometimes correct.** When the declared budget is spent with the trace still
  open, the right move is a provisional claim with the tier capped and the gap named — *not* a
  push to manufacture an artifact. §9's stopping rule and this are the same rule.

So: know where you are on the line, move rightward when the cost is justified, and never let a
summary — or a docstring — promote a position it did not earn.

It also explains why the register works while docstrings failed: register rows are dated facts
with citations, docstrings were assessments written by the process being assessed.

## 8. Discovering what this document does not contain

Every other section of this file encodes a *known* failure mode. A checklist cannot, by
construction, cover unknown unknowns — and this document is therefore **structurally incomplete on
purpose**. What
follows is not a list of what to look for; it is the set of instruments that actually surfaced
unknowns in this project, with their observed yield.

**Where this session's five findings actually came from** (the honest tally):

| Instrument | Findings it produced |
|---|---|
| External challenge — someone with different priors asks | **3 of 5** (`rad` cloneable; "did you start from literal originals?"; "how can 9 be correct before the joint layer exists?") |
| Undirected breadth sweep — enumerate *all* of a category | **1** (`config/envs/model/storage/algo.py`, missed by keyword grep, found by "every `.py` since a date") |
| Pattern-noticing across history — this happened twice, why? | **1** (hedge-stripping, from the CTRL find→lose→rediscover-wrong cycle) |

Consequences, each stated as a practice:

> **Re-measured 2026-08-25, and the tally above understates the first row badly.**
> The single largest defect this project has found — [C69](CONSTRUCTION.md#c69), an unseeded RNG
> moving the door ~1.6 cm between evaluations that recorded the same seed, which invalidated
> [C67](CONSTRUCTION.md#c67)'s central reading — came from an **external reader with no access to
> this repository at all**. They reasoned from the public upstream's structure to a hypothesis about
> ours, and handed over a two-minute grep rather than a conclusion.
>
> The internal instruments had every chance and none of them fired: 862 tests, 69 register entries,
> the grids' own `seed` field, and [C41](CONSTRUCTION.md#c41) already flagging run-to-run variance
> as live. **Nothing looked, because a `seed` field reads as evidence that seeding happened.** That
> is a join defect in the shape [`SYSTEM.md`](SYSTEM.md) names as this project's signature, between
> "we passed a seed" and "the thing that varies was seeded by it".
>
> **The practice worth copying is that the reader was blind to our notes**, not that they were
> external per se. Being unable to see our reasoning is what stopped them inheriting its blind
> spots. A useful cheap version, when no outside reader is available: state the *mechanism* you
> believe produces a number, then verify each RNG, config key and code path it names actually does
> what the name implies — separately from whether the number looks right. Three RNGs were in play
> in C69 and the recorded seed named the least important of them.
>
> [`../../docs/anthropic-prompting.md`](../../../docs/anthropic-prompting.md) is the reference for
> this technique (it calls it a *blind spot pass*, and splits unknowns into known-unknowns,
> unknown-knowns and unknown-unknowns). **Deliberately linked from here rather than added to
> [`CLAUDE.md`](../CLAUDE.md)'s read-first list**: that file's job is this repo's gotchas, and the
> guide's own argument is that stacking general methodology into an always-loaded file is the
> failure it was written to correct.

- **Breadth beats targeting for discovery.** A keyword grep finds what you already expect to
  exist. Enumerate the whole category instead — every `.git` under a root, every `.py` by date,
  every entry in the registry — and read the list. The keyword search missed five files that the
  undirected one caught, in the same directory, on the same day.
- **A repeat is a finding about the process, not the instance.** The second occurrence of any
  failure shape is evidence about the procedure. Chase the shape, not the case.
- **External challenge is the highest-yield instrument and cannot be self-administered.** This is
  a real limit, not a gap to paper over. The partial substitutes: adversarial self-review from a
  named stance ("assume this is wrong; what would falsify it"), and failure-biased delegated jobs
  (assume the attempt fails unless conclusively shown otherwise). Both are weaker than a person
  who holds different priors. Say so rather than pretend coverage.
- **A derived surface's SILENCE is not evidence of absence, and this is the C69 defect wearing a
  different hat.** *(Added 2026-09-04.)* C69's line above is *"nothing looked, because a `seed`
  field reads as evidence that seeding happened"* — a join between a surface and the thing it
  stands for. Three instances in one session, all mine, all the same join: an axis missing from
  `audit_comparability_seam.py`'s list read as *"this axis is uncovered"* when the `rad`/`soda`
  crop was recorded in **five** live documents including `PART2-METRIC-INVENTORY.md:265`; a PART2
  **section heading** read as *"I know what this section covers"* when I had not opened it; and two
  `REGISTER.md` rows whose status column said `open` while their own prose said RESOLVED, which
  `scripts/open_decisions.py` had been reporting as live findings for a day. **The instruments in
  this project are derived from the prose corpus, so their coverage is a fact about the derivation,
  never about the twelve.** The seam audit says exactly this about itself in its own summary — and
  I read past it, which is the point: a caveat printed by an instrument does not protect the person
  who is using the instrument as an index.
  **Practice**: before writing "not covered", "no axis for", "nothing records" — grep the corpus,
  and open the section rather than matching its title. Where an instrument reports coverage, make
  it cite the document the coverage comes from, so a missing citation is visible instead of a
  missing axis being invisible. **All three were caught by external challenge**, which is the row
  above, and this is one more count for it.
- **For *unknown knowns* — the rules so obvious to their holder they were never written — narrate
  assumptions back.** The copy-first rule surfaced only when the framework was described aloud and
  its holder said "no, the base assumption is that you start from the originals." Stating what you
  believe is too obvious to state is the only instrument that reaches these.

**The refinement loop, so this document can grow rather than ossify:**

1. A new failure mode is found → register row (dated, cited) **and** a line here, with the
   instance that motivated it. A rule without its motivating instance cannot later be judged
   inapplicable, and becomes overprescription.
2. A rule here proves wrong or inapplicable → amend it *in place* with the case that broke it.
   Deviating from this document in a case it does not fit is correct behaviour, not violation —
   `porting-directive.md` is the standard; this is procedure, and procedure is falsifiable.
3. Anything here that has never fired is suspect. An assertion that has never failed has not been
   tested; it has converted an unchecked area into one that looks checked.

## 9. Budget tiers — what changes is the *kind* of step, not the amount

Three tiers were actually run in this project, and each failed in a way characteristic of what it
optimized. A fourth is proposed. The tiers are **not** "the same work, more of it" — each admits
step kinds the tier below structurally cannot contain.

The objective inverts across the boundary: **tiers 0–1 optimize P(finish); tier 2 optimizes
P(detect the error | an error exists).** The quantity to maximize is not actions taken — that is
gameable by padding — but **independent points at which the work could be shown wrong**.

| Tier | Optimizes | Characteristic step kinds | Characteristic failure | Directive tier reached |
|---|---|---|---|---|
| **0 — integration-first** | time to something that runs | pick a shared abstraction; fit baselines to it; test that it runs | the shared shape silently overwrites algorithm-specific structure; found only when an *adjacent* baseline breaks (`onpolicy_ext.py`; the `storage_cls` bug surfaced by wiring PPG, not by testing IBAC-SNI) | none — structural claim by assertion |
| **1 — result-equivalence** | mechanism correct *as understood* | read the reference; write an equivalent; test outputs are sane and parameters move; classify honestly | no base term, so a construction is written where a copy was available; self-consistency tests only; the honest label absorbs the pressure instead of the practice changing (`ppg`, `ibac_sni`) | **T4** — structural accounting |
| **2 — falsification-first** | P(detect error \| error) | see below | verification theatre / infinite regress, if no stopping rule | **T1/T2** — executable agreement |
| **3 — empirical** | agreement with published results | reference-domain training runs, multi-seed, distributional comparison | none reached here — **gated by compute, not by discipline** (~17 days sequential local for 12×3 seeds) | **T3** |

**Tier-2 step kinds, each with an instance from this project:**

| Step kind | Instance | Yield |
|---|---|---|
| executable comparison under transplanted weights | CTRL `Impala` T1 | **2 real bugs** invisible to reading (NHWC flatten order; max-pool pad value `-inf` vs `0`) |
| diff a third-party port against *its own* base | DZ's IBAC-SNI vs `joonleesky/train-procgen-pytorch` | hands you someone else's already-scoped N-edits **for free** — 5 files. Available all session, never used |
| undirected breadth enumeration (not keyword search) | every `.py` in `~/Downloads` by date | found 5 files a keyword grep missed the same day |
| run the reference itself | ran `test_parity.py`; ran the reference's own `RewardNormalizer`/`VecNormalize` | distinguished "genuinely executed" from "plausibly reported" |
| mutation-test the test (red→green) | every normalizer; the EMA direction | proved the assertion has teeth; an assertion that never failed has not been tested |
| premise check as a *separate* pass | shared-PPO-core premise | three bugs fixed inside a premise establish nothing about whether the premise should hold |
| trace one datum across the reachable call graph | reward → storage → GAE | found `rewards_raw` declared and never populated |
| triangulate a claim across ≥3 independent sources | truncation bootstrap: `ALDA_Official`, RL-ViGen's own wrapper, DZ's port | upgraded a repair into a *documented divergence from upstream itself* |
| narrate assumptions back to their holder | describing the framework aloud | surfaced copy-first, an unknown known |
| adversarial pass from a named stance | reviewing the PROVENANCE design | 7 attacks, 5 material design changes |
| **backtrack — discard working, tested code** | `ppg`/`ibac_sni` rebuild | the move tiers 0–1 structurally cannot make |

**The stopping rule, without which tier 2 is unbounded.** Maximizing falsification surface has its
own failure mode: verify forever, ship nothing. The directive already supplies the bound —
*budget, do not estimate*, and *exhaustion is a result*. So: declare a spend limit per module in
advance; when it is spent with the trace still open, **cap the declared tier at what was reached,
name what was not, and report the module there.** Tier 2 does not mean "verify until certain." It
means "spend a declared budget on falsification rather than on throughput, then declare honestly."

**Which tier is warranted where** is a judgement, not a rule — but the default has a direction
(§5 of the directive): anything touching the training loop's arithmetic on every step is assumed
to matter, and the burden is on showing it does not. One-time and setup-only differences are
discardable without proof.

## 10. Golden path vs reverse path — the tradeoff that actually decides abstractions

Every abstraction has two paths through it. The **golden path** is the intended sequence when the
abstraction holds: short, elegant, visible at decision time. The **reverse path** is what you must
traverse when it does not hold: from a wrong number, back out through the abstraction, to the
truth it hid.

**The decisive property is that these are not symmetric, and the asymmetry runs the wrong way.**

**1. Golden-path length and reverse-path cost are coupled through how much is hidden.** The shared
PPO core had an excellent golden path precisely because it made four independently-authored
methods look like one. That is exactly why its leaks were invisible: LR decay, gradient clipping,
epoch count, value-loss formula, and the storage class were each hidden by the same elegance that
made the golden path short. **A more elegant abstraction hides more, so when it leaks, more is
hidden.** Elegance is not protective; it is the mechanism of concealment.

**2. The reverse path is paid by the builder too — and it still does not deter them.** An earlier
draft of this section framed it as an externality (builder takes the golden path, downstream pays
the reverse one). **That is wrong, and the truth is worse.** The builder is the one asked to patch
the leaks, and in this project that is literally what happened: the same process that built on a
shared PPO core then spent a full session patching its leaks — `storage_cls`, LR decay, gradient
clipping, epoch count, value-loss formula, reward normalization — one at a time.

Two consequences follow, and both are sharper than the externality story:

- **Incentive alignment does not fix this.** "Make whoever builds it maintain it" is the standard
  remedy for externalities and it is *already satisfied* here. The bet was still taken. So the
  failure is not short-termism or cost-shifting; it is a **prediction failure** about quantities
  that are not observable when the decision is made.
- **Paying the reverse path feels like progress.** Each patch is a genuine bug genuinely fixed,
  with a test, and a commit. Nothing in the experience registers as *"I am paying instalments on a
  bad abstraction."* This is exactly why `porting-directive.md` §5 insists that repair does not
  discharge the finding: three bugs fixed inside a shared class establish nothing about whether the
  class should be shared, and the *rate* of defects against one constructed unit is itself the
  evidence — which is why the premise check must be a separate, triggered pass rather than a
  thought held while repairing.

The timing asymmetry that survives: the golden path is paid **once, upfront, in one visible
lump**; the reverse path in **many small instalments**, each individually justifiable, which is
what keeps the total invisible even to the person paying it.

**3. Only one of them is observable at decision time.** You can see the golden path when choosing.
You cannot see P(leak) or the reverse-path cost. That is the trap, and it is why this mistake
recurs rather than being learned once.

The expected cost is `P(holds)·golden + P(leaks)·reverse`. For twelve independently-authored
algorithms the prior on P(holds) is low, and here it was **empirically zero** — all four on-policy
methods disagreed with the shared core on at least one axis. With reverse cost tending to
intractable, the abstraction is a bad bet *regardless of how good the golden path looks*. That is
the honest post-mortem on "we couldn't fix all the bugs in reasonable time": the reverse path was
not merely expensive, it was **unbounded**, because finding a leak required re-deriving what each
baseline should have done from its own reference — which is the entire porting problem, recursively.

**But duplication is not free of the tradeoff either, and pretending otherwise is dishonest.** Its
reverse path is real: a fix must be applied N times and copies drift. The difference is that this
failure is **bounded and locally findable** — "fixed in 3 of 4 places" is a `grep` away, N is
known, and divergence is detectable by comparison. Shared-abstraction failure is "the number is
wrong and nothing indicates where," which is unbounded.

So the criterion is not *avoid abstraction*. It is:

> **Prefer failure modes whose reverse path is bounded and locally findable. Accept a longer
> golden path to get one.**

### 10a. Stale priors in the directive — one root cause, three surface forms

`porting-directive.md` was authored while an improperly-shared PPO head, buffer, and training loop
existed and had to be argued down. **None of what follows is a defect in the standard.** Each is a
place where its context was load-bearing and is now absent — and where a reader starting from a
clean tree, or from a *different* wrong architecture, can be misled.

**Root cause, single:** the directive was written as a *corrective against a specific artifact*, so
wherever it needed to be concrete it reached for the thing in front of it. That produces three
recognisable surface forms — and the same three are worth checking for in **any** rule inherited
from a corrective context, including this file:

| Form | What it looks like | Why it misleads later |
|---|---|---|
| **(a) Enumerated prohibition** | forbids the *specific artifacts* that were wrong, instead of stating the test that made them wrong | a differently-shaped mistake passes the list; a correct structure that happens to be on the list gets refused |
| **(b) Reactive mechanism** | fires on damage already accumulated | structurally dormant on greenfield — cannot prevent the first construction |
| **(c) Assumed topology** | singular nouns fix a structure that should be derived | forecloses arrangements that were never considered because only one existed |

**The instances, and the fix for each — additive, so nothing protective is lost:**

**(a) §1 — "own file, own utilities, no shared base classes, runners, or adapters."** This
enumerates what was wrong at the time. Two failure directions follow. *Over-refusal:* this project
already runs **two** runners — `trainer.py` (off-policy) and `trainer_onpolicy.py` (on-policy) —
because PPO-family and SAC-family genuinely differ in loop shape, and collapsing them was the
original error while atomising into twelve would be cost with no benefit. A literal reading of the
sentence forbids the arrangement that is actually correct. *Under-detection:* a shared thing that
is none of "base class / runner / adapter" — a helper module, a config dataclass, a mixin, a
utility function with retained state — passes the list untouched while doing the same damage.
**Fix:** keep the list as *the instances that motivated the rule*, and put the generative test above
it — §10's uniform-vs-selective criterion. The list stops being the rule and becomes evidence for it.

Same treatment for §1's second enumeration, *"normalizers, schedulers, buffers, target-network
EMAs, anything consuming RNG are not lifted out"* — an accurate list of what was wrongly shared
here, and the principle underneath it is **statefulness**, which generates the list plus everything
not on it.

**(b) §5 — "declare in advance a defect count at which the premise check fires."** Presupposes a
constructed unit already accumulating defects: exactly right for an existing core that is leaking,
**structurally dormant when nothing has been built**. An agent starting clean gets no prompt to ask
*"should this shared thing exist?"* until after it exists and leaks — the original failure,
recurring. **Fix:** keep the reactive trigger; add the prospective half — apply §10's test **at the
moment of introducing** anything shared between two or more baselines. Two triggers, one before and
one after, neither replacing the other.

Also in this form: §1's *"extraction happens only in retrospect"*, which presupposes existing code
to extract from. Sound as written; silent on the greenfield case where a genuinely pure shared unit
could be correct up front. The purity test still governs — retrospect is the *usual* safeguard, not
the criterion.

**(c) §2 — "the harness performs all segmentation, aggregation, and metric computation."** The
singular fixes a topology. **What is actually required is far narrower: the reported metric axis
must be common.** Whether the layer below it is one harness, two (on-policy / off-policy), or three
along some axis nobody has needed yet is **derived from what the baselines actually require, not
assumed** — and the correct number is discovered, not decided in advance. **Fix:** read §2 as
constraining the *axis*, not the *component count*; the invariant is "one axis, N components, each
justified," and any component whose failure is uniform across everything it serves is legitimate by
§10's test regardless of how many there are.

Mild, noted without change: §0's *"most of this work is transcription"* was true of the situation
it described and is roughly true here (8 of 12 have a reachable base), but it is a description of a
project's composition, not a law — a project of twelve JAX references would make it false without
making the directive wrong.

**When to concatenate a correction into the claim, and when to leave both.** A fix appended after
the thing it fixes leaves two texts where one would do, and a reader must reach the second. Whether
to merge them depends on which kind of staleness it is — and git history plus `REGISTER.md` already
preserve the record, so inline preservation is redundant unless the *old wording itself* names a
live trap:

| Kind | Example | Do |
|---|---|---|
| **plainly wrong** | a stale citation (`§3a`'s single-file reference for four now-separate encoders) | **concatenate** — state the current truth; the error's only value is a dated register row |
| **was true, expired** | `§5`'s "still open, not resolved" for findings since built | **concatenate** — the reader needs current state, not a diff against a state they never saw |
| **framing names a live trap** | `§7`'s "re-derive the architecture fresh" — sound-sounding, and *exactly* the instruction that produced `ppg`/`ibac_sni` as constructions, because re-derivation is not copy-first | **concatenate, quoting the old wording *inside* the correction** as an example of the trap |

**There is no "keep both" case.** An earlier version of this table had one, and it was confused:
it conflated *preserving the wording* with *leaving the claim standing as live text*. Those are
separable, and only the first is ever wanted. A superseded instruction left in place is read as an
instruction — a reader hits it before reaching whatever corrects it, which is precisely the
"contradiction here, resolution further down" failure. Quote it inside the correction instead:
the trap stays visible, and nothing false remains addressed to the reader in the imperative.

So the rule is unconditional: **concatenate.** What varies is only whether the old wording is worth
quoting inside the merged text — usually not, occasionally yes when the wording itself names a trap
that recurs.

**Non-regression — why the enumerations stay.** Deleting the lists to leave only the principles
would trade one failure for another: a bare test is easy to argue past, while a concrete list of
real traps is not. The asymmetry to preserve is that **a rule without its motivating instance
becomes overprescription, and an instance without its generating rule becomes over-specification**.
Every fix above is additive — the generative test goes *above* the list, the prospective trigger
*alongside* the reactive one — so nothing that currently protects stops protecting.

**Proposed patch to `porting-directive.md`, for the owner to apply or reject** (not applied here —
it is the standard, and this file is procedure). §1, before the enumeration:

> Sharing is illegitimate exactly where its failure would be *selective* — visible in one
> baseline's numbers and not another's — and legitimate where failure is *uniform* across
> everything it serves, since uniform wrongness surfaces as a systematic offset and selective
> wrongness does not. The prohibitions below are the instances that motivated this test, not its
> definition; apply the test to shapes they do not name, and at the moment of introduction rather
> than after defects accrue.

This also explains why one abstraction in this project is legitimate while the other was not — and,
per §10a(c), the point is about **failure distribution, not component count**. A harness component
serving all twelve is wrong for all twelve identically, surfacing as a systematic offset; a shared
PPO core is wrong for one baseline and not another, surfacing as nothing at all. Uniform wrongness
is detectable, selective wrongness is not — and that test applies unchanged whether the layer
below the common metric axis turns out to be one component or several. `porting-directive.md` §1
states the conclusion — *duplication is cheaper than a wrong abstraction* — and this section is the
reason.

## 10b. Three cases from 2026-08-16, recorded as evidence rather than as rules

All three were surfaced by external review challenging something already written, not by self-audit — which is
itself the pattern worth noting, since it is the one instrument that cannot be self-administered.
They are here as **cases**, with what generalises and what plainly does not. If your situation
does not match the case, the case does not bind you; read the reasoning and decide.

**Case 1 — a four-tier correctness grade was hiding a failure as a middle rank.**
`INTEGRATION-DELTA.md` first graded authored elements as built-in / verified-after / argued /
unverified, which reads as a quality ladder. It is not one. "Verified after" means the abstraction
was applied without its correctness being visible, and the test only reports that this instance
survived — the process that produced it is unchanged and will leak again where no test is looking.
Regraded to binary: **intrinsic** (correctness legible at the edit, against the original; the test
confirms) or **not intrinsic** (a debt, green or not). The regrade moved real entries: a value
chosen for cross-baseline uniformity turned out to have silently disabled half of one algorithm's
mechanism, which no test could have caught because the code does exactly what it says.
*Generalises:* the shape of the grading vocabulary decides what gets treated as acceptable.
*Does not generalise:* a binary grade is right when there is an original to be intrinsic
*against*. Where none exists, forcing the binary just relabels the gap.

**Case 2 — I described my own edits instead of measuring them.**
This module's docstring claimed "every file here started as a byte-copy of its counterpart." A
`difflib` pass over code lines: 100%, 99%, 44%, 3%, 7% textual descent. True for two files, false
for three — and the 3% file was the one carrying the weakest structural claim. The measurement
took one command and existed the entire time. *Generalises:* when a claim about your own work is
mechanical, the cost of checking is usually a single command, and asserting instead is a choice.
*Watch for:* the low numbers were not all defects — two files implement an algorithm whose
reference is a *different repo* than the base, so they cannot textually descend from it. The
measurement is the input to a judgement, not the judgement.

**Case 3 — I delegated a record of my own decisions to subagents.**
Eight agents were launched to reconstruct, from artefacts, which parts of the code were authored
here and why. They could not have known: the reasons live in the session, not the tree. What they
could return is guesses I would then have to verify — which is the inherited-claim problem this
file exists to prevent, paid for at fan-out scale. The mechanical half (finding tagged sites) was
a `grep` returning 77 hits in one call. *Generalises:* delegation moves work that is legible from
the artefacts; a record of intent is not. *Does not generalise:* this says nothing against
delegating genuine fan-out — a parallel read of one reference across four axes, earlier the same
day, produced the cited spec that the whole rebuild rests on, and independently confirmed two
defects found by hand.

## 11. Open questions — surfaced, not resolved

1. **The trigger problem is only partly solvable.** Omission → a test catches it. Judgement → a
   test catches it *iff* self-reporting stays honest, which this session's evidence supports (the
   Construction labels were accurate even while the construction order was wrong). Discovery →
   **not** solvable by a trigger; closed here by a one-time exhaustive inventory (`~/Downloads`
   swept and closed 2026-08-16) rather than a recurring check, at the owner's direction.
2. **Where does the copy-first rule belong?** Not in `porting-directive.md` — a hard rule there
   would mis-prescribe for 8 of 12 (framework boundary, absent original, dependency subgraphs with
   dead edges) and would overconstrain a standard that deliberately specifies properties, not
   procedures. Currently: §4 here. Unresolved whether that is the right home.
3. **K3 — metric vocabulary.** Deferred by explicit decision. `Nd_ln.py`'s namespacing
   (`train_metrics/*`, `eval_metrics/*`, `episode_return`, `success_rate`, `smoothed_*`) is a
   *vocabulary* source only, to be borrowed selectively and only where its own choice is good, and
   only after hermetic porting is substantially further along. Never an architecture anchor.
4. **Contract layer: descriptive before constructive.** Surfacing what arguments/methods/counters
   already mean (units, origin, multiplicity, implicit properties) comes first. Building
   declaration machinery and build-time enforcement presupposes knowing what the contract *is* —
   and two of twelve baselines are constructions slated for replacement, so enforcement now would
   freeze a contract partly inferred from code that is going to change.
5. **Readiness is joint, not per-baseline.** base + N + M is verifiable in isolation; **K is a
   relation among twelve** and cannot be established for one. "Is baseline 3 done?" is not
   well-formed until the reporting layer exists. This invalidated a "9 of 12 correct" claim made
   in this same session.
6. **Does a blind-spot pass have a cadence?** Per baseline at step zero is established. Whether it
   should also fire on re-entry after a compaction is unresolved.
7. **This document is weakest exactly where it matters most.** §§3–6 are known failure modes —
   well covered. §8's instruments are derived from a sample of five, three of which came from
   external challenge, which is the one instrument that cannot be self-administered. So the
   coverage of unknown unknowns rests substantially on something outside the procedure. That is
   an honest structural limit, and the reason §8 exists rather than a claim that §8 solves it.
8. **Does the procedure self-propagate?** Partially, and unevenly. §4's triage genuinely generates
   the next action (the derived state dictates construction order). §3c genuinely hands the next
   step its input (the port-vs-base diff *is* the N term). §§5–6 are constraints, not
   step-generators — they shape work already chosen rather than choosing it. Whether the
   constraint sections need a generating form, or are correctly passive, is unresolved.
