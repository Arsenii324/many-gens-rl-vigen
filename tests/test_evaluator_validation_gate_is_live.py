"""`gate_shared_evaluator_validated` must track the world, not repeat one string forever.

The gate used to hardcode "ZERO of twelve evaluator burdens are discharged", unconditionally --
which is the exact failure mode this project has fixed seven times elsewhere: an instrument whose
verdict does not depend on what actually happened. It stayed wrong through two rewrites because
nobody could prove it wrong without re-deriving the whole validation history by hand.

This pins three behaviors against a scratch ledger, so a future edit that reintroduces a hardcoded
verdict fails immediately rather than being trusted for another day.
"""
import importlib.util
import hashlib
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "datasphere" / "native" / "validated_evaluator_families.json"


def _gates():
    spec = importlib.util.spec_from_file_location("_pg_eval", ROOT / "scripts" / "production_gates.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_pg_eval"] = m
    spec.loader.exec_module(m)
    return m


def _current_revisions(family):
    sys.path.insert(0, str(ROOT))
    from scripts.eval_provenance import (evaluator_family_code_revision,
                                         evaluator_family_config_revision)
    return (evaluator_family_code_revision(ROOT, family),
            evaluator_family_config_revision(ROOT, family))


def test_the_ledger_is_well_formed():
    """Structure check only -- NOT a completeness claim. ppg/ibac_sni may genuinely be absent
    while their validation jobs are still in flight; that is real, current state, not a defect."""
    ledger = json.loads(LEDGER.read_text())
    gates = _gates()
    for key in ledger:
        if key.startswith("_"):
            continue
        assert key in gates.EVALUATOR_FAMILIES, f"'{key}' in the ledger is not a known family"
    for family, entry in ledger.items():
        if family.startswith("_"):
            continue
        assert {"job", "family_code_revision", "family_config_revision",
                "runtime_imports_checked", "paired", "diagnostics_complete",
                "validation_kind", "evaluator_revision", "evaluator_scope",
                "evaluator_scope_revision", "evaluator_measurement_revision",
                "evaluation_records_path", "evaluation_records_sha256"} <= entry.keys()


def _with_fake_ledger(gates, monkeypatch, fake: dict):
    real_read_text = pathlib.Path.read_text

    def patched(self, *a, **k):
        if self.name == "validated_evaluator_families.json":
            return json.dumps(fake)
        return real_read_text(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, "read_text", patched)


def _scope(family):
    from datasphere.native.evaluator_identity import FAMILY_ALLOWED_BASELINES

    sampled = family in {"idaac", "ppg", "ibac_sni", "ctrl"}
    ctrl = family == "ctrl"
    return {
        "family": family,
        "baseline": FAMILY_ALLOWED_BASELINES[family][0],
        "task": "Door",
        "frame": 100000,
        "eval_scope": "endpoint",
        "regimes": ["train"],
        "scenes": [0],
        "episodes": 5,
        "episode_seed": 1,
        "seed": 101,
        "device": "cuda",
        "action_repeat": 1,
        "frame_stack": 1,
        "image_size": 64,
        "episode_length": 500,
        "deterministic_setting": (
            {"backend": "jax", "mode": "seeded-prng", "enabled": True}
            if ctrl else
            {"backend": "torch", "mode": "torch.use_deterministic_algorithms", "enabled": True}
        ),
        "eval_policy_mode": "sample" if sampled else "mode",
    }


def _fake_environment(gates, monkeypatch, tmp_path):
    import scripts.eval_provenance as provenance

    monkeypatch.setattr(gates, "ROOT", tmp_path)
    functions = {
        "evaluator_family_code_revision": lambda _root, family: f"code-{family}",
        "evaluator_family_config_revision": lambda _root, family: f"config-{family}",
        "evaluator_family_revision": lambda _root, family: f"static-{family}",
    }
    for module in (gates, provenance):
        for name, function in functions.items():
            monkeypatch.setattr(module, name, function, raising=False)


