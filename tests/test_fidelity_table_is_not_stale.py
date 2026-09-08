"""`docs/FAITHFULNESS.md`'s generated block must still match the tree.

The 2026-09-08 documentation sweep found that file stale on essentially every numeric claim about
the on-policy four -- idaac's gamma, rollout, lr and process count, ppg's num_envs and lr, the
frame-stack split, ctrl's cluster count. None was wrong when written; each described a port or a
decision that was later replaced, and nobody went back.

`scripts/audit_executed_hyperparameters.py` already asks whether a CLAIMED value reaches the
process, but only for claims in the one machine-readable shape it parses -- six of them. The prose
tables it cannot reach are exactly where the staleness was.

So the numbers are generated now, and this makes going stale a test failure rather than a reader's
wrong belief.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_the_generated_fidelity_block_matches_the_tree():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_fidelity_table.py"), "--check"],
        capture_output=True, text=True, cwd=str(ROOT))
    assert result.returncode == 0, (
        "docs/FAITHFULNESS.md's generated hyperparameter block no longer matches the tree. "
        "A decision landed and the document did not follow it -- which is the exact failure this "
        "block exists to prevent.\n"
        "Run: python scripts/generate_fidelity_table.py --write\n"
        f"{result.stdout}{result.stderr}")


def test_the_block_actually_carries_the_values_that_went_stale():
    """A generator that emitted an empty table would pass the check above."""
    text = (ROOT / "docs" / "FAITHFULNESS.md").read_text()
    block = text.split("<!-- BEGIN GENERATED")[1].split("<!-- END GENERATED -->")[0]
    for baseline in ("drqv2", "svea", "sgqn", "curl", "drq", "rad", "soda", "alda",
                     "idaac", "ppg", "ibac_sni", "ctrl"):
        assert f"`{baseline}`" in block, f"{baseline} is missing from the generated table"
    # The specific claims the sweep found stale, in their corrected form.
    assert "| `idaac` | `idaac` | 3e-4" in block, "idaac's lr should read 3e-4 (IDAAC-C2), not 5e-4"
    assert "`procs` 1&rarr;16" in block, "ibac_sni's v100 overlay is what production actually runs"
    assert block.count("| 3 |") >= 12, "all twelve stack 3 frames since A40-REVISED-2"
