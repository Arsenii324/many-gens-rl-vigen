"""The operator guide must stay runnable: every need routed, every option documented.

[Claude 2026-09-16] This exists because the guide went eight days out of date without anything
noticing. The launch path moved to a wrapper layer and the guide kept describing the layer below
it; nothing failed, because prose cannot fail. These tests make it fail.

They are cheap -- no host, no GPU, no network -- and they guard the three ways the guide rots:
a need whose section is deleted or reduced to a stub, a script that gains an option nobody
documents, and an instruction naming a path a fresh clone does not contain.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import operator_readiness as opr  # noqa: E402


def test_every_operator_need_routes_somewhere_real():
    missing = []
    for phase, need, doc, heading, tool in opr.NEEDS:
        body = opr.section_of(ROOT / doc, heading)
        if body is None:
            missing.append(f"{need}: no section {heading!r} in {doc}")
        elif len(body.strip()) <= 200:
            missing.append(f"{need}: section {heading!r} in {doc} is a stub")
        if tool is not None and not (ROOT / tool).exists():
            missing.append(f"{need}: tool {tool} is missing")
    assert not missing, "operator needs with nowhere to go:\n  " + "\n  ".join(missing)


def test_live_script_interfaces_are_documented():
    """A required variable the guide never names is a hole the operator falls into."""
    undocumented = []
    for script, doc in opr.INTERFACE_CONTRACTS:
        spath = ROOT / script
        assert spath.is_file(), f"{script} does not exist"
        required, optional = opr.extract_interface(spath)
        text = (ROOT / doc).read_text(errors="replace")
        for var in sorted(required):
            if var not in text:
                undocumented.append(f"{script}: REQUIRED {var} not named in {doc}")
        for var in sorted(optional):
            if var not in text:
                undocumented.append(f"{script}: option {var}={optional[var]!r} not stated in {doc}")
    assert not undocumented, "script/doc drift:\n  " + "\n  ".join(undocumented)


def test_the_guide_only_names_paths_a_clone_actually_has():
    problems = opr.clone_completeness()
    assert not problems, "unrunnable instructions:\n  " + "\n  ".join(problems)


def test_section_of_does_not_mistake_a_shell_comment_for_a_heading():
    """Regression: '# 1. record the run' inside a ```bash fence truncated a 27-line section to 123
    characters, which would have marked every command-bearing section an empty stub."""
    body = opr.section_of(ROOT / "notes/RUNNING-ON-PRODUCTION-HOST.md", "After a run")
    assert body is not None
    assert len(body.strip()) > 400, "code-fence comments are being read as headings again"
    assert "populate_evaluator_ledger" in body


def test_the_checker_actually_fails_when_something_is_wrong(tmp_path):
    """A check that cannot fail is the defect this project names most often."""
    doc = tmp_path / "guide.md"
    doc.write_text("# Guide\n\nRun `scripts/definitely_not_here.py`.\n")
    saved_docs, saved_root = opr.INSTRUCTION_DOCS, opr.ROOT
    try:
        opr.ROOT = tmp_path
        opr.INSTRUCTION_DOCS = ("guide.md",)
        assert opr.clone_completeness(), "clone_completeness passed a guide naming a missing path"
    finally:
        opr.INSTRUCTION_DOCS, opr.ROOT = saved_docs, saved_root


def test_runs_clean_as_a_command():
    out = subprocess.run([sys.executable, str(ROOT / "scripts/operator_readiness.py")],
                         capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert out.returncode == 0, f"operator_readiness.py exited {out.returncode}\n{out.stdout[-2000:]}"


def test_the_script_inventory_in_the_guide_is_current():
    """158 entry points, generated from their own docstrings. A hand-edited table of that size is
    wrong within a week; this makes staleness fail instead of accumulating."""
    out = subprocess.run([sys.executable, str(ROOT / "scripts/script_inventory.py"), "--check"],
                         capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert out.returncode == 0, out.stdout + out.stderr


def test_every_file_in_the_production_host_directory_is_indexed():
    """Its README says 'read this entire directory'. On 2026-09-16 thirteen of its thirty-three
    files were missing from that index, including the current-state note."""
    problems = opr.index_completeness()
    assert not problems, "unindexed operator documents:\n  " + "\n  ".join(problems)
