# Open questions from the owner, and what followed from each

Not a yes/no list. Each row records what the question actually turned up, because several of them
turned up something other than their own answer — three overturned a change I had already written
down, and one overturned a change I had already made.

Status: OPEN / ANSWERED / **REVERSED** (the question showed my position was wrong).

---


## How to research one of these without reading the repo

[Claude 2026-09-09] This file is the entry point, not the answer. The route that works:

1. **Find the axis here.** If it is listed, the status line already says whether it is settled, and
   `REVERSED` rows exist because several confident positions turned out to be wrong.
2. **`python scripts/where_is_this_decided.py <term>`** — every occurrence of the topic across
   `notes/ docs/ datasphere/ scripts/ tests/`, ordered newest-file-first, with supersession markers
   flagged and the `git log -S` command for the change that actually moved the value. It reports
   provenance, deliberately not truth.
3. **Read the set, not the top row.** Recency is last-touched, which a typo fix also moves. And
   several notes here were written by an assistant from whatever was in its context, so an
   exhaustive-sounding review may have seen a subset — breadth is a claim, not a property of tone.
4. **Check the primary source when one exists.** `ext/` holds the vendored papers. Every IDAAC-C2
   constant was fixed by reading `raileanu21a-supp.pdf` rather than a review's summary of it, and
   that is the only method in this project with a record of finding real defects.

The failure this guards against is not ignorance, it is premature closure: settling on the first
document found, when a contradicting one sits three files away with no marker saying which is
current.

---

## Answered, with what followed

**"Why the procs=1? I'm very sure there was a way that was advocated for."** — REVERSED, twice.
First reading: base `procs` is stale, raise to 16. Wrong: `resources.json` shows `gt4.1` has 4
logical CPUs and `gt4i.1` has 8. Second reading: the `v100` override to 16 is unverified. Also
wrong: `notes/remote-infra.txt` is a captured session from the production host showing `nproc` 16,
and the competence pilot was already scheduled in the runbook and in `production_gates.py`. What
remains is one line of stale prose. **Followed from it:** the habit of declaring something
unexamined that the project had already examined — which then recurred twice more.

**"The project's prose might be stale in some sources."** — ANSWERED, and it was the most
productive question asked. It led to the docs sweep, which found `docs/FAITHFULNESS.md` has not
been touched since 2026-09-05 and is stale on **every** numeric claim about the on-policy four
(idaac's gamma/rollout/lr/num_processes, ppg's num_envs/lr, the frame-stack split, ctrl's cluster
count). Thirteen findings, four rated MISLEADING.

**"How could reward normalization have existed in none? It could have."** — REVERSED. Twelve review
files discuss it and review 2 gives it a numbered section. My committed text was accurate; three
conversational retellings had inflated it. Recorded as a memory.

**"Do the subagents differentiate between prod and not, and read docs like this?"** — REVERSED, and
it changed the sweep's output. My briefs never mentioned `host_profiles`, so both source-reading
agents were resolving BASE values and reporting them as production. Corrected mid-run; agent A
re-ran and its revised report overturned my change-plan item 3.

**"Is it already time to run svea? Do we not have changes incoming?"** — ANSWERED: no, and the
question was right. Four findings would have voided it. **Followed from it:** holding the run
exposed that the wave is 3 cells rather than 7, once the `families.json` edits were withdrawn.

**"Would it still run 3h? How can this be a thing just for a mock run?"** — ANSWERED, and the
number was wrong. `cfg-sgqn-cover-v197` is the same family, same overlay path, same 10000 frames,
same tier, same hour: SUCCESS in **2381s**. An rlvigen attest cell is a 40-minute job. Timeout cut
from 7800s to 3600s. **Followed from it:** the 7800s v197 svea cell spent ~1200s working and ~6600s
hung after a crash, which produced the stall watchdog.

**"What are the actual things that change learning, not just scaffold?"** — ANSWERED: two.
`ibac_sni`'s policy-head init, and the step-0 evaluation's RNG consumption. Everything else on my
list was declaration, prose, instrumentation or integrity. **Followed from it:** the list was
mostly paperwork and had been presented as though it weren't.

