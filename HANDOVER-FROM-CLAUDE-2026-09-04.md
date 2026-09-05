# Handover notes — the long tail

Written 2026-09-04 by the Claude session that did the pre-production pass, for the Codex session now
working in this tree. **Deliberately excludes what the recent session log already shows.** What is
here is the standing context: facts that are load-bearing, cheap to violate by accident, and not
re-derivable from a diff.

Ownership note: this file is written by that session and nothing else edits it. See the last
section for how to ask it questions.

---

## 0. Two things that are true right now and are not in the log

- **`bt1ptu2e6stuko76s6dd` (curve-preflight2, `dmc_gb` + `alda`) ERRORed and was never diagnosed.**
  It was the first ever run of the `run_scene_dmc_gb` and `run_scene_alda` evaluator families.
  Until someone reads its log, **two of seven evaluator families remain unexercised**, and the
  failure might be in the evaluator, the launcher, or the job shape. Do not assume it is benign.
- **`verify_regime` abstains in the container.** `bt1sgcg49j6d6jk84vuj` emitted the abstention
  **16 times** ("could not read back mode or scene ... UNVERIFIED"). The check announces loudly
  instead of passing silently, which is the design — but it means the regime is currently
  **unverified** for `idaac`, `ppg` and `ibac_sni`, so the protection is not yet protecting. The
  wrapper walk (`_mode` via `.env/._env/._gym_env/.venv/.unwrapped`) does not reach those stacks.
  This matters because the failure it guards against produces **retention ≈ 1.0**, which reads as
  invariance rather than as a bug.

---

## 1. The frame, which everything else is downstream of

Twelve visual-RL baselines on RL-ViGen **robosuite Door**. **The null is each original repository
running its own `train.py`.** That single sentence decides most arguments: a shared harness, a
"small refactor across clones", or a helper that two baselines import are all deviations from the
null and carry a burden of proof. Hermetic-first, duplication-free, **joins carry the burden**.

Corollaries that come up constantly:

- Editing a clone to make it match another clone is almost always the wrong move. Editing **our**
  harness to accommodate a clone is almost always the right one.
- `ext/` is **read-only** per-project downloads. Copy out, edit the copy.
- What can be changed cheaply is *configuration* (a flag the repo already parses). What is expensive
  is *code* in a clone. When both would fix something, take the flag and declare it.

## 2. The facts that invalidate work if forgotten

| id | fact | why it bites |
|---|---|---|
| **C95** | A container-trained checkpoint **cannot** be validly evaluated on this laptop — `MUJOCO_GL=egl` there vs `glfw` here. Same checkpoint read 131.5 in-container and 13.85 locally. | This once invalidated an entire evaluation methodology after the fact. **Every reported number must come from the container.** It is also the whole reason the intermediate checkpoint grid is evaluated in-job rather than brought home. |
| **C55** | The random-policy floor on Door is **1.82**, and it is *regime-invariant* (`randomize_dynamics = False` in every branch of `robosuitevgb/utils.py:67-104`). | A "result" of 2.0 is noise. Retention over a floored denominator is **undefined**, not small. |
| **C69** | Door placement is drawn from the **global** numpy RNG (`UniformRandomSampler` calls bare `np.random.uniform`). | *Any* extra env interaction — including a diagnostic `reset()`/`step()` — shifts every subsequent episode. This is why the new `verify_regime` deliberately does **not** probe, and why adding one now would silently invalidate comparison with records already in `results/records/`. |
| **C70** | `torch.use_deterministic_algorithms(True)` is **ours**, not upstream. | It is a deviation to declare, and it can change throughput. |
| **C3** | `ibac_sni` at 64×64 was a 227× oversized model — 64×64 was taken from IBAC-SNI's *pixel* (TensorFlow CoinRun) branch while the architecture stayed the *MiniGrid* one. Now repaired by porting `impala_cnn` from its own repo. | The general lesson: this project once mixed two branches of one upstream and produced a configuration **nobody had ever run**. Check whether a number was scoped to a different env/scale before treating it as a tie worth preserving. |
| **P6** | Supplies the 100-pixel render `rad`/`soda` need. | At 84, `random_crop`'s `crop_max = 84 − 84 = 0` and its own guard returns the input unchanged — **RAD silently becomes SAC**. A "working" run that is quietly the wrong algorithm. |

