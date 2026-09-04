"""IBAC-SNI's feature extractor — a copy of its base's `common/model.py`, plus two scoped edits.

**Base term** (`docs/STEP-ZERO.md` gate 1): `joonleesky/train-procgen-pytorch` @ `1678e4a`,
`common/model.py`, vendored verbatim at `_upstream_1678e4a/common_model.py`. This file started as
a byte-copy of that. Run `diff _upstream_1678e4a/common_model.py model.py` and every edit below is
the whole of what changed — the minimality claim is mechanical, not prose.

**Edit E1 — `ImpalaModel` accepts a non-64 input size.** The base hardcodes
`nn.Linear(in_features=32 * 8 * 8, ...)` (`common/model.py:102`), correct only for Procgen's
64x64. This project's target is 84x84 (`docs/STEP-ZERO.md`, situation block). `_impala_flat_dim`
replaces the constant with the formula that produced it, and **provably reduces to it**:
`_impala_flat_dim(64) == 32 * 8 * 8`, asserted at import and pinned by
`tests/test_ibac_sni_base_parity.py`. A `porting-directive.md` §4 adaptation forced by the target,
not a design choice.

**Edit E2 — `ImpalaModel.forward` takes uint8 and scales.** The base's model receives already-
scaled float input because its env stack ends in `ScaledFloatFrame`
(`common/env/procgen_wrappers.py:365-377`, `obs/255.0`) and `TransposeFrame` (`:350-362`,
NHWC->NCHW). This project's harness (`rlgen/envs.py`) delivers uint8 NCHW instead, so the two
wrappers' arithmetic has to live somewhere; it lives here. Same total computation, different
seam — `porting-directive.md` §4.

**Nothing else is touched.** `MlpModel`, `NatureModel` and `GRU` are carried over unused rather
than deleted: keeping them is zero edits, and deleting them would be an edit needing its own
justification. Only `ImpalaModel` is instantiated (the base's own `config.yml` sets
`architecture: impala` for every Procgen entry, and DZ's two IBAC blocks keep it).

**Init, stated precisely because this module's previous version got it wrong.** The base applies
`xavier_uniform_init` to `ImpalaModel` *in its entirety* (`common/model.py:105`) — which includes
`self.fc`, since `nn.Module.apply` recurses. The discarded construction initialised that `fc`
orthogonally with `gain=sqrt(2)`, and its docstring described the base as using "xavier_uniform_
conv init and orthogonal_(gain=sqrt(2)) linear init". The base uses `orthogonal_init` only in
`CategoricalPolicy`'s two heads and in `GRU` (`common/policy.py:19-20,29`), never in the encoder.
Carrying the base's `apply(xavier_uniform_init)` verbatim keeps that correct by construction.
"""

from .misc_util import orthogonal_init, xavier_uniform_init
import torch.nn as nn
import torch


class Flatten(nn.Module):
    def forward(self, x):
        return x.view(x.size(0), -1)


class MlpModel(nn.Module):
    def __init__(self,
                 input_dims=4,
                 hidden_dims=[64, 64],
                 **kwargs):
        """
        input_dim:     (int)  number of the input dimensions
        hidden_dims:   (list) list of the dimensions for the hidden layers
        use_batchnorm: (bool) whether to use batchnorm
        """
        super(MlpModel, self).__init__()

        # Hidden layers
        hidden_dims = [input_dims] + hidden_dims
        layers = []
        for i in range(len(hidden_dims) - 1):
            in_features = hidden_dims[i]
            out_features = hidden_dims[i + 1]
            layers.append(nn.Linear(in_features, out_features))
            layers.append(nn.ReLU())
        self.layers = nn.Sequential(*layers)
        self.output_dim = hidden_dims[-1]
        self.apply(orthogonal_init)

    def forward(self, x):
        for layer in self.layers:
            x = layer(x)
        return x


class NatureModel(nn.Module):
    def __init__(self,
                 in_channels,
                 **kwargs):
        """
        input_shape:  (tuple) tuple of the input dimension shape (channel, height, width)
        filters:       (list) list of the tuples consists of (number of channels, kernel size, and strides)
        use_batchnorm: (bool) whether to use batchnorm
        """
        super(NatureModel, self).__init__()
        self.layers = nn.Sequential(
            nn.Conv2d(in_channels=in_channels, out_channels=32, kernel_size=8, stride=4), nn.ReLU(),
            nn.Conv2d(in_channels=32, out_channels=64, kernel_size=4, stride=2), nn.ReLU(),
            nn.Conv2d(in_channels=64, out_channels=64, kernel_size=3, stride=1), nn.ReLU(),
            Flatten(),
            nn.Linear(in_features=64*7*7, out_features=512), nn.ReLU()
        )
        self.output_dim = 512
        self.apply(orthogonal_init)

    def forward(self, x):
        x = self.layers(x)
        return x


class ResidualBlock(nn.Module):
    def __init__(self,
                 in_channels):
        super(ResidualBlock, self).__init__()
        self.conv1 = nn.Conv2d(in_channels=in_channels, out_channels=in_channels, kernel_size=3, stride=1, padding=1)
        self.conv2 = nn.Conv2d(in_channels=in_channels, out_channels=in_channels, kernel_size=3, stride=1, padding=1)

    def forward(self, x):
        out = nn.ReLU()(x)
        out = self.conv1(out)
        out = nn.ReLU()(out)
        out = self.conv2(out)
        return out + x

