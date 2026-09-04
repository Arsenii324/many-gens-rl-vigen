"""`scripts/check_citations.py` runs, and no citation in this repo is BROKEN.

Its first run reported 427 citations, 0 broken, and 54 apparent failures that were all the
script's own false positives — deleted-file references, out-of-tree paths, and paths relative to a
reference repo's layout. It was tuned down rather than left crying wolf, and this pins the tuned
behaviour: a regression that re-inflates those categories into failures would make the instrument
useless in the specific way it was warned about.

The value here is drift protection, not discovery. Line numbers rot silently when a reference is
re-cloned at a different commit, which turns a checked claim back into a remembered one with no
visible event. It found nothing on its first run, and that is reported as a number rather than as
"clean".
"""
from __future__ import annotations

import functools
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _run(*extra):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "check_citations.py"), *extra],
                          capture_output=True, text=True, cwd=ROOT)


@functools.lru_cache(maxsize=1)
def _run_plain():
    """The no-argument invocation, shared by the two tests that both call `_run()` with no
    extra flags against the same unchanging repo state. Each spawn re-scans ~400+ citations
    across the whole tree; caching removes one of the two identical subprocess runs."""
    return _run()


def test_no_citation_points_past_the_end_of_its_file():
    """--strict exits 1 on any BROKEN citation. BROKEN is unambiguous: the path resolved
    uniquely and the cited line does not exist."""
    r = _run("--strict")
    assert r.returncode == 0, (
        "a citation points past the end of the file it names:\n" + r.stdout[-3000:])


def test_the_checker_still_separates_defects_from_uncheckable_citations():
    """The tuning is the load-bearing part; a regression that folds EXTERNAL/HISTORICAL/
    AMBIGUOUS back into a failure count would restore the false-positive flood."""
    out = _run_plain().stdout
    for cls in ("RESOLVED", "AMBIGUOUS", "EXTERNAL", "HISTORICAL", "MISSING", "BROKEN"):
        assert cls in out, f"category '{cls}' vanished from the report"
    assert "real defects (BROKEN + MISSING)" in out
    assert "never that it says what the citing text claims" in out, (
        "the report must keep stating that it checks line EXISTENCE, not content — without "
        "that line a green run reads as 'the citations are correct', which it does not mean")


def test_it_actually_finds_citations_rather_than_passing_vacuously():
    """A regex that matched nothing would pass every assertion above."""
    out = _run_plain().stdout
    n = int(next(l for l in out.splitlines() if l.startswith("citations found:")).split()[-1])
    assert n > 100, f"only {n} citations found — the pattern has probably stopped matching"
