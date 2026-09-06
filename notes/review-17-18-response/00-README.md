# Response to external reviews 17 and 18 — reading guide

Written 2026-09-06/07 by the Claude session working this repository, for an external reviewer
who will read this alongside the full repository, the original papers/implementations, and
general web access. Purpose: state precisely what I (this session) did with every claim in
`notes/ai-review-17-external.md` and `notes/ai-review-18-external.md`, what I verified myself
versus took on the reviews' word, what changed in the actual codebase as a result, and — the part
most likely to contain what the owner is looking for — what I am *not* confident about, including
things I only noticed were uncertain while writing this document rather than while doing the work.

**Companion agent.** A second agent ("Codex", with a sub-agent "Luna" doing deep source review)
is working the same repository concurrently and produced its own exhaustive triage
(`notes/review-17-triage.md`, `notes/review-18-triage.md`) and a 12-baseline source-fidelity
matrix (`notes/PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md`). Those documents cover ground this one
does not duplicate in full; where relevant I point to them rather than restate their content, but
I have not independently re-verified everything in them, and that is itself named as a blind spot
in `04-blind-spots-and-unverified-claims.md`.

## Files in this response

1. **`01-review-17-item-by-item.md`** — every numbered section and every project-wide issue in
   review 17, in its own order, each with: what it claims, what I checked and how, what I did
   (fixed / declared / deferred / disagreed / not yet touched), and a confidence label.
2. **`02-review-18-item-by-item.md`** — same structure for review 18's baseline table, its three
   "reasoning" corrections, its source-precedence policy proposal, and its own documentation review.
3. **`03-changes-made.md`** — a plain changelog: every commit this session made in direct response
   to either review, in order, with the exact hash, what changed, and why. This is the part that
   is mechanically checkable against `git log` — use it as the anchor for verifying the rest.
4. **`04-blind-spots-and-unverified-claims.md`** — the part the owner specifically asked not to be
   thin. Claims from both reviews I did *not* independently verify (only cross-corroborated,
   trusted at face value, or left for Codex/Luna); places my own fixes are themselves unverified
   at the scale that matters (a full training run); and operational consequences of what I
   changed that I noticed only in retrospect, while writing this document.

## Confidence labels used throughout

- **VERIFIED** — I read the actual source file, ran the actual code, or read the actual primary
  document myself this session, and the review's claim matches what I found.
  I cite the exact file/line/command.
- **VERIFIED, REVIEW WAS WRONG** — I checked and the review's specific claim did not hold; I say
  what actually is the case instead.
- **CORROBORATED, NOT PRIMARY-VERIFIED** — the two reviews agree with each other, or the review
  agrees with something already in this project's own documents, but I did not independently
  re-derive the claim from a primary source (the paper's own PDF/LaTeX, the original repository)
  myself this session.
- **TAKEN ON TRUST** — I acted on the claim (or declined to act, deliberately) without checking it
  against anything myself. Named explicitly wherever this is the case; there are fewer of these
  than I would like, and `04-blind-spots-and-unverified-claims.md` is where they are collected.
- **NOT YET ADDRESSED** — genuinely still open, either mine to do or explicitly deferred to Codex.

## The short version, for orientation before the detail

Both reviews converge strongly on IDAAC needing the published DMC continuous-control recipe
(frame_stack=3, `ppo_epoch=10`, `num_processes=1`, etc.) instead of the Procgen-parser-derived
defaults the project shipped with. This session verified that recipe against the primary source
directly (`ext/idaac/raileanu21a-supp.pdf`, done before either review arrived), then — once the
implementation gap was closed — made it the actual production default, not just a documented
target. That work, and the false-certification bug it surfaced along the way (`evaluator_scope`
recording the wrong observation geometry for eleven of twelve baselines), is the largest concrete
outcome of this review cycle and is detailed in `03-changes-made.md`.

The two reviews *disagree* with each other in exactly one place that matters: whether CTRL should
switch to its paper's hyperparameter table (review 17: yes) or whether that is an unresolved
paper-vs-official-code conflict that should not be silently resolved either way (review 18: yes,
name it, don't pick). This session sided with review 18's framing and filed it as a project
register item (`C97`) rather than switching CTRL's live configuration — this is argued in both
item-by-item files under the CTRL section.

Everything else — SGQN's released-code-vs-Table-6 gap, the RL-ViGen-variant naming convention,
IBAC-SNI's remaining architecture gaps, the "two fidelity axes" framing, the source-precedence
policy — is addressed at the level of confidence stated for each, and none of it should be read as
fully closed. Read `04-blind-spots-and-unverified-claims.md` before trusting any single item in
the other three files in isolation.
