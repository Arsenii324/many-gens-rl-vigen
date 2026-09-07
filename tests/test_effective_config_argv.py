"""`effective_config.json`'s argv must be the command that RAN, overrides included.

Codex Q63, from the PPG geometry probe. The artifact recorded the pre-override argv
(`--num_envs 8 --nstep 256`) while the process executed
`--num_envs 8 --nstep 256 --num_envs 1 --nstep 2048`. The run was valid, because argparse takes the
last value -- but reconstructing what ran required knowing that, which is a property of argparse
rather than of anything the artifact records. An artifact whose entire purpose is "what actually
ran" must not need a second document to be read correctly.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "datasphere" / "native" / "run_probe.sh"


def _effective_config(env: dict, argv: list[str]) -> dict:
    """Run the embedded python body with a chosen argv, exactly as the runner pipes it."""
    text = RUNNER.read_text()
    body = text.split("python3 -c '", 1)[1].split("' > \"$cell_out/effective_config.json\"", 1)[0]
    payload = b"\0".join(a.encode() for a in argv)
    base = dict(os.environ)
    base.update({"_EC_CELL": "ppg-s1", "_EC_FAMILY": "ppg", "_EC_BASELINE": "ppg",
                 "_EC_SEED": "1", "_EC_TASK": "Door", "_EC_FRAMES": "65536"})
    base.update(env)
    result = subprocess.run([sys.executable, "-c", body], input=payload,
                            capture_output=True, env=base)
    assert result.returncode == 0, result.stderr.decode()
    return json.loads(result.stdout)


def test_argv_carries_the_overrides_that_were_appended():
    merged = ["runnable/_launch/ppg.sh", "Door", "8", "65536", "1", "--num_envs", "1",
              "--nstep", "2048"]
    config = _effective_config({"NATIVE_EXTRA_OVERRIDES": "--num_envs 1 --nstep 2048"}, merged)
    assert config["argv"] == merged, "the recorded argv must be the executed one"
    assert config["argv"][-4:] == ["--num_envs", "1", "--nstep", "2048"]


def test_the_override_provenance_survives_the_merge():
    """Merging must not cost the ability to say WHICH tail came from the job config."""
    merged = ["runnable/_launch/ppg.sh", "Door", "--num_envs", "1"]
    config = _effective_config({"NATIVE_EXTRA_OVERRIDES": "--num_envs 1"}, merged)
    assert config["extra_overrides"] == ["--num_envs", "1"], (
        "a reader must be able to tell a descriptor value from a job-config deviation without "
        "diffing two argv lists")


def test_a_run_without_overrides_is_unchanged():
    plain = ["runnable/_launch/ppg.sh", "Door", "8", "65536", "1"]
    config = _effective_config({"NATIVE_EXTRA_OVERRIDES": ""}, plain)
    assert config["argv"] == plain
    assert config["extra_overrides"] == []


def test_the_runner_pipes_the_merged_list():
    """The capture site itself, since the body above cannot see how it is fed."""
    text = RUNNER.read_text()
    assert 'printf \'%s\\0\' "${argv[@]}" ${extra_overrides[@]+"${extra_overrides[@]}"} | env' in text, (
        "the argv piped into the capture must include the overrides")
