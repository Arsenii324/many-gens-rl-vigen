"""A descriptor edit must not void a code validation.

The evaluator revision was one hash over code AND configuration. That was right about
under-sensitivity -- a descriptor edit really can change what is measured -- and wrong about
consequences: **every `families.json` edit invalidated every family already validated**, and the
pending owner decisions A14 (host profiles) and A20 (`curve_eval_episodes`) both live in that file.

So the evaluator could not be frozen for validation while any decision stayed open, and the hash
moved twice in one day for exactly this reason. Two stamps fix it: configuration changes move the
config revision and the combined one, and leave the code revision alone.
"""
import importlib.util
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _prov():
    spec = importlib.util.spec_from_file_location("_prov_split", ROOT / "scripts" / "eval_provenance.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_prov_split"] = module
    spec.loader.exec_module(module)
    return module


def test_the_two_member_sets_partition_the_whole():
    prov = _prov()
    assert set(prov.CODE_MEMBERS) | set(prov.CONFIG_MEMBERS) == set(prov.REVISION_MEMBERS)
    assert not (set(prov.CODE_MEMBERS) & set(prov.CONFIG_MEMBERS)), "a member is in both sets"
    assert prov.CONFIG_MEMBERS, "configuration must have at least one member or the split is a no-op"


def test_a_config_edit_moves_config_and_combined_but_not_code():
    """Executed against the real file, then restored -- the property, not the intention."""
    prov = _prov()
    families = ROOT / "datasphere" / "native" / "families.json"
    if not families.is_file():                                     # pragma: no cover
        pytest.skip("families.json is not in this tree")
    original = families.read_text()
    before = (prov.evaluator_code_revision(ROOT), prov.evaluator_config_revision(ROOT),
              prov.evaluator_revision(ROOT))
    try:
        data = json.loads(original)
        data["_revision_split_probe"] = "transient"
        families.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        after = (prov.evaluator_code_revision(ROOT), prov.evaluator_config_revision(ROOT),
                 prov.evaluator_revision(ROOT))
    finally:
        families.write_text(original)
    assert after[0] == before[0], (
        "a families.json edit changed the CODE revision, so descriptor edits still void code "
        "validations and the split has bought nothing"
    )
    assert after[1] != before[1], "a families.json edit must move the CONFIG revision"
    assert after[2] != before[2], "the combined revision must still notice a configuration change"


def test_records_carry_all_three():
    grid = (ROOT / "scripts" / "eval_grid.py").read_text()
    for field in ("evaluator_revision=", "evaluator_code_revision=", "evaluator_config_revision="):
        assert field in grid, f"records do not stamp {field}"
    assert grid.count("evaluator_code_revision=EVALUATOR_CODE_REVISION") == \
           grid.count("evaluator_revision=EVALUATOR_REVISION"), (
        "some emit sites stamp the combined revision without the code revision, so those rows "
        "cannot be checked for code identity"
    )
