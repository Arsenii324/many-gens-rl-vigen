"""`runnable/_patches/*.patch` must still reproduce the clones they claim to.

`RECOVERY-HANDOFF.md:30` states the clones are "reproducible from `ext/` plus
`runnable/_patches/*.patch`". Nothing checked it, and by 2026-09-05 five of six had drifted --
including two edits that unblocked families which could not be evaluated at all.

The tool that checks this had two bugs of its own while being written, and both are pinned below,
because each made it report something confidently wrong:

1. it passed `--src-prefix=a/` AND rewrote paths to `a/...`, producing `aa/` -- which marked all six
   snapshots stale and would have overwritten six provenance files had the output not been compared
   against an untouched family first;
2. it parsed `diff --git a/...` headers only, so a NEW file (whose header reads `diff --git b/x b/x`)
   was dropped, regeneration deleted that entry, and the check never converged.
"""
import importlib.util
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location(
        "_patch_tool", ROOT / "scripts" / "refresh_clone_patches.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_patch_tool"] = module
    spec.loader.exec_module(module)
    return module


def test_new_file_entries_are_not_dropped_by_the_parser():
    """alda's snapshot adds specs/train_alda_robosuite_door.yaml; its header starts `b/`, not `a/`."""
    tool = _tool()
    patch = ROOT / "runnable" / "_patches" / "alda.patch"
    if not patch.is_file():                                        # pragma: no cover
        pytest.skip("alda snapshot is not in this tree")
    covered = tool.patched_files(patch)
    assert any(name.endswith("specs/train_alda_robosuite_door.yaml") for name in covered), (
        f"the added spec file was dropped from the covered set: {covered}"
    )


def test_every_snapshot_currently_reproduces_its_clone():
    tool = _tool()
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "refresh_clone_patches.py"),
                           "--check"], capture_output=True, text=True)
    if "MISSING SOURCE" in proc.stdout:                            # pragma: no cover
        pytest.skip("ext/ sources are not all present in this tree")
    assert proc.returncode == 0, (
        "a clone patch no longer reproduces its clone, so RECOVERY-HANDOFF's stated recovery path "
        f"is broken:\n{proc.stdout}"
    )


def test_regeneration_is_idempotent():
    """A checker that cannot converge reports permanent staleness, which reads as noise."""
    tool = _tool()
    for family in ("ctrl", "idaac", "alda"):
        patch = ROOT / "runnable" / "_patches" / f"{family}.patch"
        if not patch.is_file() or not (ROOT / tool.SOURCE_OF[family]).is_dir():
            continue                                               # pragma: no cover
        assert tool.rebuild(family).strip() == patch.read_text().strip(), (
            f"{family}: regenerating the snapshot does not reproduce the stored one, so the check "
            "would stay red no matter how often it is run"
        )
