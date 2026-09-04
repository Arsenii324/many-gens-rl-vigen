"""PPG's encoder — a copy of its base's `impala_cnn.py`, plus the two init helpers it needs.

**Base term** (`docs/STEP-ZERO.md` gates 0/1): `openai/phasic-policy-gradient` @ `7295473`,
vendored verbatim at `_upstream_7295473/` after the working tree was opened (0 dirty, 0 untracked,
19/19 parse, PyTorch throughout). `diff` this against `_upstream_7295473/impala_cnn.py` and every
edit below is the whole of what changed.

**Nothing here transfers from `ibac_sni` by analogy, and assuming it would was a live risk.** Both
baselines run "an IMPALA CNN", but the two references initialise completely differently:
`train-procgen-pytorch` applies `xavier_uniform_` to the whole model, while this one uses
*normalized fan-in* init (`NormedConv2d`/`NormedLinear` below) with per-stack `scale` factors
threaded through the constructor. Same architecture name, different network.

## Edits over the base

**E1 — the batch/time axes collapse to one batch axis.** The reference's `forward` takes
`(B, T, H, W, C)`, folds `B*T`, transposes NHWC->NCHW, runs the stacks, unfolds, and flattens
(`impala_cnn.py:143-158`). Its `T` exists because `roller.py` collects `(env, step)`-shaped
rollouts. This project's harness hands the encoder `(B, C, H, W)` uint8 already in NCHW, one
observation per row, so the fold/transpose/unfold round-trip has nothing to do and is removed.
The arithmetic between them is untouched — verified numerically, not asserted:
`tests/test_ppg_base_parity.py` runs the vendored `ImpalaCNN` on `(1, B, H, W, C)` and this one on
the NCHW-transposed same tensor under transplanted weights, and requires agreement.

**E2 — none needed for input size.** The reference computes its own flattened width through
`CnnDownStack.output_shape` (`impala_cnn.py:112-119`, `(h + 1) // 2` per pooled stack), so 84x84
falls out as 84->42->21->11 -> `32*11*11 = 3872` with no edit at all. Worth noting because
`ibac_sni`'s base hardcoded `32*8*8` and needed a real edit (E1 there) to accept anything but 64.

**E3 — `scale_ob` stays 255.0 and stays inside the model.** Same seam as `ibac_sni`'s E2 but for
the opposite reason: here the reference *already* divides inside `forward` (`impala_cnn.py:146`),
so this is zero edits rather than a moved responsibility.

`Encoder`/`ImpalaEncoder`'s `gym3` wrapper (`impala_cnn.py:11-51,158-186`) is dropped: it exists
to carry `initial_state`/`first` for recurrent rollouts, this project is non-recurrent everywhere,
and `gym3.types` is a dependency the harness does not have. Declared, not silent.
"""
from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F


def NormedLinear(*args, scale=1.0, **kwargs):
    """`_upstream_7295473/torch_util.py:327-341`, verbatim apart from the dropped fp16 branch.

    Normalized fan-in init: take PyTorch's default init, then rescale each output unit's weight
    vector to have L2 norm exactly `scale`. Not xavier, not orthogonal — a third thing, and the
    one this reference actually uses.
    """
    out = nn.Linear(*args, **kwargs)
    out.weight.data *= scale / out.weight.norm(dim=1, p=2, keepdim=True)
    if kwargs.get("bias", True):
        out.bias.data *= 0
    return out


def NormedConv2d(*args, scale=1, **kwargs):
    """`_upstream_7295473/torch_util.py:343-351`, verbatim. Norm is over `dim=(1,2,3)` — per
    output channel, across in-channels and both kernel axes."""
    out = nn.Conv2d(*args, **kwargs)
    out.weight.data *= scale / out.weight.norm(dim=(1, 2, 3), p=2, keepdim=True)
    if kwargs.get("bias", True):
        out.bias.data *= 0
    return out


