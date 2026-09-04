"""`greenmark` decides whether the suite needs re-running. Both its known bugs were silent.

It answers two questions: *is the last green run still about this tree*, and *do the pending
changes even need a run*. A wrong answer is not a wrong number — it is a skipped suite, so the
failure is invisible by construction and shows up later as "but the tests passed".

Its own docstrings record two defects, both of the shape this project keeps finding, and both are
pinned here because nothing else would notice them coming back:

- **A sentinel that compared equal to itself.** `tree_id` fed `git write-tree` an empty file as an
  index; write-tree silently produced nothing and the function returned `"unknown"`. Two
  `"unknown"`s match, so it reported the tree STABLE while measuring nothing at all.
- **`RL-ViGen-upstream/` and `setup/` classified as not-code.** They carry patches P1-P5 that
  every baseline runs through, so `--why` said "docs-only, no run needed" for a change to the
  environment itself.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.greenmark import CODE_PREFIXES, pending_changes, tree_id  # noqa: E402

if subprocess.run("git rev-parse --git-dir", shell=True, cwd=ROOT,
                  capture_output=True).returncode != 0:
    pytest.skip("not a git repository", allow_module_level=True)


class TestWhatCountsAsCode:
    @pytest.mark.parametrize("path", [
        "RL-ViGen-upstream/train.py",          # carries P1-P5; every baseline runs through it
        "setup/apply_patches.py",              # the patch registry itself
        "runnable/_shim/sitecustomize.py",     # the MPS-as-CUDA shim
        "runnable/_launch/rlvigen.sh",         # how five baselines are invoked
        "tests/test_contract.py",
        "scripts/greenmark.py",
        "rlgen/protocol.py",
        "pytest.ini",
    ])
    def test_is_code(self, path):
        assert path.startswith(CODE_PREFIXES), (
            f"{path} would be classified as not-code, so --why would report 'docs-only' and the "
            "suite would be skipped for a change that can move every number")

    @pytest.mark.parametrize("path", [
        "docs/CONSTRUCTION.md", "README.md", "docs/SYSTEM.md",
    ])
    def test_is_not_code(self, path):
        assert not path.startswith(CODE_PREFIXES), (
            f"{path} counted as code; the check then never saves a run and gets ignored")


class TestTreeIdentity:
    def test_stable_when_nothing_changes(self):
        assert tree_id() == tree_id()

    def test_is_a_real_hash_not_a_sentinel(self):
        """The original bug returned the literal 'unknown', which matches itself."""
        t = tree_id()
        assert t not in ("", "unknown", None)
        assert len(t) == 16 and all(c in "0123456789abcdef" for c in t), t

    def test_changes_when_a_file_changes(self, tmp_path):
        """The property the whole instrument rests on. Without it every stamp stays valid."""
        before = tree_id()
        probe = ROOT / ".greenmark_selftest_tmp"
        probe.write_text("transient file written by tests/test_greenmark.py\n")
        try:
            after = tree_id()
        finally:
            probe.unlink(missing_ok=True)
        assert after != before, (
            "adding a file did not change the tree id, so a stamp taken before an edit would "
            "still validate after it -- the exact failure the 'unknown' sentinel caused")
        assert tree_id() == before, "removing the file did not restore the id"


class TestWhyAnswersTheCommittedDeltaCase:
    """A clean tree with a stale stamp is the COMMON case, and it used to be the one refused.

    `--why` reads the working tree; staleness compares committed tree hashes. Both can be true at
    once, and the branch that handled it used to print an instruction ("use git diff ...") rather
    than an answer.
    """

    def _why(self, monkeypatch, capsys, diff_out, returncode=0):
        import scripts.greenmark as gm

        class R:
            def __init__(self):
                self.stdout, self.stderr, self.returncode = diff_out, "", returncode

        class FakeMark:                       # PosixPath attributes are read-only
            def exists(self): return True
            def read_text(self, *a, **k): return "deadbeefdeadbeef\n"

        monkeypatch.setattr(gm, "pending_changes", lambda: ([], []))       # clean working tree
        monkeypatch.setattr(gm, "MARK", FakeMark())
        monkeypatch.setattr(gm, "tree_id", lambda: "0000000000000000")     # -> stale
        monkeypatch.setattr(gm.subprocess, "run", lambda *a, **k: R())
        monkeypatch.setattr(gm.sys, "argv", ["greenmark.py", "--why"])
        gm.main()
        return capsys.readouterr().out

    def test_a_committed_code_change_says_run_the_suite(self, monkeypatch, capsys):
        out = self._why(monkeypatch, capsys, "rlgen/protocol.py\ndocs/X.md\n")
        assert "STALE" in out and "CODE CHANGED" in out and "rlgen/protocol.py" in out

    def test_a_committed_docs_only_change_says_no_run_needed(self, monkeypatch, capsys):
        """The whole point of the tool: not re-running a 10-minute suite for prose."""
        out = self._why(monkeypatch, capsys, "docs/A.md\nREADME.md\n")
        assert "DOCS-ONLY" in out and "CODE CHANGED" not in out

    def test_an_unresolvable_stamp_falls_back_to_re_run_rather_than_claiming_docs_only(
            self, monkeypatch, capsys):
        """If the diff fails, the safe answer is 'run the suite' -- never 'no run needed'."""
        out = self._why(monkeypatch, capsys, "", returncode=128)
        assert "Re-run the suite" in out
        assert "DOCS-ONLY" not in out


class TestTheClassifierIsFedTheFilesItClassifies:
    """C94: `TestWhatCountsAsCode` checks the classifier on a *string*. Nothing checked that the
    string ever reaches it.

    It does not. `RL-ViGen-upstream/` is gitignored in full (`.gitignore:2`, `git ls-files` → 0),
    and `pending_changes()` reads `git status --porcelain`, which does not list ignored paths. So
    an edit to the environment every baseline runs through is reported as "no pending changes" —
    the exact defect the docstring at the top of this file records as fixed.

    The prefix entry is correct and unreachable. That is why this is xfail rather than a deletion:
    the assertion below is the property the project actually wants, and `strict=True` means that
    whoever closes the hole (see C94's options) gets a loud XPASS telling them to update C94 and
    unmark this test, instead of a silent green.
    """

    @pytest.mark.xfail(strict=True, reason="C94: vendored tree is gitignored, so the classifier "
                                           "never receives its paths")
    def test_an_edit_to_the_vendored_env_is_reported_as_code(self):
        probe = ROOT / "RL-ViGen-upstream" / "train.py"
        if not probe.exists():
            pytest.skip("vendored tree not installed")
        original = probe.read_bytes()
        try:
            probe.write_bytes(original + b"\n# C94 probe\n")
            files, code = pending_changes()
        finally:
            probe.write_bytes(original)
        assert any("RL-ViGen-upstream" in f for f in code), (
            "an edit to the vendored environment was not classified as a code change; "
            f"pending_changes() returned {len(files)} path(s), none of them upstream")
