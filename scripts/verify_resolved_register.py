#!/usr/bin/env python3
"""Is every `resolved` row in the register actually resolved? Checks, does not trust.

    python scripts/verify_resolved_register.py              # structure + citations (fast)
    python scripts/verify_resolved_register.py --run-tests  # also execute every pinning test
    python scripts/verify_resolved_register.py --render      # regenerate docs/RESOLVED-REGISTER.md

## Why a register needs a verifier

`docs/RECORDING-A-RESOLVED-FINDING.md` defines `resolved` as: the whole path walked, the alternative
ruled out, **a falsifier stated, and a test pinning it**. A register whose rows merely *assert* that
is the same artifact this project keeps finding stale -- a confident claim with a citation nobody
re-checks. So each row is held to its own definition:

1. **Citations resolve.** Every `evidence` entry is `path:line`; the file exists and the line exists.
   A bare basename matching several files is AMBIGUOUS and fails, because `ppo.py:130` matches nine
   files in this tree and a citation that cannot say which one it read is how a stale story survives.
2. **A falsifier is stated.** A finding with no falsifier is an opinion.
3. **A pinning test exists** -- and with `--run-tests`, passes. A `resolved` row with no test is
   DOWNGRADED to `traced` in the report, loudly, because by our own definition it is not resolved.

## What it deliberately does not check

That the verdict is *correct*. That is not automatable, and a checker claiming it would be the exact
overclaim the register exists to prevent. It checks that the evidence still leads where the row says
and that something fails when the row stops being true.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs" / "resolved-register.json"
RENDERED = ROOT / "docs" / "RESOLVED-REGISTER.md"
CITATION = re.compile(r"^(.+?):(\d+)$")

_INDEX: dict[str, list[pathlib.Path]] | None = None


def _index() -> dict[str, list[pathlib.Path]]:
    global _INDEX
    if _INDEX is None:
        skip = {".git", "__pycache__", ".venv", ".mypy_cache", ".pytest_cache"}
        found: dict[str, list[pathlib.Path]] = {}
        for path in ROOT.rglob("*"):
            if path.is_file() and not skip.intersection(path.parts):
                found.setdefault(path.name, []).append(path)
        _INDEX = found
    return _INDEX


def check_citation(ref: str) -> str | None:
    match = CITATION.match(ref)
    if not match:
        return f"{ref!r} is not `path:line`"
    rel, number = match.group(1), int(match.group(2))
    target = ROOT / rel
    if "/" not in rel:
        matches = _index().get(rel, [])
        if len(matches) > 1:
            return f"{ref} is AMBIGUOUS across {len(matches)} files -- qualify the path"
        if len(matches) == 1:
            target = matches[0]
    if not target.is_file():
        return f"{ref} -- file missing"
    lines = target.read_text(errors="replace").splitlines()
    if number > len(lines):
        return f"{ref} -- past end ({len(lines)} lines)"
    return None



def parse_pytest_outcome(stdout: str, returncode: int) -> list[str]:
    """Which pinning tests failed, and did the run itself fail in a way we could not parse?

    [Claude 2026-09-10] This is a function rather than four lines inside main() because those four
    lines shipped with the exact defect this whole register refuses. They read
    `line.startswith("FAILED")` against pytest's COLOURED output, where the line really begins
    `\x1b[31mFAILED`. Nothing matched, the run reported `0 failure(s)` and exited 0 -- while pytest
    had exited 1 over a genuinely stale artifact. An instrument that could not run must never read
    as one that ran, and that includes this one.

    So the EXIT CODE decides. The parsed lines only name which test; a non-zero exit with nothing
    parsed is reported as its own problem rather than swallowed.
    """
    plain = re.sub(r"\x1b\[[0-9;]*m", "", stdout or "")
    failed = [l for l in plain.splitlines() if l.startswith("FAILED")]
    problems = [f"pinning test FAILED: {line}" for line in failed]
    if returncode != 0 and not failed:
        tail = "\n      ".join(plain.strip().splitlines()[-4:])
        problems.append(
            f"pytest exited {returncode} but no FAILED line was parsed -- a collection error, an "
            f"internal error, or an output format this parser does not read. Last lines:\n      {tail}")
    return problems



def check_evidence_semantics(entry: dict, root) -> list[str]:
    """A citation that resolves can still point at the wrong line.

    [Claude 2026-09-14] Found live: a row cited `families.json:1083` for a curve-depth decision.
    The line resolves -- the file has 1083 lines -- but it holds `save_every_reason`, a different
    field entirely; the text meant was at :166. Line-range checking cannot catch that, and the row
    read as verified. So a row may declare `evidence_expect`, mapping a citation to a substring the
    cited line (or the two around it) MUST contain. Optional, because most citations point at a
    file rather than a claim; mandatory in effect wherever a row leans on one exact line.
    """
    problems = []
    for citation, expected in (entry.get("evidence_expect") or {}).items():
        path, _, lineno = citation.rpartition(":")
        target = root / path
        if not target.is_file():
            problems.append(f"{entry['id']}: evidence_expect cites missing file {path}")
            continue
        try:
            lines = target.read_text(errors="replace").splitlines()
            i = int(lineno)
        except (ValueError, OSError):
            problems.append(f"{entry['id']}: evidence_expect citation {citation} is unparseable")
            continue
        window = "\n".join(lines[max(0, i - 2):i + 1])
        if expected not in window:
            problems.append(
                f"{entry['id']}: {citation} does not contain {expected!r} -- the citation resolves "
                f"but points at the wrong content")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()

    doc = json.loads(REGISTER.read_text())
    entries = doc["entries"]
    problems: list[str] = []
    downgraded: list[str] = []

    seen_ids: set[str] = set()
    for entry in entries:
        eid = entry.get("id", "<no id>")
        if eid in seen_ids:
            problems.append(f"{eid}: duplicate id")
        seen_ids.add(eid)
        for field in ("question", "verdict", "why", "domain", "status"):
            if not entry.get(field):
                problems.append(f"{eid}: empty {field}")
        if entry.get("status") not in {"observed", "traced", "resolved"}:
            problems.append(f"{eid}: status {entry.get('status')!r} is not one of observed/traced/resolved")
        for ref in entry.get("evidence") or []:
            bad = check_citation(ref)
            if bad:
                problems.append(f"{eid}: {bad}")
        if entry.get("status") == "resolved":
            if not entry.get("falsifier"):
                problems.append(f"{eid}: status=resolved with no falsifier")
            pinned = entry.get("pinned_by") or []
            missing = [t for t in pinned if not (ROOT / t).is_file()]
            for t in missing:
                problems.append(f"{eid}: pinning test {t} does not exist")
            if not pinned:
                downgraded.append(eid)

    for entry in entries:
        problems.extend(check_evidence_semantics(entry, ROOT))

    if args.run_tests:
        tests = sorted({t for e in entries for t in (e.get("pinned_by") or [])
                        if (ROOT / t).is_file()})
        if tests:
            print(f"  running {len(tests)} pinning test file(s)...")
            # [Claude 2026-09-10] `--color=no` and the ANSI strip are not belt-and-braces, they
            # are the bug this block shipped with. pytest colours its summary, so `FAILED` is
            # really `\x1b[31mFAILED`, `startswith` matched nothing, and a failing suite parsed as
            # zero failures. The exit code is now what DECIDES; the parsed lines only name which
            # test, and a non-zero exit with nothing parsed is itself reported rather than
            # swallowed. This verifier exists to enforce "an instrument that could not run must
            # never read as one that ran" -- it must not be the instrument that does it.
            proc = subprocess.run([sys.executable, "-m", "pytest", *tests, "-q",
                                   "-p", "no:cacheprovider", "--color=no"],
                                  capture_output=True, text=True, cwd=ROOT, timeout=3600)
            outcome = parse_pytest_outcome(proc.stdout, proc.returncode)
            problems.extend(outcome)
            print(f"  pytest exit={proc.returncode}, {len(outcome)} problem(s)")

    if args.render:
        RENDERED.write_text(render(doc, downgraded))
        print(f"  wrote {RENDERED.relative_to(ROOT)}")

    by_status: dict[str, int] = {}
    for entry in entries:
        by_status[entry["status"]] = by_status.get(entry["status"], 0) + 1
    print(f"\n{len(entries)} entries: " + ", ".join(f"{n} {s}" for s, n in sorted(by_status.items())))
    if downgraded:
        print(f"\n{len(downgraded)} row(s) claim `resolved` with NO pinning test. By this project's own")
        print("definition that is `traced`, not `resolved`. They are rendered as such:")
        for eid in downgraded:
            print(f"    {eid}")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for problem in problems:
            print(f"    {problem}")
        return 1
    print("\nEvery citation resolves and every stated pinning test exists.")
    return 0


def render(doc: dict, downgraded: list[str]) -> str:
    out: list[str] = []
    add = out.append
    add("<!-- GENERATED by scripts/verify_resolved_register.py --render — do not edit by hand. -->")
    add("<!-- Source of truth: docs/resolved-register.json -->")
    add("")
    add("# The resolved register")
    add("")
    add("**One row per question this project has settled, so it is not re-derived — and, more")
    add("importantly, not re-opened, re-argued for ten minutes, and acted on backwards.** That has")
    add("happened here: `ppg-nminibatch` went through three defensible conclusions before the right")
    add("one, and `ctrl-cudnn-on-volta` has had two wrong theories, one of which was acted on.")
    add("")
    add("Only **`resolved`** may be quoted as fact. `traced` means the mechanism is understood and")
    add("the consequence is not settled. A row claiming `resolved` without a pinning test is")
    add("rendered as `traced`, because [`RECORDING-A-RESOLVED-FINDING.md`](RECORDING-A-RESOLVED-FINDING.md)")
    add("defines `resolved` as including one.")
    add("")
    add("Verified by `scripts/verify_resolved_register.py`: every citation resolves, every pinning")
    add("test exists, and with `--run-tests` every one of them passes. **It does not check that a")
    add("verdict is correct** — that is not automatable, and claiming it would be the overclaim this")
    add("register exists to prevent.")
    add("")
    domains: dict[str, list[dict]] = {}
    for entry in doc["entries"]:
        domains.setdefault(entry["domain"], []).append(entry)
    for domain in sorted(domains):
        add(f"## {domain}")
        add("")
        for entry in domains[domain]:
            status = entry["status"]
            if entry["id"] in downgraded:
                status = "traced (claimed resolved, no pinning test)"
            add(f"### `{entry['id']}` — **{status}**")
            add("")
            add(f"**Q.** {entry['question']}")
            add("")
            add(f"**Verdict.** {entry['verdict']}")
            add("")
            add(f"**Why.** {entry['why']}")
            add("")
            if entry.get("evidence"):
                add("**Evidence.** " + ", ".join(f"`{e}`" for e in entry["evidence"]))
                add("")
            if entry.get("falsifier"):
                add(f"**Falsified by.** {entry['falsifier']}")
                add("")
            if entry.get("pinned_by"):
                add("**Pinned by.** " + ", ".join(f"`{t}`" for t in entry["pinned_by"]))
                add("")
            if entry.get("supersedes"):
                add(f"**Supersedes.** {entry['supersedes']}")
                add("")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
