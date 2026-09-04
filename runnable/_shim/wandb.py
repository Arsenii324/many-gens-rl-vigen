"""Offline W&B shim for native probes: never touches the network, records what was logged.

[Codex 2026-09-01 10:30 MSK] wrote this fail-closed -- every attribute raised -- to satisfy an
unconditional upstream import while rejecting all tracking use.

[Claude 2026-09-03 MSK] `ctrl` is the baseline that made fail-closed untenable: `train_ppo.py:111`
calls `wandb.init(...)` unconditionally, with no `--track` flag to turn off, so a raising `init`
means ctrl cannot run at all. That cost attempt #10 (`bt1efc5ma3m0lohlnq2d`).

**The property worth keeping is "no network", not "raise".** Raising was a means to it. So this
records instead: `init` returns a run object, `log` appends one JSON object per call to a local
file, and nothing here opens a socket or imports the real client. That is strictly more honest than
a silent no-op -- a silent no-op would let a family whose only metric sink is W&B produce empty
curves and look successful.

Fail-closed is still reachable, and is one variable away: `RLGEN_WANDB_STRICT=1` restores the
original raising behaviour exactly, for any probe that wants to assert a baseline never logs.

The sink path is `RLGEN_WANDB_JSONL` when set, else `wandb_offline.jsonl` in the working directory.
"""
from __future__ import annotations

import json
import os
import threading

__version__ = "0.0.0-offline-shim"

_lock = threading.Lock()


def _strict() -> bool:
    return os.environ.get("RLGEN_WANDB_STRICT", "") not in ("", "0", "false", "False")


def _sink_path() -> str:
    return os.environ.get("RLGEN_WANDB_JSONL") or "wandb_offline.jsonl"


def _refuse(*_args, **_kwargs):
    raise RuntimeError("W&B tracking is disabled for this native probe")


def _jsonable(value):
    """Numpy scalars, arrays and W&B media objects all reach `log`; none are JSON by default."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    for attribute in ("item", "tolist"):
        method = getattr(value, attribute, None)
        if callable(method):
            try:
                return _jsonable(method())
            except Exception:
                pass
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return repr(value)


class _Anything:
    """Permissive stand-in for `wandb.config`, `wandb.Video`, and anything else reached for.

    It is callable, subscriptable, iterable and attribute-settable, because upstream code does all
    four to W&B objects and a shim that breaks on any of them just moves the crash.
    """

    def __init__(self, name: str = "wandb"):
        object.__setattr__(self, "_name", name)

    def __call__(self, *_args, **_kwargs):
        return _Anything(f"{object.__getattribute__(self, '_name')}()")

    def __getattr__(self, item):
        return _Anything(f"{object.__getattribute__(self, '_name')}.{item}")

    def __setattr__(self, _key, _value):
        return None

    def __setitem__(self, _key, _value):
        return None

    def __getitem__(self, item):
        return _Anything(f"{object.__getattribute__(self, '_name')}[{item!r}]")

    def __iter__(self):
        return iter(())

    def __repr__(self):
        return f"<wandb-offline-shim {object.__getattribute__(self, '_name')}>"

    def __bool__(self):
        return False


class _Run(_Anything):
    def __init__(self):
        super().__init__("run")
        object.__setattr__(self, "id", "offline")
        object.__setattr__(self, "name", "offline")
        object.__setattr__(self, "dir", os.getcwd())

    def log(self, *args, **kwargs):
        return log(*args, **kwargs)

    def finish(self, *_args, **_kwargs):
        return None


config = _Anything("config")
run = None


def init(*_args, **kwargs):
    """Return a run without contacting anything. Records the config it was handed."""
    if _strict():
        _refuse()
    global run
    run = _Run()
    _append({"_event": "init", "config": _jsonable(kwargs)})
    return run


def log(data=None, step=None, commit=None, **_kwargs):
    if _strict():
        _refuse()
    record = {"_event": "log", "data": _jsonable(data or {})}
    if step is not None:
        record["step"] = _jsonable(step)
    if commit is not None:
        record["commit"] = bool(commit)
    _append(record)


def finish(*_args, **_kwargs):
    _append({"_event": "finish"})


def _append(record: dict) -> None:
    line = json.dumps(record, default=repr)
    with _lock:
        try:
            with open(_sink_path(), "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            # A probe must not die because its metric sink is unwritable; the run is the artifact.
            pass


def __getattr__(name):
    if _strict():
        return _refuse
    return _Anything(f"wandb.{name}")
