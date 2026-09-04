"""`ibac_sni` against its literal base — the edits are checked, not described.

Every claim `rlgen/algos/ibac_sni/` makes about being "a copy plus scoped edits" is checkable
here, by running the vendored pristine base (`_upstream_1678e4a/`, `joonleesky/train-procgen-pytorch`
@ `1678e4a`) side by side with the module. `docs/STEP-ZERO.md` gate 2: no tier claimed without a
runnable artifact that produces it.

These are the ONLY numerical verifications this baseline has. The algorithm itself (the
bottleneck, the SNI loss) is T4 — structural accounting against a TF 1.x reference this repo does
not execute. That limit is stated in `rlgen/algos/ibac_sni/__init__.py` and not papered over here.
"""
from __future__ import annotations

import hashlib
import pathlib
import types

import numpy as np
import pytest
import torch

MOD = pathlib.Path(__file__).resolve().parents[1] / "rlgen" / "algos" / "ibac_sni"
UP = MOD / "_upstream_1678e4a"


def _load_base(filename):
    """Execute a vendored base file as a standalone module.

    The one rewrite applied is `from .misc_util import ...` -> the module's own `misc_util`, which
    is legitimate precisely because `test_misc_util_is_a_byte_identical_copy` below proves the two
    files are the same bytes. If that test ever fails, this loader is lying and every test using
    it is void — which is why it is asserted rather than assumed.
    """
    src = (UP / filename).read_text()
    src = src.replace("from .misc_util import", "from rlgen.algos.ibac_sni.misc_util import")
    mod = types.ModuleType("base__" + filename[:-3])
    exec(compile(src, str(UP / filename), "exec"), mod.__dict__)
    return mod


# --------------------------------------------------------------------------------------------
# The base is intact and the "zero edits" claim is literal
# --------------------------------------------------------------------------------------------

def test_misc_util_is_a_byte_identical_copy_of_the_base():
    """`misc_util.py` claims ZERO edits. That is a hash claim, so check the hash."""
    ours = (MOD / "misc_util.py").read_bytes()
    base = (UP / "common_misc_util.py").read_bytes()
    assert hashlib.sha256(ours).hexdigest() == hashlib.sha256(base).hexdigest(), (
        "misc_util.py is documented as a byte-identical copy of the base. It is not. Either the "
        "file was edited without updating that claim, or the vendored base was touched — and "
        "_upstream_1678e4a/ is documented as never edited.")


def test_vendored_base_still_matches_the_upstream_commit_hashes():
    """`_upstream_1678e4a/PROVENANCE.md` pins each vendored file by sha256. Pin it for real."""
    expected = {
        "common_model.py": "b648f4d7b6cd6c4f", "common_policy.py": "646806e1a5d32395",
        "common_misc_util.py": "76c10f92e5f7fdbc", "common_storage.py": "e72b0bb06e06ff80",
        "agents_ppo.py": "1bcddc3a72d90ad1", "agents_base_agent.py": "1a545d22d1d1b58f",
        "DZ_common_policy_ibac.py": "9274a9d54efeec58", "DZ_agents_ppo_ibac.py": "c3e020574f30231a",
    }
    for name, prefix in expected.items():
        got = hashlib.sha256((UP / name).read_bytes()).hexdigest()[:16]
        assert got == prefix, f"{name}: vendored base changed ({got} != {prefix})"


# --------------------------------------------------------------------------------------------
# EDIT E1 -- the input-size generalisation reduces to the base at the base's own size
# --------------------------------------------------------------------------------------------

def test_e1_flat_dim_reduces_to_the_bases_own_hardcoded_constant():
    from rlgen.algos.ibac_sni.model import _impala_flat_dim
    assert _impala_flat_dim(64) == 32 * 8 * 8 == 2048   # the literal constant at common/model.py:102
    assert _impala_flat_dim(84) == 32 * 11 * 11 == 3872


