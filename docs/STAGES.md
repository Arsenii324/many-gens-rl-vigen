# Stages — a virtual view

**What this is.** A projection of the project onto stages a person can hold in their head, for the
question *"where is this, and what is left?"* The real objects are register entries, commits,
patches and tests; this file only names groupings over them, the way a virtual address space names
groupings over pages it does not own.

**Three things it is not**, stated because each is a way this file could be misread:

- **Not an instruction to the builder.** The rules for how work is done live in
  [`porting-directive.md`](../../../docs/porting-directive.md),
  [`SYSTEM.md`](SYSTEM.md) and
  [`rl-experiment-runbook.md`](../../../docs/rl-experiment-runbook.md). Nothing here overrides or
  supplements them, and a stage boundary is never a reason to do or not do something.
- **Not error containment.** Stages do not bound where a mistake can reach. [C45](CONSTRUCTION.md#c45)
  is the demonstration: one unvaried axis reached [C17](CONSTRUCTION.md#c17),
  [C19](CONSTRUCTION.md#c19), [C35](CONSTRUCTION.md#c35) and [C42](CONSTRUCTION.md#c42)
  simultaneously, across four stages. A gate at a boundary would not have held it, because from a
  false premise the downstream statements are not independently checkable.
- **Not a partition.** Entries sit in more than one stage where they genuinely do. The patch
  registry P1–P13 is the clearest case: most of it was forced by *launch viability* and all of it
  is *construction*, so it appears in both and is double-counted on purpose.

**Derived, not asserted.** Every stage below names register entries that actually exist;
`tests/test_stages_map.py` fails if a stage cites nothing, or cites an entry the register does not
have. If the two disagree, the register is right.

---

## The stages

**1 · Acquire & pin.** Every candidate cloned at a pinned commit, so `diff`-from-pristine *is* the
exhaustive change statement. *Entries:* [C26](CONSTRUCTION.md#c26).

**2 · Select.** One implementation per algorithm, each choice with a reason and a named runner-up.
*Entries:* [C12](CONSTRUCTION.md#c12), [C24](CONSTRUCTION.md#c24).

**3 · Launch viability.** Do the steps actually execute on this hardware and software — a liveness
check, not a measurement, and deliberately cheap. *Entries:* [C25](CONSTRUCTION.md#c25),
[C34](CONSTRUCTION.md#c34), [C39](CONSTRUCTION.md#c39), [C40](CONSTRUCTION.md#c40),
[C44](CONSTRUCTION.md#c44).

**4 · Read the territory.** What the twelve actually *are* and actually *emit* — the convention
surface and the emission surface. Read-only in intent, though see the note on stop points below.
*Entries:* [C1](CONSTRUCTION.md#c1)–[C15](CONSTRUCTION.md#c15) for conventions,
[C13](CONSTRUCTION.md#c13), [C28](CONSTRUCTION.md#c28), [C33](CONSTRUCTION.md#c33) for emissions.

**5 · Settle the output contract.** What is reported, on what axes, and a run that can be *shown*
to have honoured it rather than declared it. *Entries:* [C23](CONSTRUCTION.md#c23),
[C27](CONSTRUCTION.md#c27), [C29](CONSTRUCTION.md#c29), [C30](CONSTRUCTION.md#c30),
[C43](CONSTRUCTION.md#c43), [C45](CONSTRUCTION.md#c45).

**6 · Anchor & scale.** What chance scores, what is achievable, what two identical runs differ by,
and whether we can land on a published cell at all. *Entries:* [C17](CONSTRUCTION.md#c17),
[C18](CONSTRUCTION.md#c18), [C19](CONSTRUCTION.md#c19), [C21](CONSTRUCTION.md#c21),
[C31](CONSTRUCTION.md#c31), [C32](CONSTRUCTION.md#c32), [C36](CONSTRUCTION.md#c36),
[C37](CONSTRUCTION.md#c37), [C38](CONSTRUCTION.md#c38), [C41](CONSTRUCTION.md#c41),
[C46](CONSTRUCTION.md#c46), [C48](CONSTRUCTION.md#c48).

**7 · Constructions.** The edits required to make baselines meet the contract, each with class,
reason, effect and commit. *Entries:* P1–P13 (`setup/apply_patches.py`),
[C16](CONSTRUCTION.md#c16), and the pending [C43](CONSTRUCTION.md#c43)/[C45](CONSTRUCTION.md#c45)
patch.

**8 · Production.** The table, at the settled budget, with seeds. *Entries:*
[C35](CONSTRUCTION.md#c35), [C42](CONSTRUCTION.md#c42), [C47](CONSTRUCTION.md#c47) — all of them
probes rather than the table, which is the point of the status below.

**9 · Defense.** The write-up whose methods section *is* the ledger from 1–8.

---

## Where this sits, 2026-08-20

| Stage | State |
|---|---|
| 1 Acquire & pin | **done** — 21 patches present, 0 unresolved, tree matches pinned commits |
| 2 Select | **done** — twelve, none an alias |
| 3 Launch viability | **mostly** — the Linux branch of every launcher has still never run ([C40](CONSTRUCTION.md#c40)) |
| 4 Read the territory | **largely done** — convention surface mapped ([C1](CONSTRUCTION.md#c1)–[C15](CONSTRUCTION.md#c15)); emission inventory built 2026-08-17 ([`PART2-METRIC-INVENTORY.md`](PART2-METRIC-INVENTORY.md)). Separate from it, [C28](CONSTRUCTION.md#c28) is a READY *build* task — wiring family-tier metrics into nine logging paths — not a survey |
| 5 Output contract | **partial, and the enforced part grew** — `Protocol` exists and hashes, and was false-certifying until 2026-08-18. The comparability seam is now **checked in five places** rather than described: y-axis (`test_success_convention.py`), x-axis (`test_x_axis_invariant.py`), horizon and truncation (`test_truncation_seam.py`), scene (`test_scene_coverage_contract.py`), regime (`test_eval_regime_invariant.py`). What is still open is decisions, not enforcement: [C43](CONSTRUCTION.md#c43), [C45](CONSTRUCTION.md#c45) — [C33](CONSTRUCTION.md#c33) was decided 2026-08-18 (return is the reported endpoint, success rate stays emitted) |
| 6 Anchor & scale | **three of four** — floor, ceiling and resolution exist; **no published cell has been reproduced** ([C48](CONSTRUCTION.md#c48)). Resolution gained a second half 2026-08-19: seeds were audited per clone ([C20](CONSTRUCTION.md#c20)) — eleven of twelve are seed-controlled, `ppg` has no seed knob at all and so cannot contribute a 5-seed row |
| 7 Constructions | **in progress** — P14 applied to the five RL-ViGen-native baselines; the other seven are seven clone deviations and a decision, not a slot ([C43](CONSTRUCTION.md#c43)/[C45](CONSTRUCTION.md#c45) reopened for that reason) |
| 8 Production | **not started, and now blocked on a prerequisite that was assumed** — see below |
| 9 Defense | **not started** |

> **Superseded 2026-08-25 — read the paragraph below as history, not as status.** It says the
> project has no usable checkpoint. It now has **five**, and four verified cells, all re-derived
> deterministically after [C69](CONSTRUCTION.md#c69)/[C70](CONSTRUCTION.md#c70). What blocks stage 8
> today is different and is stated under "What blocks stage 8 now", further down.

**What blocked stage 8 as of 2026-08-20.** Not tooling and not porting. The project has produced
exactly two full-length training runs and **neither yields a usable checkpoint**: the 08-18 run's
training distribution does not match what its config declares ([C54](CONSTRUCTION.md#c54)), and
the 08-20 replication solved Door at 20k frames and then collapsed to a constant sub-random
policy for the remaining 70k ([C57](CONSTRUCTION.md#c57)). Production assumed "a run produces a
checkpoint" as background; that assumption is what failed, and it failed for two unrelated
reasons at once. The cheapest thing that moves this is [C57](CONSTRUCTION.md#c57)'s option 1 —
three to five seeds at 40k frames — which converts one collapse into a rate and needs no
decision to start.

**What blocks stage 8 now, 2026-08-25 — and which of it is a decision rather than work.**

The 08-20 blocker is gone: five checkpoints exist, four cells are verified, and the evaluator is
reproducible. What remains splits cleanly into *compute* and *decisions*, and the decisions gate
the compute rather than the other way round.

| what is missing | why | gated by |
|---|---|---|
| cells for `sgqn` | ~11h locally ([C60](CONSTRUCTION.md#c60)); an ordinary run on the free V100 | **[C64](CONSTRUCTION.md#c64) first** — running `sgqn` before its `aux_lr` is settled spends 11h on a configuration that may be discarded |
| cells for `curl` | cannot run under the MPS shim, needs CUDA ([C52](CONSTRUCTION.md#c52)) | **hardware only — no decision pending.** A free V100 is available (2026-08-25, not DataSphere, so outside its cost ceiling); see [`compute.md`](compute.md). DataSphere runs both regimes, Kaggle only `train` |
| more than one seed per baseline | [C41](CONSTRUCTION.md#c41) puts run-to-run variation near 49%; every current cell is **n=1** | a decision on how many seeds the claim needs, and the compute to buy them |
| anything on **Lift** | never run; **every finding in this project is Door-only** | a scope decision: two tasks, or one task stated as one |
| the other seven baselines | the retention endpoint does not read their checkpoints ([C72](CONSTRUCTION.md#c72)) | **deferred by the owner** — not a gap to fill, a design question to take later |

**One decision is missing from the table above because it is not about a missing run — it is about
what the existing numbers mean.** The evaluation protocol was **constructed, not decided**
([C43](CONSTRUCTION.md#c43)/[C45](CONSTRUCTION.md#c45)): 20 episodes × 10 scenes × 2 regimes, pooled,
with scenes then *dropped* by the floor and 25%-success guards, and the surviving subset reported.
RL-ViGen averages ten scenes unconditionally. Both are defensible; they are different quantities;
`regime_retention_report.py` prints the divergence in its own output and nobody has chosen. This is
**upstream of C64 and C68** — those decide what a run should be, this decides what its number is —
and it is the owner's, alongside [C72](CONSTRUCTION.md#c72).

**The ordering matters and is the reason this is written as a table.** [C64](CONSTRUCTION.md#c64)
and [C68](CONSTRUCTION.md#c68) are cheap to decide and expensive to get wrong afterwards: C64
decides what an `sgqn` run should be, and C68 says a budget that is not a multiple of 50 000
silently discards its tail. Both are *upstream of every remaining run*. Deciding them costs
minutes; discovering them after four training runs costs the runs.

**What is genuinely finished** and needs nothing further: the instrument layer. The floor is
measured, the denominator guards refuse a chance-level or unsolved cell, the contamination screen
catches a checkpoint whose provenance is wrong, the evaluator is bit-reproducible across
processes, and each of those has a test that fails when the property breaks. That was not true a
week ago and it is the part that had to be right before any number meant anything.

**The consolidated result, 2026-08-24 — four verified cells, one number.** Stated as a finding
rather than as four experiments, because that is what it is:

| cell | pooled train-regime return | successes | re-derived successes | yields retention? |
|---|---|---|---|---|
| `drqv2` seed 6 | 115.31 | **59/200** | **61/200** | **yes — 0.003** |
| `drqv2` seed 7 | 85.01 | 0/200 | 0/200 | no |
| `svea` seed 1 | 97.50 | 6/200 (never >1/20 on a scene) | **12/200** | no |
| `drq` seed 1 | 79.29 | **0/200** | **0/200** | no |

The fourth column is the same checkpoints re-run after [C69](CONSTRUCTION.md#c69)/[C70](CONSTRUCTION.md#c70)
made the evaluator reproducible (`results/regime-retention-c69/`). **The finding is unchanged and
the verdicts are identical**, which is the point of showing both. Note `svea` doubled, 6 → 12: still
far below the 25% denominator floor and still refused, but it is the baseline whose per-scene
plateau nearly produced a 0.947 retention headline ([C55](CONSTRUCTION.md#c55)), so the size of the
swing is worth seeing. Neither column is "the right one" — they are two placement draws, and only
the second reproduces.

> **Reading a grid file: three naming traps, each of which yields a confidently wrong answer.**
> Verified 2026-08-24 against the runs' own `.hydra/overrides.yaml`.
>
> 1. **The `seed` field inside a grid JSON is the *evaluation* seed, not the training seed.** It
>    reads `0` in all seven grids. The training seed appears only in the run directory name —
>    `cell55k` is seed **6**, `cell_drqv2_s7` is **7**, `drq_s1`/`svea_s1` are **1**. Taking `seed`
>    from the JSON would report seven runs at one seed, which is false for every one of them.
> 2. **`cell55k` is a 50k checkpoint.** The run was launched with `num_train_frames=55000`; the
>    snapshot is at `trained_step=50000`. The name carries the budget, the file carries the step.
> 3. **The archived 2026-08-18 run passed no `seed=` override**, so it silently took
>    `cfgs/config.yaml`'s default, **seed 1** — the same seed as `drq_s1` and `svea_s1`. That
>    resemblance is an artifact of a default, not a controlled comparison: different algorithms,
>    different dates, and that run carries [C54](CONSTRUCTION.md#c54)'s provenance defect.
>
> Algorithm identity is likewise not in the grid file — it comes from the config the run composed:
> `config.yaml` → `algos.drqv2.DrQV2Agent`, `drq_config.yaml` → `DrQAgent`, `svea_config.yaml` →
> `SVEAAgent`. **All seven grids are three algorithms, five of them DrQ-v2.**

**Three of twelve baselines have a retention grid; nine have none.** `drqv2`, `drq` and `svea` — that
is the whole set. Verified 2026-08-24 by listing `results/regime-retention/*.json`, after three
separate write-ups gave three different numbers (seven, eight, nine).

> **The reason they disagreed is a naming trap worth knowing about.** `results/cell-*/` directories
> exist for `ctrl`, `curl`, `ppg`, `rad`, `sgqn` and others, and **none of them is a cell.** They
> contain only `watcher.log` and `frames/*.npy` — training-distribution witness captures from
> `watch_training_frames.py`. Not one holds an `eval.csv`, a snapshot, or a `train.csv`. Counting
> directories named `cell-*` therefore over-counts cells by six. The retention grids live in
> `results/regime-retention/`, and that is the only place to count them.

The table is the **denominator** only. The matching `eval-easy` numerators have since been measured
for all four and are archived beside them (`drq` seed 1: 22.18 pooled, 1/200; `drqv2` 100k:
131.05, 63/200) — they are recorded so nobody spends another grid re-deriving them, and they
change nothing above, because a numerator over a denominator that never solved the task is
refused before it is divided.

**At 50k frames on Door, three of four runs reach a shaping plateau without ever opening the
door.** Returns of 79–115 against a random floor of 1.82 look like learning and are not: robosuite
pays up to 0.25/step for gripper proximity and 0.25/step for door rotation, against a sparse +1.0
for the actual success. A policy that optimises the shaping and never solves the task sits exactly
there, and it does so *stably*, which is why its return curve looks healthy.

Three consequences, none of which is another experiment:

1. **Return is not evidence of learning on this task.** Only the success count separates the two,
   and it costs an evaluation grid to obtain. Every claim about "how well baseline X learned"
   must cite successes, not return.
2. **Retention is undefined for most cells, and that is a property of the budget, not a defect.**
   A ratio needs a denominator that represents competence ([C55](CONSTRUCTION.md#c55)); three of
   these four have none.
3. **The comparison table cannot be built at 50k.** Not "is incomplete" — cannot. Yet
   [C57](CONSTRUCTION.md#c57) has both 120k runs diverging to NaN, so the budget cannot simply be
   raised without first establishing the divergence rate. **That pair is the project's binding
   constraint**, and it is now measured on both sides rather than assumed on either.

**Inventory, updated 2026-08-24.** `scripts/check_checkpoint_finite.py --all` now reports **6
finite snapshots and 1 dead**, against 3 and 1 four days earlier. The three new ones are cells
built with [`scripts/run_cell.sh`](../scripts/run_cell.sh) and all carry verified provenance:
`drqv2` seed 6 (52 frames, all `train|0`), `drqv2` seed 7 (51), `svea` seed 1 (60).

**But only one of the three yields a retention number**, and that is the finding to carry
forward. A denominator has to represent competence, and at 50k frames on Door only `drqv2` seed 6
learned the task (59/200 successes); `drqv2` seed 7 got 0/200 and `svea` seed 1 got 6/200 —
never more than 1/20 on any scene — so both report no retention at all
([C55](CONSTRUCTION.md#c55)).

That is a squeeze, not a setback to route around: **below ~50k frames most baselines have no
skill to retain, and both runs that reached 120k diverged to NaN** ([C57](CONSTRUCTION.md#c57)).
The window that yields a *measurable* cell is narrower than the window that yields a *finite*
one, and nothing had priced that before.

**And the training curve does not tell you which you have.** Both 55k `drqv2` cells look healthy
in training — seed 6 ends at 425.2 (sd 71.6), seed 7 at 169.8 (sd 14.3), neither flat, neither
near the floor. Evaluated, seed 6 has **59/200** successes and yields a retention number; seed 7
has **0/200** and yields none. Seed 7's evaluated return (163.17 on train scene 0) matches its
training curve closely, so nothing is inconsistent: it simply collects ~165 of shaping reward
without ever opening the door.

The planning consequence is concrete. **A run cannot be triaged from its return curve** — the
only thing that separates a usable cell from an unusable one is the success count, and that
requires the evaluation grid, which costs ~45 minutes per checkpoint on top of the run. Budget
per cell is therefore run + grid, not run; and since one of two apparently-fine `drqv2` seeds
produced no cell, seeds are needed to *obtain* a cell, not merely to put an error bar on one.

**Inventory, 2026-08-20 — what seventeen runs have produced.** Counted rather than remembered,
by walking `exp_local` for runs whose `.hydra/hydra.yaml` names a baseline:

| | |
|---|---|
| runs recorded | **17**, all `drqv2`, all Door |
| snapshots on disk | **4** |
| snapshots that are finite | **3** — all from the one 08-18 run (50k, 100k, final) |
| baselines with any checkpoint | **1 of 12** |
| checkpoints with verified training provenance | **0** ([C54](CONSTRUCTION.md#c54)) |

Three separate reasons runs leave nothing, and each is worth knowing before planning the next
batch. A 200k-frame run reached **439.19** and saved nothing, because `save_snapshot` was not set.
Three healthy 40k runs saved nothing, because `train.py:309` only writes at multiples of 50k
steps. And the two runs that reached 120k both diverged to NaN
([C57](CONSTRUCTION.md#c57)) — though the 08-18 one diverged *after* its last save, which is why
its three checkpoints survive.

So the only interval that has ever yielded a finite checkpoint is **50k–100k frames**, and
`save_snapshot=True` has to be passed explicitly. That is the planning constraint for all twelve,
and it is narrower than any document previously said.

**Scope caveat, recorded because nothing else states it.** `rlgen/protocol.py:38` declares
`TASKS = ("Door", "Lift")`, and **no baseline has ever trained on Lift** — 14 Door run
directories, zero Lift. So every empirical claim this project holds is a Door claim:
[C52](CONSTRUCTION.md#c52)'s determinism split, [C54](CONSTRUCTION.md#c54),
[C56](CONSTRUCTION.md#c56)'s env interference, [C57](CONSTRUCTION.md#c57)'s collapse, and the
retention numbers. Lift appears in the register only as a random-policy floor
([C17](CONSTRUCTION.md#c17): 6.562, 0/25) and as configuration facts. This is not a defect — half
a task set is a reasonable place to be mid-project — but the project's own null says coverage is
declared rather than discovered, and the *task* coverage of every finding was not declared
anywhere until this line.

---

## The part that cannot be planned

Stages 5 onward cannot be specified in advance, and this is structural rather than a gap in
foresight. Whether a metric set can hold two entries or two hundred is a fact about the twelve
implementations, not about the plan; whether a same-named quantity is the same quantity is
decidable only by reading both interiors. A plan that named those answers would be asserting over
the territory.

What *can* be fixed in advance is not the content but the admissibility of whatever ends up there,
and those rules already exist and are not restated here — they live in
[`porting-directive.md`](../../../docs/porting-directive.md) (§1 hermetic, duplication over wrong
abstraction; §5 step N dictates step N+1) and in
[`COMPARABILITY_CONTRACT.md`](COMPARABILITY_CONTRACT.md)'s stance.

One consequence worth stating here because it cuts across stage 4 and stage 7: **deciding a
quantity's exhaustive contract is construction-grade judgement**, so an emission inventory is not
a neutral survey that precedes contract-building. It is where contract decisions begin, and its
output belongs in the ledger — which is what
[`PART2-METRIC-INVENTORY.md`](PART2-METRIC-INVENTORY.md) already does, recording collisions such
as three action-distribution families rather than reconciling them.

## Breadth and depth

Neither mode is the rule. Some questions are answerable only across baselines — a same-named
quantity colliding across two implementations is invisible from inside either one, which is why
[C28](CONSTRUCTION.md#c28) is inherently twelve-wide. Some are answerable only by taking one run
to depth — [C45](CONSTRUCTION.md#c45) → [C47](CONSTRUCTION.md#c47) needed a trained checkpoint,
ten scenes and a within-scene control before the question had a number. Which a given question
needs is a judgement about that question.
