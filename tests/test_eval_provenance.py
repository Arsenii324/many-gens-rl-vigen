from pathlib import Path

import pytest

from scripts.eval_provenance import (ActionDiagnosticsAccumulator, action_diagnostics,
                                     completed_episode_diagnostics, evaluator_revision,
                                     placement_hash)


class _Space:
    low = [-1.0, -1.0]
    high = [1.0, 1.0]


class _Env:
    action_space = _Space()
    episode_diagnostics = [{
        "initial_placement": {"body_pos": [0.1, 0.2, 0.3], "body_quat": [1, 0, 0, 0]},
        "episode_length": 2,
        "termination_reason": "time_limit",
        "reward_sum": 1.0,
        "reward_mean": 0.5,
        "reward_min": 0.4,
        "reward_max": 0.6,
        "applied_mode": "train",
        "applied_scene_id": 0,
        "action_clip_rate_coordinate": 0.0,
        "action_clip_rate_vector": 0.0,
        "action_raw_executed_l1": 0.0,
    }]


class _NoActionSpace:
    pass


def test_placement_hash_is_derived_from_realized_parameters():
    a = {"body_pos": [0.1, 0.2, 0.3], "body_quat": [1, 0, 0, 0]}
    b = {"body_pos": [0.1, 0.2, 0.31], "body_quat": [1, 0, 0, 0]}
    assert placement_hash(a) != placement_hash(b)


def test_completed_diagnostics_adds_derived_hash_and_policy_scale():
    row = completed_episode_diagnostics(_Env(), {"log_std_mean": 0.0}, 1)[0]
    assert len(row["placement_hash"]) == 64
    assert row["policy_scale"]["log_std_mean"] == 0.0


def test_evaluator_revision_hashes_every_measurement_affecting_source():
    root = Path(__file__).resolve().parents[1]
    revision = evaluator_revision(root)
    assert len(revision) == 64
    assert revision == evaluator_revision(root)


def test_evaluator_revision_distinguishes_runtime_host_profiles(monkeypatch):
    """Profile-selected rollout/replay geometry must never share an evaluator identity."""
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("NATIVE_HOST_PROFILE", "datasphere")
    datasphere = evaluator_revision(root)
    monkeypatch.setenv("NATIVE_HOST_PROFILE", "v100")
    v100 = evaluator_revision(root)
    assert len(v100) == 64
    assert datasphere != v100


def test_evaluator_revision_rejects_an_unknown_runtime_host_profile(monkeypatch):
    monkeypatch.setenv("NATIVE_HOST_PROFILE", "not-a-reviewed-host")
    with pytest.raises(RuntimeError, match="unknown host profile"):
        evaluator_revision(Path(__file__).resolve().parents[1])


def test_action_diagnostics_reports_vector_clipping():
    row = action_diagnostics([2.0, 0.5], _Env())
    assert row["action_clip_rate_coordinate"] == 0.5
    assert row["action_clip_rate_vector"] == 1.0
    assert row["action_raw_executed_l1"] == 1.0


def test_action_diagnostics_accumulator_records_pre_env_actions_without_mutating_them():
    accumulator = ActionDiagnosticsAccumulator(_Env())
    first = [2.0, 0.5]
    second = [0.5, -2.0]
    accumulator.observe(first)
    accumulator.observe(second)
    row = accumulator.finish()

    assert first == [2.0, 0.5]
    assert second == [0.5, -2.0]
    assert row["available"] is True
    assert row["actions_observed"] == 2
    assert row["action_clip_rate_coordinate"] == 0.5
    assert row["action_clip_rate_vector"] == 1.0
    assert row["action_raw_executed_l1"] == 2.0
    assert row["scope"] == "policy_output_before_env_action_boundary"
    assert row["controller_clipping_observed"] is False


def test_action_diagnostics_marks_unobserved_bounds_unavailable():
    accumulator = ActionDiagnosticsAccumulator(_NoActionSpace())
    accumulator.observe([0.0, 0.0])
    row = accumulator.finish()
    assert row["available"] is False
    assert row["reason"] == "action_bounds_not_observed"
    assert row["bounds_source"] == "normalized_fallback"


def test_declared_patch_and_grid_wire_real_rows():
    root = Path(__file__).resolve().parents[1]
    patcher = (root / "setup" / "apply_patches.py").read_text()
    grid = (root / "scripts" / "eval_grid.py").read_text()
    assert "P20 realized placement in reset" in patcher
    assert '"episode_diagnostics": diagnostics' in grid
    # [Corrected 2026-09-05, external review 7] The stamp is backend-specific now: torch's
    # deterministic-algorithms flag is not a property of a JAX measurement, and requirements-native
    # installs torch for every family so the old single boolean read `true` on ctrl regardless.
    assert '"determinism_backend": backend' in grid
    assert '"torch_deterministic_algorithms": DETERMINISTIC_ALGORITHMS' in grid
    assert '"deterministic_algorithms"' in grid
    assert "evaluator_revision=EVALUATOR_REVISION" in grid