Patch classes are **PLATFORM / RESTORES / ENABLES**; the ENABLES set is `P6, P10, P11, P14, P15, P18`.

## 3. Where knowledge lives, and the rule about writing to it

- **`docs/CONSTRUCTION.md`** — the single authority for what is open / decided / resolved. Items
  carry a class (INHERITED / OURS / UNDECLARED / FALSE-CERTIFICATION / DESIGN-GAP).
- **`docs/REGISTER.md`** — dated findings, newest last. The entry count is **test-enforced**
  (`test_docs_not_stale.py::test_the_register_entry_count_is_true`), so adding a row means updating
  the closing count.
- `docs/FAITHFULNESS.md`, `docs/COMPARABILITY_CONTRACT.md`, `docs/EVAL-PROTOCOL.md`,
  `docs/EVAL-DECOMPOSITION.md`, `docs/EVALUATOR-DELTA.md`, `docs/STEP-ZERO.md`, `docs/POINTS-LIST.md`.
- **Recompute, do not trust prose**: `scripts/requirements.py` (R1–R7), `scripts/open_decisions.py`
  (what waits on a person), `scripts/deviations.py`, `scripts/audit_comparability_seam.py`,
  `scripts/audit_shared_evaluator.py`, `scripts/audit_implementations.py`.
  `docs/TASK.md`'s status table is **stale by design** — `requirements.py` supersedes it.
- **Owner's rule: register prose is written with an editor, never a shell heredoc.**

## 4. Standards this project holds itself to

These are not style preferences; each exists because it was violated once and cost something.

1. **Verify before repeating — including your own earlier claim from the same session.** Several of
   this project's worst hours came from a confident statement made twice before being checked.
2. **Order of authority when auditing:** the checkpoint's saved `args` outranks the README, the
   README outranks the prose, and **every disagreement between them is itself a finding**.
3. **An instrument that could not run must never be readable as one that ran and passed.** This was
   the dominant failure mode of 2026-09-04: a knob the runner never read, a checker whose contract
   failure shared an exit code with argparse's usage error, a post-condition asserting a filename
   the descriptor had renamed, and six evaluators that never verified their own regime.
4. **Do not validate an instrument by a ratio.** Use a dispersion test with the sample sizes stated;
   `audit_shared_evaluator.py` does this and it is why `idaac`'s burden could be discharged
   honestly (ours 9.023 sd 6.488 N=20 vs theirs 5.347 N=10, z = 1.46).
5. **One number, one home.** `production-schedule.json` drifted from `plan_production.py` and every
   production shape argued from it was argued from the wrong throughput.
6. **Fix the class, not the instance.** Every fix above got a test that fails on the *category*.

## 5. Traps that have actually bitten, more than once

- **The one-surface read.** A launcher is not the only thing that can pass an argument —
  `datasphere/native/families.json`'s `options` block passes flags too. Concluding "nothing consumes
  X" from grepping `runnable/_launch/*.sh` alone has produced wrong edits repeatedly.
- **`&&` as the last command of a loop body under `set -e`** is the body's exit status, and it has
  silently killed jobs. Use `if`.
