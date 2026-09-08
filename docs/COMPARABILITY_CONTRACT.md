# The comparability contract

> **Added 2026-08-17: the open "emission inventory" item is now done, elsewhere.**
> `docs/PART2-METRIC-INVENTORY.md` carries the per-baseline account of what is emitted and against
> what, with six findings — including two the contract below does not anticipate: frame stacking
> split the twelve **8/4 when this was written**, then 9/3, then 10/2, and is now **12/0**
> (A40 REVISED-2, 2026-09-08; `rlgen/protocol.py:118-132`) — so `Protocol.frame_stack` no
> longer certifies a value any run lacks — and the action distribution comes in three
> families, not one. Read that first; this file is the
> older framing.


> # ⚠ §1–§10 DESCRIBE THE RETIRED `rlgen/` PORT — read this before relying on them
>
> **Amended 2026-08-26, carrying its case.** This file's "seam" half rests on one sentence, §1's
> *"Every baseline's environment interaction, training and eval alike, goes through
> `rlgen/envs.py`'s construction path"*, and everything from §1 to §10 is built on it — the
> choke-point grep, the three-layer action clipping, the four adapter classes, the checkpoint
> schema, the mutation tests. **`rlgen/` was superseded as the null on 2026-08-17**, when the
> approach became "the original repository, cloned, running its own `train.py`". There is now **no
> single construction path**: each clone builds its own env, and the twelve adapters do not exist.
> The file carries **31 references to `rlgen/`** and, until this note, not one marker saying so.
>
> **What this costs, precisely.** The head of this file (the vocabulary half, 2026-08-16/17) says
> *"§1–§10 establish that every baseline is measured the same way… that is the seam"* and then
> reasons from it. That reasoning is now unsupported: the seam it cites was a property of a shared
> harness this project deliberately removed. **The vocabulary half still stands on its own** — the
> coverage classes, the reconciliation axes, the `ctrl`/`ibac_sni` entropy worked example, the
> "same name with different definitions is worse than different names" stance are about *what may
> be compared*, and none of them depends on `rlgen/`.
>
> **Why this matters more than it did yesterday.** [`TASK.md`](TASK.md) R3 was relaxed on
> 2026-08-26 from *identical evaluation code* to *metrics on the same axes*, and **this document was
> named as the one that carries the new burden**. Half of it cannot: the per-baseline audit it
> would supply is an audit of an architecture that no longer runs. So R3's evidence base is not
> "incomplete", it is **partly void**, and the owner's grading of R3 as *still NOT MET* is correct
> for a stronger reason than the one recorded there.
>
> **Do not delete §1–§10.** They are the record of how the seam was established once, and
> [C30](CONSTRUCTION.md#c30) already tracks "contract enforced against the superseded port, not the
> clones" as an open item — this note is that entry's evidence, not a replacement for it. What is
> needed is a clone-era seam audit, which does not exist.

What makes the 12 baselines' reported metrics sit on the same axis — **not** "do their training
internals match" (they don't need to, and mostly don't).

**Two questions, and this document originally answered only the first.** §1–§10 establish that
every baseline is *measured* the same way: one env construction path, one evaluator, one x-axis.
That is the **seam**. The head of the file, below, establishes the other half — whether the number
that comes out is the same **quantity** — which is a property of the reported vocabulary, not of
the plumbing. Both are required and neither implies the other: twelve baselines can go through an
identical evaluator and still report four different things under four different names.

*(§0's pointer to a plan file is stale — that file has since been overwritten for unrelated work.
The provenance note itself still stands.)*

---

## Context, definitions, stance for the reported-metric axis  ·  [DURABLE]

Read before the sections below. They check a seam; this decides what may travel through it.

### Context

**Almost nothing in this layer has a reference to be faithful to.** Every paper measures its own
thing on its own benchmark, so the *cross-algorithm* vocabulary is authored here and cannot
inherit correctness from the porting work however good the ports get. One real exception, stated
because an absolute claim here would be wrong: the **eval protocol** does have a reference —
RL-ViGen's own `eval.py::robo_eval`, which this project's evaluator is checked against
(`VALIDATION.md` §0.05). So the seam has an anchor; the vocabulary does not.

And it is **joint**: a metric axis is a property of the set, never of a member, so no baseline can
be declared metric-ready on its own.

### Definitions

- **Quantity** — what is measured, defined without reference to any algorithm, carrying a unit, an
  origin, and a multiplicity. *"Episodic return under the eval protocol"* is a quantity;
  `Loss/pi` is a name.
- **Emission** — a (name, quantity, definition) triple that some baseline actually produces. What
  the code emits, not what a document says it emits.
- **Coverage class** — the property that decides what a quantity may be *used* for:
  - **Universal** — all twelve can emit it under an identical definition. Comparison-bearing.
  - **Subfamily** — only a subset can, where the subset is fixed by a *structural* property of the
    algorithm class (on-policy vs off-policy), never by who happened to implement what.
    Comparison-bearing **within** the subfamily; the boundary is declared, not inferred.
  - **Singleton** — one baseline only (IDAAC's order-pair accuracy, CTRL's cluster entropy).
    Diagnostic, never comparison-bearing, and legitimate as such.
  - **Accidental** — varies across baselines for no principled reason. **The defect class.**
- **Caveat** — a known asymmetry inside a comparison-bearing quantity: render cost per environment
  frame differs between the on- and off-policy families, so wall-clock-per-frame is not the same
  bargain for both. A caveat does **not** demote a quantity; it travels with it.
- **Reconciliation** — the demonstration that two emissions of the same *nominal* quantity were
  produced the same way. **A shared name is not a reconciliation and is not evidence of one.**
  Axes along which two honestly-named "entropy" numbers silently differ:
  *which distribution* (the policy that acts, or something else); *whether passes are mixed*;
  *the support* (a 7-D Gaussian's summed entropy is unbounded above; a Categorical's is bounded by
  `log n` — same word, different ranges, no shared zero); *which transitions are included*
  (warmup dropped? truncated episodes handled how?); *when it is read* (pre- or post-update);
  and *how it is averaged* (a mean of minibatch means is not the mean).

  Worked example, both from this repo: `ctrl`'s `pi/entropy` is one Gaussian pass's entropy summed
  over 7 dims. `ibac_sni`'s `Loss/entropy` is a 50/50 mix of two passes, where the noisy term is
  the **mean of the component entropies of a mixture** — not the entropy of the mixture, and not
  the entropy of anything that acts, because the reference computes it that way (a mixture has no
  closed-form entropy). One measures the acting policy; the other measures a distribution that
  never selects an action. Renaming them alike would make them look reconciled and make the
  discrepancy harder to find.

### Stance

- **The null is non-comparability.** Two numbers are not relatable until shown to be, and the
  default coverage class of a quantity is **unclassified**, not universal. This inverts a burden:
  the work is not protecting an existing comparability from erosion, it is *earning* it per
  quantity. A corollary worth stating because this document's own definitions invite the opposite
  reflex: **harmonising names is not progress and can be harm** — it buys the appearance of
  reconciliation at the cost of hiding that none was done.
- **The reference is authoritative about the algorithm and never about the measurement.** Carrying
  a reference's metric *names* into this project is a fidelity error wearing fidelity's clothes.
- **A quantity is comparison-bearing only if its definition is identical everywhere it appears** —
  same unit, same origin, same multiplicity. **Same name with different definitions is worse than
  different names**, because the first hides and the second announces.
- **Provenance does not transfer a contract, any more than a name does.** The bullet above covers
  same-name/different-definition; the sharper case is same-*lineage*. Two PPO-derived baselines
  each emitting `entropy` share an ancestor and are still two quantities until someone has read
  both interiors. Shared derivation is a reason to look, never a reason to assume.
- **A contract question interrupts the work; it does not advance it.** Work is not a continuous
  series of successes, and *"does this satisfy the contract"* is where that becomes visible: the
  question cannot be closed on the spot. It asks for verification, for grounds, and for a burden
  of proof to be discharged against a null of **not the same** — and that null is not lifted by
  deleting the word *not*. The C++ rule-of-thumb for a `struct` is that every possible set of
  parameter values has a meaning; a `struct` implementing a data structure quietly violates it,
  since most combinations have no error-free meaning. Both are called structs and the contracts
  are not the same. So **deciding what a quantity's exhaustive contract is, is construction-grade
  judgement, and acting on that decision is a construction** — it belongs in the ledger with the
  rest, not in a survey.
- **Coverage is declared, not discovered.** A metric only some baselines have is fine. A metric
  whose coverage nobody has written down is not.
- **Caveats are reported upfront, with the number.** A caveat first noticed while reading results
  is a defect in this contract, not a footnote on the result.
- **Accidental variation in a comparison-bearing quantity is a defect even when nothing downstream
  currently breaks** — it is the selective-failure position (`docs/STEP-ZERO.md` gate 3),
  invisible by construction. The qualifier is load-bearing: a **singleton** diagnostic may be
  named and defined however its own algorithm finds natural, because nothing is ever placed
  beside it. Policing those would be cost with no comparison to protect.

**These four coverage classes are proposed, not derived.** They are a first cut that fits the
cases seen so far and may not carve the space correctly — the likeliest failure is a quantity that
is universal in *name* and subfamily in *meaning* (episodic return is identical across all twelve;
return-per-wall-clock-second is not, and only becomes honest once split by family). If a case does
not fit, amend the classification rather than forcing the case into it.

### Known open state, 2026-08-16 — measured, not asserted

The emitted train-side names were enumerated from the code and **are currently accidental**:

| quantity | `ctrl` | `ibac_sni` | others |
|---|---|---|---|
| policy loss | `pi/pg_loss` | `Loss/pi` | `ppg/*`, `idaac/*`, SAC-family: different again |
| value loss | `v/loss` | `Loss/v` | ditto |
| policy entropy | `pi/entropy` | `Loss/entropy` | ditto |

Four naming conventions across five modules for quantities that are the same thing. The
`ibac_sni` row is the newest and was introduced **2026-08-16 during its base-first rebuild**, by
carrying `train-procgen-pytorch`'s own logging names — a direct violation of the first stance
point above, committed while writing it. Recorded rather than quietly renamed, because the
instructive part is that faithfulness to the wrong layer looks exactly like diligence.

The eval side (`frames`, `mean`, `median`, `iqm`) is shared in *code*, which is a stronger position
than the diagnostic vocabulary — §1–§10 establish that one evaluator and one env path produce it
for all twelve, so the largest reconciliation axes (which transitions, which scenes, how many
trials) are fixed by the protocol rather than per baseline.

**That is not the same as reconciled, and the gap is the interesting part.** Sharing an evaluator
fixes *how* the number is collected; it does not by itself settle that "an episode" or "a frame"
denotes the same event for an on-policy baseline stepping one env and an off-policy one replaying
a buffer — which is exactly where the on/off-policy render-cost caveat lives. Treat the eval axis
as **the most likely to survive reconciliation**, not as already having survived it. It has been
grepped, not inventoried against this framework.

**Not yet done:** the emission inventory (per baseline, every emitted quantity classified into the
four coverage classes). Until it exists, every claim about which metrics are comparison-bearing is
argument-shaped.

---

## 0. How this was actually produced (provenance, not padding)  ·  [HISTORY]

The plan's Stage 2 called for 12 independent agents, one per baseline, run in parallel via the
Workflow tool. That attempt was made and **failed completely**: all 12 agents hit the session's
usage limit before any returned a result — roughly 1.06M subagent tokens spent, zero usable
output. Retrying immediately would fail the same way (the limit resets on a fixed clock, not on
availability), so this document was produced as a **single direct audit pass** instead, drawing on
this session's own extensive prior verification of every one of these 12 baselines (all cited
below by file:line, not asserted from memory) plus fresh targeted checks for whatever wasn't
already pinned down under this specific lens. Stage 4 (findings) and Stage 6 (standing checklist
for future baselines) are merged into one document because splitting them would have meant writing
the same checklist twice.

