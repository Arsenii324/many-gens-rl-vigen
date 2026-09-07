# START HERE — the index to the surfaces

**Read [`CURRENT-STATE-AND-RESPONSIBILITY.md`](CURRENT-STATE-AND-RESPONSIBILITY.md) first,
especially right after a context loss or compaction.** This file indexes what each surface is
*for*, as a stable reference; that one says what's *true right now* — what's in flight, what V100
jobs are running, what's queued, what's genuinely owner-only today — and is kept current rather
than appended-to. Added 2026-09-06 at the owner's explicit request for exactly this distinction.

An index, not a join: it links and says *what each surface is for*. Content stays in the surfaces so
this file cannot drift out of date with them. The one thing inlined is the category set itself,
because knowing **which categories exist** is the thing that was actually missing.

## Run first

    python scripts/production_gates.py      # is the fleet launchable, recomputed from the tree
    python scripts/open_decisions.py        # what the project's own records say awaits a person
    python scripts/requirements.py          # R1–R7, recomputed

The gate script is the only artefact here that cannot go stale, because it reads the tree instead of
remembering it.

---

## The categories, and where each lives

### 1. Decisions awaiting the owner — **one surface, as of 2026-09-05**

- [`DECISION-SHEET.md`](DECISION-SHEET.md) — this session's, **answerable by exception**: every row
  carries the default that will be acted on. Read the revision sections at the end; several rows
  changed after later evidence.
- `python scripts/open_decisions.py` — the project's own, derived from `REGISTER.md`,
  `CONSTRUCTION.md`, `requirements.py` and `FAITHFULNESS.md`.

**Reconciled.** They used not to know about each other — the project's own "one number, one home"
rule broken at the level of the record of what is undecided. `open_decisions.py` now *reads* the
sheet and lists its items alongside the registers, so **running the script is sufficient**; the sheet
stays the place the rows live, and nothing is duplicated. Its own closing line was the argument for
the fix: *"a decision written down nowhere is invisible here."*

Reasoning behind each default: [`owner-decisions-recommended.md`](owner-decisions-recommended.md).

### 2. Host migration, DataSphere → V100

[`MIGRATION-T4-TO-V100.md`](MIGRATION-T4-TO-V100.md) — every value, assumption and gate that changes
with the host, in one place, with a migration order. Exists because one descriptor serves two
machines with incompatible limits and **the expensive failure is applying half the deltas**: too
large on DataSphere fails loudly, too small on the V100 succeeds quietly and measures the wrong
experiment.

**Two different orderings, not one — checked 2026-09-05 after being asked whether a single "what to
run on V100 access" + "what's still open" checklist already existed. It did not; it was assembled
just now from these two, and the gap between them is now closed rather than just noted:**

- [`MIGRATION-T4-TO-V100.md`](MIGRATION-T4-TO-V100.md)'s "Migration order" — **host mechanics**: GPU
  confirm, renderer control, host profile, schedule regen, gates, canary, launch. 7 steps.
- [`review-11-12-gemini-triage.md`](review-11-12-gemini-triage.md)'s "Recommended dependency order"
  — **defect repair and design-point decisions**, T1–T30. 7 steps, mostly not V100-gated: steps 1–5
  are code/decision work doable now, on this machine or on remote CPU, and several are silent
  prerequisites for the migration order's own steps (its T13 = migration step 2, its T9 = migration
  step 4). Migration order previously had no canary step of its own; it now does (step 6), matching
  this order's step 7.
- The decision surface above (§1) is the *third* axis — ratification status — and is orthogonal to
  both: an item can be code-complete per either order above and still sit open in `DECISION-SHEET.md`
  until the owner rules on it.

Run the dependency order's steps 1–5 first (they need no V100), then the migration order in full.

### 3. Running the campaign

[`PRODUCTION-RUNBOOK.md`](PRODUCTION-RUNBOOK.md) — what to watch per cell, failure signatures we have
actually seen, predeclared abort criteria, and what must not be done mid-run. **This category had no
surface before 2026-09-05.**

### 4. Specifications not yet merged into the authoritative protocol

These belong in `docs/EVAL-PROTOCOL.md` and are not there yet, so the protocol is not frozen:

- [`record-completeness-spec.md`](record-completeness-spec.md) — what every episode row must carry.
  **The only requirement that cannot be repaired after the fleet finishes.**
