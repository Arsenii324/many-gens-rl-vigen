"""Adapter over the VENDORED ALDA source. Nothing here reimplements a network.

Every module ALDA defines is imported from `third_party/alda/`, which holds ALDA_Official
@ 8dcc968 byte-for-byte (see `third_party/alda/UPSTREAM.md`; `test_vendored_files_are_pristine`
checks the hashes). This file exists only to do the two things upstream's code cannot do here,
and to make each of them a visible, testable patch rather than a rewrite:

  1. RESOLUTION. Upstream hardcodes `nn.Linear(in_features=4096, ...)` in the encoder and
     `nn.Linear(256, 4096)` plus `transition_shape=(256, 4, 4)` in the decoder. Those are correct
     only at 64x64. RL-ViGen renders 84x84 and `robo_make` takes no size argument, so at 84 the
     encoder's flat width is 6400 and the transposed convolutions land on 80, not 84.
     `patch_for_image_size` replaces EXACTLY two Linear layers and sets `output_padding` on the
     transposed convolutions that need it. It touches nothing else -- same conv stack, same
     channel widths, same activations, same initialisation. At 64 it is a provable no-op
     (`test_patch_is_a_noop_at_64`).

  2. THE UNWIRED ARM. Upstream's `ContinuousLatent.forward` returns only `z_hat`, so it cannot
     be fed to a trainer that reads `z_quantized` -- it is dead code in the release. `Continuous`
     below subclasses it and fills the two missing keys, which is what turns "SAC+AE" from a
     separate program into a one-line config change.

Codebook trainability is handled here too. Upstream creates the codebook as
`nn.Parameter(..., requires_grad=True)` and then never applies a gradient to it (FINDINGS
ALDA A1 -- the critic's gradient is real but `latent_optimizer.zero_grad()` discards it, and
ALDA's own loss contributes none). `freeze_codebook` reproduces that END STATE explicitly, so
the freeze is declared and testable instead of emergent.
"""
from __future__ import annotations

import os
import sys

import torch
import torch.nn as nn

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VENDOR = os.path.join(_ROOT, "third_party", "alda")
if _VENDOR not in sys.path:
    # prepended so `from common.utils import off_diagonal` inside the vendored
    # `quantized.py` resolves to our shim rather than to anything else on the path
    sys.path.insert(0, _VENDOR)

# --- upstream, unmodified -------------------------------------------------- #
from autoencoders.quantized_autoencoder import (          # noqa: E402
    Conv2DBlock, Conv2DTransposeBlock, QuantizedDecoder, QuantizedEncoder)
from disentangle.latents.associative import AssociativeLatent            # noqa: E402
from disentangle.latents.continuous import ContinuousLatent as _UpstreamContinuous  # noqa: E402
from disentangle.latents.quantized import QuantizedLatent as _UpstreamQuantized     # noqa: E402
from models.sac import (Actor, Critic, HistoryEncoder, QFunction,        # noqa: E402
                        RLProjection, gaussian_logprob, squash, weight_init)

__all__ = ["Actor", "Critic", "QFunction", "RLProjection", "HistoryEncoder", "weight_init",
           "gaussian_logprob", "squash", "AssociativeLatent", "QuantizedEncoder",
           "QuantizedDecoder", "Conv2DBlock", "Conv2DTransposeBlock", "build_latent_model",
           "build_encoder_decoder", "conv_plan", "freeze_codebook", "OuterEncoder",
           "ClampLatent",
           "count_parameters", "Continuous", "Quantized"]


# --------------------------------------------------------------------------- #
# resolution
# --------------------------------------------------------------------------- #
def conv_plan(size: int, n_layers: int = 4, k: int = 4, s: int = 2, p: int = 1):
    """Spatial sizes down upstream's encoder, and the output_padding that inverts each step.

    Conv2d:          out = floor((in + 2p - k) / s) + 1     -> with (4, 2, 1): floor((in-2)/2)+1
    ConvTranspose2d: out = (in - 1) * s - 2p + k + op       -> with (4, 2, 1): 2*in + op

    so `op = in - 2 * out`, which is 0 for even `in` and 1 for odd. Derived rather than assumed,
    because a decoder that silently reconstructs 80x80 from an 84x84 input would train against a
    mis-sized target and every loss would still look reasonable.
    """
    sizes = [size]
    for _ in range(n_layers):
        nxt = (sizes[-1] + 2 * p - k) // s + 1
        assert nxt >= 1, f"image {size} is too small for {n_layers} stride-{s} layers"
        sizes.append(nxt)
    out_pads = [sizes[i] - 2 * sizes[i + 1] for i in range(n_layers)]
    assert all(o in (0, 1) for o in out_pads), (sizes, out_pads)
    return sizes, out_pads


