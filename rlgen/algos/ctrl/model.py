"""CTRL's network: `ext/ctrl_public/models.py::CTRLModel` (NOT `CTRLDAACModel` -- confirmed the
one this project uses, `docs/REGISTER.md`), rebuilt in PyTorch informed by that Flax reference.

PROVENANCE AND TIER, stated precisely (`docs/REGISTER.md`, 2026-08-16, corrected after this
docstring previously said "transcribed" unqualified, which overclaimed). CTRL's own reference is
Flax/JAX; this project is PyTorch throughout, so per `porting-directive.md` §1 this crosses the
framework boundary that "converts a faithful-transcription artifact into a constructed one" --
this IS a construction, informed by the reference and by an earlier `agy`-built prototype
(independently T1/T2-verified at the time, `docs/REGISTER.md` 2026-08-14), not itself that
prototype. The `Impala` encoder specifically now carries its OWN real, passing T1 check
(`tests/test_ctrl_parity.py`: Flax weights transplanted into this exact class, forward outputs
compared on the same input, agree to <1e-3) -- found and fixed two real bugs to get there, neither
visible from reading alone: the flatten order (PyTorch's native NCHW vs. Flax's NHWC) and the
maxpool padding VALUE (Flax's SAME-padding pads with the value that cannot win a max -- effectively
`-inf` -- not the 0 that's correct for the conv calls; zero-padding here silently wins a max
whenever a window's true pre-ReLU values are all negative, which happens routinely). The rest of
`CTRLPolicy` (the MLPs, `concat`, `protos`, FiLM conditioning) and `algo.py`'s training-loop math
are NOT yet covered by an equivalent numerical check -- T4 (structural accounting) for those parts,
stated as such rather than implied by the encoder's real T1 result.

INIT SCHEME -- CTRL's own four init functions (`models.py:13-23`), not borrowed from
`idaac`/`ppg`'s own independently-verified schemes even where the numbers coincide:
  `default_conv_init`   = `glorot_uniform()`      -- identical to PyTorch's `xavier_uniform_`
                                                      (Glorot and Xavier name the same method).
  `default_relu_init`   = `orthogonal(sqrt(2))`    -- Dense layers followed by relu.
  `default_linear_init` = `orthogonal(1.0)`        -- MLP output layers, `fc_v`, `concat`,
                                                      `protos`.
  `default_logits_init` = `orthogonal(0.01)`       -- `fc_pi` in the reference (Categorical
                                                      logits); this project's continuous
                                                      adaptation routes it to the Gaussian mean
                                                      head instead (see below), matching this
                                                      project's own established `mean_head_gain`
                                                      convention (`idaac/model.py`), which was
                                                      independently found to already be 0.01.
Flax's `nn.Dense`/`nn.Conv` default `bias_init` is zeros and nothing here overrides it, so every
bias below is zeroed to match.

ADAPTATION, form settled and recorded (`docs/REGISTER.md`, 2026-08-14). CTRL is discrete
(Procgen, `Categorical`); this project's action space is continuous (7-D robosuite). Two
independent adaptation surfaces, not one:
  1. The policy/value head: `DiagGaussianHead`, same external convention every other on-policy
     module here already uses (`idaac`/`ppg`/`ibac_sni`'s own model docstrings).
  2. `action_mlp`'s input (`models.py:176`, `jax.nn.one_hot(action, n_actions)` in the
     reference): the FiLM math (`(1+gamma_a)*z_state + beta_a`) does not care how `gamma_a`/
     `beta_a` were produced, only that `action_mlp` receives some fixed-size vector. Chosen: the
     raw continuous action vector, replacing the one-hot vector directly -- not binned, not
     dropped. See the register entry for the considered alternatives and the falsifiable
     condition that would overturn this.

`embedding_type="attention"` (the reference's other mode, `nn.SelfAttention`) is NOT implemented
here -- `embedding_type="concat"` is `train_ppo.py`'s own confirmed flag default and the only
mode any cited launch configuration uses. Scope is declared, not silently narrowed: T1/T2 parity
claims for this module cover the concat path only.

`reward_mlp` (`models.py:124`) is not transcribed at all -- confirmed dead in the reference's own
live forward pass (register entry, 2026-08-14: the FiLM-from-reward branch inside `cluster()` is
commented out). Building unreachable machinery would be exactly the "unused hook reads as a
considered decision with nothing behind it" gap `porting-directive.md` §5 warns against.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


def _conv_init(m: nn.Conv2d) -> nn.Conv2d:
    nn.init.xavier_uniform_(m.weight)
    nn.init.zeros_(m.bias)
    return m


def _relu_dense_init(m: nn.Linear) -> nn.Linear:
    nn.init.orthogonal_(m.weight, gain=2.0 ** 0.5)
    nn.init.zeros_(m.bias)
    return m


def _linear_dense_init(m: nn.Linear) -> nn.Linear:
    nn.init.orthogonal_(m.weight, gain=1.0)
    nn.init.zeros_(m.bias)
    return m


def _logits_dense_init(m: nn.Linear) -> nn.Linear:
    nn.init.orthogonal_(m.weight, gain=0.01)
    nn.init.zeros_(m.bias)
    return m


class ResidualBlock(nn.Module):
    """`models.py::ResidualBlock`: relu -> conv -> relu -> conv, then a skip add."""

    def __init__(self, c: int):
        super().__init__()
        self.c1 = _conv_init(nn.Conv2d(c, c, 3, 1, 1))
        self.c2 = _conv_init(nn.Conv2d(c, c, 3, 1, 1))

    def forward(self, x):
        y = self.c1(F.relu(x))
        y = self.c2(F.relu(y))
        return x + y


def _same_pad_2d(x: torch.Tensor, kernel: int, stride: int, value: float = 0.0) -> torch.Tensor:
    """Flax/TF "SAME" padding, formula-for-formula, applied explicitly before an unpadded
    PyTorch pool/conv -- NOT PyTorch's own symmetric `padding=k` argument, which pads the same
    amount on both sides and is only equivalent to SAME when the required total padding happens
    to be even. `models.py::Impala`'s maxpool (kernel=3, stride=2) needs total padding 1 at an
    84-input first stage, which SAME splits asymmetrically (0 before, 1 after) -- confirmed by
    the formula below, not assumed. `pad_total = max((ceil(in/stride)-1)*stride + kernel - in, 0)`,
    `pad_before = pad_total // 2`, `pad_after = pad_total - pad_before`; applied identically to
    both spatial dims since the inputs here are always square.

    `value` matters and must be chosen per caller, found the hard way (`docs/REGISTER.md`,
    2026-08-16): the default 0.0 is correct for the conv calls (a zero-padded input contributes
    nothing to a weighted sum) but WRONG for max-pooling, where a 0-valued pad can silently win
    the max whenever a window's genuine (pre-ReLU, possibly all-negative) values are all below
    zero -- exactly the case at every stage here, since pooling runs on `conv0`'s raw linear
    output before any activation. The maxpool call passes `value=-inf`, matching Flax's own
    `nn.max_pool`'s padding value for this reason, not by convention -- confirmed by a real T1
    weight-transplant test that failed with `value=0.0` (broadly-spread, non-edge-localized
    disagreement, ruling out a simple asymmetry-direction bug) and passed with `value=-inf`.
    """
    h = x.shape[-2]
    out_h = -(-h // stride)  # ceil
    pad_total = max((out_h - 1) * stride + kernel - h, 0)
    pad_before = pad_total // 2
    pad_after = pad_total - pad_before
    return F.pad(x, (pad_before, pad_after, pad_before, pad_after), value=value)


class Impala(nn.Module):
    """`models.py::Impala`: 3 stages of (16,2),(32,2),(32,2) channels/residual-blocks, each
    conv3x3-stride1 + maxpool3x3-stride2, then flatten -> relu -> Dense(256) -> relu.

    FIXED 2026-08-16 (`docs/REGISTER.md`): two corrections found while building a real
    weight-transplant T1 check against THIS module specifically, not the earlier prototype it
    was informed by.

    (1) The flatten step permutes NCHW -> NHWC before flattening, matching Flax's own
        `out.reshape(out.shape[0], -1)` on an NHWC tensor exactly. Flattening directly in
        PyTorch's native NCHW order (the first version of this file) is harmless for training
        from scratch -- the `fc` layer's own learned weights absorb any fixed permutation of
        which input position holds which feature -- but makes a weight-transplant comparison
        against the actual Flax reference meaningless, since a transplanted `fc` weight matrix
        assumes the two flattens agree on feature order.

    (2) Maxpool padding uses Flax/TF "SAME" (`_same_pad_2d`, explicit and asymmetric where the
        required total padding is odd), not PyTorch's `nn.MaxPool2d(..., padding=1)` (always
        symmetric). The two conventions produce the SAME output spatial size at every stage for
        this architecture (verified by the flatten-size assertion below, which held under both),
        but NOT the same values where SAME's own padding is asymmetric -- confirmed asymmetric at
        this project's actual 84x84 input by the formula in `_same_pad_2d`'s own docstring. A
        size match is not a value match; conflating them here would have been exactly the kind of
        "reading is not evidence" gap `porting-directive.md` §3 warns about, caught only by
        building the real comparison rather than trusting that same-output-shape implies
        same-output-values.
    """

    def __init__(self, in_ch: int, image_size: int = 84, out_dim: int = 256):
        super().__init__()
        self.stages = nn.ModuleList()
        c = in_ch
        for out_c, nblock in [(16, 2), (32, 2), (32, 2)]:
            conv = _conv_init(nn.Conv2d(c, out_c, 3, 1, 0))  # padding done explicitly in forward
            blocks = nn.ModuleList([ResidualBlock(out_c) for _ in range(nblock)])
            self.stages.append(nn.ModuleDict({"conv": conv, "blocks": blocks}))
            c = out_c
        with torch.no_grad():
            flat = self._conv_forward(torch.zeros(1, in_ch, image_size, image_size)).numel()
        if image_size == 84:
            assert flat == 3872, f"84x84 IMPALA flatten must be 3872, got {flat}"
        self.fc = _relu_dense_init(nn.Linear(flat, out_dim))

    def _conv_forward(self, x: torch.Tensor) -> torch.Tensor:
        for stage in self.stages:
            x = _same_pad_2d(x, kernel=3, stride=1)
            x = stage["conv"](x)
            x = _same_pad_2d(x, kernel=3, stride=2, value=float("-inf"))
            x = F.max_pool2d(x, kernel_size=3, stride=2, padding=0)
            for block in stage["blocks"]:
                x = block(x)
        return x

    def forward(self, obs_uint8: torch.Tensor) -> torch.Tensor:
        assert obs_uint8.dtype == torch.uint8, f"encoder expects uint8, got {obs_uint8.dtype}"
        x = obs_uint8.float() / 255.0
        x = self._conv_forward(x)
        x = x.permute(0, 2, 3, 1).contiguous()  # NCHW -> NHWC, matching Flax's flatten order
        x = F.relu(x.reshape(x.shape[0], -1))
        return F.relu(self.fc(x))


class MLP(nn.Module):
    """`models.py::MLP`: every layer relu-init'd and relu-activated except the last, which is
    linear-init'd with no activation."""

    def __init__(self, dims):
        super().__init__()
        self.dims = list(dims)

    def build(self, in_dim: int) -> nn.Sequential:
        layers, d = [], in_dim
        for i, dim in enumerate(self.dims):
            lin = nn.Linear(d, dim)
            if i == len(self.dims) - 1:
                _linear_dense_init(lin)
            else:
                _relu_dense_init(lin)
                layers += [lin, nn.ReLU(inplace=True)]
                d = dim
                continue
            layers += [lin]
            d = dim
        return nn.Sequential(*layers)


