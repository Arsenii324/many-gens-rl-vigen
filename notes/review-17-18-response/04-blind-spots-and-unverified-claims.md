# Blind spots, unverified claims, and things I only noticed while writing this document

This file exists because the owner explicitly asked for it and warned, correctly, that a blind
spot during the work is likely to also be a blind spot during writing unless deliberately worked
against. What follows is an attempt to work against that: a systematic pass over both reviews and
this session's own response to them, listing every place I am not confident, in addition to (not
instead of) the confidence labels already given in `01-review-17-item-by-item.md` and
`02-review-18-item-by-item.md`. Read those two files for the itemized claim-by-claim detail; this
file collects what matters most and adds what I found only by deliberately looking for it.

## Demonstrated, not hypothetical: I already missed one thing this way

While writing this document I checked whether `docs/PART2-METRIC-INVENTORY.md`'s Finding 5 —
which my own new test (`test_the_split_is_still_nine_three` in `tests/test_observation_geometry.py`)
explicitly asserts must be updated "in the same commit" as any frame-stack-split change — had
actually been updated when I moved idaac from the single-frame column to the stacked column. **It
had not.** The doc still said "8/4" and still listed `idaac` as single-frame, three separate
places, until I found and fixed it (commit `2860353`) specifically while preparing this response.
The test suite never caught this, because nothing in the test suite checks that document against
the code — only `test_observation_geometry.py` and `test_comparability_seam_audit.py` do, and I
had already fixed both of those. This is exactly the failure shape review 17's documentation
correction names (`historical findings survive after the implementation they describe has been
superseded`) and review 18's `DECISION-SHEET.md` criticism names (a reviewer should not have to
infer which of several documents is current) — caught, this time, only because the owner asked me
to write a document forcing a second pass, not because any instrument in the project caught it.
**Update: I ran that grep rather than leaving it as a stated intention, and it surfaced something
more significant than the count mismatch itself.** `grep -rn "8/4|8 of 12|four Procgen|..."
docs/ notes/` turned up roughly two dozen hits; most were a *different* 8/4 or 4-of-12 split
entirely (critic-loss formula families, reward-normalizer scope, time-limit handling,
"continuous ground truth exists for") and were correctly left alone. A handful were genuinely
about the frame-stack axis and genuinely stale: `docs/FAITHFULNESS.md` ("all four Procgen methods
run without frame stacking"), `docs/SYSTEM.md`'s summary of `PART2-METRIC-INVENTORY.md`'s own
content, and a backward-reference inside `PART2-METRIC-INVENTORY.md` itself that had quietly
started implying two *different* axes (frame-stack, and on-policy-vs-off-policy algorithm family)
were the same fact, because they used to share the same four-baseline membership by coincidence.
All fixed (commit `4031c04`).

The more significant find was in `docs/CONSTRUCTION.md#c2`, this project's own register entry for
the frame-stack split. Its 2026-09-04 "DEFAULT SET" reasoning argues `idaac`'s adversarial head
makes frame-stacking *structurally incoherent* — and its own "Provenance" paragraph honestly flags
that argument as "reasoning from each method's own mechanism, not a citation — no document in this
project records an architectural block on frame stacking." That citation now exists, from the
primary source, and says the opposite (this is exactly the same primary-source read that produced
DECISION-SHEET A35 in the first place, earlier in this session, before either external review
arrived). **This means this project's own register carried a since-falsified theoretical argument,
self-labeled as weak evidence, for at least several days, without anyone going back to correct it
once the falsifying evidence existed** — including me, until writing this document forced a second
look at a document I had not touched since finding the correction in A35 itself. I added a
correction note rather than rewriting the entry's body, per this project's own convention, and
explicitly did not extend the same scrutiny to `ctrl`'s "double-counting" or `ibac_sni`'s
"mis-calibration" arguments in the same entry — I have not checked those against any primary
source, and they may or may not hold up the same way `idaac`'s did.

**I still do not know how many more instances of either pattern exist** — a stale count, or a
stale *argument* whose premise was later disproven elsewhere without the original document being
told. I ran one grep for one axis (frame stacking) because that was the axis this session's own
work happened to touch. I did not run the equivalent search for any other axis this session
touched or corrected (the SAC/DDPG backbone split, the CTRL paper-vs-code numbers, ALDA's
500k/600k budget, SGQN's release-code-vs-Table-6 gap) to check whether *those* corrections also
need propagating into a register entry's own stated reasoning somewhere I haven't looked.

## CLOSED after this document's first draft: CTRL's paper-table numbers

This section originally named CTRL's paper table as this response set's single highest-impact
unverified claim — both reviews agreed on the same numbers, but I had only cross-corroboration
between them, not a primary-source read of my own. Named here as an example of the document
identifying its own gap and then that gap actually getting closed, not left as a standing
confession: `ext/papers-sorted/CTRL-Cross-Trajectory-Representation-Learning/latex-source/
appendix.tex` was present in `ext/` all along (I had genuinely not checked), I read it directly,
and every number both reviews cite is exactly correct. The one thing that read turned up that
neither review's phrasing preserves — the paper specifies one shared learning rate for RL and
representation learning together, not two independently-tuned rates that coincide at 5e-4 — is
now recorded in `docs/CONSTRUCTION.md#c97` and `01-review-17-item-by-item.md`'s CTRL section.
This is the clearest demonstration in this whole response set that "named as a blind spot" and
"left as a blind spot" are different things, and that closing one is often cheap once named.

## Operational risk I introduced and did not fully think through: IDAAC-C2's throughput/memory profile

Making IDAAC-C2 the production default changed the per-update compute pattern substantially: 10
PPO epochs instead of 1, 32 minibatches instead of 8, one 2048-step rollout instead of sixteen or
four 256-step rollouts. `scripts/audit_job_budgets.py`'s `MEASURED_TRAIN_FPS["idaac"] = 30` is a
number measured under the *old* recipe. I never re-measured or even estimated the new recipe's
actual frames-per-second, because no new idaac job config has been built or submitted under the
new recipe yet — only the descriptor (`families.json`) changed, and every idaac config
`audit_job_budgets.py` currently checks is a historical, already-superseded artifact whose "ok"
status says nothing about a config that does not exist yet. **The first real submission under this
new recipe should not trust the old throughput number for its timeout**, and I did not flag this
loudly enough anywhere else before writing this document. Related, same root cause (nothing has
actually run the new recipe remotely yet):

- `fixed_peak_gib: 3.17` (idaac's memory ceiling in `families.json`) was measured at
  `num_processes=4`. The new recipe uses `num_processes=1` (probably less memory from that alone)
  but `num_steps=2048` and correspondingly larger rollout-storage tensors, plus a 32-minibatch
  gradient step and 10 epochs of it. I have not reasoned through whether 3.17 GiB is still a safe
  ceiling; I only asserted, in a commit message, that it's "likely a safe overestimate" without
  actually computing or measuring anything. That assertion should be treated as a guess, not a
  verified fact.
- `cells_per_job: 2` (packing two idaac cells per DataSphere job) — unexamined against the new
  memory/compute profile.
- `tier: "gt4.1"` — unexamined against whether the new recipe's compute pattern is still
  well-suited to that GPU tier.
- The entire remote pipeline — the actual bash-to-python argv threading through `idaac.sh`, the
  CUDA-specific code path (`IDAACRolloutStorage` hardcodes `self.device = 'cuda'`, a fact this
  project's own `idaac.sh` comments already name as a reason a green local run "proves the env
  integration, NOT the CUDA path"), real multi-hour training stability, actual checkpoint
  save/load round-tripping with the new 9-channel network shape — **none of this has been run.**
  Every verification I did this session was local, on CPU (or MPS pretending to be CUDA via this
  project's own shim), covering construction, a forward pass, and a five-step rollout. That is
  real evidence the wiring is not obviously broken; it is not evidence the new recipe trains, or
  even runs to completion, on the actual target platform.

## A related, smaller operational rough edge: old checkpoints under the new code

A checkpoint trained under the old idaac-P recipe (frame_stack=1, 3-channel first conv layer)
loaded under the new default code (which now constructs a 9-channel network unless
`--frame_stack=1` is explicitly passed) will fail with a PyTorch shape-mismatch error at
`load_state_dict`, not a clear message saying "this checkpoint predates the C2 transition." I did
not add any check or friendly error for this. It is a real, if minor, discoverability problem for
whoever next tries to resume or re-evaluate an old idaac-P checkpoint without already knowing this
document exists.

## C98 (the evaluator_scope fix) has the identical "not yet run for real" gap, for all twelve baselines

The fix itself (source `frame_stack`/`image_size` from `OBSERVATION_GEOMETRY` instead of a CLI
default) is small, and I verified it computes the right dictionary locally for every baseline via
the full test suite. But `eval_grid.py` is a shared `CODE_MEMBER` across all twelve families, so
this change — like the IDAAC-C2 change — has not been exercised by an actual remote evaluation job
for *any* family since it landed. Per this project's own governing sequencing rule (mailbox Q47),
that is deliberate (one final validation wave, not a reactive one after every fix) rather than an
oversight, but I want it named here specifically because a reader of this document might otherwise
assume "the tests pass" means "this has been confirmed against a real evaluator run," which it has
not, for either C98 or the IDAAC-C2 recipe.

## Claims taken entirely on trust, not independently checked at all this session

Collected here from the item-by-item files for scanability; see those files for exactly which
review made each claim:

- ~~RAD's 100→84 render/crop mechanism~~ — **checked after this document's first draft: verified,
  with a real CLAIMS-LEDGER bug found and fixed as a result.** `runnable/dmc_gb/src/
  arguments.py:91-93` sets `image_size=100, image_crop_size=84` for
  `args.algorithm in {'rad','curl','pad','soda'}`. `runnable/dmc_gb/src/algorithms/rad.py`'s `RAD`
  class is completely empty (`class RAD(SAC): def __init__(self, obs_shape, action_shape, args):
  super().__init__(obs_shape, action_shape, args)`) — pure `SAC` inheritance, no crop code of its
  own. The actual crop lives in the shared replay buffer's generic `sample()`
  (`runnable/dmc_gb/src/utils.py:187-190`, calling `augmentations.random_crop`), so RAD, CURL,
  PAD, and SODA all get it "for free" from the same code path, not from anything RAD-specific.
  `augmentations.py::random_crop` (line 112) uses genuine `torch.LongTensor(n).random_(0,
  crop_max)` randomness, with `if crop_max <= 0: return x` — a real degenerate-to-no-op guard at
  native 84, exactly the failure mode review 17 warned forcing RAD to native resolution would
  hit. Found in the process: `notes/CLAIMS-LEDGER.md`'s `rad` row said the augmentation was
  `random_shift` — wrong; `random_shift` is a separate function (line 105) used by `drq`/`svea`'s
  own samplers, not by RAD's path. Fixed the row with a dated correction note; left "not the
  paper's crop/translate" unchanged since that specific comparison was not independently
  re-verified. Full trace in `01-review-17-item-by-item.md`'s RAD section.
- RAD's DMCGB-provenance claim ("based on the official implementation") and its n-step value, and
  SODA's own paper-vs-code auxiliary-LR ambiguity and its train-mode guard — **still zero
  independent checks this session.** Only RAD's crop mechanism (above) was traced; SODA itself has
  had no code read at all beyond confirming it shares RAD's crop-size branch in `arguments.py`.
  This is not because I judged them unimportant; both reviews rate these baselines as already
  strong, and I allocated attention to the baselines flagged as urgent instead. That allocation
  might be wrong — "already strong per two static reviews" is not the same as "verified."
- ~~IBAC-SNI's specific architecture-gap numbers~~ — **checked after this document's first draft:
  all verified, both sides.** `ext/IBAC-SNI/coinrun/coinrun/policies.py:58-59` confirms the 256-d
  latent and `ρ-5` shift; `runnable/ibac_sni/torch_rl/bottleneck.py:34`/`model.py:207` confirm this
  project's own port is unshifted and 64-d; `README.md:109` confirms the 12-sample reproduction
  command and L2=1e-4. A genuinely new finding beyond either review: `-uda`/`use_data_augmentation`
  is defined once (`config.py:131`) and **read nowhere else in the entire source tree** — a dead
  flag, not DrQ-style shift or anything else. Reported to Codex. See review 17's item-by-item file
  for the full detail.
- ~~ALDA's five headline hyperparameters~~ — **checked after this document's first draft: verified
  against all four official DMC-task specs, not assumed.** `ext/ALDA_Official/specs/train_alda_
  {finger_spin,walker_walk,ball_in_cup_catch,cartpole_balance}.yaml` are byte-identical on all
  five values, confirming they're genuinely uniform authors' defaults, not task-tuned — stronger
  evidence than either review states. See review 17's item-by-item file.
- ~~DrQ-v2's exact replay-capacity numbers~~ — **checked after this document's first draft:
  arithmetic independently redone, both numbers confirmed exactly.** `datasphere/native/
  families.json:28-30` (V100 override): 600,000 training frames at `action_repeat=1` give 600,000
  transitions; Door has no early termination, so at most 600,000/500 = 1,200 episode resets each
  add one extra reset-observation entry, giving 601,200 transitions retained — 620,000 capacity
  leaves exactly 18,800 headroom, non-evicting. `families.json:101` (ordinary DataSphere profile):
  300,000, independently confirmed as the profile's actual value, not the V100 override generalized
  incorrectly to it (the exact distinction `review-17-triage.md:123` and `review-18-triage.md:70`
  already warn against conflating). This item had extensive prior corroboration already
  (`notes/DECISION-SHEET.md` A14, `notes/MIGRATION-T4-TO-V100.md`); what was missing was my own
  independent recompute, which is now done and matches.
- ~~The CTRL authors' claimed original JAX/Flax/Optax versions~~ — **checked after this document's
  first draft: verified exactly against the primary source.** `ext/ctrl_public/requirements.txt`:
  `jax[cuda110]==0.2.17`, `flax==0.3.4`, `optax==0.0.9` — the authors' own pinned versions, byte-
  exact match to the claimed `≈0.2.17/0.3.4/0.0.9`.
- ~~Whether the continuous-action clip-fraction/raw-vs-executed instrumentation both reviews
  recommend already exists~~ — **checked after this document's first draft: it does, substantially**
  (`scripts/eval_provenance.py::ActionDiagnosticsAccumulator`, wired into all six of
  `eval_grid.py`'s per-family evaluators). See review 17's item-by-item file for the detail. The
  one real remaining gap: raw per-step action values are not retained as literal traces, only the
  derived clip-rate/L1-distance aggregates.
- ~~Whether `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md` still contains the overbroad
  `EXACT SOURCE MATCH` verdicts for SVEA/CURL~~ — **checked after this document's first draft: it
  did, and I fixed both.** CURL's "Core method" row said "EXACT SOURCE MATCH for the mechanism";
  verified directly (`RL-ViGen-upstream/algos/curl.py:54`, `class CURLAgent(DrQV2Agent):`) that the
  actual backbone is DrQ-v2, not SAC — a mechanism-level swap, not a hyperparameter variant. Added
  a dated correction rather than rewriting the row. SVEA had no augmentation row at all (a coverage
  gap, not a wrong verdict) — added one: `RL-ViGen-upstream/algos/svea.py:12,299` calls
  `random_overlay` (`RL-ViGen-upstream/utils.py:227-241`, a Places365 alpha-blend, confirmed no
  `random_conv`/`random_convolution` exists anywhere in the tree), SODA's/SGQN's augmentation
  family, not SVEA's own random-convolution augmentation. Both match `CLAIMS-LEDGER.md`'s
  pre-existing rows for `curl`/`svea`, which had recorded these facts already — this document just
  hadn't been reconciled against them. Commit pending alongside this file.

## Things I did not do that both reviews explicitly asked for, named plainly rather than left implicit

- **No baseline has been renamed** to expose lineage (`drqv2-rlvigen`, `CURL-RLViGen`,
  `SODA-code`/`SODA-paper`, `IDAAC-C`, etc.) anywhere a result, job config, or the `baselines` list
  in `families.json` would show it. Every fix this session made changed *documentation* describing
  what a baseline is, not the label a reader would see on a results table.
- **No formal source-precedence policy document** exists stating review 18's seven rules (or any
  equivalent) as this project's adopted policy, despite judging the rules individually sound and
  consistent with decisions already made case-by-case.
- **No two-axis (benchmark-fidelity / method-fidelity) field** was added to `CLAIMS-LEDGER.md` or
  any other document across all twelve baselines, despite judging review 18's framing correct.
  The distinction is applied in prose, per baseline, not as a structural change.
- **A25's proposed replacement taxonomy** (two orthogonal fields: RL backbone/optimizer,
  generalization mechanism) was not built — I fixed the specific factual error (the false "SAC
  backbone" claim) without adopting the review's proposed restructuring.
- **The post-selection ranking caution** (review 18, "three places" item 3) was never checked
  against A25's current text at all — not fixed, not confirmed already-adequate, genuinely
  unexamined.
- **No consolidated startup-time contract emission** (review 17 item 8: shape, dtype, frame stack,
  render resolution, raw/executed action ranges, all emitted once at run start) — pieces of this
  exist (`OBSERVATION_GEOMETRY`, `evaluator_scope`) but not as one artifact the way the review
  describes.
- **No SHA256 provenance chain** (review 17 item 10: upstream URL, commit SHA, pristine-tree hash,
  patch hash, final-tree hash) was audited or built this session.

## A methodological note on how this document itself was produced, for the reviewer's own calibration

This document was written directly from this session's own working memory of what it did,
cross-checked against `git log` for the mechanical changelog and against a handful of targeted
greps/reads (the `PART2-METRIC-INVENTORY.md` check above, confirming the IBAC-SNI PDF content,
confirming the exact code lines cited for the SVEA/DrQ-v2/CURL/DrQ backbone claims) run while
writing it, not a fresh, from-scratch re-audit of the entire repository against both reviews line
by line. It is therefore subject to the same class of risk it warns about elsewhere: things this
session did not think to check while doing the work are not guaranteed to have been thought of
while writing about the work, despite the deliberate effort above to work against exactly that.
The `PART2-METRIC-INVENTORY.md` gap was caught this way; there is no strong reason to believe it
was the only one, only that it is the only one this particular pass happened to surface.
