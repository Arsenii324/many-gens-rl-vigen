"""The production host guard must actually REFUSE, not merely be present in the file.

This exists because the first version of the guard was dead code. `run_probe.sh:6` does
`export NATIVE_HOST_PROFILE="${NATIVE_HOST_PROFILE:-datasphere}"`, so by the time the guard tested
`-z "${NATIVE_HOST_PROFILE:-}"` several hundred lines later the variable was ALWAYS set and the
refusal could never fire. `gate_production_names_its_host` passed on it, and the gate's own
"non-vacuity" test passed too -- because that test removed the guard and checked the GATE noticed.
It proved the gate reads the file. It could not prove the guard works.

So this one runs the shell. It lifts both fragments out of the real script rather than retyping
them, and executes them under the two conditions that matter.
"""
import os
import pathlib
import re
import subprocess

import pytest

RUNNER = pathlib.Path(__file__).resolve().parents[1] / "datasphere" / "native" / "run_probe.sh"


def _fragments() -> str:
    text = RUNNER.read_text()
    capture = re.search(r'if \[\[ -n "\$\{NATIVE_HOST_PROFILE:-\}" \]\]; then.*?\nfi\n',
                        text, flags=re.DOTALL)
    # The shared guard is called by both the --run-cells and normal entrypoints. Extract the
    # function itself so this test remains independent of either path's bootstrap code.
    guard = re.search(r'require_production_configuration\(\) \{.*?\n\}\n',
                      text, flags=re.DOTALL)
    assert capture, "the explicit-host capture is gone from run_probe.sh"
    assert guard, "the production guard(s) are gone from run_probe.sh"
    assert guard.group(0).count("REFUSING") == 2, (
        "expected both the host-profile and NATIVE_PRODUCTION guards in one capture")
    return capture.group(0) + "\n" + guard.group(0) + "\nrequire_production_configuration\necho REACHED_THE_RUN\n"


def _run(env_extra: dict[str, str]) -> subprocess.CompletedProcess:
    script = "set -u\n" + _fragments()
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin", **env_extra})


def test_normal_entrypoint_refuses_production_scale_before_bootstrap(tmp_path):
    """The ordinary ``bash JOB CODE RESULT`` path must guard before apt/bootstrap."""
    marker = tmp_path / "bootstrap-invoked"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_apt = fake_bin / "apt-get"
    fake_apt.write_text("#!/bin/sh\ntouch \"$BOOTSTRAP_MARKER\"\nexit 0\n")
    fake_apt.chmod(0o755)
    payload = tmp_path / "dummy-payload.tgz"
    result_archive = tmp_path / "dummy-result.tgz"
    payload.write_bytes(b"not a real payload")
    result_archive.write_bytes(b"unused")
    environment = {**os.environ,
                   "PATH": f"{fake_bin}:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin",
                   "BOOTSTRAP_MARKER": str(marker),
                   "FRAMES": "600000"}
    environment.pop("NATIVE_HOST_PROFILE", None)
    environment.pop("NATIVE_PRODUCTION", None)

    done = subprocess.run(
        ["bash", str(RUNNER), str(payload), str(result_archive)],
        cwd=RUNNER.parents[2], capture_output=True, text=True, env=environment,
    )

    assert done.returncode == 3, f"normal entrypoint did not guard: rc={done.returncode}\n{done.stdout}"
    assert "REFUSING:" in done.stdout + done.stderr
    assert not marker.exists(), "normal entrypoint reached apt/bootstrap before refusing"


def test_production_scale_without_a_named_host_is_refused():
    done = _run({"FRAMES": "600000"})
    assert done.returncode == 3, f"the guard did not fire: rc={done.returncode} {done.stdout}"
    assert "REFUSING" in done.stderr
    assert "REACHED_THE_RUN" not in done.stdout, "execution continued past the refusal"


def test_production_scale_with_a_named_host_proceeds():
    """'Fully configured' now means both flags -- extended when the NATIVE_PRODUCTION guard
    (Q18(c)) was added; this test used to pass on NATIVE_HOST_PROFILE alone."""
    done = _run({"FRAMES": "600000", "NATIVE_HOST_PROFILE": "v100", "NATIVE_PRODUCTION": "1"})
    assert done.returncode == 0 and "REACHED_THE_RUN" in done.stdout


def test_a_probe_is_not_blocked():
    """Every existing probe config relies on the default; blocking those would be a regression."""
    done = _run({"FRAMES": "10000"})
    assert done.returncode == 0 and "REACHED_THE_RUN" in done.stdout


@pytest.mark.parametrize("frames", ["599999", "600000", "600001"])
def test_the_boundary_is_the_protocol_budget(frames):
    done = _run({"FRAMES": frames})
    expected = 0 if frames == "599999" else 3
    assert done.returncode == expected, f"FRAMES={frames} gave rc={done.returncode}"


def test_production_scale_without_native_production_is_refused():
    """Codex, mailbox Q18(c): NATIVE_HOST_PROFILE alone is not enough -- NATIVE_PRODUCTION governs
    whether apply_production_settings does anything at all. Missing it at production scale must
    also refuse, not silently train at probe-scale cadence/replay while looking successful."""
    done = _run({"FRAMES": "600000", "NATIVE_HOST_PROFILE": "v100"})  # host set, PRODUCTION not
    assert done.returncode == 3, f"the guard did not fire: rc={done.returncode} {done.stdout}"
    assert "NATIVE_PRODUCTION" in done.stderr
    assert "REACHED_THE_RUN" not in done.stdout


def test_production_scale_with_both_flags_proceeds():
    done = _run({"FRAMES": "600000", "NATIVE_HOST_PROFILE": "v100", "NATIVE_PRODUCTION": "1"})
    assert done.returncode == 0 and "REACHED_THE_RUN" in done.stdout


def test_a_probe_is_not_blocked_by_the_production_flag_either():
    done = _run({"FRAMES": "10000", "NATIVE_HOST_PROFILE": "v100"})  # no NATIVE_PRODUCTION
    assert done.returncode == 0 and "REACHED_THE_RUN" in done.stdout


def test_production_path_has_a_strict_conflict_guard_for_resolved_defaults():
    """A config-level override must not silently redefine a production cell."""
    source = RUNNER.read_text()
    assert "NATIVE_PRODUCTION_STRICT" in source
    assert "NATIVE_PRODUCTION_CONFLICT" in source


def test_production_path_refuses_a_conflicting_resolved_setting(tmp_path):
    source = RUNNER.read_text()
    start = source.index("apply_production_settings() {")
    end = source.index('\n\nif [[ "${1:-}" == "--run-cells" ]]', start)
    fake_python = tmp_path / "python3"
    fake_python.write_text("#!/bin/sh\nprintf '%s\\n' SAVE_EVERY_FRAMES=50000\n")
    fake_python.chmod(0o755)
    script = "set -u\n" + source[start:end] + "\napply_production_settings ibac_sni:1\n"
    done = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                          env={"PATH": f"{tmp_path}:/usr/bin:/bin", "FAMILY_TOOL": "unused",
                               "NATIVE_PRODUCTION": "1", "FRAMES": "600000",
                               "SAVE_EVERY_FRAMES": "2000"})
    assert done.returncode == 3
    assert "NATIVE_PRODUCTION_CONFLICT" in done.stderr
