"""IDAAC's encoder — a copy of its base's `ResNetBase`, with the two edits the target forces.

**Base term** (`docs/STEP-ZERO.md` gates 0/1): `rraileanu/idaac` @ `2fe3020`, vendored verbatim at
`_upstream_2fe3020/` after the working tree was opened (0 dirty, all files parse, PyTorch).
`diff` this against `_upstream_2fe3020/model.py` and the edits below are the whole of what changed.

**Deliberately a NEW FILE rather than a rewrite of `model.py`.** Replacing that module wholesale
is what broke `ppg` mid-rebuild: its `algo.py` imported symbols that vanished, and the tree was
red across several steps. Landing the faithful encoder beside the existing one keeps every step
green and lets the integration be its own scoped edit — "big actions leak like abstractions"
applies to a refactor as much as to a class hierarchy.

## Why nothing here could be assumed from the two baselines rebuilt before it

Three consecutive IMPALA-family encoders, three different answers:

| | flatten width | conv padding | init |
|---|---|---|---|
| `ibac_sni` base | hardcoded `32*8*8` | `nn.Conv2d(padding=1)` | `xavier_uniform_` everywhere |
| `ppg` base | **derived** (`(h+1)//2` per stack) | `nn.Conv2d(padding=1)` | **normalized fan-in**, per-stack scales |
| `idaac` base | hardcoded `2048` | **`Conv2d_tf`, TF SAME** | `orthogonal_` linears + `xavier_uniform_` convs |

The T1 blind spot recorded in `STEP-ZERO.md` matters here specifically: a weight transplant
overwrites initialisation and cannot see the third column being wrong, so this file is paired with
an init-parity check, not only a forward check.

## Edits

**E1 — the flatten width is derived instead of hardcoded.** `model.py:145` is
`nn.Linear(2048, hidden_size)`, i.e. `32*8*8`, correct only for Procgen's 64x64. Each
`_make_layer` applies one `MaxPool2d(3, 2, 1)` after a stride-1 SAME conv, so at 84x84 the stack
gives 84 -> 42 -> 21 -> 11 and the width is `32*11*11 = 3872`. `_flat_dim` computes it and
**provably reduces to the reference's constant at 64**, asserted at import.

**E2 — uint8 input is scaled here.** The reference's `forward` does no scaling; its env stack
delivers floats. This project's harness passes uint8 NCHW, so the `/255` lives here. Same seam as
`ibac_sni`'s E2 and the opposite of `ppg`'s base, which already divided internally.

`Conv2d_tf` is carried verbatim, asymmetric pad included — **but its asymmetric branch is dead in
this architecture, and an earlier version of this docstring claimed the opposite.** Found by
red-green: substituting a plain `nn.Conv2d(padding=1)` for it left the T1 transplant **green** at
both 64x64 and 84x84. The reason is arithmetic, not luck — every conv here is `kernel_size=3,
stride=1`, so `total_padding = (out-1)*stride + 3 - in` with `out == in` is always exactly 2, an
even number, and the one-sided `F.pad` never fires. `Conv2d_tf` is equivalent to symmetric
`padding=1` for this network at every input size.

It is still carried, for two reasons that are worth separating from the false one: the null is the
base implementation and dropping it would need an argument rather than an absence of one; and the
equivalence is a property of *these* hyperparameters, so a later stride or kernel change would
silently break a substitution that looks safe today. What is *not* claimed any more is that it
currently makes a numerical difference. Carried with the reference's own wart: `BasicBlock` passes `padding=(1, 1)`, a tuple that can only ever fail the
`== "VALID"` test, so the value is ignored and SAME is computed regardless — reproduced because
reproducing it costs nothing and diverging from it would need an argument.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


def init(module, weight_init, bias_init, gain=1):
    """`_upstream_2fe3020/utils.py:4-7`, verbatim."""
    weight_init(module.weight.data, gain=gain)
    bias_init(module.bias.data)
    return module


init_ = lambda m: init(m, nn.init.orthogonal_, lambda x: nn.init.constant_(x, 0))
init_relu_ = lambda m: init(m, nn.init.orthogonal_, lambda x: nn.init.constant_(x, 0),
                            nn.init.calculate_gain('relu'))


def apply_init_(modules):
    """`model.py:18-31`, verbatim. Touches only Conv2d/BatchNorm/GroupNorm — so calling it after
    the Linears are built leaves their orthogonal init intact, which is what the reference does."""
    for m in modules:
        if isinstance(m, nn.Conv2d):
            nn.init.xavier_uniform_(m.weight)
            if m.bias is not None:
                nn.init.constant_(m.bias, 0)
        elif isinstance(m, (nn.BatchNorm2d, nn.GroupNorm)):
            nn.init.constant_(m.weight, 1)
            if m.bias is not None:
                nn.init.constant_(m.bias, 0)


class Flatten(nn.Module):
    def forward(self, x):
        return x.reshape(x.size(0), -1)


class Conv2d_tf(nn.Conv2d):
    """`model.py:41-85`, verbatim — Conv2d with TensorFlow's SAME padding.

    The one-sided `F.pad` when the total padding is odd is the part a hand-rolled equivalent gets
    wrong: PyTorch's symmetric `padding=` cannot express it.
    """

    def __init__(self, *args, **kwargs):
        super(Conv2d_tf, self).__init__(*args, **kwargs)
        self.padding = kwargs.get("padding", "SAME")

    def _compute_padding(self, input, dim):
        input_size = input.size(dim + 2)
        filter_size = self.weight.size(dim + 2)
        effective_filter_size = (filter_size - 1) * self.dilation[dim] + 1
        out_size = (input_size + self.stride[dim] - 1) // self.stride[dim]
        total_padding = max(
            0, (out_size - 1) * self.stride[dim] + effective_filter_size - input_size
        )
        additional_padding = int(total_padding % 2 != 0)
        return additional_padding, total_padding

    def forward(self, input):
        if self.padding == "VALID":
            return F.conv2d(input, self.weight, self.bias, self.stride,
                            padding=0, dilation=self.dilation, groups=self.groups)
        rows_odd, padding_rows = self._compute_padding(input, dim=0)
        cols_odd, padding_cols = self._compute_padding(input, dim=1)
        if rows_odd or cols_odd:
            input = F.pad(input, [0, cols_odd, 0, rows_odd])
        return F.conv2d(input, self.weight, self.bias, self.stride,
                        padding=(padding_rows // 2, padding_cols // 2),
                        dilation=self.dilation, groups=self.groups)


class BasicBlock(nn.Module):
    """`model.py:101-127`, verbatim. Note `relu` BEFORE the first conv, and `+= identity`."""

    def __init__(self, n_channels, stride=1):
        super(BasicBlock, self).__init__()
        self.conv1 = Conv2d_tf(n_channels, n_channels, kernel_size=3, stride=1, padding=(1, 1))
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = Conv2d_tf(n_channels, n_channels, kernel_size=3, stride=1, padding=(1, 1))
        self.stride = stride
        apply_init_(self.modules())
        self.train()

    def forward(self, x):
        identity = x
        out = self.relu(x)
        out = self.conv1(out)
        out = self.relu(out)
        out = self.conv2(out)
        out += identity
        return out


def _flat_dim(image_size, channels=(16, 32, 32)):
    """[E1] The formula behind the reference's hardcoded `2048`.

    One `MaxPool2d(kernel_size=3, stride=2, padding=1)` per `_make_layer`; the conv before it is
    stride 1 with SAME padding and does not change the spatial size.

        64 -> 32 -> 16 -> 8   =>  32 *  8 *  8 = 2048   (the reference's own constant)
        84 -> 42 -> 21 -> 11  =>  32 * 11 * 11 = 3872   (this project's target)
    """
    h = image_size
    for _ in channels:
        h = (h + 2 * 1 - 3) // 2 + 1
    return channels[-1] * h * h


assert _flat_dim(64) == 2048, "E1 must reduce to the reference's own constant at 64x64"


class NNBase(nn.Module):
    """`model.py:87-99`, verbatim.

    Carried rather than inlined. The three encoders above previously each grew their own
    `_hidden_size` + `output_size` property instead — an intra-module union of the same kind as
    the `ValueResNet(ResNetBase)` mistake, one layer up, and made for the same reason: it looked
    like avoidable duplication.
    """

    def __init__(self, hidden_size):
        super(NNBase, self).__init__()
        self._hidden_size = hidden_size



def _build_trunk(module, num_inputs, hidden_size, channels, image_size):
    """The stacks + fc that all three of the reference's encoders happen to build identically.

    **A function, deliberately, not a base class.** `ValueResNet` was first written as
    `class ValueResNet(ResNetBase)` because their `__init__`s are identical — and it silently
    inherited `ResNetBase.forward`, which returns `(value, features)` where the reference's
    `ValueResNet` returns the value alone (`model.py:265`). The union was built on having read
    `__init__` and inferred the rest.

    The reference keeps these three as **siblings**, and so do we. `porting-directive.md` §1's
    "disjoint is the null, sharing is earned" is not only a rule about sharing between baselines;
    it applies inside a module, where the twenty lines saved are worth less than the one
    behaviour that can leak in unnoticed. A helper shares exactly what is passed to it and can
    import nothing else.
    """
    module.layer1 = _make_layer(num_inputs, channels[0])
    module.layer2 = _make_layer(channels[0], channels[1])
    module.layer3 = _make_layer(channels[1], channels[2])
    module.flatten = Flatten()
    module.relu = nn.ReLU()
    module.fc = init_relu_(nn.Linear(_flat_dim(image_size, tuple(channels)), hidden_size))


def _make_layer(in_channels, out_channels, stride=1):
    """`model.py:150-159` / `:195-204` / `:243-252` — identical in all three reference classes."""
    return nn.Sequential(
        Conv2d_tf(in_channels, out_channels, kernel_size=3, stride=1),
        nn.MaxPool2d(kernel_size=3, stride=2, padding=1),
        BasicBlock(out_channels),
        BasicBlock(out_channels),
    )


def _trunk_forward(module, x):
    """The stacks + fc pass, identical in all three (`model.py:161-171`, `:206-213`, `:255-263`)."""
    if x.dtype == torch.uint8:                     # [E2]
        x = x.float() / 255.0
    x = module.layer1(x)
    x = module.layer2(x)
    x = module.layer3(x)
    x = module.relu(module.flatten(x))
    return module.relu(module.fc(x))


class ResNetBase(NNBase):
    """`model.py:129-171`, with edits E1 and E2. Returns `(value, features)`.

    Module names match the reference (`layer1.0`, `layer1.2.conv1`, `fc`, `critic_linear`) so a
    `state_dict` transplants with no remapping — which is what makes the parity test a real T1.
    """

    def __init__(self, num_inputs, hidden_size=256, channels=(16, 32, 32), image_size=64):
        super().__init__(hidden_size)          # NNBase, as the reference has it
        _build_trunk(self, num_inputs, hidden_size, channels, image_size)
        self.critic_linear = init_(nn.Linear(hidden_size, 1))
        apply_init_(self.modules())
        self.train()


    def forward(self, inputs):
        x = _trunk_forward(self, inputs)
        return self.critic_linear(x), x            # (value, features) -- model.py:171


class ValueResNet(NNBase):
    """`model.py:224-265`. A SIBLING of `ResNetBase`, not a subclass.

    Same trunk and the same `critic_linear = init_(nn.Linear(hidden, 1))` — but **`forward`
    returns the value alone** (`model.py:265`), where `ResNetBase` returns a two-tuple.

    This class was first written as `class ValueResNet(ResNetBase)` precisely because the two
    `__init__`s are identical. It inherited the wrong `forward`, and the docstring asserted the
    two were "structurally identical … same forward" — a claim built on having read `__init__`
    and inferred the rest. `porting-directive.md` §1's "disjoint is the null" turns out to apply
    *inside* a module as much as between baselines: twenty saved lines are worth less than one
    behaviour that leaks in unnoticed.
    """

    def __init__(self, num_inputs, hidden_size=256, channels=(16, 32, 32), image_size=64):
        super().__init__(hidden_size)          # NNBase, as the reference has it
        _build_trunk(self, num_inputs, hidden_size, channels, image_size)
        self.critic_linear = init_(nn.Linear(hidden_size, 1))
        apply_init_(self.modules())
        self.train()


    def forward(self, inputs):
        return self.critic_linear(_trunk_forward(self, inputs))    # value ONLY -- model.py:265


class PolicyResNetBase(NNBase):
    """`model.py:173-222` — IDAAC's advantage head, and the one genuinely new mechanism here.

    Same trunk, but `critic_linear` is `Linear(hidden_size + act_dim, 1)` and `forward`
    **concatenates the action** before it. That is what makes it `A(s, a)` rather than `V(s)`;
    the encoder-decoupling IDAAC is named for depends on it.

    **Continuous adaptation, `porting-directive.md` §4, NOT INTRINSIC.** The reference builds
    `F.one_hot(actions.squeeze(1), num_actions)` (`model.py:217`), meaningless for a 7-D
    continuous action. The mechanism's requirement is *some fixed-size vector representation of
    the action to concatenate* — one-hot is Procgen's way of supplying that, not something the
    concat depends on — so the raw action vector is fed directly and `num_actions` becomes
    `act_dim`. Same branch point already decided for `ctrl`'s `action_mlp` (`docs/REGISTER.md`,
    2026-08-14), decided the same way so that a wrong choice is wrong *uniformly* across both
    baselines rather than selectively in one (`docs/STEP-ZERO.md` gate 3).

    Also a sibling rather than a subclass, for the reason `ValueResNet` records: it currently
    overrides both methods, so nothing leaks *today* — and "nothing leaks today" is the golden
    path, not a guarantee.

    `actions=None` keeps the reference's zero-vector fallback (`model.py:214-215`).
    """

    def __init__(self, num_inputs, hidden_size=256, channels=(16, 32, 32), image_size=64,
                 act_dim=7):
        super().__init__(hidden_size)          # NNBase, as the reference has it
        self.act_dim = act_dim
        _build_trunk(self, num_inputs, hidden_size, channels, image_size)
        # [ADAPTATION] reference: Linear(hidden_size + num_actions, 1), num_actions discrete
        self.critic_linear = init_(nn.Linear(hidden_size + act_dim, 1))
        apply_init_(self.modules())
        self.train()


    def forward(self, inputs, actions=None):
        x = _trunk_forward(self, inputs)
        if actions is None:
            act_vec = torch.zeros(x.shape[0], self.act_dim, device=x.device, dtype=x.dtype)
        else:
            # [ADAPTATION] reference: F.one_hot(actions.squeeze(1), self.num_actions).float()
            act_vec = actions.reshape(x.shape[0], -1).to(dtype=x.dtype)
        return self.critic_linear(torch.cat((x, act_vec), dim=1)), x


# ---------------------------------------------------------------------------------------------
# Order classifiers — copied verbatim, having first been re-derived by hand for no reason
# ---------------------------------------------------------------------------------------------
# `rlgen/algos/idaac/model.py::OrderDiscriminator` is hand-written, and its docstring correctly
# DESCRIBES `LinearOrderClassifier` — the reference's default — while the reference itself sits
# ten lines away in a file this project had already vendored. That is a re-derivation from prose
# where a copy was available, which is the exact failure the base-first practice exists to
# prevent, committed inside a base-first rebuild.
#
# The cause was an unexamined filter: "port what the module needs" rather than "port the file,
# then justify each removal". Every application of that filter is an authored decision, and it
# was being made silently and by default — backwards from "disjoint is the null, everything else
# is burden of proof". Copying costs nothing; the original runs.


class LinearOrderClassifier(nn.Module):
    """`model.py:269-281`, verbatim. **IDAAC's default order classifier** — reached because
    `--use_nonlinear_clf` defaults to False (`arguments.py:142-145`).

    A single `Linear(2*emb, 2)` with a `Softmax`, no hidden layer. Note it emits
    PROBABILITIES, not logits: a loss expecting logits would be wrong against this.
    """

    def __init__(self, emb_size=256):
        super(LinearOrderClassifier, self).__init__()
        self.main = nn.Sequential(
            Flatten(),
            init_(nn.Linear(2 * emb_size, 2)),
            nn.Softmax(dim=1),
        )
        self.train()

    def forward(self, emb):
        x = self.main(emb)
        return x


class NonlinearOrderClassifier(nn.Module):
    """`model.py:284-297`, verbatim. The opt-in variant; `hidden_size` defaults to **4**, which
    is small enough that generosity here is a real divergence rather than a harmless one."""

    def __init__(self, emb_size=256, hidden_size=4):
        super(NonlinearOrderClassifier, self).__init__()
        self.main = nn.Sequential(
            Flatten(),
            init_relu_(nn.Linear(2 * emb_size, hidden_size)), nn.ReLU(),
            init_(nn.Linear(hidden_size, 2)),
            nn.Softmax(dim=1),
        )
        self.train()

    def forward(self, emb):
        x = self.main(emb)
        return x