**"Is the policy-head init a real bottleneck?"** — ANSWERED, quantitatively. Inverting the measured
clip rate (sigma 1.027 from its own `log_std`, then solving the two-sided clip probability) puts
the initial |mean| at **0.818** on a [-1, 1] action space — 82% of the way to the bound before a
gradient step. Not slight. Changed.

**"Do we have the git-repo creation ready?"** — ANSWERED, and it surfaced something not asked
about: **the GitHub repo is PUBLIC**, 985 files including 91 `notes/` files, against CLAUDE.md's
"private by default for anything uploaded". Left for the owner; the command is in the chat.

**"What's rlvigen and is it even relevant?"** — ANSWERED: a family, not an algorithm — drqv2, svea,
sgqn, curl, drq share one payload and evaluator. **Followed from it:** my "not one shared DrQ-v2
backbone" claim was weaker than presented. `docs/COMPARABILITY_CONTRACT.md:254` already enumerates
the three encoder classes per file and line, and `docs/FAITHFULNESS.md:326` already records SVEA's.
Only the repr_dim numbers were unwritten.

**"Are you sure the terminal save fails?"** — REVERSED in framing. I have **not** observed a
failure. `safe_write` returns False on three paths and never raises, by design; `ctrl`'s
`_save_state` had no `return` at all, so its terminal caller could not check it. That is a
fail-open path verified in source, not an observed failure, and I described it as though it had
fired. All seven families were traced: five already fail-closed under Q18(b), ctrl and ppg were
not, and the exclusion appears nowhere in the 247-file prose corpus.

**"Research not just some claims but all."** — ANSWERED by instrument, not by reading: a corpus
check over all 247 prose files for every claim the four agents raised. Most were already recorded.
Genuinely absent from the entire corpus: ALDA's `AdamW(weight_decay=0.1)` on the trunk both actor
and critic read (zero hits for either term), the SAC families' two-speed `encoder_tau=0.05`, and
idaac's `--eps` labelled RMSprop while configuring Adam. All three are faithful upstream behaviour
— disclosures, not changes.

## Reversed by the question, in full

**The ctrl inert-constants change.** I added six flags to `ctrl.options` and then reverted them.
`tests/test_every_constant_reaches_the_process.py` already exempts exactly those six, with a second
test that reads `train_ppo.py` and fails the moment a declared value stops matching the default.
Simulated A45's proposed `lr_ctrl` edit against it: the test fails, which is the silent no-op I had
claimed it missed. Reverting kept `families.json` untouched, which is why the wave is 3 cells.

## Later questions, and what followed

**"Do we just wait for the three agents?"** — no. Agent B had already landed; the answer was to
keep working and fold results in as they arrived.

**"What are the longest remaining chains? Does the eval_frames thing invalidate all?"** —
ANSWERED: it invalidates nothing, because every record that exists is a 10k attestation cell and
attestation asks only whether a record's `evaluator_revision` is live. **Followed from it:** the
chain ranking made clear my own work is a rounding error against a 9-28 day campaign, which
reframed the rest of the session away from polishing.

**"What's the final set of edits?"** — ANSWERED, and answering it shrank the set twice. Item 10
(the eval sentinel) turned out to be a cfg-and-runner defect rather than a source one and left the
voiding batch entirely; the ctrl inert-constants item was reverted outright. The wave went from 7
cells to 3.

**"Is the policy-head init a real bottleneck?"** — see the entry above, and then FALSIFIED by its
own cell. Recorded as `CORRECTIONS.md` #103.

