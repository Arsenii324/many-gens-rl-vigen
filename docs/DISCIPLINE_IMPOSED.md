# Discipline imposed this session — dense recap, not for presentation

**Superseded as the authoritative document, 2026-08-14, by
`/Users/a2mogus/build-projs/ccm-intro/docs/porting-directive.md`** (workspace root, written
separately by the user, confirmed as authoritative — "I've worked a lot on it and I think it's
proper"). That file formalizes and in several places sharpens what's recapped below. Where the two
disagree, the directive wins. This file is kept as a session trace — where a rule was first arrived
at, and the concrete instances that motivated it — not as a second standard to reconcile against.

Not a standard-setting doc (that's `RIGOR.md`, or now `porting-directive.md`). This is a compressed
log of the actual rules the user imposed, turn by turn, densely, for reapplication — not
readability. No hedging, no framing.

## 1. Verification epistemics

- Only propose integration methods whose validity you can verify. Unverifiable = "I will replace
  all buffers with one and all PPO's with one" — you don't know which interfaces link to it.
- Two-outcome frame for any unification claim: (1) exact match across all components, AND it
  succeeds — verify, never assume by default; (2) hidden discrepancy exists → either a specific,
  brittle mechanism (explicit TODO, stated, not silently absorbed) or it plain doesn't fit
  ("patching" = doesn't fit, say so).
- Don't assume (1) happens by default, ever. Don't assume you can "tag along with (2)" without
  having the mechanism fully modeled and in a verification harness.
- Bug-level scrutiny (fixing things found inside an assumed-valid premise) ≠ architecture-level
  scrutiny (testing the premise itself). Finding+fixing 3 bugs in a shared class does not validate
  that the class should be shared. Check the premise separately, explicitly.
- Split claims by type, not by available budget. Mechanical facts (git remote origin, a formula
  copied verbatim from a fetched primary source) — verify once, trust after. Argument-shaped
  claims (a docstring justifying a design choice, a "not yet decided" note, your own earlier
  session output) — never inherited as settled; re-derive every time they're load-bearing,
  regardless of how much time/budget is available. More budget does not fix this by itself.
- Old comments/docs/citations are claims timestamped to when written, under whatever assumption
  set held then — not evidence. Applies to the agent's own prior statements in the same session
  identically to third-party text. Timestamp new claims (date them) so this stays checkable later.
- Text embedded in code/docs that argues FOR a design choice (a docstring rationalizing sharing,
  surviving prose from a superseded plan) is advocacy, not neutral documentation — read it as a
  claim to verify, same as a citation, especially when it was written by the same process making
  the choice it argues for.
- When a claim depends on something from before a context compaction, go check the raw transcript
  — do not trust the compacted summary's coverage of it. Concrete cost of skipping this once: a
  real unfixed bug (CTRL `_embed_windows` episode-boundary splice) and its proposed fix both
  silently vanished until dug back out.
- "Cosmetic" is not a spectrum word in code. Only zero-behavioral-difference things are cosmetic
  (names, comments, formatting, import order). Any actual behavioral difference (clip value, init
  scheme, optimizer grouping) is consequential by definition; the open question is whether its
  *magnitude* matters for the specific claim resting on it — that needs evidence, not an a priori
  label.
- Effect-size discard rule: one-time/setup cost (import order costing 3s at startup) — discard
  without proof needed. Anything touching the training loop's math on every step (grad clip,
  normalization, discount factor, buffer ordering, sample count) — assume matters by default,
  burden is on showing it doesn't, not the reverse.
- Documentation of a divergence (citation-style, "DEPARTS" points) makes it legible/auditable. It
  does NOT justify or validate it. Justifying needs a separate, substantive argument: does this
  specific divergence affect the specific claim resting on the baseline's results.
- Contract ≠ code. Byte-identical shared code can carry different effective contracts depending on
  what each caller silently relies on. A class verified safe for caller A says nothing about
  whether it satisfies a property caller B is silently assuming and A never exercised. Check what
  each new consumer of shared code assumes about post-call state, not just whether the code is
  "the same."

## 2. Default / burden of proof

- Default posture: disjoint, not shared. Sharing must be affirmatively earned per-component
  (matching hyperparameters checked against each paper's own primary source, matching contracts,
  matching framework where relevant) — not assumed viable pending disproof.
- "Already built" is not evidence the build was correct. Treating dated, already-scrutinized code
  as validated-by-survival is exactly the bias to catch in yourself, actively, not just note once.
- The assumption that inheritance/sharing is earned does NOT transfer across a strategic reframe.
  Pre-reframe constructions get zero credit from having existed before the reframe.
- Distinguish artifact classes explicitly: code that is a faithful port of one paper (the other 8
  baselines: literal unmodified execution, or a documented one-hop copy) deserves trust once
  verified. Code that is your own constructed architecture spanning multiple papers (shared class
  hierarchies, shared buffers) deserves the harshest scrutiny available, not inherited credibility
  — "if something is wide and details aren't written through, assume it has consequences and
  implicit caveats," as a standing default, not a one-time check.
- A framework difference (JAX vs PyTorch) means literal code-sharing with an original was never
  possible in the first place — so "sharing" in that case is 100% invented internally, with zero
  precedent from either paper's own practice, and needs the strongest justification of all, not
  the weakest.

## 3. Scope discipline — what counts as a decision, what to build

- Decision log = only decisions made while developing something NEW, with effect actually seen
  (built/tested/verified). "Left at default" is not a decision. Not a retrospective of
  already-integrated code's history (that's git log / FAITHFULNESS.md's job).
- Don't backfill the decision log with the session's prior fixes. Trim aggressively if this
  happens; note the correction.
- Flag findings; do not build fixes unprompted. Applies uniformly: the reward normalizer, splitting
  `onpolicy_ext.py`, writing a from-scratch PyTorch CTRL — all flagged, none built, pending
  explicit go-ahead each time.
- Fidelity strictly prioritized over speed. A constant +/-50% training-loop slowdown from going
  disjoint is real, not dismissed — but do not attempt simultaneous fidelity-and-speed
  optimization, and do not do unprompted speed rewrites. Flag a slowdown if noticed; don't chase it.
- "Code is free, information is everything" — when an existing architecture turns out unjustified,
  salvage the informational content (citations, verified formulas, declared deviations, bug fixes)
  into the rebuild; do not treat the existing class hierarchy as worth preserving for its own sake.
- Strategic-framing supersession: when the whole approach changes, do not mass-rewrite old docs to
  reconcile them with the new framing. Checkpoint via annotated git tag, then remove/branch —
  preserve full history, never lose it, never let it get gitignored.
- Do not switch into planning mode unless explicitly asked. Being asked for a judgment/position/
  recommendation is not a request to plan or execute. ("I don't want to plan just now" is a
  standing-until-revoked instruction, not a one-off.)
- Lean practice cuts both ways: not casual heavy multi-agent orchestration for its own sake, AND
  not "inventing AI-slopped big bulks of code or not-needed documents." Staged work, alternating
  with verification, not one-shot attempts that disregard uncertainty.

## 4. Provenance / fidelity labeling

- Original-authors-fidelity is yes/no, never a spectrum. A fork, an edited copy, a third-party
  reimplementation is NO regardless of how faithful it tries to be — labeled and shelved
  separately from the yes.
- Want at least one verified fidelity=YES location per algorithm, on disk, with the verification
  method stated (git remote origin check, not a folder name guess).
- Distinguish precisely, every time, which of several cited "references" is: the actual original
  authors' release, a sibling project's own from-scratch port, a third party's independent port, or
  this project's own code. Never collapse these into one word ("ported").
- "Not vendored locally, only known online" is a distinct, weaker status than "vendored and
  verified" — say so plainly, don't blur them.

## 5. Delegation (agy) discipline, as actually applied

- Good fit: broad, unbounded search where the target isn't known in advance (does X exist anywhere
  online) and the output's citations are cheap to spot-check afterward (one WebFetch per claim).
- Bad fit: local mechanical checks where you already hold the needed context (git remote -v sweeps
  — write the script/run the commands yourself, don't re-explain context to a cold job for
  something this cheap to just do).
- Bad fit: narrow, single-known-target lookups (one specific URL vs one specific local file) — do
  directly via a fetch tool, no delegation overhead needed.
- Bad fit: high-judgment construction where verifying the output costs about as much as doing the
  task yourself (e.g. a rigorous cross-framework algorithm port) — the checking cost swallows the
  delegation win.
- Always spot-check agy's positive, actionable findings independently (refetch the cited file
  yourself) before treating them as fact — a suspiciously clean/complete result is not itself
  evidence of completeness.
