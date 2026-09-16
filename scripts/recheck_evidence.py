#!/usr/bin/env python3
"""Re-hash the sources behind every evidence bundle and say which still match.

    python scripts/recheck_evidence.py                 # every bundle
    python scripts/recheck_evidence.py ppg-aux-phase-8-minibatches-per-epoch
    python scripts/recheck_evidence.py --local-only    # skip the host

For each excerpt in `results/evidence/*/manifest.json`:

* `SAME`   -- the source still exists with the hash recorded at capture time;
* `DRIFT`  -- it exists with a different hash (a repo file was edited, a log was appended to).
  The excerpt is still what the source said THEN; whether the claim survives the change is a
  question for CLAIM.md, not for this script;
* `GONE`   -- the source no longer exists. The excerpt is now the only copy;
* `INPUTS` -- a local command whose named repo inputs changed since capture;
* `HEAD`   -- a local command with no named inputs; only the repo head was recorded.

Tests do not call this: the host is not always reachable, and a drifted source is information,
not a failure. On the host it runs `test`, `stat` and `sha256sum` only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from capture_host_evidence import EVIDENCE, SSH, _hashes_command, _host_path, _q  # noqa: E402


def _host_hashes(paths: list[str]) -> dict[str, str | None]:
    if not paths:
        return {}
    script = "; ".join(
        f"if test -e {_q(_host_path(p))}; then sha256sum {_q(_host_path(p))} | cut -d' ' -f1; else echo GONE; fi"
        for p in paths)
    proc = subprocess.run(SSH + [script], capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise SystemExit(f"host unreachable or refused ({proc.returncode}): {proc.stderr.strip()[-300:]}")
    lines = proc.stdout.strip().splitlines()
    return {p: (None if line == "GONE" else line) for p, line in zip(paths, lines)}


def _local_hash(rel: str) -> str | None:
    path = ROOT / rel
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("slugs", nargs="*")
    ap.add_argument("--local-only", action="store_true")
    args = ap.parse_args()

    bundles = [EVIDENCE / s for s in args.slugs] or sorted(p for p in EVIDENCE.iterdir() if p.is_dir())
    manifests = {b.name: json.loads((b / "manifest.json").read_text()) for b in bundles}
    host_paths = sorted({e["source"]["path"] for m in manifests.values() for e in m["excerpts"].values()
                         if e["source"]["kind"] == "host-file"})
    host = {} if args.local_only else _host_hashes(host_paths)

    counts: dict[str, int] = {}
    for slug, manifest in manifests.items():
        print(f"== {slug}")
        for name, entry in manifest["excerpts"].items():
            src = entry["source"]
            if src["kind"] == "host-dir-hashes":
                if args.local_only:
                    status = "SKIPPED"
                else:
                    listing = subprocess.run(
                        SSH + [_hashes_command(argparse.Namespace(host_hashes=src["path"], name_glob=src["glob"]))],
                        capture_output=True, text=True, timeout=600)
                    now = hashlib.sha256(listing.stdout.encode()).hexdigest() if listing.returncode == 0 else None
                    status = "GONE" if now is None else ("SAME" if now == src["listing_sha256"] else "DRIFT")
            elif src["kind"] == "host-file":
                if args.local_only:
                    status = "SKIPPED"
                else:
                    now = host[src["path"]]
                    status = "GONE" if now is None else ("SAME" if now == src["sha256"] else "DRIFT")
            elif src["kind"] == "repo-file":
                now = _local_hash(src["path"])
                status = "GONE" if now is None else ("SAME" if now == src["sha256"] else "DRIFT")
            else:
                inputs = src.get("inputs") or {}
                changed = [k for k, v in inputs.items() if _local_hash(k) != v]
                status = ("INPUTS" if changed else "SAME") if inputs else "HEAD"
                if changed:
                    status += " " + ",".join(changed)
            counts[status.split()[0]] = counts.get(status.split()[0], 0) + 1
            print(f"  {status:<8} {name}  <- {src.get('path') or src.get('command', '')[:70]}")
    print("summary:", "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
