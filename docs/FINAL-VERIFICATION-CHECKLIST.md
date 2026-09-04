# Final verification checklist — "most finished state"

Living document for the 2026-08-14 push to bring the project to a finished, parity-verified state
and transition toward Nd_ln-shaped code without regressing the protocol. Updated as each item
closes; nothing is marked DONE without the evidence line that proves it.

**Rule for this document**: a row moves to DONE only with (a) what was checked, (b) how (command
or file:line), (c) the result. "I believe X" is not evidence; "ran X, got Y" is.

---

## 1. Per-baseline parity status

> **Four rows below were falsified 2026-08-16 and are corrected in place.** They shared one
> mechanism, which is worth naming once rather than four times: **"byte-identical to an audited
> port" inherits that audit's scope, and nobody had checked what the scope was.** Measuring
> textual descent (`difflib` over code lines, `scripts/state.py`) against the *authors' own*
> repositories showed the audits had never reached them:
>
> | baseline | descends from | descends from the authors' repo |
> |---|---|---|
> | `alda` | `gen-rebuttal/vigen-idaac/vigen_alda` at ~100% | `ext/ALDA_Official`: **0%** — flag **withdrawn** 2026-08-16 after audit; a renamed reimplementation, not an unread reference |
> | `idaac` | same sibling port | `ext/idaac` (`rraileanu/idaac`): **0%** |
> | `ppg` | nothing | `ext/phasic-policy-gradient`: **0%** — but note the construction was *algorithmically* closer than 0% suggests: it already had dual encoders, unclipped value loss and no grad clipping. Descent measures provenance, not quality |
> | `ibac_sni` | DZ's PyTorch port | `ext/IBAC-SNI`: rebuilt base-first, see below |
>
> **0% descent is a flag, not a verdict** — `ctrl` reads 0% legitimately (JAX/Flax crossing) and
> `rad` reads 0% legitimately (thin wrapper over `sac.py`, which reads 93%). What makes these four
> different is that a reachable, same-framework, first-party reference existed and was not the
> thing the port descended from.

