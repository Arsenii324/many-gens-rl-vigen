#!/usr/bin/env python3
"""Which checkpoints do the existing grids name? — helper for `rederive_grids.sh` (C69).

Prints `<snapshot path>|<label>`, one per line, deduplicated by snapshot path.

Kept as a file rather than a heredoc inside the shell script because the script already nests one
heredoc and a second refused to parse. That is a small thing, but the general version of it is
why this repo prefers files over inline snippets: a heredoc cannot be run, tested, or read on its
own.

**The label is the existing grid's stem**, e.g. `cell55k`, `snapshot_100k_frames`. Reusing it
means a re-derived grid lands under the name every document already cites, so a reader comparing
old and new is comparing like with like. Deduplication is by snapshot *path*, so the archived run
that holds three checkpoint files in one directory yields three entries, not one — the failure
the first version of the caller had.

Note this deliberately does NOT deduplicate by content hash: `snapshot.pt` and
`snapshot_100k_frames.pt` are byte-identical (C67), and re-deriving both is how that stays
visible. Collapsing them here would hide the very thing C67 records.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
GRIDS = ROOT / "results" / "regime-retention"


def main() -> int:
    if not GRIDS.is_dir():
        print(f"no grid directory at {GRIDS}", file=sys.stderr)
        return 1
    seen: dict[str, str] = {}
    for p in sorted(GRIDS.glob("*__train.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"unreadable grid {p.name}: {e}", file=sys.stderr)
            continue
        snap = d.get("snapshot")
        if not snap:
            continue  # the random-policy floor has no checkpoint, by design
        seen.setdefault(snap, p.stem.split("__")[0])
    for snap, label in seen.items():
        print(f"{snap}|{label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
