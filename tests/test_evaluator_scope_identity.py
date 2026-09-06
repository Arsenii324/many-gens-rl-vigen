"""Tests for the resolved, row-level evaluator measurement scope."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _scope(**overrides):
    scope = {
        "family": "idaac", "baseline": "idaac", "task": "Door", "frame": 100000,
        "eval_scope": "endpoint", "regimes": "train,eval-easy", "scenes": "0,1",
        "episodes": 20, "episode_seed": 20260903, "seed": 101, "device": "cuda",
        "action_repeat": 1, "frame_stack": 1, "image_size": 64, "episode_length": 500,
        "deterministic_setting": {"backend": "torch", "mode": "torch.use_deterministic_algorithms",
                                   "enabled": True},
        "eval_policy_mode": "sample",
    }
    scope.update(overrides)
    return scope


def test_each_scope_field_moves_measurement_revision():
    from datasphere.native.evaluator_identity import canonical_evaluation_scope, measurement_revision, scope_revision
    base = canonical_evaluation_scope(_scope())
    base_scope = scope_revision(base)
    base_measurement = measurement_revision("static-family-revision", base_scope)
    changes = {
        "task": "Lift", "frame": 200000,
        "eval_scope": "curve", "regimes": "eval-hard,train", "scenes": "2,3",
        "episodes": 3, "episode_seed": 7, "seed": 102, "device": "cpu",
        "action_repeat": 2, "frame_stack": 3, "image_size": 100, "episode_length": 1000,
        "deterministic_setting": {"backend": "torch", "mode": "torch.use_deterministic_algorithms",
                                   "enabled": False},
    }
    for field, value in changes.items():
        altered = copy.deepcopy(_scope())
        altered[field] = value
        resolved = canonical_evaluation_scope(altered)
        assert scope_revision(resolved) != base_scope, field
        assert measurement_revision("static-family-revision", scope_revision(resolved)) != base_measurement


def test_same_family_baseline_mutation_moves_measurement_revision():
    from datasphere.native.evaluator_identity import canonical_evaluation_scope, scope_revision

    first = canonical_evaluation_scope(_scope(
        family="rlvigen", baseline="drqv2", eval_policy_mode="mode"))
    second = canonical_evaluation_scope(_scope(
        family="rlvigen", baseline="svea", eval_policy_mode="mode"))
    assert scope_revision(first) != scope_revision(second)


def test_family_baseline_mapping_is_canonical_and_rejects_mismatch():
    from datasphere.native.evaluator_identity import (
        FAMILY_ALLOWED_BASELINES, canonical_evaluation_scope,
    )

    assert FAMILY_ALLOWED_BASELINES == {
        "rlvigen": ("drqv2", "svea", "drq", "sgqn", "curl"),
        "dmc_gb": ("rad", "soda"),
        "alda": ("alda",), "idaac": ("idaac",), "ppg": ("ppg",),
        "ibac_sni": ("ibac_sni",), "ctrl": ("ctrl",),
    }
    mismatched = _scope(baseline="drqv2")
    with pytest.raises(ValueError, match="baseline.*family"):
        canonical_evaluation_scope(mismatched)


def test_scope_does_not_change_static_payload_config_revision():
    from datasphere.native import evaluator_identity
    static = evaluator_identity.evaluator_family_config_revision(ROOT, "idaac")
    first = evaluator_identity.scope_revision(evaluator_identity.canonical_evaluation_scope(_scope()))
    altered = _scope()
    altered["episodes"] = 3
    second = evaluator_identity.scope_revision(evaluator_identity.canonical_evaluation_scope(altered))
    assert first != second
    assert evaluator_identity.evaluator_family_config_revision(ROOT, "idaac") == static


def test_equivalent_scope_encodings_are_canonicalized_without_reordering_semantic_axes():
    from datasphere.native.evaluator_identity import canonical_evaluation_scope, scope_revision
    first = canonical_evaluation_scope(_scope())
    equivalent = _scope()
    equivalent["regimes"] = ["train", "eval-easy"]
    equivalent["scenes"] = [0, 1]
    assert first == canonical_evaluation_scope(equivalent)
    assert scope_revision(first) == scope_revision(canonical_evaluation_scope(equivalent))
    reordered = _scope()
    reordered["regimes"] = "eval-easy,train"
    assert scope_revision(first) != scope_revision(canonical_evaluation_scope(reordered))


def test_unresolved_scope_is_rejected_before_setup():
    from datasphere.native.evaluator_identity import canonical_evaluation_scope
    missing_mode = _scope()
    del missing_mode["eval_policy_mode"]
    with pytest.raises(ValueError, match="eval_policy_mode"):
        canonical_evaluation_scope(missing_mode)
    unknown_determinism = _scope()
    unknown_determinism["deterministic_setting"] = {"backend": "unknown", "enabled": True}
    with pytest.raises(ValueError, match="deterministic_setting"):
        canonical_evaluation_scope(unknown_determinism)


@pytest.mark.parametrize("field,value", [
    ("eval_scope", "not-a-scope"),
    ("regimes", "train,unknown"),
    ("scenes", "-1"),
    ("scenes", "10"),
    ("device", " "),
    ("frame_stack", 0),
    ("image_size", 0),
    ("episode_length", 0),
])
def test_invalid_scope_values_are_rejected_by_helper(field, value):
    from datasphere.native.evaluator_identity import canonical_evaluation_scope

    invalid = _scope(**{field: value})
    with pytest.raises(ValueError, match="evaluator scope"):
        canonical_evaluation_scope(invalid)


@pytest.mark.parametrize("option,value", [
    ("--baseline", "drqv2"),
    ("--regimes", "train,unknown"),
    ("--scenes", "-1"),
    ("--scenes", "10"),
    ("--device", " "),
    ("--frame-stack", "0"),
    ("--image-size", "0"),
    ("--episode-length", "0"),
])
def test_invalid_cli_scope_values_fail_before_family_setup(monkeypatch, tmp_path, option, value):
    import sys
    import scripts.eval_grid as grid

    snapshot = tmp_path / "snapshot.pt"
    snapshot.write_bytes(b"checkpoint")
    monkeypatch.setattr(grid, "find_snapshot", lambda _path: snapshot)
    monkeypatch.setattr(grid, "_idaac_setup", lambda: pytest.fail("family setup happened first"))
    monkeypatch.setattr(sys, "argv", [
        "eval_grid.py", "--family", "idaac", "--baseline", "idaac",
        "--snapshot", str(snapshot), "--frame", "1", option, value,
    ])
    with pytest.raises(ValueError, match="evaluator scope"):
        grid.main()


def test_eval_grid_rejects_unresolved_scope_before_family_setup(monkeypatch, tmp_path):
    import sys
    import scripts.eval_grid as grid

    snapshot = tmp_path / "snapshot.pt"
    snapshot.write_bytes(b"checkpoint")
    monkeypatch.setattr(grid, "find_snapshot", lambda _path: snapshot)
    monkeypatch.setattr(grid, "family_eval_policy_mode", lambda _family: "unknown-policy")
    monkeypatch.setattr(grid, "_idaac_setup", lambda: pytest.fail("family setup happened first"))
    monkeypatch.setattr(sys, "argv", ["eval_grid.py", "--family", "idaac",
                                       "--baseline", "idaac", "--snapshot", str(snapshot),
                                       "--frame", "1"])
    with pytest.raises(ValueError, match="eval_policy_mode"):
        grid.main()


def test_invalid_cli_scope_refuses_before_torch_import_or_determinism(monkeypatch, tmp_path):
    import builtins
    import sys
    import scripts.eval_grid as grid

    snapshot = tmp_path / "snapshot.pt"
    snapshot.write_bytes(b"checkpoint")
    monkeypatch.setattr(grid, "find_snapshot", lambda _path: snapshot)
    monkeypatch.setattr(sys, "argv", [
        "eval_grid.py", "--family", "idaac", "--baseline", "drqv2",
        "--snapshot", str(snapshot), "--frame", "1",
    ])
    real_import = builtins.__import__
    torch_imports = []

    def no_torch_import(name, *args, **kwargs):
        if name == "torch":
            torch_imports.append(name)
            raise AssertionError("torch imported before scope refusal")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_torch_import)
    with pytest.raises(ValueError, match="evaluator scope"):
        grid.main()
    assert torch_imports == []


def test_blank_task_refuses_before_family_setup(monkeypatch, tmp_path):
    import sys
    import scripts.eval_grid as grid

    snapshot = tmp_path / "snapshot.pt"
    snapshot.write_bytes(b"checkpoint")
    monkeypatch.setattr(grid, "find_snapshot", lambda _path: snapshot)
    monkeypatch.setattr(grid, "_idaac_setup", lambda: pytest.fail("family setup happened first"))
    monkeypatch.setattr(sys, "argv", [
        "eval_grid.py", "--family", "idaac", "--baseline", "idaac",
        "--snapshot", str(snapshot), "--frame", "1", "--task", "   ",
    ])
    with pytest.raises(ValueError, match="evaluator scope"):
        grid.main()


def test_record_envelope_defaults_scope_attestation_to_null():
    import importlib.util

    path = ROOT / "datasphere/native/normalize_curves.py"
    spec = importlib.util.spec_from_file_location("scope_normalize", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    row = module.record()
    assert row["evaluator_scope"] is None
    assert row["evaluator_scope_revision"] is None
    assert row["evaluator_measurement_revision"] is None


def test_scope_has_explicit_backend_policy_and_all_runner_routes_pass_resolved_args():
    helper = (ROOT / "datasphere/native/evaluator_identity.py").read_text()
    grid = (ROOT / "scripts/eval_grid.py").read_text()
    runner = (ROOT / "datasphere/native/run_probe.sh").read_text()
    normalizer = (ROOT / "datasphere/native/normalize_curves.py").read_text()
    for field in ("evaluator_scope", "evaluator_scope_revision", "evaluator_measurement_revision"):
        assert field in grid
        assert field in normalizer
    for marker in ("--regimes", "--scenes", "--episodes", "--episode-seed", "--device", "--eval-scope"):
        assert runner.count(marker) >= 3, marker
    assert "deterministic_setting" in helper
    assert "eval_policy_mode" in helper


def test_ctrl_and_sampled_policy_modes_are_explicit():
    from datasphere.native.evaluator_identity import (
        effective_deterministic_setting, family_eval_policy_mode, policy_mode_for,
    )
    from datasphere.native.normalize_curves import CONVENTIONS

    from datasphere.native.evaluator_identity import FAMILY_ALLOWED_BASELINES

    for family, baselines in FAMILY_ALLOWED_BASELINES.items():
        for baseline in baselines:
            assert CONVENTIONS[baseline]["eval_policy_mode"] == family_eval_policy_mode(family)
            assert policy_mode_for(family, baseline) == family_eval_policy_mode(family)
    assert effective_deterministic_setting("ctrl", True)["backend"] == "jax"
    assert effective_deterministic_setting("idaac", True)["backend"] == "torch"


def test_policy_mode_for_rejects_mismatched_family_baseline():
    from datasphere.native.evaluator_identity import policy_mode_for

    with pytest.raises(ValueError, match="baseline.*family"):
        policy_mode_for("idaac", "drqv2")
