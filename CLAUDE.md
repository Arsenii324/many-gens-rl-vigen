# many-gens-rl-vigen

Supplements the workspace `CLAUDE.md` one level up; it does not replace it. Everything here is
specific to this comparison and should not be read as applying to other projects in the workspace.

## BEFORE ANY ACTION ON THE PRODUCTION HOST — read `notes/production-host/` in full

**`cds2` is a university communal machine with strict GPU and environment control, shared with
other people's running work.** Before touching it in any way, read
**[`notes/production-host/`](notes/production-host/)** — **every file, in full.** Not this section,
which is a pointer and not a substitute; the enforceable specifics live in those files and the
specifics are where the harm is.

The four that override everything, stated here so they cannot be missed — and still not a
replacement for reading:

1. **All work happens strictly inside a Docker container.** Install into the container. Never the
   host.
2. **Never install, update, change or remove anything on the host.** No `apt-get`, `brew`, `pip`
   outside a container, conda, or any package manager. **Never touch drivers.**
3. **Never cause another user's process to fail** — not by OOM, CUDA OOM, a full disk, or taking
   every core or both GPUs. Assume no resource is free; verify, then keep verifying.
4. **A block is a stop, not a puzzle.** A busy GPU, a missing permission, an unreadable path: do
   not work around it. It probably encodes context nobody wrote down.

Two specifics that have already nearly caused harm and are easy to miss:

- `run_on_production_host.sh` defaults to **`--gpus all`**, which takes *both* V100s. Always set
  `DOCKER_GPUS='"device=N"'` on a card verified free.
- Run `NATIVE_HOST_DRY_RUN=1` first, every time, and read its `mounts:` and `env:` blocks. It runs
  every guard without executing anything.

Never write a document that implies a machine may be used, a resource is free, or an action is safe
by default. Reachability is not permission.

Layout and routing: [`docs/PROJECT-INDEX.md`](docs/PROJECT-INDEX.md). Where the project sits:
[`docs/STAGES.md`](docs/STAGES.md). What is open: [`docs/CONSTRUCTION.md`](docs/CONSTRUCTION.md).
Where to resume, and which traps cost time last session:
[`docs/STEP-ZERO.md`](docs/STEP-ZERO.md)'s newest handoff block — the operational facts live only
there, and the register is the first thing to grep when a run fails.

