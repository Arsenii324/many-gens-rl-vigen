#!/usr/bin/env python3
"""`run_cell.sh` must launch a budget that the wanted checkpoint is actually reachable from — C77.

The five RL-ViGen natives save at `global_step % int(5e4) == 0`, and that check sits inside
`if time_step.last():` at the TOP of a `while step < until` loop. At the end of the episode landing
on step N the while-test runs first, `N < N` is false, and the loop exits before the episode-end
block — so the save for step N never happens. A run launched at exactly N saves at every multiple
of 50k strictly BELOW N and never at N.

`run_cell.sh` asserted the opposite in a comment for a week: *"The default is therefore 50000, not
55000: same checkpoint, ~9% less compute."* It is no checkpoint. That claim cost a 3.5-hour drqv2
run which ended holding step-50000 weights, and its default budget would have produced zero
checkpoints for every future cell.

These drive the shipped `effective_frames` through the script's own `--effective-frames` query mode
rather than re-implementing it. That matters here more than usual: the failure being guarded
against was a *belief* about the rule, and a test that restates the belief would have agreed with
the bug.
"""
from __future__ import annotations

import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_cell.sh"

NATIVES = ("drqv2", "svea", "drq", "sgqn", "curl")
OTHERS = ("rad", "soda", "alda", "idaac", "ppg", "ctrl", "ibac_sni")


def eff(baseline: str, want: int) -> int:
    out = subprocess.run(["bash", str(SCRIPT), "--effective-frames", baseline, str(want)],
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return int(out.stdout.strip())


@pytest.mark.parametrize("baseline", NATIVES)
@pytest.mark.parametrize("want", [50_000, 100_000, 150_000])
def test_a_native_budget_always_exceeds_the_checkpoint_it_is_for(baseline, want):
    """The whole finding, stated as a property rather than a case."""
    got = eff(baseline, want)
    assert got > want, (
        f"{baseline} would be launched at exactly {want}, and the save for step {want} is "
        f"unreachable from there — the run would produce no checkpoint at {want} (C77)")


@pytest.mark.parametrize("baseline", NATIVES)
def test_a_budget_that_already_overshoots_is_left_alone(baseline):
    """55000 already works — it is what every existing 50k cell was launched with."""
    assert eff(baseline, 55_000) == 55_000, "a working budget was altered"


@pytest.mark.parametrize("baseline", OTHERS)
def test_non_natives_are_untouched(baseline):
    """Their cadences are settable (`--save_freq`, `checkpoint_n_steps`), so the trap does not apply.

    Bumping them would silently change a budget for no reason, and a budget is a reported number.
    """
    assert eff(baseline, 100_000) == 100_000, f"{baseline}'s budget was altered without cause"


def test_the_withdrawn_claim_is_not_still_in_the_script():
    """The comment that caused this is gone, and its correction names the entry.

    A wrong claim removed but not replaced invites the same inference from the same code, which is
    how C68's correct cadence produced C77's wrong boundary.
    """
    src = SCRIPT.read_text(encoding="utf-8")
    assert "C77" in src, "the corrected block no longer cites the entry that explains it"
    # Not a substring ban. The script QUOTES the withdrawn claim inside the comment that refutes
    # it, which is the right way to retire a wrong belief — a reader who finds only the correction
    # cannot tell what was corrected. The first version of this test failed on exactly that, the
    # same way the seam audit's null test first failed on "NOT that the metrics are comparable".
    # What must never happen is the claim standing unqualified.
    if "same checkpoint, ~9% less compute" in src:
        i = src.index("same checkpoint, ~9% less compute")
        around = src[max(0, i - 700):i + 700]
        assert any(k in around for k in ("WRONG", "It is not the same checkpoint", "It is NO checkpoint")), (
            "the withdrawn claim appears in run_cell.sh without its refutation nearby — a reader "
            "would take it as current guidance, which is what it was for a week")
