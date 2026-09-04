"""The structural guarantees behind "evaluation is identical across baselines".

The supervisor's requirement is a property of the CODE, so it is tested as one. Each test here
corresponds to a way the requirement failed in a real repo:

  * three eval paths coexisting          -> test_exactly_one_eval_stepping_loop
  * an evaluator that can branch on algo  -> test_evaluate_cannot_see_the_algorithm
  * per-baseline tag literals             -> test_no_tag_literals_outside_tags_module
  * one baseline evaluating, another not  -> test_every_runnable_baseline_emits_the_required_tags
  * episode count drifting per entry point -> test_episode_count_comes_only_from_the_protocol
"""
from __future__ import annotations

import ast
import inspect
import os
import re

import numpy as np
import pytest

from rlgen import evaluate as ev
from rlgen import tags
from rlgen.envs import EnvSpec, make_env
from rlgen.protocol import Protocol

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: First-party source. Vendored upstream and the generated baselines folder are excluded, and
#: `legacy` does not exist -- superseded code was deleted, not parked (see instruction.md).
FIRST_PARTY_DIRS = ("rlgen", "tools", "tests", "mutants")

#: `rlgen/algos/` holds VENDORED reference implementations (the SAC stack behind RAD and SODA,
#: recovered from this repo's own history). They are excluded from the "no literals" scans below
#: for one reason only: editing them makes every future diff against the reference harder to read,
#: which is the same argument as for RL-ViGen's own algos. The exemption is EARNED, not assumed --
#: `test_vendored_algorithms_never_log_directly` proves their logging path is inert.
VENDORED_DIRS = (os.path.join("rlgen", "algos"),)


def is_vendored(path: str) -> bool:
    rel = os.path.relpath(path, ROOT)
    return any(rel.startswith(v) for v in VENDORED_DIRS)
FIRST_PARTY_FILES = ("train.py", "plot.py")


def first_party_sources() -> list[str]:
    out = [os.path.join(ROOT, f) for f in FIRST_PARTY_FILES]
    for d in FIRST_PARTY_DIRS:
        for dirpath, _dn, fns in os.walk(os.path.join(ROOT, d)):
            if "__pycache__" in dirpath:
                continue
            out += [os.path.join(dirpath, f) for f in fns if f.endswith(".py")]
    return [p for p in out if os.path.exists(p)]


def test_first_party_sources_is_not_empty():
    """A scan that scans nothing passes every test built on it.

    This is the exact failure recorded in docs/REVIEW.md: a cross-check parsed zero rows and
    reported success. Every scan in this file rests on this list, so it is asserted first.
    """
    srcs = first_party_sources()
    assert len(srcs) >= 8, f"only found {len(srcs)} first-party sources: {srcs}"


def test_exactly_one_eval_stepping_loop():
    """One function in the tree steps an environment for evaluation.

    Detection is `env.step(` inside a loop, in first-party code, outside the trainer's own
    experience-collection loop. Three eval paths is how the previous repo's twelve baselines
    ended up on two different benchmarks with two different aggregations.
    """
    allowed = {
        os.path.join(ROOT, "rlgen", "evaluate.py"),   # run_episode -- THE loop
        os.path.join(ROOT, "rlgen", "trainer.py"),    # experience collection, not evaluation
        # The on-policy loop collects a rollout. It is allowed to step the env for the same
        # reason the off-policy loop is -- and it does NOT evaluate: it calls the shared
        # `_do_eval`, which calls the shared `evaluate`, which owns the only eval-stepping loop.
        os.path.join(ROOT, "rlgen", "trainer_onpolicy.py"),
        # tools/crosscheck_against_rlvigen_eval.py deliberately contains a SECOND stepping loop:
        # it is a transcription of RL-ViGen's own `eval.py::robo_eval`, calling `robo_make`
        # directly, so that our evaluator can be compared against an independent implementation
        # on the same policy. A cross-check that reused our loop would compare our loop to itself
        # and prove nothing.
        #
        # This exemption is the one dangerous entry in this set, so it is fenced by
        # `test_the_crosscheck_loop_cannot_leak_into_production` below: nothing under rlgen/ may
        # import that module. A diagnostic that becomes reachable from the pipeline stops being a
        # diagnostic.
        os.path.join(ROOT, "tools", "crosscheck_against_rlvigen_eval.py"),
    }
    def receiver(node: ast.Attribute) -> str:
        """Best-effort name of whatever `.step()` was called on."""
        v = node.value
        if isinstance(v, ast.Name):
            return v.id
        if isinstance(v, ast.Attribute):
            return v.attr
        return ""

    #: `.step()` is also torch's optimizer/scheduler API, which appears inside every training
    #: loop. The property under test is about stepping an ENVIRONMENT, so the receiver has to
    #: look like one. Without this the scan flags `policy_opt.step()` and the test stops meaning
    #: what its name says.
    NOT_AN_ENV = ("opt", "optim", "sched", "scaler")

    offenders = []
    for path in first_party_sources():
        if path in allowed or "/tests/" in path or "/mutants/" in path or is_vendored(path):
            continue
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.For, ast.While)):
                continue
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == "step"):
                    who = receiver(sub.func).lower()
                    if any(t in who for t in NOT_AN_ENV):
                        continue
                    offenders.append(f"{os.path.relpath(path, ROOT)}:{sub.lineno} ({who}.step)")
    assert not offenders, (
        "environment stepping inside a loop outside the shared evaluator: "
        + ", ".join(offenders))


