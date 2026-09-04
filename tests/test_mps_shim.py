"""The MPS shim is shared by several baselines, so a change made for one can break another.

That is not hypothetical. `runnable/_shim/sitecustomize.py` gained a device-remapping wrapper
around torch's factory functions because RL-ViGen's `svea.py` calls
`torch.as_tensor(obs, device='cuda')`, which never goes through `Tensor.to` and so was not
intercepted. The wrapper's `(*a, **k)` signature then broke `import kornia` — kornia runs
`@torch.jit.script` at import time, TorchScript resolves `torch.*` builtins by object identity,
missed on the replaced objects, fell back to compiling the wrapper, and refused it with
"Compiled functions can't take variable number of arguments". SODA and RAD import kornia. Both
had been green minutes earlier; the shim edit was made for a third baseline and broke them
silently until they were re-run.

These tests run the shim in a SUBPROCESS with `RLGEN_MPS_AS_CUDA=1`, because the shim mutates
the torch namespace process-wide and must never do that to the test session itself.

They are skipped where MPS is absent — which includes every CI box and Kaggle. That is a real
limit: on those machines this file proves nothing, and the shim is not exercised there anyway.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHIM = ROOT / "runnable" / "_shim"


def _has_mps() -> bool:
    try:
        import torch
        return torch.backends.mps.is_available() and not torch.cuda.is_available()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _has_mps(), reason="shim only activates where MPS is present and CUDA is not")


def run_under_shim(code: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "RLGEN_MPS_AS_CUDA": "1", "PYTHONPATH": str(SHIM)}
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          env=env, timeout=600)


def test_kornia_still_imports_under_the_shim():
    """The exact regression above. kornia is imported by dmc_gb's augmentations path."""
    r = run_under_shim("import kornia; print('OK', kornia.__version__)")
    assert "OK" in r.stdout, (
        "importing kornia under the shim failed -- if this is a TorchScript "
        "NotSupportedError about variable arguments, a torch.* replacement lost its "
        f"builtin-table entry.\nstdout: {r.stdout[-2000:]}\nstderr: {r.stderr[-3000:]}")


def test_factory_functions_redirect_cuda_to_mps_without_losing_dtype():
    """svea's `torch.as_tensor(obs, device='cuda')` must land on MPS, as float32.

    Both spellings are checked: the string 'cuda' and a torch.device object. Intercepting only
    the string form is a mistake this shim has already made once, in Tensor.to.
    """
    r = run_under_shim(
        "import torch, numpy as np\n"
        "a = torch.as_tensor(np.zeros((2, 3), dtype=np.float32), device='cuda')\n"
        "b = torch.zeros(2, 2, device=torch.device('cuda'))\n"
        "c = torch.tensor(np.log(3.0), device='cuda')\n"   # np.log gives float64; MPS has none
        "print('DEV', a.device.type, b.device.type, c.device.type, 'DT', a.dtype, c.dtype)\n")
    assert "DEV mps mps mps" in r.stdout, f"{r.stdout[-2000:]}\n{r.stderr[-2000:]}"
    assert "torch.float32 torch.float32" in r.stdout, (
        "float64 must be downcast for MPS, and it must be the float32 the CUDA path would NOT "
        f"have used -- that asymmetry is announced, not silent.\n{r.stdout[-2000:]}")


def test_shim_is_inert_when_not_asked_for():
    """No env var, no mutation. The shim sits on PYTHONPATH for launchers that do not want it."""
    env = {**os.environ, "PYTHONPATH": str(SHIM)}
    env.pop("RLGEN_MPS_AS_CUDA", None)
    r = subprocess.run(
        [sys.executable, "-c",
         "import torch; print('AVAIL', torch.cuda.is_available())"],
        capture_output=True, text=True, env=env, timeout=300)
    assert "AVAIL False" in r.stdout, (
        f"the shim activated without RLGEN_MPS_AS_CUDA=1\n{r.stdout}\n{r.stderr[-1000:]}")


