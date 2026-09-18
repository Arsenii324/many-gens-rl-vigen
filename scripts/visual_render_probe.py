#!/usr/bin/env python3
"""Dump a handful of PNGs per regime, so a human can look and answer a question no metric answers.

    python scripts/visual_render_probe.py --out results/evidence/visual-render-probe/frames

## Why this exists, and why it is not a measurement

The renderer-parity item in `OPERATOR-GUIDE.md` §11.4 asked for a full R_A/R_B comparison: the same
checkpoint evaluated here and on the production host, to show the two renderers agree numerically.
That is real work and was descoped (owner, 2026-09-18) to something smaller: **a visual question**,
because our returns already sit on the published table's axis (`notes/CAMPAIGN-REPORT-2026-09-18.md`
§2) -- what remains open is whether the pixels look right, not whether the axis is right.

C55/C95 (`docs/CONSTRUCTION.md`) already show the renderer is not a free choice: the same checkpoint
reads train 131.5 under `MUJOCO_GL=egl` (container, matching the production path) and 13.85 under
`MUJOCO_GL=glfw` (this laptop). A CPU/`glfw` render therefore answers a DIFFERENT question than the
one being asked, so this script does not have a local fallback. It must run where the cells run.

## What it does

For each of `train`, `eval-easy`, `eval-medium`, `eval-hard`, at a fixed seed and scene, it resets
the RL-ViGen Door environment (`wrappers.robo_wrapper.robo_make`, the same constructor every cell
and every offline evaluation uses) and saves the reset observation as one PNG. No checkpoint is
loaded and no policy runs: the visual question is about the *environment*, not about a trained
agent, so a checkpoint dependency would be a needless extra thing to get right for no benefit
answering this one.

## What it deliberately does NOT do

Launch anything. `make_env` is injected (`--maker`) precisely so this can be imported and its
frame-writing logic tested without robosuite, mujoco or a GPU present -- see
`tests/test_visual_render_probe.py`. The default `--maker` path
(`wrappers.robo_wrapper.robo_make`) only resolves inside the pinned cell image, with
`MUJOCO_GL=egl`, on the host. Running it there is a deliberate, separate, recorded step -- see
`results/evidence/visual-render-probe/CLAIM.md` for why it has not been run yet and the exact
command to run when it is.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Callable, Protocol

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGIMES = ("train", "eval-easy", "eval-medium", "eval-hard")


class _ResetEnv(Protocol):
    def reset(self): ...


def default_maker(task: str, seed: int, scene_id: int, mode: str, frame_stack: int) -> _ResetEnv:
    """The real path. Only resolves where robosuite/mujoco/robosuitevgb are installed."""
    upstream = ROOT / "RL-ViGen-upstream"
    if str(upstream) not in sys.path:
        sys.path.insert(0, str(upstream))
    from wrappers.robo_wrapper import robo_make  # noqa: PLC0415
    return robo_make(name=task, frame_stack=frame_stack, action_repeat=1,
                     seed=seed, scene_id=scene_id, mode=mode)


def _last_frame_hwc(obs):
    """The stack is CHW, channel-stacked across `frame_stack` repeats of the SAME reset frame
    (`FrameStackWrapper.reset` appends the identical pixel array `frame_stack` times -- see
    `RL-ViGen-upstream/wrappers/robo_wrapper.py`). The last 3 channels are one RGB frame; taking
    any of the `frame_stack` copies gives the same image, so there is no aliasing here to worry
    about, only a format conversion.
    """
    import numpy as np
    frame = np.asarray(obs)[-3:]           # (3, H, W)
    return np.transpose(frame, (1, 2, 0))  # (H, W, 3), what PNG writers expect


def capture(maker: Callable[..., _ResetEnv], out_dir: pathlib.Path, *, task: str = "Door",
           seed: int = 0, scene_id: int = 0, frame_stack: int = 3) -> list[pathlib.Path]:
    """One PNG per regime. Returns the paths written, in REGIME order."""
    from PIL import Image  # noqa: PLC0415  (only needed on the path that actually writes files)

    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for regime in REGIMES:
        env = maker(task=task, seed=seed, scene_id=scene_id, mode=regime, frame_stack=frame_stack)
        time_step = env.reset()
        frame = _last_frame_hwc(time_step.observation)
        path = out_dir / f"{regime}-scene{scene_id}-seed{seed}.png"
        Image.fromarray(frame, mode="RGB").save(path)
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "results/evidence/visual-render-probe/frames"))
    ap.add_argument("--task", default="Door")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--scene", type=int, default=0)
    ap.add_argument("--frame-stack", type=int, default=3)
    args = ap.parse_args(argv)

    print(f"MUJOCO_GL={__import__('os').environ.get('MUJOCO_GL', '<unset>')} "
          "-- must be 'egl' to match the production render path (C95); this script does not set it")
    written = capture(default_maker, pathlib.Path(args.out), task=args.task, seed=args.seed,
                      scene_id=args.scene, frame_stack=args.frame_stack)
    for p in written:
        print(f"  wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