- [`proposal-inference-and-checkpoint-selection.md`](proposal-inference-and-checkpoint-selection.md)
  — outer unit is the training seed (n=3, *not* 600 episode rows), scene estimand, competence
  threshold, checkpoint rule.
- [`retention-and-eval-depth.md`](retention-and-eval-depth.md) — checkpoint retention, eval
  frequency and depth with the arithmetic, and the cross-scale problem.

### 4b. The whole picture at once

[`SYNTHESIS.md`](SYNTHESIS.md) — ~60 findings across five reviews reduce to **three generative
mechanisms**, one of them caused by the porting act itself. Written from a session holding all of it
simultaneously; not derivable from any single document.

### 5. Evidence and verified findings

- [`faithfulness-reconciliation.md`](faithfulness-reconciliation.md) — `FAITHFULNESS.md`'s divergence
  table checked against the clones; includes the verified nine-of-twelve parallelism table.
- [`rlvigen-published-door-anchor.md`](rlvigen-published-door-anchor.md) — RL-ViGen's **published**
  Door numbers, and which baselines make a discriminating anchor.
- [`production-readiness-by-class.md`](production-readiness-by-class.md) — ready / partial / not
  ready, item by item.
- [`external-review-triage.md`](external-review-triage.md), [`review-4-5-triage.md`](review-4-5-triage.md)
  — the five external reviews, item by item, against the tree. **Historical: carries a status stamp
  of what has since been fixed. Do not read the bodies as live defect lists.**

### 5b. Current exhaustive source-review inputs — **evidence to reconcile, not a replacement for the authority surfaces**

- [`PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md`](PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md) —
  the 12-baseline, source-to-live-configuration matrix. It records exact matches, necessary
  adaptations, source conflicts, and unspecified fields rather than flattening them into a single
  "faithful" label.
- [`review-17-triage.md`](review-17-triage.md), [`review-18-triage.md`](review-18-triage.md) —
  current external-review findings reconciled against primary sources and the live tree. Their
  closure classifications are inputs to `DECISION-SHEET.md`, `FAITHFULNESS.md`, and the production
  configuration; they do not silently change any of those authorities.
- [`review-19-response/00-review-19-triage.md`](review-19-response/00-review-19-triage.md) —
  independent current-tree triage of external review 19. It distinguishes stale snapshot claims
  from live unresolved fidelity and production-readiness issues.
- [`EXTERNAL-REVIEW-ARTIFACT-BLUEPRINT.md`](EXTERNAL-REVIEW-ARTIFACT-BLUEPRINT.md) and
  [`review-artifact-spec.md`](review-artifact-spec.md) — inclusion, provenance, and
  privacy contract for external source review. The implemented local builder is
  [`../scripts/build_external_review_artifact.py`](../scripts/build_external_review_artifact.py);
  it creates a new directory only, never uploads or publishes anything, excludes generated
  results/private coordination, records every omission, and redacts unsafe symlink targets.
  `tests/test_external_review_artifact.py` is its narrow safety contract.
- [`../docs/ORIGINAL_LOCATIONS.md`](../docs/ORIGINAL_LOCATIONS.md) and
  [`PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md`](PRIMARY-SOURCE-FIDELITY-RECONCILIATION.md) —
  source identity authority. For IBAC-SNI, the canonical paper is arXiv 1910.12911; the retained
  1901.10902 InfoBot download is explicitly unrelated and excluded by the builder.

### 6. What the instruments cannot see — *this section is the surface*

Scattered, and it should not be. Known limits: `audit_implementations.py` verdicts are
**`GENUINE (PRESENCE ONLY)`** for five of twelve — it checks that a symbol exists, not that the term
reaches the gradient or that its inputs are right; `audit_comparability_seam.py` reports completeness
relative to a **hand-maintained axis list**; `production_gates.py` has produced **two false passes
about itself** (a failing `git` read as a clean tree, a RAM gate inspecting the cost model instead of
the submission path), both now pinned by tests. **Anyone quoting a green check should know which of
these apply.**

### 7. Corrections and retractions — the highest citation risk

Several claims in these files were wrong and are corrected *inline*, which means a reader can still
find the pre-correction version. See [`CORRECTIONS.md`](CORRECTIONS.md).

### 6b. Do existing measurements still stand?

