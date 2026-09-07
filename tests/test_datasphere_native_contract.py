"""Regression tests for the native-only DataSphere pre-submission contract.

Each test runs the contract tool as a user would; it does not inspect source text.
"""

from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "datasphere" / "native" / "contract.py"
RUNNER = ROOT / "datasphere" / "native" / "run_probe.sh"
PLACES_CONFIGURER = ROOT / "datasphere" / "native" / "configure_places365_val.py"
PREFLIGHT_CONFIG = ROOT / "datasphere" / "native" / "cfg-preflight.yaml"
PROBE_SCHEDULE = ROOT / "datasphere" / "native" / "probe-schedule.json"
RESOURCE_SAMPLER = ROOT / "datasphere" / "native" / "measure_resources.py"


def _runner_contract() -> int:
    return int(runpy.run_path(str(TOOL))["RUNNER_CONTRACT"])


ROBOSUITE_IMPORT_CLOSURE = ROOT / "datasphere" / "native" / "robosuite-import-closure.json"
DRQV2_CALIBRATION_CONFIG = ROOT / "datasphere" / "native" / "cfg-drqv2-calibration-a.yaml"
DRQV2_REPAIRED_CALIBRATION_CONFIG = ROOT / "datasphere" / "native" / "cfg-drqv2-calibration-a-v11.yaml"
DRQV2_IMPORT_GATED_CALIBRATION_CONFIG = ROOT / "datasphere" / "native" / "cfg-drqv2-calibration-a-v12.yaml"
DRQV2_CLOSURE_CALIBRATION_CONFIG = ROOT / "datasphere" / "native" / "cfg-drqv2-calibration-a-v14.yaml"
# [Codex 2026-09-01 15:01 MSK: reserve a distinct immutable retry configuration after the v14 raw failure audit]
DRQV2_MATPLOTLIB_CLOSURE_CALIBRATION_CONFIG = ROOT / "datasphere" / "native" / "cfg-drqv2-calibration-a-v15.yaml"
# [Codex 2026-09-01 15:04 MSK: reserve a distinct immutable retry configuration after adding the RobosuiteVGB import gate]
DRQV2_WRAPPER_GATE_CALIBRATION_CONFIG = ROOT / "datasphere" / "native" / "cfg-drqv2-calibration-a-v16.yaml"
# [Codex 2026-09-01 15:52 MSK: reserve an immutable config for the reviewed source-hashed dependency-closure calibration]
DRQV2_SOURCE_CLOSURE_CALIBRATION_CONFIG = ROOT / "datasphere" / "native" / "cfg-drqv2-calibration-a-v17.yaml"
DRQV2_TERMINAL_EVAL_CALIBRATION_CONFIG = ROOT / "datasphere" / "native" / "cfg-drqv2-calibration-a-v18.yaml"
# [Codex 2026-09-01 20:34 MSK: bind the first strict-P16 SVEA probe to a new immutable configuration]
SVEA_STRICT_CALIBRATION_CONFIG = ROOT / "datasphere" / "native" / "cfg-svea-asset-calibration-v20.yaml"
ALDA_PAYLOAD_TOOL = ROOT / "datasphere" / "alda" / "contract.py"
# [Claude 2026-09-02 02:45 MSK: the first multi-cell calibration configuration]
TRIO_CALIBRATION_CONFIG = ROOT / "datasphere" / "native" / "cfg-rlvigen-trio-calibration-v21.yaml"


def test_payload_build_rejects_a_secret_before_creating_an_archive(tmp_path):
    """Catches a future allowlist regression that would upload credentials."""
    source = tmp_path / "source"
    (source / "runnable" / "_launch").mkdir(parents=True)
    (source / "runnable" / "_launch" / "rlvigen.sh").write_text("#!/usr/bin/env bash\n")
    (source / "setup").mkdir()
    (source / "setup" / "apply_patches.py").write_text("print('ok')\n")
    (source / "requirements-native.txt").write_text("numpy==1.26.4\n")
    (source / "wandb_key.txt").write_text("must-not-leave-this-machine\n")
    archive = tmp_path / "payload.tgz"

    result = subprocess.run(
        [sys.executable, str(TOOL), "build-payload", "--source", str(source), "--output", str(archive)],
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "forbidden payload member" in result.stderr
    assert not archive.exists()


# [Codex 2026-09-01 21:42 MSK: require an ALDA-specific payload boundary instead of widening the SVEA archive]
def test_alda_payload_builder_rejects_a_secret_before_creating_an_archive(tmp_path):
    """A future ALDA archive must fail locally rather than upload credentials."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "wandb_key.txt").write_text("must-not-leave-this-machine\n")
    archive = tmp_path / "alda-payload.tgz"

    result = subprocess.run(
        [sys.executable, str(ALDA_PAYLOAD_TOOL), "build-payload", "--source", str(source), "--output", str(archive)],
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "forbidden payload member" in result.stderr
    assert not archive.exists()


def test_alda_payload_verifier_rejects_a_prior_result_or_checkpoint(tmp_path):
    """A sealed ALDA source archive must never smuggle a previous run into a probe."""
    archive = tmp_path / "alda-bad-payload.tgz"
    checkpoint = tmp_path / "snapshot.pt"
    checkpoint.write_bytes(b"prior-state")
    with tarfile.open(archive, "w:gz") as handle:
        handle.add(checkpoint, arcname="runnable/alda/results/snapshot.pt")

    result = subprocess.run(
        [sys.executable, str(ALDA_PAYLOAD_TOOL), "verify-payload", "--archive", str(archive)],
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "payload member" in result.stderr


def test_probe_runner_preserves_a_training_failure_through_tee(tmp_path):
    """Catches a pipe without pipefail that turns a failed trainer into a green job."""
    result = subprocess.run(
        ["bash", str(RUNNER), "--test-command", "false", "--output", str(tmp_path / "run")],
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert (tmp_path / "run" / "training.log").exists()


def test_probe_runner_measures_a_successful_training_process_tree(tmp_path):
    """The calibration wrapper emits sampled resource evidence alongside trainer output."""
    output = tmp_path / "run"
    result = subprocess.run(
        [
            "bash",
            str(RUNNER),
            "--measure-command",
            "python3 -c 'import time; time.sleep(0.1)'",
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads((output / "resources.json").read_text())
    assert report["samples"]


def test_result_archive_accepts_tar_dot_prefix_for_the_required_manifest(tmp_path):
    """A successful run must not turn red because GNU tar lists members as `./name`."""
    archive = tmp_path / "result.tgz"
    manifest = tmp_path / "run_manifest.json"
    manifest.write_text("{}")
    with tarfile.open(archive, "w:gz") as handle:
        handle.add(manifest, arcname="./run_manifest.json")

    result = subprocess.run(
        ["bash", str(RUNNER), "--verify-result-archive", str(archive)],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "tarfile.open" in RUNNER.read_text()


def test_runner_has_an_unambiguous_completion_marker():
    """A remote status error without a shell line must remain diagnosable from raw logs."""
    assert "native probe completed successfully" in RUNNER.read_text()


def test_asset_gate_rejects_an_absent_places365_validation_split(tmp_path):
    """Catches an implicit directory fallback before SVEA can begin training."""
    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "check-asset",
            "--asset",
            str(tmp_path / "missing-val"),
            "--expected-count",
            "36500",
            "--expected-sha256",
            "0" * 64,
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "Places365 validation asset is absent" in result.stderr


def test_places_loader_selects_val_directly_and_rejects_the_old_fallback(tmp_path):
    """SVEA's no-argument loader must resolve val, never a parent directory."""
    from PIL import Image

    upstream = tmp_path / "RL-ViGen-upstream"
    upstream.mkdir()
    source_utils = ROOT / "RL-ViGen-upstream" / "utils.py"
    (upstream / "utils.py").write_text(source_utils.read_text())
    (upstream / "cfgs").mkdir()
    (upstream / "cfgs" / "aug_config.cfg").write_text(
        (ROOT / "RL-ViGen-upstream" / "cfgs" / "aug_config.cfg").read_text()
    )

    data_root = tmp_path / "places-root"
    images = data_root / "places365_standard" / "val" / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (8, 8)).save(images / "one.jpg")

    configured = subprocess.run(
        [
            sys.executable,
            str(PLACES_CONFIGURER),
            "--repo",
            str(upstream),
            "--dataset-root",
            str(data_root),
        ],
        text=True,
        capture_output=True,
    )
    assert configured.returncode == 0, configured.stderr

    loaded = subprocess.run(
        [
            sys.executable,
            "-c",
            "import pathlib, sys; sys.path.insert(0, sys.argv[1]); import utils; "
            "utils._load_places(batch_size=1, image_size=8, num_workers=0); "
            "assert pathlib.Path(utils.places_dataloader.dataset.root) == pathlib.Path(sys.argv[2])",
            str(upstream),
            str(images.parent),
        ],
        text=True,
        capture_output=True,
    )
    assert loaded.returncode == 0, loaded.stderr

    for child in sorted(images.parent.rglob("*"), reverse=True):
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    images.parent.rmdir()
    rejected = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, sys.argv[1]); import utils; "
            "utils._load_places(batch_size=1, image_size=8, num_workers=0)",
            str(upstream),
        ],
        text=True,
        capture_output=True,
    )
    assert rejected.returncode != 0
    assert "fallback disabled" in rejected.stderr


def test_preflight_is_a_bounded_svea_asset_path_gate():
    """The scheduled preflight must exercise the SVEA loader within its 20-minute cap."""
    config = PREFLIGHT_CONFIG.read_text()

    assert "timeout --foreground 1200s" in config
    assert "PREFLIGHT_ONLY=1 BASELINE=svea" in config
    assert "FRAMES=0" in config
    assert "- places365-val.tgz: PLACES365_VAL" in config
    assert "nvidia/cuda:12.2.2-runtime-ubuntu22.04" in config

    schedule = json.loads(PROBE_SCHEDULE.read_text())
    preflight = next(job for job in schedule["serial_jobs"] if job["name"] == "preflight")
    assert preflight["baseline"] == "svea"
    assert preflight["frames"] == 0


def test_preflight_manifest_declares_that_it_did_not_train():
    """An environment gate must not masquerade as a 10k training measurement."""
    runner = RUNNER.read_text()

    assert '"preflight_only"' in runner
    # [Claude 2026-09-02 00:55 MSK: the preflight branch must still declare an empty endpoint marker;
    # the resource-source string moved into the per-baseline manifest when one job gained several runs]
    assert 'PREFLIGHT_ONLY:-0' in runner
    assert 'export FINAL_EVALUATION_MARKER=""' in runner
    assert '"resource_high_water_source": "GNU time -v in each cells/<baseline>-s<seed>/training.log"' in runner


def test_drqv2_calibration_does_not_receive_svea_places365_asset():
    """Places365 is a SVEA-only private asset, never a hidden DrQ-v2 dependency."""
    config = DRQV2_CALIBRATION_CONFIG.read_text()

    assert "timeout --foreground 1800s" in config
    assert "BASELINE=drqv2 FRAMES=10000" in config
    assert "places365" not in config.lower()
    assert "bash ${JOB} ${CODE} ${RESULT}" in config


def test_repaired_drqv2_calibration_references_only_the_reviewed_v11_payload():
    """The dependency repair must be a new immutable job configuration, never a rewritten v9 record."""
    assert DRQV2_REPAIRED_CALIBRATION_CONFIG.exists()
    config = DRQV2_REPAIRED_CALIBRATION_CONFIG.read_text()

    assert "native-payload-v11.tgz: CODE" in config
    assert "BASELINE=drqv2 FRAMES=10000 TASK=Door SEED=1" in config
    assert "places365" not in config.lower()
    assert "nvidia/cuda:12.2.2-runtime-ubuntu22.04" in config


def test_import_gated_drqv2_calibration_references_only_the_reviewed_v12_payload():
    """The final dependency-contract retry must bind the import-gated payload immutably."""
    assert DRQV2_IMPORT_GATED_CALIBRATION_CONFIG.exists()
    config = DRQV2_IMPORT_GATED_CALIBRATION_CONFIG.read_text()

    assert "native-payload-v12.tgz: CODE" in config
    assert "BASELINE=drqv2 FRAMES=10000 TASK=Door SEED=1" in config
    assert "places365" not in config.lower()
    assert "nvidia/cuda:12.2.2-runtime-ubuntu22.04" in config