class ImpalaBlock(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(ImpalaBlock, self).__init__()
        self.conv = nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=3, stride=1, padding=1)
        self.res1 = ResidualBlock(out_channels)
        self.res2 = ResidualBlock(out_channels)

    def forward(self, x):
        x = self.conv(x)
        x = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)(x)
        x = self.res1(x)
        x = self.res2(x)
        return x


def _impala_flat_dim(image_size):
    """[EDIT E1] The formula behind the base's hardcoded `32 * 8 * 8`.

    Each of the three `ImpalaBlock`s applies exactly one `MaxPool2d(kernel_size=3, stride=2,
    padding=1)` (`ImpalaBlock.forward` above); its `conv` is `stride=1, padding=1`, so it does not
    change the spatial size. PyTorch's pooling output size is
    `floor((H + 2*padding - kernel) / stride) + 1`.

        64 -> 32 -> 16 -> 8   =>  32 *  8 *  8 = 2048   (the base's own constant, reproduced)
        84 -> 42 -> 21 -> 11  =>  32 * 11 * 11 = 3872   (this project's target)

    The `assert` is the point of the function, not decoration: it makes the "this edit does not
    change the base at the base's own input size" claim mechanical.
    """
    h = image_size
    for _ in range(3):
        h = (h + 2 * 1 - 3) // 2 + 1
    return 32 * h * h


assert _impala_flat_dim(64) == 32 * 8 * 8, "E1 must reduce to the base's own constant at 64x64"


class ImpalaModel(nn.Module):
    def __init__(self,
                 in_channels,
                 image_size=64,          # [EDIT E1] added; default is the base's own Procgen size
                 **kwargs):
        super(ImpalaModel, self).__init__()
        self.block1 = ImpalaBlock(in_channels=in_channels, out_channels=16)
        self.block2 = ImpalaBlock(in_channels=16, out_channels=32)
        self.block3 = ImpalaBlock(in_channels=32, out_channels=32)
        # [EDIT E1] was: nn.Linear(in_features=32 * 8 * 8, out_features=256)
        self.fc = nn.Linear(in_features=_impala_flat_dim(image_size), out_features=256)

        self.output_dim = 256
        self.apply(xavier_uniform_init)

    def forward(self, x):
        # [EDIT E2] The base's env stack scaled and transposed before the model saw the tensor
        # (`procgen_wrappers.py:350-377`). This project's harness hands over uint8 NCHW, so the
        # scaling happens here. `.float() / 255.0` is not in-place: the caller's rollout buffer
        # holds the same uint8 tensor and must not be mutated.
        if x.dtype == torch.uint8:
            x = x.float() / 255.0
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        x = nn.ReLU()(x)
        x = Flatten()(x)
        x = self.fc(x)
        x = nn.ReLU()(x)
        return x


class GRU(nn.Module):
    def __init__(self, input_size, hidden_size):
        super(GRU, self).__init__()
        self.gru = orthogonal_init(nn.GRU(input_size, hidden_size), gain=1.0)

    def forward(self, x, hxs, masks):
        # Prediction
        if x.size(0) == hxs.size(0):
            # input for GRU-CELL: (L=sequence_length, N, H)
            # output for GRU-CELL: (output: (L, N, H), hidden: (L, N, H))
            masks = masks.unsqueeze(-1)
            x, hxs = self.gru(x.unsqueeze(0), (hxs * masks).unsqueeze(0))
            x = x.squeeze(0)
            hxs = hxs.squeeze(0)
        # Training
        # We will recompute the hidden state to allow gradient to be back-propagated through time
        else:
            # x is a (T, N, -1) tensor that has been flatten to (T * N, -1)
            N = hxs.size(0)
            T = int(x.size(0) / N)

            # unflatten
            x = x.view(T, N, x.size(1))

            # Same deal with masks
            masks = masks.view(T, N)

            # Let's figure out which steps in the sequence have a zero for any agent
            # We will always assume t=0 has a zero in it as that makes the logic cleaner
            # (can be interpreted as a truncated back-propagation through time)
            has_zeros = ((masks[1:] == 0.0) \
                            .any(dim=-1)
                            .nonzero()
                            .squeeze()
                            .cpu())

            # +1 to correct the masks[1:]
            if has_zeros.dim() == 0:
                # Deal with scalar
                has_zeros = [has_zeros.item() + 1]
            else:
                has_zeros = (has_zeros + 1).numpy().tolist()

            # add t=0 and t=T to the list
            has_zeros = [0] + has_zeros + [T]

            hxs = hxs.unsqueeze(0)
            outputs = []
            for i in range(len(has_zeros) - 1):
                # We can now process steps that don't have any zeros in masks together!
                # This is much faster
                start_idx = has_zeros[i]
                end_idx = has_zeros[i + 1]

                rnn_scores, hxs = self.gru(
                    x[start_idx:end_idx],
                    hxs * masks[start_idx].view(1, -1, 1))

                outputs.append(rnn_scores)

            # assert len(outputs) == T
            # x is a (T, N, -1) tensor
            x = torch.cat(outputs, dim=0)
            # flatten
            x = x.view(T * N, -1)
            hxs = hxs.squeeze(0)

        return x, hxs
