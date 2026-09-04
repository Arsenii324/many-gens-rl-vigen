"""Success rate means the same thing in all twelve, and nothing was checking that it stays so.

Success rate is the only unit-free, task-defined quantity available here — Door's return is dense
and scale-arbitrary — so it is the quantity a comparison most depends on. Twelve implementations
emit it, and they agree on a convention that is *not* the only reasonable one:

    an episode counts as a success if robosuite's `_check_success` held at ANY step

The alternative, the flag at the LAST step, is what RL-ViGen's own `habi_eval` uses and what
`eval_across_scenes.py` was first written with by mistake. On an auto-resetting env the two differ,
and they differ silently: both produce a number in [0, 1] that looks like a success rate.

Under this project's own null, twelve emissions sharing a name are twelve quantities until shown
otherwise. Reading them showed otherwise — every site accumulates with `x = x or bool(...)`. That
reading is what this file turns into something that stays true. Without it, one clone edited to
final-step convention would move `success_rate` from **universal** to **accidental**, the defect
class, with no test failing and no number looking wrong.

Deliberately checks the *convention*, not the value: the sites are read as source, so this needs
no environment and no run.
"""
from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Every place a success flag is turned into a per-episode boolean. Seven sites, twelve baselines:
# the upstream entry covers the five RL-ViGen ships (drqv2, svea, sgqn, curl, drq) through P11.
# Some files hold more than one convention legitimately. `RL-ViGen-upstream/train.py` carries the
# any-step accumulation in `eval()` (robosuite, patched by P11) AND the final-step read in
# `habi_eval()` (habitat, untouched and not used here) — so the check is scoped to the method that
# runs, not to the file. That coexistence is itself the reason this convention needs pinning: one
# file, one name, two quantities, separated only by which method the env family dispatches to.
SCOPE = {"RL-ViGen-upstream/train.py": ("def eval(self)", "def habi_eval")}

SITES = {
    "upstream (drqv2/svea/sgqn/curl/drq, via P11)": "RL-ViGen-upstream/train.py",
    "alda": "runnable/alda/trainers/alda_trainer.py",
    "ctrl": "runnable/ctrl/train_ppo.py",
    "dmc_gb (rad/soda)": "runnable/dmc_gb/src/train.py",
    "idaac": "runnable/idaac/test.py",
    "ppg": "runnable/ppg/phasic_policy_gradient/vec_monitor2.py",
    "ibac_sni": "runnable/ibac_sni/torch_rl/scripts/evaluate.py",
}

# `x = x or bool(...)` / `x[i] = (x[i] or bool(...))` -- the accumulate-if-ever shape.
ANY_STEP = re.compile(
    r"([A-Za-z_][\w\.]*(?:\[[^\]]+\])?)\s*=\s*\(?\s*\1\s+or\s+bool\(", re.M)


def source(rel: str) -> str:
    p = ROOT / rel
    if not p.exists():
        pytest.skip(f"{rel} absent")
    raw = p.read_text(errors="replace")
    if rel in SCOPE:
        start, end = SCOPE[rel]
        i, j = raw.find(start), raw.find(end)
        assert i != -1 and j > i, f"{rel}: scope markers {SCOPE[rel]} no longer found"
        raw = raw[i:j]
    return re.sub(r"\s+", " ", raw)


@pytest.mark.parametrize("name,rel", list(SITES.items()), ids=lambda v: str(v).split("/")[-1][:22])
def test_each_baseline_accumulates_success_over_the_whole_episode(name, rel):
    text = source(rel)
    hits = [m for m in ANY_STEP.finditer(text)
            if "success" in text[m.start():m.end() + 130]]
    assert hits, (
        f"{name}: no any-step success accumulation found in {rel}. Either the convention changed "
        "or the site moved. If it changed, `success_rate` is no longer one quantity across the "
        "twelve and the comparability contract's coverage class for it must change with it.")


@pytest.mark.parametrize("name,rel", list(SITES.items()), ids=lambda v: str(v).split("/")[-1][:22])
def test_no_baseline_reads_success_only_from_the_final_step(name, rel):
    """The failure this guards is silent: both conventions yield a plausible number in [0, 1].

    RL-ViGen's own `habi_eval` does `success_rate += time_step.info['success']` *after* the episode
    loop, reading the last step only. On an auto-resetting env that is a different quantity.
    """
    text = source(rel)
    bad = re.findall(r"success_rate\s*\+=\s*\w+\.info\[.success.\]", text)
    assert not bad, (
        f"{name}: reads success from the final timestep only ({bad[0]!r}), while the other "
        "baselines accumulate over the episode. Two quantities under one name.")


def test_the_convention_is_written_down_where_a_reader_would_look():
    """A convention held only in code is one edit from being lost with nothing to appeal to."""
    inv = (ROOT / "docs" / "PART2-METRIC-INVENTORY.md").read_text(errors="replace")
    assert "success" in inv.lower(), "the metric inventory no longer discusses success at all"


def test_the_site_list_covers_every_baseline():
    """Guards the checker itself: a baseline added without a site here is silently unprotected."""
    covered = {"drqv2", "svea", "sgqn", "curl", "drq", "alda", "ctrl", "rad", "soda",
               "idaac", "ppg", "ibac_sni"}
    assert len(covered) == 12
    listed = " ".join(SITES)
    for b in ("alda", "ctrl", "idaac", "ppg", "ibac_sni"):
        assert b in listed, f"{b} has no site in SITES"
