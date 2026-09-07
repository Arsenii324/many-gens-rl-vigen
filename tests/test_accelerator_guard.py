"""Production must refuse to train on the wrong runtime, not merely record it.

External recommendation 22, item 9. `run_probe.sh` already DETECTED the accelerator -- torch.cuda
for six families, `jax.devices()` for ctrl -- but only to write it into a manifest. A ctrl cell
falling back to JAX CPU runs perhaps fifty times slower and finishes with an honest manifest saying
it had no GPU: the same "succeeds quietly" failure that `require_production_configuration` exists to
prevent for host profiles.
"""
from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "datasphere" / "native" / "run_probe.sh"


def _guard(env: dict, tmp_path: pathlib.Path) -> subprocess.CompletedProcess:
    """Run just the guard function, extracted from the runner into a file.

    Extracted rather than sourced through a process substitution: the nested quoting needed for
    `source <(sed ...)` inside `bash -c` inside a Python string is its own failure mode, and a test
    that fails for its own quoting teaches nothing about the guard.
    """
    text = RUNNER.read_text()
    start = text.index("require_accelerator() {")
    end = text.index("require_production_configuration() {")
    script = tmp_path / "guard.sh"
    script.write_text(text[start:end] + '\nrequire_accelerator "drqv2:1"\n')
    base = {"PATH": "/usr/bin:/bin:/usr/local/bin",
            "FAMILY_TOOL": "datasphere/native/family.py"}
    return subprocess.run(["bash", str(script)], capture_output=True, text=True,
                          cwd=str(ROOT), env={**base, **env})


def test_production_scale_refuses_without_an_accelerator(tmp_path):
    """This machine has no CUDA, which makes it the right place to assert the refusal."""
    result = _guard({"FRAMES": "600000"}, tmp_path)
    assert result.returncode != 0, "a production cell must not start on CPU"
    # Either refusal is correct and which one appears depends on the interpreter this test's
    # minimal PATH resolves: a python3 without torch refuses at the import, one with torch but no
    # CUDA refuses at the device query. Asserting only the second made the test fail for the wrong
    # reason on a machine where the guard was working perfectly.
    assert "REFUSING" in result.stderr, result.stderr
    assert ("resolved no CUDA device at production scale" in result.stderr
            or "did not import" in result.stderr), result.stderr
    # The device-query message is the one that matters in the container, where torch always
    # imports; assert it exists in the source so a refactor cannot quietly drop it.
    assert "resolved no CUDA device at production scale" in RUNNER.read_text()


def test_probe_scale_is_untouched(tmp_path):
    """Several diagnostic configs in this tree run on CPU deliberately."""
    assert _guard({"FRAMES": "10000"}, tmp_path).returncode == 0


def test_the_opt_out_is_explicit_and_announced(tmp_path):
    result = _guard({"FRAMES": "600000", "NATIVE_ALLOW_CPU": "1"}, tmp_path)
    assert result.returncode == 0
    assert "NATIVE_ACCELERATOR_CHECK_SKIPPED" in result.stderr, (
        "an opt-out that leaves no trace in the log is indistinguishable from the guard not running")


def test_ctrl_is_checked_through_jax_not_torch():
    """ctrl's requirements filter torch out entirely, so torch.cuda would be the wrong question."""
    text = RUNNER.read_text()
    guard = text[text.index("require_accelerator() {"):text.index("require_production_configuration() {")]
    assert 'if family == "ctrl":' in guard
    assert "jax.devices()" in guard
    assert "CPU fallback" in guard


def test_the_guard_runs_after_the_bootstrap_on_the_training_path():
    """It needs torch/jax importable; the family's dependencies install only mid-script."""
    text = RUNNER.read_text()
    install = text.index("pip install -r /tmp/requirements-for-this-job.txt")
    call = text.index('require_accelerator "$cells"')
    assert call > install, (
        "the guard must not run before the dependencies it imports are installed")
