"""Sample the native calibration process tree without adding a monitoring dependency."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import time
from pathlib import Path


def command(*args: str) -> str:
    try:
        completed = subprocess.run(args, text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def linux_processes(root_pid: int) -> list[int]:
    parents: dict[int, list[int]] = {}
    for status in Path("/proc").glob("[0-9]*/status"):
        try:
            fields = dict(
                line.split(":", 1) for line in status.read_text(errors="replace").splitlines() if ":" in line
            )
            parents.setdefault(int(fields["PPid"].strip()), []).append(int(status.parent.name))
        except (KeyError, ValueError, OSError):
            continue
    found = [root_pid]
    for parent in found:
        found.extend(parents.get(parent, []))
    return found


def is_live(pid: int) -> bool:
    if platform.system() == "Linux":
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().split()
            return fields[2] != "Z"
        except OSError:
            return False
    state = command("ps", "-o", "stat=", "-p", str(pid))
    return bool(state) and "Z" not in state


def linux_process(pid: int) -> dict[str, object] | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text().split()
        status = dict(
            line.split(":", 1) for line in Path(f"/proc/{pid}/status").read_text().splitlines() if ":" in line
        )
    except (KeyError, OSError, ValueError):
        return None
    return {
        "pid": pid,
        "cpu_seconds": (int(stat[13]) + int(stat[14])) / os.sysconf(os.sysconf_names["SC_CLK_TCK"]),
        "last_cpu": int(stat[38]),
        "rss_kib": int(status.get("VmRSS", "0 kB").split()[0]),
        "hwm_kib": int(status.get("VmHWM", "0 kB").split()[0]),
        "threads": int(status.get("Threads", "0").strip()),
    }


def portable_process(pid: int) -> dict[str, object] | None:
    if platform.system() == "Linux":
        return linux_process(pid)
    fields = command("ps", "-o", "pid=", "-o", "rss=", "-o", "pcpu=", "-p", str(pid)).split()
    if len(fields) != 3:
        return None
    return {
        "pid": int(fields[0]),
        "rss_kib": int(fields[1]),
        # [Codex 2026-09-01 20:34 MSK: normalize macOS ps locale decimals so host-only telemetry parsing stays portable]
        "cpu_percent": float(fields[2].replace(",", ".")),
        "threads": None,
    }


def parse_gpu_devices(raw: str) -> list[dict[str, object]]:
    devices = []
    for line in raw.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 5:
            continue
        try:
            devices.append(
                {
                    "gpu_uuid": parts[0],
                    "utilization_gpu_percent": int(parts[1]),
                    "utilization_memory_percent": int(parts[2]),
                    "used_memory_mib": int(parts[3]),
                    "total_memory_mib": int(parts[4]),
                }
            )
        except ValueError:
            continue
    return devices


# [Codex 2026-09-01 10:07 MSK: sample device load as well as per-process VRAM for tier decisions]
def gpu_devices() -> list[dict[str, object]]:
    raw = command(
        "nvidia-smi",
        "--query-gpu=uuid,utilization.gpu,utilization.memory,memory.used,memory.total",
        "--format=csv,noheader,nounits",
    )
    return parse_gpu_devices(raw)


def gpu_compute_processes() -> list[dict[str, object]]:
    raw = command(
        "nvidia-smi",
        "--query-compute-apps=pid,used_memory,gpu_uuid",
        "--format=csv,noheader,nounits",
    )
    result = []
    for line in raw.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 3 and parts[0].isdigit():
            result.append({"pid": int(parts[0]), "used_memory_mib": int(parts[1]), "gpu_uuid": parts[2]})
    return result


def topology() -> dict[str, object]:
    try:
        affinity = sorted(os.sched_getaffinity(0))
    except AttributeError:
        affinity = list(range(os.cpu_count() or 1))
    return {
        "system": platform.system(),
        "machine": platform.machine(),
        "logical_cpu_count": os.cpu_count() or 1,
        "affinity": affinity,
        "lscpu_json": command("lscpu", "--json") if platform.system() == "Linux" else "",
    }


def sample(root_pid: int) -> dict[str, object]:
    pids = linux_processes(root_pid) if platform.system() == "Linux" else [root_pid]
    processes = [entry for pid in pids if (entry := portable_process(pid)) is not None]
    return {
        "monotonic_seconds": time.monotonic(),
        "process_count": len(processes),
        "processes": processes,
        "gpu_devices": gpu_devices(),
        "gpu_compute_processes": gpu_compute_processes(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval-seconds", type=float, default=1.0)
    parser.add_argument(
        "--ready-file",
        type=Path,
        help="touch after the first sample, so a launcher can start the measured child only then",
    )
    args = parser.parse_args()
    if args.interval_seconds <= 0:
        parser.error("--interval-seconds must be positive")
    samples = []
    while is_live(args.pid):
        samples.append(sample(args.pid))
        if args.ready_file is not None and not args.ready_file.exists():
            args.ready_file.touch()
        time.sleep(args.interval_seconds)
    args.output.write_text(json.dumps({"host": topology(), "root_pid": args.pid, "samples": samples}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
