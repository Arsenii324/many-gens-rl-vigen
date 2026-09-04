"""The shared plotter, and the success probe's wrapper walk."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import plot  # noqa: E402
from rlgen import evaluate as ev  # noqa: E402
from rlgen import registry, tags  # noqa: E402
from rlgen.logging_ import RunLogger, run_dir  # noqa: E402
from rlgen.protocol import Protocol  # noqa: E402


# ---------------------------------------------------------------------- success probe
def test_success_probe_walks_the_real_attribute_names():
    """Regression: the chain does not use one attribute name throughout.

    ExtendedTimeStep/FrameStack/ActionRepeat link with `_env`, Gym2DMC with `_gym_env`, and
    VGBWrapper with `env`. Walking only `_env` stopped at Gym2DMC, and `success` was silently
    empty in every row of the first real run -- a missing column, not an error.
    """
    class Task:
        def _check_success(self):
            return True

    class VGB:
        def __init__(self, inner):
            self.env = inner

    class Gym2DMC:
        def __init__(self, inner):
            self._gym_env = inner

    class Link:
        def __init__(self, inner):
            self._env = inner

    class Outer:
        def __init__(self, inner):
            self._env = inner

    chain = Outer(Link(Link(Link(Gym2DMC(VGB(Task()))))))
    assert ev._read_success(chain) is True


def test_success_is_none_rather_than_invented_when_unreachable():
    class Outer:
        _env = None
    assert ev._read_success(Outer()) is None


# ---------------------------------------------------------------------- plotter
def _fake_run(root: str, baseline: str, seed: int, task: str = "Door") -> str:
    p = Protocol(task=task, total_frames=200, episodes_per_scene=1, eval_scene_ids=(0, 1),
                 horizon=10, seed=seed)
    d = run_dir(root, p, baseline)
    lg = RunLogger(d, p, baseline=baseline, tensorboard=True)
    pol = lambda o: np.full(7, 0.1 * (seed + 1), np.float32)  # noqa: E731
    for frames in (0, 100, 200):
        tr = ev.evaluate(p, pol, mode="train", scene_ids=(0,), frames=frames,
                         baseline=baseline, backend="synthetic")
        evl = ev.evaluate(p, pol, mode="eval-easy", frames=frames, baseline=baseline,
                          backend="synthetic")
        lg.log_episodes(tr.records)
        lg.log_scalars(tr.scalars, frames)
        lg.log_eval(evl, frames)
    lg.close()
    return d


def test_plotter_has_no_per_baseline_branch():
    """R5: one drawing routine for every baseline."""
    src = open(os.path.join(ROOT, "plot.py"), encoding="utf-8").read()
    for name in registry.BASELINES:
        if name == "random":
            continue
        assert f'"{name}"' not in src and f"'{name}'" not in src, \
            f"plot.py mentions the baseline {name!r} by name"


def test_plotter_reads_jsonl_and_events_identically():
    """Same numbers by both paths, so `--events` and the default cannot disagree."""
    pytest.importorskip("tensorboard")
    with tempfile.TemporaryDirectory() as root:
        _fake_run(root, "drqv2", 0)
        a = plot.discover(root, plot.read_run)
        b = plot.discover(root, plot.read_run_events)
        assert len(a) == len(b) == 1
        for tag in (tags.EVAL_RETURN_MEAN, tags.TRAIN_EVAL_RETURN_MEAN, tags.GAP_ABSOLUTE):
            sa, sb = a[0]["series"][tag], b[0]["series"][tag]
            assert set(sa) == set(sb)
            for k in sa:
                assert sa[k] == pytest.approx(sb[k], rel=1e-6), f"{tag}@{k}"


def test_discover_refuses_roots_that_would_collect_unrelated_runs():
    """$TMPDIR, `/` and `$HOME` are never a logs root, and accepting one produces a wrong figure
    rather than an error. A test derived exactly such a root by accident and stayed green."""
    for bad in (tempfile.gettempdir(), os.sep, os.path.expanduser("~")):
        with pytest.raises(ValueError, match="refusing to treat"):
            plot.discover(bad)
    # A legitimate root that merely LIVES in temp must still work, or the guard is too broad.
    with tempfile.TemporaryDirectory() as root:
        _fake_run(root, "drqv2", 0)
        assert len(plot.discover(root)) == 1


def test_plotter_aggregates_seeds_and_emits_a_figure():
    with tempfile.TemporaryDirectory() as root:
        _fake_run(root, "drqv2", 0)
        _fake_run(root, "drqv2", 1)
        _fake_run(root, "curl", 0)
        runs = plot.discover(root)
        assert len(runs) == 3
        agg = plot.aggregate(runs, tags.EVAL_RETURN_MEAN)
        assert len(agg[("Door", "drqv2")][200]) == 2, "two seeds did not aggregate"
        assert len(agg[("Door", "curl")][200]) == 1
        out = plot.make_figure(runs, os.path.join(root, "fig.png"))
        assert os.path.getsize(out) > 5000
        table = plot.make_table(runs)
        assert "drqv2" in table and "curl" in table


def test_plotter_refuses_to_plot_nothing():
    """A plot of no runs is a missing measurement, not an empty figure."""
    with tempfile.TemporaryDirectory() as empty:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "plot.py"), "--logs", empty],
                           capture_output=True, text=True, cwd=ROOT)
        assert r.returncode == 1 and "no runs" in (r.stdout + r.stderr)


def test_an_alias_would_be_labelled_in_the_legend():
    """No baseline is currently an alias -- `ctrl` was, wrongly, until it was identified as a
    PPO-based method rather than a CURL variant. The labelling machinery still has to work, so it
    is tested against a constructed spec rather than deleted along with its last user."""
    from rlgen.registry import BaselineSpec
    fake = BaselineSpec(name="x", method="X", backbone="b", status="alias", alias_of="curl",
                        paper="-")
    assert fake.label == "x (= curl)"
    assert plot.label_for("drqv2") == "drqv2"
    for n, s in registry.BASELINES.items():
        if s.status == "alias":
            assert s.alias_of and s.alias_of in s.label, f"{n} hides its aliasing"