def test_e1_encoder_is_numerically_identical_to_the_base_under_weight_transplant():
    """At 64x64 -- the base's own input size -- edit E1 must change NOTHING.

    Same weights transplanted into both, same input, outputs must agree to floating point. This
    is a real forward-parity check against the actual base code, not a shape assertion.
    """
    base_model = _load_base("common_model.py")
    from rlgen.algos.ibac_sni.model import ImpalaModel as OursImpala

    torch.manual_seed(0)
    theirs = base_model.ImpalaModel(in_channels=3)
    ours = OursImpala(in_channels=3, image_size=64)
    ours.load_state_dict(theirs.state_dict())          # fails loudly if the graphs differ at all

    x = torch.rand(4, 3, 64, 64)
    theirs.eval(); ours.eval()
    with torch.no_grad():
        a, b = theirs(x), ours(x)
    assert torch.allclose(a, b, atol=1e-6), f"max diff {(a - b).abs().max().item()}"


def test_e2_uint8_scaling_reproduces_the_bases_ScaledFloatFrame():
    """The base scaled outside the model (`procgen_wrappers.py:373`, `obs/255.0`); edit E2 moved
    that inside. Feeding uint8 to ours must equal feeding pre-scaled float to the base."""
    base_model = _load_base("common_model.py")
    from rlgen.algos.ibac_sni.model import ImpalaModel as OursImpala

    torch.manual_seed(0)
    theirs = base_model.ImpalaModel(in_channels=3)
    ours = OursImpala(in_channels=3, image_size=64)
    ours.load_state_dict(theirs.state_dict())

    raw = torch.randint(0, 256, (4, 3, 64, 64), dtype=torch.uint8)
    theirs.eval(); ours.eval()
    with torch.no_grad():
        a = theirs(raw.float() / 255.0)     # what ScaledFloatFrame handed the base
        b = ours(raw)                       # what our harness hands us
    assert torch.allclose(a, b, atol=1e-6), f"max diff {(a - b).abs().max().item()}"


def test_e2_does_not_mutate_the_callers_tensor():
    """The rollout buffer holds the same uint8 tensor. An in-place `div_` would corrupt it."""
    from rlgen.algos.ibac_sni.model import ImpalaModel
    m = ImpalaModel(in_channels=3, image_size=64).eval()
    raw = torch.randint(0, 256, (2, 3, 64, 64), dtype=torch.uint8)
    before = raw.clone()
    with torch.no_grad():
        m(raw)
    assert torch.equal(raw, before), "encoder mutated its input in place"


# --------------------------------------------------------------------------------------------
# storage.py -- the GAE equivalence claim, run rather than argued
# --------------------------------------------------------------------------------------------

def _run_both_storages(T=16, N=1, gamma=0.99, lam=0.95, truncate_at=None, seed=0):
    """Drive the base's `Storage` and ours over one identical random rollout."""
    from rlgen.algos.ibac_sni.storage import RolloutStorage
    base_storage = _load_base("common_storage.py")

    rng = np.random.default_rng(seed)
    obs_shape, act_dim, dev = (2, 4, 4), 3, torch.device("cpu")

    rew = rng.normal(size=(T, N)).astype(np.float32)
    val = rng.normal(size=(T, N)).astype(np.float32)
    done = np.zeros((T, N), dtype=np.float32)
    if truncate_at is not None:
        done[truncate_at] = 1.0
    last_val = rng.normal(size=(N,)).astype(np.float32)
    boot = rng.normal(size=(N,)).astype(np.float32)

    # --- the base's own buffer -----------------------------------------------------------
    theirs = base_storage.Storage(obs_shape, 1, T, N, dev)
    zero_obs = np.zeros((N, *obs_shape), dtype=np.float32)
    for t in range(T):
        theirs.store(zero_obs, np.zeros((N, 1), dtype=np.float32),
                     np.zeros((N,), dtype=np.float32), rew[t], done[t], [{}] * N,
                     np.zeros((N,), dtype=np.float32), val[t])
    theirs.store_last(zero_obs, np.zeros((N, 1), dtype=np.float32), last_val)
    theirs.compute_estimates(gamma=gamma, lmbda=lam, use_gae=True, normalize_adv=True)

    # --- ours --------------------------------------------------------------------------
    ours = RolloutStorage(T, N, obs_shape, act_dim, dev)
    ours.init_obs(torch.zeros(N, *obs_shape, dtype=torch.uint8))
    for t in range(T):
        trunc = torch.tensor(done[t]) if truncate_at is not None else torch.zeros(N)
        ours.insert(torch.zeros(N, *obs_shape, dtype=torch.uint8),
                    torch.zeros(N, act_dim), torch.zeros(N, 1),
                    torch.tensor(val[t]).unsqueeze(-1),
                    torch.tensor(rew[t]), torch.tensor(rew[t]),
                    torch.tensor(done[t]), trunc,
                    torch.tensor(boot).unsqueeze(-1), gamma)
    ours.compute_returns(torch.tensor(last_val).unsqueeze(-1), gamma, lam)
    return theirs, ours


