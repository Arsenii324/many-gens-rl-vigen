#!/usr/bin/env python3
"""Which built payloads no longer match the tree, and in which members?

    python scripts/audit_payload_freshness.py                    # every payload-*.tgz found
    python scripts/audit_payload_freshness.py --strict           # exit 1 if any is stale
    python scripts/audit_payload_freshness.py <archive> ...      # only these

## Why this exists

`contract.py verify-payload` asserts every member is DECLARED, which a stale archive satisfies
perfectly -- its own docstring says so. The complementary check is `--expect path:marker`, and it
is *deliberately dumb*: a substring the caller names, "because the caller is the only one who
knows which identifier is new."

That works exactly as far as the caller's memory. `cfg-metrics-probe-ctrl-ppg-v66` was submitted
against a payload built before the edit it existed to validate; it built, verified, uploaded, and
would have run green over code that was not in it. The failure is not that the check was weak --
it is that the check had to be *remembered*, and a check you must remember to ask for is not a
guard, it is a habit.

This asks nothing of the caller. It compares every member of every archive to the working tree,
byte for byte, and reports what has drifted. Run it before any submission.

## What "stale" means here, precisely

A member whose bytes in the archive differ from the same path in the tree right now. That is not
automatically wrong -- a payload built to test a since-reverted change is legitimately different,
and so is one kept deliberately for a re-run of an old configuration. So this REPORTS and names
the members; only `--strict` turns it into a failure, for a pre-submission hook that wants one.

A member missing from the tree is reported separately: that is a payload referring to a file that
no longer exists, which no rebuild can reproduce.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def audit(archive_path: pathlib.Path) -> dict:
    stale: list[str] = []
    absent: list[str] = []
    same = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        for info in archive.getmembers():
            if not info.isfile():
                continue
            member = archive.extractfile(info)
            if member is None:
                continue
            in_archive = member.read()
            on_disk = ROOT / info.name
            if not on_disk.is_file():
                absent.append(info.name)
                continue
            if _sha(in_archive) != _sha(on_disk.read_bytes()):
                stale.append(info.name)
            else:
                same += 1
    return {"archive": archive_path.name, "stale": stale, "absent": absent, "identical": same}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("archives", nargs="*")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    if args.archives:
        paths = [pathlib.Path(a) for a in args.archives]
    else:
        paths = sorted(ROOT.glob("**/payload-*.tgz")) + sorted(ROOT.glob("**/native-payload-*.tgz"))
    paths = [p for p in paths if p.is_file()]
    if not paths:
        print("no payload archives found. Nothing was compared -- which is NOT the same as "
              "nothing having drifted.")
        return 1

    drifted = []
    for path in paths:
        try:
            row = audit(path)
        except (tarfile.TarError, OSError) as exc:
            print(f"  {path.name:34} UNREADABLE: {exc}")
            drifted.append(path.name)
            continue
        if row["stale"] or row["absent"]:
            drifted.append(row["archive"])
            print(f"  {row['archive']:34} STALE -- {len(row['stale'])} member(s) differ from the "
                  f"tree, {len(row['absent'])} no longer exist ({row['identical']} identical)")
            for name in sorted(row["stale"])[:8]:
                print(f"      differs  {name}")
            for name in sorted(row["absent"])[:4]:
                print(f"      ABSENT   {name}")
        else:
            print(f"  {row['archive']:34} matches the tree ({row['identical']} members)")

    print()
    if drifted:
        print(f"  {len(drifted)} of {len(paths)} payload(s) do not match the current tree.")
        print("  A stale payload passes verify-payload perfectly: that check asks whether every")
        print("  member is DECLARED, not whether it is CURRENT. Submitting one runs code that is")
        print("  not the code this tree reports, and the result looks green either way.")
        print("  Rebuild before submitting, or keep it deliberately and say why.")
    else:
        print(f"  All {len(paths)} payload(s) match the working tree.")
    return 1 if (drifted and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
