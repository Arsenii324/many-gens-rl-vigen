#!/usr/bin/env python3
"""Would this job config die on the tier it asks for, or name a cell that does not exist?

Both failures happened on 2026-09-05, twenty minutes apart, and both were preventable from the
tree alone:

- `cfg-rlvigen-functional-v116.yaml` asked for `CELLS=rlvigen:1`. `rlvigen` is an evaluator FAMILY;
  its baselines are drqv2/svea/drq/sgqn/curl. The job provisioned, started, and died in three
  minutes having produced nothing.
- `cfg-ctrl-functional-v115.yaml` and the alda config asked for `gt4.1`. ctrl was SIGKILLed at
  11.07 GiB; alda's own descriptor already recorded 15.73 GiB against that tier's 14.5 usable.

`gate_scheduler_ram_invariant` was PASSING throughout, because it verifies that the SUBMIT script
contains a memory check. It does. Hand-written configs submitted with `datasphere project job
execute` never go through that script -- which is written in that gate's own comment, as the reason
alda was SIGKILLed the first time. A gate that certifies a mechanism nobody is obliged to use
certifies nothing; this one reads the configs themselves.

Only configs that are still SUBMITTABLE are judged. A config whose payload archive no longer exists
on disk cannot be run, so its tier is history, not a live risk.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
NATIVE = ROOT / "datasphere" / "native"
sys.path.insert(0, str(NATIVE))


def _descriptor() -> dict:
    return json.loads((NATIVE / "families.json").read_text())


def declared_baselines() -> dict[str, str]:
    """baseline name -> owning family."""
    out: dict[str, str] = {}
    for family, entry in _descriptor().items():
        if family.startswith("_") or not isinstance(entry, dict):
            continue
        for baseline in entry.get("baselines", []):
            out[baseline] = family
    return out


def config_inputs(text: str) -> list[str]:
    return re.findall(r"^\s*-\s+([^\s:]+):\s+\w+\s*$", text, flags=re.MULTILINE)


def is_submittable(text: str) -> bool:
    """Every declared input must exist, or the config cannot be run at all."""
    for entry in config_inputs(text):
        if "/" in entry and not (ROOT / entry).exists():
            return False
    return True


def audit() -> int:
    baselines = declared_baselines()
    import family as family_tool  # noqa: E402  (needs NATIVE on the path)

    problems: list[tuple[str, str]] = []
    uncertified: set[str] = set()
    checked = superseded = 0
    for path in sorted(NATIVE.glob("cfg-*.yaml")):
        text = path.read_text()
        cells = re.search(r"\bCELLS=(\S+)", text)
        tier = re.search(r"cloud-instance-type:\s*(\S+)", text)
        if not cells or not tier:
            continue
        if not is_submittable(text):
            continue
        if "# SUPERSEDED" in text:
            # A config explicitly retired by a person. The default is LIVE: anything unmarked is
            # judged, so forgetting to mark something is the safe direction, and history does not
            # accumulate into permanent red that trains everyone to ignore the report.
            superseded += 1
            continue
        checked += 1
        spec = cells.group(1)
        for cell in spec.split(","):
            name = cell.split(":")[0]
            if name not in baselines:
                near = ", ".join(sorted(b for b, f in baselines.items() if f == name)) or "none"
                problems.append((path.name, f"`{name}` is not a baseline; if it is a family, its "
                                             f"baselines are: {near}"))
        # A Places365 baseline (svea, sgqn, soda) trains against overlay images that must be
        # supplied as a job input. The runner fails closed on this -- NATIVE_PLACES365_MISSING --
        # but only AFTER provisioning. Checked here, before the job is paid for. This cost one job.
        descriptor = _descriptor()
        needs_places = set()
        for cell in spec.split(","):
            name = cell.split(":")[0]
            for family, entry in descriptor.items():
                if family.startswith("_") or not isinstance(entry, dict):
                    continue
                if name in (entry.get("places365_baselines") or []):
                    needs_places.add(name)
        if needs_places and "PLACES365_VAL" not in text:
            problems.append((path.name, f"{', '.join(sorted(needs_places))} require the Places365 "
                                        f"overlay set, but no `places365-val.tgz: PLACES365_VAL` "
                                        f"input is declared"))
        try:
            for fam in family_tool.families_of_cells(spec):
                if (family_tool.production(fam) or {}).get("fixed_peak_gib") is None:
                    uncertified.add(fam)
        except Exception:
            pass
        try:
            # [Claude 2026-09-06] job.sh's real submit path admits a job at
            # family_tool.admission_tier_for(tier) rather than the literal declared tier (g1.1 has
            # no RAM/vCPU model in this module, so it is admitted as gt4i.1, a conservative floor).
            # This audit called check_tier/check_memory with the raw tier instead and flagged every
            # g1.1 config as "unknown job tier: g1.1" -- a false positive discovered when two g1.1
            # configs submitted and ran successfully for real (bt18a8fjl3qrp5jv50g6,
            # bt1vsfov1mmg9shjp898) while this gate reported FAIL. Exactly the failure class this
            # gate's own docstring warns about, now happening to the gate itself for a tier that
            # did not exist when it was written. Fixed at the one shared definition rather than by
            # mirroring it a second time here.
            admission_tier = family_tool.admission_tier_for(tier.group(1))
            family_tool.check_tier(spec, admission_tier)
            # Unmeasured is reported separately below. Treating "no measurement" as a BLOCKING
            # failure here would flag six of seven families and make the instrument unreadable,
            # which is how instruments stop being run. Treating it as a PASS is what killed ctrl.
            # It is neither: it is a named, countable gap.
            # [Claude 2026-09-07] Pass THIS config's budget: check_memory now charges the
            # replay allocation that families.json's fixed_peak_gib excludes (review 21 #12), and
            # a 10k probe must not be sized against the 600k production buffer.
            config_frames = re.search(r"\bFRAMES=(\d+)", text)
            family_tool.check_memory(spec, admission_tier, allow_unmeasured=True,
                                     frames=int(config_frames.group(1)) if config_frames else None)
        except (ValueError, SystemExit) as exc:
            # family.fail() raises ValueError. Catching only SystemExit sent these to the generic
            # branch below, which labelled a clean, correct REJECTION as "could not be evaluated"
            # -- reporting an instrument failure where the instrument had in fact worked.
            problems.append((path.name, str(exc) or f"rejected on {tier.group(1)}"))
        except Exception as exc:  # pragma: no cover - a malformed cell spec reaches here
            problems.append((path.name, f"could not be evaluated: {exc}"))

    print("Can each submittable job config actually run on the tier it requests?\n")
    print(f"  {checked} submittable config(s) checked, {superseded} marked superseded "
          f"(a config whose payload is gone is history, not a live risk)\n")
    if uncertified:
        print(f"  NOT CERTIFIABLE -- no measured fixed_peak_gib: {', '.join(sorted(uncertified))}")
        print("  These pass the tier check because nothing is known, not because they fit. ctrl was")
        print("  in this set until it was SIGKILLed. A completed run replaces the gap with a number.\n")
    if not problems:
        print("  no config asks for something that cannot run")
        return 0
    for name, why in problems:
        print(f"  !! {name}: {why}")
    print("\n  A config that names a nonexistent cell, or a tier that cannot hold the family, pays")
    print("  for provisioning and bootstrap and then dies -- with an error indistinguishable from")
    print("  a code fault. Both of these happened on 2026-09-05.")
    return 1


if __name__ == "__main__":
    raise SystemExit(audit())
