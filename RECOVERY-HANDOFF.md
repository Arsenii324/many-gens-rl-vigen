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

**Where the candidate lives, and the risk that carries.** ~~This tree has **no
`.git`**.~~ **Corrected 2026-09-04 (later the same day): it does now** — one
local repository, 637 files, 8.2 MB, no remote and nothing pushed, following
the rule `scripts/deviations.py` already stated (clones carry their own `.git`
and are reproducible from `ext/` plus `runnable/_patches/*.patch`, so the
patches are tracked and the 200 MB clones are not). **The reconciliation below
is untouched by this** and remains the single largest risk. The versioned
original is `ccm-intro/projects/many-gens-rl-vigen`,
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

**Open and owner-facing**: P-C76 / R3, plus production authorisation and the actual
1–2 V100 allocation. The protocol defaults are otherwise frozen: all three headline metrics,
endpoint headline plus 50k trajectory stamps, three seeds, 6e5 Door frames (which supplies C48's
anchor), and **C61 at 0.0 for ibac_sni only**. This working tree is the production tree; no pre-run
merge is required. `python scripts/open_decisions.py`
is the live list; `python scripts/requirements.py` recomputes R1–R7 rather than
trusting `docs/TASK.md`'s stale table.

**Later on 2026-09-04 — the contract moved and the tree is versioned.**
**R7 is no longer NOT MET**: it failed partly because this project read each
job's records out of a scratch directory and discarded them, so the repo held
zero training logs and zero eval result sets while six jobs had produced them.
`results/records/` and `results/logs/` now retain 1,001 records and five
training curves (1.6 MB) — the storage rule `EVAL-PROTOCOL` §6 already
prescribed. Two of R7's four links were also graded against the **pre-C95 local
pipeline** and could not have passed whatever the clone era produced. **R3 is
now the only hard NOT MET**, and it is P-C76, which is yours.

**This tree is under git** (`.gitignore` restored from the versioned original
after I overwrote it). Local only, nothing pushed; it is *not* the hunk-by-hunk
merge, which remains yours and unstarted.

**Defaults set and awaiting approval, none marked settled**: C48 (the anchor,
contingent on §3b #5), C61 (`ibac_sni` uses entropy coefficient 0.0 as the
empirical production default after its 0.01 trip-wire fired), the endpoint-only cross-baseline
table, adaptive seeds with an explicit table of what each count licenses, the
camera axis excluded with its blocker named, and C84 narrowed to an MPS-only
event that cannot reach a production number. Fidelity items 5 and 6 dissolved as
port-era artefacts; `scripts/open_decisions.py` is 27, from 29.

**Production remains out of reach at the planned shape**, and this is arithmetic:
`datasphere/native/plan_production.py` puts 6e5 × 3 seeds × 12 baselines at
**525 job-hours / ~120k RUB / 18.5× the 5M-unit grant**, after enforcing CTRL's measured
`gt4i.1`, one-cell envelope; one cell's archive
at 6e5 is ~1.5 GB. Nothing about the production run is approved or started.
*(Free local disk was ~30 GB and is **73.1 GB** since the owner cleared space on
2026-09-04, so archive size no longer binds; the reason checkpoints stay remote
is C95, not capacity.)*

**Later still on 2026-09-04 — the contract moved again, and four instruments were
found reporting verdicts they had not earned.**

**R4 is now MET**, and it was never a judgement: it asks whether the twelve can be
given an equal training length, which the descriptors answer without any run.
Computed, the seven runner families execute **599,040–600,064** frames against a
600,000 request — equal to **0.17%**, the residual being each family's own rollout
quantum. **R6 now has evidence** rather than an opinion:
`scripts/audit_implementations.py` checks each algorithm's distinctive mechanism is
defined *and executes at the budget being reported*, and the answer is
budget-dependent — 12/12 at 6e5, but **11/12 at 10,000 frames, because `ppg`'s
auxiliary phase first fires at 65,536 frames**. Every `ppg` number this project
holds is therefore PPO exactly. That is a budget floor with a mechanism behind it,
not a guess about where learning saturates.

**All twelve can now produce a checkpoint curve, validated on hardware**
(`bt1h3l1rl7v7n4bve0au`, `bt1791fdh5uctgr1ckhk`), so "endpoint" and "best over the
trajectory" are both reconstructible. Because C95 forbids evaluating those
checkpoints locally, `run_probe.sh::run_curve_eval` evaluates the grid **in the
container** and sends home records; `bt1sgcg49j6d6jk84vuj` is its first real run
and also the first ever exercise of the `ppg` and `ibac_sni` evaluator families.

**[C61](docs/CONSTRUCTION.md#c61) is measured**: under the newly-ported impala
architecture `ibac_sni`'s `mean_log_std` rose monotonically **0.0026 → 1.4472**
over 100k frames, entropy 9.95 → 20.03, success 0.00 throughout — entropy
*inflation*, not collapse, and it survives the architecture change, which separates
C61 from C3. `bt1338ue402pkpua43g0` changes one flag to test whether the entropy
bonus causes it.

**The day's theme is instruments reporting what they had not earned**: a cadence
knob the runner never read (two jobs validated nothing; one reported SUCCESS); a
payload checker whose contract failure shared an exit code with argparse's usage
error, so a mistyped command read as "marker missing"; a `ppg` post-condition
asserting a filename the descriptor had already renamed; and six of seven evaluator
families that never verified the regime they were handed. All four are fixed, and
each has a test that fails on the **class** rather than the instance.

*(Those figures were **445 h / 101k / 15.6×** until 2026-09-04, when the cost
model was found to cover only TEN baselines while describing itself as twelve —
a stale note claimed `alda` and `ctrl` had no successful CUDA run after both had
completed. Every previously quoted production cost was short by a sixth of the
fleet. Shorter shapes, for scale: 1e5 × 1 seed is 42 h / 7.3k RUB / **1.1×** the
grant, and 1e5 × 3 seeds is 95 h / 16.6k / 2.6×.)*
