"""The supplementary action rule must be executed once, early, not first at the endpoint.

`run_curve_eval` never passes `--policy-mode`, so on `card0-20260909-115331` it exercised ppg's
sampled path 572 times and its `mode` path zero times. The mode path first ran at the ENDPOINT,
after 3.6 hours of training, and died in nine seconds on a defect that one episode would have
surfaced.

The probe therefore runs one episode, one scene, one regime, against the FIRST stamp that exists.
Three properties matter and each has a test:

1. it runs when a supplementary mode is configured, and reports `NATIVE_MODE_PATH_BROKEN`;
2. it runs **once**, not once per stamp -- a per-stamp probe would multiply across a 13-stamp grid;
3. it is **non-fatal**. ppg's native grid was complete and valid; a probe that aborted the cell
   would have destroyed a good primary result to protect a supplementary one.

Its output goes to `mode_path_probe.jsonl`, which `collect_record_delivery`'s `offline_eval_*` glob
does not match: a single episode is a smoke test, never a record.
"""
from __future__ import annotations

import pathlib
import subprocess
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "datasphere" / "native" / "run_probe.sh"


def _extract_function(name: str) -> str:
    source = RUNNER.read_text()
    start = source.index(f"{name}() {{")
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError(f"missing {name}")


def _run(tmp_path, modes, fail_on, stamps=("model_51200.pt", "model_102400.pt")):
    cell = tmp_path / "cell"
    (cell / "checkpoints").mkdir(parents=True)
    for name in stamps:
        (cell / "checkpoints" / name).write_text("weights")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "eval_grid.py").write_text(textwrap.dedent(f"""
        import sys
        argv = sys.argv
        mode = argv[argv.index("--policy-mode") + 1] if "--policy-mode" in argv else "native"
        out = argv[argv.index("--out") + 1]
        if mode in {fail_on!r}:
            sys.stderr.write("stub failure for %s\\n" % mode)
            raise SystemExit(1)
        open(out, "a").write('{{"policy_mode": "%s"}}\\n' % mode)
    """))
    script = tmp_path / "run.sh"
    script.write_text(
        "set -uo pipefail\n"
        f"cd {tmp_path}\n"
        f"ENDPOINT_EVAL_POLICY_MODES={modes}\n"
        "CURVE_EVAL_REGIMES=train\nCURVE_EVAL_SCENES=0\nCURVE_EVAL_EPISODES=1\n"
        "CURVE_EVAL_DEVICE=cpu\n"
        + _extract_function("run_curve_eval")
        + f'\nrc=0\nrun_curve_eval "{cell}" idaac idaac 1 1000 || rc=$?\necho "RETURNED=$rc"\n'
    )
    # stderr INTO stdout, not concatenated after it: the probe reports on stderr and the stamp
    # banners on stdout, so appending one to the other would destroy the interleaving that the
    # "reported at the FIRST stamp" assertion depends on -- and that assertion would then be
    # measuring the harness rather than the runner.
    proc = subprocess.run(["bash", str(script)], stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, timeout=300)
    return proc.stdout, cell


def test_a_broken_mode_path_is_reported_at_the_first_stamp(tmp_path):
    output, cell = _run(tmp_path, "native,mode", fail_on=["mode"])
    assert "NATIVE_MODE_PATH_BROKEN" in output, (
        "the mode path was never exercised during the curve pass:\n" + output
    )
    # Reported before the SECOND stamp is evaluated -- whichever stamp that is.
    #
    # Not `frame=102400`: `for item in "$dir"/*` globs LEXICOGRAPHICALLY, so `model_102400.pt`
    # sorts before `model_51200.pt` and the loop does not visit stamps in frame order. Asserting a
    # numeric order here would have been asserting something the runner never promised.
    begins = [i for i, line in enumerate(output.splitlines())
              if "NATIVE_CURVE_EVAL_BEGIN" in line]
    broken = next(i for i, line in enumerate(output.splitlines())
                  if "NATIVE_MODE_PATH_BROKEN" in line)
    assert len(begins) == 2 and begins[0] < broken < begins[1], (
        "the probe must report after the first stamp and before the second, not once the curve "
        "has finished:\n" + output
    )


def test_the_probe_is_not_fatal(tmp_path):
    output, cell = _run(tmp_path, "native,mode", fail_on=["mode"])
    assert "RETURNED=0" in output, (
        "a broken mode path aborted the curve pass; ppg's complete native grid would have been "
        "destroyed to protect a supplementary comparison:\n" + output
    )
    # ...and every stamp was still evaluated on the native path.
    assert (cell / "offline_eval_curve.jsonl").read_text().count("native") == 2


def test_the_probe_runs_exactly_once(tmp_path):
    output, cell = _run(tmp_path, "native,mode", fail_on=[],
                        stamps=("m_1000.pt", "m_2000.pt", "m_3000.pt", "m_4000.pt"))
    assert output.count("NATIVE_MODE_PATH_PROBE_BEGIN") == 1, (
        "the probe ran per stamp; on a 13-stamp grid that multiplies its cost thirteen-fold"
    )
    assert output.count("NATIVE_MODE_PATH_OK") == 1
    assert (cell / "offline_eval_curve.jsonl").read_text().count("native") == 4


def test_no_probe_when_no_supplementary_mode_is_configured(tmp_path):
    output, cell = _run(tmp_path, "native", fail_on=["mode"])
    assert "NATIVE_MODE_PATH_PROBE_BEGIN" not in output
    assert "RETURNED=0" in output
    assert not (cell / "mode_path_probe.jsonl").exists()


def test_the_probe_never_writes_a_record(tmp_path):
    """Its file must not match collect_record_delivery's `offline_eval_*` glob."""
    _output, cell = _run(tmp_path, "native,mode", fail_on=[])
    assert (cell / "mode_path_probe.jsonl").is_file()
    assert not list(cell.glob("offline_eval_*mode*"))
    # The one probe episode must not have leaked into the curve record. Matching the VALUE, not
    # the bare word: "mode" is a substring of "policy_mode" and would match every native row.
    curve = (cell / "offline_eval_curve.jsonl").read_text()
    assert '"policy_mode": "mode"' not in curve
    assert curve.count('"policy_mode": "native"') == 2
