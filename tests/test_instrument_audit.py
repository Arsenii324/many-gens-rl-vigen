"""`scripts/audit_instruments.py` -- the auditor that reports which instruments are unaudited.

It is the most self-referential checker here, so the failure to guard against is the flattering
one: an auditor that reports good coverage because it cannot tell covered from uncovered. Each
test below is an input whose correct answer is known by construction.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_instruments as A  # noqa: E402


def tree(tmp: pathlib.Path, scripts: dict, tests: dict) -> pathlib.Path:
    (tmp / "scripts").mkdir(parents=True); (tmp / "tests").mkdir(parents=True)
    for n, b in scripts.items():
        (tmp / "scripts" / n).write_text(b)
    for n, b in tests.items():
        (tmp / "tests" / n).write_text(b)
    return tmp


def test_an_uncovered_instrument_is_reported_as_uncovered(tmp_path):
    rows = A.audit(tree(tmp_path, {"lonely.py": "x = 1\n"}, {}))
    assert [r["instrument"] for r in rows] == ["lonely"]
    assert rows[0]["tests"] == [] and rows[0]["red_green"] is False


def test_a_test_without_a_failure_assertion_is_not_counted_red_green(tmp_path):
    """The distinction the whole audit exists for: referenced is not the same as checked."""
    rows = A.audit(tree(tmp_path, {"thing.py": "x = 1\n"},
                        {"test_thing.py": "import thing\ndef test_it(): assert thing.x == 1\n"}))
    assert rows[0]["tests"] == ["test_thing.py"]
    assert rows[0]["red_green"] is False, (
        "a test that only asserts the happy path must not read as red-green, or the audit "
        "reports exactly the coverage it was built to question")


def test_a_deliberate_failure_assertion_is_counted(tmp_path):
    rows = A.audit(tree(tmp_path, {"thing.py": "x = 1\n"},
                        {"test_thing.py": "import thing\n# mutant: break it deliberately\n"}))
    assert rows[0]["red_green"] is True


def test_private_helpers_are_not_audited_as_instruments(tmp_path):
    rows = A.audit(tree(tmp_path, {"_helper.py": "x = 1\n", "real.py": "y = 2\n"}, {}))
    assert [r["instrument"] for r in rows] == ["real"]


def test_it_sees_this_repository(tmp_path):
    """Not a tautology: it must find the real scripts dir and not silently return nothing."""
    rows = A.audit()
    assert len(rows) > 15, f"only {len(rows)} instruments found in the real tree"
    assert any(r["instrument"] == "audit_instruments" for r in rows), (
        "the auditor must audit itself; excluding it is how it would stay green forever")