[`RESULTS-VALIDITY.md`](RESULTS-VALIDITY.md) — **derived from a concern, not from a file, and it
found something five reviews missed.** Every retained record was written 04 Sep 16:55; `eval_grid.py`
was modified 05 Sep 01:25, in four measurement-affecting ways. So no number in `results/records/` is
comparable with anything measured next — including the `idaac` discharge that is one of only two of
twelve, and the `drqv2` 480.6 that the migration plan proposes as the renderer probe.

### 7b. What each row may claim

[`CLAIMS-LEDGER.md`](CLAIMS-LEDGER.md) — per-baseline, the name it must be called and the
qualification that travels with it, plus the claims the table cannot support whatever the numbers
say. Exists because a limitations section assembled at write-up time is assembled from memory.

### 8. Cross-agent coordination

`ask-claude.md` (Codex writes) and `claude-answers.md` (Claude writes) — single-writer files so
concurrent edits cannot lose a message. **Append-only logs, not state.** State lives in the surfaces
above.

### 9. Archive

`ai-review-2..5-external.md` — the reviews as received. `remote-infra.txt` — the measured host.

---

## Categories with no surface yet — named so they are not lost

Derived by asking *what are we worried about*, not by listing files. These have no home:

- ~~Open questions~~ → [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md) (six, with where to look)
- ~~Acceptance / handover~~ → [`ACCEPTANCE-R7.md`](ACCEPTANCE-R7.md) (skeleton; three prerequisites listed)
- ~~Agent collaboration protocol~~ → [`COLLABORATION.md`](COLLABORATION.md)
- **Spend ledger** — ~20 DataSphere jobs are recorded only as `job.sh` SUBMIT lines in `EVIDENCE`.
- ~~Instrument limits~~ → §6 above is now that surface.
- **Spend ledger** — deliberately not built: the DataSphere spend is sunk and that platform is being left behind. If a V100 cost record is wanted it should track *hours*, not RUB.

## Two standing cautions this session earned

1. **Documents describing state go stale within hours** when two agents work concurrently. Every
   claim about the tree should be re-derived before being quoted; the gate script is what re-derives.
2. **An instrument that cannot run must never read as one that passed.** Five instances so far: two
   false passes in the gate script, the payload checker's exit-code collision with argparse, the
   knob the runner never read, and the seam audit's replay claim. When adding a check, ask what it
   reports when it *cannot* run.

---

## Added 2026-09-05 (later)

- [`review-6-7-8-triage.md`](review-6-7-8-triage.md) — reviews 6, 7 and 8 against the tree, plus an
  assessment of the Gemini "strongest review" pair. **Four confirmed defects were fixed from these**,
  including two that would have failed every remote evaluation and one — IBAC-SNI's VIB coefficient
  being 10^4 too large — that invalidates the competence evidence the fleet plan depended on.
  Review 7 is the most complete audit the project has received; read it before the others.
- The **instrument-limits** section (§6 above) gains one: `production_gates.py` produced a **third**
  false pass, `placement provenance`, which matched the loop variable `episode_index` and reported
  that records carried an episode id when none reached a record. Now matched on the emitted key.
- [`NEXT-ACTIONS.md`](NEXT-ACTIONS.md) — where pre-production stands against review 7's priority
  order: what is done, what is blocked on the owner, and the order that unblocks the most.
- [`EVALUATOR-THROUGHPUT.md`](EVALUATOR-THROUGHPUT.md) — the same 40 idaac
  episodes took 17 minutes on an older payload and did not finish in an hour on the current one.
  A production-planning finding: the campaign's eval budget assumes the old throughput.

## Added overnight 2026-09-05 — new instruments, and what each refuses

Run these alongside `production_gates.py`; all three are now gates.

    python scripts/audit_executed_hyperparameters.py   # does a value we CLAIM reach the process?
    python scripts/audit_job_budgets.py                # can a config's timeout fit its own workload?
    python scripts/refresh_clone_patches.py --check    # do the patch snapshots still reproduce the clones?

**Why each exists** — every one closes a class that had already caused a failure:

- **executed hyperparameters**: `ibac_sni` ran at `beta=1.0` for the project's whole life while
  `FAITHFULNESS.md:808` recorded 1e-4. The value was researched, sourced, written down, and never
  wired to the process. No existing audit asked that question — they check that a *mechanism* is
  present, not that a *value* arrives.
- **job budgets**: a job was killed by its own `timeout` after paying for provisioning and bootstrap,
  and seven sibling configs carried the identical budget. Rates are measured per family and cite the
  job IDs they came from.
