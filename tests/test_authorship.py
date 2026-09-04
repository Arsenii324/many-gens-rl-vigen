"""What counts as "code" decides every authorship percentage this project has published.

`scripts/authorship.py` measures each first-party file against every reference on disk. The
comparison is line-based, so `code()` — which decides what a line is — sets the denominator and
the numerator of every figure in `docs/STATE-2026-08-16.md` and the authorship rows of the audit.

Its rules are choices, not obviously-correct behaviour, and two of them can move a percentage a
long way. They are pinned here so they stay deliberate.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.authorship import code  # noqa: E402


def wrote(tmp_path, body: str) -> pathlib.Path:
    p = tmp_path / "m.py"
    p.write_text(body)
    return p


class TestWhatIsStripped:
    def test_the_module_docstring_does_not_count_as_code(self, tmp_path):
        """This project writes very long module docstrings. Counting them would make two files
        look similar for sharing prose, which is the opposite of what is being measured."""
        f = wrote(tmp_path, '"""A module docstring\nspanning lines.\n"""\nimport os\nx = 1\n')
        assert code(f) == ["import os", "x = 1"]

    def test_blank_lines_and_full_line_comments_are_dropped(self, tmp_path):
        f = wrote(tmp_path, "import os\n\n# a comment\n   \nx = 1\n")
        assert code(f) == ["import os", "x = 1"]

    def test_trailing_whitespace_is_normalised(self, tmp_path):
        """Otherwise a reformat registers as authorship."""
        assert code(wrote(tmp_path, "x = 1   \ny = 2\t\n")) == ["x = 1", "y = 2"]

    def test_an_inline_comment_is_kept_with_its_line(self, tmp_path):
        """Only FULL-line comments are dropped; a trailing comment stays attached, so two files
        agreeing on code but not on inline commentary read as different."""
        assert code(wrote(tmp_path, "x = 1  # why\n")) == ["x = 1  # why"]


class TestWhatIsDeliberatelyNotStripped:
    def test_only_the_first_docstring_is_removed(self, tmp_path):
        """Function and class docstrings COUNT as code. That is a choice with consequences: a
        file whose bulk is docstrings is compared largely on prose. `STATE-2026-08-16.md` records
        exactly such a case (`ibac_sni/storage.py`, "entirely docstring"). Pinned so the choice
        is visible rather than incidental."""
        f = wrote(tmp_path, '"""Module."""\ndef f():\n    """Inner docstring."""\n    return 1\n')
        assert '    """Inner docstring."""' in code(f)

    def test_a_file_with_no_module_docstring_is_untouched(self, tmp_path):
        assert code(wrote(tmp_path, "import os\nx = 1\n")) == ["import os", "x = 1"]

    def test_a_docstring_not_at_the_top_is_not_treated_as_the_module_docstring(self, tmp_path):
        f = wrote(tmp_path, "import os\n'''not a module docstring'''\nx = 1\n")
        assert len(code(f)) == 3


class TestDegenerateInputs:
    def test_a_missing_file_yields_no_lines_rather_than_raising(self, tmp_path):
        assert code(tmp_path / "absent.py") == []

    def test_a_file_that_is_only_a_docstring_yields_nothing(self, tmp_path):
        """And the caller must skip it: `main` does `if not ol: continue`, because a
        zero-line file would otherwise divide by zero or score 100% against anything."""
        assert code(wrote(tmp_path, '"""Only prose.\n\nNothing else.\n"""\n')) == []
