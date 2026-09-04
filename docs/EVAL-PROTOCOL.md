Written 2026-09-03.

# The evaluation protocol — and a proposed decision for P-C76 / R3

**Status: PROPOSED. Nothing here is settled.** Every item below is a decision I have made *as if*
it were mine, so that it can be argued with concretely. The register keeps them OPEN until the
owner records otherwise; a default is not a decision.

---

## 0. The fact that determines the whole design

`scripts/audit_eval_cadence.py`, run today:

| | evals per run | regimes | cadence unit |
|---|---|---|---|
| `drqv2 svea sgqn curl drq` | 5 | 2 | frames |
| `rad soda` | 4 | 2 | steps |
| `alda` | 6 | 3 | steps |
| `idaac` | 2 | 1 | **updates** |
| `ctrl` | 0 | 2 | **continuous, not episodic** |
| `ibac_sni`, `ppg` | **0** | 0 | none |

Its own conclusion: *"three of twelve run no periodic training-time evaluation at all … so 'metrics
on the same axes' is **not reachable from training logs by construction**. It is reachable offline,
from checkpoints, which is why the evaluator is a separate harness."*

**So the choice between "save checkpoints" and "save eval results" is not a trade-off.** Training
logs cannot deliver same-axes metrics for a quarter of the set at any cadence, in any format, no
matter how much logging is added. Adding tensorboard to `ppg`/`ibac_sni`/`ctrl` would produce more
numbers on *more* different axes, not fewer.

**Decision: checkpoints are the primary artefact. Evaluation is offline, from them.**

Three further reasons, all from this project's own history:

1. **The evaluation procedure is not settled yet** — this document is the attempt to settle it.
   Committing to eval outputs now would freeze the very thing under discussion.
