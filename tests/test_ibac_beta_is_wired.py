"""IBAC-SNI's VIB coefficient must reach the process, not just the fidelity table.

FAITHFULNESS.md:808 recorded `vib_beta: 1e-4` as matching CoinRun, and recorded that beta is
per-benchmark (1e-3 toy, 1e-6 Multiroom, 1e-4 CoinRun).  The launcher passed no `--beta`, so the
executed value was the branch default of 1.0 -- 10,000x the value the table claimed.  beta scales
the bottleneck KL that is the whole IBAC mechanism, so this is not a cosmetic mismatch.

This is the "two homes for one number" failure in its most expensive form: the sourced value lived
in prose, and the process used a default nobody had looked at.
"""
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "runnable" / "_launch" / "ibac_sni.sh"
TRAIN = ROOT / "runnable" / "ibac_sni" / "torch_rl" / "scripts" / "train.py"
COINRUN_BETA = 1e-4


def _exec_line() -> str:
    text = LAUNCHER.read_text()
    match = re.search(r"^exec .*?(?=\n(?!\s))", text, re.MULTILINE | re.DOTALL)
    assert match, "ibac_sni.sh no longer ends in a single exec invocation"
    return " ".join(match.group(0).split())


def test_the_launcher_passes_beta_explicitly():
    line = _exec_line()
    assert "--beta" in line, (
        "ibac_sni.sh must pass --beta; without it train.py's default of 1.0 applies, which is "
        "10,000x the CoinRun value FAITHFULNESS.md:808 records as ours"
    )
    value = re.search(r"--beta\s+(\S+)", line)
    assert value and float(value.group(1)) == pytest.approx(COINRUN_BETA), (
        f"expected the CoinRun beta {COINRUN_BETA}, found {value and value.group(1)}"
    )


def test_the_upstream_default_is_still_the_dangerous_one():
    """If upstream ever defaults beta sensibly, this test should be revisited, not silently kept."""
    if not TRAIN.is_file():                                        # pragma: no cover
        pytest.skip("ibac_sni clone is not present in this tree")
    match = re.search(r'add_argument\("--beta".*?default=([0-9.eE+-]+)', TRAIN.read_text(), re.S)
    assert match, "could not read train.py's --beta default"
    assert float(match.group(1)) == 1.0, (
        "train.py's --beta default changed; re-derive whether the launcher's explicit value is "
        "still the right one rather than assuming this test still guards the same thing"
    )
