# Handoff — the part that does NOT survive compaction

Every other document here records **what is true**. This one records **what I was thinking**:
priorities, suspicions I have not proven, why the next step is the next step, branches deliberately
left open, and constraints I am carrying that no gate encodes. Those vanish when a conversation is
compacted, and a file like this makes their survival *closer* to true, not true. Read it as a
colleague's notes, not as a specification.

Last updated **2026-09-17, ~02:20 MSK**, by Claude. The 15:30 version's ordered plan is now mostly
executed, and the section below it is kept because the reasoning still reads correctly — but items
1-3 have happened. Read this block first; it is what changed overnight.

## Morning state, 2026-09-17 07:20 — read this before the 02:20 block below

**Both cells survived the night. Neither will finish, and that was expected rather than a failure.**

| cell | state at 07:20 | what exists |
|---|---|---|
| `ibac_sni` s101 | endpoint grid, native pass ~40/44 | **528 curve rows** (12 stamps, complete) + the native endpoint |
| `idaac` s102 | training COMPLETE ~07:00, now in its curve grid | 11 intermediates + terminal checkpoint, curve ~132 rows |

**The single most useful thing to know: the native endpoint pass alone is a result.** The endpoint
grid runs two passes into two files (`run_probe.sh:1127`), and the native pass is the estimand ibac
actually reports — SAMPLED return. So `528 curve + 44 native endpoint` stands on its own. The `mode`
pass is the extra that makes the cross-family policy-mode block possible; at ~5.7 min/row it needs
~4.2 h more and will not finish before the booking ends. Losing it costs a comparison axis, not the
cell.

**Everything is already banked to the laptop**, so an interruption costs compute and not artifacts:

    scratchpad/fetched/card1-20260916-203537   81 MB  ibac: 528 curve rows, 12 checkpoints, endpoint so far
    scratchpad/fetched/card1-20260916-213222   69 MB  idaac: 11 checkpoints + terminal, curve rows so far

Re-sync before relying on them; rsync moves only the changed `.jsonl` (2.4 MB last time).

**The recovery route is proven, not assumed.** A cell cut mid-grid never writes `result.tgz`, so
collection goes through `assemble_reaped_delivery.py`, the same path used for the reaped idaac s101.
I dry-ran it at 07:05 against the banked ibac copy: 528 rows assembled, correctly sourced, every row
marked `_assembled_after_reaping`. Use it rather than inventing something:

```bash
# 1. rebuild the delivery the cell never got to assemble. --out is NOT a free choice: it must be
#    the exact path collect-host-run.sh reads (collect-host-run.sh:62).
python scripts/assemble_reaped_delivery.py ./fetched/card1-20260916-203537 \
  --out ./fetched/card1-20260916-203537/native-out/records_delivery.jsonl \
  --reason "<why the cell was cut>"
# 2. collect it. The flag is REQUIRED -- without it the collector refuses a run with no completion
#    marker, and with it the collector re-checks that EVERY row carries _assembled_after_reaping.
NATIVE_ACCEPT_WATCH_STOP=1 bash datasphere/native/collect-host-run.sh ibac_sni \
  ./fetched/card1-20260916-203537
```

[Claude 2026-09-17] Both details are corrections to what this section said an hour earlier. I had
written `--out <bundle>.jsonl` and omitted the flag, and either would have failed at collection.
`collect-host-run.sh:105-106` prints this exact two-line recipe when it refuses, so the script
already knew; I had not read that far. If you hit a refusal here, read its stderr rather than
guessing — it names the commands.

**idaac has no 600,064 checkpoint and that is correct.** Its last logged update is 288 at step
591,872, so the 50k cadence boundary was never crossed again; intermediates stop at 550,912 and the
terminal `agent-robosuite:Door-idaac-s102.pt` is the only artifact for the final policy. It reads as
a missing file if you do not know it is expected.

**Card 1 is now in a state with no yield capability at all.** Both cells are past training, and
`run_probe.sh:197` polls the sentinel only while the training PID lives. Our combined hold is
1,640 MiB of 32,494, so we are unlikely to be what crowds a co-tenant — but the honest claim is
"unlikely to matter", not "protected", and handing the card back is now a manual act. Free was 6,944
at 07:06, having widened from 4,956 when idaac left training and released its EGL contexts.

