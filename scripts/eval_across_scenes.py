#!/usr/bin/env python3
"""What is the scene axis worth IN RETURN? The follow-up C46 names and could not answer.

    python scripts/eval_across_scenes.py --snapshot path/to/snapshot.pt
    python scripts/eval_across_scenes.py --episodes 10 --scenes 0,1,2,3,4,5,6,7,8,9

[C45] establishes from source that we train and evaluate on scene 0 while RL-ViGen averages ten.
[C46] measures the axis in *observation* space: all nine other scenes separate from scene 0, at
~84% of the distance the train-to-eval-easy step covers. Both stop short of the question a
results table actually asks — **how many points of return does the missing axis cost?**

That needs a trained policy, because the answer is a property of the policy, not the renderer. A
policy that learned texture-invariant features loses little; one that keyed on scene 0's textures
loses a lot. Nothing in observation space can distinguish those two.

## Design

The training scene is the control, not just another row:

  * **scene 0** — the scene the policy was trained on. In-distribution.
  * **scenes 1-9** — held out. Never seen.
  * **retention** = mean return over 1-9, divided by scene 0.

**This is SCENE retention, not the regime retention `docs/CONSTRUCTION.md` C43 is about.** C43
means `eval-easy` performance as a fraction of `train` performance, which no current run can
produce because only one regime is ever evaluated. This script holds the regime fixed and varies
the scene. A policy could retain perfectly on one axis and collapse on the other, so any reported
figure has to name which axis it is.

`mode` is held at `eval-easy` throughout, so the *only* thing varying is scene identity. That is
the intervention C45 says our runs never perform, and holding the regime fixed is what makes the
result attributable to scene rather than to difficulty.

## Reading the number honestly

- **One seed, one checkpoint.** This is a measurement of one policy, not of a method. Episode
  dispersion is reported (sd and a bootstrap CI on each mean) because a retention ratio computed
  from two noisy means is itself noisy, and a point estimate would invite over-reading.
- **A retention near 1.0 is not proof of invariance** at this episode count; it is failure to
  detect a difference. The CI width states what this run could have resolved.
- **Return, not success rate**, is the primary endpoint because that is what RL-ViGen publishes
  (C33). Success rate is reported alongside since it is what this project has been logging.
- **Inference runs on CPU by default, and that is a choice rather than a fallback.** MPS is
  faster, but [C41] measures the MPS training path diverging from itself by 48% at 40k frames,
  and there is no reason to import that variance into a measurement whose entire question is
  whether a *difference between scenes* is real. CPU inference is deterministic, so re-running
  this script on the same checkpoint returns the same numbers. `--device mps` is available and
  will be quicker; the numbers then carry the backend's noise as well as the task's.
- The snapshot is whatever the run had reached, **not a converged policy**. A partially-trained
  policy may be more scene-dependent than a converged one, or less; the frame count is printed
  with the result so the claim carries its own budget.
"""
from __future__ import annotations

import argparse
import hashlib
import os

# [Added 2026-09-05.] Must precede any CUDA initialisation, so module scope. This file calls
# `torch.use_deterministic_algorithms(True)` at :146, which SUCCEEDS on CUDA and then raises at the
# first CuBLAS operation unless this is set -- see the same note in scripts/eval_grid.py. The
# rlvigen five run through this path, so without it their CUDA evaluations carry the identical
# latent failure that killed job bt1s5a6pub9muqgcoil9 on the idaac path.
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import pathlib
import sys
import json
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.metrics import bootstrap_ci, wilson_interval  # noqa: E402
from scripts.eval_provenance import completed_episode_diagnostics, policy_scale  # noqa: E402


LAST_PLACEMENT_WITNESSES: list[str] = []
LAST_EPISODE_DIAGNOSTICS: list[dict] = []


