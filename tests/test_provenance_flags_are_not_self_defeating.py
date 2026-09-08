"""The dirtiness flag must not be dirtied by the thing that records it.

`source_dirty` answers "does the recorded commit describe what was uploaded". It is written in two
places: `job.sh`'s submission-ledger block and `contract.py`'s payload manifest. Both computed it
as `bool(git status --porcelain)`.

`results/submissions.jsonl` is untracked and is written BY the submission. So from the first job
onward the working tree was never clean by that measure, and every row said `source_dirty: true` --
including six submitted from a tree that `production_gates.py::gate_source_tree_frozen` had just
verified clean in the same minute.

Nothing failed. The flag simply became a constant, which is worse than absent: a genuinely dirty
submission would have been indistinguishable from those six. Same shape as the docstring-versus-code
numbers found earlier the same day -- a signal that cannot vary tells you nothing.
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
JOB = ROOT / "datasphere" / "native" / "job.sh"
CONTRACT = ROOT / "datasphere" / "native" / "contract.py"

#: Outputs of the provenance machinery itself. They cannot describe the source they record, so
#: neither may count as evidence that the source is dirty.
SELF_WRITTEN = ("results/submissions.jsonl", "results/attempt-outcomes.json")


def test_the_submission_ledger_excludes_itself():
    text = JOB.read_text()
    assert 'bool(git("status", "--porcelain"))' not in text, (
        "job.sh counts its own untracked ledger as tree dirtiness, so source_dirty is true for "
        "every submission ever made")
    for path in SELF_WRITTEN:
        assert path in text, f"{path} is not excluded from job.sh's dirtiness check"


def test_the_payload_manifest_excludes_the_same_files():
    text = CONTRACT.read_text()
    assert '"source_dirty": status is None or bool(status)' not in text, (
        "contract.py has the same self-defeating check; any payload built after the first "
        "submission would report dirty regardless of the tree")
    for path in SELF_WRITTEN:
        assert path in text, f"{path} is not excluded from contract.py's dirtiness check"


def test_a_real_modification_still_reads_dirty(tmp_path):
    """The exclusion must be narrow: only those two files, never a blanket pass."""
    import subprocess
    import sys
    sys.path.insert(0, str(ROOT / "datasphere" / "native"))
    import contract

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "a.txt").write_text("one\n")
    # `results/` must already be TRACKED, as it is in the real repository (results/README.md).
    # git collapses an entirely-new directory to a single `?? results/` entry, which no per-file
    # exclusion can match -- so a fixture without this would test a situation that cannot occur
    # and would fail for the wrong reason.
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "README.md").write_text("kept\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "init"], check=True)
    assert contract._git_identity(tmp_path)["source_dirty"] is False

    # The excluded file alone must NOT read as dirty.
    (tmp_path / "results" / "submissions.jsonl").write_text("{}\n")
    assert contract._git_identity(tmp_path)["source_dirty"] is False, (
        "the ledger alone must not mark the tree dirty")

    # Any other change must.
    (tmp_path / "a.txt").write_text("two\n")
    assert contract._git_identity(tmp_path)["source_dirty"] is True, (
        "the exclusion is too broad; a real modification must still read dirty")
