"""The saturation alert must fire on the failure that every other check clears.

PRODUCTION-RUNBOOK:18: ibac_sni at sigma ~ 4.3, entropy climbing 9.95 -> 20.03, success 0.00
throughout, and PERFECTLY FINITE the entire time. A NaN check clears it; a wall-clock check clears
it; a returns check reads it as a method that is merely bad.
"""
from __future__ import annotations

import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from watch_policy_health import values_in, verdicts  # noqa: E402


def _ramp(to_sigma, n=40):
    return [(math.log(to_sigma) / (n - 1)) * i for i in range(n)]


def test_the_documented_runaway_warns():
    out = verdicts(_ramp(4.3))
    assert any(m.startswith("NATIVE_POLICY_SATURATION_WARNING") for m in out), out


def test_a_healthy_policy_is_silent():
    assert verdicts([-0.02 * i for i in range(40)][:20]) == []


def test_collapse_warns_too():
    out = verdicts([-0.2 * i for i in range(40)])
    assert any(m.startswith("NATIVE_POLICY_COLLAPSE_WARNING") for m in out), out


def test_a_high_but_flat_sigma_does_not_warn():
    """Saturation requires RISING. A method whose sigma is simply large and stable is a result."""
    assert not any(m.startswith("NATIVE_POLICY_SATURATION_WARNING")
                   for m in verdicts([math.log(3.0)] * 40))


def test_too_few_points_says_nothing():
    assert verdicts([0.0, 0.1]) == []


def test_it_parses_the_shapes_the_loops_actually_emit():
    text = '\n'.join([
        '{"mean_log_std": "0.0006404993390"}',
        "| train | mean_log_std: -0.0139 |",
        "pi_logstd=0.5",
    ])
    assert values_in(text) == [0.0006404993390, -0.0139, 0.5]


def test_it_never_aborts():
    """The whole design: it speaks, it does not kill."""
    source = (ROOT / "scripts" / "watch_policy_health.py").read_text()
    assert "NOT aborting" in source
    for forbidden in ("os.kill", "sys.exit(1)", "SIGKILL", "SIGTERM"):
        assert forbidden not in source, f"{forbidden} would turn a reportable result into a gap"
