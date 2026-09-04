Written 2026-09-04.

# Retained results — the cheap half of every job that ran

## What is here and why it is in the repository

`docs/EVAL-PROTOCOL.md` §6 states the storage rule this directory implements:
**checkpoints stay remote, records come back.** One `drqv2` cell at 100k returns a 296 MB archive
of which 199 MB is checkpoints and about 200 KB is the numbers; at 6e5 × 3 seeds × 12 baselines the
archives are ~53 GB against ~30 GB free on the working laptop. So the archives are not kept and
the records are.

Until 2026-09-04 neither was kept. Every job's records were read once out of a scratch directory
and discarded, which meant the project had produced measurements it could no longer show — and
`scripts/requirements.py` graded **R7** ("the clone-to-curve path works") as NOT MET partly for
that reason. These files are that gap closed.

- **`records/`** — one `.jsonl` per job, in the schema `datasphere/native/normalize_curves.py`
  emits: one record per (phase, regime, scene set, frame), with `native` carrying the baseline's
  own keys verbatim. `*__offline_eval_cuda.jsonl` are offline-evaluator grids; `*__records.jsonl`
  are the runner's normalized output.
- **`logs/`** — the training curve each baseline writes in its own format, straight from the
  returned archive: `train.csv`/`eval.csv` for the RL-ViGen five, `progress*.csv` for `idaac` and
  `ppg`, `log.csv` for `ibac_sni`. These are the inputs the shared plotter reads.

Filenames are `<job id>__<cell>__<original name>`, so every row traces to the DataSphere job that
produced it and nothing here is anonymous.

## What these files are NOT

**They are not a results table**, and no row here has been selected, ranked or pooled. Which of
them may be compared with which is decided by `docs/EVAL-DECOMPOSITION.md` and
`docs/COMPARABILITY_CONTRACT.md`, not by their being adjacent in a directory. In particular:

- Everything here is **single-seed**. Per `EVAL-PROTOCOL.md` §4b, one seed licenses existence and
  floor claims only, never a ranking.
- `ctrl`'s and `ibac_sni`'s rows are **outside the pooled table** for stated reasons — a different
  estimand ([`COMPARABILITY_CONTRACT`](../docs/COMPARABILITY_CONTRACT.md) §5d) and a policy whose
  action mass is mostly outside the action box ([C61](../docs/CONSTRUCTION.md#c61)).
- Ten of twelve baselines have an **undischarged shared-evaluator burden**
  (`scripts/audit_shared_evaluator.py`), so a number here from those ten comes from an instrument
  not yet shown to measure what that baseline's own evaluator measures.

## Regenerating

Nothing here is authored. Each file is a copy of an artifact returned by a job whose id is in its
name; `bash datasphere/native/job.sh diagnose <job id> <dir>` fetches the archive again, and
`datasphere/native/normalize_curves.py --directory <dir>` rebuilds the records from it.