# -- per-symbol coverage of the patched surface -------------------------------------------------
#
# docs/CONSTRUCTION.md C39. An independent review counted the shim's patched surface at roughly 35
# points -- ~15 named symbols, 7 legacy typed constructors and ~20 wrapped tensor factories --
# against the three tests above. Those three cover the two regressions the shim has actually had;
# they do not cover the surface.
#
# One subprocess enumerates every patched point and prints a verdict per name; the tests below
# assert over that. Doing it the obvious way -- a subprocess per symbol -- would cost ~35 process
# starts, and this file's own docstring records that the shim must run in a subprocess because it
# mutates the torch namespace process-wide. So: one process, many named assertions.

SURFACE_PROBE = r"""
import torch, numpy as np
def emit(name, ok, detail=""):
    print(f"CHECK\t{name}\t{'ok' if ok else 'FAIL'}\t{detail}")

# 1. torch.cuda.* -- the availability lies the repos' `assert` guards depend on
emit("cuda.is_available", torch.cuda.is_available() is True)
emit("cuda.device_count", torch.cuda.device_count() == 1)
emit("cuda.current_device", torch.cuda.current_device() == 0)
emit("cuda.get_device_name", "mps" in torch.cuda.get_device_name(0).lower(),
     torch.cuda.get_device_name(0))
for fn in ("empty_cache", "synchronize", "set_device", "manual_seed", "manual_seed_all"):
    try:
        getattr(torch.cuda, fn)(0) if fn == "set_device" else getattr(torch.cuda, fn)()
        emit(f"cuda.{fn}", True)
    except Exception as e:
        emit(f"cuda.{fn}", False, f"{type(e).__name__}: {e}")

# manual_seed must NOT be an alias of torch.manual_seed: that recurses into cuda.manual_seed_all.
try:
    torch.manual_seed(0); emit("no_seed_recursion", True)
except RecursionError as e:
    emit("no_seed_recursion", False, "torch.manual_seed recursed")

# 2. legacy typed constructors. DoubleTensor -> float32 is DELIBERATE: MPS has no float64 at all,
#    so the alternative is a hard failure. Asserted so the substitution stays visible.
for name, want in (("FloatTensor", torch.float32), ("DoubleTensor", torch.float32),
                   ("HalfTensor", torch.float16), ("LongTensor", torch.int64),
                   ("IntTensor", torch.int32), ("ByteTensor", torch.uint8),
                   ("BoolTensor", torch.bool)):
    try:
        t = getattr(torch.cuda, name)((2, 2))
        emit(f"typed.{name}", t.dtype == want and t.device.type == "mps",
             f"{t.dtype} on {t.device.type}")
    except Exception as e:
        emit(f"typed.{name}", False, f"{type(e).__name__}: {e}")

# 3. device redirection, both spellings, tensor and module
try:
    emit("Tensor.cuda", torch.zeros(2).cuda().device.type == "mps")
    emit("Module.cuda", next(torch.nn.Linear(2, 2).cuda().parameters()).device.type == "mps")
    emit("Tensor.to.str", torch.zeros(2).to("cuda").device.type == "mps")
    emit("Tensor.to.device", torch.zeros(2).to(torch.device("cuda")).device.type == "mps")
    emit("Tensor.is_cuda", torch.zeros(2).to("mps").is_cuda is True)
except Exception as e:
    emit("device_redirect", False, f"{type(e).__name__}: {e}")

# 4. the ~20 wrapped factories: float64 in, float32 out, on the accelerator
FACTORIES = ["tensor", "as_tensor", "zeros", "ones", "empty", "full", "arange", "randn", "rand",
             "randint", "randperm", "eye", "linspace", "logspace", "zeros_like", "ones_like",
             "empty_like", "full_like", "randn_like", "rand_like"]
base = torch.zeros(4, dtype=torch.float64)
for fn in FACTORIES:
    try:
        f = getattr(torch, fn)
        if fn in ("tensor", "as_tensor"):
            t = f(np.zeros(4, dtype=np.float64), device="cuda")
        elif fn == "full_like":
            t = f(base.to("cuda"), 1.0)
        elif fn.endswith("_like"):
            t = f(base.to("cuda"))
        elif fn == "full":
            t = f((2, 2), np.float64(1.0), device="cuda")
        elif fn == "arange":
            t = f(0, 4, dtype=torch.float64, device="cuda")
        elif fn in ("linspace", "logspace"):
            t = f(0, 1, 4, dtype=torch.float64, device="cuda")
        elif fn in ("randint",):
            t = f(0, 5, (2, 2), device="cuda")
        elif fn == "randperm":
            t = f(4, device="cuda")
        elif fn == "eye":
            t = f(3, dtype=torch.float64, device="cuda")
        else:
            t = f(4, dtype=torch.float64, device="cuda")
        ok = t.device.type == "mps" and t.dtype != torch.float64
        emit(f"factory.{fn}", ok, f"{t.dtype} on {t.device.type}")
    except Exception as e:
        emit(f"factory.{fn}", False, f"{type(e).__name__}: {e}")
"""


