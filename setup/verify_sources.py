#!/usr/bin/env python3
"""Verify source trees reconstructed by bootstrap_sources.py without network access."""

import argparse

from bootstrap_sources import BootstrapError, verify_all


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", action="append")
    args = parser.parse_args()
    try:
        unverifiable = verify_all(families=args.family)
    except BootstrapError as error:
        print(f"error: {error}")
        return 2
    print("source reconstruction verified")
    for name in unverifiable:
        print(f"NOT VERIFIED HERE: {name} needs a case-sensitive filesystem; "
              f"its reconstruction cannot be materialized on this one. Verify it on Linux.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())