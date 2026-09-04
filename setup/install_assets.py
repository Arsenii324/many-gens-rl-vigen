#!/usr/bin/env python3
"""Install RL-ViGen's texture pack into the active robosuite.

WHY THIS EXISTS. RL-ViGen's evaluation modes randomise object and arena textures by name --
`Custom01` .. `Custom40`. Those textures are NOT in released robosuite; RL-ViGen ships a *patched*
robosuite under `RL-ViGen-upstream/third_party/robosuite/` that adds them. Install stock robosuite
from PyPI and every eval mode dies with:

    FileNotFoundError: Custom05 does not exist as a file name or as a built-in texture name

while `mode=train` runs fine, because train randomises nothing. That asymmetry is the dangerous
part: the failure appears only on the eval path, which is the path whose numbers get published.

This resolves a question the sibling project (../gen-rebuttal/vigen-idaac) left open -- whether the
vendored and pip robosuites actually differ. They do, and this is one concrete difference.

TWO WAYS TO FIX IT, and why this one:
  (a) install RL-ViGen's vendored robosuite instead of the released one;
  (b) copy the 40 textures into whatever robosuite is installed.

**setup/install.sh does (a)**, because copying textures turned out to be insufficient on its own:
the two robosuites differ in 761 files, and the `Custom*` names are resolved through XML the fork
also carries, so stock robosuite still failed after the textures were in place. This script
therefore now functions mainly as (b)-as-a-VERIFIER: it confirms the *active* robosuite carries
RL-ViGen's texture pack, whichever way it was installed, and copies anything missing. Under the
supported install its source and target are the same directory and it copies nothing.

Idempotent: re-running copies nothing and exits 0. `--check` reports and changes nothing.
"""
from __future__ import annotations

import argparse
import filecmp
import hashlib
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "RL-ViGen-upstream", "third_party", "robosuite",
                   "robosuite", "models", "assets", "textures")


def target_dir() -> str:
    import robosuite
    return os.path.join(os.path.dirname(robosuite.__file__), "models", "assets", "textures")


def wanted() -> list[str]:
    if not os.path.isdir(SRC):
        return []
    return sorted(f for f in os.listdir(SRC) if f.lower().startswith("custom") and f.endswith(".png"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report only; exit 1 if incomplete")
    args = ap.parse_args()

    names = wanted()
    if not names:
        print(f"FATAL: no custom textures at {SRC}\n"
              f"       Is RL-ViGen-upstream present? Run setup/install.sh first.", file=sys.stderr)
        return 2

    dst = target_dir()
    if not os.path.isdir(dst):
        print(f"FATAL: robosuite texture dir not found: {dst}", file=sys.stderr)
        return 2

    copied = present = 0
    for n in names:
        s, d = os.path.join(SRC, n), os.path.join(dst, n)
        if os.path.exists(d) and filecmp.cmp(s, d, shallow=False):
            present += 1
            continue
        if args.check:
            print(f"  -- missing or differing: {n}")
            continue
        shutil.copy2(s, d)
        copied += 1

    # Verify by re-reading, not by trusting the copy loop.
    ok = [n for n in names
          if os.path.exists(os.path.join(dst, n))
          and filecmp.cmp(os.path.join(SRC, n), os.path.join(dst, n), shallow=False)]
    digest = hashlib.sha256(
        b"".join(open(os.path.join(SRC, n), "rb").read() for n in names)).hexdigest()[:16]

    print(f"  source   {SRC}")
    print(f"  target   {dst}")
    print(f"  textures {len(ok)}/{len(names)} present and identical  (pack sha256[:16] {digest})")
    if args.check:
        print(f"\n{'OK' if len(ok) == len(names) else 'INCOMPLETE'}")
        return 0 if len(ok) == len(names) else 1
    print(f"\n{copied} copied, {present} already present")
    if len(ok) != len(names):
        print("FAILED -- some textures did not land.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
