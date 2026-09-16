# ibac_sni's three production stops on 16 Sep: two memory-floor yields and one worker death

None of the three was the process-count yield. The project's record says the first one was.

## Status

- **Resolved** for what fired in each attempt. The sentinel text and the trainer's exit decide it.
- **Traced** for attempt 2's root cause: an env worker died during the first reset with
  `EGL_NOT_INITIALIZED`, and why is not established.
- **Correction.** `notes/model/STOP-MECHANISMS.md` row 2 and commit `bb05db6` attribute attempt 1
  to `--yield-on-processes`. The sentinel shows the memory floor fired. The row is corrected in
  place, with the reversal left visible.

## Chain

1. **How to read a sentinel.** The watcher writes `compute processes went ...` when the
   process-count branch fires, and `free memory ... below the ... floor` otherwise
   (fact:floor_text_implies_not_process_branch, `raw/watcher-branch.txt`). So the floor text means
   the process branch did not fire at that check.
2. **Attempt 1, card 0.**
   - The sentinel reads fact:a1_reason (`raw/a1-stop.txt`), at fact:a1_yield_time
     (`raw/times.txt`), with fact:a1_procs_on_card compute processes on the card.
   - The occupancy log (`raw/a1-occupancy.txt`) shows who held the card at 01:03: colleagues
     fact:a1_colleagues, one other cell of ours, and ibac_sni's three processes. That is
     fact:a1_card_used_mib MiB used of 32,768.
   - No PPO update had been logged yet (fact:a1_updates_logged).
   - The floor stood our cell down on a card that two colleagues and our own second cell were
     already using. That is its purpose.
   - The project's record says otherwise: fact:stated_cause (`raw/stated-cause.txt`), and
     fact:row2_claim (`raw/stated-row.txt`).
3. **Attempt 2, card 0.**
   - No sentinel. The trainer exited on its own: fact:a2_no_sentinel (`raw/a2-stop.txt`).
   - It died fact:a2_wall_clock after start, with fact:a2_error on a worker pipe during the first
     `reset()` and fact:a2_egl in the render context (`raw/a2-death.txt`).
   - The card held about 28 GB at the time (`raw/a2-occupancy.txt`).
4. **Attempt 3, card 1.**
   - The sentinel reads fact:a3_reason at fact:a3_yield_time (`raw/a3-stop.txt`). The cell had
     reached fact:a3_last_frame (`raw/a3-progress.txt`).
   - The occupancy log (`raw/a3-occupancy.txt`) shows the sequence:
     - ours alone at fact:a3_ours_alone_mib MiB;
     - a minute later fact:a3_colleague_arrives is on the card;
     - after we stood down, the colleague holds fact:a3_after_we_left_mib MiB.
   - This is the case `d0899fb` describes, and the evidence agrees with it.
5. **What replaced blind retries.** A waiter launches only when a card has
   fact:waiter_threshold_mib MiB free (`raw/next-attempt.txt`). It launched a fourth attempt on
   card 1 at 14:16 MSK, outside this bundle's scope.

## What this does not show

- **Whether `--yield-on-processes` was armed in attempt 1.** The watcher's arm-time output is not
  in `job.log`. If it was armed, it had not fired by the time the floor did. Six processes against
  a baseline of three plus one of ours would have counted as crowded, so it may have been about to
  fire.
- **Why attempt 2's worker lost its EGL display.** Memory pressure from 16 EGL contexts on a
  28 GB-occupied card is plausible, and the later 14-18 GB launch thresholds assume it, but this
  bundle does not establish it.
- **That the colleague in attempt 3 would have been harmed had we stayed.** Its growth to
  32,344 MiB once we left is consistent with it taking what was free. Nothing here shows it needed
  that memory.
- **Anything about the process-count yield firing on 9 Sep.** It did fire then, on ppg/idaac
  cells (for example `card0-20260909-012345`). That history is not captured here.

## Falsifier

- A sentinel from attempt 1 reading `compute processes went ...`. The captured `job.log` line
  rules that out unless the file changes.
- An occupancy log showing card 1 without `rlvigen_kalugin_df` at 12:11-12:12.

`gpu-occupancy.log` is still being appended, so `recheck_evidence.py` reports it as DRIFT. The
captured lines are what matters.

## Sources

The host files are under `~/rlvigen-runs/`: the three run directories, `gpu-occupancy.log` and
`ibac-waiter.log`. Re-take everything with `bash capture.sh`.
