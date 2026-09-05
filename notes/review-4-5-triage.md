# Reviews 4 and 5 — triage against the tree

Written 2026-09-05. Both read in full. Both are strong; review 4 is the most technically substantive
of the five, and **both caught defects in instruments I wrote.**

---

## Verified true, and mine to have prevented

**My `gate_source_tree_frozen` was a false-green.** It read `git status --short`'s *stdout* and never
checked the return code, so where git fails — a packaged artifact with no `.git` — stdout is empty,
the line count is zero, and the gate reported the tree **clean**. That is failure-to-check rendered
as a pass, on the one gate that establishes provenance. **Fixed to fail closed**, with a test that
mocks a failing git (`tests/test_production_gates.py`).

**My `ppg` figure was wrong and I propagated it into the descriptor.** I told Codex the rollout gap
was 8× and that "65,536" was unsourceable; it edited `families.json`'s `constants_note` accordingly,
overwriting text that was **correct**. Sourced now: `runnable/ppg/README.md:34` documents
`mpiexec -np 4`, `train.py:27,131` defaults `num_envs=64`, `ppg.py:252,271` passes `comm` into the
optimizer so gradients synchronise. Upstream is `4 × 64 × 256 = 65,536`; ours is `1 × 8 × 256 =
2,048`. **32×.** Revert requested in `claude-answers.md` A16.

**And the consequence retracts a claim I made twice.** `n_pi=32` was never rescaled, so PPG's
auxiliary phase now fires every `32 × 2,048 = 65,536` frames against upstream's `≈2.1M`. My "PPG
gets nine auxiliary phases at 6e5, so the budget is sufficient" is **a symptom of the rescaling, not
evidence of fidelity.**

## Verified true, new, and not previously known here

| finding | evidence |
|---|---|
| **Nine of twelve baselines carry a resource-forced learning-dynamics adaptation** | `ppg` 32×, `idaac` 16× (`arguments.py:62-67`), `ibac_sni` 16× (`scripts/train.py:41`, `--procs` default 16), `ctrl` 4× (`train_ppo.py:86`, `num_envs` 64) — plus the RL-ViGen five's 300k replay cap against ~1M |
| **Replay cap discards half the experience** | `families.json:90` caps at 300,000 in a 600,000-frame run. The recorded reason is honest: uncapped is 38.8 GiB and no allowed tier holds it |
| **`audit_comparability_seam.py` is wrong about it** | `:654-655` emits *"uniform over the whole run … exceeds 6e5"* whenever a capacity exists, **without comparing it to 6e5**. At 300k both clauses are false |
| **`production-schedule.json` describes the wrong experiment** | rows carry frames `[100000, 500000]` — no 600000 — and still recommend `EVAL_EVERY_FRAMES: 25000` after online evaluation was disabled |
| **IBAC-SNI's evaluator ignores `--device`** | `utils/agent.py:12,15` loads the CPU-saved model and computes `self.device`, **then never uses it**; `preprocess_obss` takes no device. Evaluation always runs on CPU |
| **DMC-GB visual seeding is not paired across families** | `eval_grid.py:318-319` uses `seed + 42` for rad/soda eval envs, matching their native convention. Door *placement* is now paired; the *visual* condition is not |

**One the reviewers did not mention, found while checking the device bug:** `agent.py`'s `argmax`
branch calls `dist.probs.max(...)` — **categorical-only code** that would raise on the continuous
`Normal` policy. We pass `argmax=False`, so it is latent, not live. It should not be left as a trap.

## Superseded since the reviews were written

- **Review 5's red `audit_eval_cadence --check`** ("STALE idaac … train.py:291") now reports
  **12/12 anchors hold** — fixed in the interim.

## Not verified, and I am not asserting them

- Review 4's claim that `FAITHFULNESS.md` says the current IDAAC config matches a *continuous-control*
  IDAAC precedent (rollout 2048, γ=0.99, lr 3e-4, 10 epochs) while production runs the Procgen family
  (γ=0.999, lr 5e-4, 1 epoch). The executed values I recovered — `lr 5e-4, gamma 0.999,
  num_processes 4, num_steps 256` — are consistent with the Procgen half of that claim. I have not
  located the continuous-control precedent text, so the contradiction is **plausible and unchecked**.
- Review 4 section M's specific list for the environment lock, beyond what is already recorded.

## The synthesis both reviews approach and neither states

Every one of those nine adaptations was forced by **DataSphere's 4–8 cores and 27 GiB ceiling**.
Production is **another V100 with Docker and a Linux environment of our choice**.

So the largest remaining class of fidelity criticism may be an artefact of hardware we are leaving
behind. **Core count and RAM on the production host is one question**, and with many cores and ~40+
GiB most of that table closes — converting nine declared learning-affecting adaptations into a
configuration that matches the sources. That is worth asking before any schedule is frozen, because
it changes what the production configuration *should be*, not merely how fast it runs.


---

## Update 2026-09-05 — items previously recorded-but-unverified, now checked

Three of review 5's rows I had recorded without confirming are **verified true**:

- **`gate_release_suite_green` overclaims** — it inspected one docs test and grepped for `xfail`
  anywhere in it. Mine; fixed to run the fast audits and to state that it is not the full suite.
- **Container pinned by a mutable tag** — `source-lock.json` has
  `nvidia/cuda:12.2.2-runtime-ubuntu22.04`, no digest. Now a gate, scoped to migration since the
  image that matters is the V100 one.
- **`results_table.py` bootstraps pooled episodes** (`:116`), with no seed clustering — the exact
  inference the corrected plan forbids. Now a gate.

**Review 5's provenance-asymmetry claim does NOT reproduce.** Comparing a retained `train` row
against a retained `offline-eval` row, the field sets are **identical** — nothing is only in one.
If the claim holds it must concern the *pre-normalization* `offline_eval_*.jsonl` output rather than
the records that come home, which is a narrower statement than the review made. Not asserting it.

Still recorded-but-unverified: review 4's IDAAC continuous-precedent contradiction (I could not
locate the precedent text) and its section M list beyond the digest.