def test_dependency_closure_drqv2_calibration_references_only_the_reviewed_v14_payload():
    """The audited dependency closure must become a new immutable calibration configuration."""
    assert DRQV2_CLOSURE_CALIBRATION_CONFIG.exists()
    config = DRQV2_CLOSURE_CALIBRATION_CONFIG.read_text()

    assert "datasphere/native/run_probe.sh: JOB" in config
    assert "native-payload-v14.tgz: CODE" in config
    assert "BASELINE=drqv2 FRAMES=10000 TASK=Door SEED=1" in config
    assert "places365" not in config.lower()
    assert "nvidia/cuda:12.2.2-runtime-ubuntu22.04" in config
    assert "cloud-instance-type: gt4.1" in config


def test_matplotlib_closure_drqv2_calibration_is_a_new_unsubmitted_config():
    """The raw-audited v14 failure requires a new immutable payload/config pair."""
    assert DRQV2_MATPLOTLIB_CLOSURE_CALIBRATION_CONFIG.exists()
    config = DRQV2_MATPLOTLIB_CLOSURE_CALIBRATION_CONFIG.read_text()

    assert "datasphere/native/run_probe.sh: JOB" in config
    assert "native-payload-v15.tgz: CODE" in config
    assert "BASELINE=drqv2 FRAMES=10000 TASK=Door SEED=1" in config
    assert "places365" not in config.lower()
    assert "nvidia/cuda:12.2.2-runtime-ubuntu22.04" in config
    assert "cloud-instance-type: gt4.1" in config


def test_wrapper_gate_drqv2_calibration_is_a_new_unsubmitted_config():
    """A changed fail-closed gate must seal a new payload/config pair."""
    assert DRQV2_WRAPPER_GATE_CALIBRATION_CONFIG.exists()
    config = DRQV2_WRAPPER_GATE_CALIBRATION_CONFIG.read_text()

    assert "datasphere/native/run_probe.sh: JOB" in config
    assert "native-payload-v16.tgz: CODE" in config
    assert "BASELINE=drqv2 FRAMES=10000 TASK=Door SEED=1" in config
    assert "places365" not in config.lower()
    assert "nvidia/cuda:12.2.2-runtime-ubuntu22.04" in config
    assert "cloud-instance-type: gt4.1" in config


def test_source_closure_drqv2_calibration_is_a_new_unsubmitted_config():
    """A source-hashed dependency closure must bind a new immutable payload/config pair."""
    assert DRQV2_SOURCE_CLOSURE_CALIBRATION_CONFIG.exists()
    config = DRQV2_SOURCE_CLOSURE_CALIBRATION_CONFIG.read_text()

    assert "datasphere/native/run_probe.sh: JOB" in config
    assert "native-payload-v17.tgz: CODE" in config
    assert "BASELINE=drqv2 FRAMES=10000 TASK=Door SEED=1" in config
    assert "places365" not in config.lower()
    assert "nvidia/cuda:12.2.2-runtime-ubuntu22.04" in config
    assert "cloud-instance-type: gt4.1" in config


def test_terminal_eval_drqv2_calibration_binds_a_new_p15_payload():
    """The endpoint protocol change must not rewrite or reuse the v17 record."""
    assert DRQV2_TERMINAL_EVAL_CALIBRATION_CONFIG.exists()
    config = DRQV2_TERMINAL_EVAL_CALIBRATION_CONFIG.read_text()

    assert "native-payload-v18.tgz: CODE" in config
    assert "BASELINE=drqv2 FRAMES=10000 TASK=Door SEED=1" in config
    assert "places365" not in config.lower()
    assert "nvidia/cuda:12.2.2-runtime-ubuntu22.04" in config
    assert "cloud-instance-type: gt4.1" in config


def test_svea_calibration_binds_the_strict_p16_payload_and_private_val_asset():
    """A finite SVEA probe must not reuse a pre-strict payload or omit its declared val asset."""
    assert SVEA_STRICT_CALIBRATION_CONFIG.exists()
    config = SVEA_STRICT_CALIBRATION_CONFIG.read_text()

    assert "timeout --foreground 1800s" in config
    assert "BASELINE=svea FRAMES=10000 TASK=Door SEED=1" in config
    assert "native-payload-v20.tgz: CODE" in config
    assert "- places365-val.tgz: PLACES365_VAL" in config
    assert "PLACES365_EXPECTED_COUNT=36500" in config
    assert "PLACES365_EXPECTED_SHA256=70237503ec14fba495dd9440ce2901707447a142933773a4441e446788f57669" in config
    assert "bash ${JOB} ${CODE} ${RESULT} ${PLACES365_VAL}" in config
    assert "cloud-instance-type: gt4.1" in config


def test_rlvigen_launcher_uses_a_remote_selected_python_interpreter(tmp_path):
    """A remote run must invoke its supplied interpreter, not a developer's local venv."""
    launcher = tmp_path / "runnable" / "_launch" / "rlvigen.sh"
    launcher.parent.mkdir(parents=True)
    launcher.write_text((ROOT / "runnable" / "_launch" / "rlvigen.sh").read_text())
    launcher.chmod(0o755)
    (tmp_path / "RL-ViGen-upstream").mkdir()
    invocation = tmp_path / "invocation.txt"
    interpreter = tmp_path / "remote-python"
    interpreter.write_text(f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" > {invocation}\n")
    interpreter.chmod(0o755)

    result = subprocess.run(
        ["bash", str(launcher), "drqv2", "Door"],
        env={**__import__("os").environ, "PYTHON_BIN": str(interpreter)},
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert invocation.exists()
    assert invocation.read_text().startswith("train.py --config-name config")


def test_box1_launchers_use_a_remote_selected_python_interpreter(tmp_path):
    """ALDA, IDAAC, and PPG must not reintroduce a developer-local venv dependency."""
    launches = {
        "alda": ([], "runnable/alda", "scripts/train.py"),
        "idaac": (["idaac", "Door", "1"], "runnable/idaac", "train.py"),
        "ppg": (["Door", "1"], "runnable/ppg", "-m phasic_policy_gradient.train"),
        # [Claude 2026-09-02 00:35 MSK: ctrl, ibac_sni and dmc_gb kept the developer-local venv
        # default that already cost job bt1rpl91299g2o84chib; cover every launcher, not the audited three]
        "ctrl": (["Door", "2"], "runnable/ctrl", "train_ppo.py"),
        "ibac_sni": (["Door", "2"], "runnable/ibac_sni/torch_rl", "scripts/train.py"),
        "dmc_gb": (["rad", "Door", "0"], "runnable/dmc_gb", "src/train.py"),
    }
    for name, (arguments, workdir, expected) in launches.items():
        launcher = tmp_path / "runnable" / "_launch" / f"{name}.sh"
        launcher.parent.mkdir(parents=True, exist_ok=True)
        launcher.write_text((ROOT / "runnable" / "_launch" / f"{name}.sh").read_text())
        launcher.chmod(0o755)
        (tmp_path / workdir).mkdir(parents=True, exist_ok=True)
        invocation = tmp_path / f"{name}-invocation.txt"
        interpreter = tmp_path / f"{name}-remote-python"
        interpreter.write_text(f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" > {invocation}\n")
        interpreter.chmod(0o755)

        result = subprocess.run(
            ["bash", str(launcher), *arguments],
            env={**__import__("os").environ, "PYTHON_BIN": str(interpreter)},
            text=True,
            capture_output=True,
        )

        assert result.returncode == 0, f"{name}: {result.stderr}"
        assert invocation.exists(), name
        assert invocation.read_text().startswith(expected), name


# [Codex 2026-09-01 21:41 MSK: require the ALDA launch environment to expose its separately vendored models package]
# [Claude 2026-09-02 09:05 MSK: rewritten. The previous version asserted that third_party/alda was
# ON the path, which was true and still broken: third_party/alda/trainers/ is a regular package and
# runnable/alda/trainers/ is a namespace package, and Python resolves a regular package ahead of a
# namespace one regardless of path order -- so putting that directory on the path shadowed ALDA's
# own trainers and `import trainers.alda_trainer` failed outright. A test that checks the path is
# not a test that checks the import. This one imports.]
def test_alda_launch_environment_reaches_models_without_shadowing_alda_s_own_packages(tmp_path):
    launcher = tmp_path / "runnable" / "_launch" / "alda.sh"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text((ROOT / "runnable" / "_launch" / "alda.sh").read_text())
    launcher.chmod(0o755)

    # a miniature of the real collision: `trainers` exists in both trees, only one has __init__.py
    (tmp_path / "runnable" / "alda" / "trainers").mkdir(parents=True)
    (tmp_path / "runnable" / "alda" / "trainers" / "alda_trainer.py").write_text("MARKER = 'alda-own'\n")
    (tmp_path / "third_party" / "alda" / "trainers").mkdir(parents=True)
    (tmp_path / "third_party" / "alda" / "trainers" / "__init__.py").write_text("")
    (tmp_path / "third_party" / "alda" / "models").mkdir(parents=True)
    (tmp_path / "third_party" / "alda" / "models" / "__init__.py").write_text("")
    (tmp_path / "third_party" / "alda" / "models" / "sac.py").write_text("MARKER = 'vendored-models'\n")

    interpreter = tmp_path / "remote-python"
    captured = tmp_path / "pythonpath.txt"
    interpreter.write_text(f"#!/usr/bin/env bash\nprintf '%s' \"$PYTHONPATH\" > {captured}\n")
    interpreter.chmod(0o755)

    result = subprocess.run(
        ["bash", str(launcher)],
        env={**__import__("os").environ, "PYTHON_BIN": str(interpreter)},
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr

    program = (
        "import trainers.alda_trainer as t, models.sac as m\n"
        "assert t.MARKER == 'alda-own', t.MARKER\n"
        "assert m.MARKER == 'vendored-models', m.MARKER\n"
        "print('NO_SHADOWING')\n"
    )
    imported = subprocess.run(
        [sys.executable, "-c", program],
        env={**__import__("os").environ, "PYTHONPATH": captured.read_text()},
        cwd=str(tmp_path / "runnable" / "alda"),
        text=True,
        capture_output=True,
    )
    assert imported.returncode == 0, imported.stderr
    assert "NO_SHADOWING" in imported.stdout


def test_bootstrap_provisions_python_before_using_it():
    """The runtime image is minimal, so Python must be installed before the first invocation."""
    runner = RUNNER.read_text()

    assert "python3-pip" in runner
    assert runner.index("apt-get -qq install") < runner.index("python3 -V")
    assert "DEBIAN_FRONTEND=noninteractive" in runner
    assert runner.index("DEBIAN_FRONTEND=noninteractive") < runner.index("apt-get -qq update")
    assert "libxrender1 time" in runner


def test_native_requirements_include_upstream_logger_dependency():
    """RL-ViGen's logger imports termcolor although its upstream metadata omits it."""
    requirements = (ROOT / "requirements-native.txt").read_text()

    assert "termcolor==2.5.0" in requirements


# [Codex 2026-09-01 15:01 MSK: lock the robosuiteVGB import closure exposed by failed remote job bt15uqu1idas8dkq38vf]
def test_native_requirements_include_robosuitevgb_import_dependency():
    """The vendored robosuiteVGB package imports matplotlib without metadata."""
    requirements = (ROOT / "requirements-native.txt").read_text()

    assert "matplotlib==3.7.5" in requirements


# [Codex 2026-09-01 15:20 MSK: prevent an incomplete upstream import graph from becoming another paid remote discovery]
def test_robosuite_import_closure_verifies_source_hashes_and_exact_pins(tmp_path):
    """The source-audited closure must reject a missing pin before remote timing."""
    checked = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "verify-robosuite-closure",
            "--source",
            str(ROOT / "RL-ViGen-upstream"),
            "--requirements",
            str(ROOT / "requirements-native.txt"),
            "--closure",
            str(ROBOSUITE_IMPORT_CLOSURE),
        ],
        text=True,
        capture_output=True,
    )
    assert checked.returncode == 0, checked.stderr

    incomplete = tmp_path / "requirements-native.txt"
    incomplete.write_text((ROOT / "requirements-native.txt").read_text().replace("h5py==3.11.0\n", ""))
    rejected = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "verify-robosuite-closure",
            "--source",
            str(ROOT / "RL-ViGen-upstream"),
            "--requirements",
            str(incomplete),
            "--closure",
            str(ROBOSUITE_IMPORT_CLOSURE),
        ],
        text=True,
        capture_output=True,
    )
    assert rejected.returncode != 0
    assert "missing exact closure requirement: h5py==3.11.0" in rejected.stderr


def test_native_requirements_pin_every_direct_robosuite_dependency():
    """--no-deps is valid only when the remote input closes Robosuite's direct requirements."""
    requirements = (ROOT / "requirements-native.txt").read_text().splitlines()
    pinned = {
        line.split("==", 1)[0].lower().replace("_", "-")
        for line in requirements
        if "==" in line and not line.lstrip().startswith("#")
    }

    assert {
        "numpy",
        "numba",
        "scipy",
        "mujoco",
        "pillow",
        "opencv-python",
        "pynput",
        "termcolor",
    } <= pinned


