"""`OBSERVATION_GEOMETRY` must describe the runs, not a belief about them.

The table it pins was wrong when first written: `Protocol.DEFAULT_FRAME_STACK = 3` was applied to
all twelve baselines while four of them — the ones whose originals are Procgen — feed a single
RGB frame. The protocol hash therefore certified an observation shape four runs did not have,
and nothing caught it, because nothing connected the declaration to the launchers.

These tests make that connection, against the two artefacts that are actually version-controlled:

  - `runnable/_launch/<name>.sh`, which sets `RLVIGEN_IMAGE_SIZE`;
  - `runnable/_patches/<name>.patch`, the exported diff of each clone.

The clones themselves are ~200 MB each and are NOT in git, which is exactly why the patches are.

## What this cannot see

A patch says what changed, not what the unmodified file already did. So for frame stacking the
NEGATIVE claim — "this baseline does not stack" — is checked as "no seam in its patch introduces
a stack", which would miss a stack that upstream already had. That is checked separately, and
loudly, for the four Procgen baselines: their references are single-frame by construction
(Procgen serves one RGB frame), and if one of them ever grew a stack the positive assertion here
would still pass. Read `docs/PART2-METRIC-INVENTORY.md` §4 before trusting this file alone.
"""
from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAUNCH = ROOT / "runnable" / "_launch"
PATCHES = ROOT / "runnable" / "_patches"

from rlgen.protocol import OBSERVATION_GEOMETRY  # noqa: E402

#: Which launcher drives which baseline. Several baselines share one, which is the point of the
#: clone layout: dmc_gb carries rad and soda, rlvigen.sh carries all five of RL-ViGen's own.
LAUNCHER_OF = {
    "rad": "dmc_gb.sh", "soda": "dmc_gb.sh",
    "alda": "alda.sh", "ppg": "ppg.sh", "idaac": "idaac.sh",
    "ibac_sni": "ibac_sni.sh", "ctrl": "ctrl.sh",
    "drqv2": "rlvigen.sh", "svea": "rlvigen.sh", "sgqn": "rlvigen.sh",
    "curl": "rlvigen.sh", "drq": "rlvigen.sh",
}

#: Whose upstream is Procgen, which serves a single RGB frame -- and which of those STILL declares
#: single-frame. All four originate in Procgen; `idaac` is deliberately not in this set any more.
#: [Claude 2026-09-06, DECISION-SHEET A35] The authors' own DMC continuous-control recipe stacks 3
#: frames (`ext/idaac/raileanu21a-supp.pdf` SS E) and this project adopted it as idaac's declared
#: main config (Q55) once the frame-stack implementation gap closed (A65/C98) -- exactly the
#: "someone later adds a FrameStack ... must argue for it" case this file's own docstring names.
#: The argument is A35/`families.json`'s idaac `constants_note`; idaac now belongs with
#: `test_stacking_baselines_really_stack` below, not this set.
PROCGEN_ORIGINS = {"ppg", "ibac_sni", "ctrl"}


def test_every_baseline_has_a_declared_geometry():
    assert set(OBSERVATION_GEOMETRY) == set(LAUNCHER_OF), (
        "OBSERVATION_GEOMETRY and LAUNCHER_OF must cover the same twelve baselines; a baseline "
        "in one and not the other is a baseline whose observation shape nothing checks.")


@pytest.mark.parametrize("name", sorted(OBSERVATION_GEOMETRY))
def test_render_size_matches_its_launcher(name):
    """`RLVIGEN_IMAGE_SIZE` in the launcher is what the run actually renders at."""
    declared_size = OBSERVATION_GEOMETRY[name][0]
    launcher = LAUNCH / LAUNCHER_OF[name]
    if not launcher.exists():
        pytest.skip(f"{launcher.name} not written yet")
    text = launcher.read_text()
    m = re.search(r'RLVIGEN_IMAGE_SIZE="\$\{RLVIGEN_IMAGE_SIZE:-(\d+)\}"', text)
    if m is None:
        # rlvigen.sh deliberately leaves it unset: 84 is RL-ViGen's own robo_config.yaml default
        # and P6 is inert. Absence is the assertion, so it is checked as one rather than skipped.
        assert declared_size == 84, (
            f"{launcher.name} sets no RLVIGEN_IMAGE_SIZE, so the run renders at RL-ViGen's own "
            f"84, but OBSERVATION_GEOMETRY declares {declared_size} for {name}")
        assert "RLVIGEN_IMAGE_SIZE is left unset" in text or "unset here on purpose" in text, (
            f"{launcher.name} relies on an unset RLVIGEN_IMAGE_SIZE without saying so")
        return
    assert int(m.group(1)) == declared_size, (
        f"{launcher.name} renders at {m.group(1)} but OBSERVATION_GEOMETRY says {declared_size} "
        f"for {name} -- one of them is describing a run that does not happen")


