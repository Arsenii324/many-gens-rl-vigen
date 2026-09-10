"""Each test here pins one row of `docs/resolved-register.json`.

A register row marked `resolved` must have something that FAILS when it stops being true --
otherwise it is a confident assertion with a citation, which is the artifact this project keeps
finding stale. `scripts/verify_resolved_register.py` downgrades any `resolved` row without a
pinning test to `traced` in the rendered view, and these are the tests that stop that happening for
the seven rows that had none.

Several of these assert that something is STILL BROKEN -- notably the VRAM cap. That is deliberate.
The register's claim is "the cap does not protect a co-tenant", and if someone repairs the launchers
that claim silently becomes false. The test failing is the signal to re-derive the row, not a
regression.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTER = json.loads((ROOT / "docs" / "resolved-register.json").read_text())
ROWS = {e["id"]: e for e in REGISTER["entries"]}


def test_whole_card_jobs():
    """`whole-card-jobs`: nothing may be packed against ppg or ctrl@v100."""
    chain = (ROOT / "datasphere" / "native" / "battery-chain.sh").read_text()
    assert "one cell at a time" in chain.lower() or "CARD 0 ONLY" in chain, (
        "the battery chain no longer states that it runs one cell at a time"
    )
    # ctrl's two profiles must still differ, since the whole-card figure is v100-specific.
    #
    # num_envs lives under `constants` -- the TRAINER's CLI values -- not under `production`, which
    # carries campaign/scheduling settings. `host_profiles.v100` overrides `constants.num_envs` to
    # "64". Reading the wrong layer returns None and would have made this test fail against a
    # correct repo.
    sys.path.insert(0, str(ROOT / "datasphere" / "native"))
    import family
    ds = (family.resolved_descriptor("ctrl", profile="datasphere").get("constants") or {})
    v100 = (family.resolved_descriptor("ctrl", profile="v100").get("constants") or {})
    assert str(ds.get("num_envs")) == "16" and str(v100.get("num_envs")) == "64", (
        f"ctrl profiles changed: datasphere={ds.get('num_envs')} v100={v100.get('num_envs')}; "
        f"the 32,435 MiB whole-card measurement was taken at v100/64 and must be re-measured"
    )


def test_vram_cap_is_not_protection():
    """`vram-cap-is-not-protection`: still true only while the launchers drop PYTHONPATH.

    Asserts the BROKEN state on purpose. If this fails, someone fixed the launchers and the register
    row must be re-derived rather than assumed to still hold.
    """
    launchers = sorted((ROOT / "runnable" / "_launch").glob("*.sh"))
    exporting = [p for p in launchers if 'export PYTHONPATH="' in p.read_text()]
    preserving = [p for p in exporting if "PYTHONPATH:+" in p.read_text()]
    assert exporting, "no launcher exports PYTHONPATH; the register row's premise has changed"
    assert not preserving, (
        f"{len(preserving)} launcher(s) now PRESERVE PYTHONPATH, so the VRAM cap may reach a "
        f"trainer. The register row 'the cap is not protection' must be re-derived: {preserving}"
    )


def test_disk_bound_is_declared():
    """`disk-bound-is-declared`: host-run.sh refuses a writable mount without a stated bound."""
    source = (ROOT / "datasphere" / "native" / "host-run.sh").read_text()
    assert "HOST_RUN_DISK_BOUND_GIB" in source
    assert "NATIVE_DISK_ABS_FLOOR_GIB" in source, "the floor is no longer the project's own constant"
    # read-only mounts must stay exempt: they cannot consume.
    assert 'if [[ -z "$READONLY" ]]; then' in source, (
        "the guard no longer exempts read-only mounts, so a read-only probe now needs a bound"
    )


def test_keep_the_supplementary_mode_pass():
    """`keep-the-supplementary-mode-pass`: the three sampling families still get a second pass."""
    sys.path.insert(0, str(ROOT / "datasphere" / "native"))
    import family
    import evaluator_identity as identity
    sampling = [f for f, m in identity.FAMILY_EVAL_POLICY_MODE.items() if m == "sample"]
    assert sorted(sampling) == ["ibac_sni", "idaac", "ppg"], sampling
    for fam in sampling:
        env = family.family_environment(fam) if hasattr(family, "family_environment") else None
        if env is None:
            source = (ROOT / "datasphere" / "native" / "family.py").read_text()
            assert '"ENDPOINT_EVAL_POLICY_MODES"] = "native,mode"' in source, (
                "the supplementary mode pass is no longer configured for sampling families"
            )
            return


def test_curve_depth_vs_endpoint_depth():
    """`curve-depth-vs-endpoint-depth`: curve stays shallower than the endpoint, and above 1."""
    sys.path.insert(0, str(ROOT / "datasphere" / "native"))
    import family
    for fam in ("idaac", "rlvigen"):
        prod = family.resolved_descriptor(fam, profile="v100").get("production") or {}
        # `offline_eval_episodes` is the ENDPOINT GRID depth. `eval_episodes` is a different thing
        # -- the ONLINE, training-time evaluation count that becomes EVAL_EPISODES -- and for
        # rlvigen both happen to be 20, so reading the wrong one would pass by coincidence.
        curve = int(prod["curve_eval_episodes"])
        endpoint = int(prod["offline_eval_episodes"])
        assert curve >= 2, f"{fam}: curve depth {curve} -- one episode is noise, not a cheaper curve"
        assert endpoint > curve, (
            f"{fam}: endpoint {endpoint} is not deeper than curve {curve}; the endpoint carries the "
            f"reported number and is where depth belongs"
        )


def test_random_floor_survives_closure_change():
    """`random-floor-survives-closure-change`: the floor policy must remain observation-blind."""
    source = (ROOT / "scripts" / "probe_floor.py").read_text()
    assert "rng.uniform(-1.0, 1.0" in source, (
        "probe_floor no longer draws uniform random actions; if the floor policy ever reads the "
        "observation it stops being invariant to frame stack, image size and crop policy, and the "
        "cross-closure comparison in the register row is void"
    )
    for forbidden in ("model(", "policy(", "agent."):
        assert forbidden not in source, f"probe_floor references {forbidden!r} -- is it still blind?"


def test_note_citations_must_resolve(tmp_path):
    """`note-citations-must-resolve`: the checker must actually catch a stale citation."""
    note = tmp_path / "fake-note.md"
    note.write_text("This cites `datasphere/native/family.py:999999` and `nonexistent_file_xyz.py:3`.\n")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_note_citations.py"), str(note), "--strict"],
        capture_output=True, text=True, cwd=ROOT, timeout=600)
    assert proc.returncode == 1, f"the checker passed a note with two bad citations:\n{proc.stdout}"
    assert "PAST END" in proc.stdout and "FILE MISSING" in proc.stdout, proc.stdout


def test_every_resolved_row_this_file_claims_to_pin_exists():
    """Guard the guard: the ids above must still be in the register."""
    for eid in ("whole-card-jobs", "vram-cap-is-not-protection", "disk-bound-is-declared",
                "keep-the-supplementary-mode-pass", "curve-depth-vs-endpoint-depth",
                "random-floor-survives-closure-change", "note-citations-must-resolve"):
        assert eid in ROWS, f"register row {eid} disappeared; this test file pins nothing for it"


# --- the-verifier-must-fail-when-it-should -----------------------------------------------------
# [Claude 2026-09-10] These pin the register's own verifier. Its first real run printed
# "pytest exit=1, 0 failure(s)" and exited 0, over a genuinely stale artifact: it matched
# `startswith("FAILED")` against coloured output beginning `\x1b[31mFAILED`. The register exists to
# refuse instruments that cannot fail; it must not be one.

def _verifier():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_verify_register", ROOT / "scripts" / "verify_resolved_register.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_coloured_failure_line_is_still_a_failure():
    """The original defect, reproduced verbatim: this is what pytest actually emits."""
    problems = _verifier().parse_pytest_outcome(
        "\x1b[31mFAILED\x1b[0m tests/test_x.py::test_y - assert False", 1)
    assert len(problems) == 1 and "test_x.py" in problems[0]


def test_a_nonzero_exit_with_nothing_parsed_is_reported_not_swallowed():
    """A collection error prints no FAILED line at all. Silence here is how the defect survived."""
    problems = _verifier().parse_pytest_outcome("INTERNALERROR> KeyboardInterrupt", 2)
    assert len(problems) == 1 and "exited 2" in problems[0]


def test_a_clean_run_reports_nothing():
    """The check must still be able to pass, or it is noise rather than a gate."""
    assert _verifier().parse_pytest_outcome("12 passed in 4.2s", 0) == []


# --- ctrl-cudnn-on-volta ------------------------------------------------------------------------
# [Claude 2026-09-10] A hardware fact cannot be re-measured in CI, so what this pins is the CLAIM
# against drift: the committed probe artifact must keep saying what the register says it says. If
# someone edits the verdict without a new measurement, or deletes the evidence, this fails.

PROBE_LOG = ROOT / "results" / "logs" / "volta-conv-probe-2026-09-10.log"


def test_the_volta_probe_artifact_still_says_what_the_register_claims():
    assert PROBE_LOG.is_file(), "the probe artifact backing ctrl-cudnn-on-volta is gone"
    text = PROBE_LOG.read_text(errors="replace")
    # The card it ran on, so the claim cannot be re-pointed at different hardware.
    assert "Tesla V100-SXM2-32GB" in text and "compute_capability=7.0" in text
    # The two halves that make this a CONV finding rather than a broken-GPU finding.
    assert "MATMUL OK" in text, "without a passing matmul this proves nothing specific to conv"
    assert "CONV FAILED" in text
    assert "All algorithms tried" in text
    # The build measured. A different jaxlib is a different question, not this answer.
    assert "jax=0.4.35 jaxlib=0.4.34" in text


def test_the_probe_was_not_the_void_one():
    """The first probe exited 0 having run nothing. Absence of these strings is the tell."""
    text = PROBE_LOG.read_text(errors="replace")
    assert "command not found" not in text
    assert "probe python exit=10" in text, "exit 10 is the matmul-OK/conv-FAILED verdict"


PIN_LOG = ROOT / "results" / "logs" / "volta-cudnn-pin-2026-09-10.log"


def test_the_cudnn_pin_is_what_makes_ctrl_run_and_is_still_declared():
    """The 2x2 that separated card from cuDNN, plus the pin that acts on it.

    [Claude 2026-09-10] Written after recording the WRONG cause twice. A single-variable probe
    could not tell 'sm_70 is uncovered' from 'cuDNN is too new'; only varying cuDNN on a FIXED
    card did. This pins both halves: the measurement, and the fix actually being declared.
    """
    import json
    text = PIN_LOG.read_text(errors="replace")
    assert "cudnn=9.5.1.17: CONV OK" in text
    assert "cudnn=9.1.0.70: CONV OK" in text
    # 3465600 is the arithmetically exact result, so this pins a CORRECT conv, not merely one
    # that raised no exception: 3844*27 + 248*18 + 4*12 = 108300 per channel, times 32 channels.
    assert "sum=3465600" in text

    families = json.loads((ROOT / "datasphere" / "native" / "families.json").read_text())
    reqs = families["ctrl"]["pip_requirements"]
    assert "nvidia-cudnn-cu12==9.5.1.17" in reqs, (
        "ctrl no longer pins cuDNN. Unpinned, it resolves to the newest release, which on sm_70 "
        "fails every conv engine with `<unknown cudnn status: 5003>`.")