def test_runner_records_resolved_dependency_versions_for_each_result():
    """A successful remote result must retain the actual resolver output, not only requested pins."""
    runner = RUNNER.read_text()

    assert '"$out/resolved_packages.json"' in runner
    assert '"resolved_packages": read_json(OUT / "resolved_packages.json")' in runner


def test_offline_wandb_shim_never_reaches_the_network_and_records_what_was_logged(tmp_path):
    """The shim's contract, restated 2026-09-03.

    It was "import may succeed, any tracking call must raise". `ctrl` cannot satisfy that: its
    `train_ppo.py:111` calls `wandb.init(...)` unconditionally with no flag to turn off, so a
    raising `init` means the baseline cannot run -- which is what happened to attempt #10.

    The property actually worth defending is that nothing leaves the machine, and that a run whose
    only metric sink is W&B does not silently produce nothing. So: default mode records to a local
    JSONL, strict mode still refuses, and neither imports a client or opens a socket.
    """
    import json as _json
    import os as _os

    shim = ROOT / "runnable" / "_shim" / "wandb.py"
    assert shim.exists()
    sink = tmp_path / "sink.jsonl"
    base = {**_os.environ, "PYTHONPATH": str(shim.parent), "RLGEN_WANDB_JSONL": str(sink)}
    base.pop("RLGEN_WANDB_STRICT", None)

    program = (
        "import wandb; wandb.init(project='p', config={'a': 1}); "
        "wandb.log({'episode_reward': 1.5}, step=64); wandb.finish()"
    )
    recorded = subprocess.run([sys.executable, "-c", program], cwd=tmp_path, env=base,
                              text=True, capture_output=True)
    assert recorded.returncode == 0, recorded.stderr

    events = [_json.loads(line) for line in sink.read_text().splitlines() if line.strip()]
    assert [event["_event"] for event in events] == ["init", "log", "finish"]
    # The point of recording rather than no-op'ing: the value and its x-axis both survive.
    assert events[1]["data"]["episode_reward"] == 1.5
    assert events[1]["step"] == 64

    # Fail-closed is still one variable away, for a probe that wants to assert a baseline is silent.
    strict = subprocess.run([sys.executable, "-c", "import wandb; wandb.init()"], cwd=tmp_path,
                            env={**base, "RLGEN_WANDB_STRICT": "1"}, text=True, capture_output=True)
    assert strict.returncode != 0
    assert "W&B tracking is disabled" in strict.stderr

    # No network, checked at the source rather than by watching a socket: the module imports
    # nothing that could carry a request, and the real client is never reached for.
    source = shim.read_text()
    for forbidden in ("import requests", "import socket", "urllib", "http.client", "wandb_sdk"):
        assert forbidden not in source, forbidden


def test_runner_import_gates_native_entrypoint_before_timed_training():
    """A missing import must stop before it can be confused with a resource calibration."""
    runner = RUNNER.read_text()

    assert 'importlib.import_module("train")' in runner
    assert runner.index('importlib.import_module("train")') < runner.index('run_cell_list "$cells"')
    # [Codex 2026-09-01 15:04 MSK: exercise the RobosuiteVGB import boundary that v14 reached only after measurement began]
    assert 'importlib.import_module("wrappers.robo_wrapper")' in runner
    assert runner.index('importlib.import_module("wrappers.robo_wrapper")') < runner.index('run_cell_list "$cells"')


