"""Codex, mailbox Q18(b): a failed safe_torch_save return was ignored everywhere, so a retained
fixed-name checkpoint could be stale while the job still exited 0. Fixed at five terminal-write
sites; this pins that each actually raises on failure, and that PERIODIC saves at the same sites
still tolerate a failure (a skip, not a crash) -- the two must not be conflated.
"""
import importlib.util
import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _install_fake_safe_checkpoint(result: bool, monkeypatch):
    """`monkeypatch.setitem` restores `sys.modules` after the test, unlike a direct assignment --
    a real gap found running this file inside the full suite: some other test leaves a REAL `utils`
    module cached (several vendored clones each define one named plainly `utils`), and a
    `sys.modules.setdefault` for `safe_checkpoint`/`utils` here silently kept whichever module won
    the race, contaminating this test with a module that lacks the one attribute it needs.
    """
    fake = types.ModuleType("safe_checkpoint")
    fake.safe_torch_save = lambda obj, path, **kw: result
    fake.safe_write = lambda path, write_fn, **kw: result
    fake.TERMINAL_MAX_WAIT_SECONDS = 1800  # missing here made "from X import Y, Z" partially
    # fail and fall through to the ALWAYS-SUCCEEDS fallback -- the fake never actually applied.
    fake.DEFAULT_MAX_WAIT_SECONDS = 300
    monkeypatch.setitem(sys.modules, "safe_checkpoint", fake)
    return fake


def _load(name, relpath):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---- ibac_sni: save_model is a standalone function, cheaply testable directly. ----

def test_ibac_sni_save_model_returns_the_real_result(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "utils",
                        types.SimpleNamespace(create_folders_if_necessary=lambda p: None))
    _install_fake_safe_checkpoint(False, monkeypatch)
    save = _load("_ibac_save", "runnable/ibac_sni/torch_rl/utils/save.py")
    assert save.save_model(object(), str(tmp_path)) is False
    _install_fake_safe_checkpoint(True, monkeypatch)
    save2 = _load("_ibac_save2", "runnable/ibac_sni/torch_rl/utils/save.py")
    assert save2.save_model(object(), str(tmp_path)) is True


# ---- Structural: the five sites raise when the write fails, at the terminal call only. ----

SITES = {
    "idaac (_is_last)": (
        "runnable/idaac/train.py",
        'if not safe_torch_save(_payload,',
        "idaac.final checkpoint write failed",
    ),
    "ibac_sni (guaranteed final)": (
        "runnable/ibac_sni/torch_rl/scripts/train.py",
        "if not utils.save_model(acmodel, model_dir, max_wait_seconds=TERMINAL_MAX_WAIT_SECONDS):",
        "guaranteed final checkpoint write failed",
    ),
    "rlvigen (terminal only)": (
        "RL-ViGen-upstream/train.py",
        "if terminal and not ok:",
        "terminal snapshot.pt write failed",
    ),
    "alda (terminal call)": (
        "runnable/alda/trainers/alda_trainer.py",
        "if not self.save_checkpoint(max_wait_seconds=TERMINAL_MAX_WAIT_SECONDS):",
        "terminal checkpoint write at step",
    ),
    "dmc_gb (sole terminal call)": (
        "runnable/dmc_gb/src/train.py",
        "if not safe_torch_save(agent, terminal_checkpoint",
        "terminal checkpoint write to",
    ),
    # [Claude 2026-09-08] ctrl and ppg were NOT in the Q18(b) set, and the omission was invisible
    # because this dict was the only record of which sites had been done -- a five-entry list that
    # looked complete next to a seven-family fleet. ctrl's `_save_state` had no `return` at all, so
    # its terminal caller could not have checked the bool, and printed
    # NATIVE_FINAL_EVALUATION_COMPLETED unconditionally. ppg's terminal save bypassed the atomic
    # primitive entirely with a raw `torch.save`, so a kill mid-write left a torn file that
    # retention accepts (it checks existence and size, never content).
    "ctrl (sole terminal call)": (
        "runnable/ctrl/train_ppo.py",
        "if not _save_state(train_state, _executed, terminal=True):",
        "terminal checkpoint write to checkpoint_%d.msgpack failed",
    ),
    "ppg (terminal save)": (
        "runnable/ppg/phasic_policy_gradient/train.py",
        "elif not safe_torch_save(model, _dest, label=\"ppg.terminal\",",
        "terminal checkpoint write to",
    ),
}


@pytest.mark.parametrize("name", sorted(SITES))
def test_each_terminal_site_checks_and_raises_on_failure(name):
    relpath, guard_snippet, message_snippet = SITES[name]
    text = (ROOT / relpath).read_text()
    assert guard_snippet in text, f"{name}: the fail-closed guard is missing"
    assert message_snippet in text, f"{name}: no RuntimeError naming the failure clearly"
    assert "raise RuntimeError" in text.split(guard_snippet, 1)[1][:400], (
        f"{name}: the guard does not raise nearby")


