# A run-level constant on every row: one defect class, two instances, 98 % of two bundles

**2026-09-10.** `collect_record_delivery` stamps run-level structures onto **every** delivered row.
Anything large in one is multiplied by the row count, and the multiplication is invisible from any
single row — which is why both instances below survived review.

## Instance 1 — `_run_provenance.cells.<cell>.resource_samples` (fixed)

`records_delivery.jsonl` on `card0-20260909-115331`: **1,365,573,627 bytes for 964 rows.** About
1.4 MB per row, of which roughly 8 KB was the record.

The run manifest inlined the resource sampler's entire per-second series — 2,173,638 bytes, 1,783
samples — and 616 offline-eval rows carried it. Three things were wrong at once:

1. **Size.** `collect-host-run.sh` had measured this field once at *"roughly 231 KB per row"*
   against a short cell. True when written, never re-checked.
2. **It grows with the run.** The sampler appends about once a second, so the field is a function
   of duration. The 45-hour cell this fleet is scheduled around would carry ~160,000 samples per row.
3. **It names other people's processes.** `gpu_compute_processes` comes from `nvidia-smi
   --query-compute-apps=pid,...`; on a shared host that is every user's PIDs and GPU memory — nine
   foreign PIDs in that run — replicated into every published record.

Fixed by calling `summarize_resources`, which the project already had and which emits no PID:
**410 bytes, 5,302× smaller**, projected bundle ~3 MB. Nothing lost — the full series stays in the
cell's own `resources.json`.

## Instance 2 — `native.runtime_import_manifest` (found, not yet fixed)

Found immediately by `scripts/explain_delivery_size.py`, written to explain instance 1:

    card0-20260909-035152__records.jsonl: 569 rows, 19,703,882 bytes, 34,628 bytes/row mean
          total bytes     per row  field
           18,439,071      32,406  native
           14,679,702      25,799  native.runtime_import_manifest
            9,622,871      16,911  native.runtime_import_manifest.module_files
            4,986,901       8,764  native.runtime_import_manifest.unlisted_local_files

**74 % of that bundle is one field**, and it holds **two distinct values across 569 rows** —
505 rows share one, 13 share another (the mode pass loads a slightly different set, which is
itself worth keeping). It already carries `module_files_sha256`, its own digest.

**Nothing reads it.** Grepped `scripts/`, `datasphere/`, `tests/`: `module_files` and
`unlisted_local_files` appear only where `eval_provenance.py:93-95` writes them. It is write-only
provenance, stored 518 times more than it has values.

### The fix, deliberately not applied tonight

Keep `module_files_sha256` on every row — that is the provenance fact, *which import set produced
this row*, and it preserves the 505/13 distinction. Write each distinct manifest once to a sidecar
keyed by that digest.

It is cheap and has no consumers to break, but it changes what a record carries, and
`scripts/eval_grid.py` is a `CODE_MEMBER`. It belongs in the same single evaluator-revision bump as
the `no_grad` fix and the `eval_policy_mode` fix rather than in a bump of its own, and it should
land when there is time to re-run the full suite behind it rather than at the end of a session.

## The general rule this yields

**A structure that is constant across a run must not be stamped per row; a digest of it must.** The
row stays self-identifying, the store holds one copy, and a change in the constant remains visible
because the digest changes.

`collect-host-run.sh` now guards the class rather than either instance: it reports at over 64 KB
per row and refuses over 1 MB per row (overridable with `NATIVE_ACCEPT_FAT_DELIVERY=1`), pointing
at `explain_delivery_size.py`. **Bytes per row, not total bytes** — a genuinely large run has many
rows, so a total-size threshold would refuse it while passing a small run with a bloated manifest,
which is exactly backwards. Note that instance 2 sits *below* that guard at 34.6 KB/row: the guard
catches the severe case, and the tool is what finds the rest.
