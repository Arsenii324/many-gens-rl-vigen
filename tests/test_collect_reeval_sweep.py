"""The sweep collector must key rows the way the records are actually shaped.

[Claude 2026-09-16] Written because the first version of the dedup key produced 44 distinct keys
for the 88 rows of a ppg endpoint sweep. The endpoint grid runs TWICE -- once sampling, once taking
the mode -- and both passes carry identical cell/frame/regime/scene_set. The policy mode lives in
`conventions.eval_policy_mode`, not at the top level where the first key looked, so collecting an
endpoint sweep would have rejected it wholesale as duplicated or silently kept half of it.

These tests run against the committed records, which is the only place the real row shape exists.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collect_reeval_sweep import _row_key  # noqa: E402

BUNDLES = ("reeval-v214-ppg-endpoint", "reeval-v214-ppg-curve", "reeval-v214-idaac-endpoint")


def _rows(tag: str) -> list[dict]:
    path = ROOT / "results" / "records" / f"{tag}__records.jsonl"
    if not path.is_file():
        pytest.skip(f"{tag} not collected in this tree")
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


@pytest.mark.parametrize("tag", BUNDLES)
def test_every_row_keys_uniquely(tag):
    rows = _rows(tag)
    keys = {_row_key(r) for r in rows}
    assert len(keys) == len(rows), (
        f"{tag}: {len(rows)} rows collapse to {len(keys)} keys. Collecting this sweep would drop "
        "rows or reject it as duplicated.")


def test_the_two_endpoint_passes_are_distinguished():
    """The specific collision that motivated this file."""
    rows = _rows("reeval-v214-ppg-endpoint")
    modes = {(r.get("conventions") or {}).get("eval_policy_mode") for r in rows}
    assert modes == {"sample", "mode"}, f"expected both endpoint passes, got {modes}"
    without_mode = {(r.get("cell"), r.get("frame"), r.get("regime"), r.get("scene_set"))
                    for r in rows}
    assert len(without_mode) * 2 == len(rows), (
        "the endpoint sweep should be exactly two passes over the same grid")
    assert len({_row_key(r) for r in rows}) == len(rows), (
        "the key must separate the passes that cell/frame/regime/scene_set cannot")


def test_a_duplicated_archive_still_collides():
    """Two copies of the SAME archive must produce identical keys, or duplicates go undetected."""
    rows = _rows("reeval-v214-ppg-curve")
    assert _row_key(rows[0]) == _row_key(dict(rows[0]))