class CnnBasicBlock(nn.Module):
    """`impala_cnn.py:53-86`. `scale` reaches both convs as `sqrt(scale)`, so a stack's total
    scale is distributed across its blocks rather than applied twice."""

    def __init__(self, inchan, scale=1, batch_norm=False):
        super().__init__()
        self.inchan = inchan
        self.batch_norm = batch_norm
        s = math.sqrt(scale)
        self.conv0 = NormedConv2d(self.inchan, self.inchan, 3, padding=1, scale=s)
        self.conv1 = NormedConv2d(self.inchan, self.inchan, 3, padding=1, scale=s)
        if self.batch_norm:
            self.bn0 = nn.BatchNorm2d(self.inchan)
            self.bn1 = nn.BatchNorm2d(self.inchan)

    def residual(self, x):
        if getattr(self, "batch_norm", False):
            x = self.bn0(x)
        x = F.relu(x, inplace=False)
        x = self.conv0(x)
        if getattr(self, "batch_norm", False):
            x = self.bn1(x)
        x = F.relu(x, inplace=False)
        x = self.conv1(x)
        return x

    def forward(self, x):
        return x + self.residual(x)


class CnnDownStack(nn.Module):
    """`impala_cnn.py:88-119`. `firstconv` takes the DEFAULT scale=1 — only the residual blocks
    receive the per-stack `scale`, which is easy to get wrong when reading quickly."""

    def __init__(self, inchan, nblock, outchan, scale=1, pool=True, **kwargs):
        super().__init__()
        self.inchan = inchan
        self.outchan = outchan
        self.pool = pool
        self.firstconv = NormedConv2d(inchan, outchan, 3, padding=1)
        s = scale / math.sqrt(nblock)
        self.blocks = nn.ModuleList(
            [CnnBasicBlock(outchan, scale=s, **kwargs) for _ in range(nblock)]
        )

    def forward(self, x):
        x = self.firstconv(x)
        if getattr(self, "pool", True):
            x = F.max_pool2d(x, kernel_size=3, stride=2, padding=1)
        for block in self.blocks:
            x = block(x)
        return x

    def output_shape(self, inshape):
        c, h, w = inshape
        assert c == self.inchan
        if getattr(self, "pool", True):
            return (self.outchan, (h + 1) // 2, (w + 1) // 2)
        return (self.outchan, h, w)


class ImpalaCNN(nn.Module):
    """`impala_cnn.py:121-157`, with edit E1 (no batch/time fold, input already NCHW).

    Module names are kept identical to the reference (`stacks.N.firstconv`,
    `stacks.N.blocks.M.conv0`, `dense`) so a state_dict transplants across without remapping —
    which is what makes the parity test in `tests/test_ppg_base_parity.py` a real T1 rather than
    a shape check.
    """

    name = "ImpalaCNN"

    def __init__(self, inshape, chans=(16, 32, 32), outsize=256, scale_ob=255.0,
                 nblock=2, final_relu=True, **kwargs):
        """`inshape` is (C, H, W) here; the reference takes (H, W, C) because its input is NHWC."""
        super().__init__()
        self.scale_ob = scale_ob
        curshape = tuple(inshape)
        s = 1 / math.sqrt(len(chans))          # per stack scale
        self.stacks = nn.ModuleList()
        for outchan in chans:
            stack = CnnDownStack(curshape[0], nblock=nblock, outchan=outchan, scale=s, **kwargs)
            self.stacks.append(stack)
            curshape = stack.output_shape(curshape)
        self.dense = NormedLinear(int(curshape[0] * curshape[1] * curshape[2]),
                                  outsize, scale=1.4)
        self.outsize = outsize
        self.final_relu = final_relu

    def forward(self, x):
        # [E1] The reference folds (B,T) and transposes NHWC->NCHW here; our harness already
        # supplies (B,C,H,W). `.float()/scale_ob` is not in-place: the rollout buffer holds this
        # same uint8 tensor and must not be mutated.
        x = x.to(dtype=torch.float32) / self.scale_ob
        for stack in self.stacks:
            x = stack(x)
        x = x.reshape(x.shape[0], -1)          # reference's flatten_image, C-major, same order
        x = torch.relu(x)
        x = self.dense(x)
        if self.final_relu:
            x = torch.relu(x)
        return x


class PPGPolicy(nn.Module):
    """`_upstream_7295473/ppg.py:66-158`, `PhasicValueModel` at its default `arch="dual"`.

    **Dual encoders are the architecture, not an optimisation.** `enc_keys` resolves to
    `["pi", "vf"]` under `arch="dual"` (`ppg.py:80-90`), so `pi_enc` and `vf_enc` are two
    *separate, independently-parameterised* IMPALA CNNs. The policy gradient trains one and the
    value function the other; the auxiliary phase is what transfers value knowledge back into the
    policy encoder, which is the whole point of the method. A single shared encoder is a different
    algorithm (`arch="shared"` in the same file) — and closing that gap is one reason this rebuild
    exists: `docs/FAITHFULNESS.md` carried "PPG's dual-network gap" as a standing open finding
    against the construction this replaces.

    Three heads, all `NormedLinear(..., scale=0.1)` (`ppg.py:105-108`):
      `pi_head`      on `pi_enc` -> action distribution parameters
      `vf_vhead`     on `vf_enc` -> `vpredtrue`, the value used by PPO
      `aux_vf_head`  on `pi_enc` -> `vpredaux`, the auxiliary-phase target head

    **The continuous head is authored — the reference has none.** `distr_builder` raises on any
    non-`Discrete` action type (`distr_builder.py:22-38`), and its `_make_normal` is dead code
    with `scale` hardcoded to 1.0 and the authors' own `warnings.warn("Using stdev=1")`
    (`docs/REGISTER.md`, 2026-08-16). So `pi_head` emits a mean and `logstd` is a separate
    state-independent parameter, matching what `make_pdtype` would do for a Box space and what
    the other three on-policy baselines here already do. `porting-directive.md` §4 adaptation
    with no first-party reference; graded NOT INTRINSIC in `docs/INTEGRATION-DELTA.md`.

    One wart carried rather than tidied: the reference assigns `self.pi_enc = enc_fn(obtype)`
    (`ppg.py:92`) and then immediately overwrites it in the `enc_keys` loop (`ppg.py:99-100`),
    building one throwaway encoder. Not reproduced — it allocates a network that is never read,
    and reproducing an allocation is not fidelity to any behaviour.
    """

    def __init__(self, obs_shape, act_dim, hidden=256, init_log_std=-1.0,
                 chans=(16, 32, 32), nblock=2):
        super().__init__()
        self.pi_enc = ImpalaCNN(obs_shape, chans=chans, outsize=hidden, nblock=nblock)
        self.vf_enc = ImpalaCNN(obs_shape, chans=chans, outsize=hidden, nblock=nblock)
        self.pi_head = NormedLinear(hidden, act_dim, scale=0.1)
        self.vf_vhead = NormedLinear(hidden, 1, scale=0.1)
        self.aux_vf_head = NormedLinear(hidden, 1, scale=0.1)
        self.logstd = nn.Parameter(torch.full((1, act_dim), float(init_log_std)))

    def _distr(self, mean):
        return torch.distributions.Normal(mean, self.logstd.exp().expand_as(mean))

    def forward(self, obs):
        """-> (pd, vpredtrue, vpredaux). Mirrors `ppg.py:135-157` minus the state plumbing."""
        pi_x = self.pi_enc(obs)
        vf_x = self.vf_enc(obs)
        pd = self._distr(self.pi_head(pi_x))
        vpredtrue = self.vf_vhead(vf_x)[..., 0]
        vpredaux = self.aux_vf_head(pi_x)[..., 0]
        return pd, vpredtrue, vpredaux

    def act(self, obs, deterministic=False):
        pd, _v, _aux = self.forward(obs)
        a = pd.mean if deterministic else pd.sample()
        return a, logp(pd, a)


def logp(dist, a):
    """Summed over action dims, keeping a trailing 1 for the trainer's storage contract."""
    return dist.log_prob(a).sum(-1, keepdim=True)


def entropy(dist):
    return dist.entropy().sum(-1)


def _value_only(policy, obs):
    """`vpredtrue` without running the policy encoder.

    `forward` evaluates BOTH encoders because the training loop needs both. The trainer calls
    `value_of` once per environment step, where `pi_enc`'s output is discarded — so running it
    would double the per-step encoder cost for nothing. Not an approximation: the reference's own
    `vf_keys` path reads `vf_vhead(vf_enc(ob))` and nothing else (`ppg.py:145-152`), and
    `tests/test_ppg_hermetic.py` pins this against `forward`'s `vpredtrue` exactly.
    """
    return policy.vf_vhead(policy.vf_enc(obs))[..., 0]


PPGPolicy.value = lambda self, obs: _value_only(self, obs)
