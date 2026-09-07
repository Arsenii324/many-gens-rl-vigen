"""Production PPG cell must keep training and checkpoint evaluation on one C2 contract."""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _ppg_descriptor():
    return json.loads((ROOT / "datasphere" / "native" / "families.json").read_text())["ppg"]


def test_ppg_descriptor_declares_effective_dmc_comparator_parameters():
    """Descriptor values, not train.py defaults, define production PPG C2."""
    ppg = _ppg_descriptor()
    assert ppg["constants"] == {
        # [A36 RESOLVED 2026-09-07] SS E's geometry, adopted after a same-tier paired probe put
        # the cost at 32% (78.54 vs 59.44 IPS) = about +8.3 GPU-h on a campaign near 893.
        "num_envs": "1",
        "nstep": "2048",
        "frame_stack": "3",
        "gamma": ".99",
        "lr": "3e-4",
        "aux_lr": "3e-4",
        "nminibatch": "32",
        "entcoef": "0",
        # [Claude 2026-09-07, A36 corrected] SS E's shared grid includes "linear rate decay over
        # 1 million environment steps", and its PPG-specific search covers only
        # N_pi/E_pi/E_V/E_aux/beta_clone -- all of which equal PPG's released defaults, so nothing
        # overrides the shared grid for PPG. idaac already runs the same literal horizon from the
        # same sentence.
        "lr_decay_env_steps": "1000000",
    }
    options = ppg["options"]
    pairs = list(zip(options[::2], options[1::2]))
    assert dict(pairs) == {
        "--interacts_total": "{frames}",
        "--nstep": "{nstep}",
        "--seed": "{seed}",
        "--log_dir": "{run_dir}",
        "--save_mode": "all",
        "--ic_per_save": "{save_every}",
        "--frame_stack": "{frame_stack}",
        "--gamma": "{gamma}",
        "--lr": "{lr}",
        "--aux_lr": "{aux_lr}",
        "--lr_decay_env_steps": "{lr_decay_env_steps}",
        "--nminibatch": "{nminibatch}",
        "--entcoef": "{entcoef}",
    }


def test_ppg_cell_and_evaluator_propagate_the_descriptor_contract():
    """Cell training metadata and checkpoint evaluator must carry the same stack and params."""
    cell = (ROOT / "runnable" / "_launch" / "ppg_cell.sh").read_text()
    evaluator = (ROOT / "runnable" / "_launch" / "ppg_eval.py").read_text()

    for flag, variable in {
        "--frame_stack": "FRAME_STACK",
        "--gamma": "GAMMA",
        "--lr": "LR",
        "--aux_lr": "AUX_LR",
        "--nminibatch": "NMINIBATCH",
        "--entcoef": "ENTCOEF",
    }.items():
        assert f"{flag}) {variable}=\"$argument\"" in cell
        assert re.search(rf"{flag[2:]}=\$\{{{variable}(?::-[^}}]+)?\}}", cell)

    assert '--frame_stack "$FRAME_STACK"' in cell
    assert 'bash "$HERE/ppg.sh" "$TASK" "$NENV" "$@"' in cell
    assert 'ap.add_argument("--frame_stack", type=int, default=3' in evaluator
    assert "frame_stack=args.frame_stack" in evaluator


def test_ppg_rollout_length_override_reaches_ppo(tmp_path):
    """The geometry probe's --nstep must be a real CLI-to-rollout setting, not dead text."""
    del tmp_path
    train = (ROOT / "runnable" / "ppg" / "phasic_policy_gradient" / "train.py").read_text()
    assert "nstep=256" in train
    assert "parser.add_argument('--nstep', type=int, default=256)" in train
    assert "nstep=nstep" in train


def test_ppg_eval_loads_and_runs_a_real_nine_channel_c2_checkpoint(tmp_path, monkeypatch):
    """A real saved PPG model must receive the same 9-channel env used by production C2."""
    rlv = ROOT / "RL-ViGen-upstream"
    paths = [rlv, rlv / "envs" / "robosuiteVGB", ROOT / "runnable" / "ppg",
             ROOT / "runnable" / "_shim"]
    old_path = list(sys.path)
    for path in reversed(paths):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    monkeypatch.setenv("RLVIGEN_ROOT", str(rlv))
    monkeypatch.setenv("RLVIGEN_IMAGE_SIZE", "64")
    monkeypatch.setenv("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    if sys.platform == "darwin":
        monkeypatch.setenv("PYGLFW_LIBRARY", "/opt/homebrew/lib/libglfw.dylib")

    try:
        import torch
        from phasic_policy_gradient import ppg
        from phasic_policy_gradient.envs import get_venv
        from phasic_policy_gradient.impala_cnn import ImpalaEncoder

        try:
            venv = get_venv(num_envs=1, env_name="robosuite:Door", mode="eval-easy",
                            seed=1, scene_id=0, condition_seed=1, frame_stack=3)
        except Exception as error:
            text = str(error).lower()
            if any(token in text for token in ("egl", "opengl", "gl context", "display",
                                               "libgl", "mujoco_gl", "glfw")):
                pytest.skip(f"real PPG C2 eval needs unavailable renderer: {error}")
            raise

        try:
            assert tuple(venv.ob_space.shape)[-1] == 9
            model = ppg.PhasicValueModel(
                venv.ob_space,
                venv.ac_space,
                lambda obtype: ImpalaEncoder(obtype.shape, outsize=256, chans=(16, 32, 32)),
                arch="dual",
            )
            checkpoint = tmp_path / "model_terminal.jd"
            torch.save(model, checkpoint)
        finally:
            close = getattr(venv, "close", None)
            if callable(close):
                close()

        import importlib.util
        spec = importlib.util.spec_from_file_location("ppg_eval_c2", ROOT / "runnable" /
                                                      "_launch" / "ppg_eval.py")
        evaluator = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(evaluator)
        monkeypatch.setattr(sys, "argv", ["ppg_eval.py", "--model", str(checkpoint),
                                           "--task", "Door", "--mode", "eval-easy",
                                           "--num_envs", "1", "--episodes", "1", "--seed", "1",
                                           "--frame_stack", "3"])
        assert evaluator.main() == 0
    finally:
        sys.path[:] = old_path
