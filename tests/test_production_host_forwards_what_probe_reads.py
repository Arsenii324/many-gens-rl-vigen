"""Every variable `run_probe.sh` reads must reach it on the production host.

The forwarding list in `run_on_production_host.sh` is hand-maintained, and its own comment records
two occasions where it had already fallen behind: `NATIVE_PRODUCTION` missing (every
production-scale cell would have died after paying the container bootstrap) and `NATIVE_CONCURRENT`
missing (cell packing silently disabled). A third round found 25 more, including
`NATIVE_PLACES365_SPLIT` -- the A22 production decision, unreachable on the host without it.

Derived, not hand-listed: a variable added to the runner is checked the day it is added.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE = ROOT / "datasphere" / "native" / "run_probe.sh"
WRAPPER = ROOT / "datasphere" / "native" / "run_on_production_host.sh"

#: Read by run_probe.sh but deliberately not forwarded, each for a stated reason.
NOT_FORWARDED = {
    # The wrapper sets this itself, to the in-container path of the archive it copied in.
    "RLVIGEN_ARCHIVE",
}

PREFIXES = (
    "NATIVE_", "ENDPOINT_", "OFFLINE_", "CURVE_", "PLACES365", "RLVIGEN_", "CELL_",
    "EVAL_", "SAVE_", "CELLS", "FRAMES", "TASK", "SEED", "RECORDS",
)


def _read_by_probe() -> set[str]:
    text = PROBE.read_text()
    names = set(re.findall(r"\$\{([A-Z][A-Z0-9_]{2,})(?::[-?=]|\})", text))
    return {name for name in names if name.startswith(PREFIXES)}


def _forwarded_by_wrapper() -> set[str]:
    text = WRAPPER.read_text()
    match = re.search(r"for name in ([A-Z][\s\S]*?); do", text)
    assert match, "could not find the forwarding list in run_on_production_host.sh"
    return set(re.findall(r"[A-Z][A-Z0-9_]+", match.group(1)))


def test_wrapper_forwards_every_variable_the_runner_reads():
    missing = sorted(_read_by_probe() - _forwarded_by_wrapper() - NOT_FORWARDED)
    assert not missing, (
        "run_on_production_host.sh does not forward these, so they cannot be set on the "
        f"production host: {missing}")


def test_rlvigen_archive_is_supplied_as_environment_not_position():
    """run_probe.sh's third positional is Places365; RL-ViGen arrives by environment."""
    text = WRAPPER.read_text()
    assert 'RLVIGEN_ARCHIVE=/work/rlvigen.tgz' in text
    assert '/work/places365.tgz' in text


def test_thread_pool_limits_are_forwardable():
    """External review 25: unforwarded OMP/MKL limits let every process pick its own default."""
    forwarded = _forwarded_by_wrapper()
    assert {"OMP_NUM_THREADS", "MKL_NUM_THREADS"} <= forwarded


def test_production_scale_refuses_without_a_per_cell_ceiling():
    """A stuck cell must not be able to burn the job and take the result archive with it.

    The archive is written LAST, so a job-level cutoff loses every completed cell's evidence.
    `run_probe.sh` caps a cell only when `CELL_TIMEOUT_SECONDS` is set, and silently does not cap
    when it is absent (external recommendation 22). The VALUE needs the host throughput
    measurement, so the wrapper refuses rather than inventing one -- the decision is forced to be
    made, the number still comes from measurement.
    """
    text = WRAPPER.read_text()
    assert "CELL_TIMEOUT_SECONDS is unset" in text, (
        "a production-scale run with no per-cell ceiling must be refused, not accepted silently")
    # Inside the production-scale block, beside the other two refusals.
    block = text[text.index('if [[ "${FRAMES:-10000}" -ge 600000 ]]; then'):]
    block = block[:block.index("\nfi\n")]
    for required in ("NATIVE_PRODUCTION", "NATIVE_HOST_PROFILE", "CELL_TIMEOUT_SECONDS"):
        assert required in block, f"{required} refusal is not in the production-scale guard"