- Two independent searches converging on the same negative result, via genuinely different methods
  (fork enumeration vs. citation-graph analysis), is real corroboration; the same method run twice
  is not.

## 6. The meta-plan's own content (condensed — full version outside this repo's version control at
   `/Users/a2mogus/.claude/plans/jolly-spinning-valiant.md`, not duplicated here; see
   `ORIGINAL_LOCATIONS.md`/`COMPARABILITY_CONTRACT.md` for what's actually committed)

- Non-negotiable invariant: every baseline's env interaction, train and eval, goes through one
  choke point (`rlgen/envs.py`) — verified by exhaustive grep, not assumed, re-verified per audit.
- Checklist categories that must be checked per baseline, not assumed uniform: frame/step/time
  accounting (action_repeat/frame_stack applied twice or zero, budget unit mismatch, warm-up
  counted asymmetrically, eval frames leaking into train counter, off-by-one at budget boundary);
  eval/metric definition (reward transform reachable from eval path, obs dtype/scale mismatch at
  the `act()` boundary, action postprocessing done zero or twice, capability vs. axis-alignment as
  a distinct risk); logging/checkpoint schema (non-conforming metric names, checkpoint fingerprint
  fragility, hardcoded protocol fields that should be read from the shared object); seeding/RNG
  (global vs. local state, reachability after the global seed call, not just existence of a seed
  call); the `act(obs, deterministic)` contract itself (dtype/shape/range, purity of the
  deterministic branch); hidden coupling through incidentally-shared utilities (is sharing because
  every paper genuinely specifies the same thing, or merely convenient).
