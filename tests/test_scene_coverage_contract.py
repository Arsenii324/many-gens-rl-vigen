"""The evaluation-scene axis: what the protocol certifies vs what the runners actually do.

This is `docs/CONSTRUCTION.md` C45 made executable, and it is a **clone-facing** test — it
constrains the trees that produce reported numbers, not the superseded `rlgen/` port. That
distinction is the point of `scripts/test_inventory.py`, which shows most of this suite pointing
at the port rather than the clones. The exact share is deliberately not quoted here: adding this
file changed it, so any number written down would have been stale on arrival. Run the script.

## The gap, stated once

`Protocol` declares `eval_scene_ids = (0..9)` and `episodes_per_scene = 10`, so
`n_eval_episodes == 100`, and **those fields are inside `Protocol.hash()`** — the hash is this
project's definition of "two numbers are comparable iff this matches". RL-ViGen's own
`eval.py` really does sweep those ten scenes: every ten episodes it rebuilds the eval env with
an incremented `scene_id` (`eval.py:178-184`), which reproduces the supplemental's §D.1.1
protocol of "10 distinct scenes, 10 trials each, 100 trials in total".

`train.py` does not. It contains **no occurrence of the string `scene`** at all, so its in-loop
evaluation runs at `robo_make`'s default `scene_id=0` forever. Every number this project has
produced came through `train.py`.

So the protocol certifies a ten-scene average and the runs deliver one scene, and the hash
agrees with itself either way. That is a FALSE-CERTIFICATION in the register's sense: not a
wrong number, a number carrying a guarantee nothing enforced.

## Why these assertions are on source text

They pin *upstream* structure, which is the thing that silently changes under a re-clone —
exactly the drift `scripts/check_citations.py --content` was built to catch in prose. Reading
the source is the only way to state it without running robosuite, which this test must not do:
it has to stay fast and runnable on a machine with no MuJoCo.

The tests were written to fail if the gap was **closed** as well as if it widened, because a
closed gap must be accompanied by a protocol change, and a silent fix would leave every earlier
number incomparable to every later one with no record of when it changed.

**It closed for `train.py` on 2026-08-19 and they fired**, which is the whole reason they existed.
P14 gave that loop the scene axis and a train-regime denominator, and `Protocol.env_patches`
records it, so the hash separates pre- and post-P14 numbers.

**That is five baselines, not twelve**, and this file's assertions were briefly rewritten as
though it were all of them. `train.py` serves `drqv2`, `svea`, `sgqn`, `curl` and `drq`; the other
seven have their own loops and still evaluate one scene. The per-baseline count lives in
`scripts/audit_eval_axis.py` and is pinned by `tests/test_eval_axis_coverage.py`, because the
error that produced the premature close was exactly a claim with no per-baseline form.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "RL-ViGen-upstream"
sys.path.insert(0, str(ROOT))

pytestmark = pytest.mark.skipif(not UPSTREAM.exists(),
                                reason="RL-ViGen-upstream clone absent")


def src(rel: str) -> str:
    p = UPSTREAM / rel
    assert p.exists(), f"{rel} missing from the clone -- the tree is not what this pins"
    return p.read_text(errors="replace")


class TestWhatTheProtocolCertifies:
    def test_protocol_declares_a_ten_scene_hundred_episode_evaluation(self):
        from rlgen.protocol import Protocol
        p = Protocol()
        assert len(p.eval_scene_ids) == 10
        assert p.episodes_per_scene == 10
        assert p.n_eval_episodes == 100

    def test_the_scene_axis_is_inside_the_hash(self):
        """If it were outside, single-scene and ten-scene runs would hash alike and the
        comparability claim would be silently false rather than loudly unmet."""
        from rlgen.protocol import Protocol
        a = Protocol()
        b = Protocol(eval_scene_ids=(0,), episodes_per_scene=100)
        assert a.n_eval_episodes == b.n_eval_episodes == 100, "episode count held equal"
        assert a.hash() != b.hash(), (
            "a one-scene protocol must not hash equal to a ten-scene one; otherwise the hash "
            "certifies coverage it never checked")


class TestWhatUpstreamActuallyDoes:
    def test_their_offline_evaluator_sweeps_scenes(self):
        """`eval.py` is where RL-ViGen's published robosuite numbers come from."""
        t = src("eval.py")
        assert re.search(r"scene_id\s*=\s*count", t), (
            "eval.py no longer rebuilds the env with an incrementing scene_id -- the reference "
            "protocol this project compares against has changed shape")
        assert re.search(r"i\s*<\s*100\s+and\s+i\s*%\s*10\s*==\s*0", t), (
            "the 100-episode / 10-per-scene cadence is gone from eval.py")

    def test_their_training_loop_now_does_too_because_we_patched_it(self):
        """This assertion used to be `"scene" not in t`, and it fired on 2026-08-19 as designed.

        The gap it guarded is **closed**: P14 (C45 + C43) gave `train.py`'s evaluation the scene
        axis and a train-regime denominator. The old assertion was written to fail if the gap
        closed as well as if it widened, because a closed gap must be accompanied by a protocol
        change — and it was: `Protocol.env_patches` now carries P14, so pre- and post-P14 numbers
        hash differently.

        What it guards now is the reverse: that the sweep is not silently lost to a re-clone,
        which would return every number to single-scene without any status changing.
        """
        t = src("train.py")
        assert "_eval_regime" in t and "for scene_id in scene_ids:" in t, (
            "train.py's scene sweep is gone -- a re-clone probably reverted P14. Every number "
            "produced in that state is single-scene again, and C45 is no longer closed")

    def test_robo_make_defaults_to_scene_zero(self):
        """So "no scene argument" means "scene 0", not "a random scene"."""
        t = src("wrappers/robo_wrapper.py")
        assert re.search(r"def robo_make\([^)]*scene_id\s*=\s*0", t, re.S)

    def test_scene_id_is_a_real_axis_not_a_label(self):
        """It reaches the reset config, so scenes differ in what is rendered."""
        t = src("envs/robosuiteVGB/robosuitevgb/vgb_wrapper.py")
        assert re.search(r"get_custom_reset_config\(\s*task=task,\s*mode=mode,\s*scene_id=scene_id",
                         t, re.S), "scene_id no longer feeds the reset config"

    def test_scene_and_difficulty_are_separate_axes(self):
        """`mode` sets randomisation; `scene_id` sets texture. Conflating them would make the
        Easy/Medium/Hard mapping in C27 mean something different again."""
        t = src("envs/robosuiteVGB/robosuitevgb/utils.py")
        for regime in ("train", "eval-easy", "eval-medium", "eval-hard"):
            assert f"'{regime}'" in t, f"regime {regime} vanished from make_env"
        assert re.search(r"assert scene_id >= 0 and scene_id <= 9", t)