@pytest.mark.parametrize("name", sorted(n for n in OBSERVATION_GEOMETRY
                                        if n in PROCGEN_ORIGINS))
def test_procgen_origin_baselines_are_declared_single_frame(name):
    """The 8/4 split is not a preference; it follows from the reference's own input.

    Procgen serves one RGB frame and these four encoders were built for one, so stacking would be
    a deviation in the clone. This pins the declaration to that reasoning: if someone later adds
    a FrameStack to one of these seams, they must change this table too and will have to argue
    for it.
    """
    assert OBSERVATION_GEOMETRY[name][1] == 1, (
        f"{name}'s reference is Procgen (single RGB frame); declaring a stack means a deviation "
        f"was added to its clone, which must be justified in docs/RUNNABLE-ORIGINALS.md")
    patch = PATCHES / f"{name}.patch"
    if patch.exists():
        body = "\n".join(l for l in patch.read_text().splitlines()
                         if l.startswith("+") and not l.startswith("+++"))
        assert "FrameStack" not in body, (
            f"{name}.patch introduces a FrameStack while OBSERVATION_GEOMETRY declares 1 frame")


@pytest.mark.parametrize("name", ["rad", "soda", "alda", "idaac"])
def test_stacking_baselines_really_stack(name):
    """The positive half. These four reach a FrameStack, and the patch is where to see it."""
    assert OBSERVATION_GEOMETRY[name][1] == 3
    patch = PATCHES / f"{'dmc_gb' if name in ('rad', 'soda') else name}.patch"
    if not patch.exists():
        pytest.skip(f"{patch.name} not exported yet -- run scripts/deviations.py --export")
    assert "FrameStack" in patch.read_text(), (
        f"{patch.name} shows no FrameStack, but {name} is declared as 3-frame stacked")


def test_the_split_is_still_nine_three():
    """A bare count, so a silent drift in either direction shows up as a number, not a story.

    [Claude 2026-09-06] Was 8/4 until idaac moved from single-frame to 3-stack (DECISION-SHEET
    A35, Q55) -- named here as the one deliberate exception, not a silent drift, exactly per this
    test's own stated purpose.
    """
    stacked = sorted(n for n, (_s, f) in OBSERVATION_GEOMETRY.items() if f == 3)
    single = sorted(n for n, (_s, f) in OBSERVATION_GEOMETRY.items() if f == 1)
    assert len(stacked) == 9 and len(single) == 3, (
        f"the frame-stack split moved: {len(stacked)} stacked {stacked}, "
        f"{len(single)} single {single}. That is a comparability change, not a refactor -- "
        "update docs/PART2-METRIC-INVENTORY.md Finding 5 in the same commit.")
    assert set(single) == PROCGEN_ORIGINS


class TestTheProtocolCarriesEachBaselineSGeometry:
    """C2's false-certification half, closed 2026-08-19.

    `OBSERVATION_GEOMETRY` recorded the truth from the start, and `Protocol` ignored it: both
    `image_size` and `frame_stack` are **inside the hash** and defaulted to (84, 3) for every
    baseline. So `Protocol(name="ppg")` certified an 84px 3-frame observation that ppg never sees
    — it renders at 64 and stacks one — and a ppg run hashed identically to a drqv2 run on the
    axis that is supposed to say whether two numbers are comparable.

    Same defect and same fix as `time_limit_handling` (C1). The map existed; only the wiring was
    missing.
    """

    def test_every_baseline_s_protocol_matches_the_map(self):
        from rlgen.protocol import Protocol
        bad = {n: ((Protocol(name=n).image_size, Protocol(name=n).frame_stack), g)
               for n, g in OBSERVATION_GEOMETRY.items()
               if (Protocol(name=n).image_size, Protocol(name=n).frame_stack) != g}
        assert not bad, f"protocol disagrees with the geometry it is supposed to certify: {bad}"

    def test_baselines_with_different_observations_do_not_hash_alike(self):
        from rlgen.protocol import Protocol
        assert Protocol(name="ppg").hash() != Protocol(name="drqv2").hash(), (
            "a 64px single-frame run and an 84px three-frame run must not carry the same "
            "comparability hash; that is the whole job of the observation block")

    def test_an_explicit_value_is_never_overwritten(self):
        from rlgen.protocol import Protocol
        assert Protocol(name="ppg", frame_stack=3).frame_stack == 3
        assert Protocol(name="ppg", image_size=84).image_size == 84

    def test_an_unknown_name_falls_back_to_the_documented_defaults(self):
        from rlgen.protocol import Protocol, DEFAULT_IMAGE_SIZE, DEFAULT_FRAME_STACK
        p = Protocol()
        assert (p.image_size, p.frame_stack) == (DEFAULT_IMAGE_SIZE, DEFAULT_FRAME_STACK)
        assert p.name not in OBSERVATION_GEOMETRY
