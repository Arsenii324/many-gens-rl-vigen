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
        # [Claude 2026-09-08] The wrapper now makes THREE kinds of docker call, not one, and a stub
        # that logs argv and returns nothing breaks two of them:
        #   `docker info`            -- the daemon-reachability check
        #   `docker run <helper>`    -- helper_python, which must PRINT a value on stdout
        #   `docker run <image>`     -- the real cell, whose argv is what these tests inspect
        # Emulate the first two and fall through to the third, so the argv log still holds the run
        # under test rather than whichever call happened last.
        'if [[ "$1" == "info" ]]; then exit 0; fi\n'
        'for arg in "$@"; do\n'
        '  case "$arg" in\n'
        '    *source-lock.json*) echo "nvidia/cuda:12.2.2-runtime-ubuntu22.04@sha256:'
        '94c1577b2cd9dd6c0312dc04dff9cb2fdce2b268018abc3d7c2dbcacf1155000"; exit 0;;\n'
        '    *disk-requirement*)  echo 5; exit 0;;\n'
        '  esac\n'
        'done\n'
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
        # [Claude 2026-09-08] Both are now MANDATORY before the wrapper reaches any other
        # guard: an unnamed GPU and an uncapped VRAM request are each refused first, on
        # purpose, since they cost nothing to check and protect a co-tenant. Each test
        # below asserts a LATER refusal, so it has to get past these two.
        "DOCKER_GPUS": '"device=0"',
        "NATIVE_VRAM_CAP_MIB": "2048",
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
    # [Claude 2026-09-08] This asserted `"all" in argv` -- the default that was REMOVED, because on
    # a machine under a per-day GPU assignment it claimed every card including a neighbour's. The
    # test encoded the hazard as the contract. It now asserts the named card reaches docker, and
    # that the old default is NOT silently back.
    assert "--gpus" in argv, "the named card must reach docker"
    assert '"device=0"' in argv, f"DOCKER_GPUS must be passed through verbatim: {argv[:8]}"
    assert "all" not in argv, "the removed --gpus all default must not reappear"
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
    # [Claude 2026-09-08] The two now-mandatory variables and a docker stub, because the payload
    # check sits after the configuration refusals and the daemon check. It is still BEFORE anything
    # that starts a container for real work, which is the property that matters: a typo in a path
    # is diagnosed as a typo, not as a docker problem.
    fake_bin = _stub_docker(tmp_path, tmp_path / "argv.txt")
    result = subprocess.run(
        ["bash", str(SCRIPT), str(missing), str(tmp_path / "result.tgz")],
        capture_output=True, text=True, cwd=str(ROOT),
        env={"PATH": f"{fake_bin}:/usr/bin:/bin",
             "DOCKER_GPUS": '"device=0"', "NATIVE_VRAM_CAP_MIB": "2048"},
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
    env = {"PATH": f"{_stub_docker(tmp_path, tmp_path / 'argv.txt')}:/usr/bin:/bin",
           "FRAMES": "600000", "NATIVE_HOST_PROFILE": "v100",
           # Mandatory as of 2026-09-08 and refused FIRST; this test asserts a later refusal.
           "DOCKER_GPUS": '"device=0"', "NATIVE_VRAM_CAP_MIB": "2048"}
    result = subprocess.run(
        ["bash", str(SCRIPT), str(code), str(tmp_path / "result.tgz")],
        capture_output=True, text=True, env=env, cwd=str(ROOT),
    )
    assert result.returncode == 3
    assert "NATIVE_PRODUCTION is unset" in result.stderr


def test_production_scale_refuses_without_host_profile(tmp_path):
    code = tmp_path / "payload.tgz"
    code.write_text("payload")
    env = {"PATH": f"{_stub_docker(tmp_path, tmp_path / 'argv.txt')}:/usr/bin:/bin",
           "FRAMES": "600000", "NATIVE_PRODUCTION": "1",
           "DOCKER_GPUS": '"device=0"', "NATIVE_VRAM_CAP_MIB": "2048"}
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
        # [Claude 2026-09-08] Both are now MANDATORY before the wrapper reaches any other
        # guard: an unnamed GPU and an uncapped VRAM request are each refused first, on
        # purpose, since they cost nothing to check and protect a co-tenant. Each test
        # below asserts a LATER refusal, so it has to get past these two.
        "DOCKER_GPUS": '"device=0"',
        "NATIVE_VRAM_CAP_MIB": "2048",
        "CELLS": "drqv2:1,drqv2:2",
        "FRAMES": "600000",
        "NATIVE_PRODUCTION": "1",
        # Required at production scale since 2026-09-07: without a per-cell ceiling one stuck cell
        # burns the job and the result archive, written last, is lost for every completed cell.
        "CELL_TIMEOUT_SECONDS": "7200",
        # [2026-09-08] Production scale now also requires a second-device mirror.
        # tmp_path is on the same filesystem as the result here, so the deviation
        # marker is what keeps these tests about what they are about.
        "NATIVE_RESULT_MIRROR": str(tmp_path / "mirror"),
        "NATIVE_ACCEPT_SAME_DEVICE": "1",
        # [Claude 2026-09-08] macOS cannot report a GNU fsid, so the mirror device is
        # unverifiable here. The guard now REFUSES that rather than accepting a garbage value,
        # which is correct and is why this line is needed.
        "NATIVE_ACCEPT_UNVERIFIED_DEVICE": "1",
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
    # [Claude 2026-09-08] A docker stub is now required here, and it must answer THREE call shapes.
    # `docker info` gates the whole script; `helper_python` computes the disk requirement in a
    # container and must print a number on stdout -- the wrapper stopped running python3 on the
    # host, so a bin with only `df` in it now fails at the daemon check instead of reaching the
    # disk floor this test is about. 48 GB is drqv2:1 at 600k on the v100 profile, against the
    # 10 GB of free space the fake `df` reports.
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "info" ]]; then exit 0; fi\n'
        'for arg in "$@"; do\n'
        '  case "$arg" in\n'
        '    *source-lock.json*) echo "nvidia/cuda:12.2.2-runtime-ubuntu22.04@sha256:'
        '94c1577b2cd9dd6c0312dc04dff9cb2fdce2b268018abc3d7c2dbcacf1155000"; exit 0;;\n'
        '    *disk-requirement*) echo 48; exit 0;;\n'
        '  esac\n'
        'done\n'
        'exit 0\n'
    )
    docker.chmod(docker.stat().st_mode | stat.S_IEXEC)

    env = {
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        # [Claude 2026-09-08] Both are now MANDATORY before the wrapper reaches any other
        # guard: an unnamed GPU and an uncapped VRAM request are each refused first, on
        # purpose, since they cost nothing to check and protect a co-tenant. Each test
        # below asserts a LATER refusal, so it has to get past these two.
        "DOCKER_GPUS": '"device=0"',
        "NATIVE_VRAM_CAP_MIB": "2048",
        "FRAMES": "600000",
        "NATIVE_PRODUCTION": "1",
        # Set so the run reaches the DISK check this test is about; the production-scale ceiling
        # refusal fires earlier and would otherwise mask it.
        "CELL_TIMEOUT_SECONDS": "7200",
        # [2026-09-08] Production scale now also requires a second-device mirror.
        # tmp_path is on the same filesystem as the result here, so the deviation
        # marker is what keeps these tests about what they are about.
        "NATIVE_RESULT_MIRROR": str(tmp_path / "mirror"),
        "NATIVE_ACCEPT_SAME_DEVICE": "1",
        # [Claude 2026-09-08] macOS cannot report a GNU fsid, so the mirror device is
        # unverifiable here. The guard now REFUSES that rather than accepting a garbage value,
        # which is correct and is why this line is needed.
        "NATIVE_ACCEPT_UNVERIFIED_DEVICE": "1",
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
             "DOCKER_GPUS": '"device=0"', "NATIVE_VRAM_CAP_MIB": "2048",
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


def test_a_dry_run_exists_and_stops_before_docker():
    """[Claude 2026-09-08] Until this existed, the operator's FIRST execution of this script on the
    production host would have been its first execution anywhere. Every other test in this file
    reads the source; none runs it. With `set -euo pipefail` and `${VAR:?}`, a missing variable, a
    swapped positional or a typo in the forwarded-variable list surfaces as an abort partway
    through -- on the host, on the day, with the campaign waiting."""
    text = SCRIPT.read_text() if "SCRIPT" in globals() else (
        ROOT / "datasphere" / "native" / "run_on_production_host.sh").read_text()
    assert "NATIVE_HOST_DRY_RUN" in text
    dry = text.index('if [[ -n "${NATIVE_HOST_DRY_RUN:-}" ]]; then')
    docker = text.index("docker run --rm --name")
    assert dry < docker, "the dry run must stop BEFORE docker, or it is not a dry run"
    # it must come after the guards, or it proves nothing about them
    assert text.index("refusing: FRAMES=") < dry
    assert text.index("DOCKER_ENV_ARGS+=(-e \"RECORDS_OUT=") < dry, (
        "the dry run must be after env assembly, so it exercises the forwarding")


def test_the_filesystem_id_probe_validates_its_output():
    """A guard whose failure path depends on a command failing CLEANLY is not a guard.

    `stat -f -c %i` is GNU coreutils, where -f means the filesystem. Where -f means a format
    string instead, the command SUCCEEDS and prints something else -- so the `unreadable` branch
    never fires and a garbage value reaches the same-device comparison. This gates whether the
    campaign's only off-device copy is actually on another device.
    """
    text = (ROOT / "datasphere" / "native" / "run_on_production_host.sh").read_text()
    body = text[text.index("_dev_of()"):text.index("_result_dev=")]
    # [Claude 2026-09-08] This asserted `^[0-9]+$` and was WRONG about the only platform that
    # matters. GNU stat prints a filesystem ID in HEX -- cds2 returns `c4aaf1bac0c3eb66` -- so a
    # numeric-only validation rejected every real id, reported "unreadable" on every production
    # run, and could never reach the same-device branch that carries the durability finding. The
    # test encoded the bug rather than catching it.
    assert "=~ ^[0-9a-fA-F]+$" in body, (
        "the fsid must be validated as HEX: GNU stat prints it that way, and a numeric-only "
        "pattern rejects every real id while a bare non-empty check accepts macOS's garbage")
    # The original defect must still be caught: macOS `stat -f` takes a format string and prints
    # something containing '(' , spaces and the letters r/n/u/s -- none of which are hex.
    for garbage in ("unreadable", "(fsid -c", "9d3f 1a", ""):
        import re
        assert not re.fullmatch(r"[0-9a-fA-F]+", garbage), f"{garbage!r} must not validate"