## Overnight, 2026-09-16 20:35 → 2026-09-17 02:20

**Two cells are on card 1 at once, deliberately, and the packing was measured rather than assumed.**

- `ibac_sni` s101 **finished training** at 21:19, F 600,064, in **44 minutes of wall clock**
  [corrected 2026-09-17: 44 minutes is counted from the 20:35 launch and includes ~13 minutes of
  in-container bootstrap; `time -v` in its `training.log` gives 31 min 32 s of training]. That is
  the first ibac cell ever to complete a 600k run, and it breaks the cell-cost model this project
  has been planning against: the model says training is 4.95 h and evaluation 4.6-5.5 h. For an
  on-policy family at procs=16 training is ~45 minutes and the **in-cell grid is the whole cost**
  (3,476 episodes, 13 stamps). If that generalises to ppg and ctrl, the campaign's bottleneck is
  evaluation, not training, and the planning arithmetic in §9 should be re-derived per family.
- On entering the grid its card delta fell **7,421 → 839 MiB**, matching the separately measured 841
  MiB eval-cell figure. The 16 EGL contexts really do go away at `num_envs=1`. I had said I would
  check that against the card rather than assume it; it held.
- `idaac` s102 was launched **from zero** at 21:32 onto the same card, since idaac cannot resume.
  At 02:15 it is at step 395,264 of 600,000 with 7 checkpoints already retained.
- **Packing ratio r = 0.90** (ibac eval 1.872 → 1.680 log-lines/min), against the runbook's `r<0.5`
  "packing loses" threshold. `docker stats` shows each cell at ~1 core, not sixteen. A load average
  of 42.67 on this 16-core host was **other people's jobs**, not ours — check `docker stats` before
  concluding anything from `loadavg` here.

**The co-tenant is back and the margin is thin.** At 02:15 `rlvigen_kalugin_df` holds 22,536 MiB in
two processes on card 1; ours are idaac 2,640 and ibac 831; free is **4,950 against the 4,000 floor**.
I decided not to intervene, and the reason is structural rather than optimistic:
`run_probe.sh:197` polls the yield sentinel only `while kill -0 "$training_pid"`. ibac's training PID
exited at 21:19, so **ibac's in-cell grid does not obey the sentinel**; idaac, still training, does.
If free crosses the floor, idaac is stood down and ibac's grid continues untouched — which is the
sacrifice ordering I would have chosen by hand. Do not "fix" this by stopping idaac early.

**What to do when ibac's result lands** (`ibac_sni-s101-prod-result.tgz`, estimated ~09:20 on 09-17,
watch budget expires 04:43 on 09-18 so there is slack): collect, ledger, bind — and expect the
**endpoint rows to grade UNVERIFIABLE**. That is not a defect to chase at collection time. It is
understood and written up in `results/evidence/ibac-endpoint-weights-equal-frame-600064/`: ibac's
terminal `snapshot.pt` is not byte-identical to `model_600064.pt` because the terminal write happens
with the model back on CUDA, but all 37 parameter tensors are bitwise equal, so the endpoint really
does measure the 600,064-frame policy. The auditor indexes by file hash and cannot see that.

**The exact collection sequence for ibac, worked out in advance so the morning is mechanical.**
ibac differs from idaac in one way that matters here: idaac's checkpoints live under `native-work/`,
which the documented rsync EXCLUDES, so auditing its frame labels needed a second fetch. ibac's
retained checkpoints are under `native-out/cells/ibac_sni-s101/checkpoints/` (twelve files, ~4.6 MB
each), so the standard fetch already carries them and the provenance bind needs no extra transfer.

```bash
rsync -a --exclude 'native-work' \
  varaksin_as@100.98.2.11:'~/rlvigen-runs/card1-20260916-203537' ./fetched/
python scripts/record_host_run.py card1-20260916-203537 --update-status --status completed \
  --note "<what actually happened>"
bash datasphere/native/collect-host-run.sh ibac_sni ./fetched/card1-20260916-203537
# [corrected 2026-09-17] a populate_evaluator_ledger.py line stood here; never run it on a production
# run (OPERATOR-GUIDE §8 item 3). The provenance audit also needs the records file as its argument.
python scripts/audit_record_frame_provenance.py results/records/card1-20260916-203537__records.jsonl \
  --checkpoints ./fetched/card1-20260916-203537/native-out/cells/ibac_sni-s101/checkpoints
python scripts/campaign_status.py
python scripts/production_gates.py | tail -3
```

