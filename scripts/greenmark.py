#!/usr/bin/env python3
"""Record which tree the suite was last green on, and whether that is still this tree.

    python scripts/greenmark.py --set     # after a green run: stamp the current tree
    python scripts/greenmark.py           # before committing: is the stamp still valid?
    python scripts/greenmark.py --why     # do the pending changes even need a run?

## Why this exists

Three times in one session a commit message asserted "suite green" on the strength of a run
that predated the last edit. Once it was actually red (`b49fd26a`, a generated file left stale by
a `registry.py` edit); twice it happened to be true, which is worse, because a claim that is
right by luck teaches nothing.

Resolve was not the fix — the intent was present every time. The fix is mechanical: a green
result is scoped to the tree that produced it, so stamp the tree, and compare.

The stamp is the **content hash of the working tree** — `git write-tree` against a throwaway
index, so it sees unstaged edits and untracked-but-added files alike, and touches nothing.

Getting this right took a second attempt, and the tool found the first one. Hashing
`git status --porcelain` + `HEAD` seemed equivalent and is not: *committing* changes `HEAD` while
changing no file, so the stamp went stale the instant its own commit landed. Content identity is
what "does this green result cover this tree" actually means; commit identity is a proxy that
breaks exactly when you use it.

**It caught itself first.** The stamp was set immediately after writing this file, against a
tree the suite had not been run on — the precise failure it exists to prevent, committed while
building it. That is not an argument against the tool; it is the argument for it. The correct
order is always: run, *then* stamp.

**What this cannot do:** it does not run the suite, know whether the run was complete, or notice
that the stamp was set after a run that failed. It only answers "has the tree changed since the
stamp". A stamp set carelessly is worse than none — the same limit `scripts/state.py` states
about itself.
"""
from __future__ import annotations
import hashlib, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARK = ROOT / ".greenmark"


def tree_id() -> str:
    """Content hash of the working tree, stable across a commit that changes no file."""
    import os, tempfile
    # A NON-EXISTENT path: git needs to create the index itself. An empty file is not a valid
    # index and `write-tree` silently produces nothing, which this returned as "unknown" -- a
    # sentinel that compares equal to itself and so reported STABLE while measuring nothing.
    d = tempfile.mkdtemp()
    try:
        env = {**os.environ, "GIT_INDEX_FILE": os.path.join(d, "idx")}
        subprocess.run("git add -A", shell=True, cwd=ROOT, env=env, capture_output=True)
        tree = subprocess.run("git write-tree", shell=True, cwd=ROOT, env=env,
                              capture_output=True, text=True).stdout.strip()
    finally:
        import shutil; shutil.rmtree(d, ignore_errors=True)
    if not tree:
        raise RuntimeError("git write-tree produced no tree -- greenmark cannot identify "
                           "this tree and must not pretend to")
    return tree[:16]


# RL-ViGen-upstream and setup/ are patched by this project (P1-P5) and the suite exercises them,
# so a change there is emphatically code. Omitting them made --why report "docs-only" for a
# patch to the env every baseline runs through -- found 2026-08-17 while patching P5.
CODE_PREFIXES = ("rlgen/", "tests/", "tools/", "scripts/", "configs/", "pytest.ini",
                 "RL-ViGen-upstream/", "setup/", "runnable/_shim/", "runnable/_launch/")


def pending_changes():
    """Files differing from the last commit, split into code and not-code.

    A docs-only edit cannot change what the suite would report, so re-running it is pure
    latency — a 2-minute suite was being run for `.md` edits repeatedly before this existed.
    Deciding that mechanically beats deciding it by feel, because "it's only docs" is exactly
    the judgement that is right ninety times and wrong the once that matters.
    """
    out = subprocess.run("git status --porcelain", shell=True, cwd=ROOT,
                         capture_output=True, text=True).stdout.splitlines()
    files = [l[3:].strip() for l in out if l.strip()]
    code = [f for f in files if f.startswith(CODE_PREFIXES)]
    return files, code


def main() -> int:
    if "--why" in sys.argv:
        files, code = pending_changes()
        if not files:
            # `--why` inspects the WORKING TREE; the staleness check compares the committed tree
            # hash. Both can be true at once -- commit some docs and you get "STALE" from one and
            # "no pending changes" from the other, which reads as a contradiction and sent me
            # looking for a bug that was not there. Say which question is being answered.
            stale = MARK.exists() and MARK.read_text().strip() != tree_id()
            if stale:
                # The stamp IS a git tree hash, so the committed delta is available here rather
                # than as an instruction for the reader to run themselves. This branch used to
                # end "use `git diff <stamped-tree>..HEAD`, or just re-run the suite" -- correct,
                # and it made the common case (work committed since the last green run) the one
                # case the tool refused to answer.
                stamped = MARK.read_text().strip()
                r = subprocess.run(f"git diff --name-only {stamped} HEAD", shell=True, cwd=ROOT,
                                   capture_output=True, text=True)
                changed = [f for f in r.stdout.splitlines() if f.strip()]
                if r.returncode != 0 or not changed:
                    print("no UNCOMMITTED changes — but the greenmark is STALE, and the stamped "
                          f"tree {stamped} could not be diffed against HEAD "
                          f"({r.stderr.strip()[:60] or 'no output'}). Re-run the suite.")
                else:
                    ccode = [f for f in changed if f.startswith(CODE_PREFIXES)]
                    print(f"no UNCOMMITTED changes — but the greenmark is STALE: "
                          f"{len(changed)} file(s) changed by COMMIT since the last green run.")
                    if ccode:
                        print(f"CODE CHANGED ({len(ccode)} of {len(changed)}) — run the suite:\n  "
                              + "\n  ".join(ccode[:8]))
                    else:
                        print(f"DOCS-ONLY ({len(changed)} file(s)) — the suite cannot be "
                              "affected; no run needed.")
            else:
                print("no pending changes")
        elif not code:
            print(f"DOCS-ONLY ({len(files)} file(s)) — the suite cannot be affected; "
                  f"no run needed:\n  " + "\n  ".join(files[:8]))
        else:
            print(f"CODE CHANGED ({len(code)} of {len(files)}) — run the suite:\n  "
                  + "\n  ".join(code[:8]))
        return 0
    cur = tree_id()
    if "--set" in sys.argv:
        MARK.write_text(cur + "\n")
        print(f"greenmark set: {cur}")
        return 0
    if not MARK.exists():
        print("NO GREENMARK — the suite has not been stamped against any tree.")
        return 1
    old = MARK.read_text().strip()
    if old == cur:
        print(f"greenmark VALID ({cur}) — the tree is unchanged since the last green run.")
        return 0
    print(f"greenmark STALE — stamped {old}, tree is now {cur}.\n"
          "The tree changed after the last green run; that result does not cover it.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
