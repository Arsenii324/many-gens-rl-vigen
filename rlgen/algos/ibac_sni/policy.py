"""IBAC-SNI's policy — the base's `common/policy.py` with the bottleneck the authors actually wrote.

**Base term**: `joonleesky/train-procgen-pytorch` @ `1678e4a`, `common/policy.py`, vendored at
`_upstream_1678e4a/common_policy.py`. `CategoricalPolicy`'s skeleton (embedder -> heads,
`orthogonal_init` gains, `is_recurrent`) is carried over; the discrete head is replaced and a
bottleneck inserted.

**Semantic authority is `ext/IBAC-SNI` (`microsoft/IBAC-SNI` @ `6b3a58b`), NOT DZ's port.** DZ's
`common/policy_ibac.py` is a re-derivation from the paper (`_upstream_1678e4a/PROVENANCE.md`); the
authors released their own code, so it is used for wiring only. Every number below was read out of
the reference directly, and the four marked **[verified here]** were re-read by hand rather than
taken from a subagent's report.

## What the reference does, and what this file therefore does

| Point | Reference | Citation |
|---|---|---|
| sigma | `softplus(rho - 5.0)` — a **-5.0 offset**, so std starts ~0.0067 (near-deterministic) | `coinrun/coinrun/policies.py:57-58` **[verified here]** |
| mu, rho | **one** `dense(out, 256*2)` split in half, not two layers | `policies.py:56-57` **[verified here]** |
| post-bottleneck | `relu` applied to **both** the sample and the mean | `policies.py:104-105` **[verified here]** |
| KL | analytic `KL(N(mu,sigma) || N(0,1))`, `reduce_sum(reduce_mean(., 0)) / log(2)` — **in bits** | `policies.py:61-64` **[verified here]** |
| KL vs. SNI | computed once from the encoding distribution; **independent of the train/run split** | `policies.py:61-67` |
| value head under SNI | `self.vf_run = self.vf_train = fc(h_vf, 'v', 1)` — **fully deterministic, both heads**, with the authors' own comment *"Use deterministic value function for both as VIB for regression seems like a bad idea"* | `policies.py:160-161` **[verified here]** |
| run policy | `pdfromlatent(h_vf)` — deterministic, from the mean | `policies.py:164` |
| train policy | mixture over `NR_SAMPLES` draws | `policies.py:139-147` |

The authors' **own PyTorch** bottleneck (`torch_rl/bottleneck.py:29-45`) agrees on every
structural point — one `Linear(in, 2*out)`, `softplus`, analytic `kl_divergence` to `N(0,I)`,
`rsample`, per-dim KL summed at `torch_rl/model.py:192-193` — and differs only in lacking the
`-5.0` offset, the `/log(2)`, and the post-bottleneck ReLU. Where the two first-party paths
disagree this file follows **CoinRun**, because CoinRun is the path that produced the paper's
headline numbers and is a PPO+IMPALA-on-procedural-levels setting structurally identical to this
baseline's host. Recorded as a decision, not passed over: `docs/REGISTER.md`, 2026-08-16.

## Three places this contradicts the module that was discarded

1. **The value head was mixed.** The old construction computed
   `value = lambda*value_det + (1-lambda)*value_stoch`, and this project's `registry.py` note
   advertised that as a feature ("SNI mixes ... including the value estimate"). The reference does
   the opposite, deliberately and with a comment saying why.
2. **sigma was `exp(clamp(log_sigma, -10, 2))`.** Both first-party paths use `softplus`. At init
   the old form gives std = 1.0; the reference's gives std ~= 0.0067.
3. **`init_log_std` was -1.0.** The reference reaches a continuous head through
   `make_pdtype(ac_space)` (`policies.py:123`), i.e. baselines' `DiagGaussianPdType.pdfromlatent`,
   which is `logstd = tf.get_variable('pi/logstd', [1, size], initializer=tf.zeros_initializer())`
   — **state-independent, initialised to 0**, so std = 1.0. Fetched and read from
   `openai/baselines`'s published `baselines/common/distributions.py` (not on this disk), so this
   one is a **read citation, not a local-file citation**.

## The continuous adaptation — `porting-directive.md` §4, stated as a branch point

The reference's VIB head is `_matching_fc(h, 'pi', ac_space.n, ...)` (`policies.py:140`), which
uses `ac_space.n` and is therefore **discrete by construction**. No continuous IBAC-SNI exists
anywhere (`docs/ORIGINAL_LOCATIONS.md`). The adaptation is confined to swapping what the shared
policy head parameterises, exactly as `make_pdtype` would have: a `Categorical` over logits
becomes a diagonal `Normal(mean_head(z), exp(logstd))` with `logstd` a state-independent
parameter. Everything structural around it — one shared head fed by two different latents, the
mixture over samples, the 50/50 loss mix, the deterministic value head — is unchanged.

**`init_scale` is 1.0, not 0.01, and that is deliberate.** Under `Config.BETA >= 0` the head is
built by `_matching_fc(h, 'pi', ac_space.n, init_scale=1.0, init_bias=0)` (`policies.py:140`)
*before* the SNI branch's `pdfromlatent(h_vf, init_scale=0.01)` (`policies.py:164`); the enclosing
scope is `reuse=tf.AUTO_REUSE` (`policies.py:133`) and `train_model` is built first
(`ppo2.py:63`), so the variable already exists and the later `0.01` is silently ignored. The
non-VIB branch (`policies.py:151`) really does get 0.01. Whether the authors intended this or it
is an artefact of `AUTO_REUSE` cannot be told from the code; what the code *does* is not in doubt,
and fidelity to the reference decides it. Recorded in `docs/REGISTER.md` with both readings.
"""

