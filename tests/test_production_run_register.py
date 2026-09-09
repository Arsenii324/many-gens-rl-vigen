"""The run register must cover every records file, state its blind spots, and not go stale.

A catalogue a human maintains rots on the first busy day. This one is generated, and `--check` is
what makes "generated" enforceable rather than aspirational.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "production_run_register.py"
REGISTER = ROOT / "results" / "PRODUCTION-RUNS.md"


def _run(*args: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=str(ROOT))
    return proc.returncode, proc.stdout + proc.stderr


def test_the_register_is_current():
    code, out = _run("--check")
    assert code == 0, out + "\n\nRegenerate: python scripts/production_run_register.py"


def test_check_actually_fails_when_stale(tmp_path):
    """A --check that cannot fail certifies nothing -- this project's own recurring defect."""
    original = REGISTER.read_text()
    try:
        REGISTER.write_text(original + "\nstale line introduced by a test\n")
        code, out = _run("--check")
        assert code == 1, "a modified register must fail --check"
        assert "STALE" in out
    finally:
        REGISTER.write_text(original)
    assert _run("--check")[0] == 0, "the test must restore the register"


def test_every_records_file_appears():
    jobs = {p.name.split("__", 1)[0] for p in (ROOT / "results" / "records").glob("*.jsonl")}
    assert jobs, "no records files: this test would pass vacuously"
    text = REGISTER.read_text()
    missing = sorted(j for j in jobs if f"`{j}`" not in text)
    assert not missing, f"records files absent from the register: {missing[:5]}"


def test_the_caveats_name_what_cannot_be_seen():
    text = REGISTER.read_text()
    for needle in ("Caveats", "not COMMITTED here", "Runs not yet collected do not appear",
                   "not comparable across `policy_mode`", "Overwrite safety"):
        assert needle in text, f"missing caveat: {needle}"


def test_headline_numbers_are_split_by_policy_mode():
    """Pooling a sampled return with a mode return is the defect comparison_blocks.py refuses."""
    text = REGISTER.read_text()
    assert "| policy mode | regime | return | success rate | episodes |" in text


def test_it_records_the_door_reward_ceiling():
    """SR=0 and return<=250 are the same statement; the register must not present them as two."""
    text = REGISTER.read_text()
    assert "cannot exceed 250" in text