def test_evaluate_cannot_see_the_algorithm():
    """`evaluate` receives the policy as an opaque callable, and no config/agent/model object."""
    sig = inspect.signature(ev.evaluate)
    banned = {"agent", "model", "algo", "algorithm", "config", "cfg", "hyper", "net", "spec"}
    got = set(sig.parameters)
    assert not (got & banned), f"evaluate() accepts algorithm-bearing parameter(s): {got & banned}"
    assert "policy" in got
    ann = sig.parameters["policy"].annotation
    assert ann in (ev.Policy, "Policy") or "Callable" in str(ann), \
        f"policy must be a plain callable, got {ann!r}"


def test_evaluate_ignores_the_label_parameters():
    """`baseline`/`backbone` are recorded on the output and never read by control flow.

    Verified by measurement, not by reading: the same policy under two different labels must
    produce identical numbers. If a branch ever keys on them, this fails.
    """
    p = Protocol(task="Door", total_frames=0, episodes_per_scene=2,
                 eval_scene_ids=(0, 1), horizon=20)
    pol = lambda obs: np.full(7, 0.3, dtype=np.float32)  # noqa: E731
    a = ev.evaluate(p, pol, mode="eval-easy", backend="synthetic", baseline="drqv2",
                    backbone="drqv2")
    b = ev.evaluate(p, pol, mode="eval-easy", backend="synthetic", baseline="svea",
                    backbone="sac")
    assert [r.return_raw for r in a.records] == [r.return_raw for r in b.records]
    assert a.scalars == b.scalars


def test_no_tag_literals_outside_tags_module():
    """Nothing writes a logging key as a string literal."""
    pat = re.compile(r'["\'](?:eval|train_eval|train|diag|gap)/[a-z_]+["\']')
    offenders = []
    for path in first_party_sources():
        if path.endswith(os.path.join("rlgen", "tags.py")) or is_vendored(path):
            continue
        for i, line in enumerate(open(path, encoding="utf-8"), 1):
            if line.lstrip().startswith("#"):
                continue
            if pat.search(line):
                offenders.append(f"{os.path.relpath(path, ROOT)}:{i}")
    assert not offenders, ("logging-key literal(s) outside rlgen/tags.py: " + ", ".join(offenders))


def test_episode_count_comes_only_from_the_protocol():
    """Changing `episodes_per_scene` is the ONLY way to change how many episodes run."""
    pol = lambda obs: np.zeros(7, dtype=np.float32)  # noqa: E731
    for n in (1, 3):
        p = Protocol(task="Door", total_frames=0, episodes_per_scene=n,
                     eval_scene_ids=(0, 1, 2), horizon=20)
        r = ev.evaluate(p, pol, mode="eval-easy", backend="synthetic")
        assert len(r.records) == n * 3 == p.n_eval_episodes
        assert r.scalars[tags.EVAL_EPISODES] == float(n * 3)


