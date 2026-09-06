# Part 1 — the originals, running, with the change count as the deliverable

Started 2026-08-17. **This supersedes the port-and-harness approach** that `docs/STATE-2026-08-16.md`
describes. That document remains accurate about what `rlgen/` contains; it is no longer the plan.

## The null, and what counts as work

**The null is the original repository, cloned, running its own `train.py`.** Duplication across
baselines is free — each repo brings its own loop, buffer, logger and eval, and that is the
default state, not a problem to solve. **Any join is work and carries the burden of proof.**

A code change is a change. An import change is a change. A rewrite is a rewrite. Fewer changed
lines is better, and a changed line in a load-bearing place counts for more than one line.

`python scripts/deviations.py` prints the exhaustive count: every clone lives at
`runnable/<name>/` with a `PRISTINE:` first commit, so `git diff` against it *is* the complete
statement of what we changed. Nothing has to be remembered or kept in sync.

**That was not true until 2026-08-17, and the failure is worth keeping.** `git diff` is blind to
untracked files, so every file this project ADDED to a clone was missing from both the count and
the exported patch — including `alda/specs/train_alda_robosuite_door.yaml`, which this very
document called a deviation. The alda patch could not have rebuilt the alda clone. `deviations.py`
now runs `git add -N` over untracked paths first, and prints the ones it deliberately ignores
(run artifacts, the `data` symlink) rather than dropping them silently. The script also
re-derives each PRISTINE commit's claim against the `ext/` repo it names and exits 1 on a
mismatch — it caught one on its first run (`ibac_sni` was labelled with a different vendored
base's SHA), and the red/green behaviour was verified by deliberately mislabelling and restoring.

## Status

**`bash runnable/_launch/smoke_all.sh` reproduces the table below.** Last full pass
2026-08-17 05:24, **12/12 TRAINED, harness exit 0**, 66 minutes wall-clock on this M2 Pro —
verbatim output in `docs/smoke-2026-08-17.txt`. It runs every baseline
briefly and judges each on *evidence of training* — a metric line only a real update produces —
rather than on an exit code, which would pass a run that built an env and stopped. Two non-zero
exits are expected and named in its header: `ctrl` exits 1 on success (absl calls
`sys.exit(main(argv))` on a returned tuple) and `ppg` is capped by `timeout` because it has no
stopping point below 100M interacts.

| baseline | clone | runs on RL-ViGen robosuite | deviation |
|---|---|---|---|
| `svea` | *none, by design* | **yes** — RL-ViGen's own `train.py`, exit 0; Places365 overlay live | 0 files; P1–P20 only |
| `drqv2`, `drq`, `sgqn` | *none, by design* | **yes** — each smoke-run individually, exit 0, training | 0 files; P1–P20 only |
| `curl` | *none, by design* | **yes on CPU** (exit 0, training); **fails on MPS**, see below | 0 files; P1–P20 only |

All five re-verified under P12 on 2026-08-17: exit 0 each, and each now constructs **two
different** envs — the logs read `Now the mode is train` then `Now the mode is eval-easy`, where
before P12 both said `train`. Verbatim table in `docs/smoke-p12-2026-08-17.txt`.
| `rad` | `runnable/dmc_gb` | **yes** — 1k steps, real losses, train + eval-easy | shared, below |
| `soda` | `runnable/dmc_gb` | **yes** — 1k steps, `aux_loss` live, train + eval-easy | shared, below |
| `alda` | `runnable/alda` | **yes** — own `scripts/train.py` + spec; `episode_reward` and `episode_reward_distracting` | 4 files, +223/−8 |
| `ppg` | `runnable/ppg` | **yes** — own `train.py` CLI; PPO **and** the auxiliary phase, 34 full PPG cycles (68 aux epochs); eval via `_launch/ppg_eval.py` | 8 files, +289/−9 |
| `idaac` | `runnable/idaac` | **yes** — own `train.py`; train 28.15 vs eval-easy 2.64, exit 0 | 8 files, +492/−45 |
| `ibac_sni` | `runnable/ibac_sni` | **yes** — own `scripts/train.py`, bottleneck + SNI-vib active; **and its own `scripts/evaluate.py` measures a saved policy in a held-out regime** | 10 files, +630/−183 |
| `ctrl` | `runnable/ctrl` | **yes** — own `train_ppo.py`; PPO + cluster + target EMA; in-distribution 7.177 vs eval-easy 4.315 | 5 files, +477/−84 |

**No candidate-wide total is asserted in this checkout.** `scripts/deviations.py` marks four clones
PARTIAL because their pristine histories omit non-source assets, so summing their present diffs
would read as an authored-total claim that the tool explicitly refuses to make. The per-clone figures
above are re-derived on every docs test; calculate a total only in a checkout where all six clones
are whole. `--export` writes `runnable/_patches/<name>.patch`, which IS version-controlled even
though the clones are not.

Both insertion counts are printed because each flatters a different story: `+` is inflated by the
long justifying comments this project writes, and `code+` hides how much a reader must actually
read. Neither is the honest number on its own.

### Why the RL-ViGen five have no clone

RL-ViGen ships `algos/{drqv2,svea,sgqn,curl,drq}.py` **together with** the benchmark, so "the
original repository running its own `train.py`" already *is* `RL-ViGen-upstream`. Cloning it five
times would fabricate five copies of one tree and make the change count look like work nobody did.
Their deviation is the patch set every other baseline also goes through:
`python setup/apply_patches.py --check`. That check also verifies the tree carries *nothing*
undeclared, in both directions — a hand-edit nobody wrote down, and a declared patch that has
gone missing. Untracked paths are judged against a two-entry allow-list rather than a wildcard,
so a stray `.py` in the vendored tree still fails; verified by putting one there and watching it
fail, then removing it.

**Two launcher facts the five needed, both zero source lines.** `algos/sgqn.py` does a bare
`import drqv2` and `algos/curl.py` a bare `import drq` — module paths that resolve only if
`algos/` is itself a top-level `sys.path` entry, so it is on `PYTHONPATH`. Without it hydra
reports `Error locating target 'algos.sgqn.SGQNAgent'` and swallows the `ModuleNotFoundError`
underneath, which is why this looked like a config problem for one round.

**`curl` is the one baseline that does not run under the MPS shim.** It fails with
`scatter: index -1 is out of bounds for dimension with size 256`, reported at a
`torch.as_tensor` call — MPS surfaces errors when the queue flushes, not where they happen, so
that location is not the culprit. The same command with `device=cpu` trains to completion,
exit 0. So this is an MPS backend limitation in CURL's contrastive loss, not our integration and
not RL-ViGen's code, and it does not bear on the T4. Isolated by running it, not by assuming.

## Launch environment is not a deviation, but it is not free

Recorded per baseline in `runnable/_launch/<name>.sh`, because a run needing undocumented
environment is not reproducible at any change count.

**`runnable/_shim/sitecustomize.py` — zero repo lines.** These repos are CUDA-native; `dmc_gb`
alone calls `.cuda()` at 22 sites across 7 files, `idaac`'s `IDAACRolloutStorage` hardcodes
`self.device = 'cuda'`, and `algo/idaac.py` constructs `torch.cuda.FloatTensor`. Rewriting those
would be dozens of authored deviations bought purely for local convenience, while the
authoritative runs go to a T4 where the originals run **unmodified**.

**The cost, stated because it is easy to forget: a green local run does not prove the CUDA path.**
The shim downcasts float64 to float32 (MPS has none) and reports `is_cuda` for MPS tensors. Both
are announced at runtime. **The authoritative smoke for every baseline is on real CUDA** — Kaggle
or DataSphere — and is still owed.

Not every baseline needs it, and the reason is worth keeping: `ppg` and `ibac_sni` both select
their device through `torch.cuda.is_available()` / `torch.has_cuda` and fall back to CPU on their
own, so they run shimless. `ctrl` is JAX and the shim is irrelevant to it.

**`runnable/_shim/no_tf/tensorflow.py` — a TensorFlow that raises on any attribute access.**
`idaac` needs `baselines.common.vec_env`, whose `running_mean_std.py` imports TensorFlow at module
scope for a class (`TfRunningMeanStd`) that `VecNormalize(use_tf=False)` never constructs. An AST
pass over the import chain shows the complete set of `tf.*` names reachable at import time is
exactly `['float32']`, as a default argument of a function nothing calls; that one name is a
sentinel and everything else raises. Installing multi-gigabyte TensorFlow to satisfy an
unreachable import would land on every environment this baseline ever runs in.

## Deviations, per clone

### `dmc_gb` (covers `rad`, `soda`, and the SAC they share) — 7 files, +135 / −10

| file | change | why |
|---|---|---|
| `src/env/wrappers.py` | +29 / −1 | a guarded `if domain_name == 'robosuite'` branch in `make_env` and an `_RGBOnly` wrapper. RL-ViGen's robosuite env is natively gym-style with a `Box(7,)` action space and a `{'rgb': (3,H,W) uint8}` observation, so the seam is one call — `dmc2gym.make` becomes `robosuitevgb.utils.make_env`. **No existing logic modified.** `train.py` itself needs **zero** changes: it already builds a train env and a `test_env` at `--eval_mode`, which is exactly RL-ViGen's train / eval-easy structure. |
| `src/arguments.py` | +1 / −1 | accept `eval-easy` / `eval-medium` / `eval-hard` alongside DMC's own mode vocabulary |
| `src/utils.py` | +2 / −2 | `np.array(x, copy=False)` → `np.asarray(x)`; NumPy 2 made the former an error |
| `setup/config.cfg` | +1 / −1 | fill the repo's own `"/your/data/path/here/"` placeholder |

### `alda` — 4 files, +223 / −8

One guarded branch in `trainers/alda_trainer.py::initialize_env_dmc` building all three envs and
returning early, so no existing line is modified. The regimes map onto RL-ViGen's own:
`env`→`train`, `color_env`→`eval-easy`, `distract_env`→`eval-hard`.
`specs/train_alda_robosuite_door.yaml` is a **new file**, which is this repo's own configuration
mechanism. Eval video is off: `VideoRecorder.record` calls `env.render(mode=…, height=…, …)` and
RL-ViGen's `VGBWrapper.render` accepts none of those; `VideoRecorder(None)` disables itself by the
repo's own logic.

**[2026-09-06] +18 lines**: the `train_metrics.jsonl` persistence write (2026-09-05, `use_wandb=False`
production runs otherwise discard every metric) had a latent bug — a residual 0-d `torch.Tensor`
from the averaging loop above it crashes `json.dumps` where `wandb.log` tolerated it silently.
Fixed with a `default=` handler scoped to this addition. See `notes/CORRECTIONS.md` #91.

### `ppg` — 8 files, +289 / −9

`envs.py` gains `get_robosuite_venv` and a one-line dispatch in `get_venv` on a `robosuite:`
prefix. The venv is `gym3.ConcatEnv` of `gym3.FromGymEnv` — **gym3's own classes**, already a
dependency — over a wrapper that transposes CHW→HWC and declares a real uint8 Box.

The continuous head is the interesting part, and it is authored. `distr_builder.py`'s
`_make_normal` was **unreachable** upstream: `tensor_distr_builder` raised on every non-Discrete
eltype, so nothing called it, and its body hardcoded `scale=1.0` under the authors' own
`warnings.warn("Using stdev=1")`. It now consumes `[loc | log_stdev]`, where the log-stdev half is
a **state-independent `nn.Parameter`** on `PhasicValueModel` — that is what PPO does for
continuous control. Emitting the stdev from the policy head instead would have needed zero lines
in `ppg.py`; it was rejected because a state-dependent stdev is a different algorithm, not a
cheaper spelling of this one. `torch_util.register_distributions_for_tree_util` gains `Normal`,
because `aux_train` stores `oldpd` in the segment dict and slices it per minibatch.

**Evidence the head is right:** logged entropy 9.9333 against 7 × ½log(2πe) = 9.9326 for a 7-dim
unit Gaussian, and the auxiliary phase's `pol_distance` — a Normal–Normal KL — trains at ~1e-4.

**Continuous adaptation:** the reference line computes `td.kl_divergence(oldpd, pd).mean()`, which
is correct for its categorical path. Here the authored Box head returns a 7-coordinate Normal while
PPO log-probabilities sum event coordinates, so the implementation sums the KL event dimension
before averaging samples. This preserves `beta_clone`'s scale at the adapted design point; the
literal categorical reduction would make it about 7× weaker.

### `idaac` — 8 files, +492 / −45

`distributions.py` +57: `FixedNormal`, `AddBias` and `DiagGaussian` **copied verbatim** from
`ikostrikov/pytorch-a2c-ppo-acktr-gail@41332b7`, which is the file's own upstream — `init`,
`FixedCategorical` and `Categorical` in it are byte-identical to that source. IDAAC dropped the
Box branch because Procgen is discrete; this restores it rather than inventing one. `AddBias`
lives in the upstream's `utils.py` and is placed next to its only caller so the change stays in
one file.

`model.py` +33/−7 restores the upstream `action_space`-based dispatch that IDAAC replaced with a
bare int, and makes `PolicyResNetBase` concatenate a Box action directly instead of one-hotting
it — that head is IDAAC's own advantage mechanism, so this is a real continuous adaptation.
It also **fixes a latent bug**: `num_actions` was never forwarded from `IDAACnet` into the base,
so the advantage head sat at its default 15 — exactly right for Procgen and silently wrong for
anything else.

`envs.py` +62 adds `make_rlvigen_venv`, which puts RL-ViGen behind the **same** VecEnv stack
(`VecMonitor` → `VecNormalize(ob=False)` → `VecPyTorchProcgen`) with baselines' own `DummyVecEnv`
replacing `ProcgenEnv`. It also supplies `info['level_seed']`, which is not bookkeeping:
`IDAACRolloutStorage.before_update` pairs each observation with another carrying the same
`level_seed` and asks the order classifier which came first — that key *defines* what "the same
instance" means. **Different from Procgen, and it bears on IDAAC specifically:** a Procgen env
draws a new level every episode, so one rollout spans many instances; here each env is one
instance for the whole run and instance diversity per batch is capped at `num_processes`.

### `ibac_sni` — 10 files, +630 / −183

Drives `torch_rl/`, the authors' **own PyTorch** implementation, not the TF `coinrun/` branch.
`utils/get_obss_preprocessor` already had a generic `Box([H,W,3])` branch — written for RGB envs,
unused by MiniGrid — so preprocessing needed no change at all; the wrapper only has to present
that shape.

**The one deliberate scaling choice:** `utils/format.preprocess_images` does
`torch.tensor(images, dtype=torch.float)` with **no division**. Correct for MiniGrid, whose
"image" is small category indices; wrong for 0–255 RGB by two orders of magnitude. The division by
255 is in the seam wrapper, not in the repo's preprocessor.

`model.py` +28/−7: the Gaussian head, with `Independent(Normal, 1)` chosen so `log_prob()` and
`entropy()` return shape `(B,)` exactly as `Categorical` does — which is what leaves
`algos/ppo.py` untouched. `algos/base.py` +10/−2: the action buffer gains a trailing dimension and
a float dtype, and `exps.action` reshapes with `*self.actions.shape[2:]`, which is empty for
Discrete and therefore byte-equivalent there.

**Evidence:** logged `H 9.935`, the same 7-dim unit-Gaussian entropy, with episode length 500
matching robosuite's horizon.

### `ctrl` — 5 files, +477 / −84

The only JAX baseline. `vec_env.py` +85 adds `RLViGenVecEnvCustom` with interface parity to
`ProcgenVecEnvCustom`, reusing the `VecMonitor`/`VecNormalize` **vendored in that same file**, plus
`_SyncVecEnv` — a minimal vectoriser, authored, because ProcgenEnv is already vectorised and this
file therefore ships none.

`models.py` +64/−5: `continuous` flag, a state-independent `log_std` param declared
unconditionally (so `state_update`, which copies params by name, sees the same key set either
way), `make_pi` returning `MultivariateNormalDiag` — again chosen for `(B,)`-shaped `log_prob`
and `entropy` — and `embed_action` replacing the one-hot in CTRL's cluster embedding.

**Two findings about the reference, both verified against the pristine `ext/` copy:**

1. **`ctrl_public@7a118c8` cannot run its own `ppo_ctrl` algorithm.** `algo.py:203` comments out
   `scores_w_target = w_clust_target @ protos` while line 211 still reads `scores_w_target`, so
   `loss_cluster` raises `NameError` the first time `update_cluster` is called. `w_clust_target`
   *is* bound by the tuple unpacking above, so restoring the authors' own two commented lines is
   the minimal repair and the only one whose intent is unambiguous. Not a porting problem and not
   specific to RL-ViGen.
2. **Recorded, not fixed:** the MYOW loop is `for k_idx in range(myow_k)` but indexes
   `indx[:, 0 + 1]` — `k_idx` is never used, so every iteration draws the same nearest cluster and
   differs only in the random member draw. Changing it would change the algorithm.

The rest are version-drift repairs, each labelled in place: `jnp.split` for the removed
`.split` array method, `.at[].add()` for `jax.ops.index_add`, `jax.tree_util.tree_map` for
`jax.tree_multimap`, plain-dict updates for `FrozenDict.copy(add_or_replace=)`, and an `int32`
index buffer where a float32 one was fed to `take_along_axis`. `requirements.txt` pins
`jax==0.2.17 / flax==0.3.4 / optax==0.0.9`; no wheels exist for those on python 3.11 arm64, and
this runs on `jax 0.4.35 / flax 0.10.2 / optax 0.2.3` — pinned there because `tensorflow_probability`
0.25's JAX substrate, which `models.py` imports, breaks on jax ≥ 0.5. That gap is real and is
recorded rather than assumed away.

**`ctrl` exits 1 on success, and that is upstream, not a failure.** `main()` returns
`(returns_ood_acc, mean_ood)` and `__main__` calls `absl.app.run(main)`, which does
`sys.exit(main(argv))` — Python turns a non-int return value into exit code 1. The run printed
its final line first. Anyone wiring this into CI must not treat a nonzero exit as a failed run.
The repo also prints `JAX BACKEND: cpu` itself (`algo.py:637`), which is how the local backend
claim above is checked rather than assumed.

`evaluate_ppo.py` is left discrete-only. It is a standalone script that `train_ppo.py` never
imports, and it calls `apply_fn(params, state)` expecting `(value, logits)` while `CTRLModel`
returns `(value, pi), (...), Q` — so it does not match its own model either. Declared gap.

## RL-ViGen patches P6–P14 (P1–P5 predate this part)

`setup/apply_patches.py`, pinned by `Protocol.env_patches` and two contract tests. Each is stated
so its effect on a Linux/CUDA run is checkable:

- **P6 — render size settable.** `robo_config.yaml` fixes 84×84. At a native 84 render RAD's own
  `random_crop` degrades to the identity by its own `crop_max <= 0` guard, so **RAD run
  faithfully is exactly SAC**; SODA is louder — `assert x.size(-1) == 100` — and cannot run at
  all. Both are the authors' code behaving correctly for an input their papers do not use. P6
  turned out to be the general key rather than a RAD/SODA special case: ALDA's encoder is built
  for 64, IDAAC hardcodes `nn.Linear(2048, …)` which is 32×8×8 and *only* 64, PPG's paper is
  Procgen at 64, and CTRL's `model.init` example is literally `jnp.zeros((1, L, 64, 64, 3))`.
  Off unless `RLVIGEN_IMAGE_SIZE` is set.
- **P7 — `MUJOCO_GL` defaulted, not forced.** `train.py`/`eval.py` opened with
  `os.environ['MUJOCO_GL'] = 'egl'`; there is no EGL on macOS, so `import train` died at
  `wrappers/dmc.py` before reading an argument. `setdefault` is strictly weaker: with the variable
  unset — every Linux, Kaggle and DataSphere run — the environment is byte-identical.
- **P8 — the outermost action spec stays float32.** `ReplayBufferStorage.add` asserts
  `spec.dtype == value.dtype`; the spec said float64 and every agent emits float32, so it fired on
  the **first stored transition**. Cause, read rather than guessed: `robo_make` puts
  `action_scale.Wrapper` *outside* `ActionDTypeWrapper`, and dm_control 1.0.14 does
  `minimum = np.array(-1.0)` before `np.result_type(...)`, which re-promotes to float64. (Not
  NEP 50 — `np.result_type(-1.0, 1.0, np.float32)` is float32 on numpy 2.4.6; the python floats
  are made *strong* by being turned into arrays first.) The patch adds a second
  `ActionDTypeWrapper` outside rather than moving the first: no existing line changes, and it is
  provably inert where the spec is already float32. **This means RL-ViGen's own five could not
  train on robosuite at all with dm-control 1.0.14.**
- **P9 — robosuite keeps a `MUJOCO_GL` the caller set.** `third_party/.../binding_utils.py`
  assigns `MUJOCO_GL` at import — `"cgl"` on macOS, which dm_control rejects outright — so
  importing robosuite makes dm_control unimportable in any process started afterwards. It
  surfaced as the least informative error here: the main process survived, a spawned replay
  worker re-imported `train.py` and died, and the parent reported *"DataLoader worker exited
  unexpectedly. Details are lost due to multiprocessing."* On Linux the value it would have
  written is the one already set.

- **P10 — robosuite's own success flag in `info`.** Door's return is dense and scale-arbitrary;
  `_check_success` is sparse, task-defined and unit-free, and **nothing reported it**, RL-ViGen's
  own five included — their `logger.py` declares an `SR` column that only the *habitat* eval path
  ever fills, so every robosuite `SR: 0.0000` printed to date was a default. One line, and like
  P6 it reaches every baseline at once because they all pass through this wrapper.
- **P11 — the eval loop actually reports it.** `Gym2DMC` converts to `dm_env` and discards
  `info`, and `wrappers/dmc.py`'s `ExtendedTimeStep` has no field for it. Rather than change the
  TimeStep type, P11 hangs `last_info` on `Gym2DMC` and relies on every wrapper above delegating
  unknown attributes — `ActionDTypeWrapper`, `ActionRepeatWrapper`, `FrameStackWrapper`,
  `ExtendedTimeStepWrapper`, and dm_control's own `action_scale.Wrapper`, all checked. A first
  version of P11 was applied and then **withdrawn** for reading a field that does not exist on
  this path: it would have logged a computed-looking `0.0` forever, which is worse than an
  obviously-unfilled one. Exact at `action_repeat=1`; at k>1 a success lost inside a repeat is
  missed, which is stated in the patch rather than left to be found.

- **P12 — the eval env gets a regime, and before it there was no generalisation measurement.**
  `Workspace.setup` built `train_env` and `eval_env` with *identical arguments*; neither passed
  `mode`, so both inherited `robo_config.yaml`'s `mode: train`. RL-ViGen's own five were
  evaluating on the training distribution. Same failure P1's note describes — P1 fixed the callee
  and P3 threaded `mode` through `robo_make`; this caller used neither. Reads
  `RLVIGEN_EVAL_MODE`, default `None`, which is `robo_make`'s own default and reproduces
  upstream exactly when unset.

`RLGEN_MPS_AS_CUDA` and `replay_buffer_num_workers=0` are macOS-only launcher settings, not
patches; the second changes data-loading concurrency and no number.

## Open, and deliberately not decided in Part 1

**Render resolution is per baseline, by design, and that is a comparability question, not a
solved one.** `rad`/`soda` see an 84 crop of a 100 render; `alda`, `ppg`, `idaac`, `ibac_sni`
render 64; the RL-ViGen five render 84. Different fields of view. Pre-empting that from inside
Part 1 would be exactly the quiet join this approach exists to avoid — it is the first Part 2
item.

Also open: the **CUDA smoke on a T4** for every baseline; `evaluate_ppo.py`; and `ibac_sni`'s
`--procs > 1`, which dies locally because MuJoCo GL contexts do not survive `fork` on macOS
(`multiprocessing.set_start_method("fork")` is hardcoded in its `scripts/train.py`).

## The CUDA smoke: what the T4 has actually proved so far

`compute/rlvigen-cuda-smoke/` (private Kaggle kernel, `machine_shape: NvidiaTeslaT4`) is the
answer to this document's own repeated caveat that a local run does not prove the CUDA path. It
does more than run on a GPU: it clones each upstream **from its public URL at the pinned SHA** and
applies our exported patch, so a green run proves the patches reproduce the clones from public
sources rather than merely existing.

**Confirmed on a real T4 (run 3, 2026-08-17):**

- `Tesla T4, 15360 MiB`, `torch 2.10.0+cu128`, `is_available: True`, `numpy 2.0.2`.
- Both upstreams cloned at exactly the pinned SHAs — `RL-ViGen 90d8b8c`, `dmc_gb ff9c0aa` —
  fetched by SHA from GitHub, with the resulting HEAD checked against the claim.
- **All thirteen RL-ViGen patch hunks applied cleanly to a fresh clone, and
  `apply_patches.py --check` exited 0.** The patch registry reproduces the vendored tree from
  public sources on a machine that has never seen this workspace.
- `dmc_gb.patch` applied cleanly — `git apply` fails loudly on any context mismatch, so this is a
  real check that the patch belongs to that commit.
- robosuite 1.4.0 installed from RL-ViGen's own `third_party` tree.

**RAD TRAINS ON A REAL T4, WITH NO SHIM (run 6).** This is the claim the whole
`runnable/_shim` design rests on, and it is now measured rather than assumed:

    Observations: (9, 100, 100)
    Cropped observations: (9, 84, 84)
    | eval  | S: 0    | ER: 0.9440 | ERTEST: 0.8421 | SR: 0.0000 | SRTEST: 0.0000
    | train | E: 1 | S: 500  | R: 0.0000 | ALOSS: -1.4971 | CLOSS: 0.0375 | AUXLOSS: 0.0000
    | train | E: 2 | S: 1000 | R: 2.9033 | ALOSS: -2.8157 | CLOSS: 0.0042 | AUXLOSS: 0.0000
    | eval  | S: 1000 | ER: 2.3101 | ERTEST: 1.3983 | SR: 0.0000 | SRTEST: 0.0000
    Completed training for logs/robosuite_Door/rad/0

Note what those two shape lines prove independently: **P6 is live on the T4 and RAD is genuinely
RAD**, not the SAC it degrades to at a native 84 render — the 100×100 observation really is being
cropped to 84 by RAD's own `random_crop`. The `SR`/`SRTEST` columns are P10+P11 reporting. The
`EGLError(EGL_NOT_INITIALIZED)` traces after "Completed training" are `__del__` teardown noise,
printed as "Exception ignored in".

**Still not confirmed: RL-ViGen's own five on CUDA.** The SVEA stage has now timed out at its cap
with **no output** on three consecutive runs, and each run eliminated a hypothesis rather than
guessing at the next:

| run | change | result |
|---|---|---|
| 5, 6 | ran after RAD | timed out; RAD trained in the same kernel |
| 7 | ran **first**, on a fresh EGL display, `hydra-submitit-launcher` installed, `num_seed_frames` raised above one episode | **still timed out**; RAD then trained *after* it, exit 0 |

So ordering is not the cause, the erroring EGL teardown is not the cause, the missing hydra
launcher plugin was not the cause, and neither was the seed budget. The renderer, the GPU, the
patch set and the clone are all shared with RAD, which works either side of it.

| 8 | `replay_buffer_num_workers=0`, output to files instead of pipes | **`SVEA exit: -11`** — SIGSEGV. Not a hang at all |

| 9 | `-X faulthandler` | **located it exactly** |

**FOUND (run 9).** The interpreter's own dump names the site:

    train.py:27  ->  RL-ViGen-upstream/logger.py:13  ->  torch/utils/tensorboard/writer.py:19

`logger.py` line 13 is `from torch.utils.tensorboard import SummaryWriter`, at **module scope,
unconditionally** — `use_tb=False` does not prevent it — and on Kaggle's image that import
segfaults the interpreter. It is not the renderer, not the GPU, not EGL, not the DataLoader, and
nothing to do with RL-ViGen's algorithms or with this project's patches. **`dmc_gb`'s logger
imports no tensorboard, which is precisely why RAD worked every time.**

| 10 | install `tensorboard` + `protobuf` | identical crash, identical line |
| 11 | `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` | **crash gone**, replaced by a hang producing 0 bytes in 900 s |
| 12 | **P13** — import TensorBoard lazily, in the one branch that uses it | **unblocked**: SVEA now starts, builds both envs, runs its first eval (`R: 0.9374`), then `exit 1` |
| 13 | print the HEAD of stderr with EGL teardown filtered | **answered**: `Loading train partition of places365_standard...` — a missing DATASET, not a code fault |

**P13 was the blocker, and SVEA now runs on the T4** — workspace created, both envs built, first
eval logged. It then exits 1 for a reason run 12 could not show: robosuite's EGL contexts raise
`EGL_NOT_INITIALIZED` from `__del__` at interpreter shutdown, dozens of "Exception ignored in"
blocks, and the log slice took the *tail* of stderr, which is all of that noise. Run 13 prints
the head with those blocks filtered out. **A diagnostic that shows teardown noise instead of the
exception is the same failure mode as a timeout that discards its output** — the second time
tonight this stage hid its own evidence.

**ANSWERED (run 13).** With the log finally showing its head instead of its teardown, SVEA gets
through workspace creation, both envs, and its first eval (`R: 0.9374`), then prints

    Loading train partition of places365_standard...

and dies. **SVEA needs the Places365 overlay dataset** — `algos/svea.py:12` imports
`random_overlay` and line 299 applies it every update — and that dataset is not in the kernel.
`rad` never touches it, which is exactly why RAD trained on every one of the six runs while SVEA
failed on every one. So the last failure in this sequence is a **missing 546 MB dataset**, not a
code fault, not the GPU, and not anything this project changed.

Supplying it means publishing `data/places365_standard` as a Kaggle Dataset and listing it in
`dataset_sources`. Deliberately not done here: it is 546 MB, it is off the critical path, and the
same overlay is already present locally where `soda` and `svea` both run.

**None of this is on the critical path**, and that is worth stating plainly rather than leaving
implied: Kaggle is python 3.12, so it cannot run RL-ViGen's eval regimes at all (mujoco 2.x,
cp311). The most Kaggle can ever certify for these five is the train regime. `compute/datasphere/`
exists for the real answer.

