# Accountability — the open taskset, and how each item was actually closed

Asked for on 2026-09-17 (20:52 MSK): keep the whole taskset written down, so that no request is
closed at an intermediate step, closed narrowly, or closed without its verification. An item moves
to **DONE** only with a short report of *how* it is done and *what verified it*. "Written" is not
"verified"; "ran" is not "checked against ground truth".

Before marking anything DONE: name the command or artifact that proves it, run or read it fresh,
read the whole output, and only then write the closing report. Re-read the request's own words at
that moment; a finish line written early can be narrower than what was asked.

Status words: **OPEN** (not started) · **PARTIAL** (some done; the missing part is named) ·
**DONE** (with a closing report) · **BLOCKED** (on a named external condition).

---

## A. The campaign itself — the overarching goal

> "run the 12 'baselines' on, say, rl vigen easy door and get genuinely same-axes measurements...
> reasonably try ('best effort') see what succeeded or failed."
> "Optimally utilize the provided communal host's resources for the highest-impact results till
> the deadline ... Work no less than till 9:00 with active monitoring ..."

| id | task | status | what closes it |
|---|---|---|---|
| A1 | Prod monitoring alive at all times, including when nothing of ours runs | PARTIAL (continuous duty) | trip watcher + beat Monitor re-armed on each 30-min expiry; waiter-log Monitor likewise. **Logger renewed 2026-09-18 10:11 and it did not go smoothly:** killing the old one and starting a replacement 2 s later left the host with NO logger, because the dead parent's `sleep` child still held the flock. Fixed by retrying until it appears in `pgrep`; the renewal script now warns loudly if none is running. The new logger runs 40 h from 10:11. Never closes while the campaign runs. |
| A2 | Launch the highest-information next cell when a card is genuinely vacant (co-tenant absent ≥10 consecutive min) | **ARMED 2026-09-18 01:10** | A real window opened 21:29–21:49 on 17 Sep (CAPACITY fired 21:39, 32,495 MiB free) and passed unused because nothing launches automatically. `wait-and-train-v4.sh` now waits on the host for `idaac` s103 under the validated rule (holders **and** free memory, ten samples), with MAXWAIT=36000 so it ends when the occupancy logger does; all seven of its refusal branches were exercised first. A Monitor tails its log. Queue after s103: `ibac_sni` s102 from zero, `ibac_sni` s103, `ppg`'s two remaining seeds (note 35). |
| A3 | Every finished cell collected and verified, not merely copied | DONE for idaac s101, idaac s102, ibac_sni s101; ibac_sni s102 partial salvaged | Closing check per cell: records file in results/records, host-runs.jsonl status, endpoint rows present, evaluator gate still 7/7, production_gates 0 fail. |
| A4 | A reading of what the finished cells say, updated when n grows | PARTIAL | notes/production-host/34-… holds the two-seed idaac reading (ranking retracted). Update when idaac s103 lands. |
| A5 | Honest succeed/fail account across all 36 cells | PARTIAL | campaign_status.py table: 3 DONE, 1 PARTIAL, 32 MISSING. Report at the end of the window, with the reason for each non-run. |

## B. The operator guide — a new operator runs the whole thing without access to me

> "Assume a new operator would run the whole thing e2e on host without having access to you ...
> Flesh out this path at all parts ... what's what, what runs what, what runs after what, whats
> the containers ... call-integration, download-integration, operator-instructions integration,
> monitoring and tooling that you'd use, observability."
> "put the things you're actually sure in, not a random layer of a big lot of untested scripts"
> "Have a clean model and understanding of what every part, stage, or facet of the operator's run
> would do ... restarting/early stopping/checkpoint capability ... docker image names and
> caveats/run procedure/resources ... integrations and checks ... golden path still most fleshed
> out ... catalogize all [out-of-reach], narrow each to the isolated part, and leave a clean label
> for the operator what's the target/state/thing/operation to be achieved there."

Guide: `notes/OPERATOR-GUIDE.md`. Each facet below is a separate item so that none is closed by
the others.

| id | facet | status | what closes it |
|---|---|---|---|
| B1 | Stages and what feeds what (artifact spine) | DONE (§3, §4) | — |
| B2 | Checkpoint / restart / resume capability, per family, all seven | DONE 21:00 | see closing report B2 |
| B3 | Early-stopping and stop mechanisms: every way a cell ends before 600k | DONE 21:00 | see closing report B3 |
| B4 | Docker images, run flags, caveats (EGL/graphics, --gpus, venv mount, caches) | DONE 21:20 | see closing report B4 |
| B5 | Resources per family (VRAM, disk, CPU, wall time) | DONE 21:10 | see closing report B5 |
| B6 | Integrations and checks | DONE 21:05 | see closing report B6 |
| B7 | Golden path fully fleshed, as executed | DONE 21:10 | see closing report B7 |
| B8 | Off-golden-path model | DONE 21:30 | see closing report B8 |
| B9 | Out-of-reach catalogue, each narrowed and labelled (target / state / operation) | DONE 21:15 | see closing report B9 |
| B10 | Links to project-wide docs instead of duplicating | DONE 21:35 | see closing report B10 |
| B11 | Grounding pass: nothing in the guide that I did not execute is stated as working | DONE 21:45 | see closing report B11 |

## D. Out-of-reach items being closed while compute is unavailable

Catalogue in OPERATOR-GUIDE §11.4. These are the ones that can move without a free card.

| id | item | status | what closes it |
|---|---|---|---|
| D1 | O2, payloads for the four families that have never run | PARTIAL — laptop half DONE 2026-09-17 21:20 | `build-payload` + `verify-payload` + `verify-evaluator-binding` exit 0 for `rlvigen`, `dmc_gb`, `alda`, `ctrl`. Left: the payload-naming decision (v5 reads a literal `payload-v214-` name) and the copy to the host. |
| D2 | O8, a fresh clone reconstructed on Linux | **DONE 2026-09-17 22:05** | Ran in a `python:3.11-slim` container on the host against the committed tree: `bootstrap_sources.py` then `verify_sources.py`, both exit 0, both printing `source reconstruction verified`; 9 min 40 s, 1.7 GB. Evidence bundle `results/evidence/linux-reconstruction-from-a-fresh-tree` (tests green). Scratch removed — which took a second container, because container output is root-owned. Left open and renamed O8b: a fresh clone taken to a payload on Linux, and any host other than cds2. |
| D3 | O8's remainder: a fresh clone taken to a verified payload on Linux | **DONE 2026-09-18 01:30** | One container, same fresh tree: reconstruct, then build-payload + verify-payload + verify-evaluator-binding for all seven families — every exit code 0, RUNNER_CONTRACT read as 19 from the tree. Captured as the second excerpt in `results/evidence/linux-reconstruction-from-a-fresh-tree` (bundle tests green); scratch removed, host at 168 GiB free. What remains is O8b (any host other than cds2) and the fact that a fresh clone has never been taken to a RUNNING cell. |
| D4 | O1, the Places365 train corpus on the host | **DONE 2026-09-18 10:50** | 26 GB, 1,803,462 files, 365 classes shipped from the laptop's validated copy as a tar stream; `verify_datasets --split train` on the host PASS; 200 sampled files sha256-identical to the laptop, 0 mismatched; permissions fixed; no duplicate archive. The blocker was the source (csail 623 B/s) not the host (GitHub 13.7 MB/s). Untested: a cell consuming it at run time. |
| D5 | O1's other half: making `svea`/`sgqn`/`soda` launchable once the corpus lands | **DONE 2026-09-18 07:05** | `train-production-cell-v6.sh` (v5 + PAYLOAD + PLACES365_DIR, deployed); the wrapper path dry-run proven for `svea:101` (read-only mount, forwarded split, pinned image, rc=0); `payload-v215-rlvigen.tgz` and `payload-v215-dmc_gb.tgz` on the host, hash-verified; sizing written up in OPERATOR-GUIDE §5.3 including the 47.5 GiB disk double-charge and the ~40 GiB RAM bound. Still untested and labelled as such: a cell actually consuming the corpus at run time. |

## C. Housekeeping questions

| id | task | status | what closes it |
|---|---|---|---|
| C1 | "Do we have local residual files that take a lot of space? Answer, don't delete" | DONE (answered) | Deletion of the scratchpad clonetest (287 MB) postponed until the user returns, as allowed. |

---

## Closing reports

(Each DONE item gets a dated paragraph here: what was done, what verified it, what remains out of
scope and why.)

**B2, B3 — 2026-09-17 ~21:00.** OPERATOR-GUIDE §6b (ten stop paths: trigger, active window, marker,
what survives) and §6c (where each family's checkpoints sit mid-training; what a restore holds,
uses and loses; whether any launcher wires it). *Verified:* every file:line citation re-read with
grep after writing; four were off and corrected. The yield marker order (YIELDED then FAILED) was
checked against the 16 Sep job log in an evidence bundle, which exposed a real defect in guide §10.1
(it read only the last marker) — fixed. Resume is labelled unexecuted everywhere. *Out of scope:*
whether a continued run may stand in for a seed is an owner decision (§11.4 O5).

**B6 — ~21:05.** §8b: each check with what it proves, what it does not, when it runs, and whether it
ran here. *Verified:* gates, campaign_status, export_fleet, operator_readiness, open_decisions and
audit_attempt_ledger --strict all re-run fresh (gates showed 1 FAIL for uncommitted docs, 37/0/9
after commit). Two descriptions corrected against the collector's and launcher's code.