| baseline | status | evidence |
|---|---|---|
| `random` | negative control, nothing to verify | — |
| `drqv2` | faithful; stddev schedule fixed 2026-08-13 | `docs/FAITHFULNESS.md` §2, VALIDATION.md |
| `svea` | uses SODA's overlay not SVEA's conv; DrQ-v2-based not SAC — **known, documented divergence** | FAITHFULNESS.md §2 |
| `sgqn` | `aux_lr`/`sgqn_quantile` fixed 2026-08-10; shared-encoder mechanism traced and documented; critic weight 0.9 (code) vs 0.7 (paper) — **deliberately left**, matches RL-ViGen's own published results | FAITHFULNESS.md §2, §6 |
| `curl` | matches RL-ViGen's own `curl_config.yaml` verbatim; **verified 2026-08-14** the original paper's momentum(EMA) key encoder is absent from RL-ViGen's own port (one shared encoder, not two) — inherited faithfully, now documented in the registry note rather than left implicit | FAITHFULNESS.md §2, `rlgen/registry.py` |
| `drq` | nstep fixed 2026-08-13 (1, not inherited 3) | FAITHFULNESS.md §4 table |
| `rad` | faithful per FAITHFULNESS.md §3 | — |
| `soda` | faithful per FAITHFULNESS.md §3 | — |
| `alda` | **CORRECTED 2026-08-16.** Byte-identical to gen-rebuttal's port — that `diff` still holds. What it does *not* establish is fidelity to ALDA: that port descends **0%** from `ext/ALDA_Official`, which is PyTorch with a conventional layout, so no framework crossing excuses it. This project also has **no `alda/buffer.py` at all** — it runs the shared `rlgen/replay.py`, so the sibling's own `BufferVerifier` transition-alignment guard has no equivalent running here. `utd` 1.0→0.25 stands (red-green tested). **AUDITED 2026-08-16 and the flag was withdrawn**: the reference's own main path (`AssociativeLatent`, `alda_trainer.py:226`) IS what this port implements — `nets.py`'s `Continuous`/`Quantized`/`OuterEncoder` and `config.py:131`'s `latent_model="associative"` default track `disentangle/latents/*` under renamed classes and a flattened layout. Same situation as `ctrl`: a reimplementation whose text cannot descend because the structure differs. **Not rebuilt, deliberately. Status: concept-level agreement established; never numerically checked (no T1/T2/T3), and the `BufferVerifier` gap stands.** | `scripts/state.py`; `docs/INTEGRATION-DELTA.md`; FAITHFULNESS.md §3 |
| `idaac` | **CORRECTED 2026-08-16.** Same two-hop as `alda`: descends **0%** from `rraileanu/idaac` (`ext/idaac`, the author's own repo, PyTorch). Newly established: that repo ships **no continuous head at all** (`ppo_daac_idaac/distributions.py` defines only `Categorical`; `model.py:313,360` wires it unconditionally), so it can settle the encoder, storage and losses but never the policy head. Separately, `config.py:152`/`model.py:84` justify the continuous head as a `DEVIATION from [IK]` — Kostrikov's `pytorch-a2c-ppo-acktr`, which **is not on this disk**. The per-value corrections stand. **Status: unaudited against the authors' code; one load-bearing citation uncheckable.** | `scripts/state.py`; `docs/REGISTER.md` 2026-08-16; FAITHFULNESS.md §4 |
| `ppg` | **CORRECTED 2026-08-16.** The per-value citations (`n_pi`, `aux_epochs`, `beta_clone`, the 256→2048 rollout fix) all stand — values were checked against the paper and code. What was never checked is the *module*: it descends **0%** from `ext/phasic-policy-gradient` across all four files, while that reference is clean (`@7295473`, 0 dirty, 19/19 parse) and **PyTorch**, so no crossing excuses it. Matching hyperparameters is not the same claim as implementing the algorithm. **Status: construction with a reachable same-framework base; queued for base-first rebuild, where a real T1/T2 is available.** | `scripts/state.py`; FAITHFULNESS.md §4 |
| `ibac_sni` | **CORRECTED 2026-08-16, then rebuilt.** The old claim — "VIB mechanism matches DZ's reference formula-for-formula" — was true and measured the wrong thing: **DZ's port is itself a Construction**, a re-derivation from the paper, while the authors' own release (`ext/IBAC-SNI`, `microsoft/IBAC-SNI` @ `6b3a58b`) sat in-repo unread and ships **its own PyTorch bottleneck**. Matching a re-derivation formula-for-formula inherits its errors exactly. Against the authors' code the old module diverged on six points, two changing the algorithm: sigma was `exp(clamp(log_sigma,-10,2))` where both first-party paths use `softplus` (CoinRun with a `-5.0` offset, so std starts ~0.0067 not 1.0), and the value head was **mixed** under SNI where `policies.py:161` sets `vf_run = vf_train = fc(h_vf,'v',1)` with the authors' own comment *"VIB for regression seems like a bad idea"*. Also absent: the `--l2 0.0001` term, `--nr-samples 12`, and the KL's `/log 2`; and a `sni_lambda` knob existed that the reference does not have. **Rebuilt base-first** from `joonleesky/train-procgen-pytorch` @ `1678e4a` (vendored, sha256-pinned). Note the 2026-08-14 value-head fix cited here was a *different* defect in the *old* module and was genuine. **Status: rebuilt; algorithm tier T4 (no TF-crossing transplant attempted); the only numerical checks are against the PPO host.** | `docs/INTEGRATION-DELTA.md`; `tests/test_ibac_sni_base_parity.py`; `rlgen/algos/ibac_sni/_upstream_1678e4a/PROVENANCE.md` |
| `ctrl` | **zero independent verification available anywhere** — no sibling project, no DZ reference. Three structural divergences from the paper documented (missing Sinkhorn loss term, same- vs neighbouring-cluster positives, shared optimizer). Highest remaining risk. | FAITHFULNESS.md §`ctrl`, §5 item 8 |

## 2. Cross-project corroboration used

- `gen-rebuttal` (sibling project, real GPU runs): IDAAC (R2, R9, R16, R21 — all inherited already-fixed), ALDA (utd/D1 — found live-broken here, fixed).
- DZ's `IBAC_SNI_torch`: mechanism formula match confirmed; no continuous-action code anywhere (checked, not assumed — `Categorical` head, `Normal` used only for the VIB latent).
- Original IBAC-SNI author code (`ext/IBAC-SNI`): TF CoinRun + the authors' own torch port, both checked directly for the value-head routing question. No Appendix E / continuous-control section exists in the IBAC-SNI paper — confirmed by reading the actual appendix table of contents (A–D only). The "Appendix E" association was a cross-paper mixup with IDAAC.
- Original CTRL paper source + `bmazoure/ctrl_public` JAX repo: three divergences found and documented, one fixed.

## 3. Self-corrections made this session (kept visible, not scrubbed)

Per the project's own standing rule (`docs/RIGOR.md` "verify a claim before repeating it"), every
wrong claim below was caught and corrected in place, not deleted:

1. IDAAC minibatch size — believed broken (8 samples), traced fully, found correct (64 samples);
   the *dataclass defaults* were stale, not the training dynamics.
2. `evaluate.py` reproducibility — believed broken per an uncited claim, then wrongly believed
   "not present" (conflating with gen-rebuttal's R20), then **measured** on the real backend and
   found working, better than assumed.
3. IBAC-SNI critic — believed to bypass the bottleneck entirely (wrong: never checked `cfg.algo`);
   actual defect was the opposite (too much noise reaching the critic, not too little). Corrected
   2026-08-14, this session.

## 4. Remaining open items (not silently dropped)

| item | status | why not closed |
|---|---|---|
| `load_state_dict` swallows unknown keys | **FIXED 2026-08-14** | all 3 sites (`DrQV2Adapter`, `SacAdapter`, `PPOFamilyAdapter`) now raise `KeyError` on a mismatched key; red-green verified across all 3; `test_load_state_dict_refuses_a_mismatched_checkpoint_instead_of_loading_it_partially` |
| SGQN critic weight 0.9 vs 0.7 | deliberately left | matches what RL-ViGen actually runs; changing it would need a declared patch (P6) |
| `ctrl` — no independent check exists | inherent limitation | no sibling project or DZ reference covers CTRL |
| `test_gaussian_machinery.py` | **APPLIED 2026-08-14** | copied into `tests/`, redundant per-file sys.path hack removed (conftest.py already handles it), all 5 pass |
| `ibac_sni` value head reads noisy pass during training | **FIXED 2026-08-14** | see §1 table; corrected an earlier WRONG diagnosis (critic "never sees the bottleneck") in the same session |

## 5. Suite health (updated per run)

- Before this session's cross-check work: 158 tests.
- After config/doc fixes + `nd_ln_parity.py`: 169 tests, 168 passed, 1 skipped, 0 failures.
- After IBAC-SNI value-head fix + `load_state_dict` fix + `test_gaussian_machinery.py`: 178 tests,
  177 passed, 1 skipped, 0 failures.
- After `nd_ln_style_train.py` + its first 4 tests: 182 tests, 181 passed, 1 skipped, 0 failures.
- After adding the differential/hyperparameter-parity/preflight tests to
  `tests/test_nd_ln_style_train.py` (§6) — the pass that caught the seeding-gap finding in §10 —
  and cherry-picking the seeding fix back to `main`: **`main` 181 tests (180 passed, 1 skipped, 0
  failed, exit 0), `nd-ln-architecture-transition` 188 tests (187 passed, 1 skipped, 0 failed, exit
  0).** Both counts are fresh, cold reruns performed 2026-08-14 as the closing step of this
  document (`pytest tests -q`, tail read directly, and cross-checked against
  `pytest --collect-only` per-file sums — not inferred from a background exit code alone, per §7's
  own rule). Every fix landed this session is additionally red-green verified individually (see §3
  and the commit messages).

## 6. Nd_ln-architecture transition — DONE, staged per the plan below

`nd_ln_style_train.py` (repo root) + `tests/test_nd_ln_style_train.py` (7 tests, grown from an
initial 4 -- see below). An Nd_ln-shaped CLI/console-output entry point for ALDA that calls
`rlgen.trainer.train` directly -- the SAME function `train.py --config alda` calls -- so there is
exactly one training loop, not two. Verified:

- Argument names mirror `Nd_ln.py`'s own (`--seed`, `--total_timesteps`, `--task_name`,
  `--train_mode`, `--eval_mode`, `--eval_frequency`, `--eval_episodes`) wherever a concept
  corresponds; Nd_ln.py's noise-scheduler flags are NOT reproduced, because they belong to the
  different algorithm Nd_ln.py trains (a disentangled encoder + gradient-reversal discriminator,
  not ALDA's VQ codebook -- `DISCREPANCY_MATRIX.md` T11/X6).
- End-to-end tested on the **synthetic** backend (fast, in the suite) and manually smoke-tested on
  the **real** robosuite backend (40 frames, CPU, exit 0, real `episodes.csv` produced) -- both
  runs confirmed the artifact schema matches every other baseline's (`tags.EPISODE_COLUMNS`).
- The Nd_ln-shaped final printout (`eval_metrics/episode_return` etc., DZ's own tag names) reads
  back the SAME `episodes.csv` the training loop already wrote, via `tools/nd_ln_parity.py`'s
  reader -- one measurement, two ways of printing it, never a second run.
- Refuses a retention ratio against a near-zero denominator (observed directly on the real smoke
  run: Door's near-zero reward regime at 40 frames triggered exactly this refusal, correctly).
- **Three more tests added after the initial 4**, per the user's explicit ask for the strongest
  verification the transition code itself could carry, not just tests of what it produces:
  `test_differential_wrapper_vs_canonical_path_agree_on_the_constructed_agent` (builds the same
  ALDA agent via `nd_ln_style_train._canonical_alda_agent` and via the wrapper's own construction
  path, asserts byte-identical weights and actions), `test_hyperparameter_parity_between_the_two_construction_paths`
  (every `AldaConfig` field, not just the ones that happened to differ), and
  `test_preflight_self_check_is_present_and_would_catch_a_drift` (the wrapper's own
  `preflight_check()` runs before every real training call, `main()` refuses with exit code 3 on a
  mismatch rather than training on drifted hyperparameters silently). The differential test is the
  one that **found the §10 seeding-gap finding** -- it failed on first write, not because the test
  was wrong, but because the two paths genuinely produced different weights.

**What this deliberately does NOT do**: replace the 10-scene evaluation protocol, narrow episode
counts below what's configured, or reimplement any part of SAC/ALDA. `--eval_episodes` sets
episodes-per-scene; all 10 scenes are still evaluated and logged normally.

## 6a. Nd_ln-architecture transition — plan (superseded by the DONE section above; kept as the
record of what was decided and why, since the instruction was to use git rather than lose this)

Per the user's explicit framing ("first make your version work okay in a checkpoint that's
verified and then try the transition") and the `faithful_nd_ln.py` lineage's own hard-won lesson
("do not restate the reference; call it" — reimplementing SAC/ALDA to match Nd_ln.py's shape is
where every bug in that lineage lived):

1. **Checkpoint (git)**: commit the current verified state to `main` before any structural work.
2. **Branch**: do the transition on a feature branch, so `main` stays the known-good state the
   whole session's verification applies to.
3. **What "transition to nd_ln-architecture" means here, decided rather than assumed**: NOT
   replacing the 10-scene/100-episode protocol with Nd_ln.py's single-scene/10-episode one —
   `DISCREPANCY_MATRIX.md` documents concrete, measured defects in that shape (E1: ~64% relative
   SE from single-scene sampling; T1: no truncation bootstrapping; T6: wrong UTD). Regressing to
   it would undo verified work. Instead: build a genuine Nd_ln-shaped **entry point** — a
   single-scene-friendly training/eval driver whose *architecture* (one script, periodic eval,
   TensorBoard-style logging, `evaluate_policy(env, num_episodes=N)` shape) matches what DZ
   recognizes, but which calls into the SAME audited `rlgen.trainer`/`rlgen.algos.alda.agent`/
   `rlgen.evaluate` machinery rather than reimplementing SAC — extending `tools/nd_ln_parity.py`'s
   already-applied "wrap, don't reimplement" principle from reporting into the training entry point
   itself.
4. **Verify structurally** before any real run: unit tests, a synthetic-backend smoke run, THEN a
   short real-backend smoke run (MPS + glfw work locally, confirmed this session).
5. **Merge back** once green, with the branch preserved (not deleted) so the pre-transition state
   is recoverable by name, not just by reflog.

## 7. Final adversarial review pass (do this LAST, after everything else)

Not a re-read for typos. For each of the 12 baselines and every file touched this session:
- Re-derive the claimed fix from its cited source directly (re-open the PDF/repo, don't trust the
  earlier note).
- For every "X and Y match" claim, check the actual runtime values, not the dataclass defaults —
  this exact class of error occurred three times this session (see §3) and is the single most
  likely place a fourth one hides.
- Run the full suite once more, cold, and read the tail for the pass/fail line directly — do not
  infer it from a background task's exit code alone.
- Check `git status`/`git diff --stat` against this document's own list of touched files —
  anything touched but not accounted for here is a gap in this checklist, not a reason to trust
  the checklist.

## 8. Git state — "use git not to lose the versions"

```
main                            3e4dbeca  Seed torch/numpy/random before agent construction; ...
  ↑                             0033a462  Complete the verification checklist: ...
  ↑ (branch point)               13022d53  Fix exploration schedule, ALDA utd, ... [THE CHECKPOINT]
                                 |
nd-ln-architecture-transition   a093f1f0  Add differential/hyperparameter-parity/preflight tests
                                 dcef9efd  Seed torch/numpy/random ... [same content, cherry-picked to main as 3e4dbeca]
                                 4d6b0c23  Complete the verification checklist: ...
                                 3d2bb5a8  Add nd_ln_style_train.py ...            [THE TRANSITION]
```

`main` holds every verification/parity fix from this session, INCLUDING the seeding-gap fix
(§10) — cherry-picked from the branch (`dcef9efd` → `3e4dbeca`) once it was confirmed foundational
rather than transition-specific, since it touches both trainers every baseline goes through, not
just ALDA. The transition branch holds everything `main` has plus the additive Nd_ln wrapper and
its differential/parity/preflight tests — a strict superset, not a fork that diverges. `main` is
therefore recoverable by name at any point, not just via reflog, and the transition can be
reviewed, extended, or dropped without touching the verified baseline. Both branches confirmed
clean (`git status` — nothing to commit) and both confirmed green on a fresh, cold, full-suite run
performed as the last step of this document (§5): `main` 181/181 non-skipped passing, branch
188/188 non-skipped passing, exit 0 on both, counts cross-checked against `pytest --collect-only`.

## 9. Final adversarial pass — actually performed, not just planned

Per §7's own rule, done after everything else, before writing this section:

- Re-derived the IBAC-SNI value-head claim from the reference files directly a second time
  (`ext/IBAC-SNI/coinrun/coinrun/policies.py:149-189`, `ext/IBAC-SNI/torch_rl/model.py`), after
  first catching my own wrong diagnosis mid-session — the correction is documented in place in
  `docs/FAITHFULNESS.md`, not silently replaced.
- Checked every "X matches Y" claim in the diffs against runtime values specifically (not
  dataclass defaults) for `configs/vigen.yaml`, `rlgen/algos/idaac/config.py`,
  `rlgen/algos/alda/config.py` — this exact class of error occurred three times this session
  (IDAAC minibatch size, `evaluate.py` reproducibility, IBAC-SNI critic routing) before being
  caught, so it was the first thing re-checked here.
- Found one real inconsistency on this pass: `docs/VALIDATION.md`'s mutation-sweep triage table
  still said `load_state_dict`'s defect was "recorded... not yet fixed" after the fix had already
  landed. Corrected in place (see the commit).
- Grepped every doc for the fixed defect's description (`load_state_dict.*silent`) to check for
  other stale copies — found none beyond the one above.
- Ran the full suite fresh, cold, three separate times across the session's later fixes (not
  reusing an earlier result), read the tail of each log directly for the pass/fail line rather
  than inferring it from a background task's exit code alone.
- `git diff --stat` cross-checked against this document's own file list (§1 evidence column, §3,
  §6) — no file touched this session is absent from this checklist's account of it.

## 10. MAJOR FINDING, post-transition: weight initialisation was never seeded, repo-wide

Found by the differential test written for `nd_ln_style_train.py` (§6) when it failed
unexpectedly — two agents built from the identical declared seed produced different actions.
Traced to the actual cause rather than patched around: **neither `rlgen/trainer.py::train` nor
`rlgen/trainer_onpolicy.py::train_onpolicy` ever called `torch.manual_seed`**, for any of the 12
baselines, ever. `protocol.seed` genuinely controls the environment (episode selection,
reproducible evaluation — verified 2026-08-13) and `RandomAgent`, but not neural network weight
init. A seeding utility existed with zero callers the whole time
(`rlgen/algos/soda_utils.py::set_seed_everywhere`).

**Fixed in both trainers.** Verified three ways:
- `test_off_policy_training_is_reproducible_from_a_declared_seed` /
  `test_on_policy_training_is_reproducible_from_a_declared_seed` (`tests/test_contract.py`) — the
  REAL production entry points, called twice, checkpoints compared recursively (module weights
  AND optimiser state, not just top-level tensors — a naive flat comparison breaks on optimiser
  state dicts, caught and fixed while writing this test).
- `test_different_seeds_still_produce_different_weights` — the fix must not have collapsed every
  seed to one.
- Red-green: reverted both trainer files, confirmed both new tests fail without the fix, restored,
  confirmed byte-identical to backup, confirmed green.

**Impact: none on any existing result**, because none exists — zero real training runs as of this
finding (`docs/dz-report-ru.md` §1). This is the best possible time to have found it. Documented
prominently in `docs/VALIDATION.md` §5 (which also had a THIRD stale copy of the already-corrected
"episodes are not byte-reproducible" claim, found and fixed in the same pass — grepping for a
defect's name does not find every restatement of its conclusion).

**Cherry-picked to `main` as commit `3e4dbeca` (from `dcef9efd` on the transition branch),
2026-08-14** — it is a foundational correctness fix, not specific to the transition, and it
touches the two files every single baseline's training goes through. `main` re-verified green
afterward with a fresh `pytest tests -q` run (181 tests, 180 passed, 1 skipped, 0 failures, exit
0, cross-checked against `--collect-only`'s per-file sum) — see §5, §8.

## 11. A further deep pass, requested explicitly after §9 ("review deep")

Not a re-read. Traced concrete call graphs (who actually invokes what, at runtime) rather than
trusting a method's name or its presence in a class.

**Found and FIXED**: `Learner.state_dict`/`load_state_dict` (`rlgen/algos/idaac/algo.py`, was
lines 281-307) — a hand-curated pair covering exactly `{policy, policy_opt, value_net, value_opt,
disc, disc_opt}`, with **zero callers anywhere in the repo**. The actual checkpoint path is
`PPOFamilyAdapter.state_dict`/`load_state_dict` (`rlgen/agents.py`), a generic reflection over
`vars(self.learner)` that the adapter uses instead — confirmed by grepping for `.learner.state_dict`
/`.learner.load_state_dict` (zero hits) and by checking that the one test which round-trips a
saved-and-reloaded checkpoint (`test_load_state_dict_refuses_a_mismatched_checkpoint_instead_of_
loading_it_partially`, `tests/test_pipeline_integrity.py`) builds its agent through `spec.build`
and calls `.state_dict()`/`.load_state_dict()` on that adapter-level object, never on a bare
`Learner`. Had the dead pair ever been called, it would ALSO have been wrong for `PPGLearner`/
`IBACSNILearner`/`CTRLLearner`, silently omitting `vib`/`ctrl_predictor`. Removed rather than kept
as a "for reference" artifact — CLAUDE.md's own rule ("if you are certain that something is
unused, you can delete it completely") and the exact same class of defect this session already
found once (`rlgen/algos/soda_utils.py::set_seed_everywhere`, §10) — dead code that reads as
load-bearing is worse than no code, because it is what a future reviewer (or this reviewer, on
first read) reaches for first. Full suite re-verified green after removal (targeted subset first:
`-k "idaac or ppg or ibac or ctrl or pipeline_integrity or checkpoint"`, 45 passed; then the full
suite, unchanged pass count).

**Found, then RESOLVED by the owner as "not wanted" rather than fixed**: no baseline's checkpoint
captures enough state to resume training, which this pass first read as a gap because
`rlgen/algos/alda/config.py`'s own comment describes a plan that sounds like it needs one ("launch
[Lift] at 1.1M first and extend by resume"). Raised with the owner directly rather than assumed.
**Correction from that conversation**: `gen-rebuttal`'s own `--resume` was never a designed
feature — it exists because a real run was launched on cloud compute for a fixed step count, the
checkpoint was downloaded afterward, the replay buffer was not, and continuing required a warm
restart out of operational necessity. The owner's judgement: eval-only checkpoints are the right
scope, and checkpointing a full replay buffer (tens of GB per run at this project's `buffer_
capacity`) would be undesirable on its own terms regardless of whether resume is wanted. So this
closes as "investigated, and correctly not built" rather than "open, flagged for later" — see
`docs/VALIDATION.md` §5 for the full writeup, corrected in the same conversation.

Suite re-verified after this pass: `pytest tests -q` on `nd-ln-architecture-transition`, exit 0,
0 failures (the removal in this section is the only code change; the rest is documentation).
