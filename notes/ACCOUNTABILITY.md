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
| A1 | Prod monitoring alive at all times, including when nothing of ours runs | PARTIAL (continuous duty) | trip watcher (background shell, no timeout) + beat Monitor alive; beat re-armed on each 30-min expiry; occupancy logger restarted before it lapses — its own header says it started 2026-09-16T19:22:05 with hours=40, so it stops about **11:22 MSK on 2026-09-18** (checked, not recalled: the ledger previously said 14:45). Never closes while the campaign runs. |
| A2 | Launch the highest-information next cell when a card is genuinely vacant (co-tenant absent ≥10 consecutive min) | BLOCKED on vacancy | Queue: idaac s103 (makes idaac n=3) → ibac_sni s102 full re-run → ppg s101. Each launch follows the preflight practice (no result tgz, prior log preserved, disk ≥ highest live floor + 10 GiB, host-runs.jsonl entry, watch-cell.sh + self-vram-cap armed). |
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
