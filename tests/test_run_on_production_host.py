"""`run_on_production_host.sh` constructs the right `docker run` invocation.

This cannot be a real end-to-end test -- it needs Docker, an NVIDIA GPU, and the actual
production host, none of which exist in CI or on this laptop. What it CAN pin, and what would
actually catch a real regression, is that the script builds the correct command: the right image,
the right mounts, the right env-var forwarding, and the right positional arguments into
`run_probe.sh` -- by substituting a stub `docker` binary that records its own argv instead of
running anything, exactly the technique used to develop the script in the first place.
"""
from __future__ import annotations

import pathlib
import stat
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "datasphere" / "native" / "run_on_production_host.sh"


def test_script_is_valid_bash():
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def _stub_docker(tmp_path: pathlib.Path, log_path: pathlib.Path) -> pathlib.Path:
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        f'printf \'%s\\n\' "$@" > "{log_path}"\n'
        'mkdir -p "$(dirname "${@: -1}")" 2>/dev/null || true\n'
        # Find the -v host:/work mount and drop the expected output files there, so the
        # script's own post-run `cp` steps succeed rather than masking what we want to check.
        'work_mount=""\n'
        'prev=""\n'
        'for arg in "$@"; do\n'
        '  if [[ "$prev" == "-v" && "$arg" == *":/work" ]]; then work_mount="${arg%:/work}"; fi\n'
        '  prev="$arg"\n'
        'done\n'
        'if [[ -n "$work_mount" ]]; then\n'
        '  mkdir -p "$work_mount/out"\n'
        '  echo fake-result > "$work_mount/out/result.tgz"\n'
        '  echo \'{"fake": true}\' > "$work_mount/out/records.jsonl"\n'
        'fi\n'
    )
    docker.chmod(docker.stat().st_mode | stat.S_IEXEC)
    return fake_bin


def test_builds_correct_docker_invocation_with_extra_mount(tmp_path):
    code = tmp_path / "payload.tgz"
    code.write_text("payload")
    rlvigen = tmp_path / "rlvigen.tgz"
    rlvigen.write_text("rlvigen")
    snapshot = tmp_path / "snap.pt"
    snapshot.write_text("snapshot")
    result_out = tmp_path / "result.tgz"
    log_path = tmp_path / "docker-argv.txt"

    fake_bin = _stub_docker(tmp_path, log_path)
    env = {
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "CELLS": "drqv2:2",
        "FRAMES": "100000",
        "TASK": "Door",
        "SEED": "2",
        "OFFLINE_EVAL_FAMILY": "rlvigen",
        "OFFLINE_EVAL_BASELINE": "drqv2",
        "EXTRA_MOUNT_1": f"{snapshot}:/work/snap.pt:OFFLINE_EVAL_SNAPSHOT",
        # Unrelated variable that must NOT reach the container (allow-list, not blanket forward).
        "HOME": str(tmp_path),
        "NOT_ON_THE_ALLOW_LIST": "should-not-appear",
    }
    result = subprocess.run(
        ["bash", str(SCRIPT), str(code), str(result_out), str(rlvigen)],
        capture_output=True, text=True, env=env, cwd=str(ROOT),
    )
    assert result.returncode == 0, result.stderr

    argv = log_path.read_text().splitlines()
    joined = " ".join(argv)

    assert "run" in argv and "--rm" in argv
    assert "--gpus" in argv and "all" in argv
    assert "nvidia/cuda:12.2.2-runtime-ubuntu22.04@sha256:" in joined
    assert f"{snapshot}:/work/snap.pt:ro" in argv
    assert "OFFLINE_EVAL_SNAPSHOT=/work/snap.pt" in argv
    assert "CELLS=drqv2:2" in argv
    assert "FRAMES=100000" in argv
    assert "OFFLINE_EVAL_BASELINE=drqv2" in argv
    assert "RECORDS_OUT=/work/out/records.jsonl" in argv, (
        "RECORDS_OUT must be rewritten to a real in-container path, not left as a "
        "DataSphere-output-binding placeholder")
    assert "NOT_ON_THE_ALLOW_LIST" not in joined and "should-not-appear" not in joined, (
        "only allow-listed env vars may reach the container")
    assert "run_probe.sh /work/code.tgz /work/out/result.tgz /work/rlvigen.tgz" in joined

    assert result_out.read_text() == "fake-result\n"


def test_refuses_a_missing_payload(tmp_path):
    missing = tmp_path / "no-such-payload.tgz"
    result = subprocess.run(
        ["bash", str(SCRIPT), str(missing), str(tmp_path / "result.tgz")],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert result.returncode != 0
    assert "no such payload archive" in result.stderr
