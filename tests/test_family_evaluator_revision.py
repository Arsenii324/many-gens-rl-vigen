"""The offline evaluator identity follows code that actually computes a row.

The old single hash named the patch *generator* but not the imported implementation families.  It
therefore invalidated every evaluator after a training-only checkpoint change and missed an edit
to, for example, CTRL's actual vector environment.  These tests pin the distinction before the
new manifest is introduced.
"""
from pathlib import Path
import json

import pytest

from scripts import eval_provenance as provenance


ROOT = Path(__file__).resolve().parents[1]


def _mutate_bytes(monkeypatch, target: Path):
    """Make one source look changed without writing into the shared working tree."""
    original = Path.read_bytes
    target = target.resolve()

    def altered(self):
        value = original(self)
        if self.resolve() == target:
            return value + b"\n# transient revision probe\n"
        return value

    monkeypatch.setattr(Path, "read_bytes", altered)


def test_every_family_has_a_nonempty_existing_runtime_closure():
    assert set(provenance.EVALUATOR_FAMILIES) == set(provenance.FAMILY_RUNTIME_MEMBERS)
    for family in provenance.EVALUATOR_FAMILIES:
        members = provenance.evaluator_runtime_members(ROOT, family)
        assert members, family
        assert all((ROOT / member).is_file() for member in members), family


def test_live_ctrl_runtime_edit_moves_only_ctrl_family_identity(monkeypatch):
    before = {family: provenance.evaluator_family_code_revision(ROOT, family)
              for family in provenance.EVALUATOR_FAMILIES}
    _mutate_bytes(monkeypatch, ROOT / "runnable/ctrl/vec_env.py")
    after = {family: provenance.evaluator_family_code_revision(ROOT, family)
             for family in provenance.EVALUATOR_FAMILIES}

    assert after["ctrl"] != before["ctrl"]
    assert all(after[family] == before[family]
               for family in provenance.EVALUATOR_FAMILIES if family != "ctrl")


def test_live_rlvigen_utils_edit_moves_only_rlvigen_family_identity(monkeypatch):
    """External review 14: eval_across_scenes.py's run_scene does `import utils` live -- eval_mode,
    TruncatedNormal and the augmentation functions all live there and are measurement-relevant.
    Was omitted from FAMILY_RUNTIME_MEMBERS["rlvigen"]; an edit here used to move nothing."""
    before = {family: provenance.evaluator_family_code_revision(ROOT, family)
              for family in provenance.EVALUATOR_FAMILIES}
    _mutate_bytes(monkeypatch, ROOT / "RL-ViGen-upstream/utils.py")
    after = {family: provenance.evaluator_family_code_revision(ROOT, family)
             for family in provenance.EVALUATOR_FAMILIES}

    assert after["rlvigen"] != before["rlvigen"]
    assert all(after[family] == before[family]
               for family in provenance.EVALUATOR_FAMILIES if family != "rlvigen")


def test_ibac_training_driver_is_not_an_offline_evaluator_dependency(monkeypatch):
    before = provenance.evaluator_family_code_revision(ROOT, "ibac_sni")
    _mutate_bytes(monkeypatch, ROOT / "runnable/ibac_sni/torch_rl/scripts/train.py")
    assert provenance.evaluator_family_code_revision(ROOT, "ibac_sni") == before


def test_ppg_imported_training_module_is_in_the_evaluator_closure(monkeypatch):
    """PPG's package init imports train.py, so that module is evaluator-reachable."""
    before = {family: provenance.evaluator_family_code_revision(ROOT, family)
              for family in provenance.EVALUATOR_FAMILIES}
    _mutate_bytes(monkeypatch, ROOT / "runnable/ppg/phasic_policy_gradient/train.py")
    after = {family: provenance.evaluator_family_code_revision(ROOT, family)
             for family in provenance.EVALUATOR_FAMILIES}

    assert after["ppg"] != before["ppg"]
    assert all(after[family] == before[family]
               for family in provenance.EVALUATOR_FAMILIES if family != "ppg")


def test_unknown_family_is_rejected():
    with pytest.raises(ValueError, match="unknown evaluator family"):
        provenance.evaluator_family_code_revision(ROOT, "not-a-family")


def test_training_descriptor_edit_does_not_change_evaluator_identity(tmp_path):
    """families.json is training/provenance input, not fixed-checkpoint evaluator identity."""
    descriptor = ROOT / "datasphere/native/families.json"
    target = tmp_path / "datasphere/native/families.json"
    target.parent.mkdir(parents=True)
    target.write_text(descriptor.read_text())

    before = {family: provenance.evaluator_family_config_revision(tmp_path, family)
              for family in provenance.EVALUATOR_FAMILIES}
    data = json.loads(target.read_text())
    data["ctrl"]["_family_revision_test"] = "transient"
    target.write_text(json.dumps(data))
    after = {family: provenance.evaluator_family_config_revision(tmp_path, family)
             for family in provenance.EVALUATOR_FAMILIES}

    assert after == before
