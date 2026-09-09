# Local disk: what is safe to reclaim, and the one thing that must move before it can be

**2026-09-09. Nothing in this list has been deleted.** Measured on the laptop, not the host.

**Free space: 19 GiB.** `docs/local-envs.md` / CLAUDE.md record ~32 GB, so this has tightened.

| where | size |
|---|---:|
| `.../many-gens-rl-vigen/data/places365_standard` | **27 GB** |
| this job's scratch, `~/.claude/jobs/d037da9e/tmp` | **11 GB** |
| `datasphere/native/*.tgz` (191 payloads) | **4.5 GB** |
| `ext/` + `RL-ViGen-upstream/` + `runnable/` | 1.5 GB |
| workspace-root `*.tgz` (25 files) | 464 MB |

---

## A. MUST NOT be deleted yet — it is the only copy, and the host needs it

### `data/places365_standard/train` — **26 GB**

**Do not delete. Upload first.**

- **The host has no Places365 at all.** `find ~ -iname '*places365*'` on the production host returns
  only test *filenames*. There is no dataset there.
- **`datasphere/native/places365-val.tgz` is 66 bytes** — a stub, not an archive. There is no
  packaged copy either.
- **Production refuses the `val` split.** `run_probe.sh:1962-1973`: at `FRAMES >= 600000` the runner
  refuses unless `NATIVE_PLACES365_SPLIT=train`, or `NATIVE_PLACES365_ACCEPT_VAL=1` records an
  explicit deviation.
- **Three baselines need it**, and they are the disk-heaviest cells in the battery:
  `svea`, `sgqn`, `soda` each charge **45.0 GiB** for it, for a 72.9-73.7 GiB per-cell requirement.
  The other nine charge **0.0**.

**So deleting it blocks 3 of 12 baselines and costs a ~27 GB re-download.** Once it is on the host
and verified (`setup/verify_datasets.py --split train` -> 365 classes), the local copy becomes the
best candidate on this page.

*This is also a battery prerequisite that was not on any list: `svea`/`sgqn`/`soda` cannot run at
production scale until a 26 GB transfer happens.*

### `data/places365_standard/val` — 546 MB
Same argument, smaller, and it is the non-production default. Move with the train split.

---

## B. Safe to delete now — reproducible from git

### `datasphere/native/*.tgz` — 4.5 GB, 191 files
Payloads are `contract.py build-payload --source . --output ... --families ...` output. Every one is
rebuildable from its commit, and **all but `payload-v208-rlvigen.tgz` are stale anyway** — they
report *"built for runner contract 14 but this runner needs 19"*.

**Keep:** `payload-v208-rlvigen.tgz` (272 KB, the only contract-19 payload, already staged on the
host). **Candidates:** the other 190.

### workspace-root `*.tgz` — 464 MB, 25 files
Largest: `payload-onpolicy-v30/v29/v26.tgz` (91 MB each), `result.tgz` (62 MB),
`alda-payload-v1.tgz` (51 MB), `payload-alda-v32.tgz` (36 MB). Same argument; none is referenced by
`results/`.

---

## C. Safe to delete now — my own scratch from finished investigations

`~/.claude/jobs/d037da9e/tmp/`, **~5.5 GB of the 11 GB**:

| dir | size | last touched |
|---|---:|---|
| `seedvar` | 1.0 GB | 09-08 |
| `sgqn-diag` | 1.0 GB | 09-08 |
| `shape100k` | 937 MB | 09-07 |
| `libsweep` | 813 MB | **08-18** |
| `p365` | 561 MB | 09-08 |
| `v3-sgqn` | 482 MB | 09-08 |
| `alda89` | 368 MB | 09-05 |
| `v2-drq` | 340 MB | 09-08 |

**Keep** (live, small): `fetched/` 145 MB — the collected `idaac` run; `rescue/` 21 MB and
`rescue-ppg/` 20 MB — the running second copies of both cells.

---

## D. Keep — vendored and load-bearing

`ext/` 662 MB (the primary-source PDFs this project keeps being right by reading),
`RL-ViGen-upstream/` 448 MB, `runnable/` 412 MB (hashed family runtimes).

---

## Totals

| action | reclaimed | free after |
|---|---:|---:|
| B + C, no transfer needed | **~10.5 GB** | ~29 GB |
| plus A, after uploading Places365 | **+26.5 GB** | ~56 GB |

**Recommended order:** do B and C first — they need no transfer and no decision. Do A only after the
dataset is on the host and `verify_datasets.py --split train` passes there, because it is currently
the project's only copy.
