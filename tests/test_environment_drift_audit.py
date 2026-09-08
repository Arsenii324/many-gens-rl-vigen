"""Real drift must be caught; family boundaries and unattributed jobs must not be called drift."""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_environment_drift import drift  # noqa: E402


def test_same_versions_are_not_drift():
    assert drift([("a", {"torch": "2.1", "numpy": "1.26"}),
                  ("b", {"torch": "2.1", "numpy": "1.26"})]) == {}


def test_a_package_absent_from_one_job_is_not_drift():
    """ctrl installs flax and the torch families do not. Reporting that would make the tool
    useless -- 67 of 131 packages 'differ' that way across the corpus."""
    assert drift([("a", {"torch": "2.1", "flax": "0.10"}),
                  ("b", {"torch": "2.1"})]) == {}


def test_a_genuine_version_difference_is_drift():
    found = drift([("a", {"torch": "2.1"}), ("b", {"torch": "2.2"})])
    assert "torch" in found and set(found["torch"].values()) == {"2.1", "2.2"}


def test_one_job_cannot_drift_against_itself():
    assert drift([("a", {"torch": "2.1"})]) == {}


def test_the_unattributed_bucket_is_never_compared():
    """Its first version pooled every job whose family could not be read and reported the result
    as DRIFT -- which was jobs from different families compared to each other."""
    source = (ROOT / "scripts" / "audit_environment_drift.py").read_text()
    assert 'by_family.pop("?"' in source
    assert "NOT compared" in source
