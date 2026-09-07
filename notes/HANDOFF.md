# Handoff — the part that does NOT survive compaction

Every other document here records **what is true**. This one records **what I was thinking**:
priorities, suspicions I have not proven, why the next step is the next step, branches deliberately
left open, and constraints I am carrying that no gate encodes. Those are the things that vanish
when a conversation is compacted, and a file like this makes their survival *closer* to true, not
true. Read it as a colleague's notes, not as a specification.

Last updated 2026-09-07, night, by Claude. Codex is stopped for the remainder of the project.

> **This file was substantially rewritten on the night of 2026-09-07.** The version before it
> described the v194 wave as the thing to finish. v194 is now a diagnostic: correcting `ctrl`'s
> native policy mode moved every family's evaluator revision. What follows replaces that plan.

## What I would do next, and why that order

1. **One job, then six.** The v196 configs are built and their payloads verified, but the wave is
   deliberately not submitted as seven. Submit `cfg-dmc_gb-attest-v196.yaml` (soda) FIRST: that one
   cell exercises the Places365 train path end to end, P21's revision stability and the
   `RLVIGEN_IMAGE_SIZE` repair — the three pieces of machinery that have never run. Submit the
   other six only if it lands. A shared-core mistake submitted seven times is paid for seven times,
   and shared-core mistakes are what this session kept finding.
2. **Do not touch the hashed members** — `eval_grid.py`, `eval_across_scenes.py`,
   `eval_provenance.py`, `metrics.py`, `evaluator_identity.py`, `normalize_curves.py`,
   `rlvigen-source.json`, `families.json`, or anything under `runnable/` and `RL-ViGen-upstream/` —
   from the moment the wave starts until it is attested. Comment bytes count.
3. **Then the host sequence**, in the runbook's §0 order. Nothing there is a decision; all of them
   are measurements. Places365 must pass `verify_datasets.py --split train` on the host ONCE before
   the first svea/sgqn/soda cell (runbook §2b).

## Suspicions I have NOT proven

- **The `--policy-mode mode` pass has still never executed anywhere.** Its scope canonicalises and
  it is unit-tested, but no job has produced a `mode` record. The owner has ruled no secondary pass
  is scheduled, so this is now a dormant capability rather than a planned step — but it means the
  path would first execute during any future cross-block analysis. Note `ctrl` no longer needs it:
  its native rule IS the mode.
- **`ppg` is the weakest link in the "each family's own evaluator" claim.** OpenAI ships no
  evaluation runner at all, so its native sampling rests on `PpoModel.act()`, a rollout convention.
  Every other family's rule was verified against a released evaluator. If a reviewer attacks the
  estimand story, this is where it gives.
- **The full suite had never completed in this tree before tonight**, and the first complete run
  found 14 failures, about half of them pre-existing checks that could not fail for the right
  reason. I fixed those. I do not believe I have found the last one of that species — the pattern
  (a check anchored only against our own files) is not exhausted by the instances found.

## Constraints I am carrying that no gate encodes

- **A bare `ERROR` status is not a diagnosis.** The rlvigen `NameError` survived an entire wave
  because a status was read and a log was not. Always pull the log; the real error is often twenty
  lines above the visible one (dmc_gb's `EGLError` was teardown noise over the real `RuntimeError`).
- **Tests that read source as text pass while the code raises.** Three defects today were covered by
  such tests. `tests/test_eval_grid_names_resolve.py` now guards one class of that; the general
  lesson is not guarded and cannot be.
- **Do not pool across tiers.** gt4i.1 is 1.14x gt4.1. I made this error once with the per-episode
  evaluation rates and caught it only on a direct question.
- **Price a decision before taking it.** A36 was decided by +8.3 GPU-h against ~893; A22 nearly went
  the wrong way on a 105 GB figure that our own `fetch_overlay_dataset.sh` header contradicted
  with "~24 GB". **Check the tree for the number before quoting one.**

## Branches deliberately left open

- **`preserve_snapshots` thinning is a no-op at current fleet settings.** I implemented it generally
  because the descriptor field was silently inert for six families; it does nothing today. If a
  future profile sets `preserve > save_every`, that path activates and has never run for real.
- **No `--memory` / `--cpus` caps on the production host.** Deliberate: a cap guessed before the
  step-2 measurement turns an honest overcommit into an OOM kill. Add them after, not before.
- **No wall-clock ceiling in `run_on_production_host.sh`.** Recommendation 22 asks for one; I did
  not add it because the right value is a decision about how long a stuck cell may burn, and I had
  no measurement to derive it from.
- **The `mode`-pass ledger question.** Wave configs attest the NATIVE scope only. If the forced
  scope should also be attested, that is a second entry shape in the ledger — a decision, not a
  flag.

## What I am least sure about

**Whether the fleet's numbers will be comparable in the way the frame claims.** The mechanics are
sound and the axes are declared, and the estimand question is now much better anchored than it was
— each family's rule is verified against its own released evaluator, `ctrl` was corrected, and the
owner has ruled the residual 9/3 split acceptable with the reporting consequence fixed in advance
(rank within a block, never across; `notes/SAME-AXES-VERDICT.md`).

What still worries me is narrower and more specific than before: **`ppg`**, whose native rule has
no evaluator behind it, and the fact that **three of the twelve baselines have still never produced
a single attested record** — svea, sgqn and soda could not, by construction, until P21 tonight. The
first soda job is the real test of that repair, and it has not run yet.

If one thing in this project turns out to be wrong at publication time, my guess is no longer the
policy-mode axis. It is something in the Places365 path for those three baselines, because that
path has had three separate defects in one day and has never once run end to end.
