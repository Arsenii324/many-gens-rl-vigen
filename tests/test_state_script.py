"""`scripts/state.py` must actually run, because a handoff cites it for facts.

Two bugs were found in that script by hand between writing it and committing it — one printed a
false divergence alarm on a converged tree, the other hid the repo's worst provenance case behind
a number that looked like its best. Both were caught by running it and reading the output.

A tool that a handoff defers to, and that breaks silently, is worse than no tool: the next session
sees a traceback (or, worse, a partial table) where it expected the facts. This is a smoke test,
not a correctness test — it pins that the script runs and still emits the fields the handoff
promises, nothing about whether the numbers are right.
"""
from __future__ import annotations

import pathlib
import pytest
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _run():
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "state.py")],
                          capture_output=True, text=True, cwd=ROOT)


def test_state_script_runs_clean():
    r = _run()
    assert r.returncode == 0, f"scripts/state.py exited {r.returncode}\n{r.stderr[-2000:]}"
    assert not r.stderr.strip(), f"unexpected stderr:\n{r.stderr[-2000:]}"


def test_state_script_emits_the_fields_the_handoff_relies_on():
    out = _run().stdout
    for field in ("branch:", "vs main:", "base term", "descent"):
        assert field in out, f"missing '{field}' — the handoff cites this script for it"
    # Every registered baseline must appear; a silently dropped row is the failure mode
    # that would make the table read as "nothing to look at here".
    for name in ("ibac_sni", "ppg", "idaac", "ctrl", "alda", "rad", "soda"):
        assert name in out, f"baseline '{name}' vanished from the state table"


# `scripts/state.py:84,86` cite `../gen-rebuttal/...` -- a SIBLING PROJECT outside this repo.
# The two-hop source tag cannot be computed where that sibling is absent, so this test is
# structurally inapplicable there rather than failing. That is a genuine precondition, not a
# guard over a fault: it skips only when the input does not exist, and it says which input.
# It matters because `mutants/run.py` copies the tree to /tmp, where the sibling is not
# reachable, and the sanity mutant correctly refused to measure anything against that copy.
SIBLING = ROOT.parent / "gen-rebuttal"


@pytest.mark.skipif(not SIBLING.exists(),
                    reason=f"needs the sibling project at {SIBLING} for the two-hop source tag")
def test_state_script_names_which_reference_a_descent_figure_came_from():
    """`alda` matches a SIBLING project's port ~100% and the authors' own repo 0%.

    Printing only the percentage made the repo's worst provenance case look like its
    cleanest transcription. The source tag is the fix and must not regress.
    """
    out = _run().stdout
    alda = next((l for l in out.splitlines() if l.startswith("alda")), "")
    assert alda, "no alda row in the state table"
    assert "<" in alda and ">" in alda, (
        f"alda's descent figure carries no source tag: {alda!r} — a bare percentage here "
        "misrepresents a two-hop construction as a clean transcription")