**This project's instruments miss defects at joins, measurably.** The largest one found to date —
[C69](docs/CONSTRUCTION.md#c69), an unseeded RNG moving the door ~1.6 cm between evaluations that
recorded the *same seed* — was found by an outside reader with no access to this repository, while
862 tests, 71 register entries and a `seed` field in every grid did not. A green suite is evidence
about artifacts and says almost nothing about the seams between them. Before trusting one on a
claim about **our own measurements**, run a blind-spot pass: state the mechanism you believe
produces a number, then check that each RNG, config key and code path it names does what its name
implies. Technique and its yield here: [`docs/STEP-ZERO.md`](docs/STEP-ZERO.md) §8.

## Read in full, not in fragments

- [`docs/SYSTEM.md`](docs/SYSTEM.md) — what is recorded where, and what routes where. Consult
  before adding any document, format, or record type.
- [`docs/RESEARCH-FRAME.md`](docs/RESEARCH-FRAME.md) — which claim this design can support.
  Several open items follow from the claim and cannot be decided on their own merits.
- [`docs/PREMISES.md`](docs/PREMISES.md) — **the decision surface**: every place something was *set*
  rather than derived, as a ladder P0–P10 with the evidence forcing each rung. Added to this list
  2026-08-25, and the reason is a change of stage rather than a change of mind: the remaining work
  on this project is largely *decisions*, so the surface is now governing. Two rungs earn it on
  their own — **P4** holds the evaluation-protocol choice that decides what every reported number
  means, and **P6** ("published values do not transfer; they have to be *mapped*, and mapping is a
  choice") is the half-named root of the class [C75](docs/CONSTRUCTION.md#c75) names. Reading a
  premise before arguing with a value costs a minute and has repeatedly turned out to be where the
  argument already lives.
- [`docs/PART2-METRIC-INVENTORY.md`](docs/PART2-METRIC-INVENTORY.md) — **the reasoning of record
  for what every reported metric *is***: which returns are raw and which normalised (with the
  wrapper-order argument that decides it), the 8/4 frame-stack split, the three-way resolution
  split, three distinct action distributions, per-baseline x-axis units. Added to this list
  2026-08-26 for a specific reason: on that day its reward and frame-stack facts were **re-derived
  from scratch** by an agent that had not read it. The answers agreed, which was luck — a fresh
  derivation that disagreed would have been filed as a finding against a document nobody had
  opened. It was already routed from `PROJECT-INDEX.md`, `SYSTEM.md`, `TASK.md` and
  `RESEARCH-FRAME.md`; the routing was not the problem, not consulting it was. Before deriving any
  fact about what a number means, read this file — and treat
  `scripts/audit_comparability_seam.py` as its regression check, never as a second opinion.
- [`../../docs/porting-directive.md`](../../docs/porting-directive.md) — the standard the nulls
  below cite. A quoted line without its section loses the conditions for relaxing it.

Keep this list to documents that govern how to work; anything holding what is true is routed into
via [`docs/PROJECT-INDEX.md`](docs/PROJECT-INDEX.md).

## Nulls

These hold by default. Each names where the conditions for relaxing it live, and that link is the
only route to relaxing it — this list is a restriction, not a summary you may act from. The lines
are taken from their sources unchanged; do not paraphrase them here, because a second wording
drifts from the first and nothing notices. **Anything in parentheses is this project's own note,
not part of the quote** — that is the only place an addition may live.
`tests/test_claude_md_nulls.py` checks the unparenthesised text against the source it names.

If a null and a task appear to conflict, the conflict is the finding. Record it rather than
resolving it silently.

- Hermetic per baseline: own file, own utilities, no shared base classes, runners, or adapters.
  Duplication is cheaper than a wrong abstraction.
  → [`../../docs/porting-directive.md`](../../docs/porting-directive.md) §1
- Step N dictates step N+1: a discovery halts the downstream plan.
  → [`../../docs/porting-directive.md`](../../docs/porting-directive.md) §5
- Record branch points, not their forced consequences. Per branch point: the structural property
  of the original that the mechanism depends on, the options considered, the choice, and the
  result that would show the choice was wrong.
  → [`../../docs/porting-directive.md`](../../docs/porting-directive.md) §4
- The reference is authoritative about the algorithm, not about the measurement.
  → [`../../docs/porting-directive.md`](../../docs/porting-directive.md) §2
- Reach T3 on the reference's own domain before adapting.
  → [`../../docs/porting-directive.md`](../../docs/porting-directive.md) §4
- Two numbers from different systems are not the same quantity until shown to be. (Reading added
  2026-08-18: this covers quantities that share a name, and quantities that share a lineage.)
  → [`docs/RESEARCH-FRAME.md`](docs/RESEARCH-FRAME.md),
  [`docs/COMPARABILITY_CONTRACT.md`](docs/COMPARABILITY_CONTRACT.md)
- Which baselines a quantity applies to has to be written down. A quantity only some of them have
  is fine; one whose coverage nobody recorded is not. (Rendered plainly; the source phrases it
  "coverage is declared, not discovered".)
  → [`docs/COMPARABILITY_CONTRACT.md`](docs/COMPARABILITY_CONTRACT.md)
- A caveat first noticed while reading results is a defect in this contract, not a footnote on
  the result. (Owner, 2026-08-18: noticing one while the contract is still being built is
  acceptable.)
  → [`docs/COMPARABILITY_CONTRACT.md`](docs/COMPARABILITY_CONTRACT.md)
- Every checker needs a test that deliberately breaks what it claims to check. If you cannot
  construct an input that makes it red, it is decoration. A "nothing was checked" result is a
  failure, not a pass. (Written 2026-08-18, not a long-standing rule — weigh it accordingly.)
  → [`../../docs/rl-experiment-runbook.md`](../../docs/rl-experiment-runbook.md) §7b
