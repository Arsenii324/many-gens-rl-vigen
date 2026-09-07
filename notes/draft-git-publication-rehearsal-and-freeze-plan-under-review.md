# Git publication rehearsal and source-freeze plan — DRAFT, UNDER REVIEW

> **Status:** hypothetical operating plan, not an approved commit plan and not authorization to
> push. It may be rehearsed only in disposable local directories. The final-freeze and GitHub
> phases wait for the active research tree to stop changing and for explicit owner decisions.

## Goal

Prove, without modifying either live repository, that the intended source can be assembled into a
small, secret-free candidate; that the recovery and legacy histories can coexist without being
misrepresented as reconciled; and that a clean clone can reconstruct and verify the twelve-baseline
project. Only then freeze the exact production source and, separately, publish it to an explicitly
approved private remote.

## Evidence and constraints this plan implements

- `notes/push-plan-review.md`: the recovery workspace and versioned tree are independent histories;
  ignored baseline clones are intentional; live dataset symlinks must not be deleted.
- `notes/review-artifact-spec.md`: excluded material must be declared, not made indistinguishable
  from material absent from the project.
- `notes/review-11-12-gemini-triage.md`: P0 implementation and validation work precedes source
  freeze; a commit must not bless an intermediate state.
- Private by default. No GitHub repository is created or changed during rehearsal.
- The live recovery tree, live legacy tree, their indexes, branches, remotes, ignored clones,
  datasets and symlinks are read-only throughout rehearsal.
- Model A remains the candidate architecture: upstream repositories are reconstructed from pinned
  sources plus versioned patches. Nested `.git` directories are never deleted.
- Shell inventories are NUL-delimited. This is required because the current recovery tree contains
  an untracked filename with embedded newlines.
- No command in this plan uses `git add .` in a live tree, modifies a live remote, or deletes a live
  path.

## Paths and named artifacts

Read-only inputs:

```text
RECOVERY_SOURCE=/Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen
LEGACY_SOURCE=/Users/a2mogus/build-projs/ccm-intro/projects/many-gens-rl-vigen
PROJECT_PYTHON=/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python
```

Every rehearsal creates one disposable root with these children:

```text
<rehearsal>/candidate/             recovery history plus a stable working-tree capture
<rehearsal>/legacy-candidate/      legacy history plus a stable working-tree capture
<rehearsal>/mock-github.git/       local bare remote
<rehearsal>/clean-clone/           clone made only from mock-github.git
<rehearsal>/capture/               binary diffs and NUL-safe manifests
<rehearsal>/reports/               scans, inventories, tests and final rehearsal verdict
```

The durable report, if useful, may later be copied into `notes/` after review. Raw scans and
candidate repositories stay outside the live project.

## Stage A — collision-free local rehearsal

Stage A may run while Claude is active. It creates no commit object, index change, branch, remote,
or file in either source tree.

### A1. Create and identify the disposable workspace

- [ ] Create the rehearsal root with `mktemp -d /tmp/rlvigen-publish-rehearsal.XXXXXX`.
- [ ] Record its absolute path, start time, both source `HEAD` values, active branches, and
  `git status --porcelain=v1 -z` hashes in `reports/rehearsal-metadata.txt`.
- [ ] Record that this is a point-in-time rehearsal, not the final production source.
- [ ] Do not install a cleanup trap. Keep the rehearsal until its report is reviewed; removal is a
  separate, explicit action against the resolved `mktemp` path.

### A2. Capture the recovery tree without its ignored bulk

- [ ] Clone the committed recovery history into `candidate/` with `git clone --no-hardlinks`.
- [ ] Capture tracked work as `git diff --binary --full-index HEAD -- .` under `capture/`.
- [ ] Capture untracked, non-ignored names with
  `git ls-files --others --exclude-standard -z` under `capture/`.
- [ ] For every NUL-delimited untracked path, record `git hash-object -- <path>` and copy that file
  into the candidate with its relative path preserved.
- [ ] Apply the binary tracked diff inside the candidate.
- [ ] Recompute the tracked diff hash and every untracked content hash in the source.
- [ ] If either differs from the pre-copy capture, mark the attempt `RACED_WITH_WRITER`, leave the
  evidence intact, and start a new rehearsal root. Never try to merge two moments silently.
- [ ] Verify that `ext/`, `data/`, payload archives, checkpoints, `RL-ViGen-upstream/`, and the six
  ignored `runnable/*/` clones were not copied.
