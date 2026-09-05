#!/usr/bin/env python3
"""Every line this project changed in an original repo, counted and shown.

    python scripts/deviations.py            # per-baseline summary
    python scripts/deviations.py --full     # the complete diffs

## What this measures

`runnable/<name>/` is a full clone of an original repository with a `PRISTINE:` commit as its
first commit. Everything after that commit is ours. `git diff` against it is therefore the
*complete and exhaustive* statement of what we changed — not a summary, not a description, and
not something anyone has to remember to update.

The target is **fewer changed lines**, and a changed line in a load-bearing place counts for more
than its number suggests. This script reports the count; judging weight is a person's job.

## What is NOT counted here, and why

`runnable/_shim/sitecustomize.py` changes **zero** repo lines: it makes CUDA-native code run on
Apple MPS from outside, via `PYTHONPATH`. That is deliberate — patching `.cuda()` at its 22 call
sites across 7 files in `dmc_gb` alone would be 22 deviations bought purely for local
convenience, while the authoritative runs go to a T4 where the originals run unmodified.

**So a green local smoke run does not prove the CUDA path.** The shim downcasts float64 to
float32 (MPS has no float64) and reports `is_cuda` for MPS tensors; both are real differences
from the T4 path, and both are announced rather than silent. Read the shim's own docstring.

Launch-environment facts (`PYTHONPATH`, `MUJOCO_GL`, an env var a patch reads) are also not
deviations — they change no source line — but they are not free either: they must be recorded in
the launcher, or the run is not reproducible.
"""
from __future__ import annotations

import pathlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNABLE = ROOT / "runnable"

#: Where each clone was taken FROM, so the PRISTINE commit's claim can be re-derived instead of
#: believed. A clone whose baseline is not listed here simply skips the check -- silently
#: assuming a match would be the failure this table exists to prevent.
#: Untracked paths that are NOT deviations. Everything else untracked is a file we ADDED and is
#: counted and exported as such.
#:
#: This list exists because `git diff` does not see untracked files, so for a while this script
#: silently omitted every ADDED file -- including `alda/specs/train_alda_robosuite_door.yaml`,
#: which docs/RUNNABLE-ORIGINALS.md describes as a deviation and which was therefore missing from
#: both the count and the exported patch. A patch that cannot rebuild the clone is not a record
#: of the clone.
#:
#: Each entry is a run artifact or launch environment, and each says which. The ignored files are
#: PRINTED on every run rather than silently dropped: an ignore list nobody sees is how the next
#: omission happens.
IGNORED_UNTRACKED = {
    "door.xml":       "run artifact -- a robosuite task model dumped at cwd during a run; "
                      "49 KB of MuJoCo XML named after the task, and ALDA's own repo ships one "
                      "for the same reason",
    "__pycache__":    "python bytecode",
    "logs":           "run output (idaac writes its logger here)",
    "models":         "run output (idaac's --save_dir)",
    "results":        "run output (alda's --results_dir)",
    "exp_local":      "run output (RL-ViGen's hydra run dir)",
    "data":           "launch environment -- the overlay-dataset symlink dmc_gb.sh creates",
    ".egg-info":      "pip install -e artifact",
}


def is_ignored(rel: str) -> str | None:
    """Returns the REASON a path is ignored, or None if it counts as ours."""
    parts = rel.rstrip("/").split("/")
    for key, why in IGNORED_UNTRACKED.items():
        if key in parts or rel.endswith(key) or any(seg.endswith(key) for seg in parts):
            return why
    return None


SOURCE_OF = {
    "alda": "ext/ALDA_Official",
    "dmc_gb": "ext/dmcontrol-generalization-benchmark",
    "ppg": "ext/phasic-policy-gradient",
    "idaac": "ext/idaac",
    "ibac_sni": "ext/IBAC-SNI",
    "ctrl": "ext/ctrl_public",
}


def git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True).stdout


