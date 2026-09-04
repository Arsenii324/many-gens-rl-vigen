"""The 3 / 9 time-limit split, pinned so the survey in `rlgen/protocol.py` cannot rot.

`Protocol.time_limit_handling` declares `"truncate_with_bootstrap"` and that string is inside
`hash()`. It is true of **three** baselines out of twelve. The docstring there carries the
per-clone survey; this file makes the survey executable, because a table in a comment is exactly
the kind of true-once statement this project keeps catching itself filing as permanent.

**Why it matters more than it looks.** Door and Lift have no early termination, so every episode
ends by time limit. A baseline that treats that as a terminal state zeroes the bootstrap on
*every* episode and biases its value targets downward throughout training. Three baselines do not
do this and nine do, so two groups' value targets mean different things underneath every number
either produces — and no `git diff` can show it, because nobody introduced it.

**The split is lineage, not accident.** The three correct ones are the SAC-family clones
descended from Yarats' dmcontrol code, which carried the fix. The nine others are the RL-ViGen
five plus the four Procgen-native algorithms — and those four are wrong *here* only because the
environment changed underneath them: in Procgen every episode genuinely is a termination, so
their authors were right for Procgen.

**What this file checks and what it cannot.** It asserts on SOURCE TEXT, not on behaviour: that
each clone still contains (or still lacks) the idiom the survey attributes to it. That is enough
to catch a clone being edited or replaced, which is the realistic way the survey goes stale. It
is NOT a proof that the bootstrap is or is not applied at runtime — for that you would have to
train, and a test that trains is not a test anyone runs. A clone missing from the checkout is
skipped by path, which is the one genuinely inapplicable case.
"""
from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# (label, path, must_contain, why) -- `must_contain` is the idiom the survey attributes to it.
BOOTSTRAPS = [
    ("rad/soda (dmc_gb)", "runnable/dmc_gb/src/train.py", "_max_episode_steps",
     "done_bool = 0 if episode_step + 1 == env._max_episode_steps else float(done)"),
    ("alda", "runnable/alda/trainers/alda_trainer.py", "_max_episode_steps",
     "the identical idiom against self.env.env._max_episode_steps"),
]

ZEROES = [
    ("RL-ViGen five", "RL-ViGen-upstream/wrappers/robo_wrapper.py", "discount = 0.0",
     "Gym2DMC.step sets discount 0 on any done, with no termination/truncation branch"),
    ("ctrl", "runnable/ctrl/buffer.py", "(1 - done[t])",
     "the GAE recursion masks by done"),
    ("idaac", "runnable/idaac/ppo_daac_idaac/storage.py", "self.masks[step",
     "GAE masked by masks[step + 1]"),
    ("ppg", "runnable/ppg/phasic_policy_gradient/ppo.py", "1.0 - first[",
     "notlast = 1.0 - first[:, t + 1]"),
]


def _read(rel: str) -> str:
    p = ROOT / rel
    if not p.exists():
        pytest.skip(f"{rel} absent from this checkout (clones are ~200 MB and not in git)")
    return p.read_text(encoding="utf-8", errors="replace")


@pytest.mark.parametrize("label,rel,needle,why", BOOTSTRAPS,
                         ids=[b[0].replace("/", "-") for b in BOOTSTRAPS])
def test_the_three_that_bootstrap_still_do(label, rel, needle, why):
    """These three treat the horizon as a truncation, which is correct for Door and Lift."""
    assert needle in _read(rel), (
        f"{label} no longer contains {needle!r} in {rel}. The survey in rlgen/protocol.py says "
        f"it bootstraps through the time limit ({why}). Either the clone changed or the survey "
        "was wrong -- resolve it there, do not delete this test.")


@pytest.mark.parametrize("label,rel,needle,why", ZEROES,
                         ids=[z[0].replace(" ", "-") for z in ZEROES])
def test_the_nine_that_do_not_still_do_not(label, rel, needle, why):
    """These treat every episode end as terminal. On Door and Lift that is every episode."""
    assert needle in _read(rel), (
        f"{label} no longer contains {needle!r} in {rel}. The survey in rlgen/protocol.py says "
        f"it zeroes the bootstrap at the horizon ({why}). If this was fixed deliberately, the "
        "split is no longer 3/9 and BOTH the survey and Protocol.time_limit_handling need "
        "revisiting -- that field is hashed.")


def test_the_protocol_no_longer_declares_one_convention_for_twelve():
    """This was a tripwire and it fired on 2026-08-19, which is what it was for.

    It used to assert that the field still read `"truncate_with_bootstrap"`, so that re-valuing it
    could not happen by accident: the field is inside `hash()`, so a change invalidates every
    recorded protocol hash. The change was made deliberately, with the re-stamp bundled into the
    one P14 had already forced that day, and the entry recording it is C1.

    What it guards now is the reverse: that the blanket value does not come back.
    """
    src = (ROOT / "rlgen" / "protocol.py").read_text(encoding="utf-8")
    assert 'time_limit_handling: str = "truncate_with_bootstrap"' not in src, (
        "the blanket value is back. It is inside hash(), so it would again certify a convention "
        "nine of twelve baselines do not have, and two runs differing in it would hash alike")
    assert 'time_limit_handling: str = "per-baseline"' in src
    assert "TIME_LIMIT_HANDLING = {" in src, (
        "the per-baseline map is gone; without it the sentinel is never filled and the hash stops "
        "distinguishing the conventions again")
    assert "TRUE OF THREE BASELINES OUT OF TWELVE" in src, (
        "the annotation recording that this field once asserted the opposite of what nine "
        "baselines do, from inside the hash, was deleted. The history is the point")