- Five verification layers, defense in depth: atomic-unit trace (follow one obs/action/frame-count/
  reward/done/seed through the full call graph to a genuinely trusted boundary); runtime contract
  assertions at the choke point (permanent, not a one-time read); differential/empirical
  step-counting smoke tests; mutation-test the comparability layer itself (does the safety net have
  teeth); a standing reviewer checklist for future additions.
- A 12-agent parallel Workflow for the per-baseline audit failed completely (session usage limit,
  ~1.06M tokens, zero output) — do not retry the same shape immediately; redo directly.

## 7. Known-open items at time of writing (2026-08-14) — pointers, not the full state

- Reward normalizer (idaac/ppg/ibac_sni/ctrl family): declared in config, does nothing in code.
  Mechanism verified faithful via 3 independently-checked sources (original IDAAC clone's import
  statement, an unrelated project's vendored OpenAI Baselines `VecNormalize`, CTRL's own official
  `vec_env.py` read directly). Placement (inline in `trainer_onpolicy.py` vs. a trainer-owned
  wrapper object vs. an env-layer decorator) not decided; options analysis done, not executed.
- `onpolicy_ext.py`'s shared `Learner` core (PPG/IBAC-SNI/CTRL inheriting IDAAC's PPO): default
  flipped to disjoint-should-be-earned. CTRL's own reference is JAX, never had a code relationship
  with IDAAC's PyTorch core at all — zero precedent for sharing. PPG's official code has zero grad
  clipping and two internally-inconsistent discount factors; this repo's shared core imposes grad
  clipping on it, undeclared as a decision (recorded as a fact, not framed as an accepted
  divergence). PPG's dual-network requirement already found missing (2026-08-14,
  `FAITHFULNESS.md`), left as an explicit open decision. CTRL's `_embed_windows` has no
  episode-boundary guard — found twice, fixed never, now written down (`FAITHFULNESS.md` §CTRL
  divergence 4).