def test_native_train_import_resolves_through_the_offline_shim():
    """The exact module path used remotely imports before a new calibration is scheduled."""
    environment = {
        **__import__("os").environ,
        "MUJOCO_GL": "egl",
        "PYOPENGL_PLATFORM": "egl",
        "WANDB_MODE": "offline",
        "WANDB_DISABLED": "true",
        "PYTHONPATH": ":".join(
            str(path)
            for path in (
                ROOT / "RL-ViGen-upstream",
                ROOT / "RL-ViGen-upstream" / "algos",
                ROOT / "RL-ViGen-upstream" / "envs" / "robosuiteVGB",
                ROOT / "runnable" / "_shim",
            )
        ),
    }

    result = subprocess.run(
        [sys.executable, "-c", "import train"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr


def test_bootstrap_records_and_rejects_a_software_egl_renderer():
    """CUDA availability alone does not prove the robosuite renderer is hardware-backed."""
    runner = RUNNER.read_text()

    assert '"$out/egl.json"' in runner
    assert "GL.glGetString(GL.GL_RENDERER)" in runner
    assert "software EGL renderer" in runner


def test_payload_verifier_rejects_an_undeclared_checkpoint(tmp_path):
    """Catches a future archive-member regression that leaks a prior run."""
    archive = tmp_path / "bad.tgz"
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"prior-result")
    with tarfile.open(archive, "w:gz") as handle:
        handle.add(checkpoint, arcname="results/checkpoint.pt")
    result = subprocess.run(
        [sys.executable, str(TOOL), "verify-payload", "--archive", str(archive)],
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "undeclared payload member" in result.stderr


def test_resource_sampler_records_cpu_topology_affinity_and_process_samples(tmp_path):
    """A calibration needs evidence of where its worker actually ran, not just elapsed time."""
    worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.35)"])
    output = tmp_path / "resources.json"
    result = subprocess.run(
        [
            sys.executable,
            str(RESOURCE_SAMPLER),
            "--pid",
            str(worker.pid),
            "--output",
            str(output),
            "--interval-seconds",
            "0.02",
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text())
    assert report["host"]["logical_cpu_count"] >= 1
    assert report["host"]["affinity"]
    assert report["samples"]
    assert any(sample["process_count"] >= 1 for sample in report["samples"])


def test_resource_sampler_parses_per_gpu_utilization_and_memory():
    """A tier decision needs sampled GPU load, not only a GPU process's VRAM allocation."""
    from datasphere.native.measure_resources import parse_gpu_devices

    devices = parse_gpu_devices("GPU-123, 38, 7, 1024, 23034")

    assert devices == [
        {
            "gpu_uuid": "GPU-123",
            "utilization_gpu_percent": 38,
            "utilization_memory_percent": 7,
            "used_memory_mib": 1024,
            "total_memory_mib": 23034,
        }
    ]


def test_terminal_train_hook_evaluates_and_retains_the_exact_final_frame():
    """A finite calibration must not exit after its final update without endpoint evidence."""
    script = r'''
import contextlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace

root = Path(sys.argv[1])
sys.path[:0] = [str(root / "RL-ViGen-upstream"), str(root / "RL-ViGen-upstream" / "algos")]
# [Codex 2026-09-01 16:21 MSK: isolate the Robosuite train-loop regression from the host-only DMC GLFW import]
sys.modules["wrappers.dmc"] = types.ModuleType("wrappers.dmc")
import train

class TimeStep:
    observation = object()
    reward = 0.0
    def last(self):
        return False

class Environment:
    def reset(self):
        return TimeStep()
    def step(self, action):
        return TimeStep()

class Replay:
    def add(self, time_step):
        pass

class Video:
    def init(self, observation):
        pass
    def record(self, observation):
        pass
    def save(self, name):
        pass

train.utils.Until = lambda limit, repeat=1: lambda step: step * repeat < limit
train.utils.Every = lambda every, repeat=1: lambda step: (step * repeat) % every == 0
train.utils.eval_mode = lambda agent: contextlib.nullcontext()

workspace = train.Workspace.__new__(train.Workspace)
workspace.cfg = SimpleNamespace(num_train_frames=1, num_seed_frames=2,
                                eval_every_frames=1, action_repeat=1,
                                save_snapshot=True, env="robosuite")
workspace._global_step = 0
workspace._global_episode = 0
workspace.train_env = Environment()
workspace.replay_storage = Replay()
workspace.train_video_recorder = Video()
workspace.agent = SimpleNamespace(act=lambda *args, **kwargs: object())
workspace.logger = SimpleNamespace(log=lambda *args, **kwargs: None)
workspace.timer = SimpleNamespace(total_time=lambda: 0.0)
evaluations, snapshots = [], []
workspace.eval = lambda: evaluations.append(workspace.global_frame)
workspace.save_snapshot = lambda: snapshots.append(workspace.global_frame)
workspace.train()
assert evaluations == [0, 1], evaluations
assert snapshots == [1], snapshots
'''
    environment = {
        **__import__("os").environ,
        "PYTHONPATH": ":".join(
            str(path)
            for path in (
                ROOT / "RL-ViGen-upstream",
                ROOT / "RL-ViGen-upstream" / "algos",
                ROOT / "RL-ViGen-upstream" / "envs" / "robosuiteVGB",
                ROOT / "runnable" / "_shim",
            )
        ),
    }
    result = subprocess.run(
        [sys.executable, "-c", script, str(ROOT)],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr


def test_runner_rejects_a_missing_final_evaluation_marker_and_accepts_the_exact_one(tmp_path):
    """A zero trainer status is insufficient unless it emitted the endpoint marker."""
    output = tmp_path / "run"
    output.mkdir()
    training_log = output / "training.log"
    training_log.write_text("trainer exited cleanly\n")
    missing = subprocess.run(
        ["bash", str(RUNNER), "--verify-final-eval", "10000", "--output", str(output)],
        text=True,
        capture_output=True,
    )
    assert missing.returncode != 0
    assert "final evaluation marker missing" in missing.stderr

    training_log.write_text("NATIVE_FINAL_EVALUATION_COMPLETED frame=10000\n")
    accepted = subprocess.run(
        ["bash", str(RUNNER), "--verify-final-eval", "10000", "--output", str(output)],
        text=True,
        capture_output=True,
    )
    assert accepted.returncode == 0, accepted.stderr


def test_run_manifest_records_the_final_evaluation_marker_for_non_preflight_runs():
    """Artifact review must not infer endpoint evidence from a successful shell status."""
    runner = RUNNER.read_text()

    assert '"final_evaluation_marker"' in runner
    assert 'NATIVE_FINAL_EVALUATION_COMPLETED frame=' in runner


def test_run_manifest_reads_the_actual_per_cell_endpoint_marker():
    """IDAAC/PPG may round the requested budget, and one job can contain several cells."""
    runner = RUNNER.read_text()
    assert 're.findall(r"NATIVE_FINAL_EVALUATION_COMPLETED frame=([0-9]+)"' in runner
    assert '"final_evaluation_marker": final_marker(log)' in runner
    assert 'marker if (log.exists()' not in runner


def _run_manifest_builder(tmp_path, *, cells, failed=(), failure_marker=""):
    """Execute the manifest heredoc from the real runner against a synthetic cell tree."""
    source = RUNNER.read_text()
    start = source.index("python3 - <<'PY' > \"$out/run_manifest.json\"")
    body_start = source.index("\n", start) + 1
    body_end = source.index("\nPY", body_start)
    script = source[body_start:body_end]
    out = tmp_path / "native-out"
    for identifier, log_text in cells.items():
        cell = out / "cells" / identifier
        cell.mkdir(parents=True)
        (cell / "training.log").write_text(log_text)
    environment = {
        **os.environ,
        "NATIVE_CELLS": ",".join(cells),
        "FRAMES": "600000",
        "FAILED_CELLS": " ".join(failed),
        "FAILURE_MARKER": failure_marker,
        "PAYLOAD_SHA256": "payload",
        "ASSET_SHA256": "asset",
    }
    script = script.replace('OUT = Path("/tmp/native-out")', f"OUT = Path({str(out)!r})")
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, env=environment,
        text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads((out / "run_manifest.json").read_text())


def _extract_runner_function(name):
    source = RUNNER.read_text()
    start = source.index(f"{name}() {{")
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError(f"{name} not found")


def _run_normalizer_failure_harness(tmp_path, endpoint, *, prior_failure=""):
    out = tmp_path / "out"
    out.mkdir()
    (out / "run_manifest.json").write_text(json.dumps({
        "final_evaluation_marker": "NATIVE_FINAL_EVALUATION_COMPLETED frame=600000",
        "failure_marker": prior_failure or None,
    }))
    archive = tmp_path / "result.tgz"
    script = tmp_path / "normalizer-failure.sh"
    script.write_text(
        "set -euo pipefail\n"
        "cell_status=${PRIOR_STATUS:-0}\n"
        "export FAILURE_MARKER=${PRIOR_FAILURE:-}\n"
        "python3() {\n"
        "  if [[ \"${1:-}\" == datasphere/native/normalize_curves.py ]]; then return 7; fi\n"
        "  command python3 \"$@\"\n"
        "}\n"
        + _extract_runner_function("normalize_records") + "\n"
        + 'normalize_records "$1"\n'
        + 'tar -czf "$2" -C "$1" .\n'
        + 'if [[ "$cell_status" -ne 0 ]]; then exit 1; fi\n'
    )
    environment = {
        **os.environ,
        "ENDPOINT_EVAL": endpoint,
        "PRIOR_STATUS": "1" if prior_failure else "0",
        "PRIOR_FAILURE": prior_failure,
    }
    result = subprocess.run(
        ["bash", str(script), str(out), str(archive)],
        cwd=ROOT, env=environment, text=True, capture_output=True,
    )
    with tarfile.open(archive, "r:gz") as handle:
        manifest = json.loads(handle.extractfile("./run_manifest.json").read())
    return result, archive, manifest


def test_normalizer_failure_is_archived_and_fatal_for_production(tmp_path):
    result, archive, manifest = _run_normalizer_failure_harness(tmp_path, "1")
    assert result.returncode != 0
    assert archive.is_file()
    assert manifest["final_evaluation_marker"] is None
    assert manifest["failure_marker"].startswith("NATIVE_RECORDS_NORMALIZATION_FAILED")


def test_normalizer_failure_is_explicit_but_nonfatal_for_exploration(tmp_path):
    result, archive, manifest = _run_normalizer_failure_harness(tmp_path, "0")
    assert result.returncode == 0
    assert archive.is_file()
    assert "NATIVE_RECORDS_NORMALIZATION_TOLERATED" in result.stderr
    assert manifest["final_evaluation_marker"] == "NATIVE_FINAL_EVALUATION_COMPLETED frame=600000"
    assert manifest["failure_marker"] is None


def test_normalizer_failure_does_not_replace_an_earlier_cell_failure(tmp_path):
    prior = "NATIVE_FINAL_EVALUATION_FAILED cells=idaac-s101"
    result, archive, manifest = _run_normalizer_failure_harness(
        tmp_path, "1", prior_failure=prior,
    )
    assert result.returncode != 0
    assert archive.is_file()
    assert manifest["failure_marker"] == prior


def test_manifest_distinguishes_requested_frames_from_realized_cell_endpoint(tmp_path):
    manifest = _run_manifest_builder(
        tmp_path,
        cells={"ppg-s101": "NATIVE_FINAL_EVALUATION_COMPLETED frame=600064\n"},
    )

    assert manifest["frames_requested"] == 600000
    assert manifest["cells"]["ppg-s101"]["frames_requested"] == 600000
    assert manifest["cells"]["ppg-s101"]["observed_endpoint"] == 600064
    assert manifest["cells"]["ppg-s101"]["final_evaluation_marker"] == \
        "NATIVE_FINAL_EVALUATION_COMPLETED frame=600064"


def test_failed_cell_manifest_has_no_completion_marker_and_keeps_failure_state(tmp_path):
    manifest = _run_manifest_builder(
        tmp_path,
        cells={"idaac-s101": "NATIVE_FINAL_EVALUATION_COMPLETED frame=598016\n"
                       "NATIVE_ENDPOINT_EVAL_FAILED idaac rc=1\n"},
        failed=("idaac-s101",),
        failure_marker="NATIVE_FINAL_EVALUATION_FAILED cells=idaac-s101",
    )
    cell = manifest["cells"]["idaac-s101"]

    assert manifest["final_evaluation_marker"] is None
    assert manifest["failure_marker"] == "NATIVE_FINAL_EVALUATION_FAILED cells=idaac-s101"
    assert manifest["cells_failed"] == ["idaac-s101"]
    assert cell["completed"] is False
    assert cell["final_evaluation_marker"] is None
    assert cell["observed_endpoint"] is None
    assert cell["terminal_status"] == "failed"
    assert "NATIVE_ENDPOINT_EVAL_FAILED" in cell["failure_marker"]


def test_runner_sets_completion_only_on_success_and_records_failure_marker(tmp_path):
    runner = RUNNER.read_text()
    offline = runner.split('elif [[ -n "${OFFLINE_EVAL_SNAPSHOT:-}" ]]', 1)[1].split("\nelse", 1)[0]
    # Located structurally, not by the else-branch's first line: that line stopped being
    # `run_cell_list` when require_accelerator was inserted ahead of it, and this slice then
    # raised IndexError -- a broken test that reads like a broken runner.
    _call = runner.index('run_cell_list "$cells"')
    training = runner[runner.rindex("\nelse\n", 0, _call):runner.index("\nfi\n", _call)]

    assert 'if run_offline_eval "$out"; then' in offline
    assert 'FINAL_EVALUATION_MARKER="NATIVE_OFFLINE_EVAL_COMPLETED"' in offline
    assert 'FINAL_EVALUATION_MARKER=""' in offline
    assert 'FAILURE_MARKER="NATIVE_OFFLINE_EVAL_FAILED' in offline
    assert 'if run_cell_list "$cells"' in training
    assert 'FINAL_EVALUATION_MARKER="NATIVE_FINAL_EVALUATION_COMPLETED"' in training
    assert 'FAILURE_MARKER="NATIVE_FINAL_EVALUATION_FAILED' in training


# [Codex 2026-09-01 21:43 MSK: specify the ALDA endpoint adapter before changing its trainer entry path]
def test_alda_terminal_finalizer_evaluates_all_regimes_then_retains_checkpoint_and_emits_exact_marker(tmp_path):
    """ALDA's finite run needs a post-train endpoint, independent of episode boundaries."""
    script = ROOT / "runnable" / "alda" / "scripts" / "train.py"
    harness = r'''
import importlib.util
import sys
import types

wandb = types.ModuleType("wandb")
wandb.init = lambda **kwargs: None
sys.modules["wandb"] = wandb
sys.modules["yaml"] = types.ModuleType("yaml")
torch = types.ModuleType("torch")
torch.cuda = types.SimpleNamespace(is_available=lambda: True)
sys.modules["torch"] = torch
common = types.ModuleType("common")
utils = types.ModuleType("common.utils")
utils.setup_logging = lambda **kwargs: None
utils.create_instance_from_spec = lambda *args, **kwargs: None
utils.print_spec = lambda *args, **kwargs: None
utils.parse_spec_overrides = lambda spec, overrides: spec
common.utils = utils
sys.modules["common"] = common
sys.modules["common.utils"] = utils

spec = importlib.util.spec_from_file_location("alda_train", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Trainer:
    env_steps = 10000
    def __init__(self):
        self.calls = []
    def evaluate(self, step, distracting_env=False, color_env=False):
        self.calls.append(("evaluate", step, distracting_env, color_env))
    def save_checkpoint(self):
        self.calls.append(("save_checkpoint",))

trainer = Trainer()
module.finalize_trainer(trainer)
assert trainer.calls == [
    ("evaluate", 10000, False, False),
    ("evaluate", 10000, True, False),
    ("evaluate", 10000, False, True),
    ("save_checkpoint",),
], trainer.calls
'''
    result = subprocess.run(
        [sys.executable, "-c", harness, str(script)],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "NATIVE_FINAL_EVALUATION_COMPLETED frame=10000" in result.stdout


def test_resource_sampler_normalizes_a_macos_locale_decimal(monkeypatch):
    """A local telemetry parser must not fail merely because `ps` follows a comma locale."""
    from datasphere.native import measure_resources

    monkeypatch.setattr(measure_resources.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(measure_resources, "command", lambda *args: "42 1024 12,5")

    assert measure_resources.portable_process(42) == {
        "pid": 42,
        "rss_kib": 1024,
        "cpu_percent": 12.5,
        "threads": None,
    }


# [Claude 2026-09-02 02:00 MSK: one job now carries several (baseline, seed) cells, optionally at
# the same time. Specify the three properties that decide whether that is safe: every cell is
# attempted, any failure fails the job, and NATIVE_CONCURRENT really does overlap them.]
FAKE_LAUNCHER = """#!/usr/bin/env bash
set -euo pipefail
baseline="$1"
shift
run_dir=""
seed=""
for argument in "$@"; do
  case "$argument" in
    hydra.run.dir=*) run_dir="${argument#hydra.run.dir=}" ;;
    seed=*) seed="${argument#seed=}" ;;
  esac
done
if [[ "$baseline" == "bad" ]]; then
  echo "deliberate trainer failure" >&2
  exit 1
fi
if [[ -n "${CELL_BARRIER:-}" ]]; then
  echo "$baseline-$seed" >> "$CELL_BARRIER"
  waited=0
  while [[ "$(wc -l < "$CELL_BARRIER")" -lt "${CELL_BARRIER_SIZE:?}" ]]; do
    sleep 0.2
    waited=$((waited + 1))
    if [[ "$waited" -gt 50 ]]; then
      echo "cell never met the others at the barrier" >&2
      exit 1
    fi
  done
fi
mkdir -p "$run_dir/tb"
# a real torch checkpoint, because the cell path now gates on its floating-point values
"$CELL_PYTHON" -c "import sys, torch; torch.save({'identity': sys.argv[1], 'agent': {'w': torch.zeros(4)}}, sys.argv[2])" \
  "$baseline-$seed" "$run_dir/snapshot.pt"
printf 'frame,episode_reward\n500,1.5\n' > "$run_dir/train.csv"
printf 'frame,episode_reward\n0,0.2\n' > "$run_dir/eval.csv"
printf 'tb-events' > "$run_dir/tb/events.out.tfevents"
echo "NATIVE_FINAL_EVALUATION_COMPLETED frame=10000"
"""


def _run_cells(tmp_path, cells, extra_env=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    launcher = tmp_path / "fake_launcher.sh"
    launcher.write_text(FAKE_LAUNCHER)
    launcher.chmod(0o755)
    work = tmp_path / "work"
    output = tmp_path / "out"
    return subprocess.run(
        [
            "bash", str(RUNNER), "--run-cells",
            "--cells", cells,
            "--work", str(work),
            "--output", str(output),
        ],
        cwd=str(ROOT),
        env={
            **__import__("os").environ,
            "NATIVE_LAUNCHER": str(launcher),
            "NATIVE_NO_TIME_WRAPPER": "1",
            "NATIVE_FAMILY": "rlvigen",
            "CELL_PYTHON": sys.executable,
            "FRAMES": "10000",
            **(extra_env or {}),
        },
        text=True,
        capture_output=True,
    ), output


def test_each_cell_keeps_its_own_snapshot_and_curve(tmp_path):
    """Several runs in one job must not overwrite or borrow each other's artifacts."""
    result, output = _run_cells(tmp_path, "alpha,beta")

    assert result.returncode == 0, result.stderr
    for name in ("alpha", "beta"):
        cell = output / "cells" / f"{name}-s1"
        import torch

        assert torch.load(cell / "snapshot.pt", weights_only=False)["identity"] == f"{name}-1"
        assert cell.joinpath("train.csv").exists()
        assert cell.joinpath("eval.csv").exists()
        assert cell.joinpath("tb", "events.out.tfevents").exists()
        assert cell.joinpath("training.log").exists()


def test_a_cell_spec_carries_its_own_seed(tmp_path):
    """The packing experiment is the same baseline at several seeds; the seed must reach the trainer."""
    result, output = _run_cells(tmp_path, "alpha:7,alpha:8")

    assert result.returncode == 0, result.stderr
    import torch

    for seed in (7, 8):
        loaded = torch.load(output / "cells" / f"alpha-s{seed}" / "snapshot.pt", weights_only=False)
        assert loaded["identity"] == f"alpha-{seed}"


def test_job_continues_past_a_failed_cell_and_then_fails(tmp_path):
    """Aborting would discard the later cells' evidence; hiding it would make the job falsely green."""
    result, output = _run_cells(tmp_path, "bad,good")

    assert result.returncode != 0
    assert "NATIVE_CELL_FAILED bad-s1" in result.stdout + result.stderr
    import torch

    assert torch.load(output / "cells" / "good-s1" / "snapshot.pt", weights_only=False)["identity"] == "good-1"
    assert not (output / "cells" / "bad-s1" / "snapshot.pt").exists()


def test_concurrent_mode_really_overlaps_the_cells(tmp_path):
    """Packing is the whole production cost argument; a loop that only looked parallel would sink it."""
    barrier = tmp_path / "barrier.txt"
    barrier.write_text("")
    environment = {"CELL_BARRIER": str(barrier), "CELL_BARRIER_SIZE": "3"}

    serial, _ = _run_cells(tmp_path / "serial", "a:1,b:1,c:1", environment)
    assert serial.returncode != 0
    assert "never met the others at the barrier" in serial.stdout + serial.stderr

    barrier.write_text("")
    concurrent, output = _run_cells(
        tmp_path / "concurrent", "a:1,b:1,c:1", {**environment, "NATIVE_CONCURRENT": "1"}
    )
    assert concurrent.returncode == 0, concurrent.stderr
    for name in ("a", "b", "c"):
        assert (output / "cells" / f"{name}-s1" / "snapshot.pt").exists()


def test_a_slow_cell_is_cut_off_without_destroying_the_finished_cells_evidence(tmp_path):
    """One job carries several cells and writes the archive last; a hung cell must not take the rest."""
    launcher = tmp_path / "slow_launcher.sh"
    launcher.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\nif [[ \"$1\" == \"slow\" ]]; then sleep 30; fi\n"
        "run_dir=\"\"\nfor argument in \"$@\"; do case \"$argument\" in hydra.run.dir=*) "
        "run_dir=\"${argument#hydra.run.dir=}\" ;; esac; done\n"
        "mkdir -p \"$run_dir\"\nprintf 'state' > \"$run_dir/snapshot.pt\"\n"
        "printf 'frame\\n1\\n' > \"$run_dir/train.csv\"\n"
        "echo \"NATIVE_FINAL_EVALUATION_COMPLETED frame=10000\"\n"
    )
    launcher.chmod(0o755)
    work = tmp_path / "work"
    output = tmp_path / "out"

    result = subprocess.run(
        ["bash", str(RUNNER), "--run-cells", "--cells", "slow,quick",
         "--work", str(work), "--output", str(output)],
        cwd=str(ROOT),
        env={
            **__import__("os").environ,
            "NATIVE_LAUNCHER": str(launcher),
            "NATIVE_NO_TIME_WRAPPER": "1",
            "NATIVE_FAMILY": "rlvigen",
            "CELL_PYTHON": sys.executable,
            "FRAMES": "10000",
            "CELL_TIMEOUT_SECONDS": "2",
        },
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "NATIVE_CELL_FAILED slow-s1" in result.stdout + result.stderr
    assert (output / "cells" / "quick-s1" / "snapshot.pt").exists()


# [Claude 2026-09-02 01:35 MSK: P17's premise, as an executable fact rather than a claim in a
# comment. If a future torch gives TransformedDistribution an entropy(), this goes red and P17
# has to be re-decided rather than silently kept.]
def test_drq_actor_distribution_has_no_analytic_entropy_unlike_drqv2s():
    """Why drq and drqv2 report different entropy columns, and why P17 deletes rather than renames."""
    environment = {
        **__import__("os").environ,
        "MUJOCO_GL": "egl",
        "PYOPENGL_PLATFORM": "egl",
        "WANDB_MODE": "offline",
        "WANDB_DISABLED": "true",
        "PYTHONPATH": ":".join(
            str(path)
            for path in (
                ROOT / "RL-ViGen-upstream",
                ROOT / "RL-ViGen-upstream" / "algos",
                ROOT / "RL-ViGen-upstream" / "envs" / "robosuiteVGB",
                ROOT / "runnable" / "_shim",
            )
        ),
    }
    program = "\n".join(
        [
            "import torch",
            "from drq import SquashedNormal",
            "from utils import TruncatedNormal",
            "mu, std = torch.zeros(2, 3), torch.ones(2, 3)",
            "analytic = TruncatedNormal(mu, std).entropy()",
            "assert analytic.shape == (2, 3)",
            "try:",
            "    SquashedNormal(mu, std).entropy()",
            "except NotImplementedError:",
            "    print('SQUASHED_NORMAL_HAS_NO_ANALYTIC_ENTROPY')",
            "else:",
            "    raise SystemExit('SquashedNormal now has entropy(); re-decide P17')",
        ]
    )

    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "SQUASHED_NORMAL_HAS_NO_ANALYTIC_ENTROPY" in result.stdout
    # and the vendored agent that runs remotely no longer makes that call. Parsed, not grepped:
    # P17's own comment quotes the deleted line, so a text search would find it forever.
    import ast

    def calls_entropy(relative):
        tree = ast.parse((ROOT / "RL-ViGen-upstream" / "algos" / relative).read_text())
        return any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "entropy"
            for node in ast.walk(tree)
        )

    assert not calls_entropy("drq.py")
    assert calls_entropy("drqv2.py")


# [Claude 2026-09-02 02:35 MSK: the overlay asset was gated on BASELINE == svea. sgqn calls the
# same utils.random_overlay on every update, so that gate was wrong the moment a second agent
# joined a job.]
def test_places365_is_required_by_sgqn_as_well_as_svea():
    """A job whose cells include sgqn must carry the declared private overlay asset."""
    def needs(cells):
        return subprocess.run(
            ["bash", str(RUNNER), "--cells-need-places365", cells],
            cwd=str(ROOT), text=True, capture_output=True,
        ).returncode == 0

    assert needs("svea")
    assert needs("sgqn")
    assert needs("drq,sgqn,curl")
    assert needs("drqv2:1,sgqn:2")
    assert not needs("drqv2")
    assert not needs("drq,curl")
    assert not needs("drqv2:1,drqv2:2,drqv2:3,drqv2:4")


def test_trio_calibration_binds_the_v21_payload_the_asset_and_a_per_cell_cap():
    """The three unrun RL-ViGen agents in one job: sgqn needs the asset, and no cell may hang the job."""
    config = TRIO_CALIBRATION_CONFIG.read_text()

    assert "native-payload-v21.tgz" in config
    assert "CELLS=drq,sgqn,curl" in config
    assert "places365-val.tgz" in config
    assert "PLACES365_EXPECTED_COUNT=36500" in config
    assert "CELL_TIMEOUT_SECONDS=" in config
    assert "cloud-instance-type: gt4.1" in config
    # the job-level cap must exceed the sum of the per-cell caps plus a bootstrap, or a slow cell
    # would be cut off by the outer timeout before the archive is written
    import re
    job_cap = int(re.search(r"timeout --foreground (\d+)s", config).group(1))
    cell_cap = int(re.search(r"CELL_TIMEOUT_SECONDS=(\d+)", config).group(1))
    assert job_cap > 3 * cell_cap + 900, (job_cap, cell_cap)


# [Claude 2026-09-02 03:30 MSK: retention moved out of the runner and into family.py when a second
# source family appeared. These are the same two fail-closed gates P16 established, now stated
# against the module that owns them, plus the per-family shapes they have to get right.]
FAMILY_TOOL = ROOT / "datasphere" / "native" / "family.py"


def _family(*arguments):
    return subprocess.run([sys.executable, str(FAMILY_TOOL), *arguments], cwd=str(ROOT), text=True, capture_output=True)


def test_family_resolves_each_baseline_to_the_repository_that_owns_its_train_loop():
    for baseline, expected in (("drqv2", "rlvigen"), ("sgqn", "rlvigen"), ("rad", "dmc_gb"), ("soda", "dmc_gb")):
        result = _family("family-of", "--baseline", baseline)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == expected

    unknown = _family("family-of", "--baseline", "not-a-baseline")
    assert unknown.returncode != 0
    assert "no family declares baseline" in unknown.stderr


def test_family_builds_each_familys_own_argv_rather_than_one_shared_flag_set():
    """RL-ViGen takes hydra key=value; dmcontrol-generalization-benchmark takes argparse flags."""
    rlvigen = _family(
        "command", "--baseline", "drqv2", "--task", "Door", "--frames", "10000",
        "--eval-every", "10000", "--eval-episodes", "2", "--seed", "5", "--run-dir", "/w/run",
    )
    assert rlvigen.returncode == 0, rlvigen.stderr
    argv = rlvigen.stdout.split("\n")[:-1]
    assert argv[0] == "runnable/_launch/rlvigen.sh"
    assert argv[1:3] == ["drqv2", "Door"]
    assert "num_train_frames=10000" in argv
    assert "seed=5" in argv
    assert "hydra.run.dir=/w/run" in argv

    dmc = _family(
        "command", "--baseline", "soda", "--task", "Door", "--frames", "10000",
        "--eval-every", "5000", "--eval-episodes", "2", "--seed", "5", "--run-dir", "/w/run",
    )
    assert dmc.returncode == 0, dmc.stderr
    argv = dmc.stdout.split("\n")[:-1]
    assert argv[0] == "runnable/_launch/dmc_gb.sh"
    assert argv[1:4] == ["soda", "Door", "5"]
    assert argv[argv.index("--train_steps") + 1] == "10000"
    assert argv[argv.index("--eval_freq") + 1] == "5000"
    # save_freq must equal the budget or dmc_gb's default 100k never fires on a 10k calibration
    assert argv[argv.index("--save_freq") + 1] == "10000"
    assert argv[argv.index("--log_dir") + 1] == "/w/run"


def test_family_retention_fails_closed_on_a_missing_curve_or_checkpoint(tmp_path):
    run_dir = tmp_path / "run"
    output = tmp_path / "out"
    run_dir.mkdir()
    arguments = ["retain", "--baseline", "drqv2", "--frames", "10000", "--seed", "1",
                 "--run-dir", str(run_dir), "--output", str(output)]

    no_curve = _family(*arguments)
    assert no_curve.returncode != 0
    assert "required curve is absent" in no_curve.stderr

    (run_dir / "train.csv").write_text("frame,episode_reward\n500,1.0\n")
    no_checkpoint = _family(*arguments)
    assert no_checkpoint.returncode != 0
    assert "terminal checkpoint is absent" in no_checkpoint.stderr

    (run_dir / "snapshot.pt").write_bytes(b"")
    empty_checkpoint = _family(*arguments)
    assert empty_checkpoint.returncode != 0
    assert "terminal checkpoint is absent or empty" in empty_checkpoint.stderr

    (run_dir / "snapshot.pt").write_bytes(b"weights")
    (run_dir / "eval.csv").write_text("frame,episode_reward\n0,0.1\n")
    (run_dir / "tb").mkdir()
    (run_dir / "tb" / "events").write_text("e")
    kept = _family(*arguments)
    assert kept.returncode == 0, kept.stderr
    assert (output / "train.csv").exists()
    assert (output / "eval.csv").exists()
    assert (output / "tb" / "events").exists()
    assert (output / "snapshot.pt").read_bytes() == b"weights"


def test_family_retention_finds_dmc_gbs_nested_working_directory_and_normalises_the_checkpoint(tmp_path):
    """dmc_gb writes to log_dir/<domain>_<task>/<algorithm>/<seed>, and names the checkpoint by step."""
    run_dir = tmp_path / "run"
    work = run_dir / "robosuite_Door" / "soda" / "3"
    (work / "model").mkdir(parents=True)
    (work / "train.log").write_text('{"step": 500}\n')
    (work / "eval.log").write_text('{"step": 0}\n')
    (work / "model" / "10000.pt").write_bytes(b"agent-object")
    output = tmp_path / "out"

    kept = _family("retain", "--baseline", "soda", "--frames", "10000", "--seed", "3",
                   "--run-dir", str(run_dir), "--output", str(output))

    assert kept.returncode == 0, kept.stderr
    assert (output / "train.log").exists()
    assert (output / "eval.log").exists()
    # normalised name, with the real source recorded rather than lost
    assert (output / "snapshot.pt").read_bytes() == b"agent-object"
    retained = json.loads((output / "retained.json").read_text())
    assert retained["family"] == "dmc_gb"
    assert retained["checkpoint_source"].endswith("model/10000.pt")


def test_soda_needs_the_overlay_asset_and_rad_does_not():
    assert _family("needs-places365", "--cells", "soda").returncode == 0
    assert _family("needs-places365", "--cells", "rad").returncode != 0
    assert _family("needs-places365", "--cells", "rad,soda").returncode == 0


# [Claude 2026-09-02 03:50 MSK: dmcontrol-generalization-benchmark's loop evaluates and checkpoints
# only on an episode boundary that divides eval_freq/save_freq, and its save_freq default is 100k,
# so a 10k calibration would have finished with no checkpoint at all and no exact endpoint. Same
# shape of gap P15 closed for RL-ViGen and finalize_trainer closed for ALDA, and the same answer:
# an endpoint hook AFTER the unchanged loop, adding no environment step and no update.]
def test_dmc_gb_finalizer_evaluates_both_regimes_then_checkpoints_and_emits_the_exact_marker(tmp_path):
    script = ROOT / "runnable" / "dmc_gb" / "src" / "train.py"
    harness = r'''
import importlib.util
import sys
import types

for name in ("torch", "gym", "numpy", "utils", "arguments", "logger", "video"):
    module = types.ModuleType(name)
    sys.modules.setdefault(name, module)
saved = []
sys.modules["torch"].save = lambda obj, path: saved.append((obj, path))
# train.py now writes through runnable/_shim/safe_checkpoint.safe_torch_save rather than calling
# torch.save directly (disk-safety, added 2026-09-05). Stubbed here rather than put on sys.path,
# so this harness keeps testing finalize_run's OWN logic -- what gets saved and when -- without
# also depending on the real atomic-write mechanism, which tests/test_safe_checkpoint.py covers.
safe_checkpoint_module = types.ModuleType("safe_checkpoint")
safe_checkpoint_module.safe_torch_save = lambda obj, path, **kw: saved.append((obj, path)) or True
sys.modules["safe_checkpoint"] = safe_checkpoint_module
sys.modules["numpy"].mean = lambda values: sum(values) / max(1, len(values))
env_module = types.ModuleType("env")
wrappers = types.ModuleType("env.wrappers")
wrappers.make_env = lambda **kwargs: None
env_module.wrappers = wrappers
sys.modules["env"] = env_module
sys.modules["env.wrappers"] = wrappers
algorithms = types.ModuleType("algorithms")
factory = types.ModuleType("algorithms.factory")
factory.make_agent = lambda **kwargs: None
algorithms.factory = factory
sys.modules["algorithms"] = algorithms
sys.modules["algorithms.factory"] = factory
sys.modules["arguments"].parse_args = lambda: None
sys.modules["logger"].Logger = object
sys.modules["video"].VideoRecorder = object

spec = importlib.util.spec_from_file_location("dmc_gb_train", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

calls = []
module.evaluate = lambda env, agent, video, episodes, L, step, test_env=False: calls.append(("evaluate", env, step, test_env))

class Logger:
    def dump(self, step):
        calls.append(("dump", step))

class Args:
    train_steps = 10000
    eval_episodes = 2

module.finalize_run(
    env="train-env", test_env="eval-env", agent="agent", video=None,
    L=Logger(), args=Args(), model_dir=sys.argv[2], last_eval_step=5000,
)
assert calls == [
    ("evaluate", "train-env", 10000, False),
    ("evaluate", "eval-env", 10000, True),
    ("dump", 10000),
], calls
assert saved and saved[0][1].endswith("10000.pt"), saved

calls.clear()
saved.clear()
module.finalize_run(
    env="train-env", test_env="eval-env", agent="agent", video=None,
    L=Logger(), args=Args(), model_dir=sys.argv[2], last_eval_step=10000,
)
assert calls == [], calls
'''
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    result = subprocess.run(
        [sys.executable, "-c", harness, str(script), str(model_dir)],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("NATIVE_FINAL_EVALUATION_COMPLETED frame=10000") == 2


def test_dmc_gb_loop_records_the_step_it_last_evaluated_at():
    """The finalizer must not re-run an evaluation the loop already did at exactly the endpoint."""
    source = (ROOT / "runnable" / "dmc_gb" / "src" / "train.py").read_text()

    assert "last_eval_step" in source
    # the loop records it before the call site, and the call passes it through
    assert source.index("last_eval_step = step") < source.rindex("finalize_run(")
    assert "finalize_run(env, test_env, agent, video, L, args, model_dir, last_eval_step)" in source


# [Claude 2026-09-02 04:40 MSK: one job must not be able to contain a clone it does not run. The
# allowlist is base + declared families, and the declaration travels inside the archive so the
# remote verifier applies the same rule without being told.]
def test_a_family_payload_contains_that_familys_source_and_no_other_clone(tmp_path):
    dmc_archive = tmp_path / "dmc.tgz"
    build = subprocess.run(
        [sys.executable, str(TOOL), "build-payload", "--source", str(ROOT),
         "--output", str(dmc_archive), "--families", "dmc_gb"],
        text=True, capture_output=True,
    )
    assert build.returncode == 0, build.stderr

    with tarfile.open(dmc_archive) as archive:
        names = [member.name for member in archive.getmembers() if member.isfile()]
        manifest = json.loads(archive.extractfile("payload_manifest.json").read())

    assert manifest["families"] == ["dmc_gb"]
    assert any(name.startswith("runnable/dmc_gb/src/") for name in names)
    assert "runnable/_launch/dmc_gb.sh" in names
    assert not any(name.startswith("runnable/alda/") for name in names)
    assert not any(name.startswith("runnable/idaac/") for name in names)
    assert "runnable/_launch/rlvigen.sh" not in names
    # the payload the remote verifier sees must satisfy its own declaration
    verify = subprocess.run(
        [sys.executable, str(TOOL), "verify-payload", "--archive", str(dmc_archive)],
        text=True, capture_output=True,
    )
    assert verify.returncode == 0, verify.stderr


def test_native_payload_carries_eval_grids_transitive_provenance_helper(tmp_path):
    """Both evaluator entry points import this helper after the archive is extracted."""
    archive_path = tmp_path / "idaac.tgz"
    build = subprocess.run(
        [sys.executable, str(TOOL), "build-payload", "--source", str(ROOT),
         "--output", str(archive_path), "--families", "idaac"],
        text=True, capture_output=True,
    )
    assert build.returncode == 0, build.stderr
    with tarfile.open(archive_path) as archive:
        assert "scripts/eval_provenance.py" in archive.getnames()


def test_an_rlvigen_payload_cannot_smuggle_another_familys_source(tmp_path):
    archive_path = tmp_path / "rlvigen.tgz"
    build = subprocess.run(
        [sys.executable, str(TOOL), "build-payload", "--source", str(ROOT),
         "--output", str(archive_path), "--families", "rlvigen"],
        text=True, capture_output=True,
    )
    assert build.returncode == 0, build.stderr
    with tarfile.open(archive_path) as archive:
        names = [member.name for member in archive.getmembers() if member.isfile()]
    assert "runnable/_launch/rlvigen.sh" in names
    assert not any(name.startswith("runnable/dmc_gb/") for name in names)

    smuggled = tmp_path / "smuggled.tgz"
    with tarfile.open(archive_path) as source, tarfile.open(smuggled, "w:gz") as target:
        for member in source.getmembers():
            extracted = source.extractfile(member)
            target.addfile(member, extracted)
        payload = b"print('not declared')\n"
        info = tarfile.TarInfo("runnable/dmc_gb/src/train.py")
        info.size = len(payload)
        target.addfile(info, __import__("io").BytesIO(payload))

    verify = subprocess.run(
        [sys.executable, str(TOOL), "verify-payload", "--archive", str(smuggled)],
        text=True, capture_output=True,
    )
    assert verify.returncode != 0
    assert "payload member manifest differs from archive" in verify.stderr


def test_payload_verifier_rejects_an_offline_family_it_does_not_carry(tmp_path):
    """Offline-only jobs select their family from OFFLINE_EVAL_FAMILY, not CELLS.

    A valid rlvigen-only payload previously passed integrity checking, then spent a full remote
    bootstrap before IDAAC checkpoint unpickling failed because its clone was absent.
    """
    archive = tmp_path / "rlvigen.tgz"
    build = subprocess.run(
        [sys.executable, str(TOOL), "build-payload", "--source", str(ROOT),
         "--output", str(archive), "--families", "rlvigen"],
        text=True, capture_output=True,
    )
    assert build.returncode == 0, build.stderr

    verify = subprocess.run(
        [sys.executable, str(TOOL), "verify-payload", "--archive", str(archive),
         "--require-families", "idaac"],
        text=True, capture_output=True,
    )
    assert verify.returncode != 0
    assert "does not carry required family" in verify.stderr


# [Claude 2026-09-02 04:55 MSK: found by a local rehearsal, not by reading. dmc_gb's very first
# action after building both environments is utils.write_info, which shells out to
# `git describe --always` and lets a CalledProcessError propagate. The remote payload is a
# tarball, so /tmp/native-work/runnable/dmc_gb is not a git repository and EVERY rad or soda job
# would have died there -- after paying the full bootstrap, before one environment step. It works
# in the original tree only because that tree's clone still has its .git.]
def test_dmc_gb_records_provenance_without_requiring_a_git_checkout(tmp_path):
    harness = (
        "import json, sys, types\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import utils\n"
        "class Args:\n"
        "    seed = 1\n"
        "utils.write_info(Args(), sys.argv[2])\n"
        "data = json.load(open(sys.argv[2]))\n"
        "assert 'git' in data, data\n"
        "print('PROVENANCE_WRITTEN', data['git'])\n"
    )
    target = tmp_path / "info.log"
    outside_a_repository = tmp_path / "elsewhere"
    outside_a_repository.mkdir()

    result = subprocess.run(
        [sys.executable, "-c", harness, str(ROOT / "runnable" / "dmc_gb" / "src"), str(target)],
        cwd=str(outside_a_repository),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "PROVENANCE_WRITTEN" in result.stdout


# [Claude 2026-09-02 06:10 MSK: the endpoint a family reaches is not always the endpoint asked for,
# and the difference is arithmetic rather than tolerance. Stated here so that adding idaac or ppg
# is a descriptor entry whose rule is checked, not a percentage someone picked.]
def test_expected_endpoint_is_exact_for_the_families_whose_loops_stop_where_asked():
    for baseline in ("drqv2", "svea", "rad", "soda"):
        result = _family("expected-endpoint", "--baseline", baseline, "--frames", "500000")
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "500000"


def test_expected_endpoint_rounds_by_a_familys_own_rollout_quantum(tmp_path):
    """A synthetic descriptor, so the rule is tested rather than only the two families that use it."""
    descriptors = json.loads((ROOT / "datasphere" / "native" / "families.json").read_text())
    descriptors["floored"] = {
        **descriptors["rlvigen"],
        "baselines": ["floored"],
        "options": ["--num_steps", "256", "--num_processes", "4"],
        "endpoint": {"rule": "floor_to_quantum", "quantum_flags": ["--num_steps", "--num_processes"]},
    }
    descriptors["overshooting"] = {
        **descriptors["rlvigen"],
        "baselines": ["overshooting"],
        "options": ["--num_envs", "8", "--nstep", "256"],
        "endpoint": {"rule": "ceil_to_quantum", "quantum_flags": ["--num_envs", "--nstep"]},
    }
    path = tmp_path / "families.json"
    path.write_text(json.dumps(descriptors))

    harness = (
        "import sys, json\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from pathlib import Path\n"
        "import family\n"
        "path = Path(sys.argv[2])\n"
        "assert family.expected_endpoint('floored', 10000, path) == 9216, family.expected_endpoint('floored', 10000, path)\n"
        "assert family.expected_endpoint('overshooting', 10000, path) == 10240\n"
        "assert family.expected_endpoint('floored', 10240, path) == 10240\n"
        "print('ENDPOINT_RULES_OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", harness, str(ROOT / "datasphere" / "native"), str(path)],
        text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "ENDPOINT_RULES_OK" in result.stdout


def test_dmcgb_calibration_binds_its_own_payload_and_the_overlay_asset():
    config = (ROOT / "datasphere" / "native" / "cfg-dmcgb-calibration-v22.yaml").read_text()

    assert "dmcgb-payload-v22.tgz" in config
    assert "CELLS=rad,soda" in config
    assert "places365-val.tgz" in config
    assert "PLACES365_EXPECTED_SHA256=" in config
    assert "CELL_TIMEOUT_SECONDS=" in config


# [Claude 2026-09-02 06:50 MSK: run_probe.sh is a separate job input from the payload, so the two
# can drift. Job bt1p2nhbap9p3ih73vvg paid a full bootstrap to discover that the runner had begun
# calling family.py and the payload predated it. The check now happens right after extraction.]
def test_a_payload_built_for_an_older_runner_is_refused_before_the_bootstrap(tmp_path):
    archive = tmp_path / "payload.tgz"
    build = subprocess.run(
        [sys.executable, str(TOOL), "build-payload", "--source", str(ROOT), "--output", str(archive)],
        text=True, capture_output=True,
    )
    assert build.returncode == 0, build.stderr

    import re

    stamped = int(re.search(r"RUNNER_CONTRACT = (\d+)", TOOL.read_text()).group(1))
    current = subprocess.run(
        [sys.executable, str(TOOL), "verify-payload", "--archive", str(archive),
         "--require-runner-contract", str(stamped)],
        text=True, capture_output=True,
    )
    assert current.returncode == 0, current.stderr

    future = subprocess.run(
        [sys.executable, str(TOOL), "verify-payload", "--archive", str(archive),
         "--require-runner-contract", str(stamped + 1)],
        text=True, capture_output=True,
    )
    assert future.returncode != 0
    assert "rebuild the payload before submitting" in future.stderr


def test_the_runner_demands_the_contract_the_builder_stamps():
    """The two numbers must move together, or the check would be decorative."""
    runner = RUNNER.read_text()
    builder = (ROOT / "datasphere" / "native" / "contract.py").read_text()

    import re

    demanded = int(re.search(r"--require-runner-contract (\d+)", runner).group(1))
    stamped = int(re.search(r"RUNNER_CONTRACT = (\d+)", builder).group(1))
    assert demanded == stamped, (demanded, stamped)
    assert "scripts/eval_grid.py:evaluator_revision=EVALUATOR_REVISION" in runner


# [Claude 2026-09-02 07:25 MSK: found by a local idaac rehearsal that reached its endpoint and then
# failed to keep the curve: only the checkpoint path was being rendered, and IDAAC's logger puts
# the environment, the algorithm and the seed inside the curve's filename.]
def test_every_declared_artifact_name_is_rendered_not_taken_literally(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "models").mkdir(parents=True)
    (run_dir / "progress-robosuite:Door-idaac-s7.csv").write_text("total_num_steps\n9216\n")
    (run_dir / "models" / "agent-robosuite:Door-idaac-s7.pt").write_bytes(b"actor-critic")
    output = tmp_path / "out"

    kept = _family("retain", "--baseline", "idaac", "--task", "Door", "--frames", "10000",
                   "--seed", "7", "--run-dir", str(run_dir), "--output", str(output))

    assert kept.returncode == 0, kept.stderr
    assert (output / "progress-robosuite:Door-idaac-s7.csv").exists()
    assert (output / "snapshot.pt").read_bytes() == b"actor-critic"
    retained = json.loads((output / "retained.json").read_text())
    assert all("{" not in name for name in retained["curves"]), retained["curves"]
    assert "{" not in retained["checkpoint_source"], retained["checkpoint_source"]


def test_idaac_floors_its_budget_to_a_whole_rollout():
    """IDAAC computes num_env_steps // num_steps // num_processes updates; the marker says so.

    [Claude 2026-09-06] Values recomputed for DECISION-SHEET A35's IDAAC-C2 rollout (num_processes
    1 x num_steps 2048 = 2048 quantum, was 4x256=1024): 10000//2048*2048=8192; 500000 stays
    499712 (488*1024 == 244*2048, coincidence); 1024 is now BELOW one rollout, floors to 0.
    """
    for requested, executed in ((10000, 8192), (500000, 499712), (1024, 0)):
        result = _family("expected-endpoint", "--baseline", "idaac", "--frames", str(requested))
        assert result.returncode == 0, result.stderr
        assert int(result.stdout.strip()) == executed, (requested, result.stdout)


# [Claude 2026-09-02 08:10 MSK: the fifth undeclared import, and the first one the gate could not
# have caught: hydra selects the agent at run time, so importing the entry point never touched
# algos/sgqn.py -> rl_utils.py -> captum. Both halves are pinned here.]
def test_sgqns_attribution_dependency_is_declared():
    requirements = (ROOT / "requirements-native.txt").read_text()
    assert "captum==" in requirements

    source = (ROOT / "RL-ViGen-upstream" / "rl_utils.py").read_text()
    assert "from captum.attr import" in source, "upstream changed; re-derive the closure"


def test_the_import_gate_covers_the_agent_each_cell_will_actually_select(tmp_path):
    """Reading the entry point is not reading the agent; hydra picks that at run time."""
    harness = (
        "import sys, json\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import family\n"
        "entry = family.descriptor('rlvigen')\n"
        "gate = entry['import_gate']\n"
        "modules = list(gate['modules'])\n"
        "for spec in 'drq,sgqn,curl'.split(','):\n"
        "    modules.append(family.render(entry['baseline_module'], {'baseline': spec}))\n"
        "assert 'sgqn' in modules and 'drq' in modules and 'curl' in modules, modules\n"
        "assert 'train' in modules and 'wrappers.robo_wrapper' in modules, modules\n"
        "print('GATE_COVERS_AGENTS')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", harness, str(ROOT / "datasphere" / "native")],
        text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "GATE_COVERS_AGENTS" in result.stdout


# [Claude 2026-09-02 08:15 MSK: one family's undeclared import must not destroy another family's
# calibration in the same job. Job bt1psnr0q4ss6h6fs8il carried three cells across two families;
# had the dmc_gb gate failed, aborting would have taken sgqn's result with it.]
def test_a_family_that_fails_its_import_gate_blocks_only_its_own_cells(tmp_path):
    result, output = _run_cells(tmp_path, "alpha,beta", {"BLOCKED_FAMILIES": "rlvigen"})

    assert result.returncode != 0
    assert "failed its import gate" in result.stdout + result.stderr
    for name in ("alpha", "beta"):
        assert not (output / "cells" / f"{name}-s1" / "snapshot.pt").exists()

    unblocked, output = _run_cells(tmp_path / "clear", "alpha,beta", {"BLOCKED_FAMILIES": "dmc_gb"})
    assert unblocked.returncode == 0, unblocked.stderr
    assert (output / "cells" / "alpha-s1" / "snapshot.pt").exists()


# [Claude 2026-09-02 10:25 MSK: ALDA and CTRL have no structured sink -- ALDA creates its log file
# and leaves it empty because its metrics go to the stream handler and to W&B, and CTRL logs only
# through W&B plus one printed line per log step. W&B does not run on DataSphere and is not worked
# around there, so for those two the console log IS the curve. The fail-closed property is kept by
# requiring THAT to be non-empty, not by dropping the requirement.]
def test_a_family_whose_curve_is_its_console_log_still_fails_closed_without_one(tmp_path):
    run_dir = tmp_path / "run"
    work = run_dir / "alda_robosuite_door" / "seed_1" / "checkpoints"
    work.mkdir(parents=True)
    (work / "sac_None_step_2000.pt").write_bytes(b"state")
    # ALDA really does create this file and leave it empty; that is what made it a bad requirement
    (run_dir / "alda_robosuite_door" / "seed_1" / "output_log_0.txt").write_text("")
    output = tmp_path / "out"
    output.mkdir()

    arguments = ["retain", "--baseline", "alda", "--frames", "2000", "--seed", "1",
                 "--run-dir", str(run_dir), "--output", str(output)]

    without_console = _family(*arguments)
    assert without_console.returncode != 0
    assert "console log" in without_console.stderr

    (output / "training.log").write_text("[INFO] alda: eval/episode_reward: 2.42\n")
    with_console = _family(*arguments)
    assert with_console.returncode == 0, with_console.stderr
    retained = json.loads((output / "retained.json").read_text())
    assert "training.log (console)" in retained["curves"]
    assert retained["checkpoint_source"].endswith("sac_None_step_2000.pt")


# [Claude 2026-09-02 10:45 MSK: docs/CONSTRUCTION.md#c57 -- a drqv2 run diverged to NaN around
# frame 35,000, trained 70,000 more, logged seven evaluations and wrote a snapshot, and every
# artifact this project keeps looked like a run that had merely trained badly. On a seven-hour
# production run that costs the run and everything computed from it. The gate is cheap; the test
# is what stops it from being decorative.]
def test_a_checkpoint_of_nans_fails_the_finiteness_gate(tmp_path):
    import torch

    healthy = tmp_path / "healthy.pt"
    torch.save({"agent": {"weights": torch.randn(64, 64)}}, healthy)
    diverged = tmp_path / "diverged.pt"
    weights = torch.randn(64, 64)
    weights[3, 7] = float("nan")
    torch.save({"agent": {"weights": weights}}, diverged)
    empty = tmp_path / "empty.pt"
    torch.save({"agent": {"step": 10000}}, empty)

    good = _family("check-finite", "--family", "rlvigen", "--root", str(ROOT), "--checkpoint", str(healthy))
    assert good.returncode == 0, good.stderr
    assert json.loads(good.stdout)["non_finite"] == 0
    assert json.loads(good.stdout)["float_values"] == 4096

    bad = _family("check-finite", "--family", "rlvigen", "--root", str(ROOT), "--checkpoint", str(diverged))
    assert bad.returncode != 0
    assert "1 of 4096" in bad.stderr and "NaN or infinite" in bad.stderr

    nothing = _family("check-finite", "--family", "rlvigen", "--root", str(ROOT), "--checkpoint", str(empty))
    assert nothing.returncode != 0
    assert "no floating-point values" in nothing.stderr


# [Claude 2026-09-02 10:40 MSK: job bt1a8q6ee090jh1k9npp died in bootstrap because CTRL's
# jax[cuda12] install replaced numpy and cudnn with versions torch, numba and matplotlib reject.
# The shared `pip check` caught it -- after a full bootstrap. This catches it before one.]
def test_a_family_that_cannot_share_an_environment_is_refused_before_the_bootstrap():
    mixed = _family("check-co-schedulable", "--cells", "alda,ppg,ibac_sni,ctrl")
    assert mixed.returncode != 0
    assert "cannot share a job" in mixed.stderr
    assert "ctrl" in mixed.stderr

    alone = _family("check-co-schedulable", "--cells", "ctrl,ctrl:2")
    assert alone.returncode == 0, alone.stderr

    ordinary = _family("check-co-schedulable", "--cells", "alda,ppg,ibac_sni")
    assert ordinary.returncode == 0, ordinary.stderr


def test_ppg_declares_the_headers_its_mpi_extension_needs():
    """mpi4py has no wheel for this image and builds a C extension."""
    packages = _family("apt-packages", "--family", "ppg")
    assert packages.returncode == 0, packages.stderr
    assert "python3-dev" in packages.stdout
    assert "libopenmpi-dev" in packages.stdout


# [Claude 2026-09-02 10:55 MSK: jax[cuda12] requires nvidia-cudnn-cu12>=9 and torch 2.3.1+cu121
# pins 8.9.2.26; there is no version of both. CTRL is a JAX baseline that never imports torch, so
# its job installs the base requirements without it. The privilege is deliberately tied to
# co_schedulable false, so it can never quietly change what another baseline in the same job runs.]
def test_only_a_family_that_cannot_share_a_job_may_drop_a_base_requirement():
    for_ctrl = _family("filtered-requirements", "--cells", "ctrl")
    assert for_ctrl.returncode == 0, for_ctrl.stderr
    lines = for_ctrl.stdout.splitlines()
    assert not any(line.startswith(("torch==", "torchvision==")) for line in lines)
    assert not any("download.pytorch.org" in line for line in lines)
    # everything the robosuite environment needs is still there
    assert any(line.startswith("numpy==1.26.4") for line in lines)
    assert any(line.startswith("numba==") for line in lines)
    # ...and captum and kornia are NOT, which reverses what this test asserted until 2026-09-02.
    # It read `assert any(line.startswith("captum=="))` under the comment above, on the premise
    # that captum is part of what the robosuite environment needs. It is not: captum is sgqn's
    # attribution library and kornia is svea/soda's augmentation one, and BOTH DEPEND ON TORCH.
    # Excluding torch by name while keeping them left pip free to resolve torch transitively --
    # and with our pin gone it took the newest, torch 2.14.0, with CUDA 13 wheels onto a CUDA 12.2
    # driver. Job bt1amu1210ol8ofufa16 warned "The NVIDIA driver on your system is too old" and
    # died with no traceback. Excluding a package by name does not exclude its dependants.
    assert not any(line.startswith(("captum==", "kornia==")) for line in lines)

    for_others = _family("filtered-requirements", "--cells", "drqv2,sgqn")
    assert for_others.returncode == 0, for_others.stderr
    assert any(line.startswith("torch==") for line in for_others.stdout.splitlines())
    assert for_others.stdout == (ROOT / "requirements-native.txt").read_text()


# [Claude 2026-09-02 11:45 MSK: a 500k RL-ViGen run performs ten checkpoint saves and upstream keeps
# one, because every save writes the same filename. The nine it discards are the same policy at
# 50k, 100k, ... -- a budget curve that costs no training to evaluate and a full retrain to
# recover. P18 writes a step-stamped copy when the job asks; this keeps them, and keeps the
# terminal one unambiguous.]
def test_intermediate_checkpoints_are_kept_separately_from_the_terminal_one(tmp_path):
    import torch

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "train.csv").write_text("frame,episode_reward\n500,1.0\n")
    torch.save({"agent": {"w": torch.zeros(4)}, "step": 500000}, run_dir / "snapshot.pt")
    for step in (50000, 100000):
        torch.save({"agent": {"w": torch.zeros(4)}, "step": step}, run_dir / f"snapshot_{step}.pt")
    output = tmp_path / "out"

    kept = _family("retain", "--baseline", "drqv2", "--frames", "500000", "--seed", "1",
                   "--run-dir", str(run_dir), "--output", str(output))

    assert kept.returncode == 0, kept.stderr
    retained = json.loads((output / "retained.json").read_text())
    assert set(retained["intermediate_checkpoints"]) == {"snapshot_50000.pt", "snapshot_100000.pt"}
    assert (output / "checkpoints" / "snapshot_50000.pt").exists()
    # the terminal checkpoint keeps its own place and is not duplicated into the curve directory
    assert torch.load(output / "snapshot.pt", weights_only=False)["step"] == 500000
    assert not (output / "checkpoints" / "snapshot.pt").exists()


def test_p18_is_off_unless_the_job_asks_and_is_a_cadence_when_it_does():
    """Twelve snapshots are 3.4-6.5 GiB per cell against 20.2 GiB free in the container.

    P18 became a CADENCE on 2026-09-02 rather than a boolean, because upstream's save gate is a
    hardcoded `global_step % int(5e4)` and a 600k run therefore saves twelve times: keeping all of
    them is 6.5 GiB for `drq`, and keeping none loses a budget curve that costs no training to
    produce. The dial is the same one for the curve's resolution and its cost.

    Asserted textually because `train.py` is the vendored tree and importing it needs hydra,
    robosuite and a GL context. Three separate properties are checked rather than one literal --
    the previous version pinned the exact string `os.environ.get('RLVIGEN_PRESERVE_SNAPSHOTS')`
    and broke when a default argument was added to the same call, which is the register's standing
    lesson about textual assertions matching a spelling rather than a behaviour.
    """
    patches = (ROOT / "setup" / "apply_patches.py").read_text()
    assert "RLVIGEN_PRESERVE_SNAPSHOTS" in patches
    assert '"P18": "ENABLES"' in patches

    train = (ROOT / "RL-ViGen-upstream" / "train.py").read_text()
    assert "snapshot_{self.global_frame}.pt" in train
    assert "RLVIGEN_PRESERVE_SNAPSHOTS" in train
    # off unless asked: the whole stamping block sits behind a truthiness test on the variable
    assert "if preserve:" in train
    # a cadence, not a flag
    assert "cadence = int(preserve)" in train
    assert "self.global_frame % cadence == 0" in train
    # and the endpoint is always kept when anything is -- a budget curve missing its last point
    # is not a budget curve
    assert "terminal = self.global_frame == self.cfg.num_train_frames" in train


# [Claude 2026-09-02 12:50 MSK: the common envelope. Not a replacement for the native logs -- they
# are retained unchanged and carried whole in `native` -- and not computed inside any trainer. Its
# whole point is that `regime` and `scene_set` are explicit on every row, because RL-ViGen's eval
# number is ten scenes and dmc_gb's is one, and a table that put them in one column would be
# comparing different measurements.]
NORMALIZER = ROOT / "datasphere" / "native" / "normalize_curves.py"


def test_one_native_evaluation_row_becomes_one_record_per_axis(tmp_path):
    cell = tmp_path / "cells" / "drqv2-s3"
    cell.mkdir(parents=True)
    (cell / "retained.json").write_text(json.dumps({"family": "rlvigen"}))
    (cell / "eval.csv").write_text(
        "frame,episode_reward,success_rate,train_regime_reward,train_regime_success\n"
        "10000,6.54,0.1,44.18,0.4\n")
    (tmp_path / "run_manifest.json").write_text(json.dumps(
        {"cells": {"drqv2-s3": {"baseline": "drqv2", "seed": "3"}}}))

    result = subprocess.run(
        [sys.executable, str(NORMALIZER), "--directory", str(tmp_path)],
        text=True, capture_output=True)
    assert result.returncode == 0, result.stderr

    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(records) == 2, records
    by_regime = {row["regime"]: row for row in records}
    assert by_regime["eval-easy"]["scene_set"] == "0-9"
    assert by_regime["eval-easy"]["episode_return_mean"] == 6.54
    assert by_regime["train"]["scene_set"] == "0"
    assert by_regime["train"]["episode_return_mean"] == 44.18
    # lossless: the whole native row travels with each record
    assert by_regime["train"]["native"]["episode_reward"] == "6.54"
    assert all(row["baseline"] == "drqv2" and row["seed"] == "3" for row in records)


def test_the_envelope_never_calls_a_single_scene_number_a_ten_scene_one(tmp_path):
    """dmc_gb evaluates one scene; RL-ViGen sweeps ten. The difference has to survive."""
    cell = tmp_path / "cells" / "rad-s1"
    cell.mkdir(parents=True)
    (cell / "retained.json").write_text(json.dumps({"family": "dmc_gb"}))
    (cell / "eval.log").write_text(json.dumps(
        {"step": 10000, "episode_reward": 1.99, "success_rate": 0.0,
         "episode_reward_test_env": 2.73, "success_rate_test_env": 0.0}) + "\n")

    result = subprocess.run(
        [sys.executable, str(NORMALIZER), "--directory", str(tmp_path)],
        text=True, capture_output=True)
    assert result.returncode == 0, result.stderr

    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert {row["scene_set"] for row in records} == {"0"}
    assert {row["regime"] for row in records} == {"train", "eval-easy"}


# [Claude 2026-09-02 13:25 MSK: the runner's own gate imports RL-ViGen's train.py, which imports
# torchvision. CTRL is a JAX baseline that runs with torch filtered out and reaches the robosuite
# environment through robosuitevgb, so it would fail on a module it was never going to use. Job
# bt1m4tjcmldq0qmb2ts9 died exactly there.]
def test_a_job_without_torch_does_not_run_the_torch_entrypoint_gate():
    assert _family("excludes-base-requirements", "--cells", "ctrl").returncode == 0
    assert _family("excludes-base-requirements", "--cells", "drqv2,sgqn").returncode != 0

    runner = RUNNER.read_text()
    guard = runner.index('excludes-base-requirements --cells')
    entrypoint = runner.index('importlib.import_module("train")')
    assert guard < entrypoint, "the guard has to come before the import it guards"


# --- verify-payload --expect ------------------------------------------------------------------
# A payload's version number certifies WHEN it was built, not WHAT it contains, and job configs
# name payloads by filename. cfg-metrics-probe-ctrl-ppg-v66 was submitted against an archive built
# before the edit it existed to validate; it would have run green. `verify_payload` cannot catch
# that -- its job is that every member is DECLARED, which a stale archive satisfies perfectly.
#
# `verify_contains` is exercised directly rather than through the CLI: routing these through
# `verify-payload` tests the DECLARATION check instead, which rejects a toy archive as undeclared
# before --expect is ever consulted. The first version of these tests did exactly that and passed
# for the wrong reason.
import importlib.util as _ilu
import pytest

_spec = _ilu.spec_from_file_location("_contract", ROOT / "datasphere" / "native" / "contract.py")
_contract = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_contract)


def _tiny_payload(tmp_path, body: str) -> Path:
    archive = tmp_path / "payload.tgz"
    member = tmp_path / "thing.py"
    member.write_text(body)
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(member, arcname="scripts/thing.py")
    return archive


def test_expect_fails_when_the_payload_predates_the_edit(tmp_path):
    """The whole point: a stale archive must be rejected BEFORE the job is submitted."""
    stale = _tiny_payload(tmp_path, "def f():\n    return 1\n")
    with pytest.raises(ValueError) as caught:
        _contract.verify_contains(stale, ("scripts/thing.py:the_new_identifier",))
    assert "predates that edit" in str(caught.value), (
        "a payload missing the edit must say so; such a payload otherwise builds, verifies, "
        "uploads and runs green")


def test_expect_passes_when_the_edit_is_present(tmp_path):
    """The negative control. A check that can only fail is as useless as one that can only pass."""
    fresh = _tiny_payload(tmp_path, "def f():\n    return the_new_identifier\n")
    _contract.verify_contains(fresh, ("scripts/thing.py:the_new_identifier",))


def test_expect_reports_a_missing_member_differently_from_a_missing_marker(tmp_path):
    """Two different defects: the file was never shipped, versus it shipped stale.

    They need different fixes -- a payload_members declaration versus a rebuild -- so collapsing
    them into one message sends the reader to the wrong place.
    """
    archive = _tiny_payload(tmp_path, "x = 1\n")
    with pytest.raises(ValueError) as caught:
        _contract.verify_contains(archive, ("scripts/absent.py:anything",))
    assert "not in the payload at all" in str(caught.value)


def test_contract_failure_and_bad_invocation_have_different_exit_codes(tmp_path):
    """[Claude 2026-09-04] A failed contract exits 4; a malformed command line exits argparse's 2.

    They were both 2. A caller that reads only the status -- `... && echo PRESENT || echo MISSING`,
    which is how this gate is used from a shell -- then reports a *present* marker as missing when
    the invocation is wrong. That happened today: `--archive` was passed positionally, argparse
    exited 2, and all four checkpoint edits were reported MISSING from a payload that contained
    every one of them. The near-consequence was an unnecessary payload rebuild; the general one is
    that a check which could not run must never be readable as a check that ran and failed.
    """
    import subprocess, sys, tarfile
    archive = tmp_path / "payload.tgz"
    member = tmp_path / "thing.py"
    member.write_text("print('no marker here')\n")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(member, arcname="scripts/thing.py")

    contract = Path(__file__).resolve().parents[1] / "datasphere" / "native" / "contract.py"
    bad = subprocess.run([sys.executable, str(contract), "verify-payload", str(archive)],
                         capture_output=True, text=True)
    assert bad.returncode == 2, "argparse's own error must stay 2"

    real = subprocess.run([sys.executable, str(contract), "verify-payload", "--archive",
                           str(archive), "--expect", "scripts/thing.py:absent_marker"],
                          capture_output=True, text=True)
    assert real.returncode == 4, (
        f"a genuine contract failure must exit 4, got {real.returncode}: {real.stderr}")


def test_submit_refuses_stale_payload_before_datasphere_execute(tmp_path):
    """Submission must reject a stale CODE archive before invoking the cloud CLI.

    The real job runner already rejects this archive, but that check used to happen only after
    the container had started.  A fake `datasphere` executable makes this a real submit-path test
    without creating a remote job: reaching it is the failure.
    """
    archive = tmp_path / "stale-payload.tgz"
    with tarfile.open(archive, "w:gz") as handle:
        manifest = tmp_path / "payload_manifest.json"
        manifest.write_text(json.dumps({"runner_contract": _runner_contract() - 1,
                                        "families": ["idaac"]}))
        handle.add(manifest, arcname="payload_manifest.json")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    invoked = tmp_path / "datasphere-invoked"
    fake_cli = fake_bin / "datasphere"
    fake_cli.write_text(
        "#!/bin/sh\n"
        "touch \"$FAKE_DATASPHERE_INVOKED\"\n"
        "exit 0\n"
    )
    fake_cli.chmod(0o755)
    image = json.loads((ROOT / "datasphere/native/source-lock.json").read_text())["container_image"]
    config = tmp_path / "stale.yaml"
    config.write_text(
        "name: stale-payload-submit\n"
        "cmd: >-\n"
        "  CELLS=idaac:1 FRAMES=10000 bash ${JOB} ${CODE} ${RESULT}\n"
        "inputs:\n"
        f"  - {archive}: CODE\n"
        "env:\n"
        "  docker:\n"
        f"    image: {image}\n"
        "cloud-instance-type: gt4.1\n"
    )

    result = subprocess.run(
        ["bash", str(ROOT / "datasphere/native/job.sh"), "submit", str(config)],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "FAKE_DATASPHERE_INVOKED": str(invoked),
            "NATIVE_EVIDENCE_LOG": str(tmp_path / "actions.log"),
        },
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "runner contract" in result.stderr
    assert not invoked.exists(), "stale payload reached datasphere execute"


def test_submit_refuses_payload_for_a_different_resolved_family(tmp_path):
    """Submission must reject a valid archive that does not carry the requested family."""
    archive = tmp_path / "wrong-family-payload.tgz"
    with tarfile.open(archive, "w:gz") as handle:
        manifest = tmp_path / "payload_manifest.json"
        manifest.write_text(json.dumps({"runner_contract": _runner_contract(),
                                        "families": ["ppg"]}))
        handle.add(manifest, arcname="payload_manifest.json")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    invoked = tmp_path / "datasphere-invoked"
    fake_cli = fake_bin / "datasphere"
    fake_cli.write_text(
        "#!/bin/sh\n"
        "touch \"$FAKE_DATASPHERE_INVOKED\"\n"
        "exit 0\n"
    )
    fake_cli.chmod(0o755)
    image = json.loads((ROOT / "datasphere/native/source-lock.json").read_text())["container_image"]
    config = tmp_path / "wrong-family.yaml"
    config.write_text(
        "name: wrong-family-submit\n"
        "cmd: >-\n"
        "  CELLS=idaac:1 FRAMES=10000 bash ${JOB} ${CODE} ${RESULT}\n"
        "inputs:\n"
        f"  - {archive}: CODE\n"
        "env:\n"
        "  docker:\n"
        f"    image: {image}\n"
        "cloud-instance-type: gt4.1\n"
    )

    result = subprocess.run(
        ["bash", str(ROOT / "datasphere/native/job.sh"), "submit", str(config)],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "FAKE_DATASPHERE_INVOKED": str(invoked),
            "NATIVE_EVIDENCE_LOG": str(tmp_path / "actions.log"),
        },
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "required family" in result.stderr
    assert not invoked.exists(), "wrong-family payload reached datasphere execute"
