"""The run manifest's resource field must not grow with the run, and must name nobody.

## The defect this pins

`run_probe.sh` built the manifest with `"resource_samples": read_json(resources.json)` -- the
sampler's entire per-second series, inlined. `collect_record_delivery` then stamps that manifest
onto EVERY delivered row. On `card0-20260909-115331` (ppg, 3.6 h) the series reached 2,173,638
bytes and 616 rows carried it, giving a **1,365,573,627-byte `records_delivery.jsonl` for 964
rows** -- roughly 1.4 MB per row, of which about 8 KB was the record.

`collect-host-run.sh` had measured this field once, at "roughly 231 KB per row", against a short
cell. That number was true when written and was never re-checked against a production-length run.
So the failure is not that someone chose a bad size; it is that the size was a function of run
duration and nothing said so.

## Why these two properties and not a size threshold

A threshold ("under 100 KB") would have passed every short cell and failed only in production,
which is exactly the trap the original measurement fell into. The properties below hold at every
duration:

1. **Bounded.** A 100x longer series must not make a larger summary. This is the actual defect:
   size proportional to duration. A 45-hour cell would have carried ~160,000 samples per row.
2. **Names nobody.** `gpu_compute_processes` comes from `nvidia-smi --query-compute-apps=pid,...`,
   which on a SHARED host lists every user's PIDs and GPU memory -- nine distinct foreign PIDs in
   that run. Publishing those into every record of a results repository is not something a size
   fix should be allowed to reintroduce.

The scheduling signal survives as `peak_gpu_compute_process_count`: a count answers "was the card
busy?" without publishing whose job it was.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "datasphere" / "native"))

FOREIGN_PIDS = [864779, 890455, 890470, 890631, 895931, 923336, 949001, 974761, 1105459]


def series(samples: int) -> dict:
    """A resources.json shaped exactly like the sampler's, with foreign GPU processes in it."""
    return {
        "host": {"logical_cpu_count": 16},
        "root_pid": 3732,
        "samples": [
            {
                "monotonic_seconds": float(i),
                "free_disk_gib": 277.27 - i * 0.0001,
                "process_count": 5,
                "processes": [
                    {"pid": 3732, "rss_kib": 3172, "hwm_kib": 3172, "threads": 1,
                     "cpu_seconds": 0.03, "last_cpu": 8},
                ],
                "gpu_devices": [
                    {"gpu_uuid": "GPU-8b832400", "used_memory_mib": 28355,
                     "total_memory_mib": 32768, "utilization_gpu_percent": 100},
                ],
                "gpu_compute_processes": [
                    {"pid": pid, "used_memory_mib": 308, "gpu_uuid": "GPU-8b832400"}
                    for pid in FOREIGN_PIDS[: 1 + i % 4]
                ],
            }
            for i in range(samples)
        ],
    }


def test_summary_size_does_not_grow_with_run_duration():
    from summarize_result import summarize_resources
    short = len(json.dumps(summarize_resources(series(10))))
    long = len(json.dumps(summarize_resources(series(10_000))))
    # Only the sample_count digits may differ; nothing may scale with the series.
    assert long - short < 64, (
        f"summary grew {short} -> {long} bytes for a 1000x longer run. This field is stamped on "
        f"every delivered row, so anything proportional to duration multiplies across the bundle "
        f"-- that is what made records_delivery.jsonl 1.27 GiB."
    )


def test_summary_names_no_process():
    from summarize_result import summarize_resources
    blob = json.dumps(summarize_resources(series(500)))
    for pid in FOREIGN_PIDS:
        assert str(pid) not in blob, (
            f"PID {pid} reached the summary. On a shared host these are other users' jobs, and "
            f"this value is copied into every published record."
        )
    assert "pid" not in blob and "processes" not in blob
    # ...while the scheduling signal itself is kept.
    assert summarize_resources(series(500))["peak_gpu_compute_process_count"] == 4


def test_the_manifest_stores_the_summary_and_not_the_series():
    """Anchored on run_probe.sh's own text: the regression is one word wide."""
    text = (ROOT / "datasphere" / "native" / "run_probe.sh").read_text()
    assert 'read_json(directory / "resources.json")' not in text, (
        "the run manifest is inlining the raw sampler series again"
    )
    assert 'resource_summary(directory / "resources.json")' in text


def test_the_summary_keeps_what_the_host_notes_are_derived_from():
    """A summary that dropped these would make committed notes unreproducible from a record."""
    from summarize_result import summarize_resources
    summary = summarize_resources(series(100))
    for field in ("peak_process_tree_rss_kib",          # note 22, what a cell actually uses
                  "peak_gpu_process_memory_mib",        # note 26, the VRAM cap
                  "min_free_disk_gib",                  # note 27, disk caps parallelism
                  "sampled_seconds",                    # note 25/28, the train/eval split
                  "peak_gpu_compute_process_count"):    # note 24, what a yield costs
        assert summary.get(field) is not None, f"{field} missing from the resource summary"


def test_real_artifact_if_present():
    """If the 2.17 MB artifact from the failing run is on this machine, use it, not a fixture."""
    real = pathlib.Path("/Users/a2mogus/.claude/jobs/d037da9e/tmp/ppg-resources-real.json")
    if not real.is_file():
        pytest.skip("the real resources.json is not on this machine")
    from summarize_result import summarize_resources
    raw = json.loads(real.read_text())
    summary = summarize_resources(raw)
    assert len(json.dumps(raw)) > 2_000_000
    assert len(json.dumps(summary)) < 1_000
    blob = json.dumps(summary)
    observed = {g.get("pid") for r in raw["samples"] for g in (r.get("gpu_compute_processes") or [])}
    assert observed, "the real artifact should contain GPU compute processes"
    assert not [p for p in observed if p and str(p) in blob]
