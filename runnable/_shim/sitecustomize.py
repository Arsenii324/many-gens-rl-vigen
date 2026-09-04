"""Local-only shim: let CUDA-native original repos run on Apple MPS, changing zero repo lines.

Activated only when `RLGEN_MPS_AS_CUDA=1` and CUDA is genuinely absent. Python imports
`sitecustomize` automatically when it is on `PYTHONPATH`, so no launcher wrapper is needed and
nothing inside a cloned repo has to know this exists.

## Why this rather than patching the repos

`dmcontrol-generalization-benchmark` calls `.cuda()` at 22 sites across 7 files and asserts
`torch.cuda.is_available()`. Rewriting those to `.to(device)` is ~22 authored deviations bought
purely for local convenience — and the authoritative training runs go on a T4 (Kaggle /
DataSphere) where the originals run **unmodified**. So device adaptation belongs in our launcher,
not in their source.

## What this is NOT

**A smoke run under this shim does not prove the CUDA path works.** It proves the environment
integration works — env construction, wrapper stack, shapes, the training loop turning over. The
authoritative smoke for a baseline is on real CUDA. MPS also lacks float64, so any float64 tensor
a repo builds (e.g. `torch.tensor(np.log(x))`) will fail loudly here and succeed on T4; that
asymmetry is the shim's, not the repo's, and must not be "fixed" by editing the repo.
"""
import os

