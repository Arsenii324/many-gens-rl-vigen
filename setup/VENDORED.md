# The vendored stack: what is pinned, and what breaks when it moves

Every pin below was arrived at by a failure. None is a preference. They are recorded here because
the failures are unequal: some crash immediately, and some **only break the evaluation path**,
which is the path whose numbers get published.

## RL-ViGen

| | |
|---|---|
| source | `https://github.com/gemcollector/RL-ViGen` |
| commit | `90d8b8c40acb63af6f938c1f4cc79a0cfee7d7ec` |
| location | `RL-ViGen-upstream/` — **gitignored** (1.8 GB) |
| provenance | `setup/install.sh` clones and checks out that commit; `Protocol.env_commit` records it in every protocol card |

It is not importable as a library: no `setup.py` at the root, `wrappers/` has no `__init__.py`,
and its modules use absolute imports rooted at the repo directory. `rlgen/envs.py` therefore puts
the repo root on `sys.path` and imports `wrappers.robo_wrapper` — the seam, and the only place
this repo touches upstream directly.

### Five patches — `setup/apply_patches.py`

*(P4 and P5 were added after this section was first written. P4 makes the Places365 overlay follow
the caller's device instead of assuming CUDA — without it SVEA and SGQN die at their first update
on any CPU/MPS machine. P5 casts DrQ's `log_alpha` to float32, because `np.log` of a Python float
is float64 and MPS does not support float64; DrQ dies at construction without it. P5 spent weeks as
an undeclared hand-edit, which is why `--check` now diffs the **whole** vendored tree against its
pinned commit rather than only confirming the patches it knows about.)*

Idempotent and self-verifying: `--check` exits 1 if any is missing, applying twice is a no-op, and
it refuses to guess if an anchor has moved. `tests/test_contract.py::test_upstream_patches_are_applied`
fails the build when the tree is unpatched.

**P1 — `make_env` ignored its caller's `mode`.** *(the dangerous one)*
`robosuitevgb.make_env(task_name, seed, scene_id)` read the visual regime from the hydra config
`robo_config.yaml`, so every environment was built in whatever that file said — `train` — no
matter what was requested. Train and eval envs then render **identically**, so the train→eval
generalisation gap is not merely wrong — it is **zero by construction**, and it looks like a clean
result rather than a failure. The sibling project (`../gen-rebuttal/vigen-idaac`) hit exactly this
and recorded it as B7; in their own words it held *"for the whole project until now"*.

The patch makes `mode` an argument; `rlgen/envs.py` then **asserts** the env reports the mode that
was asked for, because a request that is silently dropped is worse than one that fails. And
because an assertion on a self-reported field could itself be satisfied by an env that reports
correctly and renders identically, `test_eval_modes_actually_look_different_from_train` compares
the actual pixels between regimes.

**P2 — the background video was loaded for every mode, and `train/` has no assets.**
`VGBWrapper.__init__` called `load_video(mode, ...)` unconditionally. The shipped asset pack
contains `assets/video/{eval-easy,eval-hard,eval-extreme}` and no `train` directory — nor the
`eval-medium` that the code's own assert accepts. `cv2.VideoCapture` on a missing file reports a
frame count of −1, and `np.empty((-1, H, W, 3))` raises `negative dimensions are not allowed`. So
upstream's robosuite path does not run in train mode out of the box. `video_buf` is read only
under `if self.video_background:`, and that flag is set for `eval-hard` alone, so guarding the
load is behaviour-preserving where it matters and turns a crash into a no-op everywhere else.

**P3 — `robo_make` dropped `mode`, and the resolved regime was unreachable.**
The wrapper chain does not forward attribute lookups down to `VGBWrapper` — it stops at
`Gym2DMC`, which links to its child through `_gym_env` rather than `_env`. So even with P1 a
caller had no way to ask what it got, and a naive walk returns `None` silently. The patch threads
`mode` and hoists `_vigen_regime` onto the outermost wrapper, which is what makes P1's assertion
possible.