- **clone patches**: `RECOVERY-HANDOFF.md` says the clones are reproducible from `ext/` plus these
  snapshots. Five of six had drifted and nothing re-derived them.

### New tests worth knowing about

`tests/test_family_env_smoke.py` builds **every** family's real evaluation environment, runs the
real strict regime guard, steps a full episode and asserts the diagnostics are complete — in about
20 seconds, with no checkpoint and no GPU. Three of the four defects found overnight lived in code
no test had ever executed against a real environment.

### The standing caution this night earned, added to §6

**A skip line is a claim about the world, exactly like an assertion.**
`tests/test_rlvigen_reference.py` — 14 tests — skipped for the project's entire life because its
condition tested a hardcoded path that does not exist here, while the workbook was reachable all
along. That is the *same* assumption that made the script itself print "absent" every time it ran.
When a module skips, ask whether the reason is still true.
- [`PRODUCTION-CALENDAR.md`](PRODUCTION-CALENDAR.md) — the campaign cost recomputed from measured
  throughput and a measured env-construction time, replacing CORRECTIONS #12's envelope. ~991 GPU-h,
  41 days sequential on one GPU, ~21 packed — and what A20's depth costs in days.
- [`EVALUATOR-VALIDATION-STATUS.md`](EVALUATOR-VALIDATION-STATUS.md) — which families are proven on
  the current evaluator, with job IDs, and why "validated" here means the path executes rather than
  the number repeats.
- [`review-9-10-triage.md`](review-9-10-triage.md) — reviews 9 and 10. They found CTRL's evaluator
  double-reset (which I had wrongly refuted) and IBAC's unrunnable `procs=16` target; both fixed and
  gated.

## Added 2026-09-05 (overnight, later) — three more instruments, and what each refuses

    python scripts/audit_submission_configs.py     # would this config die on the tier it asks for?
    python scripts/record_measured_peak.py <dir>   # turn a finished job into a memory measurement

Both exist because **three jobs were lost in twenty minutes to failures fully derivable from the
tree**: two configs asked for a tier below their family's declared minimum (ctrl SIGKILLed at
11.07 GiB), and one named `rlvigen` — an evaluator *family* — where a baseline was required.

The instructive part is that `gate_scheduler_ram_invariant` was **passing throughout**. It verifies
that the submit script contains a memory check. It does. Hand-written configs go straight to
`datasphere project job execute` and never touch that script — which is written in that gate's own
comment, as the reason alda was SIGKILLed the *first* time. Added to §6's list of instrument limits:

> **Certifying that a mechanism exists is not certifying that the path in use invokes it.**

`family.check_memory` was worse than absent: `if peak is None: continue`, and the caller printed
`memory ok`. Only alda had a recorded peak, so the check was a formality for six of seven families.
It now fails closed, with `--allow-unmeasured` when the risk is taken deliberately.

### The evaluator code revision is FROZEN

    4a77df8be2c5a197484237f2e7f11141ce3f9c371351d6e7c687cf0ae1440e82

Unconditional. `evaluator_config_revision` moves freely — it did today, when ctrl's measured memory
peak was recorded — and that is the point of the split: config identity and code identity are
different questions, and one hash answering both meant every descriptor edit voided every validated
family. Status, in-flight jobs and the noise-floor section: `EVALUATOR-VALIDATION-STATUS.md`.

### A skip line is a claim about the world — now enforced, not just written down

§6's standing caution had been written and not applied: `test_family_env_smoke.py` and
`test_family_regime_readback.py` carried eight `except Exception -> pytest.skip` sites, where a
`TypeError` in our own wrapper produced the same green skip as an uninstalled dependency. They now
skip only for a genuinely absent prerequisite. **On this machine all 12 pass and none skips.**

## Added 2026-09-05 (still later) — checkpoint writes are now disk-safe, fleet-wide

Raised as a direct production concern: a multi-hour or multi-day run must not die to a full disk
partway through a checkpoint write, and must never leave a torn, half-written file at the path a
resume or an evaluator loads next.

    runnable/_shim/safe_checkpoint.py    # the shared helper; on PYTHONPATH for all seven families
    tests/test_safe_checkpoint.py        # 4 property tests + a structural check per family

