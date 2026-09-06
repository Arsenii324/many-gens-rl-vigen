"""Exercise `run_curve_eval`'s shell logic before it ever runs on a paid GPU.

[Claude 2026-09-04] This function decides which frame each intermediate checkpoint is recorded at,
and a wrong frame does not fail -- it silently mislabels an entire curve. It had never executed.
So the function is extracted from `run_probe.sh` and run against real checkpoint filenames, taken
from the jobs that actually produced them (`bt1h3l1rl7v7n4bve0au` returned `model000.jd`,
`model_2048.pt` and `agent-robosuite:Door-idaac-s1_4096.pt`; `bt1791fdh5uctgr1ckhk` returned
`checkpoint_10000.msgpack`), with `python3` stubbed by a shell function so no evaluator is needed.
"""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "datasphere" / "native" / "run_probe.sh"


def _extract(name: str) -> str:
    text = RUNNER.read_text()
    start = text.index(f"{name}() {{")
    depth, i = 0, start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    raise AssertionError(f"{name} not found")


def _run(tmp_path: Path, family: str, filenames: list[str], save_every: int = 2000,
         discard: str = "0") -> tuple[str, list[str], list[str]]:
    cell = tmp_path / "cell"
    (cell / "checkpoints").mkdir(parents=True)
    for name in filenames:
        (cell / "checkpoints" / name).write_bytes(b"weights")
    script = tmp_path / "harness.sh"
    script.write_text(
        "set -euo pipefail\n"
        # stub: record the --frame and --snapshot the function chose, then succeed
        'python3() {\n'
        '  local frame="" snap="" out="" append=0\n'
        '  while [[ $# -gt 0 ]]; do\n'
        '    case "$1" in --frame) frame="$2"; shift 2;; --snapshot) snap="$2"; shift 2;;'
        ' --out) out="$2"; shift 2;; --append) append=1; shift;;'
        ' *) shift;; esac\n'
        '  done\n'
        '  echo "CALLED frame=$frame file=$(basename "$snap")" >> "$LOG"\n'
        '  if [[ "$append" == 1 ]]; then echo "{\\"frame\\":$frame}" >> "$out";'
        ' else echo "{\\"frame\\":$frame}" > "$out"; fi\n'
        "}\n"
        + _extract("ppg_checkpoint_frame") + "\n"
        + _extract("run_curve_eval") + "\n"
        'run_curve_eval "$1" "$2" "$2" 1 "$3"\n')
    log = tmp_path / "calls.log"
    env = {"PATH": "/usr/bin:/bin", "LOG": str(log),
           "CURVE_EVAL_DISCARD_WEIGHTS": discard, "CURVE_EVAL_EPISODES": "3"}
    proc = subprocess.run(["bash", str(script), str(cell), family, str(save_every)],
                          capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    calls = log.read_text().splitlines() if log.exists() else []
    records = (cell / "offline_eval_curve.jsonl").read_text().splitlines()
    return proc.stdout + proc.stderr, calls, records


def test_six_families_take_the_frame_straight_from_the_filename(tmp_path):
    out, calls, _ = _run(tmp_path, "ibac_sni", ["model_2048.pt", "model_4096.pt", "model_10112.pt"])
    frames = sorted(int(re.search(r"frame=(\d+)", c).group(1)) for c in calls)
    assert frames == [2048, 4096, 10112], calls
    assert "NATIVE_CURVE_EVAL_COMPLETED" in out


def test_idaac_names_survive_embedded_digits(tmp_path):
    """`agent-robosuite:Door-idaac-s1_4096.pt` contains a 1 from the seed before the real stamp."""
    _, calls, _ = _run(tmp_path, "idaac", ["agent-robosuite:Door-idaac-s1_4096.pt"])
    assert "frame=4096" in calls[0], calls


def test_ppg_save_index_is_converted_to_frames(tmp_path):
    """ppg names by save index; recorded raw they would plot at 0, 1, 2 beside real frame counts."""
    _, calls, _ = _run(tmp_path, "ppg", ["model000.jd", "model001.jd", "model005.jd"], save_every=2000)
    frames = sorted(int(re.search(r"frame=(\d+)", c).group(1)) for c in calls)
    assert frames == [2000, 4000, 12000], calls


def test_ctrl_msgpack_stamps(tmp_path):
    _, calls, _ = _run(tmp_path, "ctrl", ["checkpoint_10000.msgpack"])
    assert "frame=10000" in calls[0]


def test_weights_are_discarded_only_when_asked(tmp_path):
    cell = tmp_path / "cell"
    _run(tmp_path, "ctrl", ["checkpoint_2000.msgpack"], discard="0")
    assert (cell / "checkpoints" / "checkpoint_2000.msgpack").exists()

    other = tmp_path / "second"
    _run(other, "ctrl", ["checkpoint_2000.msgpack"], discard="1")
    assert not (other / "cell" / "checkpoints" / "checkpoint_2000.msgpack").exists(), \
        "CURVE_EVAL_DISCARD_WEIGHTS=1 must remove an evaluated intermediate"


def test_every_checkpoint_record_survives_the_curve(tmp_path):
    """Each evaluator process defaults to truncation; the runner must explicitly append."""
    _, _, records = _run(tmp_path, "rad", ["2500.pt", "5000.pt", "7500.pt"])
    assert records == ['{"frame":2500}', '{"frame":5000}', '{"frame":7500}']


def test_missing_checkpoint_directory_is_insufficient(tmp_path):
    """No checkpoint directory is an incomplete requested curve, not a successful curve."""
    cell = tmp_path / "cell"
    cell.mkdir(parents=True)
    script = tmp_path / "h.sh"
    script.write_text("set -euo pipefail\n" + _extract("run_curve_eval") +
                      '\nrun_curve_eval "$1" ctrl ctrl 1 2000\n')
    proc = subprocess.run(["bash", str(script), str(cell)], capture_output=True, text=True)
    assert proc.returncode != 0
    assert "NATIVE_CURVE_EVAL_NO_STAMPS" in proc.stderr


def test_zero_usable_stamps_is_insufficient(tmp_path):
    """A nonempty directory with no parseable checkpoint stamp must also fail closed."""
    cell = tmp_path / "cell"
    (cell / "checkpoints").mkdir(parents=True)
    (cell / "checkpoints" / "checkpoint-final.pt").write_bytes(b"weights")
    script = tmp_path / "h.sh"
    script.write_text("set -euo pipefail\n" + _extract("run_curve_eval") +
                      '\nrun_curve_eval "$1" ctrl ctrl 1 2000\n')
    proc = subprocess.run(["bash", str(script), str(cell)], capture_output=True, text=True)
    assert proc.returncode != 0
    assert "NATIVE_CURVE_EVAL_NO_STAMPS" in proc.stderr


@pytest.mark.parametrize("endpoint,expected", [("1", "fatal"), ("0", "tolerated")])
def test_curve_caller_applies_production_strictness_but_tolerates_exploration(
        tmp_path, endpoint, expected):
    cell = tmp_path / "cell"
    cell.mkdir(parents=True)
    script = tmp_path / "h.sh"
    script.write_text(
        "set -euo pipefail\n"
        + _extract("run_curve_eval") + "\n"
        + _extract("run_curve_eval_with_policy") + "\n"
        + 'ENDPOINT_EVAL="$1" run_curve_eval_with_policy "$2" ctrl ctrl 1 2000\n'
    )
    proc = subprocess.run(
        ["bash", str(script), endpoint, str(cell)], capture_output=True, text=True,
    )
    if expected == "fatal":
        assert proc.returncode != 0
        assert "NATIVE_CURVE_EVAL_FATAL" in proc.stderr
    else:
        assert proc.returncode == 0
        assert "NATIVE_CURVE_EVAL_TOLERATED" in proc.stderr


def test_offline_eval_selects_its_family_for_dependency_bootstrap():
    """An eval-only ALDA job must install ALDA dependencies before importing its evaluator."""
    text = RUNNER.read_text()
    assert 'cells="${CELLS:-${BASELINES:-${BASELINE:-${OFFLINE_EVAL_FAMILY:-drqv2}}}}"' in text


def test_ppg_curve_uses_interaction_count_logged_at_save(tmp_path):
    """PPG save filenames are indices; the save log carries their actual x-axis."""
    cell = tmp_path / "cell"
    cell.mkdir()
    (cell / "training.log").write_text(
        "Saving to /tmp/model000.jd IC=0\n"
        "Saving to /tmp/model001.jd IC=4096\n"
        "Saving to /tmp/model002.jd IC=6144\n"
    )
    helper = _extract("ppg_checkpoint_frame")
    script = tmp_path / "h.sh"
    script.write_text("set -euo pipefail\n" + helper +
                      '\nprintf "%s\\n" "$(ppg_checkpoint_frame "$1" 1 2000)"\n')
    r = subprocess.run(["bash", str(script), str(cell)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "4096", r.stdout + r.stderr
