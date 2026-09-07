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