class TestTheCloneRunnersInheritTheGap:
    """Every clone that builds a robosuite env pins scene 0, so this is not one runner's bug."""

    CLONES = {
        "runnable/idaac/ppo_daac_idaac/envs.py": r"scene_id=0",
        "runnable/dmc_gb/src/env/wrappers.py": r"scene_id\s*=\s*0",
        # ibac_sni left this set on 2026-09-03 -- see the test below. It was the LAST clone
        # passing a literal; the two that remain pass a parameter whose default is 0, which this
        # pattern cannot tell apart from a constant and which `audit_eval_axis.py` calls
        # "threaded, never varied". Both are single-scene in practice, which is why C45 does not
        # move on the strength of any of this.
    }

    @pytest.mark.parametrize("rel,pat", list(CLONES.items()), ids=lambda v: str(v)[:28])
    def test_clone_hardcodes_scene_zero(self, rel, pat):
        p = ROOT / rel
        if not p.exists():
            pytest.skip(f"{rel} absent")
        assert re.search(pat, p.read_text(errors="replace")), (
            f"{rel} no longer pins scene 0. If it became configurable, C45 is partly closed for "
            "this baseline and the protocol must say so")


    def test_ibac_sni_is_now_env_configurable_and_still_never_swept(self):
        """C45's last literal, removed 2026-09-03 — and the distinction it forces.

        `ibac_sni_runtime.py` is OUR adapter: upstream `ibac_sni` is a MiniGrid/CoinRun repository with no
        robosuite in it at all, so `make_rlvigen_env` is authored by this project and widening it
        deviates from nobody. It now reads `RLVIGEN_SCENE_ID`, exactly as it already read
        `RLVIGEN_MODE` for the regime.

        **Both halves are asserted on purpose.** Configurable is a precondition for a sweep and is
        not a sweep; nothing in this tree moves the variable, so what has been *measured* is
        unchanged and `audit_eval_axis.py` still reports 5 of 12. A test that checked only the
        first half would let "reachable" be misread as "closed", which is the exact error C45's own
        2026-08-19 correction was written to prevent.
        """
        p = ROOT / "runnable/ibac_sni/torch_rl/ibac_sni_runtime.py"
        if not p.exists():
            pytest.skip("ibac_sni absent")
        t = p.read_text(errors="replace")
        assert "RLVIGEN_SCENE_ID" in t, "the scene axis regressed to a literal"
        assert not re.search(r"scene_id=0\b", t), "a literal 0 came back"
        # and nothing sweeps it: no caller in the tree sets the variable
        setters = [q for q in (ROOT / "runnable" / "ibac_sni").rglob("*.py")
                   if "RLVIGEN_SCENE_ID" in q.read_text(errors="replace") and q != p]
        assert not setters, (
            f"something now varies ibac_sni's scene: {setters}. If a driver was added, C45 is "
            "closer to closed for this baseline and the register must say so.")


def test_the_gap_is_declared_open_because_it_is_closed_for_only_five():
    """A known, unfixed gap must stay written down.

    Without this the failure mode is silent: someone closes C45 in code, the prose keeps saying
    "single-scene", and a later reader trusts whichever they happen to open. Equally, if the gap
    is fixed, this test fails and forces the register to be updated in the same change.
    """
    doc = (ROOT / "docs" / "CONSTRUCTION.md").read_text(errors="replace")
    m = re.search(r"^\|\s*\[C45\]\(#c45\)\s*\|[^|]*\|[^|]*\|\s*\*{0,2}([A-Z-]+)", doc, re.M)
    assert m, "C45 has vanished from the register summary table"
    assert m.group(1) == "OPEN", (
        f"C45 is marked {m.group(1)}. P14 closed it for the five upstream baselines only; the "
        "other seven still evaluate one scene, which `scripts/audit_eval_axis.py` reports per "
        "baseline. It was briefly marked RESOLVED on 2026-08-19 on the strength of a verification "
        "that covered five of twelve. If it is closed again, the audit must show twelve sweeping "
        "in the same commit")
