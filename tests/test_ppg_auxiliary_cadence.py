"""PPG's auxiliary phase must fire at the published continuous-control cadence.

PPG's defining mechanism is its auxiliary phase, which fires every
`num_envs x nstep x n_pi` environment interactions. That product -- not any single
constant -- is the quantity a reader compares against the literature, and it is the
one external review 11 section 7 named as this project's clearest "handicapped
baseline?" attack surface.

Two reference points bracket it:

  * literal Procgen PPG (`train.py` defaults `num_envs=64`, `n_pi=32`, nstep 256):
    524,288 per auxiliary phase single-rank, ~2.1M under the 4-rank MPI setup the
    review assumed. At a 600k budget that is roughly one auxiliary phase, or none --
    i.e. faithful-to-Procgen PPG at this budget is essentially PPO, not PPG. Some
    retiming is therefore FORCED by the budget; the only question is which.
  * the one published continuous-control PPG design point (IDAAC's continuous-control
    appendix: 2048-step rollouts, one process, n_pi=32): 65,536 per auxiliary phase.

Door is continuous control, so the second is the applicable reference, and this
project's base constants (8 x 256, n_pi=32) already match it exactly. A host profile
that raises `num_envs` for throughput silently doubles the interval and moves the run
off that reference -- which is precisely what the V100 profile did until 2026-09-05.

This test pins the product across EVERY host profile, so the invariant survives a
future profile that changes num_envs or nstep for a good throughput reason without
noticing what it costs.
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ROOT / "datasphere" / "native" / "families.json"

# n_pi is PPG's own default and is not overridden by any launcher; assert that too,
# because the cadence below is only interpretable while it holds.
UPSTREAM_N_PI = 32
PUBLISHED_CONTINUOUS_CONTROL_CADENCE = 65_536


def _ppg():
    return json.loads(FAMILIES.read_text())["ppg"]


def _cadence(constants):
    return int(constants["num_envs"]) * int(constants["nstep"]) * UPSTREAM_N_PI


def test_ppg_upstream_n_pi_is_still_32():
    """If PPG's own n_pi default moves, every cadence number here is stale."""
    train = (ROOT / "runnable" / "ppg" / "phasic_policy_gradient" / "train.py").read_text()
    assert "n_pi=32," in train, (
        "PPG's upstream n_pi default is no longer 32; the auxiliary-phase cadence "
        "asserted by this file must be recomputed against the new value.")


def test_base_constants_match_the_published_continuous_control_cadence():
    constants = _ppg()["constants"]
    assert _cadence(constants) == PUBLISHED_CONTINUOUS_CONTROL_CADENCE, (
        f"ppg base constants give {_cadence(constants):,} interactions per auxiliary "
        f"phase, not the published continuous-control {PUBLISHED_CONTINUOUS_CONTROL_CADENCE:,}. "
        "Either restore the constants or record, in families.json, which reference the "
        "new cadence is measured against -- an undeclared cadence is the finding review 11 "
        "section 7 raised.")


@pytest.mark.parametrize("profile", sorted(_ppg().get("host_profiles", {})))
def test_every_host_profile_preserves_the_cadence(profile):
    ppg = _ppg()
    constants = dict(ppg["constants"])
    constants.update(ppg["host_profiles"][profile].get("constants", {}))
    cadence = _cadence(constants)
    assert cadence == PUBLISHED_CONTINUOUS_CONTROL_CADENCE, (
        f"host profile {profile!r} gives {cadence:,} interactions per PPG auxiliary "
        f"phase against the base {PUBLISHED_CONTINUOUS_CONTROL_CADENCE:,}. A profile may "
        "only change this deliberately: state the reference in a constants_reason and "
        "update this test in the same edit. Raising num_envs for throughput alone is the "
        "exact regression this test exists to catch.")
