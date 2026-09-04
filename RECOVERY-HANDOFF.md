# Isolated candidate recovery handoff

This file belongs only to the reconstructed candidate, never the original
project tree. The recovery notebook's explicit first document and raw-evidence
ledger are external to keep recovery operations out of the project-wide
research record:

`/tmp/ccm-intro-datasphere-recovery-2026-08-31.2KXKs5/START-HERE.md`

Before changing this candidate, read that file, then the original project's
`CLAUDE.md`, `docs/PROJECT-INDEX.md`, `docs/STEP-ZERO.md`, `docs/SYSTEM.md`,
`docs/PREMISES.md`, and `docs/PART2-METRIC-INVENTORY.md`. The old shared
harness is superseded; each original baseline's own entry point is the null.
Candidate changes are reviewed and merged only hunk-by-hunk against the
untouched original; there is no automatic merge.

## State, updated 2026-09-04 — the previous version of this section was false

It read *"Current local gate: `tests/test_datasphere_native_contract.py` has 42
passing tests. No remote job is active or queued from this candidate."* Both
halves had gone stale: that file now holds 81 tests, and this candidate has
submitted roughly twenty DataSphere jobs. A handoff that describes a quiet tree
while the tree is running jobs is the exact failure this project keeps
recording elsewhere, so it is corrected rather than patched over.

**Where the candidate lives, and the risk that carries.** This tree has **no
`.git`**. The versioned original is `ccm-intro/projects/many-gens-rl-vigen`,
branch `nd-ln-architecture-transition`, HEAD `f041f5e1`, with 53 uncommitted
files and content from ~2026-08-18. 30 files differ between the two; 18 exist
in only one. Everything from 2026-08-31 onward — the whole `datasphere/native`
infrastructure, C95, P19, the pre-production pass — exists **only here**. Per
the policy above the reconciliation is hunk-by-hunk and manual; it has not been
done and is the single largest risk to this work.

**Local gate.** `python -m pytest tests/ -q` — the expected steady state is
**one** deliberate failure,
`test_docs_integrity.py::test_internal_links_resolve[PROJECT-INDEX.md]`, whose
link (`../../gen-rebuttal/vigen-idaac`) resolves in the canonical tree and not
in this partial copy.

**What this candidate established.** All twelve baselines run end to end on
CUDA at a common budget (`docs/dated/preprod-table-2026-09-03.md`); evaluation
of a container-trained checkpoint on this laptop is invalid
([C95](docs/CONSTRUCTION.md#c95)); the evaluation procedure and a proposed
answer to P-C76 are in [`docs/EVAL-PROTOCOL.md`](docs/EVAL-PROTOCOL.md); the
production-readiness working list, recovered from a transcript after being lost,
is [`docs/POINTS-LIST.md`](docs/POINTS-LIST.md).

**Added 2026-09-04 — the first competent policy, and the metrics work.**
`drqv2` at 100k (`bt15e9v1k2ngmb71hnjn`) reaches **success 1.00 / return 480.6
in the training regime and 1.44 at the random floor in eval-easy** — retention
0.30%, the project's first *defined* retention number, since every earlier cell
was floored in both regimes and the ratio was undefined rather than small. See
[`docs/dated/hundred-k-results-2026-09-04.md`](docs/dated/hundred-k-results-2026-09-04.md).
`idaac`'s shared-evaluator burden is discharged (`CONSISTENT`, 2 of 12) on a
powered comparison, using a dispersion test rather than a point ratio.
Per-baseline metrics now reach the record set: per-episode success flags in all
seven evaluator families, `ctrl`'s full metric dict via the W&B sink reader, and
C61 policy health on all four continuous PPO heads instead of two.

**Open and owner-facing**: P-C76 / R3, the §3b knobs (headline metric, seeds,
budget), and the merge above. Defaults are now recorded for **C48** (anchor via
`drqv2` at 6e5, contingent on §3b #5) and **C61** (hold the coefficient at 0.01,
decide on the diagnostic, trip-wire named) — recorded as defaults awaiting
approval, which does **not** mark either settled. `python scripts/open_decisions.py`
is the live list; `python scripts/requirements.py` recomputes R1–R7 rather than
trusting `docs/TASK.md`'s stale table.

**Production remains out of reach at the planned shape**, and this is arithmetic:
`datasphere/native/plan_production.py` puts 6e5 × 3 seeds × 12 baselines at
**445 job-hours / ~101k RUB / 15.6× the 5M-unit grant**, and one cell's archive
at 6e5 is ~1.5 GB against ~30 GB free here. Nothing about the production run is
approved or started.