- Off-policy side: same suspected problem, not yet audited at this depth. `rlgen/trainer.py`/
  `rlgen/replay.py` supply a buffer used across both the RL-ViGen-native 5
  (drqv2/svea/sgqn/curl/drq) and this project's own additions (rad/soda/alda) — structurally
  confirmed shared, not yet checked against whether rad/soda/alda's own papers actually need the
  same buffer semantics.
- No PyTorch reference for CTRL exists anywhere (two independent agy searches, different methods,
  same negative result) — any PyTorch CTRL work has zero external ground truth to check against,
  ever, by construction.
- `docs/ORIGINAL_LOCATIONS.md` has the full per-algorithm original-location table this recap
  compresses out of. `docs/FAITHFULNESS.md` has the per-algorithm hyperparameter/divergence
  analysis. `docs/COMPARABILITY_CONTRACT.md` has the interface-level audit. This file is the
  process rules underneath all three, not a restatement of their content.

---

## Appendix A: the instrument substitution — coding replaced by a gated evidential pipeline

Sections 1-7 above are a rule list. This is the single structure underneath most of them — named
explicitly because it was asked for by name and the request was for completeness, not elegance.
Four anchor phrases, each expanded exhaustively with every concrete instance found across the
session, then the structure stated as stages, then its recursive application to the agent's own
claims (not just to code), then what breaks without it.

### Anchor 1 — "start with original, minimal edits, each edit scoped, all interaction with other
stuff is seen"

This bundles three distinct constraints that were repeatedly treated as one non-negotiable unit:

- **Start with original.** Every design question got redirected to "what does the actual reference
  do" before any proposal was entertained: the entire `ORIGINAL_LOCATIONS.md` exercise (find the
  real `git remote`-verified original for all 12 baselines before trusting any claim about
  fidelity); "did you take ours IDAAC port or some official one?"; "we could theoretically see if
  same VecNormalize is used by all algos"; the disjoint-by-default architectural conclusion itself
  is this constraint applied at the whole-baseline level — each baseline's own paper is the
  "original" to build from, not a shared internal class.
- **Minimal edits.** The rejection, at the root, of "I will replace all buffers with one and all
  PPO's with one" as a first move. Stage 1's actual instrumentation was kept deliberately thin —
  "counters and asserts, not a mechanism" — when construction was unavoidable. The standing
  CLAUDE.md-level default ("a bug fix doesn't need surrounding cleanup") reinforces this
  independently and was never in tension with it. Salvage-not-preserve when an architecture turns
  out wrong: keep the information, discard the class hierarchy, rebuild minimally per baseline
  rather than patch the shared thing further.
- **Each edit scoped, all interaction seen.** The atomic-unit trace methodology, stated verbatim in
  the meta-plan and executed repeatedly: "trace every read, write, transform, duplication, or count
  site... across the entire reachable call graph... stopping only at a named, genuinely trusted
  external boundary... never at 'this looks like an abstraction I can trust' without checking."
  Concrete executions: tracing `action_repeat`/`frame_stack` from init through the full call loop
  (the original cherry-picked example); tracing where a reward-normalizer edit would sit and what
  it would and would not touch (four placement options weighed against the shared choke-point
  invariant *before* any code); tracing the env/algorithm/training-loop coupling question before
  permitting a placement decision to stand; the `_assert_action_contract` exact-shape check
  specifically designed to catch a caller that touches the interface in an unscoped way (extra or
  missing dimensions passing silently).

### Anchor 2 — "contracts of arguments are important"

The claim that a type signature is not the same thing as a contract, stated first in the original
framing instruction and then enforced repeatedly on specific values:

- The founding example, verbatim: "in Python we can pass a float for a float wherever we want, but
  naturally we know that some floats are meters, some are coefficients, some are logarithms, some
  pairs of floats have interesting structure (e.g. complex numbers)" — a type doesn't impose a
  requirement, but that doesn't mean there's no assumption riding on it.
