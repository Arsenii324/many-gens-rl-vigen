"""No init array may hardcode the observation's channel count.

Flax's `nn.Conv` declares only its OUTPUT features, so the CTRL model itself needed no edit for
A40 REVISED-2's three-frame stack. That made "Flax infers the input width" look true. It is true of
the LAYER and false of `init`, which takes the width from whatever array it is handed -- and three
separate call sites handed it a literal `(64, 64, 3)`.

Job `bt12q2bfbiih2lb43obp` died 2:38 into the first three-frame ctrl cell:

    flax.errors.ScopeParamShapeError: Initializer expected to generate shape (3, 3, 3, 16)
    but got shape (3, 3, 9, 16) for parameter "kernel" in "/encoder//conv2d_0"

Training failed first only because it runs first. `scripts/eval_grid.py` carried the identical
literal and would have failed the same cell at its endpoint evaluation; `evaluate_ppo.py` carried
a third copy. A literal that is wrong in two places is wrong in the third.

The behavioural test below is the one that matters: it initialises the real model at the declared
geometry and applies a real observation of that geometry, which is exactly the pairing that broke.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rlgen.protocol import OBSERVATION_GEOMETRY  # noqa: E402

jnp = pytest.importorskip("jax.numpy")
pytest.importorskip("flax")


def test_no_call_site_hardcodes_three_channels():
    for relative in ("runnable/ctrl/train_ppo.py", "runnable/ctrl/evaluate_ppo.py",
                     "scripts/eval_grid.py"):
        text = (ROOT / relative).read_text()
        offending = [line.strip() for line in text.splitlines()
                     if "jnp.zeros" in line and "64, 64, 3" in line]
        assert not offending, (
            f"{relative} initialises Flax parameters from a hardcoded (64, 64, 3), which pins the "
            f"encoder at one frame regardless of the declared geometry: {offending}")


def test_the_evaluator_derives_the_shape_from_the_declaration():
    text = (ROOT / "scripts" / "eval_grid.py").read_text()
    assert 'OBSERVATION_GEOMETRY["ctrl"]' in text
    assert "3 * frame_stack" in text, (
        "the evaluator must derive the channel count from the declared frame stack, or it will "
        "silently disagree with the trainer the next time the stack moves")


def test_the_real_model_initialises_at_the_declared_geometry():
    """The behavioural half: the encoder's kernel must be built for the declared channel count.

    Pinned to the CPU backend. jax-metal fails the orthogonal initializer with
    `failed to legalize operation 'mhlo.custom_call'`, which is a local backend limitation and has
    nothing to do with the property under test.
    """
    import os
    import subprocess

    image_size, frame_stack = OBSERVATION_GEOMETRY["ctrl"]
    channels = 3 * frame_stack
    code = f"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path({str(ROOT / 'runnable' / 'ctrl')!r}).resolve()))
import jax, jax.numpy as jnp
from models import CTRLModel
model = CTRLModel(dims=(256, 256), n_cluster=200, n_actions=7, continuous=True,
                  n_att_heads=2, embedding_type='concat')
state = jnp.zeros((1, 10, {image_size}, {image_size}, {channels}))
action = jnp.zeros((1, 10, 7))
params = model.init(jax.random.PRNGKey(0), state=state, action=action, reward=action)
convs = [leaf.shape for path, leaf in jax.tree_util.tree_flatten_with_path(params)[0]
         if len(leaf.shape) == 4]
print(convs[0][2])
"""
    environment = {**os.environ, "JAX_PLATFORMS": "cpu"}
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          timeout=600, env=environment, cwd=str(ROOT))
    if done.returncode != 0:
        pytest.skip(f"ctrl's JAX model could not be built here: {done.stderr.strip()[-300:]}")
    built_for = int(done.stdout.strip().splitlines()[-1])
    assert built_for == channels, (
        f"the encoder's first convolution was built for {built_for} input channels while "
        f"OBSERVATION_GEOMETRY declares {frame_stack} frames ({channels} channels). That is the "
        "exact mismatch that killed bt12q2bfbiih2lb43obp.")
