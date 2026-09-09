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
    assert "| policy mode | regime | return | **SE** | success rate | episodes |" in text


def test_it_records_the_door_reward_ceiling():
    """SR=0 and return<=250 are the same statement; the register must not present them as two."""
    text = REGISTER.read_text()
    assert "cannot exceed 250" in text


def test_the_curve_summary_appears_when_curve_rows_exist(tmp_path, monkeypatch):
    """No collected run has eval_scope=curve yet, so this is proven synthetically.

    Without it the curve line would be dead code that looks alive: for `idaac` the curve is 484 of
    528 rows and it is what makes a plateau visible.
    """
    import importlib.util, json
    spec = importlib.util.spec_from_file_location("_reg", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    recs = tmp_path / "records"
    recs.mkdir()
    def row(frame, mean):
        return json.dumps({"baseline": "idaac", "cell": "idaac-s101", "seed": 101,
                           "regime": "train", "frame": frame, "episodes": 60,
                           "episode_return_mean": mean, "phase": "offline-eval",
                           "evaluator_scope": {"eval_scope": "curve"}})
    (recs / "card0-x__records.jsonl").write_text(
        "\n".join(row(f, m) for f, m in [(51200, 24.7), (350208, 50.3), (598016, 24.7)]) + "\n")
    monkeypatch.setattr(mod, "RECORDS", recs)
    monkeypatch.setattr(mod, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    text = mod.build()
    assert "**curve** (train regime, 3 stamp(s))" in text, text[:400]
    assert "peak 50.30 @350,208" in text
    assert "ends below its peak" in text, "a run that falls back must say so"


def test_the_register_states_which_half_check_covers():
    text = REGISTER.read_text()
    assert "Derived versus asserted" in text
    assert "says nothing about the second" in text


def test_the_endpoint_table_carries_a_standard_error():
    """A mean without its noise floor invites reading wiggle as a trend."""
    text = REGISTER.read_text()
    assert "| policy mode | regime | return | **SE** | success rate | episodes |" in text
    assert "± " in text


def test_the_curve_line_states_the_noise_floor_and_the_gap_in_SE(tmp_path, monkeypatch):
    import importlib.util, json
    spec = importlib.util.spec_from_file_location("_reg", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    recs = tmp_path / "records"
    recs.mkdir()

    def row(frame, mean, sd=15.0):
        return json.dumps({"baseline": "idaac", "cell": "c", "seed": 1, "regime": "train",
                           "frame": frame, "episodes": 33, "episode_return_mean": mean,
                           "episode_return_sd": sd, "phase": "offline-eval",
                           "evaluator_scope": {"eval_scope": "curve"}})
    (recs / "j__records.jsonl").write_text(
        "\n".join(row(f, m) for f, m in [(1000, 10.0), (2000, 50.0), (3000, 10.0)]) + "\n")
    monkeypatch.setattr(mod, "RECORDS", recs)
    monkeypatch.setattr(mod, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    text = mod.build()
    assert "SE ≈ 2.6 per point" in text, text[:600]
    assert "is not a trend" in text
    assert "ends below its peak by 15.3 SE" in text
