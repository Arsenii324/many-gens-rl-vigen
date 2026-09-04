"""`idaac`'s encoder against its literal base — T1 *and* init-parity.

Both sides are PyTorch (`rraileanu/idaac` @ `2fe3020`), so a weight transplant is available. It is
paired with an init-parity check because of a limit found the hard way on `ppg` and now written
into `docs/STEP-ZERO.md`'s T1 definition: **transplanting overwrites initialisation, so T1 is
structurally blind to it.** That matters more here than anywhere yet — three consecutive baselines
have now had three different init schemes (xavier / normalized-fan-in / orthogonal+xavier), so
there is no prior from a neighbour to fall back on.

`sys.modules` is restored in teardown. The `ppg` version of this file did not, and 14 tests in
another file failed on a full run while both passed in isolation.
"""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys
import types

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
UP = ROOT / "rlgen" / "algos" / "idaac" / "_upstream_2fe3020"


def _load_vendored():
    """Load the vendored `model.py` with its intra-package imports satisfied.

    No `pytest.skip` guard: a blanket one on the `ppg` equivalent turned a real import failure
    into a silent pass, and pytest's `s` scans as a pass. If the base will not load, this file
    has no meaning and must say so loudly.
    """
    pkg = "_idaac_upstream_pkg"
    if pkg not in sys.modules:
        m = types.ModuleType(pkg)
        m.__path__ = [str(UP)]
        sys.modules[pkg] = m
    # `model.py` imports `from ppo_daac_idaac.distributions import Categorical` and
    # `from ppo_daac_idaac.utils import init` -- the reference's own package layout, which is not
    # this one. Aliased rather than edited: `_upstream_2fe3020/` is never modified.
    alias = types.ModuleType("ppo_daac_idaac")
    alias.__path__ = [str(UP)]
    sys.modules.setdefault("ppo_daac_idaac", alias)
    for real, asname in (("distributions", "ppo_daac_idaac.distributions"),
                         ("utils", "ppo_daac_idaac.utils"),
                         ("model", f"{pkg}.model")):
        if asname in sys.modules:
            continue
        spec = importlib.util.spec_from_file_location(asname, UP / f"{real}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[asname] = mod
        spec.loader.exec_module(mod)
    return sys.modules[f"{pkg}.model"]


@pytest.fixture(scope="module")
def vendored():
    before = dict(sys.modules)
    try:
        yield _load_vendored()
    finally:
        for name in set(sys.modules) - set(before):
            del sys.modules[name]
        sys.modules.update(before)


def test_vendored_base_matches_the_pinned_hashes():
    expected = {
        "model.py": "8ab8ff3ad74ff9fa", "storage.py": "94ee5caa68a6a5e9",
        "distributions.py": "945c4ede237642b8", "utils.py": "80ff234507c570e5",
        "algo_idaac.py": "9171fda7adce2159", "algo_daac.py": "964206e55ce4f38a",
        "algo_ppo.py": "a4e68ba597861d77", "hyperparams.py": "661d85c7a12b4547",
    }
    for name, prefix in expected.items():
        got = hashlib.sha256((UP / name).read_bytes()).hexdigest()[:16]
        assert got == prefix, f"{name}: vendored base changed ({got} != {prefix})"


def test_the_reference_still_ships_no_continuous_head(vendored):
    """Pins the fact the authored Gaussian head rests on (`docs/REGISTER.md`, 2026-08-16).

    If a re-clone ever added one, the head would need re-deciding rather than silently remaining
    authored.
    """
    src = (UP / "distributions.py").read_text()
    assert "class Categorical" in src
    assert "DiagGaussian" not in src and "class Normal" not in src, (
        "the reference now ships a continuous head — the authored one must be re-derived from it")


def test_e1_flat_dim_reduces_to_the_references_own_constant():
    from rlgen.algos.idaac.encoder import _flat_dim
    assert _flat_dim(64) == 2048            # the literal constant at model.py:145
    assert _flat_dim(84) == 32 * 11 * 11 == 3872


@pytest.mark.parametrize("hw,cin", [(64, 3), (84, 9)])
def test_encoder_agrees_with_the_vendored_reference_under_weight_transplant(vendored, hw, cin):
    """T1. Same weights, same pixels, outputs must agree — value head and features both."""
    from rlgen.algos.idaac.encoder import ResNetBase as Ours

    torch.manual_seed(0)
    theirs = vendored.ResNetBase(cin, hidden_size=256, channels=[16, 32, 32])
    if hw != 64:                     # the reference hardcodes 2048; give it the right fc for hw
        import torch.nn as nn
        from rlgen.algos.idaac.encoder import _flat_dim, init_relu_
        theirs.fc = init_relu_(nn.Linear(_flat_dim(hw), 256))
    ours = Ours(cin, hidden_size=256, channels=(16, 32, 32), image_size=hw)
    ours.load_state_dict(theirs.state_dict())      # raises if the graphs differ at all

    x = torch.rand(4, cin, hw, hw)
    theirs.eval(); ours.eval()
    with torch.no_grad():
        (v_t, f_t), (v_o, f_o) = theirs(x), ours(x)
    assert torch.allclose(v_t, v_o, atol=1e-5), f"value diff {(v_t - v_o).abs().max().item():.3e}"
    assert torch.allclose(f_t, f_o, atol=1e-5), f"feat diff {(f_t - f_o).abs().max().item():.3e}"


def test_e2_uint8_scaling_matches_prescaled_float(vendored):
    """E2 moved the /255 inside; feeding uint8 to ours must equal prescaled float to theirs."""
    from rlgen.algos.idaac.encoder import ResNetBase as Ours
    torch.manual_seed(0)
    theirs = vendored.ResNetBase(3, hidden_size=256, channels=[16, 32, 32])
    ours = Ours(3, hidden_size=256, channels=(16, 32, 32), image_size=64)
    ours.load_state_dict(theirs.state_dict())
    raw = torch.randint(0, 256, (4, 3, 64, 64), dtype=torch.uint8)
    theirs.eval(); ours.eval()
    before = raw.clone()
    with torch.no_grad():
        (_, f_t), (_, f_o) = theirs(raw.float() / 255.0), ours(raw)
    assert torch.allclose(f_t, f_o, atol=1e-5)
    assert torch.equal(raw, before), "encoder mutated the caller's buffer in place"


def test_initialisation_matches_the_reference_layer_for_layer(vendored):
    """The check T1 cannot make. Same seed, compare tensors.

    IDAAC's scheme is a third distinct one — `orthogonal_` on the linears (gain 1 and gain
    sqrt(2)) then `xavier_uniform_` over convs via `apply_init_`, which only touches
    Conv2d/BatchNorm and so leaves the linears alone. Getting the ORDER wrong silently changes
    every weight while leaving the forward arithmetic perfect.
    """
    from rlgen.algos.idaac.encoder import ResNetBase as Ours
    torch.manual_seed(4321)
    theirs = vendored.ResNetBase(3, hidden_size=256, channels=[16, 32, 32])
    torch.manual_seed(4321)
    ours = Ours(3, hidden_size=256, channels=(16, 32, 32), image_size=64)
    t, o = theirs.state_dict(), ours.state_dict()
    assert set(t) == set(o), f"module names diverged: {sorted(set(t) ^ set(o))[:4]}"
    bad = [k for k in t if not torch.allclose(t[k], o[k], atol=1e-6)]
    assert not bad, f"{len(bad)} tensors initialise differently, e.g. {bad[:4]}"


def test_conv2d_tf_pads_asymmetrically_where_plain_conv_cannot(vendored):
    """Demonstrates that the asymmetric branch EXISTS — not that this network uses it.

    Stated precisely because the distinction was got wrong once: `stride=2` below is a
    configuration IDAAC never builds. Every conv in `_make_layer` and `BasicBlock` is
    `kernel_size=3, stride=1`, where total padding is always exactly 2 — even — so the one-sided
    pad never fires and `Conv2d_tf` is numerically identical to `nn.Conv2d(padding=1)` throughout
    this model, at every input size. A mutation swapping them left T1 green, which is how this was
    found (`docs/REGISTER.md`, 2026-08-16).

    So this test guards the mechanism, and the reason `Conv2d_tf` is carried is fidelity plus the
    fact that the equivalence depends on these hyperparameters — a later stride change would
    silently break a substitution that looks safe today.
    """
    import torch.nn as nn
    from rlgen.algos.idaac.encoder import Conv2d_tf
    torch.manual_seed(0)
    tf = Conv2d_tf(3, 4, kernel_size=3, stride=2)
    plain = nn.Conv2d(3, 4, kernel_size=3, stride=2, padding=1)
    plain.load_state_dict(tf.state_dict())
    x = torch.rand(2, 3, 8, 8)          # even size, stride 2 -> TF pads one-sided
    with torch.no_grad():
        a, b = tf(x), plain(x)
    assert a.shape == b.shape
    assert not torch.allclose(a, b, atol=1e-6), (
        "Conv2d_tf and a symmetric nn.Conv2d agree here — either the asymmetric branch is dead "
        "or this input no longer exercises it, and carrying Conv2d_tf would need re-justifying")


def test_value_resnet_transplants_from_the_references_own_ValueResNet(vendored):
    """`ValueResNet` is structurally `ResNetBase`, but the reference keeps it a distinct class
    and so do we — IDAAC's premise is that the value function lives in a SEPARATE network."""
    from rlgen.algos.idaac.encoder import ValueResNet as Ours
    torch.manual_seed(0)
    theirs = vendored.ValueResNet(3, hidden_size=256, channels=[16, 32, 32])
    ours = Ours(3, hidden_size=256, channels=(16, 32, 32), image_size=64)
    ours.load_state_dict(theirs.state_dict())
    x = torch.rand(4, 3, 64, 64)
    theirs.eval(); ours.eval()
    with torch.no_grad():
        v_t, v_o = theirs(x), ours(x)
    # Value ALONE, not (value, features): ValueResNet.forward differs from ResNetBase's
    # (model.py:265). Inheriting ResNetBase's forward was the bug this unpacking caught.
    assert torch.is_tensor(v_t) and torch.is_tensor(v_o), "forward should return one tensor"
    assert torch.allclose(v_t, v_o, atol=1e-5), f"diff {(v_t - v_o).abs().max().item():.3e}"


def test_advantage_head_matches_the_reference_on_its_shared_trunk(vendored):
    """The advantage head's TRUNK is transplantable; its final layer is not, and that is the
    adaptation.

    The reference's `critic_linear` is `Linear(hidden + num_actions, 1)` over a ONE-HOT action;
    ours is `Linear(hidden + act_dim, 1)` over the raw continuous vector. Different shapes, so no
    transplant is possible there — which is exactly why the adaptation is graded NOT INTRINSIC.
    What IS checkable is that everything upstream of the concat is unchanged, so the divergence is
    confined to the one layer that has to diverge.
    """
    from rlgen.algos.idaac.encoder import PolicyResNetBase as Ours
    torch.manual_seed(0)
    theirs = vendored.PolicyResNetBase(3, hidden_size=256, channels=[16, 32, 32], num_actions=15)
    ours = Ours(3, hidden_size=256, channels=(16, 32, 32), image_size=64, act_dim=7)
    shared = {k: v for k, v in theirs.state_dict().items() if not k.startswith("critic_linear")}
    missing, unexpected = ours.load_state_dict(shared, strict=False)
    assert not unexpected, unexpected
    assert set(missing) == {"critic_linear.weight", "critic_linear.bias"}, missing

    x = torch.rand(4, 3, 64, 64)
    theirs.eval(); ours.eval()
    with torch.no_grad():
        f_t = theirs(x)[1]
        f_o = ours(x)[1]
    assert torch.allclose(f_t, f_o, atol=1e-5), "the trunk diverged, not just the head"


def test_advantage_head_actually_conditions_on_the_action():
    """A head that ignores its action is a value head wearing an advantage head's name — and it
    would pass every shape and transplant check above."""
    from rlgen.algos.idaac.encoder import PolicyResNetBase
    torch.manual_seed(0)
    p = PolicyResNetBase(9, image_size=84, act_dim=7).eval()
    x = torch.randint(0, 256, (4, 9, 84, 84), dtype=torch.uint8)
    a1, a2 = torch.randn(4, 7), torch.randn(4, 7)
    with torch.no_grad():
        adv1, adv2, adv0 = p(x, a1)[0], p(x, a2)[0], p(x, None)[0]
    assert not torch.allclose(adv1, adv2, atol=1e-6), "advantage ignores the action"
    assert not torch.allclose(adv1, adv0, atol=1e-6), "the actions=None fallback is not distinct"
    assert p.critic_linear.in_features == 256 + 7