def test_every_runnable_baseline_emits_the_required_tags():
    """No baseline may be missing a curve another baseline has."""
    from rlgen import registry
    from rlgen.agents import policy_for
    p = Protocol(task="Door", total_frames=0, episodes_per_scene=1, eval_scene_ids=(0,),
                 horizon=10)
    for name in registry.runnable():
        spec = registry.get(name)
        if spec.build is None:
            continue
        agent = spec.build(p, p.obs_shape, 7, "cpu", {"seed": 0})
        pol = policy_for(agent, True)
        tr = ev.evaluate(p, pol, mode="train", scene_ids=(0,), backend="synthetic")
        evl = ev.evaluate(p, pol, mode="eval-easy", scene_ids=(0,), backend="synthetic")
        produced = set(tr.scalars) | set(evl.scalars) | {tags.GAP_ABSOLUTE}
        missing = (tags.REQUIRED_TAGS - produced) - {tags.EVAL_SUCCESS_RATE,
                                                    tags.TRAIN_EVAL_SUCCESS_RATE}
        assert not missing, f"{name} is missing {sorted(missing)}"


def test_protocol_hash_travels_with_every_episode():
    p = Protocol(task="Door", total_frames=0, episodes_per_scene=1, eval_scene_ids=(0, 1),
                 horizon=10)
    r = ev.evaluate(p, lambda o: np.zeros(7, np.float32), mode="eval-easy", backend="synthetic")
    assert r.records and all(rec.protocol_hash == p.hash() for rec in r.records)


def test_seeds_differ_across_episodes():
    """Reusing one seed for every episode collapses across-episode variance to zero.

    Mutant M6. The synthetic env is deterministic given its seed, so if `_episode_seed` were
    constant, every episode on a scene would return exactly the same number.
    """
    seeds = {ev._episode_seed("abc", "eval-easy", 3, 0, i) for i in range(20)}
    assert len(seeds) == 20, "episode seeds are not distinct"
    assert ev._episode_seed("abc", "eval-easy", 3, 0, 0) \
        != ev._episode_seed("abd", "eval-easy", 3, 0, 0), \
        "episode seed does not depend on the protocol hash, so a stale cached result could pass "
    assert ev._episode_seed("abc", "eval-easy", 3, 0, 0) \
        != ev._episode_seed("abc", "eval-easy", 4, 0, 0), \
        "episode seed does not depend on the scene id"


def test_evaluate_uses_exactly_the_scenes_it_was_given():
    """Evaluating the training scene while labelling the result `eval` is mutant M7.

    It produces a number that looks like generalisation and is not, with no crash and no visible
    anomaly in any curve.
    """
    p = Protocol(task="Door", total_frames=0, episodes_per_scene=2, horizon=10)
    r = ev.evaluate(p, lambda o: np.zeros(7, np.float32), mode="eval-easy",
                    scene_ids=(2, 5, 7), backend="synthetic")
    assert sorted(r.per_scene()) == [2, 5, 7]
    assert {rec.scene_id for rec in r.records} == {2, 5, 7}


def test_aggregation_follows_the_protocol():
    """`mean` and `iqm` are different quantities; the reported one must be the declared one."""
    xs = [0.0, 1.0, 2.0, 3.0, 100.0]
    assert ev._reduce(xs, "mean") != ev._reduce(xs, "iqm")
    p = Protocol(task="Door", total_frames=0, episodes_per_scene=4,
                 eval_scene_ids=(0, 1, 2), horizon=10)
    pol = lambda o: np.zeros(7, np.float32)  # noqa: E731
    got_mean = ev.evaluate(p, pol, mode="eval-easy", backend="synthetic")
    got_iqm = ev.evaluate(p.replace(aggregation="iqm"), pol, mode="eval-easy",
                          backend="synthetic")
    assert got_mean.scalars[tags.EVAL_RETURN_MEAN] == pytest.approx(
        ev._reduce(got_mean.returns, "mean"))
    assert got_iqm.scalars[tags.EVAL_RETURN_MEAN] == pytest.approx(
        ev._reduce(got_iqm.returns, "iqm"))
    assert got_mean.scalars[tags.EVAL_RETURN_MEAN] != got_iqm.scalars[tags.EVAL_RETURN_MEAN]


