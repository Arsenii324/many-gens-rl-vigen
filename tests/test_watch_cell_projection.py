"""A slow cell must be visible in minutes, from the laptop -- item 5 of the 2026-09-20
stop-mechanisms fix.

2026-09-19: a cell ran at 2.4 frames per second against a required ~14 FPS, and nothing in the
chain compared elapsed progress against the ceiling
(`notes/inventory-2026-09-19/eval-cost-and-timeout-trace.md` Part 2, 2d: "No projection mechanism
found"). `watch-cell.sh` polls the production host over ssh, so this test never runs the script
itself; it lifts the pure `project_training_finish` function out of it (same extraction pattern as
`tests/test_places365_checks_the_split_it_consumes.py`) and drives it with canned
header+last-row text exactly as the ssh poll would fetch it from a real `train.csv`.
"""
from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
WATCHER = ROOT / "datasphere" / "native" / "host-scripts" / "watch-cell.sh"

BEGIN = "# --- BEGIN project_training_finish ---"
END = "# --- END project_training_finish ---"


def _function_text() -> str:
    text = WATCHER.read_text()
    start = text.index(BEGIN)
    end = text.index(END) + len(END)
    return text[start:end]


def _run(raw: str, frames: str, ceiling_s: str, mode: str) -> tuple[int, str]:
    script = (
        "set -euo pipefail\n"
        + _function_text()
        + f'\nproject_training_finish "$1" "{frames}" "{ceiling_s}" "{mode}"\n'
    )
    done = subprocess.run(["bash", "-c", script, "_", raw],
                          capture_output=True, text=True, timeout=10)
    return done.returncode, done.stdout + done.stderr


# A real train.csv header (drqv2, fetched/card0-20260920-094616/native-out/cells/drqv2-s101/train.csv)
HEADER = ("actor_ent,actor_logprob,actor_loss,batch_reward,buffer_size,critic_loss,critic_q1,"
          "critic_q2,critic_target_q,episode,episode_length,episode_reward,fps,frame,step,"
          "total_time")


def _row(frame: str, total_time: str) -> str:
    # frame is column 14 (index 13), total_time is column 16 (index 15), 0-indexed by comma count.
    cols = ["0"] * 16
    cols[13] = frame
    cols[15] = total_time
    return ",".join(cols)


def test_a_healthy_cell_projects_a_finish_within_its_ceiling(tmp_path):
    """2000 frames in 100s = 20 FPS; target 600000 frames -> 30000s = 8.33h. Ceiling 12h: no overrun."""
    raw = HEADER + "@@TCROW@@" + _row("2000", "100")
    code, out = _run(raw, "600000", "43200", "trip")
    assert code == 0, out
    assert "PROJECTION projected training finish in 8.3 h at 20.00 FPS; ceiling 12.0 h" in out, out
    assert "OVERRUN" not in out, out


def test_the_2026_09_19_incident_would_have_tripped_the_watch(tmp_path):
    """The actual incident: 2.4 FPS against a ~14 FPS requirement (600000 frames / 43200s ceiling).

    At 2.4 FPS a 600000-frame cell finishes in 69.4h against a 12h ceiling -- wildly over 10%.
    """
    raw = HEADER + "@@TCROW@@" + _row("8640", "3600")  # 8640 frames in 1h = 2.4 FPS
    code, out = _run(raw, "600000", "43200", "trip")
    assert code == 0, out
    assert "OVERRUN" in out, out
    assert "exceeds the ceiling" in out, out


def test_beat_mode_never_emits_the_actionable_overrun_line(tmp_path):
    """OVERRUN is for trip to act on; beat is a heartbeat and must not print it."""
    raw = HEADER + "@@TCROW@@" + _row("8640", "3600")
    code, out = _run(raw, "600000", "43200", "beat")
    assert code == 0, out
    assert "OVERRUN" not in out, out
    assert "PROJECTION" in out, out


def test_a_family_with_no_train_csv_says_so_rather_than_guessing(tmp_path):
    """idaac/ppg/ibac_sni/alda/ctrl/dmc_gb write no train.csv; the ssh fetch sends an empty field."""
    code, out = _run("", "600000", "43200", "trip")
    assert code == 0, out
    assert "PROJECTION" in out, out
    assert "cannot project" in out, out
    assert "OVERRUN" not in out, out


def test_an_unknown_ceiling_still_projects_but_never_reports_an_overrun(tmp_path):
    raw = HEADER + "@@TCROW@@" + _row("8640", "3600")
    code, out = _run(raw, "600000", "", "trip")
    assert code == 0, out
    assert "ceiling unknown h" in out, out
    assert "OVERRUN" not in out, out


def test_a_row_with_no_progress_yet_says_so(tmp_path):
    raw = HEADER + "@@TCROW@@" + _row("0", "0")
    code, out = _run(raw, "600000", "43200", "trip")
    assert code == 0, out
    assert "cannot project" in out, out


def test_a_header_missing_the_needed_columns_says_so(tmp_path):
    raw = "some,other,columns@@TCROW@@1,2,3"
    code, out = _run(raw, "600000", "43200", "trip")
    assert code == 0, out
    assert "no frame/total_time column" in out, out


def test_just_under_ten_percent_over_is_not_an_overrun():
    """finish_h is exactly 100.0h (100000 frames at 1000/3600 FPS); ceiling 327273s is just above
    finish_s/1.1 (327272.7...), so finish does not exceed ceiling*1.1."""
    raw = HEADER + "@@TCROW@@" + _row("1000", "3600")
    code, out = _run(raw, "100000", "327273", "trip")
    assert code == 0, out
    assert "OVERRUN" not in out, out


def test_just_over_ten_percent_over_is_an_overrun():
    """Same projection, ceiling 327272s -- one second less crosses ceiling*1.1 (359999.2s)."""
    raw = HEADER + "@@TCROW@@" + _row("1000", "3600")
    code, out = _run(raw, "100000", "327272", "trip")
    assert code == 0, out
    assert "OVERRUN" in out, out
