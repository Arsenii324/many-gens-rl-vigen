"""`prior_art.py` must flag terms with a history, prefer code, and never fail silently.

It exists because on 2026-09-09 I nearly published three things the codebase already documented.
Its retrospective test is the honest one: run it on the notes where those misses happened and
check it surfaces the treatment I missed.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prior_art.py"


def _run(*args: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=str(ROOT))
    return proc.returncode, proc.stdout + proc.stderr


def test_it_surfaces_the_treatment_that_was_actually_missed(tmp_path):
    """THE retrospective test: NATIVE_RESULT_MIRROR was argued in run_on_production_host.sh.

    I wrote 'no durable second location exists on this host' without checking, and that file had
    already drawn the second-copy versus second-failure-domain distinction.
    """
    note = tmp_path / "draft.md"
    note.write_text("We need `NATIVE_RESULT_MIRROR` and there is nowhere on this host for one.\n")
    code, out = _run(str(note), "--min-hits", "3")
    assert code == 0, out
    assert "NATIVE_RESULT_MIRROR" in out, out
    assert "run_on_production_host.sh" in out, out
    assert "in code" in out


def test_code_hits_are_listed_before_prose(tmp_path):
    note = tmp_path / "draft.md"
    note.write_text("About `NATIVE_RESULT_MIRROR`.\n")
    code, out = _run(str(note), "--min-hits", "3")
    assert code == 0, out
    block = out.split("NATIVE_RESULT_MIRROR")[1]
    first = next(l for l in block.splitlines() if "code " in l or "prose " in l)
    assert "code " in first, f"code must lead:\n{block}"


#: Built at runtime so the literal never appears in this file. The first version hardcoded it and
#: the term then had two "prior mentions" -- both in this test -- which is the self-referential
#: version of exactly the problem prior_art.py exists to catch.
ABSENT = "zz" + "qq_nonexistent" + "_symbol"
ABSENT_UPPER = "ZZ" + "QQ_ALSO" + "_ABSENT"


def test_a_file_of_novel_terms_reports_no_prior_art_and_says_that_is_weak(tmp_path):
    note = tmp_path / "draft.md"
    note.write_text(f"`{ABSENT}` and `{ABSENT_UPPER}` only.\n")
    code, out = _run(str(note), "--min-hits", "2")
    assert code == 0, out
    assert "No term in this file has prior treatment" in out
    assert "WEAK evidence" in out, "it must not imply novelty is proven"


def test_the_file_itself_is_not_counted_as_prior_art(tmp_path):
    """A term used ten times in the draft must not read as ten prior mentions."""
    note = tmp_path / "draft.md"
    note.write_text(f"`{ABSENT}`\n" * 10)
    code, out = _run(str(note), "--min-hits", "2")
    assert code == 0, out
    assert "No term in this file has prior treatment" in out


def test_it_does_not_swallow_errors(tmp_path):
    """Regression: a blanket `except Exception: continue` made it print a header and nothing else.

    That is an instrument reporting a clean result because it could not run. If a term raises, the
    traceback must reach the caller rather than be silently skipped.
    """
    text = SCRIPT.read_text()
    assert "except Exception:\n                continue" not in text
    # The phrase wraps across comment lines, so match a fragment that does not.
    assert "an instrument that could not run must" in text, "the reasoning must stay with the code"


def test_min_hits_filters(tmp_path):
    note = tmp_path / "draft.md"
    note.write_text("About `NATIVE_RESULT_MIRROR`.\n")
    _, low = _run(str(note), "--min-hits", "3")
    _, high = _run(str(note), "--min-hits", "100000")
    assert "NATIVE_RESULT_MIRROR" in low
    assert "No term in this file has prior treatment" in high


def test_missing_file_is_reported(tmp_path):
    code, out = _run(str(tmp_path / "nope.md"))
    assert code == 0
    assert "no such file" in out
