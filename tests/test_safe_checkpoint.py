"""A multi-hour training run must not die to a full disk, or corrupt its own checkpoint on a torn
write. Every family's checkpoint-save call now goes through `runnable/_shim/safe_checkpoint.py`;
this tests the shared module's four load-bearing properties, plus that every real call site was
actually rewired rather than merely having a helper written and left unused.
"""
import importlib.util
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHIM = ROOT / "runnable" / "_shim"


def _sc():
    spec = importlib.util.spec_from_file_location("safe_checkpoint", SHIM / "safe_checkpoint.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["safe_checkpoint"] = m
    spec.loader.exec_module(m)
    return m


def test_a_normal_write_lands(tmp_path):
    sc = _sc()
    p = tmp_path / "ckpt.pt"
    assert sc.safe_write(p, lambda tmp: pathlib.Path(tmp).write_text("hello"))
    assert p.read_text() == "hello"


def test_a_failed_write_does_not_corrupt_the_previous_checkpoint(tmp_path):
    """The property that matters most: a torn write must never destroy the last GOOD checkpoint,
    because that file is exactly what a resume or an evaluator loads next."""
    sc = _sc()
    p = tmp_path / "ckpt.pt"
    p.write_text("GOOD")

    def _boom(tmp):
        pathlib.Path(tmp).write_text("partial garbage")
        raise RuntimeError("disk exploded mid-write")

    assert sc.safe_write(p, _boom) is False
    assert p.read_text() == "GOOD", "a failed write corrupted the previous checkpoint"
    assert not (p.parent / (p.name + ".tmp-writing")).exists(), "a temp file was left behind"


def test_insufficient_disk_waits_then_skips_without_raising(tmp_path):
    sc = _sc()
    p = tmp_path / "ckpt.pt"
    p.write_text("STILL GOOD")
    result = sc.safe_write(p, lambda tmp: pathlib.Path(tmp).write_text("never"),
                           min_free_bytes=1 << 62, max_wait_seconds=1, poll_seconds=1)
    assert result is False
    assert p.read_text() == "STILL GOOD"


def test_torch_save_wrapper_round_trips_and_forwards_kwargs(tmp_path):
    sc = _sc()
    p = tmp_path / "t.pt"
    tensor = torch.arange(5)
    assert sc.safe_torch_save(tensor, p, torch_kwargs={"pickle_protocol": -1})
    assert torch.equal(torch.load(p, weights_only=False), tensor)


#: One call site per family that writes a checkpoint. Verified against the file, not assumed --
#: every one of these was a bare `torch.save`/`th.save`/raw `open().write()` before tonight.
CALL_SITES = {
    "rlvigen": ("RL-ViGen-upstream/train.py", "safe_torch_save(payload, snapshot"),
    "rlvigen_stamped": ("RL-ViGen-upstream/train.py", "safe_torch_save(payload, stamped"),
    "dmc_gb_terminal": ("runnable/dmc_gb/src/train.py", "safe_torch_save(agent, terminal_checkpoint"),
    "dmc_gb_periodic": ("runnable/dmc_gb/src/train.py", "safe_torch_save(agent, os.path.join(model_dir"),
    "idaac_final": ("runnable/idaac/train.py", "safe_torch_save(_payload,"),
    "ibac_sni_model": ("runnable/ibac_sni/torch_rl/utils/save.py", "safe_torch_save(model, path"),
    "ibac_sni_stamped": ("runnable/ibac_sni/torch_rl/scripts/train.py", "safe_torch_save(acmodel,"),
    "alda": ("runnable/alda/trainers/alda_trainer.py", "safe_torch_save("),
    "ppg": ("runnable/ppg/phasic_policy_gradient/log_save_helper.py", "safe_torch_save(self.model"),
    "ctrl": ("runnable/ctrl/train_ppo.py", "safe_write(os.path.join(_dir"),
}


@pytest.mark.parametrize("name", sorted(CALL_SITES))
def test_every_family_checkpoint_site_is_wired(name):
    relpath, needle = CALL_SITES[name]
    text = (ROOT / relpath).read_text()
    assert needle in text, f"{name}: {relpath!r} does not call through safe_checkpoint at all"


@pytest.mark.parametrize("relpath,forbidden", [
    ("runnable/dmc_gb/src/train.py", "torch.save(agent, terminal_checkpoint)"),
    ("runnable/dmc_gb/src/train.py", "torch.save(agent, os.path.join(model_dir"),
    ("runnable/idaac/train.py", "torch.save(_payload,"),
    ("runnable/ibac_sni/torch_rl/utils/save.py", "torch.save(model, path)"),
    ("runnable/alda/trainers/alda_trainer.py", "torch.save(\n"),
    ("runnable/ppg/phasic_policy_gradient/log_save_helper.py", "th.save(self.model,"),
    ("RL-ViGen-upstream/train.py", "torch.save(payload, f)"),
])
def test_the_bare_unsafe_call_is_actually_gone(relpath, forbidden):
    """Guards against a partial edit: the safe call being ADDED without the bare one being removed,
    which would leave the file calling torch.save twice or shadow the fix silently."""
    text = (ROOT / relpath).read_text()
    assert forbidden not in text, f"{relpath}: the original unsafe call is still present"


def test_shim_is_on_every_familys_pythonpath():
    """ibac_sni and ppg did not have `_shim` on PYTHONPATH before tonight; the other five already
    did. All seven must now, or `import safe_checkpoint` fails at the first checkpoint write."""
    launchers = {
        "rlvigen": "runnable/_launch/rlvigen.sh",
        "dmc_gb": "runnable/_launch/dmc_gb.sh",
        "alda": "runnable/_launch/alda.sh",
        "ctrl": "runnable/_launch/ctrl.sh",
        "idaac": "runnable/_launch/idaac.sh",
        "ppg": "runnable/_launch/ppg.sh",
        "ppg_cell": "runnable/_launch/ppg_cell.sh",
        "ibac_sni": "runnable/_launch/ibac_sni.sh",
        "ibac_sni_cell": "runnable/_launch/ibac_sni_cell.sh",
    }
    missing = [name for name, path in launchers.items()
              if "runnable/_shim" not in (ROOT / path).read_text()]
    assert not missing, f"these launchers do not put _shim on PYTHONPATH: {missing}"


#: Every real call site wraps its import in try/except ImportError, falling back to plain
#: torch.save. Two real bugs escaped detection before this test existed: a keyword collision that
#: crashed on every real call (caught only by a remote job), and a missing PYTHONPATH entry in a
#: test harness (caught only by running the FULL suite, not the narrow safe_checkpoint file). Both
#: are the same class of gap: testing the module in isolation, never as its real callers actually
#: invoke it. This test drives every site's fallback definition directly.
FALLBACK_SITES = {
    "rlvigen": "RL-ViGen-upstream/train.py",
    "idaac": "runnable/idaac/train.py",
    "alda": "runnable/alda/trainers/alda_trainer.py",
    "ibac_sni_save": "runnable/ibac_sni/torch_rl/utils/save.py",
    "ibac_sni_train": "runnable/ibac_sni/torch_rl/scripts/train.py",
    "dmc_gb_terminal": "runnable/dmc_gb/src/train.py",
    "dmc_gb_periodic": "runnable/dmc_gb/src/train.py",
    "ppg": "runnable/ppg/phasic_policy_gradient/log_save_helper.py",
    "ctrl": "runnable/ctrl/train_ppo.py",
}


@pytest.mark.parametrize("name", sorted(FALLBACK_SITES))
def test_every_site_wraps_the_import_in_try_except_importerror(name):
    """A missing `_shim` on PYTHONPATH -- exactly what happened in the dmc_gb finalizer test
    before this was added -- must degrade to plain torch.save, never crash the caller.

    Counting `except ImportError:` occurrences globally in the file (the original version of this
    test) is a false-negative trap: a file with unrelated import guards elsewhere (numpy/torch
    compat shims, which idaac and ibac_sni both have) can have MORE except-ImportError blocks than
    safe_checkpoint imports while one of those imports is still genuinely unguarded -- exactly what
    happened when TERMINAL_MAX_WAIT_SECONDS was added as a second, separate import statement at
    four of five sites. Checked precisely now: every `from safe_checkpoint import` line must be
    directly preceded by its OWN `try:` line, not merely coexist with guards somewhere in the file.
    """
    lines = (ROOT / FALLBACK_SITES[name]).read_text().splitlines()
    import_lines = [i for i, l in enumerate(lines) if "from safe_checkpoint import" in l]
    assert import_lines, f"{name}: no safe_checkpoint import found at all"
    unguarded = [i for i in import_lines if lines[i - 1].strip() != "try:"]
    assert not unguarded, (
        f"{name}: import(s) not directly preceded by their own try: -- "
        + "; ".join(f"line {i + 1}: {lines[i].strip()!r} (preceded by {lines[i-1].strip()!r})"
                    for i in unguarded))


def test_the_fallback_actually_works_when_the_real_module_is_absent(tmp_path, monkeypatch):
    """Execute a representative fallback definition with `safe_checkpoint` genuinely unimportable,
    confirming the degraded path still writes a real, loadable file rather than merely not
    crashing."""
    import sys
    blocked = {"safe_checkpoint"}
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def guarded_import(name, *args, **kwargs):
        if name in blocked:
            raise ImportError(f"{name} deliberately blocked for this test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded_import)
    sys.modules.pop("safe_checkpoint", None)

    namespace = {}
    exec(
        "try:\n"
        "    from safe_checkpoint import safe_torch_save\n"
        "except ImportError:\n"
        "    def safe_torch_save(obj, path, torch_kwargs=None, **_kwargs):\n"
        "        import torch as _torch\n"
        "        _torch.save(obj, path, **(torch_kwargs or {}))\n"
        "        return True\n",
        namespace,
    )
    p = tmp_path / "fallback.pt"
    assert namespace["safe_torch_save"](torch.arange(4), p, label="irrelevant") is True
    assert torch.equal(torch.load(p, weights_only=False), torch.arange(4))


def test_safe_torch_save_accepts_an_explicit_label_without_colliding(tmp_path):
    """The bug caught live on a real remote job: `safe_torch_save` hardcoded `label="torch.save"`
    while ALSO forwarding a caller's own `label=...` through **kwargs, so `TypeError: got multiple
    values for keyword argument 'label'` fired on every call site that passed one -- which was all
    eleven of them. This is the exact call shape every real site uses.
    """
    sc = _sc()
    p = tmp_path / "t.pt"
    assert sc.safe_torch_save(torch.arange(2), p, label="alda.checkpoint")
    assert sc.safe_torch_save(torch.arange(2), p, label="ctrl.checkpoint", torch_kwargs={})


def test_a_small_known_size_needs_far_less_than_the_flat_default(tmp_path):
    """The gap the user named directly: a flat multi-GiB margin can starve a checkpoint that would
    easily fit. With `expected_bytes` known, the threshold scales to the object, not the host."""
    sc = _sc()
    p = tmp_path / "t.pt"
    tiny = 1024  # 1 KiB
    # A margin demanding more than ~3 KiB (SIZE_SAFETY_FACTOR x tiny) would starve this on a host
    # with, say, 500 MB free -- comfortably below DEFAULT_MIN_FREE_BYTES (2 GiB) but nowhere near
    # a real constraint for a 1 KiB object.
    result = sc.safe_write(p, lambda tmp: pathlib.Path(tmp).write_bytes(b"x" * tiny),
                           expected_bytes=tiny, min_free_bytes=None,
                           max_wait_seconds=0, poll_seconds=1)
    assert result is True, "a tiny known-size object was starved by an oversized default margin"
    needed = sc.MIN_MARGIN_FLOOR_BYTES  # the computed threshold for a tiny object is the floor
    assert needed < sc.DEFAULT_MIN_FREE_BYTES, "the floor should be well below the flat default"


def test_force_env_var_bypasses_the_disk_check_entirely(tmp_path, monkeypatch):
    sc = _sc()
    monkeypatch.setenv("SAFE_CHECKPOINT_FORCE", "1")
    p = tmp_path / "ckpt.pt"
    # An impossible threshold -- would hang/skip without the force flag.
    result = sc.safe_write(p, lambda tmp: pathlib.Path(tmp).write_text("ok"),
                           min_free_bytes=1 << 62, max_wait_seconds=0)
    assert result is True and p.read_text() == "ok"


def test_min_free_bytes_env_override_wins_over_everything(tmp_path, monkeypatch):
    """An operator's environment override must win over both the caller's own min_free_bytes and
    over expected_bytes-derived sizing -- it exists specifically to correct the machine's own
    judgment without a code change on a running job."""
    sc = _sc()
    monkeypatch.setenv("SAFE_CHECKPOINT_MIN_FREE_BYTES", "1")  # trivially satisfiable
    p = tmp_path / "ckpt.pt"
    result = sc.safe_write(p, lambda tmp: pathlib.Path(tmp).write_text("ok"),
                           min_free_bytes=1 << 62,  # would otherwise starve forever
                           expected_bytes=1 << 62, max_wait_seconds=0)
    assert result is True and p.read_text() == "ok"


def test_a_malformed_env_override_is_ignored_not_fatal(tmp_path, monkeypatch):
    sc = _sc()
    monkeypatch.setenv("SAFE_CHECKPOINT_MIN_FREE_BYTES", "not-a-number")
    p = tmp_path / "ckpt.pt"
    result = sc.safe_write(p, lambda tmp: pathlib.Path(tmp).write_text("ok"))
    assert result is True, "a malformed env var must not crash the write"


def test_torch_save_computes_expected_bytes_from_the_real_serialized_size(tmp_path, monkeypatch):
    """`safe_torch_save` must serialize FIRST and derive its margin from the real payload size, not
    fall back to the flat multi-GiB default -- otherwise the size-aware fix does not reach the path
    every real family actually calls."""
    sc = _sc()
    p = tmp_path / "t.pt"
    seen = {}
    real_safe_write = sc.safe_write

    def spy(path, write_fn, **kwargs):
        seen.update(kwargs)
        return real_safe_write(path, write_fn, **kwargs)

    monkeypatch.setattr(sc, "safe_write", spy)
    sc.safe_torch_save(torch.arange(3), p, label="x")
    assert "expected_bytes" in seen and seen["expected_bytes"] > 0
    assert seen["expected_bytes"] < sc.DEFAULT_MIN_FREE_BYTES, (
        "a small tensor's real serialized size should be tiny next to the flat default")