**Every one of the eleven checkpoint-write call sites across all seven families** now goes through
it: atomic (write to a temp path, then rename), and disk-space-checked (wait up to 300s, then skip
that stamp loudly rather than raise). `ENABLES`-class in this project's own taxonomy (see P18/P19):
on the golden path -- disk has room, the write succeeds -- behaviour is byte-for-byte identical to
before; nothing about training, the random draws, or what is learned changes. Proven, not merely
argued: `tests/test_safe_checkpoint.py` includes a test that a write failing PARTWAY THROUGH does
not corrupt the previous good checkpoint, and two real remote jobs (alda, ctrl -- the two most
structurally different call sites: multi-optimizer dict save, and the non-torch JAX/msgpack path)
proved the import path and atomic rename work for real, not just in a local unit test.

**One frozen code member had to change to fix this**: `setup/apply_patches.py`'s P18 anchor text
matched the exact line this edit replaced, so the anchor broke and the evaluator code revision moved
a third time (CORRECTIONS #51). The move is provenance-correct and behaviourally inert, argued and
tested rather than assumed; see `EVALUATOR-VALIDATION-STATUS.md` for whether that argument stood in
for a full re-validation sweep or a confirming one was run anyway.

**What is explicitly NOT done here, and why**: the replay buffer is still never saved (for any
family except alda, which already has a `save_buffer` flag nobody turns on) -- costed at ~763 GiB
fleet-wide if done for all seven, ~27x the entire checkpoint curve, against a host whose actual disk
capacity has never been measured. See `retention-and-eval-depth.md`'s new section. Not a gap in this
work; a separate, larger decision left to the owner.

**A skipped-for-disk-pressure stamp is logged loudly in training.log (`SAFE_CHECKPOINT_SKIPPED`) but
is NOT YET a structured field in `records.jsonl`** -- adding that touches the frozen evaluator
surface a fourth time for a cosmetic improvement, so it is left as a documented log fact. If this
path is ever exercised in production, check training.log at that stamp before trusting the curve.

## Added 2026-09-05 (still later) — checkpoint margin is size-aware, with two escape hatches

Raised directly: a flat multi-GiB margin is safe against ENOSPC but can starve a checkpoint that
would easily fit, on a small host, for no reason connected to what is actually being written.

`safe_torch_save` now serializes to memory first, measures the REAL payload size, and requires only
`max(64 MiB, 3x that size)` free -- not a flat 2 GiB regardless of host or object. Two environment
escape hatches exist for when the automated judgment is itself wrong, readable by a job already
running, no restart needed:

    SAFE_CHECKPOINT_FORCE=1              # skip the disk check entirely; write is still atomic
    SAFE_CHECKPOINT_MIN_FREE_BYTES=<int> # override the computed threshold with an exact value

Five new tests in `tests/test_safe_checkpoint.py` cover this, including one that spies on the actual
call `safe_torch_save` makes to confirm the size-aware path is genuinely reached by every real
caller, not just exercised in isolation -- the exact class of gap CORRECTIONS #52 found twice.

## Added 2026-09-05 (still later) — a concurrent-write race in safe_checkpoint, found by a direct question

Prompted by being asked directly whether compute/disk/off-golden-path concerns were truly settled,
not by an observed failure: `safe_checkpoint.safe_write`'s disk-space check and the write itself are
not atomic together. Two packed cells sharing a disk could both check `shutil.disk_usage()`, both
see enough free space, both proceed, and the second to finish could still hit real `ENOSPC` -- a
TOCTOU race, never previously written down because packing has never actually been run (the 0.658
retention figure is one measurement, extrapolated into the calendar, not a tested concurrent
scenario).

**Checked before recording, not assumed**: the failure mode under this race is bounded to a skip,
never corruption. `write_fn` always targets a `.tmp` path first; any exception (including a real
ENOSPC hit during the write itself) is caught and only ever touches that tmp file. The atomic-rename
safety property survives the race; only its efficiency doesn't (both processes might skip a stamp
when only one strictly needed to). Not fixed tonight -- a real fix (a filesystem lock, or reserving
space before both checks proceed) is real engineering against a scenario that has never actually
been exercised, and packing itself remains untested. Recorded so it is not rediscovered the
expensive way if packing is ever actually run.

Also unresolved: the production host's actual filesystem/mount type has never been measured
(`notes/remote-infra.txt` has CPU/RAM/GPU, no `df -h`, no mount info) -- lower risk, since a
same-directory `os.replace` is atomic on essentially any POSIX filesystem including ordinary NFS
operation, but "unmeasured" is still the honest word for it.

