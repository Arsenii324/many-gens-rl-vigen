# Reviews 9 and 10 — triage against the tree

Written 2026-09-05, after Codex ran out of quota. Both reviews read; both are strong. **They found
two things I had missed and one thing I had actively refuted, wrongly.**

---

## Confirmed and fixed: CTRL's evaluator double-resets

Both reviews report it; review 10 spells out the sequence exactly. **They are right and my earlier
refutation (CORRECTIONS #22) was wrong.**

`_SyncVecEnv` auto-resets on done (`vec_env.py::step_wait`) and `_reset_one` advances
`self._episode_indices[index] += 1` on **every** reset. With `run_scene_ctrl` also resetting
explicitly per measured episode, the sequence was:

    explicit reset -> condition 0 -> measured episode 0
    terminal auto-reset -> condition 1, DISCARDED
    explicit reset -> condition 2 -> measured episode 1

So **measured episode *i* ran condition index 2*i*** while the record claimed *i*. ctrl was unpaired
from every other family and its recorded `placement_condition_seeds` were factually wrong.

**Why I got it wrong**: I checked `runnable/_patches/ctrl.patch`, where the constructor swallows
`condition_seed` in `**_ignored`, and concluded there was no counter. That patch is a **provenance
snapshot** — and I had spent part of the same night proving those snapshots drift (five of six were
stale). The live clone passes `condition_seed` into `_SyncVecEnv`. **The clone is the artifact; the
patch is a record of it.**

**Fixed** by resetting once and letting the auto-reset begin each subsequent episode — the pattern
idaac and ppg already used, which is why they were correct. **Verified by instrumenting the live
counter: 0 -> 1 -> 2 -> 3, one index per measured episode** (it was 0 -> 2 -> 4 before).

### Review 10's sharper point about the test, which also applied to mine

> The current pairing gate passes because it verifies the seed machinery syntactically. It does not
> exercise this state machine.

Correct — and my first replacement test had the same flaw in a different place: it drove the env
directly and **passed on the broken code**, because the defect lives in the *caller*. The test now
executes **both** reset patterns and shows they produce different counters, while
`test_ctrl_episode_pairing.py` checks structurally that the evaluator uses the right one. Neither is
sufficient alone.

## Confirmed and gated: IBAC's `procs=16` target cannot start

Review 9's P0, verified. The descriptor **already recorded the measurement** from job
`bt1q6jd096m3re2n7jp2`:

> procs is 1, and that is now MEASURED rather than assumed. With 2 it dies at `torch_rl.PPOAlgo`'s
> parallel env setup with **EOFError** ... MuJoCo GL contexts do not survive a fork ... the same is
> true on Linux with EGL.

And `torch_rl/scripts/train.py:110` **forces** it: `multiprocessing.set_start_method("fork")`.

So the v100 profile's `ibac_sni: procs 16` would **fail at startup**, and my own A14 status note —
which said ibac_sni was "the one that becomes source-faithful" — was exactly backwards. It is the
one target that cannot be applied at all.

`gate_ibac_procs_is_runnable` now fails on any profile that raises procs above 1 while the fork start
method is forced, and A14 carries the correction. The candidate fix (switch to `spawn`) is a real
port, not a one-liner: `penv.py` passes live env objects into `Process(...)`, which spawn must
pickle.

## Already handled before these reviews landed

- **CTRL online-eval JAX RNG** (review 10) — mechanism confirmed, remedy **rejected**:
  `ext/ctrl_public/train_ppo.py:193,202` has the identical rebinding, so patching it is our
  deviation. The gate now states it isolates the placement stream only.
- **Cross-scene pairing** (both) — `scene_id` is inside `placement_condition_seed`, so scene
  comparisons are unpaired. Recorded as **A21** with three options, plus a `CLAIMS-LEDGER` caveat.
  **The headline across-regime contrast is unaffected and that was verified from real records**, not
  argued: train and eval-easy at scene 0 carry byte-identical condition seeds.
- **0/12 current-revision validations** (both) — no longer true for three families. `ppg`,
  `ibac_sni` and `dmc_gb` are now validated under the current revision `a8664a7f98dc`; see
  `EVALUATOR-VALIDATION-STATUS.md`. Validation is *not* discharge, and the table says so.
- **Beta** (review 9) — independently confirms our own finding. Three sources now agree.

## Open, and correctly identified

PPG's auxiliary cadence (A19), IDAAC's Procgen-vs-continuous-control lineage, time-limit semantics,
the source freeze, the 600k canary, and the statistical protocol. All are owner decisions or
production-host work, all on `DECISION-SHEET.md` and `NEXT-ACTIONS.md`.

**Places validation split is no longer "open" as of later the same session — A22 decided it**
(keep `use_val=True`, recorded as a deviation for svea/sgqn/soda, reversible if parity with
published overlay-augmentation numbers is ever wanted). Left "open" here would have been the same
staleness this project keeps finding elsewhere: a triage note not revisited after its own subject
moved.

---

## Re-audit 2026-09-05 (later): a second reviewer pass over all nine reviews

Run as an independent audit with no inherited context, told explicitly not to trust these triage
notes. Four results changed something.

**Confirmed and acted on:**

1. **`penv.worker()` re-seeds nothing** (review 10's deeper, second-order claim about ibac_sni).
   Verified directly: `runnable/ibac_sni/torch_rl/torch_rl/torch_rl/utils/penv.py:4` has no seeding
   call of any kind. With `fork` and Door placement drawn from the global numpy RNG (C69), all
   `procs` workers would generate the **identical** placement sequence. It is invisible today only
   because the EGL crash happens first. The danger was that `gate_ibac_procs_is_runnable` keyed on
   the fork alone and would have gone **green** the moment someone switched to spawn, certifying a
   configuration whose 16 environments are silently identical. The gate now requires both.

2. **The real-environment tests swallowed the bug class they exist to catch** — eight
   `except Exception -> pytest.skip` sites. Fixed; see CORRECTIONS #44. On this machine all 12 now
   pass and **none** skips, so those lines were protecting nothing.

3. **Places365 augmentation is drawn from the validation split, and was tracked by nothing.**
   Confirmed live at `configure_places365_val.py:34-35`. Now A22 on the decision sheet.
   **My own summary of this was itself too strong**: "tracked by nothing" is right about the
   decision surfaces, and wrong about `CLAIMS-LEDGER.md`, which already carried the qualification on
   `sgqn` and `soda` — but not on `svea`, which uses the same overlay path. Fixed there too. The real
   defect was subtler than "untracked": a shared property of three baselines was recorded as a
   per-row detail on two of them, which is how it stayed invisible as a *decision*.

4. **The noise floor.** Raised as belonging to no review: a frozen evaluator still does not
   reproduce itself, because MuJoCo physics and EGL rendering sit outside Torch's determinism
   scope. This project had already measured it (CORRECTIONS #37/#38) but had not written it into
   the definition of "validated". Now in `EVALUATOR-VALIDATION-STATUS.md`.

**One attribution corrected.** The re-audit reported that this file claimed Places365 was tracked on
`DECISION-SHEET.md` and `NEXT-ACTIONS.md`, and that the claim was false. The finding's *substance*
is right — `DECISION-SHEET.md` had zero mentions — but this file never made that claim; it does not
mention Places365 at all, which is precisely how the item went missing. Recorded because an audit's
attribution errors are worth the same scrutiny as the code's.

**Everything else it reported as still-standing** was already tracked and correctly marked: the
uncommitted tree (now 138 paths), zero-of-twelve evaluator validation, no production canary, the
unfrozen statistical protocol, ibac competence, and the external anchor. No new defect there.
