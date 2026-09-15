# Endgame plan — the booking ends 2026-09-16 23:59 MSK

Written 2026-09-15 15:45 MSK, with **32.2 hours of booking left** and the node shared by four
people. This is a triage plan, not a campaign plan, and it says so up front.

## The arithmetic that decides everything

`plan_production` costs the full campaign at **800.9 job-hours = 33.4 card-days**. Even both cards
free for the whole remaining window is ~2.7 card-days. **We can afford roughly 8% of the campaign.**
So the question is not "how do we run it" but "what is the most valuable thing that fits".

## What we have that costs no training

Two full-length runs are already trained and their checkpoints are retained and verified:

| run | baseline | frames | checkpoints | verified |
|---|---|---|---|---|
| `card0-20260909-115331` | ppg, seed 1 | 600,064 | 14 (13 `.jd` + terminal) | **14/14 sha-match their rows** |
| `card0-20260909-035152` | idaac, seed 101 | 598,016 | 12 | not yet sha-checked |

Both are superseded only by evaluator REVISION (`16e960b1f446` against today's `248751f7caca` /
`1b092f978fdc`), not by a change of estimand: every offline-eval row carries
`eval_policy_mode=sample` and ppg is still `sample` today.

**Re-evaluating them costs evaluation only.** That is the highest value per GPU-hour available:
it converts training compute already spent into admissible results, and it exercises the full
production eval shape (curve → endpoint → delivery → ledger) as a by-product.

## Order of work

1. **SMOKE / differential** — re-measure ONE cell whose old value is known:
   `train / scene 0 / 20 episodes / endpoint / native` → **26.099544954299926**.
   Episode seeds are content-addressed, so an identical number proves the closure change did not
   move the measurement, and a different one names what moved. Decides the whole question in ~20
   episodes. *(launched 15:40 MSK on card 1)*
2. **ppg endpoint grid** — 4 regimes x 11 scene sets x 20 episodes x 2 policy modes = 1,760
   episodes, ~5.9 h. Produces the headline number for one baseline at full length.
3. **idaac completion** — its run needs only the **3 missing eval-hard mode rows** that made it
   `paired=False`; not the other 566, and no retraining.
4. **ppg curve** — 13 stamps x 44 rows x 3 episodes = 1,716 episodes, ~5.7 h. Descriptive, not the
   headline, so it yields to anything above it.
5. Only if the window still allows: one NEW training cell, cheapest-but-most-exercising.

## Hard constraints, not preferences

- **Never CUDA OOM, including spikes, including other people's jobs.** The per-process VRAM cap
  **does not bind** -- all nine family launchers overwrite `PYTHONPATH`, and ppg once reached
  26,653 MiB under a 10,240 MiB cap. So our footprint is observed, not bounded, and the 4000 MiB
  floor reacts only after memory is taken. **Therefore: no co-occupancy of an occupied card.**
- **Card 1 is not ours by default.** `launch-card-cell.sh` refuses it unless
  `NATIVE_YIELD_ON_PROCESSES=1`, and arms the PID-based neighbour yield alongside the memory floor.
- **Nothing host-wide.** No pip, apt, driver or global state on the host; docker and trivial shell
  only, including inside any script called by a script.
- **No silent timer may end a run.** The watch budget was sized from host defaults that
  underestimated the real grid by 11x; that is fixed (it now reads `production-env`), but the
  watches still kill without warning, and a reaped cell never reaches `collect_record_delivery`.

## What would make me stop and re-plan

- The smoke cell returning a value **different** from 26.099544954299926 -- that reopens the
  estimand question and nothing else should run until it is understood.
- Either card acquiring another tenant -- we stand down rather than share.
- Any eval whose measured seconds-per-episode is far from the 12 s the budget assumes.