## Added 2026-09-05 (full-project audit, requested directly by the owner) — four new decisions, six defects

Requested plainly: take responsibility for the whole project, all aspects, all stages, all prisms
(docs, code, papers). Findings and fixes, not a re-list of what §1-9 above already cover:

- **New decisions, A26-A29** (in [`DECISION-SHEET.md`](DECISION-SHEET.md)): A26 (PPG auxiliary
  cadence vs wall-clock, after reverting an undeclared V100 override that had doubled it away from
  the one published continuous-control reference — [`CORRECTIONS.md`](CORRECTIONS.md) #58); A27
  (off-policy update-to-data ratio — first version used the wrong denominator, corrected after
  review 14 caught it, see [`FINDING-update-to-data-ratio.md`](FINDING-update-to-data-ratio.md));
  A28 (three seeds resolve ~53% relative difference, not the ~31% a stale five-seed-era sentence
  claimed — the normal approximation also failed at this n; see
  [`FINDING-resolving-power-at-n3.md`](FINDING-resolving-power-at-n3.md)); A29 (idaac's and ppg's
  regular-phase update density runs 4x-32x their Procgen source because a single V100 cannot run
  Procgen's parallelism — see
  [`FINDING-on-policy-update-density.md`](FINDING-on-policy-update-density.md)).
- **Six defects found and fixed**, all local, tested, non-vacuously verified — full detail in
  `CORRECTIONS.md` #58-#66: an undeclared PPG cadence override; a red-green-tested fix that
  protected a retired code path production never ran (ALDA utd); a descriptor-scanner class-fix
  that was correct but nothing forced it to run before a remote job; a stale canary budget floor
  that would have passed a zero-rollout V100 canary for idaac/ibac_sni; a schedule artifact
  modeling IBAC's memory with a different, stale formula than the gate that checks it; a runner bug
  where a FAILED cell's manifest could still carry a COMPLETED marker; and an evaluator identity
  hash omitting a file (`RL-ViGen-upstream/utils.py`) it imports live.
- **The evaluator code revision moves on every edit to the files above** — checked live, don't
  trust a cited hash from earlier in this file or elsewhere; run `production_gates.py`'s "shared
  evaluator validated" row.
- **A recurring class, worth naming**: three of the six defects were "the same fact computed twice,
  correctly in one place and stale in the other" (idaac's diff-size figures; the descriptor
  scanner's reach vs. what runs before a job; IBAC's memory model in two files). Worth a standing
  suspicion whenever a number looks "already fixed": check whether anything else computes the same
  fact independently.
- **Process idea adopted mid-session** (the owner's): where a test pins EXACT literal text (a line
  number, a string-slice boundary) rather than behavior, the tested site now carries a one-line
  comment naming the test — applied at the sites touched tonight, not swept across the whole tree.

## Added 2026-09-05 (still later) — A30, and a same-session self-correction worth reading

**A30** ([`DECISION-SHEET.md`](DECISION-SHEET.md)): `ctrl`, `idaac` and `ibac_sni` all sample from
an unbounded, unclamped Gaussian action head and pass the RAW sample both to `env.step()` and into
their own PPO log-probability computation — but robosuite's controller clips the action before it
is actually executed. Traced directly, confirmed real, not fixed (method-defining); the runbook's
diagnostics now cover all three, not just `ibac_sni`.

**Worth reading regardless of interest in A30 itself**: the entry's own revision history is a live
example of this project's core discipline working within a single session — a first draft claimed
`log_std` monitoring was missing for all three, was checked against the live tree minutes later,
found wrong (all three already call `gaussian_policy_health`; `ibac_sni`'s case was already an
independent open decision since 2026-09-04), and corrected in place rather than left standing.
CORRECTIONS #69 is the same correction, filed as its own numbered entry precisely so a
self-correction is as visible as an externally-found one.

**Full suite status, checked fresh**: 0 failures, exit 0, after every fix through CORRECTIONS #69.
Gate: 28 PASS / 1 FAIL (dirty tree, expected during concurrent work) / 11 OWNER.

## Added 2026-09-05 (later still) — per-family online-eval mechanism, fully traced

