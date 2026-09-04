"""Expose `third_party/alda/models` as the top-level package `models`, and nothing else.

ALDA's trainer does `from models.sac import Actor, Critic, ...`. The obvious way to satisfy that
is to put `third_party/alda` on PYTHONPATH — and that breaks ALDA, because `third_party/alda`
also contains a `trainers/` directory which is a REGULAR package, while ALDA's own `trainers/` is
a NAMESPACE package, and Python prefers the regular one regardless of path order. The trainer
would then import a different `trainers` than the one being run.

This was previously solved with a directory containing a symlink `models -> …/third_party/alda/
models`. That works locally and **does not ship**: the symlink was absolute, and the payload
builder wrote no entry for it at all, so on the container the declared PYTHONPATH entry
`runnable/_shim/alda_models` did not exist and the import gate failed with `No module named
'models'` — job bt18fm6ds7a1kpetgqpe, after it had successfully got past everything else.

So this is a real file that ships, and it re-points the package's `__path__` at the real
directory. Submodules (`models.sac`) then load from `third_party/alda/models/sac.py` while
`third_party/alda` itself never joins `sys.path`, which is the whole point. Upstream's own
`models/__init__.py` is empty (0 bytes), so nothing of theirs is skipped by not executing it; if
that ever changes, this file must exec it rather than shadow it.
"""
import pathlib

_here = pathlib.Path(__file__).resolve()
_real = _here.parents[4] / "third_party" / "alda" / "models"
if not _real.is_dir():  # fail where the cause is visible, not at the first `from models.sac`
    raise ImportError(
        f"the alda models shim expected {_real} and it is not there; "
        "third_party/alda/models must be a payload member for this family")
__path__ = [str(_real)]