def test_gae_and_returns_match_the_bases_own_storage_exactly():
    """No truncation -> the two must agree to floating point, advantages and returns both.

    This is what licenses `storage.py`'s equivalence table. It is also what caught the advantage
    normaliser's epsilon being 1e-5 instead of the base's 1e-8 (fixed 2026-08-16): the difference
    is invisible by inspection and shows up here immediately.
    """
    theirs, ours = _run_both_storages(truncate_at=None)
    assert torch.allclose(ours.advantages(normalize=True).squeeze(-1), theirs.adv_batch, atol=1e-6)
    assert torch.allclose(ours.returns[:-1].squeeze(-1), theirs.return_batch, atol=1e-6)


def test_advantage_normaliser_epsilon_matches_the_base():
    """Pin the constant itself, so a future edit can't silently reintroduce the drift."""
    src = (MOD / "storage.py").read_text()
    assert "adv.std() + 1e-8" in src, "advantage epsilon must be the base's 1e-8 (common/storage.py:69)"


def test_truncation_adaptation_diverges_from_the_base_exactly_as_predicted():
    """The ONE deliberate divergence (`porting-directive.md` §4) — pinned, not just described.

    Where an episode is truncated, ours folds `gamma * V(final_obs)` into that step's reward and
    the base does not. So the two MUST differ, and differ by a predictable amount. A test that
    only checked agreement would silently pass if the adaptation were deleted.
    """
    theirs, ours = _run_both_storages(truncate_at=7)
    ours_ret = ours.returns[:-1].squeeze(-1)
    assert not torch.allclose(ours_ret, theirs.return_batch, atol=1e-4), (
        "the truncation-bootstrap adaptation has stopped having any effect — either it was "
        "removed, or this test is no longer exercising a truncation")
    # Everything strictly after the truncation is unaffected by it (GAE runs backwards, and the
    # mask cuts the recursion at the boundary), so those steps must still agree exactly.
    assert torch.allclose(ours_ret[8:], theirs.return_batch[8:], atol=1e-6), (
        "the adaptation leaked past the episode boundary it is scoped to")


# --------------------------------------------------------------------------------------------
# The reference's SNI structure, asserted against the module rather than the docstring
# --------------------------------------------------------------------------------------------

@pytest.fixture
def learner():
    from rlgen.algos.ibac_sni.algo import Learner
    from rlgen.algos.ibac_sni.config import Config
    torch.manual_seed(0)
    return Learner(Config(), (9, 84, 84), 7, torch.device("cpu"))