`--update-status` now works without the run directory (it was changed on 2026-09-16 for exactly
this), so the status can be moved from `running` to a terminal value from the laptop.

Expect the curve rows to grade CORROBORATED and the endpoint rows UNVERIFIABLE. Do not treat the
second as a defect to chase — see the bundle named above.

**A suspicion I did not chase.** A weight-level hash in `audit_record_frame_provenance.py` would tie
those two files automatically and would subsume the byte-alias route. I left it out because it needs
torch and each family's model class importable at audit time, which the auditor does not currently
require. If someone decides that cost is acceptable, ibac's endpoint and ppg's 88 both move off
UNVERIFIABLE for the right reason.

**Three of my own instruments were wrong tonight**, which is the recurring lesson rather than a new
one. The monitor read idaac at "0%" for 4.5 hours because `train/total_num_steps | 3.71e+05` is
scientific notation and the regex captured the leading `3`. `watch_policy_health.py` ignored ibac's
actual `lns` field while I had written "ibac never logs log_std" into three places. And two live
scripts still carried a claim I had already retracted elsewhere. Validate against the artifact, not
against the last thing you wrote.

---

The previous version (2026-09-07) planned the v196 attestation wave; that wave landed, the host ran,
and two 600k baselines are banked.

## What I would do next, and why that order

1. **Finish idaac's curve and collect it.** 7 of 11 stamps at last check, 4 cells in flight. This is
   the cheapest remaining increment: it costs no training, and it gives idaac the complete
   endpoint+curve pair that ppg already has. The sweep skips finished stamps, so restarting it is
   free — do that rather than reasoning about whether it died.
2. **Let idaac s102 finish.** It is the second seed, giving `{101, 102}` against the schedule's
   `[101, 102, 103]`, and it is the only cell that moves `campaign_status` off 1-of-36.
3. **ibac_sni, but only into a card that has been free for a while.** It needs roughly 11 GiB that
   *stays*. Four of its five failures were the memory floor firing on a card a colleague was
   holding — not an ibac_sni defect, a scheduling fact. Launching into a fresh vacancy is what
   failed; I did it once today and the co-tenant returned within minutes.
4. **Then a third seed, not a new baseline.** Three seeds of two baselines is a reportable result
   under the n=3 policy; one seed of six baselines is not. I would resist the pull toward breadth.

## The peer session ended, and one thing it offered is now unowned

A second agent (`foundation-verification-audit-prod ⑂`) worked this tree in parallel for ~3 hours
and exited cleanly at ~16:20 — **nothing uncommitted, nothing unpushed**, which is worth saying
because the known failure mode with parallel sessions here is the opposite. Its work is in the
history: the evidence bundles under `results/evidence/`, `docs/resolved-register.json` rows
including `vram-ours-peak-sums-the-whole-card`, and the ppg endpoint double-run analysis.

**It had offered to do one thing it did not get to**: a curve join of idaac's rows against the 11
intermediate checkpoints, which it said were already hashed in its bundle. Those rows landed at
16:00 (`reeval-v214-idaac-curve__records.jsonl`, 484 rows). If that join matters, it is unowned.

Two of its catches are load-bearing and should not be re-litigated: `measure_vram_bounds.py` summed
every compute process on the card under a field named `ours_peak_mib`, and the ppg endpoint ran
twice to completion so mode rows could be paired — which is what refuted "the nine mode baselines
are unaffected".

## Suspicions I have NOT proven

