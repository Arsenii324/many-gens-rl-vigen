# A cell stops obeying the yield sentinel when its training process exits

`notes/model/STOP-MECHANISMS.md` row 2 said "only a TRAINING cell obeys it", contrasting training
cells with dedicated eval cells. On 2026-09-17 that turned out to be the coarser half of the truth,
and the finer half is now demonstrated rather than read out of the code: the poller's loop is
`while kill -0 "$training_pid"` (`run_probe.sh:196`), so a cell that has finished training and moved
into its in-cell grid ignores the sentinel too. The distinction is **before vs after the training
PID exits, inside one cell.**

## Status

**Resolved, by an unplanned natural experiment.** Three of our cells shared card 1 when the co-tenant
`rlvigen_kalugin_df` reclaimed ~22.2 GiB. Every cell's watcher wrote a sentinel within 33 seconds.
Exactly one cell died: the only one still training.

| cell | phase | sentinel written | free at that moment | outcome |
|---|---|---|---|---|
| `ibac_sni` s101 | endpoint grid | 08:01:02 | fact:grid_ibac_free_mib MiB | **ignored it, still running** |
| `ibac_sni` s102 | **training** | 08:01:33 | fact:training_cell_free_mib MiB | **obeyed it, cell stopped** |
| `idaac` s102 | curve grid | 08:01:35 | fact:grid_idaac_free_mib MiB | **ignored it, still running** |

## Chain

1. **All three watchers fired on the same event.** `raw/sentinel-grid-ibac.txt`,
   `raw/sentinel-training-cell.txt` and `raw/sentinel-grid-idaac.txt` are the three sentinel files,
   written 08:01:02, 08:01:33 and 08:01:35, each naming the 4000 MiB floor. Free memory is different
   in each because the card was collapsing while they sampled: 2365, 75 and 321 MiB.
2. **Only the training cell acted.** `raw/training-cell-stopped.txt` is that cell's own log
   announcing fact:training_cell_marker and stopping.
3. **The other two did not.** `raw/grids-still-running.txt` was taken after the event and shows both
   grid containers still up. They have continued producing rows since.

## What this does not show

It does not show that ignoring the sentinel is safe. It is tolerable here only because a grid cell's
footprint is small — about 820 MiB against a training cell's 2,600–7,400 — so our grids were not
what crowded the co-tenant. On a card where every cell of ours was past training, **nothing of ours
could yield at all**, and handing the card back would be a manual act.

It also does not show that the resulting sacrifice order is designed. It follows from PID lifetime,
not from a policy: the cell that dies is whichever one happens to still be training. That was the
right outcome here — the grid cells had already banked their training — but a different pairing
could get the wrong one for the same reason.

## Falsifier

Find a cell that was past training and stopped on a sentinel anyway, or a still-training cell that
ignored one. Either would mean the poller's lifetime is not what governs this. Concretely: if a
future run shows `NATIVE_CELL_YIELDED` in a log whose training had already completed, this claim is
wrong.

A weaker one, not needing the host: if `run_probe.sh:196` ever stops keying its loop on
`kill -0 "$training_pid"`, the mechanism behind the table above has changed and the rows say nothing
about the new code.

## Why it was worth capturing

The claim was already written into `STOP-MECHANISMS.md` at about 04:10 the same night, from reading
the source. Four hours later the host produced the experiment on its own. A documented claim that
survives contact with an unplanned event is worth more than the same sentence derived twice from the
same file, which is the failure mode this project keeps finding in its own checks.
