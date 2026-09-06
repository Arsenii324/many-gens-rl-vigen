"""How many baselines actually sweep evaluation scenes — pinned per baseline, not in aggregate.

This test exists because of a specific error on 2026-08-19. P14 gave `RL-ViGen-upstream/train.py`
a ten-scene sweep, it was verified on a live `drqv2` run, and C45 and C43 were marked RESOLVED the
same hour. P14 serves **five** baselines. The other seven have their own training loops and were
untouched.

The verification was real; the generalisation was not. The claim "we evaluate ten scenes" had no
per-baseline form, so one baseline's evidence licensed a sentence about twelve. A test that
asserted "the sweep exists" would have passed throughout and caught nothing — which is why this
one counts rows instead.
"""
from __future__ import annotations

import functools
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import audit_eval_axis as A  # noqa: E402

pytestmark = pytest.mark.skipif(not (ROOT / "RL-ViGen-upstream").exists(),
                                reason="RL-ViGen-upstream clone absent")

UPSTREAM = {"drqv2", "svea", "sgqn", "curl", "drq"}


@functools.lru_cache(maxsize=1)
def rows():
    return {r["baseline"]: r for r in (A.audit_one(n) for n in A.TREES)}


def test_the_audit_covers_exactly_the_twelve():
    from rlgen.registry import BASELINES
    real = {n for n, s in BASELINES.items()
            if s.status == "implemented" and n != "random" and not n.startswith("__")}
    assert set(A.TREES) == real


def test_only_the_upstream_five_sweep_scenes():
    """The load-bearing count. If P14's equivalent reaches another clone, this fails and the
    register must say so in the same commit -- which is the whole point."""
    swept = {b for b, r in rows().items() if r["sweeps"]}
    assert swept >= UPSTREAM, f"an upstream baseline stopped sweeping: {UPSTREAM - swept}"
    extra = swept - UPSTREAM
    assert not extra, (
        f"{sorted(extra)} now appear to sweep scenes. If that is real, C45 covers more than five "
        "baselines and its entry must be updated in this commit; if it is the audit being fooled "
        "by a threaded parameter nothing varies, the audit needs tightening")


def test_no_family_pins_the_scene_by_a_literal_any_more():
    """Was: "the pinned ones are pinned by a literal", asserting `ibac_sni` still was.

    `ibac_sni` stopped being on 2026-09-03 — it reads `RLVIGEN_SCENE_ID` now — and it was the last
    one. **The count of what actually gets measured did not change**, which is the whole reason
    this test is rewritten rather than deleted: `audit_eval_axis.py` still reports five sweepers,
    because a threaded parameter nothing moves is single-scene exactly as a literal is. Keeping the
    invariant that matters (five) beside the fact that changed (no literals) is what stops
    "reachable" from being read as "closed"."""
    r = rows()
    assert not r["ibac_sni"]["scene_pinned"], "ibac_sni pins a literal again"
    assert not r["ibac_sni"]["sweeps"], "ibac_sni now sweeps -- C45 must be updated"
    assert sum(1 for v in r.values() if v["sweeps"]) == 5, (
        "the number of baselines that actually vary the scene changed; C45 and "
        "docs/CONSTRUCTION.md must be updated in the same change")


def test_idaacs_scene_id_is_a_parameter_of_OUR_adapter_defaulting_to_zero():
    """C45's verdict for `idaac` was "pins a literal 0". That is now "defaults to 0", and the
    distinction matters in exactly one direction.

    `make_rlvigen_venv` is **ours** -- 63 of the 64 lines in `ppo_daac_idaac/envs.py` are authored
    by this project over PRISTINE -- so widening it is not a deviation from idaac's authors. It now
    takes `scene_id=0`, which leaves every training and in-loop-evaluation call byte-identical and
    lets the OFFLINE grid sweep scenes without touching idaac's own code. That is the route C43
    and C45 chose over seven clone deviations, and this is the first family it is exercised on.

    What has NOT changed, and this test pins it: nothing inside idaac passes a non-zero scene.
    """
    envs = (ROOT / "runnable" / "idaac" / "ppo_daac_idaac" / "envs.py").read_text()
    # frame_stack=None added 2026-09-06 (DECISION-SHEET A35, IDAAC-C2); unrelated to scene_id and
    # keeps every existing call byte-identical (defaults to getattr(args, "frame_stack", 1)).
    assert ("def make_rlvigen_venv(args, device, mode, num_envs, scene_id=0, "
            "frame_stack=None):") in envs
    assert "scene_id=scene_id" in envs, "the parameter must reach robo_make"
    callers = [line for line in envs.splitlines() if "make_rlvigen_venv(" in line
               and "def " not in line]
    for line in callers:
        assert "scene_id" not in line, (
            f"a caller inside idaac now passes a scene: {line.strip()!r}. C45's finding is that "
            "idaac evaluates one scene; only the offline grid may vary it.")


def test_no_non_upstream_tree_varies_scene_id_anywhere():
    """Stronger than the call-site audit: nothing in those trees moves a scene at all."""
    import re
    for tree in {A.TREES[b] for b in A.TREES if b not in UPSTREAM}:
        txt = "\n".join(f.read_text(errors="replace")
                        for f in (ROOT / tree).rglob("*.py")
                        if "__pycache__" not in str(f))
        assert not re.search(r"for\s+\w*scene\w*\s+in|scene_ids\s*=", txt), (
            f"{tree} appears to iterate scenes now; C45's five-of-twelve statement is stale")
