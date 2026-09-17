# The pinned sources reconstruct from a fresh tree on Linux, and the result verifies

`setup/bootstrap_sources.py` is the first step of the operator's cold start
(`docs/RUN-THIS-PROJECT.md` §1): it clones each upstream at its pinned commit, applies this
project's patches, and materialises `runnable/` and `RL-ViGen-upstream/`. Until 2026-09-17 nobody
had ever run it that way in this campaign. The maintainer's laptop cannot: RL-ViGen holds two files
whose names differ only in case, so the script refuses on a case-insensitive filesystem, and
`setup/verify_sources.py` names that as a pending proof rather than passing silently.

Everything the campaign shipped was therefore built from a tree that had been reconstructed
**once, long ago**, and re-verified against its own hashes — which proves the tree has not drifted,
and says nothing about whether a new operator could produce it.

## Status

**Resolved on 2026-09-17.** Both steps ran to completion on Linux and both verified.

| step | result |
|---|---|
| `setup/bootstrap_sources.py` | rc fact:bootstrap_rc, in fact:wall_clock of wall clock |
| `setup/verify_sources.py` | rc fact:verify_rc |

Both printed `source reconstruction verified`. `runnable/` came out at fact:runnable_size.

## Chain

1. **A fresh tree, not ours.** What was shipped is `git archive HEAD` — the committed tree, with no
   `runnable/` upstreams and no `ext/`. That is what a clone gives an operator.
2. **The reconstruction ran to completion on a case-sensitive filesystem.**
   `raw/container-run.txt` shows `git version 2.47.3`, then `bootstrap rc=0` after
   fact:wall_clock, then the sizes of the trees it produced.
3. **The result verifies against the pins.** The same excerpt shows `verify_sources.py` printing
   `source reconstruction verified` and `verify rc=0`, in a tree built minutes earlier from
   upstream clones rather than from the maintainer's working copy.
4. **The container exited cleanly** (`docker rc=0`), and the host had 173 GiB free afterwards.

## What this does not show

- Nothing about the **payload** built from such a tree. Payload building and the evaluator binding
  were verified separately, on the laptop, against the long-standing reconstructed tree.
- Nothing about **Places365** (OPERATOR-GUIDE §11.4 O1): `bootstrap_sources.py` does not fetch it.
- Nothing about **this host's own `~/rlvigen-work/repo`**, which is a different, older checkout
  (OPERATOR-GUIDE §6d).
- It is **one run at one moment**: it shows the pinned commits were fetchable on 2026-09-17, not
  that they will stay so. An upstream that disappears breaks this step and nothing else here would
  notice until an operator tried it.

## Falsifier

Re-run `RERUN=1 bash capture.sh`. A non-zero `bootstrap rc`, a `verify rc` other than 0, or a
missing `source reconstruction verified` line falsifies the claim. A refusal naming a
case-insensitive filesystem means it was run somewhere it cannot be run.

## How it was run, and why that way

The production host is the only Linux available here, and its rules allow `docker run` but not
arbitrary Python on the host shell. So:

1. The repository's **committed** tree (`git archive HEAD`, 37 MB — no `runnable/` upstreams, no
   `ext/`, which is exactly what a fresh clone holds) was copied to `~/bootstrap-test/tree.tgz`.
2. One container did the rest, with its own network for the clones, 4 GiB of RAM and no GPU:

       docker run --rm --memory 4g -v ~/bootstrap-test:/work -w /work python:3.11-slim bash -c '
         apt-get install -y git; tar xzf /work/tree.tgz -C /work/repo; cd /work/repo
         python3 setup/bootstrap_sources.py; python3 setup/verify_sources.py'

3. The scratch directory was removed afterwards by its exact name.

`raw/container-run.txt` is that container's own output.

## What this does and does not establish

- **Does:** the pinned commits are still fetchable, the patches still apply, and the reconstruction
  a new operator would perform produces a tree that passes `verify_sources.py`. The cold start's
  first step is no longer untested.
- **Does not:** say anything about the *payload* built from such a tree — that was verified
  separately, on the laptop, against the already-reconstructed tree. Nor about Places365
  (OPERATOR-GUIDE §11.4 O1), which this step does not touch.
- **Cost, for planning:** 9 min 40 s and about 1.7 GB of disk, on this host's network.