class DiagGaussianHead(nn.Module):
    """Adaptation, form settled externally -- see module docstring. `mean` uses
    `default_logits_init`'s gain (0.01), matching `fc_pi`'s own init exactly; `log_std` is a bare
    Parameter, outside the reference's init scheme entirely, matching `idaac/model.py`'s own
    continuous-adaptation shrinkage reasoning (robosuite's [-1,1] box)."""

    def __init__(self, in_dim: int, act_dim: int, init_log_std: float = -1.0):
        super().__init__()
        self.mean = _logits_dense_init(nn.Linear(in_dim, act_dim))
        self.log_std = nn.Parameter(torch.full((act_dim,), float(init_log_std)))

    def forward(self, feat) -> torch.distributions.Normal:
        return torch.distributions.Normal(self.mean(feat), self.log_std.exp())


def logp(dist: torch.distributions.Normal, a: torch.Tensor) -> torch.Tensor:
    return dist.log_prob(a).sum(-1, keepdim=True)


def entropy(dist: torch.distributions.Normal) -> torch.Tensor:
    return dist.entropy().sum(-1)


class CTRLPolicy(nn.Module):
    """`models.py::CTRLModel`, `embedding_type="concat"` only (see module docstring). ONE shared
    `encoder` for `ac()` (policy+value) AND `cluster()` -- matches the reference exactly (a
    single `self.encoder = Impala(...)` in `setup()`, called from both methods), NOT
    `CTRLDAACModel`'s dual `encoder_policy`/`encoder_value`.
    """

    def __init__(self, obs_shape, act_dim: int, window: int, n_clusters: int, hidden: int = 256,
                 init_log_std: float = -1.0):
        super().__init__()
        in_ch, image_size = obs_shape[0], obs_shape[1]
        self.act_dim = act_dim
        self.hidden = hidden
        self.window = window

        self.encoder = Impala(in_ch, image_size, hidden)
        self.fc_v = _linear_dense_init(nn.Linear(hidden, 1))
        self.dist_head = DiagGaussianHead(hidden, act_dim, init_log_std)

        # action_mlp: dims = [hidden, hidden*2] (models.py:123, dims[:-1]+[dims[-1]*2] at
        # dims=(256,256)) -- input is the raw continuous action vector (act_dim), not a one-hot
        # (see the adaptation note above).
        self._action_mlp = MLP([hidden, hidden * 2]).build(act_dim)
        # `concat` (models.py:129, `nn.Dense(self.dims[-1])`) consumes the WHOLE window flattened
        # (`z = (...).reshape(state.shape[0], -1)` before `self.concat(z)`, models.py:181-182) --
        # width `window * hidden`, not `hidden`. `window` must be fixed at construction (PyTorch
        # `Linear` needs a static input width, unlike Flax's shape-inferred `nn.Dense`).
        self.concat = _linear_dense_init(nn.Linear(window * hidden, hidden))

        self._v_clust_mlp = MLP([hidden, hidden]).build(hidden)
        self._w_clust_mlp = MLP([hidden, hidden]).build(hidden)
        self._v_pred_mlp = MLP([hidden, hidden]).build(hidden)
        self._w_pred_mlp = MLP([hidden, hidden]).build(hidden)

        # `models.py:137-139`, `self.protos = nn.Dense(n_cluster, kernel_init=default_linear_init)`
        # -- the Sinkhorn-Knopp prototype layer. `protos.weight` (PyTorch's (out,in) convention)
        # gives the n_clusters prototype vectors directly, one per row -- no need for the
        # reference's identity-matrix extraction trick (`models.py:187-189`,
        # `apply_fn(..., jnp.eye(hidden), method=protos_fn)`), which exists only because Flax's
        # functional API has no direct weight-tensor handle the way an `nn.Module` does.
        self.protos = _linear_dense_init(nn.Linear(hidden, n_clusters))

    def protos_fn(self, x):
        return self.protos(x)

    @torch.no_grad()
    def act(self, obs_u8: torch.Tensor, deterministic: bool = False):
        z = self.encoder(obs_u8)
        dist = self.dist_head(z)
        a = dist.mean if deterministic else dist.sample()
        return a, logp(dist, a)

    def value(self, obs_u8: torch.Tensor) -> torch.Tensor:
        return self.fc_v(self.encoder(obs_u8))

    def ac(self, obs_u8: torch.Tensor):
        z = self.encoder(obs_u8)
        return self.fc_v(z), self.dist_head(z)

    def cluster(self, state_u8: torch.Tensor, action: torch.Tensor):
        """state_u8: (B, T, C, H, W) uint8. action: (B, T, act_dim) float.
        Returns (v_clust, w_clust, v_pred, w_pred), each (B, hidden).
        """
        B, T = state_u8.shape[0], state_u8.shape[1]
        img_shape = state_u8.shape[2:]

        z_state = self.encoder(state_u8.reshape(B * T, *img_shape)).reshape(B, T, self.hidden)

        z_action = self._action_mlp(action.reshape(B * T, self.act_dim)).reshape(B, T, -1)
        gamma_a, beta_a = z_action.chunk(2, dim=-1)

        assert T == self.window, f"cluster() got a window of {T}, module built for {self.window}"
        z = ((1 + gamma_a) * z_state + beta_a).reshape(B, -1)
        z = self.concat(z)

        v_clust = self._v_clust_mlp(z)
        w_clust = self._w_clust_mlp(v_clust)
        v_pred = self._v_pred_mlp(z)
        w_pred = self._w_pred_mlp(v_pred)
        return v_clust, w_clust, v_pred, w_pred
