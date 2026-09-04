"""Red-green for `scripts/audit_seed_control.py`, plus the tree verdicts it produced.

Every false negative pinned here was real. The first version of the audit reported
`AGENT_ONLY` for upstream, `DECLARED_NEVER_CONSUMED` for alda and `NO_KNOB` for ctrl -- three
wrong verdicts on nine baselines -- and each was found by reading the source, not by running the
checker. The checker was then changed until it reproduced what reading established. These tests
exist so those three defects cannot come back silently, because all three failed in the same
direction: **understating** seed control, which is the direction that would have made this
project report a defect it does not have.

The house rule (`CLAUDE.md`, from `docs/rl-experiment-runbook.md` 7b) is that a checker needs an
input that makes it red. Each `test_would_have_missed_*` below is that input.
"""
from __future__ import annotations

import functools
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_seed_control as A  # noqa: E402

#: `A.audit(name)` reads a fixed tree under ROOT and is pure for the duration of one test session.
#: `TestTheTreesAsTheyStand` calls it on overlapping trees from three different tests; cache it so
#: the repo-wide source scan runs once per tree instead of once per (test, tree) pair. Scoped to
#: this module only -- the synthetic-tree classes above call `A.seeding_sites`/`A.verdict`/
#: `A.declarations` directly, never `A.audit`, so they are unaffected.
_audit = functools.lru_cache(maxsize=None)(A.audit)


def tree(tmp_path: pathlib.Path, **files) -> pathlib.Path:
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return tmp_path


class TestTheDistinctionThatCarriesTheFinding:
    """A seeding CALL proves nothing; the ARGUMENT is the whole question."""

    def test_a_constant_seed_is_not_seed_control(self, tmp_path):
        root = tree(tmp_path, **{"t.py": "import torch\ntorch.manual_seed(0)\n"})
        sites = A.seeding_sites([root / "t.py"])
        assert len(sites) == 1 and sites[0]["seed_derived"] is False
        v, _ = A.verdict([{"kind": "argparse", "default": "0"}], sites)
        assert v == "DECLARED_CONSTANT_ONLY", (
            "a tree that calls manual_seed(0) has a knob that turns nothing; if this ever reads "
            "as controlled, the audit is counting calls instead of reading values")

    def test_a_seed_derived_argument_is(self, tmp_path):
        root = tree(tmp_path, **{"t.py": "import torch\ntorch.manual_seed(args.seed)\n"})
        assert A.seeding_sites([root / "t.py"])[0]["seed_derived"] is True


class TestFalseNegativesThatActuallyHappened:
    def test_would_have_missed_env_seeding_via_constructor_kwarg(self, tmp_path):
        """Upstream/idaac/dmc_gb seed envs as `robo_make(..., seed=cfg.seed)`, never `.seed()`.

        Looking only at call names reported AGENT_ONLY for all three.
        """
        root = tree(tmp_path, **{"t.py": "e = robo_make(name=t, seed=cfg.seed)\n"})
        sites = A.seeding_sites([root / "t.py"])
        assert sites, "a seed passed to an env constructor is env seeding and must be seen"
        assert sites[0]["side"] == "env" and sites[0]["seed_derived"]

    def test_would_have_missed_an_absl_declared_seed(self, tmp_path):
        """ctrl declares with `flags.DEFINE_integer('seed', 1, ...)`, not argparse."""
        root = tree(tmp_path, **{"t.py": 'flags.DEFINE_integer("seed", 1, "Random seed.")\n'})
        d = A.declarations(root, [root / "t.py"])
        assert [x for x in d if x["kind"] == "absl"], (
            "absl is a third declaration mechanism; missing it reported ctrl as having no knob")

    def test_would_have_missed_a_dynamically_imported_live_path(self):
        """ALDA is reached by `importlib.import_module(spec['module'])`.

        No AST walk finds that, so `TREES` declares the extra directory. If the declaration is
        dropped, alda silently reads as unseeded again.
        """
        assert A.TREES["alda"][3] == ["trainers"], (
            "alda's live path is dynamic; without the declared extra dir its seeding is invisible")


@pytest.mark.skipif(not (ROOT / "runnable" / "ppg").exists(), reason="ppg clone absent")
class TestTheTreesAsTheyStand:
    def test_twelve_of_twelve_are_seed_controlled(self):
        """Was eleven. `ppg` gained a seed knob on 2026-09-02 -- see C20's correction.

        The count is asserted rather than the set, because the failure this guards is a baseline
        quietly LOSING seed control, and that shows up as a count before it shows up anywhere else.
        """
        results = {r["tree"]: r for r in (_audit(n) for n in A.TREES)}
        controlled = [b for r in results.values() if r["verdict"] == "SEED_CONTROLLED"
                      for b in r["baselines"]]
        assert len(controlled) == 12, f"expected 12, got {len(controlled)}: {sorted(controlled)}"

    def test_ppgs_seed_knob_is_ours_and_stays(self):
        """The tripwire, now pointing the other way.

        C20 recorded ppg as the one baseline with no seed knob at all -- the TorchRL failure in
        this repo, and the reason ppg could not contribute a multi-seed row. That is no longer
        true, and it is not true because upstream changed: `runnable/ppg/phasic_policy_gradient/
        train.py` is OURS at this point, exposing `--seed` and seeding random, numpy and torch
        before `get_venv` receives it. So the direction worth guarding reversed. If this reverts,
        ppg's three seeds silently become three runs of the same unseeded configuration, which
        looks like a seed set and is not one.
        """
        r = _audit("ppg")
        assert r["verdict"] == "SEED_CONTROLLED", (
            f"ppg now reads {r['verdict']}. C20's correction says it is seed-controlled by our "
            "construction; if that was reverted, C20 and the register must say so in the same "
            "commit")
        assert any(d["kind"] in ("argparse", "absl") for d in r["decls"]), (
            "ppg's trainer no longer declares a seed flag")

    def test_default_seeds_disagree_across_trees(self):
        """Not a defect, but it means "the default run" is a different run per baseline, so a
        5-seed plan has to name its seeds rather than inherit them."""
        defaults = set()
        for n in A.TREES:
            for d in _audit(n)["decls"]:
                defaults.add(str(d["default"]))
        assert len(defaults) > 1, (
            "if every tree ever agrees on one default seed this test should be deleted, not "
            "weakened -- but until then the disagreement is the thing to remember")
