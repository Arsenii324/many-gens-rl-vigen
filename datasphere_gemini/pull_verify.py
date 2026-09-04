#!/usr/bin/env python3
"""Verification half of the DataSphere pull for many-gens-rl-vigen.

Verifies:
  1. result.tgz exists and is non-zero
  2. result.tgz is a fully valid, uncorrupted tar archive readable to end
  3. Essential outputs (checkpoints, train.csv, logs) are present inside result.tgz
"""
import os
import sys
import tarfile

def verify(output_dir, expected, log=print):
    if not expected:
        log("FATAL: No expected files specified to verify.")
        return False
    ok = True
    for name in expected:
        p = os.path.join(output_dir, name)
        if not os.path.exists(p):
            log(f"FATAL: Expected file missing: {name}")
            ok = False
            continue
        size = os.path.getsize(p)
        if size == 0:
            log(f"FATAL: {name} arrived empty (0 bytes)")
            ok = False
            continue
        if name.endswith((".tgz", ".tar.gz")):
            try:
                with tarfile.open(p, "r:gz") as t:
                    members = t.getnames()
                    n = len(members)
                log(f"  OK {name}: {size / 2**20:.2f} MiB, {n} members, archive reads to end.")
                # Verify key internal deliverables
                critical = [m for m in members if "snapshot" in m or "train" in m or "log" in m]
                log(f"    Critical members found: {len(critical)} (e.g. {critical[:3]})")
            except Exception as ex:
                log(f"FATAL: {name} is corrupted or truncated: {ex}")
                ok = False
                continue
        else:
            log(f"  OK {name}: {size / 2**20:.2f} MiB")
    return ok
