"""The watch budget must be sized from the grid that will actually run.

[Claude 2026-09-14] The eval grid is decided INSIDE the container by `production_env`; the watch
budget is computed OUTSIDE it, before the container exists. They drifted, and only one governs.

Measured: host defaults imply 2 curve regimes x 2 scene sets and one policy mode = 316 episodes
(1.6 h). `production_env` emits 4 regimes x 11 scene sets over 13 stamps plus a 44-row endpoint at
TWO policy modes = 3,476 episodes (17.4 h). An 11x underestimate. Corroborated by
card0-20260909-115331, whose offline_eval_curve.jsonl holds 572 rows = 13 stamps x 44.

Because EVAL_ALLOWANCE = max(derived, CELL_TIMEOUT), five of twelve baselines -- idaac, ppg,
ibac_sni, ctrl, drqv2, i.e. 15 of 36 cells -- had a watch shorter than their evaluation. A reaped
cell never reaches `collect_record_delivery`, so what is lost is every record of the run, not a
pass. idaac card0-20260909-035152 died exactly this way.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "datasphere" / "native" / "launch-card-cell.sh"
sys.path.insert(0, str(ROOT / "datasphere" / "native"))


def _production_scope(cells="ppg:1"):
    import family
    return family.production_env(cells)


def test_the_descriptor_grid_is_far_larger_than_the_host_defaults():
    """The premise of the fix. If this ever stops holding, the fix is no longer needed."""
    env = _production_scope()
    c_rows = len(env["CURVE_EVAL_REGIMES"].split(",")) * (len(env["CURVE_EVAL_SCENES"].split(",")) + 1)
    e_rows = len(env["ENDPOINT_EVAL_REGIMES"].split(",")) * (len(env["ENDPOINT_EVAL_SCENES"].split(",")) + 1)
    modes = len(env["ENDPOINT_EVAL_POLICY_MODES"].split(","))
    assert c_rows == 44 and e_rows == 44, (c_rows, e_rows)
    assert modes == 2, "the supplementary mode pass doubles endpoint cost and must be budgeted"
    host_c_rows, host_e_rows = 2 * 2, 4 * 2          # the launcher's old defaults
    assert c_rows > host_c_rows * 5 and e_rows > host_e_rows * 5


def test_the_launcher_reads_the_descriptor_rather_than_its_own_defaults():
    source = LAUNCHER.read_text()
    assert "production-env --cells" in source, "the budget no longer asks the descriptor"
    query = source.index("production-env --cells")
    rows = source.index('_c_regimes="$(_csv_count')
    assert query < rows, "the scope must be read BEFORE the row counts are derived"


def test_it_refuses_rather_than_guessing_when_the_descriptor_cannot_be_read():
    """Falling back to host defaults would silently restore the 11x underestimate."""
    source = LAUNCHER.read_text()
    assert "ABORTING: NATIVE_PRODUCTION=1 but production-env could not be read" in source
    assert "exit 4" in source


def test_repo_and_image_are_defined_before_the_budget_needs_them():
    """The query runs in a container; REPO and IMAGE used to be defined below the budget block."""
    source = LAUNCHER.read_text()
    assert source.index('REPO="$(cd') < source.index("production-env --cells")
    assert source.index('IMAGE="${NATIVE_HELPER_IMAGE') < source.index("production-env --cells")


def test_the_launcher_still_parses():
    assert subprocess.run(["bash", "-n", str(LAUNCHER)]).returncode == 0
