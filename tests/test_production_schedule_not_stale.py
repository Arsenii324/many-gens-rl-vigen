"""One number, one home: the schedule must not keep its own copy of the throughput table.

[Claude 2026-09-04] `production-schedule.json` carried a hand-maintained FPS table and drifted from
`plan_production.py` without anything noticing: it still read `drqv2: 17.53` after that figure had
been re-grounded on a 100k run at **26.05**, and still listed `alda`, `idaac`, `ppg`, `ibac_sni`
and `ctrl` as "estimated" after all five had completed real CUDA runs. A stale cost model is not a
harmless document -- every production shape argued from it was argued from the wrong throughput.

`plan_production.py --sync-schedule` regenerates the copy; this fails if it is out of date.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "datasphere" / "native"

_spec = importlib.util.spec_from_file_location("_plan_for_schedule", NATIVE / "plan_production.py")
plan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plan)

SCHEDULE = json.loads((NATIVE / "production-schedule.json").read_text())
V100_SCHEDULE = NATIVE / "production-schedule-v100.json"


def test_throughput_table_matches_the_source_of_truth():
    assert SCHEDULE["measured_completed_frames_per_second_gt4_1"] == dict(
        sorted(plan.MEASURED_FPS_GT4_1.items())), (
        "production-schedule.json's FPS table has drifted from plan_production.py. "
        "Run `python datasphere/native/plan_production.py --sync-schedule`.")


def test_every_baseline_is_present_not_just_the_measured_ones():
    """The stale table held seven of twelve, which made a twelve-baseline plan look complete."""
    assert len(SCHEDULE["measured_completed_frames_per_second_gt4_1"]) == 12


def test_estimated_list_reflects_the_current_basis():
    expected = [b for b, basis in sorted(plan.FPS_BASIS.items()) if basis != "measured"]
    assert SCHEDULE["estimated_baselines"] == expected
    assert "drqv2" not in SCHEDULE["estimated_baselines"]


def test_planner_respects_budget_independent_minimum_tier():
    """Memory arithmetic must not downgrade a family whose smaller tier has never worked."""
    row = plan.plan_row("ctrl", 600_000, None, [101, 102, 103])
    assert row["tier"] == "gt4i.1"
    assert row["cell_ram_gib"] == 13.4
    assert row["max_cells_per_job"] == 1


def test_schedule_generator_emits_the_current_protocol_shape():
    """Regeneration must not silently drop the fields its own stale-file checks require."""
    result = subprocess.run([sys.executable, str(NATIVE / "plan_production.py")],
                            check=True, capture_output=True, text=True)
    generated = json.loads(result.stdout)
    assert {row["frames"] for row in generated["rows"]} == {600_000}
    assert generated["measured_completed_frames_per_second_gt4_1"] == dict(
        sorted(plan.MEASURED_FPS_GT4_1.items()))
    assert "recommended_settings" not in generated


def test_v100_schedule_is_resolved_from_its_profile_and_makes_throughput_unknown():
    """A V100 artifact must not inherit DataSphere replay, tiers, or measured-throughput labels."""
    result = subprocess.run(
        [sys.executable, str(NATIVE / "plan_production.py"), "--host-profile", "v100"],
        check=True,
        capture_output=True,
        text=True,
    )
    generated = json.loads(result.stdout)
    assert generated["host_profile"] == "v100"
    assert generated["host"]["cpu_cores"] == 16
    assert generated["host"]["ram_gib_available"] == 113
    assert generated["host"]["gpu_vram_mib"] == 32 * 1024
    assert "tiers" not in generated, "DataSphere billing tiers do not describe the V100 host"

    rows = {row["baseline"]: row for row in generated["rows"]}
    for row in rows.values():
        assert row["v100_completed_frames_per_second"] is None
        assert row["throughput_source"] == "UNMEASURED_ON_V100"
        assert row["endpoint_eval_episodes"] == 20
        assert row["curve_eval_episodes"] == 3
        assert row["save_every_frames"] == 50_000
    assert rows["drqv2"]["replay_capacity"] == 620_000
    assert rows["drqv2"]["evicts_before_endpoint"] is False
    assert rows["idaac"]["runtime_constants"]["num_processes"] == "16"
    assert rows["idaac"]["executed_endpoint"] == 598_016
    assert rows["ppg"]["runtime_constants"]["num_envs"] == "8"
    assert rows["ppg"]["executed_endpoint"] == 600_064
    assert rows["ibac_sni"]["executed_endpoint"] == 600_064
    assert generated["resolved_descriptor_sha256"]


def test_v100_schedule_models_ibac_sni_resolved_process_tree_not_one_worker_envelope():
    """The V100 profile asks for 16 workers, so its memory plan must model all 16.

    `bt1kgfmbbjhnslfjekg1` measured 1.23 GiB in the parent plus 0.98 GiB per worker;
    with the 1.0 GiB declared margin the lower bound is 17.91 GiB.  The former 3.10
    GiB figure was a one-process T4 envelope attached to a 16-process V100 command.
    """
    row = next(row for row in plan.v100_schedule(600_000, [101]) ["rows"]
               if row["baseline"] == "ibac_sni")
    assert row["runtime_constants"]["procs"] == "16"
    assert row["cell_ram_gib_model"] == 17.91
    assert "process tree" in row["cell_ram_model_basis"]


def test_checked_in_v100_schedule_matches_the_explicit_profile_generator():
    assert V100_SCHEDULE.is_file(), (
        "generate it with plan_production.py --host-profile v100 --sync-schedule")
    expected = subprocess.run(
        [sys.executable, str(NATIVE / "plan_production.py"), "--host-profile", "v100"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert V100_SCHEDULE.read_text() == expected
