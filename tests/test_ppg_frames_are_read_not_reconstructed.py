"""A ppg checkpoint whose frame cannot be read must be skipped, never reconstructed.

[Claude 2026-09-09] ppg names checkpoints by SAVE INDEX (`model004.jd`), not by frame, so the frame
has to come from the `Saving to ... IC=<n>` lines its own logger writes. The fallback used to
reconstruct `(stamp + 1) * save_every` when that lookup failed. Measured against a live ppg cell:

    actual IC=   0, 51200, 100352, 151552, 200704     (saves land on the rollout quantum, 25 x 2048)
    fallback     50000, 100000, 150000, 200000, 250000

Wrong in two independent ways -- the cadence is 51200 rather than the requested 50000, and it is off
by one save because `model000.jd` is written at IC=0. Every curve row would have carried a frame
wrong by up to 50k, shifted systematically, with nothing marking it.

A skipped checkpoint shows up as a missing row. A mislabelled one shows up as nothing at all, and
`eval_grid.py --frame` exists precisely to stop a measurement being attached to the wrong frame.
"""
from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE = ROOT / "datasphere" / "native" / "run_probe.sh"


def _fn() -> str:
    text = PROBE.read_text()
    start = text.index("ppg_checkpoint_frame() {")
    return text[start:text.index("\n}\n", start)]


def test_it_reads_the_interaction_count_from_the_log():
    body = _fn()
    assert "IC=" in body, "the authoritative interaction count is no longer consulted"
    assert "Saving to" in body


def test_it_no_longer_reconstructs_a_cadence():
    body = _fn()
    assert "(10#$stamp + 1) * save_every" not in body, (
        "the reconstruction is back; it is off by one save and uses the requested cadence rather "
        "than the rollout quantum ppg actually saves on")
    assert "NATIVE_PPG_FRAME_UNMAPPABLE" in body, "an unmappable frame is not announced"


def test_the_caller_skips_rather_than_evaluating_with_no_frame():
    text = PROBE.read_text()
    assert "NATIVE_CURVE_EVAL_SKIPPED" in text, (
        "an empty frame reaches eval_grid.py, which would record a measurement with no frame")


def test_the_function_executes_and_returns_the_logged_value(tmp_path):
    """Driven through the real bash, against a log shaped like ppg's."""
    cell = tmp_path / "cell"
    cell.mkdir()
    (cell / "training.log").write_text(
        "Saving to  /x/model000.jd IC=0\n"
        "Saving to  /x/model001.jd IC=51200\n"
        "Saving to  /x/model002.jd IC=100352\n")
    body = _fn()
    for stamp, expect in (("0", "0"), ("1", "51200"), ("002", "100352")):
        script = f"{body}\n}}\nppg_checkpoint_frame {cell} {stamp} 50000\n"
        out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)
        assert out.stdout.strip() == expect, (
            f"stamp {stamp}: got {out.stdout.strip()!r}, expected {expect!r}\n{out.stderr}")


def test_an_unmappable_stamp_returns_empty_and_says_so(tmp_path):
    cell = tmp_path / "cell"
    cell.mkdir()
    (cell / "training.log").write_text("Saving to  /x/model000.jd IC=0\n")
    script = f"{_fn()}\n}}\nppg_checkpoint_frame {cell} 7 50000\n"
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "", f"reconstructed a frame: {out.stdout!r}"
    assert "NATIVE_PPG_FRAME_UNMAPPABLE" in out.stderr, out.stderr
