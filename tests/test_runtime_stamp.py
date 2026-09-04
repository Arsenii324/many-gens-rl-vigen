"""The protocol card must record the dependency versions the hash does not cover — C29.

`Protocol.hash()` printed *"two numbers are comparable iff this matches"* while omitting the
versions the run executes against. That is not a small omission: `mujoco` 3.x lacks
`MjModel.tex_rgb`, which RL-ViGen's texture modder reads, so on a 3.x platform the `eval-*`
regimes — **the entire manipulated variable** — cannot run, and only `train` is reachable. A
Kaggle run and a DataSphere run could therefore differ in what was executable at all and carry
identical hashes.

Closed here only in part, and deliberately: the card now records the versions and the hash no
longer claims sufficiency. **Whether to hash them is the open half of C29**, and its own entry
calls that a judgement about where to draw the boundary rather than a rule.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rlgen.protocol import VERSIONED_DEPENDENCIES, Protocol, runtime_versions  # noqa: E402


def test_every_declared_dependency_is_reported():
    v = runtime_versions()
    assert set(v) == set(VERSIONED_DEPENDENCIES)
    assert all(isinstance(x, str) and x for x in v.values())


def test_an_absent_package_is_named_not_raised():
    """A card must be writable on a machine missing a dependency; silence would be worse."""
    v = runtime_versions()
    assert all(x == "absent" or x[0].isdigit() for x in v.values()), v


def test_mujoco_is_covered_because_it_decides_what_runs():
    assert "mujoco" in VERSIONED_DEPENDENCIES, (
        "mujoco gates whether the eval-* regimes execute at all; omitting it is the specific "
        "case C29 is about")


def test_the_card_carries_the_runtime_block():
    c = Protocol(name="drqv2").card()
    assert "runtime:" in c and "mujoco:" in c


def test_the_card_no_longer_claims_the_hash_is_sufficient():
    c = Protocol(name="drqv2").card()
    assert "comparable iff this matches" not in c, (
        "the card claims the hash decides comparability again, while still not covering the "
        "dependency versions that can decide whether a regime runs")
    assert "NECESSARY, not sufficient" in c


def test_the_versions_are_not_in_the_hash_and_that_is_declared():
    """Pins the current state honestly: recording is done, hashing is C29's open judgement.

    If dependency versions are ever added to the hash, this test should fail and be rewritten in
    the same commit — that is a deliberate decision with a re-stamp cost, exactly like C1's.
    """
    import rlgen.protocol as P
    p = Protocol(name="drqv2")
    before = p.hash()
    real = P.runtime_versions
    try:
        P.runtime_versions = lambda: {k: "999.999" for k in VERSIONED_DEPENDENCIES}
        assert Protocol(name="drqv2").hash() == before, (
            "the hash moved when the dependency versions did -- they are now hashed. That is a "
            "deliberate decision with a re-stamp cost (C29 option 1 or 3); rewrite this test in "
            "the same commit that makes it")
        assert "999.999" in Protocol(name="drqv2").card(), (
            "the card stopped reporting the versions, which is the half that IS closed")
    finally:
        P.runtime_versions = real
