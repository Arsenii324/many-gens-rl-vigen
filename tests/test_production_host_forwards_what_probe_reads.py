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


def test_production_scale_requires_a_verified_second_device_for_results():
    """A 45-hour cell's results must not live on exactly one volume.

    Both `/tmp/native-out` and `/tmp/native-work` are already host-mounted, so checkpoints are
    durable as written -- that half closed on 2026-09-07. This is the other half: the host volume
    itself. The campaign is ~893 GPU-hours and a soda cell alone is ~45.

    The load-bearing part is that the second device is VERIFIED to be a second device. Requiring a
    path and trusting the operator to pick a different volume manufactures assurance without
    evidence, which is the failure mode this project keeps finding in its own checks. So the
    filesystem ids are compared and an unreadable id refuses rather than passes.
    """
    text = WRAPPER.read_text()
    block = text[text.index('if [[ "${FRAMES:-10000}" -ge 600000 ]]; then'):]
    block = block[:block.index("\nfi\n")]
    assert "NATIVE_RESULT_MIRROR is unset" in block, (
        "production scale must refuse without a second location for results")
    assert "stat -f -c %i" in block, "the mirror must be verified to be a different filesystem"
    assert "SAME filesystem" in block, "a same-device mirror must be refused, not warned about"
    assert "cannot be verified and must not be assumed" in block, (
        "an unreadable filesystem id must refuse; passing on it is the assurance-without-evidence "
        "failure this check exists to avoid")


def test_the_mirror_is_actually_written_and_reported():
    """A refusal that forces a variable but never copies anything would be pure ceremony."""
    text = WRAPPER.read_text()
    assert 'cp "$RESULT" "$NATIVE_RESULT_MIRROR/"' in text
    assert "mirrored:" in text, "the operator must be able to see that it happened"
    # [2026-09-08, external review 27 sec.13] A failed copy must be FATAL, not a warning.
    # Production scale refuses to start without a mirror, so a requirement whose failure is a log
    # line nobody greps is not a requirement -- the operator would believe two copies existed.
    assert "NATIVE_RESULT_MIRROR copy to" in text and "did not succeed" in text, (
        "a mirror that silently did not run is worse than none, because it is believed")
    block = text[text.index('if [[ -n "${NATIVE_RESULT_MIRROR:-}" ]]; then'):]
    block = block[:block.index("\nfi\n")]
    assert "exit 4" in block, (
        "a failed mirror must leave a non-zero result state; warning and exiting 0 makes the "
        "production-scale requirement theatre")


def test_concurrent_cuda_cells_fail_closed_without_a_device_map():
    """External review 27 §12: an absent device map is a silent collision on a multi-GPU host.

    With `NATIVE_CONCURRENT=1` and no `NATIVE_CELL_DEVICES`, every cell launches unpinned, so each
    CUDA process sees all GPUs and independently picks `cuda:0`. The launch looks correct; the
    symptom is one device at double memory and the rest idle, which is the packing buying nothing
    it was run for.

    The refusal is deliberately scoped: DataSphere tiers have ONE GPU and packing co_schedulable
    families onto it is the intended behaviour with nothing to assign. Refusing there would break
    the probe path for no gain, so the check fires only when more than one GPU is visible.
    """
    text = PROBE.read_text()
    assert "REFUSING: NATIVE_CONCURRENT=1 with" in text, (
        "concurrent CUDA cells with no device map must refuse on a multi-GPU host")
    assert "nvidia-smi -L" in text, (
        "the refusal must be conditioned on the GPUs actually visible, or it breaks single-GPU "
        "DataSphere packing that is intended")
    assert "repeats a device index" in text, (
        "a device list with duplicates puts two cells on one GPU silently")