if os.environ.get("RLGEN_MPS_AS_CUDA") == "1":
    try:
        import torch

        if not torch.cuda.is_available() and torch.backends.mps.is_available():
            _DEV = torch.device("mps")

            torch.cuda.is_available = lambda: True
            torch.cuda.device_count = lambda: 1
            torch.cuda.current_device = lambda: 0
            torch.cuda.get_device_name = lambda *a, **k: "mps-as-cuda (shim)"
            # NOT aliases of torch.manual_seed: that function calls cuda.manual_seed_all
            # internally, so aliasing recurses infinitely. torch.manual_seed already seeds MPS.
            torch.cuda.manual_seed_all = lambda *a, **k: None
            torch.cuda.manual_seed = lambda *a, **k: None
            torch.cuda.empty_cache = lambda: None
            torch.cuda.synchronize = lambda *a, **k: torch.mps.synchronize()
            torch.cuda.set_device = lambda *a, **k: None

            # Legacy typed constructors: `torch.cuda.FloatTensor(size=shape).fill_(0.5)` is still
            # in use (idaac's algo/idaac.py:100). These are attributes of torch.cuda, so no
            # amount of device redirection reaches them -- they have to exist.
            def _typed(dtype):
                def make(*a, size=None, **k):
                    if size is None:
                        size = a[0] if len(a) == 1 and isinstance(
                            a[0], (tuple, list, torch.Size)) else a
                    return torch.empty(tuple(size), dtype=dtype, device=_DEV)
                return make

            for _n, _dt in (("FloatTensor", torch.float32), ("DoubleTensor", torch.float32),
                            ("HalfTensor", torch.float16), ("LongTensor", torch.int64),
                            ("IntTensor", torch.int32), ("ByteTensor", torch.uint8),
                            ("BoolTensor", torch.bool)):
                setattr(torch.cuda, _n, _typed(_dt))
            # DoubleTensor deliberately maps to float32, not float64: MPS has no float64 at all,
            # so the alternative is a hard failure. Same announced asymmetry as `_to` below.

            def _to_mps(self, *a, **k):
                return self.to(_DEV)

            torch.Tensor.cuda = _to_mps
            torch.nn.Module.cuda = _to_mps

            # NOT replacing `torch.device` itself: PyTorch uses it as a TYPE in isinstance
            # checks and in `get_device_module`, and substituting a class broke both. Only the
            # string form is intercepted, below, which is what these repos actually use.
            _orig_to = torch.Tensor.to

            _warned = set()

            def _announce_f64():
                if "f64" not in _warned:
                    _warned.add("f64")
                    print("[mps-as-cuda shim] downcasting float64 -> float32 for MPS; "
                          "the CUDA path keeps float64. Local runs differ here.")

            def _is_cuda_arg(x):
                # Both forms occur: `.to('cuda')` and `.to(torch.device('cuda'))`. Intercepting
                # only the string form let ALDA through to `Torch not compiled with CUDA enabled`.
                if isinstance(x, str):
                    return x.startswith("cuda")
                return isinstance(x, torch.device) and x.type == "cuda"

            def _to(self, *a, **k):
                if a and _is_cuda_arg(a[0]):
                    a = (_DEV,) + a[1:]
                if _is_cuda_arg(k.get("device")):
                    k = {**k, "device": _DEV}
                # MPS has no float64. The originals legitimately build float64 tensors --
                # `torch.tensor(np.log(x))` is float64 because np.log returns np.float64 -- and
                # those work on CUDA. Downcast HERE so the repo stays untouched and the T4 path
                # keeps its float64. Announced once per dtype-bearing site, never silent: this
                # is a real numerical difference between the local run and the real one.
                if self.dtype == torch.float64:
                    tgt = a[0] if a else k.get("device")
                    if tgt is not None and getattr(torch.device(str(tgt)), "type", "") in ("mps",):
                        _announce_f64()
                        self = _orig_to(self, torch.float32)
                return _orig_to(self, *a, **k)

            torch.Tensor.to = _to

            # Factory functions take `device=` directly and never go through Tensor.to, so
            # `torch.as_tensor(obs, device=torch.device('cuda'))` -- RL-ViGen's svea.py:206 --
            # reaches CUDA's lazy init and dies while every `.to('cuda')` in the same file works.
            # Same redirection, same float64 downcast, same announcement.
            def _wrap_factory(fn):
                def wrapped(*a, **k):
                    if not _is_cuda_arg(k.get("device")):
                        return fn(*a, **k)
                    k = {**k, "device": _DEV}
                    if k.get("dtype") == torch.float64:
                        k["dtype"] = torch.float32
                        _announce_f64()
                    try:
                        out = fn(*a, **k)
                    except TypeError as exc:
                        # `torch.tensor(np.log(3.0), device='cuda')` infers float64 from the
                        # DATA, so the rejection happens inside the call and there is no output
                        # to inspect. Retry with an explicit float32 rather than pre-scanning
                        # arbitrary inputs. Narrow on purpose: any other TypeError propagates.
                        if "float64" not in str(exc):
                            raise
                        _announce_f64()
                        out = fn(*a, **{**k, "dtype": torch.float32})
                    if getattr(out, "dtype", None) == torch.float64:
                        _announce_f64()
                        out = out.float()
                    return out
                return wrapped

            # TorchScript resolves torch.* builtins BY OBJECT IDENTITY. Replacing them with
            # python functions makes that lookup miss, so `@torch.jit.script` falls back to
            # compiling the wrapper -- and a `(*a, **k)` signature is exactly what TorchScript
            # refuses: "Compiled functions can't take variable number of arguments". kornia does
            # `@torch.jit.script` at import time, so this broke SODA and RAD at `import kornia`,
            # silently, in a shim written for a different baseline. Copying each original's
            # builtin-table entry onto the wrapper makes TorchScript treat it as the op it wraps.
            try:
                from torch.jit._builtins import _get_builtin_table
                _btbl = _get_builtin_table()
            except Exception:
                _btbl = None

            for _n in ("tensor", "as_tensor", "zeros", "ones", "empty", "full", "arange",
                       "randn", "rand", "randint", "randperm", "eye", "linspace", "logspace",
                       "zeros_like", "ones_like", "empty_like", "full_like", "randn_like",
                       "rand_like"):
                if not hasattr(torch, _n):
                    continue
                _orig_fn = getattr(torch, _n)
                _new_fn = _wrap_factory(_orig_fn)
                if _btbl is not None and id(_orig_fn) in _btbl:
                    _btbl[id(_new_fn)] = _btbl[id(_orig_fn)]
                setattr(torch, _n, _new_fn)

            # Repos guard GPU-only kernels with `assert x.is_cuda`. Under the shim an MPS tensor
            # IS the accelerator tensor, so the guard must pass. Patched here, not in their source.
            torch.Tensor.is_cuda = property(
                lambda self: self.device.type in ("cuda", "mps"))
    except Exception as _shim_exc:
        # Deliberately does not re-raise: the shim is a LOCAL convenience, the authoritative runs
        # are on CUDA where none of this executes, and killing a local run over it would trade a
        # working smoke test for nothing. But it must not be silent either. The block above is
        # not atomic -- it rewrites ~20 torch builtins in a loop and then patches `is_cuda` -- so
        # a fault partway through leaves a HALF-applied shim: some constructors downcast float64
        # and some do not, which is a far worse state to debug than either extreme, and the
        # numbers it produces are not the ones any consistent configuration would produce.
        #
        # `pass` here was flagged by an independent audit as the same instinct
        # `docs/REGISTER.md:106` already names: making the harness cope with an awkward
        # dependency instead of making the awkwardness visible.
        import sys as _sys
        import traceback as _tb
        print("[mps-as-cuda shim] PARTIALLY APPLIED -- setup raised and was swallowed so the run "
              "could continue.\n"
              "[mps-as-cuda shim] Some torch constructors may downcast float64 and others may "
              "not. Treat any number from this run as suspect until the cause below is fixed.\n"
              f"[mps-as-cuda shim] {type(_shim_exc).__name__}: {_shim_exc}",
              file=_sys.stderr)
        _tb.print_exc(file=_sys.stderr)