UPSTREAM_FLAT_DIM = 4096              # what upstream hardcodes; correct at 64x64 only
UPSTREAM_TRANSITION = (256, 4, 4)


def build_encoder_decoder(image_size: int, num_latents: int):
    """Upstream's encoder/decoder, patched for `image_size`. Returns (encoder, decoder, plan)."""
    sizes, out_pads = conv_plan(image_size)
    s = sizes[-1]
    flat = UPSTREAM_TRANSITION[0] * s * s
    enc = QuantizedEncoder(obs_shape=(3, image_size, image_size), num_latents=num_latents)
    dec = QuantizedDecoder(obs_shape=(3, image_size, image_size),
                           transition_shape=(UPSTREAM_TRANSITION[0], s, s),
                           num_latents=num_latents)
    if flat != UPSTREAM_FLAT_DIM:
        # exactly two layers, both of which upstream wrote as literals
        enc.linear[0] = nn.Linear(in_features=flat, out_features=256)
        dec.network[0] = nn.Linear(in_features=256, out_features=flat)
    # `output_padding` is a plain attribute read at call time by F.conv_transpose2d, so setting
    # it changes the output geometry without touching a single weight. Upstream's decoder walks
    # the encoder's layers backwards, hence out_pads[::-1].
    tblocks = [m for m in dec.network if isinstance(m, Conv2DTransposeBlock)]
    assert len(tblocks) == len(out_pads), (len(tblocks), len(out_pads))
    for blk, op in zip(tblocks, out_pads[::-1]):
        conv = blk.block1[0]
        assert isinstance(conv, nn.ConvTranspose2d)
        conv.output_padding = (op, op)
    return enc, dec, {"spatial": sizes, "out_pads": out_pads, "flat_dim": flat}


# --------------------------------------------------------------------------- #
# latent models
# --------------------------------------------------------------------------- #
class Continuous(_UpstreamContinuous):
    """No quantisation, no association -- the reconstruction-only arm.

    Upstream's `forward` returns `{'z_hat': x}` only, so `compute_embeddings` (which reads
    `z_quantized`) would KeyError; the class is unreachable in the release. The two missing keys
    are filled in here, and the DETACH MATTERS: `z_quantized` is the tensor the RL path consumes
    and `AssociativeLatent` derives it from `x.detach()`. Returning a live `x` here would let
    critic gradients into the encoder for this arm and not for ALDA, so the "ablation" would
    change two things at once -- and it would trip the pre-flight routing check, which asserts
    that the graph matches `cfg.critic_grad_to_encoder`. `z_hat` stays live, exactly as the
    straight-through estimator leaves it, so reconstruction still trains the encoder.
    """

    def forward(self, x):
        return {"z_continuous": x, "z_quantized": x.detach(), "z_hat": x}


class Quantized(_UpstreamQuantized):
    """SAC+QLAE ([A] Fig. 4): hard argmin instead of the softmax retrieval.

    Two upstream defects are repaired here, both consequences of the class never being wired
    into the trainer (FINDINGS ALDA A3):

      * `values_per_latent` is a property that returns a python LIST of detached tensors when
        `optimize_values` is False, while `quantize` immediately does `v[None]` on it. So
        `QuantizedLatent(optimize_values=False).forward(...)` raises
        `TypeError: list indices must be integers`. It cannot ever have been run in that mode.
      * `quantize` ends in a bare `.squeeze()`, which drops ANY size-1 axis -- a batch of one
        silently becomes shape (n_z,) instead of (1, n_z), and the straight-through add then
        broadcasts to (n_z, n_z). `squeeze(-1)` is what it means.
    """

    def _codes(self) -> torch.Tensor:
        v = self._values_per_latent
        return v if self.optimize_values else v.detach()

    def quantize(self, x):
        v = self._codes()
        d = torch.abs(x.unsqueeze(-1) - v[None])
        inds = torch.argmin(d, dim=-1)
        values = torch.gather(v[None].expand(x.shape[0], -1, -1), -1,
                              inds.unsqueeze(-1)).squeeze(-1)
        return values, inds


