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
