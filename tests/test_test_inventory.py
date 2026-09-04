"""The instrument that measures where this suite's coverage points, measured.

`scripts/test_inventory.py` produces the figure `docs/SYSTEM.md` uses to criticise its own test
coverage — most of it aimed at the superseded `rlgen/` port rather than at the twelve clones that
produce reported numbers. Until now that number came from code nothing had checked, which is a
circular position the register already noted.

Its known defect is pinned first: the import pattern was anchored on a single path segment, so
`from rlgen.algos.ppg.algo import Learner` matched nothing and **~80 port-era tests were filed as
STANDALONE**. That error flattered the project in the exact direction the figure is used to
criticise it — it made port coverage look smaller than it was.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.test_inventory import classify  # noqa: E402


def wrote(tmp_path, body: str) -> pathlib.Path:
    p = tmp_path / "t.py"
    p.write_text(body)
    return p


class TestNestedImportsAreSeen:
    def test_deeply_nested_port_import_is_port(self, tmp_path):
        """The regression. A single-segment anchor missed every parity suite."""
        f = wrote(tmp_path, "from rlgen.algos.ppg.algo import Learner\ndef test_a(): pass\n")
        assert classify(f)[0] == "PORT"

    def test_flat_port_import_is_port(self, tmp_path):
        assert classify(wrote(tmp_path, "from rlgen.agents import X\ndef test_a(): pass\n"))[0] \
            == "PORT"

    def test_import_module_form_is_seen_too(self, tmp_path):
        assert classify(wrote(tmp_path, "import rlgen.registry\ndef test_a(): pass\n"))[0] == "PORT"


class TestPrecedence:
    def test_clone_beats_port(self, tmp_path):
        """A test touching a clone constrains what produces numbers, even if it also imports
        the port. Counting it as PORT would understate the thing the figure exists to track."""
        f = wrote(tmp_path, "from rlgen.agents import X\np='runnable/idaac'\ndef test_a(): pass\n")
        assert classify(f)[0] == "CLONE"

    def test_contract_is_separate_from_port(self, tmp_path):
        """`protocol` is live in the clone era; filing it as PORT would overstate dead coverage."""
        assert classify(wrote(tmp_path, "from rlgen.protocol import P\ndef test_a(): pass\n"))[0] \
            == "CONTRACT"

    def test_no_reference_at_all_is_standalone(self, tmp_path):
        assert classify(wrote(tmp_path, "import json\ndef test_a(): pass\n"))[0] == "STANDALONE"


class TestCounting:
    def test_counts_module_level_and_method_tests(self, tmp_path):
        body = ("def test_a(): pass\n"
                "class TestX:\n"
                "    def test_b(self): pass\n"
                "    def test_c(self): pass\n"
                "def helper(): pass\n")
        assert classify(wrote(tmp_path, body))[1] == 3

    def test_does_not_count_helpers_or_commented_out_tests(self, tmp_path):
        """Written expecting a miscount, and the code was stricter than assumed.

        `^\\s*def test_` excludes `# def test_commented(...)` (the line starts with `#`, not
        whitespace) and excludes `def testing_helper` (no underscore straight after `test`).
        Kept as a pinned test rather than deleted: both exclusions are load-bearing for the
        counts SYSTEM.md quotes, and neither is obvious from the pattern at a glance.
        """
        body = "def testing_helper(): pass\n# def test_commented(): pass\ndef test_real(): pass\n"
        assert classify(wrote(tmp_path, body))[1] == 1

    def test_an_indented_commented_test_is_also_excluded(self, tmp_path):
        body = "class TestX:\n    # def test_old(self): pass\n    def test_new(self): pass\n"
        assert classify(wrote(tmp_path, body))[1] == 1


def test_the_live_inventory_still_classifies_every_test_file(tmp_path):
    """No file may fall outside the four buckets, or the shares stop summing to the whole."""
    from scripts.test_inventory import TESTS
    files = sorted(TESTS.glob("test_*.py"))
    assert files, "no test files found -- this checker would report a clean empty inventory"
    for f in files:
        target, n = classify(f)
        assert target in {"CLONE", "CONTRACT", "PORT", "STANDALONE"}, (f.name, target)
        assert n >= 0


def test_clone_is_an_upper_bound_and_the_script_says_so(tmp_path):
    """A file that merely NAMES a clone path is counted as CLONE, and that is documented.

    Two of this session's own instrument tests embed `runnable/...` strings as fixtures -- one
    asserting that such a path classifies as code, one building a synthetic file body -- and
    together they added 15 to the CLONE count while constraining no clone at all. The detector is
    a substring search and cannot tell a target from test data.

    Pinned rather than fixed. Every sharper rule tried (require a filesystem call, require an
    import from a clone) also matched those files, and a detector wrong in an unpredictable way
    is worse than one wrong in a way that is written down.
    """
    fake = wrote(tmp_path, 'PATHS = ["runnable/idaac/x.py"]\ndef test_a(): pass\n')
    assert classify(fake)[0] == "CLONE", "the known over-count"

    src = (ROOT / "scripts" / "test_inventory.py").read_text()
    assert "UPPER BOUND" in src, (
        "the limitation is no longer documented at source; the number would then read as a "
        "count of clone-facing tests, which it is not")
