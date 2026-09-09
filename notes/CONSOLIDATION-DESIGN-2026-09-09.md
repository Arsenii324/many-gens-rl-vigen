# Consolidating the repo's understanding — a design, deliberately not an execution

**2026-09-09.** Written at the end of a long session, at ~99% context, *because* of that: whatever
I understand right now is about to be summarized, and a summary is exactly the operation whose
failure mode this note exists to reason about. So this is the design and the evidence, on disk,
where the next agent can disagree with it.

**Nothing here has been executed.** No document was merged, rewritten or deleted for this.

---

## 1. The goal, stated so it can be failed

An agent arriving at this repo should reach an **accurate** understanding, **at the depth the task
needs**, without reading everything, and without being misled by what it happens to read first.

Three failure modes, and only the first is the obvious one:

- **Too slow** — the answer exists but costs a full read. (Cheap to fix. Least important.)
- **Misled** — the agent reads a confident document that stopped being true. (Happened repeatedly.)
- **Falsely settled** — the agent reads a *correct* document and does not learn that the question
  is contested, conditional, or open. (The expensive one, and the one a consolidation *creates*.)

A consolidation that fixes the first and worsens the third is a net loss, and it will feel like
progress while it happens.

## 2. What this session actually observed, because the design should rest on evidence

Not hypotheticals. All from 2026-09-08/09, all checkable:

| observation | what it says about consolidation |
|---|---|
| Six documents asserted `idaac num_processes` 4/16 in the present tense, three days after A35 fixed it at 1. One was a **test docstring** contradicted by its own file's code comment. | Prose decays silently and nothing notices. Recency does not track truth: the stale test file had been touched more recently than the decision that superseded it. |
| `FINDING-on-policy-update-density.md`'s idaac result was not stale but **void** — it measured divergence from Procgen's 64 envs, and C2's reference *is* 1 process. | A merge that "reconciled" it would have preserved a number whose *premise* had gone. Summaries carry numbers forward and drop premises. |
| I asserted `ppg` "plateaus at 8207 MiB". It goes to **26653** at its auxiliary phase. I had 30 minutes of samples, all inside one phase. | A confident claim from partial observation reads identically to one from complete observation. **I** wrote it, in this repo, this session. |
| I withdrew packing on a misread of `nvidia-smi` (reserved, not used) and had to reverse it. | Positions written under time pressure enter the record with the same authority as considered ones. |
| The VRAM cap had **never reached a trainer** — all nine `runnable/_launch/*.sh` clobber `PYTHONPATH` — while every run logged `NATIVE_VRAM_CAP_APPLIED`. | A mechanism reporting its own success is not evidence. Consolidating *logs* would have propagated a three-day-old fiction. |
| The `raileanu21a-supp.pdf` paragraph settled `num_processes` **and opened** the action-repeat question, from one read. | Primary sources both close and open questions. Derived prose only closes them. |

**The pattern.** Every real defect this session was found by (a) reading a primary source, or
(b) a mechanical check that could fail. None was found by reading a summary — and three were
*created* by writing one.

## 3. Why the obvious instrument is the wrong one

"Merge the overlapping documents into a clean current statement" fails here for a specific,
structural reason, not a stylistic one.

**This repo's value is disproportionately in its conditionals and its dissent.** `A35` matters
because it records *what it replaced and why*. `OPEN-QUESTIONS-LEDGER` carries `REVERSED` rows whose
whole content is that a confident position was wrong. `PARAMETER-REVIEW-CONSENSUS-MATRIX` was
deliberately framed as *dispositions* rather than values, because several reviews' actual position
is "keep the value and declare it unfaithful" — which no consolidated number can express.

Summarization is lossy **in a direction that is invisible afterwards**: it keeps the conclusion and
drops the condition, the minority reading, the date, the "this held when X". You cannot audit for
what a summary removed, because the removal leaves no trace. That asymmetry — cheap to do, uncheckable
afterwards, and irreversible in practice — is why this is not a tidying task.

And the timing argument is decisive: **a consolidation performed 24 hours ago would have baked in
three positions I have since reversed.** There is no reason to believe today is different.

