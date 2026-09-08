"""The documents a reader is told to start from must not cite files that do not exist.

[Claude 2026-09-08] `README.md` pointed at `rlgen/algos/onpolicy_ext.py`, which was split into
`rlgen/algos/{idaac,ppg,ibac_sni,ctrl}/` some time ago. `docs/FAITHFULNESS.md` cites the same dead
file repeatedly. A dead path in an entry-point document is worse than one buried in an appendix:
it is the first thing someone follows, and following it costs them their trust in the rest.

Scoped to the entry points on purpose. Sweeping every `.md` in the tree would drown this in
historical ledger entries, which legitimately name files that were later removed -- those describe
a past state and are correct. These five describe what to do NOW.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

ENTRY_DOCS = ("README.md", "notes/START-HERE.md", "docs/RUN-THIS-PROJECT.md",
              "notes/RUNNING-ON-PRODUCTION-HOST.md", "notes/PRODUCTION-RUNBOOK.md")

PATH = re.compile(r"((?:scripts|setup|datasphere|runnable|rlgen|tests)/[\w./-]+\.(?:py|sh|json|yaml))")


def test_no_entry_document_cites_a_file_that_does_not_exist():
    dead = {}
    for rel in ENTRY_DOCS:
        doc = ROOT / rel
        if not doc.is_file():
            dead[rel] = ["the document itself is absent"]
            continue
        gone = sorted({m for m in PATH.findall(doc.read_text()) if not (ROOT / m).exists()})
        # A line saying a path NO LONGER exists is the fix, not the defect.
        gone = [g for g in gone
                if not re.search(rf"{re.escape(g)}[^\n]{{0,80}}(no longer exists|was split|removed)",
                                 doc.read_text())]
        if gone:
            dead[rel] = gone
    assert not dead, ("entry-point documents cite files that do not exist:\n"
                      + "\n".join(f"  {d}: {p}" for d, p in sorted(dead.items())))
