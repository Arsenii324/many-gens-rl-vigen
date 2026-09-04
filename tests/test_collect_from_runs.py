"""`collect_metrics.py --from-runs` against a real run tree's shape.

The collector reported **0 records from 0 baselines** when pointed at the only runs this project
has. It expects `<logdir>/<baseline>.log`, which is the smoke-test layout it was written and
tested against; real runs are `exp_local/<date>/<override_dirname>/`. Nothing had ever joined the
parsers to a real tree, so both sides were correct and the pair was useless.

`test_train_log_alone_yields_nothing` is the one that pins the second, subtler half: the fix
first read `train.log`, which is hydra's own log, while the `| train | F: ... |` lines the
RL-ViGen parser matches only ever go to stdout.
"""
from __future__ import annotations

import importlib
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture()
def mod():
    m = importlib.import_module("collect_metrics")
    importlib.reload(m)
    return m


def make_run(root, name="config", *, post_p14=True, csv_name="eval.csv", train_log=False):
    run = root / "2026.08.20" / "120000_action_repeat=1,env=robosuite"
    (run / ".hydra").mkdir(parents=True, exist_ok=True)
    (run / ".hydra" / "hydra.yaml").write_text(f"job:\n  config_name: {name}\n")
    if train_log:
        (run / "train.log").write_text("| train | F: 1000 | S: 1000 | R: 42.0 |\n")
    if csv_name:
        cols = "episode,episode_length,episode_reward,frame,step,success_rate,total_time"
        row = "0,500,12.5,1000,1000,0.25,1.0"
        if post_p14:
            cols += ",train_regime_reward,train_regime_success"
            row += ",34.0,0.75"
        (run / csv_name).write_text(cols + "\n" + row + "\n")
    return run


def test_post_p14_run_yields_both_regimes(mod, tmp_path):
    make_run(tmp_path, post_p14=True)
    recs, counts = mod.collect_from_runs(tmp_path)
    regimes = {r.regime for r in recs}
    assert regimes == {"eval-recorded", "train"}, regimes
    tr = [r for r in recs if r.regime == "train"][0]
    assert tr.episode_reward == 34.0 and tr.success_rate == 0.75
    assert all(r.baseline == "drqv2" for r in recs)


def test_pre_p14_regime_is_not_guessed(mod, tmp_path):
    """Calling it eval-easy is how a gap gets manufactured from one distribution."""
    make_run(tmp_path, post_p14=False)
    recs, _ = mod.collect_from_runs(tmp_path)
    assert {r.regime for r in recs} == {"eval(unrecorded)"}
    assert not any("easy" in r.regime for r in recs)


def test_train_log_alone_yields_nothing(mod, tmp_path):
    """train.log is hydra's log; the metric lines are stdout and are not persisted."""
    make_run(tmp_path, csv_name=None, train_log=True)
    recs, counts = mod.collect_from_runs(tmp_path)
    assert recs == [], "records were invented from a log that carries no metrics"


def test_a_run_without_hydra_config_is_skipped(mod, tmp_path):
    run = tmp_path / "2026.08.20" / "somerun"
    run.mkdir(parents=True)
    (run / "eval.csv").write_text("frame,episode_reward\n1000,5.0\n")
    recs, counts = mod.collect_from_runs(tmp_path)
    assert recs == [] and counts == {}, "a run whose baseline is unknown was attributed anyway"


def test_baseline_comes_from_the_runs_own_config(mod, tmp_path):
    make_run(tmp_path, name="svea_config")
    recs, _ = mod.collect_from_runs(tmp_path)
    assert {r.baseline for r in recs} == {"svea"}


def test_flat_layout_still_works(mod, tmp_path):
    """The original contract must not be broken by the new mode."""
    (tmp_path / "drqv2.log").write_text(
        "Now the mode is train\nNow the mode is eval-easy\n"
        "| eval | F: 1000 | S: 1000 | E: 0 | L: 500 | R: 5.5 | T: 0:01 | SR: 0.2000\n")
    recs, counts = mod.collect(tmp_path)
    assert any(r.baseline == "drqv2" for r in recs)


def test_a_baseline_nested_one_level_deeper_is_found(mod, tmp_path):
    """Only drqv2's config writes exp_local/<date>/<run>/.

    svea, drq, sgqn and curl interpolate ${name} into hydra.run.dir and land at
    exp_local/<date>/<name>/<run>/. A fixed `*/*/eval.csv` pattern finds drqv2 and misses four
    of the five -- and a tree containing only drqv2 runs cannot reveal that, which is how the
    first version of this collector passed its own tests while reading nothing real.
    """
    run = tmp_path / "2026.08.20" / "svea" / "135252_action_repeat=1"
    (run / ".hydra").mkdir(parents=True)
    (run / ".hydra" / "hydra.yaml").write_text("job:\n  config_name: svea_config\n")
    (run / "eval.csv").write_text(
        "episode,episode_length,episode_reward,frame,step,success_rate,total_time,"
        "train_regime_reward,train_regime_success\n0,500,9.5,1000,1000,0.1,1.0,20.0,0.3\n")
    recs, counts = mod.collect_from_runs(tmp_path)
    assert {r.baseline for r in recs} == {"svea"}, f"nested run not found: {counts}"
    assert {r.regime for r in recs} == {"eval-recorded", "train"}


def test_both_depths_are_collected_together(mod, tmp_path):
    make_run(tmp_path)                                   # drqv2, flat
    run = tmp_path / "2026.08.20" / "svea" / "135252_x"   # svea, nested
    (run / ".hydra").mkdir(parents=True)
    (run / ".hydra" / "hydra.yaml").write_text("job:\n  config_name: svea_config\n")
    (run / "eval.csv").write_text(
        "episode,episode_reward,frame,success_rate\n0,9.5,1000,0.1\n")
    recs, _ = mod.collect_from_runs(tmp_path)
    assert {r.baseline for r in recs} == {"drqv2", "svea"}