- **The evaluator-nondeterminism mechanism.** `VGBWrapper`'s `random_state` drives
  texture/colour/lighting, is seeded once at construction and never re-seeded per episode, and the
  regimes that reproduce **0/200** episodes are exactly the ones that randomise appearance. That is
  suggestive and it is not sufficient: a once-seeded generator consumed identically still yields
  identical sequences, so something must first perturb the *draw count*. My candidate is GPU
  floating-point nondeterminism (cuDNN algorithm selection) changing an action slightly, hence an
  episode's length, hence RNG consumption. **Cheap discriminating experiment, not yet run:** one
  eval-medium scene twice in one process with `torch.use_deterministic_algorithms(True)` and
  `CUBLAS_WORKSPACE_CONFIG` set. Reproduces 200/200 → it is GPU nondeterminism; still diverges → it
  is the RNG object, and `random_state` needs per-episode seeding.
- **Whether `rlvigen_kalugin_df`'s cycling is a schedule or a job loop.** It releases ~21.3 GiB and
  reclaims it within tens of minutes, repeatedly. If it is a loop with a period, a launch could be
  timed against it. I have only watched it, never characterised it, and I would not ask its owner.
- **[RESOLVED 20:49] Whether ibac_sni at `procs=16` is actually large or merely unlucky.** Large, and precisely: 7,421 MiB total (2,199 compute + 5,222 EGL), needing 11,421 with the floor against 7,194 of durable capacity beside card 1's co-tenant. Not unlucky. Its only surviving figure
  is a ~6.6 GiB *lower* bound taken 42 s in while its process count was still climbing 2 → 20. It
  may be much larger. I would not schedule it beside anything until one clean run measures it.

## Constraints I am carrying that no gate encodes

- **The second cell's real cost is the first cell.** On a shared card, sizing a launch against
  *current* free memory rather than against the co-tenant's return is how you lose the run you
  already have. This is written into `CURRENT-STATE` §7 with the arithmetic, because I nearly got
  it wrong and only caught it by computing the return case.
- **A number in a comment is not a measurement.** Three wrong VRAM figures in one day, one of which
  sized a production launch. I now treat any number whose provenance I cannot name as unknown.
- **Never write to a script that may be executing.** Five occurrences in this project. `bash` reads
  by byte offset, so the error is a syntax error at an innocent line while `bash -n` passes — the
  mtime is the diagnostic, not the contents.
- **`pgrep -f <script>` matches your own ssh shell.** `pkill -f` killed my session once and
  `pgrep -fc` self-counted into three duplicate sweeps. Resolve PIDs from `/proc/<pid>/cmdline`
  `argv[1]`; kill by PID.
- **Never grep a run directory for a marker.** `native-work/` contains `run_probe.sh`, which
  contains the marker strings. I reported a healthy cell as FAILED this way.

## Branches deliberately left open

- **ppg's seed set.** Implemented as `{1, 102, 103}`; the alternative is re-running at 101 for eight
  GPU-hours to buy a number we have. Owner's call, and the tracker reads 1-of-36 until it is made.
- **`ctrl`'s floor.** At 32,435 MiB it cannot satisfy peak-plus-floor on a 32,494 MiB card at all.
  Running it requires an empty card *and* an explicit decision to lower or waive the 4,000 MiB floor
  — which is the one thing the operating rules say never to do. I have not proposed a resolution
  because I think it needs the owner.
- **Whether the guide should absorb `production-host/`'s 33 notes or keep pointing at them.** I kept
  them separate: the guide is procedure, the directory is the reasoning and the incident record.
  Merging would produce one unreadable file; the cost is that a reader must follow links.

## What I am least sure about

- **That my enumeration of operator needs is the right enumeration.** `scripts/operator_readiness.py`
  checks 56 needs route somewhere real, and it passes — but the list is mine. It fits on one screen
  deliberately, so that a person can disagree with the *set* rather than audit the checking.
- **That the 732 admissible rows are as clean as they look.** They pass every mechanical gate. But
  the evaluator reproduces only ~35% of episodes between identical invocations and nobody knows why,
  and "within noise" is a statement about magnitude, not about understanding.
- **Whether I have been too willing to build instruments.** Three of my own checks were defective
  today in the same way as the defect they were meant to catch: one read text I had inserted myself,
  one cut sections at a shell comment, one summed a colleague's memory under a field named "ours".
  The pattern is that a new instrument is trusted before it has ever failed. I now try to break each
  one deliberately before relying on it; I do not think I do this consistently enough.
