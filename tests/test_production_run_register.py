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


def test_the_combined_scene_row_is_not_counted_as_extra_episodes(tmp_path, monkeypatch):
    """eval_grid emits per-scene rows AND a combined row that repeats them.

    Verified on card0-20260909-035152: the combined row's mean equals the per-scene mean exactly and
    its episodes equal their sum, so weighting all eleven reported n=400 for 200 distinct episodes
    and understated every SE by sqrt(2).
    """
    import importlib.util, json
    spec = importlib.util.spec_from_file_location("_reg", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    recs = tmp_path / "records"
    recs.mkdir()
    per = [{"baseline": "b", "cell": "c", "seed": 1, "regime": "train", "frame": 1,
            "scene_set": str(i), "episodes": 20, "episode_return_mean": 10.0,
            "episode_return_sd": 10.0, "phase": "offline-eval",
            "evaluator_scope": {"eval_scope": "endpoint", "eval_policy_mode": "sample"}}
           for i in range(10)]
    combined = dict(per[0], scene_set="0,1,2,3,4,5,6,7,8,9", episodes=200)
    (recs / "j__records.jsonl").write_text(
        "\n".join(json.dumps(r) for r in per + [combined]) + "\n")
    monkeypatch.setattr(mod, "RECORDS", recs)
    monkeypatch.setattr(mod, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    text = mod.build()
    assert "| 200 | 10 |" in text, f"episodes must be 200 over 10 scenes, not 400:\n{text[-900:]}"
    # The POOLED row is authoritative: its sd is 10.0 over 200 episodes -> SE 0.71. Averaging the
    # per-scene sds would give the same here only because the fixture makes every scene identical;
    # on real data it omits between-scene variance and understates by 1.1-1.4x.
    assert "± 0.71" in text, text[-900:]


def test_the_pooled_row_is_preferred_over_per_scene_weighting(tmp_path, monkeypatch):
    """The pooled row's sd includes between-scene variance; averaging per-scene sds discards it."""
    import importlib.util, json
    spec = importlib.util.spec_from_file_location("_reg3", SCRIPT)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    recs = tmp_path / "records"; recs.mkdir()
    # Ten scenes each with a TINY within-scene sd but wildly different means.
    per = [{"baseline": "b", "cell": "c", "seed": 1, "regime": "train", "frame": 1,
            "scene_set": str(i), "episodes": 20, "episode_return_mean": 10.0 * i,
            "episode_return_sd": 1.0, "phase": "offline-eval",
            "evaluator_scope": {"eval_scope": "endpoint", "eval_policy_mode": "sample"}}
           for i in range(10)]
    pooled = dict(per[0], scene_set="0,1,2,3,4,5,6,7,8,9", episodes=200,
                  episode_return_mean=45.0, episode_return_sd=30.0,
                  native={"aggregate_over_scenes": list(range(10))})
    (recs / "j__records.jsonl").write_text("\n".join(json.dumps(r) for r in per + [pooled]) + "\n")
    monkeypatch.setattr(mod, "RECORDS", recs); monkeypatch.setattr(mod, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    text = mod.build()
    assert "45.00" in text, "the pooled MEAN must be used"
    assert "± 2.12" in text, f"pooled sd 30/sqrt(200)=2.12, not per-scene 1/sqrt(200)=0.07:\n{text[-800:]}"


def test_a_missing_pooled_row_is_flagged_as_a_floor(tmp_path, monkeypatch):
    """idaac's mode/eval-hard lost its pooled row; its SE is a floor and must say so."""
    import importlib.util, json
    spec = importlib.util.spec_from_file_location("_reg4", SCRIPT)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    recs = tmp_path / "records"; recs.mkdir()
    per = [{"baseline": "b", "cell": "c", "seed": 1, "regime": "train", "frame": 1,
            "scene_set": str(i), "episodes": 20, "episode_return_mean": 10.0,
            "episode_return_sd": 10.0, "phase": "offline-eval",
            "evaluator_scope": {"eval_scope": "endpoint", "eval_policy_mode": "sample"}}
           for i in range(8)]
    (recs / "j__records.jsonl").write_text("\n".join(json.dumps(r) for r in per) + "\n")
    monkeypatch.setattr(mod, "RECORDS", recs); monkeypatch.setattr(mod, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    text = mod.build()
    assert "⚠" in text, f"a per-scene fallback SE must be marked:\n{text[-700:]}"


def test_is_summary_row_identifies_the_combined_scene_set():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_reg2", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.is_summary_row({"scene_set": "0,1,2,3,4,5,6,7,8,9"})
    assert not mod.is_summary_row({"scene_set": "7"})
    assert not mod.is_summary_row({"scene_set": 0})
