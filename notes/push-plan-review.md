# Review of `draft_hypothetical_push_plan_under_review.md` (Gemini, Plan v3)

Reviewed 2026-09-05 at the owner's request, as a parallel low-priority task. The document is
self-labelled `[DRAFT - HYPOTHETICAL - STRICTLY UNVERIFIED - DO NOT EXECUTE]`. Nothing was executed
and nothing was modified; the review is read-only and its factual claims were checked against the
filesystem.

**Verdict: redo, not patch.**

## The fact that resets everyone's picture, mine included

**The recovery workspace has its own git repository**, created 2026-09-04: branch `main`,
**30 commits**, **no remote**, 162 uncommitted paths. Its first commit is literally *"Snapshot the
recovery workspace, which had no version control at all"*.

That history shares **zero ancestry** with the versioned tree at
`ccm-intro/projects/many-gens-rl-vigen` (`main`@`c6f87df4`, `nd-ln-architecture-transition`@`f041f5e1`,
last commits 2026-08-16 and 2026-08-29; neither has a remote either). Add the six nested vendor
`.git` directories under `runnable/` and there are **three independent histories** in play.

I had been repeating "the recovery workspace has no `.git`" — true when the plan was drafted, false
since 2026-09-04, and I carried it into the review briefing. `gate_source_tree_frozen` had been
reporting a live uncommitted-path count the whole time, which only works if git is present. The
signal was in front of me.

## The two findings that make the plan unsafe as written

**S1 — the plan is silent about the two-tree situation.** It targets the recovery workspace
exclusively (its own evidence: `notes/remote-infra.txt`, the root `places365-val.tgz` symlink,
`cfg-*.yaml` files — none of which exist in the versioned tree), yet Phase 7 would push that tree's
independent history to GitHub as if it were the project's sole provenance. The versioned tree's own
uncommitted work and single-tree-only files are never diffed or reconciled. There is no
"which tree wins per file" logic anywhere.

**S2 — the plan engineers its own failure, in the wrong order.** Phase 3 deletes the six nested
`.git` dirs (~296 MB, measured) so the baselines become trackable; Phase 4's replacement `.gitignore`
**silently drops the `runnable/*/` ignore rule**, which exists with an authored comment explaining
the project's deliberate policy: clones are reproducible from `ext/` plus
`runnable/_patches/<name>.patch`, so *the change set is versioned and the clone is not*. The result
is ~160–170 MB staged against Phase 5's own `assert total_sz <= 50MB`, so the script aborts —
**after** Phase 3's `rm -rf` has already run. The one hard-to-reverse step precedes the only gate
that would have caught the problem, and a documented provenance decision gets reversed as a
side effect of a gitignore rewrite.

## Smaller, still real

- **S3**: the root `places365-val.tgz` symlink is **live**, not broken — the plan lists it for
  deletion among two genuinely dead ones. `*.tgz` is already gitignored, so deleting it buys nothing
  and risks local dataset tooling.
- **S4/S5**: no full-tree backup before destructive steps, and the size check runs *after*
  `git add .` rather than as a dry run.
- **S6**: the secret scan misses `.env`, AWS keys, `ghp_` tokens, `.netrc` and key *files*; calling
  it a "Zero-Leak Gate" overclaims.
- **S7**: never verifies the destination repo is **private**, which `CLAUDE.md` requires by default.

## What this means for A11 (our own commit decision)

It makes A11 **cheaper and safer than assumed, and separable from the push**. The workspace repo has
**no remote**, so a local commit publishes nothing, is reversible, and would close
`gate_source_tree_frozen` — the one failing gate that is ours rather than the owner's or the
hardware's. The push, by contrast, is the part that needs the reconciliation this plan lacks.

**Not doing it yet, deliberately.** The owner deferred the commit because configuration was still
moving, and it still is: four validations are in flight and one of them (ctrl) has already forced the
frozen hash to move once today. The natural trigger is *the point where the hash stops moving* — when
those four land without a further code-member fix. Then a local commit is the right conservative
step, and the push remains a separate decision with its own prerequisites.
