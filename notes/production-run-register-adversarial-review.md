# Adversarial review of the run-register system, and what it found

**2026-09-09**, written against the system built the same afternoon: `results/PRODUCTION-RUNS.md`,
`scripts/production_run_register.py`, `scripts/record_host_run.py`, `results/host-runs.jsonl`,
`datasphere/native/collect-host-run.sh`, `scripts/assemble_reaped_delivery.py`.

Reviewed by asking one question of each piece: **what would have to be true for this to report
something reassuring while the truth is bad?**

---

## B1 — BLOCKING. The two tools built for a stopped cell do not compose

`collect-host-run.sh` step 1 refuses without `NATIVE_CELL_COMPLETED`. **That marker is printed at
the end of the whole cell, after evaluation** — so a cell stopped by its own watch budget mid-
evaluation never prints it. Checked on the live run at 17:28: the log carries `NATIVE_CELL_BEGIN`
and nothing else.

`assemble_reaped_delivery.py` exists precisely to rebuild that cell's bundle. **Its output cannot
then be collected**, because the collector refuses the run for the same reason the assembler was
needed. Two tools, one case, and they meet at a wall.

**Neither refusal is wrong on its own** — that is what made it invisible. Step 1 is right that an
incomplete cell must not be filed as complete; the assembler is right that the rows exist. What was
missing is an explicit, evidenced path between them.

**Fixed:** `--accept-watch-stop`, which requires `NATIVE_CELL_BEGIN`, requires the bundle to be
assembled (every row carrying `_assembled_after_reaping`), and refuses if `NATIVE_CELL_FAILED` is
present. It prints `NATIVE_COLLECTED_AFTER_WATCH_STOP` and the resulting records are marked
per-row, so nothing about this path is silent. Without the flag the refusal is unchanged.

## B2 — A launch nobody records is invisible again

`record_host_run.py` closes the gap only when it is run. Nothing at launch requires it, so the next
cell launched by a hurried operator is exactly as invisible as today's two were this morning.

**NOT FIXED, and the fix I first wrote here was fictional.** I claimed `launch-card-cell.sh` would
record the run itself. **It cannot**: the launcher runs on the production host and the ledger is a
file in this repository, on a different machine. I wrote the remedy before checking where the two
things live.

What is actually true, and is worth stating rather than dressing up:

- **The host side is already self-describing.** Every cell writes `effective_config.json` into its
  own run directory, which is exactly what `record_host_run.py` reads. A launch is never
  unrecoverable — it is only unrecorded *here* until someone fetches it.
- **The repo side needs one local command**, and that is a procedure, not a structure:
  `python scripts/record_host_run.py <fetched-run-dir> --status "launched"`. It is now the last
  step of the launch snippet in `notes/RUNNING-ON-PRODUCTION-HOST.md` §3.0.
- **The residual risk is real and unmitigated.** A cell launched by someone who skips that command
  is invisible to `results/PRODUCTION-RUNS.md` exactly as today's two were this morning. The only
  structural fix would be a collector that enumerates run directories on the host, and this
  repository must stay checkable offline (B4), so that trade has not been made.

Recording a fix that does not exist is worse than recording the gap: the gap gets fixed, and the
fiction gets trusted.

## B3 — A status field is a snapshot presented as a fact

`host-runs.jsonl` carries `"status": "curve in progress"`. Nothing updates it. A reader next week
sees a confident present-tense claim about a run that finished or died hours later.

**Fixed:** every entry now carries `status_as_of`, and the register prints the age of the status
beside it. A stale status still misleads, but it can no longer do so silently.

## B4 — `--check` proves less than it appears to

`production_run_register.py --check` proves the Markdown matches `results/records/`. It proves
**nothing** about `host-runs.jsonl` — the statuses, the run directories, whether those runs still
exist on the host. The strongest check in the system covers the half that is machine-derived and
none of the half that is asserted.

**Not fixed, and stated instead.** Verifying a host path needs the host, and this repository must
stay checkable offline. The register now says which of its sections are derived and which are
asserted, so `--check` is not read as covering both.

## B5 — Host runs' logs are reported as absent

The register looks for `results/logs/<job>*`. Host runs put their curve in
`native-out/cells/<cell>/progress-*.csv`, which is never installed there, so **every host run reads
"logs: none"** while a 7 KB curve exists in the fetched directory.

**Fixed:** the register distinguishes "no logs installed in this repo" from "no logs exist", and
names where a host run's curve actually lives.

## B6 — The curve is not summarised at all

The register's headline table is endpoint-only. For `idaac` that is 44 rows out of 528; the 484-row
curve — the learning trajectory, and the artifact that showed the plateau — appears only as a frame
count.

**Fixed:** each run now gets a compact curve line (first/peak/last train-regime return with frames),
which is what makes a plateau visible without opening the file.

## B7 — Deleted runs stay claimed

Nothing notices if a recorded `run_dir` is removed from the host. **Accepted, not fixed** — same
reason as B4. The `status_as_of` age is the partial mitigation.

---

**What this review did not find, and I looked:** no path where a *wrong number* is reported as a
right one. Every defect above is an availability or staleness problem — a thing missing, refused,
or out of date — not a metric that lies. The per-row `evaluator_revision`, `checkpoint_sha256` and
`_run_provenance` machinery was already load-bearing and held.
