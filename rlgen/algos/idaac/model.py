"""Networks. IDAAC's architecture, re-derived for 84x84x9 continuous-control input.

Encoder: the IMPALA ResNet of Espeholt et al., which the IDAAC paper states was used for all
Procgen results. Channels [16,32,32]; each stage is conv3x3 -> maxpool(3,2,1) -> 2 residual
blocks. The flatten width is NOT portable (FINDINGS R1):
    64x64 -> 8x8  -> 32*8*8  = 2048   (what IDAAC hardcodes)
    84x84 -> 11x11 -> 32*11*11 = 3872 (ours)
so it is computed with a dummy forward and then asserted, which makes a silent shape drift
impossible rather than merely unlikely.

The policy network has two heads (action distribution, generalized advantage). The value
function lives in a SEPARATE network with its own encoder -- that decoupling is the whole of
DAAC. For algo="ppo" we use one shared network with a value head instead, so the PPO baseline
is real PPO and not the paper's DVAC ablation.
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


def _init(m: nn.Linear, gain: float = np.sqrt(2)) -> nn.Linear:
    """[IK utils.py] orthogonal weights, zero bias."""
    nn.init.orthogonal_(m.weight, gain)
    nn.init.constant_(m.bias, 0)
    return m


class _ResBlock(nn.Module):
    def __init__(self, c: int):
        super().__init__()
        self.c1 = nn.Conv2d(c, c, 3, 1, 1)
        self.c2 = nn.Conv2d(c, c, 3, 1, 1)

    def forward(self, x):
        y = self.c1(F.relu(x))
        y = self.c2(F.relu(y))
        return x + y


class ImpalaEncoder(nn.Module):
    def __init__(self, in_ch: int, out_dim: int = 256, image_size: int = 84):
        super().__init__()
        layers, c = [], in_ch
        for out_c in (16, 32, 32):
            layers += [nn.Conv2d(c, out_c, 3, 1, 1), nn.MaxPool2d(3, 2, 1),
                       _ResBlock(out_c), _ResBlock(out_c)]
            c = out_c
        self.conv = nn.Sequential(*layers)
        # IDAAC's apply_init_ (model.py:18-31) puts xavier_uniform on EVERY Conv2d with zero
        # bias. Leaving PyTorch's default (kaiming_uniform with a=sqrt(5), a legacy choice) is
        # not a neutral difference: measured on this encoder it changes conv weight std 1.70x,
        # conv output std 4.48x, encoder feature std **7.05x** and the gradient norm **37.8x**.
        # The features are what the policy, advantage and order-discriminator heads all consume,
        # so their scale is load-bearing. FINDINGS R21.
        for m in self.conv.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
        with torch.no_grad():
            flat = self.conv(torch.zeros(1, in_ch, image_size, image_size)).numel()
        # FINDINGS R1 -- known answers, so a refactor cannot silently change the width.
        if image_size == 84:
            assert flat == 3872, f"84x84 IMPALA flatten must be 3872, got {flat}"
        if image_size == 64:
            assert flat == 2048, f"64x64 IMPALA flatten must be 2048, got {flat}"
        self.fc = _init(nn.Linear(flat, out_dim))
        self.out_dim = out_dim
        self.flat_dim = flat

    def forward(self, obs_uint8: torch.Tensor) -> torch.Tensor:
        # RUNBOOK detector D5: the buffer is uint8 and scaling happens here, exactly once.
        assert obs_uint8.dtype == torch.uint8, f"encoder expects uint8, got {obs_uint8.dtype}"
        x = obs_uint8.float().div_(255.0)
        return F.relu(self.fc(F.relu(self.conv(x)).flatten(1)))


class DiagGaussianHead(nn.Module):
    """[IK distributions.py DiagGaussian] with two deliberate, marked deviations.

    Upstream inits fc_mean at the default gain and sets logstd = AddBias(zeros), i.e.
    sigma = 1.0, state-independent, unsquashed. On Procgen that head is never exercised
    (Discrete -> Categorical, which upstream inits at gain 0.01 precisely so the initial
    policy is near-uniform). Robosuite actions live in [-1,1], so gain 1 + sigma 1 puts most
    initial samples outside the box: the env clips them while the log-prob is computed on the
    unclipped action, and under OSC_POSE it also means violent initial end-effector motion.

    We keep the standard clip-outside / log-prob-inside treatment (SB3, CleanRL and upstream
    all do this) but shrink the initial distribution so the mismatch is small at init rather
    than total. FINDINGS R2.
    """

    def __init__(self, in_dim: int, act_dim: int, init_log_std: float = -1.0,
                 mean_gain: float = 0.01):
        super().__init__()
        self.mean = _init(nn.Linear(in_dim, act_dim), gain=mean_gain)
        self.log_std = nn.Parameter(torch.full((act_dim,), float(init_log_std)))

    def forward(self, feat) -> torch.distributions.Normal:
        return torch.distributions.Normal(self.mean(feat), self.log_std.exp())


def logp(dist, a):
    """Matches FixedNormal.log_probs: sum over action dims, keep a trailing 1."""
    return dist.log_prob(a).sum(-1, keepdim=True)


def entropy(dist):
    """Matches FixedNormal.entropy: SUM over action dims. FINDINGS R3 -- this is why the
    Procgen entropy coefficient is wrong here: for a 7-D Gaussian it is unbounded above."""
    return dist.entropy().sum(-1)


class PolicyNet(nn.Module):
    """head="adv" -> the DAAC/IDAAC policy net. head="value" -> the shared-net PPO baseline."""

    def __init__(self, obs_shape, act_dim: int, hidden: int = 256,
                 init_log_std: float = -1.0, mean_gain: float = 0.01, head: str = "adv"):
        super().__init__()
        assert head in ("adv", "value")
        self.head_kind = head
        self.encoder = ImpalaEncoder(obs_shape[0], hidden, obs_shape[1])
        self.dist_head = DiagGaussianHead(hidden, act_dim, init_log_std, mean_gain)
        if head == "adv":
            # A(s,a) is conditioned on the action. Procgen concatenates a one-hot; for
            # continuous control we concatenate the raw 7-D action, already on a [-1,1] scale.
            self.aux = nn.Sequential(_init(nn.Linear(hidden + act_dim, hidden)), nn.ReLU(),
                                     _init(nn.Linear(hidden, 1), gain=1.0))
        else:
            self.aux = _init(nn.Linear(hidden, 1), gain=1.0)

    def encode(self, obs):
        return self.encoder(obs)

    def act(self, obs, deterministic: bool = False):
        f = self.encode(obs)
        d = self.dist_head(f)
        a = d.mean if deterministic else d.sample()      # FixedNormal.mode() == mean
        return a, logp(d, a)

    def evaluate(self, obs, actions):
        f = self.encode(obs)
        d = self.dist_head(f)
        return logp(d, actions), entropy(d), f

    def advantage(self, feat, actions):
        assert self.head_kind == "adv"
        return self.aux(torch.cat([feat, actions], dim=-1))

    def value_from_feat(self, feat):
        assert self.head_kind == "value"
        return self.aux(feat)

    def value(self, obs):
        return self.value_from_feat(self.encode(obs))


class ValueNet(nn.Module):
    def __init__(self, obs_shape, hidden: int = 256):
        super().__init__()
        self.encoder = ImpalaEncoder(obs_shape[0], hidden, obs_shape[1])
        self.head = _init(nn.Linear(hidden, 1), gain=1.0)

    def forward(self, obs):
        return self.head(self.encoder(obs))


class OrderDiscriminator(nn.Module):
    """D_psi(f_i, f_j) -> logit of P(s_i came before s_j). IDAAC section 4.3.

    Capacity matters here, and it is easy to get wrong by being generous. IDAAC's DEFAULT is
    `LinearOrderClassifier`: `Linear(2*emb, 2) -> Softmax`, a **single linear layer with no
    hidden layer at all** (`train.py:80`, reached because `--use_nonlinear_clf` defaults to
    False, `arguments.py:142-145`). Its opt-in nonlinear variant uses `clf_hidden_size`, whose
    default is **4** (`arguments.py:152-155`).

    This class previously used `Linear(2*emb, 256) -> ReLU -> Linear(256, 1)` -- 64x the hidden
    width of even the opt-in variant, plus a nonlinearity the default does not have. A stronger
    adversary is not a neutral choice: the encoder is supposed to be able to *confuse* this
    network, so extra capacity makes IDAAC's mechanism weaker, not its evaluation stricter. It is
    consistent with the `disc/acc ~ 0.64` we measured, where the paper's game should sit nearer
    chance (FINDINGS R21).

    `disc_hidden = 0` reproduces IDAAC's default (linear); `> 0` gives the nonlinear variant at
    that width. One logit with BCEWithLogits rather than two with Softmax: for binary
    classification the two-logit softmax carries one redundant degree of freedom, so this is the
    canonical reduction of the same model, and it is numerically stabler.
    """

    def __init__(self, hidden: int = 256, disc_hidden: int = 0):
        super().__init__()
        if disc_hidden and disc_hidden > 0:
            self.net = nn.Sequential(_init(nn.Linear(2 * hidden, disc_hidden)), nn.ReLU(),
                                     _init(nn.Linear(disc_hidden, 1), gain=1.0))
        else:
            self.net = nn.Sequential(_init(nn.Linear(2 * hidden, 1), gain=1.0))

    def forward(self, fi, fj):
        return self.net(torch.cat([fi, fj], dim=-1))


def encoder_confusion_loss(logit: torch.Tensor) -> torch.Tensor:
    """L_E, eq. 3: -1/2 log D - 1/2 log(1-D), minimised at D=0.5 with value log 2.

    Written with softplus for numerical stability. Note that eq. 2 -- the *discriminator*
    loss -- is misprinted in the paper (FINDINGS B5): both cross-entropy terms sit on the same
    ordered pair, which makes it identical to this up to a factor of 2 and unable to train a
    classifier. The surrounding text says what was meant, and algo.py implements that.
    """
    return (0.5 * F.softplus(-logit) + 0.5 * F.softplus(logit)).mean()
