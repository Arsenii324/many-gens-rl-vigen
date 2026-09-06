"""check-budget's rollout-quantum floor must track the RESOLVED profile, not the base descriptor.

External review 14 section 13: idaac's `min_frames` was stored as a static 1024 (base
`num_processes=4 x num_steps=256`). The V100 profile raises `num_processes` to 16, so one full
rollout there is 4096 frames -- but the stale static floor let a canary at, say, 2000 frames pass
`check-budget` while completing ZERO rollouts (`frames // num_steps // num_processes == 0`),
training nothing and proving nothing about the profile it claims to validate. The same shape
affects `ibac_sni` (`procs x frames_per_proc`). This is a canary-validity defect, not a production
defect (a real 600k run clears every floor easily) -- which is exactly why it is dangerous: nothing
about a 600k run would ever exercise it.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FAMILY_TOOL = ROOT / "datasphere" / "native" / "family.py"


def _check_budget(cells: str, frames: int, profile: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["NATIVE_HOST_PROFILE"] = profile
    return subprocess.run(
        [sys.executable, str(FAMILY_TOOL), "check-budget", "--cells", cells, "--frames", str(frames)],
        cwd=ROOT, capture_output=True, text=True, env=env)


@pytest.mark.parametrize("family,base_floor,v100_floor", [
    # [Claude 2026-09-06] idaac removed: DECISION-SHEET A35's IDAAC-C2 transition removed its
    # v100-only `num_processes` override (16->1, now fidelity-fixed everywhere, not a per-host
    # throughput knob), so idaac no longer has a profile-dependent floor to test here at all --
    # both profiles now resolve the same 1x2048=2048 quantum. See
    # `test_the_base_datasphere_profile_floor_is_unchanged` for its single, profile-independent
    # floor.
    ("ibac_sni", 128, 2048),    # 1x128 base vs 16x128 v100
])
def test_the_stale_static_floor_used_to_pass_a_zero_rollout_v100_canary(family, base_floor, v100_floor):
    """Non-vacuity: prove the OLD bug shape really would have passed, so the fix is proven live."""
    below_v100_floor = v100_floor - 1
    assert below_v100_floor >= base_floor, "test premise: the stale base floor must be too low"
    result = _check_budget(family, below_v100_floor, "v100")
    assert result.returncode != 0, (
        f"{family} at {below_v100_floor} frames on the v100 profile must be REJECTED -- it "
        f"completes zero rollouts at that profile's process count, and the base-profile floor "
        f"({base_floor}) is not the right floor here")
    assert str(v100_floor) in result.stderr or str(v100_floor) in result.stdout, (
        "the rejection message should name the correct v100-resolved floor")


@pytest.mark.parametrize("family,v100_floor", [("ibac_sni", 2048)])
def test_the_v100_resolved_floor_itself_is_accepted(family, v100_floor):
    result = _check_budget(family, v100_floor, "v100")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("family,base_floor", [("idaac", 2048), ("ibac_sni", 128)])
def test_the_base_datasphere_profile_floor_is_unchanged(family, base_floor):
    """The fix must not raise the floor for the profile it was always correct for.

    [Claude 2026-09-06] idaac's floor moved 1024->2048 (DECISION-SHEET A35's IDAAC-C2: 1x2048, was
    4x256) -- a real change to the floor value, not a regression: it is still exactly one rollout
    on the base profile.
    """
    result = _check_budget(family, base_floor, "datasphere")
    assert result.returncode == 0, (
        f"the datasphere-profile floor for {family} regressed: {result.stderr}")


def test_idaacs_floor_is_now_profile_independent():
    """idaac no longer has a v100-specific floor at all (its `num_processes` override was removed,
    DECISION-SHEET A35): both profiles must resolve the identical 1x2048=2048 quantum."""
    result = _check_budget("idaac", 2048, "v100")
    assert result.returncode == 0, result.stderr
    result = _check_budget("idaac", 2047, "v100")
    assert result.returncode != 0, "2047 is below one rollout on either profile now"


def test_a_family_with_no_rollout_quantum_dependency_is_unaffected():
    """rlvigen's floor is about warmup (num_seed_frames), not process count; profile must not
    change it, proving the fix is scoped to the two families that actually need it."""
    result = _check_budget("drqv2", 4001, "v100")
    assert result.returncode == 0, result.stderr
    result = _check_budget("drqv2", 3999, "v100")
    assert result.returncode != 0
