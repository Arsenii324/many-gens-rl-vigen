"""Focused contracts for the configured IBAC-SNI Door production path.

These tests cover the port-specific seams which the upstream MiniGrid-only Torch-RL code cannot
exercise: 64-pixel CoinRun-style Impala geometry, a continuous action distribution, and the
shared evaluator's explicit device/regime hand-off.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IBAC = ROOT / "runnable" / "ibac_sni" / "torch_rl"


def test_door_training_retains_upstream_16_rollout_count_with_spawn_factories():
    """Door uses one parent environment and fifteen independently seeded spawned workers."""
    train = (IBAC / "scripts" / "train.py").read_text()
    runtime = (IBAC / "ibac_sni_runtime.py").read_text()
    penv = (IBAC / "torch_rl" / "torch_rl" / "utils" / "penv.py").read_text()

    assert 'add_argument("--procs", type=int, default=16' in train
    assert "envs.append(make_rlvigen_env_process(args.env, args.seed))" in train
    assert "functools.partial(make_rlvigen_env_process, args.env, args.seed + 10000*i)" in train
    assert 'start_method = "spawn" if any(callable(env) for env in self.envs[1:]) else None' in penv
    for seed_call in ("random.seed(env_seed)", "numpy.random.seed(env_seed)", "torch.manual_seed(env_seed)"):
        assert seed_call in runtime


def test_visual_impala_box_head_preserves_batchwise_ppo_contract():
    """64px Impala plus VIB must emit one seven-action Gaussian event per environment."""
    code = r'''
import contextlib
import io
import json
import numpy as np
import gym
import torch
with contextlib.redirect_stdout(io.StringIO()):
    from model import ACModel
    model = ACModel({'image': (64, 64, 3)},
                    gym.spaces.Box(-1., 1., (7,), dtype=np.float32),
                    model_type='impala', use_bottleneck=True, sni_type='vib')
    obs = type('Obs', (), {'image': torch.zeros((2, 64, 64, 3))})()
    dist_run, dist_train, value, kl = model.compute_train(obs)
sample = dist_run.sample()
print(json.dumps({
    'params': sum(p.numel() for p in model.parameters()),
    'embedding': model.image_embedding_size,
    'sample': list(sample.shape),
    'log_prob': list(dist_run.log_prob(sample).shape),
    'entropy': list(dist_train.entropy().shape),
    'value': list(value.shape),
    'kl': list(kl.shape),
}))
'''
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join((str(IBAC), str(IBAC / "torch_rl")))
    proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    observed = json.loads(proc.stdout.splitlines()[-1])
    assert observed == {
        "params": 360399,
        "embedding": 2048,
        "sample": [2, 7],
        "log_prob": [2],
        "entropy": [2],
        "value": [2],
        "kl": [2],
    }


def test_shared_evaluator_rebuilds_the_native_agent_on_its_selected_device():
    """Checkpoint evaluation must use the native loader, 64px env seam, and caller device."""
    evaluator = (ROOT / "scripts" / "eval_grid.py").read_text()
    launch = (ROOT / "runnable" / "_launch" / "ibac_sni.sh").read_text()
    agent = (IBAC / "utils" / "agent.py").read_text()
    ppo = (IBAC / "torch_rl" / "torch_rl" / "algos" / "ppo.py").read_text()

    assert 'os.environ.setdefault("RLVIGEN_IMAGE_SIZE", "64")' in evaluator
    assert 'os.environ["RLVIGEN_MODE"] = mode' in evaluator
    assert 'os.environ["RLVIGEN_SCENE_ID"] = str(scene_id)' in evaluator
    assert "ibac_utils.Agent(env_id, env.observation_space, str(model_dir)," in evaluator
    assert "policy_mode == \"mode\", 1," in evaluator
    assert "device=device)" in evaluator
    assert "--model_type impala --entropy-coef 0.0 --beta 1e-4" in launch
    assert 'export MUJOCO_GL="${MUJOCO_GL:-egl}"' in launch
    assert "loss = policy_loss - self.entropy_coef * entropy" in ppo
    assert "+ self.beta * kl" in ppo
    assert "self.acmodel.to(self.device)" in agent
    assert "actions = actions.cpu().numpy()" in agent


def test_16_process_smoke_does_not_claim_unrecorded_final_hyperparameters():
    """The gt4i.1 smoke records no beta/entropy flag and is launch evidence only."""
    evidence = json.loads((ROOT / "results" / "validation" / "ibac_sni-procs16-v125.json").read_text())
    limits = evidence["what_this_does_not_prove"]
    assert any("--beta 1e-4" in item and "--entropy-coef 0.0" in item for item in limits)
    assert any("source/payload revision" in item for item in limits)


def test_competence_gate_does_not_relabel_historical_entropy_evidence_as_final_config_evidence():
    source = (ROOT / "scripts" / "production_gates.py").read_text()
    body = source[source.index("def gate_ibac_sni_competence"):source.index("def gate_ctrl_config_binding")]
    assert "historical procs=1" in body
    assert "does not bind --beta 1e-4" in body
    assert "exact-final" in body and "procs=16 V100 competence evidence" in body