def placement_witness(observation) -> str:
    """Hash the first post-reset observation so placement provenance is inspectable."""
    digest = hashlib.sha256()

    def add(value):
        if isinstance(value, dict):
            for key in sorted(value):
                digest.update(str(key).encode())
                add(value[key])
        elif isinstance(value, (tuple, list)):
            for item in value:
                add(item)
        else:
            try:
                if hasattr(value, "detach"):
                    value = value.detach().cpu().numpy()
                array = np.asarray(value)
                digest.update(str(array.shape).encode())
                digest.update(str(array.dtype).encode())
                digest.update(array.tobytes())
            except Exception:
                digest.update(repr(value).encode())

    add(observation)
    return digest.hexdigest()


def _setup() -> None:
    rlv = ROOT / "RL-ViGen-upstream"
    os.environ.setdefault("RLVIGEN_ROOT", str(rlv))
    os.environ.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    if sys.platform == "darwin":
        os.environ.setdefault("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")
    for p in (str(rlv), str(rlv / "algos"), str(rlv / "envs" / "robosuiteVGB"),
              str(ROOT / "runnable" / "_shim")):
        if p not in sys.path:
            sys.path.insert(0, p)


def find_snapshot(explicit: str | None) -> pathlib.Path | None:
    if explicit:
        p = pathlib.Path(explicit)
        return p if p.exists() else None
    hits = sorted(ROOT.rglob("snapshot.pt"), key=lambda p: p.stat().st_mtime, reverse=True)
    return hits[0] if hits else None


