"""Source-target disclosure must survive from descriptors to reported rows."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


FAMILY = _load(ROOT / "datasphere/native/family.py", "native_family_for_provenance")
NORMALIZE = _load(ROOT / "datasphere/native/normalize_curves.py", "normalize_for_provenance")
RESULTS = _load(ROOT / "scripts/results_table.py", "results_for_provenance")


def test_every_baseline_has_explicit_source_target_and_variant():
    descriptors = json.loads((ROOT / "datasphere/native/families.json").read_text())
    labels = FAMILY.all_provenance()
    baselines = [b for entry in descriptors.values() if isinstance(entry, dict)
                 for b in entry.get("baselines", [])]
    assert len(labels) == len(set(baselines)) == 12
    for baseline in baselines:
        item = labels[baseline]
        assert set(item) == {"source_target", "source_variant"}
        assert all(isinstance(item[key], str) and item[key].strip()
                   for key in item)


def test_native_record_carries_descriptor_provenance():
    row = NORMALIZE.record(cell="ppg-s101", baseline="ppg", family="ppg", seed=101, frame=50000)
    assert row["provenance"] == FAMILY.provenance_for("ppg")
    assert "source_target" in row["provenance"]
    assert "source_variant" in row["provenance"]


def test_evaluator_record_factory_carries_the_same_provenance():
    # eval_grid deliberately obtains the shared envelope from normalize_curves; exercise that
    # exact factory rather than a second hand-written evaluator schema.
    factory = _load(ROOT / "scripts/eval_grid.py", "eval_grid_for_provenance")._record_factory()
    row = factory(cell="idaac-s101", baseline="idaac", family="idaac", seed=101, frame=50000)
    assert row["provenance"] == FAMILY.provenance_for("idaac")


def test_statistics_row_carries_the_same_provenance(monkeypatch):
    d = {"scenes": {str(i): {"returns": [10.0, 11.0], "n_success": 1} for i in range(10)},
         "control": {"returns": [10.0, 11.0]}, "episodes": 2, "snapshot_md5": "x"}
    monkeypatch.setattr(RESULTS, "load", lambda _tag, _mode: d)
    row = RESULTS.row("ppg", 101, "100k", "unused", 1.0)
    assert row["provenance"] == FAMILY.provenance_for("ppg")


def test_legacy_statistics_row_fallback_is_explicit_not_silent():
    assert RESULTS.display_provenance({"name": "synthetic-old-row"}) == (
        "UNLABELED", "legacy/mocked row; descriptor metadata absent")


def test_known_statistics_row_never_uses_legacy_fallback(monkeypatch):
    d = {"scenes": {str(i): {"returns": [10.0, 11.0], "n_success": 1} for i in range(10)},
         "control": {"returns": [10.0, 11.0]}, "episodes": 2, "snapshot_md5": "x"}
    monkeypatch.setattr(RESULTS, "load", lambda _tag, _mode: d)
    row = RESULTS.row("ppg", 101, "100k", "unused", 1.0)
    assert RESULTS.display_provenance(row)[0] != "UNLABELED"


def test_disclosure_doc_distinguishes_labels_from_faithfulness_verdict():
    text = (ROOT / "docs/EVAL-PROTOCOL.md").read_text()
    assert "not a" in text and "faithfulness verdict" in text
    assert "source_target" in text and "source_variant" in text
