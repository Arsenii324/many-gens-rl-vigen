"""Real T1 parity check: `rlgen/algos/ctrl/model.py::Impala` against a Flax mirror of
`ext/ctrl_public/models.py::Impala`, built from scratch in this file (not imported, since the
reference itself needs `tensorflow_probability` for unrelated parts of `models.py` this test
doesn't exercise) with the SAME layer shapes/strides/kernel sizes as the primary source, weight
transplant, forward comparison on the same input.

This closes a real gap found 2026-08-16 (`docs/REGISTER.md`): the T1/T2 parity verification this
project's docs previously cited for CTRL was run against an earlier, different artifact (an `agy`
scratch prototype), never against the code that actually shipped in `rlgen/algos/ctrl/`. That
code, as first written, could not even have passed this check -- it flattened in PyTorch's native
NCHW order (Flax flattens NHWC) and used symmetric maxpool padding (Flax's own SAME padding is
asymmetric where the required total padding is odd, confirmed true at this project's actual 84x84
input, not assumed). Both are fixed in `model.py` directly; this test is what makes the fix
checkable rather than a claimed fix.

Scope, stated plainly per `porting-directive.md` §3: this covers the `Impala` CNN encoder only --
forward agreement under transplanted weights, fixed input, `image_size=84` (this project's real
robosuite obs size, not a smaller size chosen for convenience). It does NOT cover the rest of
`CTRLPolicy` (the MLPs, `concat`, `protos`, the FiLM conditioning) or `algo.py`'s training-loop
math (`_sinkhorn`, `_cos_loss`, `state_update`'s EMA) -- those remain unverified against the
reference numerically, same gap, not yet closed. T1 on the encoder specifically; not a blanket T1
claim for the module.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

# ext/ctrl_public/models.py imports tensorflow_probability for the policy distribution, which
# this test doesn't need (only the encoder is under test) and which may not be importable in
# every environment this test runs in -- mocked out so the import chain this test DOES need
# (jax/flax) isn't blocked by an unrelated dependency, matching the same workaround the earlier
# agy-run parity test used for the same reason.
sys.modules.setdefault("tensorflow_probability", MagicMock())
sys.modules.setdefault("tensorflow_probability.substrates", MagicMock())
sys.modules.setdefault("tensorflow_probability.substrates.jax", MagicMock())

import numpy as np
import pytest
import torch

jax = pytest.importorskip("jax")
jnp = pytest.importorskip("jax.numpy")
nn_flax = pytest.importorskip("flax.linen")

from rlgen.algos.ctrl.model import Impala as TorchImpala

IMAGE_SIZE = 84
IN_CH = 9  # this project's real frame_stack=3 * 3 channels


class _FlaxResidualBlock(nn_flax.Module):
    num_channels: int
    prefix: str

    @nn_flax.compact
    def __call__(self, x):
        y = nn_flax.relu(x)
        y = nn_flax.Conv(self.num_channels, kernel_size=[3, 3], strides=(1, 1), padding="SAME",
                         name=self.prefix + "/conv2d_1")(y)
        y = nn_flax.relu(y)
        y = nn_flax.Conv(self.num_channels, kernel_size=[3, 3], strides=(1, 1), padding="SAME",
                         name=self.prefix + "/conv2d_2")(y)
        return y + x


class _FlaxImpala(nn_flax.Module):
    """Mirrors `ext/ctrl_public/models.py::Impala` exactly: same stage config, same layer
    names (`/conv2d_%d`, `residual_{i}_{j}/conv2d_1|2`, `/representation`), same init functions
    read from that file (`default_conv_init=glorot_uniform`, `default_relu_init=orthogonal(sqrt2)`
    -- init choice doesn't affect a weight-transplant forward check, since weights are overwritten
    after `.init()` regardless, but the layer/name structure must match for the params pytree to
    have the shape this test's transplant code expects).
    """
    prefix: str

    @nn_flax.compact
    def __call__(self, x):
        out = x
        for i, (num_channels, num_blocks) in enumerate([(16, 2), (32, 2), (32, 2)]):
            conv = nn_flax.Conv(num_channels, kernel_size=[3, 3], strides=(1, 1), padding="SAME",
                                name=self.prefix + "/conv2d_%d" % i)
            out = conv(out)
            out = nn_flax.max_pool(out, window_shape=(3, 3), strides=(2, 2), padding="SAME")
            for j in range(num_blocks):
                block = _FlaxResidualBlock(num_channels, prefix="residual_{}_{}".format(i, j))
                out = block(out)
        out = out.reshape(out.shape[0], -1)
        out = nn_flax.relu(out)
        out = nn_flax.Dense(256, name=self.prefix + "/representation")(out)
        out = nn_flax.relu(out)
        return out


def test_impala_forward_agreement_under_weight_transplant():
    key = jax.random.PRNGKey(0)
    x_np = np.random.default_rng(0).integers(
        0, 256, size=(2, IMAGE_SIZE, IMAGE_SIZE, IN_CH)).astype(np.float32)

    flax_impala = _FlaxImpala(prefix="")
    params = flax_impala.init(key, jnp.array(x_np) / 255.0)
    flax_out = np.array(flax_impala.apply(params, jnp.array(x_np) / 255.0))

    torch_impala = TorchImpala(in_ch=IN_CH, image_size=IMAGE_SIZE)
    p = params["params"]
    # Flax auto-names each `_FlaxResidualBlock` submodule instance by class name + a RUNNING
    # index across all 6 blocks (`_FlaxResidualBlock_0`..`_5`), not by the `residual_{i}_{j}`
    # string passed as `prefix` (that string only names the two Conv layers *inside* each
    # block). Confirmed by direct inspection of `params['params'].keys()`, not assumed from the
    # naming scheme's own surface reading.
    res_idx = 0
    for i, (_num_channels, num_blocks) in enumerate([(16, 2), (32, 2), (32, 2)]):
        conv_w = np.array(p["/conv2d_%d" % i]["kernel"])
        conv_b = np.array(p["/conv2d_%d" % i]["bias"])
        torch_impala.stages[i]["conv"].weight.data.copy_(
            torch.from_numpy(conv_w).permute(3, 2, 0, 1))
        torch_impala.stages[i]["conv"].bias.data.copy_(torch.from_numpy(conv_b))
        for j in range(num_blocks):
            bp = p["_FlaxResidualBlock_%d" % res_idx]
            res_idx += 1
            # The two Conv layers inside each block are keyed by their FULL dotted name
            # (`"residual_{i}_{j}/conv2d_1"`, slash included, as one string) -- not nested a
            # further level under `"residual_{i}_{j}"` then `"conv2d_1"` separately.
            w1 = np.array(bp["residual_{}_{}/conv2d_1".format(i, j)]["kernel"])
            b1 = np.array(bp["residual_{}_{}/conv2d_1".format(i, j)]["bias"])
            w2 = np.array(bp["residual_{}_{}/conv2d_2".format(i, j)]["kernel"])
            b2 = np.array(bp["residual_{}_{}/conv2d_2".format(i, j)]["bias"])
            torch_impala.stages[i]["blocks"][j].c1.weight.data.copy_(
                torch.from_numpy(w1).permute(3, 2, 0, 1))
            torch_impala.stages[i]["blocks"][j].c1.bias.data.copy_(torch.from_numpy(b1))
            torch_impala.stages[i]["blocks"][j].c2.weight.data.copy_(
                torch.from_numpy(w2).permute(3, 2, 0, 1))
            torch_impala.stages[i]["blocks"][j].c2.bias.data.copy_(torch.from_numpy(b2))

    fc_w = np.array(p["/representation"]["kernel"])
    fc_b = np.array(p["/representation"]["bias"])
    torch_impala.fc.weight.data.copy_(torch.from_numpy(fc_w).t())
    torch_impala.fc.bias.data.copy_(torch.from_numpy(fc_b))

    x_torch = torch.from_numpy(x_np).permute(0, 3, 1, 2).contiguous().to(torch.uint8)
    with torch.no_grad():
        torch_out = torch_impala(x_torch).numpy()

    diff = np.max(np.abs(flax_out - torch_out))
    assert diff < 1e-3, (
        f"Impala forward disagreement under weight transplant: max abs diff {diff:.6e} "
        f"(flax sample: {flax_out[0, :5]}, torch sample: {torch_out[0, :5]})")