**"The GitHub after everything is fixed; take responsibility over the whole horizon."** —
ANSWERED by treating the repo as a deliverable rather than a snapshot. **Followed from it:**
`setup/verify_sources.py` was failing with `source closure hash mismatch at runnable/ctrl` while
every gate passed, because that check was not among the gates. README's bootstrap instructions were
false. Fixed, and gated (`CORRECTIONS.md` #102).

**"Examples, not the exhaustive list."** — taken as scope, not as a checklist. Produced the
campaign-status view, the live `log_std` alert, and the comparison-blocks quantity fix.

**"You don't have to write prose in git commits."** — ACTED ON from `a967f01` onward; earlier
messages in this session were long.

**"Ask a fork what you forgot."** — the highest-yield single instruction of the session. It found
that `scripts/watch_policy_health.py` was not a payload member and its launch was hidden behind a
`-f` guard, so the alert would have silently never started in production while the runbook told the
operator it runs on every cell — this session's own recurring failure, rebuilt inside the
instrument written to catch it. Also: `CLAIMS-LEDGER.md` still forbade a comparison the project is
now entitled to make, and the new reconstruction gate had never been observed red. All fixed.

## Still open

- **`docs/FAITHFULNESS.md` rewrite.** Agent E's recommendation is to regenerate it from
  `families.json`/`protocol.py` outward rather than patch it. Not blocking a run.
- **Disclosures** for the three genuinely-unrecorded facts above.
- **The `ibac_sni` init at length.** Measured at 10k frames on a near-untrained policy. The
  production competence pilot is where it is actually tested.
- **Everything host-side**: renderer parity, ctrl 64-env memory, ibac_sni `procs=16` competence,
  Places365 full asset, the ~45 h `soda` canary (`notes/PRODUCTION-RUNBOOK.md:90`).


## Added 2026-09-09, from the first production runs

**"Why would IDAAC specifically run 1-proc on a physical env?"** — ANSWERED, and it opened a
different question. `num_processes=1` is fidelity: A35/Q55 (commit `15b4e73`) took the whole recipe
from `ext/idaac/raileanu21a-supp.pdf` §E, and **1 process was never tuned** — the authors' grid
searched learning rate, minibatches, entropy and epochs, while "2048 steps, 1 process" sits beside
γ and λ as inherited PPO-for-MuJoCo convention. **What it opened:** the same paragraph says they
used **action repeat 4-8**, and Door runs **action repeat 1**, so a 2048-step rollout covers 4-8x
less simulated time here. **OPEN** — see
[`idaac-2048-steps-was-chosen-under-action-repeat-8.md`](idaac-2048-steps-was-chosen-under-action-repeat-8.md).
Nothing is claimed to be wrong; the condition simply was not written down.

**"Is the memory growth a leak?"** — ANSWERED, no. `idaac` held *exactly* 2644 MiB across 37
samples in five hours. `ppg` is 8207 MiB in its policy phase and **26653 MiB in its auxiliary
phase**, which is `n_pi=32` stored segments — upstream PPG's own default, not ours.

**"Is packing really as bad as you concluded?"** — **REVERSED.** I withdrew packing after a pair
reached 29910 MiB of 32494. Wrong reading: `nvidia-smi` reports the allocator's *reserved* pool, a
fact recorded earlier in this project and not applied. The real constraint is per-family:
`idaac`-class cells pack fine, `ppg` is a whole-card job.

**"Is our allocation/reservation/pinning underutilising the GPU?"** — ANSWERED, no. 37 identical
reserved-memory samples (no churn), rollouts already on device. The limit is **33.2 env steps/sec**
with batch size 1 — a parallelism property, and `num_processes` is fidelity-fixed.

**"What cap is right — strict enough to protect a booked user, loose enough not to fail a long run?"**
— ANSWERED: **none, because a cap is the wrong instrument.** It is coercive (it OOMs *us*, and
fragmentation makes late refusal likelier, where the loss is largest), it cannot see EGL buffers or
the CUDA context, and it has in fact **never reached a trainer** — all nine `runnable/_launch/*.sh`
clobber `PYTHONPATH`. The free-memory floor with a cooperative yield is the mechanism that works.
See [`production-host/26-the-vram-cap-never-reached-a-trainer.md`](production-host/26-the-vram-cap-never-reached-a-trainer.md).

**"Do we have checkpoint duplication or brittleness for PPG?"** — ANSWERED, brittleness, now fixed.
ppg names by save index, so frames come from its `IC=` log lines; the fallback reconstructed
`(stamp+1) * save_every`, which measured **off by one save and on the wrong cadence** (actual
0/51200/100352… against 50000/100000/150000…). It now refuses and skips rather than mislabelling.

**"Is `success_rate` the right axis to judge a Door run on?"** — ANSWERED, **no**. RL-ViGen's
supplement §B states the Robosuite metric is aggregated **return**; success rate is Adroit's metric
and Habitat's. Figure 22 plots Robosuite episode return on a 0-500 axis. Today's `idaac` endpoint
reports `success_rate: 0.0`, which read as the headline says the run failed and on the benchmark's
own axis is not the claim being made. See
[`rlvigen-reports-return-not-success-rate-for-robosuite.md`](rlvigen-reports-return-not-success-rate-for-robosuite.md).

**"Is 600k frames a reduced budget for Door?"** — ANSWERED, no. RL-ViGen **Table 6** gives Robosuite
Door `int(6e5)`; **Table 2** gives `Action repeat — Robosuite: 1`. Ours is the paper's budget, so
"it needed longer" is not available as an explanation for a null. Note the trap: **Table 5 is Adroit
and also has a Door**, at `int(1e6)` and scored by success rate. A grep for "Door" returns both.

**"Did `idaac` learn Door in 598,016 frames?"** — ANSWERED, **no**, and the harness is fine. Train
return wanders 12-50 across 11 stamps with no monotone trend and **ends at 24.74 having started at
24.66**; against Figure 22's 0-500 axis that is under 10% of the range. The same curve shows the
evaluator working: regimes separate as `train ≈ eval-easy` >> `eval-medium ≈ eval-hard` at nearly
every stamp, with 60 episodes per cell. **This does NOT answer whether IDAAC's own hyperparameters,
tuned at action repeat 4-8, transfer to repeat 1** — same words, different question, and a null is
exactly the evidence that tempts an untested answer.

**"Does the VRAM cap reach the trainer?"** — ANSWERED from production, **no**, and the scope is
narrower than previously written. Two live cells declare caps of 4096 and 10240 MiB, summing to
14336; card 0 holds **28108 MiB**. The argument survives the reserved-versus-used trap: a per-process
fraction bounds what the allocator may reserve, so reserved above the cap proves the cap is not in
force either way. The cap DOES apply to the runner and to `eval_grid.py` (8 events before the cell,
15 during evaluation, 5 short-lived helpers during training), so `NATIVE_VRAM_CAP_IN_FORCE` is true
of the process that prints it and false of the trainer. **What is NOT broken:** all nine launchers
re-add `runnable/_shim`, so `sitecustomize.py`, `safe_checkpoint.py`, the `wandb` stub and `no_tf`
reach the trainer normally — the single casualty is the cap directory. See
[`production-host/26-the-vram-cap-never-reached-a-trainer.md`](production-host/26-the-vram-cap-never-reached-a-trainer.md).

**"Can the prebuilt venv be reused across families?"** — ANSWERED, **not blindly**, and I got this
wrong for an hour. `filtered-requirements` is byte-identical for all twelve, and the env directory is
named by that hash — but the host's only prebuilt env reads `"cells": "idaac:1"`, `"editable": []`,
with `robosuite`/`robosuitevgb` **ABSENT**. `build-env.sh` bakes the editable installs only when the
build payload carries `RL-ViGen-upstream/`, and **payloads never do** — the runner git-clones it. So
that env cannot run an `rlvigen` cell, and nothing refused the reuse. Worse, it would not have failed
loudly: `run_probe.sh` skips the editable installs under `NATIVE_VENV` and its import check ran with
`third_party/robosuite` prepended, a path **no** `runnable/_launch/*.sh` keeps. Now guarded —
`PYTHONPATH="" python3 -c "import robosuite"`, refusing with `NATIVE_EDITABLE_NOT_INSTALLED`. Neither
running cell uses the prebuilt env at all; both take `NATIVE_PIP_CACHE=1`, and `drqv2` will too.

**"The curve and endpoint eval paths have no stated authority between them — do they disagree?"** —
ANSWERED, **they are the same closure at two sample sizes**, measured on the live `idaac` cell
2026-09-09. Both rows carry `evaluator_revision=16e960b1f446` and an `evaluator_scope` identical in
every field — task, regimes, scenes `[0..9]`, `episode_seed=20260903`, `action_repeat=1`,
`frame_stack=3`, `image_size=64`, `episode_length=500`, `eval_policy_mode=sample`, deterministic
torch — **except `eval_scope` (curve/endpoint), `frame`, and `episodes` (3 vs 20)**. So there is no
authority question between them: one is the other at 3 episodes per scene instead of 20.

Their regime orderings agree. Endpoint at 598016 over 400 episodes per regime: train 33.69,
eval-easy 31.58, eval-medium 11.93 (4 of 11 scene sets so far). Curve at 550912 over 60: train 24.74,
eval-easy 21.12, eval-medium 7.16, eval-hard 11.65.

**The caveat that survives:** the curve runs **3 episodes per scene**, so a single curve point is
thin and should not be read as a level — only the regime aggregate and the trend across stamps carry
weight. RL-ViGen's own Robosuite protocol is 10 per environment (supplement §B); the endpoint's 20 is
richer, the curve's 3 is not.

**"Why did `idaac` produce a null on Door?"** — ANSWERED at the level of mechanism: **it
over-updates**. From the first complete production cell, `approx_kl_k3` reaches **1.0-1.5 nats**
against PPO's usual 0.01-0.05 target, `clip_fraction` saturates at **0.80-0.84** from 100k onward,
and `dist_entropy` falls 9.92 → −1.75 driven entirely by σ collapsing 0.996 → 0.188 (the arithmetic
for a 7-DoF diagonal Gaussian matches both endpoints to two decimals), with IDAAC's tuned entropy
coefficient at 0.0. `value_loss` is healthy, so it is not the critic; `order_acc` never leaves
0.34-0.44, so the auxiliary task is not learning either. **Consistent with — not proof of** — the
condition recorded in
[`idaac-2048-steps-was-chosen-under-action-repeat-8.md`](idaac-2048-steps-was-chosen-under-action-repeat-8.md),
since 10 PPO epochs over 2048 samples is far more aggressive per unit of simulated time at action
repeat 1 than at the authors' 4-8. Three predefined discriminating arms and what each predicts are in
[`idaac-on-door-is-a-trust-region-blowout.md`](idaac-on-door-is-a-trust-region-blowout.md). **Read
`ppg`'s log for the same three columns** — it is on-policy with Procgen-tuned constants too, and if
it shows the same signature the finding is about the transfer, not about IDAAC.

**"Is the in-cell final evaluation an authority?"** — ANSWERED, **no, and it inverts**. At frame
598016 the in-cell evaluation reports train-mode 18.8 and eval-easy 40.6 over **10 episodes**, while
the standalone endpoint grid at the same frame reports train 33.69 and eval-easy 31.58 over **400
per regime**. The in-cell path ranks eval-easy ABOVE train; the standalone ranks it below. Ten
episodes cannot separate regimes whose returns differ by less than a standard error, so the in-cell
number is a smoke signal and never a result. The standalone grid is the authority.

**"Is the watch budget big enough for evaluation?"** — ANSWERED, **no, and the live cell is one
minute inside its reaper.** `EVAL_ALLOWANCE` defaulted to `CELL_TIMEOUT_SECONDS` — the *training*
budget — while the same file's comment said evaluation is 1.6x training. Measured to completion:
training 4.95h, curve 4.60h, endpoint **5.52h**, because `ENDPOINT_EVAL_POLICY_MODES` defaults to
`native,mode` and sweeps the whole 44-row grid **twice**. Evaluation is 10.12h against a 6h
allowance, 69% short, and the policy-mode count was the term nobody had multiplied by.

**The failure this causes is not a truncated evaluation.** `collect_record_delivery` runs *after*
evaluation, so a reaped cell never reaches it — every row written and none bundled, for a
twelve-hour cell. `card0-20260909-035152`'s second endpoint pass is projected to finish **18:36
against a reaper at 18:37**.

Fixed forward: the allowance is now derived from episodes actually scheduled (including policy
modes) at a measured 12 s/episode x1.5, floored at the old default, and the launcher prints the
workload so a wrong number is visible before the cell starts. For today's configuration it derives
62,568s against the 21,600s used. Six tests, `tests/test_eval_allowance_is_derived.py`.

Mitigation for the cell already running, since the reaper cannot be moved without removing the
instrument: its `*.jsonl`, `*.csv` and `job.log` are pulled locally every ten minutes. **That is a
second copy, not a rescue, and the earlier wording overstated it** — the rows stay on the host's
disk whatever happens; what the stop costs is `collect_record_delivery`, an ASSEMBLY step
(concatenate + stamp `_run_provenance`) that computes no metric and that
`scripts/assemble_reaped_delivery.py` reproduces from a fetched copy.

**"Is `ppg`'s policy being trained?"** — ANSWERED, **barely, and the trainer said so 291 times.**
`Warning: nminibatch > ntrain!! (32 > 1)` appears once per iteration in `cells/ppg-s1/training.log`.
`minibatch_optimize` splits along the **batch (environment)** axis, and `num_processes=1` makes
`ntrain = 1`, so the requested `--nminibatch 32` was clamped to **1**. With `n_epoch_pi = 1` that is
**one gradient step per iteration — 256 policy updates over 524,288 frames instead of 8,192.**

It also dissolves the earlier dilemma: `clipfrac ≡ 0.000` and `approxkl ≈ 1e-13` are **arithmetic,
not evidence.** With one minibatch the ratio is measured before the only step, so it is exactly 1
every time. **The two columns a reader would check are the two the defect forces to look perfect.**

Neither constant is wrong — `1 process` and `32 minibatches` are both sourced from the same
paragraph of IDAAC's supplement — and PPG was written for Procgen where 64 environments make the
batch axis the natural split. **The interaction is the defect, and no fidelity table has a row for
interactions.** `idaac` is unaffected: its lineage flattens `num_processes × num_steps`, which is why
its `clip_fraction` reads 0.83.

Guarded: `audit_training_diagnostics.py` now reports trainer warnings **above** the range checks.
See [`ppg-took-256-gradient-steps-not-8192.md`](ppg-took-256-gradient-steps-not-8192.md).

**"Which reward number is the result — the training log's or the record's?"** — ANSWERED, **always
the record's**, and the confusion has now cost time twice in one day. Three families normalise
TRAINING reward (`REWARD_NORMALIZATION` in `rlgen/protocol.py`: `idaac`, `ppg`, `ctrl`), and their
training logs report on that normalised scale while **every record reports raw return regardless**.
The two are not the same quantity and need not even move in the same direction:

| | training log | offline record (raw) |
|---|---|---|
| `idaac` @ ~545k | `train/mean_episode_reward` **50.1** | curve train regime **24.7** |
| `ppg` @ ~524k | `EpRewMean` **28.3**, rising | `Misc/FrameRewMean × EpLenMean` = **8.3**, falling |

They also measure different things even before normalisation: the training figure is the on-policy
rollout return *while learning*, the record is an offline evaluation of a fixed checkpoint. **A
summary that quotes a training-log reward is not reporting a result**, and for `ppg` it would have
reported a 22x improvement on a run whose raw return may be falling.

`scripts/audit_training_diagnostics.py` flags the inconsistency directly, using the identity
`EpRewMean = EpLenMean x FrameRewMean` that must hold when both are raw.

**"Did the `ppg_checkpoint_frame` fix actually matter?"** — CONFIRMED in production, on its first
row. `card0-20260909-115331` began its curve evaluation 2026-09-09 15:42 with
`NATIVE_CURVE_EVAL_BEGIN ppg frame=0 file=model000.jd`, taking the frame from the trainer's own
`IC=0` line. **The removed reconstruction would have written `(0 + 1) x 50000 = 50000`** — wrong by
50,000 frames on the very first stamp, and wrong on every subsequent one, since the real cadence is
0, 51200, 100352, 151552 … against the reconstruction's 50000, 100000, 150000. A measurement of the
untrained initial policy would have been filed as a measurement at 50k. The 13 `IC=` lines match the
13 `model00N.jd` files on disk one-for-one, so the positional mapping is sound for this whole run.

**"What does a random policy score on Door?"** — ANSWERED, **≈ 2.0**, measured 2026-09-09 from
`ppg`'s frame-0 curve stamp (its randomly initialised checkpoint) under the production evaluator, 60
episodes per regime: train **2.24**, eval-easy **1.98**, eval-medium **1.54**, eval-hard **2.04**,
success rate 0.000 throughout.

**This corrects a claim I made earlier the same day.** I wrote that `idaac` "did not learn Door"
because its curve ends where it began. Against a baseline of 2, `idaac`'s 24.7-50.3 is **12-25x
random** — it learned, and it learned almost all of it by frame 51,200, then oscillated for 550,000
frames without further progress. **The finding is the plateau, not an absence of learning**, and a
plateau is what the trust-region diagnostics predict. Writing "did not learn" without a baseline was
an assertion the data did not support.

Caveat: this is `ppg`'s initialisation, not a per-family baseline. Every family's curve evaluates its
own frame-0 checkpoint, so a proper per-family random reference costs nothing as the battery runs.

**"What do RL-ViGen's own algorithms score on Door?"** — **UNKNOWN, and not obtainable from the
vendored documents.** Searching both PDFs' extracted text for a numeric Door return finds none:
every "Door" line is a hyperparameter. The Robosuite results live in **Figures 22 and 19, which are
images**, and Figure 22's caption says training steps are *"normalized into (0, 1)"*, so neither
axis gives an absolute value.

**I used Figure 22's 0-500 y-axis as though it were a target, twice, before checking.** It is the
plot's range. Statements of the form "the gap to RL-ViGen's own results is real" are **withdrawn** —
there may be a gap, and these documents cannot establish it. `drqv2` at 6e5 under our own evaluator
is the only route to a comparable Door number available to this project, which is a further reason
to run it early rather than late.

**"Is a random-policy floor available for every family?"** — ANSWERED, **no, and I claimed otherwise
within the hour.** `ppg` has a frame-0 row only because its save-index scheme writes `model000.jd` at
`IC=0`. **`idaac`'s earliest retained checkpoint is 51,200**; no untrained checkpoint exists for it.
`eval_grid.py` refuses without a snapshot (`"no snapshot found; nothing was measured"`) rather than
constructing a fresh policy, which is correct and means the floor cannot be recovered afterwards from
the evaluator alone.

A per-family floor needs the trainer to write a checkpoint before the first update — a `runnable/`
change under the same hashed-tree constraint that defers the `ppg` minibatch fix, so schedule the two
together. `scripts/learning_over_random.py` computes the ratio where a floor exists, prints
`NO frame-0 row -- floor unknown, ratio NOT computed` where it does not, and **refuses to borrow one
from another family**, since initialisation scale is architecture-specific.

**"Has the IDAAC-C2 recipe been validated by a full-length run?"** — **NOW YES, and the answer is
split.** `families.json` declared `ppo_epoch: 10` and the rest of C2 as "this project's best
technical default (Q55)" while stating plainly that it was **NOT YET VALIDATED by a full-length
training run**. `card0-20260909-035152` spent that validation: 600,064 frames, full C2.

**Validated as learning:** endpoint train return **33.69** over 400 episodes, ~17x a random policy.
**Not validated as competent:** success rate **0.000** across all 880 endpoint episodes, with the
curve plateauing after frame 51,200 — almost all progress inside the first 8% of the budget.
**And the diagnostics say why:** `approx_kl_k3` 1.0-1.5 nats, `clip_fraction` 0.82, σ 0.996 → 0.188.

The proposed `ppo_epoch` 10 → 3 arm is **not** a repeat of the `bt1djeamji7gilgnndft` pilot, which
ran `frame_stack=1` on a short budget under **C1** and was judged on returns; the arm holds full C2
at 600k and is judged on diagnostics. That pilot nonetheless already showed `ppo_epoch=3` giving
substantially higher raw returns, so two independent hints now point at epoch count. The arm needs
**no hashed-tree change** — `NATIVE_EXTRA_OVERRIDES="--ppo_epoch 3"` is a declared escape hatch
recorded in `effective_config.json`. **The faithful default stays 10**; the arm is a diagnostic.

**"What does a Door return number mean, and is SR=0.000 evidence of a broken flag?"** — ANSWERED
from the vendored source. Door's reward is `1.0` when `hinge_qpos > 0.3`, and **otherwise** at most
`0.25` reaching + `0.25` latch. Success and shaping are mutually exclusive per step (`elif`), with
`reward_scale=1.0` and `horizon=500`.

**So a policy that never opens the door cannot exceed return 250, and return > 250 proves at least
one success step.** `idaac`'s 33.69 is 0.067/step — 13.5 % of the shaped ceiling — with the latch
component contributing almost nothing, i.e. **it learned to approach the handle and never to turn
it**. SR 0.000 across 880 episodes is consistent, not a broken flag: the convention is pinned and
tested (`tests/test_success_convention.py`, seven sites, any-step; REGISTER 2026-08-18).

Consequences: **the remaining gap is discrete, not gradual** — improving 34 → 60 is better hovering,
not progress toward opening. **`drqv2` gets a hard criterion**: clearing 250 proves the harness
supports competence; landing near 34 with SR 0.000 alongside `idaac` would point at the task
configuration, action space or observation rather than at either algorithm. And `success_rate = 0`
and `return <= 250` are the **same statement**, so they must not be reported as two independent
observations. See [`what-a-door-return-number-means.md`](what-a-door-return-number-means.md).

**"Did the first production cell collect, and is it certified?"** — **Collected, not certified**, and
the refusal is right. `card0-20260909-035152` was stopped by its own watch budget at 18:37 MSK during
endpoint pass 2. **569 rows are installed** at `results/records/card0-20260909-035152__records.jsonl`
— 484 curve, 44 endpoint `native`/sample, **41 of 44** endpoint `mode` — via
`assemble_reaped_delivery.py` and `NATIVE_ACCEPT_WATCH_STOP=1`, every row marked
`_assembled_after_reaping` and `_run_provenance_missing`.

**`populate_evaluator_ledger.py` REFUSED**, exactly as it should:
`paired=False (regime eval-hard does not share the reference placement sequence)`. The mode pass is
missing precisely **3 rows: `eval-hard` at scene sets `8`, `9`, and the aggregate
`0,1,2,3,4,5,6,7,8,9`**. An incomplete grid cannot be certified as a paired evaluation, and writing
`paired=True` unchecked is what the ledger exists to prevent.

**The recovery is specified and deliberately deferred.** Those 3 rows are reproducible from the
retained `snapshot.pt` with one `eval_grid.py` invocation at `--policy-mode mode --eval-scope
endpoint --frame 598016 --regimes eval-hard --scenes 8,9`. It needs a GPU and the render stack, so it
runs on the host — and card 0 is running `ppg`'s evaluation until roughly 01:20. **Three rows do not
justify contending with a live production evaluation**, so this waits, and it doubles as the
standalone-evaluation-from-a-previous-cell experiment
[`production-host/28`](production-host/28-eval-is-sixty-percent-of-a-cell.md) wants proven.
