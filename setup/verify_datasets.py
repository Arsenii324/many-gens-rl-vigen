#!/usr/bin/env python3
"""Is the EXTERNAL dataset this project needs present and usable? Sources are a separate question.

[Claude 2026-09-07.] The separation is the point. `setup/apply_patches.py --check` and the payload
contract prove that the CODE reconstructs; this proves that a large asset the repository
deliberately does not carry is on disk and readable. A clean clone with no Places365 is a
successfully reconstructed clone -- it simply cannot train `svea`, `sgqn` or `soda` until the
dataset arrives, which is a different sentence and deserves a different command.

    python setup/verify_datasets.py                    # uses PLACES365_ROOT or ./data
    python setup/verify_datasets.py --split val        # check the probe asset instead

Deliberately CHEAP. The production split is ~1.8M images across 365 class directories; hashing or
opening all of them on every run would make this the kind of check people skip. It verifies the
structure, the class count, and that a handful of representative images actually decode -- which is
what catches the real failures: a truncated download, a flat dump that `ImageFolder` cannot read, or
a path pointing at the wrong partition.
"""
from __future__ import annotations

import argparse
import pathlib
import random
import sys

#: Only these three consume the overlay dataset. The other nine baselines must not be blocked by
#: its absence, and `family.py needs-places365` already enforces that at run time.
OVERLAY_BASELINES = ("svea", "sgqn", "soda")
EXPECTED_CLASSES = 365
SAMPLE_IMAGES = 5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=None,
                        help="dataset root holding places365_standard/; "
                             "defaults to $PLACES365_ROOT, else ./data")
    parser.add_argument("--split", default="train", choices=("train", "val"),
                        help="train is the production split (DECISION-SHEET A22)")
    args = parser.parse_args()

    import os
    root = pathlib.Path(args.root or os.environ.get("PLACES365_ROOT") or "data")
    partition = root / "places365_standard" / args.split

    print("Places365")
    print(f"  configured root:            {root}")
    print(f"  selected split:             {args.split}"
          f"{'  (production, A22)' if args.split == 'train' else '  (probe/legacy)'}")
    print(f"  needed by:                  {', '.join(OVERLAY_BASELINES)}")

    if not partition.is_dir():
        print(f"  directory/layout valid:     NO -- {partition} is absent")
        print("  dataset usable:             FAIL")
        print()
        print("  bash setup/fetch_overlay_dataset.sh <dest> " + args.split)
        print("  Sources reconstruct without this; only the three baselines above need it.")
        return 1
    print(f"  directory/layout valid:     yes ({partition})")

    classes = sorted(p for p in partition.iterdir() if p.is_dir())
    print(f"  class directories:          {len(classes)}", end="")
    if args.split == "train" and len(classes) != EXPECTED_CLASSES:
        print(f"  -- EXPECTED {EXPECTED_CLASSES}")
        print("  dataset usable:             FAIL")
        return 1
    print("")

    images = []
    for directory in random.Random(0).sample(classes, min(len(classes), SAMPLE_IMAGES)):
        found = next((p for p in sorted(directory.iterdir()) if p.is_file()), None)
        if found is not None:
            images.append(found)
    if not images:
        print("  representative images:      NONE FOUND")
        print("  dataset usable:             FAIL")
        return 1

    try:
        from PIL import Image
    except ImportError:
        print(f"  representative images:      {len(images)} present, NOT decoded (Pillow absent)")
        print("  dataset usable:             PASS (structure only)")
        return 0

    for path in images:
        try:
            with Image.open(path) as handle:
                handle.verify()
        except Exception as error:                                    # noqa: BLE001
            print(f"  representative images:      FAILED to decode {path}: {error}")
            print("  dataset usable:             FAIL")
            return 1
    print(f"  representative images:      {len(images)} decoded")
    print("  dataset usable:             PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