def main() -> int:
    if not RUNNABLE.exists():
        print("no runnable/ directory yet")
        return 1
    full = "--full" in sys.argv
    export = "--export" in sys.argv
    clones = sorted(p for p in RUNNABLE.iterdir()
                    if p.is_dir() and (p / ".git").exists())
    if not clones:
        print("no cloned originals under runnable/ yet")
        return 1

    total_ins = total_del = total_files = total_code = 0
    incomplete: list[tuple[str, int]] = []
    bad_base = []
    unverifiable = []
    print(f'{"clone":<16}{"files":>6}{"+":>7}{"-":>7}{"code+":>7}   baseline commit')
    print("-" * 78)
    ignored_seen = {}
    for c in clones:
        base = git(["log", "--format=%H", "--reverse"], c).split("\n")[0]
        # `git diff` is blind to untracked files, so ADDED files -- which are deviations, and
        # sometimes the most load-bearing ones -- would not appear at all. `add -N` (intent to
        # add) makes them visible to diff without staging content or touching the PRISTINE
        # commit, which is what keeps this script read-only in every way that matters.
        for line in git(["status", "--porcelain"], c).splitlines():
            if not line.startswith("??"):
                continue
            rel = line[3:].strip()
            why = is_ignored(rel)
            if why:
                ignored_seen.setdefault(rel, why)
                continue
            git(["add", "-N", "--", rel], c)
        # [Claude 2026-09-04] A clone whose working tree is slimmed reports its ABSENCES as
        # deletions, which is authorship it never had. Rather than refusing to count such a clone
        # at all -- which left four of six uncountable and the deviation record unregenerable --
        # exclude deleted paths from the diff and SAY SO. Verified safe by inspection: every
        # absent path is a non-source artifact (dmc_gb's `src/env/data/*.pt` and video assets,
        # ppg's upstream `results/*/progress-*.csv`, ibac_sni's one stray `.gitignore`, since
        # restored), so no authored change hides behind the filter.
        #
        # The one thing this cannot see is a deletion WE made. That is acceptable because this
        # project's clone edits are additive by policy -- but it is a real limit, so the label
        # below says PARTIAL rather than pretending the number is the same kind of fact.
        missing = sum(1 for line in git(["status", "--porcelain"], c).splitlines()
                      if line.startswith(" D"))
        diff_args = ["diff"] + (["--diff-filter=d"] if missing else [])
        stat = git(diff_args + ["--numstat", base], c).strip()
        # The PRISTINE subject names the ext/ commit it was taken from. That name is a CLAIM,
        # and it was wrong once already (ibac_sni was labelled 1678e4a -- the SHA of a
        # separately vendored base -- while ext/IBAC-SNI is at 6b3a58b). So re-derive it here
        # rather than trusting the string: whatever this baseline says it came from, ask that
        # repository what its HEAD actually is.
        claimed = re.search(r"\b[0-9a-f]{7,40}\b",
                            git(["log", "--format=%s", "-1", base], c))
        src = SOURCE_OF.get(c.name)
        if claimed and src and (ROOT / src).exists():
            # [Corrected 2026-09-05.] `git -C <dir> log` WALKS UP when <dir> is not itself a
            # repository, so it cheerfully returned the ENCLOSING repo's HEAD and this check
            # accused all six baselines of mislabelled provenance against one unrelated commit
            # (12f6322, ccm-intro's own HEAD). ext/ has no .git and neither do the vendored copies
            # inside it. Ask whether the directory is its own repository root before believing the
            # answer -- and when it is not, say the claim is UNCHECKABLE here rather than wrong.
            toplevel = git(["rev-parse", "--show-toplevel"], ROOT / src).strip()
            own_repo = toplevel and pathlib.Path(toplevel).resolve() == (ROOT / src).resolve()
            if not own_repo:
                unverifiable.append(f"{c.name}: {src} carries no git identity of its own, so its "
                                    f"claimed base {claimed.group(0)} cannot be checked in this tree")
            else:
                actual = git(["log", "-1", "--format=%h"], ROOT / src).strip()
                if actual and not actual.startswith(claimed.group(0)[:len(actual)]):
                    bad_base.append(f"{c.name}: claims {claimed.group(0)}, {src} is at {actual}")
        ins = dels = files = 0
        for line in stat.splitlines():
            parts = line.split("\t")
            if len(parts) == 3 and parts[0].isdigit():
                ins += int(parts[0]); dels += int(parts[1]); files += 1
        # Insertions that are neither blank nor comment-only. Reported ALONGSIDE the raw count,
        # never instead of it: this project writes long justifying comments, so `+` overstates
        # how much behaviour moved, while `code+` understates how much a reader has to read.
        # Deletions are not split -- a deleted comment is as gone as a deleted statement.
        code_ins = 0
        for line in git(diff_args + [base], c).splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                body = line[1:].strip()
                if body and not body.startswith("#"):
                    code_ins += 1
        subj = git(["log", "--format=%s", "-1", base], c).strip()[:34]
        # A clone whose working tree is INCOMPLETE cannot be counted. The isolated candidate
        # carries slimmed copies -- ppg is 462 tracked files short, alda 113, dmc_gb 112 -- and
        # `git diff` against PRISTINE reports those absences as changes, so ppg reads 456 files and
        # 684,101 lines where the whole tree reads 8 and 107. That is deletions, not authorship,
        # and a total containing it is worse than no total at all.
        if missing:
            incomplete.append((c.name, missing))
            subj = f"PARTIAL ({missing} absent, deletions excluded) {subj}"[:60]
        print(f"{c.name:<16}{files:>6}{ins:>7}{dels:>7}{code_ins:>7}   {subj}")
        total_ins += ins; total_del += dels; total_files += files; total_code += code_ins
        if full and stat:
            print(git(diff_args + [base], c))
        if export:
            # The clones are ~200MB each and carry their own .git; they are NOT tracked in the
            # main repo. The PATCH is, so the change set is version-controlled and the clone is
            # reproducible from ext/ + this file.
            out = ROOT / "runnable" / "_patches"
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{c.name}.patch").write_text(git(diff_args + [base], c))
    print("-" * 78)
    if incomplete:
        names = ", ".join(f"{n} (-{k})" for n, k in incomplete)
        print("NO TOTAL: these clones are not whole in this tree, so nothing here is a count of")
        print(f"          what we authored -- {names}")
        print("          Run this in a tree where every clone is complete; the numbers there are")
        print("          the authoritative ones, and the docs quote those.")
    else:
        print(f'{"TOTAL":<16}{total_files:>6}{total_ins:>7}{total_del:>7}{total_code:>7}')
    print("\n`+` counts every inserted line; `code+` counts only those that are neither blank")
    print("nor comment-only. Both are shown because each flatters a different story.")
    if unverifiable:
        print("\nBASELINE UNCHECKABLE HERE -- not a mismatch, and NOT a pass either:")
        for u in unverifiable:
            print(f"  ?? {u}")
        print("  Check these in a tree where ext/ holds real clones with their own .git.")
        print("  NOTE: a zero exit does NOT certify these -- it means no MISMATCH was proven, and")
        print("  a claim that could not be checked is not a claim that was checked and passed.")
    if bad_base:
        print("\nBASELINE MISLABELLED -- the PRISTINE commit does not name its actual source:")
        for b in bad_base:
            print("  !! " + b)
    if ignored_seen:
        print("\nUntracked but NOT counted (run artifacts and launch environment):")
        for rel, why in sorted(ignored_seen.items()):
            print(f"  -- {rel:<44} {why}")
    print("\nEvery line above is ours. runnable/_shim/ changes zero repo lines and is not counted;")
    print("see this file's docstring for why, and for what a local smoke run does not prove.")
    return 1 if bad_base else 0


if __name__ == "__main__":
    sys.exit(main())
