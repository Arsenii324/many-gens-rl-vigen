"""The geometry audit must report contradictions, not just print a table.

Frame stack and render size are the values this project has most often quoted wrongly in its own
prose, and each time the error was found by tracing five links by hand. The audit exists so the
answer is one command; this test exists so the audit cannot become a decoration that always
agrees with whatever it is given.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_observation_geometry.py"


def _run(extra: list[str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(AUDIT)] + (extra or []),
                          capture_output=True, text=True, cwd=str(ROOT))


def test_the_audit_runs_and_covers_all_twelve():
    sys.path.insert(0, str(ROOT))
    from rlgen.protocol import OBSERVATION_GEOMETRY

    result = _run()
    assert result.returncode == 0, result.stderr
    for baseline in OBSERVATION_GEOMETRY:
        assert baseline in result.stdout, f"{baseline} missing from the geometry audit"


def test_it_names_the_baselines_the_runtime_check_has_never_run_for():
    """`never run` must be reported, not silently counted as agreement."""
    result = _run()
    assert "never run" in result.stdout or "every baseline has a record" in result.stdout


def test_strict_flags_a_record_that_contradicts_the_declaration(tmp_path, monkeypatch):
    """Feed it a record whose geometry disagrees with the protocol; --strict must exit 1."""
    records = ROOT / "results" / "records"
    planted = records / "zzz-synthetic-geometry-contradiction__records.jsonl"
    # A baseline whose declared pair is (3, 84), recorded as (1, 999) and nothing else would be
    # CONTRADICTED -- but drqv2 already has a valid record, so use a baseline with none.
    # It must carry the LIVE revision. A record with none was never produced by the evaluator --
    # training-curve rows carry no `evaluator_revision` -- so it says nothing about the current
    # closure's geometry and is classified as historical, not as a contradiction. Planting the
    # live revision is what makes this a test of the current tree rather than of any old file
    # that happens to sit in results/records.
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "datasphere" / "native"))
    from evaluator_identity import evaluator_family_revision
    planted.write_text(json.dumps({
        "baseline": "curl", "family": "rlvigen",
        "evaluator_revision": evaluator_family_revision(ROOT, "rlvigen"),
        "evaluator_scope": {"frame_stack": 1, "image_size": 999},
    }) + "\n")
    try:
        result = _run(["--strict"])
        assert result.returncode == 1, result.stdout
        assert "CONTRADICTED" in result.stdout
        assert "curl" in result.stdout
    finally:
        planted.unlink()

    # And with the plant removed it must go back to passing, or the test proves nothing.
    assert _run(["--strict"]).returncode == 0


def test_the_live_revision_map_is_never_silently_empty():
    """An empty map turns every record into a mismatch and reads as `never run`.

    Written after the audit reported `never run` for drqv2 and drq minutes after they produced
    records carrying exactly the live revision. `_live_revisions()` called
    `evaluator_family_revision(family)` against a `(root, family)` signature and
    `except Exception: continue` converted the TypeError into an empty dict.

    The identical bug was written into `scripts/audit_attempt_ledger.py` the same day and found
    there first, because that instrument disagreed with `populate_evaluator_ledger.py` and the
    disagreement was loud. Here there was nothing to disagree with, so a wrong answer looked like
    the audit's ordinary "no evidence yet" verdict — which is the one distinction this audit exists
    to make.
    """
    import importlib.util
    import sys as _sys

    spec = importlib.util.spec_from_file_location(
        "_geometry_audit_under_test", ROOT / "scripts" / "audit_observation_geometry.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)

    live = audit._live_revisions()
    assert live, "the live-revision map is empty; every record would read as historical"

    _sys.path.insert(0, str(ROOT / "rlgen"))
    from rlgen.protocol import OBSERVATION_GEOMETRY
    missing = sorted(set(OBSERVATION_GEOMETRY) - set(live))
    assert not missing, f"no live revision for {missing}; their records cannot be judged current"
