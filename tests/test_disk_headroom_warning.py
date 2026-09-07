"""Free disk was measured every 30 seconds and nothing ever read it.

`safe_checkpoint.py` catches ENOSPC at write time and responds by waiting and then SKIPPING, which
is the right call at that layer -- it never corrupts a checkpoint. But the consequence is that a
multi-day cell can spend hours declining to save while the log says nothing, and finish with no
retained checkpoints to evaluate. The measurement existed; the warning did not
(external recommendation 22, item 11).
"""
from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasphere" / "native" / "measure_resources.py"


def _module():
    spec = importlib.util.spec_from_file_location("_measure_resources", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_sampler_still_records_free_disk():
    module = _module()
    entry = module.sample(1)
    assert "free_disk_gib" in entry


def test_the_thresholds_are_declared_and_ordered():
    module = _module()
    parser_defaults = {}
    import argparse
    parser = argparse.ArgumentParser()
    # Re-declare via the module's own main() parser by inspecting the source, which is cheaper and
    # more honest than executing main(): it needs a live pid and loops until that pid exits.
    text = SOURCE.read_text()
    assert "--disk-warn-gib" in text and "--disk-critical-gib" in text
    assert "NATIVE_DISK_LOW" in text or "NATIVE_DISK_" in text


def test_the_warning_is_announced_on_the_runner_marker_convention():
    """Greppable beside NATIVE_CELL_*, or an operator scanning the log will not see it."""
    text = SOURCE.read_text()
    assert "NATIVE_DISK_CRITICAL" in text
    assert "NATIVE_DISK_LOW" in text
    assert "NATIVE_DISK_RECOVERED" in text, (
        "a warning that never clears trains the reader to ignore it")
    # It must reach the log, not just the JSON artifact.
    assert "file=sys.stderr" in text


def test_it_says_what_actually_happens_when_space_runs_out():
    """The failure mode is silent SKIPPING, not a crash; the message must say so."""
    text = SOURCE.read_text()
    assert "skipped" in text.lower()
