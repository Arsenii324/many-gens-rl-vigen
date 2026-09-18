# Adversarial review of the operator package — what can still go wrong, and what that implies

**2026-09-18, 11:20 MSK.** Written before a context compaction, because most of what follows is
*practical* knowledge — which guard actually fires, what was tried and abandoned, where a check
would pass vacuously — and that is the first thing lost when a conversation is summarised. Conclusions
survive compaction; the reasoning that makes them trustworthy does not.

The question asked: **is this very well prepared for an operator to run?** The honest split is in
[`OPERATOR-GUIDE.md`](OPERATOR-GUIDE.md) §11. This file is the adversarial half.

---

## 1. Failure scenarios, worst first

### 1a. Could harm another group — the one class the standing rule forbids outright

| scenario | why it is possible | state |
|---|---|---|
| **Host RAM exhaustion with a co-tenant present.** An RL-ViGen cell is ~40 GiB resident (36.7 GiB replay at the v100 cap + 3.3 GiB peak). The host has 125 GiB, with 43 GiB in use by others on 18 Sep. If their job grows while we hold 40 GiB, the kernel OOM killer picks a victim and it may be theirs. | `launch-card-cell.sh` and `run_on_production_host.sh` gate **VRAM and disk only**. Nothing reads `MemAvailable`. | **Partly closed 2026-09-18**: `wait-and-train-v4.sh` now takes `MIN_RAM_GIB` and refuses the launch below it (armed at 55 GiB for `svea`). A cell launched **by hand**, bypassing the waiter, is still unguarded. |
| **Two RL-ViGen cells packed.** 80 GiB of replay on a 125 GiB host. | §5.3 warns; nothing refuses. | Open. The waiter refuses while any `cell-c*` container is up, so the automated path cannot do it; a manual second launch can. |
| **Our own growth starving a co-tenant's allocator** between 20 s polls. | The memory floor is cooperative and polls; an atomic allocation can fail before the next sample. | Open by design, documented in §5.1. Reduced by the ten-minute vacancy rule, not removed. |

### 1b. Wastes a window — the scarcest resource (the card was free once in 13 hours, for 20 minutes)

- **The waiter fires exactly once.** After any launch, success or a 24-second EGL death, `wait-and-train-v4.sh` exits. A cell that dies at minute one leaves no waiter, so the rest of the window goes unused. **Open**, and the cheapest real improvement left.
- ~~A mistyped wrapper or missing payload waits ten hours and then fails at the instant of launch.~~ **Closed 2026-09-18**: validated at arm time; all five refusal branches exercised with an isolated lock (`WAITER_LOCK`, added because the hardcoded path made every test refuse at the lock and reach none of the branches it meant to test).
- **`svea`'s bootstrap clones RL-ViGen from GitHub at run time** — its payload deliberately omits that tree. A network failure at 03:00 costs the window. Measured 13.7 MB/s on 18 Sep, so it is fast, not absent.
- **The Places365 loader step is unexecuted and runs ~20 minutes in**, after the bootstrap. `configure_places365_val.py` writes loader config while the corpus is mounted `:ro`. If it attempts a write under `/opt/places365`, the cell dies late. **This is the single most likely first-run failure.**

### 1c. Nobody notices

- **Who watches the watcher.** The waiter's heartbeat goes to a log that only a tailing Monitor reads. Across a compaction or a session change, nothing reads it, and a dead waiter looks exactly like a quiet one. The heartbeat makes this *diagnosable*, not *detected*.
- **`flock` descriptors are inherited by children.** It bit three scripts on 18 Sep — `wait-and-train-v3.sh` (lock held 14 h past its cell by the reaper's `sleep`), v4 on restart, and `gpu-occupancy-log.sh`, where killing and restarting two seconds apart left the host with **no logger at all**. A waiter with a stale log refuses, correctly, so that would have been a silent night. Rule: wait for the **lock**, not the process, and verify with `pgrep` afterwards.

### 1d. Corrupts a result quietly

- **`production_reading.py` skips rows silently** — six bare `continue`s. A family whose rows lack `conventions.eval_policy_mode` would vanish from the headline with no warning. **Open**; the fix is to count and print what was skipped ("a check needs its comparison count").
- **Endpoint-frame mismatch.** `campaign_status` calls a cell DONE only at the scheduled endpoint. `ibac_sni` lands at 600,064, `rlvigen` should land at 600,000. A cell that lands elsewhere reads as RUNNING forever while looking complete on disk.
- **Any edit to a hashed file mid-campaign** moves every family's evaluator revision and supersedes new records. Comment bytes count. Gates catch it; nothing prevents it.
- **Double measurement of one checkpoint.** `idaac` s101 has both an in-cell grid and an offline re-evaluation for the same frame. `production_reading.py` now averages within a scene first, so a repeat is a better estimate rather than an extra scene — **other consumers were not audited for this.**

## 2. What I would verify next, in order

1. **The first `svea` cell is the integration test** — it exercises the waiter's launch branch, `train-production-cell-v6.sh` and the Places365 loader in one shot, none of which has ever run. Watch against fixed checkpoints, not vibes: container up by minute 1; no `EGL_NOT_INITIALIZED` by minute 2; GPU memory held by minute 25; Places365 loader lines and first `F` rows by minute 30; `free -g` above 40 GiB at minutes 5, 30, 120. A miss at any checkpoint → stop deliberately and record, rather than discover at hour nine.
2. **Make the waiter survive a fast failure** (re-arm if the launcher exits non-zero within a few minutes and the card is still clear).
3. **Count the skipped rows** in `production_reading.py`.
4. **Per cell, unchanged:** record at launch, `watch-cell.sh` armed, `BP=` set at collection, MISMATCHED 0, ledger `--strict` 0, `campaign_status` moves.
5. **At the end:** gates 0 fail, full suite green, every reported number regenerable by `production_reading.py --retention`.

## 3. The mechanism that would help an operator most, and is not yet written

Per stage: **target state · the artifact it leaves (exact path) · who consumes it · the one command that proves it · how to redo only that stage · what it does NOT leave.** The last two columns are what turn "it broke" into "redo stage 4".

And a companion list of **state that is not in any file**, because that is where entangled state hides and where three of today's defects lived:

- the pulled image digest and docker layer cache (a cell's environment is rebuilt inside it every launch);
- the host's own checkout `~/rlvigen-work/repo`, which is at commit `672202d` (9 Sep) with 34 locally changed paths — **its git log is not evidence of what runs**; compare hashes;
- detached processes holding `flock`s (§1c);
- files written by containers as **root**, which the operator cannot delete or even list without another container;
- `~/.prod-monitor-seen`, which makes `NEW-GROUP` fire once per group ever.

**What I would not add:** a new "check every stage" script. Untested checkers here have passed vacuously three times, and a fresh one on the critical path is a liability, not a safeguard. The table should point at commands that already exist and have already been run.
