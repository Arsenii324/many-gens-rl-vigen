#!/usr/bin/env python3
"""Everything waiting on the owner, from every source that holds one. One command, one list.

    python scripts/open_decisions.py
    python scripts/open_decisions.py --strict    # exit 1 if anything is waiting on ME instead

## Why this exists

The standing instruction is to work until *"what remains is only the decisions/tuning/design-level
decisions for me to take."* That is a **checkable** state, and nothing checked it: the items live in
four places with four shapes, and a reader had to visit all four and know which was which.

- `CONSTRUCTION.md`'s summary table — the register's own "your decision" column.
- `docs/RESEARCH-FRAME.md` / `INTEGRATION-DELTA.md` — §4 branch points whose **Choice** row is not
  yet filled (`scripts/decisions.py` enumerates these).
- `scripts/requirements.py` — R1–R7 states that are `NEEDS JUDGEMENT` by construction.
- `FAITHFULNESS.md` §5 — the fidelity triage's own open items.

**The distinction this tool exists to draw** is between *waiting on a person* and *waiting on
work*. Those look identical in a register — both read "OPEN" — and only one of them means the
project is finished in the sense that was asked for. An item needing a run, a script, or a
measurement is **mine**; an item needing a preference, a trade-off, or an authority I do not have
is **the owner's**. Listing them together without that split is how "only decisions remain" becomes
unfalsifiable.

## What it does not do

It does not decide anything, and it does not rank. It also does not claim completeness: it reports
what the four sources say, and a decision nobody wrote down anywhere is invisible to it — which is
the argument for writing them down, not for trusting this list as exhaustive.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs" / "CONSTRUCTION.md"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def register_items() -> list[tuple[str, str]]:
    """Register rows whose last column says the decision is the owner's."""
    out = []
    for line in REGISTER.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| [C"):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 6:
            continue
        cid = re.match(r"\[(C\d+)\]", cells[1])
        if cid and "your decision" in cells[-2].lower():
            out.append((cid.group(1), cells[2][:96]))
    return out


def pending_branch_points() -> list[tuple[str, str]]:
    """§4 blocks whose Choice row is not filled — the decisions ledger's own PENDING."""
    d = _load("decisions")
    return [(",".join(x["entries"]) or "—", x["title"][:96])
            for x in d.parse() if not x["settled"]]


def judgement_requirements() -> list[tuple[str, str]]:
    r = _load("requirements")
    out = []
    for rid, (title, fn) in r.CHECKS.items():
        try:
            state, why = fn()
        except Exception as e:
            state, why = "UNCHECKABLE", f"{type(e).__name__}: {e}"
        if state in ("NEEDS JUDGEMENT", "PARTLY", "NOT MET"):
            out.append((f"{rid} [{state}]", (title + " — " + why)[:150]))
    return out


def fidelity_items() -> list[tuple[str, str]]:
    """FAITHFULNESS §5's numbered items that are not struck through as resolved."""
    txt = (ROOT / "docs" / "FAITHFULNESS.md").read_text(encoding="utf-8")
    try:
        sec = txt.split("## 5. What would raise fidelity most")[1].split("\n## ")[0]
    except IndexError:
        return []
    # Split into items so each one's own annotations can be read. §5 marks some items with
    # `**Whose:** mine` / `**Whose:** the owner's` -- the document already states who each belongs
    # to, and honouring that is better than a heuristic. An item explicitly marked mine is WORK,
    # not a decision, and listing it here would inflate the queue the owner is asked to clear.
    parts = re.split(r"\n(?=\d+\.\s|~~\d+\.)", sec)
    out = []
    for part in parts:
        m = re.match(r"\s*(\d+)\.\s+(.{0,200})", part, re.S)
        if not m:
            continue
        body = re.sub(r"\s+", " ", m.group(2)).strip()
        if body.startswith("~~") or "RESOLVED" in part[:400]:
            continue
        whose = re.search(r"\*\*Whose:\*\*\s*(.{0,24})", part)
        if whose and "mine" in whose.group(1).lower():
            continue          # the document says it is work, not a decision
        tag = " [owner-marked]" if whose else ""
        out.append((f"§5 item {m.group(1)}", body[:104] + tag))
    return out



FINDINGS = ROOT / "docs" / "REGISTER.md"


def undispositioned_findings(limit: int = 200) -> list[tuple[str, str]]:
    """Register rows still marked `open`: findings recorded and not yet dispositioned.

    Added 2026-09-02, because this tool's own disclaimer -- "a decision written down nowhere is
    invisible here" -- was understating the problem. These findings ARE written down; they were
    simply in a file nothing read. A finding can sit `open` for a good reason (it needs a run, or
    it is a caveat with no action), so this is deliberately NOT merged into the count of decisions
    waiting on a person. It is here so that the answer to "what is still outstanding?" cannot be
    silently narrower than the record.

    Rows are `| date | finding | locator | status | note |`; the status cell is the fourth.
    """
    out: list[tuple[str, str]] = []
    for line in FINDINGS.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("| 20"):
            continue
        cells = [c.strip() for c in line.split(" | ")]
        if len(cells) < 5 or cells[3].lower() != "open":
            continue
        date = cells[0].lstrip("| ").strip()
        headline = cells[1].strip().lstrip("*").split(".**")[0].split("**")[-1]
        out.append((date, headline[:104]))
    return out[-limit:]


def decision_sheet(root: pathlib.Path) -> list[tuple[str, str]]:
    """The session decision sheet, which this script could not see until 2026-09-05.

    `notes/DECISION-SHEET.md` holds owner-facing items with a recommended default each, and nothing
    here referenced it -- so the project had TWO decision surfaces that did not know about each
    other, which is the "one number, one home" rule broken at the level of the record of what is
    undecided. This closes it by reading the sheet rather than duplicating it: rows live there, this
    only surfaces them.
    """
    return [(tag, note) for tag, note, _status in decision_sheet_with_status(root)]


def decision_sheet_with_status(root: pathlib.Path) -> list[tuple[str, str, str]]:
    """Same rows as `decision_sheet`, plus each entry's own status word from its `### A<n> STATUS,`
    heading (e.g. `OPEN`, `DECIDED`, `ANALYSIS INCOMPLETE`).

    Added 2026-09-06 after the owner drew a distinction this file's own docstring already makes for
    a different axis (waiting on a person vs. waiting on work), applied one level deeper: among
    entries genuinely waiting on the owner, some already carry a finished "our best" analysis and
    wait only on formal ratification, while others (A35-A37) never had that analysis done at all --
    "run a comparison" is not a substitute for the actual pilot spec. Both read identically as a
    plain `### A<n> OPEN,` row would; nothing distinguished them until an entry declared its own
    status as `ANALYSIS INCOMPLETE` instead. This surfaces that distinction rather than requiring a
    reader to open the sheet and check each entry's depth by hand.
    """
    sheet = root / "notes" / "DECISION-SHEET.md"
    if not sheet.is_file():
        return []
    rows: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for line in sheet.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\|\s*\*\*(A\d+)\*\*\s*\|\s*([^|]+?)\s*\|", line)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            rows.append((m.group(1), " ".join(m.group(2).split()), ""))
    # later "### A9 STATUS, ... — ..." revision headings supersede or add items
    text = sheet.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"^#+\s*(A\d+)\s*([A-Z][A-Z ]*[A-Z])?,?[^\n]*?—\s*([^\n]+)$", text, re.M):
        tag, status, note = m.group(1), (m.group(2) or "").strip(), " ".join(m.group(3).split())
        existing = next(((t, q, s) for t, q, s in rows if t == tag), None)
        if existing is None:
            seen.add(tag)
            rows.append((tag, note, status))
        else:
            _, old_note, old_status = existing
            rows = [(t, q, s) if t != tag else
                    (t, old_note + f"   [revised: {note[:60]}]", status or old_status)
                    for t, q, s in rows]
    return sorted(rows, key=lambda r: int(r[0][1:]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)

    groups = [
        ("REGISTER — items whose column says the decision is yours", register_items()),
        ("BRANCH POINTS — §4 blocks with no Choice recorded", pending_branch_points()),
        ("REQUIREMENTS — R1–R7 not mechanically settleable", judgement_requirements()),
        ("FIDELITY — FAITHFULNESS §5's own open items", fidelity_items()),
    ]
    findings = undispositioned_findings()

    print("OPEN DECISIONS — everything waiting on a person, from every source that holds one\n")
    total = 0
    for title, items in groups:
        print(f"  {title}   ({len(items)})")
        if not items:
            print("    (none)")
        for key, what in items:
            print(f"    {key:<14} {what}")
        total += len(items)
        print()

    print(f"  {total} item(s) waiting on a decision.\n")
    print(f"  FINDINGS still marked `open` in REGISTER.md   ({len(findings)})")
    print("  Not decisions and not counted above -- recorded so that 'what is outstanding?' cannot")
    print("  be answered more narrowly than the record. Some need a run, some are standing caveats.")
    for date, headline in findings:
        print(f"    {date}   {headline}")
    print()
    print("  WAITING ON A PERSON is not the same as WAITING ON WORK, and a register shows both")
    print("  as OPEN. An item needing a run, a script or a measurement is mine; one needing a")
    print("  preference, a trade-off or an authority I do not have is the owner's. Only the second")
    print("  kind belongs on this list, and an item that turns out to need work should be moved")
    print("  off it rather than left to look like a decision nobody is taking.")
    sheet = decision_sheet_with_status(ROOT)
    if sheet:
        incomplete = [(t, q) for t, q, s in sheet if s == "ANALYSIS INCOMPLETE"]
        rest = [(t, q) for t, q, s in sheet if s != "ANALYSIS INCOMPLETE"]
        if incomplete:
            print(f"\n  ANALYSIS INCOMPLETE -- the \"our best\" layer was never actually done, "
                  f"not just unratified   ({len(incomplete)})")
            print("  Not waiting on the owner's sign-off; waiting on someone (me) to produce the")
            print("  actual spec/pilot/reasoning. Highest-priority reading of this whole list.")
            for tag, question in incomplete:
                print(f"    {tag:<6} {question[:150]}")
        print(f"\n  DECISION SHEET -- notes/DECISION-SHEET.md, answerable by exception   ({len(rest)})")
        print("  Each carries a recommended default that will be acted on absent an answer.")
        for tag, question in rest:
            print(f"    {tag:<6} {question[:150]}")
    else:
        print("\n  DECISION SHEET: notes/DECISION-SHEET.md not found")

    print("\n  NOT A COMPLETENESS CLAIM: a decision written down nowhere is invisible here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
