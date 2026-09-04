"""`ppg` against its literal base — the project's first real weight-transplant T1.

Both sides are PyTorch here, unlike `ibac_sni` (whose reference is TF 1.x, so its algorithm stays
T4). That makes a genuine **forward agreement under transplanted weights** available: build the
vendored `ImpalaCNN` and ours, copy one state_dict into the other, feed the same observation, and
require the outputs to agree to floating point. Nothing about naming, shapes or docstrings can
fake that.

The vendored tree is never edited (`_upstream_7295473/PROVENANCE.md`). `torch_util.py` imports
`mpi4py`, which is not installed here and has nothing to do with the arithmetic under test, so it
is stubbed **in this file** — the dependency shim lives with the test, not in the reference.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
UP = ROOT / "rlgen" / "algos" / "ppg" / "_upstream_7295473"


def _load_vendored():
    """Import the vendored `impala_cnn` as a package so its `from . import torch_util` resolves."""
    if "mpi4py" not in sys.modules:
        # Permissive stub rather than a fixed attribute list: `torch_util` uses MPI in type
        # ANNOTATIONS (`comm: MPI.Comm`, evaluated at def time) as well as at call sites, and
        # enumerating what it touches is guesswork that fails one attribute at a time. Nothing
        # here is exercised — the encoder under test is pure torch; MPI only has to exist for
        # the module to import.
        class _AnyAttr(types.ModuleType):
            def __getattr__(self, name):
                return type(name, (), {})
        mpi = _AnyAttr("mpi4py.MPI")
        m = types.ModuleType("mpi4py")
        m.MPI = mpi
        sys.modules["mpi4py"] = m
        sys.modules["mpi4py.MPI"] = mpi
    pkg_name = "_ppg_upstream_pkg"
    if pkg_name not in sys.modules:
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(UP)]
        sys.modules[pkg_name] = pkg
    # `torch_util.py:15` does `from . import logger`, which is the reference's own logging
    # layer -- deliberately not vendored (`PROVENANCE.md`: the vendored set is algorithm code).
    # Stubbed here rather than pulled in, for the same reason as mpi4py: it has nothing to do
    # with the arithmetic under test, and vendoring it to satisfy an import would widen the
    # base term for a test's convenience.
    log_name = f"{pkg_name}.logger"
    if log_name not in sys.modules:
        lg = types.ModuleType(log_name)
        for fn in ("log", "info", "warn", "debug", "logkv", "dumpkvs"):
            setattr(lg, fn, lambda *a, **k: None)
        sys.modules[log_name] = lg
        setattr(sys.modules[pkg_name], "logger", lg)
    for mod in ("torch_util", "impala_cnn"):
        full = f"{pkg_name}.{mod}"
        if full not in sys.modules:
            spec = importlib.util.spec_from_file_location(full, UP / f"{mod}.py")
            m = importlib.util.module_from_spec(spec)
            sys.modules[full] = m
            spec.loader.exec_module(m)
    return sys.modules[f"{pkg_name}.impala_cnn"]


@pytest.fixture(scope="module")
def vendored():
    """Loads the vendored encoder, then **puts `sys.modules` back**.

    The teardown is not tidiness. Without it this file installed an `mpi4py` stub and a synthetic
    package into the global module table and left them there, and **14 tests in
    `test_real_env.py` failed** on a full run while both files passed in isolation — a failure
    that only exists when the suite is run as a suite, which is how it is actually run. A test
    that corrupts other tests is worse than a missing test: it produces failures whose cause is
    somewhere the traceback never points.

    No `try`/`pytest.skip` here, deliberately.

    An earlier version wrapped this in `except Exception: pytest.skip(...)`. The vendored tree
    then failed to import for an ordinary reason (`torch_util` wants `. import logger`) and
    **every parity test silently skipped while the run reported green** — pytest prints `s`, and
    `s` scans as a pass. A T1 that skips is not a T1, and a fixture that converts a real failure
    into a quiet one is precisely the vacuous-test mode `docs/RIGOR.md` names. If the base cannot
    be loaded, this test file has no meaning and should say so loudly.
    """
    before = dict(sys.modules)
    try:
        yield _load_vendored()
    finally:
        for name in set(sys.modules) - set(before):
            del sys.modules[name]
        sys.modules.update(before)


# --------------------------------------------------------------------------------------------
# The base is intact
# --------------------------------------------------------------------------------------------

def test_vendored_base_matches_the_pinned_hashes():
    import hashlib
    expected = {
        "ppg.py": "ff94cfe2f61375b6", "ppo.py": "640185fd4604e686",
        "impala_cnn.py": "029ab63688264b27", "reward_normalizer.py": "e1052fcc12430de1",
        "roller.py": "1a87c55a7b112e9a", "distr_builder.py": "3de4655f99b792d5",
        "torch_util.py": "5687b6171bffabbc", "minibatch_optimize.py": "239322b6a2a059c6",
        "tree_util.py": "ba2f835a26245781",
    }
    for name, prefix in expected.items():
        got = hashlib.sha256((UP / name).read_bytes()).hexdigest()[:16]
        assert got == prefix, f"{name}: vendored base changed ({got} != {prefix})"


def test_the_reference_still_has_no_reachable_continuous_head(vendored):
    """Pins the finding the whole head design rests on (`docs/REGISTER.md`, 2026-08-16).

    `_make_normal` exists but nothing calls it, and `tensor_distr_builder` raises on any
    non-Discrete action type. If a future re-clone changed that, the authored Gaussian head would
    need re-deciding rather than silently staying authored.
    """
    src = (UP / "distr_builder.py").read_text()
    assert "def _make_normal" in src
    body = src.split("def tensor_distr_builder")[1]
    assert "_make_normal" not in body, "the reference now wires a Normal head — re-decide"
    assert "raise ValueError" in body


# --------------------------------------------------------------------------------------------
# T1 — forward agreement under transplanted weights
# --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("hw,cin", [(84, 9), (64, 3)])
def test_encoder_agrees_with_the_vendored_reference_under_weight_transplant(vendored, hw, cin):
    """The real T1. Reference takes (B, T, H, W, C); ours takes (B, C, H, W) — edit E1.

    Same weights, same pixels, and the outputs must match. This is what makes E1's claim
    ("the round-trip has nothing to do") a measurement rather than a description.
    """
    from rlgen.algos.ppg.model import ImpalaCNN as Ours

    torch.manual_seed(0)
    theirs = vendored.ImpalaCNN(inshape=(hw, hw, cin), chans=(16, 32, 32), outsize=256,
                                scale_ob=255.0, nblock=2)
    ours = Ours((cin, hw, hw), chans=(16, 32, 32), outsize=256, nblock=2)
    # Identical module names on both sides -> a plain load, no key remapping. If the graphs
    # differed at all this raises rather than silently partially loading.
    ours.load_state_dict(theirs.state_dict())

    raw = torch.randint(0, 256, (5, hw, hw, cin), dtype=torch.uint8)   # NHWC, as the ref wants
    theirs.eval(); ours.eval()
    with torch.no_grad():
        a = theirs(raw.unsqueeze(0).float())[0]                       # (1, B, H, W, C) -> (B, D)
        b = ours(raw.permute(0, 3, 1, 2).contiguous())                # (B, C, H, W)
    assert a.shape == b.shape == (5, 256)
    assert torch.allclose(a, b, atol=1e-5), f"max diff {(a - b).abs().max().item():.3e}"


def test_flatten_width_is_derived_not_hardcoded(vendored):
    """E2 claims no edit was needed for 84x84 because the reference derives its own width.

    Check that against the reference itself rather than trusting the claim: build both at 84 and
    at the reference's native 64, and require the `dense` layer to agree each time.
    """
    from rlgen.algos.ppg.model import ImpalaCNN as Ours
    for hw, cin in ((84, 9), (64, 3)):
        theirs = vendored.ImpalaCNN(inshape=(hw, hw, cin), chans=(16, 32, 32), outsize=256,
                                    scale_ob=255.0, nblock=2)
        ours = Ours((cin, hw, hw))
        assert ours.dense.in_features == theirs.dense.in_features, (
            f"{hw}x{hw}: ours {ours.dense.in_features} vs reference {theirs.dense.in_features}")
    assert Ours((9, 84, 84)).dense.in_features == 32 * 11 * 11 == 3872


def test_initialisation_matches_the_reference_layer_for_layer(vendored):
    """A weight transplant is structurally BLIND to initialisation — and that is where PPG
    differs most from the other baselines here.

    Found by red-green: mutating `CnnDownStack.firstconv` to take the per-stack `scale` (the exact
    misreading `model.py` warns about — only the residual blocks receive it) left the transplant
    test **green**, because the transplant overwrites every weight before the forward pass. T1
    proves the arithmetic; it says nothing about the network you actually start training.

    So: build both under the same seed and require the tensors themselves to agree. This works
    because both constructors consume RNG in the same order (stacks in order, each `firstconv`
    then its blocks, then `dense`), which is itself a structural property worth pinning.
    """
    from rlgen.algos.ppg.model import ImpalaCNN as Ours

    torch.manual_seed(1234)
    theirs = vendored.ImpalaCNN(inshape=(84, 84, 9), chans=(16, 32, 32), outsize=256,
                                scale_ob=255.0, nblock=2)
    torch.manual_seed(1234)
    ours = Ours((9, 84, 84), chans=(16, 32, 32), outsize=256, nblock=2)

    t_sd, o_sd = theirs.state_dict(), ours.state_dict()
    assert set(t_sd) == set(o_sd), (
        f"module names diverged: only-theirs={sorted(set(t_sd) - set(o_sd))[:4]} "
        f"only-ours={sorted(set(o_sd) - set(t_sd))[:4]}")
    bad = [k for k in t_sd if not torch.allclose(t_sd[k], o_sd[k], atol=1e-6)]
    assert not bad, (
        f"{len(bad)} tensors initialise differently from the reference, e.g. {bad[:4]} — the "
        "init SCHEME diverges even though the forward arithmetic agrees")


def test_normed_init_is_the_references_scheme_not_xavier():
    """`NormedLinear`/`NormedConv2d` rescale each output unit's weight vector to norm `scale`.

    Guards against the specific error this module's docstring warns about: reaching for
    `ibac_sni`'s xavier init because both baselines run "an IMPALA CNN".
    """
    from rlgen.algos.ppg.model import NormedConv2d, NormedLinear
    torch.manual_seed(0)
    lin = NormedLinear(64, 32, scale=1.4)
    assert torch.allclose(lin.weight.norm(dim=1, p=2), torch.full((32,), 1.4), atol=1e-5)
    assert torch.count_nonzero(lin.bias) == 0
    conv = NormedConv2d(8, 16, 3, padding=1, scale=0.5)
    # `p=2` is not optional: without it `Tensor.norm` defaults to Frobenius, which routes a
    # 3-tuple `dim` into `linalg.matrix_norm` and raises "dim must be a 2-tuple". The reference
    # passes `p=2` (`torch_util.py:348`) and so does the port; an earlier version of THIS TEST
    # dropped it and failed, which is a test bug that reads exactly like a code bug.
    assert torch.allclose(conv.weight.norm(dim=(1, 2, 3), p=2), torch.full((16,), 0.5), atol=1e-5)


def test_policy_uses_two_independent_encoders(vendored):
    """`arch="dual"` is PPG's architecture, and a shared encoder is a different algorithm.

    Closes the "PPG dual-network gap" that `docs/FAITHFULNESS.md` carried against the discarded
    construction — asserted structurally, and by gradient isolation rather than by identity alone.
    """
    from rlgen.algos.ppg.model import PPGPolicy
    torch.manual_seed(0)
    p = PPGPolicy((9, 84, 84), 7)
    assert p.pi_enc is not p.vf_enc
    assert not (set(map(id, p.pi_enc.parameters())) & set(map(id, p.vf_enc.parameters())))

    obs = torch.randint(0, 256, (3, 9, 84, 84), dtype=torch.uint8)
    _pd, vpredtrue, _aux = p(obs)
    vpredtrue.sum().backward()
    assert all(q.grad is None or q.grad.abs().sum() == 0 for q in p.pi_enc.parameters()), (
        "the value head's gradient reached the POLICY encoder — the encoders are entangled and "
        "this is arch='shared', not PPG")
    assert any(q.grad is not None and q.grad.abs().sum() > 0 for q in p.vf_enc.parameters())