## 1. The non-negotiable invariant — re-confirmed  ·  [PORT-ERA-U]

Every baseline's environment interaction, training and eval alike, goes through
`rlgen/envs.py`'s construction path. Re-verified this pass: grepped every file under `rlgen/` for
`robosuite`/`suite.make`/`gym.make`/`robo_make`; every hit outside `rlgen/envs.py` is a comment or
docstring, never a second construction call. Holds for all 12.

## 2. Findings that are uniform across all 12 baselines, by construction — checked once, not 12 times  ·  [PORT-ERA-U]

Re-deriving these 12 times would mean checking the *same shared code* 12 times, which is exactly
the redundant-work pattern this project's own architecture reframe (Part of this plan's context)
eliminated the need for. Each is true for every baseline **because** it's centralized in code no
baseline's own file touches — the citation is that shared code, not per-baseline evidence.

- **Frame/action_repeat/frame_stack accounting (checklist A)**: entirely owned by
  `rlgen/envs.py` (env construction) and `rlgen/trainer.py`/`rlgen/trainer_onpolicy.py` (budget
  counting, `frames += protocol.action_repeat`). No baseline's own `act()`/`update()` file
  computes a frame count, applies `action_repeat`, or re-stacks frames — confirmed by the same
  choke-point grep as §1, since if a baseline touched the environment directly it would have shown
  up there. **Compliant, all 12.**
