"""`audit_row_closure.py --strict` must actually refuse a mixed-closure PRODUCTION row.

It did not. It compared each row's `execution_kind` to the literal string `"production"`, which is
not in the vocabulary: `contract.py`'s `RECORD_EXECUTION_KINDS` are `preflight`,
`eval_only_validation`, `training_production` and `exploratory`. No record in the corpus has ever
carried `"production"`, so the branch that reports findings was unreachable and the audit exited 0
whatever it was given -- including a synthetic production row pooling two different closures.

An audit that cannot fail is not evidence, and this one is what stands behind A24/A25's rule that
seeds from different closures are not pooled. So it is tested by construction here rather than by
reading: build records that violate the rule, and require a non-zero exit.
"""
from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_row_closure.py"
RECORDS = ROOT / "results" / "records"


def _template() -> dict:
    files = sorted(RECORDS.glob("*.jsonl"))
    if not files:
        pytest.skip("no records to use as a template")
    with files[0].open() as handle:
        return json.loads(handle.readline())


def _corpus(tmp_path: pathlib.Path, kind: str, revisions: tuple[str, ...]) -> pathlib.Path:
    base = _template()
    out = tmp_path / "synthetic__records.jsonl"
    with out.open("w") as handle:
        for seed, revision in enumerate(revisions, start=1):
            record = copy.deepcopy(base)
            record["seed"] = seed
            record["evaluator_revision"] = revision
            record["evaluator_code_revision"] = revision
            record["_delivery_provenance"] = dict(
                record.get("_delivery_provenance") or {}, execution_kind=kind)
            handle.write(json.dumps(record) + "\n")
    return tmp_path


def _run(records: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(AUDIT), "--strict", "--records", str(records)],
        capture_output=True, text=True, cwd=ROOT)


SAME = ("a" * 64, "a" * 64, "a" * 64)
MIXED = ("a" * 64, "a" * 64, "b" * 64)


def test_a_mixed_closure_production_row_is_refused(tmp_path):
    result = _run(_corpus(tmp_path, "training_production", MIXED))
    assert result.returncode != 0, (
        "a production row pooling two evaluator closures was accepted; this is the check that "
        "stands behind A24/A25's no-pooling rule")
    assert "MIXED-CLOSURE finding" in result.stdout


def test_a_mixed_closure_exploratory_row_is_tolerated(tmp_path):
    """Development legitimately spans payloads; flagging that trains readers to ignore the audit."""
    result = _run(_corpus(tmp_path, "exploratory", MIXED))
    assert result.returncode == 0, result.stdout


def test_a_single_closure_production_row_passes(tmp_path):
    result = _run(_corpus(tmp_path, "training_production", SAME))
    assert result.returncode == 0, result.stdout


def test_the_production_kind_matches_the_declared_vocabulary():
    """The dead-check bug in one line: the audit's kind must be one contract.py can emit."""
    sys.path.insert(0, str(ROOT / "datasphere" / "native"))
    from contract import RECORD_EXECUTION_KINDS

    import importlib.util
    spec = importlib.util.spec_from_file_location("_audit_row_closure", AUDIT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.PRODUCTION_KINDS <= RECORD_EXECUTION_KINDS, (
        f"{module.PRODUCTION_KINDS - RECORD_EXECUTION_KINDS} cannot appear in any record, so the "
        "production branch of the audit is unreachable")