- `_assert_action_contract`'s exact-shape rule (`(act_dim,)` exactly, rejecting `(act_dim, 1)` or
  `(1, act_dim)`) — logged in `DECISION_LOG.md` specifically because it's a contract decision, not
  a type fact: numpy would happily broadcast past a shape mismatch that should be a caught bug.
- `step_calls`/`action_clip_events`'s own `DECISION_LOG.md` entry: what exactly a counter counts
  (agent decisions, not physical ticks; `action_repeat` folded in once, not per-tick) is a semantic
  contract on an integer, not derivable from its type.
- `assert_respects_deterministic` — `deterministic=True` must be a pure function of `obs` alone.
  IBAC-SNI's VIB eval-mode leak was explicitly reframed, on this basis, as an *interface* defect
  (violates the contract on the boundary function), not an *internals* defect (a bug inside the
  algorithm) — the same underlying bug, differently and more usefully classified once "contract"
  was treated as the operative category instead of "correctness."
- `reward_norm`/`reward_raw` kept as two permanently separate values in gen-rebuttal's own env
  wrapper, with the contract stated as a code comment: "the normaliser must never touch the number
  reported as an episode return" — a semantic contract on which of two floats is "the" reward,
  enforced by keeping them syntactically distinct rather than trusting a convention.
- Truncation vs. termination vs. done, named explicitly in the original instruction as an example
  of the same class of thing, and later found concretely load-bearing: `trainer_onpolicy.py`'s
  boot-value bootstrapping logic exists specifically because Door/Lift's episode ends are always
  time limits, never early terminations, and treating the boolean `done` flag as if it fully
  captured this distinction would silently corrupt the GAE computation at every episode boundary.
- The contract-vs-code point, reached late and generalized past hyperparameters: byte-identical
  shared code can carry *different effective contracts* for different callers. `Learner.update()`
  was verified safe for IDAAC's own usage; `PPGLearner._auxiliary_phase()` reads `storage.obs`/
  `storage.returns` *after* calling it, relying on a post-call state guarantee IDAAC's own code and
  tests never had reason to exercise. Same bytes, unverified new contract, not caught by "the base
  class already works."

### Anchor 3 — "our default assumptions are important"

Every unstated default is itself a claim, and claims about *sharing* specifically get inverted:
assume they don't hold until shown to, rather than assume they hold until shown not to.

- The sharpest instance, stated as a direct challenge: "why do you assume shared-head default as
  opposed to disjoint-implementations default?" — catching that a "let's check X against Y"
  framing had silently kept X (shared) as the default being tested, rather than treating disjoint
  as the default and sharing as the thing needing to be earned.
- The original instruction's version of the same rule: "don't assume (1) [uniform convergence]
  happens by default," and "don't assume you can 'tag along with (2)' without having it all in your
  head, and in the verification model."
