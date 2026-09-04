#!/usr/bin/env python3
"""Check that `file.py:123`-style citations resolve, and point where they claim to.

    python scripts/check_citations.py            # report
    python scripts/check_citations.py --strict   # exit 1 if any citation is BROKEN

## Why

This repo's epistemic structure rests on citations. `policies.py:161` is the difference between
"the reference does X" being a mechanical claim and it being an argument-shaped one. Nothing has
ever checked that those line numbers resolve — and line numbers drift silently whenever a
reference is re-cloned at a different commit, which turns a checked claim back into a remembered
one without anyone noticing.

## What it can and cannot decide

The honest limit is **ambiguity**, and it is the majority case, so it is reported separately
rather than folded into a failure count:

  RESOLVED    the path is unique in this tree and the line exists     -> checkable
  BROKEN      unique path, line is PAST END OF FILE                   -> a real defect
  MISSING     a *repo-relative* path that does not exist and git has  -> a real defect
              never heard of
  HISTORICAL  a repo-relative path git knows was deleted              -> NOT a defect
  EXTERNAL    outside this tree, or relative to a reference repo's    -> NOT a defect
              own layout (`~/Downloads/...`, `common/model.py`)
  AMBIGUOUS   a bare basename matching several files (`model.py:88`)  -> NOT a defect

Only BROKEN and MISSING are failures.

**Tuned down after its first run, and the tuning is the interesting part.** That run reported
427 citations, **0 BROKEN**, and 54 "MISSING" — of which essentially all were legitimate citation
styles this script did not model: `onpolicy_ext.py` cited by log entries *about a file that was
deliberately deleted*; `~/Downloads/...` and sibling-project paths that are outside the tree by
construction; and `common/model.py`, which is a path inside the *reference's* layout, not ours.
Counting those as defects would have made the instrument noise, and a check that cries wolf is
worse than no check — so they are now separated out and only genuinely repo-relative, never-known
paths count.

**What the existence check cannot do:** verify that the cited line *says what the citing text
claims*. It checks that a line exists, not that it means anything. A citation can resolve
perfectly and still be wrong about its content.

## `--content`: the part that was called a reading problem, and mostly is not

The paragraph above used to end "that is a reading problem and stays one." Measured against the
corpus, that was too pessimistic: **55% of citations here are written with the cited code quoted
in a span right next to them** —

    `train.py:128` -- `global_frame = global_step * action_repeat`

That span *is* the claim about that line, so it can be checked. `--content` extracts it and asks
where the text actually sits. This matters more than line-existence ever did, because the failure
SYSTEM.md predicted — "line numbers drift silently when a reference is re-cloned" — is invisible
to the existence check and obvious to this one. A file that grew by 40 lines still contains line
128; it just no longer says what we said it says.

The anchor also **disambiguates**. A bare `algo.py:203` matches several trees and the existence
check gives up (AMBIGUOUS, 53% of the corpus). If exactly one candidate has the anchor text at
that line, content resolves what the path could not.

Verdicts, and what each is worth:

  CONFIRMED   anchor sits in the cited range, and is rare in the file   -> the strong case
  WEAK        anchor sits in the cited range but recurs many times      -> passed, proves little
              (`/255.` occurs 30x; matching it at the cited line is
              close to free, so it is NOT counted as confirmation)
  DRIFT       anchor is in the file, but at a different line            -> the citation is stale;
              the offset is reported, and it is a real defect
  ABSENT      anchor is nowhere in the file                             -> wrong file, or the
                                                                           claim was never true
  UNANCHORED  no usable code span next to the citation                  -> not checkable, not wrong

WEAK is separated out on purpose. Folding it into CONFIRMED would let a 90%-pass headline rest on
matches that a random line would also have produced, which is the same vacuity that made the
existence check report 0 defects across 677 citations.

## Measured precision, and why this is a lead generator rather than a verdict

**7 of the 22 starred defects were hand-checked against the files: 4 real, 3 false — ≈57%.**
Stated because an unmeasured defect count is exactly the kind of number this project exists to
distrust, and because the first 4 checked were all real, which would have supported a much
better-sounding and less true claim.

The real ones are stale line numbers into the port, all drifting *later*: `rlgen/envs.py:113` is
a blank line, `rlgen/agents.py:312` is `__getattr__` rather than the `on_policy = True` it is
cited for. Nothing else in this repo would have found them.

The false ones are a single class, and it is the instrument's permanent ceiling: **the document
quotes a construct in its own notation rather than the file's.** `docs/independent-audit` writes
GAE as `(1 - done[t])` where `ppo_daac_idaac/storage.py` spells it `self.masks[step + 1]`. The
citation is correct, the prose is clearer than the source, and no textual matcher can bridge
that. So a starred row means *"re-read this line"*, never *"this is wrong"*.
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

SCAN_GLOBS = ["docs/*.md", "*.md", "rlgen/**/*.py", "scripts/*.py", "tests/*.py", "tools/*.py"]
SKIP_PARTS = {".git", "__pycache__", "ext", "RL-ViGen-upstream", "_upstream_1678e4a",
              "third_party", ".venv", "runs", "outputs"}

# `some/path/file.py:123`, `file.py:12-34`, `file.py:12,34`
CITE = re.compile(r"(?<![\w/.])([\w./-]+\.(?:py|md|ya?ml))[:](\d+)(?:[-,](\d+))*")


# This checker's own tests cite deliberately wrong lines -- that is what they assert on. Reading
# them as claims about the repo makes the instrument report its own fixtures as defects.
SKIP_FILES = {"tests/test_citation_content.py"}


def scan_targets() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for g in SCAN_GLOBS:
        for p in ROOT.glob(g):
            rel = p.relative_to(ROOT)
            if p.is_file() and not (set(rel.parts) & SKIP_PARTS) and str(rel) not in SKIP_FILES:
                out.append(p)
    return sorted(set(out))


def build_index() -> dict[str, list[pathlib.Path]]:
    """basename -> every file with that name, anywhere (ext/ included: citations point there)."""
    idx: dict[str, list[pathlib.Path]] = collections.defaultdict(list)
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        parts = set(p.relative_to(ROOT).parts)
        if ".git" in parts or "__pycache__" in parts:
            continue
        idx[p.name].append(p)
    return idx


# Top-level directories that make a citation genuinely repo-relative, so a failure to
# resolve is OUR defect rather than a reference's layout or someone else's tree.
OURS = ("rlgen/", "docs/", "tests/", "tools/", "scripts/", "configs/", "baselines/")


def _have_history() -> bool:
    """Is there a git repository here at all? Cached; queried once.

    This is not the same question as "did git know this path", and conflating them is what made
    `mutants/run.py` unusable for as long as it existed. That runner mutates a COPY of the tree
    (correctly -- `RIGOR.md` section 7.3) and excludes the 516 MB `.git` from the copy. So every
    `_git_knew` call in a mutant tree returned False, every HISTORICAL citation reclassified as
    MISSING, and the runner's own sanity gate -- "an unmutated copy must PASS" -- failed every
    time. Mutation testing reported a fatal error that looked like a citation defect, and the real
    cause was that the checker silently requires a repository it was not given.

    `.git` cannot simply be symlinked into the copy: `tests/test_greenmark.py` calls
    `git write-tree`, which writes objects, and a mutant tree must not write to the real
    repository's object store.
    """
    global _HISTORY
    if _HISTORY is None:
        import subprocess
        r = subprocess.run(["git", "rev-parse", "--git-dir"],
                           cwd=ROOT, capture_output=True, text=True)
        _HISTORY = r.returncode == 0
    return _HISTORY


_HISTORY: bool | None = None


def _git_knew(cite: str) -> bool:
    """Did this path ever exist here? A log entry about a deliberately deleted file
    (`onpolicy_ext.py`) is a correct citation to a thing that is correctly gone.

    Returns False when there is no repository, and callers must consult `_have_history()` before
    treating that False as evidence -- absence of history is not evidence of absence.
    """
    if not _have_history():
        return False
    import subprocess
    r = subprocess.run(["git", "log", "--all", "--oneline", "-1", "--", cite],
                       cwd=ROOT, capture_output=True, text=True)
    return bool(r.stdout.strip())


def resolve(cite: str, idx) -> tuple[str, pathlib.Path | None]:
    if "/" in cite:
        direct = ROOT / cite
        if direct.is_file():
            return "RESOLVED", direct
        # a partial path like `coinrun/coinrun/policies.py` -- match as a suffix
        hits = [p for p in idx.get(pathlib.PurePath(cite).name, [])
                if str(p).endswith(cite)]
        if len(hits) == 1:
            return "RESOLVED", hits[0]
        if len(hits) > 1:
            return "AMBIGUOUS", None
        if cite.startswith(OURS):
            if _git_knew(cite):
                return "HISTORICAL", None
            # Without a repository the checker cannot tell "deliberately deleted" from "broken".
            # Reporting MISSING there would be an absence of evidence presented as evidence -- the
            # same failure `scripts/watch_divergence.py` returns BLIND for.
            return ("MISSING", None) if _have_history() else ("UNCLASSIFIABLE", None)
        return "EXTERNAL", None      # a reference repo's own layout, or another tree
    hits = idx.get(cite, [])
    if len(hits) == 1:
        return "RESOLVED", hits[0]
    if len(hits) > 1:
        return "AMBIGUOUS", None
    return ("HISTORICAL", None) if _git_knew(cite) else ("EXTERNAL", None)


# --- content anchoring -------------------------------------------------------------------
# How far from the citation a code span may sit and still be read as describing it. In
# characters across the whole document, not within one line: this prose wraps at ~100 columns,
# so an anchor one line away is ~100 characters away and a per-line window never sees it.
NEAR = 200
# A failing anchor only counts as a defect if it is bound this tightly to the citation.
TIGHT = 60
RANK = {"CONFIRMED": 0, "PARAPHRASE": 1, "WEAK": 2, "DRIFT": 3, "ABSENT": 4}


def mask_fences(text: str) -> str:
    """Blank out ``` fenced blocks, preserving length so offsets stay valid.

    Fences break backtick pairing: a document with one fenced block has every span after it
    paired off-by-one, which silently turns code into prose and prose into code.
    """
    out, fence = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
            out.append(" " * len(line))
        else:
            out.append(" " * len(line) if fence else line)
    return "\n".join(out)
# A cited line often names a `def` whose body carries the quoted text, and prose cites a
# 2-3 line construct by its first line. Allow that much slack before calling it drift.
SLACK = 3
# Above this many occurrences in the file, matching the anchor at the cited line is close to
# free and confirms nothing. Tuned by the `/255.` case, which recurs throughout preprocessing.
RARE = 3


def usable_anchor(span: str) -> bool:
    """Is this code span specific enough to check a line against?

    Rejecting prose is the whole job. A first version accepted any span containing `.` or `)`,
    which let through `` `. As released, ` `` and `` `), ` `` -- both of which would "confirm"
    against almost any line and turn the check into decoration.
    """
    s = span.strip()
    if len(s) < 4:
        return False
    # A span crossing a line break is prose the pairing walked into, not a quoted line.
    if "\n" in span:
        return False
    # Non-ASCII means the author's own notation, not source text: `Adam(lr=3e-4, B1=0.9)`
    # written with Greek betas, `nn.Linear(2048, ·)` with a placeholder dot. Real Python here
    # is ASCII, so this separates "quoted from the file" from "described by the writer".
    if not s.isascii():
        return False
    # A span that is itself a citation is not evidence about another citation. Two citations on
    # one line were reading each other as anchors, which is where most of the first run's 256
    # "ABSENT" came from.
    if CITE.search(s):
        return False
    # A path or filename is a pointer to somewhere else, not a quote of the cited file.
    # `nets.py`, `reward_normalizer.py`, `rlgen/envs.py::_assert_contract` were all being
    # tested for presence *inside the file they point away from*, which they never are.
    if re.search(r"[\w-]+\.(?:py|md|ya?ml|sh|json|txt)\b", s) or "::" in s:
        return False
    # Prose that merely touches punctuation. `), and `, `) — unlike `, ` (module docstring
    # point 5), ` all passed a naive "contains a bracket" test and confirmed nothing.
    if re.match(r"^[)\]},;:.\s—-]", s) and not re.match(r"^\)\s*$", s):
        return False
    codey = bool(re.search(r"[=(){}\[\]]|\w\.\w|_|/\d|\d/", s))
    if not codey:
        return False
    words = [t for t in s.split() if t.isalpha()]
    return not (len(words) >= 2 and not re.search(r"[=({\[]|\w\.\w|_|=", s))


def spans_of(line: str) -> list[tuple[int, int, str]]:
    """Backtick spans with positions, paired from the START of the line.

    Pairing matters: the citation itself is usually inside a span, so slicing a window at the
    citation's end begins *mid-span* and the first backtick found is a closing one. Searching
    that window then captures the prose BETWEEN two code spans and calls it code.
    """
    return [(m.start(1), m.end(1), m.group(1)) for m in re.finditer(r"`([^`]{3,90})`", line)]


def anchors_of(line: str, m: re.Match) -> list[str]:
    """EVERY usable code span near the citation, nearest first.

    Taking only the nearest span was wrong, and the case that showed it is instructive:

        RL-ViGen's own configs set `action_repeat: 2` (`cfgs/config.yaml:10`,
        `cfgs/svea_config.yaml:9`) ... We run `action_repeat=1`, because ...

    The nearest span *after* the citation is `action_repeat=1` -- our value, not the cited file's.
    The prose is exactly right; the checker picked the wrong quote and called the document wrong.
    A citation holds if ANY quoted code beside it sits at that line, so all of them are tried.
    """
    out = []
    for s, e, span in spans_of(line):
        if s <= m.start() and m.end() <= e:      # the citation's own span
            continue
        d = s - m.end() if s >= m.end() else m.start() - e
        if d > NEAR or not usable_anchor(span):
            continue
        # A blank line between them ends the thought; anything past it is a different claim.
        between = line[min(e, m.start()):max(s, m.end())]
        if "\n\n" in between:
            continue
        # A `|` between them, on a table row, means they sit in DIFFERENT CELLS. Added
        # 2026-08-19 after this checker reported two correct citations as drifted: in a
        # per-baseline wiring table each row cites its own file, and the nearest span to row N's
        # citation was row N+1's code. Anchoring across a cell boundary quotes one row's code at
        # another row's citation, which is a defect in the checker, not the document. Scoped to
        # table rows so a shell pipe in ordinary prose still anchors normally.
        if line.lstrip().startswith("|") and "|" in between:
            continue
        out.append((d, span))
    return sorted(out, key=lambda t: t[0])


DOTTED = re.compile(r"^([A-Za-z_]\w*)\.([A-Za-z_]\w*)$")
CALL = re.compile(r"^([A-Za-z_][\w.]*)\(")


def enclosing_symbols(lines: list[str], lineno: int) -> set[str]:
    """`def`/`class` names whose body contains this line, by indentation.

    This is what makes a *qualified symbol* anchor checkable. `rlgen/agents.py:83` annotated
    `DrQV2Adapter.act` cites the last line of that method -- `return np.clip(a, -1.0, 1.0)`.
    The literal string `DrQV2Adapter.act` appears nowhere in the file, so a text match calls a
    precise, correct citation ABSENT. What the citation actually claims is a scope, so scope is
    what gets checked.
    """
    out: set[str] = set()
    if not (1 <= lineno <= len(lines)):
        return out
    indent = len(lines[lineno - 1]) - len(lines[lineno - 1].lstrip())
    for i in range(lineno - 1, -1, -1):
        ln = lines[i]
        if not ln.strip():
            continue
        ind = len(ln) - len(ln.lstrip())
        if ind < indent or (i == lineno - 1):
            d = re.match(r"\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)", ln)
            if d:
                out.add(d.group(1))
                indent = ind
            elif ind < indent:
                indent = ind
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def needles(anchor: str) -> list[str]:
    """Forms the anchor could take in source. Documents quote code the way prose needs it.

    `act()` is written with empty parens for a method that takes arguments; `action_repeat=1`
    describes a YAML line spelled `action_repeat: 2`. Matching only the literal makes the
    instrument reject correct citations for being written in English.
    """
    a = anchor.strip()
    out = [_norm(a)]
    c = CALL.match(a)
    if c:
        out.append(_norm(c.group(1) + "("))
    if "=" in a and "==" not in a:
        out.append(_norm(a.replace("=", ":", 1)))
    if ":" in a:
        out.append(_norm(a.replace(":", "=", 1)))
    return list(dict.fromkeys(out))


_FILE_CACHE: dict[tuple, list[str]] = {}


def _lines(path: pathlib.Path) -> list[str] | None:
    """Read with a cache keyed on (path, mtime, size), not on path alone.

    Keying on path alone was a real bug, found by this tool's own test: a checker whose job is
    to notice that a file changed under a citation was itself serving pre-change contents. It
    is invisible in a single run — nothing edits files mid-run — and it silently made the
    instrument un-testable, which is how it survived being written.
    """
    try:
        st = path.stat()
    except OSError:
        return None
    key = (path, st.st_mtime_ns, st.st_size)
    if key not in _FILE_CACHE:
        try:
            _FILE_CACHE[key] = path.read_text(errors="replace").splitlines()
        except OSError:
            return None
    return _FILE_CACHE[key]


def content_verdict(path: pathlib.Path, first: int, last: int, anchor: str):
    """Where does the anchor actually sit, relative to where it was cited?"""
    lines = _lines(path)
    if lines is None:
        return "ABSENT", "unreadable"

    # A qualified name is a claim about SCOPE, not about the text of one line.
    d = DOTTED.match(anchor.strip())
    if d:
        scope = enclosing_symbols(lines, first)
        if d.group(2) in scope:
            return "CONFIRMED", f"line {first} is inside {'.'.join(sorted(scope))}"

    hits: list[int] = []
    for needle in needles(anchor):
        hits = [i for i, ln in enumerate(lines, 1) if needle in _norm(ln)]
        if hits:
            break
    if not hits:
        # Documents quote code the way a sentence needs it, not byte-for-byte. FAITHFULNESS.md
        # writes `global_frame = global_step * action_repeat` for a source that reads
        # `return self.global_step * self.cfg.action_repeat` under `def global_frame`. The
        # claim is true and the literal is absent, so identifier-level agreement AT THE CITED
        # LOCATION is reported as its own verdict rather than as either a pass or a defect.
        toks = {t for t in re.findall(r"[A-Za-z_]\w{3,}", anchor)}
        if len(toks) >= 2:
            lo, hi = max(1, first - SLACK), min(len(lines), last + SLACK)
            window = _norm(" ".join(lines[lo - 1:hi]))
            if all(t in window for t in toks):
                return "PARAPHRASE", f"all of {sorted(toks)} at {lo}-{hi}, exact text differs"
        return "ABSENT", f"{anchor!r} not in {path.name}"
    inside = [i for i in hits if first - SLACK <= i <= last + SLACK]
    if inside:
        return ("CONFIRMED", f"{len(hits)}x") if len(hits) <= RARE \
            else ("WEAK", f"{len(hits)}x in file")
    near = min(hits, key=lambda i: min(abs(i - first), abs(i - last)))
    return "DRIFT", f"cited {first}, found at {near} ({near - first:+d})"


def candidates(cite: str, idx) -> list[pathlib.Path]:
    """Every file a citation could mean -- used to let content disambiguate a bare basename."""
    if "/" in cite:
        direct = ROOT / cite
        if direct.is_file():
            return [direct]
        return [p for p in idx.get(pathlib.PurePath(cite).name, []) if str(p).endswith(cite)]
    return list(idx.get(cite, []))


def strong_defect(anchor_list, used: str, cands) -> bool:
    """Is this failure precise enough to act on without re-reading the file first?

    Hand-checking a systematic sample of the raw defect list found most of it was noise of one
    shape: the anchor was a *label* rather than a quote -- `[IK]` (a reference tag), `dmc_gb`
    (a directory), `MUJOCO_GL` (an env var) -- picked up from a neighbouring sentence and then
    reported as missing from a file it was never a quote of.

    Rather than keep adding rejection rules until the number looked good -- which is fitting the
    instrument to the answer -- the failures are stratified and only this stratum is claimed:

      * one candidate file, so no ambiguity about what was cited;
      * the anchor that decided it is the NEAREST one, not one borrowed from further off;
      * bound within 40 characters;
      * and it looks like a quoted line -- an operator plus two identifiers -- not a label.
    """
    if len(cands) != 1 or not anchor_list:
        return False
    d0, nearest = anchor_list[0]
    if used != nearest or d0 > 40:
        return False
    idents = re.findall(r"[A-Za-z_]\w*", used)
    return len(idents) >= 2 and bool(re.search(r"[=(\[]|\w\.\w", used))


def run_content(idx, show: int) -> tuple[collections.Counter, list[str]]:
    counts: collections.Counter[str] = collections.Counter()
    problems: list[str] = []
    for src in scan_targets():
        try:
            raw = src.read_text(errors="replace")
        except OSError:
            continue
        # Scan the whole document, not line by line: these docs wrap prose at ~100 columns, so
        # an anchor routinely sits on the line before or after its citation. Fenced blocks are
        # masked (length-preserving) because ``` fences break backtick pairing.
        text = mask_fences(raw)
        for m in CITE.finditer(text):
            cite, first = m.group(1), int(m.group(2))
            last = int(m.group(3)) if m.group(3) else first
            lineno = text.count("\n", 0, m.start()) + 1
            anchor_list = anchors_of(text, m)
            cands = candidates(cite, idx)
            if not anchor_list or not cands:
                counts["UNANCHORED"] += 1          # no quoted claim, or no file to read
                continue
            # The citation holds if ANY quoted anchor sits in ANY candidate file at that line.
            # Over candidates this is the disambiguation the path could not do; over anchors it
            # is the fix for picking the wrong quote out of a sentence. Both make the test more
            # permissive, so the anchor count is reported with every defect: a verdict reached
            # against one anchor is a stronger statement than one reached against six.
            (verdict, detail), where, anchor = min(
                ((content_verdict(p, first, last, a), p, a)
                 for p in cands for _, a in anchor_list),
                key=lambda t: RANK[t[0][0]])
            # Confirming is permissive on purpose (any anchor, any candidate) because a false
            # alarm costs more than a miss -- a checker that cries wolf stops being read. But
            # that same permissiveness makes a FAILURE weak evidence: the anchor that failed may
            # simply belong to a neighbouring sentence. So a defect is only reported when a
            # CLOSELY-bound anchor failed. The rest are honestly "not checkable", not "wrong".
            if verdict in ("DRIFT", "ABSENT") and anchor_list[0][0] > TIGHT:
                counts["UNANCHORED"] += 1
                continue
            counts[verdict] += 1
            if verdict in ("DRIFT", "ABSENT") and strong_defect(anchor_list, anchor, cands):
                counts["STRONG"] += 1
            if verdict in ("DRIFT", "ABSENT"):
                try:
                    where = where.relative_to(ROOT)
                except ValueError:
                    pass
                mark = "*" if strong_defect(anchor_list, anchor, cands) else " "
                problems.append(f"{mark}{verdict:<9} {src.relative_to(ROOT)}:{lineno}  "
                                f"{cite}:{first}  anchor `{anchor[:44]}`  "
                                f"[{len(cands)} cand, {len(anchor_list)} anchor(s), "
                                f"best {where}: {detail}]")
    return counts, problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--content", action="store_true",
                    help="check that cited lines CONTAIN the code quoted beside them")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any citation is BROKEN")
    ap.add_argument("--show", type=int, default=25, help="how many failures to print")
    args = ap.parse_args()

    idx = build_index()

    if args.content:
        counts, problems = run_content(idx, args.show)
        total = sum(counts.values())
        print(f"citations found: {total}   (content mode)")
        for k in ("CONFIRMED", "PARAPHRASE", "WEAK", "DRIFT", "ABSENT", "UNANCHORED"):
            print(f"  {k:<12}{counts[k]:>5}")
        real = counts["DRIFT"] + counts["ABSENT"]
        checked = real + counts["CONFIRMED"] + counts["WEAK"] + counts["PARAPHRASE"]
        print(f"\ncandidate defects (DRIFT + ABSENT): {real} of {checked} checkable")
        print(f"  of which STRONG (marked * below): {counts['STRONG']} -- one candidate file, "
              f"nearest\n  anchor, bound within 40 chars, and shaped like a quoted line rather "
              f"than a label.\n  A hand-checked sample of the unmarked remainder was mostly "
              f"noise, so only the\n  starred rows are claimed as defects; the rest are leads.")
        print("WEAK is not confirmation: the anchor recurs often enough in the file that a "
              "random\nline would likely match it too. UNANCHORED citations were not checked at "
              "all --\nno code span was quoted beside them, so there is no claim to test.")
        if problems:
            print()
            for p in problems[:args.show]:
                print(p)
            if len(problems) > args.show:
                print(f"... and {len(problems) - args.show} more")
        return 1 if (args.strict and real) else 0

    counts: collections.Counter[str] = collections.Counter()
    failures: list[str] = []
    line_cache: dict[pathlib.Path, int] = {}

    for src in scan_targets():
        try:
            text = src.read_text(errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in CITE.finditer(line):
                cite, first = m.group(1), int(m.group(2))
                last = int(m.group(3)) if m.group(3) else first
                status, path = resolve(cite, idx)
                if status != "RESOLVED":
                    counts[status] += 1
                    if status == "MISSING":
                        failures.append(
                            f"MISSING   {src.relative_to(ROOT)}:{lineno}  ->  {cite}")
                    continue
                if path not in line_cache:
                    try:
                        line_cache[path] = len(path.read_text(errors="replace").splitlines())
                    except OSError:
                        line_cache[path] = 0
                n = line_cache[path]
                if last > n:
                    counts["BROKEN"] += 1
                    failures.append(
                        f"BROKEN    {src.relative_to(ROOT)}:{lineno}  ->  {cite}:{last} "
                        f"but {path.relative_to(ROOT)} has {n} lines")
                else:
                    counts["RESOLVED"] += 1

    total = sum(counts.values())
    print(f"citations found: {total}")
    for k in ("RESOLVED", "AMBIGUOUS", "EXTERNAL", "HISTORICAL", "MISSING", "BROKEN",
              "UNCLASSIFIABLE"):
        print(f"  {k:<12}{counts[k]:>5}")
    real = counts["BROKEN"] + counts["MISSING"]
    print(f"\nreal defects (BROKEN + MISSING): {real}")
    if counts["UNCLASSIFIABLE"]:
        # Loud, and deliberately not counted as a defect. Without a repository this checker cannot
        # tell a citation to a deliberately-deleted file from a broken one, and saying "defect"
        # there would be an absence of evidence presented as evidence. Saying nothing would be
        # worse still: a run in a tree with no history would look cleaner than one with it.
        print(f"  UNCLASSIFIABLE: {counts['UNCLASSIFIABLE']} citation(s) name a repo-relative "
              "path that does not exist,\n  and there is NO GIT REPOSITORY here, so 'deliberately "
              "deleted' cannot be told from\n  'broken'. These are NOT counted as defects and are "
              "NOT evidence of correctness.\n  Re-run where history is available for a real "
              "verdict. (This is the state a mutant\n  tree runs in -- see mutants/run.py.)")
    print("Not defects: AMBIGUOUS (bare basename, several matches -- uncheckable, not wrong); "
          "EXTERNAL\n(outside this tree, or a reference repo's own layout); HISTORICAL (a path "
          "git knows was\ndeliberately deleted -- a correct citation to a thing correctly gone).")
    print("Checks that a line EXISTS, never that it says what the citing text claims.")
    if failures:
        print()
        for f in failures[:args.show]:
            print(f)
        if len(failures) > args.show:
            print(f"... and {len(failures) - args.show} more")
    return 1 if (args.strict and counts["BROKEN"]) else 0


if __name__ == "__main__":
    sys.exit(main())
