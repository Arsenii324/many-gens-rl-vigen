"""Each pathology the two production cells showed must be detectable, in both log formats.

Written against the real shapes: `idaac` emits a progress CSV with `train/*` columns, `ppg` emits
`| key | value |` blocks with `Opt/*` names. An auditor that parses one and silently finds nothing
in the other would pass every ppg run.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "audit_training_diagnostics.py"


def _run(target: pathlib.Path, *extra: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(SCRIPT), str(target), *extra],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def _csv(tmp_path: pathlib.Path, rows: list[dict]) -> pathlib.Path:
    path = tmp_path / "progress.csv"
    keys = list(rows[0])
    path.write_text(",".join(keys) + "\n"
                    + "\n".join(",".join(str(r[k]) for k in keys) for r in rows) + "\n")
    return path


def _log(tmp_path: pathlib.Path, blocks: list[dict]) -> pathlib.Path:
    path = tmp_path / "training.log"
    out = []
    for b in blocks:
        out.append("-" * 40)
        out.extend(f"| {k:<24} | {v:<8} |" for k, v in b.items())
    path.write_text("\n".join(out) + "\n")
    return path


def _healthy(n: int = 20) -> list[dict]:
    return [{"train/total_num_steps": 2048 * (i + 1), "train/approx_kl_k3": 0.02,
             "train/clip_fraction": 0.2, "train/sigma_mean": 1.0 - 0.005 * i,
             "VFStats/EV": 0.6} for i in range(n)]


def test_a_healthy_run_raises_nothing(tmp_path):
    code, out = _run(_csv(tmp_path, _healthy()), "--strict")
    assert code == 0, out
    assert "No diagnostic left its expected range" in out


def test_trust_region_blowout_is_flagged(tmp_path):
    rows = _healthy()
    for r in rows[10:]:
        r["train/approx_kl_k3"], r["train/clip_fraction"] = 1.2, 0.83
    code, out = _run(_csv(tmp_path, rows), "--strict")
    assert code == 1, out
    assert "far outside the trust region" in out
    assert "clipping boundary" in out


def test_a_policy_that_never_moves_is_flagged(tmp_path):
    rows = _healthy()
    for r in rows:
        r["train/approx_kl_k3"], r["train/clip_fraction"] = 2.5e-13, 0.0
        r["train/sigma_mean"] = 1.0
    code, out = _run(_csv(tmp_path, rows), "--strict")
    assert code == 1, out
    assert "not moving between sampling and update" in out
    assert "scale never moved" in out


def test_entropy_collapse_is_flagged(tmp_path):
    rows = _healthy()
    for i, r in enumerate(rows):
        r["train/sigma_mean"] = max(0.188, 1.0 - 0.05 * i)
    code, out = _run(_csv(tmp_path, rows), "--strict")
    assert code == 1, out
    assert "collapsed toward determinism" in out


def test_a_critic_that_does_not_fit_is_flagged(tmp_path):
    rows = _healthy()
    for r in rows:
        r["VFStats/EV"] = 0.01
    code, out = _run(_csv(tmp_path, rows), "--strict")
    assert code == 1, out
    assert "does not explain the returns" in out


def test_the_ppg_log_format_is_parsed_and_flagged(tmp_path):
    """The exact shape of the live ppg cell: `| Opt/clipfrac | 0 |` blocks, zeros throughout."""
    blocks = [{"Misc/InteractCount": 2048 * (i + 1), "Opt/approxkl": 2.5e-13,
               "Opt/clipfrac": 0, "Opt/entropy": 9.93, "train/sigma_mean": 1.0,
               "VFStats/EV": 0.8} for i in range(20)]
    code, out = _run(_log(tmp_path, blocks), "--strict")
    assert code == 1, out
    assert "Opt/clipfrac" in out, "the ppg log format must be parsed at all"
    assert "not moving between sampling and update" in out


def test_reward_series_disagreeing_in_sign_is_reported(tmp_path):
    """EpRewMean 18.1 against EpLen 500 x FrameRew 0.00746 = 3.73 -- one of them is normalised."""
    blocks = [{"EpRewMean": 18.1, "Misc/FrameRewMean": 0.00746, "EpLenMean": 500,
               "Opt/approxkl": 0.02, "Opt/clipfrac": 0.2, "train/sigma_mean": 1.0 - 0.03 * i,
               "VFStats/EV": 0.8} for i in range(6)]
    code, out = _run(_log(tmp_path, blocks), "--strict")
    assert code == 1, out
    assert "ONE IS NORMALISED" in out
    assert "3.73" in out


def test_consistent_reward_series_are_not_reported(tmp_path):
    blocks = [{"EpRewMean": 3.73, "Misc/FrameRewMean": 0.00746, "EpLenMean": 500,
               "Opt/approxkl": 0.02, "Opt/clipfrac": 0.2, "train/sigma_mean": 1.0 - 0.03 * i,
               "VFStats/EV": 0.8} for i in range(6)]
    code, out = _run(_log(tmp_path, blocks), "--strict")
    assert code == 0, out
    assert "ONE IS NORMALISED" not in out


def test_absent_series_are_named_rather_than_passed(tmp_path):
    rows = [{"train/total_num_steps": 2048 * (i + 1), "train/approx_kl_k3": 0.02} for i in range(6)]
    code, out = _run(_csv(tmp_path, rows))
    assert code == 0, out
    assert "NOT CHECKED, no series found" in out
    assert "clipfrac" in out and "sigma" in out


def test_a_file_with_no_diagnostics_refuses_rather_than_passing(tmp_path):
    (tmp_path / "empty.log").write_text("nothing to see\n")
    code, out = _run(tmp_path / "empty.log")
    assert code == 2, out
    assert "NOT the same as nothing being wrong" in out


def test_a_short_run_is_reported_not_judged(tmp_path):
    """A 2-iteration smoke run has a flat sigma and an unfitted critic by definition."""
    rows = [{"train/total_num_steps": 2048 * (i + 1), "train/approx_kl_k3": 0.02,
             "train/clip_fraction": 0.2, "train/sigma_mean": 1.0, "VFStats/EV": 0.01}
            for i in range(2)]
    code, out = _run(_csv(tmp_path, rows), "--strict")
    assert code == 0, out
    assert "Too short to judge" in out
    assert "FLAG" not in out


def test_two_cells_in_one_run_are_never_pooled(tmp_path):
    """card0-20260909-013936 ran idaac-s101 and ppg-s1 in one job; merging them mixes loggers."""
    (tmp_path / "idaac-s101").mkdir()
    (tmp_path / "ppg-s1").mkdir()
    healthy = _healthy()
    _csv(tmp_path / "idaac-s101", healthy)
    blown = [dict(r, **{"train/approx_kl_k3": 1.3, "train/clip_fraction": 0.83}) for r in healthy]
    _csv(tmp_path / "ppg-s1", blown)
    code, out = _run(tmp_path, "--strict")
    assert code == 1, out
    assert "2 unit(s), reported separately" in out
    assert "never pooled or compared" in out
    # The healthy unit must still read healthy; a pooled median would have flagged both.
    assert "No diagnostic left its expected range" in out
    assert "far outside the trust region" in out


def test_the_pooled_job_level_log_is_dropped_when_per_cell_files_exist(tmp_path):
    """The runner tees every cell into job.log, so on a two-cell job it IS the pooled mixture."""
    cells = tmp_path / "native-out" / "cells"
    (cells / "idaac-s101").mkdir(parents=True)
    _csv(cells / "idaac-s101", _healthy())
    blown = [dict(r, **{"train/approx_kl_k3": 1.3, "train/clip_fraction": 0.83}) for r in _healthy()]
    _log(tmp_path / "native-out", [{"train/approx_kl_k3": r["train/approx_kl_k3"],
                                    "train/clip_fraction": r["train/clip_fraction"],
                                    "train/sigma_mean": r["train/sigma_mean"]} for r in blown])
    (tmp_path / "native-out" / "training.log").rename(tmp_path / "native-out" / "job.log")
    code, out = _run(tmp_path, "--strict")
    assert code == 0, out
    assert "1 unit(s)" in out, out
    assert "job.log" not in out, "the pooled superset must not be checked beside its own parts"


def test_a_trainer_clamping_its_own_minibatch_count_is_flagged(tmp_path):
    """`Warning: nminibatch > ntrain!! (32 > 1)` appeared 289 times in a live cell, unread.

    The range checks CANNOT catch this: with one minibatch the ratio is 1 every time it is measured,
    so clipfrac reads 0.000 and approxkl reads float noise -- which is exactly what a perfectly
    behaved optimiser would also look like if you only had those two columns.
    """
    log = tmp_path / "training.log"
    log.write_text("\n".join(["Warning: nminibatch > ntrain!! (32 > 1)"] * 289) + "\n"
                   + "\n".join(f"| Opt/clipfrac             | 0        |\n"
                               f"| Opt/approxkl             | 2.5e-13  |\n"
                               f"| train/sigma_mean         | {1.0 - 0.03 * i:<8} |"
                               for i in range(8)) + "\n")
    code, out = _run(tmp_path, "--strict")
    assert code == 1, out
    assert "TRAINER WARNING x289" in out, out
    assert "CLAMPED its own minibatch count" in out
    assert "outranks every range check" in out


def test_no_trainer_warning_is_not_reported(tmp_path):
    code, out = _run(_csv(tmp_path, _healthy()), "--strict")
    assert code == 0, out
    assert "TRAINER WARNING" not in out