- A *positive* counterexample worth keeping, showing what a properly-surfaced default looks like:
  PPG's `gamma: 0.99` in this repo's config is tagged `[E]`/`[RLV]` (continuous-control appendix /
  RL-ViGen's own value), explicitly noted as "NOT Procgen's 0.999" — a default that was *made*,
  *sourced*, and *stated*, not silently inherited. The registry's own pre-existing `[OURS]` tag
  convention is the same discipline, applied before this session started auditing it.
- A negative counterexample, caught and only partly resolved: the claim that
  `ext/dmcontrol-generalization-benchmark/src/algorithms/rad.py` is "equivalent" to `MishaLaskin/
  rad`'s own release sat in a resource-bundle note as an unstated default for an unknown amount of
  time before this session checked it (found: structurally similar, augmentation-parameters not
  diffed — an explicit partial-verification state, not silently upgraded to "confirmed").
- "Assume any undetailed assumption about integration is false; assume claiming to be able to do
  something out of the blue is false" — the general form, stated once, applied every time a
  provenance or sharing claim showed up afterward.

### Anchor 4 — "big abstract over-optimistic edits are wrong"

- The founding statement: "Be taking the strictest, not 'I'll just do and it'll just work', but a
  very strict and critical approach" — stated before any code existed in this thread.
- The restated form, mid-session: "it seems it's not really executed directly if we assume 'blunt
  over-optimistic actions commonly fail'" — used to argue that most of the actual work should look
  like review (finding defects against a spec on things that already exist) rather than
  construction (inventing a new abstraction and hoping it holds).
- The concrete instance this killed: `PPO_FAMILY_ARCHITECTURE.md`'s original shared-core-plus-
  hook-mechanism proposal — a single, elegant-looking abstraction meant to unify four papers' PPO
  internals — found wrong on its own terms (PPG's own reference doesn't even agree with itself on
  gamma, and uses no gradient clipping at all) and removed (git-tagged, not deleted) rather than
  patched into something brittler.
- The same rejection one level up, of the *meta*-plan's own first framing: "why'd you even want to
  integrate code like before?" — abandoning "unify training internals" as the goal itself, not just
  rejecting one implementation of it, once it became clear the goal was over-scoped relative to
  what "same axis" actually requires.
- Every one of the three live "flag, don't build" items (the reward normalizer, splitting
  `onpolicy_ext.py`, a from-scratch PyTorch CTRL) is this rule applied prospectively: each is
  exactly the kind of construction a "big abstract" move would attempt in one pass, and each was
  deliberately left as a stated option set instead.

### The pipeline, stated as stages

Code is not the first move here — it's the last, and only the smallest version of it that the
earlier stages actually license:

0. **Locate ground truth mechanically** — a `git remote` check, a fetched primary source, a byte
   read directly — never an inference or a recalled belief, before any design is proposed.
1. **State the contract, not the type**, of everything the change touches or is touched by: what a
   caller may assume, not just what shape/dtype crosses the boundary.
2. **Enumerate every interaction site exhaustively**, to a named trusted boundary — not sampled, not
   assumed absent.
3. **Surface every default explicitly**, sourced or tagged `[OURS]` — treat unchecked defaults as
   false for sharing/convergence claims specifically, until stage 0-2 show otherwise.
4. **Make the smallest edit stages 0-3 actually license** — reject anything bigger or more
   "complete-feeling," however elegant, if its correctness can't be traced back to what was
   verified.
5. **Re-verify against the specific thing traced or asserted** — red-green with the exact original
   mutation re-applied, not a generic "tests still pass."
6. **Record the semantic assumption the edit encodes**, once, dated — so a later reader doesn't
   have to re-run stages 0-3 from nothing.

### Recursive application: this governs claims, not just diffs

The instrument-space restriction was never code-specific — it was applied to every assertion made
in this conversation, by treating a claim as an action requiring the same license a code edit
would. "How do you tell sharing could be re-justified?", "what's 'cosmetic in code'?", "did you
take ours IDAAC port or some official one?", "are you really quite sure the coupled construction is
justified?" are all stage-0/1/3 checks run against the agent's own prior sentence, not against a
diff. The `DECISION_LOG.md`-vs-`FAITHFULNESS.md` scoping fight earlier in the session is the same
thing again: a claim about what counts as "new, decision-worthy work" had to itself go through
stage 0 (what has actually been built, checked directly) before being accepted.

### What breaks without it, concretely, not hypothetically

- The 12-agent Workflow for the per-baseline audit skipped stage 0-2 at the *methodology* level
  (assumed the parallel-agent instrument would work at that scale without checking) — ~1.06M
  tokens, zero output, recovered by redoing it directly.
- The CTRL `_embed_windows` episode-boundary bug was found once (stage 2 done correctly, that
  session), then lost across a context compaction because it was never pushed through stage 6
  (nothing was recorded) — rediscovered only because a much later question forced a stage-0 check
  of the raw transcript instead of trusting the compacted summary's coverage.
- "PPG's own reference uses zero gradient clipping, ours applies it via inheritance" sat as a
  recorded *fact* in `FAITHFULNESS.md` without ever completing stage 6 in its full form (a stated,
  accepted-or-rejected decision) — legible, per Anchor 2's documentation-vs-justification
  distinction, but not actually justified, until this session's later turns forced the distinction.
