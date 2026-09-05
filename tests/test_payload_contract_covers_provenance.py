"""The evaluator-revision stamp and the payload contract are two homes for one list.

`scripts/eval_provenance.evaluator_revision` raises when a member it hashes is absent.  On the
remote that absence is only discovered after the bootstrap has been paid for: job
bt11qe3gunam3cnjml0u died at "cannot stamp evaluator revision: missing rlgen/protocol.py" because
`rlgen/protocol.py` had been added to the stamp while `contract.BASE_ALLOWED` was not told.

This test is the containment those two lists never had.  It is deliberately a *static* check on the
declaration rather than a check on a built archive, so it fails in the fast suite instead of on the
next submission.
"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_every_provenance_member_is_a_declared_payload_member():
    provenance = _load("_prov", "scripts/eval_provenance.py")
    contract = _load("_contract", "datasphere/native/contract.py")
    allowed = tuple(contract.BASE_ALLOWED)
    uncovered = [m for m in provenance.REVISION_MEMBERS if not contract.is_allowed(m, allowed)]
    assert not uncovered, (
        "these files are hashed into the evaluator revision but the payload contract does not "
        f"ship them, so the stamp will raise remotely: {uncovered}"
    )


def test_every_provenance_member_exists_in_the_tree():
    """A member that no longer exists fails every job, remote and local alike."""
    provenance = _load("_prov2", "scripts/eval_provenance.py")
    missing = [m for m in provenance.REVISION_MEMBERS if not (ROOT / m).is_file()]
    assert not missing, f"evaluator revision names files that are not in the tree: {missing}"


def test_each_family_runtime_closure_is_shipped_or_a_pinned_external_input():
    """A family hash must name code the remote can actually execute.

    RL-ViGen is the one deliberate exception: it is supplied as a separately hash-checked archive,
    then patched and extracted by the runner, rather than copied into every payload.  Every other
    closure member must be admitted by that family's payload allowlist before an evaluator job can
    be submitted.
    """
    provenance = _load("_family_prov", "scripts/eval_provenance.py")
    contract = _load("_family_contract", "datasphere/native/contract.py")
    for family in provenance.EVALUATOR_FAMILIES:
        allowed = contract.allowed_for(ROOT, (family,))
        uncovered = [member for member in provenance.evaluator_runtime_members(ROOT, family)
                     if not member.startswith("RL-ViGen-upstream/")
                     and not contract.is_allowed(member, allowed)]
        assert not uncovered, f"{family} hashes runtime source the {family} payload omits: {uncovered}"