class ClampLatent(nn.Module):
    """Association replaced by a plain per-dimension clamp to [-1, 1]. NOT in [A] or [AC].

    The point of this arm is that finding A1 makes it nearly a prediction rather than a guess.
    With the codebook frozen at `linspace(-1, 1, 12)` and beta = 100, retrieval is
    round-to-nearest-grid-point (measured: it agrees with a hard argmin to <1e-3 except within
    4e-4 of a midpoint). A clamp is the same map without the grid. If clamping recovers most of
    ALDA's out-of-distribution gain, then what generalises is BOUNDING the latent, and the
    Hopfield framing is a description of that rather than an additional mechanism.

    Detached exactly like `AssociativeLatent`, so `critic_grad_to_encoder` means the same thing
    for this arm as for every other.
    """

    def __init__(self, num_latents: int, *_, **__):
        super().__init__()
        self.num_latents = num_latents

    def forward(self, x):
        z_q = x.detach().clamp(-1.0, 1.0)
        return {"z_continuous": x, "z_quantized": z_q, "z_hat": x + (z_q - x).detach()}


def freeze_codebook(latent_model: nn.Module, trainable: bool) -> nn.Module:
    """Make upstream's emergent freeze explicit. See FINDINGS ALDA A1."""
    p = getattr(latent_model, "_values_per_latent", None)
    if p is not None:
        p.requires_grad_(bool(trainable))
    return latent_model


def build_latent_model(kind: str, num_latents: int, values_per_latent: int, beta: float,
                       trainable: bool) -> nn.Module:
    if kind == "associative":
        m = AssociativeLatent(num_latents, values_per_latent, beta)
    elif kind == "quantized":
        # optimize_values gates upstream's `values_per_latent` PROPERTY, which detaches when
        # False. Passed through so the two knobs cannot contradict each other.
        m = Quantized(num_latents, values_per_latent, optimize_values=trainable)
    elif kind == "continuous":
        m = Continuous(num_latents)
    elif kind == "clamp":
        m = ClampLatent(num_latents)
    else:
        raise ValueError(kind)
    return freeze_codebook(m, trainable)


def codebook_tensor(latent_model: nn.Module):
    """The (n_z, |V|) codebook, or None for the continuous arm.

    Goes to `_values_per_latent` rather than the `values_per_latent` property because upstream's
    QLAE property returns a python list when `optimize_values` is False (see `Quantized`).
    """
    v = getattr(latent_model, "_values_per_latent", None)
    return None if v is None else v.detach()


def assignment_weights(latent_model: nn.Module, x: torch.Tensor) -> torch.Tensor:
    """Softmax retrieval weights, (B, n_z, |V|). Diagnostics only -- never in a loss.

    Upstream computes these inside `associate` and does not expose them; recomputed here with
    the same expression so the health detectors can watch the memory rather than infer it.
    """
    import torch.nn.functional as F
    # Only the associative latent HAS retrieval weights: `beta` exists solely on
    # AssociativeLatent, and continuous/clamp have no codebook at all. Callers iterate over
    # configured arms, so an unguarded version crashed on 3 of the 4 kinds -- with a misleading
    # late AttributeError for `quantized` (which does have a codebook, just no beta).
    v = codebook_tensor(latent_model)
    beta = getattr(latent_model, "beta", None)
    if v is None or beta is None:
        return None
    d = torch.abs(x.unsqueeze(-1) - v[None])
    return F.softmax(-d * beta, dim=-1)


# --------------------------------------------------------------------------- #
# composition
# --------------------------------------------------------------------------- #
class OuterEncoder(nn.Module):
    """trunk (shared) -> latent model -> history (shared) -> projection (per-head).

    Upstream's `OuterEncoder.forward` chains trunk -> history -> projection with no latent model
    in between; the trainer never calls it, using `compute_embeddings` instead, which inserts the
    latent model. Ours is a container only, for exactly that reason -- the forward pass lives in
    agent.py where the latent model is in scope. Field names match upstream's
    (`shared_trunk`, `shared_history_encoder`, `projection`) so a state dict is interchangeable.
    """

    def __init__(self, shared_trunk, shared_history_encoder, projection):
        super().__init__()
        self.shared_trunk = shared_trunk
        self.shared_history_encoder = shared_history_encoder
        self.projection = projection


def count_parameters(module: nn.Module) -> int:
    return sum(p.numel() for p in module.parameters())
