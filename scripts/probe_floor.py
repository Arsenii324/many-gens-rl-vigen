#!/usr/bin/env python3
"""What does a random policy score? The floor, without which a trained 0.000 means nothing.

    python scripts/probe_floor.py --episodes 30
    python scripts/probe_floor.py --task Lift --episodes 100

This is `docs/CONSTRUCTION.md` C17, and it is the negative control this project has been
reporting numbers without. Every success rate on record is `0.000`, and nothing establishes
whether that means *"the policies fail"* or *"this task yields no successes at this budget"*.
Those are different findings and they call for different next steps.

## The gap this specifically closes

`tests/test_success_metric.py` proves the success flag can travel from `Door._check_success()` to
the caller — by **forcing** it True. That is the right test for plumbing, and it is not evidence
that the signal ever fires **on its own**. So today we cannot distinguish

    "Door is hard"                    from    "the success signal never fires in our setup"

and those look identical from a log of zeros. This runs real episodes under a random policy and
counts what actually happens.

## What is measured, and why each is here

- **success rate + Wilson interval** -- the floor itself. Wilson because at p=0 the normal
  approximation has width zero and would claim certainty from a handful of episodes.
- **whether the flag EVER fired**, reported separately from the rate. `0/100` and "never
  observed" are the same number and a different statement.
- **episode return: mean, sd, and a bootstrap CI on the mean** -- if success never fires, the
  dense reward is the only signal left. The DISPERSION is not decoration: a control without a
  spread cannot bound anything, and comparing a trained number against a bare floor mean says
  nothing about whether the difference is outside noise. This was reported as mean/max only at
  first, and that gap surfaced the moment a real training number had to be interpreted.
- **throughput** -- steps/sec and episodes/min. Not decoration: it is the input to any compute
  budget, and this project has never measured it.

## What this cannot tell you

A floor is not a ceiling. Knowing chance scores 0 does not establish that a *trained* policy can
score above 0 at an affordable budget -- that needs either a trained policy or a scripted one,
and it is deliberately not attempted here. Reporting a floor as though it bounded the achievable
is the error this file exists to avoid, not to commit.

It is also one seed's worth of a stochastic process. The interval is the honest width; the point
estimate is not.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys
import time

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.metrics import bootstrap_ci, wilson_interval  # noqa: E402


def _setup_env_path() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    rlv = root / "RL-ViGen-upstream"
    os.environ.setdefault("RLVIGEN_ROOT", str(rlv))
    os.environ.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    if sys.platform == "darwin":
        os.environ.setdefault("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")
    for p in (str(rlv), str(rlv / "envs" / "robosuiteVGB")):
        if p not in sys.path:
            sys.path.insert(0, p)


def run(task: str, mode: str, episodes: int, seed: int, max_steps: int,
        scene_id: int = 0, paired: bool = True) -> dict | None:
    """`paired` measures the floor on the SAME placements the fleet's episodes will see.

    [Added 2026-09-05] Reviews 7 and 8 both asked for the 1.818 floor to be re-measured under the
    current evaluator, because the number predates per-episode condition seeding. The marginal
    placement distribution is unchanged by that switch -- both draw uniformly -- so the floor's
    expected value should not move, and this is a confirmation rather than a correction.

    But re-measuring it *paired* is strictly more useful than re-measuring it: with the same
    `placement_condition_seed(seed, scene, i)` the baselines use, episode i of the floor runs the
    identical physical placement as episode i of every baseline. The floor stops being a
    population constant compared across samples and becomes a per-episode control.

    The action stream is a separate `default_rng(seed)` and is deliberately NOT reseeded here, so
    re-seeding the global placement stream cannot change which random actions are taken.
    """
    import robosuitevgb.utils as ru
    from scripts.eval_grid import seed_episode_placement
    try:
        env = ru.make_env(task_name=task, seed=seed, scene_id=scene_id, mode=mode)
    except Exception as e:
        print(f"  could not build {task}/{mode}: {type(e).__name__}: {str(e)[:70]}")
        return None

    rng = np.random.default_rng(seed)
    returns, successes, lengths = [], 0, []
    ever = False
    t0 = time.time()
    steps_total = 0
    conditions = []
    for ep in range(episodes):
        if paired:
            conditions.append(seed_episode_placement(seed, scene_id, ep))
        env.reset()
        ep_ret, ep_success, n = 0.0, False, 0
        for _ in range(max_steps):
            a = rng.uniform(-1.0, 1.0, size=np.shape(env.action_space.sample()))
            _, r, done, info = env.step(a)
            ep_ret += float(r)
            n += 1
            steps_total += 1
            # An episode counts as a success if the flag held at ANY step -- the same rule the
            # baselines use (e.g. ibac_sni torch_rl/algos/base.py), because the env auto-resets.
            if bool((info or {}).get("success", False)):
                ep_success = True
            if done:
                break
        returns.append(ep_ret)
        lengths.append(n)
        successes += int(ep_success)
        ever = ever or ep_success
    dt = time.time() - t0
    return dict(returns=np.array(returns), successes=successes, n=episodes, ever=ever,
                lengths=np.array(lengths), steps=steps_total, seconds=dt,
                paired=paired, scene_id=scene_id, placement_condition_seeds=conditions)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", default="Door,Lift", help="comma-separated")
    ap.add_argument("--mode", default="train")
    ap.add_argument("--episodes", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-steps", type=int, default=500, help="the protocol horizon")
    ap.add_argument("--size", default="84")
    ap.add_argument("--scene-id", type=int, default=0)
    ap.add_argument("--unpaired", action="store_true",
                    help="draw placements from the running global stream, as before 2026-09-05. "
                         "The default pairs each episode with placement_condition_seed(seed, "
                         "scene, i), the same condition the fleet's episode i will run under")
    a = ap.parse_args()

    _setup_env_path()
    os.environ["RLVIGEN_IMAGE_SIZE"] = str(a.size)

    print(f"\nPROBE -- random-policy floor, regime {a.mode!r}, {a.episodes} episodes, "
          f"horizon {a.max_steps}\n")
    rows = []
    for task in a.task.split(","):
        task = task.strip()
        print(f"  running {task} ...", flush=True)
        r = run(task, a.mode, a.episodes, a.seed, a.max_steps,
                scene_id=a.scene_id, paired=not a.unpaired)
        if r:
            rows.append((task, r))

    if not rows:
        print("\n  no environment could be built. A SKIP is not a pass: no floor was measured.")
        return 1

    print(f"\n  {'task':<8}{'succ':>7}{'rate':>8}{'95% Wilson':>18}{'ever?':>8}")
    print("  " + "-" * 50)
    for task, r in rows:
        lo, hi = wilson_interval(r["successes"], r["n"])
        print(f"  {task:<8}{r['successes']:>4}/{r['n']:<3}{r['successes']/r['n']:>8.3f}"
              f"{f'[{lo:.3f}, {hi:.3f}]':>18}{'YES' if r['ever'] else 'never':>8}")

    print(f"\n  return under a random policy -- the control any trained number is read against")
    print(f"  {'task':<8}{'mean':>9}{'sd':>8}{'min':>8}{'max':>9}{'95% CI on the mean':>22}")
    print("  " + "-" * 64)
    for task, r in rows:
        ret = r["returns"]
        clo, chi = bootstrap_ci(ret, stat=lambda x: float(np.mean(x)), seed=0)
        print(f"  {task:<8}{ret.mean():>9.3f}{ret.std(ddof=1):>8.3f}{ret.min():>8.3f}"
              f"{ret.max():>9.3f}{f'[{clo:.3f}, {chi:.3f}]':>22}")

    print(f"\n  {'task':<8}{'steps':>9}{'seconds':>10}{'steps/s':>10}{'ep/min':>9}"
          f"{'ep len':>9}")
    print("  " + "-" * 60)
    for task, r in rows:
        sps = r["steps"] / max(r["seconds"], 1e-9)
        print(f"  {task:<8}{r['steps']:>9}{r['seconds']:>10.1f}{sps:>10.1f}"
              f"{60.0 * r['n'] / max(r['seconds'], 1e-9):>9.1f}{r['lengths'].mean():>9.1f}")

    print("\n  'ever?' is reported apart from the rate on purpose: 0/N and 'never observed' are")
    print("  the same number and a different statement. Until the flag is seen firing without")
    print("  being forced, a trained 0.000 cannot be distinguished from a dead signal.")
    print("\n  A floor is NOT a ceiling. That chance scores 0 says nothing about what a trained")
    print("  policy reaches at an affordable budget -- that needs a trained or scripted policy")
    print("  and is deliberately not attempted here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
