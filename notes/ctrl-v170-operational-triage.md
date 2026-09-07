# CTRL v170 operational triage

**Checked:** 2026-09-06, Europe/Moscow. **Scope:** read-only investigation of the
v170 evaluator-validator wave, especially `bt14nfqap1l3qeppn5ug`. No job was
launched, retried, cancelled, or modified by this triage. The only repository
write is this note.

## Status from DataSphere

The project CLI (`GRPC_DNS_RESOLVER=native`, project
`bt12q57tmrs03pnt8drc`) reported:

| family | job | created (UTC) | finished (UTC) | status |
|---|---|---:|---:|---|
| rlvigen | `bt1qotj7n0bdesa178l5` | 16:59:18.620 | 17:18:39.370 | SUCCESS |
| dmc_gb | `bt18brpl6q3oqu5gp6sm` | 16:59:23.133 | 17:26:35.604 | SUCCESS |
| idaac | `bt17i6gn4lur2d206div` | 16:59:31.037 | 17:14:44.310 | SUCCESS |
| alda | `bt14iqbur5j2ikqk1ejj` | 16:59:40.536 | 17:30:59.818 | SUCCESS |
| ppg | `bt1uhle25ehkqg2tfk8b` | 16:59:59.549 | 17:15:44.553 | SUCCESS |
| ibac_sni | `bt13cv217a4m0uru0891` | 17:00:04.655 | 17:14:51.381 | SUCCESS |
| ctrl | `bt14nfqap1l3qeppn5ug` | 17:00:28.486 | 17:00:31.868 | ERROR |

`bt14nfqap1l3qeppn5ug` therefore terminated 3.382 seconds after creation.
`datasphere project job get` exposes no server-side error field beyond `ERROR`.
Its `data_cleared` flag is false and its retention deadline is 2026-09-20.

## What exists for CTRL, and what does not

`datasphere project job download-files --id bt14nfqap1l3qeppn5ug
--with-logs --with-diagnostics` returned:

```
job ... was completed with error (5). Not all files can be downloaded.
no files to download
```

The CLI's execution/attach diagnostic enumerated the remote files as:

```
stdout.txt          0.0B
stderr.txt          0.0B
docker_stats.tsv    0.0B
job_progress.jsonl  0.0B
system.log          0.0B
gpu_stats.tsv       0.0B
log.txt             2.6KB   (CLI operation log, not container output)
```

Thus there is no downloadable container stdout, stderr, system log,
progress log, GPU log, result archive, or records file for CTRL v170.

Important CLI safety finding: `datasphere project job attach` is not a passive
log-read operation in the installed client. Its implementation calls
`client.execute(args.id)` before reading logs. I invoked it while investigating;
the server rejected that execution attempt before a new container started. It
returned the following operation error:

```
status=RESOURCE_EXHAUSTED
details=Job execution quota exhausted
```

No new job ID appeared and the original job remained `ERROR`. Future triage
must not use `attach` as a read-only status/log command; use `job get`, `job
list`, and `download-files` only.

## Root cause assessment

### Confirmed

* CTRL v170 failed before any container output or result file was produced.
* A DataSphere execution operation in the same project returned
  `RESOURCE_EXHAUSTED: Job execution quota exhausted`.
* The contemporaneous project record in
  `notes/claude-answers.md` section A58 records that four A35/A36 pilot jobs
  were already executing when the seven v170 jobs were submitted; up to eleven
  executions were requested concurrently, and the observed list had ten still
  `EXECUTING`/`PREPARING`/`CREATING`. CTRL was submitted last.
* The current job list has no v170 job still running. Two newer ALDA pilot jobs
  are currently `EXECUTING`: `bt15qurft0mrovjqvs1a` (v172) and
  `bt1lp8hfjrqfn1evdg08` (v173).

### Best-supported explanation, not an absolute server postmortem

The evidence strongly supports scheduler/project execution-quota exhaustion
at CTRL's admission, rather than a CTRL code, payload, or evaluator failure:
the job died in 3.382 seconds with zero container files, and the service
explicitly reports execution quota exhaustion under the concurrent load.

