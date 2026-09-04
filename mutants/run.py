#!/usr/bin/env python3
"""Run the mutation catalogue: mutate production code, run the real suite, report survivors.

    python mutants/run.py                  # every mutant
    python mutants/run.py --id M7-evaluate-on-train-scene
    python mutants/run.py --list

MECHANICS. Each mutant is applied to a COPY of the tree, never to the working tree -- a mutation
runner that edits your source and restores it afterwards loses a race with any interruption. The
1.8 GB vendored upstream is symlinked rather than copied, so a run costs a few megabytes.

The oracle is `pytest tests` against the copy, unchanged -- or whatever a mutant's own
`oracle` field names, when a narrower claim is the more useful one. A mutant is KILLED if
that fails.

SURVIVORS ARE THE OUTPUT. A 100% kill rate on a small catalogue means the catalogue is too easy,
not that the suite is perfect. Exit is non-zero when anything survives, because every entry in
`catalogue.py` is an explicit claim that the suite catches it -- a survivor is a claim that turned
out to be false, and it should break the build until it is either fixed or downgraded in writing.

A SANITY MUTANT runs first: an unmutated copy must PASS. Without that check, a catalogue could
report 100% kills purely because the copied tree does not run at all -- which is precisely the
class of vacuous verification this file exists to replace.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mutants.catalogue import CATALOGUE, Mutant, by_id  # noqa: E402

#: Never copied into a mutant tree. `RL-ViGen-upstream` is symlinked back in afterwards.
#:
#: DERIVED, NOT ONLY LISTED. A hand-maintained skip list is the same failure class as the sweep's
#: old hand-maintained TARGETS: it silently stops being right when the tree grows. `ext/` was added
#: to this repo holding thirteen cloned reference repositories, and because nothing excluded it
#: every mutant copy became **1.6 GB** -- 44 of those per full run, for a tree whose source is a
#: couple of megabytes. Nothing failed; it just quietly cost disk and wall-clock.
#:
#: So the list below is the floor, and anything git ignores at the top level is skipped too --
#: gitignored means "not source", which is exactly the question being asked here.
SKIP = {".git", "RL-ViGen-upstream", "logs", "artifacts", ".venv", "__pycache__",
        ".pytest_cache", "ext"}


def _gitignored_toplevel() -> set:
    """Top-level entries git ignores. Empty on failure -- a broken probe must not skip nothing
    silently NOR skip everything; the explicit SKIP set above still applies either way."""
    import subprocess
    try:
        names = [n for n in os.listdir(ROOT) if not n.startswith(".")]
        if not names:
            return set()
        r = subprocess.run(["git", "-C", ROOT, "check-ignore", *names],
                           capture_output=True, text=True, timeout=20)
        return {os.path.basename(x) for x in r.stdout.split() if x}
    except Exception:
        return set()


SKIP |= _gitignored_toplevel()


#: This repo lives at `<workspace>/projects/many-gens-rl-vigen`, and it cites UPWARD out of
#: itself: `CLAUDE.md`'s nulls each name `../../docs/porting-directive.md`, and
#: `tests/test_claude_md_nulls.py` checks the quoted text against that file. A copy dropped
#: straight into a temp directory has no such ancestor, so the null test failed on the *unmutated*
#: copy and the sanity gate went FATAL -- the same unfaithful-copy failure this file already
#: records for `ext/`, one level further up and therefore invisible to a fix aimed inside the tree.
#:
#: So a mutant copy reproduces the two ancestor levels and symlinks the workspace's own `docs/`
#: back in. Nothing is copied: the link is read-only in practice because the suite only reads
#: those files.
WORKSPACE = os.path.dirname(os.path.dirname(ROOT))
PROJECTS_DIRNAME = os.path.basename(os.path.dirname(ROOT))
REPO_DIRNAME = os.path.basename(ROOT)


def make_workspace(prefix: str) -> tuple[str, str]:
    """-> (root to delete afterwards, path the tree should be copied to).

    Builds `<root>/<projects>/<repo>` with the workspace's `docs/` symlinked in beside
    `<projects>`, so a citation like `../../docs/porting-directive.md` resolves from inside the
    copy exactly as it does in the real tree.

    Two paths, not one, because they are no longer the same directory: the suite runs at the tree
    and the cleanup must remove the root above it. Returning only the tree leaked a temp directory
    per mutant, and returning only the root left callers computing the tree by hand.
    """
    tmp = tempfile.mkdtemp(prefix=prefix)
    projects = os.path.join(tmp, PROJECTS_DIRNAME)
    os.makedirs(projects, exist_ok=True)

    # Every workspace entry EXCEPT the projects directory is symlinked in beside it, and every
    # SIBLING project is symlinked inside it. Enumerated rather than listed by hand, for the same
    # reason the SKIP set above is: a hand-maintained list stops being right the moment the
    # workspace grows, and the failure is silent -- the copy just quietly stops resembling the
    # tree the suite was written against.
    #
    # Both levels are needed, and each was found by a separate sanity failure:
    #   `CLAUDE.md`'s nulls cite `../../docs/porting-directive.md`   -> the workspace level
    #   `docs/PROJECT-INDEX.md` cites `../../gen-rebuttal/vigen-idaac` -> the sibling level
    # Nothing is copied; these are links to the real thing, and the suite only reads them.
    for name in os.listdir(WORKSPACE):
        if name == PROJECTS_DIRNAME or name.startswith("."):
            continue
        dest = os.path.join(tmp, name)
        if not os.path.exists(dest):
            os.symlink(os.path.join(WORKSPACE, name), dest)

    siblings = os.path.dirname(ROOT)
    for name in os.listdir(siblings):
        if name == REPO_DIRNAME or name.startswith("."):
            continue
        dest = os.path.join(projects, name)
        if not os.path.exists(dest):
            os.symlink(os.path.join(siblings, name), dest)

    return tmp, os.path.join(projects, REPO_DIRNAME)


def make_copy(dst: str) -> None:
    # symlinks=True, and it is not cosmetic. With symlinks=False `copytree` FOLLOWS every link,
    # so one dangling symlink anywhere in the tree aborts the whole run -- which is what happened:
    # `runnable/alda/dmcontrol_generalization_benchmark/datasets` points at a target that is not
    # present, and the harness could not make a single copy. The clones arrived after this file
    # was written, so the failure was invisible until something tried to run it. Preserving links
    # as links also avoids copying whatever they point at, which is the same instinct as the
    # SKIP set above.
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copytree(ROOT, dst, symlinks=True,
                    ignore=shutil.ignore_patterns(*SKIP))
    # Skipped-for-size directories are SYMLINKED BACK, not left absent. Skipping `ext/` kept a
    # copy small and made the copy unfaithful: `tests/test_state_script.py` reads the vendored
    # reference repos to say where a figure came from, so it failed on the unmutated copy while
    # passing in the working tree. The sanity mutant caught it, which is exactly what it is for --
    # without it, every "kill" measured afterwards would have been against a broken tree.
    for name in ("RL-ViGen-upstream", "ext"):
        src_path = os.path.join(ROOT, name)
        if os.path.isdir(src_path):
            os.symlink(src_path, os.path.join(dst, name))


def apply(dst: str, m: Mutant) -> None:
    path = os.path.join(dst, m.path)
    src = open(path, encoding="utf-8").read()
    if m.find not in src:
        raise SystemExit(
            f"{m.id}: anchor not found in {m.path}. The catalogue has drifted from the code, "
            f"which means this mutant has been silently not-run. Fix the anchor.")
    if src.count(m.find) != 1:
        raise SystemExit(f"{m.id}: anchor appears {src.count(m.find)} times in {m.path}; "
                         f"a mutation that lands in an unintended place proves nothing.")
    open(path, "w", encoding="utf-8").write(src.replace(m.find, m.replace, 1))


def run_suite(cwd: str, timeout: int = 1800, oracle: str = "tests") -> tuple[bool, str]:
    """-> (passed, tail of output)."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("MUJOCO_GL", "glfw" if sys.platform == "darwin" else "egl")
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", oracle, "-x", "-q",
                            "--no-header", "-p", "no:cacheprovider"],
                           cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    out = (r.stdout + r.stderr).strip().splitlines()
    return r.returncode == 0, " | ".join(out[-2:]) if out else ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", action="append", help="run only these mutants")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--keep", action="store_true", help="keep the mutated copies for inspection")
    args = ap.parse_args()

    if args.list:
        for m in CATALOGUE:
            print(f"  {'!' if m.critical else ' '} {m.id:<34} {m.path}")
            print(f"      {m.why}")
        print(f"\n{len(CATALOGUE)} mutants, "
              f"{sum(m.critical for m in CATALOGUE)} marked critical "
              f"(would produce a wrong table rather than a crash)")
        return 0

    chosen = [by_id(i) for i in args.id] if args.id else CATALOGUE

    # ---- sanity: an UNMUTATED copy must pass, or every "kill" below is meaningless ----------
    print("=== sanity: unmutated copy ===", flush=True)
    root, tmp = make_workspace("mut-sanity-")
    make_copy(tmp)
    t0 = time.time()
    ok, tail = run_suite(tmp)
    print(f"  {'PASS' if ok else 'FAIL'}  ({time.time() - t0:.0f}s)  {tail}")
    if not args.keep:
        shutil.rmtree(root, ignore_errors=True)
    if not ok:
        print("\nFATAL: the unmutated copy does not pass, so a mutant 'kill' would prove nothing "
              "about the mutation. Fix the suite before measuring it.", file=sys.stderr)
        return 2

    # ---- the catalogue ---------------------------------------------------------------------
    print(f"\n=== {len(chosen)} mutant(s) ===", flush=True)
    killed, survived = [], []
    for m in chosen:
        root, tmp = make_workspace(f"mut-{m.id}-")
        make_copy(tmp)
        apply(tmp, m)
        t0 = time.time()
        ok, tail = run_suite(tmp, oracle=m.oracle)
        dt = time.time() - t0
        # flush=True is load-bearing, not cosmetic. Redirected to a file, Python block-buffers
        # stdout, so a 40-minute catalogue printed NOTHING until it finished -- indistinguishable
        # from a hang, and no way to see which mutant is slow. mutants/sweep.py already flushes.
        if ok:
            survived.append(m)
            print(f"  SURVIVED  {m.id:<34} ({dt:.0f}s)  <-- the suite did not notice", flush=True)
        else:
            killed.append(m)
            print(f"  killed    {m.id:<34} ({dt:.0f}s)  {tail[:70]}", flush=True)
        if not args.keep:
            shutil.rmtree(root, ignore_errors=True)

    n = len(chosen)
    print(f"\n{len(killed)}/{n} killed, {len(survived)} survived")
    if survived:
        print("\nSURVIVORS -- each is a defect this suite would ship:")
        for m in survived:
            print(f"  {m.id}  ({m.path})")
            print(f"    {m.why}")
        return 1
    print("\nEvery mutant in the catalogue was caught by `pytest tests`.")
    print("That is a statement about THIS catalogue, not about the code in general: it covers "
          f"{n} specific defects, listed in mutants/catalogue.py. Defects outside it are "
          "unmeasured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