- **Reward never reachable from a baseline's own code during eval (checklist B, reward sub-item)**:
  `evaluate()` reads raw reward directly from the shared env; no baseline's `act()` is ever handed
  a reward value at all (the interface is `obs -> action`, per `policy_for`'s own docstring).
  **Compliant, all 12.**
- **Action clipping happens three times, redundantly, uniformly (checklist B, action-postprocessing
  sub-item)** — re-verified this pass by reading all four adapter classes directly:
  `DrQV2Adapter.act` (`rlgen/agents.py:83`), `SacAdapter.act` (`rlgen/agents.py:218`),
  `PPOFamilyAdapter.act` (`rlgen/agents.py:358`), and `AldaAdapter.act` all end with
  `np.clip(a, -1.0, 1.0)`; `rlgen/trainer.py`'s main loop clips again before `env.step()`; and
  `rlgen/envs.py`'s `RoboEnv.step`/`SyntheticEnv.step` clip a third time internally (Stage 1,
  this session). Three layers, all idempotent, all landing on the same bound — defense in depth,
  not a bug, and identical for every baseline since none of the three layers is baseline-specific.
- **Checkpoint schema (checklist C)**: `state_dict()`/`load_state_dict()`/`train()` are defined
  once per adapter class (4 classes covering all 12 baselines), not per baseline. The
  `load_state_dict` fix (raises `KeyError` on a mismatched key rather than silently partial-loading
  — `docs/VALIDATION.md` §5) was applied to all three reflection-based adapters uniformly this
  session. **Compliant, all 12**, by the same centralization argument.
- **`Protocol` values are never hardcoded per baseline**: enforced structurally and *tested* —
  `tests/test_contract.py::test_no_protocol_value_is_hardcoded_outside_this_module` walks the AST
  of every first-party source file for the two telltale literals (`84`, `500`) outside
  `rlgen/protocol.py`. Already a standing, automated check, not something this pass needed to add.
- **Deterministic eval-callable correctness (checklist E)**: `assert_respects_deterministic`
  (`rlgen/agents.py`) is run generically for every registered baseline via
  `tests/test_contract.py::test_every_runnable_baseline_respects_the_deterministic_flag` — already
  a standing, automated, per-baseline check (not something this pass needed to newly verify), and
  it is what caught the one real violation of this property found this session (IBAC-SNI's VIB
  noise leaking into eval — fixed, see `docs/FAITHFULNESS.md`).

## 3. Findings that genuinely vary per baseline — checked individually, with citations  ·  [PORT-ERA-U]

### 3a. Observation dtype/scale assumption at the `act()` boundary (checklist B)

| baseline(s) | normalization point | citation |
|---|---|---|
| `idaac`, `ppg`, `ibac_sni`, `ctrl` | each asserts `obs_uint8.dtype == torch.uint8` before dividing by 255 — **corrected 2026-08-16**: this row cited one shared `rlgen/algos/idaac/model.py:76` because all four then inherited it. Since the hermetic rebuild each owns its own encoder and its own assert: `idaac/model.py`, `ppg/model.py`, `ibac_sni/model.py`, `ctrl/model.py`. The *property* is unchanged and still holds for all four; only the citation was stale | four files, one per baseline |
| `alda` | `preprocess()` hard-asserts `t.dtype == torch.uint8` before dividing by 255 | `rlgen/algos/alda/agent.py:244` (cited earlier this session) |
| `drqv2`, `svea`, `sgqn`, `curl`, `drq` | each family's own `Encoder`/`SharedCNN`/`CNNEncoder.forward` divides by 255 without an explicit assert, relying on the uint8 contract already enforced upstream by `rlgen/envs.py::_assert_contract` | confirmed per-file in the earlier 3-agent audit this session (drqv2.py:63-64, svea.py:104-108, sgqn.py:73-78, curl.py:45-50) |
| `rad`, `soda` | `rlgen/algos/modules.py`'s `NormalizeImg` does `x/255.` | `rlgen/algos/modules.py:88` |

All 12 land on the same convention (uint8 in, `/255.` at the encoder); four of twelve assert it
explicitly, eight rely on the upstream contract. **No violation found** — the eight without an
explicit local assert are not a comparability *bug*, since `_assert_contract` already guarantees
the input is uint8 before any baseline ever sees it — but recorded here because "some baselines
assert, most don't" is itself worth knowing rather than silently assumed uniform.

### 3b. RNG hygiene inside baseline-owned code (checklist D)

Grepped every file under `rlgen/algos/` and `RL-ViGen-upstream/algos/` for unseeded global RNG
calls (`np.random.rand/randn/randint/choice/uniform`, stdlib `random.*`), excluding
`rlgen/envs.py`/`rlgen/replay.py` (already known to use explicit local `Generator` instances).
Two hits:

- `rlgen/algos/soda_utils.py:124` (`np.random.randint`, inside the dead `ReplayBuffer` class) —
  **not applicable**: confirmed zero importers of `ReplayBuffer` anywhere in `rlgen/` (already
  known dead code from earlier this session), so this call never executes.
- `RL-ViGen-upstream/algos/sgqn.py:219` (`random.uniform`, inside `update_aux`'s masked-observation
  construction) — **compliant, not a bug**: confirmed reachable only from `update()`
  (`sgqn.py:194→242`), never `act()`, so not eval-reachable (consistent with §2's augmentation
  findings from earlier this session); and confirmed both `rlgen/trainer.py:108` and
  `rlgen/trainer_onpolicy.py:71` call `random.seed(protocol.seed)` — Python's stdlib global RNG
  *is* seeded by this project's existing fix, the same as `torch`'s and `numpy`'s, so this call is
  reproducible, not a hidden source of nondeterminism.

**No RNG hygiene violations found in any of the 12 baselines' own code.**

### 3c. Hidden coupling through incidentally-shared utilities (checklist F)

| shared file | actual importers | verdict |
|---|---|---|
| `rlgen/algos/modules.py` (`weight_init`, `NormalizeImg`, `Encoder`, `Actor`, `Critic`, ...) | `rlgen/algos/sac.py`, `rlgen/algos/soda.py` (2 baselines: `rad`, `soda`) | **appropriate sharing** — both are built on this project's own from-scratch `SAC` base by design, not incidentally |
| `rlgen/algos/augmentations.py` | `rlgen/algos/soda.py` (live: `random_overlay`), `rlgen/algos/soda_utils.py` (dead file) | **appropriate**, single live user |
| `rlgen/algos/soda_utils.py` | `rlgen/algos/sac.py`, `rlgen/algos/soda.py` — but only for `LazyFrames` (isinstance check) and `soft_update_params` (Polyak averaging); `ReplayBuffer`, `set_seed_everywhere`, `eval_mode` confirmed unused | **appropriate for what's actually called**; the file carries dead weight (already known) but nothing live is incidentally over-shared |

