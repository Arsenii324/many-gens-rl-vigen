> **Executor output, not a finding of record.** Produced 2026-09-20 by a read-only Sonnet executor
> from files physically on the laptop (no host access). Re-checked by the lead: a real records row of
> `idaac` s102 carries parallel per-episode lists (3 returns, 3 successes, 3 diagnostics dicts with
> 14+ fields); the two completed cells' checkpoints were absent locally and present on the host
> (108 MB, 113 MB) — fetched the same morning. Not re-checked: the manifest-field claims, the
> `resources.json` summariser failure, the `ppg` row counts. Raw audit script and output:
> the session scratchpad, `richness/audit.py`, `audit.out` (volatile).

# What a finished production cell retains — audit of 2026-09-20

The owner's concern, verbatim: *"the metrics (at least the all-checkpoint runs; better, this
including dense train metrics) should allow to richly recalculate different statistics, not just
this 'endpoint-as-headline' … if we have rich data, post-analysis could surface useful discussion
and insight."*

## Evaluation rows — per-episode grain IS kept

One row per (frame stamp, regime, scene set, policy mode); inside it `native.returns`,
`episode_success` and `episode_diagnostics` are parallel per-EPISODE lists (3 per curve row, 20 per
endpoint row). Per episode: `episode_length`, `termination_reason`, `time_to_success`,
`reward_{min,mean,max,sum}`, action-clip rates, raw action min/max/L1, `initial_placement`,
`placement_hash` and seed. Same schema for all families (one shared evaluator).

## Dense training metrics — kept unevenly

| family | what is in the records | note |
|---|---|---|
| `idaac` | `progress-*.csv` rows, 26 points (every 12 PPO updates): losses, entropy, KL, clip fraction | filed with `phase="eval"` — a mislabel |
| `ibac_sni` | `log.csv` rows, 293 points (every update): FPS, entropy, KL, grad norm, value and policy loss | |
| `ppg` | 347 points in the superseded original run; **0 in the valid closure** — its live record is an offline re-evaluation only | a gap |
| RL-ViGen natives | not yet known: no native cell has completed; the run dir holds `train.csv` and `tb/` | check on `drqv2` s101 |

## Checkpoints — were host-only for two completed cells

`idaac` s102 and `ibac_sni` s101 had no checkpoint on the laptop; `.pt` is gitignored, so a clone
never has them either. The host crashed on 2026-09-19 and its disk is shared. Fetched 2026-09-20.
Collection does not bring checkpoints by default — a policy gap, not a one-off.

## Recomputable later / not recomputable

**Can:** per-scene and per-regime variance, bootstrap intervals over episodes, success-vs-return per
episode, action-clip and extreme-action distributions, termination-reason mix, dense loss/entropy
curves where kept, placement reproducibility, pip-environment audits.
**Cannot:** anything per TIMESTEP (only episode summaries are kept); per-episode wall time (never
recorded — and it is what an evaluation-cost analysis needs); host RAM/VRAM/CPU time series
(`resources.json` was never fetched, and its summariser fails with `ModuleNotFoundError: No module
named 'summarize_result'` on both cells checked); anything needing weights for a cell whose
checkpoints were not copied off the host.

## Environment provenance per run (from `_run_provenance`, embedded in the rows)

Recorded: **pip** — 87 pinned `name:version` pairs from `importlib.metadata`; the container image
digest; the NVIDIA driver string; payload and requirements content hashes.
Not recorded: **apt/dpkg versions** (nothing captures them; only the base image is pinned, and
`apt-get install` runs unpinned inside every cell); a single CUDA field (inferable from
`torch: 2.3.1+cu121`); **the git commit** (only content hashes stand in for it).

## Defects noticed on the way

- The manifest's `train_curve_rows` / `eval_curve_rows` hardcode `train.csv` / `eval.csv` and read
  **0** for `idaac` and `ibac_sni` although 26 and 293 real rows exist under `progress-*.csv` and
  `log.csv` — two fields for one fact, disagreeing.
- `idaac`'s dense training rows carry `phase="eval"`.
