# The banked ppg 600k result is seed 1, which the production schedule does not name

The parent session reported this, and it is checked here from the artifacts. Anything that joins
records to `production-schedule-v100.json` by seed will not find ppg.

## Status

**Resolved as a fact.** Whether it matters statistically is out of this bundle's scope. The seed
was fixed before the run and not selected on outcome, but that is the parent's reading, not
established here.

## Chain

1. **What the schedule names.** Globally it names fact:schedule_seeds (`raw/schedule-now.txt`),
   and the ppg row names fact:ppg_row_seeds (`raw/schedule-ppg-row.txt`).
2. **The schedule already said so at launch.** The revision committed at
   fact:schedule_commit_time (`raw/launch-commit-time.txt`) names
   fact:schedule_seeds_at_launch (`raw/schedule-at-launch.txt`). That is before the run directory
   `card0-20260909-115331` was created at 11:53.
3. **What the run used.** Its launch record says fact:run_seed and fact:run_cells
   (`raw/run-seed.txt`).
4. **What the admissible records carry.** ppg has fact:ppg_records_seed and idaac has
   fact:idaac_records_seed (`raw/committed-seeds.txt`).
5. **Why the schedule names seeds at all.** The trees' own defaults disagree
   (fact:defaults_disagree, `raw/why-named.txt`), so a seed set must be named rather than
   inherited. The ppg run did name one, just not the scheduled one.

## What this does not show

- **Why seed 1 was chosen for that launch.** Nothing captured here records the reason.
- **That seed 1 biases the result.** No evidence either way.
- **The other baselines.** ibac_sni is being run at 101 per the parent session, which is not
  captured here.

## Falsifier

This bundle stops being current if a ppg result at seed 101, 102 or 103 replaces the banked one,
or if the schedule is changed to include 1. `tests/test_evidence_backed_register_rows.py` fails in
either case, so the row gets re-derived.

## Sources

The run record is on the host; everything else is in the repo and its history. Re-take
everything with `bash capture.sh`.