**B5 — ~21:10.** §4c.1: disk from family.py disk-requirement run for all twelve; training time, CPU
and RSS from `time -v` in the four executed training logs on the host; RAM figures from
families.json labelled computed/extrapolated, plus the fact that the launcher never checks host RAM.
*Found while verifying:* "ibac trained in 44 min" (really 31.5; 44 included bootstrap), "idaac has
8 processes" (really 1), "grid 17 h vs 45 min training" (wrong for idaac, 7.3 h) — corrected in the
guide, the procedure, HANDOFF, CURRENT-STATE and the idaac s102 ledger note.

**B7 — ~21:10.** §5.2: one cell from vacancy check to collected rows, with the launch block copied
from the 11:00 ibac_sni s102 launch and the record/watch/collect/failure commands copied from the
16–17 Sep sessions (pulled from the transcript, not recalled). The two capacity tools that ran all
afternoon were committed; capacity-check.sh re-validated from the committed copy (11:00 AVAILABLE,
07:52 not).

**B4 — ~21:20.** §6d: images, GPU/graphics/mount/limit settings with file:line, the per-launch
environment build (launch-to-first-GPU 7–22 min measured from the occupancy log), and which code
the host really runs: payload inside the cell, host checkout for launcher and watches. *Verified by
hash on the host:* launch-path files match laptop HEAD apart from comments; the in-cell
watch_policy_health.py is the payload's 229ed01 copy.

**B9 — ~21:15.** §11.4 O1–O9, each with state, why, target, operation, done-when. *Grounded by
execution:* the Places365 check was run in the helper container on the host (train FAIL 20/365,
val PASS structure-only). *Found while doing it:* the procedure told operators to run
populate_evaluator_ledger.py on production runs (two places plus HANDOFF) and to run Python on the
host shell for Places365; the host-scripts README claimed Places365 was in place. All corrected.

**B8 — ~21:30.** §10.4: what you see (the exact printed text), what it means, what to do next, in
three groups — before the cell starts, during or after training, at collection. Every row labelled
**seen** or **code**. *Verified:* each string grepped out of the script that prints it; three "seen"
labels were downgraded when the ledger showed the branch had not actually been hit.

**B10 — ~21:35.** The guide's header now routes what-a-number-means questions to TASK,
RESEARCH-FRAME, STATUS-AGAINST-THE-GOAL, EVAL-PROTOCOL, COMPARABILITY_CONTRACT,
PART2-METRIC-INVENTORY, DECISIONS-IF-PRODUCTION-GOES-WRONG and PROJECT-INDEX, rather than
restating them. *Verified:* every link resolves; each description taken from that document's own
opening lines.

**B11 — ~21:45.** Read the guide end to end against the artifacts. *Found and fixed:* §5 called
`wait-and-train-v3.sh` the default and said it enforced the vacancy rule — it counts free memory
only and would launch beside today's co-tenant, which §5.1 exists to prevent; "both launches that
ignored the check were stopped" (the second passed the check and was stopped anyway); the yield
count; two cross-references broken by a renumbering; a dangling sentence about the waiter's lock.
The procedure's own script inventory line for the waiter was corrected too. *Remaining honestly
untested:* everything in §11.4, and §11.1/§11.2's right-hand columns.

**Noticed, not acted on:** `production_run_register.py` marks terminal `failed` statuses as
"likely stale" by age, which is misleading for a status that cannot change.

**C1 — 2026-09-18, W2 of the operator-package plan.** `production_reading.py` counted skipped
*cells* (MISSING/PARTIAL) but dropped rows inside a DONE cell with six bare `continue`s and no
tally. Fixed: `_by_scene` now returns a drop reason per row, split into `DROPPED_BY_DESIGN` (curve
rows, the pooled ten-scene row) versus UNREADABLE (everything else, printed with a warning). Test
added first, red before the fix; against the real records today, 0 unreadable rows. *Verified:*
`pytest tests/test_production_reading.py` (20/20), `production_reading.py` printed output read by
eye.

**C2 — same day.** `wait-and-train-v4.sh` fires once; a fast failure (the 24 s EGL death of
2026-09-17) wastes whatever remains of a window that was free once in 13 hours. Added
`RETRY_FAST_FAILURES=1` (default 0, unarmed on the host), bounded by `FAST_FAILURE_SECONDS` and
`MAX_RETRIES`, refusing to retry a run that had already been going for a while (a partial run on
disk is a human decision, not a waiter one). *Verified:* `tests/test_wait_and_train_retry.py`
(4/4) against a fully stubbed PATH — no docker daemon runs here, nothing touches the real host,
lock or occupancy log. §5.2's manual-launch template also gained the RAM check the waiter already
enforces, since a hand launch bypasses the waiter and therefore the only RAM guard that exists.

**C3 — same day.** Added §3b to `OPERATOR-GUIDE.md`: a stage-contract table (target state,
artifact path, consumer, proof command, redo-only-this-stage, what it does NOT leave) plus the
companion "state that lives nowhere in this table" list from the adversarial review. *Verified:*
`tests/test_operator_readiness.py` (8/8, unchanged by the addition — the new section does not
break any documented-interface or clone-completeness check); `production_gates.py` back to
37 pass / 0 fail / 9 owner once committed.

**C4 — same day.** Built `scripts/visual_render_probe.py` as the substitute for the O6 renderer-
parity gate (owner's descope: a visual question, not a full R_A/R_B numeric comparison — see
§11.4). It resets the Door env at each regime through the same `robo_make` constructor every cell
uses and saves one PNG per regime. **Not yet run on the host**: it needs the same pip-install
bootstrap as a real cell (robosuite/mujoco are not baked into the pinned image), which is real
host-launch risk and cost for four PNGs standalone — C95 already rules out a cheaper local/CPU
render as answering a different question (`MUJOCO_GL=egl` vs `glfw` differ by an order of
magnitude on the same checkpoint). Recommended path, written into §11.4: run it inside the next
real cell's container, once that bootstrap is already paid for. *Verified:*
`tests/test_visual_render_probe.py` (6/6) proves the frame-extraction and file-writing logic
against a fake environment, with no robosuite/mujoco/GPU required to run that test. **Left
honestly undone:** the actual host run, and therefore the evidence bundle — creating one now with
no captured evidence would itself be an unverified claim, which this project's own evidence-bundle
discipline exists to catch.

**C5 — same day.** Removed O8b (any host other than `cds2`) from §11.4 per the owner's ruling: "if
the operator does it it's their problem." It is no longer carried as an open, unexplained item; its
history stays in this file's D2/D3 rows as what was actually run.

