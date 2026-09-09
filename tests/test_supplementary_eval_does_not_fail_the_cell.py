"""A supplementary policy-mode pass must not discard the primary endpoint result.

## The production loss this prevents

`ppg-s1` on `card0-20260909-115331` trained for 3.6 hours and wrote a **complete** native endpoint
grid -- 44 of 44 rows, four regimes by eleven scene sets, later audited clean on every validity
check (800 episode ids, none duplicated, placements paired, resets 200/200 reproducible). The cell
was then marked `NATIVE_CELL_FAILED` because the supplementary `mode` pass died nine seconds in.

`native` is the estimand `family_eval_policy_mode` says the family reports. `mode` is an extra, for
the A25 cross-group pairs. Losing the second is a gap in a supplementary comparison; losing the
first is losing the cell. `run_endpoint_eval` returned 1 for either, so a good primary measurement
was thrown away to signal a missing secondary one.

The distinction is keyed on the pass's **identity**, not its position in
`ENDPOINT_EVAL_POLICY_MODES`, so reordering that variable cannot silently make the supplementary
pass the fatal one.
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


def _harness(tmp_path, modes, fail_on):
    """Run run_endpoint_eval with a stub eval_grid.py that fails for the named policy modes."""
    cell = tmp_path / "cell"
    (cell / "x").parent.mkdir(parents=True, exist_ok=True)
    (cell / "snapshot.pt").write_text("weights")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "eval_grid.py").write_text(textwrap.dedent(f"""
        import sys
        mode = sys.argv[sys.argv.index("--policy-mode") + 1]
        out = sys.argv[sys.argv.index("--out") + 1]
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
        "ENDPOINT_EVAL_REGIMES=train\nENDPOINT_EVAL_SCENES=0\nENDPOINT_EVAL_EPISODES=1\n"
        "ENDPOINT_EVAL_DEVICE=cpu\n"
        + _extract_function("run_endpoint_eval")
        # `run_endpoint_eval` re-enables `set -e` internally, so a bare call would abort this
        # harness before the echo. run_probe.sh:528 invokes it as `... || return 1`; the `|| rc=$?`
        # below is the same set -e-safe shape, and reading $? after a bare call would instead
        # measure the harness's own death.
        + f'\nrc=0\nrun_endpoint_eval "{cell}" ppg ppg 1 600064 || rc=$?\n'
        'echo "RETURNED=$rc"\n'
    )
    proc = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=180)
    return proc.stdout + proc.stderr, cell


def test_a_failing_supplementary_pass_keeps_the_cell(tmp_path):
    output, cell = _harness(tmp_path, "native,mode", fail_on=["mode"])
    assert "RETURNED=0" in output, (
        "a failing `mode` pass still fails the cell, discarding a complete native grid:\n" + output
    )
    assert "NATIVE_ENDPOINT_SUPPLEMENTARY_FAILED" in output
    assert "NATIVE_ENDPOINT_SUPPLEMENTARY_INCOMPLETE" in output
    # ...and the primary result was actually written.
    assert (cell / "offline_eval_endpoint.jsonl").read_text().strip() == '{"policy_mode": "native"}'


def test_a_failing_primary_pass_still_fails_the_cell(tmp_path):
    output, _ = _harness(tmp_path, "native,mode", fail_on=["native"])
    assert "RETURNED=1" in output, "losing the reported estimand must still fail the cell"
    assert "NATIVE_ENDPOINT_EVAL_FAILED" in output


def test_the_split_is_by_identity_not_position(tmp_path):
    """With mode FIRST, mode must still be the non-fatal one."""
    output, _ = _harness(tmp_path, "mode,native", fail_on=["mode"])
    assert "RETURNED=0" in output
    assert "NATIVE_ENDPOINT_SUPPLEMENTARY_FAILED" in output
    assert "NATIVE_ENDPOINT_EVAL_FAILED" not in output


def test_everything_succeeding_is_unchanged(tmp_path):
    output, _ = _harness(tmp_path, "native,mode", fail_on=[])
    assert "RETURNED=0" in output
    assert "SUPPLEMENTARY" not in output
    assert output.count("NATIVE_ENDPOINT_EVAL_COMPLETED") == 2