[`FINDING-online-eval-per-family.md`](FINDING-online-eval-per-family.md) — answers "do we have
during-training eval for each of the 12, and is it RNG-safe" for all seven evaluator families
individually. Three suppressed (sentinel value, rlvigen/dmc_gb/alda), two RNG-isolated and left
running (idaac fully, ctrl partially — already tracked), two have no online-eval mechanism at all
(ibac_sni, ppg). One self-caught false alarm along the way, corrected before writing this file.

## Added 2026-09-06 — the metric-inventory subagent's 4 findings closed; C1's "does it cancel" question actually worked through

A dispatched Sonnet subagent's report (`METRIC-INVENTORY-VERDICT-2026-09-05.md`) named 4 secondary
findings beyond what CORRECTIONS #77 had already fixed. All 4 independently re-verified against
live code (not trusted from its prose) and closed — `CORRECTIONS.md` #78 (tracking) through #80:
`drq`'s architecture misclassification in PART2 Finding 6 (it's SAC-family, not DrQv2-family —
its own `SquashedNormal`/`TanhTransform`, not shared with svea/sgqn/curl); `critic_loss` is four
different formulas under one name across 8 of 12 baselines (added as PART2 Finding 8, reported not
resolved — a k2/k3-shaped naming collision, owner's call to pool or not); a stale "`ctrl` is not
wired" PART2 claim (it's wired now, for the `ppo`/`ppo_ctrl` branch — `daac`/`daac_ctrl` genuinely
still isn't, documented as an explicit caveat rather than left implicit); and a `clip_fraction`
"takes the log-ratio for precision" overclaim (checked against all four live on-policy
implementations, not just the reference helper — none of them do; only `approx_kl_k3` has a real,
smaller, and *inverted* version of that asymmetry in `idaac`/`ibac_sni`).

**The owner's sharper question — does C1's 9-vs-3 truncation-bootstrap split actually cancel in
the metrics this project reports, or is "declare and quantify" being left as formalism —**
answered directly, not deferred again: [`FINDING-c1-does-the-asymmetry-cancel.md`](FINDING-c1-does-the-asymmetry-cancel.md).
Short version: no metric in the reported matrix (`R_train`, `R_OOD`, `Δ`, success rate, retention,
floor-adjusted retention) is protected by construction; the difference and the ratio each have a
cancellation story, but the two are mutually exclusive (additive-invariant vs. multiplicative-
invariant), so reporting both is not a hedge that protects the pair jointly. Only an empirical
ablation can resolve it, and none exists yet — named as the concrete next step rather than
repeating the phrase.

**Checking whether that split is actually kept out of tables (not just declared) found two real,
independent bugs, both fixed** (`CORRECTIONS.md` #81, #82): `scripts/results_table.py` and
`scripts/preprod_table.py` — the two table generators — had zero mechanism to detect a table that
pools rows across C1's split, despite C1 being rated the largest comparability defect found. Not
yet live (today's populated cells all share one group), but `rad`/`soda`/`alda` are explicitly
"not yet run" in both files, so the first cell for any of them would have mixed silently. Fixed
additively in both, with tests. While fixing this, found and fixed a second, dormant drift risk in
the same file (#83): `preprod_table.py`'s `STACK` dict was a hand-duplicated literal that happened
to still match `rlgen/protocol.py`'s `OBSERVATION_GEOMETRY` — now reads from it directly, same
mechanism as the new `TIME_LIMIT` dict.

**A third instance of "a doc's prose went stale after the code it describes changed"** (#84, after
PART2's ctrl-wiring and clip_fraction claims): `scripts/audit_eval_state.py`'s `ppg` entry still
said "no evaluation code exists" after `runnable/_launch/ppg_eval.py` had already been written and
`preprod_table.py`'s own `ESTIMATOR` dict already correctly said `ppg: "SAMPLE"`. Fixed the entry;
a dependent test (`test_the_two_baselines_needing_evaluator_work_are_named`) also expected `ppg`
in the still-needs-work set and had to be updated to `{"ctrl"}` only, caught by running it rather
than trusting the doc edit.

**Housekeeping, unrelated to the audit content itself**: this workspace's local git (initialized
2026-09-04, no remote) had 207 files accumulated uncommitted since across multiple sessions.
Checkpointed everything except Codex/Luna's own in-progress evaluator-identity-binding repair
(explicitly excluded by path, commit `7730748`) — full list and reasoning in
`notes/claude-answers.md`'s 2026-09-06 entries. A ~2h V100/DataSphere quota was granted but
deliberately not used yet, since Codex's repair sits directly on the job-submission contract path.