The original job's own server-side error detail is not exposed by `job get`,
and the later `attach` command itself attempted an execution. Therefore the
`RESOURCE_EXHAUSTED` response is direct scheduler evidence and the strongest
root-cause explanation, but it is not claimed as a separately retrieved
post-mortem field from the original job. No evidence supports blaming the
CTRL payload or its evaluator code.

No hard numeric project concurrency ceiling was returned by the available CLI.
The number eleven is the observed/requested overlap, not a proven platform
limit.

## CTRL v153 comparison

`bt13haqsc8a4geh3lnou` (v153) was `SUCCESS`, created at 15:51:34.153 UTC and
finished at 16:11:45.914 UTC. Its config and v170 config have the same
operational experiment shape: `NATIVE_HOST_PROFILE=datasphere`, `CELLS=ctrl:1`,
`FRAMES=10000`, `TASK=Door`, `SEED=1`, endpoint evaluation over
`train,eval-easy`, scene `0`, five episodes, CUDA, and tier `gt4i.1`.

The meaningful payload difference is provenance, not the requested run shape:

| | v153 | v170 |
|---|---|---|
| payload SHA-256 | `df42f09bbda95d8ce4d06a74daf6e88e11e9dc6722c5d03ad377198324b43ef1` | `9245d61affc000764d3d58d031f44f47326675037d4b3f1b744a1e398c0fbc4f` |
| evaluator schema / runner contract | 2 / 13 | 2 / 13 |
| payload-manifest revision | `b7f687452b2d...` | `fdc8f6e77970...` |
| records' reported revision | `763de034c4ec...` (mismatch) | none |
| `door.xml` in CTRL runtime identity | yes | no |
| config revision | `eb76930446ca...` | `eb76930446ca...` |

Removing runtime-generated `runnable/ctrl/door.xml` from the hashed CTRL
closure is the documented v170 source correction. The v153 job completed and
produced data; it is superseded for current identity purposes, but its failure
mode was not a scheduler admission failure.

## Successful v170 outputs

All six successful jobs were downloaded to temporary directories and checked.
Each has both `records.jsonl` and `result.tgz`; every record set has
`record_delivery=complete`, four offline-evaluation rows (two regimes with the
intentional duplicate rich/aggregate representation), one evaluator revision,
one evaluator-scope revision, and one checkpoint SHA-256. The downloaded
archives are retained by DataSphere (`data_cleared=false`, expiry
2026-09-20) and are suitable for later evidence integration.

| family | records | result archive | offline rows | payload/record revision |
|---|---:|---:|---:|---|
| rlvigen | 19 | 93 MB | 4 | matches |
| dmc_gb | 29 | 70 MB | 4 | matches |
| idaac | 5 | 92 MB | 4 | matches |
| alda | 7 | 8.9 MB | 4 | matches v170 payload |
| ppg | 10 | 13 MB | 4 | matches |
| ibac_sni | 84 | 2.7 MB | 4 | matches |

The table's archive sizes are local download observations; they are not
performance claims. The records contain the actual endpoint means/success
rates and provenance fields, so they can be integrated after the normal
records-ingestion/review step. This triage did not copy them into `results/`
or alter any ledger.

One current-tree caveat matters: the current evaluator identity calculation
matches the v170 payload and records for `rlvigen`, `dmc_gb`, `idaac`, `ppg`,
and `ibac_sni`. Current ALDA identity is
`88e876dbcdd701d600923b9756fcac30a18e785b7ac240a78c6cfae290f186cf`, while
the v170 ALDA payload/records carry
`99757dd842c8ce35a023d5cbf5068a71a5b5aa1da70e8e43f97919278d8f278f`.
Therefore ALDA v170 is retained functional/historical evidence, but must not
be presented as a certificate for the current ALDA tree without the project's
normal final-freeze decision. The mismatch alone does not establish that its
measured behavior changed; it establishes that the current identity gate will
not accept it as current.

## Safe next action

Do not retry or cancel CTRL v170. Keep its error and absence of files as the
operational record. Treat the six successful v170 archives/records as
recoverable integration inputs, with the ALDA identity caveat above. Do not
start another evaluator-validation wave merely to replace this failed CTRL
job; the project's accepted sequence is to finish fidelity work, freeze the
tree, and run one final seven-family validator wave.

The only jobs needing ongoing status monitoring at this snapshot are the two
newer ALDA pilot jobs (`v172`, `v173`), which are outside this v170 triage.
