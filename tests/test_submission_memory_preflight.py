"""Behavioral tests for DataSphere submission admission and memory preflight."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOB = ROOT / "datasphere/native/job.sh"


def _config(tmp_path: Path, command: str, *, tier: str = "gt4.1") -> Path:
    image = json.loads((ROOT / "datasphere/native/source-lock.json").read_text())["container_image"]
    config = tmp_path / "submission.yaml"
    config.write_text(
        "name: submission-test\n"
        "desc: test-only submission\n"
        f"cmd: >-\n  {command}\n"
        "env:\n"
        "  docker:\n"
        f"    image: {image}\n"
        f"cloud-instance-type: {tier}\n"
    )
    return config


def _stubbed_submission(tmp_path: Path, config: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "datasphere-stub.log"
    stub = bin_dir / "datasphere"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'printf \'%s\\n\' "$*" >> "$DATASPHERE_STUB_LOG"\n'
        'out=""\n'
        'previous=""\n'
        'for arg in "$@"; do\n'
        '  if [[ "$previous" == "-o" ]]; then out="$arg"; fi\n'
        '  previous="$arg"\n'
        "done\n"
        '[[ -n "$out" ]]\n'
        "printf 'bt1abcdefghijklmnopq\\n' > \"$out\"\n"
    )
    stub.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["DATASPHERE_STUB_LOG"] = str(log)
    env["NATIVE_EVIDENCE_LOG"] = str(tmp_path / "actions.log")
    env["NATIVE_V100_BUDGET_STATE"] = str(tmp_path / "v100-budget.json")
    result = subprocess.run(
        ["bash", str(JOB), "submit", str(config)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    return result, log


def test_job_submission_forwards_configured_extra_overrides_to_memory_check():
    source = JOB.read_text()
    assert "cfg_extra_overrides" in source
    assert "NATIVE_EXTRA_OVERRIDES=\"$cfg_extra_overrides\"" in source
    # g1.1 has a different physical shape from the V100 *host profile*: its eight-vCPU,
    # 48--96 GiB DataSphere node is admitted against the conservative gt4i.1 envelope. The
    # submission check must use that resolved admission tier, rather than the raw requested tier.
    assert "admission_tier=\"$tier\"" in source
    assert "admission_tier=\"gt4i.1\"" in source
    assert "check-memory --cells \"$cells\" --tier \"$admission_tier\"" in source


def test_production_scale_without_explicit_profile_never_invokes_datasphere(tmp_path):
    config = _config(tmp_path, "FRAMES=600000 NATIVE_PRODUCTION=1 printf ready")

    result, log = _stubbed_submission(tmp_path, config)

    assert result.returncode != 0
    assert "native_host_profile" in result.stderr.lower()
    assert not log.exists()


def test_conflicting_profile_assignments_never_invokes_datasphere(tmp_path):
    config = _config(
        tmp_path,
        "NATIVE_HOST_PROFILE=datasphere NATIVE_HOST_PROFILE=v100 "
        "FRAMES=600000 NATIVE_PRODUCTION=1 printf ready",
    )

    result, log = _stubbed_submission(tmp_path, config)

    assert result.returncode != 0
    assert "conflict" in result.stderr.lower()
    assert not log.exists()


def test_v100_profile_is_rejected_when_config_requests_datasphere_g1_tier(tmp_path):
    config = _config(
        tmp_path,
        "NATIVE_HOST_PROFILE=v100 FRAMES=600000 NATIVE_PRODUCTION=1 "
        "NATIVE_V100_RESERVATION_MINUTES=1 printf ready",
        tier="g1.1",
    )

    result, log = _stubbed_submission(tmp_path, config)

    assert result.returncode != 0
    assert "v100" in result.stderr.lower()
    assert "datasphere" in result.stderr.lower()
    assert not log.exists()


def test_explicitly_bound_datasphere_production_reaches_stub_and_records_binding(tmp_path):
    config = _config(
        tmp_path,
        "NATIVE_HOST_PROFILE=datasphere FRAMES=600000 "
        "NATIVE_PRODUCTION=1 printf ready",
    )

    result, log = _stubbed_submission(tmp_path, config)

    assert result.returncode == 0, result.stderr
    assert "project job execute" in log.read_text()
    evidence = (tmp_path / "actions.log").read_text()
    assert "profile=datasphere" in evidence
    assert "tier=gt4.1" in evidence
    assert "binding=explicit" in evidence


def test_historical_subproduction_config_without_profile_remains_allowed(tmp_path):
    config = _config(tmp_path, "FRAMES=100000 printf probe")

    result, log = _stubbed_submission(tmp_path, config)

    assert result.returncode == 0, result.stderr
    assert "project job execute" in log.read_text()
