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


def test_ibac_entropy_line_is_read_when_no_log_std_exists():
    """The entropy fallback, on a line carrying no log_std field.

    [Claude 2026-09-16] This test's original name and docstring asserted that ibac "logs entropy
    `H`, never log_std". That was false, and the test could not catch it because the line it builds
    is synthetic and omits the fields ibac actually prints. See
    test_ibac_real_progress_line_uses_its_direct_log_std below, which is copied from the live cell.
    Before 2026-09-16 the watcher parsed zero readings from a 3,392-line live ibac log -- silent on
    the one baseline whose failure it was written for -- but the cause was a parsing gap, not an
    absent field."""
    from watch_policy_health import log_std_from_entropy
    text = "\n".join(f"U {i} | F {i*2048:06} | FPS 0350 | D 1 | rR:μσmM 1 1 1 1 | F:μσmM 1 1 1 1 "
                     f"| H {h} | V 0.1 | pL 0 | vL 0 | ∇ 0 | kl 1 | SR 0" for i, h in
                     enumerate((9.904, 9.72, 9.48, 9.10)))
    values = values_in(text)
    assert len(values) == 4, f"expected 4 entropy-derived readings, got {len(values)}"
    assert abs(values[0] - log_std_from_entropy(9.904)) < 1e-9


def test_ibac_real_progress_line_uses_its_direct_log_std():
    """Copied verbatim from ibac_sni s101 on the production host, update 218 of the live cell.

    ibac prints mean_log_std as `lns` (runnable/ibac_sni/torch_rl/scripts/train.py:294), which the
    direct patterns did not match, so this line fell through to the entropy route. The direct field
    must win: the route it was falling through to assumes a diagonal Gaussian over exactly 7 dims,
    and an assumption is worse than a number the trainer already wrote down."""
    from watch_policy_health import log_std_from_entropy
    line = ("U 218 | F 446464 | FPS 0353 | D 1399 | rR:\u03bc\u03c3mM 90.99 31.07 18.95 146.50 "
            "| F:\u03bc\u03c3mM 500.0 0.0 500.0 500.0 | H 7.883 | V 18.584 | pL 0.225 | vL 0.664 "
            "| \u2207 2.547 | kl 289.628 | SR 0.000 | clipf 0.290 | kl3 0.0288 "
            "| s 0.749 | lns -0.293 | bf 0.181")
    assert values_in(line) == [-0.293], "the direct `lns` field was not read exactly once"
    # And the fallback it replaces agrees with it, which is why the gap was invisible for a day.
    assert abs(log_std_from_entropy(7.883) - (-0.293)) < 0.002


def test_entropy_route_agrees_with_the_direct_field_on_real_data():
    """Measured over 232 progress lines of the live ibac_sni s101 cell, not asserted from theory.

    Derived-vs-direct mean log(sigma) differed by at most 0.00178 (mean 0.00046) across a range of
    -0.293 to -0.004. Both fields print at 3 decimals, worth ~0.0006 of that; the rest is that `H`
    is averaged over an update while `lns` is read at its end. The bound asserted here is the
    measured maximum with room, and it is two orders of magnitude below COLLAPSED_SIGMA = 0.05.

    The pairs below are the first, middle and last of that log. If this ever fails, the Gaussian
    assumption in log_std_from_entropy has stopped holding for this family."""
    from watch_policy_health import log_std_from_entropy
    for entropy, direct in ((9.904, -0.005), (7.948, -0.283), (7.943, -0.286)):
        assert abs(log_std_from_entropy(entropy) - direct) < 0.002, (entropy, direct)


def test_entropy_conversion_reproduces_the_runbook_sigma():
    """Ground truth, not a synthetic constant: PRODUCTION-RUNBOOK records ibac at sigma ~4.3 with
    entropy reaching 20.03. A diagonal Gaussian over 7 dims must reproduce that."""
    import math
    from watch_policy_health import log_std_from_entropy
    assert abs(math.exp(log_std_from_entropy(20.03)) - 4.23) < 0.01


def test_the_runbook_failure_fires_through_the_entropy_route():
    rising = "\n".join(f"| H {h} | V 0.1 |" for h in (9.95, 11.2, 13.4, 15.8, 18.1, 20.03))
    assert verdicts(values_in(rising)), "the documented ibac saturation produced no warning"


def test_a_direct_log_std_field_is_never_overridden_by_entropy():
    """idaac logs mean_log_std directly; the entropy route must not replace or add to it."""
    text = "| train/mean_log_std | -0.10 |\n| H 50.0 |"
    assert values_in(text) == [-0.10]