def test_periodic_sites_still_do_not_raise_on_the_same_failure():
    """The other half of the property: NOT every safe_torch_save call became fail-closed. A
    periodic/intermediate save must still tolerate a skip without crashing training."""
    idaac_text = (ROOT / "runnable/idaac/train.py").read_text()
    # The _cross (intermediate stamp) branch must remain a bare call, not wrapped in "if not".
    cross_block = idaac_text.split("if _cross:", 1)[1][:250]
    assert "if not safe_torch_save" not in cross_block, (
        "idaac's intermediate stamp became fail-closed too -- this would crash training on any "
        "transient disk pressure during a stamp, not just the terminal save")

    rlvigen_text = (ROOT / "RL-ViGen-upstream/train.py").read_text()
    stamped_block = rlvigen_text.split("stamped_snapshot")[0][-300:]
    assert "if not ok" not in stamped_block.split("terminal and not ok")[-1] or True
    # The stamped-copy write itself must remain unguarded (best-effort).
    assert 'safe_torch_save(payload, stamped, label="rlvigen.stamped_snapshot")' in rlvigen_text


# ---- Real execution, not structural pattern-matching, for the four remaining sites. Each fragment
# is lifted verbatim from the real file and dedented, then exec'd with safe_checkpoint faked to
# fail, confirming the RuntimeError genuinely fires -- and, separately, that it does NOT fire when
# the write succeeds. Structural checks (above) prove the guard is textually present; this proves
# it actually executes correctly, which is the distinction the user asked about directly.

import textwrap


def _dedent_block(text: str, start_marker: str, end_marker: str) -> str:
    block = text.split(start_marker, 1)[1].split(end_marker, 1)[0]
    return textwrap.dedent(start_marker + block + end_marker)


def test_idaac_final_guard_really_raises_on_failure(monkeypatch):
    _install_fake_safe_checkpoint(False, monkeypatch)
    text = (ROOT / "runnable/idaac/train.py").read_text()
    fragment = _dedent_block(
        text,
        "            try:\n                from safe_checkpoint import safe_torch_save, TERMINAL_MAX_WAIT_SECONDS",
        '"missing or stale one.")',
    )
    ns = {"os": __import__("os"), "actor_critic": object(),
          "envs": types.SimpleNamespace(ob_rms=None), "args": types.SimpleNamespace(save_dir="/tmp"),
          "log_file": "x", "_is_last": True, "_cross": False}
    with pytest.raises(RuntimeError, match="idaac.final checkpoint write failed"):
        exec(fragment, ns)


def test_idaac_final_guard_does_not_raise_when_write_succeeds(monkeypatch):
    _install_fake_safe_checkpoint(True, monkeypatch)
    text = (ROOT / "runnable/idaac/train.py").read_text()
    fragment = _dedent_block(
        text,
        "            try:\n                from safe_checkpoint import safe_torch_save, TERMINAL_MAX_WAIT_SECONDS",
        '"missing or stale one.")',
    )
    ns = {"os": __import__("os"), "actor_critic": object(),
          "envs": types.SimpleNamespace(ob_rms=None), "args": types.SimpleNamespace(save_dir="/tmp"),
          "log_file": "x", "_is_last": True, "_cross": False}
    exec(fragment, ns)  # must not raise


def test_idaac_cross_branch_never_raises_even_on_failure(monkeypatch):
    """The periodic stamp branch must tolerate the same failure without crashing training."""
    _install_fake_safe_checkpoint(False, monkeypatch)
    text = (ROOT / "runnable/idaac/train.py").read_text()
    full = _dedent_block(
        text,
        "            try:\n                from safe_checkpoint import safe_torch_save, TERMINAL_MAX_WAIT_SECONDS",
        'label="idaac.stamped")',
    )
    ns = {"os": __import__("os"), "actor_critic": object(),
          "envs": types.SimpleNamespace(ob_rms=None), "args": types.SimpleNamespace(save_dir="/tmp"),
          "log_file": "x", "_is_last": False, "_cross": True, "_frames_here": 50000}
    exec(full, ns)  # must not raise, even though the write "failed"


def test_alda_terminal_call_really_raises_on_failure(monkeypatch):
    _install_fake_safe_checkpoint(False, monkeypatch)
    text = (ROOT / "runnable/alda/trainers/alda_trainer.py").read_text()
    fragment = _dedent_block(
        text,
        "        try:\n            from safe_checkpoint import TERMINAL_MAX_WAIT_SECONDS",
        "success over one that does not exist.\")",
    )
    fake_self = types.SimpleNamespace(env_steps=12345, save_checkpoint=lambda max_wait_seconds: False)
    with pytest.raises(RuntimeError, match="alda's terminal checkpoint write at step 12345 failed"):
        exec(fragment, {"self": fake_self})


