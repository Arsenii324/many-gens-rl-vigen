"""IBAC-SNI's source record must name the method, not the unrelated InfoBot PDF.

`ext/baseline_resources/11_ibac_sni/paper_1901.10902.pdf` is immutable downloaded evidence and
is intentionally left in place, but `pdftotext` identifies it as InfoBot.  The correct NeurIPS
paper is already vendored under `ext/papers-sorted/IBAC-SNI/`; project-owned pointers must never
turn the unrelated download back into the baseline's canonical source.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORRECT = "1910.12911"
WRONG = "1901.10902"


def test_project_owned_ibac_citations_name_the_actual_ibac_sni_paper():
    paths = [
        ROOT / "docs" / "ORIGINAL_LOCATIONS.md",
        ROOT / "baselines" / "ibac_sni" / "README.md",
        ROOT / "rlgen" / "registry.py",
        ROOT / "rlgen" / "algos" / "ibac_sni" / "__init__.py",
    ]
    for path in paths:
        text = path.read_text()
        assert CORRECT in text, f"{path.relative_to(ROOT)} still omits IBAC-SNI's actual arXiv id"
        assert f"arXiv:{WRONG}" not in text, (
            f"{path.relative_to(ROOT)} still cites InfoBot as IBAC-SNI")

    locations = paths[0].read_text()
    assert WRONG in locations and "InfoBot" in locations and "excluded" in locations.lower(), (
        "the bad download must remain traceable as excluded evidence, not disappear from provenance")


def test_reconciliation_excludes_infobot_and_names_the_canonical_local_paper():
    text = (ROOT / "notes" / "PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md").read_text()
    assert "IBAC-SNI_paper_neurips2019.pdf" in text
    assert CORRECT in text
    assert "InfoBot" in text and "excluded" in text.lower()