**Run 10 installed `tensorboard` and `protobuf`, and it did not help**: both report `ok`, and the
crash lands on the identical line. So it is not a *missing* package. That import pulls in
protobuf-generated modules, and run 9's extension list names `google._upb._message` —
protobuf's C implementation. A hard crash rather than an exception is the signature of a
mismatch between that C extension and the generated `pb2` modules. Run 11 set `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`, the documented escape hatch. **It
removed the segfault** — and replaced it with a hang that produced **zero bytes in 900 s**, not
even hydra's own warnings, which is consistent with that backend parsing torch's many generated
`pb2` modules very slowly.

**So the answer is not to make the import work; it is not to make it.** `SummaryWriter` is
referenced at exactly one site, `logger.py:145`, inside `if use_tb:` — a feature that is off by
default and off in every run this project makes. **P13** moves the import into that branch.
Verified locally both ways: `use_tb=False` trains to exit 0, and `use_tb=True` still constructs
the writer, so it is behaviour-preserving where TensorBoard is actually used. It only stops a
disabled feature from being able to prevent the program from starting.

The value of the sequence is that each run killed a hypothesis instead of adding a guess, and the
answer turned out to be in none of them — which is the argument for instrumenting rather than
reasoning once a cheap instrument exists.

**Run 8 changed the shape of the problem.** With the four DataLoader workers removed the process
stops hanging and *crashes*: signal 11, and with **empty stdout**, so it dies before its first
print — before `Now the mode is train`, i.e. during import or env construction, not during
training. The three earlier "timeouts" were workers hanging around a parent that had already
died, which is why they carried no output.