def run_scene(agent, task: str, scene_id: int, mode: str, episodes: int, seed: int,
              action_repeat: int, frame_stack: int, step: int):
    global LAST_PLACEMENT_WITNESSES
    global LAST_EPISODE_DIAGNOSTICS
    LAST_PLACEMENT_WITNESSES = []
    LAST_EPISODE_DIAGNOSTICS = []
    from wrappers.robo_wrapper import robo_make
    import utils
    import torch

    # C70. Seeding the RNGs is necessary and NOT sufficient: torch selects CPU kernels at runtime
    # and some are nondeterministic, so two processes running identical weights over identical
    # observations can differ by ~1e-7 in the actor's output. Ordinarily invisible -- but Door's
    # success test is a threshold (`hinge_qpos > 0.3`), so a hair's difference in one action can
    # decide whether the door opens. Measured: with placement seeded but this line absent, two
    # runs of scene 1 agreed on **17 of 20 episodes** and diverged on three, one of them
    # 372.34 versus 6.01 -- the difference between a success and nothing.
    #
    # `torch.set_num_threads(1)` does NOT fix it (checked); the variation is kernel selection, not
    # thread scheduling. With this line, three processes agree bit-for-bit.
    #
    # Kept next to the seeding rather than at import: both are preconditions of one claim -- that a
    # recorded seed names a measurement -- and separating them is how the first half came to look
    # sufficient.
    torch.use_deterministic_algorithms(True)

    # C69. Seed the GLOBAL numpy RNG before the env is built, because that is the one the door's
    # placement sampler draws from.
    #
    # `robosuite/utils/placement_samplers.py` lines 167/183/196/198 call bare `np.random.uniform`
    # -- `UniformRandomSampler` holds no `random_state` and accepts no rng. It is what decides
    # where the door and its handle sit on every reset (`door.py`: x_range [0.07,0.09],
    # y_range [-0.01,0.01]). The `seed` argument threaded through `robo_make` reaches VGBWrapper's
    # `random_state`, which drives texture/colour/lighting only -- a different RNG object.
    #
    # So without this line the door moves between processes that record an identical seed.
    # Measured, three processes, seed=0/scene 0/train: x = -0.128117, -0.112590, -0.120571
    # (~1.6 cm of spread, the sampler's full declared range). With it, all three agree exactly.
    # On a task whose reaching term is 0.25*(1 - tanh(10*dist)) and whose success is
    # `hinge_qpos > 0.3`, that is not a rounding difference.
    #
    # Upstream already does this -- `train.py:47` and `eval.py:54` both call
    # `utils.set_seed_everywhere(cfg.seed)`, which seeds global numpy at `utils.py:38`. This
    # evaluator is our own code and simply never did. Every grid measured before 2026-08-25
    # carries the defect; see C69 for which conclusions that does and does not disturb.
    #
    # Seeded per scene from the same base rather than once per run, so each scene sees the SAME
    # sequence of object placements. That is what makes the scene comparison an intervention:
    # `mode` and geometry are held fixed and only scene identity varies, which is what this
    # script's docstring claims it does.
    utils.set_seed_everywhere(seed)

    env = robo_make(name=task, frame_stack=frame_stack, action_repeat=action_repeat,
                    seed=seed, scene_id=scene_id, mode=mode)
    # Verify the scene actually applied rather than trusting the argument. `make_env` falls back
    # to robo_config.yaml for anything it is not given, so a silent fallback would leave every
    # "scene" identical and produce a retention of exactly 1.0. P3 hoists the constructor's
    # authoritative values; reading them avoids a diagnostic reset/step that would consume C69 RNG.
    resolved = getattr(env, "_vigen_regime", None)
    if not isinstance(resolved, dict):
        # Test doubles and older wrappers may expose the same constructor values directly. This is
        # still a read-only check; never call reset/step merely to manufacture metadata.
        direct_mode = getattr(env, "_mode", None)
        direct_scene = getattr(env, "_scene_id", getattr(env, "scene_id", None))
        if direct_mode is not None or direct_scene is not None:
            resolved = {"mode": direct_mode, "scene_id": direct_scene}
    if not isinstance(resolved, dict):
        print(f"    ! could not read the env's regime back -- '{mode}'/{scene_id} is UNVERIFIED",
              file=sys.stderr)
        raise RuntimeError("the evaluation environment has no regime read-back; refusing "
                           "to measure a cell")
    applied = resolved.get("scene_id")
    if applied != scene_id:
        raise RuntimeError(f"asked for scene {scene_id}, env reports {applied!r} -- the scene "
                           "argument did not take effect and this row would be a duplicate")

    # The same check for `mode`, which the block above argues for and did not do. `make_env` falls
    # back to `robo_config.yaml` for anything it is not given, and that file declares `mode: train`
    # -- so a silent fallback would evaluate every "eval-easy" grid in the TRAINING regime and
    # produce a retention of about 1.0. That is the same clean-looking null the scene check exists
    # to prevent, on the other axis, and it would be more convincing because 1.0 is a number a
    # reader might accept.
    #
    seen_mode = resolved.get("mode")
    if seen_mode != mode:
        raise RuntimeError(
            f"asked for mode {mode!r}, env reports {seen_mode!r} -- the regime argument did not "
            "take effect. Every row of this grid would be measured in the wrong regime, and a "
            "retention near 1.0 would look like invariance.")

    # `agent is None` means the random-policy floor. This exists because "the agent scores 2.0
    # on the training scene" is not interpretable on its own -- 2.0 could be most of what the
    # task offers or none of it. Retention divides by that number, so without a floor a ratio
    # of two chance-level scores reads as a generalization result. Same envs, same scenes, same
    # episode count as every other row, so the comparison is like-for-like.
    spec = env.action_spec()
    act_rng = np.random.default_rng(seed)
    # Per-episode success flags, aligned index-for-index with `rets`. The count alone cannot
    # answer "what did the episodes that SUCCEEDED score", which is the question that separates
    # a policy opening the door from one accumulating shaped reaching reward. Collected, never
    # acted on: the loop's behaviour, its RNG draws and its env interaction are unchanged.
    rets, succ, flags = [], 0, []
    for episode_index in range(episodes):
        # C69: bind placement to the declared condition immediately before the measured reset.
        # This makes the paired sequence independent of family-specific construction/probes.
        condition = int(np.random.SeedSequence(
            [int(seed), int(scene_id), episode_index]
        ).generate_state(1, dtype=np.uint32)[0])
        np.random.seed(condition)
        ts = env.reset()
        LAST_PLACEMENT_WITNESSES.append(placement_witness(ts.observation))
        total, succeeded = 0.0, False
        while not ts.last():
            if agent is None:
                action = act_rng.uniform(
                    getattr(spec, "minimum", -1.0), getattr(spec, "maximum", 1.0),
                    spec.shape).astype(np.float32)
            else:
                # `utils.eval_mode` is not decoration: without it the agent acts with exploration
                # noise and this measures a noisier policy than the one the run produced. Copied
                # from RL-ViGen's own robosuite eval loop rather than reconstructed.
                with torch.no_grad(), utils.eval_mode(agent):
                    action = agent.act(ts.observation, step, eval_mode=True)
            ts = env.step(action)
            total += float(ts.reward or 0.0)
            # Success comes from `env.last_info`, checked at EVERY step -- patch P11's
            # convention, and the one the other seven baselines use.
            #
            # This was written the other way first, reading `time_step.info['success']` after
            # the loop. That is habitat's path (`habi_eval`); on the robosuite path the wrapped
            # TimeStep carries `info=None`, so the SR column would have been a silent zero for
            # every scene -- the exact defect P11 exists to fix, reintroduced downstream of it.
            succeeded = succeeded or bool(
                (getattr(env, "last_info", None) or {}).get("success", False))
        rets.append(total)
        succ += int(succeeded)
        flags.append(int(succeeded))
    LAST_EPISODE_DIAGNOSTICS.extend(completed_episode_diagnostics(
        env, policy_scale(agent), len(rets)))
    return np.array(rets), succ, flags


