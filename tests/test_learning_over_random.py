"""A floor must be used when present, reported when absent, and never borrowed.

Written after calling a plateau a failure to learn for want of a random baseline, and then --
within the hour -- asserting that every family has one. `ppg` does, by accident of its save-index
scheme writing `model000.jd` at IC=0. `idaac`'s earliest checkpoint is 51,200 and it has none.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "learning_over_random.py"


def _run(target: pathlib.Path) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(SCRIPT), str(target)],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def _write(path: pathlib.Path, rows: list[dict]) -> pathlib.Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def _row(baseline, cell, seed, regime, frame, mean, episodes=20):
    return {"baseline": baseline, "cell": cell, "seed": seed, "regime": regime,
            "frame": frame, "episode_return_mean": mean, "episodes": episodes}


def test_a_ratio_is_computed_against_the_cells_own_floor(tmp_path):
    f = _write(tmp_path / "r.jsonl", [
        _row("ppg", "ppg-s1", 1, "train", 0, 2.24),
        _row("ppg", "ppg-s1", 1, "train", 600064, 22.4),
    ])
    code, out = _run(f)
    assert code == 0, out
    assert "floor    2.24" in out
    assert "10.0x" in out, out


def test_the_peak_is_reported_separately_from_the_last(tmp_path):
    """A run that rises then falls back must not read as a run that never rose."""
    f = _write(tmp_path / "r.jsonl", [
        _row("idaac", "idaac-s101", 101, "train", 0, 2.0),
        _row("idaac", "idaac-s101", 101, "train", 350208, 50.0),
        _row("idaac", "idaac-s101", 101, "train", 598016, 24.0),
    ])
    code, out = _run(f)
    assert code == 0, out
    assert "last   24.00 @598016 =  12.0x" in out, out
    assert "peak   50.00 @350208 =  25.0x" in out, out


def test_a_missing_floor_is_reported_and_no_ratio_is_invented(tmp_path):
    """idaac's real shape: earliest checkpoint 51,200, no untrained one."""
    f = _write(tmp_path / "r.jsonl", [
        _row("idaac", "idaac-s101", 101, "train", 51200, 24.7),
        _row("idaac", "idaac-s101", 101, "train", 598016, 33.7),
    ])
    code, out = _run(f)
    assert code == 0, out
    assert "NO frame-0 row -- floor unknown, ratio NOT computed" in out
    assert "x" not in out.split("train")[1].split("\n")[0], "no ratio may be printed"


def test_a_floor_is_never_borrowed_from_another_family(tmp_path):
    """ppg's 2.24 must not become idaac's floor just because both are in the file."""
    f = _write(tmp_path / "r.jsonl", [
        _row("ppg", "ppg-s1", 1, "train", 0, 2.24),
        _row("ppg", "ppg-s1", 1, "train", 600064, 22.4),
        _row("idaac", "idaac-s101", 101, "train", 51200, 24.7),
    ])
    code, out = _run(f)
    assert code == 0, out
    # Blocks are sorted, so idaac's comes first; take only its own lines, not everything after.
    lines = out.splitlines()
    start = next(i for i, l in enumerate(lines) if "idaac / idaac-s101" in l)
    idaac_lines = []
    for l in lines[start + 1:]:
        if l.strip() == "" or "/" in l and "seed" in l:
            break
        idaac_lines.append(l)
    idaac_block = "\n".join(idaac_lines)
    assert "NO frame-0 row" in idaac_block, out
    assert "2.24" not in idaac_block, f"ppg's floor leaked into idaac's block:\n{idaac_block}"
    assert "x" not in idaac_block.replace("unknown", ""), f"no ratio may appear:\n{idaac_block}"
    assert "NOT borrowed from another cell or family" in out


def test_the_floor_is_episode_weighted_across_scene_sets(tmp_path):
    """One regime spans many scene_set rows; a plain mean over rows would misweight them."""
    f = _write(tmp_path / "r.jsonl", [
        _row("ppg", "ppg-s1", 1, "train", 0, 1.0, episodes=90),
        _row("ppg", "ppg-s1", 1, "train", 0, 10.0, episodes=10),
        _row("ppg", "ppg-s1", 1, "train", 1000, 19.0, episodes=100),
    ])
    code, out = _run(f)
    assert code == 0, out
    assert "floor    1.90" in out, out   # (1.0*90 + 10.0*10)/100, not (1+10)/2
    assert "10.0x" in out


def test_empty_input_refuses_rather_than_reporting_nothing_found(tmp_path):
    f = _write(tmp_path / "r.jsonl", [])
    code, out = _run(f)
    assert code == 2, out
    assert "NOT the" in out and "same as nothing having been measured" in out


def test_it_says_plainly_that_this_is_not_a_leaderboard(tmp_path):
    f = _write(tmp_path / "r.jsonl", [_row("ppg", "ppg-s1", 1, "train", 0, 2.0),
                                      _row("ppg", "ppg-s1", 1, "train", 100, 20.0)])
    code, out = _run(f)
    assert code == 0, out
    assert "not a leaderboard" in out
    assert "weakest bar" in out
