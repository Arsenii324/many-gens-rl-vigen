"""The Gaussian policy machinery, checked against closed forms rather than against itself.

WHY THIS FILE EXISTS. Three of our on-policy baselines (`ppg`, `ibac_sni`, `ctrl`) run a continuous
diagonal-Gaussian policy for which **no reference implementation exists** -- IDAAC's released code
ships only `FixedCategorical`, and its paper never names the action distribution used for its own
continuous experiments. So the encoder, the PPO core and each method's auxiliary loss can be checked
against primary sources, and the action distribution cannot.

What *can* be checked is that the distribution maths is right. These are the cheapest tests in the
repo -- no training run, no environment -- and they catch the class of defect suspected in the one
third-party continuous PPG that exists (a tanh log-det-Jacobian omission, which makes the PPO
importance ratio silently wrong).
"""
from __future__ import annotations

import torch

from rlgen.algos.idaac.model import DiagGaussianHead


def _pair(seed: int = 0, B: int = 64, A: int = 7):
    torch.manual_seed(seed)
    return (torch.randn(B, A), torch.rand(B, A).add(0.2),
            torch.randn(B, A), torch.rand(B, A).add(0.2))


def _our_kl(mu_o, std_o, mu_n, std_n):
    """The closed form used by PPGLearner._auxiliary_phase, copied verbatim."""
    return (torch.log(std_n / std_o) + (std_o ** 2 + (mu_o - mu_n) ** 2)
            / (2.0 * std_n ** 2) - 0.5).sum(-1).mean()


def test_ppg_clone_kl_matches_the_closed_form():
    """PPG's auxiliary phase holds the policy still with beta_clone * KL. If that KL is wrong, the
    aux phase is free to move the policy while optimising a value target -- the exact failure the
    term exists to prevent."""
    mu_o, std_o, mu_n, std_n = _pair()
    ref = torch.distributions.kl_divergence(
        torch.distributions.Normal(mu_o, std_o),
        torch.distributions.Normal(mu_n, std_n)).sum(-1).mean()
    assert torch.allclose(_our_kl(mu_o, std_o, mu_n, std_n), ref, atol=1e-6)


def test_ppg_clone_kl_is_in_the_direction_the_paper_specifies():
    """Cobbe's L_joint uses KL(pi_old || pi_theta): the OLD policy is the reference and the new one
    is pulled toward it. The reverse is a different, mode-seeking objective, and on random inputs
    the two differ by ~10%, so this is not a distinction without a difference."""
    mu_o, std_o, mu_n, std_n = _pair()
    forward = _our_kl(mu_o, std_o, mu_n, std_n)
    reverse = torch.distributions.kl_divergence(
        torch.distributions.Normal(mu_n, std_n),
        torch.distributions.Normal(mu_o, std_o)).sum(-1).mean()
    assert not torch.allclose(forward, reverse, atol=1e-3), \
        "forward and reverse KL coincide on this sample; the test cannot detect a flipped direction"
    ref_forward = torch.distributions.kl_divergence(
        torch.distributions.Normal(mu_o, std_o),
        torch.distributions.Normal(mu_n, std_n)).sum(-1).mean()
    assert torch.allclose(forward, ref_forward, atol=1e-6), "KL direction is reversed"


def test_clone_kl_is_exactly_zero_when_the_policy_has_not_moved():
    """A non-zero penalty for a policy that did not move would drag it away from itself."""
    mu, std, _, _ = _pair()
    assert float(_our_kl(mu, std, mu.clone(), std.clone())) == 0.0


def test_entropy_and_log_prob_sum_over_every_action_dimension():
    """A 7-D Gaussian's entropy and log-density are sums over dimensions. Getting this wrong by
    taking a mean instead of a sum rescales the entropy bonus and the importance ratio by 1/7 --
    silently, and in a way that looks like a tuning problem rather than a bug."""
    mu, std, _, _ = _pair()
    d = torch.distributions.Normal(mu, std)
    closed = (0.5 * (1 + torch.log(torch.tensor(2 * torch.pi))) + torch.log(std)).sum(-1)
    assert torch.allclose(d.entropy().sum(-1), closed, atol=1e-5)
    assert d.log_prob(d.sample()).sum(-1, keepdim=True).shape == (mu.shape[0], 1)


def test_our_policy_head_is_unsquashed_so_no_jacobian_term_is_owed():
    """If a tanh squash were introduced, log_prob would need a `- sum(log(1 - tanh(u)^2))`
    correction, and omitting it makes the PPO ratio wrong. We use a plain Normal, matching the
    Kostrikov convention IDAAC builds on, so no correction is owed -- this test fails the moment
    someone adds a squash without the Jacobian."""
    head = DiagGaussianHead(16, 7)
    dist = head(torch.randn(4, 16))
    assert isinstance(dist, torch.distributions.Normal), \
        f"policy head returns {type(dist).__name__}; if it is now squashed, log_prob owes a " \
        f"tanh log-det-Jacobian term and this repo does not add one"