**C6 — same day, closing the plan.** The full suite failed once mid-pass:
`test_default_maker_only_resolves_the_real_dependency_lazily` (C4's test) passed alone but failed
in company with "DID NOT RAISE ImportError" — a sibling test's `sys.modules["wrappers.robo_wrapper"]`
injection had leaked, the exact "green in isolation, red in company" failure
`test_eval_loop_measurement.py` already names for these same module names. Fixed by moving the
check into a subprocess, which starts with none of that state; confirmed against the specific
239-file subset that reproduced the pollution (now exits 0), and against the file alone (6/6).

**Plan closed.** `production_gates.py`: 37 pass / 0 fail / 9 owner. `pytest tests/ -q`: full run,
100% collected, no F/E markers, no "short test summary info" section, exit 0 captured directly
(not through a pipe — see the memory note on why that matters). Tree clean at the commits above.
W1 did not fire: the card was occupied by other groups for the entire session (a third group,
`sg_sam2`, joined partway through; noted, not acted on — no launch decision was needed). W2(a)–(d),
W3 and W4/W5 are done, tested, and committed as listed above. §7b of CURRENT-STATE-AND-
RESPONSIBILITY.md carries the three decisions that remain the owner's.

**C7 — post-close, continuing autonomously while the card stays occupied.** Answering the owner's
detailed questions about checkpointing, disk, eval scheduling and mounts (verified against actual
code and the live host rather than recalled) surfaced a real doc staleness: O2 claimed
`train-production-cell-v5.sh`'s hardcoded payload name blocked `rlvigen`/`dmc_gb`/`alda`/`ctrl` and
that the fix "has not been made or tested." False — `train-production-cell-v6.sh` already takes
`PAYLOAD=<path>` (confirmed by `diff`: v5 verbatim plus that substitution, identical behaviour when
`PLACES365_DIR` is unset), and it's the exact mechanism `svea`'s armed waiter uses right now.
Corrected in the guide; `test_operator_readiness.py` 8/8, gates 37/0/9 after commit.

**C8 — GitHub-readiness audit, prompted by the owner asking "is this ready to take from GitHub?"**
Found the single largest gap of the whole session: **none of the day's 9 commits had been pushed**
(local `main` 9 ahead / 0 behind `mygithub/main`). Scanned the diff for secrets first (clean;
the pre-existing host IP/username already appears in 83 files on the pushed history, not new
exposure), confirmed fast-forward, pushed to `main` at the real GitHub URL
(`https://github.com/Arsenii324/many-gens-rl-vigen.git`).

Then validated the GitHub path itself, not just the local one: confirmed the repo is genuinely
public via the GitHub API; did an actual `git clone` of the literal URL (not `git archive HEAD`,
which is what the existing `linux-reconstruction-from-a-fresh-tree` bundle used) inside a
container on the host, ran `bootstrap_sources.py` + `verify_sources.py`, both rc=0 — new evidence
bundle `results/evidence/github-url-clone-reconstructs/`. Ran `test_operator_readiness.py` against
the literal cloned directory (not the working copy) — 8/8. Found and fixed a real gap: no
document anywhere stated the actual `git clone <url>` command; added to
`docs/RUN-THIS-PROJECT.md`'s first line. Cleaned the host scratch dir through a container
(root-owned files), disk confirmed restored (125 GiB free before and after). Pushed this second
round too (`8094d96`).

Surfaced, not decided (policy calls for the owner): the repo is public with no `LICENSE` file, and
has no CI. Stated plainly in the bundle's "What this does not show" rather than acted on.

*What this changes and does not change:* the distribution mechanism (can a stranger actually get
this from GitHub and start the cold start) is now verified end to end. It changes nothing about
the open scientific question, the untested `svea` configuration, or the three owner decisions —
those stand exactly as before.

**C9 — disk cleanup, and a chain of self-corrections on per-family eval mechanics, prompted by the
owner's sustained, specific pushback.** Full detail in `production-host/27`'s "Executed" section
and `production-host/37`; summarized here so the taskset stays traceable in one place.

- **Disk**: 17 pre-production probe directories in `~/rlvigen-runs`, individually verified (not
  pattern-matched) — checkpoint content, whether rows exist anywhere in the repo (current or
  superseded), evaluator revision. Two real production attempts and one physical sample kept; 17
  removed by literal name, no glob, inside a container mounting only that directory. 66G→36G,
  host free disk 125→153 GiB.
- **The "96s endpoint eval" claim was wrong**: cited from a 10-episode attestation job, not the
  800-episode production grid. Real number, from a completed cell's own log:
  eval (curve+endpoint) ≈13.6h vs training ≈7.46h — eval costs roughly double training, explained
  fully by episode-count arithmetic (eval runs 2.4× the total environment steps training does, at
  a faster per-step rate that doesn't make up the difference).
- **ppg's checkpoint cadence was wrong twice before it was right.** First: "100,000 default, never
  overridden" — wrong, because `families.json`'s templated options (not the shell launchers I
  grepped) wires `ic_per_save`, and `families.json`'s own comment already named this exact mistake
  as a defect fixed 2026-09-04, which I re-asserted as current. Second (the retraction): implied
  neither 50k nor 100k was the real number — also incomplete; the real executed argv shows
  `--ic_per_save 50000` explicitly. Reconciled: 50,000 is the configured threshold; ~51,200 (the
  MPI rollout quantum) is why saves don't land on clean 50k boundaries. `production-host/37`
  carries the full account, including why three independent files had to agree before this was
  checkable at all.
- **ctrl's in-loop eval steps two fully-vectorized test environments at training's own scale**
  (`num_envs=FLAGS.num_envs` for both), every training step — confirmed by reading `_mk`'s
  construction, not assumed from the "every step" wording. Unlike idaac's explicitly-budgeted
  ~20% overhead, no equivalent cost accounting for ctrl's ~3× was found anywhere in `families.json`
  — real asymmetry, surfaced, not fixed.
- **The RNG-isolation gap in ctrl** (JAX policy key consumed by eval calls, only NumPy restored)
  was independently re-derived from code, then checked against `notes/FINDING-online-eval-per-
  family.md` — already documented, already reviewed, accepted as non-blocking. Correctly not
  presented as a new finding.
- **Config-hierarchy question, answered but not written up as a file**: traced from
  `family.py`'s actual resolution code (`resolved_descriptor`, `host_profile`, `render`) — five
  layers (`families.json` base → host-profile override, merged per-key → `NATIVE_HOST_PROFILE`
  selecting which profile → template rendering → a fully separate, parallel shell-env-var
  hierarchy for operational parameters that never feeds back into the template layer). No existing
  dedicated doc found for this; owner said it's fine to leave as a verbal answer rather than a new
  artifact.

**Pattern worth naming plainly**: three of the corrections above share one root cause — checking a
source file or a shell launcher and concluding "not set" without checking whether a *different*
layer (a JSON template, a real executed argv) does the actual wiring. The fix that worked every
time was the same: read the real executed config of a completed run, not the code in isolation.

## Open taskset, 2026-09-18 ~19:55 — self-audited against everything the owner raised this session

Written because the owner asked directly what's been raised and only partially, narrowly, or not
handled — audited honestly rather than assumed closed. Tracked here so none of it quietly drops.

| # | item | status |
|---|---|---|
| T1 | **The download+patch "entangled push" audit**: some algorithm code is gitignored (`runnable/*/`), reconstructed at bootstrap from a third-party clone + `runnable/_patches/*.patch`, never committed itself. Owner asked whether this is truly recoverable long-term, deeply, reconstructing from repo data if needed. | **CLOSED — a real, already-flagged, still-open risk, confirmed with hard evidence, not fixed.** All 7 pinned upstream URLs read from `setup/source-reconstruction.json`: **5 of 7 are on individual researchers' personal GitHub accounts** (`gemcollector`, `SumeetBatra`, `rraileanu`, `bmazoure`), not institutional orgs. The manifest DOES hash-verify a fresh clone twice (`tree` = the pinned commit's own git tree hash; `expected_tree_hash` = the tree after the patch applies) plus `patch_sha256` — this catches a *wrong* reconstruction (corrupted clone, mismatched patch) reliably. **It does nothing if the clone itself becomes impossible** — repo deleted, made private, or renamed. No local mirror or archived copy of any of the 7 repos exists anywhere in this project; `.gitignore`'s own comment states the reason plainly ("~200MB each... reproducible from ext/ plus the patch") — a deliberate space-vs-durability tradeoff, not an oversight. Confirmed this was already surfaced: an external reviewer (`notes/ai-review-19-external.md`, item 19) explicitly recommended a `source_archive_sha256` — a hash of an actual archived copy — specifically *because* "years later GitHub branches can move, disappear or become archived." Every other item on that reviewer's checklist (tree hashes, patch hash, container digest, dependency-lock hash, resolved argv) was implemented, cross-checked directly against `source-reconstruction.json` and `source-lock.json`. **The one item that would close the unavailability risk — the actual archive — was not.** Not fixed here: archiving ~1.4 GB of third-party repos into durable storage reverses an existing, reasoned decision and costs real disk/repo size, which is the owner's call, not mine to make unilaterally. |
| T2 | Disk-floor softening guidance for a single long run tracking close to its own predicted need — confirmed tunable (`NATIVE_DISK_ALLOWANCE_GIB`, uncapped), confirmed no doc walks an operator through it. | **OPEN** — gap identified, not written up. |
| T3 | Auto-stop visibility at cold start ("very very obvious and explicit") — agreed not currently met; stop mechanisms scattered across §6b/§5.1/per-family sections. | **OPEN** — same gap as T2 from a different angle. |
| T4 | Whether "delete one of tar/untarred if we have both" was ever acted on. | **Checked, closed with an honest limit.** Scanned the host (`$HOME`, depth 3) for any `.tgz`/`.tar.gz` sitting beside its own extracted directory — none found now. Cannot rule out a differently-named case (e.g. an archive whose stem doesn't match its nested extracted path, which this exact-name check would miss); nothing obvious remains to act on. |
| T5 | Whether the `anthropic-prompting.md` feedback pass actually completed or was only acknowledged. | **Checked, closed with an honest limit.** The file (`~/build-projs/ccm-intro/docs/anthropic-prompting.md`, a different repo than this one — git log here can't see it) has an mtime of 16 Aug, before this session's campaign work began. Consistent with "reviewed, no changes needed" but not proof of it; mtime alone can't distinguish that from "never touched." |
| T6 | Does anything unify the *operational* model of a run (`production-host/`) with its *scientific-fidelity* model (`FAITHFULNESS.md`/`CONSTRUCTION.md`) into one formal picture of "the run"? | **CLOSED — confirmed a real seam.** `RESEARCH-FRAME.md` explicitly scopes itself to the scientific-design question only; `CONSTRUCTION.md`/`FAITHFULNESS.md`/`RESEARCH-FRAME.md` never reference `production-host` anywhere. The link runs one way only: 3 `production-host` notes (07, 22, 24) cite fidelity concerns when a host decision has a scientific consequence; nothing crosses back. Where a genuinely cross-cutting case (ctrl's RNG-isolation gap — a runtime mechanism with a fidelity consequence) actually lives: a standalone root-level `notes/FINDING-*.md` file, in neither surface family's own numbering. No doc claims or attempts the unification; not fixed, since the owner asked whether this is true rather than for it to be built. |

Items already closed this session (ppg cadence, the 96s retraction, "offline eval is manual" being
wrong, the config-hierarchy trace, the disk cleanup) are in C9 above, not repeated here.

## C10 — closing what was closeable: T2/T3 written, T1 checked live, monitor cadence tuned

The owner asked to continue on the open items' own line, in full, rather than leave documented
gaps as documentation. Three concrete actions:

- **T2/T3 closed for real**: added §6b.1 to `OPERATOR-GUIDE.md` — every auto-stop mechanism from
  §6b's table, with its env var, default, how to loosen it, whether it can be disabled, and the
  real cost of disabling it, in one place, positioned to be read before launching rather than
  discovered after a stop. Includes `self-vram-cap.sh`'s honest status: not arming it changes
  nothing measurable today, since it can't see EGL memory and its cap never reaches a trainer
  anyway (§6b's own existing findings). One thing named as still irreducibly a judgement call, not
  a table lookup: *how much* disk headroom is safe to give up for a specific long run, on this
  specific host, today — that depends on the shared filesystem's live state at decision time, which
  no static document can print. Verified: `test_operator_readiness.py` 8/8.
- **T1 given a live check, not left purely theoretical**: queried the GitHub API for all 7 pinned
  upstream commits (`setup/source-reconstruction.json`) — **all 7 return HTTP 200 today.** The
  long-term risk (5 of 7 on personal accounts, no local mirror, confirmed real in C9) is unchanged;
  what's added is the current fact that it has not materialized yet. Read-only check, no clone, no
  write — appropriate for a risk assessment, not a fix, and the fix (vendoring ~1.4 GB) remains the
  owner's call for the same reason stated in C9.
- **Monitor cadence**: the owner asked whether the recurring "nothing happened" capacity beats
  could be less frequent. Checked `watch-capacity.sh` first rather than just widening the Monitor
  tool's own re-arm interval: the periodic `HOST ...` heartbeat line was gated on a hardcoded `15`
  (minutes), while every real event (`CAPACITY`/`OPENING`/`NEW-GROUP`/`LOGGER`) fires immediately on
  its own trigger, completely unaffected by that counter. Made it `HEARTBEAT_MIN`, an env var
  (default 15, so any other caller of this script is unaffected), so this session's own monitor can
  widen it without losing any real detection.

**Honest final position, since the owner asked directly whether any concerns remain**: no — not
"none remain." What changed is that every item that could be closed by more of my own work *is*
closed now (T1 checked, T2/T3 written, cadence tuned). What remains open, irreducibly, is not
fixable by more documentation or more code from this side: the `svea` configuration has still never
fired for real (external — needs a card window); the competence-gate finding is the actual
scientific result, not a defect; the three owner decisions in `CURRENT-STATE-AND-RESPONSIBILITY.md`
§7b are genuinely the owner's to make; and T1's real fix (an archived mirror) is a resource/policy
decision, not a technical one I can complete alone. Calling any of those "closed" would be the
exact kind of overclaim this session's own corrections (the 96s number, ppg's cadence, twice) exist
as evidence against.

## C11 — `svea`'s waiter GAVE UP: W1 is now closed as "never got a window," not "still pending"

21:18:49, the Monitor caught it live: `GAVE UP after 36000s without a window` — the waiter's own
10-hour `MAXWAIT`, armed this morning, exhausted with the card occupied for its entire span.
Confirmed directly on the host, not just from the log line: `pgrep -af "wait-and-train-v4.sh"`
finds no process. **Not a launch failure** — no cell ever started, so there is nothing for
`results/host-runs.jsonl` or the attempt ledger to record.

Every place that had been saying "armed, watching" is now wrong and was corrected: `HANDOFF.md`'s
top block (rewritten as an evening state), and a genuinely stale line in
`CURRENT-STATE-AND-RESPONSIBILITY.md` ("svea/sgqn/soda blocked on Places365," which stopped being
true on the 18th when the corpus landed — fixed with the doc's own established strikethrough
convention, since it hadn't been updated when Places365 resolved). The now-pointless log-tail
Monitor (nothing further will ever appear in a dead waiter's log) was stopped; the capacity Monitor
stays armed.

**Per the standing rule, nothing new has been armed.** The card is still occupied by the same three
groups it has been all session. This is now, honestly, a fully idle state on our side: no waiter,
no cell, no pending launch — watching only, until the owner says what to arm next.

## C12 — actually working the remaining list, called out directly for having stopped after C11

The owner asked plainly whether I'd followed up on the standing-concerns list or just held watch —
correctly: I had only held watch since C11. Two items from that list were genuinely actionable
without a card (neither launches anything), so I did them:

- **O2, fully closed.** Discovered the host already had `payload-v215-rlvigen.tgz` and
  `payload-v215-dmc_gb.tgz` from that morning (06:48) — verified both against the *current*
  committed tree (a fresh `git archive HEAD`, not the host's own checkout) with
  `contract.py verify-payload --require-evaluator-identity --require-runner-contract 19`: rc=0
  both, no rebuild needed. Built, verified (`verify-payload` + `verify-evaluator-binding`, all
  rc=0) and shipped `payload-v215-alda.tgz` and `payload-v215-ctrl.tgz`, the two that were missing.
  All four families' payloads now sit on the host at v215, each checked against today's actual
  commit, not assumed. Own scratch directories on host removed by exact name through a container
  (files were root-owned).
- **O9, root-caused precisely rather than left as "not attempted."** Actually ran `build-env.sh`
  for `svea:101` against `payload-v215-rlvigen.tgz`. It refused: `already built:
  torch-02805cc0-94c1577b2cd9`. Checked why: the script's cache key is
  `${stack}-${reqhash}-${digest}`, and `reqhash` reflects only the resolved package list, never
  whether the payload carried `RL-ViGen-upstream/`. A directory at that exact hash already existed
  — built 2026-09-08 for `idaac`, confirmed via its own `ENVIRONMENT.json` (`"editable": []`) — so
  the script reported success without ever comparing contents. **This is a real, previously
  undiagnosed gap in the build script itself**, not an unattempted task. The actual fix (delete
  that directory, rebuild at the same hash from a payload that carries the upstream tree) is a
  one-command operation once decided — not done here, because that directory is host state from
  10 days before this session, and deleting it crosses the same line every other "don't touch what
  you didn't create" decision in this file has drawn. `OPERATOR-GUIDE.md` O9 rewritten to state the
  real mechanism instead of the old, now-known-imprecise "not executed."

Verified: `test_operator_readiness.py` 8/8 after the O9 rewrite.

## C13 — a real launch, and O9's "one-command fix" (C12) was itself wrong

**Full detail in `HANDOFF.md`'s top block (2026-09-19 ~20:33) — this is a pointer, not a
duplicate**, since the handoff already carries the verified/uncommitted/plan distinctions in full.

- Card 1 went genuinely clear; the owner returned and authorized launching directly. `svea` s101
  is now running (`card1-20260919-203001`, container `cell-c1-1241086`). Still in bootstrap as of
  this entry — no W1 checkpoint past "container up" is confirmed yet. Post-launch recording
  (`record_host_run.py`, `production_run_register.py`, `audit_attempt_ledger.py --strict`,
  `watch-cell.sh`) is **not done yet** — time-sensitive, see the handoff.
- **C12's "delete and rebuild is a one-command fix" was wrong.** Rebuilding from a payload
  "believed to carry `RL-ViGen-upstream/`" reproduced the identical failure, because no payload
  ever carries it (`run_probe.sh:1788-1789` already said so). The real fix needed `build-env.sh` to
  clone and patch the tree itself — implemented, committed (`d25905b`), verified for real on the
  host (`"editable": ["robosuite", "robosuitevgb"]`, confirmed logically via the script's own
  `set -e` ordering that the patch check passed before the successful installs could run).
- Two files (`CURRENT-STATE-AND-RESPONSIBILITY.md`, `OPERATOR-GUIDE.md`) are written but
  **uncommitted** right now — real content, not yet re-verified against the test suite. Six local
  commits are unpushed. Neither is a "problem," both are simply not finished — named here so they
  aren't silently assumed done.

## Open taskset, 2026-09-19 21:15 MSK — supersedes the 2026-09-18 list above as the working list

An item is closed only by what its last column names. A narrower step being done is written in the
status, never as DONE. Order of work: E1 → E2/E3 (as inventories return) → E4 → E5 → E6; F runs in
parallel on the host's clock; G items are picked up inside E5/E6 or last.

**[ENDED 2026-09-20 01:01 MSK — history. All three stopped executors resumed with their context intact, including the two killed mid-turn. Occupancy logger restarted 01:03 MSK for 40 h; the host's copy of `gpu-occupancy-log.sh` hashes `b1bc775…` against the laptop's `e25fd3e…` — it runs and writes; the difference is not yet examined.]** QUOTA HOLD, owner's instruction 2026-09-19 21:53 MSK. The owner's AI quota was ~82%; its 5-hour
window resets at 01:00 MSK on 20 Sep. I cannot see the quota. Plan: no new work until the reset;
wake about every 55 minutes only to keep caches warm (mine, and a one-word ping to each persistent
executor); the single exception is the host coming back, which gets the short F1 forensics because
it concerns the running cell. Stopped for the hold, to RESUME AFTER 01:00 with the brief it already
has: the budget-research executor (the code executor; it had only confirmed `pdftotext` exists).
Left to finish: the hands executor (extending `notes/model/HARNESS-MODEL.md`, uncommitted, the lead
reviews the diff) and the docs executor (mapping `open_decisions.py` against CURRENT-STATE §7b).
**Owed to the owner after the reset, in this order:** (8) a queue-order proposal, natives first or
not; (9) budget vs scope "handled in full", starting from the earlier agent research on budgets
that the owner remembers and the repository should hold; (10) best proposals with context for
P-C76 and the other nine owner gates, stopped-cell continuation, LICENSE/CI, and the value of
`ctrl`'s lowered floor. The owner decides; the proposals are mine to make.

**E. Understand first, then restructure** (owner, 2026-09-19: step back, take the whole frame, do not
dive implementation-first; note understanding once instead of re-deriving it each session)

| id | item | status | what closes it |
|---|---|---|---|
| E1 | ~~Sweep of EVERYTHING the owner said this session against the primary docs~~ **Re-scoped by the owner 2026-09-19 (recorded 21:46 MSK): they meant the last ~day's discussion — the issues both of us raised at production start-up, the scripts, the operator package, and my owner-facing decision list — NOT a canon of everything they ever said; their statements are stage-bound and may have changed.** The four-day sweep below stays as an executor report; it is not a to-do list, and its rows are not to be promoted into rules. Remaining work is only the recent-day scope | PARTIAL — only §7b items 1–9 and the external/blocked ruling checked and recorded (`f2d3757`). The owner's original numbered list (up to ~19–20), the eval-cost ×3/×2 question and the replay-buffer question were answered in chat and never swept **Sweep RETURNED (stored 21:37 MSK)**, stored in `notes/inventory-2026-09-19/owner-statement-sweep.md`: 83 durable statements — 32 CARRIED, 24 PARTIAL, 34 NOT FOUND, 3 contradictions. Done so far: two rulings the owner stated as standing (the `ppg` rollout quantum; the upper edge of autonomy) went into CURRENT-STATE §4 as items 7–8, and four dated remarks into a separate "context, NOT constraints" block under it — restructured after the owner pointed out that their statements are stage-bound. **NOT yet triaged: the other ~28 NOT FOUND and all 24 PARTIAL rows.** Many are work-style rules that live only in Claude Code auto-memory (invisible to the executor and to every other agent) and belong in the project `CLAUDE.md` under E6; several are owner QUESTIONS answered only in chat (swap/thrashing, eval taking ~2× training, automatic vs manual eval being the same code) whose answers need a home or a pointer | every owner statement in the session transcript listed with the file:line that carries it, or added |
| E2 | Code liveness inventory | RETURNED, 5 claims re-checked, stored in `notes/inventory-2026-09-19/code.md` | the claims the restructure relies on re-checked one by one at the time they are used |
| E3 | Docs surface inventory | RETURNED (stored 21:20 MSK) in `notes/inventory-2026-09-19/docs.md`. Probes passed; its production-host orphan count was an artifact of my brief and is corrected in the file's header. Headline: 11 files claim to be an entry point; 8 overlap groups, among them 4 current-state/handoff surfaces, 3 operator-procedure docs, 4 owner-decision ledgers, 7 handoffs | returned, known-answer probes checked, "not checked" list read, stored beside E2 |
| E4 | My own reading of the core, not delegated | PARTIAL — `RESEARCH-FRAME.md`, the launch chain to the `docker run`, `production-host/36`, the schedule. Read 2026-09-19: `SYSTEM.md` §1–§Auditing — **the project already has a document system** (layers Standard / Log / Reference / Measurement / Assurance / Working; triggers; section scope tags; "cite a measurement, do not restate it"; working state carries a scope and expires). The production-stage files under `notes/` grew outside it: its layer table names none of them and it was last touched 2026-09-06. So E6 is *bringing `notes/` into that system*, not designing a new one. Not yet: `family.py` argument resolution, the eval → records → `production_reading.py` path, the rest of `EVAL-PROTOCOL.md`, `SYSTEM.md` from "Four kinds of divergence" on | each read, and what it changes written into E5's map |
| E5 | One structure map, rewritten in place, every statement tagged executed / read-in-code / doc-claims-only. Must carry what was found 2026-09-19 and lives nowhere else: two code sources (host checkout before `docker run`, payload after), the env allowlist at `run_on_production_host.sh:811-831`, `wait-and-train-v4.sh` defaulting to the **v5** wrapper, the double defaults (`SEED`, `FRAMES`, `EVAL_EVERY_FRAMES`, `NATIVE_EXPECT_OURS`), `RESUME_SNAPSHOT` never reaching the container | **DONE 2026-09-20 01:03 MSK, with a process error of mine stated.** The hands executor extended `notes/model/HARNESS-MODEL.md` with §0 (the chain before the container, the v5/v6 name mapping, two code sources, the env allow-list, the dry run's reach), §1b (seven-layer value precedence, `NATIVE_EXTRA_OVERRIDES`, the double defaults), host RAM as the unbounded resource in §5, and two more entries in §7; `tests/test_citation_content.py` exit 0. **The error:** I had said I would keep its in-progress file out of my commits, then used `git add -A notes` twice, so its unreviewed edits were committed and pushed inside `9f61b64` and `b4ef567` under unrelated messages. Reviewed after the fact instead: §0 read in full against my own trace, four citations spot-checked, all hold. It also corrected the code inventory — `RESUME_SNAPSHOT` IS set in three `cfg-drqv2-resume-*.yaml`; the gap is only in the host chain's allow-list. From here: `git add` names explicit paths while any executor may be editing. Earlier status, kept: NOT STARTED — waits on E2–E4 by design. **Found 2026-09-19 (recorded 21:37 MSK): a file-anchored map already exists** — `notes/model/HARNESS-MODEL.md` (124 lines, written 2026-09-16 from a code trace, includes the env allow-list) and `notes/model/STOP-MECHANISMS.md` (220 lines). The docs inventory skipped `notes/` subfolders, so neither of us saw it. E5 is therefore *read, re-verify and extend those two files*, not write a new map | the map exists at a location chosen per `docs/SYSTEM.md`, and `OPERATOR-GUIDE.md` §5's stale v3/v5 diagram is corrected against it |
| E6 | Doc roles settled: which file is state, which is reference, which are frozen snapshots; standing working rules (arrangement, executor-trust requirements, recording the owner's words) into the project `CLAUDE.md` — today they sit only in Claude Code auto-memory, which no other agent reads | PARTIAL. Done 2026-09-19: the owner's working rules (eight, verbatim, from the E1 sweep) and the executor arrangement are in the project `CLAUDE.md` under "How the owner wants this project worked". Done 2026-09-20: the `notes/` production-stage files are placed in `docs/SYSTEM.md`'s layers (the roles were already coherent in `OPERATOR-GUIDE.md`'s header — the sprawl was two labelling defects: the procedure's banner called itself "the operator's guide", and the map never routed to `notes/model/`, which is how the harness map was nearly duplicated; both fixed); `HANDOFF.md` no longer takes routine state. **The owner-decision lists are now ONE list (2026-09-20):** A59–A72 filed in `DECISION-SHEET.md` (55 → 69 items in `open_decisions.py`), §7b links each of its items to its A-number and keeps its full text. Drafted by the docs executor; all 16 owner quotes checked verbatim by the lead, who corrected three items before filing (the `ibac_sni` probe is approved-and-deferred, not dropped; no leading estimand is fixed; one taskset line had been presented as the owner's words). Input found 2026-09-19: owner decisions live in TWO unreconciled lists — what `open_decisions.py` gathers (register, DECISION-SHEET A-items, gates) and the hand-built CURRENT-STATE §7b. One must become a view of the other | roles written in one place; `HANDOFF.md`/this file stop growing by append or the reason they still do is stated |

**F. The campaign**

*2026-09-20 01:23 MSK:* **F5 — `idaac` s103 (`card1-20260920-011652`) RUNNING, recorded, watched.** Closes as F1 would have: collected; provenance audit MISMATCHED 0; status updated; strict audit exit 0. **F6 — proposals for the owner's items 8, 9, 10 were given in chat on 2026-09-20 ~01:25** (natives first with `drqv2`/`curl`/`drq`, Places365 baselines held on G10; keep 600k — it is RL-ViGen's published Door budget — plus one bounded `ibac_sni` 10× probe; ratify P-C76 as run; rerun-from-zero; MIT + third-party notice after a licence check; `ctrl` on an exclusive card with a `MEM_FRACTION` smoke before any floor waiver). **The owner has NOT answered yet; nothing in F6 is decided.** When they rule, write each ruling into the sources `open_decisions.py` reads (mapping: `notes/inventory-2026-09-19/decision-list-mapping.md`), not only into §7b.

| id | item | status | what closes it |
|---|---|---|---|
| F1 | `svea` s101 (`card1-20260919-204235`) | **FAILED, recorded 22:08 MSK. Forensics done: the host crashed uncleanly ~21:25 and rebooted 22:05 (no `shutdown` in `last -x`; all tenants lost); NOT caused by us (~8.6 GiB RAM, 2.8 GiB VRAM at the last sample). New finding: the cell trained at ~2.4 FPS with GPU util 0 — it would have been reaped at ~100–180k frames; suspect `RLVIGEN_PLACES_WORKERS=0`. Open: prove the throughput cause before any Places365 relaunch; restart the occupancy logger (dead since the crash); the "first measured RAM of a native cell" is only a 35-minute sample, not a full-replay figure.** Earlier status, kept: RUNNING, recorded. **Unwatched from the laptop since 21:33 MSK 19 Sep**: the host stopped answering ssh and ping over the VPN route (`utun100`) while the internet stayed up; `watch-cell.sh` tripped on "host unreachable on 3 consecutive polls", correctly. The cell is detached and its floor/disk/yield watchers run on the host, so it is not affected — but whether it is still alive is UNKNOWN until the host answers. NetBird on the laptop is healthy (management and signal connected); the `cds2` peer shows "Connecting", no ICE candidates, no handshake — the host's agent is not answering. The owner asked whether WE downed it. Not excluded: RAM is the one resource no watcher of ours bounds, and a native cell's RAM was never measured here; against it, at last sight (21:05–21:17) the host had 73 GiB available and our cell was ~40 minutes old with a near-empty replay buffer. **Forensics to run FIRST on reconnect, before anything else:** `uptime` and `who -b` (did it reboot, when); `docker inspect cell-c1-1272142 --format '{{.State.Status}} {{.State.OOMKilled}} {{.State.ExitCode}}'` if the container still exists; the RSS samples in `native-out/cells/svea-s101/resources.json`; the last timestamp in `~/rlvigen-runs/gpu-occupancy.log` and whether there is a gap (host down vs network down); `free -g` and swap use. Write the answer into CURRENT-STATE §2 whichever way it falls. Then: check the cell, then re-arm `watch-cell.sh trip` (RUN/LOG/CELL as before, FLOOR=55) and the capacity monitor | collected; `audit_record_frame_provenance.py` MISMATCHED 0; status updated; strict ledger audit exit 0; **measured RAM and wall time of a native cell extracted** into OPERATOR-GUIDE §4c.1 |
| F2 | Queue order: the RL-ViGen five first? They are the only identified across-method contrast (`RESEARCH-FRAME.md`) and had zero production cells | TO BRING TO THE OWNER with measured cost per native cell (needs F1's numbers) | owner's answer recorded in CURRENT-STATE §7b |
| F3 | Is P-C76 (what retention is measured over) ratified? | **ANSWERED 2026-09-19: no.** `EVAL-PROTOCOL.md:5` is still "PROPOSED. Nothing here is settled"; production runs on its operational default (ten scenes, all twelve). Not lost: `open_decisions.py` lists it (C76, A4) and `production_gates.py` carries "estimands frozen: P-C76 open" | closed as a question; the decision itself stays the owner's |
| F4 | Budget vs scope (§7b item 1) | OWNER'S | — |

**G. Carried loose ends — none urgent, none to be lost**

| id | item | status |
|---|---|---|
| G1 | O9: does the one prebuilt env's requirement hash hold for `dmc_gb`, `alda`, `ppg`, `ibac_sni`? | **CLOSED 2026-09-19**: eleven baselines hash `10d2004a` (also `idaac`), `ctrl` `2466d111`; executor ran all 12, lead re-ran 4. Recorded in CURRENT-STATE §7b item 8 |
| G9 | **Found 2026-09-19 (recorded 21:51 MSK) while reading HANDOFF: the prebuilt-env hash is machine-dependent.** Same requirement lines → `10d2004a` (en_US sort), `e26959bf` (`LC_ALL=C`), and the host's directory says `02805cc0` (older `family.py` in the host checkout, 43 lines different, and/or GNU vs BSD collation). `run_probe.sh:1552-1558` recomputes in-container and refuses on mismatch. Latent: the production wrappers never pass `NATIVE_VENV_HOST`, so no production cell uses the prebuilt env | **OPEN** — needs the host: compare the in-container hash with `ENVIRONMENT.json`. Candidate fix (not made): `LC_ALL=C sort` on both sides, then rebuild the env once. G1's "CLOSED" stands only for "same requirement set" |
| G10 | **The Places365 baselines' scheduled throughput is from a banned loader configuration** (found 2026-09-20 01:05 MSK; detail in CURRENT-STATE §2). `svea`/`sgqn`/`soda` were timed with 8 overlay workers before 2026-09-04; the default has been 0 since 2026-09-08 for heap corruption; at 0 workers the one sample is ~2.4 FPS for `svea` (schedule: 9.99). And the wrappers' default `TIMEOUT_S` (12 h) is below the schedule's own training time for SEVEN baselines — `soda` 51.3 h, `rad` 27.1, `sgqn` 25.6, `alda` 19.1, `svea` 16.7, `drq` 13.4, `curl` 12.7 (I first wrote six and omitted `alda`; the hands executor caught it against the JSON). **Timeout half FIXED 2026-09-20 on the laptop:** both wrappers refuse a baseline other than `idaac`/`ppg`/`ibac_sni` when `TIMEOUT_S` is unset, warn when it is below the scheduled time, and a drift test ties their embedded table to `production-schedule.json`; 11 red-green tests. **Host swap PENDING with G11's**: v5 is executing for `idaac` s103 | **OPEN** — needs: a real throughput measurement at 0 workers on this host (warm cache, idle host), or a safe worker count established; per-baseline `TIMEOUT_S` derived from the schedule in the wrapper or the guide; the schedule's three rows re-labelled. No Places365 cell is to be launched before the first two |
| G13 | **Full-suite checkpoint, 2026-09-20 02:27 MSK:** 3 FAILED, 0 ERROR — both my own regressions. (a) `test_places365_checks_the_split_it_consumes.py` ×3: my `6458c05` set the Places365 skip flag above the marker where that test lifts the shipped block; fixed by reading `${places365_skip_asset_check:-0}`. (b) the `resolved register holds` gate: my three added lines in `EVAL-PROTOCOL.md` moved the `A20 decided` anchor from :490 to :492; anchor updated, markdown regenerated. After the fixes: the affected files pass, gates **37 pass / 0 fail / 9 owner**. `payload-v216-rlvigen.tgz` on the host predates (a); harmless in production (the flag is always set there), to be rebuilt with the next payload | Mount-path test ADDED and mutation-checked by the lead (with the skip flag forced to 0, exactly `test_a_preverified_mount_skips_check_asset_with_no_expected_vars_set` fails; 8/8 pass on the real script). **OPEN only for:** a fresh full-suite run at the next checkpoint |
| G12 | **PREPARED, NOT RUN (01:53 MSK 20 Sep): the Places365 loader-worker experiment that unblocks `svea`/`sgqn`/`soda`.** Hypothesis, unproven: the heap corruption that banned overlay-loader workers on 2026-09-08 (`malloc_consolidate(): unaligned fastbin chunk detected`, DataSphere) came from Docker's 64 MB `/dev/shm`; `--shm-size 2g` landed two days later (`8d735a4`) and workers > 0 were never retried. Design: short non-production cells by the documented pattern (`RUNNING-ON-PRODUCTION-HOST.md` §3.0) — `CARD=1 CELLS=svea:<seed> FRAMES=10000 CELL_TIMEOUT_SECONDS=3600 NATIVE_HOST_PROFILE=v100 NATIVE_PLACES365_DIR_HOST=~/rlvigen-assets/places365-train NATIVE_PLACES365_SPLIT=train NATIVE_DISK_ALLOWANCE_GIB=<free−65> RLVIGEN_PLACES_WORKERS=<w> nohup bash datasphere/native/launch-card-cell.sh ~/rlvigen-work/payload-v216-rlvigen.tgz <result> ~/rlvigen-assets/rlvigen-door2-90d8b8c4.tgz`, after `NATIVE_HOST_DRY_RUN=1`. Arms: `w=0` once (the reference FPS on this host with a warm file cache — last night's 2.4 FPS was one cold 35-minute sample), then `w=4` three times, because the recorded failure was INTERMITTENT and one clean run proves nothing (the comment above `run_probe.sh:2206` says so itself). Read: FPS from `train.log`; any `malloc`/`corrupted`/non-zero `CELL EXIT`; GPU util. Accept workers > 0 only if all three runs are clean AND the FPS gain is real; otherwise the three baselines cost ~69 h of training per seed and that goes to the owner as a scope fact. Needs ~2–3 h of card 1 | **WAITS for card 1** (after `idaac` s103, ~20 h) and is small enough not to need the owner — but a production Places365 launch afterwards does wait on their queue-order ruling |
| G11 | **`wait-and-train-v4.sh` counts occupancy samples across a logger gap** (found 2026-09-20 01:06 MSK by a `DRYRUN=1`): three minutes after the logger was restarted it reported "streak 10/10", built from pre-crash lines of 21:16–21:25 plus three fresh ones. It checks only the age of the LAST line (`LOG_MAX_AGE`), not that the HOLD samples are contiguous. Harmless that time (both cards had been empty for three hours by `nvidia-smi`), wrong in general: after any logger outage the ten-minute rule silently becomes a one-sample rule | **FIXED and committed 2026-09-20 01:42 MSK; host swap PENDING.** Validated against ground truth on the host's real log: replaying 01:05 (three minutes after the logger restart) the old script says `10/10 … LAUNCHABLE`, the fixed one `5/10 … wait` with a `streak reset` line; replaying 01:14 (twelve genuine samples) the fixed one still says LAUNCHABLE. Default gap is a fixed 180 s (three logger intervals) — my brief's `POLL*3` was wrong, POLL is not the log cadence. Unparsable timestamps reset the streak, loudly. **The fixed script sits on the host as `~/rlvigen-work/wait-and-train-v4.gapfix-pending.sh`; the live `wait-and-train-v4.sh` (`5f5b38c`) was NOT overwritten because the waiter is still running for `idaac` s103. Swap it in after that cell ends: keep the old copy, check nothing matches `pgrep -f '[w]ait-and-train'`, move the pending file over.** History: the hands executor added `MAX_SAMPLE_GAP` (default 3×POLL) with a red-green test reproducing the 7+3 case; reviewed by the lead (`say` is file-only so safe inside the captured function; GNU `date -d` parses the real log format on the host, checked). Sent back once: an unparsable timestamp skipped the check silently (fail-open) — must reset the streak and say so. Uncommitted, NOT deployed; the host still runs `5f5b38c`. Original plan: require the HOLD samples to span no more than ~HOLD×POLL×1.5 seconds, with a red-green test on a log with a gap. Until then: after a logger restart, do not arm the waiter for ten minutes. Host runs v4 at `5f5b38c` and v5 at `c2d99a2`, each one commit behind the laptop; both differences checked (opt-in retry, default off; comment-only) |
| G2 | `EVAL-PROTOCOL.md` says nine off-policy baselines; a direct count gives eight | **CLOSED 2026-09-19**: eight, from replay-buffer presence in code; `EVAL-PROTOCOL.md:401` corrected with the reason. Left open, smaller: `docs/REGISTER.md:178` (2026-09-02, append-only log) says "seven" — a log row is not rewritten; unexplained |
| G3 | `ext/` copies of six upstream repos have no `.git`; never diffed against the pinned commits, so the "local backup" of §7b item 4 is unverified; `ext/rl_vigen` is not a copy at all | **CLOSED for six of seven 2026-09-19** (tree hashes equal the pins; `ext/` differs only by our patch). For RL-ViGen no locally verifiable copy at the pinned commit exists — **accepted by the owner 2026-09-19** (deletion unlikely, local copy held, a reproduction should not vendor others' work); CLOSED, recorded in CURRENT-STATE §7b item 4 |
| G4 | Host checkout's `run_on_production_host.sh` is one commit behind the laptop (`8d735a4` vs `1178978`); the diff is comment-only, checked | NOTED, no action |
| G5 | Attempt 1 of `svea` s101 (`card1-20260919-203001`) has no ledger row of its own: it died before writing a config and the recorder refuses such a run. Its failure is in attempt 2's note | NOTED |
| G6 | Two empty, untracked, oddly named directories in the project root (a space-only name; a python one-liner as a name), dated 7–8 Sep | NOTED, left alone |
| G7 | `ppg` seed 1 operator note | LAST, per owner |
| G8 | Commits since the last push | see `git rev-list` before each push |

## Open taskset, 2026-09-20 09:41 MSK — what the owner's rulings of that night leave owed

The 2026-09-19 taskset above stays the record of E/F/G. These are new, from the rulings recorded in
CURRENT-STATE §7b the same hour. Working values are MINE to set and tune; the owner ratifies finals.

| id | item | status | what closes it |
|---|---|---|---|
| H1 | **Evaluation cost, head-on.** Why the grid costs ~2× training (3,476 episodes at ~11.65 s, sequential, after training — `notes/model/HARNESS-MODEL.md` §4); which of its factors are scientifically required (episodes per cell for a stated SE; ten scenes; four regimes; two policy-mode passes; 13 curve stamps) and which are inherited defaults; what cuts wall time WITHOUT touching an estimand (evaluating in parallel on a card that sits 90% empty during the grid; evaluating curve stamps while training continues); `ctrl`'s in-loop test envs as the same question inside one algorithm | **ANALYSED 2026-09-20 09:59 MSK** (`notes/inventory-2026-09-19/eval-cost-and-timeout-trace.md`, two load-bearing claims re-checked in code; `HARNESS-MODEL.md` §3–§4 corrected). Finding: every grid factor has a stated reason; the cost is SERIAL execution — ~2,400–3,200 episodes × ~12.5 s in one process on one of 16 cores, GPU near idle. The pooled row is free; rows reseed absolutely, so they are order-independent. `ctrl`'s in-loop test envs feed logging only and have no off switch — left as upstream wrote them. **Working decision (mine): parallelise evaluation, splitting by REGIME (4 processes, each all ten scenes, so pooled rows stay intact) and running stamps side by side, bounded by a worker count; nothing in the grid is dropped.** Gate before adoption: on a real retained checkpoint, the parallel rows must equal the sequential rows — bit-identical for the nine mode baselines, and identical or explained for the three sampling ones | implemented outside the evaluator closure (orchestration only, `eval_grid.py` untouched), validated row-for-row on the host against an existing cell's rows, then to the owner with before/after hours |
| H2 | **Data-richness audit.** What a finished cell retains, per episode and per training step: are returns/successes stored per EPISODE (not only means), per scene, regime, stamp, policy mode; are dense training metrics (tensorboard, train.csv, per-update losses) collected off the host; are all checkpoints kept. Anything only available as an aggregate is a finding | **AUDITED 2026-09-20** (`notes/inventory-2026-09-19/data-richness-audit.md`): evaluation rows DO keep per-episode lists with 14+ diagnostic fields, so distributional statistics are recomputable; NOT kept: per-step traces, per-episode wall time, host resource time series (`resources.json` never fetched, summariser broken), apt versions, the git commit; `ppg` has 0 dense training rows in its valid closure; **two completed cells' checkpoints were host-only — being fetched to `fetched/`**. Fixes outside the frozen evaluator closure are with the hands executor (apt versions, commit in the payload, manifest row counts, `phase` mislabel, summariser import, a checkpoint-fetching collection step). Per-episode wall time lives inside `eval_grid.py`, i.e. inside the closure: not changed mid-campaign | the executor's fixes reviewed and committed; natives' dense metrics checked on `drqv2` s101; the closure-bound gaps stated in EVAL-PROTOCOL as known limits |
| H3 | **The training timeout.** `run_probe.sh:401-402` wraps training in `timeout --foreground ${CELL_TIMEOUT_SECONDS}s` — a hard wall-clock cut with no notice; the same file's comment says such a bound must be sized for the longest legitimate run ("45 hours at production scale") and that HANGS are the stall watchdog's job (log silence > `CELL_STALL_SECONDS`, default 1800 s, progress-aware). The wrappers' 43,200 s default follows from nothing. Since 2026-09-20 the wrappers refuse slow baselines without an explicit value, which removes the silent cut but not the design question | **TRACED 2026-09-20** (same report, Part 2; not re-checked by the lead yet): `timeout --foreground` makes the cell exit 124 with NO marker of its own — a timed-out cell is indistinguishable in the log from any other failure; the stall watchdog (log silence > 1800 s) guards TRAINING only, not evaluation; the host-side reaper is progress-aware but acts only after the whole watch budget is spent; nothing anywhere projects finish-vs-limit although the training log carries frames and elapsed time. **Working design (mine):** the ceiling becomes a generous backstop derived from the schedule (≥ 3× scheduled training, never the bare 12 h), hangs stay the watchdog's job and the watchdog is extended to evaluation, a timeout gets its own marker, and the laptop-side `watch-cell.sh` heartbeat prints projected finish against the ceiling so a slow cell is seen in minutes (the 2.4 FPS `svea` cell would have been flagged in its first heartbeat) | implemented with tests; the closure-membership of `run_probe.sh` checked first |
| H4 | Answers owed to the owner's five questions (anchor, Lift, estimands, recorded apt/pip versions, licence) | given in chat the same hour; the apt/pip one needs a check of a real run's manifest | each answer's home in the docs, where it has one |
| H5 | **Standing host rules for another agent of the owner's** using cds2-class machines: a project-independent rules folder. The owner has a local 'host rules' folder I could not find by name or content | BLOCKED on its path; meanwhile distil one from `notes/production-host/` + the project `CLAUDE.md` for the owner to compare | reviewed, not attested unread |
| H6 | First native cell: `drqv2` s101 on card 0 (booked for our group), by hand via the v6 wrapper with an explicit `TIMEOUT_S` and disk allowance, dry run first | **RUNNING since 09:46 MSK 20 Sep** (`card0-20260920-094616`), dry run passed, recorded, watched (floor 77). **MEASURED 2026-09-20:** 31 FPS steady on the V100 (DataSphere T4: 26.05), 5.37 h for 600k, 38.5 GiB RAM at full replay (computed ~40), 2.2 GiB VRAM in training; solves the training scene by ~150k frames. Still owed: these numbers written into `production-schedule-v100.json` (its fields say UNMEASURED_ON_V100) and OPERATOR-GUIDE §4c.1's "never run" rows; the deferred evaluation from the retained checkpoints; then collection | launched, recorded, watched |
| H7 | `ibac_sni` 6M-frame probe | after H1 decides its evaluation shape (13 stamps × the full grid at 6M is the expensive part, not the training) | run, read, reported |
| H8 | Deployment of host scripts is by hand (`scp` of flattened copies into `~/rlvigen-work/`), partly blocked while a cell runs. Is that path documented well enough for an operator to reproduce, and should it be one checked command | OPEN | the procedure names it, with a hash check; or a small deploy script with a test |

**Usage hold from 2026-09-20 10:02 MSK (owner: 80% of the window used).** No new work or delegations until the owner's usage window resets; only the 55-minute keep-warm tick, and action if a running cell is in danger. In flight when the hold began: hands executor on the retention/provenance fixes (H2; its edits will be UNCOMMITTED and unreviewed — review before committing, explicit paths only); docs executor on the host-rules draft under `ccm-intro/docs/host-rules-draft-2026-09-20/`; two cells running and watched (`drqv2` s101 on card 0, `idaac` s103 on card 1); a checkpoint fetch into `fetched/` (first run ended with rsync exit 23 — some host files unreadable, list them). **Next after the reset, in order:** read `drqv2`'s first throughput; review and commit the executor's fixes; brief H1 (parallel evaluation by regime, validated row-for-row) and H3 (timeout redesign) once the evaluator-closure file list is known; review the host-rules draft and give it to the owner.

**Owner, 2026-09-20 10:14 MSK (usage at 90%; all of this to be done AFTER the window resets):** external anchor — nothing to decide. Lift — not now. Mode-only estimands — asked if doable: yes, every baseline already has a mode pass; working value: keep both passes, headline mode-only. Time-limit handling — owner wanted to know it was considered, not left at random: it was (`CONSTRUCTION.md` C1, `DECISION-SHEET.md` A5 and A48, `RESEARCH-FRAME.md`). Upstream-not-redistributed notice — ok, no licence for now. **Timeout: \"do the proper timeout thing not an arbitrary one that would stop jobs randomly\"** (H3 is approved as designed). G12 (loader workers > 0) — ok, \"2.4FPS isn't the way\". H8 — \"the operator should be able to deploy and run e2e\"; automate what can be, leave to discretion only what is named as such, not parts \"randomly\". Host-rules draft reviewed and amended by the lead the same morning (`ccm-intro/docs/host-rules-draft-2026-09-20/`); six calls left to the owner are in its README and the chat.

**Wrap-up, 2026-09-20 17:49 MSK (owner: no further runs now; finish what must not be aborted, defer the rest).** Done: `idaac` s103 completed by itself (F5 → collect); `drqv2` s101 trained, its evaluation stopped by me and deferred (H6: throughput ~32 FPS and RAM 38.5 GiB are the measurements owed; the evaluation itself is now owed); my two orphaned reaper timers removed (uid, exact args and start time checked); the fixed waiter and wrappers deployed to the host with old copies kept (G10/G11 host swap DONE); the interrupted executor's retention/provenance edits reviewed and committed (57 test files green; closure membership established: `eval_grid.py`, `eval_across_scenes.py`, `eval_provenance.py`, `evaluator_identity.py`, `normalize_curves.py`, `metrics.py`, `rlvigen-source.json` and each family's algorithm code are IN; `run_probe.sh`, `contract.py`, `collect-host-run.sh`, `family.py`, `families.json` and the launch chain are OUT — so H1 and H3 can be built in `run_probe.sh` without touching an attestation). **Cancelled for now by the owner's instruction:** G12 (loader-worker runs) and H7 (`ibac_sni` 6M probe). **Still owed, none needs a card:** collect `idaac` s103; H3 (proper timeout) and H1 (parallel evaluation) as code with tests; the silent defaults in `production_reading.py` / `campaign_status.py`; the two owner-decision lists; `source_commit` producer in `contract.py`; the guide sentence for `COLLECT_CHECKPOINTS=1`; why `cell-c0-yield-605720` had exited while its cell ran; which host files rsync could not read (exit 23).


**Correction, 2026-09-20 22:33 MSK.** My commit message for the retention/provenance fixes and the wrap-up paragraph above say `source_commit` is \"HALF DONE: nothing writes them yet\" and list \"`source_commit` producer in `contract.py`\" as owed. Wrong: `contract.py` has stamped `source_commit` and `source_dirty` into `payload_manifest.json` all along (`contract.py:282-294, 319`); I inferred the gap from a diff that did not touch the producer instead of reading it. Checked on the real payload that ran on the host: `payload-v216-rlvigen.tgz` carries `source_commit 6458c05…`, `source_dirty False`. With the cell script now surfacing those two fields in the run manifest, the chain is complete; the item is CLOSED. Wrap-up mode continues (owner, 22:3x: no runs): hands-2 resumed on the cell-lifetime guards; the code executor is giving `plan_production.py` an input for measured V100 throughput (the generator hardcoded UNMEASURED and had no such input).

**Night of 2026-09-20, 23:28 MSK.** Done since the last paragraph, all committed: the V100 schedule now carries measurements (`measured-v100-throughput.json` feeds `plan_production.py`; 4 of 12 baselines measured, the slowest usable cell per baseline, the defective `svea` sample excluded); `CURRENT-STATE` §2 rewritten in place — I had appended to it four times in two days against its own rule — with the chronology moved verbatim to `production-host/40`, which also records card 0's holder timeline for 20 Sep and that a 3-minute vacancy there was a restart between a labmate's jobs. The owner is asleep; no runs overnight; card 0 stays unused unless they say otherwise. In flight: the hands-2 executor, waiting on its own background test run before its final report (cell-lifetime guards; its edits remain uncommitted until reviewed).

**23:30 MSK, 20 Sep — another project of the owner's is on cds2 tonight.** Its session (ood-gen-study, peer session \"iclr-2027-programme-shallow-fork\") reports the owner told it directly at ~22:50 to run on an idle card: card 0, containers named `ogs-*`, work under `~/ood-gen-study-cds2` only, VRAM capped ~8.5 GB, 8 of 16 CPUs, ~3 h, yields under 4 GB free; it follows the host-rules draft and touches nothing under `~/rlvigen-*`. The owner's \"no runs for now\" was said to THIS session about this project; I told the peer so and that nothing of ours is armed. **For our watchers:** `ogs-*` holders in `gpu-occupancy.log` are the owner's, not strangers — `watch-cell.sh`'s KNOWN list (`sg_sam2 rl4vla_cudagl rlvigen_kalugin_df`) does not include them, so a future cell's watcher will trip NEW-GROUP on them once; that is expected. Cost note the owner asked for: the four Sonnet executors reported ~3.1M tokens over two days (under ~$6–10 at Sonnet prices); the lead's own turns are the expensive part.

**23:32 MSK, night of 20–21 Sep — card priority, RELAYED BY THE PEER SESSION, to be confirmed by the owner.** The ood-gen-study session reports the owner told it: whenever any of the three cards (cds2 0, cds2 1, ccmplanner 1) is available, that project uses it and this one does not; the two sessions are the only ones using cards under the owner's name; if our wrap-up needs a card, ask that session and it makes room. It restricts us and is consistent with the owner's \"no further runs for now\", so I follow it; it is NOT the owner's word to this session, so it is recorded as relayed. Consequence: `drqv2`'s deferred evaluation, the native queue, G12 and the `ibac_sni` probe all wait on the owner or on a request to that session. That session now READS our `~/rlvigen-runs/gpu-occupancy.log` instead of running a second logger; I told it the logger exits ~17:00 MSK on 21 Sep (40 h from 01:02 on 20 Sep) and that the 19 Sep gap must not be counted across. **Design input for the yield fix (H3, `production-host/38`), from their experience with the same labmate:** a free-memory threshold is too late against a job that ramps to 30 GiB; they yield on \"any foreign process appears, release within 15 s\". For OUR evaluation phase — ~850 MiB held, everything retained, nothing worth defending — that stricter trigger deserves to be the default; weigh it when reviewing the executor's fix.

**2026-09-21 00:06 MSK — the cell-lifetime guards are committed (laptop), NOT deployed.** Hands-2's work, reviewed by the lead: the diff of the yield watcher read in full; `bash -n` on all five scripts; the 45 new/changed tests green; MUTATION: with the poller made blind to the sentinel, all 4 yield tests fail; then all 51 test files that reference the changed scripts or docs — exit 0, 0 FAILED — plus the register, section-scope and operator-readiness checkers, all exit 0. What it does: one yield poller per cell covering training, curve evaluation, endpoint evaluation and the gaps between (`NATIVE_CELL_YIELDED phase=…`); the stall watchdog now covers evaluation (`NATIVE_CELL_STALLED phase=…`, threshold unchanged); a timeout names itself (`NATIVE_CELL_TIMEOUT phase=training limit=… `, with the last frame seen); the wrappers default `TIMEOUT_S` to max(3× scheduled training, 24 h) for scheduled baselines instead of refusing (unknown baselines still refuse; `idaac`/`ppg`/`ibac_sni` keep 12 h exactly); `watch-cell.sh` projects training finish against the ceiling and trips on an overrun > 10% (it reproduces the 2.4 FPS `svea` case as an OVERRUN). H3 and `production-host/38`: FIXED ON THE LAPTOP. **Still open:** (a) DEPLOY — `run_probe.sh` ships by payload (new payloads needed for every family before its next cell), the wrappers, `watch-cell.sh`-side nothing, and `run_on_production_host.sh` (two new env names on its forward list) lives in the host CHECKOUT, not the flattened copies — all only while nothing of ours runs; (b) a cell that DOES hit its ceiling still skips retention and evaluation although its checkpoints are durable (`run_one_cell`, the `|| return 1` after training) — salvage-on-timeout is unbuilt; (c) the evaluation-phase yield TRIGGER is still the free-memory floor written by the host observer; the peer session's experience says \"any foreign process appears\" is the trigger that is not too late — our launcher has that mode (`NATIVE_YIELD_ON_PROCESSES`) but the 20 Sep launches passed `EXPECT_OURS=20`, which can never trip; (d) no real multi-hour cell has exercised any of this.
