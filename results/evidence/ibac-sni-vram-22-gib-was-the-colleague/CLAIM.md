# The "22.1 GiB" ibac_sni VRAM figure is mostly a colleague's memory

On 16 Sep the production session reported ibac_sni at procs=16 as occupying 22,675 MiB. It
parked the cell until a card has 26.7 GB free and wrote the figure into
`measured-vram-bounds.json`. The figure comes from `scripts/measure_vram_bounds.py` as of
`bb191cd`, and that revision sums every compute process on the card.

- **The sum includes 21,300 MiB of two processes** that belong to whatever else held card 1.
  Everything captured points to `rlvigen_kalugin_df`.
- **The cell itself had reached about 6.6 GB when the floor stood it down, 42 s in, still
  growing.** Its full footprint is unmeasured.

## Status

**Resolved.** The 22,675 figure is not ours, and the script's sum is unfiltered.

**Traced only.** The true procs=16 footprint is unknown. About 6.6 GB is a lower bound.

## Chain

1. **The number, reproduced.**
   - The `bb191cd` script, run over exactly the captured `resources.json` (`raw/resources.txt`),
     reports fact:reported_ours_mib MiB "ours", i.e. fact:reported_ours_gib
     (`raw/script-report.txt`).
   - Its loop sums every entry of `gpu_compute_processes` (fact:sums_all_processes,
     `raw/script-sum.txt`), although its docstring says the sum is over the cell's own process
     tree (`raw/script-claim.txt`).
2. **What the samples contain** (`raw/decompose.txt`).
   - There are 38 samples over fact:sampler_span_s s, all on card fact:card. That UUID is host
     card 1 (fact:card1_uuid, `raw/card-map.txt`).
   - The compute processes are two at 10,650 MiB and three small ones, which make up the sum:
     fact:colleague_sized_pids.
   - No compute pid is in the cell's process tree (fact:no_compute_pid_in_tree). The tree's pids
     are container-namespace, so the script could not have matched them anyway.
3. **Whose the two 10,650 MiB processes are.**
   - At the first sample, the card total minus our two 308 MiB processes leaves
     fact:rest_of_card_at_start_mib.
   - That is exactly what the on-host logger reads for card 1 in the surrounding minutes, where it
     resolves the card's two processes to the colleague's container:
     fact:colleague_alone_mib (`raw/occupancy.txt`).
   - A direct `/proc/<pid>/cgroup` lookup at about 14:40 resolved pid 536927 to
     `rlvigen_kalugin_df`. **That lookup was not captured before the process exited**, so it is an
     observation, not evidence here. The arithmetic above is the evidence.
4. **What the cell itself used.**
   - The card grew fact:card_growth while the cell's process count went fact:still_starting.
   - If the rest of the card stayed constant, ours was fact:ours_at_kill_if_rest_constant_mib MiB
     at the last sample.
   - EGL render contexts are not compute processes, so only the card delta can see them.
   - The memory floor stood the cell down (fact:s101_reason, `raw/stop.txt`) at
     fact:s101_yield_time (`raw/yield-time.txt`), still initialising.
5. **The number before this one was not measured either.** The waiter's "measured ~15 GiB"
   (fact:waiter_claimed_gib, `raw/unmeasured-waiter-figure.txt`) has no measurement behind it.

## What this does not show

- **ibac_sni's steady-state footprint at procs=16.** Getting it needs a run that is not stood down
  in its first minute.
- **That the rest of the card stayed constant during the 42 s.** The logger samples every 60 s,
  and our window fell between two of its samples. Its readings on either side are 22,836 and
  22,837.
- **Which other entries of `measured-vram-bounds.json` are inflated the same way.** Any entry
  measured on a shared card is suspect. Entries measured on an exclusive card cannot include
  co-tenants, but they may miss EGL memory.

## What follows

- Treat the parking rule "26.7 GB free" as resting on a wrong number, not as a measured bound.
  The need is unknown, and at least 6.6 GB.
- `measure_vram_bounds.py` needs an attribution that is valid on a shared card: the card delta
  from arm time, flagged when co-tenants move, and a "not at steady state" flag when the process
  count is still rising at the last sample. The production session owns that fix.

## Falsifier

- A `resources.json` from this cell whose two 10,650 MiB pids are in its own tree.
- A card-1 reading in which the rest of the card was not about 22.8 GB at 14:26-14:28.

## Sources

The sources are:
- the host cell `~/rlvigen-runs/card1-20260916-141636`;
- `gpu-occupancy.log`, which is still appended to and so reads DRIFT on recheck;
- `ibac-waiter.log`;
- the script at `bb191cd`.

Re-take everything with `EVIDENCE_WORK=<dir> bash capture.sh`.