def _entry(tmp_path, family, **overrides):
    from datasphere.native.evaluator_identity import measurement_revision, scope_revision

    scope = _scope(family)
    scope.update(overrides.pop("scope", {}))
    code = f"code-{family}"
    config = f"config-{family}"
    static = f"static-{family}"
    scope_hash = scope_revision(scope)
    artifact = tmp_path / "results" / "validation" / f"{family}.jsonl"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "phase": "offline-eval", "family": family, "baseline": scope["baseline"],
        "evaluator_revision": static, "evaluator_code_revision": code,
        "evaluator_config_revision": config, "evaluator_scope": scope,
        "evaluator_scope_revision": scope_hash,
        "evaluator_measurement_revision": measurement_revision(static, scope_hash),
    }
    raw = (json.dumps(row, sort_keys=True) + "\n").encode()
    artifact.write_bytes(raw)
    entry = {
        "job": f"job-{family}", "baseline": scope["baseline"],
        "code_revision": "historical", "family_code_revision": code,
        "family_config_revision": config, "runtime_imports_checked": True,
        "paired": True, "diagnostics_complete": True,
        "validation_kind": "functional_endpoint", "evaluator_revision": static,
        "evaluator_scope": scope, "evaluator_scope_revision": scope_hash,
        "evaluator_measurement_revision": measurement_revision(static, scope_hash),
        "evaluation_records_path": str(artifact.relative_to(tmp_path)),
        "evaluation_records_sha256": hashlib.sha256(raw).hexdigest(),
    }
    entry.update(overrides)
    return entry, artifact


def _all_fake_entries(gates, tmp_path):
    return {family: _entry(tmp_path, family)[0] for family in gates.EVALUATOR_FAMILIES}


def test_a_stale_revision_entry_does_not_count(monkeypatch):
    """The exact defect this replaces: alda's real validation predates CORRECTIONS #47's hash move.

    Confirms the gate treats a superseded-revision entry as NOT current, by construction rather than
    by re-reading prose.
    """
    gates = _gates()
    fake = {f: {"family_code_revision": "not-the-current-hash",
                "family_config_revision": "not-the-current-hash",
                "runtime_imports_checked": True, "job": "x", "paired": True,
                "diagnostics_complete": True} for f in gates.EVALUATOR_FAMILIES}
    _with_fake_ledger(gates, monkeypatch, fake)
    verdict, reason = gates.gate_shared_evaluator_validated()
    assert verdict == gates.OWNER
    assert "needs re-run" in reason


def test_all_current_and_complete_passes_with_shallow_functional_endpoint(
        monkeypatch, tmp_path):
    gates = _gates()
    _fake_environment(gates, monkeypatch, tmp_path)
    fake = _all_fake_entries(gates, tmp_path)
    _with_fake_ledger(gates, monkeypatch, fake)
    verdict, reason = gates.gate_shared_evaluator_validated()
    assert verdict == gates.PASS
    assert "all 7" in reason


def test_scope_attestation_is_required(monkeypatch, tmp_path):
    gates = _gates()
    _fake_environment(gates, monkeypatch, tmp_path)
    fake = _all_fake_entries(gates, tmp_path)
    for key in ("validation_kind", "evaluator_scope",
                "evaluator_scope_revision", "evaluator_measurement_revision",
                "evaluation_records_path", "evaluation_records_sha256"):
        fake["idaac"].pop(key)
    _with_fake_ledger(gates, monkeypatch, fake)
    verdict, reason = gates.gate_shared_evaluator_validated()
    assert verdict == gates.OWNER
    assert "scope" in reason.lower() or "attestation" in reason.lower()


@pytest.mark.parametrize("mutation", [
    lambda entry: entry["evaluator_scope"].update({"baseline": "drqv2"}),
    lambda entry: entry["evaluator_scope"].update({"eval_policy_mode": "mode"}),
    lambda entry: entry["evaluator_scope"].update({"eval_scope": "curve"}),
    lambda entry: entry.update({"evaluator_scope_revision": "wrong"}),
    lambda entry: entry.update({"evaluator_measurement_revision": "wrong"}),
    lambda entry: entry.update({"evaluator_revision": "wrong"}),
    lambda entry: entry.update({"evaluation_records_path": "../escape.jsonl"}),
    lambda entry: entry.update({"evaluation_records_sha256": "wrong"}),
])
def test_invalid_scope_or_binding_never_counts(monkeypatch, tmp_path, mutation):
    gates = _gates()
    _fake_environment(gates, monkeypatch, tmp_path)
    fake = _all_fake_entries(gates, tmp_path)
    mutation(fake["idaac"])
    _with_fake_ledger(gates, monkeypatch, fake)
    verdict, _reason = gates.gate_shared_evaluator_validated()
    assert verdict == gates.OWNER


