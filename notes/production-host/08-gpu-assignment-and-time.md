# GPU assignment, and what time it is

## The machine is under a strict GPU assignment schedule

**You may use only the GPU assigned to you, on the machine it is assigned on, during the period it
is assigned for.** Not another card on the same machine. Not the same-numbered card on another
machine. Not an idle card. Not "just to check".

**Assignment on record: 8 September — `cds2`, `V100-1`.**

Everything about that sentence is load-bearing:

- **`V100-1`, not `V100-0`.** Identify the card by what `nvidia-smi` reports and pin it at the
  Docker level: `DOCKER_GPUS='"device=1"'`. `CUDA_VISIBLE_DEVICES` alone does not limit what the
  container can reach.
- **`cds2`, not any other host.** Similar names are not the same machine and never imply a rename
  or an equivalent. `cdsserver` is not `cds2`. `aicenter1`, `aicenter2`, `aicenter3` are three
  different machines, not one with revisions. See `00-authority-and-scope.md`.
- **8 September, and that date is in the owner's timezone.** See below.

**An assignment does not roll over.** When the day ends, the entitlement ends, whether or not our
run has finished. Someone else's assignment begins.

## Time: report UTC+3, always, and never only UTC

**The owner counts in UTC+3. This session's shell reports UTC.** They differ by three hours, and
near midnight they differ by a calendar day — which is exactly when a GPU assignment changes hands.

**Every time stated to the owner, or written into a plan, carries UTC+3 — with UTC alongside where
a command or a log line is involved.** A bare `09:00` is ambiguous and, on the boundary of an
assignment window, dangerous: `2026-09-08 22:00 UTC` is already **9 September** for the owner, and
the 8 September assignment is over.

The 8 September assignment, resolved:

```
8 Sept (UTC+3)   2026-09-08 00:00  ..  2026-09-09 00:00   UTC+3
in UTC           2026-09-07 21:00Z ..  2026-09-08 21:00Z
```

Job logs, `datasphere` timestamps and this shell are UTC. Convert before reasoning about the
window, never after.

## The consequence that changes the plan

At 2026-09-08 12:13 UTC+3 (09:13 UTC), **11.8 hours remained** on the assignment.

| | duration | fits in what remains? |
|---|---:|---|
| drqv2 canary (gate 5) | ~9.1 h | **yes**, with roughly 2.5 h of margin |
| one median 600k cell | ~15 h | **no** |
| soda canary (A10) | ~45 h | **no**, and it does not fit any single day |

**A 45-hour cell cannot be run inside a one-day GPU assignment.** `notes/DECISION-SHEET.md` A10
names `soda` at full 6e5 as the canary precisely because it is the longest projected cell — and
that is unrunnable under this schedule without either a multi-day assignment or a resumable design.
`ai-recommendation-22` already establishes that an off-policy cell **cannot** be resumed from a
mid-run checkpoint, because replay state is not persisted; a crashed or cut-off cell must restart
the same seed from frame 0.

**So the schedule is a real constraint on the campaign, not a detail of one run.** It has to be
settled with the owner before any long cell starts:

- how many consecutive days are assigned, and on which machine;
- whether a cell that will outlive its window may start at all — under the no-resume rule, it
  cannot, because being cut off wastes the whole cell and the GPU-time with it;
- what the campaign's per-day unit therefore is.

**Do not start a cell whose projected wall clock exceeds the remaining assignment.** Read the
projection from `audit_job_budgets.py` / the schedule, compare it against the window in UTC+3, and
if it does not fit, stop and raise it.

## Before every host session

1. Confirm today's assignment — machine, card, date — rather than reusing yesterday's.
2. `nvidia-smi`: confirm the assigned card is the one being pinned, and note what is on it.
3. Compute the remaining window in UTC+3, and check the intended run against it.
4. If the run does not fit, do not start it.
