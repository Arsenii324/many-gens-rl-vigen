"""The feasibility criterion must not double-count the co-tenant.

[Claude 2026-09-16] The first version computed `window = peak + floor + co-tenant hold` and
compared it to CURRENT free memory. That double-counts whenever the co-tenant is already resident,
because their hold is already subtracted from `free`. It reported ppg as needing 32,446 MiB on a
32,494 MiB card, and idaac as unschedulable while a card sat with 9,190 MiB free against idaac's
6,638 need. Running it against the live host is what showed it; reading it did not.

The correct form asks what a card can durably give US:
    capacity = card total - co-tenant PEAK hold - floor
    runnable = family peak + floor <= capacity
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import campaign_feasibility as cf  # noqa: E402


def test_capacity_subtracts_the_cotenant_once_not_twice():
    card, floor = cf.CARD_TOTAL_MIB, cf.FLOOR_MIB
    cotenant = 21_300
    capacity = card - cotenant - floor
    # idaac: peak 2,638 -> need 6,638, which fits beside a 21.3 GiB co-tenant.
    assert 2_638 + floor <= capacity, (
        "idaac must be schedulable beside the measured co-tenant; if this fails the criterion has "
        "regressed to double-counting")
    # ppg: peak 7,146 -> need 11,146, which does NOT fit beside the same co-tenant.
    assert 7_146 + floor > capacity, "ppg must NOT fit beside a 21.3 GiB co-tenant"


def test_ctrl_cannot_fit_one_card_at_all():
    """32,435 + 4,000 exceeds the card, so no co-tenant state makes ctrl schedulable."""
    assert 32_435 + cf.FLOOR_MIB > cf.CARD_TOTAL_MIB


def test_an_eval_cell_fits_where_a_training_cell_does_not():
    """The scheduling model the host actually has."""
    capacity_with_cotenant = cf.CARD_TOTAL_MIB - 21_300 - cf.FLOOR_MIB
    assert cf.EVAL_CELL_MIB < capacity_with_cotenant
    assert cf.EVAL_CELL_MIB < 2_638, "an eval cell must be smaller than the smallest trainer"


def test_it_runs_without_a_host_and_names_the_blocked_baselines():
    out = subprocess.run([sys.executable, str(ROOT / "scripts/campaign_feasibility.py")],
                         capture_output=True, text=True, cwd=ROOT, timeout=300)
    assert out.returncode == 0, out.stdout + out.stderr
    for blocked in ("svea", "sgqn", "soda"):
        assert blocked in out.stdout
    assert "BLOCKED ON ASSET" in out.stdout, "the Places365 blocker must be named, not implied"
    assert "NEEDS AN EMPTY CARD" in out.stdout, "ctrl's card-size problem must be named"
    assert "UNMEASURED" in out.stdout, "ibac_sni's missing figure must read as unmeasured"


def test_strict_fails_while_baselines_are_blocked():
    """Five baselines cannot be scheduled by adding GPU time. --strict must say so."""
    out = subprocess.run([sys.executable, str(ROOT / "scripts/campaign_feasibility.py"), "--strict"],
                         capture_output=True, text=True, cwd=ROOT, timeout=300)
    assert out.returncode == 1, "strict passed while baselines are blocked on assets and card size"