def retention(rows: dict) -> dict:
    """Held-out return as a fraction of the training scene's, with the control able to refuse.

    Separated from `main` so the arithmetic can be tested without robosuite, and because two of
    its rules are judgement rather than division:

    * **scene 0 is the denominator and must exist.** It is the TRAINING scene; without it there
      is no in-distribution reference and a mean over scenes 1-9 is just a number.
    * **a zero or negative training mean makes retention meaningless**, not infinite. A policy
      that scores 0 in-distribution cannot have its held-out score expressed as a fraction of it,
      and returning a large ratio there would manufacture a headline from a failed run.
    """
    if 0 not in rows:
        return {"ok": False, "why": "no scene 0 (the training scene) -- no control, no retention"}
    train = rows[0][0]
    held_arrays = [rows[s][0] for s in sorted(rows) if s != 0]
    if not held_arrays:
        return {"ok": False, "why": "no held-out scene evaluated"}
    held = np.concatenate(held_arrays)
    tm = float(train.mean())
    if tm <= 0:
        return {"ok": False, "why": f"training-scene mean is {tm:.3f}; retention undefined",
                "train_mean": tm, "held_mean": float(held.mean())}
    n_succ = sum(rows[s][1] for s in rows if s != 0)
    n_eps = sum(len(rows[s][0]) for s in rows if s != 0)
    return {"ok": True, "train_mean": tm, "held_mean": float(held.mean()),
            "retention": float(held.mean()) / tm, "n_held": len(held),
            "held_succ": n_succ, "held_eps": n_eps}