**Corrects an earlier claim from this session's `PPO_FAMILY_ARCHITECTURE.md` work** (that document
no longer lives in the tree — see §7 below for why and where it went), which stated `weight_init`
was "currently `.apply()`-ed identically across seven SAC/DrQ-family agents." Checked directly
this pass: it's imported by exactly two files (`sac.py`, `soda.py`), covering `rad` and `soda` —
not seven baselines. The DrQ-v2 family (`drqv2`/`svea`/`sgqn`/`curl`/`drq`) each define their own
weight-init inside `RL-ViGen-upstream/algos/*.py` and never import `rlgen/algos/modules.py` at
all. The earlier claim was imprecise; corrected here rather than left standing, per this session's
own rule about not repeating an unverified claim.

## 4. Empirical smoke test (methodology layer 3) — one baseline per family, real registry path  ·  [PORT-ERA-U]

Static reading alone wasn't treated as sufficient — ran real agents through the Stage-1
instrumentation directly:

```
drqv2      step_calls=8 (expected 8)  clip_events=0  max_abs=0.183
alda       step_calls=8 (expected 8)  clip_events=0  max_abs=0.172
idaac      step_calls=8 (expected 8)  clip_events=0  max_abs=0.012
```

Built through `registry.get(name).build(...)` — the actual path `rlgen/trainer.py`/
`trainer_onpolicy.py` use — on the synthetic backend, `action_repeat=1`, 8 real `env.step()` calls
each, policy actions (not zeros). `step_calls` matched the independently-known-correct count
exactly for all three, one representative per family (off-policy DrQ-v2, off-policy SAC, on-policy
PPO). Zero clip events at random/near-init policy weights for all three — no action-scale
miscalibration visible at this smoke-test scale (does not rule out drift after real training;
noted as a limit of this check, not claimed as proof of capability preservation for a trained
policy).

**Update, later the same session**: the other 9 baselines' own smoke tests, and the real-backend
(robosuite, not synthetic) equivalent for all 12, were both added as permanent, red-green-verified
tests once the session-limit constraint eased — see §5, now closed rather than open.

## 5. Open items, stated plainly rather than silently closed  ·  [PORT-ERA-U]

- ~~9 of 12 baselines lack an individual empirical smoke test~~ **CLOSED**:
  `tests/test_contract.py::test_every_baseline_step_calls_matches_ground_truth`, parametrized over
  all of `registry.BRIEF_BASELINES`, synthetic backend, red-green verified.
- ~~No real-backend (robosuite) smoke test was run for any baseline~~ **CLOSED**:
  `tests/test_real_env.py::test_every_baseline_step_calls_matches_ground_truth_on_the_real_backend`,
  same 12 baselines, real robosuite, red-green verified the same way.
- **The PPO-family per-baseline findings** (PPG's gamma/grad-clip/dual-optimizer divergence from
  its own reference, CTRL's window-construction gap, IBAC-SNI's KL timing) are
  internals-faithfulness questions, correctly out of scope for THIS document. **As of 2026-08-16
  they are largely built**: `ppg`, `ibac_sni` and `ctrl` are hermetic modules carrying their own
  reference-sourced values, and `onpolicy_ext.py` is deleted. **What remains open is different from
  what this bullet originally tracked**: `ppg` and `ibac_sni` were written *from understanding
  rather than from their literal base* — constructions where a copy was reachable — and neither has
  any numerical comparison against its reference. Current state: `docs/REGISTER.md` (dated rows) and
  `docs/ORIGINAL_LOCATIONS.md`'s classification table; the corrected practice is
  `docs/STEP-ZERO.md` §4.

## 5b. The platform is a comparability axis, discovered 2026-09-03  ·  [DURABLE]

