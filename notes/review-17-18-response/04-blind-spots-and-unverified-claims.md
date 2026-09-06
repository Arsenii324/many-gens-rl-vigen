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

## The single highest-impact unverified claim: CTRL's paper-table numbers

Both reviews independently give the same CTRL paper table (num_envs=32, PPO/RL epochs=1,
representation epochs=1, lr_repr=5e-4, cluster_len=2, nearest_clusters=3, temperature=.3). I acted
on the *disagreement between the reviews about what to do with these numbers* (filed `C97`,
declared a conflict, kept the official code's values running) without ever independently reading
CTRL's own arXiv LaTeX source myself to confirm the numbers are correct in the first place. Two
independent extractions agreeing is real evidence — better than one — but it is not the same
class of evidence as this session's own IDAAC recipe verification, which I *did* do by reading
`ext/idaac/raileanu21a-supp.pdf` directly with `pdftotext` before either review existed. If CTRL's
arXiv source is present in this project's `ext/` tree (I have not checked whether it is), reading
it directly is the single most valuable remaining verification step from either review that I did
not take, and it is cheap.

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

- RAD's and SODA's entire treatment — DMCGB provenance claims, the 100→84 render/crop mechanism,
  RAD's n-step value, SODA's paper-vs-code auxiliary-LR ambiguity. Zero code reads this session.
  This is not because I judged them unimportant; both reviews rate these baselines as already
  strong, and I allocated attention to the baselines flagged as urgent instead. That allocation
  might be wrong — "already strong per two static reviews" is not the same as "verified."
- IBAC-SNI's specific architecture-gap numbers (VIB latent 256 vs 64, 12 samples vs 1, shifted vs
  unshifted posterior scale, L2 1e-4, the `-uda` flag's actual behavior). I read the wrong-PDF
  finding's *text* directly but never opened `ext/IBAC-SNI`'s actual CoinRun source code to check
  any of these specific numeric claims.
- ALDA's five headline hyperparameters (`batch_size=128`, `num_latents=12`, `values_per_latent=12`,
  `beta=100`, `frame_stack=3`) matching the official repo's `specs/` — accepted because they are
  already, unchanged, present in this project's own spec file, not because I opened ALDA's
  upstream repository to compare.
- DrQ-v2's exact replay-capacity numbers (≈620k V100, 300k DataSphere, "effectively non-evicting
  for a 600k run") — accepted from the review and this project's pre-existing `CLAIMS-LEDGER.md`,
  arithmetic not independently redone.
- The CTRL authors' claimed original JAX/Flax/Optax versions (≈0.2.17/0.3.4/0.0.9).
- Whether the continuous-action clip-fraction/raw-vs-executed instrumentation both reviews
  recommend already exists. `scripts/eval_grid.py` has an `action_probe`/`_new_action_probe`
  object I used, unmodified, while fixing something unrelated (`run_scene_idaac`'s frame_stack
  argument) — I saw its name, not its contents, and do not know whether it already satisfies this
  recommendation or falls short of it.
- Whether `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md` (Codex/Luna's document) still contains the
  overbroad `EXACT SOURCE MATCH` verdicts for SVEA/CURL that review 18 names — I verified the
  underlying *code* fact those verdicts are wrong about, but never opened that specific document
  to check whether it has since been corrected.

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