def test_logger_rejects_an_unknown_tag():
    """A baseline inventing its own key is how the shared plotter starts having to guess."""
    import tempfile
    from rlgen.logging_ import RunLogger
    p = Protocol(task="Door", total_frames=0)
    with tempfile.TemporaryDirectory() as d:
        lg = RunLogger(d, p, baseline="x", tensorboard=False)
        lg.log_scalars({tags.EVAL_RETURN_MEAN: 1.0}, 0)          # known: fine
        # Built by concatenation rather than written as a literal: this file is itself scanned
        # by test_no_tag_literals_outside_tags_module, and a literal here would trip it.
        invented = "eval" + "/" + "my_own_metric"
        with pytest.raises(KeyError, match="unknown log tag"):
            lg.log_scalars({invented: 1.0}, 0)
        lg.close()


def test_logger_refuses_to_mix_two_protocols_in_one_run():
    import tempfile
    from rlgen.logging_ import RunLogger
    p = Protocol(task="Door", total_frames=0, episodes_per_scene=1, eval_scene_ids=(0,),
                 horizon=10)
    other = p.replace(episodes_per_scene=3)
    r = ev.evaluate(other, lambda o: np.zeros(7, np.float32), mode="eval-easy",
                    backend="synthetic")
    with tempfile.TemporaryDirectory() as d:
        lg = RunLogger(d, p, baseline="x", tensorboard=False)
        with pytest.raises(ValueError, match="Two protocols in one log"):
            lg.log_episodes(r.records)
        lg.close()


def test_vendored_algorithms_never_log_directly():
    """What earns `rlgen/algos/` its exemption from the tag-literal scan.

    Those files are vendored reference implementations and they contain their own
    `L.log(...)` calls with their own tag strings. That is fine ONLY because every call site in this repo
    passes `L=None`, so the branch is inert and no tag of theirs ever reaches a log. If that ever
    changes, two logging paths exist and the shared plotter starts having to guess -- so it is
    asserted rather than remembered.
    """
    import re
    algos = os.path.join(ROOT, "rlgen", "algos")
    if not os.path.isdir(algos):
        pytest.skip("no vendored algorithms")
    # every internal log is guarded by an `if L is not None` / `if L:` style check
    for fn in os.listdir(algos):
        if not fn.endswith(".py"):
            continue
        src = open(os.path.join(algos, fn), encoding="utf-8").read()
        for i, line in enumerate(src.splitlines(), 1):
            if re.search(r"\bL\.log\(", line):
                window = "\n".join(src.splitlines()[max(0, i - 4):i])
                assert re.search(r"if L is not None|if L\b", window), (
                    f"rlgen/algos/{fn}:{i} logs without an `if L is not None` guard; the "
                    f"exemption in test_no_tag_literals_outside_tags_module is no longer safe")
    # and the adapter that drives them passes None
    adapter = open(os.path.join(ROOT, "rlgen", "agents.py"), encoding="utf-8").read()
    assert "self._m.update(self._view, None, step)" in adapter, (
        "SacAdapter no longer passes L=None to the vendored update; the vendored files would "
        "then log their own tags outside rlgen/tags.py")


def test_the_crosscheck_loop_cannot_leak_into_production():
    """The one exempted second eval loop must stay unreachable from the pipeline.

    `tools/crosscheck_against_rlvigen_eval.py` is allowed its own env-stepping loop because being
    an INDEPENDENT implementation is the entire point -- comparing our evaluator against itself
    would prove nothing. That exemption is safe only while no production code can reach it.
    """
    import re
    offenders = []
    for src in first_party_sources():
        rel = os.path.relpath(src, ROOT)
        if not rel.startswith("rlgen" + os.sep):
            continue
        text = open(src, encoding="utf-8").read()
        if re.search(r"crosscheck_against_rlvigen_eval", text):
            offenders.append(rel)
    assert not offenders, (
        "production code imports the cross-check's independent eval loop: " + ", ".join(offenders))
