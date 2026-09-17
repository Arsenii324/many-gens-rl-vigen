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
| A1 | Prod monitoring alive at all times, including when nothing of ours runs | PARTIAL (continuous duty) | trip watcher (background shell, no timeout) + beat Monitor alive; beat re-armed on each 30-min expiry; occupancy logger restarted before it lapses (~14:45 MSK 2026-09-18). Never closes while the campaign runs. |
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
| B2 | Checkpoint / restart / resume capability, per family, all seven | OPEN | Per family: what is written, when, where on host (mid-training vs after completion), what a resume restores and what it loses, whether the launcher wires resume. Each fact cited to code or families.json, and the claims I made from memory re-read. |
| B3 | Early-stopping and stop mechanisms: every way a cell ends before 600k | OPEN in the guide (exists in notes/model/STOP-MECHANISMS.md) | List each mechanism (timeout, stall watchdog, memory floor, disk floor, reaper, self-vram-cap, manual sentinel), what triggers it, which marker it writes, which contexts it covers, and what state it leaves. Link STOP-MECHANISMS.md, don't duplicate; verify it against current scripts. |
| B4 | Docker images, run flags, caveats (EGL/graphics, --gpus, venv mount, caches) | PARTIAL (§6 topology) | Image refs quoted from source-lock.json / launcher, each flag's reason, known caveats that bit us. |
| B5 | Resources per family (VRAM, disk, CPU, wall time) | PARTIAL (§4c) | Measured numbers with their source file; which are measured vs extrapolated. |
| B6 | Integrations and checks (contract verify, gates, evaluator binding, collectors, provenance, ledger) | PARTIAL (§8, RUNNING-ON-PRODUCTION-HOST) | One table: check → what it proves → when to run → what a failure means. Each command actually run once. |
| B7 | Golden path fully fleshed, as executed | PARTIAL | A single ordered procedure from clone to collected result, using only commands executed in this campaign, with expected output at each step. |
| B8 | Off-golden-path model | PARTIAL (§10) | Failure triage extended by B2/B3 facts: what to do after each stop kind. |
| B9 | Out-of-reach catalogue, each narrowed and labelled (target / state / operation) | PARTIAL (§11.3 lists, not narrowed) | Every never-executed part as its own entry with: isolated part, why out of reach, target state, the operation that achieves it, and how to tell it worked. |
| B10 | Links to project-wide docs instead of duplicating | PARTIAL | docs/RUN-THIS-PROJECT.md already deferred to; check PROJECT-INDEX, EVAL-PROTOCOL, COMPARABILITY_CONTRACT, STATUS-AGAINST-THE-GOAL, compute.md and link where they own the fact. |
| B11 | Grounding pass: nothing in the guide that I did not execute is stated as working | PARTIAL (§11 boundary) | Re-read the whole guide at the end; every command either executed (and where) or labelled untested. |

## C. Housekeeping questions

| id | task | status | what closes it |
|---|---|---|---|
| C1 | "Do we have local residual files that take a lot of space? Answer, don't delete" | DONE (answered) | Deletion of the scratchpad clonetest (287 MB) postponed until the user returns, as allowed. |

---

## Closing reports

(Each DONE item gets a dated paragraph here: what was done, what verified it, what remains out of
scope and why.)