That also means the earlier eliminations still hold and are now sharper: RAD builds the same
robosuite env, on the same GPU, in the same kernel, and does not crash. The difference is what
`RL-ViGen/train.py` imports — it pulls in **dm_control's renderer and robosuite's EGL context in
one process**, where `dmc_gb` reaches robosuite through `dmc2gym` alone.

Run 9 adds `-X faulthandler`, which makes the interpreter dump a Python traceback on the fatal
signal. That converts "segfaults somewhere" into a file and a line, and is the last cheap step
before this becomes a guess.

**None of this affects the seven non-RL-ViGen baselines**, whose CUDA path is represented by RAD
and confirmed twice.

**Earlier: RAD died before its first env step with**

    AttributeError: 'MjData' object has no attribute 'qM'. Did you mean: 'M'?

from `robosuite/controllers/base_controller.py:156`. Cause: unpinned `mujoco` installs a version
in which `MjData.qM` was renamed, and RL-ViGen's vendored robosuite 1.4.0 predates the rename.
**This machine happened to have mujoco 2.3.7 already, so the pin was invisible locally** — it is
precisely the class of thing a remote run exists to find. Pinned to `mujoco==2.3.7` and re-pushed.

**Two operational notes worth not rediscovering.** `enable_gpu: true` alone gets a **Tesla P100**
(sm_60), which Kaggle's own `torch 2.10.0+cu128` does not support — `machine_shape` is not
optional. And anything written under `/kaggle/working` becomes the kernel's *output*: the first
run cloned 1.8 GB of RL-ViGen there, and `kaggle kernels output` then rate-limited for half an
hour trying to download it just to fetch a log. Clone into `/kaggle/temp`.

