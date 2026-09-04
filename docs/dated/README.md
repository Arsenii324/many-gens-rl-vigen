# Dated snapshots — true when written, not maintained after

**Written 2026-08-24.**

Documents here state what was true **on the date in their filename**. They are not living documents,
they are not corrected when the project moves, and nothing in the project is allowed to depend on
them. A claim found here is a *lead*: check it against the live document before acting on it.

Everything else under `docs/` is the opposite — corrected at source, expected to be true now.

## Why this folder exists

`PROJECT-INDEX.md` requires every document to be reachable from the index, enforced by
`tests/test_docs_integrity.py::test_no_document_is_orphaned_from_the_index`, because
*"a document nobody can find is a document nobody maintains."* That rule is right for living
documents and wrong for snapshots, which nobody should maintain by design. Applied to snapshots it
produced a slow leak: one index row per report, forever, against `SYSTEM.md`'s loudest stated
weakness — *"it is large, and growing faster than it is being read."*

So the folder gets **one** index row and its files get none. The path is the signal.

## The rule the test enforces

`tests/test_docs_integrity.py::test_dated_snapshots_declare_their_write_time` requires:

1. Every `docs/dated/*.md` states its write date in its first 15 lines, matching `Written YYYY-MM-DD`.
2. This folder is named in `PROJECT-INDEX.md`, so the *folder* is reachable even though its
   contents are not indexed individually.

Point 1 is the load-bearing half. A snapshot whose date is only in its filename gets quoted out of
context the moment someone pastes a paragraph out of it, and this project has already lost a
finding that way — `SYSTEM.md` records a CTRL finding that survived a compaction *"more confident
and less correct,"* because summarisation strips hedges. A date inside the prose survives the
paste; a date in the filename does not.

## What belongs here

Reports, review passes, audits, and briefings that answer "what did we think on date X" — supervisor
reports, one-off adversarial reviews, point-in-time status.

## What does not

Anything another document cites as authority, and anything anyone would need to correct later. If
you find yourself wanting to fix a file in here, that is the signal it was never a snapshot: move it
into `docs/` and give it a real index row.

**Not a home for working state.** Working state — what to do next, what to distrust, what was just
tried — belongs in `STEP-ZERO.md`'s handoff block, which is the single live slot. Snapshots record
what *was*; working state records what to *do*, and mixing them is how `HANDOFF.md` came to sit at
the repo root asserting a 2026-08-10 state as fact until it was marked EXPIRED.
