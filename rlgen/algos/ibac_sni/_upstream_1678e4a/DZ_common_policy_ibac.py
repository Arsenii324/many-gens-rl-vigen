# IBAC-SNI policy for train-procgen-pytorch.
# Implements the Information Bottleneck Actor-Critic (IBAC) of Igl et al. (NeurIPS 2019):
# a stochastic latent bottleneck z ~ N(mu(o), sigma(o)) with a KL(z || N(0,I)) penalty,
# plus support for Selective Noise Injection (SNI): a deterministic (mean) pass used for
# the policy-gradient / rollout, and a stochastic (sampled) pass used for the IB term.
from .misc_util import orthogonal_init
from .model import GRU
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Categorical, Normal


class IBACPolicy(nn.Module):
    def __init__(self, embedder, recurrent, action_size, ib_dim=None):
        """
        embedder: CNN feature extractor with attribute .output_dim
        recurrent: bool
        action_size: number of discrete actions
        ib_dim: bottleneck dimensionality (defaults to embedder.output_dim)
        """
        super(IBACPolicy, self).__init__()
        self.embedder = embedder
        D = self.embedder.output_dim
        self.ib_dim = ib_dim or D

        # bottleneck: embedder features -> (mu, log_sigma) of the stochastic latent z
        self.fc_mu = orthogonal_init(nn.Linear(D, self.ib_dim), gain=1.0)
        self.fc_logsigma = orthogonal_init(nn.Linear(D, self.ib_dim), gain=1.0)

        # heads consume the latent z
        self.fc_policy = orthogonal_init(nn.Linear(self.ib_dim, action_size), gain=0.01)
        self.fc_value = orthogonal_init(nn.Linear(self.ib_dim, 1), gain=1.0)

        self.recurrent = recurrent
        if self.recurrent:
            self.gru = GRU(self.ib_dim, self.ib_dim)

    def is_recurrent(self):
        return self.recurrent

    def _bottleneck(self, x):
        h = self.embedder(x)
        mu = self.fc_mu(h)
        log_sigma = self.fc_logsigma(h).clamp(-10.0, 2.0)   # numerical stability
        sigma = log_sigma.exp()
        return mu, sigma

    def _heads(self, z, hx, masks):
        if self.recurrent:
            z, hx = self.gru(z, hx, masks)
        logits = self.fc_policy(z)
        p = Categorical(logits=F.log_softmax(logits, dim=1))
        v = self.fc_value(z).reshape(-1)
        return p, v, hx

    def kl_to_prior(self, mu, sigma):
        # KL( N(mu,sigma^2) || N(0,1) ), summed over latent dims, mean over batch
        kl = 0.5 * (mu.pow(2) + sigma.pow(2) - 2.0 * torch.log(sigma + 1e-8) - 1.0)
        return kl.sum(dim=1).mean()

    def forward(self, x, hx, masks, sample=False, return_ib=False):
        """
        sample=False -> deterministic pass (z = mu). Used for rollout and, under SNI,
                        for the policy-gradient objective.
        sample=True  -> stochastic pass (z = mu + sigma*eps). Used for the IB term.
        return_ib=True also returns the KL bottleneck loss for the current pass.
        """
        mu, sigma = self._bottleneck(x)
        if sample:
            eps = torch.randn_like(sigma)
            z = mu + sigma * eps
        else:
            z = mu
        p, v, hx = self._heads(z, hx, masks)
        if return_ib:
            return p, v, hx, self.kl_to_prior(mu, sigma)
        return p, v, hx
