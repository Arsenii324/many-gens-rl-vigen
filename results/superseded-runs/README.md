# Superseded-closure runs — preserved, and NOT results

These rows were produced on evaluator closures that no longer exist. They are kept because they
were the only copy and the host directories that held them are ~5 GB of finished scratch; they are
**not** admissible as measurements and nothing in the reporting path reads this directory.

| file | rows | baseline | closure | current closure |
|---|---|---|---|---|
| `card0-20260909-115331__records.jsonl` | 964 (347 train, 1 eval, 616 offline-eval) | ppg | `16e960b1f446` | `248751f7caca` |
| `card0-20260909-013936__records.jsonl` | 16 | idaac | `16e960b1f446`, `184329928b51` | `1b092f978fdc` |
| `card0-20260909-005543__records.jsonl` | 6 | idaac | `16e960b1f446` | `1b092f978fdc` |

## Why they are not in `results/records/`

`populate_evaluator_ledger.py` refuses a record whose `evaluator_revision` is not the live one, and
that refusal is the most valuable thing it does. `audit_row_closure.py` exists to refuse pooling
across closures. Putting these beside current records would invite exactly the pooling both tools
are built to prevent, so they live here, labelled, instead.

## What was dropped, and what was not

`_run_provenance` is retained on the FIRST row of each file and stripped from the rest. It is
identical across rows of one run — manifest, payload and asset digests, resolved packages — and at
roughly 231 KB per row it was 98% of the bytes. That turned 1.3 GB into 22 MB. Every measurement
field on every row is intact; only the repeated provenance blob is gone.

## What they are good for

Diagnostics, not numbers: what a curve looked like, whether a phase ran, how many offline-eval rows
a configuration produced. The 964-row ppg run is the largest evaluation sweep this workspace has
done on the native host and is useful as a shape reference. It cannot be compared against anything
measured on the current closure.