- [ ] Verify that `runnable/_launch/`, `_patches/`, `_shim/`, source locks, tests, scripts, configs
  and notes were copied if present and non-ignored.

The capture mechanism must be a small checked script before execution; ad-hoc line parsing is not
acceptable. Its regression fixture must contain spaces, tabs and embedded newlines in filenames.

### A3. Capture the legacy working state separately

- [ ] Clone the legacy repository into `legacy-candidate/` using a local/shared clone to avoid an
  unnecessary second 544-MiB object-store copy.
- [ ] Apply the same stable tracked-diff plus NUL-safe untracked capture procedure.
- [ ] Keep the current legacy branch identity (`nd-ln-architecture-transition` at capture time).
- [ ] Do not commit the legacy tree's current 53-path working state automatically.
- [ ] Produce `reports/legacy-working-state.tsv` with path, tracked/untracked status, content hash,
  and size. This is evidence to reconcile, not material automatically destined for GitHub.

### A4. Perform file-level reconciliation before choosing branch policy

- [ ] Compare the two captured candidates by relative path and content hash, excluding each `.git`
  directory and ignored/re-generated bulk.
- [ ] Generate `reports/two-tree-reconciliation.tsv` with columns:

```text
path  recovery_state  legacy_state  recovery_hash  legacy_hash  disposition  rationale  reviewer
```

- [ ] Classify every legacy-only or divergent authored path as one of:

```text
RECOVERY_WINS
LEGACY_WINS
KEEP_BOTH_WITH_DISTINCT_NAMES
HISTORICAL_ONLY
GENERATED_OR_RUN_OUTPUT_EXCLUDE
NEEDS_OWNER_DECISION
```

- [ ] Require a concrete rationale for every disposition.
- [ ] Do not call two disconnected branches “reconciled.” They preserve two histories. Reconciliation
  is complete only when every material working-tree difference has a disposition.
- [ ] Do not create an `--allow-unrelated-histories` merge merely to make a graph look connected.
  Such a merge would imply content reconciliation that did not occur.

### A5. Prove or reject Model A clean reconstruction

This is a hard gate the Gemini plan omitted. `setup/install.sh` fetches and patches RL-ViGen only;
`setup/apply_patches.py` does **not** reconstruct the six ignored `runnable/*/` repositories.
`scripts/refresh_clone_patches.py` only compares existing `ext/` sources and clones. Therefore the
current statement “reviewers can run apply_patches.py” is insufficient for a clean GitHub clone.

- [ ] Inventory each of the six source repository URLs, exact commits, expected destination paths,
  and patch files from the current source locks and clone histories.
- [ ] Add no bootstrap code to the live tree during rehearsal. Instead, write a candidate-only
  reconstruction script and tests inside `candidate/`.
- [ ] Require the script to clone each upstream at its exact pin into a temporary source path,
  copy/clone it to `runnable/<family>`, apply `runnable/_patches/<family>.patch`, and fail on any
  rejected or fuzzy patch.
- [ ] Require a machine-readable reconstruction manifest with upstream URL, commit, patch SHA-256,
  and resulting authored-file hashes.
- [ ] Compare the reconstructed authored files to the current live clones using
  `scripts/refresh_clone_patches.py --check` and `scripts/deviations.py` in an environment where
  both source and clone trees exist.
- [ ] If exact reconstruction cannot be demonstrated, Stage A fails. Do not publish Model A with a
  README promise that the clean clone cannot perform.

Candidate-only bootstrap work is a proposal. It reaches the live tree later through ordinary
review and tests, not by copying the rehearsal wholesale.

### A6. Inspect paths, links, secrets and personal data without rewriting evidence

- [ ] Inventory all symlinks with link target and target existence. Classify each as live external
  dependency, dead generated link, or authored link.
- [ ] Do not delete a link merely because it is dead in the rehearsal machine. Decide whether it
  belongs in `.gitignore`, the exclusion manifest, or source only after determining provenance.
- [ ] List files containing absolute local paths or host/account identifiers. Do not bulk-replace
  them: historical configs and run records may need exact paths for provenance, while executable
  defaults may need portability.
- [ ] Run a credential scanner on both the candidate worktree and all reachable Git objects. The
  required scanner must support redaction; its report must not print complete token values.
- [ ] Supplement it with filename-only searches for `.env`, `.netrc`, private keys, W&B, GitHub,
  DataSphere, cloud-provider and bearer-token indicators.
- [ ] Treat every match as `REVIEW_REQUIRED`; distinguish code that names an environment variable
  from an embedded credential.