from .misc_util import orthogonal_init, xavier_uniform_init
from .model import GRU
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Normal, Categorical, Independent, MixtureSameFamily, kl_divergence
import numpy as np


class Bottleneck(nn.Module):
    """q(z|h) = N(mu, softplus(rho + scale_offset)); returns (mu, rsample, KL-per-dim).

    Transcribed from the authors' own PyTorch `Bottleneck`
    (`ext/IBAC-SNI/torch_rl/bottleneck.py:20-45`), with `scale_offset` carrying CoinRun's
    `rho - 5.0` (`coinrun/coinrun/policies.py:58`) which the torch path lacks.

    `encode` is one `Linear(in, 2*out)` split in half — both first-party paths do this rather than
    two separate layers (`bottleneck.py:26`, `policies.py:56-57`).
    """

    def __init__(self, input_size, output_size, scale_offset=-5.0):
        super(Bottleneck, self).__init__()
        self.output_size = output_size
        self.scale_offset = scale_offset
        self.encode = nn.Linear(input_size, 2 * output_size)
        # `torch_rl/bottleneck.py:14-18,47-49` -- xavier_uniform with relu gain, zero bias. The
        # base's own `xavier_uniform_init` (`misc_util.py:26-30`) is gain=1.0, so the gain is
        # passed explicitly here rather than reusing the default.
        xavier_uniform_init(self.encode, gain=nn.init.calculate_gain('relu'))

    def stats(self, x):
        """(mu, std) from one `encode` call -- `policies.py:56-58`, `bottleneck.py:31-34`."""
        stats = self.encode(x)
        mu = stats[:, :self.output_size]
        # `NormalWithSoftplusScale(mu, rho - 5.0)` == `Normal(mu, softplus(rho - 5.0))`.
        std = F.softplus(stats[:, self.output_size:] + self.scale_offset)
        return mu, std

    def forward(self, x, nr_samples=1):
        """-> (mu, z, KL-per-dim), with `z` of shape `(nr_samples, B, output_size)`.

        At `nr_samples=1` this is exactly the authors' torch `Bottleneck.forward`
        (`bottleneck.py:29-45`) up to the leading axis: same `rsample`, same analytic
        `kl_divergence` to a fixed `N(0, I)`, same per-dim (unreduced) KL. `nr_samples > 1` is
        CoinRun's `encoding.sample(Config.NR_SAMPLES)` (`policies.py:73-75`).
        """
        mu, std = self.stats(x)
        prior = Normal(torch.zeros_like(mu), torch.ones_like(std))
        kl = kl_divergence(Normal(mu, std), prior)   # per-example, per-dim; reduced by the caller
        eps = torch.randn(nr_samples, *mu.shape, device=mu.device, dtype=mu.dtype)
        return mu, mu.unsqueeze(0) + std.unsqueeze(0) * eps, kl


def info_loss_bits(kl_per_dim):
    """`reduce_sum(reduce_mean(kl, 0)) / log(2)` -- `coinrun/coinrun/policies.py:62-64`.

    Batch-mean first, then sum over latent dims, then convert nats to **bits**. The authors' torch
    path sums-then-means and stays in nats (`torch_rl/model.py:192-193`, `algos/ppo.py:74`); the
    two reductions are equal (both are linear), but the `/log(2)` is not — it rescales the term
    `beta` multiplies by 1/ln 2 ~= 1.4427. Since `beta = 0.0001` is quoted from the CoinRun
    README, the CoinRun unit is the one that makes that number mean what it meant.
    """
    return kl_per_dim.mean(dim=0).sum() / float(np.log(2.0))


