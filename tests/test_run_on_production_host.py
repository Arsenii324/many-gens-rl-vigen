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
import sys

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
    # run_probe.sh's third positional is the PLACES365 asset (`asset_archive`, its line ~600), and
    # every cfg-*.yaml that passes a third argument passes Places365 there -- 15 of them -- while
    # RL-ViGen always arrives as `RLVIGEN_ARCHIVE=${RLVIGEN}`. This assertion previously demanded
    # the opposite and so pinned the defect in place.
    assert "run_probe.sh /work/code.tgz /work/out/result.tgz" in joined
    assert "/work/rlvigen.tgz" not in joined.split("run_probe.sh")[1], (
        "the RL-ViGen archive must not be passed positionally; run_probe.sh would treat it as "
        "the Places365 asset")
    assert "RLVIGEN_ARCHIVE=/work/rlvigen.tgz" in argv

    assert result_out.read_text() == "fake-result\n"


def test_refuses_a_missing_payload(tmp_path):
    missing = tmp_path / "no-such-payload.tgz"
    result = subprocess.run(
        ["bash", str(SCRIPT), str(missing), str(tmp_path / "result.tgz")],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert result.returncode != 0
    assert "no such payload archive" in result.stderr


def test_production_scale_refuses_without_native_production(tmp_path):
    """The refusal run_probe.sh raises inside the container must happen on the host first.

    run_probe.sh exits 3 at FRAMES >= 600000 with NATIVE_PRODUCTION unset -- but only after the
    full apt-get/pip bootstrap has been paid for. Catching it here costs nothing.
    """
    code = tmp_path / "payload.tgz"
    code.write_text("payload")
    env = {"PATH": "/usr/bin:/bin", "FRAMES": "600000", "NATIVE_HOST_PROFILE": "v100"}
    result = subprocess.run(
        ["bash", str(SCRIPT), str(code), str(tmp_path / "result.tgz")],
        capture_output=True, text=True, env=env, cwd=str(ROOT),
    )
    assert result.returncode == 3
    assert "NATIVE_PRODUCTION is unset" in result.stderr


def test_production_scale_refuses_without_host_profile(tmp_path):
    code = tmp_path / "payload.tgz"
    code.write_text("payload")
    env = {"PATH": "/usr/bin:/bin", "FRAMES": "600000", "NATIVE_PRODUCTION": "1"}
    result = subprocess.run(
        ["bash", str(SCRIPT), str(code), str(tmp_path / "result.tgz")],
        capture_output=True, text=True, env=env, cwd=str(ROOT),
    )
    assert result.returncode == 3
    assert "NATIVE_HOST_PROFILE is unset" in result.stderr


def test_production_knobs_reach_the_container_and_output_is_host_durable(tmp_path):
    """The variables a production cell needs, and the mount that makes a killed run recoverable.

    NATIVE_PRODUCTION gates apply_production_settings; NATIVE_CONCURRENT gates run_probe.sh's
    parallel cell branch (packing). Both were missing from the forwarding allow-list originally,
    which made this script unable to run the production campaign it exists for.
    """
    code = tmp_path / "payload.tgz"
    code.write_text("payload")
    result_out = tmp_path / "result.tgz"
    log_path = tmp_path / "docker-argv.txt"
    out_dir = tmp_path / "durable-out"

    fake_bin = _stub_docker(tmp_path, log_path)
    env = {
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "CELLS": "drqv2:1,drqv2:2",
        "FRAMES": "600000",
        "NATIVE_PRODUCTION": "1",
        "NATIVE_CONCURRENT": "1",
        "NATIVE_HOST_PROFILE": "v100",
        "NATIVE_OUT_HOST_DIR": str(out_dir),
        # This test is about env forwarding and mounts, not disk: two packed drqv2 cells need
        # 81 GiB and no CI machine is guaranteed to have it.
        "NATIVE_DISK_FLOOR_GB": "1",
        "DOCKER_GPUS": '"device=1"',
    }
    result = subprocess.run(
        ["bash", str(SCRIPT), str(code), str(result_out)],
        capture_output=True, text=True, env=env, cwd=str(ROOT),
    )
    assert result.returncode == 0, result.stderr

    argv = log_path.read_text().splitlines()
    assert "NATIVE_PRODUCTION=1" in argv
    assert "NATIVE_CONCURRENT=1" in argv
    assert "NATIVE_HOST_PROFILE=v100" in argv
    assert "CELLS=drqv2:1,drqv2:2" in argv
    assert '"device=1"' in argv, "DOCKER_GPUS must pin at the docker level, not via CUDA_VISIBLE_DEVICES"
    assert f"{out_dir}:/tmp/native-out" in argv, (
        "run_probe.sh writes every checkpoint to the container-local /tmp/native-out and only "
        "packages it at the very end -- without this mount a killed container loses the whole run")
    assert out_dir.is_dir()


def test_production_scale_refuses_when_disk_is_below_the_floor(tmp_path):
    """An off-policy production cell needs ~25 GB (19 GB of replay episodes alone).

    Discovering that after several hours of training, when a checkpoint write fails, is the
    failure this guard exists to prevent.
    """
    code = tmp_path / "payload.tgz"
    code.write_text("payload")
    fake_bin = tmp_path / "diskbin"
    fake_bin.mkdir()
    df = fake_bin / "df"
    # 10 GB free, reported in 1K blocks in the position `df -Pk` puts it.
    df.write_text(
        "#!/usr/bin/env bash\n"
        'echo "Filesystem 1024-blocks Used Available Capacity Mounted on"\n'
        'echo "/dev/fake 100000000 89500000 10485760 90% /"\n'
    )
    df.chmod(df.stat().st_mode | stat.S_IEXEC)

    env = {
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "FRAMES": "600000",
        "NATIVE_PRODUCTION": "1",
        "NATIVE_HOST_PROFILE": "v100",
        "NATIVE_OUT_HOST_DIR": str(tmp_path / "out"),
        "CELLS": "drqv2:1",
    }
    result = subprocess.run(
        ["bash", str(SCRIPT), str(code), str(tmp_path / "result.tgz")],
        capture_output=True, text=True, env=env, cwd=str(ROOT),
    )
    assert result.returncode == 4, result.stderr
    assert "below the" in result.stderr and "GB this job needs" in result.stderr
    assert "disk-requirement --cells" in result.stderr, (
        "the refusal must name the command that explains the number")


def test_the_live_run_directory_is_mounted_not_just_the_cell_output(tmp_path):
    """Checkpoints are written under {run_dir} = /tmp/native-work, not /tmp/native-out.

    families.json's artifact_root is `{run_dir}` for five of seven families and a subdirectory of
    it for the other two, and `family.py retain` copies into the cell output only AFTER training
    finishes. Mounting the cell output alone made training.log durable and nothing else, so a
    container killed at hour 20 of a 27-hour cell lost every checkpoint it had written.
    """
    code = tmp_path / "payload.tgz"
    code.write_text("payload")
    result_out = tmp_path / "result.tgz"
    log_path = tmp_path / "docker-argv.txt"
    fake_bin = _stub_docker(tmp_path, log_path)
    out_dir = tmp_path / "out"
    work_dir = tmp_path / "work"

    result = subprocess.run(
        ["bash", str(SCRIPT), str(code), str(result_out)],
        capture_output=True, text=True, cwd=str(ROOT),
        env={"PATH": f"{fake_bin}:/usr/bin:/bin", "NATIVE_DISK_FLOOR_GB": "1",
             "NATIVE_OUT_HOST_DIR": str(out_dir), "NATIVE_WORK_HOST_DIR": str(work_dir)},
    )
    assert result.returncode == 0, result.stderr
    argv = log_path.read_text().splitlines()
    assert f"{out_dir}:/tmp/native-out" in argv
    assert f"{work_dir}:/tmp/native-work" in argv, (
        "the live run directory holds the checkpoints as they are written")
    assert work_dir.is_dir()


def test_the_disk_floor_is_per_family_not_one_constant():
    """A single 60 GB floor is right for one off-policy cell and 30x too strict for idaac.

    A guard that is wrong for half the fleet gets overridden as a matter of routine, and a
    routinely-overridden guard is not a guard.
    """
    sys.path.insert(0, str(ROOT / "datasphere" / "native"))
    import family

    off_policy = family.disk_requirement_gib("drqv2:1", 600_000, profile="v100")["required_gib"]
    on_policy = family.disk_requirement_gib("idaac:1", 600_000, profile="v100")["required_gib"]
    packed = family.disk_requirement_gib("drqv2:1,drqv2:2", 600_000, profile="v100")["required_gib"]

    assert 40 < off_policy < 50, off_policy
    assert on_policy < 10, on_policy
    assert packed > off_policy * 1.8, "packing two cells roughly doubles the requirement"
    probe = family.disk_requirement_gib("drqv2:1", 10_000, profile="v100")["required_gib"]
    assert probe < 10, "a 10k probe must not be sized against a 600k replay buffer"


def test_preflight_script_is_valid_and_fails_closed(tmp_path):
    """Eight checks, exit 0 only if all pass -- and it must FAIL where it cannot verify.

    Run here it cannot reach a Docker daemon or a GPU, and the right behaviour is to say so and
    refuse, not to pass by default. A preflight that greens on a machine it cannot inspect is worse
    than no preflight.
    """
    script = ROOT / "datasphere" / "native" / "preflight_production_host.sh"
    syntax = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert syntax.returncode == 0, syntax.stderr

    result = subprocess.run(["bash", str(script), "--cells", "idaac:1", "--frames", "600000"],
                            capture_output=True, text=True, cwd=str(ROOT))
    assert result.returncode != 0, "must refuse when it cannot verify the host"
    assert "Do not start a production cell" in result.stdout
    # The checks that ARE decidable from any machine must still be made rather than skipped.
    assert "source-lock pins an image" in result.stdout
    assert "disk:" in result.stdout
    assert "memory model" in result.stdout
    assert "renderer parity" in result.stdout, (
        "a green preflight must not be mistakable for a renderer-parity pass")
