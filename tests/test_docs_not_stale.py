"""Numbers restated in prose must match the tool that produces them.

This project's recurring failure is not wrong reasoning, it is a true statement filed as a
permanent one. `docs/SYSTEM.md` opens with two instances; `pytest.ini` records a third, where a
stale measurement kept driving a live decision after the underlying number had doubled. The
deviation ledger is the current candidate: it is quoted in two documents and changes every time
a line is added to any clone.

So the totals are checked rather than maintained. If this test fails, the fix is to re-run
`python scripts/deviations.py` and paste the new numbers — not to relax the test.

**What it covers:** the grand total AND every per-baseline figure of the form
"`N files, +I / -D`" in `RUNNABLE-ORIGINALS.md`. The per-baseline check was added after the
totals check passed while *all six* section headers were stale — which is precisely the blind
spot the first version of this docstring named and then did nothing about.

**What it still cannot see:** every other prose claim in those documents. This is a floor under
the numbers, not a proof that the words around them are true.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = [ROOT / "docs" / "RUNNABLE-ORIGINALS.md", ROOT / "docs" / "STEP-ZERO.md",
        ROOT / "README.md",      # the front door quotes the total too, and is read first
        # The audit report quotes the ledger in its Sources footer, and it is the document most
        # likely to be read by someone outside the project -- so it is the worst one to let go
        # stale. It went stale within an hour of being written, which is why it is listed here.
        ROOT / "docs" / "AUDIT-2026-08-17.md"]


def ledger_totals():
    """(files, insertions, deletions, code_insertions) as scripts/deviations.py reports them."""
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "deviations.py")],
                       capture_output=True, text=True, timeout=300)
    m = re.search(r"^TOTAL\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$", r.stdout, re.M)
    if m is None:
        pytest.skip("scripts/deviations.py produced no TOTAL row "
                    f"(clones absent from this checkout?)\n{r.stdout[-600:]}")
    return tuple(int(g) for g in m.groups())


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_quoted_deviation_totals_match_the_ledger(doc: pathlib.Path):
    files, ins, dels, code = ledger_totals()
    text = doc.read_text()
    # Both spellings occur: "29 files, +807 / -118 (554 non-comment)" and the compact
    # "29 files, +807/-118 (554 non-comment)". Unicode minus too -- the docs use it.
    quoted = re.findall(r"(\d+)\s+files,\s*\+(\d+)\s*/\s*[-−]\s*(\d+)\s*\((\d+)\s+non-comment\)",
                        text)
    if not quoted:
        pytest.skip(f"{doc.name} quotes no ledger total")
    for got in quoted:
        assert tuple(int(g) for g in got) == (files, ins, dels, code), (
            f"{doc.name} says {files_str(got)} but scripts/deviations.py now reports "
            f"{files_str((files, ins, dels, code))}. Re-run it and update the document; do not "
            "loosen this test. A number quoted in prose is a snapshot, and this project's "
            "documented failure mode is snapshots filed as facts.")


def files_str(t) -> str:
    return f"{t[0]} files, +{t[1]}/-{t[2]} ({t[3]} non-comment)"


def per_baseline():
    """{name: (files, insertions, deletions)} from scripts/deviations.py."""
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "deviations.py")],
                       capture_output=True, text=True, timeout=300)
    return {m.group(1): tuple(int(g) for g in m.group(2, 3, 4))
            for m in re.finditer(r"^(\w+)\s+(\d+)\s+(\d+)\s+(\d+)\s+\d+\s", r.stdout, re.M)}


def test_per_baseline_figures_match_the_ledger():
    """Every "N files, +I / -D" in RUNNABLE-ORIGINALS.md must be some baseline's real row.

    Added because the totals check went green while all six per-baseline section headers were
    stale. A document can be right in aggregate and wrong in every line of its detail.
    """
    led = per_baseline()
    if not led:
        pytest.skip("scripts/deviations.py listed no clones")
    # A slimmed checkout reports some clones as INCOMPLETE and prints no numbers for them, so the
    # doc's per-baseline figures -- which quote a whole tree -- match nothing here. That is the
    # tool being honest, not the doc being stale; the isolated candidate carries clones missing
    # up to 462 tracked files. Skip rather than compare, exactly as the TOTAL test does.
    _raw = subprocess.run([sys.executable, str(ROOT / "scripts" / "deviations.py")],
                          capture_output=True, text=True, timeout=300).stdout
    if "INCOMPLETE:" in _raw:
        pytest.skip("some clones are not whole in this checkout, so deviations.py reports no "
                    "per-baseline numbers for them:\n"
                    + "\n".join(l for l in _raw.splitlines() if "INCOMPLETE:" in l))
    doc = (ROOT / "docs" / "RUNNABLE-ORIGINALS.md").read_text()
    valid = {(f, i, d) for (f, i, d) in led.values()}
    quoted = re.findall(r"(\d+)\s+files?,\s*\+(\d+)\s*/?\s*[-−]\s*(\d+)", doc)
    checked = 0
    for got in quoted:
        t = tuple(int(g) for g in got)
        if t[0] > 50:          # the grand total row; covered by the other test
            continue
        checked += 1
        assert t in valid, (
            f"RUNNABLE-ORIGINALS.md quotes '{t[0]} files, +{t[1]}/-{t[2]}', which matches no "
            f"baseline in scripts/deviations.py. Real rows: "
            + "; ".join(f"{k} {v[0]}/+{v[1]}/-{v[2]}" for k, v in sorted(led.items())))
    assert checked >= len(led), (
        f"only {checked} per-baseline figures found in the document but {len(led)} clones "
        "exist -- a baseline's row was probably dropped rather than updated")


# -- the patch registry's SIZE, which is quoted as a range and drifted for exactly that reason --

PATCH_DOCS = [ROOT / "docs" / "RUNNABLE-ORIGINALS.md", ROOT / "docs" / "STEP-ZERO.md",
              ROOT / "docs" / "INTEGRATION-DELTA.md", ROOT / "README.md"]


def highest_patch_id() -> int:
    """The largest N among the patch ids the registry actually DECLARES.

    Read from the declaration (`PATCH_CLASS`), not from the file's text. The first version
    regexed `\\bP(\\d+)\\b` over the whole source, so on 2026-08-19 a *comment* in
    `apply_patches.py` discussing a hypothetical, unimplemented P14 made this function report 14
    and failed all four documents for saying something true. That is the same defect the docstring
    below describes catching, aimed at the checker instead of the prose: matching the shape a
    declaration usually has rather than the declaration itself.

    `PATCH_CLASS` is authoritative because `tests/test_contract.py`'s
    `test_every_patch_declares_what_kind_of_change_it_is` pins that every family in `PATCHES` has
    an entry here, so the two cannot drift apart silently.
    """
    sys.path.insert(0, str(ROOT / "setup"))
    import apply_patches

    ids = {int(re.match(r"P(\d+)", k).group(1)) for k in apply_patches.PATCH_CLASS}
    return max(ids) if ids else 0


@pytest.mark.parametrize("doc", PATCH_DOCS, ids=lambda p: p.name)
def test_quoted_patch_range_matches_the_registry(doc: pathlib.Path):
    """"P1-P<N>" in prose must name the registry's real highest id.

    Added 2026-08-17 after an independent audit found the four documents disagreeing with the
    code and with each other: two said P1-P11, four said P1-P12, and `setup/apply_patches.py`
    had held P13 for some time. The registry's CONTENT was never at risk -- `Protocol.env_patches`
    hashes it and `tests/test_contract.py` pins the hash -- but nothing checked the number people
    actually read, so the one uncovered restatement was the one that rotted. That is the same
    shape as the per-baseline blind spot above, one level out.
    """
    top = highest_patch_id()
    if top == 0:
        pytest.fail("setup/apply_patches.py declares no P<N> ids at all -- the registry is "
                    "unreadable to this test, which is a failure and not a reason to skip")
    assert top < 100, ("the registry reached P100 and this test's two-digit matcher can no "
                       "longer tell a patch id from the Tesla P100 named in the docs")
    # The invariant is on the HIGHEST id a document mentions, not on each range it writes.
    # `RUNNABLE-ORIGINALS.md` legitimately says "P6-P13 (P1-P5 predate this part)": that lower
    # range is a true historical statement, and a test that read it as a claim about the
    # registry's extent would be demanding the document say something false.
    # At most two digits: a three-digit P-number in these documents is an NVIDIA card (the docs
    # name a Tesla P100 as the wrong-accelerator trap), not a patch id. The guard above keeps
    # that shortcut honest -- if the registry ever reaches P100 the test fails rather than
    # quietly starting to read GPU names as patch ids.
    text = doc.read_text()
    ids = [int(m) for m in re.findall(r"\bP(\d{1,2})[a-z]?\b", text)]
    if not ids:
        pytest.skip(f"{doc.name} mentions no patch ids")

    # A document may legitimately DISCUSS a patch that does not exist yet -- P14 is scoped in the
    # register and deliberately unimplemented, and `INTEGRATION-DELTA.md` explains what its
    # arrival would do to the numbers already produced. Refusing that sentence would push the
    # planning out of the documents and into nowhere. But an unmarked forward reference is
    # exactly the drift this test exists to catch, so a future id is allowed ONLY on a line that
    # says it is not real. Marking is the author's declaration; the test enforces that it exists.
    UNBUILT = re.compile(r"unimplemented|not (?:yet )?implemented|proposed|scoped|proposal|"
                         r"proposal|would (?:be|add)|hypothetical|proposed|future", re.I)
    for n in sorted({i for i in ids if i > top}):
        bad = [ln.strip() for ln in text.splitlines()
               if re.search(rf"\bP{n}\b", ln) and not UNBUILT.search(ln)]
        assert not bad, (
            f"{doc.name} names P{n}, above the registry's P{top}, on a line that does not mark "
            f"it as unbuilt: {bad[0][:110]!r}. Either the patch was implemented and PATCH_CLASS "
            "was not updated, or the sentence reads as a claim that P{n} exists.")

    present = [i for i in ids if i <= top]
    assert present and max(present) == top, (
        f"{doc.name}'s highest existing patch id is P{max(present) if present else 0}, but "
        f"setup/apply_patches.py declares P{top}. Either the document missed a patch or it names "
        "one that no longer exists. A patch added without touching the prose is how this drifted "
        "to three different answers across four files.")


def test_the_register_entry_count_is_true():
    """`REGISTER.md` closes with "(N entries as of ...)" and N was maintained by hand.

    It was wrong: the file claimed 65 as of 2026-08-16 when it held 67, so every later session
    that appended a row and incremented the figure carried the error forward. A count is the
    cheapest possible claim to check and the easiest to let rot, which is the exact pairing this
    project keeps finding.
    """
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parents[1]
    text = (root / "docs" / "REGISTER.md").read_text(encoding="utf-8", errors="replace")
    rows = len(re.findall(r"^\| 20\d\d-\d\d-\d\d ", text, re.M))
    m = re.search(r"\*\((\d+) entries as of", text)
    assert m, "the register no longer states an entry count"
    assert int(m.group(1)) == rows, (
        f"REGISTER.md claims {m.group(1)} entries and has {rows} dated rows. Update the closing "
        "line in the same commit as the row you added.")


def test_no_register_row_calls_itself_resolved_while_its_status_says_open():
    """A row whose prose says RESOLVED and whose status column says `open`.

    Found twice on 2026-09-04 by a manual sweep of all 137 dated rows -- the `sgqn`/P19 row and
    the C95 checkpoint row -- and both had been that way for a day or more. It matters because the
    two halves are read by different consumers: people read the prose, `scripts/open_decisions.py`
    reads the status column, so such a row inflates the open-findings count while looking closed
    to anyone who reads it. That is this project's signature join defect (STEP-ZERO section 8): a
    surface disagreeing with the thing it stands for, and the surface being trusted.

    Deliberately narrow. It keys on the BOLD `**RESOLVED` marker, which is a status claim, not on
    the word "resolved" or "withdrawn" appearing anywhere -- the 2026-08-18 nondeterminism row
    legitimately says "what is withdrawn is the unqualified claim" while the finding itself stands,
    and a test that nagged about rows like that would be turned off rather than fixed.
    """
    register = (ROOT / "docs" / "REGISTER.md").read_text(encoding="utf-8")
    offenders = []
    for line in register.splitlines():
        if not line.startswith("| 20"):
            continue
        cells = [c.strip() for c in line.split(" | ")]
        if "open" not in cells:
            continue
        if "**RESOLVED" in line:
            offenders.append(cells[0] + " " + cells[1][:90])
    assert not offenders, (
        "these rows claim **RESOLVED in their prose while their status column still reads `open`; "
        "people read the prose and open_decisions.py reads the status, so the row means two "
        "different things to two readers:\n  " + "\n  ".join(offenders))
