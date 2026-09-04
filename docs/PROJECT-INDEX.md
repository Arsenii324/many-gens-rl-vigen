# Project documents

The benchmark repo is this directory's parent. These are the documents that outlive any one
session; the code's own entry point is [`../README.md`](../README.md).

## How this set works

**[`STAGES.md`](STAGES.md)** — where the project is, at the level a person asks it.

**[`SYSTEM.md`](SYSTEM.md)** — the document system itself: the durable/working-state distinction
everything follows from, the four document shapes and how each is edited, what triggers a write to
which file, the compaction procedure, and an honest list of the system's own weaknesses.

> **2026-08-17: the approach changed, and it changes where to start.** The null is now the
> original repository, cloned, running its own `train.py`; the port under `rlgen/` is superseded.
> Start with **[`RUNNABLE-ORIGINALS.md`](RUNNABLE-ORIGINALS.md)** (what runs, what was changed to
> make it run, what the T4 proved) and **[`PART2-METRIC-INVENTORY.md`](PART2-METRIC-INVENTORY.md)**
> (what each baseline emits, and seven findings — two of which change what the benchmark
> measures). The mechanical facts now come from `python ../scripts/deviations.py`, not
> `state.py`, which reports on the superseded port and says so in its first line of output.
>
> Reproduce the whole of Part 1 with `bash ../runnable/_launch/smoke_all.sh` — 12/12, 66 minutes.

**Pick up here, in order (pre-2026-08-17 route, still valid for `rlgen/`):**
[`STEP-ZERO.md`](STEP-ZERO.md)'s handoff and gates (the practice) →
`python ../scripts/state.py` (the mechanical facts, recomputed rather than remembered) → whichever
one document below answers the question you actually have. Do not read the whole set; it is
~7500 lines and is not meant to be.

