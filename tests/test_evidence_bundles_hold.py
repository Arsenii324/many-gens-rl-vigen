"""Every evidence bundle under `results/evidence/` still shows what it says it shows.

A bundle is `CLAIM.md` (the argument), `capture.sh` (how the evidence was taken),
`manifest.json` (what was taken, with hashes and facts) and `raw/*.txt` (the evidence itself,
captured by `scripts/capture_host_evidence.py`). The sources -- host logs, result archives --
may be gone by the time anyone reads this, so the repository copy is what has to stay honest:

* an excerpt edited after capture no longer matches its recorded hash;
* a fact whose anchor is not in its excerpt is an assertion, not evidence;
* an excerpt the manifest does not know, or a manifest entry with no file, means the two drifted;
* a header that says N lines matched must show N lines unless it says TRUNCATED;
* a claim may only name facts the manifest records, so prose cannot quote a number that was never
  captured.

What this cannot check is whether the claim's reasoning is right. `CLAIM.md` states that as its
own section, and `scripts/recheck_evidence.py` re-hashes the sources that still exist.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "results" / "evidence"
sys.path.insert(0, str(ROOT / "scripts"))
from capture_host_evidence import anchor_holds, split_excerpt  # noqa: E402

BUNDLES = sorted(p for p in EVIDENCE.iterdir() if p.is_dir()) if EVIDENCE.is_dir() else []
REQUIRED_CLAIM_SECTIONS = ("## Status", "## Chain", "## What this does not show", "## Falsifier")


def _manifest(bundle: pathlib.Path) -> dict:
    return json.loads((bundle / "manifest.json").read_text())


def test_there_are_bundles():
    assert BUNDLES, "results/evidence/ holds no bundles; the test below would pass vacuously"


@pytest.mark.parametrize("bundle", BUNDLES, ids=lambda p: p.name)
def test_bundle_is_complete(bundle):
    for name in ("CLAIM.md", "capture.sh", "manifest.json"):
        assert (bundle / name).is_file(), f"{bundle.name}: missing {name}"
    manifest = _manifest(bundle)
    assert manifest["slug"] == bundle.name, f"{bundle.name}: manifest slug is {manifest['slug']!r}"
    on_disk = {p.name for p in (bundle / "raw").glob("*.txt")}
    listed = {pathlib.Path(e["file"]).name for e in manifest["excerpts"].values()}
    assert on_disk == listed, (
        f"{bundle.name}: raw/ and manifest.json disagree -- only on disk: {sorted(on_disk - listed)}, "
        f"only in manifest: {sorted(listed - on_disk)}")
    recipe = (bundle / "capture.sh").read_text()
    for name in manifest["excerpts"]:
        assert re.search(rf"\$S {re.escape(name)} ", recipe), (
            f"{bundle.name}: excerpt {name!r} is not produced by capture.sh, so it cannot be re-taken")


@pytest.mark.parametrize("bundle", BUNDLES, ids=lambda p: p.name)
def test_excerpts_are_unedited_and_headers_are_honest(bundle):
    for name, entry in _manifest(bundle)["excerpts"].items():
        content = (bundle / entry["file"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == entry["sha256"], (
            f"{bundle.name}/{entry['file']} changed after capture; re-run capture.sh rather than editing it")
        header, body = split_excerpt(content.decode())
        shown = body.count("\n") + (1 if body and not body.endswith("\n") else 0)
        assert shown == entry["shown_lines"], f"{bundle.name}/{name}: {shown} lines, manifest says {entry['shown_lines']}"
        assert f"# matched-lines: {entry['matched_lines']}  shown-lines: {shown}" in header, (
            f"{bundle.name}/{name}: header line counts disagree with the manifest")
        if shown < entry["matched_lines"]:
            assert "TRUNCATED" in header, f"{bundle.name}/{name}: capped excerpt not marked TRUNCATED"
        if entry["source"]["kind"] == "host-file":
            assert entry["source"]["sha256"] in header, f"{bundle.name}/{name}: source hash missing from header"


@pytest.mark.parametrize("bundle", BUNDLES, ids=lambda p: p.name)
def test_every_fact_is_anchored_in_its_own_excerpt(bundle):
    manifest = _manifest(bundle)
    assert manifest["facts"], f"{bundle.name}: no facts recorded -- the claim rests on nothing checkable"
    for fact in manifest["facts"]:
        entry = manifest["excerpts"].get(fact["excerpt"])
        assert entry, f"{bundle.name}: fact {fact['key']} cites unknown excerpt {fact['excerpt']}"
        header, body = split_excerpt((bundle / entry["file"]).read_text())
        assert anchor_holds(fact["anchor"], header, body), (
            f"{bundle.name}: fact {fact['key']}={fact['value']} -- anchor {fact['anchor']!r} "
            f"is not in {entry['file']}")


@pytest.mark.parametrize("bundle", BUNDLES, ids=lambda p: p.name)
def test_claim_names_only_recorded_facts(bundle):
    claim = (bundle / "CLAIM.md").read_text()
    for section in REQUIRED_CLAIM_SECTIONS:
        assert section in claim, f"{bundle.name}/CLAIM.md lacks {section!r}"
    keys = {f["key"] for f in _manifest(bundle)["facts"]}
    cited = set(re.findall(r"\bfact:([A-Za-z0-9_]+)", claim))
    assert cited, f"{bundle.name}/CLAIM.md cites no facts (write them as fact:<key>)"
    unknown = cited - keys
    assert not unknown, f"{bundle.name}/CLAIM.md cites facts the manifest does not record: {sorted(unknown)}"
    excerpts = set(_manifest(bundle)["excerpts"])
    named = set(re.findall(r"raw/([A-Za-z0-9_.-]+)\.txt", claim))
    assert not (named - excerpts), f"{bundle.name}/CLAIM.md names missing excerpts: {sorted(named - excerpts)}"


def test_the_evidence_index_lists_every_bundle():
    index = (EVIDENCE / "README.md").read_text()
    missing = [b.name for b in BUNDLES if f"({b.name}/CLAIM.md)" not in index]
    assert not missing, f"results/evidence/README.md does not index: {missing}"


def test_anchor_rule_does_not_match_the_extraction_command():
    """The failure the body/header split exists to prevent, kept as a check of the helper itself."""
    header = "# extraction: cat log | grep -n -E 'nminibatch > ntrain'\n# matched-lines: 0  shown-lines: 0\n"
    assert not anchor_holds("nminibatch > ntrain", header, "")
    assert anchor_holds("header:# matched-lines: 0 ", header, "")
    assert not anchor_holds("header:# matched-lines: 0 ", "", "# matched-lines: 0 ")
