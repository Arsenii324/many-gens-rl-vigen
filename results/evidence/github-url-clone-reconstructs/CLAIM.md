# The published GitHub URL actually clones and reconstructs — not just the committed tree

**2026-09-18.** The question asked was whether the operator package is ready for someone to
literally take from GitHub. [`linux-reconstruction-from-a-fresh-tree`](../linux-reconstruction-from-a-fresh-tree/CLAIM.md)
already proved the *committed tree* reconstructs on Linux — but it shipped that tree as a
`git archive HEAD` tarball, which never exercises `git clone` itself: reachability from an
arbitrary network, auth, `.gitattributes`, line endings, none of it. This bundle closes that
specific gap.

## Status

**Confirmed 2026-09-18.** `git clone https://github.com/Arsenii324/many-gens-rl-vigen.git` on the
production host, followed by `setup/bootstrap_sources.py` and `setup/verify_sources.py`, both exit
0 in the same container, from a tree that came from nowhere but the public URL.

## Chain

1. **The repository is actually public and reachable.** Confirmed independently via the GitHub API
   (`private: false`, `visibility: public`) before this run, and the clone itself took 4 seconds
   with no authentication (`raw/container-run.txt` line 6).
2. **The clone lands on the commit this session actually produced**, not a stale default branch:
   `HEAD: c507b5e ... on branch main` (line 9), i.e. fact:clone_head — the same commit this
   session pushed (`git push mygithub main`, fast-forward, `5f5b38c..c507b5e`).
3. **`runnable/` exists but is empty of upstream trees before bootstrapping** — fact:tracked_files
   tracked files, `runnable present pre-bootstrap? runnable` (line 10) confirms the directory node
   is tracked (for `_shim`/`_launch`/`_patches`) while the seven upstream clones inside it are
   correctly gitignored, exactly as `.gitignore` states.
4. **Reconstruction and verification both exit 0** from that clone: fact:bootstrap_rc (line 13),
   fact:verify_rc (line 24), producing `408M runnable` and `912M RL-ViGen-upstream` (lines 19-20) —
   sizes consistent with the earlier `git archive`-based run.
5. **Nothing was left behind.** `docker rc=0` (line 25); the host's own scratch directory
   (`~/github-clone-test`, ours by exact name) was removed afterward through a container, since the
   container wrote it as root; disk returned to its prior level (124→125 GiB free).

## What this does not show

- It does not repeat the payload build/verify/evaluator-binding step — that is already covered,
  from an equivalent tree, in `linux-reconstruction-from-a-fresh-tree`'s second excerpt.
- It does not test cloning from a machine other than this production host (a different network
  path, a different git client version). The host's outbound network to `github.com` is the one
  exercised here.
- It says nothing about whether the repository *should* be public with no `LICENSE` file — that is
  a policy question for the owner, not a technical one this bundle can answer. Both facts (public,
  unlicensed, confirmed via the GitHub API on 2026-09-18) are stated plainly so the decision isn't
  made by omission.
- It does not test `production_gates.py` against the bare clone before bootstrapping — that was
  tried locally and correctly fails loudly and specifically ("idaac clone absent", "source tree is
  absent: .../runnable/alda") rather than passing vacuously or crashing unintelligibly. That is the
  gate behaving as designed for a pre-bootstrap tree, not a defect, and is not re-asserted here as
  evidence because it was observed on the laptop, not captured on the host.

## Falsifier

A different published URL, a different default branch, an auth wall, a `bootstrap_sources.py` or
`verify_sources.py` exit code other than 0 from this exact recipe, or the clone landing on a commit
this session did not produce, would each contradict this claim. `RERUN=1 bash capture.sh`
reproduces the whole thing.
