#!/usr/bin/env python3
"""Keep `runnable/_patches/*.patch` reproducing the clones they claim to reproduce.

    python scripts/refresh_clone_patches.py --check     # is any snapshot stale?
    python scripts/refresh_clone_patches.py             # rewrite the stale ones

## Why this exists

`RECOVERY-HANDOFF.md:30` states that the clones "are reproducible from `ext/` plus
`runnable/_patches/*.patch`". That is the project's stated recovery path, and **nothing checked it**.
`setup/apply_patches.py` does not apply these files -- it patches the vendored RL-ViGen tree -- so
they are provenance snapshots, and a snapshot nobody re-derives drifts silently the first time a
clone is edited.

On 2026-09-05 two clone edits made it drift: idaac's regime read-back and ctrl's regime hoist, both
of which unblocked families that could not be evaluated at all. Without this, the recovery path
would have quietly stopped reproducing the tree that produced the results.

## What it does NOT do

It does not decide whether a clone edit was correct, and it is not a substitute for
`scripts/deviations.py`, which counts and characterises the deviations. This only keeps the stored
diff equal to the live one.
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATCHES = ROOT / "runnable" / "_patches"
SOURCE_OF = {
    "alda": "ext/ALDA_Official",
    "dmc_gb": "ext/dmcontrol-generalization-benchmark",
    "ppg": "ext/phasic-policy-gradient",
    "idaac": "ext/idaac",
    "ibac_sni": "ext/IBAC-SNI",
    "ctrl": "ext/ctrl_public",
}


def patched_files(patch: pathlib.Path) -> list[str]:
    """The paths the stored snapshot covers, in its own order."""
    # Parse the `+++ b/<path>` lines, not `diff --git a/...`. A NEW file's header reads
    # `diff --git b/x b/x` (its source is /dev/null), so an `a/`-only parser silently dropped it --
    # alda's specs/train_alda_robosuite_door.yaml -- and regeneration then deleted that entry and
    # never converged. The `+++` line is present for every entry, added or modified.
    names = []
    for line in patch.read_text(errors="replace").splitlines():
        if line.startswith("+++ ") and not line.startswith("+++ /dev/null"):
            name = line[4:].strip()
            if name.startswith("b/"):
                name = name[2:]
            if name not in names:
                names.append(name)
    return names


def one_diff(source: pathlib.Path, clone: pathlib.Path, relative: str) -> str:
    """`git diff --no-index` works outside a repository, which is what ext/ and runnable/ are."""
    left, right = source / relative, clone / relative
    if not right.is_file():
        return ""
    # `--no-prefix` so git prints the paths it was given verbatim; the a/ and b/ prefixes are then
    # added by the rewrite below. Passing --src-prefix here instead produced `aa/` and `bb/`,
    # which made all six snapshots look stale -- an artifact that would have overwritten six
    # provenance files had it not been compared against an UNTOUCHED family first.
    proc = subprocess.run(
        ["git", "diff", "--no-index", "--no-prefix",
         str(left) if left.is_file() else "/dev/null", str(right)],
        capture_output=True, text=True)
    # git exits 1 when files differ; anything above that is a real failure and must not read as
    # "no difference" -- an instrument that cannot run must never look like one that passed.
    if proc.returncode > 1:
        raise RuntimeError(f"git diff failed for {relative}: {proc.stderr.strip()[:200]}")
    body = proc.stdout
    # Rewrite the paths git prints into the clone-relative ones the stored snapshots use. With
    # --no-prefix git also drops the LEADING SLASH of an absolute path, so both spellings have to
    # be handled -- matching only the slashed form silently left every path unrewritten.
    for original, replacement in ((str(left), f"a/{relative}"), (str(right), f"b/{relative}")):
        body = body.replace(original, replacement).replace(original.lstrip("/"), replacement)
    # A file that exists only in the clone has no source, so git names the destination on both
    # sides of the header. Real `git diff` inside a repository writes `a/x b/x` for an addition, so
    # normalise to that -- otherwise the regenerated snapshot never equals the stored one and the
    # checker reports a permanent, uncloseable staleness.
    if not left.is_file():
        body = body.replace(f"diff --git b/{relative} b/{relative}",
                            f"diff --git a/{relative} b/{relative}", 1)
    return body


def rebuild(family: str) -> str:
    source = ROOT / SOURCE_OF[family]
    clone = ROOT / "runnable" / family
    patch = PATCHES / f"{family}.patch"
    return "".join(one_diff(source, clone, name) for name in patched_files(patch))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="report staleness, write nothing")
    args = ap.parse_args()

    stale, missing = [], []
    for family in sorted(SOURCE_OF):
        patch = PATCHES / f"{family}.patch"
        if not patch.is_file():
            continue
        if not (ROOT / SOURCE_OF[family]).is_dir():
            missing.append(family)
            continue
        current, stored = rebuild(family), patch.read_text(errors="replace")
        if current.strip() != stored.strip():
            stale.append(family)
            if not args.check:
                patch.write_text(current)

    for family in sorted(SOURCE_OF):
        mark = ("MISSING SOURCE" if family in missing
                else ("STALE" if family in stale else "current"))
        print(f"  {family:10} {mark}")
    if missing:
        print(f"\n  {len(missing)} family/families have no ext/ source here, so their snapshot could")
        print("  not be checked. That is NOT a pass -- re-run where ext/ holds the real clones.")
    if stale:
        verb = "are stale" if args.check else "were rewritten"
        print(f"\n  {len(stale)} snapshot(s) {verb}: {', '.join(stale)}")
        if args.check:
            print("  RECOVERY-HANDOFF.md says the clones are reproducible from ext/ plus these")
            print("  files. While one is stale, that claim is false. Run without --check to fix.")
    return 1 if (stale and args.check) else 0


if __name__ == "__main__":
    raise SystemExit(main())
