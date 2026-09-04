# Interim report — reward normalizer, CTRL, cleanup, Stage 3, infra, compute reality

Written 2026-08-16, at the user's request, specifically through the lens of `porting-directive.md`'s
own governing themes — not a commit log, a reflection on how the work this session actually
embodied (or failed to embody) the discipline, with concrete evidence per claim. Dense, first-person,
citation-heavy, matching `DISCIPLINE_IMPOSED.md`'s own established voice in this project.

Scope covered: the reward-normalizer arc across all 12 baselines, the CTRL hermetic module build,
deleting `onpolicy_ext.py`, the start of Stage 3 (reference-execution seam-tracing), a real
infrastructure fix (GLFW), and an honest compute-budget assessment. Everything below is traceable to
a specific commit on `nd-ln-architecture-transition`/`main` (kept in sync throughout) or a specific
`docs/REGISTER.md` entry dated 2026-08-14 through 2026-08-16.

**Known gap in this document, named by the user directly after reading it, not caught by me
first**: this report is organized around `porting-directive.md`'s six section headers, with
evidence selected to illustrate each theme — it does not give the actual concrete, per-baseline
*objects* (which files, which train/eval loops, which model structures each reference actually
supplies) that the decisions described here were made in response to. That material now exists
separately: `docs/ORIGINAL_LOCATIONS.md`'s "What each reference actually supplies" section
(added 2026-08-16, same day, same conversation) gives the concrete, verified, per-baseline-family
picture — which references have their own train loop, eval loop, both, or (for `ppg`/`ibac_sni`,
checked directly) neither. That section is the complement this report was missing, not a
restatement of it; read them together, not this one alone, for the full picture.

## 1. Start with the most original code

Every piece of new code this session was built by reading the actual primary source in full, not by
recalling what it "probably" does or extending an already-built sibling.

**Concrete instances:**

- Each of the four reward normalizers (`idaac`, `ppg`, `ibac_sni`, `ctrl`) was independently re-read
  from its *own* file — gen-rebuttal's `_RewardBookkeeping`/`RunningReturnStd`, PPG's own
  `reward_normalizer.py`, DZ's `procgen_wrappers.py`, CTRL's own `vec_env.py` — even after the first
  one (`idaac`) made it obvious the underlying math (Welford variance of a discounted return,
  clip-and-normalize) would converge to the same shape every time. I did not copy `idaac`'s
  implementation and relabel it three more times. Each one has its own citation, its own docstring
  quoting the reference's literal lines, and — for `ppg`/`ibac_sni`/`ctrl` — was verified by actually
  *running* a dependency-free copy of that baseline's own reference code side by side with the
  transcription, not just by reading it (`docs/REGISTER.md`, 2026-08-14 entries for each).