class IBACPolicy(nn.Module):
    """Replaces the base's `CategoricalPolicy` (`_upstream_1678e4a/common_policy.py`).

    One forward pass builds the whole reference graph at once -- `pd_train` (noisy, mixture over
    `nr_samples`), `pd_run` (deterministic, from the mean), a single deterministic `value`, and
    the info loss. That mirrors `CnnPolicy.__init__` (`policies.py:138-165`), which also builds
    both heads in one graph off one CNN evaluation, rather than DZ's two-call `_actor_terms`
    (`agents/ppo_ibac.py:51-60`) which runs the encoder twice.
    """

    def __init__(self,
                 embedder,
                 recurrent,
                 action_size,
                 ib_dim=256,
                 nr_samples=12,
                 scale_offset=-5.0,
                 init_scale=1.0):
        """
        embedder: (torch.Tensor) model to extract the embedding for observation
        action_size: dimensionality of the continuous action vector
        """
        super(IBACPolicy, self).__init__()
        self.embedder = embedder
        self.bottleneck = Bottleneck(self.embedder.output_dim, ib_dim, scale_offset)
        self.nr_samples = nr_samples
        self.action_size = action_size

        # One shared policy head, fed by two different latents -- `policies.py:140` (train, from
        # the samples) and `:164` (run, from the mean) resolve to the same 'model/pi' variable
        # under `reuse=tf.AUTO_REUSE`. See the module docstring on why init_scale is 1.0.
        self.fc_policy = orthogonal_init(nn.Linear(ib_dim, action_size), gain=init_scale)
        # State-independent log-std, zero-initialised -- baselines'
        # `DiagGaussianPdType.pdfromlatent`, reached via `make_pdtype(ac_space)` (`policies.py:123`).
        self.logstd = nn.Parameter(torch.zeros(1, action_size))
        # Value head reads the DETERMINISTIC latent only, under SNI -- `policies.py:160-161`.
        self.fc_value = orthogonal_init(nn.Linear(ib_dim, 1), gain=1.0)

        self.recurrent = recurrent
        if self.recurrent:
            # Carried from the base (`common_policy.py:23-25`) but unreachable: every config block
            # in the base's own `hyperparams/procgen/config.yml`, and both of DZ's IBAC blocks,
            # set `recurrent: False`. Declared exclusion, not a silent gap -- see `__init__.py`.
            raise NotImplementedError(
                "IBAC-SNI's recurrent path is not ported: no config block in the reference "
                "enables it, and this project's shared on-policy trainer threads no hidden state.")

    def is_recurrent(self):
        return self.recurrent

    def _dist(self, mean):
        """A diagonal Normal from a mean tensor, with the shared state-independent log-std."""
        return Normal(mean, self.logstd.exp().expand_as(mean))

    def forward(self, x):
        """-> (pd_train, pd_run, value, info_loss).

        `pd_train` is the mixture over `nr_samples` posterior draws (`policies.py:141-147`);
        `pd_run` is the deterministic pass (`policies.py:164`); `value` is deterministic for both
        the bootstrap and the value loss (`policies.py:161`); `info_loss` is in bits
        (`policies.py:62-64`).
        """
        h = self.embedder(x)
        # One `encode` for the whole graph: the CNN and the bottleneck are each evaluated once,
        # so `nr_samples > 1` costs extra only in the two small heads -- exactly as in the
        # reference, where `encoding.sample(NR_SAMPLES)` is reshaped into the batch dimension
        # *after* the CNN (`policies.py:72-76`).
        mu, z_samples, kl = self.bottleneck(h, nr_samples=self.nr_samples)
        info_loss = info_loss_bits(kl)

        # `out = relu(out); out_mean = relu(out_mean)` -- applied to BOTH (`policies.py:104-105`).
        z_samples = F.relu(z_samples)
        z_mean = F.relu(mu)

        # Train policy: mixture over the nr_samples component Normals (`policies.py:143-147`).
        means = self.fc_policy(z_samples).permute(1, 0, 2)   # (B, nr, act) -- cf. the TF transpose
        comp = Independent(self._dist(means), 1)
        mix = Categorical(probs=torch.full((self.nr_samples,), 1.0 / self.nr_samples,
                                           device=means.device, dtype=means.dtype))
        pd_train = MixtureSameFamily(mix, comp)

        # Run policy and the single deterministic value head.
        pd_run = Independent(self._dist(self.fc_policy(z_mean)), 1)
        value = self.fc_value(z_mean).reshape(-1)

        return pd_train, pd_run, value, info_loss

    def act(self, obs, deterministic=False):
        """Rollout-time action and its log-prob, both from the DETERMINISTIC pass.

        `Model.step` is bound to `act_model.step` (`ppo2.py:200-202`), which returns
        `a0_run`/`neglogp0_run` from `pd_run` (`policies.py:196-197,203-204`). So the action AND
        the stored `old_log_prob` are `pd_run` quantities -- the denominator of both PPO ratios in
        `optimize()`. This is the 'selective' half of Selective Noise Injection: no noise at
        rollout time.
        """
        _pd_train, pd_run, _value, _info = self.forward(obs)
        a = pd_run.mean if deterministic else pd_run.sample()
        return a, pd_run.log_prob(a).unsqueeze(-1)
