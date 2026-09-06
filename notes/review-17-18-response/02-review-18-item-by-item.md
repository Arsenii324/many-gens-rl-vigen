# Review 18 — item by item

Source: `notes/ai-review-18-external.md`. Section order matches the review.

## Overview and the "two fidelity axes" reframing

**Claim**: the project conflates three different targets — "faithful to RL-ViGen's
implementation," "faithful to the original method," "a defensible Door adaptation" — and should
freeze two orthogonal fields per baseline: benchmark fidelity and method fidelity, plus separately
recorded necessary adaptations and project-wide measurement choices.

**Judged correct, not formally retrofitted project-wide.** I agree with this framing and used it
implicitly in every individual fix this session made (e.g., stating IDAAC's config is now the
*method*-faithful DMC recipe while explicitly not claiming the `level_seed` adaptation is
method-faithful; stating SGQN's release-code profile is *benchmark*-faithful to what RL-ViGen
actually ships while explicitly not benchmark-faithful to RL-ViGen's own published table). But I
did not add a literal two-column `benchmark_fidelity` / `method_fidelity` field to
`CLAIMS-LEDGER.md` or any other document across all twelve baselines — the framework is applied
case-by-case in prose, not as a structural change to how this project records fidelity. This is a
genuine, not-fully-executed piece of the review's own most-emphasized recommendation.

## Baseline-by-baseline disposition table

Each row below states the review's specific claim/instruction for that baseline and what this
session did with it, cross-referenced to `01-review-17-item-by-item.md` where the two reviews
overlap rather than repeating the same verification narrative twice.

- **DrQ-v2**: "strongest case... keep RL-ViGen implementation, distinguish three replay values
  (original ≈1M, RL-ViGen=10M, project 620k), call 620k 'behaviorally no-eviction-equivalent for
  this horizon,' not 'exact source match.'" Same content as review 17's DrQ-v2 section — see that
  file. TAKEN ON TRUST for the specific replay-capacity numbers, as there.
- **DrQ**: "benchmark-faithful, original-hyperparameter variant... call it 'DrQ under the RL-ViGen
  Door recipe.'" VERIFIED at the code level (genuine SAC via `log_alpha`) — see review 17's DrQ
  section for the same finding, arrived at independently of this specific review sentence.
- **SVEA**: "important downgrade needed... RL-ViGen's active SVEA is DrQ-v2-like... calling the
  core mechanism `EXACT SOURCE MATCH` [in `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md`] is too
  generous." **VERIFIED, independently, and this is the single sharpest, most concretely-checkable
  claim in either review**: I read `RL-ViGen-upstream/algos/svea.py::SVEAAgent` directly and
  confirmed no SAC entropy/temperature term exists anywhere in the class — `stddev_schedule` only.
  I did not separately audit whether `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md` (a Codex/Luna
  document) actually contains an `EXACT SOURCE MATCH` verdict for SVEA that needs downgrading —
  that document is outside what I edited this session, so I cannot confirm whether this specific
  correction has been applied there. **Open**, and it is Codex/Luna's document to correct, not
  mine, but I want it on record that I verified the underlying code fact and did not verify
  whether the flagged document was actually fixed.
- **SGQN**: "same basic issue as SVEA... keep RL-ViGen-SGQN for benchmark fidelity... make Door's
  q=.9/.7/8e-5 a hard effective-config check." See the SGQN section below — this is the row where
  the two reviews' *numbers* agree but their prescriptions differ subtly from this project's own
  prior resolution, and I want the distinction stated precisely rather than folded into review
  17's already-detailed treatment.
- **CURL**: "most explicit RL-ViGen variant... `CURLAgent(DrQV2Agent)`... 'exact mechanism match'
  is too strong [again, presumably in the Codex/Luna document]." Same VERIFIED code fact as review
  17's CURL section (`CURLAgent(DrQV2Agent)`, confirmed by direct read). Same caveat as SVEA above:
  I did not check whether the flagged document itself was corrected.
- **RAD**: "good method resemblance, weaker provenance than stated... you are using Hansen's DMCGB
  standardized implementation, not Laskin et al.'s original RAD repository... rename provenance to
  DMCGB-RAD." TAKEN ON TRUST, entirely, same as review 17's RAD section — I did not check DMCGB's
  or the original RAD repository's code this session.
- **SODA**: "one of the strongest added baselines... keep." TAKEN ON TRUST, same as review 17.
- **ALDA**: "strong algorithmic fidelity, necessary task adaptation... keep source UTD≈1 as the
  fidelity primary, do not turn the old retired-port 0.25 stability fix into 'the faithful ALDA
  value'... resolve the apparent 500k-vs-600k ambiguity." **VERIFIED and acted on, precisely as
  recommended, though the UTD-primacy point and the budget point were reasoned through somewhat
  independently before I read this specific sentence.** ALDA's `utd=1.0` (source value) is the
  declared main config; the `utd=0.25` pilot arm (already running before I read either review) is
  explicitly documented as a stability-diagnostic data point that does **not** get promoted to
  primary regardless of its own outcome — the exact fidelity/performance decoupling review 18 asks
  for generally (see the "three places" section below), applied to ALDA specifically before I knew
  the review asked for it there too. The 500k/600k ambiguity: **VERIFIED as a real, live
  discrepancy** (not a stale doc) via `scripts/audit_executed_hyperparameters.py`'s
  `EXCLUDED_CLAIMS` entry, and resolved by raising `n_train_steps` to 600,000 with **both** the
  500k source-horizon checkpoint and the 600k common-budget endpoint predeclared as reportable —
  exactly the review's own suggested resolution ("train through 600k but predeclare/report the
  retained 500k checkpoint... as well as the common 600k endpoint").
- **IDAAC**: "current Procgen-shaped port should not be the primary fidelity target... IDAAC-C
  should be the source-fidelity primary regardless of whether it scores better on Door." Covered
  in full in review 17's IDAAC section and in the "three places" section below (this is where
  review 18's fidelity/performance decoupling argument is sharpest and most directly acted on).
- **PPG**: "no unique original continuous-control PPG exists... the continuous-control recipe you
  are using comes from the IDAAC authors' DMC comparator, not OpenAI PPG — correct any project
  text calling that 'the authors' own continuous-control design.' Call it 'PPG-DMC-reference Door
  port.'" **VERIFIED, and this specific correction was made to this project's own text.** I
  re-read `notes/DECISION-SHEET.md` A36's own reasoning and confirmed it had NOT made this error
  in its main table (A36 already sourced the recipe correctly to "IDAAC's continuous-control
  appendix"), but the *decision-rule* section for both A35 and A36 previously said "it is the
  authors' own stated design for exactly this problem class" — which, for PPG, is exactly the
  overclaim the review names (whose authors? IDAAC's, not OpenAI's). I corrected this specific
  sentence in A36's decision-rule text directly (see `03-changes-made.md`) when applying the
  broader fidelity/performance-decoupling fix. This is a genuinely precise, independently-checked
  correction, not just accepted at face value.
- **IBAC-SNI**: "irreducibly composite unless you implement substantially more... commit to a
  visual/CoinRun-lineage Door port... fix the source-index arXiv identifier: canonical is
  1910.12911, not 1901.10902." The lineage commitment matches this project's own pre-existing A37
  (unchanged by this review, arrived at independently and earlier). **The arXiv-ID correction: I
  independently found something more severe than what the review states** — see the dedicated
  section below.
- **CTRL**: "do not 'fix' cluster_len 10→2 yet, there is a real paper/code conflict... current
  T=10 is no less source-backed than T=2... upgrade this from 'conflict' to 'PAPER↔OFFICIAL-CODE
  CONFLICT.'" This is the review I sided with over review 17's own recommendation — see review
  17's CTRL section for the full reasoning, and `C97` in `docs/CONSTRUCTION.md` for where it lives.

## "Three places I would change the current project's reasoning, not merely its labels"

### 1. IDAAC/PPG variant-selection should not use Door performance to decide the baseline

**Claim**: the project's rule ("if the source-informed C variant reaches competence at least as
well as P, use C; if C fails, retain P as primary") lets the benchmark result choose the algorithm
definition — a reader cannot then distinguish "IDAAC generalized poorly" from "we replaced IDAAC
with whichever adaptation learned Door." Fidelity should be decided from source evidence alone,
before observing performance; the more successful adaptation can still be reported as an alternate.

**VERIFIED as a correct, sharp point, and acted on directly — this is the single most consequential
piece of either review's "reasoning" corrections, in my own judgment.** I rewrote both A35 and
A36's decision rules to split "source-fidelity designation" (decided from the recipe alone,
independent of any Door result — once a `C2` arm matches the published recipe in full, *that* arm
is entitled to the fidelity label regardless of which arm wins) from "headline-production choice"
(still empirically gated: report competence, don't discard failures). I did this specifically
because of this review's argument, read directly, not because I had already reached the same
conclusion independently — unlike several other items in this document, this is a case where the
review changed my own prior reasoning, not merely corroborated it.

**One place I want to flag as not fully resolved**: having split the two questions, IDAAC's actual
production default is now, as of this session's later work, the C2 recipe *unconditionally* — not
because it beat P on Door (it has not been tested at full length), but because the fidelity
argument alone was judged sufficient once the owner directed completing the implementation. This
is consistent with the review's own logic (fidelity decided from source evidence, independent of
performance) but it does mean IDAAC no longer has a "P" arm running in production at all, only in
historical pilot records — a real, deliberate consequence I want stated plainly rather than left
implicit.

### 2. A25's mechanism taxonomy is "factually wrong"

**Claim**: this project's A25 grouped `drqv2, svea, sgqn, drq, rad, soda` as "off-policy SAC,"
sharing a SAC backbone — but DrQ-v2 is DDPG-style, RL-ViGen's SGQN/SVEA/CURL inherit DrQ-v2, not
SAC. Proposes replacing the one-dimensional "mechanism group" with two orthogonal fields: RL
backbone/optimizer and generalization mechanism.

**VERIFIED, CONFIRMED CORRECT, AND FIXED — with more precision than the review itself states.**
I independently re-read `RL-ViGen-upstream/algos/drqv2.py`, `svea.py`, `sgqn.py`, `curl.py`,
`drq.py` line by line rather than trusting the review's claim, and found the review understates
how mixed the group actually is: it is not simply "the augmentation group is DDPG-style, drq/rad/
soda are SAC" — within the *same* review-cited group, `drq.py::DrQAgent` is genuinely SAC
(`log_alpha`, confirmed) while `drqv2`/`svea`/`sgqn` (and, in the neighbouring group, `curl`) are
DDPG-style, confirmed by the *absence* of any entropy term and the *presence* of `stddev_schedule`
in each. I fixed A25's text in `notes/DECISION-SHEET.md` to state this precisely, with exact line
citations for each of the five classes I checked (`drq.py:213-323`, `drqv2.py`/`svea.py`'s
`stddev_schedule`, `sgqn.py::SGQNAgent(DrQV2Agent)`, `curl.py::CURLAgent(DrQV2Agent)`), rather than
adopting the review's proposed replacement taxonomy (two orthogonal fields) wholesale — I judged
the *correction* (accurate backbone description) more urgent and more clearly verifiable than the
*restructuring* (a new two-field taxonomy), and did the former without the latter. The review's
proposed restructuring is **not implemented**.

### 3. Post-selection ranking caution ("best-in-group vs best-in-other-group")

**Claim**: choosing the "best" from noisy n=3 seeds and then comparing winners is post-selection
even if predeclared; keep it descriptive or predeclare fixed algorithm-to-algorithm contrasts.

**NOT ACTED ON, NOT VERIFIED AGAINST CURRENT PROJECT TEXT.** I did not check whether this
project's A25 "cross-group, best-in-group" comparison (mentioned in review 17/18's own baseline
table discussion) is currently described with or without this caution attached. This is a real
gap — the point is well-taken and consistent with this project's own separately-stated seed-policy
caution (A6/A28, "no outcome-adaptive allocation," and A23's small-n lesson, both pre-existing),
but I did not go back and check A25's own text for whether it already carries an equivalent
warning or needs one added.

## PPG's additional correction (rollout geometry, restated)

Same claim as review 17's PPG section (8×256 preserves sample count/cadence, not GAE geometry),
argued in more mechanistic detail (bootstrap boundaries every 256 steps across eight trajectories
vs. every 2048 steps in one, spanning several Door episodes since Door's horizon is 500). Same
response as review 17's file: A26's wording fixed to match; underlying implementation still
Codex's open task.

## Continuous-action clipping seam

**Claim**: agrees with the project's existing decision not to replace Gaussian policies with
tanh-squashed ones; the clip-fraction/raw-vs-executed measurement approach is correct; generalizes
the seam beyond CTRL to IDAAC and IBAC-SNI too.

**Matches this project's pre-existing decision, unchanged by me.** Update, resolving the gap
originally named here: I read `scripts/eval_provenance.py::ActionDiagnosticsAccumulator` directly
— see review 17's file's "Continuous-action clipping instrumentation" entry for the full detail.
It substantially implements this recommendation (per-coordinate and per-transition clip rates, an
L1 raw-vs-executed distance, wired into all six of `eval_grid.py`'s per-family evaluators, not
just CTRL) and honestly declares what it does not cover (the robosuite controller's own downstream
clipping, past the declared action-space boundary). It does not retain raw per-step action values
as literal traces, only these aggregate statistics — a narrower, real gap than "genuinely unknown."

## Replay capacity language

**Claim**: keep the 620k value, change the *language* from "fully faithful" to "capacity-reduced,
behaviorally equivalent with respect to replay eviction for the predeclared 600k Door horizon."

**NOT VERIFIED WHETHER THIS EXACT LANGUAGE CHANGE WAS ALREADY MADE OR STILL NEEDED.** This
project's `CLAIMS-LEDGER.md` drqv2 row (unchanged by me) reads "Replay capped at 300k in a 600k
run unless the host target is applied" — which is a different framing again (this reads like the
*DataSphere* profile's 300k, not the 620k V100 figure the reviews discuss) and I did not reconcile
the two profiles' different replay-capacity numbers or check whether either matches the exact
wording the review recommends.

## ALDA budgets

Already covered above (baseline table, ALDA row) — the 500k/600k resolution.

## Statistical/evaluation design assessment

**Claim**: broadly approves of this project's existing design (training seed as sole outer
replicate; n=3 with intervals not p-values; endpoint-as-primary; the missingness policy; the
revised, non-directional time-limit framing; the rich raw-record retention policy; caution against
a strict 1-12 rank ordering at n=3).

**Entirely a description of pre-existing project decisions (A4-A28 range in DECISION-SHEET,
predating this review cycle), not something this session changed in response to the review.** I
did not re-verify any of these against current code this session beyond what was already
established; I note the review's approval here only because omitting it would look like I
overlooked a section, not because there was anything for me to act on.

## Source precedence policy (the seven numbered rules)

**Claim**: propose formally freezing seven rules (task/eval authoritative from RL-ViGen; method-
defining machinery from paper+official code; task-specific values from an explicit task table over
generic defaults; for a Procgen-original method, preserve method-specific constants and take
generic PPO/action-domain choices from the strongest continuous-control port; paper/code conflicts
get *recorded*, not silently resolved either way; benchmark performance evaluates a frozen variant,
never chooses which variant earns the name; "behaviorally equivalent" must state its axis).

**Judged sound, applied case-by-case, NOT ADOPTED AS A FORMAL, NAMED, STANDALONE POLICY
DOCUMENT.** Every individual rule is consistent with (and largely restates) decisions this session
made or found already made — rule 5 in particular is exactly the CTRL `C97` decision (record a
conflict, don't silently pick a side) and the SGQN `C64` precedent it explicitly draws on its own
comparison to. But I did not create a single document that states these seven rules as *this
project's* adopted policy the way the review proposes; they remain implicit in how individual
register items are written. This is a real, not-fully-executed piece of the review's own most
concrete, lowest-cost recommendation ("that policy resolves most of the current ambiguity without
requiring a single new training run") — it would cost little to formalize and I did not do it.

## Review of the three project documents themselves

**Claim on `PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md`**: right structure, but several `EXACT
SOURCE MATCH` verdicts are too broad (SVEA, CURL specifically named). **Not independently
checked** — that document belongs to Codex/Luna, and I did not open it to verify whether these
specific verdicts still read as the review describes as of this writing.

**Claim on `DECISION-SHEET.md`**: "very good scientific self-correction... [but] chronological, so
obsolete conclusions and their corrections coexist hundreds of lines apart... a reviewer should
never have to infer 'latest wins' from 1,600 lines." **Directly experienced as true by me this
session, and not fixed.** I added *more* superseding entries to A35/A36 in exactly this
chronological-accretion style this session (multiple "CORRECTED", "PILOT RESULT", "IMPLEMENTED"
notes appended in sequence rather than the file being restructured), because that is this
project's established convention and I followed it rather than overriding it. The review's
criticism therefore applies *more*, not less, after this session's own edits, purely by document
length — a real, self-inflicted (if convention-following) cost I want named rather than left for
someone else to discover.

**Claim on `EXTERNAL-REVIEW-ARTIFACT-BLUEPRINT.md`**: very strong; extend its planned schema
rather than invent a new document; add arXiv TeX sources as first-class `reference/` entries, not
just PDFs. **Not independently checked** — this document and its extension are Codex's, not
something I read or edited this session.

## One artifact-level source hygiene correction (IBAC-SNI arXiv ID)

**Claim**: the local paper index names the IBAC-SNI paper `paper_1901.10902.pdf`; the actual
IBAC-SNI paper is arXiv 1910.12911; fix the identifier before generating provenance manifests,
even if "the local PDF bytes are the correct paper and only the filename is wrong."

**VERIFIED, AND FOUND TO BE MORE SEVERE THAN THE REVIEW STATES.** The review's own hedge — "even
if the local PDF bytes are the correct paper and only the filename is wrong" — turned out not to
apply. I read the actual file (`ext/baseline_resources/11_ibac_sni/paper_1901.10902.pdf`) directly
with `pdftotext` and its title page is *"InfoBot: Transfer and Exploration via the Information
Bottleneck"* (Goyal, Islam, Strouse, Ahmed, Botvinick, Larochelle, Bengio, Levine, ICLR 2019) — a
different paper by different authors on a related but distinct topic (goal-conditioned exploration
via decision-state discovery, not selective noise injection for generalization). This is not a
misnamed file; it is the wrong document entirely. I confirmed the *correct* IBAC-SNI paper (Igl et
al., "Generalization in Reinforcement Learning with Selective Noise Injection and Information
Bottleneck," NeurIPS 2019) is already present, correctly, at
`ext/papers-sorted/IBAC-SNI/IBAC-SNI_paper_neurips2019.pdf` — so no re-download was needed, only a
correction to whatever indexes the `11_ibac_sni` directory's canonical source. I did not make that
correction myself (`ext/` is read-only to me per this project's convention); I reported it to
Codex/Luna, and it has since been fixed in `docs/ORIGINAL_LOCATIONS.md`, `rlgen/registry.py`,
`baselines/ibac_sni/README.md`, and `rlgen/algos/ibac_sni/__init__.py`'s own docstring — I verified
those four fixes by reading their diffs directly before this document was written, and they are
consistent and complete as far as I checked.

## What would block source freeze

**Claim**: not generic smoke tests; specifically the RL-ViGen-vs-original identity of SVEA/SGQN/
CURL, SGQN's exact effective values, IDAAC-C as the source-continuous target and whether linear
decay is implemented, PPG's provenance target and rollout-geometry distinction, IBAC-SNI's
declared lineage and remaining gaps, CTRL's publication-vs-code target, Places365 train-vs-
validation, ALDA's 500k/600k budget. Explicitly: do not block merely because a faithful method
learns poorly.

**Status of each, as of this document**: SVEA/SGQN/CURL naming — not renamed (open). SGQN's
effective values — already correctly declared, matches C64 (closed, pre-existing). IDAAC-C as
target + linear decay implemented — **done** (this session, see `03-changes-made.md`). PPG's
target/geometry distinction — documentation fixed, implementation open (Codex). IBAC-SNI lineage —
already declared (A37, pre-existing), remaining architecture gaps open (Codex/not mine). CTRL's
target — declared as an open conflict (`C97`), not resolved either direction, matching the
review's own "record, don't pick" instruction for this specific item. Places365 split — an
already-ratified default (A22) that neither review's dissent overturned this session (see below).
ALDA's budget — **resolved** (this session, 600k with dual reporting).

## Sources used

Not independently checkable, same note as in `01-review-17-item-by-item.md`.

---

## A22 (Places365 split) — named in both reviews' periphery, resolved before this cycle

Both reviews touch this only in passing (review 18's "three places" list mentions it implicitly
via the source-precedence framework; review 17 does not mention it at all). This project's own
A22 already declares the current behavior (training the Places365 overlay on the validation split,
not train) as a **learning-affecting deviation**, not a platform detail, with a stated default
(keep it, declare it) and an explicit note that overriding it would need a fidelity-parity re-run.
I did not act on this further this session — it is an already-ratified decision, and neither
review's specific text asked me to revisit it.
