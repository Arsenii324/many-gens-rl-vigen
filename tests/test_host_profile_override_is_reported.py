"""A named, non-default host profile with no matching override must say so.

`family.resolved_descriptor()` silently returned a family's base `constants`/`production`/
`environment` whenever `families.json` declared no `host_profiles.<profile>` block for it --
indistinguishable from a family that was deliberately tuned and needed no change. Four of the
seven families (`dmc_gb`, `idaac`, `alda`, `ppg`) declare no `host_profiles` block at all, so every
V100 production run of those four used whatever profile-agnostic values were authored, unchanged,
with nothing saying so. [2026-09-20]
"""
from __future__ import annotations

import importlib.util
import io
import contextlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
FAMILY = ROOT / "datasphere" / "native" / "family.py"
DESCRIPTORS = ROOT / "datasphere" / "native" / "families.json"


def _load():
    spec = importlib.util.spec_from_file_location("_family_host_profile", FAMILY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_families_with_no_host_profiles_block_exist_today():
    """This test's premise depends on real data; if it ever stops holding, the other two tests
    below would pass vacuously and should be revisited rather than trusted blindly."""
    data = json.loads(DESCRIPTORS.read_text())
    families = {k: v for k, v in data.items() if not k.startswith("_")}
    no_v100 = {name for name, entry in families.items()
              if "v100" not in entry.get("host_profiles", {})}
    assert no_v100, "expected at least one family with no v100 override to exercise the warning"


def test_a_family_with_no_matching_override_warns_on_stderr():
    fam = _load()
    data = json.loads(DESCRIPTORS.read_text())
    families = {k: v for k, v in data.items() if not k.startswith("_")}
    no_v100 = sorted(name for name, entry in families.items()
                     if "v100" not in entry.get("host_profiles", {}))
    assert no_v100, "test premise: see test_families_with_no_host_profiles_block_exist_today"
    family_name = no_v100[0]
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        fam.resolved_descriptor(family_name, profile="v100")
    out = buf.getvalue()
    assert "NATIVE_HOST_PROFILE_NO_OVERRIDE" in out, out
    assert f"family={family_name}" in out and "profile=v100" in out, out


def test_the_default_probe_profile_stays_silent():
    """`datasphere` (the probe-safe default) is EXPECTED to have no override for most families --
    warning there would make the common case noisy for no reason."""
    fam = _load()
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        fam.resolved_descriptor("dmc_gb", profile="datasphere")
    assert buf.getvalue() == ""


def test_a_family_with_a_real_override_stays_silent():
    fam = _load()
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        fam.resolved_descriptor("rlvigen", profile="v100")
    assert buf.getvalue() == "", "rlvigen declares its own v100 block; nothing to warn about"
