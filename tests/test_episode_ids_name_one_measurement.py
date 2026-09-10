"""An episode id must identify ONE measurement, and until today it identified two.

The id was `<baseline>-s<seed>-f<frame>-<regime>-sc<scene>-e<index>`, and its own comment claimed it
was "unique across the fleet". It was not: the endpoint runs once per entry in
`ENDPOINT_EVAL_POLICY_MODES`, which defaults to `native,mode`, and neither the scope nor the action
rule appeared in the id. On `card0-20260909-035152` **all 760 mode-pass ids collided with sampled
ones** -- `idaac-s101-f598016-eval-easy-sc0-e0` names two episodes with different returns under
different action rules.

`audit_eval_validity.py` did not catch it because it checks uniqueness per FILE, and each pass
writes its own file. The collision only exists in the assembled bundle, which is exactly where a
join or a dedup would meet it -- and merging those two ids merges the two estimands
`SAME-AXES-VERDICT.md` forbids pooling.

The scope and mode fields are OPTIONAL in the parser, because every record written before
2026-09-10 lacks them. An id without them is old, not malformed, and refusing to read it would make
the audit unusable on the existing corpus.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def test_the_producer_puts_scope_and_policy_mode_in_the_id():
    source = (ROOT / "scripts" / "eval_grid.py").read_text()
    start = source.index('"eval_episode_ids": [')
    block = source[start:start + 400]
    assert "eval_scope" in block, block
    assert "eval_policy_mode" in block, block


def test_the_two_endpoint_passes_no_longer_share_an_id():
    from audit_eval_validity import ID
    sampled = "idaac-s101-f598016-endpoint-sample-eval-easy-sc0-e0"
    moded = "idaac-s101-f598016-endpoint-mode-eval-easy-sc0-e0"
    assert sampled != moded
    for eid, mode in ((sampled, "sample"), (moded, "mode")):
        m = ID.match(eid)
        assert m is not None, eid
        assert m["mode"] == mode and m["scope"] == "endpoint"
        assert m["regime"] == "eval-easy" and m["scene"] == "0" and m["idx"] == "0"


def test_pre_2026_09_10_ids_still_parse():
    """The existing corpus must stay readable, or the audit becomes unusable on it."""
    from audit_eval_validity import ID
    m = ID.match("idaac-s101-f598016-eval-easy-sc0-e0")
    assert m is not None
    assert m["scope"] is None and m["mode"] is None
    assert m["regime"] == "eval-easy" and m["frame"] == "598016"


def test_a_hyphenated_regime_is_not_swallowed_by_the_baseline():
    """`.+?` plus an explicit regime alternation, so `eval-medium` cannot be parsed as part of a name."""
    from audit_eval_validity import ID
    m = ID.match("ibac_sni-s2-f10112-curve-native-eval-medium-sc7-e3")
    assert m is not None, "hyphenated regime failed to parse"
    assert m["baseline"] == "ibac_sni" and m["regime"] == "eval-medium"
    assert m["scope"] == "curve" and m["mode"] == "native" and m["scene"] == "7"


def test_the_collision_is_detectable_in_the_real_corpus():
    """The bundle that motivated this must still report its 760 duplicates."""
    import json
    import collections
    path = ROOT / "results" / "records" / "card0-20260909-035152__records.jsonl"
    if not path.is_file():
        return
    counts = collections.Counter()
    for line in path.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        for eid in ((row.get("native") or {}).get("eval_episode_ids") or []):
            counts[eid] += 1
    duplicated = [k for k, v in counts.items() if v > 1]
    assert len(duplicated) == 760, (
        f"expected the recorded 760 duplicate ids in this pre-fix bundle, found {len(duplicated)}"
    )
