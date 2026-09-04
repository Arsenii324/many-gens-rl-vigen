#!/usr/bin/env python3
"""Verify a returned DataSphere payload against the manifest the job wrote on the box.

The point is END-TO-END integrity: bytes generated remotely must equal bytes extracted locally.
Checking that files "arrived" is not that -- the first run of this probe returned two files, both
present, both readable, and the payload inside was missing entirely.

    python verify_pullback.py <dir>       # dir holds result.tgz and manifest.txt

Exits non-zero, loudly, on any mismatch.
"""
from __future__ import annotations

import hashlib
import os
import sys
import tarfile


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    d = sys.argv[1] if len(sys.argv) > 1 else "."
    tgz, man = os.path.join(d, "result.tgz"), os.path.join(d, "manifest.txt")

    for p in (tgz, man):
        if not os.path.exists(p):
            fail(f"{p} did not arrive")
        if os.path.getsize(p) == 0:
            fail(f"{p} arrived empty")

    meta = {}
    for line in open(man, encoding="utf-8"):
        if "=" in line:
            k, _, v = line.strip().partition("=")
            meta[k] = v

    # An EMPTY manifest field is the exact signature of the first failed run: the job carried on
    # after `dd` failed and wrote `big_bin_sha256=` with nothing after it. Treat a blank value as
    # a failure, not as a missing optional.
    for key in ("big_bin_sha256", "big_bin_bytes", "generated_utc"):
        if not meta.get(key):
            fail(f"manifest field {key!r} is empty -- the job did not produce what it claims "
                 f"(this is how the first probe reported SUCCESS while returning nothing)")

    want_sum, want_bytes = meta["big_bin_sha256"], int(meta["big_bin_bytes"])

    with tarfile.open(tgz, "r:gz") as tf:
        names = tf.getnames()
        member = next((n for n in names if n.endswith("big.bin")), None)
        if member is None:
            fail(f"big.bin absent from the archive; it holds {names}")
        info = tf.getmember(member)
        if info.size != want_bytes:
            fail(f"big.bin is {info.size} bytes in the archive, manifest says {want_bytes}")
        f = tf.extractfile(member)
        if f is None:
            fail(f"{member} is not a regular file")
        h = hashlib.sha256()
        read = 0
        while chunk := f.read(1 << 20):
            h.update(chunk)
            read += len(chunk)

    if read != want_bytes:
        fail(f"read {read} bytes out of the archive, manifest says {want_bytes}")
    if h.hexdigest() != want_sum:
        fail(f"sha256 mismatch\n  on the box: {want_sum}\n  after pull: {h.hexdigest()}")

    n_small = sum(1 for n in names if n.endswith(".txt"))
    print(f"OK  round trip verified end to end")
    print(f"    generated   {meta['generated_utc']} on the DataSphere box")
    print(f"    big.bin     {read:,} bytes, sha256 {h.hexdigest()[:16]}... matches the manifest")
    print(f"    archive     {len(names)} members ({n_small} small text files) from {tgz}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
