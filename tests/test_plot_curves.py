"""R5 item 3: one routine over event files, no per-algorithm branch.

The failures that matter are silent ones. A tag a baseline never logged must be reported as that
baseline's logging gap, not dropped so the figure looks complete; and an empty run tree must be a
failure, because "nothing was plotted" and "everything plotted fine" render identically as an
absent error message.
"""
from __future__ import annotations

import importlib
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
from rlgen import tags as T   # noqa: E402  literals live in exactly one module
pytest.importorskip("matplotlib")
SW = pytest.importorskip("torch.utils.tensorboard").SummaryWriter


@pytest.fixture()
def mod():
    m = importlib.import_module("plot_curves")
    importlib.reload(m)
    return m


def write_run(root, name, tags, n=5):
    d = root / "2026.08.20" / name / "tb"
    d.mkdir(parents=True)
    w = SW(str(d))
    for t in tags:
        for i in range(n):
            w.add_scalar(t, float(i), i * 1000)
    w.close()
    return d


def test_no_event_files_is_a_failure(mod, tmp_path, capsys):
    assert mod.main([str(tmp_path), "--out", str(tmp_path / "o")]) == 1
    assert "SKIP is not a pass" in capsys.readouterr().out


def test_a_missing_tag_is_reported_not_hidden(mod, tmp_path, capsys):
    write_run(tmp_path, "runA", [T.EVAL_RETURN_MEAN, T.TRAIN_RETURN_MEAN])
    write_run(tmp_path, "runB", [T.EVAL_RETURN_MEAN])          # no loss
    rc = mod.main([str(tmp_path), "--out", str(tmp_path / "o")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "NOT LOGGED" in out and T.TRAIN_RETURN_MEAN in out
    assert "logging gap" in out


def test_runs_are_found_at_any_depth(mod, tmp_path, capsys):
    write_run(tmp_path, "flatrun", [T.EVAL_RETURN_MEAN])
    d = tmp_path / "2026.08.20" / "svea" / "nested" / "tb"
    d.mkdir(parents=True)
    w = SW(str(d)); w.add_scalar(T.EVAL_RETURN_MEAN, 1.0, 0); w.close()
    runs = mod.find_runs(tmp_path)
    assert len(runs) == 2, f"depth-sensitive discovery: {runs}"


def test_an_unknown_baseline_name_still_plots(mod, tmp_path, capsys):
    """No per-algorithm branch: the routine must not care what the run is called."""
    write_run(tmp_path, "some_baseline_nobody_has_heard_of", [T.EVAL_RETURN_MEAN])
    rc = mod.main([str(tmp_path), "--out", str(tmp_path / "o"),
                   "--tags", T.EVAL_RETURN_MEAN])
    assert rc == 0
    assert (tmp_path / "o" / (T.EVAL_RETURN_MEAN.replace("/", "_") + ".png")).exists()


def test_requesting_only_absent_tags_fails(mod, tmp_path, capsys):
    write_run(tmp_path, "runA", [T.EVAL_RETURN_MEAN])
    rc = mod.main([str(tmp_path), "--out", str(tmp_path / "o"), "--tags", "absent" + "/" + "series"])
    assert rc == 1
    assert "nothing plotted" in capsys.readouterr().out