- [ ] Scan archives only in a separate quarantined extraction directory if an archive is proposed
  for inclusion. Current Model A excludes payload/checkpoint/dataset archives.
- [ ] Run the same scan over `canonical-history`; a clean new snapshot does not remove a secret from
  old reachable commits.

Secret scanning must occur before any candidate commit. If a secret exists in history, ordinary
deletion is insufficient; publication remains blocked pending explicit history-rewrite and
credential-rotation handling.

### A7. Construct the candidate tree through a temporary index

- [ ] Create a temporary index path under `capture/`; never use the live source's index.
- [ ] Initialize it from candidate `HEAD` with `GIT_INDEX_FILE=<temp> git read-tree HEAD`.
- [ ] Stage all candidate changes into that temporary index with
  `GIT_INDEX_FILE=<temp> git add -A -- :/`.
- [ ] Generate a NUL-delimited staged path/status inventory and inspect every unexpected path.
- [ ] Write the candidate tree with `git write-tree`; record its tree ID.
- [ ] Reject individual files at or above 10 MiB unless explicitly reviewed.
- [ ] Reject any GitHub-incompatible blob at or above 100 MiB in either proposed branch history.
- [ ] Report total checkout bytes, new-object bytes, and combined reachable history size. The old
  50-MiB target is a project preference, not proof that the complete two-branch history is small.
- [ ] Compare the staged tree against `.gitignore` invariants: no datasets, vendored clones,
  checkpoints, payload archives, run directories or nested `.git` data.

Only after all scans pass may a rehearsal commit be created, and only inside `candidate/`.

### A8. Create rehearsal-only branch topology

- [ ] Create `rehearsal-main` from the temporary-index tree with `git commit-tree`, parented by the
  recovery `HEAD`. The message must include `REHEARSAL ONLY` and the capture report hash.
- [ ] Fetch the legacy committed branch into the candidate as `canonical-history` without changing
  either live repository.
- [ ] Verify with `git merge-base rehearsal-main canonical-history` that the histories are unrelated;
  document that fact rather than treating it as an error.
- [ ] Do not add the dirty legacy working state to `canonical-history`. Material paths selected by
  the reconciliation ledger belong in a reviewed successor change, not an archival branch rewrite.
- [ ] Ensure neither live repository has gained a branch, remote, reflog entry or index change.

### A9. Push atomically to a local mock remote

- [ ] Initialize `mock-github.git/` as a bare repository.
- [ ] Add it as a remote **only in `candidate/`**.
- [ ] Push `rehearsal-main:main` and `canonical-history:canonical-history` in one
  `git push --atomic` command.
- [ ] Deliberately test a rejected atomic push once using a disposable invalid ref and confirm that
  neither destination ref advances.
- [ ] Set the bare repository's symbolic `HEAD` to `refs/heads/main`.
- [ ] Record both remote ref hashes and compare them to the candidate hashes.

This is the closest safe test of the eventual GitHub operation. Two sequential pushes are not
atomic and are not an acceptable substitute.

### A10. Verify a clean clone made only from the mock remote

- [ ] Clone `mock-github.git` into `clean-clone/` without local hardlinks.
- [ ] Confirm the default checkout is `main` and `canonical-history` is discoverable.
- [ ] Confirm none of the two live source paths appears as an object alternate or required Git path.
- [ ] Run the path, symlink, secret, large-file and exclusion-manifest checks again on the clean clone.
- [ ] Execute the candidate Model-A bootstrap in a disposable cache and verify all six clone patch
  identities plus RL-ViGen P1-P21.
- [ ] Use `PROJECT_PYTHON` only for the local rehearsal checks it can support; record the exact
  interpreter and packages. The repository's clean-environment installation test is separate.
- [ ] Run focused publication/reconstruction/provenance tests first.
- [ ] Run the full test suite exactly once after the candidate stops changing. Record complete
  command, exit code, duration, pass/fail/skip counts and output artifact. A skipped source check is
  not a passing reconstruction check.
- [ ] Run `python scripts/production_gates.py` both from the clean-clone root and by absolute path
  from another working directory. The results must be identical, closing the CWD-dependent gate
  class.
- [ ] Build one small representative payload from the clean clone and verify its contract and source
  manifest without submitting a remote job.

### A11. Produce the rehearsal verdict

- [ ] Write `reports/rehearsal-verdict.md` containing:

```text
source HEADs and dirty-state capture hashes
candidate tree and commit hashes
legacy branch hash and unrelated-history statement
reconciliation ledger summary and unresolved rows
included/excluded inventory
secret/PII/path/symlink findings
blob and repository sizes
Model-A reconstruction result for all seven source families
focused and full test results
production-gate results from two working directories
atomic-push and clean-clone results
all deviations from this plan
verdict: PASS, FAIL, or INCOMPLETE
```

- [ ] `PASS` means only that publication mechanics were rehearsed. It does not mean the active
  research tree is production-ready or approved for publication.
- [ ] Preserve failed attempts and their reason. Never overwrite the chain into a final-only story.

## Stage B — final source freeze, after concurrent work ends

Stage B must not begin while Claude or another process is writing the project, while evaluator-
affecting validation is in flight, or while a live P0 from the review triage remains unresolved.

### B1. Freeze prerequisites

- [ ] Claude and Codex explicitly report their active edits complete or handed off.
- [ ] T1-T9 implementation/spec contradictions in `review-11-12-gemini-triage.md` are closed or
  deliberately owner-deferred with production disabled.
- [ ] Final evaluator members, family descriptors, statistical protocol and production host profile
  have stopped changing.
- [ ] Owner has ratified or explicitly retained the operational defaults on the decision surface.
- [ ] Current evaluator-family validations and necessary bounded design-point pilots are complete.
- [ ] No result-generating remote job still depends on uncommitted local bytes that would be lost.

### B2. Repeat, do not promote, the rehearsal

- [ ] Start a fresh Stage-A rehearsal from the stable tree. Do not reuse the prior candidate.
- [ ] Reconcile all newly changed paths and obtain a Stage-A PASS.
- [ ] Review the exact candidate diff and generated manifests.
- [ ] Run the full suite once on that exact candidate.

### B3. Make the owner-authorized local freeze

- [ ] Present the exact staged NUL-delimited inventory, source hashes, tree ID, test transcript,
  exclusion manifest and reconciliation ledger to the owner.
- [ ] Obtain explicit authorization for the local commit.
- [ ] Create the freeze commit in the live recovery repository using the already-reviewed explicit
  path inventory; do not use `git add .`.
- [ ] Verify the live commit tree ID equals the Stage-B candidate tree ID. If it differs, stop—the
  reviewed object and committed object are not the same.
- [ ] Regenerate source lock, evaluator revision, payload identity and green gates from the commit.
- [ ] Tag only after the exact committed tree passes those checks. Tag naming is an owner decision,
  not supplied by this draft.

The source-freeze commit closes provenance locally. It does not publish anything and does not imply
the GitHub push has been approved.

## Stage C — real private GitHub publication, separately authorized

Stage C is intentionally not executable from this draft because the owner has not supplied the
destination account/repository or final branch policy. Inventing those values would turn a safety
gate into a placeholder.

- [ ] Owner specifies the exact destination and confirms whether disconnected `canonical-history`
  is wanted, or whether an archive/bundle is preferable.
- [ ] Verify through GitHub that the exact destination is private before adding it anywhere.
- [ ] Fetch destination refs and record them. Never assume an empty repository.
- [ ] Rehearse the exact destination refspec against a fresh local mirror of those refs.
- [ ] Use a dedicated publication clone, not either live working tree.
- [ ] Require leases for any existing destination ref. Never blind-force.
- [ ] Push all approved refs atomically in one operation.
- [ ] Verify remote ref hashes and default branch through the remote API.
- [ ] Clone over the same transport an external reviewer would use and repeat the Stage-A clean-
  clone verification.
- [ ] Record the remote URL, visibility evidence, ref hashes, release/tag identity and verification
  transcript in the release record.

If atomic multi-ref update is unsupported by the chosen service or permissions, stop and revise the
publication transaction. Do not silently fall back to sequential pushes.

## Explicit non-goals

- No deletion of nested `.git` directories, live symlinks, datasets or run evidence.
- No bulk replacement of local paths inside historical records.
- No claim that two independent Git histories have common ancestry.
- No GitHub push merely to close `gate_source_tree_frozen`.
- No publication of ignored clone bulk as a shortcut around a missing reconstruction script.
- No use of archived performance numbers, passing targeted tests, or a successful push as evidence
  that the production experiment itself is valid.

## Current expected outcome

Stage A is useful now and collision-free if implemented as specified. Stage B should wait: the
recovery tree is actively changing and currently has live P0 repairs and validation work. Stage C
requires explicit owner authorization and exact remote/branch decisions. The first likely Stage-A
failure is Model A's missing six-clone clean bootstrap; finding and fixing that in a candidate is
precisely why rehearsal precedes commit.