Every axis above concerns what the *code* does. This one does not, and it was not on the list until
it was measured. See [C95](CONSTRUCTION.md#c95).

**The measurement.** One `drqv2` checkpoint at 60k, evaluated on eval-easy / scene 0 / twenty
episodes, four ways:

| where | code | result |
|---|---|---|
| container (Linux, CUDA, `MUJOCO_GL=egl`) | RL-ViGen's own `eval()`, two independent jobs | **41.66**, **50.73** |
| laptop (macOS, CPU, `MUJOCO_GL=glfw`) | RL-ViGen's own `_eval_regime`, unmodified | **3.41** |
| laptop | our `scripts/eval_grid.py` | **2.94** |
| laptop (MPS-as-CUDA shim) | our `eval_grid.py`, train regime | 8.58 against 20.95 on CPU |

**The rule it implies.** Two numbers are comparable only if they were produced on the same
platform. A cross-baseline table mixing container-measured and laptop-measured numbers is not a
comparison of algorithms; it is partly a comparison of machines, and the machine term is **larger
than the effect the study is trying to measure** — 12–14× here, against generalisation gaps this
project reports in the single digits.

**Why it hid for so long, which is the transferable part.** The obvious control — "run the same
checkpoint through two independent evaluators and see if they agree" — was run, and both evaluators
agreed to two decimal places. Both were *ours*. Agreement between two of your own instruments
measures your consistency, not your accuracy. The control that broke it open was running
**upstream's own evaluation loop** locally, which failed identically to ours and thereby exonerated
the code and indicted the machine. **When an instrument disagrees with a reference, the decisive
control is the reference's own instrument on your hardware, not a second instrument of yours.**

**It also explains a pattern that had been read as several separate facts.** The discrepancy scales
with policy quality, because a vision policy is what a render difference damages: an untrained 6k
agent reproduces locally, `idaac` at ~1.5 and `dmc_gb` at ~7 reproduce, and the gap grows
6.5× → 60× → 670× as `drqv2` improves from 60k to 100k. Each of those had been logged as an
independent observation. They are one observation.

**Separated, same day — it is the RENDERER.** The same grid run twice inside one container gives
train **131.54** on CUDA and **131.57** on CPU; this laptop's CPU gives **13.85**. Two devices, one
platform, the same answer to three significant figures — so the device leg is closed and
`MUJOCO_GL=egl` against macOS `glfw` is what remains. The container figure also reproduces the
run's own logged `train_regime_reward` of **135.71**, which validates `eval_grid.py` against the
training loop it was suspected of contradicting.

**A corollary that matters for any future "just correct for it" proposal**: the effect is not a
scale factor. On the ten-scene grid the same policy reads 386.1 on scene 0, 210.3 on scene 2 and
0.7 on scene 3 — a per-scene, policy-dependent collapse. There is no offset to divide out.

**Practical consequence, in force now.** Numbers produced by a baseline's own cell are measured in
the container and are comparable with each other. Numbers produced by a local offline grid are not
comparable with those, and every such number computed before 2026-09-03 is void for cross-platform
use. `normalize_curves.record()` now stamps `native.recorded_on` (host, system, machine,
`MUJOCO_GL`) so the two are mechanically separable; `mujoco_gl: "glfw"` is the tell. Records written
before that stamp existed carry no provenance and must be treated as local until shown otherwise.

## 5c. The estimator axis: nine report a mode, three report a sample  ·  [DURABLE]

Resolved 2026-09-03 by reading the two cells `scripts/audit_eval_state.py` had left open.

| estimator | baselines | how it is fixed |
|---|---|---|
| **mode** (deterministic) | drqv2, svea, drq, sgqn, curl (`dist.mean`); rad, soda, alda (`mu`); ctrl (`pi.mode()` via `algo.select_action`) | 9 |
| **sample** (stochastic) | **idaac** (`act(inputs, deterministic=False)`, and `test.py` omits the flag); **ibac_sni** (`evaluate.py --argmax` is `store_true`, default **False**); **ppg** (no deterministic path exists in the repository at all) | **3** |

**`ctrl` moved from the mode column to the sample column on 2026-09-04, and back to the mode column
on 2026-09-07 — the second move is the one that stands.** `audit_eval_state` had it as
*"deterministic (`pi.mode()`) via `algo.select_action`"*, which is true of the helper:
`select_action(..., sample=False)` returns `pi.mode()`. The 2026-09-04 entry read the calls that
produce the numbers a `ctrl` cell actually reports as `train_ppo.py:244` and `:253` — the ID and OOD
test-env steps behind `Eprew200`/`Eprew0`, which **both pass `sample=True`** — and moved `ctrl` to
`sample` on that basis. **That was the wrong call site**: those are TRAINING-time calls, not
`ctrl`'s EVALUATION-time rule. Its released evaluator, `evaluate_ppo.py:84`, calls
`select_action(..., greedy=True)`, whose greedy branch is `logits.argmax(1)` — deterministic. Found
by external review 24 and confirmed against the pinned upstream 2026-09-07; corrected in
`evaluator_identity.py`, `eval_grid.py`, `normalize_curves.py` and `audit_eval_state.py` in one
batch. **A capability is not a usage** still holds as the lesson — it just took a second pass to
apply it to the right call site. Full account: `notes/SAME-AXES-VERDICT.md`.

**Why this is an axis and not a footnote.** A sampled return and a mode return are different
quantities. The sampled one is usually lower, and by an amount that depends on the policy's entropy
*at that checkpoint* — so the gap between them is itself a function of how far training got. Put
both in one column and a difference belonging to the **estimator** is attributed to the
**algorithm**. On Door specifically the effect can be large in either direction, because success is
a threshold (`hinge_qpos > 0.3`): noise can knock a marginal policy off the latch, or jitter a stuck
one onto it.

**The fix is declaration, not uniformity.** The null this project measures against is each
baseline's own repository running its own evaluation, so overriding `idaac` or `ibac_sni` to take a
mode would be a deviation from their authors, and `ppg` has no mode to take — writing one would be
inventing a policy its authors did not ship. So the axis stays non-uniform by design and every
table carrying these numbers must say which column is which.

**How it was missed, which is the reusable part.** The audit was correct about what it had checked
and silent about what it had not: `ibac_sni`'s cell held the string `"see scripts/evaluate.py"`, and
a placeholder in a results column reads as a finding to anyone skimming. An instrument that reports
"unresolved" in the same shape as it reports an answer will have its unresolved cells quoted as
answers.

## 5d. `ctrl`'s pre-production row breaks a condition this project had already written down  ·  [DURABLE]

**Corrected within the hour: this is NOT a new axis, and I first wrote it as one.**
`scripts/audit_comparability_seam.py::reported_estimator` already draws exactly this distinction —
evaluation numbers are a fixed-policy sample mean for all twelve, while *"training-curve numbers are
NOT that, and pooling the two would be the error this axis exists to prevent"*, naming `idaac`'s
10-episode and `ctrl`/`ppg`'s 100-episode rolling windows as **different estimands**. It concludes
that the axis is uniform *"conditional on only ever reading the evaluation number"*.

**The finding is that the pre-production pass violated that condition, which is worse than a new
axis.** `ctrl`'s cell reported `Eprew200` / `Eprew0` — the training-curve numbers — because its
fixed-policy evaluator is the known-unbuilt "ADAPT" item: `evaluate_ppo.py` calls a discrete-only
helper (`logits.argmax` / `jax.random.categorical`) while `algo.select_action` already handles both
action spaces. With no usable evaluator, the cell fell back to what the training loop prints, and a
number that must never be pooled landed in the same column as eleven that may be.

**So the condition was documented, the gap that breaks it was documented, and the two had never
been put together.** Each was true and separately recorded; the consequence — that `ctrl` cannot
appear in a comparable table until its evaluator is adapted — was not.

**Eleven baselines evaluate the final policy over a fixed number of episodes.** `ctrl` does not
evaluate at all in that sense: `train_ppo.py` steps an in-distribution and an out-of-distribution
test env *inside* the training loop and reports `Eprew200` / `Eprew0` — a running mean over a
trailing window of episodes — with `SR_ID` / `SR_OOD` beside them. `scripts/audit_eval_cadence.py`
records this as *"not episodic: both test envs are stepped inside the training loop"* and *"no
cadence exists to control"*.

**Why this is a third axis and not a restatement of §5c.** The estimator axis (mode vs sample) is
about *how an action is chosen*. This is about *what population the average is over*:

| | population | measures |
|---|---|---|
| eleven baselines | N episodes played by the final saved policy | the checkpoint |
| `ctrl` | the last ~200 episodes of training, played by ~200 successive policies | a trailing average of the run |

The two coincide only when learning has plateaued. While a policy is improving the window
understates it; immediately after a collapse the window flatters it, because most of the window
predates the collapse. On a 10,000-frame validation run nothing has plateaued, so `ctrl`'s number
is the least comparable of the twelve — and it is the one most likely to be read as directly
comparable, because it arrives as a single tidy scalar like the others.

**Consequence, in force**: `ctrl`'s cell is reported with a blank episode count and that blank is
load-bearing. It is also the reason `ctrl` needs no separate ID/OOD evaluation harness — it already
reports both — which is a convenience that hides the incomparability rather than fixing it.

## 6. Standing checklist for auditing a 13th baseline (or re-auditing any of these 12), durable  ·  [DURABLE]

When a new baseline is added, or any of these 12 changes its own `act()`/`update()`/environment
interaction, re-check:

- [ ] **Environment**: does it construct or touch an environment any way other than
      `rlgen/envs.py::make_env`? (§1 — the single most important check; everything else assumes
      this holds.)
- [ ] **Frames**: does its own code compute a frame/step count, apply `action_repeat`, or re-stack
      frames anywhere? (Should be "no" for every baseline — if "yes", that's new, and needs the
      same scrutiny §2's uniform findings currently don't need.)
- [ ] **Reward**: is reward ever reachable from this baseline's own code on a path `evaluate()`
      could call (i.e., inside `act()`, not just `update()`)?
- [ ] **Observation dtype**: does `act()` assume uint8 or float input, and does that match what
      `rlgen/envs.py`/`evaluate()` actually hands it? (§3a)
- [ ] **Action range**: does `act()`'s own output ever get used anywhere that ISN'T already
      guarded by one of the three existing clip layers? (§2)
- [ ] **Checkpoint**: does `state_dict()`/`load_state_dict()` go through one of the four existing
      adapter classes' generic implementation, or does it need a new one? If new, does it raise
      (not silently partial-load) on a mismatched key, matching `docs/VALIDATION.md` §5's fix?
- [ ] **RNG**: does any of its own code call unseeded global `np.random.*` or stdlib `random.*`
      from a path reachable during training? (Seeded automatically if reachable — `rlgen/
      trainer.py`/`trainer_onpolicy.py` seed `torch`, `numpy`, and stdlib `random` globally before
      agent construction — but confirm the call is actually reachable from a code path that runs
      *after* that seeding, not from module-import time.)
- [ ] **Shared utilities**: does it import anything from `rlgen/algos/modules.py`,
      `augmentations.py`, or `soda_utils.py`? If so, is the sharing because its own paper
      genuinely specifies the same thing another importer already implements, or merely
      convenient? (§3c)
- [ ] **Deterministic eval**: does `tests/test_contract.py::test_every_runnable_baseline_respects_
      the_deterministic_flag` cover it automatically once registered? (Should be "yes" — this is
      the one item that's already a standing, automated check rather than a manual one.)
- [ ] **Smoke test**: run the §4 pattern (registry build, synthetic backend, a handful of real
      `env.step()` calls, read `step_calls`/`action_clip_events`/`max_abs_action_seen`) — cheap,
      concrete, and the empirical layer nothing else in this list substitutes for.

## 7. Where `docs/PPO_FAMILY_ARCHITECTURE.md` went, and why  ·  [HISTORY]

That document proposed a "shared PPO core + hook mechanism" strategic architecture for
`idaac`/`ppg`/`ibac_sni`/`ctrl` — build a small number of extension points on the shared `Learner`
class so each method's own quirks (IBAC-SNI's bottleneck routing, PPG's dual value network) could
attach to one shared training loop. That proposal predates, and is now known to be in tension
with, the reframe this document itself embodies: baselines don't need shared internals at all —
only the interface contract (§1–§6 above) needs to hold uniformly. The tension isn't hypothetical:
checking directly, PPG's own reference uses **two different discount factors** (0.99 in its reward
normalizer's own default, 0.999 in its actual training script) and **zero gradient clipping**
anywhere — both flatly incompatible with "share the core's single gamma and grad-clip policy
across all four," which is exactly what that document's §2.1 proposed doing with reward
normalization specifically.

Rather than rewrite that document in place to reconcile it with the reframe — which would mean
re-deriving a different architecture proposal for something no actual re-architecture work has
started on yet — it was removed from the working tree entirely, per the owner's explicit
instruction to checkpoint and remove rather than mass-rewrite docs written under the old model.
**Nothing is lost**: the full document, and the exact commit state immediately before its removal,
are preserved at the git tags `pre-lean-target-checkpoint-transition` (on
`nd-ln-architecture-transition`) and `pre-lean-target-checkpoint-main` (on `main`). Its verified,
still-useful *factual* content — the coupled/decoupled value-network table, IBAC-SNI's exact
β·KL wiring from DZ's reference, CTRL's window-density gap, PPG's dual-network requirement — remains
retrievable from those tags and remains accurate; only its *strategic* "build a shared core" framing
is what's actually superseded. **That integration work has since happened (2026-08-16).** All four were rebuilt hermetically
(`rlgen/algos/{idaac,ppg,ibac_sni,ctrl}/`), `onpolicy_ext.py` was deleted, and the architecture was
re-derived per baseline. Decisions are in `docs/DECISION_LOG.md`, findings in `docs/REGISTER.md`.

**Carry this instead of what this section originally instructed.** It said: *"re-derive the
architecture for that specific piece of work fresh, informed by the tagged document's citations."*
That instruction is quoted rather than left standing because it reads as sound and **is the
instruction that produced two of the four as constructions**: re-derivation is not the same as
starting from the literal reference. `ppg` and `ibac_sni` were re-derived *from understanding*
while a copyable base sat on disk — faithful-looking, and still constructions. The corrected rule
is `docs/STEP-ZERO.md` §4: establish whether the base is reachable **before** writing, and copy it
when it is. "Fresh" and "from the original" are different instructions, and only the second is
right when a base exists.

## 8. Stage 3 — mutation-testing the comparability layer  ·  [PORT-ERA-U]

Per the plan's methodology layer 4: don't just trust that Stage 1's instrumentation and its tests
currently pass — confirm the tests would actually notice if the instrumentation were broken.
Exhaustive (not sampled), scoped to `rlgen/envs.py` specifically: every one of its 65 mutable AST
sites (comparison flips, arithmetic sign swaps, boolean swaps, constant perturbations — the same
operator set `mutants/sweep.py` already uses), each applied to an isolated copy of the tree, oracle
= the real `pytest tests` suite.

**Ran in two passes, the second parallelized** — a serial first pass covering sites 1–57 was
taking long enough that continuing serially would have meant a very long single-threaded tail (the
owner's own direct observation, "note that tests can run in parallel/background," mid-session);
the remaining 8 sites were re-run 4-way concurrently instead (each mutant runs against its own
isolated temp-dir copy, so there's no shared state to make parallelizing unsafe), cutting what
would have been the slowest ~25–45 minutes of the run down to under 6.

**Result: 37/65 killed (57%) on the first pass.** 28 survivors, triaged by hand — a survivor is
either a real gap or a demonstrably equivalent mutant; a script doesn't get to decide which:

- **1 test-harness artifact, not a real-world gap**: line 69, the `DEFAULT_MUJOCO_GL` fallback
  constant. Survives specifically because `mutants/run.py`'s own `run_suite` pre-sets `MUJOCO_GL`
  in the subprocess environment before the mutated code runs — the exact same reason every
  invocation this session has explicitly set `MUJOCO_GL=glfw` on the command line, meaning the
  `os.environ.setdefault(...)` fallback essentially never fires in this project's actual usage
  pattern either. Not chased further — fixing what's already unreachable in normal use isn't worth
  it, and the harness-masking behavior is now stated here rather than left mysterious.
- **~4 genuinely equivalent mutants**: `sys.path.insert(0, p)` → `insert(1, p)` (position 0 vs. 1
  in `sys.path` is unobservable absent a naming collision this project doesn't have); the two
  `self._t = 0` initializations in `RoboEnv.__init__`/`SyntheticEnv.__init__` (both are
  unconditionally overwritten by `reset()`, which the documented contract requires before any
  `step()`, so the init-time value is never actually read); the `np.uint8` observation range
  perturbation (the dtype cap makes most range mutations either equivalent or immediately
  incompatible with `uint8` casting).
- **~15 inside `SyntheticEnv`'s own reward-shaping/target-computation arithmetic** (lines
  265, 276, 284–286, 289, 307, 309 and its neighbors) — already covered by this project's own
  standing caveat, restated rather than rediscovered: `docs/VALIDATION.md` §5 states plainly that
  `SyntheticEnv` "is test instrumentation. Mutating it mutates the instrument, not the system
  under test." These are exactly that category — the instrument's own internal formula, not
  anything downstream depends on being bit-exact, only on being *sensitive* (which
  `test_synthetic_env_is_sensitive_to_the_things_tests_rely_on` already separately checks).
- **8 genuine, worth-fixing gaps, closed this pass** (all in `tests/test_contract.py`/
  `tests/test_real_env.py`, all red-green verified — see below for the strongest form of that
  verification used here):
  1. `EnvSpec`'s `@dataclass(frozen=True)` was never actually exercised — nothing confirmed a
     mutated `EnvSpec` instance actually raises on attribute assignment.
     `test_env_spec_is_actually_immutable`.
  2. `_assert_contract`'s `act_dim < 1` boundary (both the `<` comparison and the `1` constant)
     was never exercised at the actual boundary — every real baseline uses `act_dim=7`, so
     `act_dim==1` (valid) vs. `act_dim==0` (invalid) was an unpinned assumption.
     `test_act_dim_boundary_is_pinned_at_exactly_one`.
  3. `RoboEnv`'s `_checked` flag — the gate that makes `_assert_contract` run once, on the first
     real reset, never again — had its initial value, its guarding condition, and its
     post-check assignment all survive independently. No test distinguished "the contract check
     genuinely ran once" from "it silently never ran, or ran every time, and nothing noticed."
     `test_real_env_contract_is_checked_once_on_the_first_reset_not_every_reset_and_not_never`
     (counts real calls via `monkeypatch`, not just the flag's final state, so a bug that flips
     the flag without the check running — or vice versa — can't pass by accident).
  4. `action_clip_events`' exact `mag == 1.0` boundary was untested on **both** `RoboEnv` and
     `SyntheticEnv` — a gap in this session's *own* Stage-1 tests specifically: the two smoke
     values already used (`0.5`, `3.0`) can't distinguish `mag > 1.0` from `mag >= 1.0`, since
     both thresholds agree at both values. Added the exact-boundary case (`mag == 1.0` must NOT
     count, since `np.clip` doesn't alter a value already at the bound) to the existing tests on
     both backends, rather than write new ones.

**Verification of the fixes — stronger than a generic red-green cycle.** Rather than only confirm
"the new tests pass" and "if I revert the whole feature, they fail" (the pattern used through most
of this session), each of the 8 specific mutations that originally survived was re-applied,
individually, with the *real* suite re-run against each — directly confirming that specific,
already-known bug is now caught, not inferring it from a broader revert:

```
line  72 (boolconst, EnvSpec frozen=True):                        killed
line 111 (cmp, act_dim < 1):                                      killed
line 111 (int, act_dim < 1):                                      killed
line 185 (boolconst, RoboEnv._checked initial value):              killed
line 205 (not, `if not self._checked`):                            killed
line 207 (boolconst, self._checked = True):                        killed
line 217 (cmp, RoboEnv's mag > 1.0):                                killed
line 301 (cmp, SyntheticEnv's mag > 1.0):                           killed
```

**8/8 confirmed killed.** Every mutation that survived the original sweep and was judged a real
(not equivalent) gap is now caught. Script: `verify_kills.py` (scratchpad, not committed — a
one-off verification tool, not part of the standing test suite; its own first run was itself a
small lesson — no `flush=True` on its prints, so redirecting its output to a file produced nothing
readable until the whole run finished, the exact block-buffering pitfall `mutants/run.py`'s own
comments already warn about, made once more here despite having read that warning earlier the
same session).

**Not pursued further, stated rather than silently dropped**: the ~15 `SyntheticEnv`-internal
survivors above are covered by existing project doctrine and weren't individually re-litigated;
a full, non-exhaustive sweep across the *rest* of `rlgen/` (not just `envs.py`) was out of scope
for this specific stage, which was about validating the Stage-1 instrumentation this pass added,
not re-auditing the whole codebase's mutation coverage from scratch.

## 9. Independent re-verification of this document's own claims  ·  [PORT-ERA-U]

A separate, independent pass at re-deriving 10 of this document's most load-bearing factual claims
(§2's uniform-by-construction assertions, §3's per-baseline citations, §8's instrumentation
details) from live source directly, using `agy` (Antigravity CLI, `gemini-3.7-flash-high`) — a
genuinely separate model/process from the one that wrote the original claims, not the same model
checking its own work. Scoped narrowly and explicitly per-claim (not "review this document and
form opinions") specifically because open-ended review needs my own judgment and can't be
delegated; re-deriving a bounded, already-stated factual claim from primary sources is squarely
the kind of task that can.

**Result: 9/10 CONFIRMED VERBATIM, 1/10 CONFIRMED IN SUBSTANCE** (claim 7, the `sgqn.py`
`random.uniform`-reachability claim — the independent pass gave a more precise framing than the
original claim, not a contradiction: `SGQNAgent` doesn't define its own `act()` at all, it
inherits `DrQV2Agent.act()` unmodified, which is what actually makes `random.uniform`
unreachable from it — same conclusion, sharper reasoning). Zero claims were found inaccurate.

**Not taken at face value despite the clean result** — a 9-VERBATIM/1-substance/0-inaccurate
outcome is exactly the "suspiciously tidy" shape worth distrusting on principle, independent of
whether this particular one happens to be genuine. Three of the ten claims were independently
re-checked a *third* time, by hand, directly against the file: the exact `agents.py` line numbers
for all four adapters' clip calls (claim 3), the precise `modules.py` importer count via a fresh
grep (claim 5), and the exact instrumentation line contents for both `RoboEnv` and `SyntheticEnv`
(claim 9, the highest-stakes one, since it's this session's own new code). All three matched
exactly. That's a real, if partial, sample-check — not a substitute for having verified every
claim personally, but enough to treat the full 10-claim result as genuinely trustworthy rather
than assumed so.

Full report: `verify_result.md` (scratchpad, not committed — like the mutation-testing scripts,
a one-off verification artifact, not part of the standing repo).

## 10. Stage 5 — implementation plan for what Stage 2/3 found  ·  [PORT-ERA-U]

The plan's own definition of this stage calls for "research/spike, options-with-tradeoffs, scoped
build steps, per-step verification, acceptance testing, documentation updates" for anything Stage
2/3 found broken. Written retrospectively rather than prospectively, because that is honestly what
happened: every finding that needed a code fix was fixed, verified, and documented in the same
pass it was discovered in — not queued into a separate future plan. Mapped onto the stage's own
categories, so the discipline is checkable rather than asserted:

- **Research/spike**: none needed. Every Stage 2/3 finding was resolved by reading the actual live
  code directly (no ambiguity requiring exploratory investigation before a fix could be attempted).
- **Options-with-tradeoffs**: none arose. Every fix had exactly one correct shape once the gap was
  understood (e.g., "the guard checks the wrong attribute name" has one fix, not a choice between
  several).
- **Scoped build steps**: each of Stage 3's 8 fixes was its own isolated change to one test file,
  never bundled — visible in the four separate, individually red-green-verified additions this
  session made to `tests/test_contract.py`/`tests/test_real_env.py`.
- **Per-step verification**: every fix got the strongest form used all session — not just "new
  test passes," but the *specific* mutation that surfaced the gap was re-applied and re-confirmed
  caught, individually, per fix (§8's `verify_kills.py` results).
- **Acceptance testing**: full suite run fresh, cross-checked against `--collect-only`'s count,
  before every commit; cherry-picked to `main` and re-verified green there too, every time — the
  standing discipline this whole session, not something new for this stage.
- **Documentation updates alongside each change**: this document itself *is* that — §3c, §8, and
  §5's now-closed items were each written in the same commit as the fix they describe, not batched
  afterward.

**What's left that Stage 2/3 found and did NOT fix, stated once more for a single point of
truth**: nothing from Stage 2. From Stage 3: nothing — all 8 real gaps found were closed. The two
categories of survivor left alone (the `MUJOCO_GL` harness artifact, `SyntheticEnv`'s own internal
reward-shaping arithmetic) were deliberately not chased, with the reasoning stated at the point
each was triaged (§8), not silently dropped. The one substantive body of work this whole document touches
without resolving is the PPO-family internals-faithfulness findings (§7, §5) — out of scope for the
comparability contract by design. **As of 2026-08-16 that work has been done** (all four hermetic,
`onpolicy_ext.py` deleted); what remains open is narrower and different: `ppg`/`ibac_sni` are
constructions written where a literal base was reachable, and no baseline in that family has a
numerical comparison against its own reference.

**This closes the meta-plan's Stages 1 through 6, plus the two additional verification passes
(§4's spare-time real-backend coverage, §9's independent re-derivation) taken because they were
cheap, available, and directly responsive to the standing instruction to keep verifying rather
than stop at "probably fine."**

---

## 3f. Three mechanism differences absent from this project's prose corpus (2026-09-08)  ·  [LIVE]

Found by a from-first-principles source walk of all twelve training loops, then checked against
every `.md` and `.txt` in the tree outside `ext/`, `RL-ViGen-upstream/` and `runnable/` — 247 files.
Most of what that sweep raised was already recorded somewhere. These three were not recorded
anywhere at all.

**All three are faithful to upstream.** Nothing below is a change; each is a disclosure, and each
is here because a reader comparing these baselines would otherwise assume uniformity that does not
hold.

### ALDA is the only baseline that applies weight decay, and the only one using AdamW

`runnable/alda/trainers/alda_trainer.py:301-303`:

    self.ae_optimizer = torch.optim.AdamW(
        list(shared_trunk.parameters()) + list(self.decoder.parameters()),
        lr=1e-3, weight_decay=0.1)

Byte-identical to `ext/ALDA_Official/trainers/alda_trainer.py:264-265`, so this is the authors' own
choice, not ours. What makes it worth stating is where it lands: `shared_trunk` is the single
`QuantizedEncoder` that *both* `actor_encoder` and `critic_encoder` wrap (`:239-249`), the
autoencoder loss reaches it un-detached, and this optimizer steps every update. So the visual
representation ALDA's actor and critic both read carries a decoupled weight-decay pull toward zero
on every step that no other baseline's encoder experiences — `weight_decay` and `AdamW` appear
**zero times** in any project document before this one, and grepping every other baseline's
optimizer construction finds no `weight_decay` anywhere. (`ibac_sni`'s `torch_rl` PPO *can* pass
`weight_decay=beta`, but only under `--use_l2w`, which defaults False and is never set.)

### The SAC-lineage three run a two-speed target update the DrQ-v2 lineage has no counterpart for

`rad`, `soda` and `alda` carry `critic_tau=0.01` **and** a separate, slower `encoder_tau=0.05`
(`runnable/dmc_gb/src/arguments.py:34-35`, `alda_trainer.py:31,45-46`). `drqv2`, `svea`, `sgqn`
and `curl` Polyak one target at a single rate and have no encoder-specific target at all. The
matrix discusses `critic_target_tau` only as an undisputed uniform value, which is true and
incomplete: the value is uniform, the *mechanism* is not.

### `idaac`'s `--eps` is documented as RMSprop's and configures Adam

`runnable/idaac/ppo_daac_idaac/arguments.py:21-25` describes `--eps` as *"RMSprop optimizer
epsilon"*; `algo/ppo.py:33` constructs `torch.optim.Adam(..., eps=eps)`. Vestigial help text from
OpenAI-baselines' shared A2C/PPO argparse, where A2C really does use RMSprop. `1e-5` is an ordinary
Adam epsilon and nothing is wrong with the run. Recorded so nobody "corrects" the value while
reasoning from the wrong optimizer's conventions.

### CTRL's MYOW neighbour index is a literal, and it is upstream's

`runnable/ctrl/algo.py:237`:

    nearby_cluster_idx = jnp.take_along_axis(indx[:, 0 + 1], ...)

`0 + 1` is a literal, so the positive is always drawn from the single nearest neighbour whatever
`myow_k` says. Byte-identical to `ext/ctrl_public/algo.py:222`, so this is CTRL's released code and
**not** something this port introduced — changing it would be a deviation, not a fix.

Dormant at the production value: `myow_k` is 1, so "always the first neighbour" and "the k-th of
k=1 neighbours" are the same thing and nothing is wrong with any number we report. It is recorded
because it stops being dormant the moment anyone raises `myow_k` toward the paper's `k=3` — at
which point the knob would appear to work and would not.

Raised as an unverified claim by the Gemini review, which carries its own header warning that its
confident claims should not be trusted; verified here against both trees directly.