### The finding that decides which remote compute is usable

**RL-ViGen's evaluation regimes require mujoco 2.x, and mujoco 2.x has no Python 3.12 wheel.
Kaggle runs Python 3.12.** This is not a preference or a slowdown; it is a hard block, and it was
invisible locally because this machine is on Python 3.11 with mujoco 2.3.7.

Established across three T4 runs, each answering one question:

| run | what it settled |
|---|---|
| 3 | robosuite 1.4.0 calls `self.sim.data.qM`, removed in newer mujoco → `AttributeError: 'MjData' object has no attribute 'qM'`, before any env step |
| 5 | `mujoco<3.3` resolves to 3.2.7 **and 3.2.7 still has `qM`** — probed and printed rather than guessed, so robosuite works |
| 5 | but RL-ViGen's texture modder (`mjmod.py:1390`) reads `MjModel.tex_rgb`, **removed in mujoco 3.0** → the *train* env renders fine and `eval-easy` dies at `_initialize_modders` on its first reset |

So mujoco 3.x satisfies robosuite and breaks RL-ViGen's visual randomization; mujoco 2.x satisfies
both. PyPI wheel availability, checked directly:

    mujoco 2.3.7  cp38 cp39 cp310 cp311           <- no cp312
    mujoco 3.0.0  cp38 cp39 cp310 cp311 cp312
    mujoco 3.2.7  cp39 cp310 cp311 cp312 cp313

2.3.7 is the last 2.x release with wheels at all, and it stops at cp311. Locally: mujoco 2.3.7 on
Python 3.11, `MjModel.tex_rgb` True and `MjData.qM` True — which is why every eval-regime run on
this machine works.

**Consequences for the compute choice, stated plainly:**

- **Kaggle (Python 3.12) can run the `train` regime only.** That is enough for a CUDA-path smoke
  and useless for generalisation, which is the entire point of this benchmark. Making it work
  would mean building mujoco 2.3.x from source in the kernel.
- **DataSphere is the option to prefer**, provided its image is Python ≤ 3.11 — then
  `mujoco==2.3.7` installs from a wheel and the environment matches this machine exactly.
- Either way, **`mujoco==2.3.7` and Python ≤ 3.11 belong in the environment spec** for any real
  run, alongside `dm-control==1.0.14`, `gym==0.25.2` and robosuite from RL-ViGen's `third_party`.

The SVEA stage is the one thing on this platform still unexplained; see above for the three
candidate causes and the experiment separating them.