def test_malformed_evidence_jsonl_never_counts(monkeypatch, tmp_path):
    gates = _gates()
    _fake_environment(gates, monkeypatch, tmp_path)
    fake = _all_fake_entries(gates, tmp_path)
    entry = fake["idaac"]
    artifact = tmp_path / entry["evaluation_records_path"]
    artifact.write_text("not json\n")
    entry["evaluation_records_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    _with_fake_ledger(gates, monkeypatch, fake)
    verdict, _reason = gates.gate_shared_evaluator_validated()
    assert verdict == gates.OWNER


def test_evidence_row_identity_must_match_ledger(monkeypatch, tmp_path):
    gates = _gates()
    _fake_environment(gates, monkeypatch, tmp_path)
    fake = _all_fake_entries(gates, tmp_path)
    entry = fake["idaac"]
    artifact = tmp_path / entry["evaluation_records_path"]
    row = json.loads(artifact.read_text())
    row["evaluator_scope_revision"] = "wrong"
    raw = (json.dumps(row, sort_keys=True) + "\n").encode()
    artifact.write_bytes(raw)
    entry["evaluation_records_sha256"] = hashlib.sha256(raw).hexdigest()
    _with_fake_ledger(gates, monkeypatch, fake)
    verdict, _reason = gates.gate_shared_evaluator_validated()
    assert verdict == gates.OWNER


def test_symlink_evidence_path_cannot_escape_repository(monkeypatch, tmp_path):
    gates = _gates()
    _fake_environment(gates, monkeypatch, tmp_path)
    fake = _all_fake_entries(gates, tmp_path)
    entry = fake["idaac"]
    artifact = tmp_path / entry["evaluation_records_path"]
    outside = tmp_path.parent / f"{tmp_path.name}-outside.jsonl"
    outside.write_bytes(artifact.read_bytes())
    artifact.unlink()
    try:
        artifact.symlink_to(outside)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"filesystem does not support symlinks: {error}")
    _with_fake_ledger(gates, monkeypatch, fake)
    verdict, reason = gates.gate_shared_evaluator_validated()
    assert verdict == gates.OWNER
    assert "escapes" in reason.lower()


def test_evidence_without_offline_eval_rows_never_counts(monkeypatch, tmp_path):
    gates = _gates()
    _fake_environment(gates, monkeypatch, tmp_path)
    fake = _all_fake_entries(gates, tmp_path)
    entry = fake["idaac"]
    artifact = tmp_path / entry["evaluation_records_path"]
    row = json.loads(artifact.read_text())
    row["phase"] = "training"
    raw = (json.dumps(row, sort_keys=True) + "\n").encode()
    artifact.write_bytes(raw)
    entry["evaluation_records_sha256"] = hashlib.sha256(raw).hexdigest()
    _with_fake_ledger(gates, monkeypatch, fake)
    verdict, reason = gates.gate_shared_evaluator_validated()
    assert verdict == gates.OWNER
    assert "offline-eval" in reason


def test_offline_eval_baseline_mismatch_never_counts(monkeypatch, tmp_path):
    gates = _gates()
    _fake_environment(gates, monkeypatch, tmp_path)
    fake = _all_fake_entries(gates, tmp_path)
    entry = fake["rlvigen"]
    artifact = tmp_path / entry["evaluation_records_path"]
    row = json.loads(artifact.read_text())
    row["baseline"] = "svea"
    raw = (json.dumps(row, sort_keys=True) + "\n").encode()
    artifact.write_bytes(raw)
    entry["evaluation_records_sha256"] = hashlib.sha256(raw).hexdigest()
    _with_fake_ledger(gates, monkeypatch, fake)
    verdict, reason = gates.gate_shared_evaluator_validated()
    assert verdict == gates.OWNER
    assert "baseline" in reason


def test_real_ledger_reflects_a_real_gap_right_now():
    """Non-vacuity against the ACTUAL ledger: it must not already claim full coverage, or this
    test's sibling above is not distinguishing anything."""
    gates = _gates()
    verdict, reason = gates.gate_shared_evaluator_validated()
    if verdict == gates.PASS:
        pytest.skip("all seven are validated on the current hash -- the gap this test checks for "
                    "is closed, which is good news, not a test failure")
    assert verdict == gates.OWNER


def test_gate_identity_inputs_are_profile_invariant(monkeypatch):
    """The gate's three live identity calls must not turn training profile into eval identity."""
    gates = _gates()
    values = []
    for profile in ("datasphere", "v100"):
        monkeypatch.setenv("NATIVE_HOST_PROFILE", profile)
        values.append({
            family: (
                gates.evaluator_family_code_revision(gates.ROOT, family),
                gates.evaluator_family_config_revision(gates.ROOT, family),
                gates.evaluator_family_revision(gates.ROOT, family),
            )
            for family in gates.EVALUATOR_FAMILIES
        })
    assert values[0] == values[1]