## 4. What the evidence suggests instead

Not a rewrite. Three moves, in increasing cost, each independently useful:

**(a) Make claims checkable rather than merged.** The mechanisms that have actually held are the
ones that fail loudly: `RUNNER_CONTRACT` in two homes, `test_docs_not_stale`, the register's
self-counting entry total, mutation-tested guards. Where a claim can be converted into a check, that
is worth more than any amount of prose reconciliation — a check cannot go quietly stale.

**(b) Navigation over merging.** `scripts/where_is_this_decided.py` (built today) answers "where is
this decided and what contradicts it" without reading the tree, and states each time that an
ordering is not a ruling, that recency is last-touched, and that an exhaustive-sounding note may
have seen a subset. `OPEN-QUESTIONS-LEDGER` is the curated entry point above it. **This is the part
that is already done**, and it is the cheap 80%.

**(c) Progressive disclosure by *area*, written as pointers, not as replacements.** A short
per-area map — host operations, fidelity, evaluator closure, comparability, run history — that says
what exists, what is current, what is contested, and *what it costs to go deeper*. Pointers can be
wrong and repaired; a merge that dropped a conditional cannot be.

**What is deliberately NOT proposed:** merging the notes series into the docs series, deleting
superseded material, or producing "the current state" as a single document. The two trees
(`ccm-intro` and the recovery workspace) are also **not** proposed for joining — they differ in ways
neither subsumes, and the git-tracked one is the one exercised on production, which makes the other
evidence rather than duplication.

## 5. Phasing, with stop conditions