*(The same wall bites anything that walks this chain. Our success probe hit it too and reported an
empty `success` column for a whole run before the walk was taught the three different link names;
the sibling project records the identical failure — "the chain stops at Gym2DMC, which is how the
first version of this check silently reported None".)*

## robosuite — install RL-ViGen's fork, editable

```bash
pip install --no-deps -e RL-ViGen-upstream/third_party/robosuite
```

**Not PyPI robosuite.** Both call themselves `1.4.0` and they differ in **761 files**. The version
string is useless as a discriminator, which is worth knowing before anyone tries to reproduce a
number from a `pip freeze`. The concrete symptom: RL-ViGen's evaluation modes randomise textures
by name (`Custom01`…`Custom40`), those textures exist only in the fork, and stock robosuite dies
with

```
FileNotFoundError: Custom05 does not exist as a file name or as a built-in texture name
```

while `mode=train` keeps working, because train randomises nothing.

**Editable, not a wheel.** The fork's `setup.py` declares no `package_data`, so a wheel build
silently drops `robosuite/models/assets/` entirely — the package imports and every asset lookup
fails. `setup/install_assets.py --check` verifies that the *active* robosuite carries the 40
textures, whichever way it was installed.

*(This settles a question the sibling project left open — whether the vendored and pip robosuites
actually differ. They do.)*

## Python pins

| pin | what moving it breaks |
|---|---|
| `mujoco==2.3.7` | 3.x renamed `tex_rgb`, which RL-ViGen's `XMLTextureModder` uses. On mujoco 3.9/3.11 **`train` runs fine and every eval mode raises** `AttributeError: 'MjModel' object has no attribute 'tex_rgb'`. mujoco 3.10+ additionally drops `MjData.qM`, which robosuite 1.4 needs. |
| `gym==0.25.2` | `robosuitevgb/vgb_wrapper.py` imports the old `gym`, not `gymnasium`. |
| `dm_control` | imported by `wrappers/dmc.py`, which `robo_wrapper.py` imports — needed even though no DMC task is used. |
| `hydra-core` | `make_env` composes a hydra config and calls `GlobalHydra.clear()` on **every** construction, which is why two environments cannot be built concurrently in one interpreter. |
| `torchvision` | `RL-ViGen-upstream/utils.py` imports it at module scope, so the whole DrQ-v2 family needs it. |
| `captum` | **SGQN only.** Its saliency path imports it at module scope; nothing upstream declares it. Recorded in `rlgen/registry.py` as `extra_requirements` so `baselines/sgqn/README.md` and the code cannot disagree. |

## `MUJOCO_GL`

macOS → `glfw`. `dm_control`'s validator rejects `cgl` outright:

```
RuntimeError: Environment variable MUJOCO_GL must be one of
['', '0', '1', 'disable', ..., 'egl', 'glfw', 'osmesa', ...]: got 'cgl'
```

Linux GPU boxes → `egl`, and it must be set **before mujoco is imported**, in the process that
will build the environment. `baselines/*/train.sh` and `rlgen/envs.py` both do this.

## The dependency trap this repo avoids

`RL-ViGen-upstream/algos/__init__.py` is one line — `from algos import pieg` — and `pieg.py`
imports `hydra` and `torchvision`. So the natural `from algos.drqv2 import DrQV2Agent` drags in
transitive dependencies of an algorithm this benchmark never runs, and dies with
`ModuleNotFoundError: hydra` on a machine that lacks them. Five of the twelve baselines were
unconstructible for exactly this reason before the rebuild.

`rlgen/registry.load_upstream_module()` loads the module file directly, bypassing the package
`__init__`, so a baseline pays only for what it actually imports. It also purges a half-executed
module from `sys.modules` on failure — otherwise the second attempt reports
`module has no attribute SGQNAgent` instead of the real `No module named captum`, which is how a
missing dependency turns into an hour of looking in the wrong place.
