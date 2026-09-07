# Handoff — the part that does NOT survive compaction

Every other document here records **what is true**. This one records **what I was thinking**:
priorities, suspicions I have not proven, why the next step is the next step, branches deliberately
left open, and constraints I am carrying that no gate encodes. Those are the things that vanish
when a conversation is compacted, and a file like this makes their survival *closer* to true, not
true. Read it as a colleague's notes, not as a specification.

Last updated 2026-09-07, late, by Claude. Codex is stopped for the remainder of the project.

## What I would do next, and why that order

1. **Finish the wave to 7/7.** Not because the gate is red — because every later step's evidence is
   only interpretable against an attested closure. Four families are SUCCESS; `alda` and `rlvigen`
   are running; `dmc_gb` was resubmitted after a fix.
2. **Do not touch `eval_grid.py`, `eval_across_scenes.py`, `families.json`, `evaluator_identity.py`
   or `normalize_curves.py` until the wave is attested.** Each is a shared closure member and each
   edit costs a full seven-family wave. I have paid that four times today.
3. **Then the host sequence**, in the runbook's §0 order. Nothing there is a decision; all four are
   measurements.

## Suspicions I have NOT proven

- **The remaining wave failures may share one cause.** `b19d12c` added a runtime geometry check and
  has now produced two distinct failures — a `NameError` in `_run_grid` (rlvigen) and an
  unnormalised observation (dmc_gb). Both were *the check being wired into paths whose values it
  assumed*. **If `alda` or the resubmitted `rlvigen` fails, look there first**, not at the family.
- **`rlvigen`'s resubmission may fail for a second, different reason.** It has never completed a
  wave cell since `b19d12c`; the `NameError` masked whatever comes after it. I fixed one error and
  have not seen the path run to completion.
- **The `--policy-mode mode` pass has never executed anywhere.** Its scope canonicalisation is
  tested, but no job has produced a `mode` record. It will first run in production unless someone
  exercises it. I judged a dedicated probe not worth the compute; that judgement is worth
  revisiting if anything about the four sampling families looks odd.

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
now sound and the axes are declared, but the evaluation-policy-mode split is a genuine UNITS
difference and the second pass that resolves it has never run. If one thing in this project turns
out to be wrong at publication time, my guess is that.
