"""The policy-health watcher must parse every family's log format, not just the ones it was written against.

[Claude 2026-09-16] Pointed at a live 3,105-line idaac training log, this script printed nothing and
exited 0 -- which is indistinguishable from "healthy, nothing to report". It had parsed ZERO
readings. idaac writes a pipe-delimited table, `| train/mean_log_std          | 0.000676 |`, and the
separator character class was ["'\\s:=] with no `|`.

The script exists to catch a run that is finite, non-crashing, and producing numbers all the way to
the end that are worth nothing -- PRODUCTION-RUNBOOK's ibac_sni at sigma ~4.3 with success 0.00
throughout. A silent watcher for that failure is the same failure one level up.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from watch_policy_health import values_in, verdicts  # noqa: E402


def test_the_pipe_delimited_table_format_is_parsed():
    """idaac's format, which produced zero readings before 2026-09-16."""
    text = "\n".join([
        "| train/mean_log_std          | 0.000676 |",
        "| train/mean_log_std          | -0.0224  |",
        "| train/mean_log_std          | -0.0581  |",
        "| train/mean_log_std          | -0.127   |",
    ])
    values = values_in(text)
    assert len(values) == 4, f"expected 4 readings from a pipe table, parsed {len(values)}"
    assert values[0] == 0.000676 and values[-1] == -0.127


def test_the_colon_and_equals_formats_still_parse():
    """The formats it was originally written against must not regress."""
    assert values_in("mean_log_std: -0.0224") == [-0.0224]
    assert values_in("mean_log_std=1.073") == [1.073]
    assert values_in("pi_logstd: 0.5") == [0.5]


def test_fewer_than_four_readings_yields_no_verdict():
    """Stated so the silence is attributable: too little data is not a clean bill of health."""
    assert verdicts([0.1, 0.2, 0.3]) == []


def test_a_saturating_head_is_actually_caught():
    """A watcher that cannot fire is the defect this file guards."""
    rising = [0.5, 0.6, 0.8, 1.2, 2.0, 3.0, 4.3, 4.5]
    assert verdicts(rising), "a head rising to sigma ~4.3 produced no verdict"
