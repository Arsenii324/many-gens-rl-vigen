# Construction register — every difference that needs a decision, and what happened to it

> **What belongs here.** One rule: **if a number could mean something different depending on how
> this is resolved, and it is not resolved yet, it goes here.** Five shapes in practice — whether
> to equalise an inherited difference (and thereby deviate), whether to declare or fix an
> undeclared asymmetry, whether a false certification is annotated or re-valued, whether a design
> gap must close before results, and whether something of ours is justified or reconsidered.
>
> **What does not.** A construction we made — that is
> [`INTEGRATION-DELTA.md`](INTEGRATION-DELTA.md), *"everything in this code that is ours, not the
> original authors'"*, together with `scripts/deviations.py` and the `PRISTINE:` commits. **That
> is the place that names all constructions we write, and this file does not replace it.** A
> finished finding with nothing pending, or a downstream product idea, also does not belong here.
> Some items are legitimately in both files — an edit *and* a decision — recorded in each for a
> different reason.
>
> **Two kinds of item live here, and their completeness guarantees are not the same.** The
> distinction matters, because treating them alike either overclaims about one or underclaims
> about the other.
>
> - **CONSTRUCTED** — decisions about things this project made, chose or changed. The
>   underlying set *is* exhaustively known, and not as an aspiration: every clone carries a
>   `PRISTINE:` first commit, so `git diff` against it **is** the complete statement of what
>   we did, and `deviations.py` regenerates it. Completeness is a property of that method,
>   which this register inherits rather than provides. A missing one is a checkable
>   bookkeeping failure, not an unknown.
> - **DISCOVERED** — differences found by checking an assumption that two things were the same,
>   and naming where they were not. These are found by inspection, so **no completeness claim is
>   available** and new ones are expected. Several here were found by a blind audit that read
>   code nobody had re-read; that is what finding them looks like, and it does not terminate.
>
> So: exhaustive over what we built, open-ended over what we found.

**This is a live document, not a snapshot.** Items enter as `OPEN`, acquire a decision, an
attempt, and an *effect* — including when the attempt failed or the effect was nothing. The
effect is the part other documents keep losing.

## Why this file exists

The items below were spread across four documents in three formats with no shared status:
`AUDIT-2026-08-17.md` §6 (ten inherited differences, as a table), `independent-audit-2026-08-17.md`
(D1–D7, mixing fixed and open), `PART2-METRIC-INVENTORY.md` (Findings 6–7 and the observation
splits, overlapping §6 in different words), and `DECISION_LOG.md` (three narrative entries from
2026-08-14, all from the **superseded** `rlgen` port era).

That scattering is itself a catalogued failure — `docs/REGISTER.md` category 42, *"Decision held
only in working state, lost,"* recorded as `(c) INTEGRATION-DELTA.md appends, but nothing
enforces it.* This file is the enforcement. **Where it disagrees with the four documents above,
this file wins**; they keep their prose and lose their status columns.

`docs/DECISION_LOG.md` is not superseded but is *historical*: it records reasoning from the port
era, which is no longer the design. Read it for why, not for what is true now.

> **Which of these actually threaten the research claim is a separate question**, answered in
> [`RESEARCH-FRAME.md`](RESEARCH-FRAME.md). Short version: every `INHERITED` item below is a
> **confound** — perfectly collinear with method identity — so none of them can be separated
> from the algorithm by this design. That is why C1 and C2 should be decided by deciding the
> *claim* first, not on their own merits.

## How to read an entry

- **ID** — `C<n>`, stable and citable. Deliberately a separate space from patches (`P1`–`P13`)
  and from the blind audit's findings (`D1`–`D7`); cross-references are given where they exist.
- **Class** — the *smell*, which is the useful axis. See the taxonomy below.
- **Status** — one of `OPEN` · `READY` · `BLOCKED` · `MONITORED` · `RESOLVED`.
  - `OPEN` — needs a **judgement between alternatives**. Must carry **Options**.
  - `READY` — no judgement needed, only a slot. Kept separate from `OPEN` on purpose: lumping
    "someone must decide this" together with "someone must find an afternoon" is how the first
    kind quietly waits on the second.
  - `BLOCKED` — decided in principle, waiting on compute, access, or a prior item.
  - `MONITORED` — deliberately not acted on, and pinned so it cannot change unnoticed.
  - `RESOLVED` — decided, carried out, **effect recorded**. Must carry **Decision** and **Effect**.
- **Blast radius** — which baselines, and what the item changes about their numbers.
- **Evidence** — a measurement where one exists, `none` where it does not. `none` is a finding.
- **Pinned by** — the test that stops it rotting, or `unpinned`.

### The classes, because the class predicts the fix

*Working, not settled — like the rest of this system. The taxonomy was written in one pass and
has not yet been stress-tested against an item it did not already have to describe.*

| Class | Meaning | Fix shape |
|---|---|---|
| **INHERITED** | A real difference between the references. Nobody introduced it. | **A property of the domain** — note it accurately. Not a defect, and not a removal candidate; see the note below. |
| **OURS** | A choice this project made where no reference dictated one. | Justify against a reference or reconsider. Highest scrutiny — a bug here is ours. |
| **UNDECLARED** | A real asymmetry that no document states. | Cheap: state it. Dangerous while it persists. |
| **FALSE-CERTIFICATION** | A field or comment asserts a property the code lacks. | Annotate or re-value. Worst kind, because it reads as verified. |
| **DESIGN-GAP** | The measurement design cannot answer the question yet. | Blocks results, not code. |

> **`INHERITED` does not mean "wrong", and nothing here proposes removing these.** That the
> twelve methods are configured differently is what "as shipped" means; it is a *property of the
> subject*, not damage to be repaired. Whether a given one is a nuisance or the thing being
> studied depends on a question that has not been asked yet.
>
> **These differences are a property of the domain, not a backlog.** Twelve independently
> developed methods are configured differently; that is what the subject *is*, and the hermetic
> setups preserve it rather than suffer from it. **This project holds no standing intent to
> eliminate, merge or normalise them**, and nothing here is a deferred plan to do so — the
> framing "not decided yet" would already presuppose that eliminating is the pending question,
> and it is not.
>
> The register's job is to note them accurately, so that if some future question ever makes one
> of them relevant, it is on record rather than rediscovered. Whether that ever happens is
> N→N+1: not knowable from here, and not to be read as imminent.

---

## Summary

| ID | Item | Class | Status | Needs |
|---|---|---|---|---|
| [C1](#c1) | Time-limit handling splits 3 / 9 | INHERITED + FALSE-CERT | **OPEN** | your decision |
| [C2](#c2) | Frame stack: 3 frames ×8, 1 frame ×4 | INHERITED | **OPEN** | your decision |
| [C3](#c3) | Historical `ibac_sni` 64×64 trunk mismatch — repaired by the source-backed Impala default | OURS | MONITORED | — |
| [C4](#c4) | float64 vs float32 alpha, CUDA only | UNDECLARED | **OPEN** | your decision |
| [C5](#c5) | Render resolution 100→84 / 84 / 64 | INHERITED | MONITORED | — |
| [C6](#c6) | Three action-distribution families | INHERITED | MONITORED | — |
| [C7](#c7) | Discount 0.99 ×9 vs 0.999 ×3 | INHERITED | MONITORED | — |
| [C8](#c8) | Learning rate spans 10× | INHERITED | MONITORED | — |
| [C9](#c9) | Reward normalisation in 3 of 12 | INHERITED | MONITORED | — |
| [C10](#c10) | Input range [0,1] ×7 vs [−0.5,+0.5] ×5 | INHERITED | MONITORED | — |
| [C11](#c11) | Instance diversity: Procgen levels vs fixed scene | INHERITED | MONITORED | — |
| [C12](#c12) | `ppg` evaluation loop is authored by us | OURS | MONITORED | — |
| [C13](#c13) | `action_repeat` declared but unread in two seams | UNDECLARED | MONITORED | — |
| [C14](#c14) | `ctrl` invents `_max_episode_steps = 10_000` | UNDECLARED | MONITORED | — |
| [C15](#c15) | `ppg` `vec_monitor2` comment contradicts its code | FALSE-CERT | MONITORED | — |
| [C16](#c16) | `ctrl` ships the authors' plaintext W&B key — **literal blanked 2026-09-03 (option 1 taken), because the entry's own "if ever uploaded" condition came true: the payload carries `runnable/ctrl/` to DataSphere.** Residual only: whether to rebuild the six payload archives that still contain it, and whether a pre-upload grep should exist as a standing gate | OURS (inherited risk) | **OPEN** | your decision |
| [C17](#c17) | Random-policy floor, and whether the signal fires at all | DESIGN-GAP | RESOLVED | — |
| [C18](#c18) | Single seed, 10 episodes → CI `[0, 0.278]` | DESIGN-GAP | READY | a slot |
| [C19](#c19) | Train/eval regime separation, measured | DESIGN-GAP | RESOLVED | — |
| [C20](#c20) | Per-clone determinism, now tested | DESIGN-GAP | RESOLVED | — |
| [C21](#c21) | No CUDA run exists | DESIGN-GAP | BLOCKED | a free run slot |
| [C22](#c22) | Mutation harness: inoperable, then pointed at the metrics | DESIGN-GAP | RESOLVED | — |
| [C23](#c23) | `Protocol.frame_stack = 3` false for 4 of 12 | FALSE-CERT | RESOLVED | — |
| [C24](#c24) | `ibac_sni` held-out number was a different quantity | OURS | RESOLVED | — |
| [C25](#c25) | Two skips that read as passes | OURS | RESOLVED | — |
| [C26](#c26) | Patch range said P11/P12 against a P13 registry | UNDECLARED | RESOLVED | — |
| [C27](#c27) | Eval regimes are not a monotone difficulty ladder | INHERITED | MONITORED | — |
| [C28](#c28) | Full observability: what a run actually emits | DESIGN-GAP | READY | a slot |
| [C29](#c29) | Protocol hash omits the dependency versions it certifies over | FALSE-CERT | **OPEN** | your decision |
| [C30](#c30) | Contract enforced against the superseded port, not the clones | DESIGN-GAP | **OPEN** | your decision |
| [C31](#c31) | The ceiling, from the benchmark's own published results | DESIGN-GAP | RESOLVED | — |
| [C32](#c32) | Three of the twelve are published as not learning these tasks | INHERITED | MONITORED | — |
| [C33](#c33) | Return is the reported endpoint; success rate stays emitted | DESIGN-GAP | RESOLVED | — |
| [C34](#c34) | Local training: infeasible for a sweep, sufficient for a question | DESIGN-GAP | MONITORED | — |
| [C35](#c35) | First learning signal, and what it does not establish | DESIGN-GAP | MONITORED | — |
| [C36](#c36) | Per-baseline throughput varies 8.3x, so frames is not a budget | INHERITED | MONITORED | — |
| [C37](#c37) | `drqv2` learns where they publish floor — comparison never like-for-like | OURS | **OPEN** | — |
| [C38](#c38) | An untrained network is not a uniform-random policy | DESIGN-GAP | MONITORED | — |
| [C39](#c39) | MPS shim: patched surface now covered per symbol | OURS | RESOLVED | — |
| [C40](#c40) | Every launcher's Linux branch has never been executed | DESIGN-GAP | MONITORED | — |
| [C41](#c41) | What the shim changes numerically, measured | DESIGN-GAP | RESOLVED | — |
| [C42](#c42) | The success signal fires: SR 0.6 on the held-out regime | DESIGN-GAP | MONITORED | — |
| [C43](#c43) | Retention not computable: we only ever evaluate one regime | DESIGN-GAP | **OPEN** | your decision |
| [C44](#c44) | Places365 loader spawns 8 workers regardless of the macOS guard | UNDECLARED | MONITORED | — |
| [C45](#c45) | We evaluate ONE scene; protocol and benchmark both say ten | FALSE-CERT | **OPEN** | your decision |
| [C46](#c46) | The scene axis is real and nearly as large as the difficulty axis | DESIGN-GAP | RESOLVED | — |
| [C47](#c47) | Held-out scenes retain ~25% of training-scene return, at 50k and 100k | DESIGN-GAP | RESOLVED | — |
| [C48](#c48) | Nothing has ever reproduced a published RL-ViGen number | DESIGN-GAP | **OPEN** | your decision |
| [C49](#c49) | The env `seed` argument is inert in train mode | INHERITED | RESOLVED | — |
| [C50](#c50) | IDAAC's target lacks the variation its objective assumes | OURS | MONITORED | — |
| [C51](#c51) | Training happens on one visual instance, with zero randomisation | INHERITED | MONITORED | — |
| [C52](#c52) | Four baselines do not reproduce at a fixed seed | DESIGN-GAP | RESOLVED | — |
| [C53](#c53) | Brief required identical eval CODE; R3 relaxed to metric comparability, dissolving the conflict | DESIGN-GAP | **RESOLVED** | — |
| [C54](#c54) | ~~Our only checkpoints were not trained on the distribution the config declares~~ — **claim WITHDRAWN 2026-09-03.** The run's own in-container `eval.csv` reads `train_regime_reward` **476.33** at SR **1.0** for the same checkpoint, regime, scene and frame where this entry's laptop re-measurement read **1.30**: a 366× gap in [C95](#c95)'s direction. The checkpoints were trained on the declared distribution; it was not measurable on this machine. Residual: whether [C46](#c46)/[C47](#c47) should be recomputed on the container | FALSE-CERTIFICATION | **OPEN** | your decision |
| [C55](#c55) | The chance floor was measured, recorded, and then not consulted | DESIGN-GAP | RESOLVED | — |
| [C56](#c56) | Two robosuite envs in one process do not render independently | INHERITED | MONITORED | — |
| [C57](#c57) | Training diverged to NaN and the run continued for 70k frames | DESIGN-GAP | **OPEN** | your decision |
| [C58](#c58) | Six of twelve leave no record of what they trained on | DESIGN-GAP | **OPEN** | your decision |
| [C59](#c59) | The comparison's collector could not read the comparison's runs | DESIGN-GAP | RESOLVED | — |
| [C60](#c60) | Checkpoint cadences exceed surviving budgets; two baselines never save | INHERITED | **OPEN** | your decision |
| [C61](#c61) | `ibac_sni` categorical-era entropy inflates its Gaussian | INHERITED | MONITORED | — |
| [C62](#c62) | Door's shaping ceiling is 250; it re-reads every return we hold | INHERITED | RESOLVED | — |
| [C63](#c63) | C54's −0.887 distance↔return correlation is a signature of an under-trained policy | OURS | RESOLVED | `918c2d84` |
| [C64](#c64) | FAITHFULNESS's `sgqn` "ours" column describes the retired port; the clone runs 1e-4/0.93 | FALSE-CERTIFICATION | OPEN | — |
| [C65](#c65) | Retention above 1 is a contamination alarm; it splits all 8 grids, with a random-policy control at 1.02 | OURS | RESOLVED | `7de97354` |
| [C66](#c66) | The `nstep` open item survived three re-triages because it lost its subject, not because it was hard | OURS | RESOLVED | `87d8eabb` |
| [C67](#c67) | `snapshot.pt` == `snapshot_100k_frames.pt`: a free replicate bounding evaluation noise (47% on a success count) | OURS | RESOLVED | `a7f7f6fe` |
| [C68](#c68) | On the robosuite path a snapshot is saved only every 50k steps and never at the end of a run | INHERITED | OPEN | — |
| [C69](#c69) | Our evaluator never seeded the RNG placing the door; ~1.6 cm of uncontrolled movement per process | OURS | RESOLVED | `b743917f` |
| [C70](#c70) | Seeding was not sufficient: torch kernel choice flips episodes; fixed to sub-percent, not to zero | OURS | RESOLVED | `8cf224cc` |
| [C71](#c71) | Dead knobs: six configured values that never reach the robosuite path; checker built for the 3 that share a shape | DESIGN-GAP | OPEN | — |
| [C72](#c72) | The retention endpoint only reads native checkpoints — five of twelve; this, not C60, is why nine have no cell | DESIGN-GAP | OPEN | — |
| [C73](#c73) | 50k is below the threshold: the same run improves 28x by 100k, so cells belong at 100k | OURS | RESOLVED | `ac945ce9` |
| [C74](#c74) | Mechanisms needing distinguishable instances, on a target that is only partly distinguishable — C50 is one member of a class | DESIGN-GAP | OPEN | — |
| [C75](#c75) | Narrowed: a formulation bound to a concrete quantity (C3/C6/C61) — distinguishability is C74, a different class with a different check | DESIGN-GAP | OPEN | — |
| [C76](#c76) | R3's evidence rebuilt on the clone architecture: 11 axes, and the one UNITS split is the evaluation scene set (C72) — ours sweeps ten scenes, all seven others pin scene_id=0 | OURS | MONITORED | — |
| [C77](#c77) | A native run launched at exactly N never saves at N — run_cell.sh asserted the opposite and would have produced zero checkpoints | OURS | RESOLVED | `13c48011` |
| [C78](#c78) | The decision ledger counted an explicitly-open decision as settled; its test used the one phrasing the code handled | OURS | RESOLVED | `4c2d96f3` |
| [C79](#c79) | Divergence has been readable live from train.csv since use_tb went on; nothing read it, and a dead run burned 64 min after dying at minute 6 | OURS | RESOLVED | `9de8ccda` |
| [C80](#c80) | Mutation testing was 100% unusable — the sanity gate failed on three unfaithful-copy causes, and reported them as citation defects | OURS | RESOLVED | `b0089c15` |
| [C81](#c81) | First clean endpoint: regime retention 0.003 at 100k, falling with budget; and the byte-identical random floor proves the regime shift is purely visual | OURS | MONITORED | — |
| [C82](#c82) | Three wrong readings of FAITHFULNESS.md from proxies for reading; its §5 was the current state all along, and the clone move had already discharged §4's divergences | OURS | MONITORED | — |
| [C83](#c83) | First cross-baseline comparison: svea retains 0.428 against drqv2's 0.003 while scoring 1.9x lower where it trained — a return-only table would invert the ranking | OURS | MONITORED | — |
| [C84](#c84) | drq died at frame 5000 on a policy scale of exactly 0, which its own [-10,2] log-std bounds should make unreachable; same seed ran fine on 08-24 | OURS | **OPEN** | your decision |
| [C85](#c85) | Sorted the session's findings by whether a run was needed; three were readable and had no instrument, so one was built with C77 as its positive control | OURS | RESOLVED | `4cce919b` |
| [C86](#c86) | Three baselines at 100k: the ranking INVERTS between trained-scene return and retention — svea last on one, first on both others | OURS | MONITORED | — |
| [C87](#c87) | First same-quantity comparison with RL-ViGen's published table: the ordering reproduces, drq within 16%, and two of their own cells sit near the random floor | OURS | MONITORED | — |
| [C88](#c88) | Scene difficulty is method-dependent: drqv2~drq rank-correlate +0.758, svea with neither — so averaging over scenes is not a neutral marginalisation | OURS | MONITORED | — |
| [C89](#c89) | Under eval-easy the TRAINED scene becomes the worst, 14–53x, in all three arms — so the seven evaluators pinned to scene_id=0 would report the shift's worst case | OURS | MONITORED | — |
| [C90](#c90) | My own test polluted sys.modules and broke 25 others; re-running the file alone passed, which is the wrong check for this failure class | OURS | RESOLVED | — |
| [C91](#c91) | `grep -c "^FAILED"` on pytest output can never match — ANSI colour precedes the word. The check I used to report suite status returns 0 on a red suite | OURS | RESOLVED | — |
| [C92](#c92) | `linalg_qr: MPS kernel failed` in the nd_ln synthetic-backend test — intermittent, passed in isolation under the same live run, cause not established | OURS | MONITORED | — |
| [C93](#c93) | greenmark's tree id is unstable while a run writes into results/, so any green stamp taken during a run is void — and tree_id ignores the CODE_PREFIXES split that the rest of the file uses | OURS | OPEN | — |
| [C94](#c94) | greenmark cannot see the gitignored vendored tree, so an upstream-only edit reports "no pending changes" and skips the suite that holds the only instrument which would catch it; the test pinning this defect checks a string, not the pipeline | OURS | OPEN | — |
| [C95](#c95) | a container-trained checkpoint may not be evaluated on this laptop: the same 60k snapshot reads train 131.5 in the container on BOTH CUDA and CPU and 13.85 here, so the device is exonerated and the **renderer** (`MUJOCO_GL=egl` vs macOS `glfw`) is the cause; the container figure also reproduces the run's own logged 135.71, validating `eval_grid.py`. Mechanism settled; recomputation of locally-produced numbers outstanding | OURS | OPEN | — |
| [C96](#c96) | the shared-evaluator ledger's one global code revision was both too broad and too narrow: a training-only patch invalidated every family, while a change to a family evaluator's local runtime could leave its revision unchanged; the static family payload closure/config binding and row-level canonical scope/measurement revisions are now locally implemented and tested, but 0/7 families are remotely validated on the current closure | OURS + FALSE-CERTIFICATION | READY | a revalidation slot |

**24 OPEN · 3 READY · 1 BLOCKED · 34 MONITORED · 34 RESOLVED · 96 total.**

**14 items need a judgement that is yours** — [C1](#c1), [C2](#c2), [C4](#c4), [C16](#c16), [C29](#c29), [C30](#c30), [C43](#c43), [C45](#c45), [C48](#c48), [C54](#c54), [C57](#c57), [C58](#c58), [C60](#c60), [C84](#c84). The `READY` items need only a slot,
and C21 is waiting on compute access. *(This line read "7 items — C1, C2, C3, C4, C16, C29, C30"
until 2026-08-18 while the table marked eleven: C33, C37, C43 and C45 had been added to the
table without it. Four decisions the owner was never told were waiting. Now derived and
asserted by `tests/test_construction_register.py::test_the_your_decision_list_matches_the_table`.)*

---

## The ones that need your judgement

### C1 — Time-limit handling splits 3 / 9 {#c1}

**Class** INHERITED + FALSE-CERTIFICATION · **Status** OPEN · **Cross-ref** blind audit D1

**Handicap — affects:** drqv2 svea sgqn curl drq ctrl idaac ppg ibac_sni
*the nine that zero the bootstrap on a task where EVERY episode ends by time limit (`rlgen/protocol.py:127-138`); `rad`/`soda`/`alda` bootstrap and are not handicapped here*

Door and Lift have **no early termination**, so every episode ends by time limit. Three baselines
treat that as truncation and bootstrap through it; nine treat it as a terminal state and zero the
bootstrap — on *every* episode, throughout training.

| | Baselines | Locator |
|---|---|---|
| **Bootstraps (correct)** | `rad`, `soda` | `runnable/dmc_gb/src/train.py:149` |
| | `alda` | `runnable/alda/trainers/alda_trainer.py:655` |
| **Zeroes** | `drqv2 svea sgqn curl drq` | `RL-ViGen-upstream/wrappers/robo_wrapper.py:42` |
| | `ctrl` | `runnable/ctrl/buffer.py:16,18` |
| | `idaac` | `runnable/idaac/ppo_daac_idaac/storage.py:58-62` |
| | `ppg` | `runnable/ppg/phasic_policy_gradient/ppo.py:38` |

**The split is lineage, not accident.** The three correct ones are the SAC-family clones
descended from Yarats' dmcontrol code, which carried the fix. The four Procgen-native ones are
wrong *here* only because the environment changed underneath them — in Procgen every episode
genuinely **is** a termination, so their authors were right for Procgen.

**Why it is also a false certification.** `rlgen/protocol.py` declares
`time_limit_handling = "truncate_with_bootstrap"` and that string is **inside `Protocol.hash()`**.
It is true of three baselines out of twelve.

**Blast radius** Nine baselines' value targets are biased downward relative to three. This sits
underneath every number either group produces and **no `git diff` can show it**, because nobody
introduced it. I rate this the largest comparability defect found.

**Evidence** Per-clone source survey, read individually. An independent blind audit asserted
*"every current clone zeroes the bootstrap"* — **false**, and caught only by reading each clone.

**Options**
1. **Split the field per-baseline**, the way `OBSERVATION_GEOMETRY` already splits frame stacking.
   Consistent with existing precedent; changes the hash once; honest.
2. **Re-value to `truncate_as_terminal`** and re-stamp. Simplest, but asserts a single value that
   is false for three baselines — trades one false certification for another.
3. **Edit the nine clones to bootstrap.** Maximum comparability, maximum infidelity: nine
   authored deviations on the ledger, and the numbers stop being the authors'.
4. **Leave and declare.** Zero work, permanent asymmetry, must appear beside every result.

*My reading: (1). It is the only option that is both true and consistent with what the project
already does for frame stacking. (3) is the one I would argue against hardest — it is exactly the
join this project exists to avoid.*

**Pinned by** `tests/test_truncation_split.py` (7 tests) · **Annotated at** `rlgen/protocol.py`

---

**Do not decide this on its own merits — and "leave it per-baseline" is not the same as leaving
it alone.** Added 2026-08-19 in answer to exactly that proposal.

[`RESEARCH-FRAME.md`](RESEARCH-FRAME.md) already settles the substance: under the claim this
design supports — *these twelve published implementations, run at their authors' own settings* —
**equalising would break the claim**, because the methods would no longer be as shipped. So the
substantive answer is indeed "declare and quantify, do not equalise". That is a decision with a
reason, not a deferral, and it follows from the claim rather than from anything about time limits.

**But one step is required regardless of the claim, and it is not a judgement call.**
`Protocol.time_limit_handling` is `"truncate_with_bootstrap"`, it is **inside `Protocol.hash()`**
(verified), and it is true of **three of twelve**. Whichever claim is chosen, the protocol
currently certifies something false about nine baselines, and two numbers that differ in this
convention hash *identically* — which is precisely the failure the hash exists to prevent. Leaving
it is not neutral; it is a false certification that survives the decision either way.

The field has to become either per-baseline or honestly plural, so that the hash separates runs
that differ in it. That is a bounded fix and it is **not** what the claim decision is about.

**Done, 2026-08-19 — the FALSE-CERTIFICATION half of this entry is closed.** `TIME_LIMIT_HANDLING`
now sits beside `OBSERVATION_GEOMETRY` in `rlgen/protocol.py`, keyed by baseline with the code
locator for each, and `__post_init__` fills the field from it whenever `name` is one of the
twelve. `Protocol(name="drq")` and `Protocol(name="rad")` no longer hash alike; the canonical
protocol carries `"per-baseline"` and asserts nothing about anyone. This is option (b) from the
field's own comment, which already called it "the consistent one".

Two things worth keeping:

- **The cost that had blocked it was the hash re-stamp**, and it was paid anyway that day: P14
  moved every hash for [C45](#c45)+[C43](#c43). Bundling the two re-stamps cost nothing beyond the
  first. A fix deferred for a cost is worth re-pricing whenever something else pays that cost.
- `tests/test_time_limit_split.py` reads the clones rather than trusting the map — the
  bootstrappers' `done_bool = 0 if episode_step + 1 == env._max_episode_steps` and the others'
  unconditional `discount = 0.0`. A map that drifts from the code it describes is worse than none.

**What remains open here is only the claim question**, and it is not answerable on this entry's
own merits: under the implementations-as-shipped claim, equalising would break the claim; under a
mechanism claim it would be mandatory. That is [`RESEARCH-FRAME.md`](RESEARCH-FRAME.md)'s to
settle, and C1 and [C2](#c2) follow from it.


> **This is not an independent decision — it follows from the claim, which is already written down
> (2026-08-26).** [`RESEARCH-FRAME.md`](RESEARCH-FRAME.md) states the claim the design supports
> — *"these published implementations, **run at their authors' own settings**, retain the following
> fractions"* — and then answers this entry directly: **"C1 and C2 ask whether to equalise
> time-limit handling and frame stack. Under the claim above the answer is no — equalising would
> break the claim, because the methods would no longer be as shipped. The right move is to declare
> and quantify them."**
>
> So the live question is **not** "equalise or not". It is **"is that the claim?"** — and if it is,
> this entry is answered and the work is disclosure, not equalisation. Both entries would only
> reopen if the intended claim were about algorithmic *mechanisms*, in which case
> [`RESEARCH-FRAME.md`](RESEARCH-FRAME.md) says the whole design needs rebuilding as a within-method
> ablation, and this entry would be the least of it.
>
> Left marked as needing judgement because **confirming the claim is itself the owner's**, and
> because a reader who accepts the claim should still see what it commits them to. But it should be
> decided *with* the claim, not separately from it — deciding it on its own merits is how one
> decision becomes several.

**DEFAULT SET AT THE PRE-RUN GATE, 2026-09-03.** This register's own working agreement says OPEN
items are decided *"in batches at gates, not continuously"*, and that the gate that matters is
**before the first expensive run**, because deciding after seeing which choice flatters a baseline
is a garden of forking paths. A pre-production sweep is that run, so C1–C4 are decided now, ahead
of it, and the reasoning below is deliberately written from the DESIGN rather than from any result.

**The governing principle, stated once and applied to all four**: the null this project measures
against is *each original repository running its own `train.py`*. A difference that an author chose
is therefore part of the thing being measured and is **kept**; a difference nobody chose is a defect
and is **fixed**. The cost of keeping is that the comparison is conditional, so every kept
difference must be declared beside the numbers and must never be averaged across.

**DEFAULT: KEEP each repository's own handling; declare it; do not rank across it.**
Bootstrapping through a time limit versus treating it as terminal is an author's choice, and
changing nine clones to match three would replace "their published methods" with "our modified
versions" — which is the one thing the hermetic design exists to prevent. **But the handicap is
real and asymmetric, and must be stated wherever these numbers appear**: on Door *every* episode
ends by time limit, so the nine that zero the bootstrap do so on every episode throughout training,
systematically truncating the value target. That is not a small conventional difference on this
task; it is a permanent bias against those nine. **What would overturn this default**: a decision
that the study is about algorithms *under a common protocol* rather than about the published
methods — in which case harmonise to bootstrap-through-truncation, and say so loudly, because it is
then a different experiment with a different null.

### C2 — Frame stack: 3 frames for eight, 1 frame for four {#c2}

> **DEFAULT SET, 2026-09-04 — declare, do NOT equalise, and the reason is that no single answer is
> right.** Equalising the stack points four different ways for the four single-frame baselines:
> `idaac` is *incoherent* with stacking (its adversarial head exists to destroy the temporal signal
> a stack supplies), `ctrl` would double-count temporal information it already encodes,
> `ibac_sni` would be mis-calibrated against a width chosen for a single frame, and `ppg`'s single
> frame is pure Procgen lineage. A uniform intervention is therefore wrong whichever way it points,
> and the honest instrument is the declaration: the seam audit carries it as a CONDITIONS split,
> which makes a difference *attributable* rather than removed. Overturn this only with evidence
> that the split explains a specific result, which no measurement here yet does.

**Class** INHERITED · **Status** OPEN

`rad soda alda` + the RL-ViGen five receive a 3-frame stack. `ppg idaac ibac_sni ctrl` receive a
single frame — exactly the Procgen lineage, because Procgen serves one RGB frame.

**Blast radius** A single frame on a manipulation task is **velocity-blind**: the gripper's motion
is not recoverable from the observation. This is arguably two different POMDPs rather than two
algorithms, which makes any head-to-head number conditional on it.

**Evidence** `scripts/probe_geometry.py` PROBE 1 — a 3-frame stack on Door carries
**0.0096–0.0103** mean absolute pixel change per step across the three render sizes. That is the
motion signal the eight receive and the four do not.

**Options**
1. **Give the four a frame stack.** Comparable observation; a real deviation from four references,
   and for `ibac_sni` it multiplies an already-oversized layer (see C3).
2. **Leave and report per-group.** Honest; means the twelve are not one comparison but two.
3. **Report both**, at extra compute.

*My reading: this one genuinely depends on the claim you want to make. If the claim is "these
twelve differ", (1). If it is "these twelve as their authors built them differ", (2). Decide the
claim first — it is the same decision, one level up.*

**Pinned by** `tests/test_observation_geometry.py` · `Protocol.OBSERVATION_GEOMETRY`

---

**The false-certification half is closed, 2026-08-19**, by the same fix as [C1](#c1) and for the
same reason: it was never a claim question. `Protocol.image_size` and `frame_stack` are **inside
the hash** and defaulted to (84, 3) for every baseline, while `OBSERVATION_GEOMETRY` — in the same
file — already recorded that `rad`/`soda` render at 100 and that `ppg`, `idaac`, `ibac_sni` and
`alda`'s stack differs. So `Protocol(name="ppg")` certified an observation ppg never sees, and a
ppg run hashed identically to a `drqv2` run on the axis that decides comparability.

The map existed from the start; only the wiring was missing. `__post_init__` now fills both from
it when `name` is one of the twelve, an explicit value is never overwritten, and an unknown name
falls back to the documented defaults. `Protocol(name="ppg").hash() != Protocol(name="drqv2").hash()`.

**What remains open is the same claim question as C1**, and it is not answerable here: equalising
frame stack would break the implementations-as-shipped claim and would be mandatory under a
mechanism claim. [`RESEARCH-FRAME.md`](RESEARCH-FRAME.md) settles it; this entry follows.


> **This is not an independent decision — it follows from the claim, which is already written down
> (2026-08-26).** [`RESEARCH-FRAME.md`](RESEARCH-FRAME.md) states the claim the design supports
> — *"these published implementations, **run at their authors' own settings**, retain the following
> fractions"* — and then answers this entry directly: **"C1 and C2 ask whether to equalise
> time-limit handling and frame stack. Under the claim above the answer is no — equalising would
> break the claim, because the methods would no longer be as shipped. The right move is to declare
> and quantify them."**
>
> So the live question is **not** "equalise or not". It is **"is that the claim?"** — and if it is,
> this entry is answered and the work is disclosure, not equalisation. Both entries would only
> reopen if the intended claim were about algorithmic *mechanisms*, in which case
> [`RESEARCH-FRAME.md`](RESEARCH-FRAME.md) says the whole design needs rebuilding as a within-method
> ablation, and this entry would be the least of it.
>
> Left marked as needing judgement because **confirming the claim is itself the owner's**, and
> because a reader who accepts the claim should still see what it commits them to. But it should be
> decided *with* the claim, not separately from it — deciding it on its own merits is how one
> decision becomes several.

**DEFAULT: KEEP 3-frame and 1-frame as they are; group by it in every table; never rank across it.**
The stack size is inherited from each lineage — Procgen serves one RGB frame, so the four Procgen
descendants take one. Kept for the same reason as C1. **The declaration matters more here than in
C1**, because a single frame on a manipulation task is *velocity-blind*: the gripper's motion is
not recoverable from the observation, so `ppg`, `idaac`, `ibac_sni` and `ctrl` are solving a
strictly harder POMDP than the other eight. A twelve-row table that sorts by return and draws a
conclusion has compared two different problems. **The practical rule**: report them as two groups,
and if a single ordering is ever needed, it is an ordering *within* a group. **What would overturn
this**: giving the four a 3-stack, which is four deviations and makes them non-reproductions of
their papers.

**CORRECTION, 2026-09-03: "the four single-frame baselines" is not one fact, it is four different
ones, and only one of them is lineage.** This entry, and `audit_comparability_seam.py`'s frame-stack
axis, group `ppg idaac ctrl ibac_sni` as a single split inherited from Procgen. Reading what each
does with the temporal axis separates them, and the differences change what "equalise the stack"
would even mean:

| baseline | why single-frame | what a 3-stack would do |
|---|---|---|
| **`idaac`** | **structural conflict** | Its auxiliary head predicts *which of two observations from one trajectory came first*, and the encoder is adversarially trained to make that prediction impossible ([`SUPERVISOR-BRIEFING.md`](SUPERVISOR-BRIEFING.md):279). A stack embeds local motion **inside a single observation**, handing the discriminator exactly the signal the objective exists to destroy. Equalising here is not a fidelity cost — it is **incoherent** |
| **`ctrl`** | **double-counting** | It builds temporal structure explicitly, over a sliding window of `cluster_len=10` single frames. Stacking would represent the same axis twice, once inside the observation and once across the window |
| **`ibac_sni`** | **mis-calibration** | Its VIB's β is tuned against single-frame input entropy. A stack adds *task-relevant* information (velocity, on a manipulation task), so the same β passes more signal and the bottleneck is effectively under-regularised. The method still runs and still means something; it is not the trade-off its authors tuned |
| **`ppg`** | **lineage only** | No mechanism-level objection found. Procgen serves one RGB frame and nothing on the robosuite path adds a wrapper |

**Consequence for this entry's open question.** "Equalise or not" was posed as one decision over
four baselines. It is not: for `ppg` it is a live option, for `ibac_sni` a recalibration, for `ctrl`
a redundancy, and for `idaac` a contradiction. **A uniform answer is wrong whichever way it points.**

**Provenance, stated because it is weaker than the rest of this entry**: this is reasoning from
each method's own mechanism, not a citation — no document in this project records an architectural
block on frame stacking, which is why the four were grouped in the first place. It was prompted by
the owner's recollection that such a block existed; the block is real for `idaac` and arguably
`ctrl`, and does not exist for `ppg`.

### C3 — Historical `ibac_sni` 64×64 trunk mismatch; production uses the source-backed Impala repair {#c3}

> **SUPERSEDED DEFAULT, 2026-09-04 — keep 64x64 and keep saying it is ours.** This was the one resolution in
> the project taken from **no reference for this target**, and that is exactly why it should not be
> changed on judgement: swapping it would replace an unjustified number with a differently
> unjustified number while silently altering the model's width (the embedding is
> `((n-1)//2-2) * ((m-1)//2-2) * 64`, so 64x64 gives 53,824 against MiniGrid's 64). Keeping it holds
> the baseline stable across every run already recorded.
> **A reason to revisit now exists and is written here rather than acted on**: `ibac_sni`'s entropy
> collapse ([C61](#c61), measured 2026-09-04, `boundary_fraction` 0.580) is on the baseline this
> entry calls handicapped, and a 227x model is a plausible contributor. Distinguishing "the
> coefficient is wrong for this head" from "the model is too wide for this task" needs a run at a
> second width — which is a real experiment, not a default.
>
> ### Researched 2026-09-04 at the owner's request — the 64 IS referenced, and that makes it worse, not better
>
> The owner's guess was *"maybe the original number was explicitly scoped to the original env it was
> run at and its scale."* It was, and the scoping includes the **network**, which is the part that
> was dropped:
>
> * IBAC-SNI ships **two** branches. `coinrun/` is **TensorFlow** (`import tensorflow as tf`,
>   `baselines.a2c.utils`) and carries the paper's *pixel* architectures — `impala_cnn`
>   (depths 16/32/32) and `nature_cnn`, selected by `arch` in `policies.py:106-116`. Those
>   downsample, and **64x64 is their input**.
> * `torch_rl/` is **PyTorch** and is the MiniGrid branch. Its `ACModel` derives width from the
>   input at `model.py:57, 83, 109` — three variants, **all MiniGrid-shaped**. At 64x64 they give
>   28,800 / 53,824 / 26,912; at MiniGrid's native 7x7 the intended 64.
> * **Our launcher runs `torch_rl/scripts/train.py`.**
>
> So 64 came from the paper's CoinRun branch and was paired with the MiniGrid branch's
> architecture. **The paper never put a 64x64 frame through this network**; it put 64x64 through
> impala/nature. Option 1 above — *"justify 64 against the paper's CoinRun branch"* — is therefore
> **weaker than it looked**: the justification only transfers if the architecture transfers with it.
>
> **And no option inside the PyTorch branch repairs it**, which is the useful negative result: all
> three `model_type` variants blow up at 64x64 because none downsamples enough, so switching
> variant buys nothing. The real choices are (a) keep 64x64 and declare that `ibac_sni`'s model is
> FC-dominated *by construction* because a MiniGrid architecture is being fed pixels; (b) lower the
> resolution, which deviates from both branches and is ours either way; (c) author a downsampling
> front-end, i.e. port the CoinRun architecture — a genuine architectural deviation.
>
> **The option space closes analytically, 2026-09-04 — option (b) is not available.** The default
> trunk is `Conv(3,16,2) → ReLU → MaxPool(2) → Conv(16,32,2) → ReLU → Conv(32,64,2) → ReLU`
> (`model.py:73-83`): **exactly one 2x downsample in the whole network**, so spatial size is
> `(n-1)//2 - 2` and the embedding is that squared, times 64:
>
> | input | spatial | embedding |
> |---|---|---|
> | 7 (MiniGrid native) | 1 | **64** |
> | 15 | 5 | 1,600 |
> | 17 | 6 | 2,304 |
> | 21 | 8 | 4,096 |
> | **64 (ours)** | 29 | **53,824** |
> | 84 | 39 | 97,344 |
>
> The paper's pixel network, `impala_cnn` with depths 16/32/32, pools three times: 64 → 32 → 16 → 8,
> giving **8x8x32 = 2,048** — the same order as `ppg`'s and `idaac`'s. To reach ~2,048 through the
> MiniGrid trunk you would need **n ≈ 17**, and a 17x17 frame cannot show a door handle when every
> other baseline gets 64 or 84. **So no resolution satisfies both constraints at once**: sane
> embedding and usable view are incompatible for this trunk, because it downsamples once. Lowering
> the resolution is therefore not a repair, and the only real one is architectural — add
> downsampling, which is what `impala_cnn` is.
>
> ### The repair exists now, opt-in and locally verified — 2026-09-04
>
> `model_type="impala"` ports IBAC-SNI's **own** pixel network from its TensorFlow branch
> (`coinrun/coinrun/policies.py::impala_cnn`) into `torch_rl/model.py`: conv3x3(depth) → maxpool(3,
> stride 2, 'same') → two residual blocks, depths 16/32/32. Both models were constructed locally
> with the bottleneck and SNI active — the one validation in this whole area that needed no GPU:
>
> | `model_type` | embedding | total parameters |
> |---|---|---|
> | `default` (MiniGrid trunk) | 53,824 | **6,900,671** |
> | `impala` (the paper's pixel net) | **2,048** | **360,399** |
>
> Nineteen times smaller, at the figure the paper's own CoinRun branch produces, and the same order
> as `ppg`'s and `idaac`'s. **Opt-in and default-off**: no existing number changes, and choosing it
> is a deliberate act. It is **not** a bug fix — `impala` and `default` are different models and
> must never share a column.
>
> ### DEFAULT CHANGED, 2026-09-04 — `runnable/_launch/ibac_sni.sh` now passes `--model_type impala`
>
> Recording the defect and leaving the defect running is not a default, it is a deferral. The
> launcher already overrides this repository's shipped defaults for exactly this reason —
> `--use_bottleneck --sni_type vib`, because the repo defaults to both off, which is plain PPO and
> not IBAC-SNI at all. **Selecting the authors' pixel architecture for a pixel task is the same act
> by the same precedent**, and it *removes* an authored hybrid rather than adding one: 64x64 with
> the MiniGrid trunk is a configuration neither branch of the paper ever ran.
>
> `--model_type default` restores the old pairing for anyone who wants the comparison.
>
> **This supersedes every ibac_sni measurement taken on the hybrid**, including [C61](#c61)'s
> entropy collapse (`boundary_fraction` 0.580 at 100k). That finding stands *for the configuration
> it was measured on* and must be re-measured here — and the re-measurement is now the experiment
> that separates "the entropy coefficient is wrong for this head" from "a 6.9M-parameter model is
> wrong for this input", which were previously inseparable.
>
> The reasoning below is kept because it is what led here:
>
> **Superseded default (keep 64x64 and the `default` trunk, declared), stated at the time as**:
> (a) is the only one of the three that adds no authored deviation, and the owner's own standard is
> that the algorithms and models stay fidelity-bound. But this materially strengthens the
> C61 suspicion — **a 3.46M-parameter FC head trained on a few thousand frames is a strong
> alternative explanation for the entropy collapse**, and it means "lower the entropy coefficient"
> and "this model is wrong for this input" are not competing hypotheses so much as two symptoms of
> the same transplant.

**Class** OURS · **Status** OPEN

**Historical handicap — affects:** ibac_sni
*the former 64×64 MiniGrid trunk, superseded by the source-backed Impala production default*

`ibac_sni`'s `torch_rl` branch is MiniGrid, which has no image-size precedent; 64 was borrowed
from the paper's own CoinRun branch. It is **the one resolution in the project not taken from a
reference**, and the architecture derives its width from the input:

```python
model.py:83   image_embedding_size = ((n-1)//2-2) * ((m-1)//2-2) * 64
```

**Evidence** `scripts/probe_geometry.py` PROBE 3 builds the real `ACModel`:

| input | embedding | conv params | total params |
|---|---|---|---|
| 7×7 — MiniGrid native, what the code was written for | 64 | 10,544 | **15,231** |
| **64×64 — ours** | 53,824 | 10,544 | **3,455,871** |
| 84×84 — the RL-ViGen five's | 97,344 | 10,544 | 6,241,151 |

The conv trunk is **identical at every resolution**. Every added parameter sits in a
fully-connected head fed by a flattened output the architecture expected to be 64-dimensional.
**The resolution was the layer size** — nobody typed one.

**Options**
1. **Justify 64 against the paper's CoinRun branch explicitly** and record it. Cheapest.
2. **Reduce the input** so the embedding is sane — deviates from both branches.
3. **Change the architecture** to pool before flattening — an authored architectural change, the
   most invasive option and the one most likely to stop being IBAC-SNI.

*My reading: (1), and say plainly in any write-up that `ibac_sni` carries a model two orders of
magnitude larger than its reference at the same nominal algorithm.*

**Pinned by** `probe_geometry.py` PROBE 3 (measurement) · resolution table unpinned

---

**SUPERSEDED DEFAULT (2026-09-04): KEEP 64x64 with the MiniGrid trunk, and mark `ibac_sni`'s row as
the one resolution in the project with no referent for this target.** C1 and C2 keep an author's choice; this is not one — 64 was taken from
the paper's *CoinRun* branch, not from anything about robosuite, and the MiniGrid branch the code
comes from has no image precedent at all. So the fidelity argument does not apply and the honest
statement is narrower: **64 is the best available referent, not a justified one.** It is kept
because the alternative is inventing a number, which is worse than borrowing one the authors
themselves used elsewhere. **The consequence is carried, not hidden**: the architecture derives its
width from the input, so this makes `ibac_sni` a 227x model, and any `ibac_sni` number is
conditional on a choice this project made rather than inherited. **What would overturn this**: a
resolution used by the paper for a continuous-control target, if one exists — that would be a real
referent and should replace 64 immediately. **This default is superseded:** the source-backed
Impala port now pairs the paper's 64x64 pixel resolution with its own pixel trunk and is the
launcher default. The former MiniGrid result remains a named legacy ablation, not the production
configuration.

### C4 — float64 vs float32 alpha, visible only on CUDA {#c4}

> **DEFAULT SET, 2026-09-04 — declare, do not harmonise.** The difference is each repository's own:
> `drq.py:213` builds log-alpha in float32 (patch P5) and `dmc_gb` uses the torch default. Both are
> upstream behaviour, the divergence is visible only on CUDA, and no reported quantity has been
> shown to move with it. Harmonising would author a change in one clone to match another for
> aesthetic uniformity — the exact move the clone-era null forbids. It stays a declared,
> per-baseline numerical fact; it is promoted to a decision only if a measurement is ever traced to
> it.

**Class** UNDECLARED · **Status** OPEN · **Cross-ref** blind audit D4

| | |
|---|---|
| `RL-ViGen-upstream/algos/drq.py:213` | `torch.tensor(np.float32(np.log(init_temperature))).to(device)` — **float32**, unconditional (this is patch P5) |
| `runnable/dmc_gb/src/algorithms/sac.py:35` | `torch.tensor(np.log(args.init_temperature)).cuda()` — **float64 on CUDA** |

`drq` is the only RL-ViGen algorithm with a temperature at all, so the comparison is exactly
`drq` against `rad`/`soda`.

**Blast radius — the second consequence is the one that matters.** (1) On the authoritative CUDA
runs, `drq`'s alpha is float32 and `rad`/`soda`'s is float64. (2) **`dmc_gb`'s local run is not
the same numerical configuration as its CUDA run** — the MPS shim downcasts float64, so locally
both are float32. A green local `rad`/`soda` result does not evidence the CUDA arithmetic.

`docs/REGISTER.md:130` accepted P5's unconditional cast *specifically to avoid machine-dependent
results*. The tree now has that cast in one clone and not the other, declared nowhere.

**Options**
1. **Add the same cast to `dmc_gb`.** One line, recorded by the ledger, makes local and CUDA
   agree and makes the two clones agree. Changes `rad`/`soda` CUDA arithmetic.
2. **Declare and leave.** Zero code, but the local/CUDA gap persists for two baselines.

*My reading: (1), and it is nearly free. But it changes a clone's numerics, so it is yours.*

**Pinned by** unpinned — worth a test either way

---

**DEFAULT: KEEP both, declare it, and treat it as a REPRODUCIBILITY hazard rather than a fairness
one.** This is the one of the four that nobody chose: `dmc_gb`'s `torch.tensor(np.log(...)).cuda()`
is float64 because numpy's default is, and RL-ViGen's is float32 because patch P5 made it so. By
the governing principle an unchosen difference is a defect to fix — but fixing it means editing a
clone's optimiser state for a scalar whose relative difference is ~1e-7, and the SAC temperature is
not a quantity where that biases either direction. **So the asymmetry is: it cannot systematically
favour anyone, but it can make a run unreproducible**, because [C41](#c41) is exactly the argument
that a 1e-7 perturbation changes an action, which changes a transition, which changes everything
after it. **It matters more now than when this entry was written**: it is visible only on CUDA, and
as of C95 every number this project reports is produced on CUDA. **What would overturn this**: any
measured divergence between two `drq` runs traced to alpha precision — at which point harmonise to
float32 and record it as a deviation.

### C16 — `ctrl` ships the authors' plaintext W&B key {#c16}

> **DEFAULT SET, 2026-09-04 — done, and this entry's status was the stale part.** Option 1 was taken
> on 2026-09-03: the literal was blanked in the clone. The residual risk is zero functionally
> (launchers pass `--wandb_mode=disabled`, and `runnable/_shim/wandb.py` opens no socket at all, so
> even a live key could not leave the box) and the secret is the original authors' committed one,
> arriving with a faithful clone rather than created by us. **No further action**: the remaining
> item is not a decision but a courtesy — that the key is theirs to rotate, not ours to publicise,
> which is why it is named here and not quoted anywhere.

**Class** OURS (inherited risk) · **Status** OPEN · **Cross-ref** audit category 50

`runnable/ctrl/train_ppo.py` still carries the original authors' plaintext Weights & Biases key.
It is **inert** — launchers pass `--wandb_mode=disabled` — and it is *their* committed secret, not
ours, arriving with a faithful clone.

**Blast radius** Zero functionally. Non-zero if this tree is ever published, shared, or uploaded:
a clone is not a defence for redistributing someone's credential.

**Measured 2026-08-24 — the exposure surface is currently empty, which makes option 2 checkable
rather than aspirational.** Searched without printing the value:

- `git log --all -S<key>` returns **nothing** — it has never been in a commit on any branch.
- It appears in **no** patch under `runnable/_patches/`, and in nothing under `compute/`, `docs/`,
  `scripts/` or `setup/` — i.e. in none of the material that would travel if this were published.
- `runnable/ctrl/` is **gitignored**, so the file holding it is not tracked at all.
- The clone is `PRISTINE: ctrl_public @ 7a118c8` — the key is upstream's own committed value in a
  **public** repository, so this is mirroring their exposure, not creating one.

Functionally inert twice over, also verified rather than assumed: our `runnable/_launch/ctrl.sh:45`
passes `--wandb_mode=disabled` (with the reason at line 23), **and** upstream's own default at
`train_ppo.py:67` is already `disabled`.

So the residual risk is narrower than the entry implied: it is not "a secret in our repo" but "a
file on this disk, untracked, holding a credential its owners published themselves." Option 2's
gate would be a one-line grep over tracked files, and it would currently pass.

**Options**
1. **Redact in the clone.** One line on the ledger, and it makes the clone non-pristine in a way
   that is arguably a *good* deviation.
2. **Leave, and gate publication.** Add it to whatever check runs before anything is uploaded.
3. **Leave and do nothing.** Only defensible while the tree stays private.

*My reading: (1) or (2), and (2) only if there is an actual pre-publication gate. Given the
standing "private by default" constraint this is not urgent, but it should not be discovered by
someone else later.*

**DEFAULT TAKEN, 2026-09-03 — option 1, because a fact in this entry's own risk assessment came
true.** The 2026-08-24 blast-radius line reads "Non-zero if this tree is ever published, shared,
**or uploaded**". It has since been uploaded: `runnable/ctrl/` is a payload member, and the payload
is a DataSphere job input, so the credential has travelled to a third-party cloud service on every
`ctrl` job — six payload versions carry it (`payload-v45` … `payload-v50`), and several of those
have been submitted. That converts the entry's hypothetical into an actual, and "gitignored"
stops being a defence, because the payload builder reads the working tree rather than the index.

**What was done, minimally.** The 40-character literal in `train_ppo.py:69` is replaced by `""`,
with a comment at the flag explaining why. **No code path changes**: the flag still exists, the
`os.environ["WANDB_API_KEY"] = FLAGS.wandb_key` at :106 still runs, and `wandb_entity` is left at
its upstream value because it is a project name and not a secret. Functionally this was already
inert three times over — upstream defaults to `disabled`, our launcher passes `--wandb_mode=disabled`,
and `runnable/_shim/wandb.py` never opens a socket — so the change removes transmission, not
behaviour. Verified after the edit: the literal appears nowhere under `runnable/`.

**What this does NOT fix, stated because it would otherwise read as retroactive.** The six payload
archives already on disk still contain it, and the jobs already submitted have already carried it.
Redaction protects future payloads only. The archives are regenerable, so deleting or rebuilding
them is available — not done here, because they are the artifacts several dated register rows cite
as evidence, and destroying evidence to tidy a secret that its own authors published is the wrong
trade. **Left to the owner**: whether to rebuild the payload archives, and whether the pre-upload
grep of option 2 should exist as a gate regardless, since redaction fixes one file and a gate would
catch the next one.

**Pinned by** unpinned

---

## Design gaps — these block results, not code

### C17 — Random-policy floor, and whether the signal fires at all {#c17}
**Class** DESIGN-GAP · **Status** RESOLVED

**Decision** measure the floor before reading anything into a reported `0.000`, since "the
policies fail" and "this task yields no successes here" are different findings needing different
next steps.

**Attempt, in two parts, because the first was not enough.** `scripts/probe_floor.py` ran 25
random episodes per task. Then — because the result was uninterpretable alone —
`scripts/probe_success_control.py` supplied the positive control the floor lacked.

**Effect** — the floor is 0 and, more usefully, **the success signal is established live**.

| task | succ | 95% Wilson | ever fired? | return mean | return max |
|---|---|---|---|---|---|
| Door | 0/25 | [0.000, 0.133] | **never** | 1.633 | 6.933 |
| Lift | 0/25 | [0.000, 0.133] | **never** | 6.562 | 34.647 |

**Superseded on the "never" point by [C42](#c42): a learned policy now fires it in 6 of 10
held-out episodes.** "Never observed" is why the floor alone could not close this: it and "the signal is dead" produce
an identical log of zeros. So the positive control drove the **simulator** to each task's own
threshold — Door's hinge past its `> 0.3`, Lift's cube above `table + 0.04` — leaving
`_check_success` unpatched. Both tasks: `False` before (not stuck True), `_check_success()` True,
flag reaches the caller. **So a trained `0.000` now means "did not reach the threshold", not "the
instrument is broken."**

Three by-products worth as much as the headline:

- **Return has real dynamic range** — Door 1.633 mean vs 6.933 max, Lift 6.562 vs 34.647. Where
  success is silent, return is not, so it survives as an endpoint. Bears on
  [`RESEARCH-FRAME.md`](RESEARCH-FRAME.md)'s note that env-derived quantities are the strongest
  case for comparability.
- **Throughput measured for the first time**: ~100 steps/s, ~12 episodes/min. 500k frames ≈ 83
  min per run locally; 12 baselines × 5 seeds × 2 tasks ≈ 166 hours. Remote compute is not a
  preference.
- **Episode length was exactly 500.0 every episode**, empirically confirming [C1](#c1)'s premise
  that these tasks only ever end by time limit.

Pinned by `tests/test_success_metric.py::test_the_success_criterion_can_actually_be_met`, so a
future change that breaks reachability — a mujoco upgrade moving `hinge_qpos_addr`, say, which
[C29](#c29) says nothing currently guards — fails loudly.

Commit `645be961`. **Spawned [C31](#c31).**

### C18 — Single seed, 10 episodes {#c18}
**Class** DESIGN-GAP · **Status** READY

Current reporting is one seed, `n=10`, giving Wilson `[0.000, 0.278]`. RL-ViGen's own paper §4
specifies **5 seeds and 95% CIs**. Resolving a 5-point difference needs roughly 70–100+ episodes
per point; `bootstrap_ci` as implemented resamples *episodes within a run* and says nothing about
seed-to-seed variance, which is usually the larger term. **Evidence** Wilson widths, computed.

**The seed-to-seed term now has a number, 2026-08-19** (`scripts/plan_seed_budget.py`). Estimated
from the only paired evidence available — [C41](#c41)'s two runs of the same configuration *and*
the same seed at nine matched checkpoints — the coefficient of variation of a single run's return
is **~17.4%**. Converting that to a detectable difference:

| seeds per arm | smallest difference in return it resolves |
|---|---|
| 1 | 68.8% |
| 3 | 39.7% |
| **5** (the paper's number) | **30.8%** |
| 10 | 21.8% |
| 20 | 15.4% |
| 50 | 9.7% |

Inverted: a 20% difference needs **12** seeds, 10% needs **48**, and 5% needs **190**.

**So the five-seed plan resolves differences of about thirty percent, not five points.** That is
the sentence to carry into any comparison this project reports.

> **CORRECTED 2026-09-05, twice over — and the corrected sentence is the one to carry.**
> **(1) The plan is no longer five seeds.** `production-schedule-v100.json` sets
> `"seeds": [101, 102, 103]`, n = 3. **(2) The table above used the NORMAL approximation**
> (`plan_seed_budget.py`'s `z = 2.802`), which is asymptotic and least valid at exactly the n this
> project plans; at n = 3 the correct t multiplier (df = 4) is 3.717. Recomputed: **n=3 resolves
> 52.7%, not 39.7%**; n=5 resolves 35.1%, not 30.8%; the two methods agree at n=50 (9.8%), which is
> the signature of a correct t-correction. A 20% difference needs **13** seeds, not 12.
> `plan_seed_budget.py` now uses t and solves the inverse by iteration.
>
> **So the sentence to carry is: the three-seed production plan resolves differences of roughly
> fifty percent.** Both inputs remain floors — the CV is from a same-seed pair (backend
> nondeterminism only) and the t-correction only raises the requirement. Full working:
> `notes/FINDING-resolving-power-at-n3.md`; the seed count itself is **A28**. It does not make five seeds
wrong — five seeds is a large improvement on one, and it is what the reference specifies — but it
bounds what a five-seed table can claim, and the bound is much weaker than the phrase "5 seeds
and 95% CIs" suggests to a reader.

Two things soften it slightly, and one hardens it. Measuring at convergence rather than mid-curve
drops the CV to ~12.2% (five seeds → ~21.6%), because C41's pair disagrees most in the middle and
finishes 7.3% apart. Return is also a dense quantity on Door, so a relative difference is not a
success-rate point. Against that: this is **one pair of runs** with non-independent checkpoints,
so it is a lower bound on the spread, exactly as C41 asks its own numbers to be read. A second
pair would improve the estimate more than any refinement of the arithmetic.

**And the estimate is conservative in a specific, checkable way.** C41's two runs share a
configuration *and a seed*, so their spread is backend nondeterminism alone — none of it comes
from the seed. Genuine seed-to-seed variation adds a different initialisation and a different
exploration path on top of that, and cannot be smaller. So **~17.4% is a floor on the
between-seed CV, and every seed count above is a floor on the seeds required.** The direction
matters: the error in this estimate makes five seeds look *better* than they are, not worse.

Note this is the *between-seed* term only. It compounds with the within-run episode term the
entry opens with; neither substitutes for the other.

### C19 — Train/eval regime separation, measured {#c19}
**Class** DESIGN-GAP · **Status** RESOLVED

**Decision** measure it before spending training compute, because if `eval-easy` were visually
near-identical to `train` then "generalisation" would be measuring noise and every run after
that would be wasted.

**Attempt** `scripts/probe_regimes.py`. The design is the point: a between-regime distance is
uninterpretable alone, because two samples of the *same* regime already differ (initial states,
and in eval the per-episode randomisation). So each regime is sampled **twice with different
seeds** to establish the within-regime control, and the verdict is the **ratio**, not the
distance. Metric is `histogram_tv_distance` — per-channel, because a colour randomisation moves
channels differently and greyscaling first would hide exactly that.

**Effect** — all three eval regimes are separated **on Door, at render 84, in one run, not
repeated on Lift** — so the measurement is licensed at the input level, under those conditions. Door, render 84, random policy, 3 episodes × 6 frames per sample:

| regime | within (control) | vs train | ratio |
|---|---|---|---|
| train | 0.0192 | — | — |
| eval-easy | 0.0775 | 0.4674 | **6.0×** |
| eval-medium | 0.0815 | 0.5897 | **7.2×** |
| eval-hard | 0.0670 | 0.4739 | **7.1×** |

Two internal checks passed without being aimed for: within-**train** is 0.019 because train
randomises nothing, while within-**eval** is 0.067–0.082 because eval randomises per episode.
That asymmetry is what the probe should show if it is measuring the intended thing.

**Limits, stated because they bound how the number may be used.** It is a marginal *intensity*
distribution, so two scenes could differ structurally and share a histogram — a large ratio is
evidence of separation, a small one is **not** proof of its absence. And it is what a *random*
policy sees; a converged policy visits a different part of the state space.

Commit `95bba362`. **Spawned [C27](#c27).**

### C20 — Per-clone determinism, now tested {#c20}

> ### Correction, 2026-09-02: `ppg` is no longer the exception, because we changed it
>
> The finding below — *"eleven of twelve declare a seed and route it… `ppg` is the exception"*, and
> the conclusion that **`ppg` cannot contribute a 5-seed row at all** — was true of the clone as
> shipped and is no longer true of the clone as it stands. `runnable/ppg/phasic_policy_gradient/
> train.py` now exposes `--seed`, seeds `random`, `numpy` and `torch` (and `cuda`) before the
> environment is built, and passes the seed into `get_venv`. **That is our construction, not
> upstream's**, and it is ENABLES-class: before it, every ppg run this project could launch was
> seed 0 with an unseeded network, so a three-seed ppg row would have been three runs of one
> configuration wearing three labels.
>
> **The audit found this, not a person.** `tests/test_seed_control_audit.py` carried a tripwire
> asserting ppg *stays* unseeded, whose message read *"If a seed knob was added, C20's finding
> changed and the register must say so in the same commit"*. The knob was added earlier in the
> same session and the ledger obligation was not discharged; the test failed on the next full run
> and named its own remedy. The tripwire now points the other way — losing the knob again is the
> failure worth catching, because it would restore a defect that looks exactly like a seed set.
>
> **What is unchanged**: the default seeds still disagree across trees (1, 0, `None`), so a seed
> set still has to be named rather than inherited. The production default is 101/102/103, named
> for that reason.

**Class** DESIGN-GAP · **Status** RESOLVED · **Commit** `705d0baa` · **Cross-ref** [C52](#c52), [C49](#c49)

The 5-seed plan rests on seeds actually controlling runs, per clone, and on the agent's RNG
stream being isolated from the environment's (Patterson et al., *Empirical Design in RL*). Not
checked for any of the twelve. Not hypothetical: the TorchRL sweep found `ppo`, `a2c` and
`impala` shipped **with no seed knob at all** while the paper claimed five seeds
(`docs/library-survey/raw/torchrl.md` §2.2).

**Screen (a) — is there a knob, and is it wired?** `scripts/audit_seed_control.py`, static,
one hop from each entry point. **Eleven of twelve declare a seed and route it to both the global
RNGs and the env constructor. `ppg` is the exception**: `phasic_policy_gradient/train.py`
defines nine `add_argument` flags and none of them is `--seed`, and no `manual_seed` /
`np.random.seed` / `random.seed` call exists anywhere in its tree. Its envs take
`get_robosuite_venv(seed=0)`, a default the launcher cannot reach. So a ppg run's weight init and
action sampling are seeded by whatever the OS supplies, two ppg runs cannot be made to agree, and
**ppg cannot contribute a 5-seed row at all** — the TorchRL failure, in this repo.

**Default seeds disagree**: 1 for upstream/ctrl/ibac_sni, 0 for alda/idaac, `None` (asserted
non-None) for dmc_gb. "The default run" is therefore a different run per baseline, so a seed set
has to be named rather than inherited.

**What screen (a) cost in instrument error, recorded because the direction matters.** Its first
version returned three wrong verdicts covering nine baselines — `AGENT_ONLY` for upstream,
`DECLARED_NEVER_CONSUMED` for alda, `NO_KNOB` for ctrl — from three separate blind spots: env
seeding done by constructor kwarg (`robo_make(..., seed=cfg.seed)`) rather than a `.seed()` call;
declaration by `absl.flags` rather than `argparse`; and a live path reached by
`importlib.import_module` from a yaml spec, which no static walk can follow. All three failed in
the same direction — **understating** seed control, i.e. inventing a defect. Each is now pinned by
a red-green test in `tests/test_seed_control_audit.py`, and all three mutants were verified to
kill. The general lesson is the one this project keeps relearning: the checker matched the shape
it expected the mechanism to have, not the mechanism.

**Screen (b) — do two same-seed runs agree?** `scripts/probe_determinism.py`, running each clone's
`smoke_all.sh` recipe twice at seed 1 and once at seed 7. The cross-seed trial is the positive
control: without it, same-seed agreement could be a fingerprint that cannot resolve runs at all.
It fired in every row below.

Wall-clock is excluded from the fingerprint, and **getting that exclusion right took three
attempts**, which is why the retractions below exist. Timing enters a log in at least three
shapes: a CSV column (`fps`, `total_time`), a keyword-then-number field (`fps 15.02`), and a
number-then-keyword phrase or line prefix (`PPO took 1.13 seconds`, `I0819 07:27:14.912374`). Each
form that slips through splits two identical runs apart, so the error is always toward
NONDETERMINISTIC — a false positive in the direction that looks like rigour.

| baseline | trainer | envs | values behind the fingerprint | verdict |
|---|---|---|---|---|
| `drqv2` | upstream | 1 | 3 rows | DETERMINISTIC |
| `svea` | upstream | 1 | 3 rows | DETERMINISTIC |
| `curl` | upstream (cpu) | 1 | 3 rows | DETERMINISTIC |
| **`sgqn`** | upstream | 1 | 3 rows | **NONDETERMINISTIC** |
| **`drq`** | upstream | 1 | 3 rows | **NONDETERMINISTIC** |
| `rad` | dmc_gb | 1 | 26 | DETERMINISTIC |
| `soda` | dmc_gb | 1 | 93 | DETERMINISTIC |
| `ibac_sni` | own | 1 | 148 | DETERMINISTIC |
| `ctrl` | own (JAX) | 4 | 54 clean | DETERMINISTIC *(corrected — see below)* |
| **`idaac`** | own | 4 | 47 clean | **NONDETERMINISTIC** |
| **`alda`** | own | 1 | 408 clean | **NONDETERMINISTIC** |
| `ppg` | own | — | — | **unmeasurable**, see below |

**Seven of eleven reproduce; four do not.** The control fired in every row, so each verdict is
about the runs and not about a blind instrument.

**One row is not on the same footing as the others: `curl` ran on CPU.** It cannot run under the
MPS shim at all (it dies with a `scatter: index -1` error, which is why `smoke_all.sh` gives it
`device=cpu`), so its verdict is about *curl-on-CPU* and says nothing about curl on the backend
every other row used. That mattered less when the table was a list; it matters now that `drq`'s
cause turns out to be the backend, because it means `curl` sits on the side of the comparison
that has been shown to reproduce for at least one other baseline. Read its DETERMINISTIC with
that attached.

The fingerprint widths differ by an order of magnitude and that is worth reading with the
verdicts. `ibac_sni`'s 148 values make its DETERMINISTIC the strongest row here; `idaac`'s 4–8
make its NONDETERMINISTIC the weakest — though for a *disagreement* verdict a thin fingerprint is
sufficient, since the values it did capture demonstrably differed. Its trials even produced
*different value counts* (8 / 6 / 4), which happens when the logged numbers themselves change.

**`sgqn` is the finding, and it is sharp because of its neighbours.** `drqv2` and `svea` run
through the *same* `train.py`, on the same machine, in the same session, and reproduce bitwise;
`svea` even shares `sgqn`'s Places365 overlay augmentation. So this is not the platform, not the
trainer, and not the augmentation — it is something in SGQN's own additions, and its two same-seed
runs differ at 1,300 frames.

**Three hypotheses tested and all rejected, recorded so nobody pays for them twice.** SGQN's
distinguishing machinery is guided backprop (`RL-ViGen-upstream/rl_utils.py:59`) and a quantile
mask over the resulting attribution (`rl_utils.py:77`). Each part was reproduced in isolation on
this backend and run twice on identical weights and inputs:

| candidate | result |
|---|---|
| gradients w.r.t. the **input** (the kernel path no other baseline exercises) | identical, max abs diff **0.000e+00** |
| gradients w.r.t. **weights** (control) | identical, max abs diff **0.000e+00** |
| captum `GuidedBackprop`, hooks and all | identical, max abs diff **0.000e+00** |
| the 0.95-**quantile mask** over the attribution | identical, **0** differing pixels |
| values sitting exactly *on* the quantile (ties would make `>=` fragile) | **0** |

Scope, because it bounds the conclusion: these ran against a small stand-in conv stack, not
SGQN's actual encoder and critic, so they eliminate the *mechanisms* rather than the module. What
remains untested is the attribution predictor's own optimiser and how SGQN's agent composes these
parts — and neither should be guessed at in prose.

**Read these together with the CPU result above, because they look contradictory and are not.**
`sgqn` reproduces on CPU, so its cause *is* something about MPS — while every MPS mechanism
listed here reproduced bitwise. Both hold: the eliminations were run against a **small stand-in
conv stack**, and they rule out those mechanisms *at that scale and shape*, not in SGQN's real
encoder and critic. What survives is "some operation on SGQN's actual MPS path is not
reproducible, and it is none of the four reproduced in miniature".

The eliminations still earn their place: the obvious story was "it takes an unusual kind of
gradient, and that kind of gradient is nondeterministic on MPS", and the *second half of that
sentence is measurably false*. Which is why the CPU result is stated as "the backend" and not as
"guided backprop".

**The next experiment is one command and it splits the space in half**: run the same pair with
`device=cpu`. Deterministic on CPU means an MPS kernel somewhere in SGQN's path and nothing about
the algorithm; nondeterministic on CPU means the algorithm itself — a hook order, a set iteration,
a tie in the quantile mask — and the platform is innocent. Not run here only because the machine
was already carrying two other workloads and the owner has asked that swap not be exhausted.

**Three of seven do not reproduce, and there are at least two distinct causes.** The first
tempting story — "the baselines that add machinery beyond their host algorithm are the ones that
drift" — does not survive `ibac_sni`, which adds an information bottleneck and SNI's two-pass
update and is the *most* reproducible row in the table.

The second was **parallel collection**. It does not survive either:

| | single env | 4 envs |
|---|---|---|
| **reproduces** | `drqv2`, `svea`, `curl`, `rad`, `soda`, `ibac_sni` | `ctrl` |
| **does not** | `sgqn`, `alda` | `idaac` |

`ctrl` runs four envs and reproduces; six single-env baselines reproduce and two do not. Env
count sorts the table in neither direction, and `idaac` fails at one process as well as four.

**The trainer is ruled out, and this is the sharpest row.** Five baselines share
`RL-ViGen-upstream/train.py`, one env each, same machine, same session: `drqv2`, `svea` and
`curl` reproduce bitwise; `sgqn` and `drq` do not. A shared loop producing both outcomes means
the cause lives in the **agent**, not in the loop around it — and the CPU results below confirm
exactly that for both failures.

So no structural property available here — trainer, env count, framework, backbone, or presence
of an auxiliary network — sorts these eleven into the two columns. **Nondeterminism is
baseline-specific**, and at a third of the table it is common enough that "seeds control runs"
cannot be assumed for the set.

**Follow-ups: three one-variable interventions.** Each changes exactly one thing against an
otherwise identical recipe:

| baseline | intervention | result | reading |
|---|---|---|---|
| `drq` | MPS → **CPU** | **reproduces** (`bca44cdd…`, both trials) | the **backend** is the cause |
| `sgqn` | MPS → **CPU** | **reproduces** (`9cad030e…`, both trials) | the **backend** is the cause |
| ~~`ctrl`~~ | 4 envs → **1** | ~~still differs~~ **void** — `ctrl` reproduces at both | there was nothing to explain |
| `idaac` | 4 processes → **1** | ~~reproduces~~ **RETRACTED — see below** | nothing established |

> ### Retraction, same day: `idaac` at one process does **not** reproduce
>
> This entry said for several hours that `idaac` reproduces at one process and that parallel
> collection is therefore its cause. **That was wrong, and it was published** — here, in
> [C52](#c52), in `MILESTONES.md`, and in commit messages.
>
> The verdict was an artefact of the fingerprint. `probe_determinism.fingerprint_stdout` required
> **three or more decimal places**, and `idaac` logs `test/mean_episode_reward` as `1.27`. Two
> one-process runs agreed on the six high-precision values the filter kept and differed on the
> ones it discarded. Caught by comparing two runs' **complete** logged output, 6 of 21 rows
> identical, first divergence `test/mean_episode_reward` 1.6 vs 1.2 — and caught only because the
> C28 wiring prompted a before/after behavioural check that read the whole dump instead of the
> fingerprint.
>
> **The error direction is systematic, not incidental.** A fingerprint over a *subset* of output
> can produce false agreements and never false disagreements. So every NONDETERMINISTIC verdict in
> this entry stands — a disagreement is positive evidence — and every DETERMINISTIC verdict is
> only as strong as the share of output behind it. That is why `n_values` sits in the table.
> **`rad` (4 values) and `soda` (4 values) are the two rows now in the same doubt as `idaac` was**;
> the CSV-fingerprinted rows (`drqv2`, `svea`, `curl`, `drq`) hash whole columns at full precision
> and `ibac_sni` (148), `ctrl` (118) and `alda` (60) are rich enough to trust.
>
> ### Second retraction, opposite direction: `ctrl` **does** reproduce
>
> This entry also reported `ctrl` NONDETERMINISTIC twice — at four envs and at one — and that is
> wrong too. `ctrl` prints `PPO took 1.134254 seconds`, **number before the keyword**, and absl
> line prefixes carry `07:27:14.912374`. The wall-clock filter matched keyword-then-number, so
> neither was removed and both entered the fingerprint. Re-analysing the same stored logs with
> all wall-clock excluded: **510 of 510 values identical** between same-seed trials at one env,
> 54 of 54 at four, with the cross-seed control still firing.
>
> **The two retractions bracket the instrument and point opposite ways.** Reading too *little* of
> the output produced a false agreement (`idaac`); reading the *clock* produced a false
> disagreement (`ctrl`). So the earlier claim in this entry — "a fingerprint over a subset can
> only produce false agreements" — was true of the defect it described and **wrong as a general
> statement about this instrument**, which was capable of erring in both directions at once.
>
> Re-analysed with wall-clock fully excluded, from logs already on disk: `alda`
> (408 values) and `idaac` (47 at four processes, 67 at one) remain NONDETERMINISTIC. `rad`,
> `soda`, `ibac_sni`, and the CSV-fingerprinted rows are unaffected — timing contamination can
> only manufacture disagreement, so it cannot have created their DETERMINISTIC verdicts.
>
> The extractor now drops both wall-clock forms, pinned by tests.

> The extractor now keeps every decimal number, and **all three affected rows were re-measured
> with it**:
>
> | row | before | after | |
> |---|---|---|---|
> | `rad` | DETERMINISTIC, 4 values | **DETERMINISTIC**, 26 values | verdict survives |
> | `soda` | DETERMINISTIC, 4 values | **DETERMINISTIC**, 93 values | verdict survives |
> | `idaac` @ 1 proc | "DETERMINISTIC", 6 values | **NONDETERMINISTIC**, 67 values | verdict overturned |
>
> So the defect changed exactly one conclusion, and the two rows that shared its risk were checked
> rather than assumed safe. `idaac`'s cause is **not** identified: it fails at one process as well
> as four.

**What survives.** `drq` and `sgqn` reproduce on CPU, so for both the cause is the MPS backend —
both are CSV-fingerprinted, full-precision, and unaffected by either defect above. `ctrl` never
had a defect to explain. `idaac` fails at one process as well as four, so parallelism is excluded
for it, and it cannot be moved to CPU without a clone deviation. `alda` is untestable on CPU for
the same kind of reason.

**The prediction was made, then tested, then held.** After `drq`'s result this entry said `sgqn`
was the next candidate because it runs the same `train.py` on the same backend, and priced the
test at 45–75 minutes of CPU trials. Run: **43 minutes per trial**, and `sgqn` reproduces on CPU.
So two of the five nondeterministic baselines have the same identified cause, and it is the
accelerator rather than anything in the algorithms.

Worth stating precisely, because it is narrower than "MPS is nondeterministic": `drqv2` and
`svea` run on **the same backend through the same trainer** and reproduce bitwise. So it is
particular operations in `drq`'s and `sgqn`'s paths that are not reproducible on MPS, not the
backend as such — and §7b's earlier measurement that conv input- and weight-gradients are bitwise
identical on this backend is consistent with that, rather than contradicting it.

**A practical consequence with a real price.** `drq` *can* be made reproducible by running on CPU,
at **774s against 133s** — 5.8×, which multiplies across a 5-seed budget.

For `idaac` that is a mechanism rather than a correlation: it can be **made** reproducible by
choosing a process count, at a throughput cost (368s against 141s for the same work), and the
choice becomes declared rather than an accident of a launcher default.

For `ctrl` it removes the only hypothesis on offer. Its fingerprint at one env is 802 values, the
widest in this whole exercise, so the disagreement is not a thin-signal artefact. `ctrl` is also
JAX, where a seeded computation is normally reproducible, which makes an unseeded source — a
Python-level `random` call, an unkeyed PRNG use, an iteration order — more likely than a kernel.
Not identified here.

**What is left is per-baseline and unidentified.** The one visible commonality among `sgqn` and
`alda` is a second network trained on its own objective with its own optimiser (SGQN's attribution
predictor at `aux_lr=0.3`; ALDA's autoencoder and quantiser). `ibac_sni`'s bottleneck is *inside*
the policy rather than a separate module, which would be consistent — but one consistent
observation across two baselines is a thing to test, not a finding, and it is recorded here only
so the next person tests it rather than rediscovers it.

**What it costs.** A nondeterministic baseline cannot be re-run to reproduce a reported number,
so for `sgqn`, `drq`, `idaac`, `ctrl` and `alda` a seed names a *distribution* rather than a run. Their variance is at
least the other baselines' and is unmeasured; [C18](#c18)'s seed budget is derived from a
`drqv2` pair (verified: `_target_: algos.drqv2` in both runs' saved hydra config) and does not
transfer to them. It also bears on [C50](#c50): IDAAC is the baseline whose mechanism is already
in question, and it is now also the one whose runs cannot be reproduced — so any future claim
that its instance term does or does not matter needs more seeds than the others, not fewer.

**`ppg` cannot be asked this question at all, and that is the second finding.** Its trainer takes
`interacts_total=100_000_000` as a `train_fn` default with **no CLI flag** — nine `add_argument`
calls and not one of them a step budget — so `smoke_all.sh` caps it with `timeout` instead. A
wall-clock-capped run does a different amount of *work* than its twin whenever machine load
differs, so two trials' fingerprints differ for reasons that have nothing to do with RNG.
Comparing them measures the scheduler. The probe now refuses (`UNBOUNDED_RUN`) rather than
reporting a scheduler artefact as nondeterminism.

Combined with screen (a), `ppg` has **neither a seed knob nor a step budget**. It cannot produce a
run that is reproducible *or* bounded, so it cannot contribute a comparable row without a clone
deviation — which would be an ENABLES-class change, not a fix.

**A DETERMINISTIC verdict here does not mean a run is reproducible.** This is 1,300 frames, and
the counter-example is already in this register: `drqv2` reproduces **bitwise** at this scale, and
[C41](#c41) measured two `drqv2` runs at the same configuration and seed agreeing exactly to
frame 10,000 and then disagreeing by up to 48.5% on the way to 100k. So the six DETERMINISTIC
rows establish that the seed *reaches* the run and that nothing gross is unseeded — they do not
establish that a production-length run can be repeated. For the five NONDETERMINISTIC rows the
failure is visible within a few hundred frames, which is strictly worse, not different in kind.

The sweep is complete: eleven baselines measured, `ppg` excluded as unmeasurable. Raw trials are
in `artifacts/determinism-2026-08-19/` (untracked, per this repo's `.gitignore`).

**Verified independently of the probe's own reporting**: all **18** verdicts (eleven baselines
plus seven follow-up and re-measurement runs) were re-derived from the stored fingerprints alone —
`a == b` for determinism, `c != a` for a live control — and agree with what the probe wrote, with
**zero disagreements**. The cross-seed control fired in every single row.

**And that check could not have caught either retraction below**, which is the useful thing about
it. Both retracted rows re-derive *correctly* from their own fingerprints: `verdict()` reported
exactly what its input showed, every time. The faults were upstream of the logic, in what the
fingerprint sampled — too little of the output in one case, the clock in the other.

So this verification establishes that **the decision rule is sound** and says nothing about
whether **the evidence fed to it was sound**. Two different questions; both wrong published
claims came from the second, and a re-derivation from the same inputs can never reach it. The
check that did reach it was comparing two runs' complete output by hand.

**Decision** Test it rather than assume it, in two screens — source first because it is cheap and
catches the strong failure, then runs because reading cannot establish determinism. Then one
intervention per surviving hypothesis, rather than a paragraph of plausible causes.

**Effect** The gap this entry names is closed: determinism is now measured for all twelve, where
before it was checked for none. What the measurement found is **not** reassuring and is now
[C52](#c52)'s problem rather than this entry's: five baselines do not reproduce, `ppg` cannot be
asked, and the 5-seed design assumed all twelve would. Three by-products that outlive the
question: `ppg`'s missing step budget, [C49](#c49)'s inert env seed, and the instrument-error
record in screen (a), where three separate blind spots all understated seed control — the
direction that invents a defect. The order was chosen to cover the five *untested trainers* first — `drq`/`curl` share
upstream's `train.py` and `soda` shares dmc_gb's, so they carry less new information per hour.
The env half of screen (b) is [C49](#c49).

### C21 — No CUDA run exists {#c21}
**Class** DESIGN-GAP · **Status** BLOCKED — on a *slot*, no longer on access

Every green in this project is MPS-with-shim. The shim announces its float64 downcast and reports
`is_cuda` for MPS tensors, and [C4](#c4) names one clone where local and CUDA genuinely differ.

**Access is solved and verified 2026-08-17.** `ccm-intro/docs/compute-yandex-datasphere.md` §7
carries the working path for the `arsen4ikvar` account: cloud `b1go0t4nfb593op2lbfd`,
organization `bpfqghefpv16ugussqck`, community `bt19h0cm8nqhr7489r9o`, **project
`bt12q57tmrs03pnt8drc`**. The `default` `yc` profile is that cloud and mints an IAM token; the
separate `datasphere` Python CLI is installed. `datasphere/README.md` records a bring-up that
has already run end to end. **The earlier note that this needed "a project id" was wrong** — the
id was in the workspace docs.

**A job is built and ready**: `datasphere/{build_payload_clone.sh,train_fps_job.sh,cfg-train-fps.yaml}`,
commit `9895154d`. It runs SVEA on Door through `runnable/_launch/rlvigen.sh` — the *same* entry point
as locally, so the number is comparable by construction — behind a CUDA gate and a GL gate, on
`gt4i.1` (interruptible T4, the cheaper of the two permitted types).

**What actually blocks it: the two-parallel limit is full.** Two jobs were EXECUTING at check time
(`kage-lrstab`, `kage-symtriple`, both created 2026-08-17 ~11:45), and they belong to a different
project. The owner's constraint is *never more than two parallel DataSphere runs*, so nothing was
submitted and nothing of theirs was touched.

**Two measured facts that change what CUDA is worth here**, both already in the workspace:

- `datasphere/README.md`: **77.9 env steps/s on gt4.1** — *slower* than this laptop's ~100/s,
  because stepping is CPU-bound (physics ~88%, render ~12%) and gt4.1 has 4 vCPU. So env stepping
  is a **hard floor of ~3.9 h per 1.1M-frame run** no matter how fast the GPU is, and the lever is
  packing runs per box rather than a bigger GPU.
- `ccm-intro/docs/compute-yandex-datasphere.md` §7: a visual-RL workload measured **378 steps/s on
  a T4 against 212 on an M2 Pro — 1.78×**, with the explicit conclusion *"benchmark before
  budgeting: here it turned a 'buy the GPU hours' plan into 'don't'."*

Together those say the sweep budget must not be extrapolated from the local 3 FPS ([C34](#c34)),
in either direction. That is exactly what the prepared job measures.

### C22 — The mutation harness: inoperable, then pointed at the metrics {#c22}
**Class** DESIGN-GAP · **Status** RESOLVED

**Decision** 45 passing metric tests is an assertion about the tests. Point the existing mutation
harness at `scripts/metrics.py` so it becomes evidence they constrain the metrics.

**Attempt, and it found two things before it found any mutant.**

1. **The harness could not run at all.** `make_copy` used `copytree(symlinks=False)`, which
   *follows* every link — and `runnable/alda/dmcontrol_generalization_benchmark/datasets` is
   dangling, so one broken symlink aborted every run. The clones arrived after that file was
   written, so nothing surfaced it until something tried to use it. Fixed by preserving symlinks
   as symlinks, which also avoids copying what they point at; a copy is 140 MB.
2. **Then the sanity mutant refused to measure.** The unmutated copy failed
   `test_state_script_names_which_reference_a_descent_figure_came_from`, which passes in the
   working tree. Cause, after two wrong guesses of mine: `scripts/state.py:84,86` cite
   `../gen-rebuttal/...`, **a sibling project outside this repository**, so the two-hop source
   tag cannot be computed in any copied tree. Structurally inapplicable there rather than
   failing — now a `skipif` naming the missing input. **Without that sanity check every "kill"
   afterwards would have been measured against a broken tree**, which is the vacuous
   verification it exists to prevent.

Also added an optional per-mutant `oracle`. A scoped oracle makes a claim *sharper* —
"`test_metrics` catches this" says more than "the suite does" — and keeps a mutant cheap enough
to run often. Not weaker: a scoped oracle that fails to kill is a survivor exactly as before, and
the sanity run still uses the whole suite.

**Effect** — six mutants on `scripts/metrics.py`, each undoing one documented design decision.
**5 killed, 1 survived.** M19 Wilson→normal-approx, M20 single-frame-measurable, M21
`explained_variance` 0.0-not-nan, M22 TV distance unnormalised, M23 saturation misses the
boundary — all killed. **M24, `approx_kl` default k3→k1, survived.**

M24 is the reason to do this at all: every test passed `estimator` explicitly, so **nothing
constrained the default**, and a change to it would have shipped in silence — on the one metric
whose entire justification is that k1 can go negative. A test now exercises the default; M24 is
killed.

Commit `2e79f3bb`.

### C29 — The protocol hash certifies comparability across environments we document as different {#c29}

**Class** FALSE-CERTIFICATION · **Status** OPEN

`Protocol.hash()` prints beside itself *"two numbers are comparable iff this matches"*. It hashes
benchmark, task, `env_commit`, `env_patches`, robot, controller, observation, episode, training,
evaluation, scoring, and `block("provenance", ["code_commit", "weights_source"])`.

**It does not hash the dependency versions the run executes against** — torch, numpy, mujoco,
procgen, gym. And this project has already established, in its own words, that those are not
incidental:

- `compute/datasphere/requirements.txt`: *"**mujoco==2.3.7 IS THE POINT OF USING DATASPHERE.**
  RL-ViGen's texture modder reads `MjModel.tex_rgb`, removed in mujoco 3.0, so every eval-\*
  regime needs 2.x."*
- `compute/rlvigen-cuda-smoke/smoke.py`: on Kaggle (cp312) no mujoco 2.x wheel exists, so it
  falls through `MUJOCO_CANDIDATES = ["mujoco<3.3", "mujoco==3.1.6", "mujoco==2.3.7"]` and lands
  on 3.2.7 — which *has* `MjData.qM` so robosuite 1.4.0 runs, but *lacks* `MjModel.tex_rgb`, so
  **"on THIS platform the train regime is the most that is reachable."**

So a Kaggle run and a DataSphere run can differ in whether the visual perturbation — the entire
manipulated variable — is executable at all, **and carry the identical protocol hash.** The
knowledge is present and well reasoned; it lives in comments and requirements files rather than
in the certification that claims to govern comparability.

**Blast radius** Every recorded and future result. This is the same shape as
[C1](#c1) and [C23](#c23): a hashed field asserting a property the system does not have.

**Evidence** Local today: torch 2.13.0, numpy 2.4.6, mujoco 2.3.7, gym 0.25.2 — recorded nowhere
that a result would carry. Read from `rlgen/protocol.py` and the two compute configs.

**Options**
1. **Add a resolved dependency set to the hash.** Strongest, and it invalidates every recorded
   protocol hash the moment any dependency moves — including patch bumps that change nothing.
2. **Record versions alongside the hash without hashing them** — stamped into every run's output,
   so two numbers can always be checked for environment equality even though the hash does not
   enforce it. Cheaper, does not churn hashes, but comparability stays a manual check.
3. **Hash only the dependencies shown to matter** (mujoco above all, since it gates whether a
   regime runs). Targeted, and requires justifying the boundary — a judgement, not a rule.

*My reading: (2) now, because it is additive and blocks nothing, with (3) as the considered
version once there is a result to protect. (1) reads correct and would make the hash churn on
irrelevant upgrades. But this is a judgement about what the hash is for, so it is yours.*

**Pinned by** unpinned

**Half closed 2026-08-19, and the half left open is the one this entry itself calls a judgement.**

What was straightforwardly false is fixed: the card printed *"two numbers are comparable iff this
matches"* beside a hash that omits the dependency versions. It now prints **"NECESSARY, not
sufficient"**, says which omission it is referring to, and carries a `runtime:` block with the
resolved versions of `torch`, `numpy`, `mujoco`, `robosuite`, `gym`, `gymnasium`, `dm-control` and
`jax` — read from package metadata, so writing a card costs nothing and cannot fail on a machine
where a dependency is installed but unloadable. **Two cards with the same hash and different
`runtime` are now visibly not interchangeable**, which was the actual defect: the knowledge lived
in requirements files rather than in anything a result carried.

This is **option 2**, and it was chosen because it is required under options 1 and 3 as well —
nothing can be hashed that is not first captured — and because it forecloses none of them.

**Still yours to decide: whether the versions enter the hash** (options 1 and 3). That is the
boundary question, and this entry's own wording is why it was not decided here: hashing
everything churns every recorded hash on a patch bump that changes nothing, and hashing only what
matters "requires justifying the boundary — a judgement, not a rule".
`tests/test_runtime_stamp.py` pins the current state by monkeypatching the versions and asserting
the hash does **not** move; if that is ever intended, the test fails and must be rewritten in the
same commit, exactly as [C1](#c1)'s tripwire required.

**DEFAULT SET, 2026-09-03: the hash keeps certifying CODE, the environment is certified ALONGSIDE
it, and the "iff" wording goes — because it is the false part.** Three options were open: hash the
dependency set into `Protocol.hash()`, record it beside the hash, or leave it. Hashing it in is
wrong, and the reason is what the hash is *for*: it answers "is this the same protocol", and a
protocol that changed because `numpy` went 1.26.4 -> 1.26.5 has not changed. Fold the environment
in and the hash churns on upgrades that alter nothing, which trains everyone to ignore a mismatch —
the failure this entry is trying to prevent, arrived at from the other side.

**What the runner already produces makes the second option nearly free.** Every job returns
`resolved_packages.json` (the actual resolver output, not the requested pins) and
`environment.json`, and as of [C95](#c95) every record carries `native.recorded_on` with host,
system, machine and `MUJOCO_GL`. So the *environment* half is captured per run; what was missing is
that the hash **claims to cover it**.

**The correction is therefore to the sentence, not the algorithm.** `Protocol.hash()` must stop
printing *"two numbers are comparable iff this matches"* and print that a matching hash means the
same **protocol**, and that comparability additionally requires the same resolved environment and
the same platform — with a pointer to where both are recorded. An "iff" that is not an "if" is a
false certification whatever it hashes, and C95 is the proof that the missing half can be worth
12-14x. **What would overturn this**: a demonstrated case where a dependency version alone changes
a reported number, which would make the environment part of the protocol rather than beside it.

### C30 — The comparability contract is enforced against the superseded port, not the clones {#c30}

**Class** DESIGN-GAP · **Status** OPEN

**The contract itself is not stale.** `rlgen/protocol.py` is live and load-bearing:
`Protocol.env_patches` pins P1–P13 against the vendored tree the clones actually run,
`OBSERVATION_GEOMETRY` describes the twelve, and `time_limit_handling` is a statement about the
clones ([C1](#c1)). That file is current.

**What is stale is what enforces it.** `tests/test_contract.py` (39 test functions) imports
`rlgen.registry`, `rlgen.agents`, `rlgen.envs`, `rlgen.replay` — the **superseded port's**
implementation, not `runnable/`. Its `test_every_runnable_baseline_respects_the_deterministic_flag`
means *runnable within `rlgen`*; `rlgen/registry.py`'s own docstring refers to the port's
`train.py` and `plot.py`. So the contract that guarantees comparability is checked against agents
that will not produce any reported number.

**The wider shape, measured** — `python scripts/test_inventory.py`, which classifies by *which*
`rlgen` module a file imports rather than by whether it mentions `rlgen` at all:

| target | 2026-08-17 | 2026-08-18 | 2026-08-19 | **2026-08-27** | constrains |
|---|---|---|---|---|---|
| **CLONE** | **20 (6%)** | **30 (8%)** | **94 (18%)** | **136 (20%)** | the twelve that produce reported numbers |
| CONTRACT | 7 (2%) | 7 (2%) | 11 (2%) | 23 (3%) | `rlgen/protocol.py` — live, used by the clone era |
| **PORT** | **236 (71%)** | **236 (59%)** | **238 (46%)** | **242 (35%)** | the **superseded** `rlgen` implementation |
| STANDALONE | 71 (21%) | 125 (31%) | 177 (34%) | 292 (42%) | metrics, docs, register, packaging |
| | 334 total | 398 total | 520 total | 693 total | |

**The 2026-08-27 column changes what the decision is about.** In eight days the PORT count moved
**+4** — from 238 to 242 — while the suite grew by 173 tests. Port-facing coverage is **frozen, not
growing**, and its share is falling by dilution: 71% → 35%. Nobody has been adding to it since the
approach changed, which is the correct behaviour and was never decided.

So the open question is no longer *"is the contract enforced against the wrong thing?"* — it is,
and the answer is not in dispute. It is **whether 242 static tests are worth retargeting at all**,
against a trend that retires them without anyone spending a day on it. Retargeting is the expensive
option and it competes with adding clone-facing tests that do not exist yet; leaving them is free
and costs only the risk that someone reads a green suite as covering the clones — which is exactly
what the project `CLAUDE.md` already warns about in its opening paragraph, and what
`scripts/test_inventory.py` exists to make visible on demand.

The 2026-08-19 column moved for two different reasons and they should not be pooled. CLONE gained
from [C20](#c20)'s seed audit, which reads all seven clone trees and is genuinely clone-facing.
STANDALONE gained from tests for the instruments that audit *this repository* rather than the
baselines. **PORT is still 238 functions in absolute terms** — its share falls only because the
denominator grows, which is the same arithmetic the note below warns about. Nothing has been
retired.

*Two columns because one column was already wrong.* The 2026-08-17 figures were quoted in three
places and one session's work invalidated them: `tests/test_scene_coverage_contract.py` added ten
clone-facing functions, moving PORT's share from 71% to 59% **without a single port test being
removed**. The absolute port count did not move at all. A share is a ratio and reads like a fact,
which is why `SYSTEM.md` now cites `python scripts/test_inventory.py` instead of transcribing it.
**The gap is still the finding**: 8% is not materially better than 6%.

**And the CLONE column is an upper bound, discovered by watching it move.** Later the same day it
read 45, then 46 — but `classify()` counts any file *mentioning* a `runnable/` path, including
test data. Two instrument tests written that evening (`test_greenmark.py` listing
`runnable/_shim/...` to assert it classifies as code, `test_test_inventory.py` embedding
`runnable/idaac` in a synthetic fixture) added **15 between them while constraining no clone at
all**, and the test that pins this limitation added a sixteenth by naming a path in its own
docstring. Documented at source rather than tightened: every sharper rule tried also matched
those files, and a detector wrong unpredictably is worse than one wrong in a stated way. **Read
CLONE as "at most this many", which makes the real gap wider than any column above.**

*A first pass put PORT at 147 and STANDALONE at 160. That was a regex fault: the parity suites
import `from rlgen.algos.ppg.algo import Learner`, and a pattern anchored on one segment before
`" import"` matched none of them, filing ~80 port-era tests as standalone. Fixed and re-run;
recorded because the first number was wrong in the flattering direction.*

Counts are test **function definitions**, not what pytest collects after parametrisation.

**The live coupling is far smaller than the test count suggests.** Clone-era code — `scripts/`,
`setup/`, `runnable/_launch/` — imports from `rlgen` exactly **twice**: `setup/install.sh:54`
(`rlgen.envs`, an installer smoke check) and `tests/test_observation_geometry.py:35`
(`rlgen.protocol.OBSERVATION_GEOMETRY`). So the clone pipeline is essentially independent of the
port except for `protocol.py`, and option 1 below is a build rather than a migration.

Some `rlgen`-touching tests are genuinely live regardless of the port — `test_real_env.py` builds
real environments, `test_eval_identity.py` exercises the eval regimes, `test_contract.py`'s
protocol assertions constrain a live object. Others (`test_ppg_storage`, `test_ctrl_parity`,
`test_ibac_sni_base_parity`, `test_reward_normalizer`, …) validate port implementations the clone
approach replaced. **Which is which has not been sorted**, and that is part of this item.

**Blast radius** "412 tests green" is the sentence most likely to be trusted about this project,
and most of what it covers is not what produces results. This is not an argument that the tests
are worthless — the port-era tests bought the audit findings that justified the clone approach —
but they are **reassurance about a different thing than a reader assumes.**

**Evidence** import classification above; `rlgen/registry.py:1-25`; `tests/test_contract.py:18-22`.

**Options**
1. **Rebuild contract enforcement against the clones.** Highest value, and it is what would make
   the contract mean what it says. Also the largest job, and it must go through each clone's own
   entry point rather than a shared harness — twelve times, hermetically.
2. **Sort the existing tests into live / port-era and label them**, so the green figure can be
   read honestly, without building anything new yet. Cheap, and strictly an improvement to what
   a reader can conclude.
3. **Accept and declare.** State plainly wherever the test count appears that it covers the port
   and the shared protocol object, not the twelve clones.

*My reading: (2) first, because it is cheap and makes the current claim honest, and it produces
the inventory that (1) would need anyway. (1) is the real fix and is a foundation-sized job, not
a cleanup. Not mine to schedule.*

**Pinned by** unpinned

**DEFAULT SET, 2026-09-03: the gap is closed in substance and the entry stays open only for the
prose.** When this was written there was no clone-era audit. There is now:
`scripts/audit_comparability_seam.py` reports per axis, per baseline, and — the part that matters —
whether each fact is **DERIVED** from code today or **RECORDED** from the document that derived it
once, with `tests/test_comparability_seam_audit.py` behind it. [C76](#c76) is its result. So the
enforcement this entry says is missing exists and runs.

**What has NOT been done is retiring the prose it replaced.** `COMPARABILITY_CONTRACT.md` §1–§10
still describe the `rlgen/` port, carry 31 references to it, and sit above the newer sections
(§5b–§5d, added today) that describe the clones. The file warns about this at its head, which is
the minimum and not the fix.

**The default: keep §1–§10, keep the warning, and treat the seam audit as the authority.** Deleting
them would destroy the record of how the seam was established once, which [C76](#c76) explicitly
depends on. The residual is a documentation ordering problem, not an enforcement gap, and it is now
labelled as such: **the enforcement question is answered; the reading-order question is not.**
**What would overturn this**: the seam audit going stale in the way §1–§10 did — which is exactly
what its DERIVED-versus-RECORDED column exists to make visible, so the guard against the repeat is
already inside the replacement.

### C31 — The ceiling, established from the benchmark's own published results {#c31}
**Class** DESIGN-GAP · **Status** RESOLVED

**Decision** bound the ceiling from the literature before spending compute, since [C17](#c17)
established a floor of 0 but said nothing about what is reachable.

**Attempt** the cheapest possible: `RL-ViGen-upstream/results/evaluation_score.xlsx` was already
in the tree. Read by `scripts/rlvigen_reference.py` rather than transcribed, because a number
retyped into a document is a number that can drift from its source. Sheet `Robosuite`, 5 seeds, three regimes, seven methods, on door and lift.

**Effect** — **there is a ceiling and it is high, but not for every method.** Mean episode return
over their 5 seeds:

| method | door Easy | door Hard | lift Easy | lift Hard |
|---|---|---|---|---|
| DrQ-v2 | 3.6 | 2.0 | 1.0 | 1.2 |
| CURL | 6.6 | 2.2 | 0.2 | 0.4 |
| DrQ | 14.0 | 3.8 | 1.4 | 1.0 |
| SVEA | 268.8 | 62.4 | 43.0 | 8.4 |
| SRM | 337.2 | 31.2 | 69.2 | 0.4 |
| PIEG | 387.2 | 87.0 | 96.4 | 7.8 |
| SGQN | **391.4** | 160.4 | 31.6 | 7.2 |

**The system-internal split is unambiguous and needs no comparison to us:** within RL-ViGen's own
table, DrQ-v2 / CURL / DrQ score one to two orders of magnitude below SVEA / SRM / PIEG / SGQN,
and in single digits on lift. Three of the five RL-ViGen baselines this project clones are
published by the benchmark's own authors as scoring at that level. See [C32](#c32).

**And a reproduction target now exists.** SVEA and SGQN are among our twelve, with 5-seed means
and spreads to hit — door Easy 268.8 (sd 136) and 391.4 (sd 95). That is the calibration
run: if the authors' own code on the authors' own benchmark does not land near the authors' own
number, nothing downstream means anything.

**The caveat, and it is my own rule turned on my own finding.** Our floor (door 1.63 mean / 6.93
max; lift 6.56 / 34.65) was measured under *our* configuration. Theirs was produced under
*theirs* — budget, action_repeat, robot, scene and episode length are not verified to match.
[`RESEARCH-FRAME.md`](RESEARCH-FRAME.md) states that two numbers from different systems are not
the same quantity until shown to be, and that applies here: the numeric closeness between their
DrQ-v2 and our random policy is **suggestive and unverified**, not established. The
system-internal split above is what stands on its own.

> **One piece of that caveat was closed 2026-08-25 by an external reviewer working from the public
> repository alone.** The open question included *which condition* the spreadsheet's "(Easy)" column
> actually is — we had been treating it as the benchmark's generalisation setting because the label
> says so. They cross-checked it against the paper's own **Figure 19**: aggregating the
> `Robosuite` sheet's per-seed cells across door/lift/twoarm for DrQ-v2 gives **48.33**, matching
> the "48" plotted for DrQ-v2 in that figure. So the spreadsheet column and the figure are the same
> condition, and it is the one this project calls `eval-easy`. Independently re-derived from
> upstream artifacts without sight of our notes.
>
> **This closes the label question only.** The rest of the caveat is untouched: budget,
> `action_repeat`, robot, scene set and episode length are still verified to match only as far as
> horizon 500, `action_repeat` 1, Panda, OSC_POSE, 84×84 and the Easy level. "Their column means
> what its name says" was worth establishing precisely because it had been assumed.

Commit `2552e184`. **Spawned [C32](#c32), [C33](#c33).**

### C32 — Three of the twelve are published as not learning these tasks {#c32}
**Class** INHERITED · **Status** MONITORED

DrQ-v2, CURL and DrQ score 0.2–14.0 mean return on door/lift across every regime in RL-ViGen's
own results ([C31](#c31)), against 268–391 for the methods that work. All three are in our
twelve, via `RL-ViGen-upstream/algos/`.

**Why this is `INHERITED` and not a defect**: it is a property of the benchmark and those methods
on these tasks, published by the people who built both. Nothing is wrong with our setup, and
nothing here proposes dropping them.

**Blast radius — on expectations, not on code.** A twelve-row table in which those three sit near
zero would be **reproducing the benchmark's own result**, not failing. That is worth knowing
*before* the table exists, because the natural reading of three near-zero rows is that our
harness broke them — and this is the evidence that it did not. It also means a comparison across
all twelve has, in effect, fewer discriminating rows than twelve.

**Not verified**: whether their non-learning persists at a larger budget, and what budget their
table used. That is in the paper rather than the spreadsheet.

### C33 — Return is the reported endpoint; success rate stays emitted {#c33}
**Class** DESIGN-GAP · **Status** RESOLVED

`evaluation_score.xlsx` reports **episode return** for robosuite. This project's primary endpoint
is **success rate** — `docs/PART2-METRIC-INVENTORY.md`, and every number currently on record.

They are not interchangeable and each has a real argument. Success rate is unit-free and
comparable across tasks with different reward scales, which is why it was chosen. Return is what
the benchmark publishes, so it is the only endpoint on which a reproduction can be checked at
all — and [C17](#c17) measured that return has dynamic range on both tasks (door 1.63 → 6.93 even
under a random policy) while success never fired.

**Options**
1. **Report both.** Return for reproduction against RL-ViGen, success rate as the unit-free
   comparison. Costs nothing at collection time — both are already emitted — and doubles what a
   reader can check.
2. **Return as primary.** Aligns with the benchmark and makes calibration direct; gives up
   cross-task comparability and inherits the reward's arbitrary scale.
3. **Success rate as primary, return recorded.** Status quo made explicit; reproduction against
   RL-ViGen then requires a second quantity anyway, which is option 1 in practice.

*My reading: (1). The two answer different questions and the collection cost is already paid.
But which is the headline is a presentation decision, and yours.*


**Decision** owner, 2026-08-18: **report RETURN**; success rate is not dropped and stays emitted.

**Effect** the primary endpoint is now the one RL-ViGen publishes, which is what makes
[C48](#c48)'s anchor possible at all: a reproduction can only be checked on an endpoint the
reference also reports, and success rate is not one. It also matches where the evidence already
is — [C47](#c47) carried its result on return (retention 0.278 / 0.238 with a live control) while
success rate was too sparse to speak (1/90, then 22/90). Success rate is retained because it is
the only unit-free, task-defined quantity available and is now uniform across all twelve
(`tests/test_success_convention.py`), so it costs nothing to keep and remains the better quantity
for any comparison across tasks with different reward scales. Commit `42bb98db`.

**What this obliges.** Return is dense and scale-arbitrary on Door, so every reported return needs
its floor beside it ([C17](#c17)) — a bare return is not readable. And the run-to-run floor from
[C41](#c41) applies to it directly.

## Monitored — known, deliberately not acted on

### C5 — Render resolution {#c5}
**Class** INHERITED · **Status** MONITORED

**Handicap — affects:** rad soda drqv2 svea sgqn curl drq alda ppg idaac ctrl ibac_sni
*three different fields of view across twelve baselines; not equalisable without breaking an encoder or an augmentation*

100→crop 84 (`rad soda`), 84 (RL-ViGen five), 64 (`alda
ppg idaac ctrl ibac_sni`).

> **Attribution corrected 2026-08-25 ([C71](#c71) #5).** This line read "the repo's own rule at
> `arguments.py`". It is not: on the robosuite path `arguments.py`'s `image_size` is **never read**
> — `dmc_gb/src/env/wrappers.py`'s robosuite branch returns before the only call that consumes it.
> The resolution is set by `_launch/dmc_gb.sh:27` exporting `RLVIGEN_IMAGE_SIZE=100`, which patch
> **P6** applies at `robosuitevgb/utils.py:46` over `robo_config.yaml`'s 84. The two mechanisms
> happen to carry the same number, which is why the dead one went unnoticed. **Anyone changing a
> resolution must edit the launcher, not `arguments.py`** — and note what turns on it: at a native
> 84, RAD's `random_crop` becomes the identity and RAD *is* SAC, while SODA's `assert x.size(-1)
> == 100` refuses to run. Five of seven are the reference's own and load-bearing: `nn.Linear(2048,·)`
is hardcoded for 64, `soda.py:51` asserts 100, RAD silently becomes SAC at 84. Different fields of
view. Not equalisable without breaking an augmentation or an encoder. See C3 for the one that is ours.

### C6 — Three action-distribution families {#c6}
**Class** INHERITED · **Status** MONITORED

SAC squashed Gaussian (`rad soda alda`) · DrQv2 tanh-mean + TruncatedNormal (RL-ViGen five) ·
unsquashed Gaussian + env clip (`ppg idaac ibac_sni ctrl`). **Evidence**: at initialisation
**31.8%** of action components are on the box boundary for the third family, **0.0%** for SAC,
**5.5%** for DrQv2 — checked against the closed form 2(1−Φ(1)) = 0.3173. Only the third family's
likelihood disagrees with what the environment executes. The library sweep found this is the
*correct* framing (TorchRL's `DEBUGGING_RL.md`: the clip "should be thought of as part of the
environment"), and that **SKRL gets it wrong** in shipped examples — so our choice has precedent.

### C7 — Discount {#c7}
**Class** INHERITED · **Status** MONITORED

0.99 ×9 vs **0.999** ×3 (`ppg idaac ctrl`), each repo's own default. On a 500-step horizon that
is an effective horizon of ~100 vs ~1000 steps. Equalisable, but it is a hyperparameter change.

### C8 — Learning rate {#c8}
**Class** INHERITED · **Status** MONITORED

1e-4 (RL-ViGen five, matching their paper's Table 6 for Door) · 5e-4 (`ppg idaac ctrl`) · 7e-4
(`ibac_sni`) · 1e-3 (`dmc_gb` actor/critic). A 10× spread, each tuned on other environments.

### C9 — Reward normalisation {#c9}
**Class** INHERITED · **Status** MONITORED

`VecNormalize` on rewards: `idaac`, `ctrl` · internal: `ppg` · none: the other nine. Reported
returns are raw everywhere (`VecMonitor` sits *inside* `VecNormalize`); only the training signal
differs.

### C10 — Input range {#c10}
**Class** INHERITED · **Status** MONITORED

[0,1] ×7 vs **[−0.5,+0.5]** ×5 (RL-ViGen, DrQv2 lineage). Trivially equalisable — but it is their
code.

### C11 — Instance diversity {#c11}
**Class** INHERITED · **Status** MONITORED

Procgen draws a new level per episode; a robosuite scene is fixed for the run. Bears on `idaac`
specifically: `level_seed` is what its order classifier means by "same instance", and that concept
does not survive the move.

### C12 — `ppg`'s evaluation loop is ours {#c12}
**Class** OURS · **Status** MONITORED

`ppg` ships no evaluation entry point at all, so `runnable/_launch/ppg_eval.py` is authored. It
lives *outside* the clone (zero ledger deviations) and reuses everything that could bias a number
— their `get_venv`, `Roller`, `VecMonitor2`, `PpoModel.act`. Ours is only the loop that stops
after N episodes. **Flagged because it is the one evaluation loop where a bug would be ours**, and
therefore deserves scrutiny the other eleven do not.

### C13 — `action_repeat` declared but unread {#c13}
**Class** UNDECLARED · **Status** MONITORED

`dmc_gb/src/env/wrappers.py` and `alda_trainer.initialize_env_dmc` both return before the
`frame_skip=` call. Both launchers pass `1`, which is what the dead knob would have set — so it is
inert *and* would bite silently the moment anyone changes it. Cross-ref D6.

### C14 — `ctrl` invents `_max_episode_steps = 10_000` {#c14}
**Class** UNDECLARED · **Status** MONITORED

`runnable/ctrl/vec_env.py:613`, against a real horizon of 500. Dead on this path; wrong if ever
read. Cross-ref D7b.

### C15 — `ppg` `vec_monitor2` contradicts its own comment {#c15}
**Class** FALSE-CERTIFICATION · **Status** MONITORED

`process()` ORs the success flag from `infos[i]` *before* the `if firsts[i]` branch, folding
post-reset info into the ending episode — the exact thing the comment three lines above says it
avoids. Benign only because a reset is never a success. Cross-ref D5.

---

### C27 — The eval regimes are not a monotone difficulty ladder {#c27}
**Class** INHERITED · **Status** MONITORED

Found while measuring C19, not looked for. **`eval-medium` shifts further from train than
`eval-hard` does** — 0.5897 vs 0.4739 — so the three regimes are not increasing amounts of one
perturbation.

The cause is in RL-ViGen's own config (`envs/robosuiteVGB/robosuitevgb/utils.py:73-90`):
`eval-medium` sets `except_robot=False` and therefore randomises **the robot's own colours**,
while `eval-easy` and `eval-hard` both set `except_robot=True` and leave the robot alone.
`eval-hard` instead adds a video background. They are *different kinds* of shift.

**Resolved as a naming collision, not an anomaly — from the supplemental, recorded in
[C45](#c45).** The paper's difficulty levels are **Easy / Hard / Extreme**, and they map onto the
code's `eval-easy` / `eval-medium` / `eval-hard`. So the code's `eval-medium` *is* the paper's
**Hard**, described there as *"additional complexities of moving light and alterations to the
robotic arm's color"* — which is exactly the `except_robot=False` randomisation measured above.
The ladder is monotone in the paper's own terms; it looks broken only when the code's names are
read as the paper's. **The measurement was right and the interpretation was the anomaly.**

**Blast radius** Any write-up that presents easy → medium → hard as a difficulty axis is making
a claim the input distribution does not support. A method could plausibly score *worse* on
medium than hard for reasons that have nothing to do with robustness ordering. Reporting the
three as an ordered sequence without this caveat would be a real misreading.

**Evidence** `scripts/probe_regimes.py`, table in [C19](#c19). Not investigated further: whether
the *task difficulty* ordering matches the visual one is a separate question needing trained
policies.

### C28 — Full observability: what a run actually emits {#c28}
**Class** DESIGN-GAP · **Status** READY

A run currently emits little more than return and success rate. When something goes wrong at
scale — or when a number looks surprising and has to be defended — that is not enough to say
*why*, and re-running to find out is the expensive way to learn it.

The family-tier metrics exist (`scripts/metrics.py`: `explained_variance`, `clip_fraction`,
`approx_kl`, `effective_sample_size`, `target_network_divergence`) and are tested, but they are
**not wired into any baseline's logging**. That is nine separate logging paths, so nine small
decisions rather than one — and each must go through the baseline's own logger, not a shared one,
for the usual reason.

**Scope, deliberately narrow.** This is about *what a run records about itself*. It is **not** a
results store, a table generator, or any presentation layer — those are downstream of work that
is not finished, and treating them as equivalent to the current build would let reporting
over-prioritise the thing being reported on.

**Why it is `READY` and not urgent.** It needs a slot, not a judgement. But it wants to be done
*before* expensive runs rather than after, because observability added afterwards cannot explain
a run that already happened.

### C34 — Local training: infeasible for a sweep, sufficient for a question {#c34}
**Class** DESIGN-GAP · **Status** MONITORED

**This entry has been corrected twice and both corrections matter more than the original.**

Measured on this M2 Pro, SVEA on Door through RL-ViGen's own `train.py`:

| phase | throughput |
|---|---|
| random policy, no updates (`probe_floor.py`) | ~100 steps/s |
| **training** (median of 67 logged points) | **2.97 frames/s** |

At RL-ViGen's own `num_train_frames: 1100000`, one run is ~102 h and the 120-run design ~12,000 h.

**Correction 1 — "it is not a path" was wrong.** The original text said local training "is not a
slow path to the same place, it is not a path." That is true of a **sweep** and false of a
**question**: three hours on this path took SVEA's eval-easy return from 1.51 to 78.2, which is
[C35](#c35) and the first result this project has. *Infeasible for a sweep* and *infeasible for a
question* are different claims and the entry collapsed them.

**Correction 2 — "the bottleneck is the part CUDA fixes" was too optimistic.** The original
reasoned that the 30× gap between stepping and training must be gradient work, which a GPU
accelerates, so CUDA would deliver a large speedup. **The gradient work is already on a GPU.**
Benchmarked directly, the SVEA-shaped encoder (9×84×84, batch 256, fwd+bwd+step):

| device | per step |
|---|---|
| CPU | 714.5 ms |
| **MPS** | **40.7 ms** — 17.6× |

So MPS is engaged and delivering; ~5 encoder-sized passes per step (SVEA computes the critic loss
on augmented *and* unaugmented observations) accounts for most of the ~330 ms. **The 3 FPS is what
the algorithm costs at this batch size on this device, not a misconfiguration.**

The consequence is the important part: **CUDA's marginal gain here is T4-versus-M2-MPS, not
GPU-versus-CPU.** `ccm-intro/docs/compute-yandex-datasphere.md` §7 measured that comparison at
**1.78×** on a similar visual-RL workload, and `datasphere/README.md` measured T4 env-stepping
*slower* than this laptop (77.9/s vs ~100/s, 4 vCPU, CPU-bound physics). A T4 may therefore take
this from ~3 FPS to single digits, not to tens. **The prepared benchmark job ([C21](#c21)) exists
precisely because that must be measured rather than reasoned about — including by me, twice.**

**Where the real lever is.** Not making one run faster. One run uses ~0.5 of 12 cores and
duty-cycles the GPU, so the lever is **concurrency** — the same conclusion `datasphere/README.md`
reached for the T4 box ("packing several runs per box, not a bigger GPU"). Two concurrent local
runs are in flight to measure whether per-run FPS holds; if it does, throughput is free.

### C35 — The setup learns: established, and what it still does not show {#c35}
**Class** DESIGN-GAP · **Status** MONITORED

SVEA on Door through RL-ViGen's own `train.py`, local MPS, seed 1, `eval-easy` every 10k frames,
10 episodes per point. Run capped at 3 h by a `timeout` I set; log at
`docs/run-svea-door-2026-08-17.log`.

| frames | eval-easy return | SR |
|---|---|---|
| 0 | 1.5073 | 0.0000 |
| 10,000 | 3.1365 | 0.0000 |
| **20,000** | **78.2457** | 0.0000 |
| 30,000 | 45.1500 | 0.0000 |

**The control** (`probe_floor.py --mode eval-easy`, 25 random episodes, same regime): mean
**1.682**, sd 1.781, 95% CI on the mean **[1.103, 2.434]**, **max single episode 8.046**.

**Established: the setup learns.** A 10-episode mean of 78.2 against a floor whose *best single
episode* was 8.0 is not a marginal call, and needs no interval to separate. The frame-0 evaluation
(1.51) sits inside the floor CI, which is what an untrained policy must do and is a check on the
comparison rather than a result. An earlier version of this entry called the signal "suggestive,
not established" from the 10k point alone (3.14); two more eval points settled it.

**What it still does not show, and these are not small.**

- **Not a reproduction.** RL-ViGen publish SVEA door Easy at **268.8** over 5 seeds ([C31](#c31)).
  We are at 45–78 after **30k of their 1.1M frames — 2.7% of the budget**. Consistent with a
  learning curve; not evidence we land where they land.
- **Success rate is 0.000 throughout.** The threshold (`hinge_qpos > 0.3`) is never reached, so
  every claim here is about **return**. That is exactly [C33](#c33): the benchmark's own endpoint
  is return, and ours is success rate.
- **One seed, one method, one task, on the MPS path** whose numerics differ from CUDA ([C4](#c4)).
- **Eval variance is large** — 78.2 then 45.2 at adjacent points, 10 episodes each. The direction
  is unambiguous; the level is not.

**A correction to [C34](#c34) worth keeping.** "Local training is infeasible" is true for a
*sweep* and false for a *question*: three hours at ~3 FPS (median 2.97 over 67 logged points) was
enough to move an endpoint from indistinguishable-from-random to 46× the floor. The local path
cannot produce the table. It can answer whether the machinery learns at all — and did.

### C36 — Per-baseline throughput varies 8.3x, so "frames" is not a budget {#c36}
**Class** INHERITED · **Status** MONITORED

Measured on this M2 Pro, Door, medians over the logged points of real runs:

| baseline | FPS | 1.1M frames costs | why |
|---|---|---|---|
| `drqv2` | **13.09** | ~23 h | one critic update, random-shift augmentation only |
| `svea` | 2.97 | ~103 h | critic loss on augmented **and** unaugmented obs, plus overlay |
| `sgqn` | **1.57** | ~195 h | adds the saliency/attribution head and masking |

**A uniform frame budget is not a uniform cost.** "1.1M frames per baseline" hides an 8.3x spread
in wall-clock and money. Any schedule treating runs as interchangeable units is wrong by most of a
week on the tail. And `drqv2` at 13 FPS makes a full-budget **local** run ~23 h, which further
narrows [C34](#c34): local is infeasible for the *sweep* and the *expensive* baselines, merely
slow for the cheap one.

### C37 — `drqv2` learns where RL-ViGen publish floor — and the comparison was never like-for-like {#c37}
**Class** OURS · **Status** OPEN

> **Sharpened 2026-08-24 by [C62](#c62), which supplies the mechanism this entry lacked and one
> datum that changes its shape.**
>
> **Their 3.6 now has a mechanical reading.** Door's shaping alone can pay at most **250** over
> 500 steps without the door ever opening. So RL-ViGen's published `drqv2` **3.6 is 1.4% of the
> shaping ceiling** — not a weakly-trained agent but one whose gripper is essentially never near
> the handle. Same for their CURL (6.6) and DrQ (14.0). Whatever their runs did, they did not
> approach the door.
>
> **And we now know where our curve crosses theirs.** Measured on the same regime they publish
> (`eval-easy`), not the train regime this entry originally compared:
>
> | our `drqv2`, eval-easy | pooled | successes |
> |---|---|---|
> | 50k frames | **3.49** | 0/200 |
> | 100k frames | **131.05** | **63/200**, 43 episodes above 250 |
>
> At 50k we sit **on** their 6e5 number. Between 50k and 100k we pass through it and keep going.
> So the entry's claim is not "ours is better" — it is that **ours crosses their published value
> at roughly a twelfth of their budget and then continues, while theirs, at twelve times more, does
> not.** That is a stronger and more specific statement than "learns where they publish floor",
> and it makes the divergence a question about *their* run rather than about ours.
>
> This remains OPEN and the caveat in [C31](#c31) is undisturbed: budget, robot, scene set and
> episode length are verified to match only as far as horizon 500, `action_repeat` 1, Panda,
> OSC_POSE, 84×84 and the Easy level. **Nothing here licenses using either number to explain the
> other** — it licenses asking why a published baseline never reached the handle.

RL-ViGen publish `DrQ-v2` on door Easy at **3.6** over 5 seeds ([C31](#c31)) — at the random floor,
and the basis for [C32](#c32)'s claim that three of the twelve are published as not learning.
**Ours reaches 57.4 by 30k frames.**

| frames | `drqv2` eval-easy | `svea` eval-easy |
|---|---|---|
| 0 | 0.846 | 1.507 |
| 10,000 | 6.904 | 3.137 |
| 20,000 | 5.809 | 78.246 |
| 30,000 | **57.443** | 45.150 |

Both learn; both far exceed the random floor (mean 1.68, best episode 8.05).

**A code-verified candidate explanation, found before spending anything on the instability
hypothesis.** RL-ViGen's own configs set **`action_repeat: 2`** (`cfgs/config.yaml:10`,
`cfgs/svea_config.yaml:9`) and **no robosuite task file overrides it**. We run **`action_repeat=1`**,
because that is what RL-ViGen's *paper* specifies for robosuite (Supplementary Table 2) and it is
this project's declared protocol. And `train.py:128` reads:

```python
def global_frame(self): return self.global_step * self.cfg.action_repeat
```

So **frames are env frames and updates are agent steps**, and at any matched `F` we perform
**twice the gradient updates they do**. Their `num_train_frames: 1100000` is ~550k updates; ours
at `ar=1` is ~1.1M. At `F=30,000` we have done 30k updates where their configuration does 15k.

Off-policy visual RL is strongly sensitive to the update-to-data ratio, so this is not a rounding
difference — **it plausibly accounts for a large part of the gap, and it means no reproduction
claim was ever available from this comparison.** The earlier framing of this entry ("we do not
reproduce their ordering") overstated what the data could support.

**This is also a paper-versus-code disagreement of the kind this project catalogues.** Their paper
says `action_repeat: 1` for robosuite; their shipped code defaults to `2`. **UNVERIFIED and
load-bearing: which of the two produced the spreadsheet.** The code default is the natural
assumption and it is only an assumption.

**Reclassified 2026-08-18: no longer awaiting a decision from the owner.** This entry was marked
"your decision" when the gap was unexplained and someone had to choose what to do about it. It is
now explained — [C45](#c45)/[C47](#c47) showed the two figures were never the same quantity, and
what remains (landing on a published cell) is [C48](#c48)'s, whose decision is a compute
allocation. Left **OPEN** because the explanation is not a measurement; downgraded from the
judgement queue because nothing here is waiting on a person.

**Partly settled, 2026-08-18, from their own scripts.** The "code default is the natural
assumption" reading is the weaker one. `scripts/train.sh` as shipped is a **DMC** script —
`env=dmc`, `action_repeat=2`, with every robosuite invocation commented out — so its `2` is not a
robosuite value at all. The only robosuite-specific invocation RL-ViGen ships is
`scripts/eval.sh`, and its robosuite branch sets **`action_repeat=1`** explicitly, matching the
paper's Supplementary Table 2. So on the evidence available, **`ar=1` is their robosuite value and
ours agrees with it**; the `2` in `cfgs/config.yaml` is a DMC-era default that no robosuite script
selects. Still not proof of what produced the spreadsheet — training invocations for robosuite are
not shipped in any form — but the "we do twice their gradient work" explanation now requires
assuming they trained with a setting their own robosuite script overrides.

**Part of the gap is now quantified, and it does not close — [C47](#c47).** Our 469.4 is a
**scene-0** figure; RL-ViGen's 3.6 is an **average over ten scenes**. Scaling ours by the measured
retention of 0.278 gives an indicative ten-scene equivalent of **~130**, so the gap narrows from
**130x to ~36x** and remains an order of magnitude. Indicative only: the retention was measured on
a *different run's* checkpoint at 50k frames, and [C41](#c41) puts run-to-run variation at 30-50%,
so this is a scale correction rather than a converted number. **It does establish that the two
figures were never the same quantity**, which is what [C45](#c45) claimed and this measures.

**The run-to-run noise floor does NOT dissolve this gap, which is worth stating because it
dissolves smaller ones.** [C41](#c41) now measures ~13% run-to-run variation at 30k frames and
~49% at 40k on identical configurations. Our `drqv2` exceeds the published 3.6 by roughly **130x**
— about two orders of magnitude beyond that floor — so whatever explains it, nondeterminism does
not. The same floor does invalidate any single-seed ordering *between our own baselines* at these
budgets, which is a separate and now-live constraint on how a results table may be read.

**Superseded as the leading explanation, 2026-08-18 — [C45](#c45) is a larger effect and points
the other way.** The `action_repeat` argument above says we do twice the gradient work at a matched
frame count, which would make us better *at the same task*. C45 says we are not measuring the same
task.

`Protocol`'s own comment states the design: *"training uses scene 0 only, evaluation uses all
ten."* But `train.py` passes no `scene_id` anywhere, so `robo_make` defaults it to 0 for **both**
envs. **Our train scene and our eval scene are the same scene.** What we report as `eval-easy` is
the training scene under appearance randomisation; what they publish is an average over ten
scenes, nine of them never trained on. **Those are different quantities.** Which is the easier one
is a separate question and is *not* settled by this entry — see [C46](#c46), where the measured
distance from the training distribution comes out the same for both. Not comparable is the claim;
not "ours is inflated".

That reframes the direction of the puzzle. It is not "why do we exceed a published floor by 130x"
— it is "we removed the scene-generalisation axis from a benchmark whose stated purpose is
measuring generalisation." The remaining `action_repeat` difference is real and still unresolved,
but it can no longer be the first thing to test.

**What this does not license.** It does not follow that our `drqv2` result is wrong, or that
re-running with the sweep will land near 3.6. Their DrQ-v2 number is an outlier *within their own
table* — DrQ-v2, CURL and DrQ publish at 2-14 on door Easy while SVEA, SRM, PIEG and SGQN publish
at 62-391 ([C31](#c31)) — so a floor-level DrQ-v2 is not the benchmark's typical result and may
carry its own explanation. The honest statement is that **no comparison between our number and
theirs is available until the scene axis matches**, which is what C45 and C43 exist to fix.

**What still needs explaining even if the ratio accounts for it.** Their 3.6 is at *full* budget.
If `drqv2` genuinely reaches ~57 at 30k frames under any sane protocol, a final value at the
random floor implies a collapse, not merely slower learning.

**RESOLVED, and it went the wrong way for the hypothesis above.** Evidence from their own repo:

- `scripts/eval.sh`, the **robosuite branch**, sets **`action_repeat=1`** explicitly.
- `scripts/train.sh` sets `action_repeat=2` — but with `env=dmc`. The `2` default in
  `cfgs/config.yaml` is the DMC value, not the robosuite one.
- Their paper's Supplementary Table 2 also specifies **1** for robosuite.

So their robosuite work runs at `action_repeat=1`, **the same as ours**, and the update-ratio
explanation largely dissolves. The paper-vs-code disagreement is real but harmless here: the code
*default* is 2 because it is written for DMC, and their robosuite scripts override it to 1, which
is what the paper says. **We are on their axis after all.**

**SUPERSEDED — see [C45](#c45).** We evaluate on **scene 0 only**; RL-ViGen's own protocol is
**10 scenes x 10 trials = 100 trials**, and `Protocol.eval_scene_ids` hashes the ten-scene version
while no run performs it. Our evaluation asks an easier question — train on scene 0, evaluate on
scene 0 with the textures re-randomised — so an agent that memorises that scene's geometry is not
penalised here and is there. That is a sufficient mechanism for the gap without anything being
wrong with the algorithm or the training, and it is now the leading explanation.

Also from the supplemental: Door's budget is **6e5** frames (Table 6), not the 1.1M in
`cfgs/task/easy.yaml` — so our 100k is 17% of their Door budget, not 9%.

The run also **falsified the collapse hypothesis** over the range tested: `drqv2` is monotone to
100k frames with SR reaching 1.000, no turn. Collapse cannot be excluded beyond 100k, but it is no
longer the leading candidate.

*Historical reasoning below, kept because the elimination order is the useful part.*

That makes the gap harder, not easier. With the leading explanation removed, and
[C42](#c42) adding **SR 0.6 on the held-out regime** to a return of 242.7 against their published
3.6, the remaining candidates are:

1. **Collapse.** Their number is at 1.1M frames; ours is at 70k and still climbing. DrQ-v2 is known
   to destabilise on some tasks. A run that peaks at ~240 and ends at ~3.6 is a *collapse*, and it
   would be visible only by running long. **Now the leading hypothesis.**
2. **A different robot, scene, or task variant.** Their `eval.sh` robosuite branch uses
   `TwoArmPegInHole`, and their spreadsheet has separate cross-embodiment sheets for IIWA and
   Kinova3 — so their robosuite results span configurations we have not matched.
3. **A different eval-regime mapping** between their Easy/Medium/Hard and our `eval-easy`.

**Options**
1. ~~**Establish which `action_repeat` produced the spreadsheet**~~ — **done, see above; it is 1.**
2. **Establish which robot and scene their door numbers used — their paper, their scripts, or
   any run metadata in the repo. Free, and it decides whether there is a discrepancy at all.
   — free, and candidate 2 above is now the cheapest unexplored explanation.
3. **Run `drqv2` to a much larger budget** to test the collapse hypothesis — ~23 h locally at
   13 FPS, and it is now the hypothesis most likely to be right.

*My reading: (2) then (3). The axis question is settled and settled against me — I proposed
the update-ratio explanation and the evidence removed it, which is the useful outcome of asking a
free question first.
Note that this bears on [C31](#c31) as well: their SVEA 268.8 is also on their protocol, so the
"reproduction target" is a target on an axis we do not currently share.*

### C38 — An untrained network is not a uniform-random policy, and the gap can be large {#c38}
**Class** DESIGN-GAP · **Status** MONITORED

Frame-0 evaluations, before any gradient step:

| baseline | frame-0 eval-easy |
|---|---|
| `drqv2` | 0.846 |
| `svea` | 1.507 |
| **`sgqn`** | **26.740** |

Uniform-random floor, same task and regime: mean **1.682**, best single episode **8.046**
([C17](#c17)).

`drqv2` and `svea` start indistinguishable from uniform random. **`sgqn` starts 16x the random
mean and 3x its best episode.** Plausible mechanism, unverified: an untrained network emits a
*consistent* action rather than a uniform one, and a constant push can beat uniform noise on a
manipulation task.

**The methodological point holds regardless of mechanism.** `probe_floor.py` measures a
**uniform-random** policy; that is not the same control as an **untrained network**. They agreed
for two baselines and differed 16x for the third. Where they differ the frame-0 evaluation is the
better baseline, being the policy the run actually starts from. Any "better than chance" claim
must say which chance.

### C39 — The MPS shim's patched surface, now covered per symbol {#c39}
**Class** OURS · **Status** RESOLVED

**Decision** ~35 patch points against 3 tests is coverage by anecdote. The three existing tests
cover the two regressions the shim has actually had; they do not cover the surface.

**Attempt** one subprocess enumerates every patched point and prints a verdict per name;
**42 parametrized assertions** read it. One process, many named failures — a subprocess per symbol
would cost ~35 process starts, and the shim must run in a subprocess because it mutates the torch
namespace process-wide.

Covered: the 10 `torch.cuda.*` functions (including that `manual_seed` is a **no-op, not an
alias** — aliasing recurses into `cuda.manual_seed_all`); the 7 legacy typed constructors (with
`DoubleTensor -> float32` asserted so the deliberate substitution stays visible); `Tensor.cuda`,
`Module.cuda`, both spellings of `Tensor.to`, and `is_cuda`; and all 20 wrapped factories for
float64-downcast plus device placement.

**Effect** — 45 tests pass, and the exercise found two things:

1. **A bug in my own probe**: `full_like` needs a `fill_value`, which the first version omitted.
   Caught by the test failing, not by review.
2. **`torch.logspace` has no MPS kernel at all.** Verified *not* a shim defect — it raises the
   identical `NotImplementedError` with the shim absent. Recorded in `MPS_UNIMPLEMENTED` as an
   **inverted assertion**: the test requires it to keep failing *for that reason*, so it cannot rot
   in either direction — if MPS implements it the test says to remove the entry, and if it starts
   failing differently the test says a shim defect is wearing a known-limitation label. No baseline
   calls it (grepped across `runnable/` and RL-ViGen's `algos/`), so it is inert today, and
   because `PYTORCH_ENABLE_MPS_FALLBACK` is unset it would raise loudly rather than drift onto CPU.

**What is still not covered**: the shim's behaviour on a *Linux* box, where it does not activate at
all — see [C40](#c40). Every test here is skipped where MPS is absent, which includes CI and Kaggle.

Commit `c7ce71f4`.

### C40 — Every launcher's Linux branch has never been executed {#c40}
**Class** DESIGN-GAP · **Status** MONITORED

`runnable/_launch/*.sh` branch on `uname -s`. The Darwin arm sets `MUJOCO_GL=glfw`,
`RLGEN_MPS_AS_CUDA=1` and `replay_buffer_num_workers=0`; the Linux arm sets `MUJOCO_GL=egl`, no
shim, and leaves RL-ViGen's own worker count. **Everything green in this project has executed the
Darwin arm.** 12/12 smoke, the 429-test suite, three training runs — all of it.

So the authoritative platform runs code paths with **zero** execution history here, and the first
T4 job ([C21](#c21)) is also the first execution of the other branch. That is a normal state for a
project that has not run remotely yet; it is worth stating because "12/12 TRAINED" reads as
platform-independent and is not.

Related: `replay_buffer_num_workers=0` is forced on macOS because forked workers die re-validating
GL. It is a **macOS-only tax** that inflates the local FPS penalty and will not appear on Linux —
so [C34](#c34)'s local throughput is pessimistic for CUDA by an unmeasured amount, on top of
everything else already recorded there.

### C41 — What the shim changes numerically, measured {#c41}
**Class** DESIGN-GAP · **Status** RESOLVED

**Decision** measure it rather than keep declaring it. The shim downcasts float64 to float32 and
announces it; the size of that effect was never bounded, so [C35](#c35) could only be defended as
an ordinal claim.

**Attempt** `scripts/probe_shim_divergence.py` — a golden trace: identical initial weights,
identical batches, identical seed, K updates, then compare loss trajectories and final parameters.
Two questions separated on purpose, because reporting them together confounds the *shim* with the
*platform*:

- **Q1, the shim's declared behaviour**: float64 vs float32 on the **same** device. No MPS involved.
- **Q2, the backend**: CPU vs MPS at the **same** dtype. No dtype change involved.

**Effect** — 250 identical updates:

| comparison | loss rel-diff step 1 | step 250 | growth | final param rel-L2 |
|---|---|---|---|---|
| Q1 cpu-float64 vs cpu-float32 | 5.13e-07 | 3.32e-07 | 1x | **7.96e-05** |
| Q2 cpu-float32 vs mps-float32 | 3.77e-07 | 1.17e-07 | 0x | **8.29e-05** |

1. **The divergence is bounded and does not grow.** Over 250 steps the per-step relative loss
   difference *shrinks*, and parameter distance sits at ~8e-5 in both comparisons rather than
   compounding. At float32 the two must differ — reordered reductions guarantee it — so the
   question was never "do they differ" but "noisy copy or different trajectory". At the update
   level it is a noisy copy.
2. **The shim downcast is no worse than the backend it runs on.** Q1 and Q2 are the same order of
   magnitude, so the declared float64 substitution adds nothing beyond using MPS at all. That also
   downgrades the *numerical* urgency of [C4](#c4): the alpha dtype asymmetry is real and
   undeclared, but it is a ~1e-5 effect, not a regime change.

**What this does NOT license, and it is the larger term.** The probe holds the data **fixed**.
Reinforcement learning does not: a tiny action difference changes the transition, which changes
the replay contents, which changes every later update. That feedback loop is the dominant
divergence mechanism in a real run and **this probe cannot see it**.

- **Licensed**: "it learns" — a claim that survives a 48% perturbation because both runs rise far
  above the random floor, which is exactly what [C35](#c35) claims.
- ~~"A beats B"~~ **— withdrawn 2026-08-18.** This line read "ordinal claims … 'A beats B'" until
  the amendment above was measured. **Two runs of the same configuration swap places between
  adjacent eval points** (B 13% behind at 30k, 48% ahead at 40k), so a single-seed ordering is not
  an ordinal fact about the methods; it is a sample from a distribution wide enough to contain
  both orders. Ordinal claims need seeds, and this entry cannot license them.
- **Not licensed**: any MPS number in a results table, or any claim that an MPS run reproduces a
  CPU or CUDA run.

**Amended 2026-08-18 — the closed-loop effect this entry predicted now has numbers, and they are
large.** Two runs of the *same* configuration and seed, a day apart on this machine, agree exactly
at frames 0 and 10,000 and then separate: **2.26% at 20k, 12.79% at 30k, 48.51% at 40k,
32.55% at 50k, 48.31% at 60k, 4.26% at 70k, 20.43% at 80k, 22.53% at 90k, 7.07% at 100k** —
**no trend**, min 2.3% and max 48.5%, and **both runs finish at `success_rate` 1.0 with returns
436-469**. Same destination, noisy path: what is unreliable is any *single eval point*, and so any
claim keyed to a frame count. **The sharpest illustration is not a percentage**: at 80k run A logs `success_rate` **1.0**
and run B **0.4**, so *"does this configuration solve Door by 80,000 frames?"* answers **yes, every
episode** and **no, two in five** from the same configuration and seed. The runs are not on divergent
trajectories; they are two noisy samples of one learning curve, and any single eval point can
disagree with its twin by up to ~50%. At 30k one logs `success_rate` 0.1 and the other 0.0,
so even "did it ever succeed by 30k" differs; **at 40k the ordering reverses**, the run behind at
30k being 48% ahead at 40k.

The practical consequence is bigger than the shim question this entry started from: **the
run-to-run disagreement at a single eval point reaches ~49%**, larger than most effects under
discussion here, and it is a floor under every single-seed comparison this project makes. At 40k
it also inverts the ranking, so **a single-seed A-vs-B ordering at these budgets carries no
information**. One pair of runs, so read it as "at least this much" rather than as an
interval. Details and citations in `REGISTER.md`, 2026-08-18.

Still no CUDA datapoint; [C21](#c21) is the only route to one.

Commit `c87379f9`.

### C42 — The success signal fires: SR 0.6 on the held-out regime {#c42}
**Class** DESIGN-GAP · **Status** MONITORED

> **Caveat added 2026-08-18: this is ONE run, and the frame counts in it are not
> reproducible.** The same configuration and seed re-run on 2026-08-18 tracks it exactly to
> 10,000 frames and then diverges — 12.79% at 30k, **48.51% at 40k**, where the new run reads
> 104.64 against the 70.46 below ([C41](#c41)). **The achievement survives** (the success flag
> fires, unforced, far above a floor of 0) **and the schedule does not**: "SR 0.6 by 70k" is one
> sample, and a re-run may reach it earlier or later. Read the left column as illustrative, not
> as a learning curve.
>
> **And every row is a SCENE-0 number.** [C47](#c47) measures held-out scenes at 27.8% of the
> training scene's return, with held-out SR at 1/90 against 0.10 on scene 0. So this table
> describes performance on the scene the policy trained on; it is not a generalisation curve, and
> the benchmark's own protocol would average it with nine scenes on which this policy does much
> worse.

`drqv2` on Door, eval-easy, 10 episodes per point, local MPS, seed 1:

| frames | return | **SR** |
|---|---|---|
| 30,000 | 57.44 | 0.000 |
| 40,000 | 70.46 | 0.000 |
| 50,000 | 89.50 | **0.100** |
| 60,000 | 121.07 | **0.200** |
| 70,000 | **242.70** | **0.600** |

**Every success rate previously on record in this project was `0.000`.** [C17](#c17) established
that the flag had *never been observed firing* in 25 random episodes and needed a positive control
— driving the simulator to the threshold — to show it was live at all. It now fires **unforced,
from a learned policy, in 6 of 10 held-out episodes.**

**What this supersedes.**
- [C17](#c17)'s "never observed" is now historical. Its positive control was still the right call:
  it is what made this reading interpretable rather than surprising.
- [C33](#c33) asked whether to report return or success rate given that success never moved.
  Success now has dynamic range, so that decision is live rather than forced.
- [C32](#c32) recorded that RL-ViGen publish `drqv2` at 3.6 and told a reader that near-zero rows
  would be *reproducing* the benchmark. Our `drqv2` reaches 242.7 return and 0.6 SR. See
  [C37](#c37) — the `action_repeat` 1-vs-2 difference means we do twice their gradient updates per
  frame, so this is not yet a contradiction of their number, but it is very far from it.

**Caveats that still bind.** One seed, one baseline, MPS path, 70k of 1.1M frames, and this is
**eval-easy only** — see [C43](#c43), which is why no retention figure follows from it.

### C43 — Retention is not computable from these runs: we only ever evaluate in one regime {#c43}

> ### Update, 2026-09-02: the regimes exist, more baselines evaluate two than this entry assumes,
> and the remaining gap is a harness rather than a patch
>
> Three things measured today move this entry without closing it.
>
> **All four regimes construct, step and render.** `train`, `eval-easy`, `eval-medium` and
> `eval-hard` had never once been built by anything in this project. Run through
> `scripts/probe_regimes.py`, each separates from `train` at 3.4×–4.2× the within-regime control
> (two samples of the same regime at different seeds). `eval-hard`'s video background loads from
> `envs/robosuiteVGB/robosuitevgb/assets/video/eval-hard/`.
>
> **The `train` regime is not a randomised distribution at all.** `robo_config.yaml` defaults to
> `mode: train`, and `robosuitevgb/utils.py`'s `train` branch sets
> `randomize_color = randomize_lighting = randomize_dynamics = randomize_camera = False` with
> `moving_light` off. So the training distribution is a **single fixed appearance**, and
> `train.py:78-79` builds `self.train_env` with no `mode` argument, which resolves to exactly that.
> Retention as this entry defines it therefore divides a randomised-regime score by a
> **fixed-appearance** score — not by "the same distribution with different textures". That is
> defensible as a denominator and it is not what the phrase "train regime" suggests, so it should
> be said wherever the ratio is reported.
>
> **They do not order by difficulty.** `eval-medium` sits *further* from `train` (0.657) than
> `eval-hard` (0.505), and the config says why: medium sets `except_robot: False` so the robot
> itself is randomised, while hard fixes the robot and adds a moving light and a video background.
> **Any table presenting easy → medium → hard as one ordered axis asserts a monotonicity this
> measurement contradicts.** There is also an `eval-extreme` video directory no code path reads.
>
> **The per-baseline count was already better than "one regime".** `dmc_gb` calls `evaluate()` on
> the training env *and* on `test_env` (`train.py:139-141`), logging `episode_reward` and
> `episode_reward_test_env` separately — so retention is computable for `rad` and `soda` from
> training logs today. `alda` evaluates **three** regimes (`alda_trainer.py:146-148`: `env='train'`,
> `color_env='eval-easy'`, `distract_env='eval-hard'`) and is the only baseline that constructs
> `eval-hard`. `ctrl` steps a train and an eval-easy env continuously inside its loop. The
> register's row of 2026-08-18 said this and this entry had not absorbed it.
>
> **What remains, and it is not a patch.** `ppg` and `ibac_sni` evaluate nothing during training,
> `idaac` evaluates one regime, and the RL-ViGen five evaluate eval-easy plus a train-regime
> denominator. Making the axis uniform across twelve **cannot** be done in training loops without
> seven authored deviations. It is done downstream instead: `scripts/eval_grid.py` runs
> regimes × scenes from one checkpoint and emits schema-2 records carrying `regime`, `scene_set`
> and the per-baseline `conventions`. That covers the RL-ViGen five today; `audit_eval_state.py`
> records what the other seven need, and none of them needs a policy written.


> ### Correction, 2026-08-19: this was marked RESOLVED and is not
>
> P14 was applied, verified on a `drqv2` run, and both entries were closed the same hour. **P14
> patches `RL-ViGen-upstream/train.py`, which serves five baselines.** The other seven have their
> own training loops and were untouched. `scripts/audit_eval_axis.py` reports the state per
> baseline, and no non-upstream tree varies `scene_id` at all: `idaac` and `ibac_sni` pass a
> literal `0`, and `alda`, `ctrl`, `ppg`, `rad`/`soda` thread a parameter that nothing ever moves.
>
> **The mistake was structural, not careless.** The claim "we evaluate ten scenes" had no
> per-baseline form, so a patch verified on one baseline was generalised to the set — and the
> verification was real, which is what made it convincing. This is the same error shape as the
> determinism retractions: a measurement whose scope was narrower than the sentence it licensed.
>
> The instrument is the fix, not resolve. `audit_eval_axis.py` prints one row per baseline, and
> `tests/test_eval_axis_coverage.py` pins that **five** sweep and seven do not — so the next claim
> of the form "we evaluate N scenes" has to name N *per baseline* or fail.
>
> **What is genuinely closed**: the five upstream baselines sweep ten scenes and measure a
> train-regime denominator. That is real and is not withdrawn. What is not closed is the other
> seven, and extending it is seven clone deviations rather than one patch — which is a decision,
> not a slot, and is why both entries are OPEN again rather than partly ticked.

**Class** DESIGN-GAP · **Status** OPEN

The project's stated goal is *"measure how much performance each **retains** when the visuals
change"*, and [`RESEARCH-FRAME.md`](RESEARCH-FRAME.md) argues retention is the right endpoint
precisely because it makes each method its own control.

**The runs as configured cannot produce it.** `runnable/_launch/rlvigen.sh:36` exports
`RLVIGEN_EVAL_MODE=eval-easy`, and `RL-ViGen-upstream/train.py:88` builds a **single** `eval_env`
with that mode. So every evaluation is on the held-out regime and **there is no train-regime
evaluation at all**.

What exists instead is the `train` log line — a *stochastic-policy, single-episode* return from the
rollout that generated the data. Dividing a deterministic 10-episode eval by that is not a
retention ratio; it mixes policy modes and sample sizes.

**Two different quantities are now called "retention", and they must not be conflated.** This
entry means **regime retention** — performance under `eval-easy` as a fraction of performance
under `train`, the axis `RESEARCH-FRAME.md` argues for, and still uncomputable because no
train-regime evaluation is run. [C46](#c46)'s follow-up measures **scene retention** — held-out
scenes as a fraction of the training scene, at a *fixed* regime — which `scripts/eval_across_scenes.py`
can compute today from a single checkpoint. They are different axes and neither substitutes for
the other: a policy could retain perfectly across scenes and collapse across regimes, or the
reverse. Where a number is reported, the axis must be named.

**Scope narrowed 2026-08-18, by reading every baseline's eval construction. "We only ever evaluate
in one regime" is true for six of the twelve and false for the other six.**

| baseline | regimes evaluated | how |
|---|---|---|
| `alda` | train + eval-easy + eval-hard | in-run; `evaluate(step)`, `distracting_env=True`, `color_env=True` |
| `ctrl` | train (ID) + eval-easy (OOD) | in-run; `env_test_ID` / `env_test_OOD`, with `succ_id` / `succ_ood` |
| `rad`, `soda` | train + eval-easy | in-run; `dmc_gb/src/train.py` evaluates `env` *and* `test_env` |
| `ppg` | train + eval-easy | checkpoint pass; PART2 §3 verified 1.1829 / 0.9825 |
| `ibac_sni` | train + eval-easy | checkpoint pass; PART2 §3 verified 0.690 / 0.690 |
| **`drqv2`, `svea`, `sgqn`, `curl`, `drq`** | **eval-easy only** | single `eval_env` — this entry's original evidence |
| **`idaac`** | **eval-easy only** | `make_rlvigen_venv(..., RLVIGEN_EVAL_MODE, 1)` |

**What this changes about the decision.** Regime retention is computable **today** for half the
baselines without touching anything, and the gap is six, not twelve. Five of the six are the
RL-ViGen group and are fixed by the single patch already scoped here and in [C45](#c45) — the
second `eval_env` — and the sixth, `idaac`, is one more env of the shape its own `test.py` already
builds. **The remedy is one patch plus one line, not a programme.**

**Blast radius**, corrected: every number produced *through the RL-ViGen launcher* is an absolute
held-out score rather than a retention figure. That is still the group that has produced almost
every number so far, so the practical effect on results to date is largely unchanged — but the
work to close it is much smaller than this entry implied, and four baselines are already emitting
the pair.

**Original blast radius, kept for the record**: every number produced so far is an absolute
held-out score, not a retention figure. The comparison the project exists to make is currently unavailable, and this was not
visible until a run produced numbers worth dividing.

**Options**
1. **Evaluate both regimes each eval point** — a second `eval_env` at `mode=train`, doubling eval
   cost (small: evals are ~10 episodes against 10k frames of training). Most faithful, and it
   makes retention a per-point quantity rather than a post-hoc guess.
2. **Run each baseline twice**, once with `RLVIGEN_EVAL_MODE=train`. Zero code change, doubles
   compute, and the two runs differ in seed-path so the ratio mixes runs.
3. **Report absolute held-out scores only**, and drop retention from the claim. Honest, and it
   gives up the endpoint that motivated the design.

*My reading: (1) — but **merged with [C45](#c45)**, not done separately. Both are changes to the
same eight lines of `train.py`'s env construction: C43 adds a train-regime eval env, C45 adds the
scene dimension. Done apart they touch the same site twice and re-pin the contract hash twice, and
the second would invalidate the first's numbers anyway — a retention figure computed on one scene
is not the retention figure the protocol declares. It edits the shared RL-ViGen tree, so it is a
patch-registry decision and yours.*

**Commit** `e21e8052`

**Decision** Sweep the ten scenes and add a train-regime denominator — **one patch, P14**, because
C43 and C45 are one edit to one loop. Owner, 2026-08-19. Recorded in §4 form in
[`INTEGRATION-DELTA.md`](INTEGRATION-DELTA.md), with its alternatives and the result that would
show it wrong; `python scripts/decisions.py` enumerates it.

**Effect** `train.py`'s evaluation now rebuilds the env per scene across the ten `Protocol`
certifies, and measures a train-regime denominator at scene 0 — the distribution actually trained
on, deliberately not swept. Verified on a `drqv2` run: 24 environments built (two at startup, two
eval points of ten scenes plus one train-regime env) and `eval.csv` gained `train_regime_reward`
0.8525 beside a ten-scene `episode_reward` 0.8718. **Retention is computable from a training run
for the first time.** Cost: ~11× the environments per eval point, which comes out of the same
budget as seed count ([C18](#c18)). P14 is ENABLES and is in `Protocol.env_patches`, so every
pre-P14 number — [C47](#c47)'s retention included — sits on a different footing and is not
superseded.

---


> **Scope clarified 2026-08-25 — this is narrower than it reads, and it is now downstream of
> [C72](#c72).** The correction above is about the *training loops*: P14 gave five baselines a
> ten-scene in-run eval and seven were untouched. That remains true and the instrument still pins
> it. But retention is not produced by the training loop — it is produced offline by
> `scripts/eval_across_scenes.py`, which sweeps **ten scenes and both regimes for any checkpoint it
> can read**, whatever the run did internally. Fourteen such grids now exist.
>
> So the live question splits, and neither half is the one this entry was opened on:
>
> - **For the five natives** — retention is computable today and has been computed. Whether their
>   *in-run* eval also sweeps ten scenes is a question about log richness, not about the endpoint.
> - **For the other seven** — the blocker is not their training loop. It is that the offline
>   evaluator cannot read their checkpoints at all ([C72](#c72)), which the owner has **deliberately
>   deferred**. Patching seven training loops would not produce a retention number for any of them.
>
> **Corrected within the day, on challenge: this entry is NOT merely C72 from another angle, and
> the paragraph above understated it.** The split above is right about *mechanics* — the offline
> grid can compute retention for the natives and cannot read the other seven. It is wrong to
> conclude there is no decision here, because it silently treats **the offline grid's protocol as
> settled, and nobody ever settled it.**
>
> That protocol was *constructed*: 20 episodes per scene, ten scenes, two regimes, pooled — then
> scenes **dropped** by the floor and 25%-success guards ([C55](#c55)), with the surviving pool
> reported as the number. `regime_retention_report.py` says so in its own output: *"pooled over the
> N usable scenes only — **NOT RL-ViGen's protocol**, which averages all ten. Dropping scenes
> changes the estimand."* RL-ViGen averages ten scenes unconditionally; we average a
> data-dependent subset. Both are defensible and they are **different quantities**, and which one
> this project reports has never been decided — it was built.
>
> **So what is open here is the evaluation protocol itself**, and it is upstream of what any
> retention number means: how many episodes, which scenes, whether a guard may drop a scene from a
> pooled mean at all (versus refusing the whole cell), and whether the reported figure should be
> comparable to RL-ViGen's published one or deliberately not. [C48](#c48) is the same question seen
> from the anchoring side.
>
> **Action for a reader: still do not act unilaterally — but not because it is subsumed.** Because
> it is a design decision belonging to the owner, alongside [C72](#c72) rather than inside it.

**DEFAULT SET, 2026-09-03 — retention IS computable now, it has been computed, and the entry's own
condition for that was met.** The 2026-09-02 update closed by saying the remaining gap was *"a
harness rather than a patch"*. That harness is `OFFLINE_EVAL` + `eval_grid.py` run on the container
([C95](#c95)), and the measurement exists: `drqv2-s2` at 100k, **four regimes x ten certified
scenes x ten episodes = 400 episodes**, against the two per cell the training loop could afford.

| regime | mean | success | per-scene shape |
|---|---|---|---|
| `train` | **90.01** | 0.22 | 0: 392.9, 2: 287.0, 4: 205.3 — the other seven 0.7–6.6 |
| `eval-easy` | 2.37 | 0.00 | flat, one 10.9 at scene 7 |
| `eval-medium` | 1.06 | 0.00 | flat |
| `eval-hard` | 0.82 | 0.00 | flat |

**The definition this project will use, stated so the number is not re-derived differently later.**
Retention needs a numerator, a denominator and a statement of what is held out, and there are *two*
distinct quantities here that a single "retention %" would conflate:

1. **Appearance retention** = regime mean / `train` mean, over the same ten scenes.
   **2.6% / 1.2% / 0.9%** for easy / medium / hard.
2. **Scene retention** = mean over the nine held-out scenes / the training scene (0), within the
   `train` regime. **56.3 / 392.9 = 14.3%.**

Both are reported, never one. They answer different questions — the first is "does the policy
survive a change of appearance", the second "does it survive a change of layout" — and this policy
fails them differently: it keeps a seventh of its performance across layout and a fortieth across
appearance.

**The floor is what makes these numbers interpretable, and it must travel with them.** A constant
zero action earns ~1.2 per episode on Door's shaped reward. So `eval-hard` at **0.82 is BELOW
doing nothing**, and `eval-medium` at 1.06 is indistinguishable from it. These are not "degraded
performance" figures; outside `train` the policy is worse than inaction, and `success` is 0.00 in
every eval regime — the door never opens once in 300 evaluation episodes.

**The honest scope**: one baseline, one seed, one budget, one task. It is a measurement, not a
result about DrQ-v2. **What would overturn the default**: a definition change is fine and expected
(the endpoint question is [C76](#c76)); what would overturn the *numbers* is a second seed
disagreeing, which nothing here has yet tested.

### C44 — The Places365 loader spawns 8 workers regardless of the macOS guard {#c44}
**Class** UNDECLARED · **Status** MONITORED

`runnable/_launch/rlvigen.sh` passes `replay_buffer_num_workers=0` on Darwin, because forked
replay workers die re-validating `MUJOCO_GL`. **That guard covers the replay buffer only.**
`RL-ViGen-upstream/utils.py:175` is a second, independent loader:

```python
def _load_places(batch_size=256, image_size=84, num_workers=8, use_val=False):
```

`num_workers=8`, hardcoded, unreachable from the override. Observed directly: `drqv2` runs with
**0 child processes**, `sgqn` with **14**, both launched with the same override — because `drqv2`
uses no overlay augmentation and `sgqn` does. Affects `svea`, `sgqn`, `pieg`, `srm`.

**Not breaking anything**: these are `multiprocessing.spawn`, not `fork`, so they survive the
condition the guard exists for. But they are unaccounted CPU and memory on exactly the baselines
already slowest, and plausibly part of why `sgqn` runs at 1.57 FPS against `drqv2`'s 13.09
([C36](#c36)). It also means the Darwin guard is narrower than its comment implies.

### C45 — We evaluate on ONE scene; the protocol certifies ten, and so does the benchmark {#c45}


> ### Correction, 2026-08-19: this was marked RESOLVED and is not
>
> P14 was applied, verified on a `drqv2` run, and both entries were closed the same hour. **P14
> patches `RL-ViGen-upstream/train.py`, which serves five baselines.** The other seven have their
> own training loops and were untouched. `scripts/audit_eval_axis.py` reports the state per
> baseline, and no non-upstream tree varies `scene_id` at all: `idaac` and `ibac_sni` pass a
> literal `0`, and `alda`, `ctrl`, `ppg`, `rad`/`soda` thread a parameter that nothing ever moves.
>
> **The mistake was structural, not careless.** The claim "we evaluate ten scenes" had no
> per-baseline form, so a patch verified on one baseline was generalised to the set — and the
> verification was real, which is what made it convincing. This is the same error shape as the
> determinism retractions: a measurement whose scope was narrower than the sentence it licensed.
>
> The instrument is the fix, not resolve. `audit_eval_axis.py` prints one row per baseline, and
> `tests/test_eval_axis_coverage.py` pins that **five** sweep and seven do not — so the next claim
> of the form "we evaluate N scenes" has to name N *per baseline* or fail.
>
> **What is genuinely closed**: the five upstream baselines sweep ten scenes and measure a
> train-regime denominator. That is real and is not withdrawn. What is not closed is the other
> seven, and extending it is seven clone deviations rather than one patch — which is a decision,
> not a slot, and is why both entries are OPEN again rather than partly ticked.

**Class** FALSE-CERTIFICATION · **Status** OPEN

**Update 2026-09-03 — the last literal hardcode is gone, and the entry does NOT move.** The
2026-08-19 correction says "`idaac` and `ibac_sni` pass a literal". `idaac` was threaded earlier
(`make_rlvigen_venv(..., scene_id=0)`, a default rather than a constant); `ibac_sni` was the last
one still passing a literal, and `general.py` now reads `RLVIGEN_SCENE_ID`. `scripts/audit_eval_axis.py`
confirms the result and, more usefully, refuses to call it progress: it reports **5 of 12 sweep**,
unchanged, and classifies every other family as "threaded, never varied", with the note that
*"either pinned to a literal 0, or threading a parameter that nothing in its tree ever moves. Both
are single-scene in practice."*

**That distinction is the point, and I checked my own claim against it rather than the other way
round.** Having made the `ibac_sni` change I was ready to write that the scene axis is now
"reachable in all seven families", which is true and misleading: reachability is a precondition for
a sweep, not a sweep. Nothing in any of those seven trees moves the parameter, so nothing has
changed about what has been *measured*. **What would actually close this is a driver**, and one now
exists for four of the seven — `eval_grid.py` sweeps scenes for `dmc_gb`, `idaac` and `ppg`, and
`OFFLINE_EVAL` can run it where the checkpoints were trained ([C95](#c95)). `alda`, `ctrl` and
`ibac_sni` still have no driver.

**This is very likely the explanation for [C37](#c37), and it invalidates the generalisation
framing of every number produced so far.**

**Settled in return space — [C47](#c47): held-out scenes retain 27.8% of the training scene's
return**, with the drop at 4.37x the same-scene episode noise and one scene scoring *below the
random-policy floor*. So this entry is not a bookkeeping discrepancy: evaluating only on scene 0
overstates held-out performance by 3.6x for the policy measured.

**And the axis is now measured, not assumed — [C46](#c46).** All nine other scenes separate from
scene 0 (median 2.68x the within-scene floor, weakest 2.12x), and the separation is **~84% of the
train-to-eval-easy step** measured in the same run against the same floor. Scene 0 is the training
scene. So the single-scene evaluation holds fixed an axis carrying about as much visual variation
as the one this project calls generalisation. **It does not follow that our number is inflated** —
a later measurement in [C46](#c46) puts their evaluation point at 97% of our distance from the
training distribution, not further, so an earlier claim here that the omission runs "in the
direction that makes the task easier" is withdrawn. What stands is that the two protocols sample
different points, not that ours is the easy one; deciding that needs a trained policy.

`rlgen/protocol.py:255-256` declares, and **hashes**:

```python
eval_scene_ids: tuple = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9)
episodes_per_scene: int = 10          # -> n_eval_episodes = 100
```

with its own comment: *"Held out from training: training uses scene 0 only, evaluation uses all
ten. Recorded explicitly because the reference repo evaluates on the full distribution INCLUDING
the training levels, and the two answers are not comparable."*

**This is the second unthreaded argument in the same two lines, and the first one was already
found and fixed.** `PART2-METRIC-INVENTORY.md` Finding 7 (2026-08-17) records that
`Workspace.setup` builds `train_env` and `eval_env` with *identical arguments*, and that neither
passes `mode` — so both fell back to `robo_config.yaml`'s `mode: train` and RL-ViGen's own five
baselines reported no generalisation gap at all. **P12** fixed that. But `robo_make`'s signature is
`(name, frame_stack, action_repeat, seed, scene_id, mode)` and those call sites pass **four of
six**: the audit found the omitted argument that was wrong, patched it, and did not enumerate the
other omission standing beside it. **The lesson is cheap and general: when one argument turns out
to be unthreaded, check every argument of that call, not the one that produced the symptom.**

**No run does this.** `RL-ViGen-upstream/train.py` never passes `scene_id`, and
`wrappers/robo_wrapper.py:121` defaults it: `def robo_make(name, frame_stack=3, action_repeat=2,
seed=1, scene_id=0, mode=None)`. So `train_env` **and** `eval_env` are both scene 0. Our logs
confirm 10 episodes per eval point, not 100.

**RL-ViGen's own protocol is the ten-scene one.** From the NeurIPS supplemental (extract kept at
`docs/refs/rlvigen-supplemental-extract.txt`), §D.1.1:

> *"In the context of Robosuite, each difficulty level comprises **10 distinct scenes**. We perform
> 10 trials for each of these scenes (**100 trials in total**)."*

And `robo_config.yaml:31` confirms the range exists: `scene_id: 0   # 0~9 (for texture)`.

**So our evaluation asks an easier question than theirs.** We train on scene 0 and evaluate on
scene 0 with appearance and lighting re-randomised; they evaluate across ten distinct scenes. An
agent that has memorised scene 0's geometry is not penalised by our protocol and is by theirs.
That is a plausible mechanism for `drqv2` reaching 469.4 with SR 1.0 here against a published 3.6
— **without** requiring anything to be wrong with the algorithm or the training.

**Blast radius.** Every eval number this project has produced — [C35](#c35), [C42](#c42),
[C19](#c19)'s separation measurement, the floor in [C17](#c17) — was measured on scene 0. The
*ordinal* claims (it learns; the regimes differ) survive, because they are within-scene
comparisons. The claim that any of it measures **generalisation in RL-ViGen's sense** does not.

**Options**
1. **Pass `scene_id` through and evaluate over all ten.** It is the protocol's declared intent and
   the benchmark's own method. Requires a patch at the same site as [C43](#c43) — `train.py`'s env
   construction — so the two should be designed as **one** patch, not two.
2. **Re-value the protocol to `(0,)`** and state plainly that this is single-scene evaluation. Cheap
   and honest, but abandons the held-out-scene design and makes our numbers non-comparable to the
   benchmark by construction.
3. **Leave and declare.** Not defensible now that it is known — the field is hashed and asserts the
   opposite of what runs.

*My reading: (1), merged with [C43](#c43). Together they are one change to the eval seam —
"evaluate the right distribution, in both regimes" — and doing them separately would mean touching
the same eight lines twice and re-pinning the contract hash twice.*

**Also recovered from the supplemental, and each is its own small correction:**

| claim | our config | RL-ViGen paper |
|---|---|---|
| Door training budget | `cfgs/task/easy.yaml`: **1.1M** frames | **Table 6: 6e5** for Door (Lift 8e5) |
| Replay buffer | shipped `config.yaml`: **1e6** | **Table 2: int(1e7)** |
| Action repeat | 1 | **"Robosuite: 1"** — confirmed, [C37](#c37) settled |
| Difficulty names | code: eval-easy / medium / hard | paper: **Easy / Hard / Extreme** — the paper's *Hard* is the code's *medium* |

That last row also explains [C27](#c27): the code's `eval-medium` randomises the robot arm
(`except_robot=False`), which the paper describes under **Hard** — *"additional complexities of
moving light and alterations to the robotic arm's color"* — while the code's `eval-hard` swaps the
arm back and adds a video background. The non-monotone visual distance I measured is the
benchmark's own design, not an anomaly.

**The budget line matters immediately**: `drqv2` reached SR 1.0 at 80k of what the paper says is a
**600k**-frame task, not 1.1M — so we are at 13% of budget, not 7%.

**Confirmed at the source, 2026-08-18 — the sweep is not merely specified in the paper, it is
implemented, and in a file we do not run.** `RL-ViGen-upstream/eval.py:178-184`:

```python
if self.level == 'train':
    pass
else:
    if i < 100 and i % 10 == 0:
        count += 1
        self.eval_env = robo_make(..., scene_id=count)
```

Ten episodes per scene, rebuilt ten times, 100 episodes — the supplemental's §D.1.1 protocol
exactly, and `Protocol.eval_scene_ids` exactly. So the two-runner picture is now definite:
**`eval.py` sweeps scenes and produces the published numbers; `train.py` does not sweep and
produces ours.** `train.py` contains **zero occurrences of the substring `scene`** — this is not
a missing argument but a missing axis.

Three further facts close the mechanism:

- **`scene_id` is a real axis, not a label.** It reaches
  `get_custom_reset_config(task=task, mode=mode, scene_id=scene_id)`
  (`envs/robosuiteVGB/robosuitevgb/vgb_wrapper.py:92-96`), and at `eval-hard` it also selects the
  background clip (`video{scene_id}.mp4`, `vgb_wrapper.py:251`). Scenes differ in what is drawn.
- **Scene and difficulty are orthogonal.** `mode` picks the randomisation regime and `scene_id`
  picks the texture set (`robo_config.yaml:31`: `scene_id: 0   # 0~9 (for texture)`); `make_env`
  asserts `0 <= scene_id <= 9` independently of `mode`. Our single-scene runs therefore under-
  sample one axis while varying the other, which is not a smaller version of their measurement —
  it is a different one.
- **For robosuite, `eval.py` never passes `mode` at all** (lines 88, 89 and 184 all omit it),
  taking it from `robo_config.yaml`, while the habitat branch passes `mode='test'` explicitly at
  line 95. So on the difficulty axis their evaluator depends on config state, which is what
  patch **P1** exists to fix on our side.

**Now pinned by `tests/test_scene_coverage_contract.py`** (12 assertions, clone-facing). It fails
if the gap widens *or closes silently*: a fix must update the register in the same commit. Every
regex was red-green checked by mutating the upstream text and confirming the match flips. It also
asserts what makes this a FALSE-CERTIFICATION rather than a mere shortfall — a one-scene protocol
and a ten-scene protocol with equal episode counts **hash differently**, so the hash was always
capable of expressing the difference; nothing ever checked that a run honoured it.

## Resolved — decision, attempt, effect

**Commit** `e21e8052`

**Decision** Sweep the ten scenes and add a train-regime denominator — **one patch, P14**, because
C43 and C45 are one edit to one loop. Owner, 2026-08-19. Recorded in §4 form in
[`INTEGRATION-DELTA.md`](INTEGRATION-DELTA.md), with its alternatives and the result that would
show it wrong; `python scripts/decisions.py` enumerates it.

**Effect** `train.py`'s evaluation now rebuilds the env per scene across the ten `Protocol`
certifies, and measures a train-regime denominator at scene 0 — the distribution actually trained
on, deliberately not swept. Verified on a `drqv2` run: 24 environments built (two at startup, two
eval points of ten scenes plus one train-regime env) and `eval.csv` gained `train_regime_reward`
0.8525 beside a ten-scene `episode_reward` 0.8718. **Retention is computable from a training run
for the first time.** Cost: ~11× the environments per eval point, which comes out of the same
budget as seed count ([C18](#c18)). P14 is ENABLES and is in `Protocol.env_patches`, so every
pre-P14 number — [C47](#c47)'s retention included — sits on a different footing and is not
superseded.

---


> **Scope clarified 2026-08-25 — this is narrower than it reads, and it is now downstream of
> [C72](#c72).** The correction above is about the *training loops*: P14 gave five baselines a
> ten-scene in-run eval and seven were untouched. That remains true and the instrument still pins
> it. But retention is not produced by the training loop — it is produced offline by
> `scripts/eval_across_scenes.py`, which sweeps **ten scenes and both regimes for any checkpoint it
> can read**, whatever the run did internally. Fourteen such grids now exist.
>
> So the live question splits, and neither half is the one this entry was opened on:
>
> - **For the five natives** — retention is computable today and has been computed. Whether their
>   *in-run* eval also sweeps ten scenes is a question about log richness, not about the endpoint.
> - **For the other seven** — the blocker is not their training loop. It is that the offline
>   evaluator cannot read their checkpoints at all ([C72](#c72)), which the owner has **deliberately
>   deferred**. Patching seven training loops would not produce a retention number for any of them.
>
> **Corrected within the day, on challenge: this entry is NOT merely C72 from another angle, and
> the paragraph above understated it.** The split above is right about *mechanics* — the offline
> grid can compute retention for the natives and cannot read the other seven. It is wrong to
> conclude there is no decision here, because it silently treats **the offline grid's protocol as
> settled, and nobody ever settled it.**
>
> That protocol was *constructed*: 20 episodes per scene, ten scenes, two regimes, pooled — then
> scenes **dropped** by the floor and 25%-success guards ([C55](#c55)), with the surviving pool
> reported as the number. `regime_retention_report.py` says so in its own output: *"pooled over the
> N usable scenes only — **NOT RL-ViGen's protocol**, which averages all ten. Dropping scenes
> changes the estimand."* RL-ViGen averages ten scenes unconditionally; we average a
> data-dependent subset. Both are defensible and they are **different quantities**, and which one
> this project reports has never been decided — it was built.
>
> **So what is open here is the evaluation protocol itself**, and it is upstream of what any
> retention number means: how many episodes, which scenes, whether a guard may drop a scene from a
> pooled mean at all (versus refusing the whole cell), and whether the reported figure should be
> comparable to RL-ViGen's published one or deliberately not. [C48](#c48) is the same question seen
> from the anchoring side.
>
> **Action for a reader: still do not act unilaterally — but not because it is subsumed.** Because
> it is a design decision belonging to the owner, alongside [C72](#c72) rather than inside it.

### C23 — `Protocol.frame_stack = 3` was false for 4 of 12 {#c23}
**Class** FALSE-CERTIFICATION · **Status** RESOLVED

**Decision** annotate rather than re-value, and add `OBSERVATION_GEOMETRY` as the per-baseline
field that must be consulted. **Effect** the protocol hash still certifies one number, but the
field now names itself as insufficient and points at the one that is not. **This is the precedent
C1 should follow.** Commit `6f9ba507`.

### C24 — `ibac_sni`'s held-out number was a different quantity {#c24}
**Class** OURS · **Status** RESOLVED

**Decision** fix. `scripts/evaluate.py` discarded `info` and reported return only, while its own
`train.py:203` reports `success_rate` — so the one baseline with a real held-out evaluator
produced a number **the comparison table was silently comparing against eleven success rates**.
**Attempt** mirrored the accumulation idiom from `torch_rl/algos/base.py:99-171` rather than
inventing one; added the `eval-script` regime label to the collector. **Effect** ledger
+22/−3; `SR` now printed and parsed; 6 parser tests. Commit `9b71840b`.

### C25 — Two skips that read as passes {#c25}
**Class** OURS · **Status** RESOLVED

**Decision** remove both. `tests/test_success_metric.py` turned *any* probe fault — including one
caused by the patches under test — into a skip; `_shim/sitecustomize.py` swallowed a partially
applied shim silently. **Attempt** assert-with-diagnostics, and announce-with-traceback
respectively; the shim still does not re-raise, because it is a local convenience and the
authoritative runs are CUDA. **Effect** red-green verified both ways — mutating the probe's
RESULT token now fails both tests; injecting a shim fault prints `PARTIALLY APPLIED` and the run
continues. Commit `1b1db3be`. **Both were re-offences** of defects `REGISTER.md:104` and `:106`
had already removed *by name*: the register records lessons but does not execute them.

### C26 — Patch range said P11/P12 against a P13 registry {#c26}
**Class** UNDECLARED · **Status** RESOLVED

**Decision** fix the four documents and close the gap that allowed it. **Effect** the registry's
*content* was never at risk (`Protocol.env_patches` hashes it, a contract test pins the hash) —
what rotted was the number a person reads, which nothing checked.
`test_quoted_patch_range_matches_the_registry` now asserts on the highest id each document
mentions, red-green verified per document. Commit `a44f514c`.


### C46 — The scene axis is real, and nearly as large as the difficulty axis {#c46}
**Class** DESIGN-GAP · **Status** RESOLVED

[C45](#c45) established *from source* that we evaluate one scene where the benchmark averages ten.
It did not establish that this matters. If scenes were near-identical, C45 would be bookkeeping.

**Measured 2026-08-18, `scripts/probe_scenes.py`, Door at `eval-easy`, random policy, 84x84.**
Same instrument and same yardstick as [C19](#c19) so the two axes can be read against each other:
histogram TV distance, with a within-scene control (same scene, two seeds) as the floor.

| | TV distance | ratio to floor |
|---|---|---|
| within-scene floor (4 scenes, two seeds each) | **0.1486** median | 1.00 |
| between-scene, scene 0 vs each of 1-9 | 0.315-0.465, **median 0.398** | 2.12-3.13, **median 2.68** |
| **positive control**: `train` vs `eval-easy`, scene 0 held fixed | **0.4735** | **3.19** |

**All nine scenes separate from scene 0**, the weakest at 2.12x the floor. And the comparison that
matters is the last row against the second: **changing the scene moves the observation
distribution ~84% as far as changing the difficulty regime does** (0.398 vs 0.4735), measured in
one run against one floor, so the two are directly comparable.

**Replicated at a second regime, and the effect is larger there.** Re-run with the regime held at
`train` instead of `eval-easy`, so scene identity is the *only* variation (no colour or lighting
randomisation at all):

| regime held fixed | within-scene floor | between-scene median TV | mode-axis TV | scene / mode |
|---|---|---|---|---|
| `eval-easy` | 0.1486 | 0.398 | 0.4735 | **84%** |
| `train` | 0.0780 | 0.442 | 0.4666 | **95%** |

The floor halves when per-reset randomisation is removed, exactly as it should, and the
between-scene distance barely moves — which is what "scene is a separate axis from appearance"
predicts. **In both regimes the scene axis is within 16% of the entire train-to-eval-easy step.**

*An independent corroboration of [C19](#c19) falls out of this.* At `train` the positive control
reads **5.98x**, against C19's separately-measured 6-7x for the same axis — a different script,
a different sample, a floor of comparable tightness, and the same answer. That is the first time
any result in this project has been reproduced by an instrument built later and independently.

**Sensitivity to the floor, because "9/9 separated" is the floor-dependent half of this.** The
four within-scene controls span 0.064-0.182, so the choice of summary matters and is reported
rather than defended:

| floor | value | control ratio | weakest scene | median | scenes ≥2.0 |
|---|---|---|---|---|---|
| min (most generous) | 0.0641 | 7.39 | 4.92 | 6.21 | 9/9 |
| **median (used above)** | **0.1486** | **3.19** | **2.12** | **2.68** | **9/9** |
| mean | 0.1358 | 3.49 | 2.32 | 2.93 | 9/9 |
| max (most conservative) | 0.1818 | 2.60 | **1.73** | 2.19 | **7/9** |

Under the harshest reading two scenes fall below the 2x threshold and the claim becomes "7 of 9",
not "9 of 9". **What survives every choice is the floor-independent comparison**, because it is a
ratio of two distances and the floor cancels: the median between-scene distance is **84% of the
mode-axis distance**, and even the weakest scene is **67%** of it. That is the number this entry
rests on; the ratios are supporting detail. The positive control fires under every floor choice
(2.60 to 7.39), so no reading of the data makes this an instrument failure.

*(Aside, not load-bearing: the min-floor column puts the mode axis at 7.39x, close to
[C19](#c19)'s 6-7x — consistent with `probe_regimes` having sampled a tighter within-regime
control than this run's within-scene one. It is an explanation for why the two ratios differ, not
evidence for either.)*

**The positive control is why this is readable at all.** A flat scene result and an instrument
that cannot see anything produce the same table. The mode axis is known separated ([C19](#c19)),
it was measured in this same run, and it fired at 3.19x — so the scene numbers are a measurement
rather than a hope. `summarise()` refuses to return `NOT SEPARATED` when the control does not
fire, and `tests/test_probe_scenes.py` pins that (8 assertions, including the recorded Door
numbers, so a later edit to this entry cannot drift from the run that produced it).

**A third measurement that cuts against the obvious reading of the two above, and it is the one
to keep.** The distances so far are scene-to-scene *at a fixed regime*. The question a results
table actually asks is different: **how far is each protocol's evaluation point from the
distribution the policy trained on** (scene 0 at `train`)?

Measured twice, and **the two passes disagree in direction — which is the result**:

| pass | sample | our point (scene 0) | held-out median | held-out / ours |
|---|---|---|---|---|
| first | 3 scenes, 2 ep x 5 frames | 0.4689 | 0.4536 | **97%** |
| **second** | **9 scenes, 3 ep x 6 frames** | **0.4650** | **0.4908** | **106%** |

The second pass is the one to use — three times the scenes and a larger sample per config — and
it puts the held-out scenes *slightly further* from training (7 of 9 above ours, range 93-121% of
our distance, absolute 0.434-0.562 against our 0.465).

*One weak reason to prefer the second pass beyond its sample size: it points the way the geometry
requires.* Scene 0 **is** the training scene, so its distance from training is the mode effect
alone, while a held-out scene carries the mode effect *plus* whatever the scene change adds.
Held-out scenes should therefore be at least as far as scene 0, never nearer. The second pass
(106%, 7 of 9 above) satisfies that; the first (97%) violated it, which is the signature of noise
rather than of a real inversion.

**But the honest reading is that this instrument does not resolve the question at these sample
sizes.** A quantity that moves from 97% to 106% when the sample grows is not measured to better
than about ten points, and the per-scene range straddles our own value from both sides. What can
be said: **the difference is small — single-digit percent in either direction — not the kind of
asymmetry that would explain a 130x gap.** The appearance randomisation dominates the metric, and
a scene change moves you *sideways* at roughly the same radius rather than outward.

**So the earlier wording here and in [C45](#c45) — that single-scene evaluation is easier "in the
direction that makes the task easier" — is withdrawn.** Not because the opposite was shown, but
because nothing of the size that claim implied is visible: the effect is within this instrument's
resolution either way.
What survives is narrower and still consequential: scene 0 and scene k are *different places*, we
only ever visit one of them, and the benchmark averages ten. Whether the one we visit is easier is
**not decidable in observation space at all**, because the thing that would make it easier —
scene 0 being the scene the policy trained on, so its specific textures may be memorised — is
invisible to a marginal intensity histogram, which cannot tell a familiar arrangement from an
unfamiliar one at the same radius. That question needs the policy, and it is exactly what
`scripts/eval_across_scenes.py` was written to answer.

**Where scene 0 sits among the ten, which decides how bad a proxy it is.** The full 45-pair
distance matrix at `eval-easy`, one sample per scene:

| | mean distance to the other nine |
|---|---|
| **scene 0 (the training scene)** | **0.3885 — lowest of the ten, rank 1/10** |
| scenes 1-9 | 0.3984 - 0.4610 |
| across all ten | mean 0.4214, sd 0.0225 (≈5%), range 0.3885-0.4610 |

**Scene 0 is the most central scene, not an outlier** (z = -1.46 against the ten, on one sample
each — suggestive, not significant at n=10). The ten are fairly evenly spread: 5% sd on the mean
pairwise distance, with an 18% spread between the most central and most peripheral.

This cuts *for* the current setup rather than against it. If exactly one scene must be evaluated,
scene 0 is the least unrepresentative available choice, and the earlier finding — that our
evaluation point is the same distance from training as theirs — is consistent with it. **What
remains true is only that ours is one point and theirs is an average of ten.** Taken together
with everything above, the observation-space case against our protocol is weaker than it looked
two measurements ago: what is left is a coverage claim, not a bias claim, and whether the
coverage matters is a return-space question.

**Answered in return space — see [C47](#c47).** The pre-registered measurement below returned
retention **0.278**, held-out gap **4.37x** the within-scene control. The coverage gap this entry
established costs real return; the observation-space caution above was the right posture and the
return-space answer is the stronger one.

**Consequence for [C45](#c45) and [C37](#c37).** Scene 0 is the *training* scene. Evaluating on it
holds fixed an axis that carries roughly as much visual variation as the entire train-to-eval-easy
step this project calls generalisation. So our `eval-easy` number is not a noisier version of
theirs — **it withholds most of one of the two axes the benchmark varies.** Which direction that
biases the number is not answered here: the measurement above puts both protocols at the same
distance from the training distribution, so any "easier" reading has to come from the policy, not
from the pixels.

**Pre-registered reading of the pending return-space measurement, written before it ran.** A
`drqv2` checkpoint at 50k frames is being evaluated across all ten scenes at `eval-easy`, with the
training scene re-run at a second episode seed as the within-scene control. Recorded in advance so
the interpretation is not chosen after seeing the number:

- **held-out gap ≤ 2x the same-scene gap** → this design did not resolve a scene effect in return.
  That is a *failure to detect*, not evidence of invariance, and C45 stays a comparability
  problem rather than a performance one.
- **held-out gap ≫ same-scene gap, retention well below 1** → scene generalisation costs real
  return, and every number this project has reported overstates it.
- **retention above 1** → the training scene is not the easiest, which would contradict the
  intuition C45 started from and would need explaining rather than reporting.

In all three cases the number is a property of **one checkpoint of one run**, and [C41](#c41) now
puts run-to-run variation at ~49% by 40k frames — so it bounds this policy, not the method.

**What this does not say.** It is a claim about the *observation stream under a random policy at
initialisation*, not about return. It cannot say how many points of return the scene axis is
worth; a trained policy that ignored texture would experience less separation than this, one
overfitted to scene 0 more. It is also one-sided by construction — a histogram distance can miss
structural differences, so a large ratio is evidence of separation while a small one would not
have been proof of its absence. Converting this into a return-space number needs a trained
checkpoint evaluated across scenes, which is the natural follow-up and needs a training run that
survives to a saved snapshot. **And demonstrated, not hypothetical: [C47](#c47) pairs these distances with per-scene returns and finds the visually *nearest* held-out scene among the worst performers and the *furthest* among the best. This instrument locates the axis; it cannot rank difficulty along it.**

**Decision** measure the scene axis with the same instrument and control structure already used
for the regime axis ([C19](#c19)), rather than reason about it — and build the positive control
into the same run so a flat result could not be mistaken for a working instrument.
**Effect** the axis is real: every held-out scene separates from scene 0 (9/9 at the median floor,
7/9 at the most conservative), and the between-scene distance is **84% of the difficulty axis at
`eval-easy`, 95% at `train`**, measured against the same floor in the same run. That is enough to
make [C45](#c45) more than bookkeeping — the two protocols sample different points, so no current
number is comparable to RL-ViGen's — and it moves [C37](#c37)'s leading explanation from
`action_repeat` to scene coverage.

**What the entry deliberately does NOT conclude**, after three further measurements that arrived
during the same session: that our number is *inflated*. Held-out scenes sit at the same distance
from the training distribution as ours (within this instrument's resolution), and scene 0 is the
most central of the ten. **The claim is coverage, not bias.** Whether the missing coverage costs
return is a separate question, pre-registered above and pending. Commit `56ab2d53`. *(This entry first cited 2117835c — deliberately written without backticks, because in this register a ticked hash means "you can look this up" and this one you cannot. The amend that recorded it **orphaned** that commit — `git cat-file -t` still resolves it, because it survives as a dangling object until gc, but **no branch reaches it** and it is not the commit holding this work. A hash cannot be written inside the commit it names in one step, and amending to fix that only moves the hash again. `test_resolved_items_name_a_commit` checks the SHAPE of a hash, not that the object is reachable, so it stayed green throughout.)*


### C47 — Held-out scenes retain ~25% of training-scene return, and training does not fix it {#c47}
**Class** DESIGN-GAP · **Status** RESOLVED

The measurement [C46](#c46) named as its follow-up and [C45](#c45) needed to stop being a
bookkeeping argument. **The reading below was pre-registered in C46 before the run.**

> **Two later findings bear on this entry; neither withdraws it.**
> [C55](#c55) measured the random-policy floor at **1.82**. Eight of the ten rows below clear it
> comfortably, so the retention figure is a real drop between real numbers — but **scene 9's 0.78
> is below chance**, making that row an absence of performance rather than a small amount of it,
> and scene 4's 8.09 is marginal. The aggregate silently includes one row of each.
> [C54](#c54) found that this checkpoint's stored training pixels match `eval-easy`, not the
> clean instance. The scene comparison below is unaffected — it varies scene with the regime
> held — but the phrase "the TRAINING scene" for row 0 is an assumption this entry inherited and
> did not check.
>
> **A third, added 2026-08-25 — and it lands on this entry's own wording.** [C69](#c69): the
> evaluator that produced these rows did not seed the RNG placing the door or perturbing the
> robot's starting joints, so **each scene's ten episodes ran at ten uncontrolled object
> placements**, and the scenes were not held to a common one. The phrase below — *"deterministic
> CPU inference"* — is true of the policy and was read, here and elsewhere, as though it made the
> measurement deterministic. It did not: the nondeterminism was in the environment, not the
> network.
>
> **Magnitude, not just direction.** Two pre-fix grids of one checkpoint put a single scene's mean
> at **84.61 vs 42.75** ([C67](#c67)), so a per-scene row of this kind can move by a factor of two
> at ten episodes. The aggregate "~25%" averages ten such rows and is correspondingly steadier, so
> the entry's **direction is not in doubt** — held-out scenes clearly retain far less. What no
> longer holds is reading any individual row as a measured property of that scene, and the ranking
> of adjacent rows carries no weight at all. [C46](#c46)'s pixel distances inherit a smaller
> version of the same thing, since each was one rendered reset and the door's position varies
> between resets; there the effect is a few percent against separations many times larger.
>
> Re-derivable deterministically now, at the cost of one evaluation pass.

`scripts/eval_across_scenes.py`, `drqv2` snapshot at **50,000 frames**, Door, regime pinned at
`eval-easy`, 10 episodes per scene, deterministic CPU inference:

| | return | 95% CI | SR |
|---|---|---|---|
| **scene 0 — the TRAINING scene** | **133.29** | [108.96, 156.00] | 0.10 |
| held-out scenes 1-9 (n=90 episodes) | **37.01** | [29.05, 45.36] | **1/90 = 0.011** |
| **retention** | **0.278** | **[0.218, 0.340]** | |

**Cross-checked against upstream's own evaluator, which is an independent validation nobody
asked for and it passed.** `train.py`'s in-loop eval logged **118.63** for this same checkpoint at
50k — same scene, same regime, same ten episodes — on MPS with its own episode seeds. This script
reports **133.29** on CPU with seed 0. The gap is **14.66 (12.4%)**, comfortably inside the
**22.01** same-scene episode noise measured below. **Two independently written evaluators, two
devices, two episode seeds, agreeing to within what episode sampling already explains** — so the
scene-0 figure is not an artifact of this script.

**The within-scene control is what makes this readable.** Scene 0 re-run at a second episode seed
scores **111.28**, so ten episodes of the *same* scene differ by **22.01**. The held-out drop is
**96.28 — 4.37x that noise**. This is the pre-registered "held-out gap ≫ same-scene gap" case:
scene generalisation costs real return, and it is not an artifact of episode variance.

**Read plainly: evaluating only on the training scene overstates this policy's held-out
performance by 3.6x.**

**The per-scene spread is the part that should worry a reader most.**

| scene | 3 | 7 | 6 | 5 | 1 | 2 | 8 | 4 | 9 |
|---|---|---|---|---|---|---|---|---|---|
| return | 77.34 | 68.77 | 59.18 | 44.27 | 35.53 | 23.30 | 15.83 | 8.09 | **0.78** |

A **99x range** across scenes the benchmark treats as one difficulty level. **And the floor was measured per scene rather than borrowed**, because [C17](#c17)'s floor is a
*scene-0* number and a scene-0 floor is not automatically the floor elsewhere. Random policy,
8 episodes each:

| scene | trained return | random floor | trained / floor |
|---|---|---|---|
| 0 (training) | 133.29 | 1.178 [0.798, 1.567] | **113x** |
| 4 | 8.09 | 1.025 [0.743, 1.397] | 7.9x |
| 9 | **0.78** [0.73, 0.86] | **1.148** [0.753, 1.662] | **0.68x** |

**The floor is flat across scenes (1.03-1.18), so the 99x spread in trained return is a fact about
the policy, not about some scenes being intrinsically harder.** That is the control this
comparison needed and it holds.

On scene 9 the trained policy does **not** beat its own scene's random floor — point estimate
below it, intervals overlapping. The defensible claim is **"no better than random"**; *"worse than
random"*, which an earlier draft of this entry asserted from the borrowed scene-0 floor, is **not**
established at n=8. A policy scoring 113x the floor where it trained scores 0.68x on scene 9. An average over ten
scenes is not a milder version of the scene-0 number; it is dominated by scenes where the policy
does not function.

**The observation-space proxy does not predict which scenes are hard — and that is a limit on
[C46](#c46), not a footnote.** Pairing each held-out scene's TV distance from scene 0 with its
return:

| scene | 4 | 2 | 7 | 8 | 9 | 1 | 3 | 5 | 6 |
|---|---|---|---|---|---|---|---|---|---|
| TV from scene 0 | 0.315 | 0.330 | 0.371 | 0.379 | 0.398 | 0.407 | 0.415 | 0.448 | **0.465** |
| return | 8.09 | 23.30 | 68.77 | 15.83 | **0.78** | 35.53 | 77.34 | 44.27 | 59.18 |

The naive expectation — further looks different, therefore harder — **is not supported**. The
visually *nearest* scene (4, TV 0.315) returns **8.09**, among the worst; the visually *furthest*
(6, TV 0.465) returns **59.18**, among the best; and the catastrophic scene (9, return 0.78) sits
mid-distance. The rank correlation is *positive* (Spearman +0.50, Pearson +0.50), i.e. pointing
the opposite way to the intuition, but at **n = 9** that is a t of ~1.5 on 7 df and resolves
nothing. **The defensible claim is the negative one: a marginal-intensity distance cannot be used
to predict, rank, or substitute for a return measurement.** C46 established that the axis exists;
it cannot say which points on it a policy will fail at, and this is the concrete demonstration.

**What this does and does not license.**

- It **does** settle [C45](#c45): the single-scene protocol is not a bookkeeping discrepancy. Every
  return this project has reported is a training-scene number, and the benchmark's own protocol
  averages ten.
- It **does not** generalise to the method. One checkpoint, one run, one task, 50k frames — and
  [C41](#c41) puts run-to-run variation at 30-50% at these budgets, so a *different* run's
  checkpoint would give a different retention. The **within-run** comparison is controlled; the
  number's transfer to `drqv2`-in-general is not.
- It **does not** speak to convergence. At 50k frames this policy is mid-training; a converged one
  might generalise better or might have overfit the training scene harder.
- Success rate is **not** the endpoint here: 0.10 on the training scene against 1/90 held out is
  directionally consistent but far too sparse to carry a claim.

**Answered at 100,000 frames: no. More training does not buy scene generalisation.**

| | 50k | 100k |
|---|---|---|
| training scene 0 | 133.29 | **455.66** (SR 1.00) |
| held-out 1-9 | 37.01 | **108.23** [75.83, 142.44] |
| **retention** | 0.278 [0.218, 0.340] | **0.238** [0.166, 0.313] |
| same-scene control gap | 22.01 | **7.58** |
| held-out gap / control | 4.4x | **45.8x** |
| held-out SR | 1/90 | 22/90 |

The policy roughly tripled on the scene it trained on (**3.42x**) and on the held-out scenes
(**2.92x**), leaving **retention statistically unchanged** — 0.278 → 0.238 with heavily overlapping
intervals. **Pre-registered case: "flat or falling", the outcome named in advance as the worse
one.** *Falling* is not established and is not claimed; *not improving* is.

**The control tightened threefold** (22.01 → 7.58) because the policy is now near-deterministic on
scene 0, which pushes the held-out gap to **45.8x the same-scene noise**. Whatever else is
uncertain here, the gap is not episode variance.

**The per-scene pattern became bimodal rather than uniformly better.** Scene 5 now returns 383.40
at **SR 1.00** and scenes 2 and 3 reach ~223 — the policy genuinely solves some held-out scenes.
But scenes 4 (**1.63**) and 9 (**2.01**) sit at their own random floors (1.03 and 1.15), and 1, 7,
8 remain between 12 and 25. **Training converted "bad everywhere" into "solved on some, floor on
others"**, which is a different failure and arguably a worse one to average: the ten-scene mean is
now dominated by which scenes happen to be in it.

**Both measurements are preserved**: `eval_across_scenes_50k.log` and `..._100k.log` beside the
run, with `snapshot_50k_frames.pt` and `snapshot_100k_frames.pt`. The same run continues to 120k and saves a snapshot at 100k
(`snapshot_100k_frames.pt`, copied because `train.py` overwrites `snapshot.pt`); the eval reruns
automatically and writes to `scene_return_100k.log` beside this run. **Pre-registering the reading
again**: retention *rising* toward 1 would mean scene generalisation is something training buys
and 50k was simply early; retention *flat or falling* would mean the policy is specialising on
scene 0 as it improves, which is the worse outcome and the one that would make the single-scene
protocol actively misleading rather than merely incomplete. Either way the 50k figure above stands
on its own control and is not superseded by the later one — they are two points, not a correction.

**Decision** run the pre-registered measurement rather than continue arguing from observation
space, with the training scene re-run at a second seed as the control.
**Effect** retention **0.278 at 50k and 0.238 at 100k** — statistically unchanged while absolute
performance tripled — with the held-out drop at **4.4x** and then **45.8x** the same-scene noise.
Two checkpoints, the second pre-registered before it ran. C45 is promoted from a comparability
defect to a **result-invalidating** one for every generalisation claim made from single-scene
runs, and [C43](#c43)'s regime-retention question now has a scene-retention sibling with two
numbers. **More training is not the answer**: it raised both figures together and left the ratio
where it was. Commit `d0f15200`.


### C48 — Nothing has ever reproduced a published RL-ViGen number {#c48}
**Class** DESIGN-GAP · **Status** OPEN

Every external comparison runs one direction: we read their table (`scripts/rlvigen_reference.py`
over `results/evaluation_score.xlsx`, [C31](#c31)) and compare our numbers to it ([C37](#c37)).
**Nothing has run their evaluation path on a policy and landed on one of their cells.**

`tools/crosscheck_against_rlvigen_eval.py` is the nearest thing and is a different check. It runs
one policy through `rlgen.evaluate.evaluate()` and through a **transcription** of
`eval.py::robo_eval`, establishing that two implementations agree on the same input. Three limits,
and the first is the one that matters:

- **Implementation agreement is not reproduction.** Two evaluators can agree perfectly while both
  compute a quantity the reference never reported — which is exactly what [C45](#c45)/[C47](#c47)
  turned out to be.
- It validates the **superseded port**, not the clones that produce numbers.
- It needs no trained policy, so it tests a loop and never a number.

**Why this is the project's missing positive control.** [C37](#c37) has been rewritten twice to
explain a 130x gap against their published `DrQ-v2`, and [C45](#c45)/[C47](#c47) then showed the
two figures were never the same quantity. One reproduced cell would have surfaced that on contact,
before any of the explanations were written.

**This is an unmet obligation from our own directive, not a proposal.**
[`porting-directive.md`](../../../docs/porting-directive.md) §3 defines the parity tiers, of which
**T3 is "distributional agreement with the reference's published results on the reference's own
domain"**, and §4 closes with:

> Reach T3 on the reference's own domain before adapting. Then a poor number afterwards isolates
> to the adaptation rather than leaving "correctly ported but ill-suited" and "quietly broken"
> indistinguishable.

That is exactly the ambiguity [C37](#c37) sat in for two rewrites. **No module here has reached
T3.**

**"Distributional agreement" needs a tolerance, and the tolerance is not ours to choose.**
[C18](#c18) now bounds it: at five seeds this design resolves differences in return of about
**31%**, so a T3 claim made at that budget is satisfied by any number within roughly a third of
the published one. Two consequences, and the second is the uncomfortable one:

- A future sentence of the form *"we reproduced their Door number"* means **"we could not
  distinguish our number from theirs at a resolution of ~31%"**. That is a real result and a weak
  one, and it must be written the second way.
- The failure direction is worse than the success direction. If our number lands within 31% we
  learn almost nothing, because "correctly ported" and "quietly broken by up to 30%" both produce
  that outcome — which is precisely the ambiguity §4 introduced T3 to remove. **At five seeds, T3
  cannot do the job §4 assigns it.**

So the tolerance has to be stated *before* the comparison, and if the intended claim is stronger
than 31%, the seed budget — not the tolerance — is the thing that has to change ([C18](#c18) puts
10% at 48 seeds per arm). This does not add a decision to the queue; it prices one already in it.

**But the obligation is not uniform across the twelve, and the naive reading is wrong.** "Reproduce
their published numbers" means something different per origin domain:

| group | baselines | what T3 means, and whether it is reachable |
|---|---|---|
| published on **our** domain | `curl`, `drq`, `drqv2`, `sgqn`, `svea` | RL-ViGen published robosuite cells for these. T3 **is** this entry's anchor, directly. **5 of 12.** |
| **DMC** lineage | `rad`, `soda`, `alda` | Continuous → continuous. The unmodified clone can run its own domain, so pre-adaptation T3 is available in principle. |
| **discrete-action** lineage | `ppg`, `idaac`, `ibac_sni`, `ctrl` | Procgen / coinrun, `Categorical` heads. **The adapted module cannot run its own domain at all** — the action space changed, which is the case §4 names ("for a change of action space, the policy distribution and what lies downstream of it"). T3 can only be reached by the *unmodified* clone, a different artifact from the one we run. |

For that last group §4 anticipates the outcome — **as an obligation, not a licence.** It is a
diagnosis arrived at after tracing, not a permission granted in advance, and §4's own instructions
run the other way: find the surface at which the missing assumption enters and *"treat that
surface, not the whole module, as the adaptation"*, recording branch points with the result that
would show each choice wrong. Adaptation and *becoming a different method* are different things,
and nothing here licenses reaching for the second to avoid the work of the first. The consequence
is also heavier, not lighter: a module that concluded this cannot appear in a results table under
the method's name.

> "This method cannot be ported without becoming a different method" is a permitted conclusion and
> must be stated as one.

**So this entry's anchor covers 5 of 12.** For the other seven no published robosuite number exists
from anyone — RL-ViGen's table holds `PIEG` and `SRM`, which we do not have, and none of our seven
— so "reproduce a published cell" is not merely expensive there, it is undefined. What §4 asks of
them is a different check, and for the discrete-lineage four the strongest honest outcome may be
T4 plus the explicit statement that they became different methods.

**Cost, which is the whole reason this is open.** It needs a policy trained at their budget —
Supplementary Table 6 gives **6e5** frames for Door — which is remote compute. **Recorded without
an ETA on purpose: this happens once compute exists. Not near, not far, not scheduled.**

**DEFAULT SET, 2026-09-04 — option 1, and the cost objection that kept this open has largely
dissolved.** This entry was written when the project had no compute and priced the anchor as "the
largest single compute item on the books". Compute exists now, and the decisive fact is narrower
than that: **if §3b #5 is taken at 6e5 — RL-ViGen's own published Door budget, which is what makes
it the anchor budget — then the anchor run and production seed 1 of `drqv2` are the same
artifact.** The marginal training cost of the anchor is then zero. What remains is running *their*
eval path on a checkpoint the production run produces anyway: one offline job, on the order of the
~60 RUB a ten-scene grid costs, and it must run in the container ([C95](#c95)).

**Scope of the default: `drqv2` alone.** It is the baseline whose published Door cell drove
[C37](#c37) through two rewrites, so it is where an anchor buys the most; and the table above
already establishes that the anchor is *undefined* for seven of the twelve, so a wider scope is not
available at any price.

**What the anchor may be claimed to show, stated before the comparison rather than after.**
[C18](#c18) puts this design's resolution at ~31% *at five seeds*; at the three of §3b #4 it is
worse than that. So this anchor **can falsify a gross discrepancy and cannot confirm fidelity** —
it is powered against the 130x shape [C37](#c37) sat in for two rewrites, and against nothing
subtler. A sentence of the form "we reproduced their Door number" is not licensed by it. That is a
weak result, and it is worth having precisely because the failure it screens for already happened
once here.

**This default is CONTINGENT on §3b #5 and inherits its status.** If the production budget is taken
at our invented 5e5 rather than their sourced 6e5, the artifacts stop coinciding, the anchor needs
a run of its own, and the original cost objection returns intact. Recorded as a default awaiting
approval, not as a settled decision.

**Options**

1. **Anchor first.** Train one baseline at their budget (6e5 Door), run their eval path, compare to
   their cell. *Effect*: the project gains its only external check, and every later comparison is
   read against it. *Cost*: the largest single compute item on the books, and it delays [C21](#c21).
2. **[C21](#c21) first.** Measure throughput on the target hardware before committing to a budget.
   *Effect*: the anchor run gets costed before it is launched, rather than discovering mid-run that
   6e5 frames does not fit. *Cost*: the anchor slips behind it.
3. **Shape-only anchor, at a reduced budget.** Run their eval path on a policy trained well short of
   6e5 and compare *protocol shape* rather than the number — does it sweep ten scenes, does the
   regime resolve as expected, does our reading of their pipeline hold. *Effect*: buys most of what
   [C45](#c45) needed at a fraction of the cost, and would have caught C45 on contact. *Cost*: it
   cannot confirm a value, so [C37](#c37) stays open.
4. **Decline the anchor.** State in the write-up that no cell was reproduced and that all external
   comparison is table-reading. *Effect*: honest, and concedes the positive control a reviewer will
   ask for.

*My reading: (3) is underrated — it is cheap, it targets the failure that actually occurred, and it
does not compete with [C21](#c21) for a full training slot. But this is your call and the ordering
against C21 is the substance of it.*

**Your decision** whether the first compute goes here or to [C21](#c21)'s throughput benchmark.

---

### C49 — The env `seed` argument is inert in train mode {#c49}
**Class** INHERITED · **Status** RESOLVED · **Commit** `d9eeca6a` · **Cross-ref** [C20](#c20)

`make_env(task_name, seed, ...)` stores `self.random_state = np.random.RandomState(seed)` in
`VGBWrapper`, and that stream is read **only** by the colour, camera, lighting and dynamics
modders. In `mode='train'` all four `randomize_*` flags are False, so `self.modders` is empty and
`except_robot` is True, and nothing ever draws from the stream.

**Measured, not just read.** `scripts/probe_seed_effect.py` crosses `env_seed ∈ {0,1}` ×
`global_seed ∈ {0,1}` × `mode ∈ {train, eval-easy}`, resetting numpy/random/torch immediately
before both construction and reset so the axes are the only free variables:

| mode | env seed moves the observation? | global seed does? | distinct obs / 4 |
|---|---|---|---|
| eval-easy | **yes** | yes | 4 |
| train | **no** | yes | 2 |

The eval-easy row is the positive control and it fired, so the train row is a null with a stated
detectable effect rather than an instrument that sees nothing. Scope: Door, scene 0, first
observation after reset. That last limit is narrower than it looks — with the global stream
pinned and no modder active, an identical first observation implies an identical trajectory under
identical actions, because placement is the only other stochastic input and it is drawn from the
global stream.

**Consequence.** `seed=args.seed + i` per parallel env — in `idaac/ppo_daac_idaac/envs.py:101`,
`runnable/ctrl/vec_env.py:601`, `runnable/ppg/phasic_policy_gradient/envs.py:44` — buys nothing during training. Parallel envs still differ,
but through successive draws on the *shared global* stream, not through the per-env seed they
appear to be given. Nothing is broken by this; it means the mechanism people would point to as
the source of env diversity is not the one supplying it.

**Decision** Measure it rather than argue from the source. The reading of `vgb_wrapper.py` was
already unambiguous, and reading has been wrong three times this week — most recently in the
screen (a) instrument that produced this entry's sibling. A crossed design with a positive
control costs eight env constructions and settles it.

**Effect** The claim is now measured, not inferred, and the control that makes it a null rather
than an absence is part of the record. Two things downstream changed: [C50](#c50) exists at all —
it is a direct consequence, and would not have been visible from the source comment it
contradicts — and any future reasoning about "N parallel envs with different seeds" as a source
of training diversity now has a measurement standing against it.

---

### C50 — IDAAC's instance labels have no referent on this target {#c50}

> ### Recommendation, 2026-09-02: keep one scene, and report the vacuity as the result
>
> The owner put the branch point precisely: *"I wonder if it might need e.g. to train on two
> scenes; but if such, shouldn't we explicitly assume it's gonna be better just by sake of two
> scenes."* That second clause is the whole argument against the obvious fix, and it holds.
>
> **Option (b), two scenes for `idaac` only.** Gives the order classifier a real referent — and
> makes `idaac` the one baseline trained on twice the visual diversity of the other eleven. Any
> generalisation gap it then shows is confounded with the extra scene, irreducibly, because the
> two changes are applied together and cannot be separated after the fact. This is the option the
> owner's remark rules out, and it is right to rule it out.
>
> **Option (c), two scenes for all twelve.** Comparable again, but it is a different benchmark:
> every baseline's training distribution changes, `train_scene_ids` changes inside `Protocol.hash`,
> and no number from before is poolable with a number from after. **And it still does not serve
> the mechanism.** IDAAC's instance loss was designed against Procgen's *200* training levels; this
> environment offers **ten scenes in total**, of which the protocol trains on one. Two is not
> "many instances", it is two — the classifier would get a label with a referent and almost no
> support. So (c) pays the full cost of changing the protocol for all twelve and still under-serves
> the one baseline it was meant to help.
>
> **That is what makes (a) more than a default.** The benchmark cannot serve this mechanism at any
> scene count it can offer: 10 available against the 200 the method assumes, and 1 by protocol.
> Keeping a single scene is therefore not ducking the question — **the honest finding is a property
> of the method-benchmark pairing, and it is reportable**: *IDAAC runs here with its
> instance-invariance term active and inert, because instance identity is not recoverable from the
> observation ([C49](#c49)), and no scene count this environment offers would change that by
> enough to matter.* A result table should carry that sentence beside IDAAC's row rather than
> presenting its number as a clean measurement of IDAAC.
>
> **What this does not settle.** It does not say the term is harmless: it still consumes gradient
> and compute, and `scripts/audit_eval_state.py` records that `idaac` additionally *samples* its
> evaluation actions where nine others take the mode. Both belong beside the row. Nor does it
> license dropping the term — that would be an authored deviation removing the method's signature
> component, which is the opposite of what this project measures.

**Class** OURS · **Status** MONITORED · **Cross-ref** [C49](#c49)

**Handicap — affects:** idaac
*its instance-invariance loss runs against a label with no referent here, so the mechanism is inert while still costing compute*

`runnable/idaac/ppo_daac_idaac/envs.py` wraps each env in `_LevelSeed(..., args.seed + i)` to supply
`info['level_seed']`, justified in its own comment: *"An RL-ViGen env's visual instance is fixed
by its seed at construction, so the seed IS the level id."* [C49](#c49) measures that sentence
and it is **false in train mode** — the seed fixes nothing there.

**Credit where the port was already careful, because it changes what the finding is.** The same
docstring goes on: *"DIFFERENT FROM PROCGEN … a Procgen env draws a new level every episode, so
one rollout spans many instances; here each env is one instance for the whole run, and instance
diversity per batch is capped at `num_processes`. Recorded, not silently equated."* So the port
did **not** claim Procgen-like diversity; it recorded the reduction and flagged it as a Part 2
question. The mechanism is live, not vestigial — `runnable/idaac/ppo_daac_idaac/storage.py:248-254` groups observations by
`levels` to build the order classifier's same-instance pairs.

What C49 falsifies is one sentence inside that otherwise careful note, and it is the sentence the
whole construction rests on: instance identity is grounded in a *visual* difference that does not
exist in train mode. The correction is sharper than the caveat already recorded. Diversity is not
merely **capped at `num_processes`** — in the visual channel it is **zero**.

Stated carefully, because the loose version invites a fair objection. The parallel envs do
**not** produce identical observations: placement is redrawn per reset and trajectories diverge,
so their pixels differ constantly. What is identical is the **visual instance** — textures,
lighting, camera — which is the property `level_seed` exists to name, and which is fixed for all
of them by one scene with no randomisation ([C51](#c51)).

The failure is that the variation which *does* exist is not a stable function of the env index.
It comes from successive draws on the **shared global** stream ([C49](#c49)), so two episodes
from slot *i* differ from each other exactly as much as an episode of slot *i* differs from one
of slot *j*. The order classifier's "same instance" and "different instance" pairs are therefore
two samples from one distribution, and no feature of the observation correlates with the label
being predicted. Not "the images are the same" — "instance identity is not recoverable from the
image", which is the claim that actually bears on a loss trained to decode it.

This is a §4 branch point in the porting-directive's exact sense: a structural property of the
original that the mechanism depends on, which the target does not have. So `level_seed` labels an
**env slot**, and the contents of that slot are not stable across resets.

A mechanism given labels with no referent should have no effect, which is a mechanistic account
of something previously seen only as a wide-CI null. It does **not** license the reverse claim —
"the loss does nothing" is still an untested measurement, and C41's noise floor swamps the
differences in question.

**Measured directly, 2026-08-20 — the label is not decodable, and the proposed fix is.**
Everything above argues from mechanism ([C49](#c49)'s inert seed, [C51](#c51)'s single scene).
`scripts/probe_level_seed_decodable.py` asks the question itself: build eight envs exactly as
`idaac/ppo_daac_idaac/envs.py:101` does (`seed=args.seed + i`), sample 25 reset frames from each,
and train a nearest-centroid classifier to recover which env a frame came from.

| arm | accuracy | 95% CI | chance | |
|---|---|---|---|---|
| **`scene_id` (control)** | **1.000** | [0.954, 1.000] | 0.125 | decodable |
| `level_seed`, eval-easy | 0.125 | [0.069, 0.215] | 0.125 | **at chance** |
| `level_seed`, train | 0.125 | [0.069, 0.215] | 0.125 | **at chance** |

The control is the point. A first attempt used `eval-easy` as the control — on the strength of
C49 measuring the env seed as live there — and it **failed** at 0.113, so the probe refused to
report. The flaw was the arm: eval-easy re-randomises textures every reset, so an env has no
single appearance and 25 resets average over the very variation the seed drives. Swapped to
`scene_id`, which C51 measured as visually distinct, the control reaches **1.000** and the nulls
below it become readable.

Two things follow, and the second was not expected:

- **`level_seed` is at chance in `eval-easy` too**, not only in train mode. The entry above argues
  the train-mode case from mechanism; the measurement says a single observation carries no
  information about which env produced it in either regime.
- **Option 2 is now measured rather than assumed.** Binding each env to a distinct `scene_id`
  gives a label a classifier recovers perfectly. Whatever else is wrong with that option — and it
  does change the training distribution — "the label would have a referent" is established.

Scope and limits: Door, scene 0, first observation after reset, nearest-centroid on 3×21×21. The
design resolves decodability down to **0.215** against 0.125, so a small effect could hide. A
stronger classifier could only raise accuracy, which makes near-chance here the conservative
direction for this entry's claim rather than proof that no model could decode it.

**Options** — three, none of them free:

1. **Disclose and keep.** IDAAC runs, its instance term is inert-by-construction, and the results
   table says so. Cheapest; makes the IDAAC row a measurement of IDAAC-minus-its-mechanism.
2. **Give the labels a referent** — bind each parallel env to a distinct `scene_id`, making the
   slot index a real visual instance. **Now known to be cheap**: [C51](#c51) measures the scene
   axis as live under `mode='train'`, so this is one argument to `robo_make`, not new machinery.
   Closest to IDAAC's intent — and cheapness is not the argument for it. It changes what the
   training distribution *is*, so it is an ENABLES-class change with a new protocol hash, it
   collides with [C45](#c45)'s scene axis rather than being independent of it, and it would make
   IDAAC the only baseline trained on a different distribution unless all twelve move together.
3. **Declare IDAAC unportable to this target** and say so. §4 permits this conclusion; it is an
   obligation to state it, not a licence to reshape the method until it fits.

My reading favours 1 for the first table and 2 as the follow-up, because 2 changes the training
distribution and would make IDAAC's row incomparable with the other eleven — which is the exact
defect this project exists to avoid.

---

**SETTLED DEFAULT, 2026-09-04 — option (a): one scene, and the vacuity is the result.** Extra
scenes would not restore the episode-length variation the original objective relies on, while
they would make IDAAC's training distribution incomparable with the other eleven.

**The mechanism argument, corrected and sharpened.** My earlier summary of this entry said IDAAC's
"instance labels have no referent". `SUPERVISOR-BRIEFING.md`:279 corrects that and the correction
matters: the discriminator does **not** classify level identity. It takes two observations from the
**same trajectory** and predicts which came first, adversarially, so the encoder is pushed to strip
temporal-position information. **That mechanism operates fine on one scene — it is not inert.**

**What is absent is the reason to expect a gain**, and it is not scene count. The paper's own chain
is *"since different levels have different lengths, capturing such information … translates into
capturing information specific to that level"*, and its stated condition is *"partial observability,
a set of goal states, and **episode length variations**"*. Door has a **fixed 500-step horizon**.
Adding scenes does not add episode-length variation, so **option (b) would not repair the mechanism
even setting aside the confound** — which is the argument the owner's own objection anticipated
from the other side.

**Consequence for reporting**: `idaac`'s number is a valid measurement of *idaac as shipped, on a
target whose structure its auxiliary objective cannot exploit*. That is a finding about the pairing,
not a defect in the run, and it must be stated wherever idaac is ranked — otherwise a low row reads
as "the method is weak" when the honest reading is "the benchmark does not contain the structure the
method was built for".

**What would overturn this**: a task variant with variable episode length, which would make the
paper's condition hold and turn this from a vacuity into a real test. That is a benchmark change,
not a knob.

### C51 — Training happens on one visual instance, with zero randomisation {#c51}
**Class** INHERITED · **Status** MONITORED · **Cross-ref** [C45](#c45), [C49](#c49), [C50](#c50)

Stated once, because four other entries assume it and none of them says it.

> **The mechanism, added 2026-08-25 after an external reviewer pointed at the table.** This entry
> asserts "zero randomisation" in `train`; here is the source of it.
> `envs/robosuiteVGB/robosuitevgb/secant/envs/robosuite/preset_customization.py`:
>
> | mode | `TASK_RANDOM_SEED["Door"]` |
> |---|---|
> | `train` | `[100, 100, 100, 100, 100, 100, 100, 100, 100, 100]` |
> | `eval-easy` | `[105, 106, 113, 114, 120, 130, 132, 163, 224, 281]` |
> | `eval-medium` | `[16, 22, 102, 171, 190, 235, 309, 338, 343, 369]` |
> | `eval-hard` | `[26, 29, 31, 100, 112, 148, 229, 275, 291, 369]` |
> | `cam-easy` / `cam-hard` | `[100]*10` each |
>
> **All ten `train` scenes share one seed**, and each scene's `TASK_TEX_CANDIDATE` entry is a single
> fixed material→texture dict rather than a candidate list to sample from — verified for **all ten**
> (the reviewer had checked about six and flagged the rest as open; closed here). So `train`-mode
> scene variation is a **deterministic lookup table**: the ten scenes genuinely differ in
> appearance, but nothing about which appearance a scene gets is stochastic. The held-out regimes
> are where the seeds actually diverge.
>
> **Two consequences.** It isolates a noise source: whatever varies between two `train`-mode
> evaluations of one checkpoint, it is not texture selection — which is what made object placement
> ([C69](#c69)) the remaining candidate, and correct. And it confirms `cam-easy`/`cam-hard` exist as
> real regimes on a **camera** axis nothing in this project has ever measured.

> **This is true of the code and false of our only checkpoints.** [C54](#c54), 2026-08-20: the
> `drqv2` run behind [C46](#c46)/[C47](#c47) has stored training pixels matching `eval-easy`, not
> the clean instance described below, and its policy is at chance on the instance this entry says
> it trained on. Everything below still describes what `train.py` does — a fresh run reproduces
> it — so the entry is not withdrawn. What it may no longer do is license a statement about a
> *particular* trained artifact without that artifact's own pixels being checked.

`make_env`'s train branch sets `randomize_color = randomize_lighting = False`,
`randomize_dynamics = False`, `randomize_camera = False`, `moving_light = False`,
`except_robot = True`. `train.py` never sets `scene_id`, so it stays at `robo_make`'s default of
0 ([C45](#c45)). Nothing else varies the appearance. **Every baseline therefore trains on a
single fixed visual instance**, and the only episode-to-episode variation is robosuite's initial
placement, drawn from the global RNG.

**Single-instance by configuration, not by construction** — measured 2026-08-19,
`scripts/probe_seed_effect.py --scenes`. The scene axis is **live in train mode**: two train-mode
envs at `scene_id` 0 and 7 render differently (mean pixel 102.08 vs 80.89, distinct fingerprints).
So training is visually fixed because `train.py` pins `scene_id=0` and never varies it, *not*
because scene selection stops working outside evaluation. The distinction is the whole content of
the entry: an axis that is unused can be used, while an axis that is dead cannot.

That directly prices [C50](#c50)'s option 2. Giving IDAAC's instance labels a visual referent
needs **one argument**, not new machinery — `robo_make` already accepts `scene_id`, and it
demonstrably works under `mode='train'`. Cheapness is not the objection to that option; changing
what the training distribution *is* remains the objection.

This is RL-ViGen's design, not a defect: train clean, evaluate under perturbation. It is
MONITORED rather than OPEN for that reason. What it changes is *interpretation*, in two places:

- "Generalisation" here means one-instance → perturbed, never multi-instance → held-out. Results
  should not be read against Procgen-style numbers where training spans hundreds of levels, and
  [C48](#c48)'s three-way origin split is partly this.
- Any mechanism whose premise is *diversity among training instances* has no material to work
  with. [C50](#c50) is the fully-established case (IDAAC's `level_seed`). Whether `ctrl`,
  `ibac_sni` and `ppg` are affected is **not** established here and must not be asserted from
  this entry alone — their mechanisms address trajectories, information flow, and value
  distillation respectively, which are not obviously the same dependency. Checking each is
  separate work.

The second bullet is deliberately weaker than the first. Generalising from IDAAC to "all four
Procgen-native baselines" is the move this entry exists to prevent.

---

### C52 — Four baselines do not reproduce at a fixed seed {#c52}
**Class** DESIGN-GAP · **Status** RESOLVED · **Cross-ref** [C20](#c20), [C18](#c18)

> **Status corrected 2026-08-26 — the detail said OPEN while the summary row said RESOLVED, and
> nothing caught it.** The decision exists and is logged: `P-C52 — report distributions, not runs`
> in [`RESEARCH-FRAME.md`](RESEARCH-FRAME.md), *"(1), owner, 2026-08-19"*. So RESOLVED is correct
> and the entry's own header was the stale half. Found by
> `tests/test_construction_register.py::test_summary_and_detail_agree_on_STATUS_not_just_presence`,
> written the same day for a different entry — the existing agreement test compared only the *set
> of ids*, never the statuses.

[C20](#c20) closed the question of whether determinism was tested. This is what it found, and it
is a different problem from the one C20 named.

`sgqn`, `drq`, `idaac` and `alda` produce different trajectories from the same seed at 1,300
frames. `ppg` cannot be asked at all — no step budget, so two trials do different amounts of work.
That is **a third of the table**, and the 5-seed plan assumed all twelve would reproduce.

*(This entry first said five, including `ctrl`. `ctrl` reproduces; its verdict was wall-clock
contamination in the fingerprint, retracted in [C20](#c20).)*

**What it does and does not break.** It does *not* invalidate averaging over seeds: each run is
still a draw, the seed still shifts the distribution (every cross-seed control fired), and a mean
over 5 seeds remains a mean. What it breaks is **reproduction** — nobody, including us, can re-run
a reported cell and get the cell back. It also adds a variance component on top of
[C18](#c18)'s, for exactly the baselines where it is unmeasured.

**Two of the four have an identified cause and it is the same one.** `drq` and `sgqn` both
reproduce on CPU, so for both the cause is the MPS backend — the second predicted from the first,
then tested. Each has a lever with a price: `drq` 774s against 133s, `sgqn` 2572s against
393–565s.

For the other two, nothing is established and **neither can be moved off MPS without a clone
deviation** — `idaac` hardcodes `torch.cuda.FloatTensor`, `alda` calls `.cuda()` unconditionally
in its replay sampler. `idaac` at least has parallelism excluded (it fails at one process as well
as four). `alda` has nothing excluded at all.

**`idaac`'s cause is NOT identified**, and an earlier version of this entry said it was. The
"reproduces at one process" result was a fingerprint artefact and is retracted in
[C20](#c20) — two one-process runs differ on 15 of 21 logged rows. The correction matters here
because it removes the one baseline that looked cheaply fixable.

So this is not one defect in five places, and **there is no single fix**. Exactly one of the five
has a known lever, and it is the expensive kind.

**The next interventions, in cost order**, each changing one variable against a recipe that
already exists:

1. ~~`idaac` on **CPU** at one process~~ — **attempted and blocked.** `idaac` exposes `--no_cuda`,
   but `ppo_daac_idaac/algo/idaac.py:105` builds the order classifier's target with
   `torch.cuda.FloatTensor(...)`, which the MPS shim materialises on MPS whatever the flag says.
   The model then sits on CPU and the target on MPS, and it dies in 7 seconds:
   `RuntimeError: Expected loss.is_mps() to be true, but got false`. So **the flag exists and
   cannot work on this stack**, and the intervention needs a clone deviation before it needs
   compute. Same shape as `ppg`'s missing seed: a knob that does not do what its name says.
   (The probe reported this as UNINTERPRETABLE rather than a verdict — three identical
   fingerprints of an error message, control not fired.)
2. ~~`alda` on **CPU**~~ — **attempted twice and blocked both times.** The spec-override route
   fails: `common/utils.py:219` reads a key's existing value before replacing it, so
   `--spec.trainer.config.device=cpu` raises `KeyError: 'device'` on a spec with no such field.
   Turning the shim off (`RLGEN_MPS_AS_CUDA=0`) does select `cpu` at `scripts/train.py:52` — and
   then the run dies inside training with
   `AssertionError: Torch not compiled with CUDA enabled`, from
   `dmcontrol_generalization_benchmark/src/utils.py:150`'s
   `torch.as_tensor(obs).cuda().float()` in the replay sampler.

   **`runnable/_launch/alda.sh:17` is right and I briefly recorded that it was not.** It says
   "SHIM REQUIRED. ALDA calls `.to('cuda')` and `torch.device('cuda')` unconditionally", and it
   is exactly so. My feasibility check ran 30 steps, which never reaches the replay sampler, so it
   passed against a path the real run fails on. **A feasibility check that does not exercise the
   expensive path is not a feasibility check** — it cost ~8 minutes of wrong compute and one
   incorrect claim, and the lesson is the cheaper half.

**Both remaining interventions are blocked by the clones rather than by compute**: `idaac` by a
hardcoded `torch.cuda.FloatTensor`, `alda` by an unconditional `.cuda()` in its replay sampler.
Neither can be moved to CPU without a clone deviation, and neither was visible from reading.
3. `ctrl` — no hypothesis left to test cheaply; it fails at one env and is JAX. Needs reading
   rather than running, starting with anything that consumes randomness outside a PRNG key.

**Options**

1. **Report distributions, not runs.** Say plainly in the results table which baselines are
   reproducible and which are not, and stop implying any cell can be re-run. Cheapest, honest,
   and it makes half the table weaker than a reader would assume from a normal benchmark.
2. **Pin what can be pinned.** Set `--num_processes 1` for `idaac` — throughput cost 368s against
   141s for the same work — and keep hunting the others. Buys one baseline back at a real price,
   and the price compounds over a 5-seed budget.
3. **Investigate before producing anything.** Bisect the remaining four. Open-ended, and the
   `sgqn` eliminations show it is not quick.
4. **Accept and enlarge the seed budget** for the affected five, on the grounds that their
   variance is strictly larger. Needs [C18](#c18)'s estimate re-derived per baseline, which needs
   runs nobody has budgeted.

My reading is 1 as the floor — it costs nothing and is true regardless — with 2 alongside it,
because `idaac` is also the baseline whose mechanism is already under question in [C50](#c50)
and the one place where "unreproducible" and "mechanism unclear" would compound.

---

**Commit** `5726d9cf`

**Decision** Report distributions, not runs, and say in the table which baselines are which.
Owner, 2026-08-19. Recorded in §4 form in [`RESEARCH-FRAME.md`](RESEARCH-FRAME.md), because it is
a decision about what the claim may say rather than about code; `python scripts/decisions.py`
enumerates it.

**Effect** The results table gains a per-baseline reproducibility column, and no cell for
`sgqn`, `drq`, `idaac` or `alda` may be described as re-runnable. Averaging over seeds is
unaffected — each run is still a draw and every cross-seed control fired. It costs nothing and
does not foreclose pinning `drq`/`sgqn` to CPU later, which is the only lever measured to work
and costs 5.8× and ~5× wall-clock respectively.

---

### C53 — The brief requires identical logging keys; the hermetic null forbids the only way to get them {#c53}
**Class** DESIGN-GAP · **Status** RESOLVED · **Cross-ref** [C28](#c28), [C72](#c72)

> **Dissolved by an owner decision, 2026-08-26 — the conflict was real and one side of it has been
> withdrawn.** [`TASK.md`](TASK.md) R3 no longer demands that the evaluation **code** be identical.
> It now reads: *"evaluation code should produce metrics that are fully on the same axes and
> directly comparable."*
>
> That removes the horn of the dilemma this entry recorded. The brief's stated purpose —
> *"для обеспечения ЧЕСТНОГО сравнения"*, to guarantee a fair comparison — is untouched; what is
> withdrawn is the *mechanism* it proposed, which was one shared evaluator, and which the hermetic
> null forbids. **Fairness was the requirement; identity was a proposed means.**
>
> **This entry was right to refuse to resolve it silently.** `CLAUDE.md`'s null says a conflict
> between a null and a task *is* the finding — and holding it open, unresolved and visible, is what
> let it be decided deliberately rather than absorbed. It is closed by a decision, not by a
> workaround.
>
> **Requires DZ's agreement.** The relaxed wording changes a verbatim supervisor requirement, and
> the owner's decision is recorded as such in [`TASK.md`](TASK.md) R3 rather than presented as an
> interpretation. Committed as `f48aecf1`'s successor.

**Decision** relax [`TASK.md`](TASK.md) R3 from *identical evaluation code* to *metrics fully on the
same axes and directly comparable*, keeping the brief's stated purpose (a fair comparison) and
dropping the mechanism it proposed. Owner, 2026-08-26.
**Effect** the conflict this entry records no longer exists: the hermetic null and R3 can both hold.
[`COMPARABILITY_CONTRACT.md`](COMPARABILITY_CONTRACT.md) becomes the document that carries R3's
burden rather than supplementing it, and [C72](#c72)'s option 1 — one evaluator per baseline —
stops being a contract violation. **Not yet agreed by DZ**, whose brief the relaxed line amends.

Recorded because `CLAUDE.md` says to: *"If a null and a task appear to conflict, the conflict is
the finding. Record it rather than resolving it silently."* This one has been resolved silently,
in code, for some time.

**The contract.** [`TASK.md`](TASK.md) R3, the criterion it calls *the load-bearing one*: evaluation
must be *"identical across baselines in all six respects: stepping, frequency, episode count,
reward collection, averaging, **logging keys**."* R5 sharpens it — *"a single constants module owns
the tag strings; no string literals at call sites"*, and *"one script … with no per-algorithm
branch"*.

**The null.** [`porting-directive.md`](../../../docs/porting-directive.md) §1: hermetic per
baseline, *"own file, own utilities, no shared base classes, runners, or adapters"*. Under the
clone design each baseline runs its authors' own logger, and the twelve emit at least six key
shapes for one quantity — `eval/episode_reward`, `Eprew200`, `Eprew0`, `rreturn_mean`,
`EpRewMean`, `test/mean_episode_reward`.

**They cannot both hold as written.** Identical keys require either editing twelve clones or a
shared logging adapter, and §1 forbids the adapter while the clone-as-null forbids the edits.

**What was actually done, and it is defensible.** The per-algorithm branch was moved *downstream*:
`scripts/collect_metrics.py` carries seven parsers and maps every baseline into one `Record`. That
satisfies R3's **purpose** — one routine can consume all twelve — and inverts its **mechanism**,
which asked for no branch at all. `python scripts/requirements.py` reports R3 NOT MET for exactly
this reason and R5 PARTLY.

**Options**

1. **Declare the collector as R3's satisfaction** and amend R3's wording to require *one canonical
   record shape* rather than identical tag names. Honest, and it is what the code does. Cost: it
   is an amendment to the contract, which only the person who set the contract can make.
2. **Meet R3 literally** by adding a tag-normalising emission to each clone. Twelve deviations,
   each ENABLES-class, to change nothing about any number — the worst ratio of deviation to
   information in the project.
3. **Leave it and disclose**, reporting R3 as met-in-purpose with the branch count as evidence.
   Cheapest and it is roughly the status quo, but it leaves the contract saying something the
   repo does not do.

My reading is 1: the collector already exists, works for twelve, and is the only option that ends
with the contract and the repo agreeing. But amending a contract is not mine to do, which is why
this is OPEN rather than a decision.

---

### C54 — The only trained checkpoints we have were not trained on the distribution the config declares {#c54}
**Class** FALSE-CERTIFICATION · **Status** OPEN · **Cross-ref** [C51](#c51), [C47](#c47), [C46](#c46), [C55](#c55), [C63](#c63)

[C51](#c51) states, as settled background that four other entries lean on, that "every baseline
therefore trains on a single fixed visual instance" — `mode: train`, no colour or lighting
randomisation, `scene_id` pinned to 0. That is what the code says and what a fresh run does. It
is **not true of the `drqv2` checkpoints this project has actually measured**, and those
checkpoints are the sole trained artifacts behind [C46](#c46) and [C47](#c47).

**Behavioural evidence.** Same evaluator, same seed, same scene 0, same episode count; only
`mode` differs:

| checkpoint | `mode=train`, scene 0 | `mode=eval-easy`, scene 0 | the run's own logged eval |
|---|---|---|---|
| 50k frames | 1.94, SR 0/20 | 71.48–133.29 | 118.63 |
| 100k frames | **1.30, SR 0.00** | **420.02, SR 0.80** | **436, SR 1.00** |

The random-policy floor is **1.82** ([C55](#c55)), so scene 0 under `train` is chance.

**It is not the regime that fails — it is that exact condition.** Read at 20 episodes on all ten
scenes, the same 50k checkpoint is *well above* chance elsewhere in the same `train` regime:

| train-mode scene | 0 | 6 | 3 | 8 | 1 | 5 | 9 | 4 | 2 | 7 |
|---|---|---|---|---|---|---|---|---|---|---|
| return | **1.94** | 4.98 | 6.55 | 6.95 | 12.24 | 14.54 | 26.21 | 35.69 | 57.73 | **80.67** |

Pooled 24.75 against a floor of 1.82 (difference +22.93, 95% CI [+18.74, +27.63]). So `train`
renders a scene this policy can act in — it reaches 80.67 on scene 7 — and the one place it
collapses to chance is the single condition its config names as where it trained.

**Return tracks visual distance to the stored training frame.** Across those ten scenes, per-pixel
distance from each rendered scene to the run's own stored training observation correlates with
return at **Pearson −0.887, Spearman −0.794**: 18.61→80.67, 26.26→57.73, 39.92→1.94, 43.29→4.98.
The declared condition, `train` scene 0, is the *most distant of all twenty* regime×scene
combinations. This is correlational across ten scenes, which also differ in ways other than
appearance, so it is evidence for the reading and not a mechanism — but it removes the obvious
alternative, that `train` mode is broken or unlearnable.

> **[C63](#c63) has since measured this correlation at a second checkpoint of this same run, and
> it reads −0.374.** The distances replicate exactly; the gradient does not. **Do not quote the
> −0.887 as a mechanism or as a way to predict which scenes a policy will handle.** What survives
> to 100k — and what this entry's conclusion actually rests on — is the two extremes, both of
> which reproduce: `eval-easy`/0 nearest and best, `train`/0 next-to-most-distant and at chance.

**Pixel evidence, which is what settles it.** The run stored one training episode. Comparing its
reset frame against freshly rendered reset frames, per pixel, across all twenty regime×scene
combinations:

| rendered as | mean abs. difference | correlation |
|---|---|---|
| **`eval-easy`, scene 0** | **7.60** | **0.942** |
| `train`, scene 7 | 18.61 | 0.833 |
| `train`, scene 0 — *what the config declares* | 39.92 | 0.607 |

`train`/scene 0 is nearly the worst match of the twenty. Channel means alone do **not** separate
these (`eval-easy` scene 0 at 2.63 vs `train` scene 4 at 3.48); the per-pixel comparison does,
and the weaker statistic was tried first and was not sufficient. Recorded because the next person
will reach for mean intensity too.

**What is not explained.** No mechanism has been found.

- The launch command is recorded in the run's own `.hydra/hydra.yaml` and carries no `mode`
  override; `env_set` is empty. It matches how runs are launched today.
- `train.py` assigns `train_env` once and never reassigns it; `eval()` never writes to replay
  storage, so the stored episode is genuinely training data.
- `robo_config.yaml` (`mode: train`, `scene_id: 0`) has an mtime of 2026-08-07, eleven days
  before the run. `utils.py` and `robo_wrapper.py` predate it too. P12 patches only the
  `eval_env` line and was verified against the commit as it stood at run time.
- Rendering is not working-directory dependent (checked both the launcher's cwd and ours).
- A 5000-frame reproduction with evals every 1000 frames did **not** reproduce it: episodes 0–3
  all render as `train`, including the ones collected after an eval had built eleven
  randomising envs. If shared texture state were the cause, today's runs would drift *faster*
  than the original, which had no P14 and built one eval env per eval.

The one systematic difference between the reproductions and the original is **run length**.
`replay_buffer.py:117` unlinks each episode file as soon as the loader has consumed it, so the
`.npz` files left on disk are never a sample of a run — they are whichever episodes had not yet
been fetched when it stopped, i.e. the last ones. Every surviving buffer is therefore the *end*
of its run, and the split is: three short runs and one 1200-frame reproduction end rendering as
`train`; the single 240-episode run ends rendering as `eval-easy`.

That reading was nearly recorded the other way round — as "early episodes render `train`, late
ones render `eval-easy`", which is incidentally true of the same files and attributes the
difference to episode index rather than to how long the run went on. The eviction rule is what
distinguishes the two, and it means **no archived run can testify about its own middle**.

Cumulative drift over a long run therefore survives as the hypothesis and is *not* established.
The reproduction is two orders of magnitude too short to have tested it, and the L1-to-`train`
creep across its episodes (8.47, 7.46, 10.15, 11.28) is well inside placement noise and must not
be read as the trend beginning.

**What would settle it:** one 120k-frame run, keeping every buffer episode, classified per
episode. That is a ~2.5 hour job and it is the only thing that distinguishes cumulative drift
from a one-off. Until then the mechanism is unknown, which is the honest state and is why this
is OPEN.

**RESULT, 2026-08-20 02:56 — the current pipeline does not drift.** 69 episodes were captured
across the full 120k run, sampled from episode 0 through **episode 239** — the same index whose
08-18 counterpart renders as `eval-easy`. Every one of the 69 classifies as `train|0`, at L1
4.29–11.87 against a clean reference, with the runner-up condition never closer than 19.81. Zero
transient disagreements. There is no switch, no creep, and no candidate for one.

So "it happens to every long run on the current code" is **ruled out**, and that was the reading
this run was started to test. What remains open is the 08-18 run itself, which is now the only
observation of the phenomenon and cannot be re-observed — its buffer kept one episode.

**The run also failed to produce a usable checkpoint, for an unrelated reason.** It learned, then
collapsed: `train_regime_success` reached **1.0 at 20k frames**, fell to 0 by 30k, and from 40k
onward every eval returns 0.68–0.69 with standard deviation 0.00 across 20 episodes — a
degenerate constant policy, below the 1.82 random floor. Its 100k snapshot scores **0.69** on
`train` scene 0. So this run answers the drift question and leaves [C57](#c57) in its place.

*Started 2026-08-20 00:41, with `scripts/watch_training_frames.py` copying each episode's reset
frame out before the loader unlinks it.* **It is not a byte-identical replication and must not
be reported as one.** P14 landed between the two runs and rewrote the eval path: the 08-18 run
called `_eval_single` against the persistent `eval_env`, today's calls `_eval_regime`, which
builds transient envs per scene. The evidence is in the runs' own logs — the 08-18 `eval.csv`
has seven columns, today's has nine, the extra two being P14's `train_regime_reward` and
`train_regime_success`. So a clean result from this run rules out "it happens to every long run
on the current code", not "it happened to that one".

**The control this entry needed, 2026-08-20.** Every argument above is about one run with no
counterpart. A `drqv2`/Door run at 55k frames now provides one, and it is the first checkpoint
this project has with **both** properties verified rather than assumed: `check_checkpoint_finite`
reports **0 of 11,459,885** non-finite parameters, and all **52** captured training episodes
classify as `train|0`, the declared condition.

Evaluated by the identical instrument, at the identical scene, in the identical regime:

| checkpoint | provenance | `train` scene 0 | success |
|---|---|---|---|
| 08-18, 50k | contested (pixels match `eval-easy`) | **3.06** | 0/20 |
| 08-20 cell, 50k | **verified `train\|0`, 52 episodes** | **424.52** | **20/20** |

One is at the 1.82 chance floor on the scene its config names; the other solves that scene in
every one of twenty episodes. Nothing else about the two runs differs that anyone has been able
to name — same launcher, same config, same task, same budget, same evaluator, same seed handling.
A within-scene control on the new one puts seed-only variation at 4% (424.52 against 407.51), so
the 140× gap is not episode noise.

This is the cleanest evidence in the entry, and it arrived last because producing it required
knowing that a checkpoint needs 50k frames to exist at all
([STAGES.md](STAGES.md)) and that finiteness has to be checked ([C57](#c57)).

For the record, that run's scene profile in its own regime — the first per-scene generalisation
data from a policy that actually learned: scene 0 **424.52** (20/20), scene 5 **391.20** (20/20),
scene 2 147.04 (11/20), scene 9 126.30 (8/20), and scenes 1, 3, 4, 6, 7, 8 between 1.10 and 31.41
with **0/20** successes throughout. Solved on four scenes, floor-level on three.

**And its retention — the first computed from a checkpoint verified on both axes.** Same grid,
both regimes, twenty episodes per scene, against the measured floors:

| | train regime | eval-easy |
|---|---|---|
| pooled return (10 scenes, n=200) | **115.31** | **3.49** |
| successes | **59 / 200** | **0 / 200** |
| against its regime's random floor | 1.82 | 1.85 |

The policy solves its training scene in twenty of twenty episodes and succeeds **zero times in
two hundred** under colour and lighting randomisation. Pooled over the four scenes whose
denominator both clears the floor and solves the task, return retention is **0.003**
[0.003, 0.004]; success-rate retention is **0.000**.

State the eval-easy side carefully, because the obvious phrasing is wrong. It is *not* "worse
than random": pooled, the policy beats the random floor by **+1.64**, 95% CI [+0.59, +2.80] —
above chance, and separably so. A first pass at this called it worse-than-random from scene 0's
0.86 alone, which is one scene of ten and is contradicted by the pool. What is true is narrower
and still severe: **barely above a random policy, and never once successful.**

The two directions together are the finding. The 08-18 checkpoint scores 464.18 on `eval-easy`
scene 0 and 3.06 on `train` scene 0; this one scores 424.52 on `train` scene 0 and 0.86 on
`eval-easy` scene 0. Each is near-solved on the distribution it trained on and at floor on the
other. `drqv2` on this task does not cross between the clean and randomised regimes **in either
direction** — n=1 per direction, Door only, so it is a result about these two runs and not yet
about the method.

**Provenance across every cell built since, 2026-08-24 — no run has reproduced the 08-18
signature.** Four cells, each classified per captured episode against the twenty rendered
conditions:

| cell | frames captured | verdict |
|---|---|---|
| `drqv2` seed 6 | 52 | **52/52 `train\|0`** |
| `drqv2` seed 7 | 51 | **51/51 `train\|0`** |
| `svea` seed 1 | 60 | **60/60 `train\|0`** |
| `drq` seed 1 | 43 | 38 `train\|0`, **5 UNMATCHED** |

The `drq` row is the one worth reading carefully, because it first came back as `train|0` ×38 and
**`eval-easy|2` ×5** — which is this entry's own signature, appearing in a live run. It is not.
Those five frames sit at **L1 57–68** from their nearest reference while a genuine match lands at
**4–12**; they resemble no rendered condition at all. Nearest-neighbour with no reject option
always names something, and the classifier had none. It now reports `UNMATCHED` above L1 25.

Had that gone unchecked, this entry would carry a second instance of its own phenomenon,
manufactured out of five frames that mean nothing — most likely arm occlusion. **The correct
reading is that nothing since 08-18 has drifted**, which is the outcome that makes the 08-18 run
stranger rather than better understood.

**Independent confirmation from a different measurement path, 2026-08-20.** Everything above is
about one run, read through pixels and through an offline evaluator. Three healthy 40k runs on
*today's* code — whose training distribution was verified clean for 69 of 69 captured episodes —
carry P14's in-loop numbers for both regimes, so they give a second, cheaper reading that needs
no checkpoint:

| | train regime | eval-easy | which is larger |
|---|---|---|---|
| 08-18 checkpoint (scene 0) | 3.06 | **464.18** | eval-easy, by 150× |
| seed 3, 30k | **171.63** | 34.32 | train, by 5× |
| seed 4, 30k | **140.37** | 17.53 | train, by 8× |
| seed 5, 30k | **105.00** | 10.77 | train, by 10× |

**The asymmetry reverses direction between the two run sets.** Each policy is strongest on the
distribution this entry says it trained on: the 08-18 run on `eval-easy`, today's runs on
`train`. Nothing about pixels, correlations or replay buffers enters this reading — it is the
runs' own logged evaluations, and it agrees.

Read the *sizes* with care, for two reasons.

These two rows are not the same quantity: P14's in-loop ratio changes both regime **and** scene
(eval-easy averaged over ten scenes, over train at scene 0), while the offline grid holds scene
and varies regime only.

And **each in-loop train-regime figure is a single episode.** `train.py:152` computes
`per = max(1, num_eval_episodes // len(scenes))`, which with the config's `num_eval_episodes: 10`
and ten scenes is `per = 1`; the denominator is then `_eval_regime('train', scenes[:1], 1)` —
one scene, one episode. The numerator is ten episodes, one per scene. So no individual ratio
above is worth reading, and `svea`'s 30k point (train-regime **0.79**, below the 1.82 floor,
while its training episodes over the same interval averaged 41.93) is that noise showing itself.
This is a defect in P14, which is ours.

What survives is the **direction**, and only because it is consistent across three independent
seeds and four evaluation points each, against a checkpoint measured the other way by a
20-episode-per-scene offline grid. The direction is what this entry claims; the magnitudes belong
to the grid, not to this table.

**A confound found 2026-08-20 and tested, not waved away.** [C57](#c57) established that the
08-18 run diverged to NaN — and the episode whose pixels are the evidence above, episode 239, was
recorded *after* that divergence. If NaN actions had corrupted the simulator, the frame would be
an artifact rather than a rendering of a visual condition, and this entry would collapse.

They did not. That episode's **observations contain 0 NaN across 31,815,504 values**, span the
full 0–255 range, and vary frame to frame (per-frame mean 73.54–77.46). The NaN actions clip to
exactly zero — every non-NaN action value in the episode is `0.000` — so the arm stopped moving
while the scene kept rendering normally. The frame used above is the **reset** frame, which
precedes any action in that episode. A corrupted simulator also could not correlate at 0.942 with
a specific valid `eval-easy` render while sitting at 0.607 against the declared one; corruption
does not select a scene.

**These checkpoints are at least numerically sound**, which [C57](#c57) made worth checking
rather than assuming: `scripts/check_checkpoint_finite.py` reports **0 of 11,459,885** parameters
non-finite across all three, against 11,449,645 for the run that diverged. So what is in dispute
here is provenance, not arithmetic — the numbers below describe a real policy whose training
distribution is unverified, not a dead network.

**Consequence, which does not wait on the mechanism.** [C46](#c46) and [C47](#c47) are not
withdrawn — they are correct measurements, cross-checked, and [C55](#c55) confirms they clear
chance. But their subject is not what they say it is. Both describe "a policy trained on the
clean single instance"; the policy they measured demonstrably was not that. Any sentence of the
form "trained on one instance, retains X% on held-out scenes" is currently unsupported for these
checkpoints, and no new baseline may be compared against them until a run whose training
distribution is verified exists. **Verifying the training distribution from the stored buffer is
cheap and nothing in this project was doing it** — that check now belongs in the runbook, not in
this entry.

**Options**.

1. **Spend the ~2.5 hours on one 120k-frame run that keeps every buffer episode**, and classify
   each. Settles cumulative-drift versus one-off, and either way produces the first checkpoint
   whose training distribution is verified rather than assumed. Costs one overnight slot and
   nothing else; it is the only option that ends with a usable artifact.
2. **Retrain the affected checkpoints without diagnosing the mechanism**, adding a per-episode
   buffer check so any recurrence is caught. Cheaper in thought, same cost in compute, and
   leaves a known-live unexplained failure in the pipeline that all twelve baselines share.
3. **Keep C46/C47 with the caveat attached and proceed.** Costs nothing now. It means the
   project's only empirical results describe a policy whose training distribution nobody can
   state, which is the kind of thing a reviewer asks about first.

My reading is 1, and it is close to free — the machine is otherwise idle overnight and the run
needs no decision from you to start. What it cannot do is choose what happens to C46/C47
afterwards, which is why this is OPEN rather than simply queued.

---

**DEFAULT SET, 2026-09-03 — this entry's central evidence is very probably an artefact of
[C95](#c95), and the entry should not be relied on until re-measured.** Every number in the table
above was produced **on this laptop**, and C95 established that a container-trained checkpoint
evaluated here reads 12–14x low because the renderer differs (`MUJOCO_GL=egl` against macOS
`glfw`). That alone would not invert an ordering — but the ordering here *is* inverted, and the
container disagrees with it.

| 100k `drqv2`, scene 0 | `mode=train` | `mode=eval-easy` |
|---|---|---|
| this entry, measured locally (seed 12) | **1.30**, SR 0.00 | **420.02**, SR 0.80 |
| container, measured 2026-09-03 (seed 2) | **392.9** | **6.8** |

**The two do not merely differ in magnitude; they point opposite ways.** Locally the checkpoint
looked like it had been trained on the randomised regime and not on the fixed one — which is
precisely the conclusion this entry draws in its title. On the container the same comparison, on
the same task at the same budget, shows the ordinary and expected shape: strong on the training
distribution, near the floor once appearance is randomised.

**So the most likely reading is that the checkpoints were trained on exactly the distribution the
config declares, and that the laptop's rasteriser makes its `eval-easy` render resemble the
container's `train` render more closely than its own `train` does.** That is a strange-sounding
claim, and it is *not proven here*: the two rows are different seeds (12 versus 2), so this is a
strong inference from a shape, not a controlled replication.

**SETTLED THE SAME DAY, AND NO JOB WAS NEEDED — the controlling evidence was already on disk.**
I was about to spend a container cell re-measuring the seed-12 checkpoint. Before submitting it I
read that run's own `eval.csv`, recovered from `bt1a5lp648o6bfehnfsg`, and it answers the question
directly, because it was written **in the container while the run was training**:

| `drqv2-s12` @ 100k, train regime, scene 0 | value |
|---|---|
| the run's own `train_regime_reward` (in-container) | **476.33**, `train_regime_success` **1.0** |
| this entry's re-measurement (this laptop) | **1.30**, SR 0.00 |

**Same checkpoint, same regime, same scene, same frame — 366x apart, and the low one is the
laptop.** The run also logged `episode_reward` 1.87 at SR 0.00 for the eval regime, so its own
ordering is the ordinary one: strong on the training distribution, floor once appearance is
randomised. This entry's inversion exists **only** in the locally-measured column.

**So the title's claim is withdrawn.** The checkpoints were trained on the distribution the config
declares. What was not measurable was the training distribution *on this machine* — [C95](#c95) —
and the two most affected numbers happen to sit either side of the comparison this entry drew.

**The evaluator variable is closed too**, which is why one table settles it: C95 showed our offline
evaluator reproduces the training loop's own figure when run in the container (131.57 against a
logged 135.71), so "our evaluator versus RL-ViGen's in-loop eval" cannot be the explanation for a
366x gap that appears only when the machine changes.

**Consequence for the entries that lean on this one**: [C46](#c46), [C47](#c47) and any retention
figure derived from them were computed on laptop numbers and inherit C95's correction, not C54's —
their arithmetic was never wrong, their inputs were. **Recorded also as a process note**: the job I
did not run would have cost ~60 RUB to produce evidence weaker than a file already in the archive.
Reading first is cheaper than measuring.

### C55 — The chance floor was measured, recorded, and then not consulted {#c55}
**Class** DESIGN-GAP · **Status** RESOLVED · **Cross-ref** [C47](#c47), [C54](#c54), [C18](#c18)

**Decision** measure the floor with a uniform random policy through the same evaluator, and make
every retention report refuse to divide by a denominator that has not cleared it. **Effect** C47
survives and is now readable: its scene 9 row is an absence rather than a small value, and one
row of its aggregate is chance. The floor also made [C54](#c54) legible — "at chance in its own
training regime" is not a statement anyone could have made before there was a chance level to
compare against.

**This entry was first written claiming the floor had never been measured. That was false, and
the correction is the more useful finding.** [C17](#c17) measured it on 2026-08-16 —
`scripts/probe_floor.py`, 25 random episodes, Door **1.633** and Lift **6.562**, 0 successes in
either — and closed as RESOLVED. The number this entry re-derives at larger sample (1.818 over
200 episodes) agrees with it.

**Re-measured 2026-09-05, under the current evaluator and PAIRED seeding** (reviews 7 and 8 both
asked for this, since 1.818 predates per-episode condition seeding): `scripts/probe_floor.py
--episodes 200` gives Door **mean 1.842, sd 2.839, 95% CI [1.511, 2.271], max 28.755, 0/200
successes, flag never fired**. 1.818 lies inside that interval, so the switch left the floor where
it was — as expected, since both schemes draw from the same marginal placement distribution.

The probe now seeds each episode with the same `placement_condition_seed(seed, scene, i)` the
baselines use, so this is no longer only a population constant: **floor episode *i* runs the
identical physical placement as baseline episode *i***, which makes it a per-episode control rather
than a number compared across samples.

**The dispersion is the part to carry forward.** A single chance episode reached **28.755**. Any
competence claim that quotes a mean against this floor without the spread is quoting the wrong
statistic.

So the gap was never *measuring* chance. It was that the measurement sat in the register while
[C47](#c47) computed a retention ratio two days later without consulting it, and nothing
connected the two. A floor recorded as a fact in one entry does not reach the instrument that
needs it; only a floor wired into the instrument does. That is what this entry actually changes,
and it is a smaller claim than the one it was written with.

Worse, `scripts/decisions.py` printed `C17` in its "RESOLVED with no §4 block" list on the same
night, and I read past it. The ledger built to stop exactly this pointed straight at the entry
and it was not enough, because the list names entries and not their contents.

What is genuinely new here, then: the floor measured **per scene and in both regimes** rather
than once per task at scene 0 (which is what makes C47's scene 9 legible as *below* chance), and
the refusal wired into the report so a future ratio cannot be computed without it. `scripts/eval_across_scenes.py --random-policy` now measures it:
a uniform policy over the action spec, same scenes, same episode counts, same everything else.

**Door, 20 episodes × 10 scenes × 2 regimes = 400 episodes, zero successes in any of them:**

| regime | pooled floor | per-scene range | 95th pct of an episode |
|---|---|---|---|
| `train` | **1.818 ± 2.234** | 1.56 – 2.29 | ~6–11 |
| `eval-easy` | **1.853 ± 1.960** | 1.53 – 2.24 | ~5–10 |

The floor does not depend on the regime, which is itself worth having: it means a regime
comparison is not confounded by the regimes offering different amounts of free reward.

**Re-reading [C47](#c47) against it.** C47 stands. Eight of its ten scenes sit clearly above
chance, so the ~25% retention it reports is a real drop between real numbers, not a ratio of
noise. Two rows need a caveat it could not have known to add:

- **scene 9 scored 0.78** — *below* the floor mean, inside the random 95% range. On that scene
  the policy is at chance; "retains 0.6%" overstates what was measured, which is "does nothing".
- **scene 4 scored 8.09**, just past the random 95th percentile. Marginal, not clean.

Neither changes C47's conclusion. Both change what the per-scene column means, and the aggregate
silently includes one row that is an absence rather than a small value.

**The instrument was wrong on its first write, in the way this project keeps rediscovering.**
`scripts/regime_retention_report.py` first guarded the denominator by asking whether it was small
relative to *the spread of the returns themselves*. A 50k checkpoint scoring 2.02 with sd 0.8 is
not small by that test, so it passed, and the report would have printed a confident ratio built
from two chance-level numbers. The quantity that matters was never statistical precision but
whether the agent can do the task at all — which is invisible without a floor to measure against.
Aimed at the wrong quantity, the guard passed its own test suite.

Fixing it to the floor was still not enough: 20 episodes *do* separate 2.02 from 1.82, so a
floor check alone re-admitted the same row. The report now carries a third verdict,
`UNSOLVED-DENOMINATOR`, for a policy that clears chance on shaped return while never once
solving the task — printed, because it is a real number, but excluded from any pooled figure,
because retention of reward shaping and retention of task competence are not the same quantity
and this project's own null forbids averaging them.

**A fourth refusal, added 2026-08-24 after the guard let a headline through.** The
`UNSOLVED-DENOMINATOR` rule fired only at **exactly zero** successes. `svea` seed 1 scored
**1/20 on every scene it succeeded on at all, and never more** — nonzero, so it passed — and was
pooled into a return retention of **0.947 [0.877, 1.022]**. I read that as SVEA being robust
where DrQ-v2 collapses (0.003), which is the expected direction from the literature and was one
step from being recorded as this project's headline result.

It was a shaped-reward plateau. `robosuite`'s Door pays up to 0.25/step for reaching proximity
and 0.25/step for door rotation against a sparse +1.0 for actually opening it, so a policy that
never opens the door still collects a return that is largely regime-insensitive **by
construction**. SVEA's 6/200 train successes against DrQ-v2's 59/200 — including **20/20 on two
scenes** — is the difference between a plateau and a skill, and only the latter can be said to
be retained or lost.

Fixed with `MIN_DENOM_SUCCESS = 0.25`: a denominator must clear the random floor *and* solve the
task in at least a quarter of episodes. The threshold is a **stated line, not a derived one** —
below it the denominator is dominated by shaping. Effect on the three verified cells: `drqv2`
seed 6 keeps 4/10 scenes and its 0.003; `drqv2` seed 7 and `svea` seed 1 now report **no pooled
retention at all**, which is the correct answer for policies that never learned the task.

Three further results from the same re-check, worth keeping:

- **Pooling over the usable subset is policy-specific.** SVEA's usable set was {1,3,5,6,7,8},
  DrQ-v2's is {0,2,5,9} — they overlap at one scene. Recomputed over all ten scenes from the raw
  JSON, by me rather than taken on report:

  | cell | all-10 train | all-10 eval-easy | ratio | successes |
  |---|---|---|---|---|
  | `drqv2` seed 6 | 115.31 | 3.49 | **0.0303** | **59/200 → 0/200** |
  | `svea` seed 1 | 97.50 | 85.51 | **0.8771** | 6/200 → 3/200 |
  | `drqv2` seed 7 | 85.01 | 15.00 | 0.1764 | 0/200 → 1/200 |

  DrQ-v2 seed 6's all-ten figure is **ten times** its usable-subset figure of 0.003, so the
  magnitude is a property of the pooling and not of the policy; the report already says the
  subset "is NOT RL-ViGen's protocol". **The success column is the part that does not move under
  any pooling choice**, and it is the defensible statement: 59 successes to 0 is a skill lost,
  6 to 3 is a policy that never had one.
- **`svea` seed 1's provenance is verified**, and better than `cell55k`'s: all **60** captured
  frames classify `train|0` at L1 3.95–11.79 against a next-nearest of 19.46–24.06.
- **The three cells' JSONs record no `device` field.** They were produced outside
  `scripts/run_regime_retention.sh`, so the CPU-inference guarantee rests on the evaluator's
  default rather than on a recorded fact. A paperwork gap, not a suspected error.

`tests/test_regime_retention_report.py` pins all three refusals, and the load-bearing test is
written against the measured values (2.02 vs 1.82, zero successes) rather than a convenient
fixture — precisely because the first version passed on exactly those numbers. Commit
`d181b2ec`.

---

### C56 — Two robosuite envs in one process do not render independently {#c56}
**Class** INHERITED · **Status** MONITORED · **Cross-ref** [C54](#c54), [C51](#c51)

Building a second robosuite env changes what the **first** one renders, from then on. Measured
directly, one process, `Door`, reading the mean of each env's reset frame:

| step | train env (scene 0) | eval-easy env |
|---|---|---|
| train env alone, 8 resets | **101–106**, stable | — |
| after an eval-easy env is *constructed* | **136** | 77 |
| after that env is *reset* once | **76** | 78 |
| after a third env (train, scene 7) is built | **81** | 82 — and scene 7 reads 82 |

The last row is the clearest statement of it: three envs configured for three different
conditions all render the same thing. A train env that has never been reconfigured stops showing
its own scene as soon as anything else exists. Deleting the second env does not restore the
first (it moves to 118, not back to ~104), and a *transient* eval env — built, reset, freed —
corrupts just as thoroughly as one kept alive.

**What this does and does not license.**

It does *not* invalidate this project's evaluation numbers. `eval_across_scenes.py` builds one
env per scene and uses it immediately, so the env being read is always the most recently
constructed one, and the most recently constructed one renders correctly — that is what the
scene-7 row above shows. [C47](#c47), [C55](#c55)'s floors and the regime grid are all built that
way and are unaffected.

Verified rather than assumed, and the first version of this paragraph did assume it — it argued
from two cases where the env in question happened to be the last one built, which is not the
same test. The test is the same scene rendered in two separate processes, once alone and once
after seven others:

| | alone | built 8th | |
|---|---|---|---|
| `train` scene 5 | 104.95, 106.13, 107.52 | 104.75, 106.28, 105.99 | same within reset noise |
| `eval-easy` scene 5 | 79.73, 78.38, 78.99 | 79.86, 78.33, 79.91 | same |

So the count of envs built before it does not touch the newest env's own rendering. Only the
older ones are damaged, and this project never reads an older one — audited rather than assumed:
of the nine `scripts/*.py` that construct an env, every one builds a single env and reads it
before constructing the next. That includes `probe_seed_effect.py`, which builds one env per
scene inside a comprehension and is the measurement [C51](#c51)'s "the scene axis is live in
train mode" rests on, so that claim is unaffected too.

It is also **not yet the explanation for [C54](#c54)**, and saying so would be the easy mistake
here. The mechanism predicts that a training run holding a persistent `eval_env` renders its
training episodes in the eval regime from the start. The live 120k run contradicts that: its
episodes 0–6 and 19 all classify as clean `train|0` at L1 6–11, including episodes collected
after the frame-0 eval had already run. So the pipeline does something these probes do not, and
what that is has not been isolated. C54 stays OPEN on its own evidence.

**Who is exposed.** The five RL-ViGen-native baselines — `drqv2`, `svea`, `drq`, `sgqn`, `curl` —
because they share `train.py`, which builds `train_env` and then `eval_env` and keeps both. That
is the exposed set, and it is exposed by construction rather than by accident. The seven clones
build their own envs (`alda` and `dmc_gb` have the most call sites, and both name an eval env),
but they run their own env stacks rather than robosuite, so whether the same defect exists there
is a separate question and is **not** answered by anything above. Assuming it generalises is the
move [C51](#c51) exists to prevent.

**Hypotheses tested and rejected**, recorded so they are not re-run:

- *"The eval env has to stay alive."* No — a transient eval env, built, reset and freed,
  corrupts as thoroughly as a persistent one (77.22 vs 75.39). Freeing it does not restore the
  train env either (118, not ~104).
- *"P14 ends each eval on a train-regime env, so it leaves the shared state in train
  configuration, which is why the live run stays clean."* This was the best candidate, since it
  explains both runs at once: the 08-18 eval path ended on a persistent eval-easy env, P14's ends
  on a `train` one. Measured directly, the 08-18 ordering leaves the train env at 75.6 and P14's
  ordering leaves it at **34.2** — further from the clean 103.4, not closer. The hypothesis
  predicted the opposite of what happened.

- *"`train.py` steps its env thousands of times between resets, and normal use re-establishes
  the rendering."* No. After an eval episode the train env reads 75.83; after a full 500-step
  episode and a reset it reads 75.92, and after a second episode 75.71. Use does not restore it.

So the interference is real, the pipeline's behaviour is real, and no account tried joins them.

**The pipeline side is not in doubt, which is why the probes are the puzzle.** The live 120k
run's captured episodes read 100.91–106.46 raw, against a clean `train|0` reference of 104–107
and an `eval-easy|0` reference of 76–78 — this is not a classifier verdict that could be
mis-assigning, it is the pixel values. Episodes 0–39 span two completed evals and every one of
them is clean. Whatever the probes are doing to their envs, `train.py` is not doing it.

Recorded now, separately, because it is reproducible in a minute and true regardless of how C54
resolves — and because the next person to build two envs in one process to save startup time
needs to know that the saving costs them both envs.

---

### C57 — Training diverged to NaN, and the run continued for 70,000 frames {#c57}
**Class** DESIGN-GAP · **Status** OPEN · **Cross-ref** [C54](#c54), [C52](#c52), [C18](#c18)

> **This entry was first written as "learned, then collapsed" — an RL stability story.** It is
> not one. The checkpoint's weights were then inspected and they are **NaN**: encoder 30,368 of
> 30,368 parameters, actor 3,067,101 of 3,069,149, critic 4,176,088 of 4,180,184, and every
> action it emits is `nan`. The network is dead, not degenerate.
>
> That the two readings look identical from the logs is the whole point. A diverged run and an
> unstable one produce the same flat curve, and only the weights distinguish them — which is
> [C17](#c17)'s lesson ("the policies fail" and "the instrument is broken" produce an identical
> log of zeros) arriving in a place nobody had pointed it.
>
> It also explains a detail the stability reading could not: **two independent seeds land on
> 0.69 with standard deviation 0.00**, to the digit. That is not a policy converging to a poor
> optimum, it is `nan` actions being clipped to the same constant by the action space.

The 120k run started for [C54](#c54) is the first full-length run on the current code whose
training distribution was verified per episode. It reached the task and then lost it:

| frame | 0 | 10k | **20k** | 30k | 40k | 50k … 110k |
|---|---|---|---|---|---|---|
| eval return | 0.87 | 9.33 | **39.34** | 18.26 | 0.69 | 0.69 (flat) |
| train-regime success | 0.0 | 0.0 | **1.0** | 0.0 | 0.0 | 0.0 |

From 40k onward every evaluation returns 0.68–0.69 with **standard deviation 0.00** over 20
episodes. That is not a weak policy, it is a constant one, and 0.69 is *below* the 1.82 random
floor ([C55](#c55)) — worse than acting at random. More than half the budget was spent there.

**It solved the task at 20k frames**, train-regime success 1.0. So Door is reachable on the clean
instance in a fifth of this budget, and this is a stability failure, not a difficulty one.

**Nothing in the pipeline notices.** Not the training loop, which ran 70,000 further frames; not
the evaluator, which logged 0.69 seven times; not `save_snapshot`, which wrote 7.4M NaN
parameters to disk without complaint; and not this project's 622 tests, none of which look at a
weight. A run that has been dead since frame ~35,000 completes, produces a checkpoint, and is
indistinguishable in every artifact we keep from one that merely trained badly. **That is the
defect** — the divergence is upstream's business, the silence is ours.

**And the signal that would have caught it is computed and thrown away, ~100,000 times per run.**
`algos/drqv2.py:195,224` sets `metrics['critic_loss']` and `metrics['actor_loss']` on every
update, and `train.py:332` hands them to the logger. They reach disk nowhere:
`logger.py:_try_sw_log` writes only to TensorBoard, which is off, and the CSV's field list is
frozen at the first dump (`_dump_to_csv` sets `fieldnames` once, from that dump's keys). Checked
across **all eight** `train.csv` files this project has ever produced — not one has a loss
column. A `nan` in `critic_loss` is the earliest and least ambiguous evidence available, it is
produced continuously, and it has never once been recorded.

That is not upstream being careless: `train.py:289` carries the comment *"wait until all the
metrics schema is populated"*, so the schema hazard was known and guarded against. The guard does
not hold here. Nor is turning TensorBoard off wrong — [P13](../setup/apply_patches.py) made that
import conditional for good reason. **Each decision is defensible and their composition discards
the diagnostic**, which is this register's recurring shape rather than anything new.

**The rate, and it depends on budget.** `scripts/check_checkpoint_finite.py --buffers` reads NaN
straight out of the stored actions, which works on runs too short to checkpoint — confirmed
against the run whose weights were separately verified dead (3500 of 3507 action values `nan`,
against 0 of 3507 for a healthy run at the same budget).

| budget reached | runs | dead | |
|---|---|---|---|
| 40k frames | 5 | **2** | seeds 1 and 2; seeds 3, 4, 5 alive (138.66 / 120.27 / 109.44, sd 45–81) |
| 120k frames | 2 | **2** | the 08-18 run *and* the 08-20 replication |

2 of 5 at 40k is 40%, Wilson 95% CI **[0.12, 0.77]** — wide enough that "how often" is not
settled, narrow enough to rule out both "one bad seed" and "always".

**`svea` at the same budget did not diverge — and that does not answer the question it was run
to answer.** All five RL-ViGen-native baselines share `train.py`, so more `drqv2` seeds can
measure a rate but cannot separate "this algorithm is unstable here" from "the shared loop kills
runs". One `svea` run at 40k, seed 1, was meant to separate them. It survived: 71 episodes, max
166.74, last ten averaging 41.55 with **sd 43.86** (varying, not the constant signature), and
**0 of 3507** NaN actions in its last stored episode.

At n=1 that is worth very little. `drqv2` itself survived 3 of 5 at this budget, so a single
surviving `svea` run is the *expected* outcome under either hypothesis and discriminates between
them barely at all. The design needed several `svea` seeds and got one — a limitation of the
experiment, recorded rather than read past, because "svea was fine" is exactly the sentence this
data does not support.

**The 08-18 run died too, and that was not known until now.** Its buffer's last episode carries
3500 NaN actions. It diverged *after* its final checkpoint — all three of its snapshots are
finite — so [C46](#c46) and [C47](#c47), which use the 50k one, are unaffected. But the pairing
in the row above is the thing to notice: **both runs that reached 120k died, and three of five
that stopped at 40k did not.** Whatever this is, more training is more of it, which is the
opposite of the shape a bad-seed story predicts.

**What this is not evidence for.** The obvious pairing — the 08-18 run trained under randomised
textures and succeeded, this one trained clean and diverged, therefore randomisation stabilises
training — is one run against one run, and it is now doubly wrong, because divergence to NaN is
a numerical event and the textures are not obviously its cause. [C52](#c52) established that
`drqv2` does not reproduce at a fixed seed and [C18](#c18) that five seeds resolve about 31%.

**One hypothesis worth naming and not yet testing:** every diverged run here trained through the
MPS-as-CUDA shim (`RLGEN_MPS_AS_CUDA=1`), and [C52](#c52) already found `drqv2` non-reproducing
on that backend while reproducing on CPU. NaN divergence is a plausible member of that family.
It is **not** established — CPU training is ~60× slower here, so the comparison that would settle
it does not fit on this machine, and it is the strongest reason so far to want non-MPS compute.

**Why OPEN rather than MONITORED.** It blocks Stage 8. A comparison table needs each baseline to
produce a checkpoint, and the project now has two runs: one whose training distribution is
contested ([C54](#c54)) and one that collapsed. **Neither is usable and there is no third.**

**Options**.

1. **A finiteness check in the training loop** — assert the loss and a weight norm are finite
   every N steps; on failure, log loudly and stop. A few lines, no algorithm touched, and it
   converts the silent case into a loud one permanently. This is the option the NaN reading
   makes obvious and the stability reading never suggested. It is a patch to twelve baselines,
   or to the shared `train.py` for five of them, so it is a deviation and therefore yours.
2. **Seeds, for the rate** — running: `drqv2`/Door at 40k, seeds 2–5. Seed 2 has already
   reproduced the divergence and seed 4 has not, so the answer is neither "always" nor "never"
   and the count is worth having.
3. **Test the MPS hypothesis** — the same seed on a non-MPS backend. Not possible here at
   ~60× CPU slowdown; this is the concrete thing remote compute would buy.
4. ~~**Checkpoint on best-eval rather than last.**~~ **Withdrawn.** Under the stability reading it
   was a defensible sidestep. Under the NaN reading it is actively harmful: it would silently
   preserve the last pre-divergence policy and *remove the only signal* that the run died, which
   is precisely the failure this entry is about.

My reading is 1 then 3, with 2 already in flight. 1 is a deviation across baselines and 3 needs
compute, so both are yours; only 2 was mine to start.

---

**DEFAULT SET AT THE PRE-RUN GATE, 2026-09-03: a non-finite checkpoint fails its cell; it is never
a result, and it is never silently retried.** The instrument now exists and did not when this entry
was written: `datasphere/native/family.py`'s finiteness probe walks any nested checkpoint structure
for floating-point values and the runner fails the cell on a single NaN or infinity. It proved
itself on `ctrl` the day it was generalised — `{"non_finite": 0, "float_values": 9955955,
"loader": "msgpack"}`. **The default has three parts.** (1) A cell whose checkpoint is non-finite is
*failed*, not reported, and the failure is the finding. (2) It is **not** automatically re-run at a
different seed, because "retry until finite" silently conditions the result set on convergence and
would turn a stability property into a survivorship artefact — the exact shape of C57's original
"learned, then collapsed" misreading. (3) The frame at which it went non-finite is worth recording
when a stamped checkpoint grid exists, since that brackets the divergence for free. **What would
overturn this**: evidence that divergence is an artefact of our harness rather than the algorithm,
which would make failing the cell a false verdict rather than a true one.

### C58 — For half the baselines, "what did it train on?" is unanswerable, not merely unanswered {#c58}
**Class** DESIGN-GAP · **Status** OPEN · **Cross-ref** [C54](#c54), [C56](#c56)

[C54](#c54) closes by saying that verifying the training distribution from the stored buffer is
cheap and nothing here was doing it. The first half of that is true of `drqv2` and **false of
half the set**, which was assumed rather than checked. The check needs one thing: an observation
recorded *during training* and still on disk afterwards. Audited across all twelve:

| baseline | witness | what exists |
|---|---|---|
| `drqv2`, `svea`, `drq`, `sgqn`, `curl` | **partial** | replay episodes spill to `buffer/*.npz`, but `replay_buffer.py:94` hardcodes `_save_snapshot = False`, so only the run's *ending* survives ([C54](#c54)) |
| `alda` | **yes** | `ReplayBuffer.save()` writes `**self.__dict__`, observations included, and `trainers/alda_trainer.py:690` calls it |
| `rad`, `soda` (`dmc_gb`) | **no** | nothing persists observations |
| `ctrl`, `ppg`, `idaac`, `ibac_sni` | **no** | on-policy; rollouts live in memory. `ibac_sni`'s one `np.save` is in `toy-classification/experiment.py`, not the RL path. *(Corrected 2026-08-21: this row said "only weights are written", which is wrong for two of the four — [C60](#c60) found that `ctrl` cannot write weights at all and `ppg` never does as configured.)* |

So six of twelve leave no trace of what they saw. For those, C54's question cannot be asked at
all — a distinction worth keeping, because "we haven't checked" invites "then check", and here
there is nothing to check.

**And the tooling silently pretended otherwise, 2026-08-24.** `scripts/run_cell.sh` attaches
`watch_training_frames.py` to every cell, which reads as "provenance is captured for all of them".
It was not. The watcher matched on `num_train_frames=`, a hydra override that appears only in
RL-ViGen run paths, and `watch_training_frames.py:31` searched only `RL-ViGen-upstream/exp_local`
— so for a clone it looked in the wrong tree for the wrong string, captured nothing, exited 0, and
the cell was produced looking checked. The `rad` test cell has **0 frames** and reported success;
that number was printed on screen at the time and read past.

Fixed three ways, and the third is the one that matters: the watcher now searches both trees, the
match string is chosen per family, and **a baseline that can be witnessed but captured nothing now
exits 4** rather than returning quietly. Baselines that cannot be witnessed at all say so up
front instead of being handed an inert watcher.

**This is the shape of every finding in this register so far**, which is why it is written down
rather than fixed in passing: two things each correct on their own — "verify the training
distribution" and "baselines keep replay buffers" — with an unexamined join between them. The
first was a lesson from a real defect; the second was true of the baseline that produced the
defect and of nobody else.

**Options**.

1. **Log an observation fingerprint per episode in each baseline** — a few numbers into whatever
   metrics stream it already has. Twelve deviations, ENABLES-class, changing no algorithm and no
   reported number, and it makes the check uniform and permanent. It is also twelve more lines
   of ours in a project whose whole discipline is minimising those.
2. **Attach `scripts/watch_training_frames.py` where a buffer exists and disclose the asymmetry.**
   Zero deviations, works today for six baselines, and leaves the comparison saying "six of our
   twelve rows have verified provenance and six do not" — which is a real thing to have to write
   in a results table.
3. **Do nothing and treat [C54](#c54) as `drqv2`-specific.** Defensible only if C54's mechanism
   is eventually shown to be specific to that run. It has not been, and the 08-18 run cannot be
   re-observed.

My reading is 2 now and 1 before any production run, because 2 costs nothing today and 1 should
not be spent until [C57](#c57) says whether runs survive at all. But 1 is twelve deviations, so
it is yours.

---

**DEFAULT SET AT THE PRE-RUN GATE, 2026-09-03: provenance is claimed at the strength it can be
demonstrated, per baseline, and the six without a stored observation say so.** For the six that keep
no observation from training, "it trained on scene 0 in the `train` regime" rests on the config and
the code path — which is a *good* argument, since the path is short and now well understood — but it
is **not** the same claim as one backed by a stored frame, and the difference is exactly what C54
found the hard way. So: numbers from those six are reported with their provenance labelled
`config-asserted`, and numbers from the rest `observation-verified`. **Deliberately NOT fixed before
the sweep**, and the reason is scope: making six clones record a training observation is six
deviations, each touching the training loop of a baseline whose faithfulness is the thing being
measured, in service of a check rather than a result. **The cheap partial that IS available**: the
records now carry `native.recorded_on` ([C95](#c95)), so the *platform* half of provenance is
mechanical for every baseline even where the observation half is not. **What would overturn this**:
any disagreement between a config-asserted claim and a later observation-verified one, which would
make the label a warning rather than a footnote.

### C59 — The comparison's collector could not read the comparison's runs {#c59}
**Class** DESIGN-GAP · **Status** RESOLVED · **Cross-ref** [C58](#c58), [C53](#c53)

`scripts/collect_metrics.py` is the instrument that turns runs into the table this project
exists to produce. Pointed at `RL-ViGen-upstream/exp_local` it reported **0 records from 0
baselines**, for all twelve, with sixteen `drqv2` runs sitting in the tree.

**Decision** add `--from-runs`, which walks a hydra output tree and reads each run's `eval.csv`,
taking the baseline from the run's own `.hydra/hydra.yaml` (`config_name`) rather than from the
directory name — RL-ViGen selects its agent by picking a whole config file, so the path never
says which baseline ran. **Effect** 106 records from the existing runs where there had been
none: 38 pre-P14, and 34 eval plus 34 train-regime rows from post-P14 runs, which record both
regimes explicitly. Commit `61b7a192`.

Two things this cost, both worth recording because each was a separate wrong guess:

- `collect()` expects `<logdir>/<baseline>.log` — a **flat directory of named logs**, which is
  the smoke-test layout it was written and tested against. The parsers were never wrong; nothing
  had joined them to a real tree.
- The first fix read `train.log` and also returned nothing, because `train.log` is *hydra's* log
  — fourteen lines of robosuite warnings — while the `| train | F: … |` lines the parser matches
  go to **stdout**, which a real run does not persist. `test_train_log_alone_yields_nothing`
  pins that, since it is the half a reader would not guess.

The regime is **not** inferred. Post-P14 runs carry `train_regime_reward`; pre-P14 runs carry no
record of what `RLVIGEN_EVAL_MODE` was, so those rows are emitted as `eval(unrecorded)` rather
than assumed to be `eval-easy` — assuming it is exactly how a generalisation gap gets
manufactured out of two measurements of one distribution, which `parse_rlvigen`'s own docstring
already warned about for a different reason.

**Then the fix repeated the defect, within the hour.** `collect_from_runs` was written with
`glob("*/*/eval.csv")` — `exp_local/<date>/<run>/` — and validated against a tree that contains
**only `drqv2` runs**. Only `cfgs/config.yaml` writes that shape. `svea_config`, `drq_config`,
`sgqn_config` and `curl_config` all interpolate `${name}` into `hydra.run.dir` and land one level
deeper, at `exp_local/<date>/svea/<run>/`. The collector found `drqv2` and silently missed **four
of the five**, and every test passed, because a fixture built from the layout I had could not
contain the layout I did not.

Caught only because a `svea` run happened to be in flight and its directory looked wrong. Fixed
with `rglob` — depth is not part of the contract, having a `.hydra/hydra.yaml` is — and pinned by
`test_a_baseline_nested_one_level_deeper_is_found`. Before: 0 svea records. After: 28.

Writing this entry did not prevent me from committing its own failure mode an hour later, which
is worth more as a datum about the register than any of the rest of it: **an entry describing a
mistake does not stop the mistake.** What stopped it was an unrelated run being open on screen.

Same shape as the rest of this register: two correct halves, no join. It is listed separately
from [C58](#c58) only because that one is about runs that record nothing and this one is about
records nothing reads.

---

### C60 — Every baseline's checkpoint cadence exceeds the budgets that survive, and two never save at all {#c60}

> ### Correction, 2026-09-02: `ppg` does save — at construction, untrained — and that is worse
>
> The table below reads *"`ppg` … `LogSaveHelper` when `ic_per_save > 0`; **never set** — the name
> appears nowhere outside `log_save_helper.py` and no launcher passes it"*. The observation is
> right and the conclusion drawn from it is wrong: **`ic_per_save` does not need to be passed,
> because it defaults to `100_000`** (`log_save_helper.py:34`). So the branch is live, and
> `__init__` calls `self.save()` the moment the helper is constructed (`:50-51`) — **before a
> single gradient step**.
>
> **Consequence at probe scale, observed.** The 2026-09-02 `ppg` cell ran 4,096 interacts, which
> never crosses a 100,000 boundary, so the construction save was the *only* save. The retained
> `snapshot.pt` therefore holds the model as initialised — and `retain()` passed it, because a
> file of the right name existed and was not empty. It was caught by arithmetic rather than by a
> gate: the differential entropy of a diagonal Gaussian depends only on σ, the run logged
> `Opt/entropy` 9.936886, and `log_std = 0` gives exactly 9.932570.
>
> **Consequence at production scale, and it is a different defect.** At 600k, six boundaries are
> crossed, so a production `ppg` checkpoint *is* trained — but it is the model at the last 100,000
> boundary, not at the endpoint. Every other baseline here is evaluated at its declared endpoint.
>
> **So "never saves" understated it in the direction that matters.** A baseline that saves nothing
> fails loudly at `retain()`. This one produces a plausible artifact of the right size and name
> whose contents are not what the row will claim they are — which is the failure mode this whole
> register exists for. The remedy is a terminal save in the clone, beside the helper's cadence,
> and it is not yet written.
**Class** INHERITED · **Status** OPEN · **Cross-ref** [C57](#c57), [C58](#c58), [STAGES.md](STAGES.md)

A table cell needs a trained policy that can be evaluated afterwards. Audited across all twelve,
that is a different question per baseline and nobody had asked it:

| baseline | saves when | default |
|---|---|---|
| `drqv2` `svea` `drq` `sgqn` `curl` | `global_step % 50_000 == 0`, and only if `save_snapshot` is passed | every 50k steps |
| `rad`, `soda` (`dmc_gb`) | `step % args.save_freq == 0` | **100k** |
| `alda` | `step % checkpoint_n_steps == 0` (`trainers/alda_trainer.py:73,614`) | 50k |
| `ibac_sni` | `save_interval` | 10 |
| `idaac` | `j == num_updates - 1` — **the final update only** | end of run |
| `ppg` | `LogSaveHelper` when `ic_per_save > 0` | **never set** — the name appears nowhere outside `log_save_helper.py` and no launcher passes it |
| `ctrl` | — | **cannot**: `train_ppo.py:12` is `# from flax.training import checkpoints`, commented out |

**`ctrl` cannot produce a checkpoint as published**, and the line is **upstream's**, not ours —
the pinned `ctrl_public @ 7a118c8` carries it, and `runnable/_patches/ctrl.patch` does not touch
checkpointing. It also declares `checkpoint_interval = 25 * 999424` (~25M steps) and ships an
`evaluate_ppo.py` whose line 60 *restores* a checkpoint its own trainer cannot write. `ppg` is the
same outcome by a different route.

*(Corrected 2026-08-21: `alda`'s row first read "`--save_freq`, default 100k". That flag is in the vendored `dmcontrol_generalization_benchmark` copy, which alda's entry point does not use — it runs `scripts/train.py` against a spec. Its real cadence is 50k, the same as the natives. Reading a flag out of a file the program does not execute is the same mistake as [C59](#c59)'s, in an audit written to catch it.)*

**The pattern across the rest holds anyway:** the remaining defaults are at or above **100k steps**,
while [C57](#c57) found that both runs reaching 120k diverged to NaN and that 50k–100k is the only
interval that has yielded a finite checkpoint. So the defaults are tuned for runs longer than the
ones that survive here, and a short run produces nothing anywhere — which is exactly what the
[STAGES.md](STAGES.md) inventory found empirically for the five natives before this audit
explained it.

This corrects [C58](#c58)'s table, which lists `ctrl` under "only weights are written". Nothing is
written.

**Two more baselines cannot produce a cell on this machine, for reasons already on file.**

- **`curl`** dies under the MPS shim with `scatter: index -1`. That is **documented in this very
  register** ([C52](#c52)'s table note) and worked around in `runnable/_launch/smoke_all.sh:15,49`
  with `device=cpu`. CPU is ~60× slower for conv work here, so a 55k cell would take days:
  `run_cell.sh` now refuses it with the reason rather than starting one.
- **`drq`** runs, but only with `use_tb=False` — turning TensorBoard on activated a latent
  upstream bug ([INTEGRATION-DELTA.md](INTEGRATION-DELTA.md), P-TB). Not blocked, just asymmetric.

**How the `curl` one was found is the part worth recording.** I crashed two 55k runs, wrote a
synthetic reproduction of its loss on MPS (which passed), read the traceback frames, and formed a
hypothesis about async error surfacing at `.item()` — before grepping the register for the error
string, which returns the answer immediately. That is the **third** time in this project that
re-deriving something already written down has cost real effort ([C55](#c55): the chance floor;
[C59](#c59): the collector layout, twice). The register is not failing to record things. It is
failing to be consulted, and by its own author.

**Option 1 is done and verified, not just written.** `scripts/run_cell.sh` now dispatches per
baseline and passes the cadence each one needs; `ctrl` and `ppg` exit immediately with the reason
rather than running for hours to produce nothing. Tested on a clone: a 2000-step `rad` run wrote
`logs/robosuite_Door/rad/0/model/1000.pt`, the **first model file any `dmc_gb` run here has ever
produced** — three earlier `rad` seeds sit in that tree with empty model directories.

**And the checkpoints cannot all be read in one process.** Extending
`check_checkpoint_finite.py` to open the clone's file broke it on RL-ViGen's: both ship a module
named `utils`, and putting both on one `sys.path` made an RL-ViGen snapshot fail with
`cannot import name 'random_overlay' from 'utils'`. `dmc_gb` and RL-ViGen also both have
`algorithms`/`algos`. Since a checkpoint here is a **pickled agent object**, reading it requires
importing its baseline's classes, so no ordering of a shared path serves twelve baselines at
once. Each checkpoint is now opened in its own subprocess with only its own paths, pinned by
`test_two_families_do_not_shadow_each_other`.

That is the hermetic principle turning up inside a diagnostic script: the argument for it is
usually made about training code, and it applies just as hard to anything that has to *read*
twelve baselines' artifacts.

**Options**.

1. **Pass the right cadence per baseline where a flag exists** — `--save_freq 25k` for
   `dmc_gb`/`alda`, `save_snapshot=True` for the natives, `ic_per_save` for `ppg`. No source
   change, seven or eight baselines covered, and it belongs in `scripts/run_cell.sh` beside the
   reasons. Does nothing for `ctrl` or `idaac`.
2. **Uncomment `ctrl`'s import and give `idaac` a periodic save** — two deviations, both
   ENABLES-class, both changing no algorithm. It is the only way those two ever produce a
   mid-training policy, and `ctrl`'s is arguably restoring a facility its own evaluator assumes.
3. **Accept that `ctrl` and `idaac` contribute end-of-run numbers only**, and say so in the table.
   Zero deviations. It means those two rows cannot carry a learning curve or an intermediate
   retention point, which is a real asymmetry to have to explain.

My reading is 1 now — it is free and unblocks most of the table — with 2 needed before `ctrl` can
appear at all. 2 is a deviation on someone else's code, so it is yours.

---

**DEFAULT SET, 2026-09-03 — the achievable cadence is not a preference, it is a fixed grid, and a
plan in the register assumed otherwise.** For the five RL-ViGen-family baselines, `save_snapshot()`
is called only from `if self.cfg.save_snapshot and (self.global_step % int(5e4) == 0)` plus the
endpoint block. `RLVIGEN_PRESERVE_SNAPSHOTS` (patch P18) is a **filter over saves upstream already
performs** — it can drop members of that set and can never add one. So the reachable stamps are
exactly `{50k, 100k, 150k, …}` ∪ `{num_train_frames}`, and nothing else is available at any budget.

**Verified against a run that was designed to disprove it.** The 60k bracket set
`RLVIGEN_PRESERVE_SNAPSHOTS=25000` expecting stamps at 25k, 50k and the endpoint; its
`checkpoints/` holds `snapshot_50000.pt` and `snapshot_60000.pt` and there is no 25k file, because
there could never have been one.

**The default, therefore**: a budget curve for this family is read at multiples of 50k plus the
endpoint, and **a point below 50k is obtained by running a short cell whose endpoint IS that
frame** — the endpoint save is the only mechanism that places a stamp off the grid. This is why the
checkpoint-defect bracketing used 6k, 50k, 60k and 100k cells rather than one run with a fine
cadence. Recorded as a default rather than left open because it is a property of upstream's code,
not a choice anyone is free to make differently.

### C61 — A hyperparameter tuned for a 15-way categorical is applied to a 7-D Gaussian {#c61}

> **CURRENT DISPOSITION, 2026-09-04 — resolved for production: `ibac_sni --entropy-coef 0.0`.**
> This is baseline-specific: IDAAC, PPG and CTRL remain healthy at 0.01. On the final IMPALA
> architecture, a controlled same-code/seed/task comparison measured mean log-std **0.5381** at
> 24,960 frames with 0.01 versus **0.0329** at 25,088 with 0.0, so the entropy bonus is causal.
> Why IBAC-SNI is uniquely sensitive remains a research question, not a reason to run the known
> destructive setting in production.

> ### SUPERSEDED FOR `ibac_sni` LATER THE SAME DAY — the diagnostic arrived, and it points at a
> ### value. Default is now `--entropy-coef 0.0` for `ibac_sni`; the other three keep 0.01.
>
> The block below set the default at 0.01 and said explicitly what would move it: *"changing the
> coefficient is itself an undeclared deviation and would need evidence pointing at a value; no
> such evidence existed."* It now exists, from a controlled pair differing in that one flag —
> identical code, seed, architecture, task and container:
>
> | coefficient | job | `mean_log_std` | entropy | at frame 24,960 |
> |---|---|---|---|---|
> | 0.01 | `bt1i1s0j8qhbal67gjnn` | 0.0026 → **1.4472** over 100k, monotonic | 9.95 → 20.03 | **0.5381** |
> | 0.0 | `bt1338ue402pkpua43g0` | **flat at 0.033** through 25,088 | 10.16 | **0.0313** |
>
> **The drift is not small on this baseline, and it is caused by the bonus.** The competing
> explanation — the policy gradient widening σ because returns carry no signal — is refuted, since
> the returns carry no more signal in the second run and σ does not move. σ ≈ 4.3 against actions
> in [−1, 1] is a policy that is noise, which is why `ibac_sni` never left the [C55](#c55) floor.
>
> **Why 0.0 — and a claim withdrawn the same hour.** I first argued that a Gaussian's entropy is
> unbounded, so *any* positive coefficient must inflate σ without limit. **This project's own data
> refutes that**, and the check cost nothing because the curves were already retained. At the same
> nominal 0.01:
>
> | baseline | `mean_log_std` | at | note |
> |---|---|---|---|
> | `idaac` | **0.0206** | 100k frames | flat |
> | `ctrl` | **0.0034** | 10k frames | flat |
> | `ppg` | **0.0008** | 4k frames | flat, and it clamps (`log_std_clamped_fraction`) |
> | `ibac_sni` | **1.4472** | 100k frames | runaway |
>
> So 0.01 is **not** inherently wrong for a continuous head, and three of the four are fine on it.
> The honest statement is narrower: *something specific to `ibac_sni` lets the entropy term
> dominate*, and the coefficient is the lever that demonstrably removes it. **The default is
> therefore an empirical workaround with the cause not yet isolated, not a principled setting** —
> which is a weaker justification than the one first written here, and it should be read that way.
>
> What survives of the mechanism argument is direction, not magnitude: for a Gaussian
> `dH/d(log σ) = 1` per dimension, so the bonus contributes a **constant upward push at every
> gradient step**, whereas a categorical's push vanishes as it approaches uniform. Drift therefore
> accumulates per *gradient step*, not per frame — and `ibac_sni` takes far more per frame than its
> siblings (`frames_per_proc` 128, `epochs` 4, `procs` 1 ≈ 3,100 steps over 100k, against `idaac`'s
> ≈ 780). In a policy that is learning, the surrogate objective pushes back; `ibac_sni` is not.
>
> **The discriminating run**, which would turn the workaround into a diagnosis: `ibac_sni` at
> **0.01 with the bottleneck off** (`--sni_type ''`, no `--use_bottleneck` — plain PPO). If σ stays
> flat, the VIB/SNI bottleneck is destroying the advantage signal that would otherwise counteract
> the bonus; if it still runs away, the update schedule is the cause. Either answer is actionable
> and neither is expensive.
>
> **Zero is the ordinary continuous-control setting**, not an exotic one: the 0.01 convention comes
> from discrete, Atari-style work, and continuous PPO implementations commonly default the entropy
> bonus to 0. The principled alternatives are clamping log_std (`ppg`; SAC by construction) and
> SAC-style automatic temperature against a target entropy of −dim(A) — **which eight of our twelve
> baselines already use**, and which is a code change rather than a configuration one.
>
> ### DEFAULT SET, 2026-09-04 — leave the coefficient at 0.01 on all four, and decide it on the
> ### diagnostic rather than in advance. The first measurement is in and the feared drift is small.
>
> **This is not "keep it for fidelity".** Transcribing a number is not fidelity, and that argument
> was already rejected here. It is that **changing the coefficient is itself an undeclared
> deviation** and would need evidence pointing at a value; no such evidence existed, and the entry
> has been open because the quantity that would supply it was not being logged on three of the four
> baselines. As of today it is logged on all four ([REGISTER](REGISTER.md), 2026-09-04) — so this
> entry stops being an argument and becomes a measurement.
>
> **First data point, and it is against the alarm.** `idaac`'s 100k checkpoint
> (`bt1lnh6b11u231cvh4ho`, 99,328 frames) carries `dist.logstd._bias` directly:
>
> | | mean_log_std | σ | entropy | boundary_fraction |
> |---|---|---|---|---|
> | at init | 0.0000 | 1.000 | 9.933 | 0.317 |
> | at 99,328 frames | 0.0240 | 1.024 | 10.100 | 0.329 |
> | linear extrapolation to 6e5 | 0.145 | 1.156 | 10.946 | 0.387 |
>
> The drift is real, monotone in the direction the entry predicts, and **small** — σ rises 2.4% over
> 100k frames, and even taken linearly to the production budget it reaches 1.16, not the saturated
> noise the entry warns of. `idaac` is also the case the entry calls *partly protected* (it
> normalises advantages), so this bounds the mildest of the four and settles nothing about the
> other three. The extrapolation is linear because there is one interval to fit; it is an
> order-of-magnitude statement, not a trajectory.
>
> **Second data point, `ppg`, and it agrees** (`bt1apmmvvtfvjveil6ko`, 2,560 frames): `mean_log_std`
> moves 0 → **0.000819**, entropy 9.93257 → 9.938303, `boundary_fraction` 0.317311 → 0.317707. That
> rate carried to 6e5 gives ≈0.19, the same order as idaac's 0.145 — two baselines, two budgets,
> the same modest drift. **`train/log_std_clamped_fraction` is 0.0**, so ppg's clamp is not binding
> at this budget and its shared keys describe the same object as its raw parameter for now; the
> clamp becoming load-bearing later is exactly what that key exists to announce. Note the budget is
> 2,560 frames — this bounds the drift's *early* rate and cannot see a late acceleration.
>
> **Third data point, `ctrl`** (`bt1ums2q8170s3cq5p9l`, 10k): `mean_log_std` 0.00205 at frame 4112
> and 0.00398 at 8224, σ 1.00206 → 1.00401, `boundary_fraction` 0.3183 → 0.3192.
>
> **The three rank in the order this entry's own mechanism predicts, which is worth more than any
> one of them.** Per-frame drift, each extrapolated linearly to 6e5: `ppg` ≈ 0.12 (clamped, so
> bounded by construction), `idaac` ≈ 0.145 (normalises advantages, so the entropy term meets an
> opposing force of order 1), `ctrl` ≈ 0.29 (**neither** — no clamp, no advantage normalisation).
> ctrl is roughly twice the others and is the one the entry singles out as least protected.
>
> **This is suggestive and not established**, and the reason is in the numbers: the three budgets
> are 4k, 8k and 99k frames, the extrapolation is linear from one or two intervals, and a ranking
> reproduced across three baselines at three different scales is a weaker instrument than it looks.
> What it does support is that the coefficient is not producing runaway entropy at any of the three,
> and that the diagnostic can now see the ordering at all — which it could not a day ago.
>
> Two constants fell out as cross-checks and both held exactly: entropy at `log_std = 0` is
> **9.93257**, the figure `runnable/ppg/phasic_policy_gradient/train.py:104` records independently,
> and `boundary_fraction` at σ=1 is **0.3173**, the 0.317 this entry states. Neither was arranged.
>
> ### THE TRIP-WIRE FIRED. `ibac_sni`, measured 2026-09-04, and the default above does not survive it
>
> **Configuration note added later the same day**: this was measured with `model_type=default`,
> the MiniGrid trunk at 64x64 — a 6,900,671-parameter model. [C3](#c3) has since made
> `--model_type impala` (360,399 parameters, the paper's own pixel network) the launcher's
> selection, so **this measurement describes a configuration we no longer run by default** and
> the escalation below must be re-tested there. It is not withdrawn: it was correct for what
> it measured, and it is the reason the architecture was examined at all.
>
> `bt1cj6rgeptsu9f3v0o6`, 100k frames — the same budget as idaac's, so this comparison needs no
> extrapolation:
>
> | frames | σ | mean_log_std | boundary_fraction |
> |---|---|---|---|
> | 128 | 1.00196 | 0.00196 | 0.31826 |
> | 50,048 | 1.52432 | 0.42120 | **0.51157** |
> | 99,968 | **1.81054** | **0.59216** | **0.57980** |
>
> **`boundary_fraction` crosses 0.50 at about 50k and reaches 0.580.** More than half the policy's
> action mass now falls outside the box robosuite will accept, so most of what the network emits is
> decided by the clip rather than by the policy. Against `idaac` at the same 100k, `mean_log_std`
> is **0.592 against 0.024 — twenty-five times the drift**, and monotone at every stamp.
>
> **This is the entry's own prediction, confirmed on the baseline it named.** `ibac_sni` has no
> clamp and no advantage normalisation. The 100k measurement here was on the former 6.9M-parameter
> MiniGrid trunk; the launcher's current source-backed Impala default is a separate configuration
> and must be judged from its own curve.
>
> **So the default above is superseded for `ibac_sni` specifically.** Its own escalation rule —
> *"either fires → the coefficient is decided per baseline on that evidence, and the affected cells
> are re-run rather than reported with a caveat"* — now applies, and holding 0.01 there is no longer
> the evidenced choice. The three others stay as they were; their measurements did not fire it.
>
> **DEFAULT SET, 2026-09-04, awaiting approval — do NOT change the coefficient, and stop treating
> `ibac_sni` as poolable.** The two halves are separately argued:
>
> * **Do not change it.** Changing `entropy_coeff` requires evidence pointing at a *value*, and
>   none exists. The measurement says 0.01 is wrong for this head; it does not say what is right.
>   Picking a number by judgement would replace a transcribed author's constant with an invented
>   one and would be the *less* defensible of the two undeclared quantities.
> * **Stop pooling it.** Reporting a number from a policy whose action mass is 58% outside the box,
>   in a table beside eleven that are not, is the kind of silent join this project exists to refuse.
>   **`ctrl` is the precedent**: it already sits outside the comparable table for a stated reason
>   ([COMPARABILITY_CONTRACT](COMPARABILITY_CONTRACT.md) §5d, a different estimand). `ibac_sni`
>   joins it for a different stated reason — its policy is mostly clipping — and both stay visible
>   with their diagnostic attached rather than being dropped.
>
> **The deciding experiment, named and NOT run** (compute is not being spent on it): a three-value
> `entropy_coeff` sweep at 100k on `ibac_sni` alone, reading `boundary_fraction` at the endpoint,
> which is roughly three cells of about an hour each. That produces the value the first half above
> says is missing. Until it is run, "hold 0.01, report outside the pooled table" is the position.
>
> **What this does NOT establish**: one seed, one budget, and the return column is noisy across the
> same stamps (12.79 → 0.97 → 7.63 → 4.50 → 4.38 → 4.74), so the drift is not yet tied to a
> degradation in reward. Whether the clipping *costs* return on Door is a separate measurement.
>
> **The trip-wire, named now so it is not chosen after seeing the run.** A production cell is
> escalated back to this entry if, at any stamp: `boundary_fraction > 0.50` (more mass outside the
> action box than inside it — control has become clipping), or `ppg`'s
> `train/log_std_clamped_fraction > 0` for two consecutive stamps (the clamp is load-bearing, so
> `ppg`'s entropy gradient is being silently cancelled and its effective coefficient is not 0.01 at
> all). Either fires → the coefficient is decided per baseline on that evidence, and the affected
> cells are re-run rather than reported with a caveat.
>
> **Unchanged and still owed to the owner**: `ibac_sni` remains the exposed one — no clamp and no
> advantage normalisation — but the old 6.9M-parameter measurement is superseded as a production
> configuration by the source-backed Impala default. The 100k Impala run already produced the
> diagnostic curve; the remaining question is the owner's coefficient/configuration decision,
> not whether the policy scale can be read. Recorded as a default awaiting approval, not as a
> settled decision.

> ### Update, 2026-09-02: the risk is not equal across the four, and one locator below is wrong
>
> The analysis under this heading is unchanged and was re-derived independently today, which is
> evidence for it rather than against. Three things are added, and the first is a correction.
>
> **`ibac_sni`'s locator points at a tree that never runs.** The table below cites
> `coinrun/coinrun/config.py:104`. Our launcher runs the **`torch_rl`** branch, where the value
> lives at `runnable/ibac_sni/torch_rl/scripts/train.py:49` — same `0.01`, different file. Anyone
> acting on this entry would have edited a file with no effect on any run here.
>
> **Only one of the four clamps its log-std.** `ppg` does, at `distr_builder.py:31` —
> `logstd.clamp(-5.0, 2.0)`, so σ ∈ [0.0067, 7.39] and its entropy is bounded after all. The other
> three do not: `idaac` uses `AddBias(torch.zeros(...))` (`distributions.py:89`), `ibac_sni`
> `nn.Parameter(torch.zeros(...))` (`torch_rl/model.py:142`), `ctrl`
> `self.param('log_std', nn.initializers.zeros, ...)` (`models.py:129`). **So the unbounded force
> this entry describes is opposed by a bound in exactly one of the four.**
>
> **The opposing force differs too, and that ranks the risk.** The entropy term is a fixed 0.01;
> what pushes back is the policy gradient, whose scale depends on normalisation. `idaac`
> normalises advantages (`algo/idaac.py:61`); `idaac`, `ppg` and `ctrl` normalise rewards.
> **`ibac_sni` does neither** — so it is the one baseline where a fixed 0.01 is opposed by
> whatever Door's raw shaped return happens to produce, *and* its σ is unbounded. It is the
> ranked-worst case and the first place a σ drift would appear.
>
> **MEASURED, 2026-09-02 — the ranking above is now data, not reasoning.** Read directly off the
> retained probe checkpoints:
>
> | baseline | frames | mean `log σ` | per 1k frames | adv-norm | rew-norm | clamped |
> |---|---:|---:|---:|---|---|---|
> | **`ibac_sni`** | 2,560 | **0.04474** | **0.01748** | none | none | no |
> | `idaac` | 9,216 | 0.00415 | 0.00045 | yes | yes | no |
> | `ppg` | 4,096 | *untrained checkpoint* | — | — | yes | **yes, [-5, 2]** |
>
> **`ibac_sni`'s `log σ` drifts 38.8× faster per frame than `idaac`'s**, in the direction the
> entropy term pushes, in exactly the baseline predicted to be worst-exposed — and `idaac`, which
> normalises both advantages and rewards, is the one that barely moves. The mechanism this entry
> describes is therefore not hypothetical here; it is visible in the first few thousand frames.
>
> Two cautions on the number. These are *early-training* rates and the opposing force grows as the
> policy improves, so a linear extrapolation to 600k would be wrong — what the table supports is
> the **ordering**, not a forecast. And `ppg` cannot be read at all, because its retained
> checkpoint is the untrained construction save (see [C60](#c60)'s correction), which is why its
> clamp goes untested rather than confirmed.
>
> **Now observable.** `scripts/metrics.py::gaussian_policy_health` returns entropy, `mean_log_std`,
> `sigma_mean` and `boundary_fraction` — the last being `erfc(1/(σ√2))` averaged over dimensions,
> i.e. the mass outside the action box: 0.317 at σ=1, 0.617 at σ=2, 0.841 at σ=5. Wired into
> `ibac_sni` first. C6 said nothing monitors σ; something does now.
>
> **DECISION STILL OPEN, and it is a small one:** clamp the three unclamped heads at **ppg's own
> `[-5, 2]`**, or leave them. In favour — it is an in-family precedent rather than an invented
> bound, it is inert in any regime a working policy occupies, and without it a slow σ drift can
> consume a nine-hour run with nothing stopping it. Against — it is an authored deviation in three
> baselines' optimisation, for a failure that has not yet been observed at the 10k scale anything
> has been run to. **My recommendation is to instrument first and decide from the vertical slice**,
> because the slice is the first run long enough for the drift to be visible if it is real.

**Class** INHERITED · **Status** OPEN · **Cross-ref** [C6](#c6), [C7](#c7), [C1](#c1)

**Handicap — affects:** idaac ppg ctrl ibac_sni
*an entropy coefficient tuned for a 15-way categorical, applied to a 7-D Gaussian whose entropy term is 3.67x larger*

The four Procgen-native clones — [C6](#c6)'s third action-distribution family — all inherit an
entropy bonus of **0.01**, verified per file rather than assumed:

| | |
|---|---|
| `idaac` | `ppo_daac_idaac/arguments.py:35` — `default=0.01` |
| `ctrl` | `train_ppo.py:46` — `flags.DEFINE_float("entropy_coeff", 0.01, …)` |
| `ibac_sni` | `coinrun/coinrun/config.py:104` — `('ent', 'entropy_coeff', float, .01)` |
| `ppg` | `phasic_policy_gradient/ppo.py:131` — `entcoef … = 0.01` |

That number was tuned by their authors against Procgen's **15-way categorical**, whose entropy is
bounded above by `ln 15 = 2.708`. On this target the same code drives a **7-D Gaussian**, whose
entropy at `σ=1` is `7 × ½ln(2πe) = 9.93`. So the same coefficient multiplies a term **3.67×
larger at initialisation**, and the rescaling appears in no diff, because no line changed.

**The unbounded part is worse than the scale part.** A categorical's entropy saturates at
`log|A|`, so the bonus has a ceiling. For a diagonal Gaussian `H = Σᵢ(log σᵢ + ½ln 2πe)`, so
`∂H/∂log σ = 1` per dimension and **7 in total, constant** — a permanent upward force on σ with
nothing bounding it.

**This is what makes it more than a scale mismatch, and the reason it is filed against
[C6](#c6).** C6's evidence is *"at initialisation 31.8% of action components are on the box
boundary"*, checked against `2(1−Φ(1)) = 0.3173`. That closed form is `σ`-dependent: at `σ=1.5` it
is `2(1−Φ(1/1.5))` ≈ 50%, at `σ=2` ≈ 62%. If the entropy bonus pushes σ up over training, **C6's
31.8% is a lower bound that grows, not a stable property** — and C6's own conclusion, that "only
the third family's likelihood disagrees with what the environment executes", understates by an
amount nobody has measured. C6 is `MONITORED`, and nothing monitors σ.

**What is *not* claimed here.** [`COMPARABILITY_CONTRACT.md`](COMPARABILITY_CONTRACT.md):62-73
already records the underlying asymmetry — that a 7-D Gaussian's summed entropy is unbounded
while a Categorical's is bounded — as a hazard for *comparing logged entropy numbers* across
baselines. This entry is the same fact with a different consequence (the loss coefficient, and
C6's boundary fraction), so it is adjacent to that coverage, not a discovery that entropy was
overlooked. And an accompanying claim that `ctrl` and `ibac_sni` log neither entropy nor σ **did
not survive checking**: `ibac_sni` has `policy_entropy`, and the contract's own table at line 128
lists `pi/entropy` for `ctrl` and `Loss/entropy` for `ibac_sni`. Per-baseline logging coverage is
therefore *unresolved here* and should not be quoted from this entry.

**MEASURED 2026-08-24, and the effect is real but small at this budget.** Option 1 below was run
without any deviation: `idaac` saves at its final update, so a 60,000-step run yields a
checkpoint whose `dist.logstd._bias` can simply be read. From an initialisation of exactly 0.0:

| | at init | after 60k steps |
|---|---|---|
| log σ, 7 dims | 0.0 | +0.0103 … +0.0481 |
| mean σ | 1.0 | **1.0252** |
| boundary fraction `2(1−Φ(1/σ))` | 0.3173 | **0.3293** |

**The direction is confirmed and the magnitude is not alarming**: every dimension moved *up*, as
the constant `∂H/∂log σ = 7` predicts, and C6's 31.8% becomes 32.9% — a drift of **1.2 percentage
points**, not the 50–62% that this entry's own σ=1.5 and σ=2 illustration invites a reader to
expect. Those were sensitivity arithmetic, not predictions, and quoting them beside a measured
+1.2pp would misrepresent the finding.

**The honest limit on that reassurance:** 60,000 steps is **0.24%** of IDAAC's own 25M-step
budget (`arguments.py:83`, `default=25e6`). The drift is monotone and unbounded in principle, so a
small number at 0.24% of the intended horizon constrains almost nothing about the full one, and
extrapolating linearly would be unjustified. What it does settle is that C6's figure is not
*stable* — it moves in the predicted direction — and that at the budgets this project can
actually run, it moves too little to change any conclusion.

**Options**.

1. ~~**Log σ per update in the four, and re-measure the boundary fraction at 50k frames.**~~
   **Done for `idaac`, above, without a deviation.** Not done for `ctrl`, `ppg` or `ibac_sni` —
   `ctrl` and `ppg` cannot checkpoint at all ([C60](#c60)), so for those two the same reading
   requires the logging change this option originally proposed.
2. **Rescale the coefficient to preserve the bonus-to-return ratio** — e.g. `0.01 × 2.708/9.93`.
   Defensible in principle and a deviation on four baselines that changes every number they
   produce; it also assumes the authors tuned the *ratio* rather than the value.
3. **Disclose and leave it.** The coefficient is what the authors shipped, and running it
   unchanged is this project's null. The cost is that [C6](#c6)'s figure stays an
   initialisation-time lower bound with no error bar.

My reading is 1, which is measurement rather than a deviation and is mine to run once the current
grids finish. 2 is a change to four baselines' tuned hyperparameters and is emphatically yours.

---

**DEFAULT SET, 2026-09-03, AND THE ENTRY IS NOW MEASURED RATHER THAN ARGUED.** This was a
structural argument — an entropy coefficient tuned for a categorical policy, applied to a Gaussian
one — and the pre-production `ibac_sni` cell supplies the observation it was missing.

**Measured over the whole run (79 logged updates, 10,112 frames):** policy entropy rose
**monotonically**, 9.944 -> 10.761, with **not one decrease**. For a 7-dimensional diagonal
Gaussian, `H = 7(½ln 2πe + ln σ)`, so that is per-dimension **σ 1.002 -> 1.126**. The policy began
at its initialisation scale and got *more* random for the entire run.

**Why that is the predicted failure and not ordinary early exploration.** A categorical policy's
entropy is bounded above by `log n_actions`: the bonus saturates once the policy is uniform and can
push no further. A Gaussian's entropy has **no upper bound** — σ can always grow — so the same
coefficient applied to the same loss (`a2c.py:61`, `loss = policy_loss - 0.01·entropy + …`) is a
term that can be increased without limit, and on a task whose reward signal at this budget is
worth single-digit return per 500-step episode, it is the term that wins. **A learning policy
should be committing, not diffusing.**

**DEFAULT REVISED THE SAME DAY, ON THE OWNER'S RULING: adapting is legitimate here, and keeping
0.01 unchanged is the wrong call.** My first default was "keep it, it is the authors' value". The
owner's objection is decisive and I accept it: *if the original was categorical, our
coefficient/method for continuous can be different.* The governing principle at [C1](#c1) keeps a
difference **an author chose**. The authors chose 0.01 *for a categorical policy*, where entropy is
bounded by `log n_actions` and the bonus saturates. Transcribing the same scalar onto a Gaussian
does not preserve their choice — it silently replaces a bounded regulariser with an unbounded one.
**Literal transcription is not fidelity when the functional form changes underneath it.**

**What the adaptation should restore is the PROPERTY, not the number**: an entropy term that cannot
grow without limit. Three ways, in order of how little they disturb the method:

1. **Bound the policy's log-std** — the mechanism this project already contains, since RL-ViGen's
   `drq` clamps log-std to `[-10, 2]` ([C84](#c84) is about that bound). It caps entropy without
   touching the loss or the coefficient, which makes it the minimal change and the closest analogue
   to the categorical ceiling. **Preferred.**
2. **`entropy_coef = 0`** — what mainstream continuous-control PPO implementations default to, and
   for exactly this reason. Honest and simple, but removes the exploration pressure entirely rather
   than bounding it.
3. **Target-entropy with an adaptive coefficient** (SAC-style). The principled continuous answer,
   and much the largest change to the method.

**Not implemented yet, deliberately**: four baselines share this lineage, three of them have only
the argument and not the measurement, and cells are in flight as this is written. It becomes a
recorded deviation in `scripts/deviations.py` when it lands, not a silent edit. **But the number is now known to be doing
something qualitatively different here than in its source domain, and that must be stated wherever
`ppg`, `idaac`, `ibac_sni` or `ctrl` numbers appear**, because it is not a hyperparameter that is
merely "untuned for this task": it is one whose *functional form* changes with the action space.

**What this does NOT establish**: that the other three behave the same way. Only `ibac_sni` was
measured; `ppg`, `idaac` and `ctrl` share the lineage and the argument but not yet the observation.
**What would overturn the default**: a longer run in which entropy turns over — the honest
alternative reading is that 10k frames is simply too early, and that is testable at 100k for the
price of one cell.

### C62 — The shaping ceiling is 250, and it re-reads every number this project has {#c62}
**Class** INHERITED · **Status** RESOLVED · **Cross-ref** [C31](#c31), [C32](#c32), [C48](#c48), [C55](#c55)

**Commit** `c0223c9d` · **Decision** derive Door's reward analytically from the vendored source instead of inferring
"shaping plateau" from our own returns. **Effect** a hard boundary that classifies every return
this project holds, and a like-for-like comparison with RL-ViGen's published table that had never
been possible. Commit `c0223c9d`.

`third_party/robosuite/.../manipulation/door.py:231-252` is an **`if/elif`**: on a step where the
door is open the reward is exactly **1.0 and no shaping**; on every other step it is at most
`0.25` (reaching, `0.25(1-tanh(10·dist))`) `+ 0.25` (latch rotation) = **0.5**. With
`horizon: 500` and `reward_shaping: true` (`robo_config.yaml:18,24`):

| quantity | value |
|---|---|
| **maximum return with the door never opening** | **250.0** — and unattainable, since it assumes zero gripper-handle distance and full latch rotation from step 1 |
| reaching term alone | 125.0 |
| gripper parked 1 cm / 3 cm from the handle, whole episode | 112.5 / 88.6 |
| successful episode | up to 500 |

**So any mean above 250 proves at least one episode opened the door**, and our 79–115 plateaus sit
at 32–46% of a ceiling reachable without the hinge ever moving — consistent with a gripper parked
1–3 cm away for 500 steps. Confirmed against our own data rather than asserted: `cell55k__train`'s
best single episode is **473.34**, far above 250, which is exactly the signature the `if/elif`
predicts for episodes that do open it.

**The like-for-like comparison, which we had never made.** RL-ViGen's Table 6 gives Door
`int(6e5)` frames at `action_repeat: 1` for robosuite — the same unit we run in, so 50k is **12×
below their budget** (22× below the repo's own `easy.yaml` default of 1,100,000), and at 50k the
repo's own `stddev_schedule` still has σ ≈ 0.55 of 1.0. Their published Door Easy means:

| | DrQ-v2 | CURL | DrQ | SVEA | SGQN | PIE-G |
|---|---|---|---|---|---|---|
| Easy, 5 seeds | **3.6** | 6.6 | 14.0 | 268.8 | 391.4 | 387.2 |

Read against the 250 ceiling this is a **source-only result the spreadsheet alone could not give**:
SVEA, SGQN, PIE-G and SRM demonstrably open the door at 6e5, while **DrQ-v2, CURL and DrQ score
1.4–5.6% of the shaping ceiling** — not "partially shaped plateaus" but near-total failure to
approach the handle. **"More budget solves Door" is therefore contradicted for three of our
twelve by the benchmark's own numbers**, and supported only for SVEA.

**And it exposes a category error in our own reporting.** The 79–115 figures are `mode="train"`;
their 3.6 is the **Easy** regime. The like-for-like pairing is our `eval-easy` against their Easy:

| | ours @ 50k | RL-ViGen @ 6e5 |
|---|---|---|
| `drqv2` eval-easy | **3.49** | **3.6** |

At a twelfth of the budget, on the regime they publish, we land on their number. That bears
directly on [C48](#c48) ("nothing has ever reproduced a published RL-ViGen number") and it was
invisible while train-regime returns were being compared against an eval-regime table.

**One anomaly, left open rather than explained.** `snapshot_100k_frames__eval-easy` pools
**131.05 with 63/200 successes and 43 episodes above 250** — a `drqv2` checkpoint at 100k frames
vastly exceeding RL-ViGen's published `drqv2` Door Easy of 3.6 at 6e5. Under
[C31](#c31)'s standing caveat the protocols are not verified to match, so this is not a
contradiction of their table; but it does mean **"our DrQ-v2 is simply under-trained relative to
theirs" is not what the evidence says**, and the gap deserves its own investigation before either
number is used to explain the other.

*Sources verified from the PDF and xlsx directly, not transcribed: supplement Table 6 and Table 2,
Figure 22's axes, and the `Robosuite` sheet's per-seed cells.*

> **Added 2026-08-25: "success" here is our word, and it is more generous than the alternative.**
> `door.py:423`'s `_check_success()` is `return hinge_qpos > 0.3` — a **live threshold, not a
> latch**: it is true while the door is open and false again if it swings back. Our evaluator
> latches it, `scripts/eval_across_scenes.py:218` doing `succeeded = succeeded or ...` at every
> step, so **our success count means "the door was open at some point during the episode"**, not
> "at the end". An external reviewer flagged the end-only reading as a hazard; it does not apply to
> us, but the definition is a choice and was never written down.
>
> **It has no upstream counterpart to disagree with.** Upstream's `eval.py::robo_eval()` — the
> function closest to our protocol — tracks only `episode_reward` and **does not compute success at
> all**; the final-step success pattern lives in `train.py::habi_eval()`, which is the Habitat path.
> So RL-ViGen's published Door figures are *returns*, and our success counts are a metric of our own
> with no published value to be compared against. That is a reason to keep reporting return beside
> success ([C33](#c33)), not a defect — but "their 3.6 versus our 63/200" is not a comparison, and
> nothing should be written as though it were.


### C63 — [C54](#c54)'s pixel-distance correlation does not survive to the next checkpoint {#c63}
**Class** OURS · **Status** RESOLVED · **Cross-ref** [C54](#c54), [C46](#c46), [C47](#c47)

[C54](#c54) concludes that the archived `drqv2` run was not trained on the distribution its config
declares. Its strongest single piece of support is a **graded** one: across the ten `train`-mode
scenes, per-pixel distance from each rendered scene to the run's own stored training frame
correlates with return at **Pearson −0.887, Spearman −0.794**. That correlation was measured at
**one checkpoint** (50k). It was never measured at a second.

**Measured at a second. It largely goes away.** Same stored episode — there is only one, so this is
literally the same training frame — same twenty rendered references, same distance code; the only
thing changed is which checkpoint produced the returns:

| | C54: train half, 50k | train half, **100k** | `eval-easy` half, **100k** | all twenty, 100k |
|---|---|---|---|---|
| Pearson | **−0.887** | **−0.374** | −0.562 | −0.539 |
| Spearman | −0.794 | −0.721 | −0.333 | −0.471 |

The distances themselves replicate: `train`/7 19.44 against C54's 18.61, `train`/2 26.39 against
26.26, `train`/0 42.20 against 39.92 — same values within render noise, same ordering. **So it is
not the metric that moved; it is that the correlation was a property of the 50k policy rather than
of the distance.**

**And one pair disposes of it without any correlation at all.** At 100k, two held-out scenes sit at
effectively the same distance from the training frame:

| combination | mean abs. distance | return @100k | successes |
|---|---|---|---|
| `eval-easy`, scene 4 | 34.34 | **1.40** | 0/20 |
| `eval-easy`, scene 5 | 34.38 | **379.58** | 20/20 |

A 0.04 difference in pixel distance, a **271×** difference in return, one scene below the 1.85
random floor and the other solved every episode. Whatever separates those two, per-pixel distance
to the training frame does not encode it.

**What this does and does not do to [C54](#c54).** C54's conclusion is untouched, because it does
not rest on the gradient — it rests on the two **extremes**, and both reproduce at 100k:
`eval-easy`/0 is still the nearest of the twenty (9.20) and the best-returning (434.27, 20/20),
and `train`/0, the declared training condition, is still next-to-most-distant (42.20) and still at
chance (2.11, 0/20). What is withdrawn is the *graded* reading — that return falls off smoothly
with visual distance. It does not, and C54's own caveat anticipated this in advance: *"this is
correlational across ten scenes, which also differ in ways other than appearance, so it is evidence
for the reading and not a mechanism."* That caveat was right and is now demonstrated.

**Why this is worth an entry rather than a footnote.** The −0.887 is quotable, and a correlation
that strong invites exactly the use its own entry disclaimed — as a mechanism, or as a way to
predict which scenes a policy will handle. Anyone reaching for it should know it reads −0.374 one
checkpoint later on the same run. **A correlation measured at a single point on an axis is a claim
about that point**, and this project now has two points on that axis that disagree.

**Falsifier, and its result — it was run against this entry the same day it was written.** The
stated falsifier was: if the 50k checkpoint's `eval-easy` half also came in near −0.89, the split
would be regime-specific rather than checkpoint-specific and this entry would be blaming the wrong
axis. The 50k grid was already on disk, so this cost one pass over stored returns. **The falsifier
did not fire.** All four halves, same distances throughout:

| checkpoint | `train` | `eval-easy` | both, n=20 |
|---|---|---|---|
| **50k** | −0.876 | −0.852 | **−0.871** |
| **100k** | −0.374 | −0.562 | **−0.539** |

Strong in *both* regimes at 50k; weak in *both* at 100k. The axis is the checkpoint, not the
regime. (The 50k `train` half reads −0.876 here against C54's −0.887 — a check on this pipeline
against C54's, not an independent result.)

**Third check, added 2026-08-24: the collapse is far larger than evaluation noise.** [C67](#c67)
found that `snapshot.pt` and `snapshot_100k_frames.pt` are the same checkpoint, giving a free
replicate of the 100k evaluation. The correlation reads `train −0.353 / eval-easy −0.541` on one and
`−0.374 / −0.562` on the other — **stable to 0.02**, against a reported collapse of ≈**0.50**. So the
effect is roughly 25× the noise on this statistic. Worth noting *why* it is so stable when the
per-scene means feeding it move by up to 2×: the correlation depends on the scenes' ordering, not
their levels.

**Which makes the finding a claim about policies, not about pixels.** At 50k this policy solves
almost nothing, and what little return it collects tracks how closely a scene resembles the one it
saw. By 100k it solves two scenes outright, and appearance stops predicting where it succeeds —
`eval-easy`/4 and `eval-easy`/5 are the extreme case, 0.04 apart in distance and 271× apart in
return. **So −0.887 is a signature of an under-trained policy rather than a property of the
benchmark's visual axis**, and it should be expected to decay as any baseline here starts actually
solving the task. That is a prediction this entry is making, and the cheapest test of it is the
next baseline that reaches non-trivial success: if its distance↔return correlation is also weak,
this reading holds; if a well-performing policy still tracks appearance at −0.85, it does not.

**Options**.

1. **Run the 50k `eval-easy` grid and settle the falsifier above** — the grid already exists, so
   this is one evaluation pass, not a training run. It decides whether the collapse is
   checkpoint-specific (this entry's claim) or regime-specific (this entry attributing it to the
   wrong axis), and it is the only option that can prove this entry wrong rather than elaborate it.
2. **Leave the correlation withdrawn and cite only C54's extremes.** Costs nothing and is already
   safe, since C54's conclusion never needed the gradient. But it leaves the project unable to say
   *why* the gradient moved, and the same statistic will be re-derived and re-quoted by whoever
   next compares scenes by appearance.
3. **Drop the distance instrument entirely.** Over-corrects: the instrument still separates the
   twenty combinations cleanly and is what [C46](#c46) used to establish the scene axis at all.
   The finding here is about what the numbers *predict*, not about whether they are measured right.

**Option 1 was taken, the same day** — the grid was already on disk, so it cost one pass. Result in
the falsifier block above; it confirmed this entry rather than refuting it, and the answer is folded
back into [C54](#c54) rather than into a fourth entry.

**Decision** re-measure a reported correlation at a second point on the axis it quantifies over
before it is used for anything, and record the second point next to the first rather than replacing
it. **Effect** C54's conclusion stands on its extremes; its gradient does not, and the entry now
says which of the two a reader may lean on. The falsifier was run and confirmed the attribution,
turning a caveat into a claim about under-trained policies. Committed as `918c2d84`.


### C64 — `FAITHFULNESS.md`'s `sgqn` "ours" column describes the retired port, not what runs {#c64}
**Class** FALSE-CERTIFICATION · **Status** OPEN · **Cross-ref** [C53](#c53), [C29](#c29)

Surfaced 2026-08-24 by a review pass over the claim-bearing documents, then re-derived here before
being recorded.

[`FAITHFULNESS.md`](FAITHFULNESS.md)'s SGQN table has an **ours** column. It reads `aux_lr` **0.3**,
`sgqn_quantile` **0.95**. `PROJECT-INDEX.md` routes readers to that file specifically *"before
quoting any baseline's result as that method's result"*, so that column is the answer to "what does
our SGQN actually run at?"

**It is wrong, and wrong in both directions at once.**

| | `aux_lr` | `sgqn_quantile` |
|---|---|---|
| paper, Table 6 (Door/Lift) | 8e-5 | 0.9 |
| what the doc's **ours** column claims | **0.3** | **0.95** |
| the 2026-08-10 fix, `configs/vigen.yaml:82` | 8e-5 | 0.9 |
| **what the clone actually runs** | **1e-4** | **0.93** |

- **Not 0.3.** The doc's own reasoning for 0.3 is explicit and was correct when written: *"We hit
  the trap because we bypass hydra. `load_upstream_module()` loads the class by file path and we
  construct it directly with our own kwargs."* The **clone does not bypass hydra** — it runs
  upstream's own `train.py`, which composes `cfgs/sgqn_config.yaml`, whose lines 54 and 56 supply
  `aux_lr: 1e-4` and `sgqn_quantile: 0.93`. The constructor default is never reached. Verified:
  `grep -n 'aux_lr\|quantile' runnable/_launch/rlvigen.sh scripts/run_cell.sh` returns **nothing**,
  so no override exists anywhere on the launch path.
- **Not 8e-5 either.** The fix is real and still on disk at `configs/vigen.yaml:82` — but that file
  configures the **superseded `rlgen/` port**, retired as the null on 2026-08-17. It cannot reach a
  clone run.

**Why this is FALSE-CERTIFICATION and not a typo.** Every individual statement in that section is
true of the system it was written about. The section is not stale in its *reasoning*; it is stale in
its *referent*. The architecture moved underneath it on 2026-08-17 and the column kept its old
meaning silently, because nothing ties the word "ours" to a code path. This is the failure shape
[`SYSTEM.md`](SYSTEM.md) names as this project's signature — *"both sides individually correct,"* the
defect living at the join — and it is the same defect as [C53](#c53) in a different file.

**The operational effect is the opposite of alarming, which is why it could sit here unnoticed.**
Our SGQN is *not* running at the catastrophic 1000×-off 0.3. It is running at upstream's own shipped
value. A reader acting on the table would go fix a defect that no longer exists, and would
misattribute any SGQN result to a hyperparameter it was never trained with.

**The live question this exposes is a real one, and it is not a typo fix.** RL-ViGen's shipped
config disagrees with RL-ViGen's own paper: `1e-4`/`0.93` against Table 6's `8e-5`/`0.9`. The
document already knows this — *"It does not agree with the paper, and the shipped default agrees
with nothing."* What was never decided is which one **this project's clone** should run.

**Options**.

1. **Run what upstream ships (1e-4 / 0.93) and change only the doc.** This is the status quo and it
   is what the project's own null prescribes — *"the null is the original repository, cloned, running
   its own `train.py`"*. Costs nothing, requires no re-run, and keeps SGQN comparable to every other
   clone, all of which take upstream's shipped values. The price: our SGQN number is then not
   comparable to the published SGQN curves in RL-ViGen's paper, which were produced at Table 6's
   values — and this project's comparison is calibrated against those curves.
2. **Override to the paper's 8e-5 / 0.9 on the clone path.** Makes SGQN comparable to the published
   curve, at the cost of a deliberate divergence from the null for exactly one of twelve baselines,
   which then has to be carried in `FAITHFULNESS.md` forever and justified against every reader who
   asks why SGQN alone was tuned. Also invalidates any SGQN cell already measured.
3. **Run both and report the gap.** Answers empirically whether the 25% `aux_lr` difference matters
   at all on Door, which nobody currently knows. Costs two cells instead of one, and if the gap is
   inside seed noise — plausible, given [C41](#c41) puts run-to-run variation near 49% at 40k
   frames — it buys a documented null result rather than a decision.

**Recommendation** option 1 for the value, option 3 only if an SGQN result is ever load-bearing. The
null's whole point is that upstream's own configuration is the thing being measured; hand-tuning one
baseline toward its paper is the join the project's founding rule exists to refuse. But this is a
judgement about what the claim may say, so it is the owner's, not mine.

> **Strengthened 2026-08-25 by an external review, and the argument is better than the one above.**
> Option 2 is framed above as "diverge from the null to match their published curve." That
> understates the problem: **the configuration that produced their published Robosuite numbers was
> never shipped**, so there is no fixed target to match.
>
> - The paper/code split is not confined to SGQN. Paper Table 2 gives `feature_dim` as 50 for
>   DrQ-v2/CURL and **256** otherwise; **every** shipped config hard-codes `feature_dim: 50`
>   (`RL-ViGen-upstream/cfgs/config.yaml:34`, `svea_config.yaml:34`, `sgqn_config.yaml:33`, `pieg_config.yaml:34`,
>   `srm_config.yaml:34`, and the rest). Already recorded here as
>   [`FAITHFULNESS.md`](FAITHFULNESS.md):71 and open decision 2 in
>   [`STATUS-AGAINST-THE-GOAL.md`](STATUS-AGAINST-THE-GOAL.md):121 — but never connected to this
>   entry.
> - **Upstream ships no robosuite launch script at all.** `RL-ViGen-upstream/scripts/` contains
>   `train.sh`, `eval.sh`, `carlatrain.sh`, `habitrain.sh`, `locoeval.sh`, `locodmc_eval.sh`;
>   `train.sh` is a DMC example and `eval.sh` a CARLA one. No shell script in the repository
>   mentions `env=robosuite`. So the CLI overrides that turned the shipped defaults into Table 6's
>   numbers are **not in the repository**.
>
> **A second correction, 2026-08-25, and this one is against my own recommendation above.** That
> recommendation rests on "the null is what upstream ships." **The project already violates that
> principle, in the same launcher, on every run.** The vendored supplement's Table 2 says
> *"Action repeat — Robosuite: 1"*; every shipped config says `2`; and `rlvigen.sh:77` passes
> `action_repeat=1`. So for `action_repeat` we follow **the paper**, and for `feature_dim` and
> `aux_lr` we follow **the shipped code** — opposite answers to the same question, in one file,
> neither recorded as a rule. Line 77 entered on 2026-08-17 in commit `6f9ba507`, titled *"Two
> comparability defects found, one fixed"*, i.e. as a comparability repair rather than a stance.
>
> **This does not decide C64, it changes what deciding it means.** The honest framing is not
> "should SGQN follow the paper or the repo" but **"what is this project's rule when upstream's
> paper and upstream's code disagree, and does the existing `action_repeat` behaviour comply with
> it or predate it?"** Answer that once and C64, `feature_dim`, and line 77 all follow. Answering it
> only for SGQN would produce a third inconsistency rather than resolve the first two.
>
> **Consequence for the choice.** "Match the paper" is not a well-defined option: it means adopting
> two of Table 6's values for one baseline while leaving `feature_dim` at the shipped 50 for all
> twelve, which reproduces neither configuration. The shipped defaults are the only *complete,
> reproducible, self-consistent* configuration upstream actually distributes. That is an argument
> for option 1 on **reproducibility** grounds rather than on the founding rule alone — and it means
> the honest write-up sentence is not "our SGQN is incomparable to their published curve because we
> chose the shipped value," but "**no run of the shipped repository is comparable to their published
> curve, because the published curve was produced by a configuration the repository does not
> contain.**"

**Falsifier for the recommendation.** If the shipped-vs-paper gap turns out to exceed seed noise on
Door, option 1 silently reports a handicapped SGQN and the recommendation is wrong. That is
measurable with option 3 and has not been measured.

**Not yet corrected in `FAITHFULNESS.md`.** Deliberately: the correction depends on which option is
taken, and writing "ours = 1e-4" first would fossilise option 1 as though it had been decided.

### C65 — Retention above 1 is a contamination alarm, and it separates every grid we hold {#c65}
**Class** OURS · **Status** RESOLVED · **Cross-ref** [C54](#c54), [C46](#c46), [C63](#c63), [C55](#c55)

Surfaced 2026-08-24 while writing an outside-reviewer brief, then re-derived here across every grid
on disk before being recorded.

**Every regime grid this project holds splits perfectly by the *sign* of the train→eval change, and
the split is exactly the contaminated/clean split.**

| grid | `train` | `eval-easy` | ratio | |
|---|---|---|---|---|
| `cell55k` (`drqv2` s6) | 115.31 | 3.49 | **0.03** | freshly trained |
| `cell_drqv2_s7` | 85.01 | 15.00 | **0.18** | freshly trained |
| `cell_drq_s1` | 79.29 | 22.18 | **0.28** | freshly trained |
| `cell_svea_s1` | 97.50 | 85.51 | **0.88** | freshly trained |
| **`random-floor`** | **1.82** | **1.85** | **1.02** | **control — no policy** |
| `snapshot_50k_frames` | 24.75 | 46.71 | **1.89** | archived checkpoint |
| `snapshot_100k_frames` | 52.16 | 131.05 | **2.51** | archived checkpoint |
| `snapshot` | 51.94 | 144.72 | **2.79** | archived checkpoint |

Four freshly-trained cells, all **below** 1. Three archived checkpoints, all **above** 1. No overlap,
and the archived run is precisely the one [C54](#c54) concludes was not trained on the distribution
its config declares.

**The random-policy row is what makes this an instrument rather than a pattern.** It is the positive
control the design needed and did not have: a policy with *no* training distribution cannot have been
contaminated by one, and it lands at **1.02** — the value the screen predicts for "no skill, nothing
to lose." So the scale is anchored at both ends by measurement rather than by assumption. Below 1 is
a policy losing something when the regime changes; at 1 is a policy with nothing to lose; above 1 is
a policy doing *better* away from its declared training condition, which is not a thing a correctly
trained policy does.

**Why this corroborates [C54](#c54) rather than restating it.** C54 argues from pixels — per-pixel
distance from the run's stored training frame, which put `eval-easy`/scene 0 nearest and the declared
`train`/scene 0 nearly furthest. This argues from the **sign of the regime effect**, uses no pixel
data at all, and covers eight grids rather than one condition. Two independent instruments, same
conclusion, and neither is derived from the other. That matters because C54's own "what is not
explained" section is still empty of a mechanism, so its support was carrying a lot of weight from a
single measurement type.

**It also generalises [C46](#c46)'s pre-registration onto a second axis.** C46 wrote, before its
measurement ran, that *"retention above 1 → the training scene is not the easiest ... and would need
explaining rather than reporting."* That was written about the **scene** axis. The same reading holds
on the **regime** axis, and now has a candidate explanation rather than only a warning: the training
condition was not what the config said.

**The screen, stated so it can be used.** A ratio above 1 is not a result and must not be reported as
one. It is a signal that the denominator is not the regime the policy trained in — which is a defect
in the *checkpoint's provenance*, not in the evaluation. Implemented in
[`regime_retention_report.py`](../scripts/regime_retention_report.py) as a refusal, the way that
tool already refuses a chance-level denominator. On the eight grids it prints `1.887 / 2.513 / 2.786`
for the archived checkpoints (every CI entirely above 1, minimum lower bound `1.490`) and
`0.030 / 0.176 / 0.280 / 0.877` for the fresh cells (maximum upper bound `0.936`). The two groups do
not overlap.

> **Which ratio, exactly — and a correction to this entry as first written.** The screen is the
> **all-scene pooled ratio**. It is *not* the POOLED retention this tool reports, which is pooled
> only over scenes whose denominator clears the floor and the 25%-success guard. **They disagree in
> sign on precisely the checkpoints this screen exists to catch**: `snapshot_100k_frames` is `2.513`
> across all ten scenes and `0.010` across the one scene that clears the guard, because that scene
> (`train`/4, 16/20 solved) is one where `eval-easy` collapses to 1.40.
>
> This entry originally said "retention ratio", and the first implementation keyed the alarm to the
> guarded number accordingly — which made it **silent on all three contaminated checkpoints** while
> passing its own tests. That is the same class of error as [C55](#c55)'s floor guard, which was
> aimed at the returns' spread and then at significance before anyone measured the floor: an
> instrument pointed at a neighbouring quantity, green because nothing made it red. Caught by
> running it on the real grids and disbelieving a quiet result, which is the practice
> [`SYSTEM.md`](SYSTEM.md) records as the only thing that has ever caught this.
>
> The two estimands answer different questions and both are worth printing: the guarded one asks
> *how much skill survives where the agent had skill*, the all-scene one asks *which regime does
> this policy prefer*. Only the second is evidence about provenance.
>
> `tests/test_regime_retention_report.py::test_the_screen_reads_all_scenes_not_the_guarded_subset`
> pins it, and **the first version of that test was itself vacuous** — it used a helper that gives
> every scene the same success count, so the guarded subset equalled all scenes and the mutation
> survived. It now builds a per-scene case where scene 0 alone clears the guard, and the mutant
> dies.

**Honest limits, since three points per side is not many.** The archived side is **three grids of one
run**, not three independent runs, so it is closer to one observation than three;
**and [C67](#c67) has since narrowed it further: `snapshot` and `snapshot_100k_frames` are the same
checkpoint byte-for-byte, so the archived side is two distinct checkpoints (50k and 100k) with the
100k evaluated twice.** The screen holds on both replicates — 2.786 and 2.513, ~10% apart, both far
above 1 — so the noise does not reach the threshold; but the evidence is n=2, not n=3.
 the clean side is
four different baselines and is the stronger half. The screen therefore currently rests on "four
independent clean runs behave one way, one contaminated run behaves the other way, and a random
policy sits exactly between them." It would be genuinely falsified by a *second* contaminated run
scoring below 1, or by any clean run scoring above it — neither of which exists yet, and the second
is the cheaper to look for.

**Decision** record the sign of the regime effect as a provenance screen and give it the control that
makes it readable, rather than treating each above-1 ratio as an anomaly to explain individually.
**Effect** three previously-separate oddities — this entry's own trigger, the 2.51 noticed while
verifying [C37](#c37), and C54's scene-0 collapse — are one finding with one cause, and the project
gains a cheap check on any future checkpoint whose training distribution is assumed rather than
witnessed. Committed as `7de97354`.

### C66 — The `nstep` question survived three re-triages because it was ill-posed, not hard {#c66}
**Class** OURS · **Status** RESOLVED · **Cross-ref** [C64](#c64), [C53](#c53)

[`FAITHFULNESS.md`](FAITHFULNESS.md) §5 item 4 — *"Decide `nstep` per family: 1-step for the seven
whose originals are 1-step, or declare 3 a deliberate protocol constant"* — was carried forward
unchanged through **three** re-triages, each time recorded as a one-line decision affecting seven
baselines that kept being outlived by findings which arrived later and got resolved first.

**It was not a hard decision that kept being deferred. It was a question that stopped being
answerable on 2026-08-17**, when the null became the clone, and nothing noticed because the item
named no code path.

- **The five natives already carry a per-algorithm value, supplied by the null itself.** The clone
  runs upstream's hydra configs: `drq_config.yaml:21` → `nstep: 1`; `config.yaml:22`,
  `curl_config.yaml:21`, `sgqn_config.yaml:21`, `svea_config.yaml:21` → `nstep: 3`. That reproduces
  RL-ViGen's Table 2 split exactly, with nobody deciding anything.
- **Four of the seven others have no `nstep` at all** — `ctrl`, `rad`, `soda`, `alda`.
- **The remaining three use the name for a different quantity.** `idaac/ppo_daac_idaac/storage.py:206`
  is a per-env step *counter*; `ppg/phasic_policy_gradient/ppo.py:33` unpacks it as *rollout length*
  from `reward.shape`; `ibac_sni/coinrun/coinrun/train_agent.py:45` passes `Config.NUM_STEPS` into
  baselines-PPO, also a rollout length. **Asking whether these should be "1-step or 3-step" is a
  category error** — it is [`COMPARABILITY_CONTRACT.md`](COMPARABILITY_CONTRACT.md)'s same-name
  different-quantity hazard, sitting inside our own open-items list rather than in a metric.

The 1-vs-3 framing was right for the retired `rlgen/` port, where `nstep` was a **shared trainer
key** (`configs/vigen.yaml:32`) and one value had to serve twelve baselines. That is the shared-base
problem the project abandoned. The clone has no shared trainer, so there is no shared knob.

**The pattern, which is the reusable part and the second instance found today.** [C64](#c64) is the
same shape in a different file: a statement true of the retired port, kept alive past its referent,
because **the architecture changed underneath the documents and nothing ties a claim to a code
path.** An open item is not evidence that a question is hard. An item that survives repeated triage
without moving should be suspected of having lost its subject, and the cheap test is to ask which
file the decision would edit — here, `configs/vigen.yaml`, which no run reads.

**Decision** re-read a long-lived open item against the *current* architecture before triaging it
again, and close it as ill-posed rather than carrying it, when its subject has moved.
**Effect** §5 item 4 is closed after three re-triages; the five baselines that have the knob already
run the value the null prescribes, and the seven that do not are no longer counted as owing a
decision. No code changed, because none needed to — which is the result, and is the kind that
[`SYSTEM.md`](SYSTEM.md) records as routinely lost. Committed as `87d8eabb`.

### C67 — Two grids are the same checkpoint, so the project accidentally measured its own evaluation noise {#c67}
**Class** OURS · **Status** RESOLVED · **Cross-ref** [C63](#c63), [C65](#c65), [C41](#c41), [C54](#c54)

Found 2026-08-24 while re-deriving results for a reviewer pack, then verified here.

**`snapshot.pt` and `snapshot_100k_frames.pt` are byte-identical** — md5
`ec21f9a30da07ca94d0511cc85be5baf` for both; `snapshot_50k_frames.pt` differs
(`b9cbe4269bcd6d13e4887d0126385737`). The archived run wrote its final snapshot and its 100k
snapshot at the same step, under two names. Nothing in either grid's metadata records this: `seed`,
`control_seed`, `episodes`, `mode`, `trained_step` and `action_repeat` all match, so **the recorded
metadata cannot distinguish a replicate from a fresh measurement**, which is why four separate
sessions used these as two independent data points.

**So the project holds a free replicate: the same weights, the same protocol, evaluated twice.**
That is a measurement nobody designed and nobody had — a bound on how much a number here moves when
*nothing* changes.

| | replicate A | replicate B | apart |
|---|---|---|---|
| `train` pooled mean | 51.94 | 52.16 | **0.4%** |
| `train` successes | **19/200** | **28/200** | **47%** |
| `eval-easy` pooled mean | 144.72 | 131.05 | **9.4%** |
| `eval-easy` successes | 62/200 | 63/200 | 1.6% |
| worst single scene, `train` | #4: 9 succ | #4: 16 succ | **1.8×** |
| worst single scene, `eval-easy` | #6: 84.61 | #6: 42.75 | **2.0×** |

**The headline is that the noise is wildly uneven across statistics, and in opposite directions in
the two regimes.** In `train` the pooled mean is reproducible to 0.4% while the success count moves
47%. In `eval-easy` it inverts: successes agree to 1.6% while the mean moves 9.4%. **A single
per-scene number can be off by a factor of two.** Any claim in this project that rests on a per-scene
value, or on a `train`-regime success count, is resting on something that moves this much when
nothing changes.

**What this does *not* undermine, checked rather than assumed.** The two entries most exposed to it
were re-run against both replicates:

- **[C63](#c63) survives with room to spare.** Its distance↔return correlation reads
  `train −0.353 / eval-easy −0.541` on replicate A and `−0.374 / −0.562` on replicate B — **stable
  to 0.02**, while the 50k→100k collapse it reports is ≈**0.50**. The effect is ~25× the noise on
  that statistic. Notably the *correlation* is far more reproducible than the per-scene means
  feeding it, because it depends on the ordering across scenes rather than their levels.
- **[C65](#c65) survives.** The two replicates give all-scene ratios 2.786 and 2.513 — ~10% apart,
  both far above 1, both alarming. But its evidence is **two distinct checkpoints, not three**; see
  the correction recorded in that entry.

**What it does undermine.** Any comparison finer than these bars, and the project has been making
some. [C41](#c41) puts run-to-run (seed) variation near 49% at 40k frames; this entry says the
*evaluation* of a fixed policy already moves a `train` success count by 47%. **The two are the same
order of magnitude, which means seed variation and evaluation noise have not been separated in
anything measured so far** — a difference attributed to seeds could be either.

**Why they are identical — resolved the same day, and the first hypothesis was wrong.** I first
guessed that saving had stopped at or near the run's NaN collapse (frame 115500, `episode_reward`
483.47 → 0.69). **That is not it**, and the timeline refutes it: the collapse is logged at 14:27:13,
while `snapshot.pt` was last written at 13:59:43 and the run's own eval at frame 110000 ran at
~14:11 — between the two — without writing anything.

The actual mechanism is [C68](#c68): on the robosuite path a snapshot is written **only** at
multiples of 50,000 steps, and there is **no end-of-run save at all**. So `snapshot.pt` holds the
100k tick, and `snapshot_100k_frames.pt` is a copy of it taken 92 seconds later (mtimes 13:59:43 and
14:01:15; the numbered names are ours, since upstream writes one fixed filename). They are identical
because they are literally the same write.

Recorded because the wrong hypothesis was the more alarming one and would have been easy to leave
standing: it was plausible, it fit the collapse, and checking it cost one `ast` walk plus three
mtimes.

> **CORRECTED 2026-08-25 by [C69](#c69) — the reading below is wrong in its central claim.** The
> 47% spread is **not** an evaluation-noise floor and not irreducible: our evaluator never seeded
> the global numpy RNG that `UniformRandomSampler` draws from, so the door physically moved ~1.6 cm
> between the two "replicates". It is a one-line defect, now fixed and mutation-verified. Read this
> entry as *"two grids of one checkpoint, measured under an uncontrolled placement variable"* — the
> byte-identity finding and the metadata gap stand; the noise-floor interpretation does not.
> In particular the claim that seed variation and evaluation noise "have not been separated" is
> superseded: what was unseparated was our own bug.

**Decision** stop counting these two grids as independent evidence, and record the checkpoint hash
so a replicate is visible in metadata. *(The original decision — "treat the replicate as the
project's measured evaluation-noise floor" — is withdrawn per C69.)*
**Effect** three consequences, none requiring a new run: the archived-checkpoint evidence is n=2 not
n=3; C63 and C65 are confirmed against noise rather than assumed robust; and the project now has a
number for "how small a difference is worth arguing about," which it did not have. **The cheap
follow-up it makes obvious**: `eval_across_scenes.py` should record a content hash of the checkpoint
it evaluates, so a replicate is visible in the metadata instead of being discovered by md5 four
sessions later. Committed as `a7f7f6fe`.

### C68 — `snapshot.pt` is never the final policy on the robosuite path, and nothing says so {#c68}
**Class** INHERITED · **Status** OPEN · **Cross-ref** [C67](#c67), [C57](#c57), [C60](#c60)

Found 2026-08-24 while resolving [C67](#c67). `RL-ViGen-upstream/train.py` has **two** snapshot-save
call sites, and only one of them is on the path robosuite runs take:

| line | inside | fires |
|---|---|---|
| `train.py:268-269` | **`habi_eval()`** (lines 240–269) | after every eval — **habitat only** |
| `train.py:309-310` | `train()` | `global_step % int(5e4) == 0`, at an episode boundary |

The robosuite path calls `self.eval()` (defined at `train.py:143`, invoked at `train.py:321`), which
**writes no snapshot**. So on every robosuite run in this project:

- **A snapshot exists only at exact multiples of 50,000 steps.**
- **There is no end-of-run save.** Whatever the policy is when training stops is simply discarded
  unless the budget happens to be a multiple of 50k.
- `save_snapshot()` (`train.py:342-346`) always writes the one fixed name `snapshot.pt`, so every
  tick overwrites the last. The `snapshot_50k_frames.pt` / `snapshot_100k_frames.pt` names in our
  archive are **ours**, copied afterwards; upstream never produces them.

**This is not hypothetical, and it explains artifacts already in use.** The archived 2026-08-18 run
had `num_train_frames=120000` and ran to 119500. Its `snapshot.pt` reports `_global_step=100000` —
**19,500 frames of training are absent from the only surviving artifact**, including the NaN
collapse at 115500. And the four 50k cells were all launched with `num_train_frames=55000`; every
one of their checkpoints reports `trained_step=50000`, which is why `cell55k` names a budget its
file does not contain. That discrepancy had been noticed and treated as a naming quirk; it is this.

**Why it matters beyond bookkeeping.** "The final checkpoint" is what a reader assumes `snapshot.pt`
is, and it is what a results table means by "the trained policy." Here it is *the last 50k tick*,
which for an arbitrary budget can be up to 49,999 steps stale. Combined with [C57](#c57) ("training
ran" ≠ "a policy exists"), the project has now found two distinct ways for a run to complete while
the artifact it leaves behind is not the thing anyone thinks it is.

**Options**.

1. **Leave upstream alone; make the staleness visible.** Record `_global_step` next to
   `num_train_frames` wherever a checkpoint is reported, and choose budgets that are multiples of
   50k so the last tick *is* the end. Zero divergence from the null, costs only discipline, and the
   grids already carry `trained_step` — nothing new to build. Does not help a run that diverges
   between ticks.
2. **Patch an end-of-run save onto the robosuite path.** One line, and it makes `snapshot.pt` mean
   what everyone reads it as. But it is a deliberate divergence from upstream in the file all five
   native baselines share, so it needs a P-number, a §4 block, and it changes what "the original,
   running its own `train.py`" means — the null's whole point.
3. **Lower the save cadence** (e.g. every 10k). Cheapest to reason about, worst on disk: each
   snapshot is ~46 MB here, and [C60](#c60) already records checkpointing as a constraint.

**Recommendation** option 1, plus stating the budget rule explicitly in the runbook: **on the
robosuite path, a training budget that is not a multiple of 50,000 silently discards its tail.**
That is a fact about upstream worth knowing regardless of which option is taken.

**Falsifier, run 2026-08-24 — it does not fire.** If some patch of ours already added a save the
audit missed, `snapshot.pt` would be current and this entry wrong about live runs. Checked: the
whole upstream tree contains exactly **five** `save_snapshot()` call sites, and only two are in
`train.py` — line 269 (`habi_eval`, habitat) and line 310 (`train`, the 50k cadence). The other
three are in `carlatrain.py` and `locotrain.py`, which are the CARLA and locomotion entry points and
are not on this path. The `5e4` literal appears exactly once and is unpatched, and no file under
`runnable/_launch/` or `scripts/` touches snapshot saving. The entry stands.

### C69 — Our evaluator never seeded the RNG that places the door, so every grid's "seed" was partly fiction {#c69}
**Class** OURS · **Status** RESOLVED · **Cross-ref** [C67](#c67), [C65](#c65), [C63](#c63), [C41](#c41), [C55](#c55)

**Surfaced 2026-08-25 by an external reviewer** reading only the public upstream repository, who
noticed that `UniformRandomSampler` holds no seeded RNG and flagged it as a candidate mechanism for
[C67](#c67)'s replicate. Verified here, then extended: the reviewer could not see our evaluator, and
our evaluator is where the defect actually lives.

**The mechanism, confirmed in source.**
`RL-ViGen-upstream/third_party/robosuite/robosuite/utils/placement_samplers.py` draws at lines
**167, 183, 196, 198** — all four are bare `np.random.uniform`. The class stores no `random_state`,
accepts no rng, and there is no seeded alternative anywhere in the file. This is the sampler that
decides where the door and its handle sit on every reset (`door.py`: `x_range=[0.07, 0.09]`,
`y_range=[-0.01, 0.01]`, plus a rotation range).

**The `seed` we thread through `robo_make` does not reach it.** That seed reaches `VGBWrapper`'s
`self.random_state = np.random.RandomState(seed)`, which drives **texture, colour and lighting**
modding — a different RNG object entirely. `scripts/eval_across_scenes.py`'s other seed,
`np.random.default_rng(seed)`, is a third, used only for the random policy's actions. Global
`np.random` was seeded by **nothing**.

**Measured, not argued.** Three processes, identical `seed=0`, `scene_id=0`, `mode=train`:

| process | door body `xpos` |
|---|---|
| 1 | `[-0.128117, -0.344142, 1.1]` |
| 2 | `[-0.112590, -0.345179, 1.1]` |
| 3 | `[-0.120571, -0.351566, 1.1]` |

**~1.6 cm of spread in x** — the sampler's entire declared range. With `np.random.seed(0)` first,
all three read `[-0.116047, -0.358795, 1.1]`, identically. End-to-end through `run_scene`, two
processes gave random-policy returns `[2.265003, 0.748782]` and `[1.650736, 0.712101]` before the
fix and bit-identical `[2.210974, 0.706753]` after; mutation-verified by removing the line again.

On a task whose reaching term is `0.25 * (1 - tanh(10 * dist))` and whose success is
`hinge_qpos > 0.3`, a 1.6 cm shift in where the handle sits relative to the gripper is not a
rounding difference.

**It was not only the door — a breadth sweep of the vendored robosuite found a second, arguably
larger uncontrolled variable.** `robots/robot.py:131-135` perturbs the robot's **initial joint
positions** on every reset, and Door takes `initialization_noise="default"`
(`environments/manipulation/door.py:138`), which `robot.py:67` resolves to
`{"magnitude": 0.02, "type": "gaussian"}` — i.e. **σ = 0.02 rad of Gaussian noise on each starting
joint angle**, drawn from `np.random.randn`, global, unseeded. So before the fix the arm *also*
started somewhere slightly different every process. Verified: after seeding, two processes report
identical `qpos[:4] = [-0.004843, 0.226637, -0.006661, -2.617047]`.

`utils/observables.py:79,101` holds the same pattern for observation corrupters; those are inert
here because Door configures none, but they would be silently uncontrolled if one were ever enabled.

**The one-line fix covers all of these**, since they share the global stream — which is the reason
to state the fix as "seed the global RNG" rather than "seed the placement sampler." Enumerating
consumers was worth doing anyway: the sweep is what turned "we found the bug" into "we know what the
seed now controls", and this project's own practice is that a keyword search finds what you already
expect to exist ([`STEP-ZERO.md`](STEP-ZERO.md) §8).

**Upstream is not at fault here; we are.** `train.py:47` and `eval.py:54` both call
`utils.set_seed_everywhere(cfg.seed)`, which seeds global numpy at `utils.py:38`. Training runs were
therefore always seeded. `scripts/eval_across_scenes.py` is **our own code**, written for the offline
grids, and it simply never did — so the defect is confined to the offline evaluation path, which is
also where every retention number this project reports comes from.

**What this overturns — [C67](#c67)'s central reading is wrong.** That entry treats the
19/200-vs-28/200 replicate as *"the project's measured evaluation-noise floor"* and concludes that
seed variation and evaluation noise *"have not been separated."* Both statements now have a
different meaning: the 47% was not a floor and not irreducible stochasticity, it was **our
unseeded object placement**, and it is fixed by one line. A floor is something you plan around; a
bug is something you remove. C67 planned around a bug.

**What survives, checked rather than assumed.**
- **[C63](#c63) is strengthened.** Its correlation read −0.353 and −0.374 on the two replicates —
  stable to 0.02 *while the door was physically moving between them*. A statistic that survives an
  uncontrolled 1.6 cm perturbation is more robust than one measured under control, not less.
- **[C65](#c65) survives on margin.** Contaminated grids read 1.887–2.786, clean ones 0.030–0.877;
  the gap is far larger than the placement effect, and the random-policy control at 1.02 was
  measured under the same defect. It should be re-derived after a reseeded re-run, but its
  conclusion is not in doubt.
- **The success counts and returns remain real measurements** of real episodes. What was wrong is
  the claim that a recorded `seed` made them reproducible.
- **[C41](#c41)'s ~49% run-to-run figure is untouched** — it comes from training runs, which were
  seeded.

**A second consequence, demonstrated 2026-08-25 and not previously suspected: the evaluation
schedule perturbs the training trajectory.** Training *is* seeded — `set_seed_everywhere` at
`train.py:47` runs before `robo_make` at `:78`, so this entry's defect is confined to the offline
evaluator. But seeding global numpy once at startup means **every subsequent `reset()` draws from
one shared stream, and evaluation resets consume from the same stream as training resets.**
Measured directly:

| | door `xpos` on the 2nd training reset |
|---|---|
| no eval env built in between | `[-0.128717, -0.346151, 1.1]` |
| one eval env built and reset in between | `[-0.118183, -0.348513, 1.1]` |

So `seed` names a training run **only for a fixed evaluation schedule**. Change `eval_every_frames`,
the number of eval episodes, or the number of scenes swept, and the training run itself collects
different data at the same seed — not through any interaction with learning, but because the
placement sampler is further along a shared RNG stream.

**This bears directly on P14.** That patch changed the eval loop from building one env to building
**ten**, one per scene ([C45](#c45)/[C43](#c43)). Every training run after it therefore sits on a
different placement stream from every run before it, at identical seeds. Comparing a pre-P14 run to
a post-P14 run at "the same seed" is not the controlled comparison it reads as. **Not measured**:
how large the resulting difference in outcomes is — the mechanism is confirmed, its magnitude is
not, and separating it from ordinary seed variance would need paired runs.

**Verified against re-derivation, 2026-08-25 — no conclusion moved, and one number moved a lot.**
Five checkpoints re-run deterministically (both regimes, `results/regime-retention-c69/`) and
compared against their pre-C69 counterparts:

| grid | pooled, old → new | successes, old → new |
|---|---|---|
| `cell55k` train (the one cell yielding retention) | 115.31 → 121.36 | 59/200 → **61/200** |
| `cell_drq_s1` train | 79.29 → 80.92 | 0/200 → **0/200** |
| `cell_drqv2_s7` train | 85.01 → 89.88 | 0/200 → **0/200** |
| **`cell_svea_s1` train** | 97.50 → 93.40 | **6/200 → 12/200** |
| `snapshot_100k_frames` eval-easy | 131.05 → 131.26 | 63/200 → 64/200 |

**What holds.** The consolidated finding — three of four cells reach a shaping plateau without
opening the door, only `drqv2` seed 6 yields a retention number — is unchanged. [C65](#c65)'s screen
still separates without overlap: fresh cells **0.035–0.868**, the archived checkpoint **2.345**.
Pooled means move by −5% to +23%, and the largest of those (`cell55k` eval-easy, 3.49 → 4.29) is
0.8 in absolute terms on a number sitting near the 1.85 floor.

**What moved: `svea`'s training success count doubled, 6/200 → 12/200.** Both are correct
measurements of different object-placement draws; neither is noise around the other. It stays below
`MIN_DENOM_SUCCESS` (50/200) and is still refused, so no reported number changes — but **`svea` is
the baseline whose 1/20-per-scene plateau nearly produced a 0.947 retention headline**
([C55](#c55)), and a 2× swing in exactly that count is a reminder of how thin the margin was.

**So the honest bound on the pre-C69 archive**: trustworthy for the *readings* drawn from it, not
for any individual per-cell count, which can differ by a factor of two from a deterministic
re-derivation of the same checkpoint. That is a statement about placement variation, not about
which archive is right.

**Every grid measured before 2026-08-25 carries this**, including all eight in
`results/regime-retention/`. They are not discarded: they measure what they measure. But no two of
them are a controlled comparison in object placement, and any of them can be re-derived
deterministically now.

*Where to seed is a branch point; its §4 block lives in [`INTEGRATION-DELTA.md`](INTEGRATION-DELTA.md) (P-C69), because a decision that changes code belongs with the authored element — `scripts/decisions.py` enumerates only that home and `RESEARCH-FRAME.md`.*

**Decision** seed global numpy per scene inside `run_scene`, from the same base seed, so each scene
sees an identical placement sequence and scene identity is the only thing varying — which is what
the script's docstring already claimed it did. **Effect** the offline evaluator is reproducible
process-to-process for the first time; C67 is corrected from a noise floor to a defect; and the
project's single largest "unexplained variance" result turns out to have had a one-line cause.
**The general lesson is the one this register keeps re-learning**: a `seed` field is evidence that
*someone* was seeded, not that *everything* was. Three RNGs were in play here and the recorded seed
named the least important of them. Fix committed as `b743917f`'s successor; see
`scripts/eval_across_scenes.py::run_scene`.

### C70 — Seeding was necessary and not sufficient: torch's kernel choice flips episodes {#c70}
**Class** OURS · **Status** RESOLVED · **Cross-ref** [C69](#c69), [C67](#c67), [C62](#c62), [C41](#c41)

Found 2026-08-25 immediately after [C69](#c69), by re-running a reseeded grid **twice** instead of
declaring the fix good. It was not good: the two runs disagreed.

**The evidence is unusually clean, because the disagreement is localised.** Scene 1, 20 episodes,
same checkpoint, same seed, two processes:

| episodes | agreement |
|---|---|
| 0–11 | **bit-identical** |
| **12, 13, 14** | **differ** — episode 14 reads **372.34** in one run and **6.01** in the other |
| 15–19 | **bit-identical again** |

**The re-convergence is what identifies the cause.** A desynchronised RNG would corrupt everything
after the first divergence; instead the runs come back together at episode 15. So *episode initial
conditions are deterministic* — C69's fix works — and the divergence happens **inside** three
episodes and does not survive a reset.

**What it is not**, each checked rather than assumed:

- **Not the RNG.** Placements are seeded per scene, and episodes 15–19 prove the stream is intact.
- **Not thread scheduling.** `torch.set_num_threads(1)` still diverges — measured.
- **Not rendering.** Frame md5s over 30 steps are identical **across processes**, and identical
  within one. The observation stream is bit-reproducible.
- **Not the environment.** With a random policy, 20 episodes reproduce exactly across processes.

**What it is: torch selects CPU kernels at runtime, and some are nondeterministic.** The actor's
output differs by around 1e-7 between processes — normally invisible. **Door makes it visible**,
because success is a threshold (`hinge_qpos > 0.3`, [C62](#c62)): a hair's difference in one action
early in an episode decides whether the gripper catches the handle, and the episode then ends at
372 instead of 6. The task converts floating-point noise into a **binary** outcome.

**Fix:** `torch.use_deterministic_algorithms(True)` in `run_scene`. Three processes then agree
bit-for-bit on the case that exposed the defect, sum `792.625412` each.

> **Corrected 2026-08-25, against my own claim: the fix reduces the nondeterminism by orders of
> magnitude but does NOT eliminate it.** "Three processes agree bit-for-bit" was true of the scene
> tested and is not universal. Measured across the full 14-grid re-derivation, where `snapshot.pt`
> and `snapshot_100k_frames.pt` are byte-identical files ([C67](#c67)) evaluated as separate runs:
>
> | | result |
> |---|---|
> | `eval-easy`, all ten scenes | **bit-identical** |
> | `train`, nine of ten scenes | **bit-identical** |
> | `train`, scene 1 | differs, `max abs` **19.2**, success counts identical (0 vs 0) |
>
> Re-running that scene three times gives `318.016607`, `318.625115`, `318.625115` — so it is
> genuinely nondeterministic, not a stale artifact, and it is **intermittent** rather than constant.
>
> **What changed is the magnitude and the consequence, which is what mattered.** Before the fix, a
> divergence flipped an episode from **372.34 to 6.01** and moved a success count. After it, the
> residue is **~0.2% of the scene's total** and leaves success counts untouched. The defect went
> from outcome-changing to below the resolution of anything this project reports.
>
> **Not chased further, deliberately.** The remaining source is unidentified — plausibly MuJoCo
> solver ordering or an op outside the deterministic-algorithms guarantee — and locating it would
> cost more than it can change, since no reported quantity moves. Recorded as a **measured bound**
> rather than left as an implied "solved": 19 of 20 scene-grids reproduce exactly, and the twentieth
> agrees on every number this project reads.

**Why this is a separate entry from [C69](#c69) rather than a footnote to it.** C69's lesson was
"seed everything that varies". This one is the sharper half: **seeding everything that varies was
still not enough**, and the remaining gap was invisible at the scale anyone would naturally test.
The determinism screen written the same hour to close C69 ran **two** episodes and **passed against
this defect** — six now, with the limit stated in the file, because the honest statement is that the
cheap screen covers the environment path and the expensive guarantee needs the torch flag.

**The general form, and it is the more useful takeaway.** On a task whose outcome is a threshold,
*there is no such thing as a negligible numerical difference*. Every argument of the shape "1e-7
cannot matter" is invalid here by construction. That applies beyond this defect — to device choice
([C41](#c41) measures the MPS path diverging from itself), to library upgrades, and to any claim
that two runs are "the same up to numerical noise".

*§4 block in [`INTEGRATION-DELTA.md`](INTEGRATION-DELTA.md) (P-C70), same routing as C69.*

**Decision** set `torch.use_deterministic_algorithms(True)` alongside the seeding in `run_scene`,
and treat the pair as one precondition rather than two options. **Effect** the offline evaluator is
now bit-reproducible across processes — verified three times — which it had never been; and the
project has a measured statement of what "numerical noise" is worth on this task, which is: an
entire episode. Committed as `8cf224cc`'s successor.

### C71 — Dead knobs: four places where a configured value never reaches the code {#c71}
**Class** DESIGN-GAP · **Status** OPEN · **Cross-ref** [C64](#c64), [C66](#c66), [C53](#c53)

Collected 2026-08-25, after the third instance turned up independently and it stopped being
coincidence. Each is a value that is **written, passed, and never read** on the robosuite path:

| # | The knob | Where it is set | Why it is dead |
|---|---|---|---|
| 1 | `--action_repeat 1` for `rad`, `soda` | `_launch/dmc_gb.sh:49` | `runnable/dmc_gb/src/env/wrappers.py`'s robosuite branch returns at `FrameStack`, before the `dmc2gym.make(..., frame_skip=action_repeat)` that is the file's only consumer |
| 2 | `action_repeat: 1` for `alda` | `runnable/alda/specs/train_alda_robosuite_door.yaml:19` | `trainers/alda_trainer.py`'s robosuite branch returns at line ~152; `env_config['action_repeat']` is read only at line 159, in the `dmc2gym.make` call that branch never reaches |
| 3 | `aux_lr: 8.0e-5`, `sgqn_quantile: 0.9` | `configs/vigen.yaml:82` | configures the **retired `rlgen/` port**; no clone run reads that file ([C64](#c64)) |
| 4 | `DEFAULT_ACTION_REPEAT = 1` | `rlgen/protocol.py:140` | declared as the protocol's value, but **the runners never consult `Protocol`** — it hashes a number nothing checks against |

**Why this is worse than a missing knob, which is the point.** An absent mechanism announces itself:
grep for `action_repeat` in `idaac`, `ctrl`, `ibac_sni` or `ppg` and you get nothing, and you know
where you stand. A **dead** knob reads as configured. It invites someone to tune it, observe no
effect, and conclude the parameter does not matter — when what does not matter is the file they
edited. Instance 3 nearly caused exactly that: the 2026-08-10 SGQN fix is real, correct, and
reaches nothing.

**Two of the four also corrupted our own bookkeeping**, which is how they were found.
[`INTEGRATION-DELTA.md`](INTEGRATION-DELTA.md):489 credited `dmc_gb.sh` with a decision it does not
make, so the audit's headline read "seven of twelve agree by anyone's decision" when the true figure
is **five**. `FAITHFULNESS.md`'s SGQN column reported `aux_lr` 0.3 for the same reason.

**And it changes the honest phrasing of the action-repeat result.** Not *"all twelve agree at 1"*,
but: **one value is enforced for five baselines by our launcher, and holds for the other seven only
because nothing on their robosuite paths can express any other value.** Those are different facts,
and only the first survives someone editing a config. The seven are not at 1 by preference — their
lineages default to **4** (`dmc_gb/src/arguments.py:12`, and alda's vendored copy of it) or **2**
(RL-ViGen's configs), so a working mechanism would put them somewhere else entirely.

**Options**.

1. **Build a dead-knob checker and run it across the twelve.** For each declared configuration key,
   establish whether any statement reachable from the robosuite entry point reads it. Catches the
   class rather than the instances, and this register now holds four instances found by hand and by
   accident — which is the usual sign that a mechanical check is overdue. Cost: real static
   analysis, and the honest risk is a checker that reports green because its reachability
   approximation is too coarse — the vacuity failure this project has hit repeatedly.
2. **Delete or neutralise the four known dead knobs**, so nothing reads as configured that is not.
   Cheap and safe, and it leaves the class unaddressed: instance 5 arrives with the next baseline.
3. **Annotate rather than delete** — mark each dead knob in place with what does not read it.
   Preserves the provenance (instance 3 records a real decision, and deleting it would erase the
   history of the SGQN fix) at the cost of leaving live-looking values on disk.

**Recommendation** option 3 for the four known cases now, and option 1 only if a fifth appears —
the class is worth a checker when it has demonstrated recurrence *after* being written down, not
before. **Not option 2**: instance 3's value is the record of a decision, and instance 4 is the
protocol's declared intent, which should be wired up rather than removed.

> **Both taken, 2026-08-25.** Option 3 is done — all four known knobs carry an in-place annotation
> naming what does not read them. Option 1 is done too, because the falsifier fired and made it
> defensible: `scripts/audit_dead_knobs.py`, pinned by `tests/test_dead_knob_audit.py`, two mutants
> killed (removing the `_returns()` guard, and removing the config-key idiom — the second is the
> regression that made its own first version report `alda` clean).
>
> **It covers the shape, not the class, and says so.** It finds instances 1, 2 and 5 — an
> early-returning domain branch dropping a parameter or a config key — and **cannot see** 3 or 4,
> which are an orphaned file and an unconsulted constant. That gap is stated in the script's
> docstring rather than left for a reader to discover, because a dead-knob audit reporting clean is
> precisely the false reassurance this entry exists to prevent.
>
> **It also found a sixth, and the honest verdict on it is "probably by design".**
> `intensity` in `dmc_gb/src/env/wrappers.py` is dropped by the same branch. It feeds
> `distracting_cs_intensity`, which belongs to the DistractingControlSuite benchmark and has no
> robosuite meaning — so this is very likely inert *by design* rather than by accident. Recorded
> anyway, because the script cannot tell those apart and neither can a reader who has not checked;
> "we looked and judged it benign" is a different state from "nobody looked."

**Falsifier, run the same day — and it FIRED. There is a fifth, so this is a class.**
The stated falsifier was: if an audit turns up no fifth dead knob, these are four historical
accidents and option 1 would be over-engineering. Rather than audit every key, I searched for the
*shape* that produced instances 1 and 2 — a `domain_name == 'robosuite'` branch returning early past
code that reads config keys — and asked what **else** those branches bypass.

**#5: `image_size` for `rad` and `soda` — and this one is the most instructive, because the dead
knob is *masked by a live one that happens to agree with it*.**

`runnable/dmc_gb/src/env/wrappers.py`'s `make_env` takes `image_size` and passes it to
`dmc2gym.make(height=image_size, width=image_size, ...)`. The robosuite branch returns before that
call, handing `_robo_make_env` only `task_name`/`seed`/`scene_id`/`mode`. So **`--image_size` does
not set the robosuite render resolution.** `arguments.py:92,95` sets it to 100 for `rad`/`soda` and
84 otherwise — a deliberate per-algorithm choice that reads as load-bearing and, on this path, is
not read at all.

**What actually sets it is a different mechanism entirely:** `_launch/dmc_gb.sh:27` exports
`RLVIGEN_IMAGE_SIZE=100`, which patch **P6** consumes at
`RL-ViGen-upstream/envs/robosuiteVGB/robosuitevgb/utils.py:46`, overriding `robo_config.yaml`'s
84×84. Two independent mechanisms, one live and one dead, **set the same number** — so the dead one
is invisible. Edit `arguments.py`'s 100 and nothing happens; edit the launcher's 100 and everything
does.

> **Correction, same day.** This entry first claimed the resolution "is 84 because `robo_config.yaml`
> says so", on the strength of a direct `make_env` call that returned `(9, 84, 84)`. That call
> **bypassed the launcher**, and therefore the env var that is the whole mechanism — measuring the
> unpatched condition and reporting it as the live one. It also led me to read
> [`RUNNABLE-ORIGINALS.md`](RUNNABLE-ORIGINALS.md):50 and :261 as contradicting each other; they do
> not. :261 describes P6 **off** (native 84 → RAD's `random_crop` degrades to identity by its own
> `crop_max <= 0` guard, so RAD is exactly SAC; SODA's `assert x.size(-1) == 100` refuses outright),
> and :50/:318 describe the launcher path with P6 **on**. Both are correct about different
> conditions, and the documents say which.
>
> **The methodological point is the one worth keeping**: reproducing a component outside its
> launcher reproduces a *different system*, and the difference here was a single exported variable
> that decides whether one of the twelve baselines is itself or is SAC.

**[C5](#c5) still needs a look, but a narrower one than first claimed.** It describes the
resolutions correctly (100→crop 84 for `rad`/`soda`) and attributes them to *"the repo's own rule at
`arguments.py`"*. That attribution is wrong — `arguments.py` is the dead knob; **P6 plus
`dmc_gb.sh:27` is what does it** — and the distinction matters because C5 is the entry a reader
consults before changing a resolution.

**Consequence for this entry's options.** The falsifier firing makes option 1 (build the checker)
the defensible choice rather than over-engineering: five instances, found one at a time by hand and
by accident, across four different files, three of which are shaped identically. The cheap first
version does not need general reachability analysis — it needs to enumerate **early-return
domain branches** and diff the parameters they consume against the parameters their function
accepts. That is the shape all three of #1, #2 and #5 share.

### C72 — The retention endpoint exists for five of twelve baselines, and nothing said so {#c72}
**Class** DESIGN-GAP · **Status** OPEN · **Cross-ref** [C60](#c60), [C57](#c57), [STAGES.md](STAGES.md)

Found 2026-08-25 while asking why nine of twelve baselines have no cell. The answer everyone
assumed was training — [C60](#c60) audits the checkpoint cadences and two baselines that never save
at all. **That is real and it is not the binding constraint.**

**The binding constraint is that the retention instrument can only read native checkpoints.**
`scripts/eval_across_scenes.py:342` does `agent = payload["agent"]` and drives it with
`agent.act(ts.observation, step, eval_mode=True)` under `utils.eval_mode(agent)` (`:203-204`) —
that is RL-ViGen's own agent interface, and only `drqv2`, `svea`, `sgqn`, `curl` and `drq` produce
it. `idaac`'s checkpoint is `{"learner", "ret_rms", "config", …}` (`docs/REVIEW.md`:210); the
others differ again.

**So even a perfect checkpoint from `idaac` could not be put through the grid.** Retention is this
project's endpoint — the measured floor, the denominator guards ([C55](#c55)), the contamination
screen ([C65](#c65)) all live in that one script and nowhere else. Every clone ships (or lacks) its
*own* evaluator — `dmc_gb/src/eval.py`, `alda/…/src/eval.py`, `ctrl/evaluate_ppo.py`,
`ibac_sni/torch_rl/scripts/evaluate.py`, and **`idaac` and `ppg` ship none** — but none of those
produces a ten-scene × two-regime grid against a measured floor.

**Why this was invisible.** Both halves are individually true and neither states the join: C60 says
"here is each baseline's checkpoint cadence", the evaluator says "here is how to grade a
checkpoint", and nothing anywhere says *the second only accepts the output of five of the twelve*.
Same shape [`SYSTEM.md`](SYSTEM.md) names as this project's signature, on the axis that decides
what the results table can contain.

**Options**.

1. **Seven more evaluators, one per baseline.** The hermetically correct answer, and what the
   founding rule prescribes: each reads its own checkpoint format and drives its own agent
   interface, no shared adapter. Each is then an authored element owing an
   [`INTEGRATION-DELTA`](INTEGRATION-DELTA.md) row and its own correctness argument. Honest, and
   **never costed** — seven times the work that produced the current one, which took a week and
   three defects ([C55](#c55), [C69](#c69), [C70](#c70)) to get right for *one* interface.
2. **One evaluator with a per-baseline shim.** Cheap, and precisely the shared abstraction the
   project exists to refuse. The superseded `rlgen/` port was abandoned for this exact reason, and
   [C66](#c66) records what a shared trainer key did to `nstep`. It would also put the guards on a
   join whose correctness is not visible at the edit.
3. **Narrow the claim to what the instrument can measure.** Report retention for the five natives,
   and state plainly that the other seven have no comparable endpoint on this axis. Cheapest and
   most honest about the present, but it makes the deliverable smaller than the brief's **R6**
   (twelve genuine baselines) and should be surfaced as such rather than absorbed quietly.

**Recommendation** option 3 **now**, as a statement of what is true, with option 1 as the path if
the twelve-baseline table is required — and priced before it is started, not during. Option 2
should be refused even though it is the tempting one.

> **The contract changed under this entry, 2026-08-26, and it changes which option is legitimate.**
> [`TASK.md`](TASK.md) R3 previously demanded that the evaluation **code** be identical across all
> baselines. Under that wording, "seven more evaluators" (option 1) read as a *violation* of the
> load-bearing requirement, and the shared adapter (option 2) looked like the only compliant answer
> even though the founding rule refuses it. That is no longer so: R3 now asks for **metrics on the
> same axes and directly comparable**, so **option 1 is both hermetically correct and
> contract-compliant**, and option 2 loses the one argument it had.
>
> The cost estimate is unchanged and so is the deferral. What changed is that the expensive option
> is no longer also the non-compliant one — which is worth knowing before the decision is taken,
> because it was previously a choice between breaking a rule and breaking a contract.
>
> **Owner's disposition, updated 2026-08-26 — option 3 is the NULL, and adaptation is permitted
> under a high bar.** The 2026-08-25 blanket deferral below is superseded by this:
>
> - **The null is option 3**: report the five natives, state plainly that the other seven have no
>   comparable endpoint. That is what holds if nothing further is done, and it is not a failure
>   state — it is the honest description of what the instrument reaches.
> - **Working carefully toward an adaptation is permitted**, hermetic-first, one evaluator per
>   baseline. What is *not* permitted is arriving at same-axis by argument.
> - **The bar, in the owner's words:** be *"in a state where we can confidently declare same-axis
>   based on all circumstances that take effect, not only name some reasons why it'd be compatible
>   and call it a day."*
>
> **That bar is the whole content of the decision, and it is higher than it sounds.** Naming reasons
> two metrics *should* be comparable is what this project already does well and is precisely what it
> does not accept as evidence elsewhere — [`INTEGRATION-DELTA.md`](INTEGRATION-DELTA.md)'s
> INTRINSIC/NOT-INTRINSIC split exists to refuse "argued, therefore correct". Applied here it means
> an adaptation must enumerate the circumstances that bear on the axis — episode boundary, reward
> collection, action repeat, success definition, normalisation, what an episode counts as, what
> ends it — and show each one holds, per baseline, rather than assert that nothing obviously
> differs. [`COMPARABILITY_CONTRACT.md`](COMPARABILITY_CONTRACT.md) is where that evidence lands.
>
> **Practical consequence**: pricing option 1 is worthwhile, but the price is not "seven
> evaluators". It is "seven evaluators **plus** the per-baseline comparability evidence for each",
> and the second half is the larger one. Any estimate that omits it is the estimate this bar exists
> to reject.
>
> **Superseded — Owner's disposition, 2026-08-25: deliberately deferred. Do not act on this entry.**
> The decision is the owner's and is *not* being taken now. The stated reason is that integration
> is exactly the shared abstraction this project refuses, so the design belongs at a point when the
> surrounding facts are settled — not decided under pressure from a coverage gap. **Work continues
> from the hermetic-first paradigm**, which for this entry means: build no adapter, build no
> per-baseline evaluators, and do not narrow the claim in a write-up on this entry's authority
> alone.
>
> **The condition that would reopen it** is if working around it becomes unrealistic — i.e. if a
> deliverable actually requires a retention number for a non-native baseline. It does not today:
> three of the five natives have cells and two more are reachable on the existing instrument
> ([C60](#c60) puts `sgqn` at ~11h locally; `curl` needs CUDA).
>
> **What this changes for a reader**: `OPEN` here means *recorded and waiting*, not *unblocked and
> available*. A session that finds this entry and starts writing evaluators is acting against the
> owner's decision, not filling a gap.

**Falsifier, run 2026-08-25 — it does not fire, and the margin is wider than expected.** The stated
falsifier was: if two or three of the seven's evaluators already emit per-scene, per-regime returns,
option 1 is far cheaper than stated. Checked the three that exist:

| evaluator | scene axis | regime axis |
|---|---|---|
| `dmc_gb/src/eval.py` (`rad`, `soda`) | **no `scene_id` anywhere** | yes — takes `eval_mode` |
| `ctrl/evaluate_ppo.py` | **no `scene_id`** | hardcoded `mode='easy'` |
| `ibac_sni/torch_rl/scripts/evaluate.py` | **no `scene_id`** | neither |

**Not one of them sweeps the scene axis.** `idaac` and `ppg` ship no evaluator at all, so the count
of existing evaluators that could feed the retention report is **zero of seven**, not two or three.
The `dmc_gb` one is the closest — it already has the regime argument — but the ten-scene sweep, the
floor, and the guards would all still be new.

So option 1's cost stands as written and the recommendation is unchanged. Worth noting *why* the
gap is this wide: the scene axis is **RL-ViGen's**, not the baselines'. Each of the seven came from
a benchmark with a different generalisation axis (DMC-GB's visual modes, Procgen's levels), so none
of their evaluators has a reason to know what a `scene_id` is. That is a fact about the
comparison's shape, not about their code quality.

### C73 — 50k sits on a threshold: the same run improves 28× by 100k, and more seeds at 50k would measure a lottery {#c73}
**Class** OURS · **Status** RESOLVED · **Cross-ref** [C57](#c57), [C60](#c60), [C41](#c41), [C68](#c68), [STAGES.md](STAGES.md)

The consolidated cell result — *"three of four runs reach a shaping plateau without opening the
door"* — invites one obvious next step: **more seeds**, to turn one success into a rate. That step
would have been wrong, and the data to see why was already on disk.

**The archived run has checkpoints at 50k *and* 100k. Same run, same seed, same contamination —
only the budget differs:**

| | 50k | 100k | |
|---|---|---|---|
| `train` pooled / successes | 24.75 / **1**/200 | 52.16 / **28**/200 | **28×** |
| `eval-easy` pooled / successes | 46.71 / 4/200 | 131.05 / **63**/200 | **16×** |
| scenes solved ≥ 10/20 | **none, in either regime** | 1 (`train`), 3 (`eval-easy`) | — |

At 50k this policy solves essentially nothing. By 100k it solves three scenes outright. **The
transition happens inside that interval**, and 50k is on the wrong side of it.

**Read together with the spread across runs, the picture is a threshold, not a lottery of skill.**
Four runs at 50k produced train success counts of **0, 0, 6 and 59 out of 200** — a range that
looks like extreme seed variance and is better explained as four samples taken *at* a threshold,
where small differences in learning progress decide whether anything has been learned yet. The one
run measured on both sides of it moves 28×.

**Consequence for the remaining plan, which is the point of the entry.** More seeds at 50k would
measure *how often a run crosses a threshold by 50k* — a property of the budget, presented as a
property of the method. **Cells should be run at 100k.** [C68](#c68) makes 100k the next legal
budget anyway (a multiple of 50 000; anything between saves at 50k and discards the tail), so the
choice is 50k or 100k with nothing in between, and 50k is demonstrably too early.

**Cost.** Roughly 2× the training time per cell — ~2.2h rather than ~1.1h locally at these budgets.
That is the price of a cell that is likely to yield a number rather than a plateau, against four
cells at 50k that yielded one number between them.

**Honest limits, and they are real.**
- **n = 1 for the paired comparison.** Only the archived run has checkpoints at both budgets.
- **That run is [C54](#c54)'s contaminated one.** The contamination concerns *which distribution it
  trained on*, not its learning dynamics, so the within-run budget comparison should survive — but
  it is measured inside a defect and should not be quoted as clean.
- **The threshold is not located.** 50k is below it and 100k is above it for this run; nothing here
  says where between, or whether it sits in the same place for `svea` or `drq`.

**Decision** run future cells at **100k**, not 50k, and stop treating the 50k spread as evidence
about seeds. **Effect** the "more seeds" step that the four-cell result seemed to demand is
withdrawn before it was taken, and the cheapest evidence for withdrawing it cost one comparison of
files already in `results/`. Committed as `ac945ce9`.

### C74 — Methods that need *distinguishable* instances, run on a target that is only partly distinguishable {#c74}
**Class** DESIGN-GAP · **Status** OPEN · **Cross-ref** [C50](#c50), [C49](#c49), [C51](#c51), [C61](#c61), [C6](#c6)

**Handicap — affects:** idaac ctrl curl ibac_sni soda svea
*a mechanism that requires telling instances apart, applied where instances are only partly distinct*

Surfaced 2026-08-25 by the owner, as a general shape the register held exactly one instance of.

[C50](#c50) records that **IDAAC's instance-invariance loss runs against a label with no referent
here**: `level_seed` is supposed to name a persistent, visually distinct instance, and
[C49](#c49) measured a classifier recovering `scene_id` at **1.000** and `level_seed` at chance
(**0.125**) in both regimes. It was filed as an IDAAC problem.

**It is not an IDAAC problem. It is a class, and IDAAC is the member that happened to be measured.**
Several of the twelve carry a mechanism whose *premise* is that two things can be told apart:

| baseline | what must be distinguishable | what this target supplies |
|---|---|---|
| `idaac` | persistent visual instances via `level_seed` | **measured absent** ([C49](#c49)) |
| `curl` | two augmented views of the *same* state, contrasted against *other* states in the batch | Door's states within one scene are visually near-identical; the contrastive negative may be nearly the positive |
| `ctrl` | clusters that separate | `ctrl_clusters` is 32 over a single fixed visual instance ([C51](#c51)) |
| `soda`, `svea` | an augmentation distribution wide enough to matter | overlay from Places365 against one fixed scene |
| `ibac_sni` | an information bottleneck with something to discard | one instance, so the nuisance variable may be near-constant |

**The general failure is not "the method is broken".** It is that a mechanism can be *inert* —
computing a loss term that is near-constant, or contrasting against negatives that are not
negative — while training runs, losses log, and nothing errors. [C50](#c50) calls this "the
mechanism works with a label that has no referent"; the same sentence fits every row above with a
different noun.

**Why this is a design gap and not a finding.** Only IDAAC's has been *measured*. The other rows are
reasoned from what the mechanism requires and what [C51](#c51) says the target provides (one fixed
visual instance in `train`, ten deterministic texture lookups across scenes — [C51](#c51)'s
`TASK_RANDOM_SEED` table). **None of them has been checked**, and the check is different for each:
a classifier probe for `idaac`, a positive-vs-negative similarity gap for `curl`, cluster
occupancy for `ctrl`, an augmentation-distance measure for `soda`/`svea`, a KL magnitude for
`ibac_sni`.

**Why it matters for the comparison rather than for the methods.** A method whose mechanism is inert
here is being compared as if it were the method. Its number is real; the label on it is not. That is
the same shape as [C61](#c61)'s entropy coefficient — a handicap recorded, not removed — which is
why this entry carries the handicap marker and appears in `python scripts/handicaps.py`.

**Options**.

1. **Probe each mechanism for inertness before reporting its baseline.** One measurement per
   baseline, each cheap relative to a cell, each answering "does this term vary at all here". The
   `idaac` probe already exists (`scripts/probe_level_seed_decodable.py`), so this is five more of
   a known shape. Gives the results table a column that says whether each method's distinguishing
   mechanism had anything to distinguish.
2. **Disclose the reasoning without measuring**, i.e. carry the table above as a stated risk. Cheap
   and honest, but it is exactly the "argued, not verified" tier
   [`INTEGRATION-DELTA.md`](INTEGRATION-DELTA.md) refuses for correctness claims.
3. **Change the target so instances are distinguishable** — bind parallel envs to distinct
   `scene_id`s, as [C50](#c50)'s option 2 proposes. This changes the training distribution for
   every affected baseline and is a design decision, not a fix.

**Recommendation** option 1 for any baseline whose number is going to be *reported*, and option 2
until then. Deliberately **not** option 3: it is a change to what is being measured, and belongs
with the owner alongside the evaluation-protocol decision.

**Falsifier.** If a probe on one of the reasoned rows — `curl` is the cheapest, since the
positive/negative similarity gap is one forward pass over a stored batch — shows the mechanism is
plainly *live*, then the class is narrower than this entry claims and may be IDAAC-specific after
all. Not run.

### C75 — The class this project keeps finding one member of: a formulation bound to a dimensionality, distribution or rate the target changes {#c75}
**Class** DESIGN-GAP · **Status** OPEN · **Cross-ref** [C2](#c2), [C3](#c3), [C5](#c5), [C6](#c6), [C61](#c61), [C74](#c74), [C50](#c50)

Named 2026-08-25 on the owner's observation. **Every instance below was already recorded, well, and
separately. What was never written down is that they are one thing** — and the class has predictive
value, which is the reason to name it rather than leave twelve good entries filed on twelve axes.

> **Narrowed 2026-08-26, on challenge, and the first version over-reached in two ways.**
>
> **First, it was written from the wrong prompt.** The owner's question was not "generalise this"
> — it was *"was the specific case of an algorithm needing samples from different trajectories
> properly worked through?"* The answer to **that** is **yes, thoroughly**: [C50](#c50) has the
> mechanism (`idaac/ppo_daac_idaac/storage.py:248-254` groups by `levels` to build the order
> classifier's pairs), the port's own recorded caveat that diversity is capped at `num_processes`,
> the precise failure (same- and different-instance pairs are *two samples from one distribution*),
> a §4 block in [`INTEGRATION-DELTA.md`](INTEGRATION-DELTA.md):255, and a direct measurement in
> [C49](#c49) — `scene_id` decodable at **1.000**, `level_seed` at **0.125, exactly chance**. The
> only lens that failed to hold it was [`FAITHFULNESS.md`](FAITHFULNESS.md), keyed by algorithm,
> which is now fixed and pinned. **Generalising was not the answer to the question asked.**
>
> **Second, the class as first written lumps two things whose checks differ in kind:**
>
> - **(a) a formulation bound to a concrete quantity** — an action-distribution family, an encoder's
>   input size, an entropy scale, a control rate. Members: [C6](#c6), [C61](#c61), [C3](#c3), and
>   the half of [C5](#c5) where RAD's `random_crop` degenerates to the identity at a native 84.
>   Checked by *reading the formulation against the target's quantity*.
> - **(b) a mechanism requiring a structural property of the data** — distinguishable instances,
>   diverse trajectories, meaningful negatives. Members: [C50](#c50), [C74](#c74). Checked by
>   *probing whether the property is present*, which is a measurement, not a reading.
>
> Those are different classes with different instruments, and [C74](#c74) already **is** (b). So
> this entry is narrowed to **(a)**, and (b) stays where it was.
>
> **Third, two members were weak and are withdrawn.** [C2](#c2) (frame stack 3 vs 1) and most of
> [C5](#c5) (three resolutions) are **comparability spread** — different baselines got different
> amounts of the same thing — not a formulation meeting a quantity it was not written for. Keeping
> them made the class look larger and the checklist vaguer.
>
> What survives is smaller and sharper, and the predictive claim survives with it: [C61](#c61) was
> found by tracing an entropy scale across a distribution change, which is exactly check (a).

**The shape.** A method is formulated against a concrete quantity — an action space's shape and
distribution family, an observation's resolution and channel count, a control rate, a notion of
"instance", a batch's notion of "other" — and the target supplies a *different* one. Nothing errors.
The mechanism runs. What changes is what it **means**, and the change is silent.

**The members already in this register, each found independently:**

| entry | the bound quantity | what the target supplies |
|---|---|---|
| [C6](#c6) | the action-distribution family the method assumes | three different families across twelve baselines; four had **no continuous head at all** and one was authored (`AUDIT-2026-08-17.md` §3) |
| [C61](#c61) | an entropy coefficient calibrated to a 15-way categorical (max entropy ln 15 = 2.708) | a 7-D Gaussian at σ=1, entropy 9.93 — the same coefficient now scales a term **3.67× larger** |
| [C2](#c2) | frame stack as the unit of temporal context | 3 frames for eight baselines, 1 for four |
| [C3](#c3) | an encoder sized for its source domain | the former 64×64 MiniGrid trunk made `ibac_sni` a **227×** model; production now uses the source-backed Impala repair |
| [C5](#c5) | render resolution and field of view | three different resolutions across the twelve |
| [C74](#c74) | a notion of *distinguishable instance* | measured absent for `idaac` ([C49](#c49)); reasoned for five others |
| [C50](#c50) | `level_seed` as a persistent visual identity | a label with no referent |

**And the root that half-named it.** [`PREMISES.md`](PREMISES.md) **P6** says *"None of these methods
was published on this benchmark… Published values do not transfer; they have to be **mapped**, and
mapping is a choice."* That is this class, seen through hyperparameters only. The class is wider:
`log_std = 0`, a frame stack, an encoder's input size and a contrastive batch's negatives are not
hyperparameters, and each is a mapping choice too.

**Why naming it earns its place: it is predictive, and both recent finds came from generalising an
instance.** [C61](#c61) was found by tracing an entropy coefficient across a distribution change.
[C74](#c74) was found by the owner generalising [C50](#c50) from one baseline to a class. So the
class says where to look, and the axes it names are a checklist that has not been run:

- **rate** — control frequency and `action_repeat`. Robosuite runs OSC_POSE at its own control
  rate; DMC-GB's lineage assumes 4, Procgen's assumes none. **Not examined as a formulation
  question**, only as an x-axis one ([`INTEGRATION-DELTA.md`](INTEGRATION-DELTA.md)'s audit).
- **episode structure** — every Door/Lift episode ends by time limit ([C1](#c1)); Procgen episodes
  genuinely terminate. Nine baselines treat a truncation as a terminal state *because their source
  domain had no truncations*. That is C1, and C1 has never been read as a member of this class.
- **reward scale and shape** — Door pays ≤0.5/step shaping plus a sparse 1.0 ([C62](#c62)); Procgen
  pays sparse; DMC pays dense in [0,1]. Value-function initialisation, reward normalisers and
  entropy trade-offs are all calibrated against a scale. **Unexamined.**
- **batch semantics** — what "another sample" means to a contrastive or clustering objective, when
  every sample comes from one visual instance. Partly [C74](#c74).

**Options**.

1. **Carry the class as a checklist and run it against each baseline before its number is
   reported.** Cheap per baseline, and it converts "we found instances when we happened to look"
   into "we looked along five named axes". The axes above are the checklist.
2. **Leave the instances filed individually** and rely on their cross-references. Zero cost, and it
   is the status quo that produced seven separate discoveries over three weeks, each of which had
   to be noticed rather than derived.
3. **Treat the class as a scope statement for the write-up**: state that twelve methods formulated
   for three different domains were run on a fourth, that mapping was required on at least five
   named axes, and that this bounds what a between-method comparison can mean.

**Recommendation** option 1 **and** option 3 — they answer different questions, one about what to
check and one about what may be claimed. Not option 2, and the reason is this entry's own evidence:
the instances were not derived, they were stumbled on, and two of the seven arrived in the last
week of a three-week project.

**Falsifier.** If running the checklist across the five named axes turns up **no** unrecorded
instance, then the class is a retrospective tidy-up rather than a predictive tool, and option 2 was
right. The cheapest test is the reward-scale axis, since [C62](#c62) already establishes the target's
scale and the source scales are in the papers' own configs.

**This entry does not decide anything.** It names a class and hands the owner a checklist; every
member listed remains open on its own terms.

### C76 — R3's evidence, re-derived on the architecture that runs: 4 of 8 axes uniform, and a near-miss that says more than the result {#c76}
**Class** OURS · **Status** MONITORED · **Cross-ref** [C1](#c1), [C2](#c2), [C5](#c5), [C30](#c30), [C71](#c71), [C72](#c72), [PART2-METRIC-INVENTORY.md](PART2-METRIC-INVENTORY.md), [TASK.md](TASK.md) R3

[R3 was relaxed](TASK.md) on 2026-08-26 to *"metrics fully on the same axes and directly
comparable"*, and named [`COMPARABILITY_CONTRACT.md`](COMPARABILITY_CONTRACT.md) as carrying the
burden — but §1–§10 of that file audit the **retired `rlgen/` port** ([C30](#c30)), whose argument
rests on one shared construction path and four adapters that the clone approach does not have. So
R3's evidence was, for nine days, a document about a system that no longer runs.

**`scripts/audit_comparability_seam.py` is the replacement**, with
`tests/test_comparability_seam_audit.py` (10 tests, every guard mutation-verified). It reports per
axis, per baseline, and — the part that matters — whether each fact is **DERIVED** now from code or
**RECORDED** from the document that derived it once.

| kind | axis | verdict |
|---|---|---|
| UNITS | reward pipeline | uniform in the **reported** value (raw, all twelve); the **learner's** reward is normalised for `idaac`/`ppg`/`ctrl` |
| UNITS | success definition | uniform (`_check_success`, any-step); split in *who computes it* — ours for the five natives ([C72](#c72)) |
| UNITS | episode horizon | uniform, 500 |
| UNITS | reported estimator | uniform — a fixed-policy sample mean everywhere, differing only in N, which is precision and not quantity |
| CONDITIONS | truncation | **SPLIT** 3 bootstrap / 9 terminal ([C1](#c1)) |
| CONDITIONS | render resolution | **SPLIT** 100 / 84 / 64 ([C5](#c5)) |
| CONDITIONS | frame-stack depth | **SPLIT** 8 stack 3 / 4 stack 1 ([C2](#c2)) |
| CONDITIONS | action repeat | uniform in value (1), reached four ways, two through a dead knob ([C71](#c71)) |
| CONDITIONS | induced action distribution | **SPLIT** 3 families — RECORDED, not re-derived |
| CONDITIONS | observation layout and pixel scaling | **SPLIT** 5 ways — the one axis here neither PART2 nor FAITHFULNESS covers |
| CONDITIONS | regimes reachable in one run | **SPLIT** — RECORDED from PART2 §3; a cost and scheduling fact, since any regime is reachable through a checkpoint pass |

| UNITS | **evaluation scene set** | **SPLIT** — ours sweeps ten scenes, all seven non-native evaluators pin `scene_id=0` |

**UNITS 4/5 uniform. CONDITIONS 1/7 uniform. Zero axes left underived** — which is a fact
about the list of axes anyone has named, not about the twelve. The script prints exactly that
rather than letting an empty gap-list read as completeness, and a test goes red if it ever
says "the enumeration is complete".

**This headline was wrong for several hours and the correction is the entry's most useful part.**
It first read *"every UNITS axis is uniform; every split is CONDITIONS"* — a comfortable result,
and it was an artefact of an axis nobody had derived. `scripts/eval_across_scenes.py` sweeps **ten
scenes**, nine held out. Every other evaluator builds its env with **`scene_id=0`** — `idaac`
`envs.py:101`, `ibac_sni` `general.py:74`, `rad`/`soda` via `dmc_gb`'s `wrappers.py:23`, `alda`
`alda_trainer.py:142`, `ctrl` and `ppg` by taking the same default — and varies only the visual
regime. So a native's number is *mean return over ten scenes* and the other seven's is *mean return
at scene 0*. **Those are different estimands**, which is [C72](#c72) restated as the axis it always
was.

That single axis is what R3 now fails on, and it fails in the one way that cannot be declared away:
a CONDITIONS split leaves numbers commensurable, a UNITS split does not. Closing it is a decision
rather than a conversion — **give the seven evaluators a scene sweep, or redefine the endpoint to
what all twelve can produce** — and it is the owner's.

**Reward scale was moved OUT of this audit in the same pass**, to [C75](#c75), because each source
paper's reward magnitude bears on whether an algorithm's hyperparameters suit the regime, not on
what a reported Door number means — all twelve are evaluated on Door and report Door's own reward.
Recorded here because narrowing an audit's scope is the kind of move that deserves suspicion:
**the same pass that removed one item added a worse one**, taking the result from "all UNITS
uniform" to "a UNITS axis splits". Scope moved in the direction that costs more.

`test_the_only_units_split_is_the_scene_set_and_every_other_split_is_conditions` names the known
split rather than counting, so a *second* one arrives with a name attached — and it also fails if
this one silently heals, since the likelier cause is the audit going blind than seven evaluators
gaining a sweep.

**Two traps recorded on the way, either of which would have produced a plausible wrong number.**
The reported return is raw for `idaac`/`ctrl`/`ppg` **only because each one's episode monitor sits
inside its normaliser** (or, for `ppg`, because normalisation happens in the learner on an
already-collected segment); move one wrapper and twelve numbers silently change units. And
`train/mean_episode_reward` is a **rolling** mean over a policy that was changing while it was
measured — `idaac` keeps 10, `ctrl` and `ppg` keep 100 — which shares a name, a unit and an axis
label with the fixed-policy evaluation mean and is a different estimand. The uniformity of the
estimator axis is conditional on only ever reading the evaluation number, and that condition is
invisible in any plot.

**The distinction the first version lacked, and it is the entry's real content.** An axis can split
the **UNITS** — what the number *means* arithmetically — or the **CONDITIONS** — what was measured,
leaving the units intact. They fail differently and need different remedies: a UNITS split makes
two numbers incommensurable and must be removed or converted; a CONDITIONS split leaves them
commensurable but makes a difference between them unattributable to the algorithm, which is exactly
what [`RESEARCH-FRAME.md`](RESEARCH-FRAME.md)'s claim already handles by declaring and quantifying.
Counting them together, as the first output did, hides which kind of trouble R3 is actually in.
**All three UNITS axes derived so far are uniform; all four splits are CONDITIONS.**

**The null is not lifted and the script cannot lift it.** Owner, 2026-08-26: *"the null is 'they
aren't same', and the reasonable absence of unknown unknowns should be established before they're
concluded same."* Every run therefore prints the null, prints the count of **underived** axes (2,
named), and is prevented by a test from emitting any sentence that reads as a verdict of
comparability. A uniform axis removes one way the numbers could differ; it says nothing about the
ways nobody enumerated, and completeness is a judgement, not a checklist result.

**Two false reports, both over-stating incomparability, both from reading the shape of code rather
than what it does.** `effective action repeat` was printed as "SPLIT 4 ways" when all twelve run at
1 and only the mechanism differs. `success definition` was printed as *five baselines record no
success at all* — which would have been the largest R3 finding in the project — because the pattern
required `info.get('success'` while every one of the five writes `(info or {}).get('success',
False)`. It was a regex. An audit biased toward over-reporting splits is the safer of the two
possible biases and is still not harmless: it spends attention on defects that are not there, and
it earns being discounted.

**The near-miss worth more than the result.** The reward-normalisation and frame-stack facts above
were derived from scratch on 2026-08-26 — and
[`PART2-METRIC-INVENTORY.md`](PART2-METRIC-INVENTORY.md) had already derived both, by hand, on
08-17, including the wrapper-order argument that is the non-obvious half. The two agreed. **That
agreement was luck**: a fresh derivation that disagreed would have been filed as a finding against
a document nobody had opened. The file was already routed from `PROJECT-INDEX.md`, `SYSTEM.md`,
`TASK.md` and `RESEARCH-FRAME.md`, so the routing was never the defect — not consulting it was.
Three corrections follow: that file is now on the project `CLAUDE.md` read-in-full list; the audit's
header states it is a regression check and **not an independent authority**; and its §5 order-of-work,
whose items 1 and 2 were complete but still listed as pending, now says so. *A numbered order of
work ages faster than the findings above it, because a finding is a statement about code and an
order is a statement about intent.*

**Decision** none — this entry supplies R3's evidence, it does not grade R3. **What would show this
wrong** an axis that is uniform here but on which two baselines' numbers still fail to compare;
that would mean the axis list, not the axis values, is what needs work.

**PROPOSED CHOICE, 2026-09-03 — and the branch point's cost estimate is wrong, which changes the
answer.** Full reasoning in [`EVAL-PROTOCOL.md`](EVAL-PROTOCOL.md). Recorded here as a proposal;
the entry stays a branch point until the owner records otherwise.

**The reframing.** `RESEARCH-FRAME.md`'s option (1) is costed as *"give the seven evaluators a scene
sweep — costs a deviation in each clone and re-opens the faithfulness ledger for seven baselines"*.
That price assumes evaluation happens **inside** the clones. It does not have to, and for a quarter
of the set it cannot: `scripts/audit_eval_cadence.py` finds `ppg` and `ibac_sni` run **no periodic
training-time evaluation at all** and `ctrl`'s is continuous rather than episodic, so *"metrics on
the same axes is not reachable from training logs by construction. It is reachable offline, from
checkpoints."*

**So evaluation moves entirely into our own harness** — `eval_grid.py` under `OFFLINE_EVAL`, loading
a checkpoint and driving the baseline's own `act`. The scene set is then a parameter of **our**
code. **Zero clone deviations, and `deviations.py` is untouched.** What it actually costs is
extending our evaluator to `alda`, `ctrl` and `ibac_sni` (four families already exist), of which
`ctrl` is the real work — a flax msgpack checkpoint and a JAX policy.

**What is deliberately NOT equalised**: the estimator. Our harness calls each baseline's own `act`,
so the three that sample keep sampling and the nine that take a mode keep doing so
([`COMPARABILITY_CONTRACT.md`](COMPARABILITY_CONTRACT.md) §5c). Equalising it would substitute our
policy for theirs, which is a fidelity change of exactly the kind this project refuses.

**The assumption it rests on, and the guard.** Driving a foreign `act` from outside its trainer must
not change what is measured — the [C95](#c95) failure mode one level in. Demonstrated for the five
natives (131.57 against a logged 135.71). **Asserted, not demonstrated, for the other seven**, which
is why job `bt1c6vj2iv6ucu9683nk` tests it on `idaac`: its own cell reported 3.01 on eval-easy, and
our harness on the same checkpoint should land at the same scale. **If that comes back far off, this
proposal is withdrawn rather than patched** — it would mean our evaluator changes a policy's
behaviour, and no amount of scene-set uniformity is worth that.

### C77 — A native run launched at exactly N never saves at N, and our own tooling asserted the opposite {#c77}
**Class** OURS · **Status** RESOLVED · **Cross-ref** [C57](#c57), [C60](#c60), [C68](#c68), [C73](#c73)

**The mechanism.** `train.py:309` saves when `global_step % int(5e4) == 0`, and that check sits
inside `if time_step.last():` at the **top** of the loop body. The loop is
`while train_until_step(self.global_step)` and `Until.__call__` returns `step < until`
(`utils.py:73`). At the end of the episode that lands on step N, the while-test is evaluated
**before** the episode-end block, `N < N` is false, and the loop exits — so the save for step N
never runs. A native run launched with `num_train_frames=N` therefore saves at every multiple of
50 000 **strictly below** N, and never at N itself.

**The cost, and what makes this a register entry rather than a note.**
[`scripts/run_cell.sh`](../scripts/run_cell.sh) carried this, written when [C68](#c68) was worked out:

> *"The default is therefore 50000, not 55000: same checkpoint, ~9% less compute."*

It is not the same checkpoint. **It is no checkpoint.** The script's default budget would have
produced zero checkpoints for every future cell, and its warning fired on exactly the budgets that
work (`FRAMES % 50000 != 0`) while staying silent on the one that does not. A `drqv2` seed-7 run at
`num_train_frames=100000` cost ~3.5 h and ended at frame 99 500 with `snapshot.pt` holding
**step=50000** — the 100k checkpoint it was launched for does not exist. A `svea` run was stopped
at 50 000 rather than spend five more hours reaching the same dead end.

**Confirmed three ways rather than inferred from the code**, because the code had already been read
once for C68 and the wrong conclusion drawn from it:

| evidence | budget | snapshot holds |
|---|---|---|
| `drqv2` seed 7, 2026-08-26 | 100 000 | **step 50 000** |
| the archived run ([C54](#c54)) | 120 000 | step 100 000 ✓ |
| all four 50k cells | 55 000 | step 50 000 ✓ |

**What was wrong in the reasoning the first time.** C68 established the *cadence* correctly — saves
happen at multiples of 50k — and then inferred the *boundary* from it without checking the loop's
exit order. A cadence and a termination condition are different facts about the same loop, and the
first does not give you the second. The tail frames that C68 called waste are what make the save
reachable at all.

**Decision** the budget must exceed the wanted checkpoint by at least one episode. `run_cell.sh`
now **raises** an exact multiple of 50 000 to `N + 5000` and says so, rather than warning: a warning
about a checkpoint that will not exist is read after the compute is already spent.
`tests/test_run_cell_budget.py` breaks it deliberately. **Effect** the 100k cells were relaunched
at 105 000; both printed the correction. Committed as `13c48011`. **What would show this wrong**
a native run launched at an exact multiple of 50 000 that does hold a checkpoint at that step.

### C78 — The decision ledger silently closed an open decision, and its test passed because it used the one phrasing the code handled {#c78}
**Class** OURS · **Status** RESOLVED · **Cross-ref** [C65](#c65), [C76](#c76), [SYSTEM.md](SYSTEM.md)

`scripts/decisions.py` classified a §4 block as settled with
`bool(ch) and "not yet made" not in ch.lower()` — a single hardcoded literal. On 2026-08-26 the
block recorded for [C76](#c76), whose **Choice** row reads *"**NOT MADE** — the owner's"*, was
counted **DECIDED** and disappeared from the list of judgements awaiting the owner.

**That is this instrument's worst possible failure direction.** The ledger exists so open decisions
stay visible; one that silently closes them still prints a confident count, and the count is what
gets trusted. It is the same shape as [C65](#c65)'s screen keyed to the wrong ratio: correct
machinery, wrong predicate, and silent.

**Its test passed throughout.** `test_an_undecided_block_reads_pending_not_settled` tried exactly
one phrasing — `"Not yet made"` — which was the literal the code tested for. A test that exercises
only the input the implementation was written around cannot fail, and this project has now recorded
that shape three times ([C65](#c65)'s dump helper giving every scene the same `n_success`, R5
matching the word "matplotlib" in its own source, and this).

**Decision** the marker list is explicit and plural (`UNDECIDED_MARKERS`), and the test is
parametrised over the phrasings a writer actually reaches for — *not made*, *undecided*, *deferred*,
*open*, *pending* — plus the reverse direction, since *"open"* and *"the owner's"* are broad enough
to demote a real decision whose Choice cell records who made it. Restoring the single literal turns
six of them red. Committed as `4c2d96f3`. **Effect** [C76](#c76)'s branch point — what the retention endpoint is measured
over — now appears as PENDING where it belongs; the ledger reads 12 logged, 10 settled, and no
previously-decided block was demoted by the broader markers. **What would show this wrong** a block
meaning "undecided" in none of the listed phrasings, still miscounted — which is why the list is a visible constant
rather than a regex, and why the falsifier is the list's completeness rather than its correctness.

### C79 — Divergence has been readable from the live log since 2026-08-20, and nothing read it {#c79}
**Class** OURS · **Status** RESOLVED · **Cross-ref** [C57](#c57), [C60](#c60), [C70](#c70), [C77](#c77)

[C57](#c57)'s finding was that a NaN-diverged run is *"indistinguishable in every artifact we
keep"*, with only an indirect tell — episode return with standard deviation 0.00. **That was true
of the artifacts it had and has not been true since.** Those eight `train.csv` files carry the
header `buffer_size,episode,episode_length,episode_reward,fps,frame,step,total_time`: episode
bookkeeping, no loss column anywhere. Turning on `use_tb=True` on 2026-08-20 — done partly *for*
C57 detection — added `actor_loss`, `actor_logprob`, `critic_loss`, `critic_q1`, `critic_q2` and
`critic_target_q`, and those go **literally `nan`** on the first bad update.

So for six days the thing C57 called invisible sat in a text file in the clear, while this project
still only checked *checkpoints*, after the fact, with `check_checkpoint_finite.py`. **This is not
an error in C57. It is a finding whose scope changed and whose consequence nobody re-derived** —
the same shape as [C68](#c68)→[C77](#c77) earlier the same day, where a correct cadence produced a
wrong boundary.

**The cost, measured on the run that prompted it.** `drqv2` seed 7, 2026-08-26: **first `nan` at
frame 7 000, 5.9 minutes in.** It ran to frame 50 000 — **64 minutes** — and was 1.2 hours from
writing a checkpoint of NaNs. Roughly a tenfold waste, and the evidence was in the log from minute
six. Note also that the *previous* seed-7 run at the same seed did **not** diverge and ended at
return 475: after [C70](#c70), divergence is a lottery, so this will recur.

**Decision** `scripts/watch_divergence.py`, with `tests/test_divergence_watch.py`. It reports and
**never kills** — a watcher that terminated runs would be one bug from killing a healthy one, and
it cannot know why a run is worth continuing. `--match` covers a whole batch, including runs
launched later, mirroring `preserve_intermediate_snapshot.py`.

**The part that matters more than the detection: it refuses to say OK when it cannot see.** `drq`
cannot run with `use_tb=True` at all (its `SquashedNormal.entropy()` regression), so its log has no
loss columns and this instrument is **blind** to it. It returns a distinct BLIND code naming the
fallback, because reporting "healthy" for a run it cannot see would convert an absence of evidence
into a clean bill of health.

**`preserve_intermediate_snapshot.py` now refuses a snapshot from a diverged run**, delegating the
judgement to `watch_divergence.inspect` rather than reimplementing it so the two cannot drift. It
had preserved 104 MB of NaNs as a 50k measurement before this existed. **That file is still on
disk** at `exp_local/2026.08.26/221025.../snapshot_50k_frames.pt` — flagged, not deleted, because
removing evidence is not an instrument's job.

**Two defects in the watcher were found by its own tests, not in production**, and both are the
kind that would have made it quietly useless: `sd == 0.0` never fires on returns parsed from
decimal strings (twenty copies of `"0.68"` have variance ~1e-17, and the real log alternated
0.68/0.69 anyway — now a 1%-of-mean coefficient of variation), and `csv.DictReader` yields `None`,
not `""`, for a column missing from a half-written row, so `float()` raised `TypeError` where only
`ValueError` was caught — a live watcher polls mid-write constantly.

Committed as `9de8ccda`. **Effect** two runs are now watched at 45-second intervals; the dead seed-7 run was caught and
stopped, and `drqv2` relaunched at 23:17. **What would show this wrong** a run that diverges with
every logged loss finite — which would mean the divergence enters through a path the update does
not log, and the checkpoint check would again be the only instrument.

### C80 — Mutation testing was 100% unusable, and its failure pointed at the wrong instrument {#c80}
**Class** OURS · **Status** RESOLVED · **Cross-ref** [C65](#c65), [C78](#c78), [C79](#c79), [RIGOR.md](RIGOR.md) §7

[`RIGOR.md`](RIGOR.md) §7 makes mutation testing the measure of whether the suite would notice a
real regression, and `mutants/run.py` implements it correctly: mutate a **copy**, run the real
suite, and refuse to report anything unless an **unmutated** copy passes first. That sanity gate
**failed every time**, so no mutant had ever been measured — and the framework had been in the repo
long enough to be cited in three documents as the thing that replaced `run_mutants.py`.

**The diagnosis pointed away from the cause.** The gate failed with
*"a citation points past the end of the file it names"*, which reads as a defect in
`docs/` — and the working tree's citation check was green. Three independent causes, each the same
shape: **the copy was not a faithful environment, and every check that noticed said so in the
vocabulary of its own subject rather than of the copy.**

| what the copy lacked | what failed | why it looked like something else |
|---|---|---|
| `.git` (516 MB, deliberately not copied) | `check_citations.py::_git_knew` shells out to `git log` to classify a citation to a deliberately-deleted file as HISTORICAL. With no repository every such citation became **MISSING** | reported as two citation defects in `docs/` |
| the workspace ancestor | `CLAUDE.md`'s nulls each cite `../../docs/porting-directive.md`, and `test_claude_md_nulls.py` checks the quoted text against it | reported as a null pointing at a missing file |
| the sibling projects | `PROJECT-INDEX.md` cites `../../gen-rebuttal/vigen-idaac` | reported as a broken internal link |

**Fixes, and the shape they share with [C79](#c79).** `_git_knew` now distinguishes *"git has no
record"* from *"there is no git"*, and a citation it cannot classify is reported
**UNCLASSIFIABLE** — printed loudly, counted as neither defect nor confirmation. That is the same
answer `watch_divergence.py` gives as BLIND, for the same reason: **absence of evidence must not be
reported as evidence, in either direction.** A run in a tree without history must not look
*cleaner* than one with it. `mutants/run.py` now reproduces the workspace and sibling levels by
**enumerating** them rather than listing them by hand — the file already records that a
hand-maintained skip list *"silently stops being right when the tree grows"*, and this is that
lesson one directory further up, where a fix aimed inside the tree could not see it.

**A real documentation defect fell out of it.** A bare `config.yaml` cited at line 34 matches
**75** files in the working tree, so it was AMBIGUOUS and therefore *never checked*; in the narrower
mutant tree it resolved to `compute/datasphere/config.yaml`, which has 26 lines, and was reported
BROKEN.

*(Written that way deliberately: the first draft of this paragraph quoted the bare
name-with-line-number, the checker parsed the example as a live citation, and this entry
**reintroduced the defect it documents** — caught by the sanity gate it also documents. Naming a
defect in the notation that causes it is its own small class.)* Both readings are useless, and the citation was unverifiable as written. Now
`RL-ViGen-upstream/cfgs/config.yaml:34` — 67 lines, and actually checked. **A narrower tree is a
better citation checker than a wider one**, because ambiguity hides defects behind "not checked".

**The catalogue was also measuring the wrong era.** Its header read *"every mutant below is a patch
to a file under `rlgen/`"* — the **retired port**. A catalogue that only mutates code which no
longer runs measures the suite's sensitivity to nothing. **M25–M31** add the clone-era instruments
(`audit_comparability_seam`, `decisions`, `requirements`, `run_cell`, `watch_divergence`,
`preserve_intermediate_snapshot`), 31 mutants total, 20 critical.

**And the reason those seven exist at all is a process failure worth recording.** Every mutation in
this session was run by hand as `cp` / patch / `pytest` / restore **on the working tree** — exactly
what `RIGOR.md` §7.3 forbids, because *"a mutation runner that edits your source and restores it
afterwards loses a race with any interruption"*. This session was interrupted twice. Nothing was
left behind — checked, `git status` clean of sentinels — but the practice was wrong, and the fix is
not a more careful restore: it is that the mutants now live in a reviewed catalogue that runs
against a copy and keeps running after the session that thought of them has ended.

**Decision** repair the copy rather than weaken the checks; report unclassifiable inputs as such.
Committed as `b0089c15`. **Effect** the sanity gate passes in 439 s and mutants run for the first time.
**What would show this wrong** a check that passes in the copy and fails in the working tree — the
reverse asymmetry, meaning the copy is now *more* permissive than the tree rather than faithful.

### C81 — The first clean endpoint number: regime retention 0.3%, and the random floor proves the manipulation is purely visual {#c81}
**Class** OURS · **Status** MONITORED · **Cross-ref** [C46](#c46), [C54](#c54), [C62](#c62), [C65](#c65), [C69](#c69), [C73](#c73), [C77](#c77), [C79](#c79)

The first cell in this project that is **uncontaminated, deterministic, verified finite, mode-verified
and paired within one run**: `drqv2` seed 7 at the 105 000-frame budget ([C77](#c77)), holding both
`snapshot.pt` (step 100 000) and its own preserved `snapshot_50k_frames.pt` (step 50 000).

| budget | usable scenes | **regime retention (return)** | SR retention | resolution floor | contamination screen |
|---|---|---|---|---|---|
| 50 000 | 4/10 | **0.019** [0.012, 0.028] | 0.000 (0/200) | 8.9% | all-scene ratio 0.064 — passes |
| 100 000 | 3/10 | **0.003** [0.002, 0.005] | 0.017 (1/200) | 22.8% | all-scene ratio 0.117 — passes |

Both drops are an order of magnitude below their own resolution floors, so the design *can* see
them. Neither triggers [C65](#c65)'s screen, unlike every archived checkpoint.

**Two findings, and the second is worth more than the first.**

**1. More training made retention worse.** Train-regime skill on the trained scene rose 312.58 →
439.75 (×1.41, successes 14/20 → 18/20) while regime retention fell **0.019 → 0.003**, on
non-overlapping intervals. The policy specialises. *n* = 1 run, so this is a direction rather than
a rate — but it is the direction that matters, because it says a bigger budget does not buy
generalisation here and may cost it. Scene retention within the train regime moved the other way
and only slightly (18.4% → 22.9%), so the two axes do not move together.

**2. The random-policy floor is byte-identical across the two regimes — 200/200 episodes — and
that is a proof, not a coincidence.** A random policy's actions do not depend on the observation;
the regime changes textures and lighting, not physics or reward geometry; and after
[C69](#c69) the placement RNG is seeded, so the trajectory is fully determined. Both regimes were
genuinely applied (`Now the mode is train` / `eval-easy` in the logs).

**So the train → eval-easy manipulation is purely visual — it perturbs neither the dynamics, nor
the initial state, nor the reward.** Any difference a *trained* policy shows between the regimes is
therefore attributable to the observation alone. That rules out an entire class of confound, and
[`RESEARCH-FRAME.md`](RESEARCH-FRAME.md)'s note that [C19](#c19) ruled the manipulation
non-nominal only *"at the input level and for a random policy"* can now be strengthened at the
**outcome** level for the same policy.

**This control did not exist before C69 and could not have.** The pre-C69 floors read 1.82 (train)
against 1.85 (eval-easy) — a difference that was pure RNG noise and would have been read as the
regime slightly perturbing the environment. Determinism converted a noisy near-equality into an
exact identity, which is the difference between an observation and a proof. It is the clearest
payment yet on C69's cost.

**Honest limits.** One run, one baseline, one task. Only 3–4 of ten scenes clear the denominator
rule at all, so the pooled retention answers *"on scenes where the agent had learned something"* —
not RL-ViGen's ten-scene protocol, which is the estimand [P-C76](RESEARCH-FRAME.md) is a branch
point about. And the eval-easy returns on the trained scene (0.89 at 50k, 1.22 at 100k) sit *below*
the 1.81 floor while several held-out scenes sit above it: a confidently wrong policy can score
worse than a random one. **Recorded as an observation, not explained** — a mechanism for it would
need a second run at minimum.

**Decision** none; this is a measurement. **What would show it wrong** `svea` at the same budget
showing retention that does not fall with budget, which would make the specialisation reading
`drqv2`-specific rather than general.

### C82 — Three wrong readings of one document, and the method that produced all three {#c82}
**Class** OURS · **Status** MONITORED · **Cross-ref** [C30](#c30), [C66](#c66), [C76](#c76), [C81](#c81), [RUNNABLE-ORIGINALS.md](RUNNABLE-ORIGINALS.md)

**The finding is about how I read, not about `FAITHFULNESS.md`.** Three claims were written about
that file on 2026-08-27, each corrected by the owner, each wrong in the same way — a conclusion
drawn from a *proxy* for reading rather than from reading.

| # | claim | how it was reached | what was actually true |
|---|---|---|---|
| 1 | "every 'Ours:' claim describes the retired port" | counted **26 `rlgen/` refs, 0 `runnable/`** | the port mediated only the *seven*; the five natives ran and still run upstream's `train.py` (§2 says so in its first line) |
| 2 | "the values are stale" | checked values — **correct, and the right method** | `idaac` runs γ 0.999 / rollout 256 / lr 5e-4, not the recorded 0.99 / 2048 / 3e-4 |
| 3 | "the file does not know the clone tree exists" | the same `runnable/` count | **§5 is re-triaged 2026-08-24 and is clone-aware throughout** — it writes clone paths *without* the `runnable/` prefix, which is exactly what the count missed |

**The document already had what I said it lacked.** §5 *"What would raise fidelity most"* is the
current-state section: it resolves, re-opens or explicitly excludes the items in §0–§4, cites
clone-era register entries and `scripts/run_cell.sh`, and carries a *"Considered and deliberately
excluded"* list so that absence and oversight do not read alike. **A reader should start there.**

**And the substantive conclusion inverts.** §4's structural findings — PPG with one shared value
head, IBAC-SNI's critic seeing the SNI-mixed pass, CTRL missing `L_clust` — describe
`rlgen/algos/onpolicy_ext.py`, *our re-derived on-policy core*. **The clone move discharged every
one of them**, verified: `runnable/ppg` ships `PhasicValueModel`, `vf_true` and a separate `aux_lr`
optimiser; `runnable/ibac_sni` ships the `bot_mean` deterministic pass; `runnable/ctrl` ships the
clustering. So §4 is not a backlog — **it is the record of the port's fidelity debt and of
hermetic-first paying it off.** I was one edit away from handing the owner a fabricated decision
("re-derive twelve baselines of fidelity comparison"); there is no such work owed.

**What is genuinely open** is what §5 already lists — its items 5, 6, 9, 10 — plus **two of its own
resolutions that the clone move re-opened**: item 2 (*"the rollout was never 256 — it is 2048"*)
and item 3 (*"gamma was never a live disagreement"*) were both settled against `configs/vigen.yaml`,
which nothing live reads. The clones run 256 and 0.999. Item 9 — the entropy coefficient `0.01`
tuned against Procgen's 15-way categorical (`ln 15 = 2.708`) now multiplying a 7-D Gaussian
(`9.933` at σ=1, **3.67×**), measured on a 60k `idaac` run — is §5's own *"largest untracked
fidelity gap now known"*, and is the owner's.

**Two sentences remain false in both eras** and are worth fixing at source rather than marking:
*"no real training has been run in this project yet"* and *"Zero real training runs exist yet, so
nothing has trained wrong silently"*. `runnable/idaac/models/` holds three checkpoints. The second
licenses an inaction, so a false premise matters even where the conclusion may survive — and it may,
for a reason it does not give ([C76](#c76): the clones **do** normalise the learner's reward).

**The method rule this yields, which is the point of the entry.** A document's era cannot be read
off its citations, and staleness cannot be counted. Before calling a claim stale: (a) check the
**value** it asserts, not the path it cites — a dead citation beside a true number is a broken link,
not a wrong claim; (b) look for the document's **own latest-state section** before writing a banner
over the whole file, because scoped appending edits put the current answer at the *end*, not the
top; (c) separate the **sentence**, the **reasoning**, and the **disposition it licenses** — only
the first is cheap to check, and only the third decides whether anything must be done.

**Decision** none owed. **Effect** two wrong banners withdrawn; §5 routed to as the entry point.
**What would show this wrong** a §5 item that is itself port-era and unmarked — two were found
(items 2, 3), so the section is current but not uniformly so, and the next reader should verify
rather than inherit that.

### C83 — The first cross-baseline comparison: `svea` retains ~140× more than `drqv2`, and is the weaker arm where it trained {#c83}
**Class** OURS · **Status** MONITORED · **Cross-ref** [C46](#c46), [C55](#c55), [C65](#c65), [C69](#c69), [C73](#c73), [C81](#c81), [RESEARCH-FRAME.md](RESEARCH-FRAME.md)

Two cells, same budget, same seed count, same evaluator, both uncontaminated and mode-verified.
**This is the comparison the project exists to make, and it is the first one it has been able to
make.**

| @ 100k, Door | trained-scene return | scene retention | **regime retention** | SR retention | usable scenes |
|---|---|---|---|---|---|
| `drqv2` seed 7 | **439.75** (18/20) | 22.9% | **0.003** [0.002, 0.005] | 0.017 (59→1 /200) | 3/10 |
| `svea` seed 1 | 234.36 (14/20) | **59.7%** | **0.428** [0.318, 0.558] | **0.390** (100→39 /200) | **9/10** |

**The weaker arm on the training distribution is the stronger one off it.** `drqv2` scores 1.9×
`svea` on the scene it trained on and then loses essentially everything under the visual shift —
one successful episode in two hundred. `svea` keeps 43% of its return and 39% of its success rate.
A table reporting only train-regime return would have ranked these two the wrong way round, which
is precisely the failure a retention endpoint exists to prevent
([RESEARCH-FRAME.md](RESEARCH-FRAME.md): *"retention makes each method its own control"*).

It is also the mechanistically expected direction and therefore weak evidence on its own: SVEA is
an augmentation method whose entire purpose is robustness to visual change, and DrQ-v2 is the
non-generalization baseline. **The result is worth more for being measurable than for being
surprising** — what is new is that this project can now produce it at all.

**Both gaps are resolved by the design, which is not automatic.** `drqv2`'s gap of 99.7% sits
against a resolution floor of 22.8%; `svea`'s 57.2% against 39.1%. The floors are set by the
*seed-only* control — the same scene re-evaluated at a different placement seed — so they measure
what this design can distinguish from noise, and both comfortably exceed theirs. `svea`'s is the
tighter margin and should be quoted with it.

**Why these two are comparable at all**, and it is not a general licence: both are RL-ViGen
natives, and the seam audit splits on **0 of 12 axes within the five natives** where seven split
across the twelve. Their hydra configs are identical on every shared key. So the collinearity that
makes across-method comparison weakly identified for the twelve **does not apply here** — recorded
in [RESEARCH-FRAME.md](RESEARCH-FRAME.md) the same day.

**Honest limits, none of which are small.**
- **One seed per arm.** Between-seed variance is unmeasured for both. The seed-only control bounds
  *placement* noise within a checkpoint, not the spread of checkpoints.
- **One task, one budget.** 100k frames is ~0.4% of IDAAC's 25M and far below RL-ViGen's own Door
  budget of 6e5; nothing here says the ordering survives to convergence.
- **The pooled numbers use different denominators** — 9 usable scenes for `svea`, 3 for `drqv2` —
  because each pools only where its own denominator clears the floor and the 25% success rule. That
  is the honest estimand (*"on scenes where the agent had learned something"*) and it is **not**
  RL-ViGen's ten-scene protocol; the two arms are therefore averaged over different scene sets, and
  that is a real caveat rather than a footnote.
- `drqv2` at 50k retained 0.019 and at 100k 0.003, so its retention **fell** with budget
  ([C81](#c81)); `svea` has no comparable 50k number because its 50k cell was refused outright
  (0/10 usable scenes). The budget trend is therefore established for one arm only.

**Decision** none — a measurement. **What would show it wrong** a second seed of either arm landing
outside the other's interval, or the ordering inverting at a larger budget. Both are cheap relative
to what has already been spent, and the second is the one that would matter for a write-up.

### C84 — `drq` crashed on a zero policy scale that its own bounds should make unreachable {#c84}
**Class** OURS · **Status** OPEN · **Cross-ref** [C57](#c57), [C70](#c70), [C79](#c79), [C81](#c81)

`drq` seed 1 at 105 000 frames, 2026-08-28: died at **frame 5 000**, ~1 000 frames after updates
begin (`num_seed_frames: 4000`), with

    ValueError: Expected parameter scale (Tensor of shape (256, 7)) ... to satisfy
    GreaterThan(lower_bound=0.0), but found invalid values: tensor([[0., 0., ...]], device='mps:0')

from `algos/drq.py:155`, `dist = SquashedNormal(mu, std)` where `std = log_std.exp()`.

**What is established.**
- **The same seed and configuration ran to frame 54 500 on 2026-08-24** (return 102.0, finite
  checkpoint at step 50 000). `drq` is not deterministically broken at this seed.
- It crashed **loudly**. Torch's distribution validation rejected the degenerate scale, so unlike
  [C57](#c57) the run stopped instead of training 70 000 more frames into a NaN checkpoint. That
  matters here specifically: `drq` is the **one baseline `watch_divergence.py` is blind to**
  ([C79](#c79)) because it cannot run with `use_tb=True`, so no loss column exists to watch. The
  crash is what surfaced it, and it is the only mechanism that would have.

**What is NOT established, and is written down rather than guessed.** `drq_config.yaml:54` sets
`log_std_bounds: [-10, 2]`, and the actor squashes with `tanh` before rescaling into those bounds
(`drq.py:147-151`), so `std` should floor at `exp(-10) ≈ 4.5e-5` and **exactly 0.0 should not be
reachable through that path at all**. A NaN would have printed as `nan`, not `0.`; `tanh(-inf)`
gives `-1`, which rescales to `-10`, not to an underflow. **I cannot account for the observed value
from reading the code**, and the honest entry says so rather than supplying a mechanism that fits.

> ### DEFAULT SET, 2026-09-04 — this is an MPS-EXECUTION event, it cannot reach a production number, and it stays open on those terms
>
> Two things were established today, both by reading and one earlier by measurement, and together
> they change what this entry is:
>
> **1. The code path provably cannot produce 0 in exact arithmetic.** `drq.py:143-151` is
> `tanh → rescale → exp` with no branch: `torch.tanh` bounds to `[-1, 1]`, the rescale maps that
> onto `log_std_bounds`, and `log_std_bounds` is `[-10, 2]` in **all three** drq-family configs
> (`drq_config.yaml:54`, `sgqn_drq_config.yaml:53`, `svea_drq_config.yaml:52`) and is passed
> straight to `Actor.__init__` (`drq.py:203`) with nothing between. So `std ∈ [4.54e-5, 7.39]`.
> Reaching exactly 0 through `exp` needs `log_std ≲ -88` in float32, which the rescale forbids;
> `tanh(-inf) = -1` gives −10, not underflow, and a NaN would have printed `nan`. Earlier this
> session the MPS-underflow story was also refuted experimentally — 200 trials at the real (256, 7)
> shape on both devices, no zeros, minimum std exactly 4.539993e-5.
>
> **So the observed value implicates the EXECUTION, not the algorithm.** That is a narrowing, not
> an explanation: a kernel returning a wrong result is consistent with everything here and is not
> demonstrated by any of it.
>
> **2. It has only ever been seen on MPS, and no production number can come from MPS.** The
> traceback reads `device='mps:0'`. [C95](#c95) forces every reported number to be produced in the
> container on CUDA, and `drq` completed its CUDA pre-production cell (`docs/dated/preprod-table-2026-09-03.md`,
> return 1.100 at 10k) with no such failure; the crash string appears in no CUDA log in the corpus.
>
> **Default: keep C84 OPEN as an unexplained MPS-correctness event, and stop treating it as a
> production risk.** What it endangers is *local rehearsal* — which is real, because a rehearsal
> that dies at frame 5,000 costs a person an afternoon. **The one observation that would overturn
> this is a CUDA sighting**, and it is worth naming precisely because nothing currently looks for
> it: the string to watch is `Expected parameter scale`. Not fixed, not explained, and no longer
> blocking.
>
> **Why not simply set `torch.use_deterministic_algorithms(True)` in training and see.** It would
> make MPS training reproducible ([C70](#c70) does exactly this for the evaluator) — and it would
> also change what training does, on all five RL-ViGen baselines, to chase a failure that cannot
> affect the deliverable. That trade is bad while production is CUDA-only.

**The leading hypothesis, held as one.** Training sets no `torch.use_deterministic_algorithms`
— that call lives in the evaluator only ([C70](#c70)) — so kernel selection varies run to run, and
[C81](#c81) already records divergence behaving as a lottery for `drqv2` at a fixed seed. Same
seed, different outcome, is consistent with that. **It is consistent with, not evidence for**: the
zero-scale value is unexplained under either reading, and a lottery explains *when* a run dies, not
*how* a bounded quantity reached zero.

**Next step, and it is the cheap one.** Re-run at the same seed. It ran once before, so a second
success makes the lottery reading much more likely and yields the cell that is needed anyway; a
second identical crash makes it a reproducible defect worth tracing with a smaller repro.

> **RESULT, 2026-08-28: the retry SURVIVED.** Same seed, same configuration, launched 16:02 —
> reached frame 100 500 in 3.1 h and wrote a **finite** `snapshot.pt` at step 100 000 (49 596 510
> parameters, 0 non-finite), gated on `check_checkpoint_finite.py` because `drq` is the baseline
> the divergence watch is blind to. The first attempt died at frame 5 000 three hours earlier.
>
> **So the lottery reading is supported and options 2–4 are no longer needed for the cell** — `drq`
> produced one. What survives is the narrower question: the zero itself is still unexplained, and a
> defect that appears once in two runs at a fixed seed will appear again. **The status stays OPEN
> for that reason**, not because a row is missing.
>
> **One thing was lost and is not recoverable for this cell.** `preserve_intermediate_snapshot.py`
> was not running — its `--seconds 80000` window had expired the previous day — so `drq` has **no
> paired 50 000 snapshot**. Its cell is 100k-only, and the within-run budget comparison
> [C81](#c81) established for `drqv2` cannot be made for `drq` without re-running it. A watcher
> with a timeout is a watcher that stops watching, and nothing announced the expiry.

**Options**, if the retry also dies — stated now so the decision is not made under time pressure
later:

1. **Report `drq` as absent, with the reason.** It joins `curl` (cannot run under the MPS shim),
   `ctrl` and `ppg` (cannot checkpoint as published) as a baseline whose row is *absent rather than
   poor*. [`FAITHFULNESS.md`](FAITHFULNESS.md) §5 item 10 already argues the table must say which
   per baseline. Costs a row; costs nothing in fidelity.
2. **Re-seed.** Try seeds other than 1 and report `drq` from whichever completes, disclosing that
   the seed was selected by survival. That is a selection effect on a cell whose whole purpose is
   comparison, and it must be declared if taken.
3. **Run it where the kernels differ** — the V100 the owner has access to. If the leading
   hypothesis is right this is the cleanest test *and* produces the cell; if `drq` dies there too,
   the MPS-lottery reading is wrong and the defect is in the algorithm's interaction with this
   configuration.
4. **Trace it with a minimal repro** — load the 08-24 checkpoint, step the actor, and find what
   drives `log_std` below `-104`. Most expensive, and the only option that would actually explain
   the zero.

**What must NOT be done:** widen `log_std_bounds` to stop the crash. That edits upstream's
algorithm to suppress a symptom, the value is RL-ViGen's own, and it would convert a loud failure
into the silent one [C57](#c57) exists to warn about.

**INVESTIGATED 2026-09-04, and the obvious explanation is REFUTED rather than confirmed.** The
natural reading of this entry is that the bounds silently failed on MPS -- that `exp()` underflowed,
or a non-finite value slipped through `tanh`. Tested directly against the expression at
`algos/drq.py:146-150` with the configured `[-10, 2]`:

| input | cpu | mps |
|---|---|---|
| -50, -10, -1, 0, +50 | std 4.54e-5 … 7.39 | identical to 7 s.f. |
| `nan` | std `nan` | std `nan` |
| `+inf` / `-inf` | 7.39 / 4.54e-5 | identical |
| 200 trials at the real **(256, 7)** shape, magnitudes to 1e11 | **no zeros, no NaNs** | **no zeros, no NaNs** |

`min(std)` is exactly the lower bound, 4.539993e-5, on both devices. **The bounded expression cannot
produce a zero scale on MPS from any finite, infinite or NaN input, at the shape that crashed.** So
the failure is not an arithmetic escape from the bounds, and "MPS underflowed" -- which C70 and C79
make an attractive story -- is wrong.

**What that leaves, stated as the narrowed question rather than a new guess.** A zero reached
`SquashedNormal` at shape (256, 7), which is an *update* batch and not an action. Since the
expression cannot manufacture one, the zero was either already in the tensor `self.trunk(obs)`
returned, or the kernel faulted in a way a synthetic tensor of the same shape does not reproduce
(memory pressure, a concurrent MPS stream). Both are testable and neither is tested: the first by
logging `log_std`'s pre-tanh min at the update that crashes, the second by re-running the same seed
under load.

**Why this matters beyond `drq`.** [C79](#c79) records that `drq` is the one baseline
`watch_divergence.py` cannot watch, because it cannot run with `use_tb=True` and so emits no loss
column. The crash was the only instrument that surfaced this. **A defect visible only through a
crash is invisible on the runs that do not crash**, and this entry is the evidence that `drq`'s
observability gap is a real risk to a production result rather than a tidiness complaint.

**Status stays OPEN**: the refutation narrows it and does not close it. What would close it is the
pre-tanh logging above, which costs one short `drq` cell.

### C85 — Sorting the session's findings by "did this need a run?" — and the three that did not {#c85}
**Class** OURS · **Status** RESOLVED · **Cross-ref** [C71](#c71), [C77](#c77), [C79](#c79), [C80](#c80), [C84](#c84), [RIGOR.md](RIGOR.md)

The owner asked, on 2026-08-28: *"if it's you finding things that influence experiment results, why
were these not found at implementation?"* The question has an answer and it is not flattering, so
it is recorded as a sort rather than as a defence.

| finding | needed a run? | why |
|---|---|---|
| [C70](#c70) torch kernel selection moves an episode across Door's `hinge_qpos > 0.3` | **yes** | no reading tells you a nondeterministic kernel changes a hinge angle past a threshold |
| [C84](#c84) a policy scale of exactly 0 under bounds that make it unreachable | **yes** | still unexplained from the code |
| [C81](#c81)/[C83](#c83) the results | **yes** | by definition |
| [C77](#c77) a run launched at exactly N never saves at N | **no** | the loop is twenty lines; [C68](#c68) read it and got the boundary wrong |
| [C79](#c79) divergence readable in `train.csv` for six days | **no** | the columns were there; nothing read them |
| [C80](#c80) mutation testing had never executed | **no** | running it once, ever, would have shown it |
| [C76](#c76)'s regex reporting five baselines as recording no success | **no** | a pattern that missed `(info or {}).get(...)` |

**So most of what cost compute this session was findable by reading, and was not found because
nobody asked the right question.** That is the honest answer, and "read more carefully" is not a
remedy — it has now failed enough times in this project to be evidence against itself.

**What the three had in common is that no instrument covered their shape.**
`scripts/audit_dead_knobs.py` already covers a fourth ([C71](#c71): a knob passed and never read).
The other three had nothing:

- **loop boundary** — a side effect gated on `% k` inside a `while step < N` loop, where `N % k ==
  0` makes the two coincide and the boundary iteration never runs.
- **written, never read** — a quantity logged at real cost that nothing reads back.
- **never executed** — an instrument with no test and no caller, so nothing establishes it has ever
  run.

**Decision** `scripts/audit_static_classes.py` + `tests/test_static_classes_audit.py`. Its positive
control is **C77 itself** — `train.py:309` must keep being flagged, and a mutation that blinds the
detector turns the test red. **Effect** on its first run it reproduced C77, raised one new
candidate in the same class, and flagged **itself** as never-executed, which writing its test
cleared. That self-report is the cheapest possible demonstration that the third check works. Committed as `4cce919b`.

**The new candidate was investigated and is NOT a defect**, pinned in the test so nobody
re-investigates it: `ibac_sni`'s save is gated on `update % save_interval` inside
`while num_frames < args.frames`, but the increment and the save are both in the body **with the
save after the increment**, so the final iteration's save runs. C77's shape is the opposite — the
save sits at the *top* of the body while `global_step += 1` is at the *bottom*, so the iteration
reaching N never begins.

**Deliberately noisy in the safe direction.** A hit is a question, not a verdict; two of the four
it currently reports are fine. The value is that the question is asked on every run rather than
after a wasted afternoon, and the cost of a false positive is a minute of reading against a
3.5-hour run.

**What this does not fix.** [C70](#c70) and [C84](#c84) were not findable this way and nothing here
would have caught them. The honest split is that static classes are worth closing because they are
cheap, not because they are the whole risk — and the experiments continue because **the open
decisions need base runs under them**, not because the code is unexamined.

### C86 — Three baselines at one budget: the ranking inverts between performance and retention {#c86}
**Class** OURS · **Status** MONITORED · **Cross-ref** [C62](#c62), [C55](#c55), [C77](#c77), [C81](#c81), [C83](#c83), [C84](#c84), [RESEARCH-FRAME.md](RESEARCH-FRAME.md)

**Historical measurement notice (2026-09-05).** These retained rows predate the evaluator's
per-episode condition seeding, deterministic-torch and strict-regime revisions. They remain the
dated observation that motivated this finding, but are not comparable with new measurements and
cannot be a production headline; see [`notes/RESULTS-VALIDITY.md`](../notes/RESULTS-VALIDITY.md).
The renderer now requires `--legacy-exploratory` explicitly.

`python scripts/results_table.py --legacy-exploratory`. Three RL-ViGen natives, 105k protocol, 20
episodes × 10 scenes × 2 regimes each, against a measured random floor of **1.81** (0/200 successes).

| @ 100k | trained scene | scene ret. | **regime ret.** | 95% CI | usable | SR train→eval | res. floor |
|---|---|---|---|---|---|---|---|
| `drqv2` s7 | **439.75** | 22.9% | 0.003 | [0.002, 0.005] | 3/10 | 29.5% → 0.5% | 5.0% |
| `drq` s1 | 378.85 | 13.4% | 0.051 | [0.024, 0.088] | 3/10 | 16.0% → 1.0% | 23.6% |
| `svea` s1 | 234.36 | **59.7%** | **0.428** | [0.319, 0.568] | **9/10** | 50.0% → 19.5% | 5.4% |

**The ranking inverts.** On the scene it trained on, `svea` is **last** — 53% of `drqv2`'s return.
On both retention axes it is **first by a wide margin**, and it is the only one of the three that
learned something on nine of ten scenes rather than three. **A results table reporting
train-regime return would have ranked these three exactly backwards**, which is the concrete case
for the retention endpoint that [`RESEARCH-FRAME.md`](RESEARCH-FRAME.md) argues for structurally.

**The two retention axes disagree, and that is reported rather than smoothed.** Scene retention
orders `svea` > `drqv2` > `drq`; regime retention orders `svea` > `drq` > `drqv2`. `drqv2` retains
better across *scenes* than `drq` and worse across the *visual regime*. They are different
manipulations — geometry-and-texture versus texture-and-lighting — and nothing in this project
established they should agree. Averaging them into one "generalization" number would manufacture
an ordering neither axis supports.

**Honest limits, and they are the same size as the result.**
- **One seed per arm.** Between-seed variance is unmeasured. The `res. floor` column bounds
  *placement* noise within a checkpoint, not the spread across checkpoints, and `drq`'s is
  **23.6%** — five times the other two — so its row is the least resolved of the three even though
  its 94.9% regime gap clears it.
- **Rows pool over different scene sets** — 3, 3 and 9 — because each pools only where its own
  denominator clears the floor and the 25% rule ([C55](#c55)). `svea`'s number is an average over
  nine scenes and `drqv2`'s over three; they are not the same statistic, which is why `usable` is a
  column and not a footnote.
- **`svea` at 50k is REFUSED**, not zero: 0/10 scenes clear the rule, and its seed-only control
  (37.8%) nearly equals its scene gap. An absence of retention, not a small one.
- **`drq` has no 50k pair** ([C84](#c84)) — the preserver was not attached — so the budget trend
  established for `drqv2` (retention *falls* 0.019 → 0.003) has one arm, not three.
- One task, one budget. 100k frames is far below RL-ViGen's own Door budget of 6e5, and nothing
  here says the ordering survives to convergence.

**Why these three may be compared at all.** All are RL-ViGen natives; the seam audit splits on
**0 of 12 axes within the five** and their hydra configs are identical on every shared key. The
one exception is `nstep` — `drq` runs 1 against 3, which is DrQ's own published value (RL-ViGen
Table 2), a property of the method rather than a porting artifact. So the collinearity that makes
across-method comparison weakly identified across the twelve does not apply here, and `drqv2` vs
`svea` is the cleanest pair of the three.

**Decision** none — a measurement, and the first the project can put in front of anyone.
**What would show it wrong** a second seed of any arm landing outside another's interval, or the
inversion disappearing at a larger budget. Both are affordable relative to what has been spent.

### C87 — The first same-quantity comparison with RL-ViGen's published table, and the ordering reproduces {#c87}
**Class** OURS · **Status** MONITORED · **Cross-ref** [C31](#c31), [C37](#c37), [C45](#c45), [C47](#c47), [C48](#c48), [C62](#c62), [C86](#c86)

[C45](#c45)/[C47](#c47) established that every previous comparison to RL-ViGen's table compared
**different quantities**: ours was a scene-0 figure, theirs is a mean over ten scenes.
[C37](#c37) was rewritten twice explaining a 130× gap that turned out not to be a gap between
comparable things. **`scripts/eval_across_scenes.py` now sweeps ten scenes**, so the same
construction is computable for the first time.

Their Door Easy, 5 seeds, ten scenes (`results/evaluation_score.xlsx`, read by
`scripts/rlvigen_reference.py`, [C31](#c31)) against ours at 100k, one seed:

| method | ours, 10-scene `eval-easy` | published | ratio | ours ÷ floor | theirs ÷ floor |
|---|---|---|---|---|---|
| `drqv2` | 15.83 | 3.6 | 4.40× | 8.7× | **2.0×** |
| `drq` | 16.24 | **14.0** | **1.16×** | 9.0× | 7.7× |
| `svea` | 64.09 | 268.8 | 0.24× | 35× | 148× |

**The published ordering reproduces exactly: `svea` > `drq` > `drqv2`.**

**What this is NOT.** It is **not** a reproduction by [C48](#c48)'s bar, and C48 stays OPEN. C48
asks for *their evaluation path* run on a policy, landing on one of their cells; this runs **our**
evaluator. Two evaluators agreeing on a quantity is a different claim from one reproducing the
other's number, and that distinction is exactly what C48 exists to keep.

**And the ordering match is weaker evidence than it looks.** With three methods a random ordering
matches with probability **1/6 ≈ 17%**. On its own that is suggestive, not conclusive. What
strengthens it is the magnitudes: `drq` lands within **16%** of the published value at **one-sixth
the budget with one seed instead of five**, which a coincidence would not have to do.

**The reading that makes the ratios coherent, and it is not flattering to the benchmark.** Their
published `DrQ-v2` at 3.6 is **twice the random floor** of 1.81, and their `DrQ` at 14.0 is 7.7×;
Door's shaping alone pays up to 250 without the door ever opening ([C62](#c62)). **So two of
RL-ViGen's own five natives essentially do not solve Door Easy in their hands either.** Our runs at
1/6 the budget already exceed both — not because our implementation is better, but because those
published cells sit near a floor that is easy to clear. `svea` is the one with real headroom, and
there we are at 24% of their value, which is what a sixth of the budget should look like.

**So the honest summary is three claims of different strength**: the ordering reproduces (weak
alone, 1-in-6 by chance); `drq`'s magnitude is close (stronger, and unexpected at this budget);
and their `DrQ-v2`/`DrQ` cells are near-floor measurements (strong, and it reframes what
"reproducing" them would even mean).

**Decision** none. **What would show this wrong** a second seed moving any of the three orderings,
or their evaluator run on our policy landing far from our figure — the latter being
[C48](#c48)'s actual test, which this does not perform and does not replace.

### C88 — Scene difficulty is method-dependent: the two DrQ-family arms agree, `svea` agrees with neither {#c88}
**Class** OURS · **Status** MONITORED · **Cross-ref** [C46](#c46), [C72](#c72), [C76](#c76), [C86](#c86), [RESEARCH-FRAME.md](RESEARCH-FRAME.md)

Per-scene train-regime return at 100k, ranked within each baseline, compared by Spearman:

| pair | ρ (n = 10) | reading |
|---|---|---|
| `drqv2` vs `drq` | **+0.758** | above the n=10 critical value (~0.648 at p<0.05) — **supported** |
| `drqv2` vs `svea` | +0.152 | not distinguishable from zero |
| `drq` vs `svea` | +0.212 | not distinguishable from zero |

**The two DrQ-family arms fail on the same scenes; `svea` does not.** The individual cells are
stark — scene 6: `svea` **259.8** against 34.0 and 37.1; scene 8: `svea` **162.7** against 0.8 and
7.3. Scene 7 is hard for all three (9.4 / 3.6 / 3.1), and scene 0, the trained one, is high for all
three, so the disagreement is not an artefact of the easy and hard extremes.

**So the scene axis is not a property of the scenes alone — it interacts with the method.** That is
the finding, and it is not what [C46](#c46) could have shown: C46 measured that scenes 1–9 separate
from scene 0 **in observation space**, which is a statement about the renderer. This is a statement
about which of those separations a given method survives, and the answer differs by method.

**Why it matters for [P-C76](RESEARCH-FRAME.md), the open endpoint decision.** If scene difficulty
were method-independent, averaging over ten scenes would be a clean marginalisation — every arm
would face the same distribution of difficulty and the mean would be comparable by construction.
**It is not.** Which scenes an arm can solve is part of what distinguishes the arms, so the choice
of scene set is not neutral between them, and the fact that
[C86](#c86)'s rows already pool over **different** scene sets (3, 3 and 9 usable) is a symptom of
this rather than an accident of thresholds.

This does not settle P-C76 — it makes option 2 (retire the scene axis, report the regime gap at
`scene_id=0` only) more costly than it looked, because scene 0 is the one scene all three arms
handle well and is therefore the least discriminating single choice available.

**Honest limits.** One seed per arm, so each ranking is a single draw and ρ carries the noise of
that. With n = 10 scenes the estimate is coarse: +0.758 clears the critical value, but +0.152 and
+0.212 being non-significant is **not** evidence of independence — it is an absence of evidence for
correlation, and three arms is far too few to claim a family effect. The natural reading — that
augmentation changes *which* visual variations are survivable, not merely how many — is a
hypothesis this cannot test with `svea` as the only augmentation arm.

**Decision** none. **What would show it wrong** a second seed reordering either DrQ-family arm's
scene ranking, or `soda`/`rad` (the other augmentation methods) correlating with `drqv2` rather
than with `svea` — which would make this an arm-specific quirk rather than a family property.

### C89 — Under the visual shift the TRAINED scene becomes the worst one, in all three arms {#c89}
**Class** OURS · **Status** MONITORED · **Cross-ref** [C19](#c19), [C46](#c46), [C72](#c72), [C81](#c81), [C86](#c86), [C88](#c88)

The ratio of held-out scenes to the trained scene **inverts** between regimes, and it does so for
every arm measured:

| held-out ÷ scene 0 | `drqv2` | `drq` | `svea` |
|---|---|---|---|
| `train` regime | 0.23× | 0.13× | 0.60× |
| `eval-easy` regime | **14.3×** | **17.4×** | **53.1×** |

Under `train`, scene 0 is the best scene, as it must be — it is the one that was trained on. Under
`eval-easy` it is the **worst**, by more than an order of magnitude, in all three.

**Against the random floor** (1.81, 95% CI [1.58, 2.06], n = 200), scene 0 under `eval-easy`:

| | mean | 95% CI | verdict |
|---|---|---|---|
| `drq` | 1.03 | [0.77, 1.37] | **below the floor** — intervals do not overlap |
| `drqv2` | 1.22 | [0.82, 1.79] | indistinguishable from random |
| `svea` | 1.34 | [0.93, 1.81] | indistinguishable from random |

So *"worse than a random policy"* is established for `drq` alone; for the other two the honest
statement is *"at chance"*. **The inversion is the robust part**, and it does not depend on the
floor comparison at all.

**The reading, held as a hypothesis.** A policy that has learned scene-0-specific visual features
is *confidently wrong* when those features are altered, while on scenes it never learned features
for it retains whatever general competence it has — reaching toward the handle region — and scores
above chance. It is a mechanism this project cannot test with the runs it has; a policy-behaviour
probe under the shifted trained scene would be needed, and nothing here is that.

**The consequence for [P-C76](RESEARCH-FRAME.md), and it is the sharpest yet.** All seven
non-native evaluators build their env with `scene_id=0` ([C72](#c72)) — so **the regime gap they
would report is measured on the single scene where the shift is most destructive.** That is not a
representative sample of the shift; it is systematically its worst case, by 14–53× in these three
arms. P-C76's **option 2** — retire the scene axis and report the regime gap at `scene_id=0`, the
cheapest option and the one every baseline can already produce — would therefore standardise on
the most pessimistic and least representative measurement available. Together with
[C88](#c88) (scene 0 is also the one scene all three arms handle well under `train`, hence the
least discriminating), option 2 now looks considerably worse than when it was written, and this
entry exists so that the decision is taken with that in front of it.

**Honest limits.** One seed per arm. Three arms, and two of them are DrQ-family, so "all three"
is really "two families". The 14–53× spread is itself large — `svea`'s 53× against `drqv2`'s 14×
is not a detail, and with one seed each nothing here separates a method effect from a draw.

**Decision** none. **What would show it wrong** an arm whose trained scene is *not* the worst under
`eval-easy`, or the effect vanishing at a larger budget — the latter being plausible, since a
better-trained policy might hold features that survive the shift.

### C90 — A test polluted `sys.modules` and broke 25 others; re-running the file alone said "fine" {#c90}
**Class** OURS · **Status** RESOLVED · **Cross-ref** [C56](#c56), [C85](#c85), [ASSURANCE.md](ASSURANCE.md)

`tests/test_eval_loop_measurement.py` — written 2026-08-29 to close the gap that the evaluator's
**measurement** loop was untested — injects fake `wrappers`, `wrappers.robo_wrapper` and `utils`
modules into `sys.modules` so `run_scene`'s function-level imports resolve to a stub. **It never
removed them.** Every later test that built a real environment got the stub: all 25 of
`tests/test_real_env.py` failed with `ContractError: the env did not report a regime`. `e` sorts
before `r`, so the pollution always reached them.

**The diagnosis was wrong twice before it was right, and both wrong turns are instructive.**

1. **"Contention with the live training run."** Plausible — the failing tests are exactly the ones
   that construct a real robosuite env, and [C56](#c56) already records that two robosuite envs do
   not render independently. It was recorded as a *hypothesis*, explicitly not established, which
   is the only part of this that went right.
2. **Re-running the file alone, which passed — and that is the trap.** 25/25 green in isolation
   reads as "fine, it was environmental". **It is exactly the wrong check for this failure class**:
   a test that pollutes global state for its successors is *green in isolation and red in company*
   by construction. The per-file re-run cannot see the bug and actively argues against looking
   further.

What settled it was re-running the **whole suite** and finding the failure reproduce with a
training run live — the same condition under which the single file had just passed. Same
condition, different result, so the condition was not the cause.

**Worse than the incident: it would have been intermittent.** `pytest-randomly` is installed, so the
suite normally runs in **random order**. This session used `-p no:randomly` throughout, which is the
only reason the failure was deterministic and therefore findable. Under the default ordering it
would appear and vanish between runs — the shape that gets filed as flakiness and never fixed.

**Decision** an `autouse` fixture saves and restores the four `sys.modules` keys around every test
in that file (`176a7013`). **Effect** the 25 `ContractError` failures are gone. **What would show
this wrong** any other
test that writes to `sys.modules`, `os.environ` or the working directory without restoring it —
this file was the first, it is unlikely to be the last, and nothing currently checks for it.

**The generalisable rule, and it is not "restore your fixtures".** It is: **a failure that
disappears when you narrow the scope is evidence about the scope, not an all-clear.** Narrowing is
the natural next step and it is the one that lies here. The honest move on seeing a file pass alone
after failing in company is to widen — run the suite again, in the same conditions — not to
conclude the environment did it.

### C91 — The grep I used to report suite status can never match, so it always said "green" {#c91}
**Class** OURS · **Status** RESOLVED · **Cross-ref** [C90](#c90), [C80](#c80), [ASSURANCE.md](ASSURANCE.md)

Throughout this session I reported the suite's state with

```
pytest ... > log; echo "exit=$?"
grep -cE "^FAILED|^ERROR" log
```

and read a `0` from the second line as "no failures". **It is `0` unconditionally.** pytest
colourises the summary, so the bytes on disk are `\033[31mFAILED\033[0m tests/...` — the line does
not *start* with `FAILED`, and `^FAILED` cannot match. Verified with `od -c`. On the run that
exposed it: `grep -c "^FAILED"` → **0**, `grep -c "FAILED"` → **2**.

**This is the [C80](#c80) shape again and it is the worst version of it** — not a check that is
weak, a check that **cannot fail**. It reports success on a green suite and on a red one, so every
reading of it was uninformative, and the fact that it kept agreeing with reality was luck plus the
exit code sitting next to it.

**What saved it:** `echo "exit=$?"` was always printed alongside, and pytest's exit code is
authoritative. On the run in question `exit=1` contradicted the grep's `0`, which is the only
reason the two remaining failures were seen at all. **Had I printed only the grep — which reads as
the more informative of the two — I would have reported green on a red suite, which is exactly the
process failure that produced `2fdc161f`.**

**Decision** the exit code is the verdict; any grep over pytest output that needs to match must use
`--color=no` or match without the anchor (`grep -c "FAILED"`). Recorded here rather than fixed in
one place because the defect is in a shell idiom I retype, not in a committed file (`176a7013`
carries the record). **Effect** re-running the suite with `--color=no` immediately showed **three**
failures where the broken grep had reported none — one of them ([C93](#c93)) previously unseen this
session. **What would show this wrong** nothing — it is verified at the byte level.

**The generalisable rule.** *A check whose failing branch has never been observed is not yet known
to have one.* This grep printed `0` perhaps twenty times and was never once seen printing anything
else; that unbroken agreement felt like evidence and was its own refutation. The same test the
project already applies to its instruments — construct an input that makes it red — applies to
throwaway shell one-liners used to make claims, and this one had never had it applied.

### C92 — `linalg_qr: MPS kernel failed` in the nd_ln test: intermittent, cause not established {#c92}
**Class** OURS · **Status** MONITORED · **Cross-ref** [C56](#c56), [C90](#c90), [`docs/local-envs.md`](../../../docs/local-envs.md)

`tests/test_nd_ln_style_train.py::test_end_to_end_on_the_synthetic_backend_produces_a_real_episodes_csv`
failed with `RuntimeError: linalg_qr: MPS kernel failed with error code 0` on the full-suite run of
2026-08-29, with a `drqv2` seed-8 training run live. **Re-running that file alone, with the same
training run still live, passed.**

**That isolation pass proves less than it looks like, and [C90](#c90) is why.** Narrowing the scope
is the move that lies for a whole class of failures. What it does establish here is narrower and
still useful: **the live training run alone is not sufficient** to produce the failure, since the
file passed while it was running. So the cause is either the suite's *own* additional MPS load on
top of the run, or genuine nondeterminism in Apple's `linalg_qr` kernel under memory pressure —
and this project has no instrument that separates those.

**Not resolved, deliberately.** One observation, one non-reproduction. Calling it a flake would be
asserting the thing that has not been shown.

**What to do when it recurs:** record the run's swap and free memory at the time (this machine has
been driven to 0.1 GB free by three rendering jobs — see [`docs/local-envs.md`](../../../docs/local-envs.md)),
and re-run the full suite with **no** training job active. If it never appears with the machine
quiet, it is contention and belongs in `local-envs.md` as an operational rule: *the suite is not a
valid gate while a run is live.* If it appears on a quiet machine, it is the kernel.

**Why it matters beyond one test:** if it is contention, then a green suite obtained during a run
is not evidence, and this session ran the suite during a run repeatedly.

### C93 — greenmark's tree id is unstable while a run is live, so a stamp taken then is void {#c93}
**Class** OURS · **Status** OPEN · **Cross-ref** [C90](#c90), [C91](#c91), [C92](#c92)

`scripts/greenmark.py`'s `tree_id()` runs `git add -A` into a scratch index and hashes the result.
`-A` includes **untracked** paths, and the live `drqv2` run writes into `results/cell-…/`
continuously (`train.csv`, `eval.csv`, snapshots). So two calls three seconds apart return
different ids:

```
5d9a85bd6185fa0c
d0a6e779e2a342f8   UNSTABLE
```

`tests/test_greenmark.py::TestTreeIdentity::test_stable_when_nothing_changes` and
`test_changes_when_a_file_changes` both fail on this. **Both are true positives.** The tree is not
stable; the tests say so correctly. What is violated is an unstated **precondition** — that the
working tree is quiet — and nothing anywhere declares it.

**The consequence is the part that matters.** greenmark exists to answer *"is this green stamp
still valid, or has the code changed under it?"* While a run is live the id changes every few
seconds, so **any stamp taken during a run is invalid before it is written.** Every greenmark stamp
taken this week was taken during a run.

**The inconsistency inside the instrument.** `pending_changes()` and `--why` already distinguish
code from not-code via `CODE_PREFIXES` — that distinction exists precisely because a docs edit
should not invalidate a green stamp. `tree_id()` honours no such distinction: it hashes everything,
so a *results* file appearing invalidates a stamp about *code*. The two halves of the same file
disagree about what a tree identity is for.

**Options** — this is the owner's call because each changes what an existing stamp means, and
[C82](#c82)'s lesson is that I should not quietly re-scope a thing whose consumers I have not
enumerated:

1. **Scope `tree_id()` to `CODE_PREFIXES`**, matching `pending_changes()`. Stamps then survive a
   run and mean "the code is unchanged". Cost: every stamp taken under the old semantics meant
   something stricter, so they are not comparable across the change — and a data-only change that
   genuinely should invalidate a result would stop doing so.
2. **Declare the precondition and enforce it** — the suite refuses to run, or these tests skip,
   while `results/cell-*` is being written. Keeps stamp semantics exactly as they are; costs the
   ability to run the suite during a run, which is most of this week.
3. **Leave it and document it.** Stamps are only valid on a quiet machine. Cheapest, and it makes
   the instrument useless in exactly the conditions it is most wanted.

**Not chosen here.** I can trace option 1's effect on `greenmark.py` but not on every artifact that
already carries a stamp, and the register's own rule is that a change whose effect is not traced in
full does not get made.

**What would show the diagnosis wrong** `tree_id()` returning a stable value twice in a row on a
machine with a run writing into `results/`. Checked: it does not.

**The third failure this session traceable to one cause.** [C90](#c90) (real-env tests), [C92](#c92)
(MPS kernel) and this one all appeared while a training run was live. C90 turned out to be mine and
unrelated; C92 is unresolved; this one is fully traced. The common thread — **the suite has never
been run on a quiet machine this week, and it is not known to be a valid gate under load** — is now
the single most load-bearing unverified assumption about the project's own quality control.

### C94 — greenmark cannot see the patched upstream, and the test that pins that defect tests the wrong layer {#c94}
**Class** OURS · **Status** OPEN · **Cross-ref** [C91](#c91), [C93](#c93), [C80](#c80), [`setup/VENDORED.md`](../setup/VENDORED.md)

`tests/test_greenmark.py`'s own docstring records this defect as **fixed**: *"`RL-ViGen-upstream/`
and `setup/` classified as not-code … `--why` said 'docs-only, no run needed' for a change to the
environment itself."* The fix added `"RL-ViGen-upstream/"` to `CODE_PREFIXES`.

**The prefix can never match. The defect is still live.** Verified, each link:

| # | link | check |
|---|---|---|
| 1 | the whole vendored tree is gitignored | `.gitignore:2:/RL-ViGen-upstream/`; `git ls-files RL-ViGen-upstream` → **0** |
| 2 | `pending_changes()` reads `git status --porcelain`, which never lists ignored paths | appended a line to `RL-ViGen-upstream/train.py`: visible **False**, classified-as-code **False** |
| 3 | the string classifier is nonetheless correct | `"RL-ViGen-upstream/train.py".startswith(CODE_PREFIXES)` → **True** |
| 4 | so with an upstream-only edit `files == []` and `--why` prints **"no pending changes"** | `scripts/greenmark.py` `main()`, the `elif not code` branch is not even reached |
| 5 | `tree_id()` does not move either — `git add -A` does not stage ignored paths | [C93](#c93)'s probe |

**Why the test passes anyway, and this is the transferable part.** `TestWhatCountsAsCode`
parametrizes over the **string** `"RL-ViGen-upstream/train.py"` and asserts it starts with a
`CODE_PREFIXES` entry. That is link 3 — the one link that works. The test never constructs a file in
an ignored path and never calls `pending_changes()`, so it exercises the classifier in isolation
from the pipeline that feeds it. **A green test, a correct assertion, and a defect that the test was
written specifically to pin, all at once.** This is [C91](#c91) one layer up: not a check that
cannot fail, but a check aimed at the layer that was never broken.

**The coverage that exists is circular.** `setup/apply_patches.py --check` diffs the **whole**
vendored tree against pinned commit `90d8b8c4`, which is exactly the right instrument — it exists
because P5 *"spent weeks as an undeclared hand-edit"*. It passes today (`exit=0`, *"matches its
pinned commit plus exactly the declared differences"*). But it is invoked **only** from
`tests/test_contract.py:391,408` — `grep` finds no caller under `scripts/`. So:

> an upstream-only edit → greenmark reports "no pending changes" → the suite is skipped → the one
> instrument that would catch the edit never runs.

The guard against the P5 scenario is disarmed by the advisor, in precisely the scenario it was
built for.

**Honest bound on severity.** The hole needs the upstream edit to be the **only** change; any
concurrent tracked-file edit sends you to the suite anyway, and `--check` then fires. No drift
exists today. This is a latent gate defect, not a live corruption — but P5 shows the scenario is the
realistic one, because a hand-edit to the vendored tree is exactly what nobody commits alongside.

**Options** (owner's call; none taken, per the rule about untraced effects):

1. **Make `pending_changes()` consult the vendored tree** — run `apply_patches.py --check`, or hash
   the tree, and report drift as a code change. Correct at the source; costs `--why` a
   multi-second subprocess on every call, which is most of the latency `--why` exists to save.
2. **Wire `--check` into a pre-suite gate that runs regardless of greenmark's advice.** Breaks the
   circularity without touching `--why`'s speed. Cheapest defensible fix.
3. **Un-ignore the vendored tree.** Makes everything visible; adds a large third-party tree to the
   repository, which `VENDORED.md`'s pinned-commit design deliberately avoids.
4. **Fix the test to exercise the pipeline rather than the string.** Does not close the hole, but
   stops the suite from asserting coverage it does not have. Done here as an `xfail(strict=True)`
   so the gap is mechanically visible and the test turns loud the moment someone closes it.

**What would show this wrong** `pending_changes()` returning a path under `RL-ViGen-upstream/` after
an edit there. Checked directly: it does not.

### C95 — A container-trained checkpoint may not be evaluated on this laptop {#c95}
**Class** OURS · **Status** OPEN · **Cross-ref** [C41](#c41), [C69](#c69), [C70](#c70), [`REGISTER.md`](REGISTER.md), [`INTEGRATION-DELTA.md`](INTEGRATION-DELTA.md)

**The rule.** Any number describing how a policy *performs* — a return, a success rate, a retention
ratio — must be produced on the machine that trained it. Local offline evaluation of a
container-trained checkpoint is not a weaker measurement of the same quantity; it is a measurement
of a different one.

**The evidence, all on one 60k `drqv2` snapshot at eval-easy / scene 0 / twenty episodes:**

| where | code | result |
|---|---|---|
| container, in-process | RL-ViGen's own `eval()` | **41.66**, and **50.73** in a second job |
| laptop | RL-ViGen's own `_eval_regime`, unmodified | **3.41** |
| laptop | our `scripts/eval_grid.py` | **2.94** |

**The control that mattered was running upstream's own loop locally.** Before that, the defect had
been "our harness disagrees with the trainer", and the standing exclusion was that two independent
offline paths agreed to two decimal places — but both paths were ours, so that showed only that
they agreed with each other. Upstream's `_eval_regime`, executed unmodified against a `Workspace`
allocated without `__init__`, fails here exactly as ours does. **The evaluator is exonerated and
the machine is the variable.**

**Two candidates remain and one job separates them**: device (container CUDA against local
CPU/MPS) and render backend (`MUJOCO_GL=egl` against macOS `glfw`). The renderer is the stronger
prior, because these are *vision* policies and a different rasteriser puts every observation
slightly out of distribution — which predicts the single pattern the whole investigation kept
reproducing, that **the damage scales with how much policy there is to damage**: an untrained 6k
agent reproduces, `idaac` at 1.5 and `dmc_gb` at 7 reproduce, and the gap grows 6.5× → 60× → 670×
as the policy improves from 60k to 100k. It also explains why swapping CPU for MPS moved the number
(20.95 → 8.58) without recovering it: both render through GLFW.

**What this does and does not invalidate.** It does **not** touch the training runs — RL-ViGen
genuinely reaches 456.06 with `train_regime_success 1.0` at 100k, produced and re-measured inside
the container. It **does** invalidate every offline generalisation number this project computed
locally from a container-trained checkpoint, R7/C43 included. `OFFLINE_EVAL` in
`datasphere/native/run_probe.sh` exists to recompute them where they belong.

**Options** (the rule is already in force; what is open is how far to go, and it is the owner's call
because each costs compute rather than correctness):

1. **Recompute only what gets reported.** Re-run the grid on the container for the checkpoints that
   appear in a result, and leave the rest. Cheapest; leaves a tree of local numbers that are void
   but still readable, which is how a wrong number gets quoted a month later.
2. **Recompute everything and delete the local numbers.** Honest and expensive, and it discards
   measurements that are still valid *as* local measurements — a local-vs-local comparison between
   two checkpoints is not affected by a constant platform offset, if the offset is constant.
3. **Recompute everything, keep the local numbers, and mark them.** Preferred by me, and **its
   mechanism is now built**: `normalize_curves.record()` stamps `native.recorded_on` with host,
   system, machine and `MUJOCO_GL`, so a record produced by a local evaluation is mechanically
   identifiable — `mujoco_gl: "glfw"` is the tell — instead of being a matter of memory. It sits in
   `native` rather than at the top level so the schema stays 2 and every existing reader keeps
   working. **What is built is the marking, not the recomputation**, and the field carries an
   explicit caveat in its docstring: it describes the process that *wrote* the record, which is the
   process that *measured* only when the two are the same, as in `eval_grid.py`. Running
   `normalize_curves` here over a fetched result archive stamps this laptop onto numbers the
   container measured. Records written before today carry no stamp at all and must be treated as
   local until shown otherwise.
4. **Establish the offset and correct for it.** Tempting and wrong: [C41](#c41) is the reason — a
   perturbed action changes the transition and therefore everything after it, so the discrepancy is
   not a scale factor that can be divided out. Recorded to be refused explicitly rather than
   re-proposed later.

**ANSWERED, 2026-09-03 — the device is exonerated and the renderer is the cause** (`bt1a4gsqf1h3sd5u72tl`).
The same grid, the same 60k snapshot, run twice inside one container:

| pass | eval-easy | train |
|---|---|---|
| container, CUDA | 45.16 | **131.54** |
| container, CPU | 39.90 | **131.57** |
| this laptop, CPU | 2.94 | **13.85** |

The two container passes agree to three significant figures on the train regime, so CUDA-versus-CPU
explains **nothing**. A container CPU reads 131.57 where this laptop's CPU reads 13.85, and what
separates them is `MUJOCO_GL=egl` from macOS `glfw`. **The prediction in the entry above was the
right one and it was tested rather than assumed.**

**The same number also validates the evaluator against the training loop.** 131.57 reproduces the
run's own logged `train_regime_reward` of **135.71** at frame 60000 — twenty episodes here against
its two. `scripts/eval_grid.py` was correct throughout; it was being run on a machine that renders
different pixels than the one that trained the policy. The whole "checkpoint does not carry the
policy" investigation was chasing a rasteriser.

**Option 4 is now refused on evidence rather than on principle.** The measured damage is not a
scale factor: on the ten-scene grid the same policy reads 386.1 on scene 0, 210.3 on scene 2, and
0.7 on scene 3. A per-scene, policy-dependent collapse cannot be divided out, and any "correction
factor" would be fitting noise.

**Status of the mitigation.** Option 3's marking is built (`native.recorded_on`). Option 1's
recomputation is what remains, and `OFFLINE_EVAL` is the instrument — proven twice today. The rule
stands unchanged and is now explained rather than merely observed.

**What would show this wrong** A local run reaching container numbers on any configuration, or a
container run reproducing the laptop's numbers under EGL. The device leg is closed: two devices,
one platform, same answer.

### C96 — The shared-evaluator ledger certified neither the code that acted nor a stable scope {#c96}
**Class** OURS + FALSE-CERTIFICATION · **Status** READY · **Cross-ref** [C76](#c76), [C95](#c95), [`EVAL-PROTOCOL.md`](EVAL-PROTOCOL.md), [`REGISTER.md`](REGISTER.md)

The former evaluator identity was a single global hash. It included all of
`setup/apply_patches.py`, although a checkpoint-only evaluation never imports a training-time
checkpoint-writing edit; it did not include the family-specific runtime modules that make a
checkpoint act. Thus the same field could make evidence stale for an irrelevant edit and remain
unchanged after a relevant one. It could not honestly certify the claimed property.

The two direct controls are deliberately asymmetric. In a temporary copy, changing
`runnable/ibac_sni/torch_rl/scripts/train.py` leaves IBAC-SNI's evaluator revision unchanged:
that driver is not on the offline action path. Changing
`runnable/ctrl/vec_env.py` moves CTRL's revision and no other family's. The first catches the
over-broad half; the second catches the blind half. Both are pinned by
`tests/test_family_evaluator_revision.py`; `tests/test_payload_contract_covers_provenance.py`
also makes every statically declared runtime member reach the matching evaluation payload (or the
separately declared RL-ViGen source archive).

**Decision** The ledger now carries a family-specific static runtime closure and configuration
revision, while each emitted row carries the resolved canonical `evaluator_scope`, its
`evaluator_scope_revision`, and the combined `evaluator_measurement_revision`. These distinctions
are implemented and locally tested; static payload closure/configuration identity is for payload
proof, and measurement revision is for analysis and pooling. A pinned RL-ViGen archive can be
compared with the deterministic post-patch closure even when `apply_patches.py --check` abstains
because the extracted tree has no nested Git repository. That abstention remains a source-lineage
limitation, not a failure of evaluator equality when the archive and post-patch closure match.

The evaluation process also captures a dynamic import manifest, and
`scripts/production_gates.py` requires it to be reviewed. It is observed evidence, not a static
proof: a dynamic import path or pickle-created object can still expose an unlisted local module.

The live gate additionally requires a human-reviewed records artifact and SHA256 binding. It
accepts `validation_kind: functional_endpoint` with a deliberately shallow canonical endpoint
scope; that proves evaluator-path functionality, not final production-report depth. The gate checks
that applicable offline rows agree with the ledger identity, but mechanics do not establish that
the job, source archive, or environment was honest.

**Effect** All earlier shared-evaluator discharges are historic measurements under a superseded
identity, not current evidence. The live gate therefore starts at 0/7 evaluator families rather
than carrying forward a plausible-but-unlicensed 2/12. This is not a statement that the old
numbers are false; it is a statement that they no longer establish the current evaluator's
equivalence. The new identity path is locally tested, but no family has yet been remotely
validated against the current closure.

**What remains** Re-run each family against its native evaluator on the current payload, inspect
the emitted import manifest, and record the paired result. This needs a bounded container slot,
not an owner choice; the endpoint protocol remains blocked on those discharges.

## Working agreement

1. **New items enter here first**, with a class and a status, before they are written up anywhere
   else.
2. **`OPEN` items are decided in batches at gates, not continuously.** The gate that matters is
   *before the first expensive run*: deciding C1–C4 after seeing which choice flatters a baseline
   is a garden of forking paths.
3. **An entry is not `RESOLVED` until the effect is recorded**, including "we did it and nothing
   changed" — which is a result and is routinely lost.
4. **Every `RESOLVED` item names its commit**, so the claim can be checked against the diff.
5. Structure is pinned by `tests/test_construction_register.py`. If that test fails, the register
   drifted from its own rules — fix the register, not the test.
