"""Every family's declared `intermediate_checkpoints` glob must actually match what it writes.

[Claude 2026-09-04] The globs were declared on 2026-09-02 and, until today, no run had ever
produced a second checkpoint for them to match -- because `SAVE_EVERY` never reached the runner
(see `test_job_knobs_are_read.py`), so every cell saved once, at the end, and `retained.json`
listed no intermediates on any job. The declaration and the behaviour had therefore never met.

This drives `family.retain` against a fabricated run directory per family, which costs nothing and
covers the half of the feature that does not need a GPU: does the glob match, and does retention
copy the matches into `checkpoints/` under names that stay distinguishable. What it cannot cover is
whether each training loop emits stamps at the requested cadence -- that is what the GPU probe is
for. Keeping the two halves separate is deliberate: a paid job should test only what it must.
"""
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "datasphere" / "native"

_spec = importlib.util.spec_from_file_location("_family_under_test", NATIVE / "family.py")
family = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(family)

_FAMILIES = json.loads((NATIVE / "families.json").read_text())
_FAMILIES = _FAMILIES.get("families", _FAMILIES)
NAMES = sorted(n for n, e in _FAMILIES.items()
               if isinstance(e, dict) and e.get("checkpoint") and e.get("intermediate_checkpoints"))


def _fill(pattern: str, stamp: int) -> str:
    """A concrete filename that the declared glob must match."""
    return pattern.replace("[0-9]", "2").replace("*", str(stamp))


def test_every_family_declares_an_intermediate_glob():
    assert len(NAMES) == 7, f"expected all seven families to declare one, got {NAMES}"


@pytest.mark.parametrize("name", NAMES)
def test_declared_glob_matches_written_stamps_and_retention_keeps_them(name, tmp_path):
    entry = _FAMILIES[name]
    run = tmp_path / name
    run.mkdir(parents=True)
    fields = {"run_dir": str(run), "task": "Door", "baseline": name, "seed": 1, "frames": 10000}
    root = family.artifact_root(name, fields)
    full = family.full_fields(name, fields)
    root.mkdir(parents=True, exist_ok=True)

    for curve in entry.get("required_curves", []):
        path = root / family.render(curve, full)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("step,return\n0,1.0\n")

    terminal = root / _fill(family.render(entry["checkpoint"], full), 10000)
    terminal.parent.mkdir(parents=True, exist_ok=True)
    terminal.write_bytes(b"terminal-checkpoint")

    stamps = (2000, 4000, 6000)
    written = []
    for stamp in stamps:
        path = root / _fill(family.render(entry["intermediate_checkpoints"], full), stamp)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"intermediate")
        written.append(path.name)

    out = tmp_path / f"{name}-out"
    out.mkdir(parents=True, exist_ok=True)
    if not entry["required_curves"]:
        # alda and ctrl log to the console; the runner captures it and retention requires it
        # non-empty. Supplying it here keeps the fail-closed rule intact rather than bypassed.
        (out / "training.log").write_text("step 0 return 1.0\n")

    retained = family.retain(name, fields, out)
    kept = sorted((retained.get("intermediate_checkpoints") or {}).keys())
    assert kept == sorted(written), (
        f"{name}: glob {entry['intermediate_checkpoints']!r} did not match the stamps a run of "
        f"this family writes.\n  wrote: {sorted(written)}\n  kept:  {kept}")
    for item in kept:
        assert (out / "checkpoints" / item).is_file(), f"{name}: {item} not copied into checkpoints/"
    assert (out / "snapshot.pt").is_file(), f"{name}: terminal checkpoint not normalised"
    assert len(set(kept)) == len(kept), f"{name}: stamps collide after copy: {kept}"


# --- the consumer: evaluating the grid where it was produced --------------------------------

def _runner() -> str:
    return (NATIVE / "run_probe.sh").read_text()


def test_curve_eval_exists_is_gated_and_runs_after_retention():
    """Retaining stamps is useless unless something evaluates them, and C95 says where.

    [Claude 2026-09-04] A container-trained checkpoint cannot be validly evaluated on this laptop,
    so the intermediate grid has to be evaluated in the container or not at all. It is also too
    large to bring home: 13 checkpoints per cell at measured sizes is 35.5 GB for 6e5 x 3 seeds
    against ~30 GB free. Both facts point the same way, so the evaluation runs in-job and only the
    records travel -- but it must stay OFF by default, or every training probe starts paying for a
    ten-scene grid per stamp.
    """
    text = _runner()
    assert "run_curve_eval()" in text
    assert 'if [[ "${CURVE_EVAL:-0}" == "1" ]]; then' in text, "must be opt-in"
    retain = text.index('"$FAMILY_TOOL" retain')
    # [Claude 2026-09-06] Was `run_curve_eval "$cell_out"` -- the literal call site moved behind
    # `run_curve_eval_with_policy` (Codex, fail-closed-at-production-scale wrapper; the wrapped
    # `run_curve_eval` function itself is unchanged and still asserted above). Confirmed this is
    # the only change: `run_curve_eval_with_policy` calls `run_curve_eval` as its first action
    # (see tests/test_curve_eval_shell.py for the wrapper's own behavioral coverage), so "retained
    # before evaluated" still means retain must precede this call site.
    call = text.index('run_curve_eval_with_policy "$cell_out"')
    assert retain < call, "stamps must be retained into the cell output before they are evaluated"


def test_curve_records_are_collected_from_the_cell_directories():
    """The records are written per cell; a collector that globs only the job root loses all of them."""
    text = _runner()
    assert '"$out"/cells/*/offline_eval_*.jsonl' in text


def test_ppg_stamps_are_converted_from_save_index_to_frames():
    """ppg names checkpoints by save INDEX (model<N>.jd), not by frame, unlike the other six.

    Recording those rows at frame=N would put ppg's curve on an axis of its own -- 0, 1, 2 -- and
    they would silently plot beside real frame counts.
    """
    text = _runner()
    assert 'if [[ "$family" == "ppg" ]]; then' in text
    assert 'frame="$(ppg_checkpoint_frame' in text
    assert "printf '%s\\n' \"$(( (10#$stamp + 1) * save_every ))\"" in text


def test_the_checkpoint_storage_projection_is_computed_not_guessed():
    """What retaining the weights would cost, from MEASURED checkpoint sizes.

    [Corrected 2026-09-04] This first asserted `total_gb > 30` on the premise that the projection
    exceeded free local disk. The owner cleared space and free disk is **73.1 GB**, so the weights
    would fit -- the premise was withdrawn the day it was written. The design it supported did not
    change, because it rests on C95 (a container-trained checkpoint cannot be validly evaluated
    here at all), not on the size. So this test now pins the arithmetic itself rather than a
    comparison against a moving number: a free-space figure does not belong in a test, and the
    conclusion never needed it.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("_plan", NATIVE / "plan_production.py")
    plan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plan)
    projected = plan.checkpoint_storage_gb(600_000, 50_000, 3)
    assert projected["stamps"] == 13, "12 stamps on the 50k grid, plus the terminal checkpoint"
    assert 30 < projected["total_gb"] < 45, projected["total_gb"]
    assert projected["rows"]["idaac"]["per_cell_gb"] < projected["rows"]["drqv2"]["per_cell_gb"]
