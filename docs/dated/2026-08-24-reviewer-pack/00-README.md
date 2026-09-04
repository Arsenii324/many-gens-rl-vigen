# Reviewer pack — map and reading order

**Written 2026-08-24. Dated snapshot, not a living document.** It states the project as of that
date and is not maintained afterwards. Every claim is checkable against a cited file; check before
relying on any of it.

## What we are asking you to do

Find what is wrong with this work. Not to approve it, not to rank it, and not to be kind about it.

The project has an unusual amount of internal self-criticism already — a 65-entry findings register,
a document describing its own document system's weaknesses, instruments that audit other
instruments. **That is exactly why an outside pass is worth buying.** All of that machinery was
built by the same process that produced the results, so it inherits that process's blind spots by
construction. The register can tell you what we noticed. It cannot tell you what we are structurally
unable to notice.

Concretely, the highest-value things you could do:

1. Attack §[03](03-what-was-measured.md). It is the whole evidential base, and it is thin.
2. Tell us whether the design in §[01](01-question-and-design.md) can answer the question it is
   posed against, given the identification problem stated there in full.
3. Read §[07](07-unknown-unknowns.md) and tell us what is missing from it.

## How this pack was made, and what that implies

It was generated on 2026-08-24 by re-reading the project's own documents and **re-deriving every
number from the artifacts** — `results/regime-retention/*.json`, the checkpoints, the configs —
rather than copying figures out of prose. That mattered: doing so surfaced three things the
project's own documents get wrong, listed below.

It supersedes a single-file version, [`../2026-08-24-outside-reviewer-brief.md`](../2026-08-24-outside-reviewer-brief.md),
which remains on disk unedited. Where this pack and that brief disagree, **this pack is the
re-derived one**, and the disagreements are listed immediately below rather than quietly fixed.

### Corrections this pack makes to the project's own documents

| what | the documents say | what the artifacts say |
|---|---|---|
| baselines with no measured cell | "eight of twelve" (seed brief §5.5) | **nine of twelve.** Only `drqv2`, `drq`, `svea` have a retention grid. See §[04](04-the-twelve-baselines.md). |
| `results/cell-*` directories | read as evaluation cells | they contain **only** `watcher.log` and `frames/*.npy` — training-distribution witness captures. Not one holds an `eval.csv`, a snapshot, or a `train.csv`. |
| `snapshot` vs `snapshot_100k_frames` | treated as two grids | **byte-identical checkpoint** (md5 `ec21f9a3…`). They are an accidental replicate pair, and they disagree by 47% on success count. See §[03](03-what-was-measured.md). |

The third is the single most consequential thing in this pack and was not known to the project
before this document was written.

## The files

Each is readable standalone. Read in order if you have time; jump if you do not.

| file | what it is | read if |
|---|---|---|
| [01-question-and-design.md](01-question-and-design.md) | the question, who asks it, the design, and why each choice | you want to judge whether the design fits the question |
| [02-vocabulary.md](02-vocabulary.md) | regime, scene, cell, retention, register classes, shaping vs success | you have not worked with RL-ViGen or robosuite |
| [03-what-was-measured.md](03-what-was-measured.md) | **the evidence.** Every grid, re-derived, with what it does and does not establish | you only read one file — read this one |
| [04-the-twelve-baselines.md](04-the-twelve-baselines.md) | per baseline: what it is, what runs, fidelity state, whether it has a cell | you want to know how much of the comparison exists |
| [05-what-would-embarrass-us.md](05-what-would-embarrass-us.md) | the things we would least like a reviewer to find, stated first | you want the short path to the weak points |
| [06-unknown-knowns.md](06-unknown-knowns.md) | things the project knows and has not acted on | you are interested in process failure modes |
| [07-unknown-unknowns.md](07-unknown-unknowns.md) | our guess at our own blind spots — labelled speculation | you want to tell us what we missed |
| [08-methodology-under-review.md](08-methodology-under-review.md) | the register, falsifier discipline, instrument vacuity, and their failure modes | you review process as well as results |
| [09-open-questions.md](09-open-questions.md) | the specific questions we want challenged | you are deciding where to spend your attention |

## Conventions used throughout

Every factual claim is tagged where it appears:

- **MEASURED** — re-derived from an artifact for this pack, with the path given.
- **INFERRED** — follows from measured things by an argument that is stated.
- **ASSUMED** — believed, load-bearing, and not established. These are the ones to attack.

Register entries are cited as **C*n*** and live in
[`../../CONSTRUCTION.md`](../../CONSTRUCTION.md); each has a class and a status. Where a number
comes from a single seed or a single checkpoint, that is stated inline, not in a footnote — because
almost all of them do, and a footnote would let you forget it.
