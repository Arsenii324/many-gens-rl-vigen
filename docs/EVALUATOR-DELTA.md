Written 2026-09-04.

# The shared evaluator, against each baseline's own — a delta ledger

## Why this file and not a number

`scripts/audit_shared_evaluator.py` compares our harness's number to each baseline's own and grades
the ratio. That is **corroboration, not proof**. Agreement to 3% shows two instruments produced
similar numbers on one checkpoint; it does not show they measure the same thing, and it lets an
undeclared difference hide behind "close enough" until the checkpoint that separates them.

This project's standing rule is the other way round: **two implementations are not the same until
shown to be, every delta is deliberate, and every difference a strict reviewer would notice is
explicit.** `INTEGRATION-DELTA.md` applies that to the twelve algorithms. Nothing applied it to the
*evaluator*, which is now the instrument that would produce every reported number under
[`EVAL-PROTOCOL.md`](EVAL-PROTOCOL.md) §1. This file is that obligation.

**Status: incomplete and honest about it.** Each row below is what I established while writing the
family, by reading that baseline's own evaluation loop. Rows marked *unverified* were not read
line-by-line and should not be trusted as complete.

---

## The deltas that apply to every family

| # | delta | class | why |
|---|-------|-------|-----|
| E1 | **Global RNG seeded before env construction** | **DELIBERATE, ours** | [C69](CONSTRUCTION.md#c69): robosuite's `UniformRandomSampler` draws door placement from bare `np.random.uniform`, so without this the door moves between processes recording an identical seed (~1.6 cm measured). **Correction, 2026-09-04 — this row said "upstream's own `train.py:47` does the same via `set_seed_everywhere`, so this restores their behaviour rather than adding one", and that is overstated.** `set_seed_everywhere` is called **exactly once in `train.py`, at line 47, during `__init__`** — grep the file, there is no second call. `_eval_regime` never re-seeds; it builds `_make_eval_env(mode, scene_id)` fresh on every eval and each `reset()` draws the door placement from the global numpy RNG *in whatever state training left it*. So their eval at 25k and their eval at 50k see different placements, and neither is reproducible from the checkpoint alone. Ours seeds per eval, which **is** an addition at eval time, not a restoration of it. **This is a reproducibility difference and NOT a bias**: both draw from the same uniform placement distribution, so both are unbiased for the mean. The practical consequences run the other way from each other — theirs gets fresh placements each eval (more independent samples across the curve), ours gets the *same* placements every time (a paired comparison across checkpoints, which is lower-variance for exactly the comparison we want and is why the fixed episode seed exists). Added to `dmc_gb`/`idaac`/`ppg` only on 2026-09-03 — before that it was missing and their placements did not match the natives'. |
| E2 | **`torch.use_deterministic_algorithms(True)`** (rlvigen family only) | **DELIBERATE, ours, and NOT upstream** | [C70](CONSTRUCTION.md#c70): without it two processes with identical weights and observations differ by ~1e-7, which Door's `hinge_qpos > 0.3` threshold can amplify into a different success. It makes our number reproducible; it does **not** make it upstream's number. A strict reviewer should be told this. |
| E3 | **Evaluation seed is a fixed constant, not the training seed** | **DELIBERATE, ours** | Added 2026-09-03. Otherwise each training seed evaluates on different door placements and the across-seed spread carries a term with no algorithmic meaning. |
| E4 | **Regimes and scenes are the harness's, not the baseline's** | **DELIBERATE, ours — the point of the exercise** | The whole purpose of a shared grid. It is a *widening*: no baseline is prevented from its own regimes, but every baseline is asked for regimes and scenes its own evaluator would not have swept. |
| E5 | **Platform is the container** | **FORCED** | [C95](CONSTRUCTION.md#c95). Not a choice. |
| E6 | **Per-episode success flags are retained, not just the count** | **DELIBERATE, ours — additive** | Added 2026-09-04 to all seven families. It is **not a new measurement**: the flag is the same `succeeded` variable the count was already summing, kept per episode instead of collapsed. No baseline's own evaluator retains this, so no baseline is being asked for anything new, and the loop's behaviour, RNG draws and env interaction are unchanged. What it buys is the question the count cannot answer — *what did the episodes that succeeded score* — which on Door separates a policy that opens the door from one banking shaped reaching reward, and a per-scene Wilson interval on SR that a scalar rate cannot carry. The risk it introduces is silent misalignment: success-conditioned return is computed by masking one array with the other, so an off-by-one does not raise, it pairs episode *i*'s return with episode *j*'s outcome and returns a plausible number. Pinned by `tests/test_eval_loop_measurement.py::test_per_episode_success_flags_align_with_returns`, which asserts equal length **and** that the flags sum to the count computed on the separate path. |

---

## Per baseline

### `drqv2 svea drq sgqn curl` — the RL-ViGen five

| aspect | theirs | ours | delta |
|---|---|---|---|
| loop | `train.py::_eval_regime` | `eval_across_scenes.run_scene` | **copied**, per its own docstring, not reconstructed |
| action | `agent.act(obs, global_step, eval_mode=True)` | identical | none |
| eval mode | `utils.eval_mode(agent)` | identical | none |
| success | `env.last_info['success']`, any step | identical | none (patch P11's convention) |
| env | `robo_make(name, action_repeat, frame_stack, seed, mode, scene_id)` | identical call | none |
| extra | — | a verification `reset()`/`step()` and an 8-step probe **before** the episode loop, to read back the applied scene and regime | **DELIBERATE, ours.** It consumes RNG draws before the first episode, so our placement sequence is offset from theirs by a fixed amount. Harmless for a mean over N episodes; **not** harmless for an episode-by-episode comparison, and it is the reason our 131.57 and their 135.71 should not be expected to match exactly. |

### `rad soda` — dmc_gb

| aspect | theirs | ours | delta |
|---|---|---|---|
| loop | `src/train.py::evaluate` | `run_scene_dmc_gb` | **VERIFIED 2026-09-04**, read line-by-line. Reset, step, accumulate and the any-step success convention are identical. Their loop additionally calls `video.init/record/save`, which touches no returned quantity. |
| action-path guard | `with utils.eval_mode(agent)` | was `with torch.no_grad()`; **now both** | **WAS A REAL DIFFERENCE, now removed.** `utils.eval_mode` (`src/utils.py:12`) is a context manager that calls `model.train(False)` and restores; it does **not** disable gradients — their `select_action` already does that internally, so our `no_grad` was redundant rather than equivalent. On today's action path the two give identical actions, **verified not assumed**: `Actor` is encoder + Linear/ReLU, and the encoder is Conv2d/ReLU/LayerNorm/Tanh/Linear, with no train/eval-sensitive layer. That is a property of the architecture, not of the code — `modules.SODAMLP` holds an `nn.BatchNorm1d`, which at this loop's batch size of 1 would read one sample's own statistics in train mode. Ours now calls theirs, so the equivalence no longer rests on the coincidence. |
| render / crop | 100, cropped to 84 by `modules.CenterCrop` inside the encoder | identical (`--image-size` default 100) | none — the crop is inside the network, so it applies to both. Note this makes rad/soda's *effective field of view* an 84 window of a 100 frame, unlike the ten baselines whose render is used whole; see the `crop policy` axis in `audit_comparability_seam.py`. |
| N | `--eval_episodes`, **default 30** | our `--episodes` | **DELIBERATE**: we set N; theirs is a flag we also set. Their default is 30, which is larger than the 10–20 used in our grids so far. |
| env seed | `test_env` is built with **`seed = args.seed + 42`**, against the train env's `args.seed` (`src/train.py:78-95`) | one seed, passed through | **UNDECLARED UNTIL 2026-09-04, now declared.** The +42 is upstream's deliberate offset: it makes their eval regime a *different visual draw* from training rather than the same instance re-skinned, since the seed drives `VGBWrapper`'s `random_state` for colour and lighting. Ours passes a single fixed episode seed, so **our eval-easy instance is not theirs** — the same regime, a different sample from it. Not a bias: both draw from the regime's own distribution, and ours is fixed so checkpoints are compared on identical appearances (E3 above). It does mean a number of ours and a number of theirs differ by more than episode sampling, which matters for the burden-of-proof comparison and did not previously appear anywhere. |
| warmup | `--init_steps` 1000, plus a **burst** of `init_steps` updates at the moment training begins (`train.py:168`) | not applicable — we evaluate a saved policy | none for the evaluator, but it means an "eval at step N" during *their* training is not comparable to one at the same N for a baseline with a different warmup ([C55](CONSTRUCTION.md#c55) floor aside, the rlvigen five seed 4000 frames and the on-policy four seed none). |

### `idaac`

| aspect | theirs | ours | delta |
|---|---|---|---|
| action | `act(inputs)` with `deterministic=False` | identical (samples) | none |
| env | `make_rlvigen_venv` | identical | none |
| episode accounting | `test.py::evaluate` takes the **first 10 completed episodes** across a vec env | ours runs N episodes per scene sequentially | **DELIBERATE and material.** Their N is a race across parallel envs; ours is a fixed count per scene. Different sampling of episode *starts*, and one reason the 1.663/3.01 comparison is not like-for-like. |
| numpy shim | `train.py:5` sets `np.bool = bool` | replicated in `_idaac_setup` | none — applied identically |

### `ppg`

| aspect | theirs | ours | delta |
|---|---|---|---|
| own evaluator | **none exists** | `_launch/ppg_eval.py`, ours | **the whole loop is ours.** There is nothing to be faithful to; the burden here is not "match theirs" but "state what we built". Uses their `Roller`, `VecMonitor2` and `PpoModel.act`, so the moving parts are theirs. |
| action | `act` samples; no deterministic path exists in the repo | identical | none |

### `ibac_sni`

| aspect | theirs | ours | delta |
|---|---|---|---|
| model load | `utils.load_model(model_dir)` | identical — checkpoint staged as `model.pt` so **their** loader loads it | none |
| action | `Agent.get_actions`, `argmax=False` → samples | identical | none |
| envs | `ParallelEnv` over `--procs` (launcher passes 1) | single env | none at procs=1; **would differ at >1** |
| episode accounting | `log_done_counter` over a vec env | N sequential episodes | **DELIBERATE**, same shape as idaac's |

### `alda`

| aspect | theirs | ours | delta |
|---|---|---|---|
| action | `select_action(preprocess_obs(obs['rgb'][None]))` | **copied exactly** | none |
| step unpacking | 5-tuple, info fifth | identical | none |
| success | `info['success']`, any step | identical | none |
| env chain | `DMCObsWrapper(FrameStack(_RoboRGB(robo_make_env(...))))` | identical, built through **their** wrappers | none |
| regimes | three: `train`, `color`→eval-easy, `distract`→eval-hard | any RL-ViGen regime via the same `_build` chain | **DELIBERATE widening** (E4). `eval-medium` is a regime alda's own evaluator cannot produce. |
| trainer | constructed by `train.py`, then `load_checkpoint` | same sequence via `_alda_trainer` | none — their factory, their order |

### `ctrl`

**No family exists.** JAX end to end, a flax msgpack checkpoint, and an `evaluate_ppo.py` whose
helper is discrete-only. Nothing to declare yet, and nothing may be reported for `ctrl` through the
shared evaluator until there is.

---

## What this ledger says about the proposal

**Three deltas are material and none was previously written down**: E2 (determinism, ours alone),
the rlvigen verification probe (RNG offset), and the episode-accounting difference for `idaac` and
`ibac_sni` (a race across parallel envs versus a fixed sequential count). Each is defensible; none
should be discovered by a reviewer instead of read here.

**One family has no reference at all** (`ppg`), so "faithful to its own evaluator" is not even the
right question there — the right one is whether our loop is a correct use of *their* rollout
machinery, which it is by construction and unvalidated by measurement.

**The ratio audit stays**, demoted to what it is: corroboration that the declared deltas do not add
up to a behavioural difference on the checkpoints tested. It is not the proof, and on a floored
checkpoint it is not even evidence.