- CTRL's `model.py`/`algo.py` came from a full, literal re-read of `ext/ctrl_public/{algo,models,
  buffer,train_ppo}.py` — not from the old `onpolicy_ext.py::CTRLLearner`'s own (already known to be
  wrong) construction, and not from my own memory of CTRL from earlier in the session. This reading
  pass alone surfaced five findings the old construction's docstring never had: the `v`/`w` embedding
  chain structure, three separate Optax optimizers (confirmed by the actual `opt_idx` call sites, not
  just the paper's pseudocode), the MYOW neighbor-selection path being unrunnable as shipped (an
  undefined variable in the reference itself), a comment/code mismatch in window subsampling, and a
  dead `reward_mlp` submodule.
- Mid-build, I caught myself about to *propagate* an error rather than originate one: an earlier
  register entry (mine, from this same session) described CTRL's `v`/`w` structure as "four
  independent embeddings." Before writing `model.py`, I re-read `models.py:192-198` directly and
  found `w_clust`/`w_pred` are MLPs applied *on top of* `v_clust`/`v_pred` — a chain, not four
  branches. I corrected the earlier entry in place rather than build on top of the wrong
  characterization. This is `porting-directive.md` §6 doing real work, not just being cited: "this
  session's own earlier output" is explicitly named there as argument-shaped, never inherited as
  settled — and the temptation to skip re-reading something I'd *just* written an hour earlier, in
  the same session, is exactly where that rule earns its keep.

## 2. Plan the effect before doing something; understand the effect, not just the mechanism

**Concrete instances:**

- Before writing a line of normalizer code, I traced the exact point in `trainer_onpolicy.py` where
  the raw reward flows into `storage.insert()`, and named the two-tensor split (`rewards` vs.
  `rewards_raw`) *before* building anything that would populate it. The plan was "training consumes
  one value, the harness measures another, and the split has to exist before the mechanism does" —
  not "build a normalizer, then figure out where it plugs in."
- Before adding a real `normalize_reward` to `idaac/algo.py::Learner`, I checked who *inherits* from
  it. `onpolicy_ext.py::CTRLLearner(Learner)` does — meaning the moment the base class gained a real
  method, CTRL would silently inherit IDAAC's gen-rebuttal-sourced normalizer through Python
  inheritance, with no line of code anywhere saying so. I added CTRL's guard *in the same commit* as
  the base-class change, not as a follow-up after noticing the leak. This is `porting-directive.md`
  §5's "trace the blast radius of any contract or shape change through its consumers before the step
  is complete" applied literally, not quoted.
- Before diffing anything for Stage 3, I checked whether the seam I was about to diff was even
  independently ported. It wasn't: `RL-ViGen-upstream/train.py`'s own robosuite path and this
  project's `rlgen/envs.py` call the *identical* `robo_make` function. Diffing there would only have
  re-derived `docs/PREMISES.md` P1 (already found, patched, test-pinned) — work with zero information
  value. I redirected to the seam that actually had an open question (replay-buffer/discount
  conventions) *before* running anything, not after wasting a diff run on the wrong seam.

## 3. Abstractions leak — and "big" abstractions leak with bugs commonly, not occasionally

This is, concretely, the story of why `onpolicy_ext.py` existed, why it kept producing real bugs, and
why deleting it was this session's actual throughline.

**Every one of the following is the same failure shape** — a shared abstraction silently overwriting
method-specific behavior, discovered only when something adjacent broke:

- IBAC-SNI's `storage_cls` bug: `trainer_onpolicy.py` hardcoded `idaac.storage.RolloutStorage` for
  *every* on-policy baseline. IBAC-SNI's own `storage.py` existed, was tested, and was never once
  reached by the real trainer — it silently ran 64 minibatches of size 32 instead of the configured
  32 of size 64, with no crash, because the two storage classes' `feed_forward_generator` signatures
  happened to be positionally compatible. Parameters still moved. Tests still passed. The bug was
  invisible from inside the premise that assumed "the storage class is interchangeable."
- CTRL silently inheriting IDAAC's linear LR decay, despite CTRL's own reference having no LR
  schedule at all — found only when reading CTRL's reference directly for the hermetic build, not
  from any test failing.
- PPG silently inheriting IDAAC's ten-epoch policy update, IDAAC's gradient clipping, and IDAAC's
  clipped value-loss formula — none of which PPG's own reference has — for the same reason: sharing
  a base class is not sharing a decision, it's *omitting* one and calling the omission a default.
- The reward-normalizer leak risk described in §2 above is the same pattern caught *before* it
  shipped, not after — which only happened because the pattern had already bitten four times and the
  discipline of checking every consumer before a base-class change had become reflexive by then.

**The general lesson, stated plainly:** a "big" abstraction here means "share the PPO core across
four different papers' methods." It is not that this idea is unreasonable on its face — it's that
every one of the four methods disagrees with IDAAC's own tuned defaults on some axis (LR schedule,
gradient clipping, epoch count, value-loss formula, reward normalization), and a shared base class
has no way to represent "this subclass disagrees with the parent on this one axis" except either
overriding every single method (at which point the sharing bought nothing) or silently inheriting the
wrong behavior. `porting-directive.md` §1's own stated reason for hermeticity — "a shared shape
silently overwrites algorithm-specific structure, and the overwrite looks like inheritance rather
than like a decision" — is not a hypothesis this session tested. It's a description of five
consecutive commits.

## 4. Code-level integration is generally not too tractable

The flip side of §3, and worth stating precisely because it's easy to over-generalize into "never
share code," which is not what happened here and not what the directive says.

**What actually IS tractable:** the five baselines (`drqv2`, `svea`, `sgqn`, `curl`, `drq`) that
import `RL-ViGen-upstream/algos/*.py` *directly, unmodified* — literal reuse of someone else's
already-authored, already-tested file, with zero abstraction layer built on top. This works fine.
There's no algorithm-code divergence *possible* for these five, because it's the same Python object
running in both places. Stage 3's seam-tracing for this family correctly found nothing to fix at the
algorithm-code layer — only at the *surrounding* harness layer (the replay buffer's discount
handling, see §6).

**What is NOT tractable:** building a *new* shared layer that spans several independently-authored
algorithms and asserting it as neutral infrastructure. `onpolicy_ext.py` was exactly this — not a
literal import of someone else's code, but a hand-authored `Learner` base class meant to hold
"the parts nobody disagrees about." The five bugs in §3 are the empirical answer to whether four
different papers' authors actually agree about grad clipping, LR schedules, epoch counts, and value
losses: they don't, on every single axis checked. Duplication (`ppg/storage.py`, byte-identical to
`ibac_sni/storage.py`) was chosen deliberately over a shared function *even where the code is
character-for-character the same*, because — per `porting-directive.md` §1 — "identical code under
different parameters is a different object, not the same object differently configured." That's not
a slogan; the SNI-mixing/gradient-accumulation/KL-early-stop divergences already found for IBAC-SNI
specifically are the concrete reason a future change to one baseline's storage semantics must not
silently reach a sibling's.

## 5. Not just the main paths — all paths matter, including the ones nobody's watching

**Concrete instances:**

- The IBAC-SNI `storage_cls` bug (§3) was found by wiring in an *adjacent* baseline (PPG), not by
  testing IBAC-SNI's own main path — which "worked" the whole time, in the sense that it ran, moved
  parameters, and passed its own tests. The bug was invisible from inside IBAC-SNI's own test suite
  because that suite only ever exercised the storage class directly, never through the real trainer's
  actual import.
- CTRL's `test_ctrl_hermetic.py` was built to assert that `w_clust_mlp`/`w_pred_mlp` *stay unmoved*
  after a full `update()` call — not just that `v_clust`/`v_pred` (the paths actually used) move. A
  test suite that only checks "the live path works" cannot distinguish "this parameter is
  intentionally dead, matching the reference exactly" from "this parameter is accidentally
  disconnected" — both look identical from the live path alone. The test exists specifically to make
  that distinction checkable.
- Every hermetic module build this session ran the *full* test suite after wiring in, not just its
  own new tests — and the full suite caught two real regressions the targeted new tests missed both
  times (`test_generated_baseline_files_are_current` after the PPG wiring; a pre-existing IBAC-SNI
  test tied to the old monkeypatch internals after that wiring). A change's actual blast radius keeps
  reaching further than the person making the change is thinking about, reliably, and the fix for
  that isn't "think harder" — it's "run everything, every time."
- Stage 3's own framing (§2) is this principle applied to reference comparison specifically: "does
  the algorithm match" is the main path, already covered for the five directly-imported baselines by
  construction. The seam nobody was independently checking — replay-buffer discount handling — is
  where the actual, previously-uncited divergence from upstream's own code was found (§6).

## 6. Training-loop fidelity is important, specifically because it's arithmetic, not narrative

Two separate findings this session are squarely "does the training loop compute the right number,"
not "does the code read correctly."

- **Reward normalization** sits directly in the training loop's data path, between `env.step()` and
  `storage.insert()`. Getting it wrong doesn't crash anything — it changes what the value function's
  regression target actually is, every single step, silently. `porting-directive.md` §5 names this
  class explicitly: "anything touching the training loop's arithmetic on every step — clipping,
  normalization, discount, buffer ordering, sample counts — is assumed to matter, and the burden is
  on showing it does not." Four real, independently-verified implementations exist now specifically
  because "probably fine, it's just normalization" was never treated as an acceptable default.
- **Truncation-vs-termination handling** (`docs/PREMISES.md` P4, corrected 2026-08-15) is the same
  class of finding from a different angle: `RL-ViGen-upstream`'s own `robo_wrapper.py` sets
  `discount=0.0` unconditionally at every episode end, with no branch for "was this actually a
  time-limit cutoff, not a real termination." Since Door/Lift never terminate early, this zeroes the
  Q-target's bootstrap at literally every episode boundary, in the reference's own shipped code. This
  project's own `rlgen/replay.py::FrameReplay.sample` already got this right — but the existing
  documentation credited that correctness against "a sibling project's earlier draft," not against
  what RL-ViGen-upstream's own code, and any published numbers produced under that exact commit,
  actually does. The fix wasn't code; it was correcting the claim about what the code diverges from —
  `porting-directive.md` §6 again: "verification attaches to a claim... a claim that changes earns no
  credit from prior verification." The reasoning behind the original fix was already correct; the
  citation for *why it matters* was wrong, and that's a real defect in a claim, not a stylistic gap.

## 7. The tiers of fidelity did real epistemic work, not just paperwork

CTRL's JAX-vs-PyTorch resolution (`docs/REGISTER.md`, 2026-08-14) is the clearest instance this
session of T1–T4 actually constraining a decision rather than being filled in after the fact:

- A background job attempted a from-scratch PyTorch port under an explicit failure-biased protocol.
- T1 (forward agreement under transplanted weights) and T2 (single-step gradient agreement, every
  stochastic draw supplied externally) were claimed by that job's own report — and then **I
  independently re-ran the actual parity test myself**, rather than trust the report's numbers. The
  test genuinely ran (non-fixed-seed floating-point differences that varied slightly run to run, not
  a canned log), and passed.
- T3 (distributional agreement with the reference's own published results, on the reference's own
  domain) was explicitly **not** claimed, because it would require a real Procgen training run that
  never happened. The report didn't round T2 up to T3 because the two are adjacent; it stopped where
  the evidence stopped.

The value of the tier system here wasn't "declare a number" — it was that T1/T2-verified and
T3-unverified are *different claims with different consequences*, and conflating them (a real risk
when a report reads as thorough) would have let a genuinely strong forward/gradient match stand in
for a distributional match nobody had actually checked. The tiers made that substitution visible and
refusable.

## 8. How adaptation is handled — branch points recorded before code, not narrated after

CTRL's `action_mlp` input is the cleanest instance: the reference's FiLM-conditioning mechanism
consumes a one-hot discrete-action vector (Procgen); this project's action space is continuous. Per
`porting-directive.md` §4, before writing `model.py` I recorded: the structural property the
mechanism actually depends on (some fixed-size vector representation of the action — the FiLM math
itself doesn't care how `gamma_a`/`beta_a` were produced), the options considered (raw continuous
vector; binned/discretized; drop the term entirely), the choice (raw vector — the mechanism's actual
requirement is satisfied directly, the alternatives each destroy information or remove a term the
paper's own mechanism depends on for no stated reason), and the falsifiable condition that would
show the choice wrong (cluster collapse or loss of action-conditioned separation traceable
specifically to this substitution). This is §4's own template — "the structural property... the
options considered, the choice, and the result that would show the choice was wrong" — followed
before the code existed, not reverse-engineered into a docstring afterward.

## 9. Where the discipline itself slipped — including from me, this session

Two instances worth recording exactly because they're the same failure class described in §§1–6
above, caught only because the user asked rather than because I caught it myself:

- **The MPS timing measurement.** I measured real training throughput (12.16 fps), wrote a scope
  decision into `docs/compute.md`, and committed it — without checking whether the measurement was
  taken under contention. It was: a completely unrelated job (a different project, `--num-envs 128`)
  had been running the entire time, alongside swap already at ~80%. I treated my own freshly-written
  number as settled the moment I wrote it down, exactly the failure `porting-directive.md` §6 warns
  against for *documentation* claims — except this time the un-re-derived claim was an empirical
  measurement I had personally just taken, in the same turn, which should if anything have made it
  *more* suspect of needing a second look (a number that convenient, that clean, from a shared
  machine with other load already visible in `ps aux` before I even started) — not less.
- **"Kaggle is exhausted."** I read this claim from an existing doc and repeated it into a new
  decision without re-checking it or noting when it was last true. It may still be accurate; the
  actual defect was writing it forward as current fact rather than as a dated claim that needs
  re-verification, which is the exact discipline `docs/DISCIPLINE_IMPOSED.md` already names ("old
  comments/docs/citations are claims timestamped to when written... not evidence") applied to a
  compute-availability fact instead of a code fact.

Both are now corrected in `docs/compute.md` with explicit dates and explicit "genuinely unknown, not
re-asserted either way" framing where the truth isn't currently known. The pattern worth naming
plainly: practicing a discipline rigorously in one domain (porting fidelity, register entries, code
review) does not make it automatic in an adjacent one (empirical measurement, third-party service
status) just because the same person is doing both in the same session. The discipline has to be
re-applied on purpose every time, including to the sentence just written.

## 10. What this leaves open

Not resolved this session, stated plainly rather than implied by omission:

- Stage 3 seam-tracing covered the env-construction and replay-buffer/discount seams for all 12
  baselines. It has not covered per-step observation/action-format agreement, nor run an actual
  scripted-action execution diff for any baseline (everything found this pass came from reading code
  precisely, which `porting-directive.md` §3 itself ranks below actual execution diffing — "reading
  is not evidence... this is the only mechanism here that finds what was never suspected").
- A real, defensible 12×3-seed empirical study is not close: at the measured (contended,
  order-of-magnitude-only) rate, one baseline/one seed at the real 500k-frame budget is on the order
  of half a day, and the full matrix sequentially is on the order of two-plus weeks of continuous
  local compute. Whether Kaggle is actually available is unresolved as of this writing. No sweep was
  launched; the decision and its reasoning are in `docs/compute.md`.
- RAD's exact augmentation-parameter diff against `MishaLaskin/rad`'s own `data_augs.py` remains
  open, explicitly deferred in the existing docs as low-priority until RAD's specific numbers matter.
- 19 of `docs/REGISTER.md`'s ~40 entries are still "Not decided" as of 2026-08-15 — recorded findings
  that haven't been resolved, which is the register working as designed (`porting-directive.md` §5:
  "an empty register is a failure of the register, not a clean module"), not a backlog to feel bad
  about, but also not something to lose track of.