@pytest.fixture(scope="module")
def surface():
    """{name: (ok, detail)} from a single shimmed subprocess."""
    r = run_under_shim(SURFACE_PROBE)
    rows = {}
    for line in r.stdout.splitlines():
        if line.startswith("CHECK\t"):
            _, name, verdict, *rest = line.split("\t")
            rows[name] = (verdict == "ok", rest[0] if rest else "")
    assert rows, ("the surface probe produced no CHECK lines, so nothing was verified.\n"
                  f"stdout: {r.stdout[-1500:]}\nstderr: {r.stderr[-2500:]}")
    return rows


def _names(prefix):
    return [n for n in (
        "cuda.is_available cuda.device_count cuda.current_device cuda.get_device_name "
        "cuda.empty_cache cuda.synchronize cuda.set_device cuda.manual_seed cuda.manual_seed_all "
        "no_seed_recursion "
        "typed.FloatTensor typed.DoubleTensor typed.HalfTensor typed.LongTensor typed.IntTensor "
        "typed.ByteTensor typed.BoolTensor "
        "Tensor.cuda Module.cuda Tensor.to.str Tensor.to.device Tensor.is_cuda "
        "factory.tensor factory.as_tensor factory.zeros factory.ones factory.empty factory.full "
        "factory.arange factory.randn factory.rand factory.randint factory.randperm factory.eye "
        "factory.linspace factory.logspace factory.zeros_like factory.ones_like "
        "factory.empty_like factory.full_like factory.randn_like factory.rand_like"
    ).split() if n.startswith(prefix)]


#: Wrapped by the shim, but the MPS BACKEND cannot execute it. Verified not to be a shim defect:
#: `torch.logspace(..., device="mps")` raises the identical NotImplementedError with the shim
#: absent. Recorded rather than skipped, because "the shim is fine here and the platform is not"
#: is a different statement from "this works", and because PYTORCH_ENABLE_MPS_FALLBACK is unset
#: (docs/CONSTRUCTION.md C39) so it RAISES rather than quietly running on CPU. No baseline calls
#: it -- grepped across `runnable/` and RL-ViGen's `algos/` -- so it is inert today. If one ever
#: does, this entry is the note that says the failure will be loud and is not ours.
MPS_UNIMPLEMENTED = {"factory.logspace": "aten::logspace.out has no MPS kernel"}


@pytest.mark.parametrize("name", _names(""))
def test_patched_symbol_behaves(surface, name):
    """Each patched point, named, so a failure says which one rather than 'the shim broke'."""
    assert name in surface, (
        f"{name} produced no verdict -- the probe did not reach it, which usually means an "
        "earlier check raised. A missing verdict is not a pass.")
    ok, detail = surface[name]
    if name in MPS_UNIMPLEMENTED:
        assert not ok, (
            f"{name} now WORKS on MPS ({detail}). That is good news and this entry is stale: "
            f"it was recorded as a backend limitation ({MPS_UNIMPLEMENTED[name]}). Remove it "
            "from MPS_UNIMPLEMENTED so the symbol is held to the normal contract again.")
        assert "NotImplementedError" in detail, (
            f"{name} fails for a DIFFERENT reason than the recorded backend limitation "
            f"({MPS_UNIMPLEMENTED[name]}): {detail}. That would be a shim defect wearing a "
            "known-limitation label.")
        return
    assert ok, f"{name} misbehaves under the shim: {detail}"
