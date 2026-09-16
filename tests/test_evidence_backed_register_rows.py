"""Pins register rows whose evidence lives in `results/evidence/` and whose premise is a code fact.

Each test asserts the premise as it stands. A failure means the code moved under the row, so the
row and its bundle's CLAIM.md must be re-derived, not that the code is wrong.
"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _function_source(path: pathlib.Path, name: str) -> str:
    text = path.read_text()
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(text, node)


def test_evaluator_sampling_rows_reproduce_within_noise():
    """`evaluator-sampling-rows-reproduce-within-noise`: per-episode reseeding leaves torch alone.

    The row explains identical placements with differing returns by this asymmetry. If torch
    joins the per-episode reseed, sampling rows may become bit-reproducible and the measured noise
    no longer describes the evaluator.
    """
    grid = ROOT / "scripts" / "eval_grid.py"
    per_episode = _function_source(grid, "seed_episode_placement")
    assert "np.random.seed(condition)" in per_episode and "_random.seed(condition)" in per_episode
    assert "torch" not in per_episode, "seed_episode_placement now touches torch; re-derive the row"
    ppg = (ROOT / "runnable" / "ppg" / "phasic_policy_gradient" / "ppg.py").read_text()
    assert "ac = pd.sample()" in ppg, "ppg no longer samples its action from the torch distribution"


def _listing(path: pathlib.Path) -> dict[str, str]:
    body = path.read_text().split("#" + "-" * 99 + "\n", 1)[1]
    return {line.split()[2]: line.split(maxsplit=3)[3].lstrip("./") for line in body.splitlines()}


def test_ppg_600k_rows_bind_to_host_weights():
    """`ppg-600k-rows-bind-to-host-weights`: every committed ppg 600k row names a retained file.

    Recomputed from the committed records and the captured host listing, so it needs no host. A
    re-collected record file whose hashes are not in that listing fails here, and the bundle must
    be re-taken against whatever weights the new rows name.
    """
    import json
    import re

    raw = ROOT / "results" / "evidence" / "ppg-600k-rows-bind-to-host-weights" / "raw"
    weights = {**_listing(raw / "intermediate-weights.txt"), **_listing(raw / "terminal-weights.txt")}
    stamps = {m.group(1): int(m.group(2))
              for m in re.finditer(r"(model\d+\.jd) IC=(\d+)", (raw / "save-stamps.txt").read_text())}
    records = ROOT / "results" / "records"
    for name, terminal in (("reeval-v214-ppg-curve__records.jsonl", False),
                           ("reeval-v214-ppg-endpoint__records.jsonl", True)):
        rows = [json.loads(line) for line in (records / name).read_text().splitlines() if line.strip()]
        assert rows, name
        for row in rows:
            file = weights.get(row["checkpoint_sha256"])
            assert file, f"{name}: frame {row['frame']} names {row['checkpoint_sha256'][:16]}, not on the host"
            if terminal:
                assert file == "snapshot.pt", f"{name}: endpoint row reads {file}"
            else:
                assert stamps[file] == row["frame"], f"{name}: frame {row['frame']} reads {file} (IC {stamps[file]})"


def test_idaac_600k_endpoint_binds_to_host_weights():
    """`idaac-600k-endpoint-binds-to-host-weights`: one snapshot, the 600k run's, full coverage."""
    import collections
    import json

    raw = ROOT / "results" / "evidence" / "idaac-600k-endpoint-binds-to-host-weights" / "raw"
    production = set(_listing(raw / "snapshot-card0-20260909-035152.txt"))
    others = set()
    for run in ("card0-20260909-005543", "card0-20260909-013936", "card0-20260910-120437"):
        others |= set(_listing(raw / f"snapshot-{run}.txt"))
    rows = [json.loads(line) for line in
            (ROOT / "results" / "records" / "reeval-v214-idaac-endpoint__records.jsonl").read_text().splitlines()
            if line.strip()]
    assert {r["checkpoint_sha256"] for r in rows} <= production - others, (
        "an idaac endpoint row names a snapshot other than card0-20260909-035152's")
    assert {r["frame"] for r in rows} == {598016}
    cover = collections.Counter((r["conventions"]["eval_policy_mode"], r["regime"]) for r in rows)
    assert set(cover.values()) == {11} and len(cover) == 8, cover