def run_random_floor(a) -> int:
    """Uniform-random policy over the same scenes, for the same episode count.

    Reported as its own table, never merged into a retention number. It is the reference a
    denominator is checked against, not another arm of the comparison.
    """
    import json as _json
    print(f"\nRANDOM-POLICY FLOOR -- {a.task}, regime {a.mode!r}")
    print(f"  {a.episodes} episodes per scene, seed {a.seed}. No network is loaded.")
    scenes = [int(x) for x in a.scenes.split(",")]
    rows = {}
    for sc in scenes:
        print(f"  scene {sc} ...", flush=True)
        try:
            rets, succ, _ = run_scene(None, a.task, sc, a.mode, a.episodes, a.seed,
                                   a.action_repeat, a.frame_stack, 0)
        except Exception as e:
            print(f"    failed: {type(e).__name__}: {str(e)[:90]}")
            continue
        rows[sc] = (rets, succ)
        print(f"    mean {rets.mean():8.3f}  sd {rets.std():7.3f}  successes {succ}/{a.episodes}")
    if not rows:
        print("  no scene evaluated -- there is no floor, and no retention may be reported")
        return 1
    allr = np.concatenate([v[0] for v in rows.values()])
    tot = sum(v[1] for v in rows.values())
    print(f"\n  FLOOR over {len(rows)} scenes: mean {allr.mean():.3f}  sd {allr.std():.3f}  "
          f"successes {tot}/{len(rows) * a.episodes}")
    if a.json:
        out = pathlib.Path(a.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_json.dumps({
            "snapshot": None, "random_policy": True, "task": a.task, "mode": a.mode,
            # placement_seeded belongs here as much as on the snapshot path below: the floor is
            # the DENOMINATOR of every "clears the floor" test in the retention report and the
            # results table, so its provenance is load-bearing. It was omitted here and only here,
            # and `scripts/verify_cells.py` caught it on its first run -- the floor read
            # placement_seeded=None while every cell read True. Not a seeding failure: the two
            # floor grids are byte-identical across 200 episodes in two different regimes, which
            # is impossible unless placement is deterministic. An unrecorded true fact still
            # fails an audit, and should.
            "placement_seeded": True,
            "trained_step": 0, "frames": 0, "action_repeat": a.action_repeat,
            "episodes": a.episodes, "seed": a.seed, "control_seed": a.control_seed,
            "scenes": {str(k): {"returns": list(map(float, v[0])), "n_success": int(v[1]),
                                "n_episodes": len(v[0])} for k, v in rows.items()},
            "control": None}, indent=2) + "\n")
        print(f"  floor written to {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--task", default="Door")
    ap.add_argument("--mode", default="eval-easy")
    ap.add_argument("--scenes", default="0,1,2,3,4,5,6,7,8,9")
    ap.add_argument("--episodes", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--control-seed", type=int, default=1,
                    help="re-run the TRAINING scene at this seed to get an episode-noise floor")
    ap.add_argument("--no-control", action="store_true",
                    help="skip the within-scene control (then no retention is interpretable)")
    ap.add_argument("--device", default="cpu",
                    help="where to run inference; cpu is the portable default and needs no shim")
    ap.add_argument("--action-repeat", type=int, default=1)
    ap.add_argument("--frame-stack", type=int, default=3)
    ap.add_argument("--json", default=None,
                    help="dump per-scene episode returns here. The printed report is scene\nretention (held-out vs scene 0) within one regime; a REGIME comparison needs the rows from\ntwo runs, which no single invocation can produce. This is that handoff, and it is raw --\nno summary statistic is written, so the consumer picks its own.")
    ap.add_argument("--random-policy", action="store_true",
                    help="evaluate a uniform random policy instead of a snapshot: the floor a\nretention denominator has to clear before dividing by it means anything.")
    a = ap.parse_args()

    _setup()
    if a.random_policy:
        return run_random_floor(a)
    snap = find_snapshot(a.snapshot)
    if snap is None:
        print("no snapshot.pt found. Train with save_snapshot=True first.")
        print("A SKIP is not a pass: the return-space scene effect was not measured.")
        return 1

    import torch
    with snap.open("rb") as f:
        payload = torch.load(f, map_location="cpu", weights_only=False)
    agent = payload["agent"]

    # Reconcile the agent's DEVICE with where its weights just landed. The snapshot pickles the
    # agent object, including `self.device` as set during training -- `cuda` here, because the
    # MPS-as-CUDA shim was active. `map_location="cpu"` moves the tensors and leaves that
    # attribute untouched, so `act()` would build `torch.as_tensor(obs, device=self.device)` on
    # one device and run CPU weights on it (drqv2.py:165). That fails on the first action, after
    # the environment has been built -- i.e. minutes in, once per scene.
    dev = torch.device(a.device)
    moved = []
    for name, val in list(vars(agent).items()):
        if isinstance(val, torch.nn.Module):
            val.to(dev)
            moved.append(name)
    if hasattr(agent, "device"):
        agent.device = dev
    print(f"  agent moved to {dev} -- modules: {', '.join(moved) or 'none found'}")
    if not moved:
        print("    WARNING: no nn.Module attributes found on the agent. If it holds its networks "
              "somewhere\n    else, they are still on CPU while `device` says otherwise.")
    trained_step = int(payload.get("_global_step", -1))
    frames = trained_step * a.action_repeat

    print(f"\nEVAL ACROSS SCENES -- {a.task}, regime {a.mode!r} held fixed")
    print(f"  snapshot: {snap.relative_to(ROOT) if snap.is_relative_to(ROOT) else snap}")
    print(f"  trained to global_step {trained_step} (= {frames} frames at "
          f"action_repeat={a.action_repeat})")
    print(f"  {a.episodes} episodes per scene, seed {a.seed}\n")

    scenes = [int(s) for s in a.scenes.split(",")]
    t0 = time.time()
    rows = {}
    for s in scenes:
        print(f"  scene {s} ...", flush=True)
        try:
            rets, succ, _ = run_scene(agent, a.task, s, a.mode, a.episodes, a.seed,
                                   a.action_repeat, a.frame_stack, trained_step)
        except Exception as e:
            print(f"    failed: {type(e).__name__}: {str(e)[:90]}")
            continue
        rows[s] = (rets, succ)

    # Within-scene control: the SAME scene, different episode seed. Without it a held-out
    # difference has nothing to be read against -- the same reason `probe_scenes.py` measures a
    # within-scene floor before reporting any between-scene distance. Ten episodes of a
    # stochastic task differ from ten more of the same task, and that spread is the resolution
    # limit of every retention number below.
    control = None
    if 0 in rows and not a.no_control:
        print(f"  scene 0 again at seed {a.control_seed}  (within-scene control) ...", flush=True)
        try:
            control = run_scene(agent, a.task, 0, a.mode, a.episodes, a.control_seed,
                                a.action_repeat, a.frame_stack, trained_step)
        except Exception as e:
            print(f"    control failed: {type(e).__name__}: {str(e)[:80]}")

    if a.json:
        out = pathlib.Path(a.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "snapshot": str(snap),
            # C67: the *content* hash, not just the path. `snapshot.pt` and
            # `snapshot_100k_frames.pt` in the archived 2026-08-18 run are byte-identical, and
            # nothing in a grid's metadata said so -- every field including `trained_step` matched,
            # so four sessions treated two evaluations of one checkpoint as independent evidence.
            # It was found by running md5 by hand, months of session-time later. With this field a
            # replicate is visible at a glance, which is the difference between a free measurement
            # of evaluation noise (what it turned out to be) and a phantom second data point.
            "snapshot_md5": hashlib.md5(snap.read_bytes()).hexdigest(),
            # C69. Marks that this grid was measured AFTER `run_scene` began seeding global numpy,
            # which is what `UniformRandomSampler` draws the door's position from. Grids written
            # before 2026-08-25 lack the key entirely, and for them the recorded `seed` did not
            # control object placement -- the door moved ~1.6 cm between processes. Written as a
            # field rather than left to the file's date because a date is a fact about the file
            # and this is a fact about the measurement.
            "placement_seeded": True,
            "task": a.task, "mode": a.mode,
            "trained_step": trained_step, "frames": frames, "action_repeat": a.action_repeat,
            "episodes": a.episodes, "seed": a.seed, "control_seed": a.control_seed,
            # `run_scene` returns (returns_array, success_COUNT) -- an int, not a per-episode
            # list. Written as a list comprehension first, which raises TypeError only after
            # every scene has been evaluated, i.e. it discards ~20 minutes of work at the last
            # line. The count is what exists, so the count is what is written.
            "scenes": {str(k): {"returns": list(map(float, v[0])),
                                "n_success": int(v[1]), "n_episodes": len(v[0])}
                       for k, v in rows.items()},
            "control": None if control is None else {
                "scene": 0, "returns": list(map(float, control[0])),
                "n_success": int(control[1]), "n_episodes": len(control[0])},
        }, indent=2) + "\n")
        print(f"\n  rows written to {out}")

    if 0 not in rows:
        print("\n  scene 0 (the TRAINING scene) could not be evaluated, so there is no control")
        print("  and no retention can be computed. Nothing is reported.")
        return 1

    print(f"\n  {'scene':<7}{'mean':>9}{'sd':>8}{'min':>8}{'max':>9}"
          f"{'95% CI on mean':>22}{'SR':>7}")
    print("  " + "-" * 70)
    for s in sorted(rows):
        r, succ = rows[s]
        lo, hi = bootstrap_ci(r, stat=lambda x: float(np.mean(x)), seed=0)
        tag = "0*" if s == 0 else str(s)
        print(f"  {tag:<7}{r.mean():>9.2f}{r.std(ddof=1):>8.2f}{r.min():>8.2f}{r.max():>9.2f}"
              f"{f'[{lo:.2f}, {hi:.2f}]':>22}{succ / len(r):>7.2f}")
    print("  * scene 0 is the TRAINING scene -- the control, not another row")

    r = retention(rows)
    if not r["ok"]:
        print(f"\n  no retention reported: {r['why']}")
        return 0

    held = np.concatenate([rows[s][0] for s in sorted(rows) if s != 0])
    train_mean, ret = r["train_mean"], r["retention"]
    lo, hi = bootstrap_ci(held, stat=lambda x: float(np.mean(x)), seed=0)
    n_succ, n_eps = r["held_succ"], r["held_eps"]
    slo, shi = wilson_interval(n_succ, n_eps)

    print(f"\n  RETENTION -- held-out scenes as a fraction of the training scene")
    print(f"    training scene 0 : {train_mean:.2f}")
    print(f"    held-out 1-9     : {held.mean():.2f}   95% CI [{lo:.2f}, {hi:.2f}]  "
          f"n={len(held)} episodes")
    print(f"    retention        : {ret:.3f}")
    if control is not None:
        c_ret, _ = control
        same_scene = float(c_ret.mean())
        print(f"\n  WITHIN-SCENE CONTROL -- scene 0 again, different episode seed")
        print(f"    scene 0 seed {a.seed}: {train_mean:.2f}   scene 0 seed {a.control_seed}: "
              f"{same_scene:.2f}")
        gap_ctrl = abs(same_scene - train_mean)
        gap_held = abs(float(held.mean()) - train_mean)
        print(f"    same-scene gap: {gap_ctrl:.2f}    held-out gap: {gap_held:.2f}"
              f"    ratio: {gap_held / gap_ctrl:.2f}x" if gap_ctrl > 0 else
              f"    same-scene gap: {gap_ctrl:.2f}    held-out gap: {gap_held:.2f}")
        if gap_ctrl > 0 and gap_held / gap_ctrl < 2.0:
            print("    The held-out drop is NOT clearly larger than re-running the same scene.")
            print("    At this episode count that is a failure to detect a difference, not")
            print("    evidence that scene identity does not matter.")
    else:
        print("\n  NO WITHIN-SCENE CONTROL was run. The retention figure above has nothing to be")
        print("  read against: ten episodes differ from ten more episodes of the SAME scene, and")
        print("  that spread is unmeasured here. Do not report this number without it.")
    print(f"    held-out SR      : {n_succ}/{n_eps} = {n_succ / max(1, n_eps):.3f}  "
          f"95% Wilson [{slo:.3f}, {shi:.3f}]")
    print(f"\n  This is the number [C45] costs us: our reported figure is the scene-0 row, and")
    print(f"  RL-ViGen's protocol is the average of all ten. Regime is held at {a.mode!r}")
    print(f"  throughout, so scene identity is the only thing that varied.")
    print(f"\n  One seed, one checkpoint, {frames} frames -- a property of THIS policy, not of the")
    print(f"  method. A retention near 1.0 at this episode count is failure to detect a")
    print(f"  difference, not proof of invariance; read the CI width for what could be resolved.")
    print(f"\n  elapsed {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