| Document | What it is | Read it when |
|---|---|---|
| [`../instruction.md`](../instruction.md) | **Start here.** What was inherited from which prior artifact, every decision and its reason, what was deleted and where it lives now, what is guaranteed by a test, and the known gaps. | Picking the repo up, or preparing to discuss it. |
| [`TASK.md`](TASK.md) | The task of record. The supervisor's brief verbatim, a faithful rendering, R1–R7 as mechanically checkable criteria, our own scope decisions, and the open questions for DZ. | First, if you want to know what was asked rather than what was built. |
| [`RIGOR.md`](RIGOR.md) | The working standard: understanding, observability, debugging, verification, the four vacuous-test failure modes, **mutation testing done properly**, claims discipline, provenance. Ends in a pre-claim checklist. | Before running or claiming anything. |
| [`SYSTEM.md`](SYSTEM.md) | **How this set of documents works, and how state survives a compaction.** The durable-vs-working-state distinction and the two symmetric failures behind it (working state filed as fact; durable claims held only in context and lost); the four document shapes and how each is edited; what event triggers a write to which file; the compaction procedure; the instruments that audit these documents and which are not built. Explicitly not a standard — it is the working system, to be changed when it makes a task harder. | Before writing to any document; when picking work up after a compaction; when deciding where something belongs. |
| [`STAGES.md`](STAGES.md) | **A virtual view of the project: nine stages a person can hold, and where the work sits on them.** Explicitly not builder instructions, not error containment, and not a partition — it names groupings over register entries it does not own. Every stage cites real entries; `tests/test_stages_map.py` fails if a stage cites nothing or cites an entry the register lacks. | When asking "where is this project and what is left?"; never as a rule for how to do the work. |
| [`../HANDOFF.md`](../HANDOFF.md) | Where to resume: state, the next steps in order, and the traps that cost the most time. Scratch — delete once absorbed. | Picking the work back up after a break or a context reset. |
| [`VALIDATION.md`](VALIDATION.md) | What was actually run, what it returned, and what it does **not** establish. Dated: this is the one place volatile numbers belong. | Before believing any claim about correctness. |
| [`STATUS-AGAINST-THE-GOAL.md`](STATUS-AGAINST-THE-GOAL.md) | **How far the actual task is, top-down.** Progress against R1–R7, the 16 open degrees of freedom ranked by distortion, the cross-checks that would remove most doubt, and the concerns. | To answer "how far along are we, really?" |
| [`SUPERVISOR-BRIEFING.md`](SUPERVISOR-BRIEFING.md) | **For the supervisor.** Two corrections to the brief, three decisions that block real compute, what is verified, and what is explicitly not established. | Before a supervisor meeting, or to understand what is waiting on someone else. |
| [`PREMISES.md`](PREMISES.md) | The decision surface. Starts from "just run the algorithms" and adds the minimum premises that make a number mean anything; then the degrees of freedom, the priority order, and the questions that need research rather than a decision. | Before designing an experiment, or when asking "why is this set to that?". |
| [`FAITHFULNESS.md`](FAITHFULNESS.md) | Per algorithm: canonical paper and author-released code, the published hyperparameters, what we run instead, and every divergence with its source tag. | Before quoting any baseline's result as that method's result. |
| [`EVAL-PROTOCOL.md`](EVAL-PROTOCOL.md) | The evaluation procedure, proposed 2026-09-03, and with it a proposed answer to P-C76/R3. Why evaluation must be **offline from checkpoints** (three of twelve run no periodic training-time evaluation at all, so same-axes metrics are unreachable from training logs by construction), the common grid, the competence gate, the checkpoint cadence, and what remains open. | Before running any evaluation, and before deciding the retention endpoint. |
| [`EVALUATOR-DELTA.md`](EVALUATOR-DELTA.md) | The shared evaluator against each baseline's own, delta by delta — the proof obligation that a ratio comparison does not discharge. Three material deltas nobody had written down: our determinism setting, an RNG offset from the rlvigen verification probe, and a different episode-accounting scheme for `idaac`/`ibac_sni`. | Before reporting any number produced by the shared evaluator. |
| [`POINTS-LIST.md`](POINTS-LIST.md) | The production-readiness (I), defaults (J) and specific-entry (K) working list, recovered from a session transcript after it was lost — it had never been written to a file. Carries a status per item. **Its I/J/K labels collide with `INTEGRATION-DELTA.md`'s I/J/K/M faithfulness ledger and are unrelated**; that collision already caused one wrong answer. | When asking what production readiness still needs. |
| [`COMPARABILITY_CONTRACT.md`](COMPARABILITY_CONTRACT.md) | Separate from `FAITHFULNESS.md`'s per-algorithm question: what makes all 12 baselines' reported metrics sit on the *same axis* even though their training internals don't need to match. The env choke-point invariant, the per-baseline audit, the choke-point instrumentation's mutation-test results, and a standing checklist for auditing a 13th baseline. | Before comparing two baselines' numbers, or before adding one. |
| [`DECISION_LOG.md`](DECISION_LOG.md) | Every decision, made while actually developing something new, about what a value/argument *means* rather than just its type (normalized vs. raw, truncation vs. termination, what a counter counts) — with the semantic assumption stated explicitly. Deliberately sparse; a fix to already-existing code belongs in `FAITHFULNESS.md`/`VALIDATION.md`/git log instead. | Before assuming what a new piece of instrumentation or integration code silently assumes. |
| [`ORIGINAL_LOCATIONS.md`](ORIGINAL_LOCATIONS.md) | A lookup table, not an analysis: for each of the 12 baselines, exactly where the original authors' own code sits on this disk (verified by `git remote -v` plus commit-level provenance, not assumed from a folder name), any continuous-action port sitting alongside it, which three baselines have no continuous ground truth anywhere on Earth, and a Transcription/Adaptation/Construction classification per `porting-directive.md` §0. | Before diffing a baseline against "the original", before trusting an old citation's claim about where a reference lives, or before assuming a baseline's code is a faithful port rather than an unreferenced construction. |
| [`REGISTER.md`](REGISTER.md) | The findings register per `porting-directive.md` §5: found → recorded → decided, one row per finding, none discharged by a later repair. Distinct from `DECISION_LOG.md` (decided-only) and `FAITHFULNESS.md` (narrative, findings scattered inline). | Before assuming an open question has already been answered somewhere, or when deciding what to work on next. |
| [`DISCIPLINE_IMPOSED.md`](DISCIPLINE_IMPOSED.md) | Dense, unpolished recap of the verification/scope/delegation rules this session converged on *before* `porting-directive.md` existed — a session trace, not a competing standard. `porting-directive.md` (workspace root, `ccm-intro/docs/`) is now the authoritative document; read that first. | Before resuming this audit work, or to see where a rule in the directive was first arrived at and why. |
| [`REVIEW.md`](REVIEW.md) | Review of the code this replaced, stamped to commit `07c3f12` with a content hash. | To understand why the rebuild happened, or to check a claim about the old code. |
| [`compute.md`](compute.md) | What runs locally and what does not; measured (contended, order-of-magnitude) real training throughput; Kaggle status flagged as unverified/undated rather than asserted. | Before launching anything longer than a smoke run. |
| [`STEP-ZERO.md`](STEP-ZERO.md) | **Standing practice, not a mechanism.** What to do per baseline *before* any code: identity, reading the original, base-term triage computed from facts rather than judgement, and the claim-shaping rules that keep results legible after a compaction (which strips hedges, measurably). §7 the observation→artifact spectrum and marking where a claim sits on it; §8 the instruments that actually surfaced unknowns here, with honest yield, and the loop by which this file grows; §9 budget tiers — how the *kind* of step changes when the objective inverts from P(finish) to P(detect error \| error), with the stopping rule that keeps the high tier bounded. | Before starting work on any baseline; after a compaction; when choosing how much rigour a piece of work warrants; when deciding whether to write code or read a reference first. |
| [`INTEGRATION-DELTA.md`](INTEGRATION-DELTA.md) | **Everything in this code that is ours rather than the original authors'** — every change, addition, removal, substitution and value choice made relative to an externally-provided base, including back-merges where reference behaviour was restored over a local version. Keyed by authored element, where `FAITHFULNESS.md` is keyed by algorithm; the two cover nearly the same set because "code we authored" and "divergence from the paper" are close to isomorphic. What makes it not a duplicate is its one extra column: whether each element's correctness is **intrinsic** (legible at the edit, against the original) or **not** (a debt, whether or not a test currently passes). The not-intrinsic rows are the point of the file. | Before trusting any part of a baseline as the method's own behaviour; before editing a module, to see what is already load-bearing and unproven; when asking "who wrote this, and how do we know it's right?" |
| [`INTERIM-REPORT-2026-08-16.md`](INTERIM-REPORT-2026-08-16.md) | Reflective, not a log: the reward-normalizer arc, CTRL's hermetic build, `onpolicy_ext.py`'s deletion, and Stage 3's start, read through `porting-directive.md`'s own themes — where abstractions leaked and why, tiers doing real epistemic work, and two places the discipline itself slipped this session (including from the one applying it). | To see the directive's principles argued from this session's actual evidence, not just cited. |
| [`../datasphere/README.md`](../datasphere/README.md) | The verified DataSphere bring-up: job scripts that have run, the GL and CUDA gates and why each exists, measured throughput, and the traps (outputs upload only at job end; `download-files` silently caps at 1 GiB and exits 0). | Before sending anything to remote compute. |
| [`../setup/VENDORED.md`](../setup/VENDORED.md) | Every pin, and what breaks when it moves. Several pins fail *only on the evaluation path*. | When the environment misbehaves, or before changing a version. |
| [`RESEARCH-FRAME.md`](RESEARCH-FRAME.md) | **What is GIVEN vs MANIPULATED vs MEASURED vs CONFOUNDED, and which claims the design can support.** Method identity is perfectly collinear with seven configuration choices, so no difference is attributable to the algorithm; retention is the endpoint precisely because it makes each method its own control. Decides C1/C2 by deciding the claim first. | Before writing up any comparison; before equalising anything between baselines; when checking whether current work still serves the question. |
| [`AUDIT-2026-08-17.md`](AUDIT-2026-08-17.md) | **The report.** Nine questions answered with locators: what was merged (nothing), what was removed (nothing), what deviated including parameters, the format/shape class that propagates into network sizes, CUDA vs MPS, the deviations that are not changes, the metric set as implemented, what to do next, and what survived being checked by people who had not read it. `AUDIT-2026-08-17.html` is the **published snapshot** of the same content and is regenerated from this file, never edited in parallel. | When someone outside the project asks what was done and how far it can be trusted; before repeating any claim about fidelity. |
| [`MILESTONES.md`](MILESTONES.md) | **Which commits are the ones that mattered.** ~11 entries out of 200+ commits, each a point where the project became something it was not before — 12/12 training, the blind audit's red-reads-as-green finding, the 3/9 truncation split, the regimes measured as separable, the contract-vs-clones debt. Also records the two direction shifts (port → clone; instrument before result). | When you need a hash from a milestone, or a milestone from a hash; when onboarding someone to what happened and why. |
| [`CONSTRUCTION.md`](CONSTRUCTION.md) | **The single authority for what is open, decided or resolved.** Each item carries a class (INHERITED / OURS / UNDECLARED / FALSE-CERTIFICATION / DESIGN-GAP), a status, a blast radius, and — once acted on — the decision, the attempt and the *effect*. Structure pinned by `tests/test_construction_register.py`; count it with `python scripts/register.py --check` rather than reading a number here, which is why this cell no longer states one — it said "26 items" from the port era until 2026-08-24, when the register held 63. | Before deciding anything about comparability; before writing a difference up anywhere else. |
| [`library-survey/CONTEXT.md`](library-survey/CONTEXT.md) | What the established RL libraries actually do, and where our practice differs. Answers three things the audit could otherwise only assert: whether any library already implements our twelve (none does — SAC is universal, robosuite appears nowhere), who in the field shares our duplication stance and on what grounds (torchtune and Dopamine do, CleanRL does but argues readability not fidelity, Acme/Pearl/Mushroom-RL are the opposite pole), and whether our four authored continuous heads have prior art (they do not — the PPG upstream's only Gaussian is unreachable dead code at fixed σ=1). `raw/` is the source of record, verbatim and unmerged; `synthesis-*.md` is our reading and says so. **All sweeps have landed** — fifteen libraries; TorchRL is the one to read first, since its issue tracker documents ~20 cases of a shared component silently changing an algorithm's numbers. | Before claiming something in this project is novel, unusual, or standard; before deciding whether to borrow from a library rather than clone an original. |
| [`independent-audit-2026-08-17.md`](independent-audit-2026-08-17.md) | A deliberately **blind** re-derivation of this project's own past findings — 50 categories, checked against the current tree — with my verification of each live finding above it and the auditor's verbatim report preserved unedited below it. D2 and D3 were re-instances of defects `REGISTER.md` had already named and removed, and are fixed with red-green verification; D1's blanket claim is **wrong** (`dmc_gb` does not zero the bootstrap) and the correction is recorded rather than the claim. Its durable conclusion: the clone approach makes most port-era defect classes *structurally impossible*, but eliminates none of the **harness** half — metric plumbing, protocol declarations, device shims, test guards — which is where every live finding sat. | When asking whether the audit inherited its author's blind spots; before assuming a past defect class cannot recur. |

**[`ASSURANCE.md`](ASSURANCE.md)** — *what is believed, and by what mechanism.* Every headline
claim sorted by **how** it is assured: by construction, by a falsifiable test that could have
failed, by measured instrument sensitivity, by independent re-derivation, by a burden of proof that
withholds rather than asserts, verified post-hoc, asserted-unverified, or a named gap. Read it
before quoting any number from this project, because the mechanisms are not interchangeable and
"verified" flattens all eight into one word.

## Dated snapshots

**[`dated/`](dated/README.md)** — documents that were true when written and are not maintained after.
Supervisor reports, one-off review passes, point-in-time audits. **This folder gets one row here and
its files get none**, deliberately: the index must not grow a row per snapshot, and the path itself
carries the "not living" signal. `tests/test_docs_integrity.py` enforces that each file inside states
its own write date in its prose, so a paragraph pasted out of one still carries it.

Read anything in there as a lead to check, never as authority. See [`dated/README.md`](dated/README.md).

## Historical and single-purpose documents

Kept, not indexed above, because they are not part of the live path. Listed so that "absent from
the index" never has to mean "forgotten" — the orphan check in `tests/test_docs_not_stale.py`
reads this section.

| file | what it is |
|---|---|
| [`STATE-2026-08-16.md`](STATE-2026-08-16.md) | What the superseded `rlgen/` port contained, measured. Read for what the port was, not for what is true now. |
| [`DECISION_LOG.md`](DECISION_LOG.md) | Port-era reasoning, three entries. Historical; the live register is [`CONSTRUCTION.md`](CONSTRUCTION.md). |
| [`FINAL-VERIFICATION-CHECKLIST.md`](FINAL-VERIFICATION-CHECKLIST.md) | A checklist run against the port era. |
| [`dz-report-ru.md`](dz-report-ru.md), [`dz-report-ru-spoken.md`](dz-report-ru-spoken.md), [`dz-report-criteria.md`](dz-report-criteria.md) | A supervisor briefing and its criteria, in Russian, from an earlier state of the project. |
| [`dz-report-2026-08-24.md`](dz-report-2026-08-24.md) | The 2026-08-24 Russian supervisor report. A **dated snapshot**, not a live document: it states the project as it stood that day, so read it for what was reported and check any claim in it against [`CONSTRUCTION.md`](CONSTRUCTION.md) before repeating it. Its taxonomy of divergence-kinds was written here first and is now recorded in [`SYSTEM.md`](SYSTEM.md). |

## Related work in this workspace

- [`../../gen-rebuttal/vigen-idaac`](../../gen-rebuttal/vigen-idaac) — IDAAC and ALDA on RL-ViGen
  robosuite for the AAAI rebuttal. The source of the env-seam invariants and of the measured
  random-policy floors this project reproduced independently. Related by documented invariants,
  not by an import — see `instruction.md` §6.
  **Correction:** an earlier version of this line described `vigen_alda/eval_dz.py` there as "DZ's
  own eval protocol". It is not a standard and was explicitly withdrawn as an example of good
  evaluation — treat it as prior work, not as a reference. Our evaluator is checked against
  RL-ViGen's `eval.py::robo_eval` instead (`VALIDATION.md` §0.05).
- [`../../../docs/rl-experiment-runbook.md`](../../../docs/rl-experiment-runbook.md) — the
  workspace standard `RIGOR.md` specialises.
- [`../../../docs/local-envs.md`](../../../docs/local-envs.md) — interpreters and hardware limits.
