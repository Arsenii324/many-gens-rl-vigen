#!/usr/bin/env python3
"""Declared, executed, observed — the observation geometry of all twelve, in one table.

## Why this exists

Frame stack and render size are the axis most often quoted wrongly in this project's own
documents, and the reason is that answering "what does this baseline actually run at" took five
steps: read `OBSERVATION_GEOMETRY`, check whether `family.py` passes a flag, check whether the
launcher defaults one, check whether `eval_grid.py` reads the table or a CLI value, and then find
a record to see what was stamped. Every one of those links has been wrong at some point:

  - `eval_grid.py`'s `--frame-stack`/`--image-size` defaulted to dmc_gb's `100/3` and
    `run_probe.sh` passed neither, so EVERY family's `evaluator_scope` was stamped with dmc_gb's
    geometry. Records from before 2026-09-07 carry `(3, 100)` for baselines that never ran at it.
  - `rad`'s declared 100x100 was not what the robosuite env produced, because the eval paths never
    set `RLVIGEN_IMAGE_SIZE`; the runtime check caught it as "expected ... 100x100, observed
    (9, 84, 84)".
  - README described the split as 8/4 long after IDAAC's frame-stack move made it 10/2.

Each was found by tracing by hand. This prints the whole chain instead, so the next reader — or
the next review — starts from an answer rather than a reconstruction.

## What each column means

  declared   `rlgen/protocol.py::OBSERVATION_GEOMETRY` -- the single source of truth
  argv       what `family.py command` actually passes, if it passes anything. Blank means the
             family takes its own clone's default, which is legitimate: the RUNTIME check below
             is what makes that safe, not a declaration.
  observed   whether any record in `results/records/` carries the declared pair. This is the only
             column that is EVIDENCE: `verify_runtime_observation_geometry` compares the real
             observation tensor against the declared pair on every family path and raises on a
             mismatch, so a matching record means the tensor really had that shape.
  stale      records carrying a pair that is NOT the declared one, i.e. the pre-2026-09-07 bug.
             Not a current defect; listed so nobody reads one as a measurement.

A baseline with no record is NOT a failure -- it means the assertion has never had the chance to
run for it, and that is worth stating rather than glossing.
"""
from __future__ import annotations

import argparse
import glob
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rlgen.protocol import OBSERVATION_GEOMETRY  # noqa: E402

FAMILY_TOOL = ROOT / "datasphere" / "native" / "family.py"


def _family_of(baseline: str) -> str | None:
    result = subprocess.run(
        [sys.executable, str(FAMILY_TOOL), "family-of", "--baseline", baseline],
        capture_output=True, text=True, cwd=str(ROOT))
    return result.stdout.strip() or None


def _argv_geometry(family: str, baseline: str) -> str:
    """What `family.py command` passes explicitly, if anything."""
    result = subprocess.run(
        [sys.executable, str(FAMILY_TOOL), "command", "--family", family,
         "--baseline", baseline, "--task", "Door", "--frames", "10000",
         "--eval-every", "-1", "--eval-episodes", "1", "--save-every", "10000",
         "--seed", "1", "--run-dir", "/tmp/audit-geometry"],
        capture_output=True, text=True, cwd=str(ROOT))
    if result.returncode != 0:
        return "?"
    argv = result.stdout.split()
    found = []
    for flag in ("--frame_stack", "--frame-stack", "--image_size", "--image-size"):
        if flag in argv:
            found.append(f"{flag}={argv[argv.index(flag) + 1]}")
    return " ".join(found)


def _recorded() -> dict[str, set[tuple]]:
    seen: dict[str, set[tuple]] = {}
    for path in glob.glob(str(ROOT / "results" / "records" / "*.jsonl")):
        with open(path) as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                scope = record.get("evaluator_scope") or {}
                baseline = record.get("baseline")
                if baseline and "frame_stack" in scope and "image_size" in scope:
                    seen.setdefault(baseline, set()).add(
                        (scope["frame_stack"], scope["image_size"]))
    return seen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 if any baseline has a record contradicting its declaration")
    args = parser.parse_args()

    seen = _recorded()
    print("OBSERVATION GEOMETRY -- declared, executed, observed\n")
    print(f"  {'baseline':10s} {'declared':>12s}  {'argv':26s} {'observed':10s} stale-records")
    contradicted, unobserved = [], []
    for baseline, (image_size, frame_stack) in OBSERVATION_GEOMETRY.items():
        declared = (frame_stack, image_size)
        family = _family_of(baseline)
        argv = _argv_geometry(family, baseline) if family else "?"
        records = seen.get(baseline, set())
        stale = sorted(r for r in records if r != declared)
        if declared in records:
            status = "yes"
        elif records:
            status = "CONTRADICTED"
            contradicted.append(baseline)
        else:
            status = "never run"
            unobserved.append(baseline)
        shown = ", ".join(f"fs={f} img={i}" for f, i in stale) if stale else "-"
        print(f"  {baseline:10s} fs={frame_stack} img={image_size:<5d} {argv:26s} "
              f"{status:10s} {shown}")

    print()
    if unobserved:
        print(f"  {len(unobserved)} baseline(s) have produced no record, so the runtime geometry")
        print(f"  assertion has never run for them: {', '.join(unobserved)}.")
        print("  Declared and would-be-checked is not the same as verified. A mismatch would fail")
        print("  the cell loudly rather than produce a wrong number -- bounded, not proven.")
    else:
        print("  every baseline has a record carrying its declared geometry.")

    if contradicted:
        print()
        print(f"  CONTRADICTED: {', '.join(contradicted)} -- a record disagrees with the")
        print("  declaration and none agrees. Either the declaration is wrong or the run was.")
        if args.strict:
            return 1

    print()
    print("  `observed` is the only evidence column. It means")
    print("  scripts/eval_across_scenes.py::verify_runtime_observation_geometry compared the real")
    print("  observation tensor to the declared pair and did not raise -- the check that caught")
    print("  rad at (9, 84, 84) when 100x100 was declared.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