def test_value_head_reads_only_the_deterministic_latent(learner):
    """`policies.py:161`: under SNI both value tensors are `fc(h_vf, 'v', 1)` — deterministic.

    So two forward passes must give the SAME value (no sampling noise) while the train policy's
    mean does vary. The discarded module mixed a stochastic value in; that would fail this.
    """
    learner.policy.eval()
    obs = torch.randint(0, 256, (8, 9, 84, 84), dtype=torch.uint8)
    with torch.no_grad():
        pd_a, run_a, val_a, _ = learner.policy(obs)
        pd_b, run_b, val_b, _ = learner.policy(obs)
    assert torch.allclose(val_a, val_b, atol=1e-6), "value head is stochastic; reference's is not"
    assert torch.allclose(run_a.mean, run_b.mean, atol=1e-6), "pd_run must be deterministic too"
    assert not torch.allclose(pd_a.component_distribution.mean,
                              pd_b.component_distribution.mean, atol=1e-6), \
        "pd_train must be the NOISY pass — it is not sampling at all"


def test_sigma_starts_near_deterministic_per_the_minus_five_offset(learner):
    """`policies.py:58` `softplus(rho - 5.0)`: std ~= 0.0067 at init, not 1.0."""
    obs = torch.randint(0, 256, (16, 9, 84, 84), dtype=torch.uint8)
    with torch.no_grad():
        _mu, std = learner.policy.bottleneck.stats(learner.policy.embedder(obs))
    assert std.mean().item() < 0.05, (
        f"initial sigma {std.mean().item():.4f} is far from the reference's ~0.0067 — the -5.0 "
        "pre-softplus offset is missing or the parameterisation reverted to exp(log_sigma)")


def test_there_is_no_sni_lambda_knob():
    """The reference's mix is a hardcoded `/2.` (`ppo2.py:104,107`); `Config.SNI` is a boolean.

    A tunable `sni_lambda` would be a degree of freedom the reference does not have. The
    discarded module had one.
    """
    from rlgen.algos.ibac_sni.config import Config
    assert not hasattr(Config(), "sni_lambda")


def test_l2_term_excludes_biases_and_includes_logstd(learner):
    """`ppo2.py:116` `[v for v in params if '/b' not in v.name]` — biases out, `pi/logstd` in."""
    names = {n for n, _ in learner.policy.named_parameters()}
    l2_ids = {id(p) for p in learner._l2_params}
    for n, p in learner.policy.named_parameters():
        if n.endswith(".bias"):
            assert id(p) not in l2_ids, f"bias {n} must be excluded from the L2 term"
    assert any(id(p) in l2_ids for n, p in learner.policy.named_parameters() if n == "logstd"), \
        "logstd is not excluded by the reference's '/b' test, so it belongs in the L2 term"
    assert names  # guard against a silently empty parameter set


def test_update_runs_and_produces_finite_losses(learner):
    """End to end through the real contract the shared trainer uses."""
    T = 16
    S = learner.storage_cls(T, 1, (9, 84, 84), 7, torch.device("cpu"))
    obs = torch.randint(0, 256, (1, 9, 84, 84), dtype=torch.uint8)
    S.init_obs(obs)
    for t in range(T):
        with torch.no_grad():
            a, lp = learner.policy.act(obs, deterministic=False)
            v = learner.value_of(obs)
        nxt = torch.randint(0, 256, (1, 9, 84, 84), dtype=torch.uint8)
        done = t == T - 1
        r = learner.normalize_reward(0.3, done)
        S.insert(nxt, a, lp, v, torch.tensor([r]), torch.tensor([0.3]),
                 torch.tensor([float(done)]), torch.tensor([float(done)]),
                 torch.zeros(1, 1), 0.99)
        obs = nxt
    with torch.no_grad():
        nv = learner.value_of(obs)
    S.compute_returns(nv, 0.99, 0.95)
    learner.cfg.num_mini_batch = 4
    out = learner.update(S, 0)
    assert set(out) == {"Loss/pi", "Loss/v", "Loss/entropy", "Loss/info_bits", "Loss/l2"}
    assert all(np.isfinite(v) for v in out.values()), out
    assert out["Loss/info_bits"] > 0.0, "KL to N(0,I) is non-negative and should not be zero here"
