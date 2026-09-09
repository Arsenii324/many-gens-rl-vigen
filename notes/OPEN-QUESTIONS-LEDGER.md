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