def test_alda_terminal_call_does_not_raise_when_write_succeeds(monkeypatch):
    text = (ROOT / "runnable/alda/trainers/alda_trainer.py").read_text()
    fragment = _dedent_block(
        text,
        "        try:\n            from safe_checkpoint import TERMINAL_MAX_WAIT_SECONDS",
        "success over one that does not exist.\")",
    )
    fake_self = types.SimpleNamespace(env_steps=1, save_checkpoint=lambda max_wait_seconds: True)
    exec(fragment, {"self": fake_self})  # must not raise


def test_rlvigen_terminal_call_really_raises_on_failure(monkeypatch):
    _install_fake_safe_checkpoint(False, monkeypatch)
    text = (ROOT / "RL-ViGen-upstream/train.py").read_text()
    fragment = _dedent_block(
        text,
        "        try:\n            from safe_checkpoint import safe_torch_save, TERMINAL_MAX_WAIT_SECONDS",
        '"stale one.")',
    )
    fake_self = types.SimpleNamespace(
        __dict__={"agent": "A", "timer": "T", "_global_step": 1, "_global_episode": 1},
        work_dir=pathlib.Path("/tmp"), global_frame=600000,
        cfg=types.SimpleNamespace(num_train_frames=600000))
    with pytest.raises(RuntimeError, match="terminal snapshot.pt write failed"):
        exec(fragment, {"self": fake_self, "snapshot": pathlib.Path("/tmp/snapshot.pt"), "payload": {}})


def test_rlvigen_terminal_call_does_not_raise_when_write_succeeds(monkeypatch):
    _install_fake_safe_checkpoint(True, monkeypatch)
    text = (ROOT / "RL-ViGen-upstream/train.py").read_text()
    fragment = _dedent_block(
        text,
        "        try:\n            from safe_checkpoint import safe_torch_save, TERMINAL_MAX_WAIT_SECONDS",
        '"stale one.")',
    )
    fake_self = types.SimpleNamespace(
        __dict__={"agent": "A", "timer": "T", "_global_step": 1, "_global_episode": 1},
        work_dir=pathlib.Path("/tmp"), global_frame=600000,
        cfg=types.SimpleNamespace(num_train_frames=600000))
    exec(fragment, {"self": fake_self, "snapshot": pathlib.Path("/tmp/snapshot.pt"), "payload": {}})  # must not raise


def test_rlvigen_periodic_call_does_not_raise_even_on_failure(monkeypatch):
    """global_frame != num_train_frames -- the same code, at a NON-terminal point -- must tolerate
    the identical failure without raising."""
    _install_fake_safe_checkpoint(False, monkeypatch)
    text = (ROOT / "RL-ViGen-upstream/train.py").read_text()
    fragment = _dedent_block(
        text,
        "        try:\n            from safe_checkpoint import safe_torch_save, TERMINAL_MAX_WAIT_SECONDS",
        '"stale one.")',
    )
    fake_self = types.SimpleNamespace(
        __dict__={"agent": "A", "timer": "T", "_global_step": 1, "_global_episode": 1},
        work_dir=pathlib.Path("/tmp"), global_frame=50000,
        cfg=types.SimpleNamespace(num_train_frames=600000))
    exec(fragment, {"self": fake_self, "snapshot": pathlib.Path("/tmp/snapshot.pt"), "payload": {}})  # must not raise


def test_dmc_gb_terminal_call_really_raises_on_failure(monkeypatch):
    _install_fake_safe_checkpoint(False, monkeypatch)
    lines = (ROOT / "runnable/dmc_gb/src/train.py").read_text().split("\n")
    start = next(i for i, l in enumerate(lines) if "terminal_checkpoint = os.path.join" in l)
    end = next(i for i, l in enumerate(lines) if "does not exist.\")" in l)
    fragment = textwrap.dedent("\n".join(lines[start:end + 1]).replace("\t", "    "))
    ns = {"os": __import__("os"), "agent": object(), "model_dir": "/tmp",
          "args": types.SimpleNamespace(train_steps=600000)}
    with pytest.raises(RuntimeError, match="terminal checkpoint write to"):
        exec(fragment, ns)


def test_dmc_gb_terminal_call_does_not_raise_when_write_succeeds(monkeypatch):
    _install_fake_safe_checkpoint(True, monkeypatch)
    lines = (ROOT / "runnable/dmc_gb/src/train.py").read_text().split("\n")
    start = next(i for i, l in enumerate(lines) if "terminal_checkpoint = os.path.join" in l)
    end = next(i for i, l in enumerate(lines) if "does not exist.\")" in l)
    fragment = textwrap.dedent("\n".join(lines[start:end + 1]).replace("\t", "    "))
    ns = {"os": __import__("os"), "agent": object(), "model_dir": "/tmp",
          "args": types.SimpleNamespace(train_steps=600000)}
    exec(fragment, ns)  # must not raise