- **Pipelines mask exit codes** (`cmd | tail` reports `tail`'s status). This has hidden real errors.
- **The shell is zsh**, which does *not* word-split unquoted parameter expansions. A phantom
  "exit 2" was chased twice before that was the answer.
- **`--families` is required when building a payload.** Without it `contract.py build-payload`
  silently produces a payload with **no clone trees** (139 KB instead of ~62 MB) and the job fails
  far away from the cause.
- **The runner is a separate job input, uploaded fresh at submit.** A broken `run_probe.sh` reaches
  the *next* job, never the ones already running — which is survivable, but means "I fixed it" does
  not apply to in-flight jobs.
- **Payload staleness**: a cfg once pointed at a payload built *before* the edit it existed to
  validate. `contract.py verify-payload --archive P --expect PATH:MARKER` is the gate; note it exits
  **4** for a contract failure and **2** only for a malformed command line.

## 6. Operational constraints (owner's, standing)

- **DataSphere**: project `bt12q57tmrs03pnt8drc`; `GRPC_DNS_RESOLVER=native` on **every** CLI call.
  Tiers **`gt4.1` (168.48 RUB/h) and `gt4i.1` (234.00, NVIDIA L4) only** — nothing more expensive.
  **Max 4 parallel jobs.** `ctrl` needs `CUDA_ROOT=/usr/local/cuda` or its jax import gate fails in
  a way that looks like dependency drift (it is not — that was chased twice).
- **Private by default** for anything uploaded, Kaggle kernels and datasets included. Unpublished lab work.
- **W&B**: key at `secrets/wandb_key.txt`, usable for remote jobs, **never printed or committed**;
  do not store checkpoints under it. Account `arsen4ikvar`.
- **No system cleanups.** Propose them; do not perform them. The narrow exception is your own proven
  scratch — and the *deletion command* must be proven safe, not merely the target.
- **Local**: interpreter `/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python` (install into
  it freely). **MPS only, never CUDA.** Time MPS work with `torch.mps.synchronize()` or the numbers
  are meaningless. Free disk is **73.1 GB** as of today (was ~30; the owner cleared space).
- **The Workflow tool is not the default**; when used, keep it lean and prefer Sonnet 5.

## 7. Numbers worth carrying in your head

- **PPG's auxiliary phase first fires at 65,536 frames** (`n_pi=32` × 2,048 interacts/iteration).
  Below that the ppg column is **PPO exactly** — not a weak PPG. Every ppg number this project holds
  is from 10k runs and is therefore PPO.
- The RL-ViGen five serve **4,000 `num_seed_frames`** of random policy before any gradient update —
  40% of a 10k budget, 1% of 6e5. Much of why short runs sit at the floor.
- **R4's residual is 0.17%**: at a 600k request the seven runner families execute 599,040–600,064
  frames. That is each family's rollout quantum and cannot be removed without editing a clone.
- **Ten of twelve baselines have an undischarged shared-evaluator burden.** Only `drqv2` and `idaac`
  have been shown to measure what their own evaluator measures. This is the honest caveat on any
  number the other ten produce, and it is about the *instrument*, not the baselines.
- **C61, corrected**: it is *not* "a Gaussian's unbounded entropy makes any positive coefficient run
  away" — three siblings refute that at the same 0.01 (`idaac` 0.0206 at 100k, `ctrl` 0.0034,
  `ppg` 0.0008 with a clamp). Only `ibac_sni` inflates (1.4472 at 100k). The default of
  `--entropy-coef 0.0` is therefore an **empirical workaround with the cause not isolated**, not a
  principled setting. The discriminating run is named in `CONSTRUCTION.md#c61`.

## 8. One standing position that appears to have changed — worth confirming with the owner

`RECOVERY-HANDOFF.md` has long said this candidate tree and the versioned original
(`ccm-intro/projects/many-gens-rl-vigen`, branch `nd-ln-architecture-transition`, HEAD `f041f5e1`)
must be reconciled **hunk-by-hunk, manually, with no automatic merge**, and called that the single
largest risk — everything from 2026-08-31 onward exists only here. The file now also states *"This
working tree is the production tree; no pre-run merge is required."*

Those can both be true (the merge deferred rather than cancelled), but they are different claims and
only the owner can retire the older one. **Flagging, not reverting.**

---

## 9. How to ask the Claude session a question

It has the full session context — every job id, why each default was set, and which arguments were
tried and rejected. Proposed protocol, chosen so the two agents can never clobber each other:

**Single-writer files. Never both agents in one file.**

- `notes/ask-claude.md` — **only Codex writes.** Append a block per question:
  `## Q<n> — <one-line topic>`, then what you need, and — importantly — **what you currently
  believe**, so the answer can correct a false premise instead of restating background.
- `notes/claude-answers.md` — **only Claude writes**, answering by `Q<n>`.

Two things that make this much cheaper:

1. **State your belief, not just your question.** Most of the value in this context is negative
   knowledge: which plausible explanation was already tested and refuted, and at what cost. "I think
   X causes Y, am I wrong?" gets a far better answer than "why does Y happen?".
2. **Anything about current file state must be re-verified.** These notes describe the tree as of
   this session's last command. Codex is editing it now; a claim here about a line number or a file's
   contents is a starting point, not an authority.

For anything urgent or ambiguous, the owner relaying a sentence inline is faster than the mailbox
and always works.
