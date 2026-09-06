"""Local, owner-authorized accounting for the exceptional DataSphere g1.1 tier."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
JOB = ROOT / "datasphere" / "native" / "job.sh"
IMAGE = json.loads((ROOT / "datasphere/native/source-lock.json").read_text())["container_image"]


def _config(tmp_path: Path, *, tier: str = "g1.1", reservation: int | None = None,
            cells: str = "", timeout_seconds: int | None = 60,
            timeout_command: str | None = None) -> Path:
    setting = ""
    if timeout_command is None:
        timeout_command = (
            f"timeout --foreground {timeout_seconds}s env"
            if timeout_seconds is not None else "env"
        )
    setting += f"{timeout_command} "
    if reservation is not None:
        setting += f"NATIVE_V100_RESERVATION_MINUTES={reservation} "
    if cells:
        setting += f"CELLS={cells} "
    setting += "echo submit-placeholder"
    config = tmp_path / f"cfg-{tier.replace('.', '-')}.yaml"
    config.write_text(
        "name: v100-budget-test\n"
        "cmd: >-\n"
        f"  {setting}\n"
        "env:\n"
        "  docker:\n"
        f"    image: {IMAGE}\n"
        f"cloud-instance-type: {tier}\n"
    )
    return config


def _fake_datasphere(tmp_path: Path, *, exit_code: int = 0) -> tuple[Path, Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    invoked = tmp_path / "datasphere-invoked"
    cli = fake_bin / "datasphere"
    cli.write_text(
        "#!/bin/sh\n"
        "touch \"$FAKE_DATASPHERE_INVOKED\"\n"
        "out=''\n"
        "while [ $# -gt 0 ]; do\n"
        "  if [ \"$1\" = '-o' ]; then out=$2; shift 2; else shift; fi\n"
        "done\n"
        "printf '%s\\n' bt1abcdefghijklmnopq > \"$out\"\n"
        f"exit {exit_code}\n"
    )
    cli.chmod(0o755)
    return fake_bin, invoked


def _submit(tmp_path: Path, config: Path, state: Path, *, cloud_exit: int = 0) -> subprocess.CompletedProcess:
    fake_bin, invoked = _fake_datasphere(tmp_path, exit_code=cloud_exit)
    return subprocess.run(
        ["bash", str(JOB), "submit", str(config)],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin",
            "FAKE_DATASPHERE_INVOKED": str(invoked),
            "NATIVE_V100_BUDGET_STATE": str(state),
            "NATIVE_EVIDENCE_LOG": str(tmp_path / "actions.log"),
        },
        text=True,
        capture_output=True,
    )


def test_g11_submit_requires_an_explicit_reservation_before_cloud_execute(tmp_path):
    result = _submit(tmp_path, _config(tmp_path), tmp_path / "v100-budget.json")

    assert result.returncode != 0
    assert "NATIVE_V100_RESERVATION_MINUTES" in result.stderr
    assert not (tmp_path / "datasphere-invoked").exists()


def test_g11_timeout_is_bounded_by_the_reservation_before_any_state_or_cloud_write(tmp_path):
    state = tmp_path / "v100-budget.json"
    result = _submit(
        tmp_path,
        _config(tmp_path, reservation=50, timeout_seconds=6000),
        state,
    )

    assert result.returncode != 0
    assert "100" in result.stderr
    assert "timeout" in result.stderr.lower()
    assert not state.exists()
    assert not (tmp_path / "datasphere-invoked").exists()


def test_g11_reservation_at_rounded_timeout_bound_reaches_cloud(tmp_path):
    state = tmp_path / "v100-budget.json"
    result = _submit(
        tmp_path,
        _config(tmp_path, reservation=101, timeout_seconds=6001),
        state,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "datasphere-invoked").exists()
    record = json.loads(state.read_text())["reservations"]
    assert record[0]["reserved_minutes"] == 101


@pytest.mark.parametrize(
    "timeout_command",
    [
        "env",
        "timeout --foreground nope env",
        "timeout --foreground 60s env timeout --foreground 120s env",
    ],
    ids=["absent", "unparseable", "ambiguous"],
)
def test_g11_unbounded_timeout_is_refused_before_cloud(tmp_path, timeout_command):
    result = _submit(
        tmp_path,
        _config(tmp_path, reservation=20, timeout_command=timeout_command),
        tmp_path / "v100-budget.json",
    )

    assert result.returncode != 0
    assert "timeout" in result.stderr.lower()
    assert not (tmp_path / "datasphere-invoked").exists()


def test_g11_submit_refuses_a_reservation_over_the_cumulative_cap(tmp_path):
    # [Claude 2026-09-06] cap_minutes and the reservation amounts must both track
    # V100_BUDGET_CAP_MINUTES (job.sh:29). A state file whose cap_minutes disagrees with the
    # script's own constant is refused outright (load_state's own consistency guard, job.sh:235)
    # -- so this fixture using the OLD cap value started failing not because the cumulative-cap
    # check broke, but one level earlier, before that check is ever reached.
    # [Claude 2026-09-06, later] Rescaled 240->420 (owner's unconditional +180min top-up). Sized
    # so the scenario still genuinely exceeds the cap: 400 + 50 = 450 > 420.
    state = tmp_path / "v100-budget.json"
    state.write_text(json.dumps({
        "schema": 1,
        "cap_minutes": 420,
        "reservations": [{
            "reservation_id": "already-used",
            "tier": "g1.1",
            "reserved_minutes": 400,
            "actual_minutes": None,
            "job_id": "bt1oldabcdefghijklq",
            "status": "submitted",
        }],
    }))

    result = _submit(tmp_path, _config(tmp_path, reservation=50), state)

    assert result.returncode != 0
    assert "420" in result.stderr
    assert "exceed" in result.stderr.lower()
    assert not (tmp_path / "datasphere-invoked").exists()
    assert json.loads(state.read_text())["reservations"][0]["reservation_id"] == "already-used"


def test_g11_ambiguous_cloud_failure_retains_reservation_and_blocks_followup(tmp_path):
    # [Claude 2026-09-06] Sized against V100_BUDGET_CAP_MINUTES so the followup genuinely still
    # exceeds the cap, keeping the scenario this test exists to check (a retained reservation from
    # an ambiguous failure correctly blocks a followup that would breach the cap) exercised.
    # [Claude 2026-09-06, later] Rescaled 240->420: 400 + 50 = 450 > 420.
    state = tmp_path / "v100-budget.json"
    first = _submit(tmp_path, _config(tmp_path, reservation=400), state, cloud_exit=17)

    assert first.returncode != 0
    retained = json.loads(state.read_text())["reservations"]
    assert len(retained) == 1
    assert retained[0]["reserved_minutes"] == 400
    assert retained[0]["job_id"] is None
    assert retained[0]["status"] == "reserved"
    assert (tmp_path / "datasphere-invoked").exists()

    followup = tmp_path / "followup"
    followup.mkdir()
    second = _submit(followup, _config(followup, reservation=50), state)

    assert second.returncode != 0
    assert "exceed" in second.stderr.lower()
    assert not (followup / "datasphere-invoked").exists()
    assert len(json.loads(state.read_text())["reservations"]) == 1


def test_g11_successful_submit_records_job_id_and_reservation(tmp_path):
    state = tmp_path / "v100-budget.json"
    result = _submit(tmp_path, _config(tmp_path, reservation=20, cells="drqv2:1"), state)

    assert result.returncode == 0, result.stderr
    record = json.loads(state.read_text())["reservations"]
    assert len(record) == 1
    assert record[0]["job_id"] == "bt1abcdefghijklmnopq"
    assert record[0]["reserved_minutes"] == 20
    assert record[0]["status"] == "submitted"


def test_v100_budget_reconcile_updates_actual_elapsed_and_status_is_local(tmp_path):
    state = tmp_path / "v100-budget.json"
    result = _submit(tmp_path, _config(tmp_path, reservation=20), state)
    assert result.returncode == 0, result.stderr
    metadata = tmp_path / "jobs.json"
    metadata.write_text(json.dumps({"jobs": [{
        "id": "bt1abcdefghijklmnopq",
        "created_at": "2026-09-05T10:00:00Z",
        "finished_at": "2026-09-05T10:30:00Z",
    }]}))
    environment = {**os.environ, "NATIVE_V100_BUDGET_STATE": str(state)}

    reconciled = subprocess.run(
        ["bash", str(JOB), "v100-budget", "reconcile", str(metadata)],
        cwd=ROOT, env=environment, text=True, capture_output=True,
    )
    assert reconciled.returncode == 0, reconciled.stderr
    report = json.loads(reconciled.stdout)
    assert report["updated"] == 1
    assert report["actual_minutes_known"] == 30.0
    assert report["accounted_minutes"] == 30.0
    # V100_BUDGET_CAP_MINUTES=420 (job.sh:29, rescaled from 240 with the owner's +180min top-up)
    # - 30 accounted = 390.
    assert report["remaining_minutes"] == 390.0

    status = subprocess.run(
        ["bash", str(JOB), "v100-budget", "status"],
        cwd=ROOT, env=environment, text=True, capture_output=True,
    )
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout)["remaining_minutes"] == 390.0


def test_g11_invalid_reservation_is_rejected_before_cloud_execute(tmp_path):
    result = _submit(tmp_path, _config(tmp_path, reservation=0), tmp_path / "v100-budget.json")

    assert result.returncode != 0
    assert "positive integer" in result.stderr
    assert not (tmp_path / "datasphere-invoked").exists()


def test_non_g11_submit_does_not_create_or_consume_v100_budget(tmp_path):
    state = tmp_path / "v100-budget.json"
    result = _submit(tmp_path, _config(tmp_path, tier="gt4.1"), state)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "datasphere-invoked").exists()
    assert not state.exists()
