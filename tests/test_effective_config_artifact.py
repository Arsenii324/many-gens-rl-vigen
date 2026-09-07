"""Every training cell must record the configuration it ACTUALLY ran, at the moment it ran it.

`notes/record-completeness-spec.md` asks for "the resolved values actually used, not the template".
A profile label in the manifest is necessary and insufficient: reconstructing what a cell ran by
re-reading `families.json` afterwards gives the wrong answer as soon as a descriptor is edited --
and descriptors were edited three times in one session. The rendered argv exists for exactly one
moment, and this captures it there.

Raised by Codex as Q8; implemented in `run_probe.sh`, which is the only place the composed argv is
known.
"""
import json
import os
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "datasphere" / "native" / "run_probe.sh"
RUNNER = RUNNER_PATH.read_text()


def test_the_runner_writes_an_effective_config_per_cell():
    assert "effective_config.json" in RUNNER, (
        "no per-cell effective-config artifact: what a cell ran could only be reconstructed from a "
        "descriptor that may since have changed"
    )
    assert "NATIVE_EFFECTIVE_CONFIG" in RUNNER, "the artifact is written but never announced"


def test_failure_to_write_it_fails_the_cell():
    """A cell whose configuration was not recorded produces a row nothing can interpret."""
    assert "NATIVE_EFFECTIVE_CONFIG_FAILED" in RUNNER, (
        "writing the effective config must fail closed; a silently missing one is worse than none, "
        "because the cell still produces numbers"
    )


def test_it_captures_the_rendered_argv_and_not_a_template():
    block = RUNNER[RUNNER.index("effective_config.json") - 3000:]
    assert '"argv": argv' in RUNNER, "the argv list itself must be recorded"
    assert "_EC_FAMILY" in RUNNER and "NATIVE_HOST_PROFILE" in RUNNER, (
        "family and selected host profile must be recorded beside the argv: the same argv under two "
        "profiles is two different experiments"
    )


def test_the_writer_produces_valid_json_when_run():
    """Executed, not merely grepped -- a writer that emits malformed JSON passes every text check.

    The inline Python is extracted and run directly, rather than slicing the surrounding shell:
    slicing shell was brittle and tested the slicing more than the writer.
    """
    # Anchored on the printf and the pipe separately: the argv list gained
    # `${extra_overrides[@]}` (Codex Q63, so the captured argv is the EXECUTED one), and a marker
    # spelling the whole line broke on a change that was not about this writer at all.
    marker = "printf '%s\\0' \"${argv[@]}\""
    assert marker in RUNNER, "the effective-config writer is no longer a piped inline python"
    assert "| env" in RUNNER[RUNNER.index(marker):RUNNER.index(marker) + 400]
    body = RUNNER[RUNNER.index(marker):]
    body = body[body.index("python3 -c '") + len("python3 -c '"):]
    body = body[:body.index("\n'")]
    env = {"_EC_CELL_ENVIRONMENT": "ALDA_RESULTS=/tmp/r\nWANDB_MODE=disabled",
           "_EC_CELL": "t-s1", "_EC_FAMILY": "fam", "_EC_BASELINE": "b", "_EC_SEED": "1",
           "_EC_TASK": "Door", "_EC_FRAMES": "10", "_EC_SAVE_EVERY": "5",
           "_EC_EVAL_EVERY": "7", "_EC_EVAL_EPISODES": "2",
           "NATIVE_HOST_PROFILE": "datasphere", "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
           "PATH": os.environ.get("PATH", "")}
    proc = subprocess.run([sys.executable, "-c", body], input=b"launcher.sh\0a\0b\0",
                          capture_output=True, env=env)
    assert proc.returncode == 0, f"the writer failed: {proc.stderr.decode()[-400:]}"
    data = json.loads(proc.stdout.decode())
    assert data["argv"] == ["launcher.sh", "a", "b"], data["argv"]
    assert data["family"] == "fam" and data["host_profile"] == "datasphere"
    assert data["save_every"] == "5" and data["eval_episodes"] == "2"
    assert data["runner_environment"]["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8", (
        "the resolved runner environment must travel with the cell"
    )
    assert data["cell_environment"] == ["ALDA_RESULTS=/tmp/r", "WANDB_MODE=disabled"], (
        "the family-specific environment resolved for this cell must be recorded; the artifact was "
        "first written BEFORE that resolution and so could not see it (Codex Q10)"
    )


def test_the_artifact_is_written_after_the_cell_environment_is_resolved():
    """Order matters: written before resolution, it records an environment that did not apply."""
    resolved = RUNNER.index("local cell_environment=()")
    written = RUNNER.index("effective_config.json")
    assert resolved < written, (
        "effective_config.json is written before `cell_environment` is resolved, so the family's "
        "actual environment (e.g. ALDA_RESULTS) is missing from the config it claims is effective"
    )


def test_a_partial_production_trajectory_fails_the_cell():
    assert "NATIVE_CURVE_EVAL_PARTIAL" in RUNNER, (
        "run_curve_eval must report a partial trajectory rather than returning success after "
        "logging each stamp failure"
    )
    assert "NATIVE_CURVE_EVAL_FATAL" in RUNNER, "a partial PRODUCTION trajectory must fail the cell"
    assert "CURVE_EVAL_STRICT:-${ENDPOINT_EVAL:-0}" in RUNNER, (
        "strictness must default to whether this is a production cell, so an exploratory probe "
        "keeps its non-fatal behaviour and production cannot mistake a partial curve for a whole one"
    )


@pytest.mark.parametrize("endpoint,strict,expect_fatal", [("1", "", True), ("0", "", False),
                                                          ("0", "1", True), ("1", "0", False)])
def test_the_strictness_default_resolves_as_intended(endpoint, strict, expect_fatal):
    """Executed, because `${A:-${B:-0}}` is the kind of expression that reads correct and is not."""
    script = 'if [[ "${CURVE_EVAL_STRICT:-${ENDPOINT_EVAL:-0}}" == "1" ]]; then echo FATAL; else echo TOLERATED; fi'
    env = {"PATH": os.environ.get("PATH", "")}
    if endpoint:
        env["ENDPOINT_EVAL"] = endpoint
    if strict:
        env["CURVE_EVAL_STRICT"] = strict
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env).stdout.strip()
    assert out == ("FATAL" if expect_fatal else "TOLERATED"), (
        f"ENDPOINT_EVAL={endpoint!r} CURVE_EVAL_STRICT={strict!r} resolved to {out}"
    )


def test_the_manifest_carries_each_cells_effective_config():
    """Offline rows inherit the manifest, so this is how the config reaches the LIGHT bundle.

    `RECORDS_OUT` exists so a caller can skip downloading `result.tgz`. The artifact lives in that
    archive; without a copy in the manifest, a caller taking the light path gets rows with no record
    of what produced them -- the same gap the offline-row provenance enrichment closed.
    """
    assert '"effective_configs"' in RUNNER, (
        "run_manifest.json must carry each cell's effective config, or it reaches only the archive"
    )
    assert 'glob("*/effective_config.json")' in RUNNER, (
        "the manifest must collect the per-cell artifacts rather than re-deriving the config"
    )


def test_the_manifest_block_is_valid_python():
    """A heredoc is not syntax-checked by `bash -n`; a broken manifest fails at the end of a run."""
    lines = RUNNER.splitlines()
    start = next(i for i, l in enumerate(lines)
                 if 'run_manifest.json"' in l and l.startswith("python3 - <<"))
    end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "PY")
    import ast
    ast.parse("\n".join(lines[start + 1:end]))