**Phase 0 — measure the actual navigation cost.** Before writing anything: take 5-8 real questions
(the action-repeat condition, "which eval runs where", "is the cap enforced", "what does a cell
cost") and record how long each takes with today's tools and where the agent goes wrong. **Stop
condition: if the existing entry points answer them, the remaining work is (a) only.** This phase is
measurement and cannot damage anything.

**Phase 1 — convert the top decayed claims into checks.** Ranked by how badly a wrong answer would
hurt. No prose merged.

**Phase 2 — per-area maps, pointers only.** One area at a time, each reviewed against Phase 0's
questions. **Stop condition: if a map cannot be written without deciding a contested question, that
question goes to the ledger as OPEN and the map records both positions.**

**Phase 3 — does not exist yet.** Any merging or rewriting is a separate decision, taken with
Phase 0-2 evidence in hand, and is the owner's.

## 6. Risks, including the one that ends the project

- **The consolidation destroys what it organises.** Primary risk. Mitigated only by refusing to
  merge in Phases 0-2 — not by care, because care is exactly what I exercised while writing three
  claims I later reversed.
- **A map becomes the new stale layer.** Real: it is prose about prose. Mitigated by pointers over
  restatement, and by a check that its references resolve.
- **False settlement.** A tidy map implies the questions are closed. Every area map must carry its
  open questions inline, not in an appendix.
- **Drift into fixing.** Several live inconsistencies are named in §7. Fixing them *during* a
  consolidation entangles two kinds of change and makes both unreviewable. They are recorded, not
  repaired here.
- **The right answer may be "don't."** If Phase 0 shows the entry points already work, the correct
  outcome is to stop after (a). That is a success, not an abandonment.

## 7. Known inconsistent or unreviewed, stated plainly rather than smoothed

- **Train/eval wiring.** `CELL_TIMEOUT_SECONDS` bounds training only; curve and endpoint eval run
  outside it. Found today, launcher budget fixed, but *the general question of what bounds a
  container's life is not settled*.
- **In-cell vs between-cell eval.** Curve eval runs in-cell per checkpoint; the endpoint grid runs
  in-cell at the end; `eval_grid.py` also runs standalone. Three paths, one evaluator, no document
  states which is authoritative for a given record.
- **Cross-cell eval overlap** was started empirically today (`ppg` training beside `idaac`
  evaluating). It works; it is not designed, and nothing records it as a supported mode.
- **The VRAM cap** is now known never to have applied. Nine launchers would need editing, and they
  are payload members — an owner decision, still open.
- **`action_repeat` 1 vs the source's 4-8** — open, filed, not answered.
- **Two workspace trees** differ and neither is a subset. Not investigated beyond noting it.

## 8. Operational state at the time of writing

`idaac:101` 600k on card 0: trained to **598016** frames (the predicted endpoint exactly), curve eval
11/11 (431 records), endpoint grid running, projected ~17:10 against an 18:36 reaper. `ppg:1` 600k
training concurrently since 11:53, at `model007.jd`. Card 0: ~28 GiB used, ~4.3 GiB free against a
4000 MiB floor, no co-tenant. Suite 2217 tests / 0 failures; gates 35 pass / 0 fail / 10 owner.
Collector `datasphere/native/collect-host-run.sh` is written and tested but **has not yet run on a
real completed cell**.

## 9. One thing I did not do

The owner referenced `docs/anthropic-prompting.md`. I did not read it before writing this, because
at ~99% context reading it risked triggering compaction mid-task and losing the pending launcher fix.
That is a judgement call and it may be the wrong one; the next agent should read it and revise this
design accordingly.

---

# Blockers, and a workflow — the part that decides whether any of the above works

Section 1-9 is the design. This is what I would raise in a review, and several of these are reasons
to *not proceed* rather than things to work around.

## B1. The agent that can do it well cannot do it, structurally

Consolidation needs both **broad context** (to know what a document omits) and **fresh context** (to
read the material being merged). These are mutually exclusive in practice. An agent with fresh
context merging N documents produces a merge weighted toward whatever it read last; an agent with
the understanding is, by then, near compaction — I am writing this at ~99%.

**Implication for the workflow, not a thing to solve:** never one big pass. Area-scoped passes small
enough that the material fits with room to spare, each one's output checked against primary sources
rather than against the other documents in the pass.

## B2. No test can catch a bad consolidation

Everything else in this repo is mutation-testable: break it, watch a check fail. **A merge that
silently drops a conditional passes every test in the suite.** The project's primary quality
mechanism does not apply to the one operation whose failure is invisible.

**Implication:** consolidation output needs a different review mode — an adversarial reader given
*both* the before and after, whose only question is "what did this drop, and was dropping it a
decision?" If that review cannot be arranged, the phase should not run. This is the strongest single
argument for pointers over rewrites: a pointer cannot drop a conditional.

## B3. There is no neutral presentation of a contested axis

Several axes are genuinely two-sided — `action_repeat` 1 vs 4-8, time-limit handling, whether
packing is viable, whether `ppg` may share a card. A map forces choices about ordering, emphasis, and
what sits in the summary versus the detail, and **every one of those encodes a verdict** even when
the text states none. "Presented neutrally" is not available.

**Implication:** for any axis the ledger marks OPEN or REVERSED, the map presents both positions at
the same depth, or links out without summarizing. Not because it is fairer — because a reader who
sees one position at depth and the other in a clause will act on the first.

## B4. Do not consolidate ground that is still moving

Today alone, live runs invalidated six documents, voided one published finding, and forced three
reversals of positions **I had written hours earlier**. Consolidating an area under active
investigation guarantees re-staling, and worse, launders fresh uncertainty into settled-looking prose.

**Implication:** rank areas by how quiescent they are. **Host operations is the worst candidate right
now** and will be until the production runs finish. Fidelity, comparability and the evaluator closure
are better: their evidence is vendored papers and hashed trees, which do not move.

## B5. The cost this is meant to fix has never been measured

I asserted that navigation is expensive. **I never measured it.** The counter-evidence is that a
subagent answered "why `num_processes=1`" — including six stale contradictions — in about three
minutes, and `where_is_this_decided.py` now does the same sweep in seconds.

**This is the blocker I would raise first in a review.** If Phase 0 shows the existing entry points
answer real questions acceptably, then the honest conclusion is that the problem was smaller than the
remedy, and the correct action is to stop. A consolidation justified by an unmeasured cost, carrying
an unbounded and uncheckable risk, is a bad trade regardless of how well it is executed.

## B6. Order the phases by reversibility, not by value

Adding a pointer map is reversible: delete it. Merging is reversible only in theory — nobody
reconstructs a dropped conditional from a diff six months later, and they will not know one was
dropped. **Irreversible steps go last, after the reversible ones have shown whether they suffice.**

## B7. The two trees must be measured before anything, and it is cheap

`ccm-intro` and the recovery workspace differ, and neither is a subset. Any consolidation that
picks one as canonical silently discards the other's unique content. **I do not know what is unique
in each** — I have worked exclusively in the recovery workspace this session.

A document-set diff costs minutes and is pure measurement. It should happen before any other phase,
because it can change the whole shape of the problem: if the trees have diverged substantially, the
first question is not "how do we consolidate" but "which tree is the subject".

## The workflow I would actually recommend

Not a project. A loop, which is what found everything today:

1. **A question arises** (from a run, a review, an owner ask).
2. **`python scripts/where_is_this_decided.py <term>`** — every position, newest first, supersession
   flagged.
3. **Read the two or three newest, plus anything marked superseded.** Not the whole set.
4. **If a primary source exists under `ext/`, read it.** This step alone produced the
   `num_processes` answer *and* the `action_repeat` question, and it is the only step with a record
   of finding things nobody was looking for.
5. **Write the answer into `OPEN-QUESTIONS-LEDGER.md`** with status OPEN / ANSWERED / REVERSED — and
   mark contradicting documents in place rather than deleting them.
6. **If the claim can become a check, make it one.** A check is the only artifact here that cannot
   go quietly stale.

Steps 2 and 5 exist as of today. **The plausible conclusion is that this loop plus Phase 0 is the
whole deliverable**, and that the rest of the design should stay unbuilt until something measured
says otherwise.

## What would change my mind

If Phase 0 shows an agent taking wrong turns on real questions — reading a stale document and acting
on it, or missing a contested axis entirely — then the per-area maps earn their risk. That is a
measurable outcome and it should be measured before, not asserted after.

---

# The domain — what anyone acting here is actually operating on

**Read this before §1.** The design and the blockers assume a map of the territory; this is that map.
It is an enumeration, not a set of solutions. Nothing here is optional to account for: each item
changes what a correct action looks like, and an executor who has not reckoned with it will produce
something that reads fine and is wrong.

## D1. The artifact kinds, which do not share decay properties or authority

Treating these as one corpus is the first error available.

| kind | authority | how it decays | cost to edit |
|---|---|---|---|
| **vendored primary sources** (`ext/*.pdf`) | highest; settles fidelity questions outright | does not decay | n/a — read-only |
| **hashed trees** (`runnable/*`, evaluator members) | defines what actually executes | cannot decay silently; the hash moves | **high** — moves payload/evaluator revisions, may force re-attestation |
| **executable contracts** (`contract.py`, `families.json`) | authoritative for "what runs" | guarded by `RUNNER_CONTRACT` and tests | medium |
| **checks and tests** | the only artifacts that *cannot* go quietly stale | can be **vacuous** rather than stale | low |
| **generated blocks** (`FAITHFULNESS.md` §0) | machine-derived, `--check`ed | cannot drift | must not hand-edit |
| **hand prose in `docs/`** | none intrinsically | **silently**, and it is where the six stale claims lived | low |
| **`notes/` series** | none intrinsically | silently — but carries reasoning found nowhere else | low |
| **external AI reviews** (`ai-review-*`) | varies wildly by vintage; the 20s series is strong, early ones are not | frozen at their date | do not edit |
| **decision records** (`DECISION-SHEET`, `OPEN-QUESTIONS-LEDGER`, `REGISTER`) | high, *and they carry their own supersession* | by accretion, not rot | append only |
| **operational logs** (`production-host/*`, work logs) | true as snapshots | instantly — they are dated observations | append only |
| **run artifacts** (records, curves, checkpoints) | data, not claims | do not decay; but **labels can be wrong** | never edit |
| **one-off scripts and probes** | encode assumptions from their moment | silently | low |

Consequence: "consolidate the documentation" is not a well-formed instruction until it says which of
these it touches. Merging prose is cheap and lossy; touching a hashed tree costs re-attestation;
editing a generated block is simply wrong.

## D2. The claim kinds, which have different verification routes

- **Measured** — has a number, a date, and a method. Verify by re-measuring. *Inherits the regime it
  was measured in*, which is the failure that recurred four times on 2026-09-09.
- **Derived** — computed from a measurement. Inherits every limitation of its input, invisibly.
- **Cited** — traceable to `ext/`. Verify against the source, never against the citation; A35 was
  right precisely because it read the PDF rather than a review's summary of it.
- **Normative** ("we should X", "declare rather than compensate") — not falsifiable the same way.
  Merging these with factual claims is how a preference acquires the authority of a measurement.
- **Status** ("the gate passes", "35/0/10") — machine-checkable and **time-varying**. Any status in
  prose is stale the moment it is written; it belongs in a check.
- **Conditional** ("under action_repeat 4-8, 2048 steps means…") — **the kind summarization
  destroys**, because the condition is the part that looks like context.

## D3. Live axes of disagreement that must not be collapsed

Each has at least two defensible positions *currently held somewhere in the repo*:

fidelity vs throughput · upstream-faithful vs adapted-for-Door · which upstream reference applies
(Procgen vs DMC) · declare-and-keep vs change-the-value · whether evaluation is part of "a run" ·
single-cell vs packed · in-cell vs standalone evaluation · `action_repeat` 1 vs 4-8 · time-limit
handling (3 bootstrap / 9 terminal) · which of the two trees is the subject.

An executor who resolves any of these *by presentation* has made an owner-level decision without
saying so.

## D4. Temporal structure — much of the corpus is true only at a time

Host state changes hourly. Gate counts change per commit. Recipes have generations (IDAAC-P → C2),
and documents written under an earlier generation are not wrong, they are **scoped**. Run outcomes
are dated observations. `HANDOFF.md` is marked EXPIRED and kept deliberately as evidence.

Consequence: a value without its timestamp and regime is not a fact, and a consolidation that
normalises everything into the present tense manufactures false currency at scale.

## D5. Ownership boundaries — not everything is the executor's to settle

- **Owner decisions** — ten gates currently read OWNER. Writing a confident summary of one does not
  close it, and reads as if it did.
- **Fidelity questions** — need a primary source first, then the owner. Never an operator judgement.
- **Operator choices** (cap values, packing, schedules) — safe to change with evidence.
- **Mechanical repairs** — safe, and should be accompanied by a check.

## D6. What is not known, and blocks honest scoping

- **What is unique to each tree.** `ccm-intro` vs the recovery workspace; neither is a subset. Not
  measured. Cheap to measure. Changes what the subject *is*.
- **The real navigation cost.** Asserted, never measured (B5).
- **How many claims are currently stale.** Six were found on *one* axis. The rate across all axes is
  unknown, and six-per-axis would imply a very different remedy than one-per-axis.
- **Whether record labels are correct.** `scripts/audit_record_frame_provenance.py` was written today
  to answer exactly this and **has not been run on a completed cell**.
- **Whether `where_is_this_decided.py` has adequate recall.** It searches seven directories and skips
  vendored trees; nobody has checked what it misses.

## D7. Constraints that bound any plan

- Hashed trees cost re-attestation, so a "tidy the launchers" change is not free.
- Production runs are in flight; the host is shared; findings are still arriving.
- **No test can validate a merge** (B2) — the project's main quality mechanism does not cover the
  central operation.
- Every executor has a context limit, and the operation needs both breadth and depth (B1).
- Documents are cheap to add and effectively impossible to un-drop.

## D8. What "done" cannot mean

- Not "one document describes the current state" — several axes have no single current state.
- Not "no document contradicts another" — contradictions between a superseded and a current document
  are *information*, and the marker is the fix, not the merge.
- Not "an agent needs to read only one file" — depth is the point; the goal is knowing *which* file,
  and what it costs to go deeper.
- Not "the uncertain material was removed" — that is the failure mode wearing the costume of success.

A reasonable "done" looks like: an agent asking a real question reaches a correct, appropriately
hedged answer in bounded time, **and can tell when the question is open**. That last clause is the
whole difficulty.
