"""Turn one returned result archive into the per-cell numbers a scheduling decision needs.

[Claude 2026-09-02 05:40 MSK] Every audit so far has been done by reading `training.log` by eye and
retyping numbers into a ledger, which is how the FPS/RUB units got mislabelled once already. This
reads the archive instead: for each cell, the measured wall time and high-water marks that GNU
`time -v` printed, the sampled process-tree and GPU envelope, the endpoint the trainer actually
reached, and the completed-frame cost at a declared tier price.

It computes nothing the archive does not contain. In particular it does not guess a charge: it
reports completed frames per second and, only when given `--rub-per-hour`, divides by that rate
and labels the result an estimate.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tarfile
import tempfile
from pathlib import Path


TIME_FIELDS = {
    "wall_clock": re.compile(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s*(\S+)"),
    "max_rss_kib": re.compile(r"Maximum resident set size \(kbytes\):\s*(\d+)"),
    "cpu_percent": re.compile(r"Percent of CPU this job got:\s*(\d+)%"),
    "user_seconds": re.compile(r"User time \(seconds\):\s*([\d.]+)"),
    "system_seconds": re.compile(r"System time \(seconds\):\s*([\d.]+)"),
    "exit_status": re.compile(r"Exit status:\s*(\d+)"),
}
# [Claude 2026-09-02 10:30 MSK: one regex set per logger, because there is one logger per family and
# they are not going to be unified. RL-ViGen prints `| train | F: ... FPS: ...`;
# dmcontrol-generalization-benchmark prints `| train | E: .. | S: .. | D: .. s` and colours it;
# ALDA prints `eval/episode_reward: x`; IDAAC prints baselines-style key/value pairs. Reading each
# on its own terms is the alternative to inventing a schema none of them writes.]
TRAIN_ROW = re.compile(r"\|\s*train\s*\|\s*F:\s*(\d+).*?FPS:\s*([\d.]+)")
EVAL_ROW = re.compile(r"\|\s*eval\s*\|\s*F:\s*(\d+).*?R:\s*([-\d.]+)")
DMCGB_TRAIN_ROW = re.compile(r"\|\s*train\s*\|\s*E:\s*\d+\s*\|\s*S:\s*(\d+)\s*\|\s*D:\s*([\d.]+)\s*s")
DMCGB_EVAL_ROW = re.compile(r"\|\s*eval\s*\|\s*S:\s*(\d+)\s*\|\s*ER:\s*([-\d.]+)\s*\|\s*ERTEST:\s*([-\d.]+)")
ALDA_EVAL_ROW = re.compile(r"alda: (eval/[a-z_]+): ([-\d.]+)")
IDAAC_EVAL_ROW = re.compile(r"test/mean_episode_reward\s*\|\s*([-\d.e+]+)")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
MARKER = re.compile(r"NATIVE_FINAL_EVALUATION_COMPLETED frame=(\d+)")


def parse_clock(text: str) -> float:
    """`9:30.46` and `1:02:03.4` both appear in GNU time output."""
    parts = [float(piece) for piece in text.split(":")]
    seconds = 0.0
    for piece in parts:
        seconds = seconds * 60 + piece
    return seconds


def summarize_log(text: str) -> dict:
    text = ANSI.sub("", text)
    summary: dict[str, object] = {}
    for name, pattern in TIME_FIELDS.items():
        match = pattern.search(text)
        if match:
            summary[name] = match.group(1)
    if "wall_clock" in summary:
        summary["wall_seconds"] = round(parse_clock(str(summary["wall_clock"])), 2)
    marker = MARKER.search(text)
    summary["endpoint_frame"] = int(marker.group(1)) if marker else None
    train_rows = TRAIN_ROW.findall(text)
    if train_rows:
        steady = [float(fps) for _, fps in train_rows[1:]] or [float(train_rows[-1][1])]
        summary["last_train_frame"] = int(train_rows[-1][0])
        summary["steady_state_fps_mean"] = round(sum(steady) / len(steady), 3)
    eval_rows = EVAL_ROW.findall(text)
    if eval_rows:
        summary["evaluations"] = [{"frame": int(frame), "return": float(value)} for frame, value in eval_rows]

    dmcgb_train = DMCGB_TRAIN_ROW.findall(text)
    if dmcgb_train:
        durations = [float(duration) for _, duration in dmcgb_train[1:]] or [float(dmcgb_train[-1][1])]
        summary["last_train_frame"] = int(dmcgb_train[-1][0])
        summary["episode_seconds_mean"] = round(sum(durations) / len(durations), 2)
        # an episode is 500 frames on this task; this is the steady-state rate excluding evaluation
        summary["steady_state_fps_mean"] = round(500 * len(durations) / sum(durations), 3)
    dmcgb_eval = DMCGB_EVAL_ROW.findall(text)
    if dmcgb_eval:
        summary["evaluations"] = [
            {"frame": int(step), "train_regime_return": float(train), "eval_regime_return": float(test)}
            for step, train, test in dmcgb_eval
        ]
    alda_eval = ALDA_EVAL_ROW.findall(text)
    if alda_eval:
        summary["alda_final_metrics"] = {key: float(value) for key, value in alda_eval[-9:]}
    idaac_eval = IDAAC_EVAL_ROW.findall(text)
    if idaac_eval:
        summary["idaac_test_returns"] = [float(value) for value in idaac_eval]
    return summary


def summarize_resources(samples: dict | None) -> dict:
    """Peaks over the sampler's own schema.

    The process-tree RSS is the peak of the per-sample SUM, not the peak of any one process, and
    it is a sum of contemporaneous resident sets rather than an allocation requirement -- shared
    pages are counted once per process. GNU time's `max_rss_kib` is the number to schedule by;
    this one says how the tree is shaped.
    """
    if not samples or not samples.get("samples"):
        return {}
    rows = samples["samples"]

    def peak(values):
        values = [value for value in values if isinstance(value, (int, float))]
        return max(values) if values else None

    return {
        "sample_count": len(rows),
        "peak_process_count": peak(row.get("process_count") for row in rows),
        "peak_thread_total": peak(
            sum(process.get("threads") or 0 for process in row.get("processes") or []) for row in rows
        ),
        "peak_process_tree_rss_kib": peak(
            sum(process.get("rss_kib") or 0 for process in row.get("processes") or []) for row in rows
        ),
        "peak_gpu_process_memory_mib": peak(
            entry.get("used_memory_mib")
            for row in rows
            for entry in row.get("gpu_compute_processes") or []
        ),
        "peak_gpu_device_memory_mib": peak(
            entry.get("used_memory_mib")
            for row in rows
            for entry in row.get("gpu_devices") or []
        ),
        "gpu_total_memory_mib": peak(
            entry.get("total_memory_mib")
            for row in rows
            for entry in row.get("gpu_devices") or []
        ),
        "peak_gpu_utilization_percent": peak(
            entry.get("utilization_gpu_percent")
            for row in rows
            for entry in row.get("gpu_devices") or []
        ),
        "mean_gpu_utilization_percent": (
            round(
                sum(
                    entry.get("utilization_gpu_percent") or 0
                    for row in rows
                    for entry in row.get("gpu_devices") or []
                )
                / max(1, sum(len(row.get("gpu_devices") or []) for row in rows)),
                1,
            )
        ),
        # [Claude 2026-09-10] Added when the run manifest started calling this instead of
        # embedding the raw series. `notes/production-host/27-disk-not-vram-is-what-caps-
        # parallelism.md` is derived from the disk floor, so a summary that dropped it would
        # have made that note unreproducible from a delivered record.
        "min_free_disk_gib": (
            min(
                (row["free_disk_gib"] for row in rows
                 if isinstance(row.get("free_disk_gib"), (int, float))),
                default=None,
            )
        ),
        "sampled_seconds": (
            round(rows[-1]["monotonic_seconds"] - rows[0]["monotonic_seconds"], 1)
            if len(rows) > 1
            and isinstance(rows[0].get("monotonic_seconds"), (int, float))
            and isinstance(rows[-1].get("monotonic_seconds"), (int, float))
            else None
        ),
        # A COUNT, never the identities. On a shared host `gpu_compute_processes` is every
        # user's PID; the scheduling question ("was the card busy?") needs only how many.
        "peak_gpu_compute_process_count": peak(
            len(row.get("gpu_compute_processes") or []) for row in rows
        ),
        "logical_cpu_count": (samples.get("host") or {}).get("logical_cpu_count"),
    }


def _require_supported_delivery(manifest_path: Path, manifest: dict, diagnostic: bool) -> None:
    """Prevent a normal report from silently promoting incomplete native artifacts."""
    if diagnostic:
        return
    if not manifest_path.is_file():
        raise ValueError("run manifest is absent; use --diagnostic for an old artifact")
    kind = manifest.get("execution_kind")
    if kind in {"training_production", "eval_only_validation"}:
        if manifest.get("finalization_schema") != 1:
            raise ValueError(
                f"{kind} manifest has no supported finalization; use --diagnostic for inspection"
            )
        if manifest.get("record_delivery") != "complete":
            raise ValueError(
                f"record delivery is {manifest.get('record_delivery')!r}, not complete; "
                "use --diagnostic for inspection"
            )


def summarize(root: Path, rub_per_hour: float | None, diagnostic: bool = False) -> dict:
    manifest_path = root / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    _require_supported_delivery(manifest_path, manifest, diagnostic)
    report: dict[str, object] = {
        "finalization_schema": manifest.get("finalization_schema"),
        "execution_kind": manifest.get("execution_kind"),
        "record_delivery": manifest.get("record_delivery"),
        "record_artifacts": manifest.get("record_artifacts"),
        "cells_requested": manifest.get("cells_requested") or manifest.get("baselines_requested"),
        "cells_failed": manifest.get("cells_failed") or manifest.get("baselines_failed"),
        "concurrent": manifest.get("concurrent"),
        "frames": manifest.get("frames"),
        "eval_every_frames": manifest.get("eval_every_frames"),
        "eval_episodes": manifest.get("eval_episodes"),
        "eval_scenes": manifest.get("eval_scenes"),
        "environment": manifest.get("environment"),
        "egl": manifest.get("egl"),
        "payload_sha256": manifest.get("payload_sha256"),
        "asset_sha256": manifest.get("asset_sha256"),
        "cells": {},
    }

    cell_dirs = sorted((root / "cells").glob("*")) if (root / "cells").is_dir() else []
    if not cell_dirs and (root / "training.log").is_file():
        cell_dirs = [root]  # a pre-cells archive
    for directory in cell_dirs:
        if not directory.is_dir():
            continue
        log = directory / "training.log"
        entry = summarize_log(log.read_text(errors="replace")) if log.is_file() else {}
        resources = directory / "resources.json"
        entry.update(summarize_resources(json.loads(resources.read_text()) if resources.is_file() else None))
        snapshot = directory / "snapshot.pt"
        entry["snapshot_bytes"] = snapshot.stat().st_size if snapshot.is_file() else 0
        for curve in ("train.csv", "eval.csv", "train.log", "eval.log"):
            path = directory / curve
            if path.is_file():
                entry.setdefault("curves", {})[curve] = max(0, len(path.read_text(errors="replace").splitlines()) - 1)
        # [Claude 2026-09-02 07:55 MSK: only a cell that emitted its endpoint marker has a
        # throughput. Falling back to the requested frame count divided a failed cell's 7-second
        # import crash into 1,351 frames/s and put it in the aggregate.]
        frames = entry.get("endpoint_frame")
        seconds = entry.get("wall_seconds")
        if frames and seconds:
            entry["completed_frames_per_second"] = round(frames / seconds, 4)
            if rub_per_hour:
                entry["estimated_completed_frames_per_rub"] = round(frames / seconds * 3600 / rub_per_hour, 1)
        # a pre-cells archive has one unnamed run; call it by its baseline rather than by the
        # directory the audit happened to extract it into
        name = directory.name
        if name == root.name and manifest.get("baseline"):
            name = f"{manifest['baseline']}-s{manifest.get('seed', '1')}"
        report["cells"][name] = entry

    finished = [entry for entry in report["cells"].values() if entry.get("completed_frames_per_second")]
    if finished:
        report["aggregate_completed_frames_per_second"] = round(
            sum(entry["completed_frames_per_second"] for entry in finished), 4
        )
        if rub_per_hour:
            report["aggregate_estimated_completed_frames_per_rub"] = round(
                report["aggregate_completed_frames_per_second"] * 3600 / rub_per_hour, 1
            )
        report["aggregate_note"] = (
            "aggregate is the sum over cells; it is only a throughput of the JOB when the cells ran concurrently"
        )
    return report


def render(report: dict) -> str:
    lines = []
    environment = report.get("environment") or {}
    egl = (report.get("egl") or {}).get("renderer")
    lines.append(f"gpu={environment.get('gpu')} torch={environment.get('torch')} egl={egl}")
    disk = (environment.get("disk_bytes") or {}).get("/tmp")
    if disk:
        lines.append(
            f"/tmp disk free={disk['free'] / 2 ** 30:.1f} GiB of {disk['total'] / 2 ** 30:.1f} GiB"
        )
    lines.append(
        f"cells requested={report.get('cells_requested')} "
        f"failed={report.get('cells_failed')} concurrent={report.get('concurrent')}"
    )
    header = (
        f"{'cell':<16}{'end':>8}{'wall_s':>9}{'fps':>8}{'cpu':>7}"
        f"{'rssGiB':>8}{'vramMiB':>9}{'snapMiB':>9}  evaluations"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for name, entry in sorted(report.get("cells", {}).items()):
        rss_kib = entry.get("max_rss_kib")
        rss = f"{int(rss_kib) / 2 ** 20:.2f}" if rss_kib else "-"
        snapshot = f"{entry.get('snapshot_bytes', 0) / 2 ** 20:.0f}"
        cpu = f"{entry.get('cpu_percent', '-')}%"
        evaluations = ", ".join(
            (
                f"{item['frame']}:{item['return']:.3f}"
                if "return" in item
                else f"{item['frame']}:train={item['train_regime_return']:.3f}/eval={item['eval_regime_return']:.3f}"
            )
            for item in entry.get("evaluations") or []
        )
        lines.append(
            f"{name:<16}{str(entry.get('endpoint_frame') or '-'):>8}"
            f"{str(entry.get('wall_seconds') or '-'):>9}"
            f"{str(entry.get('completed_frames_per_second') or '-'):>8}"
            f"{cpu:>7}{rss:>8}"
            f"{str(entry.get('peak_gpu_process_memory_mib') or '-'):>9}{snapshot:>9}  {evaluations}"
        )
    if "aggregate_completed_frames_per_second" in report:
        lines.append(
            f"aggregate completed frames/s = {report['aggregate_completed_frames_per_second']}"
            f"  ({report.get('aggregate_note', '')})"
        )
    if "aggregate_estimated_completed_frames_per_rub" in report:
        lines.append(
            f"aggregate estimated completed frames/RUB = "
            f"{report['aggregate_estimated_completed_frames_per_rub']} (estimate, not an invoice)"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, help="result.tgz to read")
    parser.add_argument("--directory", type=Path, help="already-extracted result directory")
    parser.add_argument("--rub-per-hour", type=float, default=None)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument(
        "--diagnostic", action="store_true",
        help="inspect incomplete or old artifacts without treating them as final results",
    )
    args = parser.parse_args(argv)

    if not args.archive and not args.directory:
        print("give --archive or --directory", file=sys.stderr)
        return 2
    try:
        if args.directory:
            report = summarize(args.directory.resolve(), args.rub_per_hour, args.diagnostic)
        else:
            with tempfile.TemporaryDirectory() as scratch:
                with tarfile.open(args.archive) as archive:
                    archive.extractall(scratch)
                report = summarize(Path(scratch), args.rub_per_hour, args.diagnostic)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"summary refused: {error}", file=sys.stderr)
        return 3
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