2. **[C95](CONSTRUCTION.md#c95) is the proof case.** An entire evaluation methodology was
   invalidated after the fact (wrong renderer). Because checkpoints existed, everything was
   re-measured for ~60 RUB. Had we kept only eval results, the runs would have been lost.
3. **Re-evaluation is cheap and re-training is not**: a four-regime ten-scene grid over 400
   episodes cost ~168 RUB; a production cell costs hours of GPU.

---

## 1. Proposed decision for P-C76 / R3 — and why it is cheaper than the branch point assumes

`RESEARCH-FRAME.md` frames option (1) as *"give the seven evaluators a scene sweep — costs a
deviation in each clone and re-opens the faithfulness ledger for seven baselines"*. **That cost is
an artefact of assuming evaluation happens inside the clones.**

Under §0 it does not. Evaluation runs in **our** offline harness (`scripts/eval_grid.py` +
`OFFLINE_EVAL`), which loads a checkpoint and drives the baseline's *own* action path. The scene
set is then a parameter of our harness, not of anyone's `train.py`.

**Proposal: a common evaluation grid for all twelve — same scenes, same seeds, same episode count,
same regimes — implemented entirely in our evaluator, with zero clone deviations.**

What this costs is real but different: extending `eval_grid.py` to three more families (`alda`,
`ctrl`, `ibac_sni`; `rlvigen`, `dmc_gb`, `idaac`, `ppg` already exist). That is **our** code, so it
adds nothing to `deviations.py` and re-opens no faithfulness ledger. `ctrl` needs a JAX path — its
checkpoint is a flax msgpack and its policy is JAX — which is the largest single piece of work here.

**What it does not equalise, on purpose.** The *estimator* stays each baseline's own: our harness
calls their `act`, so `idaac`/`ibac_sni`/`ppg` keep sampling and the other nine keep taking a mode
(`COMPARABILITY_CONTRACT` §5c). Equalising that would replace their policies with ours. It is
declared, not removed.

**The burden of proof is OURS, per baseline, and it is mostly undischarged.** A shared evaluator
distinct from each method's own evaluator is a new instrument, and for every baseline we must show
it measures what that baseline's own evaluator measures. `scripts/audit_shared_evaluator.py` tracks
this and currently reports **1 of 12**: `drqv2` PASS (131.57 against 135.71), `idaac` UNDERPOWERED,
ten UNRECONCILED.

Two rules it encodes, both learned here rather than assumed:

- **Ours-lower is SUSPECT, not neutral.** If our number is below the baseline's own, "their
  evaluator is generous" and "our harness handicaps their policy" predict the same observation.
  C95 was exactly that shape, at 12–14x, with nothing crashing. `idaac`'s 1.663 against 3.01 sits
  in that direction.
- **A comparison at the floor is not evidence.** Two numbers straddling 1.82 agree about nothing —
  both describe a policy doing nothing, which any harness reproduces.

**The harness running is not the discharge, and neither is the ratio.** Six families exist and
all six produce plausible magnitudes; that is a statement about the code. Agreement to 3% on
one checkpoint is corroboration, not proof — it shows two instruments produced similar numbers,
not that they measure the same thing, and it lets an undeclared difference hide behind "close
enough". **The actual obligation is structural and lives in [`EVALUATOR-DELTA.md`](EVALUATOR-DELTA.md)**:
every way our harness differs from each baseline's own evaluator, declared and classified. It
already names three material deltas that were nowhere written down — our determinism setting
(ours alone, not upstream), an RNG offset introduced by the rlvigen verification probe, and a
different episode-accounting scheme for `idaac` and `ibac_sni`.

**What would show this wrong**: if driving a baseline's `act` from outside its own trainer changes
its behaviour — the C95 failure mode one level in. Guard: our harness's number must reproduce the
baseline's own evaluator on the same checkpoint.

**Held for the natives; INCONCLUSIVE for the first non-native tried, and the reason is instructive.**
For `drqv2` it holds — 131.57 against a logged 135.71. For `idaac` (`bt1dbmtc04sg5nhc18r6`), on its
own 9,216-frame checkpoint: **our harness 1.663, its own evaluator 3.01** on eval-easy. That is
~1.8x, not C95's 12–14x, so it is *not* evidence of the failure mode — but it is not evidence of
agreement either, because **both numbers straddle the 1.82 random floor** and `idaac` samples. At
ten episodes of a stochastic policy at chance, this comparison has no power.

**So the guard cannot be completed with any checkpoint pre-production currently has**: every
non-native sits at or near the floor at 10k. It needs a *competent* policy, which needs a longer run
than pre-production has done. **This is the competence gate of §3 arriving from the other side** —
the same floor that makes a retention ratio undefined makes a fidelity check uninformative. Until a
competent non-native checkpoint exists, §1's proposal rests on the natives' evidence plus a
mechanism argument, and that limitation is part of the proposal rather than a footnote to it.

---

## 2. The grid

Per baseline, per seed, per retained checkpoint:

- **regimes**: `train`, `eval-easy`, `eval-medium`, `eval-hard` — all four. `train` is the
  retention denominator and is *not* a randomised distribution ([C51](CONSTRUCTION.md#c51)).
- **scenes**: all ten certified, per regime. Per-scene rows retained, never only the aggregate —
  today's grid showed 392.9 on scene 0 against 0.7 on scene 3, which an aggregate erases.
- **episodes**: 10 per (regime, scene) cell. 4 × 10 × 10 = 400 episodes per checkpoint ≈ 1h ≈ 168 RUB.
- **seeds**: the *evaluation* seed is **fixed and shared** across every baseline and every training
  seed; the *training* seed is the §3b #4 decision. These are different axes and the record names
  both.

  **Found by the blind-spot pass, 2026-09-03, and it was silent.** `OFFLINE_EVAL` passed the same
  variable to `--seed` and `--episode-seed`. Via [C69](CONSTRUCTION.md#c69) the evaluation seed
  seeds the *global numpy RNG*, which is what places the door on every reset — so a three-seed
  production set would have evaluated each seed's checkpoint on a **different set of door
  placements**, and the across-seed spread would have mixed the training-seed effect with an
  evaluation-seed effect having nothing to do with the algorithm. `OFFLINE_EVAL_EPISODE_SEED` is now
  separate and defaults to a constant, so "same scene set, same seed set" holds **by construction
  rather than by remembering to pass a flag**.
- **platform**: the machine that trained the policy. Non-negotiable, [C95](CONSTRUCTION.md#c95).

**Emit per-episode returns, not summaries.** `eval_grid.py` already carries `native.returns` per
cell. This is what makes the owner's "all metrics, select later" possible: median, IQM, bootstrap
CI, success-conditioned return and any competence gate are all post-processing over per-episode
data. **A summary statistic chosen at write time cannot be un-chosen.**

---

## 3. The competence gate (§3b #15)

*A method that never learns has gap ≈ 0, which reads as perfect generalization.* Today: six of
twelve sat at or below the 1.82 random floor ([C55](CONSTRUCTION.md#c55)) with success 0.00.

**Proposal**: a baseline receives a retention *ratio* only if its train-regime denominator clears
the floor by a stated margin **and** its train-regime success is non-zero. Below that it is
reported as **"did not reach competence"** — not as a number, and never as a ratio. The floor and
the margin travel with every table.

This is a reporting rule, not a filter: the run and its returns are still published.

---

## 4. Checkpoint cadence (§3b #3)

The owner's reading — *progress is algorithm-dependent, so maybe each is separate* — is the right
one, and there is a hard constraint underneath it:
[C60](CONSTRUCTION.md#c60) — the RL-ViGen five can only stamp at **multiples of 50k plus the
endpoint**. `RLVIGEN_PRESERVE_SNAPSHOTS` filters that grid; it cannot add to it.

**Proposal**: retain the 50k grid plus the endpoint for every family that can, and evaluate the
**endpoint** as the headline while publishing the curve. This makes "checkpoint selection" a
post-processing choice over a retained curve rather than a decision baked into what was kept —
consistent with §2's principle.

> ### Measured 2026-09-04 — "every family that can" turns out to be ONE, and the curve is not currently producible
>
> The sentence above was written from C60, which is about the RL-ViGen five. Read across all
> twelve — from `families.json` and confirmed against four returned archives rather than the
> descriptor alone — the per-family save cadence is:
>
> | family | save cadence | mechanism |
> |---|---|---|
> | `rlvigen` | 50k stamps + endpoint | `save_every` 50000, `RLVIGEN_PRESERVE_SNAPSHOTS` filters |
> | `dmc_gb` | 100k | live `--save_freq`, set coarsely |
> | `alda` | `save_every` 50000 configured, but the checkpoint pattern names only `{endpoint}` |
> | `ctrl`, `ibac_sni`, `idaac`, `ppg` | **endpoint only** | no `save_every` at all |
>
> **So the intersection of checkpoint frames across the twelve is the endpoint alone.** The
> `drqv2` 100k cell makes it concrete: **5 eval points, 2 checkpoints**, so three of its
> during-train eval points cannot be reproduced offline, swept over scenes, or placed beside
> another baseline. A cross-baseline *curve* is not a thing this project can currently produce;
> a cross-baseline *endpoint table* is.
>
> **The cost of changing that is graded, and the grades are what make it decidable:**
> `ibac_sni` has a **live** `--save-interval` (`torch_rl/scripts/train.py:286`, default 0) and
> `dmc_gb` a live `--save_freq` — configuration, zero fidelity cost. `ctrl` **declares**
> `checkpoint_interval` (`train_ppo.py:98`) and never reads it, so wiring it is a small declared
> deviation nearer RESTORES than ENABLES. `idaac` and `ppg` have no mechanism, so periodic saving
> there is authored behaviour and a genuine deviation.
>
> **A second measured fact about the during-train curve, while reading the same code**: the
> RL-ViGen five split `num_eval_episodes` *across* the ten scenes — `per = num_eval_episodes //
> len(scenes)` (`train.py:152`). At the shipped default of `num_eval_episodes: 10` that is **one
> episode per scene**, and the per-scene number in `eval.csv` is a single episode of a stochastic
> task. Our probes pass `EVAL_EPISODES=20`, giving two. Nothing is wrong with the code; the point
> is that a during-train per-scene value is far noisier than its presence in a CSV suggests, and
> the pooled ten-scene mean is the only part of it worth reading at these settings.
>
> **DEFAULT SET, awaiting approval: report the cross-baseline table at the ENDPOINT**, the one
> frame all twelve supply; take the two free configuration wins so `dmc_gb` and `ibac_sni` gain a
> curve at no fidelity cost; leave `idaac`/`ppg` terminal-only rather than author saving into two
> clones for a curve nobody has yet asked for. This does **not** settle §3b #3's headline
> question below — it removes the option of pretending a twelve-baseline curve is available.

**Open, not decided**: whether the headline is the endpoint or the best-on-a-held-out-criterion.
Selecting the best checkpoint *by the metric being reported* is a garden-of-forking-paths hazard
and I would refuse it; selecting by a separate criterion is defensible.

---

## 4b. Seeds, and what a given seed count licenses (§3b #4)

**DEFAULT SET 2026-09-04, awaiting approval.** The seed count is the axis that actually costs
compute, so the rule is about *claims*, not about a number to buy in advance.

**Seeds are spent adaptively, not uniformly.** Spreading three seeds across twelve baselines before
knowing which reach competence buys precision on rows that are at the floor, where
[C55](CONSTRUCTION.md#c55) already says the ratio is undefined rather than small. The order is:
one seed everywhere to find who is competent (§3 gate), then seeds concentrated on the comparisons
that are actually live.

**What each seed count licenses, stated so a later table cannot quietly exceed it:**

| seeds | admissible claims |
|---|---|
| **1** | *existence* — "this baseline reaches success 1.00 in the training regime at 100k"; and *floor* — "this baseline is indistinguishable from random in eval-easy". Both are about one run and neither orders two baselines. |
| **2** | the above, plus "the effect reproduced", which is a statement about reproducibility, not about size. |
| **3+** | a ranking claim, and only between baselines that each have 3+, at the resolution [C18](CONSTRUCTION.md#c18) allows — **~31% at five seeds**, worse at three. |

**The two results in hand are both single-seed and both stay inside row 1**: `drqv2`'s 0.30%
retention is an existence-plus-floor claim, and `ibac_sni`'s entropy collapse is an existence claim
about one run. Neither orders anything, and the write-ups say so.

**This is a rule about reporting, so it costs nothing and can be adopted before the budget is
decided.** It is also the rule that makes the cheap production shapes usable: a one-seed sweep is
not a weak version of the three-seed answer, it is a *different and legitimate* question — who is
competent — asked first because the answer changes where seeds are worth spending.

---

## 5. On-policy vs off-policy on frames seen

The owner's instruction: report it, let the audience see. Agreed, and the record already supports
it — `frames` is the executed count, and today's pass showed 9216 / 10000 / 10112 / 10240 for a
requested 10,000, because each family floors to its own rollout quantum. The table prints what ran.

No harmonisation. A phasic or on-policy method spending its budget differently is part of what is
being compared.

---

## 6. Storage, and the local-space constraint

At 6e5 with the 50k grid: ~12 stamps × 12 baselines × N seeds. A `drqv2` snapshot is ~104 MB, so
one seed is ~15 GB and three seeds ~45 GB. **This lives on the production machine, not here** —
local free space is ~12 GB.

**Proposal**: checkpoints stay remote; only *records* (JSONL, kilobytes) come back by default. A
checkpoint is fetched locally only for a specific investigation, and deleted after.

**The mechanism now exists rather than being a rule to remember.** `run_probe.sh` emits
`records.jsonl` as an optional **separate job output** (`RECORDS_OUT`), so a caller can declare
`- records.jsonl: RECORDS` and fetch ~100 KB instead of the archive. `result.tgz` is unchanged and
still contains the records, so every existing configuration means what it meant. Today's session
is the cautionary case: one five-cell archive was 791 MB and the endurance pack 207 MB, and I
extracted selectively to avoid unpacking four checkpoints I did not need.

---

## 7. What remains open after this document

- **§3b #1 headline metric** — resolved *in shape* by §2 (emit everything, select later), but the
  headline column still has to be named for the deliverable.
- **§3b #4 seeds** and **§3b #5 budget** — untouched here; #5 in particular deserves the owner's
  "can numbers decide it" question taken seriously rather than defaulted to 6e5 because RL-ViGen
  says so.
- **Evaluator family coverage — 7 families, 12 of 12 rows. COMPLETE as of 2026-09-04.**
  `rlvigen` (five baselines), `dmc_gb` (two), `idaac`, `ppg`, and — added 2026-09-03/04 —
  `ibac_sni` and `alda`. All six drive the baseline's **own** action path.

  Two things the new ones settle, both by reading each repo's own evaluator rather than improvising:

  - `ibac_sni` — its `Agent` loads from a **directory**, appending `model.pt` itself, so the
    harness stages the checkpoint under that name and lets *their* loader load it. Reaching past it
    to `torch.load` would mean the acting object is one we built.
  - `alda` — its modules do not exist until `initialize_env_dmc` then `build` have run, so the
    checkpoint cannot be loaded standalone; `_alda_trainer` runs that sequence through alda's own
    factory. Its action call is `select_action(preprocess_obs(obs['rgb'][None]))` and its step is a
    5-tuple with info fifth — copied from its `evaluate()`, because the extraction, the batch axis
    and the preprocessing are all part of *how alda acts*.

  **`ctrl` was the hardest and is done.** JAX end to end. Its checkpoint is
  `flax.serialization.to_bytes(train_state)`, and `from_bytes` **fills a target rather than
  constructing one**, so the TrainState has to be rebuilt first — the model with ctrl's own dims and
  flags, `model.init` on the same fake batch shapes, and the same optax chain, because the optimiser
  state is part of what was serialised. A wrong flag there produces a differently-shaped model
  rather than an error, which is why `CTRL_DEFAULTS` names each one against `train_ppo.py`.

  Establishing it also produced the estimator correction: `select_action(..., sample=False)` takes
  `pi.mode()`, but `train_ppo.py:244`/`:253` pass `sample=True`, so **ctrl samples** and the
  estimator axis is 4/8 rather than 3/9. That is the argument for building a family *before*
  reporting a baseline's numbers rather than after.

  **`alda` also widens its own grid.** It ships three regimes — `train`, `eval-easy` (`color_env`),
  `eval-hard` (`distract_env`) — and no `eval-medium`. Its `_build` chain takes the mode as an
  argument, so our harness constructs any RL-ViGen regime through *its* wrappers. That is the
  harness widening the grid, not a change to alda.

  **Validation status, stated because it is not the same as "works".** All six run and produce
  plausible magnitudes. Only the natives are checked against their own trainer's number (131.57
  against a logged 135.71). The one non-native comparison attempted was underpowered — see the
  guard note in §1 — so the rest rest on construction rather than measurement.

- **Whether our harness driving a foreign `act` is faithful** — §1's guard is stated, not run, for
  the seven non-native families.
