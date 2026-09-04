"""Every baseline's x-axis is env frames, and that holds only while action repeat is 1 everywhere.

`PART2-METRIC-INVENTORY.md` §2 establishes that all twelve plot against env frames, so numbers can
share an axis — but only *given* `action_repeat = 1`. Change it anywhere and that baseline's frames
stop meaning what the others' frames mean.

The invariant is held three different ways, which is why one check cannot cover it:

  explicit flag    `rlvigen.sh` (`action_repeat=1`), `dmc_gb.sh` (`--action_repeat 1`)
  config file      `alda`, in `specs/train_alda_robosuite_door.yaml`
  absence          `ppg`, `idaac`, `ibac_sni`, `ctrl` — no repeat exists in the stack at all

Two reasons this is worth pinning rather than trusting.

**It has already been wrong once.** §2 Finding 3: RL-ViGen's `cfgs/config.yaml` sets
`action_repeat: 2` and no robosuite task file overrides it, so the five ran at 2 while the other
seven ran at 1 — same wall of frames, half the policy decisions, an x-axis off by a factor of two,
against RL-ViGen's own Supplementary Table 2. Fixed in the launcher, not upstream, so the wrong
default is still one flag away.

**For two baselines the config is a label, not a control.** `alda` and `dmc_gb` are
[C13]'s dead seams — both return before the `frame_skip=` call, so the knob is inert. They pass 1,
which is what it would have set, so nothing is wrong today. But `alda`'s robosuite spec sits beside
`train_alda_finger_spin.yaml` (2) and `train_alda_cartpole_balance.yaml` (4): a spec copied from a
neighbour would *declare* a repeat the env silently ignores, and the x-axis label would be wrong
while the run was right. That is the harder failure to see, because the number is fine.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Baselines with no action-repeat mechanism at all. Absence IS the guarantee for these, so the
# assertion is that it stays absent.
NO_REPEAT = ["ppg", "idaac", "ibac_sni", "ctrl"]


def read(rel: str) -> str:
    """Source with comment lines removed.

    Not cosmetic. `rlvigen.sh` carries a comment reading "action_repeat=1 is NOT a preference, it
    is this project's declared protocol" — which satisfies a naive search for `action_repeat=1`
    even when the command below it passes 2. The first version of this file passed that mutation:
    the assertion was matching the explanation of the rule instead of the rule.
    """
    p = ROOT / rel
    if not p.exists():
        pytest.skip(f"{rel} absent")
    return "\n".join(l for l in p.read_text(errors="replace").splitlines()
                      if not l.strip().startswith("#"))


def test_the_protocol_declares_one():
    from rlgen.protocol import DEFAULT_ACTION_REPEAT, Protocol
    assert DEFAULT_ACTION_REPEAT == 1
    assert Protocol().action_repeat == 1


def test_rlvigen_launcher_overrides_upstreams_default_of_two():
    """The one place the knob is live and upstream's default is wrong."""
    t = read("runnable/_launch/rlvigen.sh")
    assert re.search(r"action_repeat=1\b", t), (
        "rlvigen.sh no longer passes action_repeat=1. Upstream's cfgs/config.yaml sets 2 and no "
        "robosuite task file overrides it, so dropping this override silently halves the policy "
        "decisions behind every frame for five of the twelve (PART2 §2 Finding 3).")


def test_dmc_gb_launcher_passes_one():
    assert re.search(r"--action_repeat\s+1\b", read("runnable/_launch/dmc_gb.sh"))


def test_alda_robosuite_spec_is_one_and_its_siblings_are_not():
    """Pinned together, because the risk is a spec copied from the wrong sibling."""
    spec = read("runnable/alda/specs/train_alda_robosuite_door.yaml")
    assert re.search(r"action_repeat:\s*1\b", spec), (
        "alda's robosuite spec no longer sets action_repeat: 1 -- and alda is a C13 dead seam, so "
        "the env will run at 1 regardless while the config claims otherwise")
    others = [p for p in (ROOT / "runnable/alda/specs").glob("*.yaml")
              if "robosuite" not in p.name]
    if others:
        vals = {m for p in others for m in re.findall(r"action_repeat:\s*(\d+)", p.read_text())}
        assert vals - {"1"}, (
            "the sibling specs no longer differ from 1, so the copy-the-wrong-neighbour risk this "
            "test describes has gone -- update the docstring rather than leaving it stale")


@pytest.mark.parametrize("baseline", NO_REPEAT)
def test_baselines_without_a_repeat_mechanism_still_have_none(baseline):
    """For these four the x-axis is frames because nothing can rescale it. Adding a repeat later
    would break the shared axis silently, since their logs would keep the same column name."""
    hits = []
    for pat in ("*.py", "*.yaml", "*.sh"):
        for p in (ROOT / "runnable" / baseline).rglob(pat):
            for n, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                if re.search(r"\b(action_repeat|frame_skip)\b", line) and not line.strip().startswith("#"):
                    hits.append(f"{p.relative_to(ROOT)}:{n}")
    assert not hits, (
        f"{baseline} gained an action-repeat mechanism: {hits[:4]}. Its x-axis was env frames "
        "because nothing could rescale it; that is no longer true, and PART2 §2 needs revisiting.")


def test_every_archived_grid_was_measured_at_action_repeat_1():
    """No grid on disk may record `action_repeat` other than 1.

    Not hygiene — this catches a live footgun. Every RL-ViGen config ships `action_repeat: 2`
    (`cfgs/config.yaml:10`, `drq_config.yaml:9`, `svea_config.yaml:9`, `sgqn_config.yaml:9`,
    `curl_config.yaml:9`), and `cfgs/task/*.yaml` overrides it nowhere. The five native baselines
    run at 1 *only* because `runnable/_launch/rlvigen.sh:77` contradicts that default on every
    launch. A bare `python train.py`, a notebook, or a remote job assembled from the upstream
    README silently runs at 2.

    What that changes is **agent decisions per episode (500 -> 250) and gradient updates per frame
    budget** — not environment steps and not the shaping ceiling. `train.py:135` defines
    `global_frame = global_step * action_repeat` and `wrappers/dmc.py:44-52` accumulates reward
    across repeats, so env steps per frame and C62's 250 are invariant. (An earlier version of this
    docstring said "halving the environment steps behind each frame", which was wrong.) The logged
    `episode_length` reads 500.0 at either value, so it cannot detect the difference either.

    Nothing else would notice: `protocol.py:140` declares `DEFAULT_ACTION_REPEAT = 1` but the
    runners never consult it, and a grid records whatever the run used rather than checking it.
    This is the check that closes that gap, at the point where a wrong value would otherwise enter
    a reported number.

    See `docs/INTEGRATION-DELTA.md`'s action-repeat audit: all twelve baselines run at 1, but only
    seven do so by anyone's decision.
    """
    import json
    grids = sorted((ROOT / "results" / "regime-retention").glob("*.json"))
    if not grids:
        pytest.skip("no grids on disk")
    wrong = []
    for g in grids:
        ar = json.loads(g.read_text(encoding="utf-8")).get("action_repeat")
        if ar != 1:
            wrong.append(f"{g.name}: action_repeat={ar!r}")
    assert not wrong, (
        "grids not measured at action_repeat=1: " + "; ".join(wrong) +
        ". Upstream's configs default to 2, so this is what a run launched outside "
        "`_launch/rlvigen.sh` looks like. The number is not comparable with the others.")
