# What I know that the files do not say

**2026-09-09, written deliberately at the end of context.** The facts of this session are committed
and will survive. This is the layer that will not: which findings were systematic and which were
luck, what nearly went wrong and didn't, and what I would actually watch. Written as a supervisor's
note, not a summary.

---

## 1. Every wrong claim I made had one shape

Four times I asserted a bound from samples taken entirely inside one regime, and four times the
regime changed:

- "`ppg` plateaus at 8207 MiB" — 30 minutes of samples, all within its *policy* phase. It reaches
  **26653** in the auxiliary phase.
- "Packing does not survive production scale" — measured at 10k frames, asserted for 600k. Wrong,
  and wrong in the direction that discards a real throughput win.
- "Download rate is 395-835 kB/s" — measured before `cudnn`, which arrived at **161.6**.
- "~18 GiB is unexplained" — no per-process data existed, so I theorised for an hour about eager
  reservation and eval subprocesses. **Both guesses were wrong.** One minute of per-process sampling
  answered it.

This is a method failure, not bad luck, and it is the single most useful thing to carry forward.
**Before asserting a bound, name the regime your samples came from and the regime changes that are
possible.** A phase change, a scale change, a slow-network window. I did not do this once
unprompted; the owner caught two of the four.

## 2. What actually found defects, ranked by yield

1. **Direct instrumentation** — per-process GPU memory, `/proc/<pid>/environ`, timestamped log
   deltas. Found the auxiliary-phase spike, and found that the VRAM cap reaches our *monitors* and
   not our *trainer*.
2. **Primary sources** — `raileanu21a-supp.pdf` settled `num_processes` **and** opened the
   action-repeat question from a single read. Derived prose only ever closes questions.
3. **Mutation testing** — two guards I wrote were vacuous until mutated. Assume yours are too.
4. **Reading documents** — found almost nothing directly. Its value was as a pointer to (1) and (2).

The subagent was useful *specifically* because it was told to establish dates and flag contradictions.
A plain "why is X" would have returned the first confident document it found, which in that case was
three days stale.

## 3. The near-misses matter more than the catches

- **If `run_probe.sh` had no renderer check**, we would now have a campaign of `llvmpipe`-rendered
  results that look entirely ordinary. The check is the only reason this is a fixed bug rather than
  a corrupted dataset.
- **If I had not added per-process sampling**, the packing guidance would still be wrong and the
  18 GiB still "unexplained".
- **The ppg frame reconstruction is the one that frightens me.** It would have attached correct
  measurements to wrong frames — off by one save *and* on the wrong cadence — and **nothing
  downstream could ever have detected it.** A record carrying `frame=200000` when the checkpoint was
  at 200704 is not implausible, not malformed, and not checkable after the fact.

## 4. Where I think the real remaining risk is

Not in what is broken. In what is **silently plausible**.

Records carry `frame`, `regime`, `scene_set`, `policy_mode`, `checkpoint_sha256`. The evaluator-
revision machinery guards **code identity** — that the tree which produced a row still exists. It
does **not** guard **label correctness** — that the row's frame is the checkpoint's frame, that its
regime is the regime actually swept. Those are set by shell plumbing, and shell plumbing is where
every defect this session lived.

**The question I would ask next:** given a record, can we verify after the fact that its `frame`
matches the checkpoint it was computed from? Today I believe the answer is no — `checkpoint_sha256`
identifies the file but nothing ties the file to the frame label independently of the code that
wrote both. If that is right, it is a bigger hole than anything fixed today, and it is invisible
precisely because the output is well-formed.

## 5. Workflow rules I would give the next agent

- **Never trust a mechanism's own success message.** `NATIVE_VRAM_CAP_APPLIED` printed for three
  days while the cap reached nothing. Verify the *effect*, externally.
- **When a number surprises you, instrument before theorising.** I lost an hour to inference that
  one minute of measurement settled.
- **`grep '^FAILED'` on pytest output silently matches nothing** (ANSI). I did this four times and
  twice nearly discarded good tests as vacuous. Strip codes first.
- **A filter that exits early kills its producer.** `| head -1` on a two-GPU `nvidia-smi` returned
  141 and aborted the wrapper; awk's `exit` did the same ten lines later.
- **Check the scope of a constant before deriving a budget from it.** `CELL_TIMEOUT_SECONDS` bounds
  training, not the container; my reaper budget covered half a cell's life.
- **A guard scoped to one file is not a guard.** The apostrophe check existed and still missed two
  new instances because it only looked at `run_probe.sh`.

## 6. Where I am genuinely uncertain

Stated because a confident handoff would be the same failure as §1:

- **Whether concurrent overlap is a safe *mode* or I got lucky with timing.** `ppg` training beside
  `idaac` evaluating works right now with ~4.3 GiB free. I have one data point and no theory of the
  worst case. It should not be adopted as a pattern on this evidence.
- **Whether ppg's 26653 MiB is its ceiling.** It is stable across ~40 minutes and one auxiliary
  phase. Later phases may allocate more; I have not seen a second one.
- **Whether the endpoint grid's two policy modes are intended.** `ENDPOINT_EVAL_POLICY_MODES=native,mode`
  comes from the production freeze and doubles the grid's cost. I did not trace why.
- **Whether idaac's `action_repeat=1` should match the source's 4-8.** Filed OPEN. I lean toward it
  being a real question rather than a transcription detail, but Door's horizon and reward structure
  differ enough from Cartpole that I would not guess.

## 7. What to watch operationally

- **The 4.3 GiB free margin.** If it crosses the 4000 MiB floor, `ppg` yields — and `ppg` cannot
  resume, so hours are lost. It has held for ~45 minutes.
- **`collect-host-run.sh` has never run on a real completed cell.** Its five refusals are tested;
  its success path is not.
- **The idaac endpoint grid projects to ~17:10 against an 18:36 reaper.** If the rate drops, that
  margin goes. Everything except the endpoint records is already durable.

## 8. The thing I would say to a supervisor

The instruments in this repo are unusually good and were, in several cases, **the only reason a
defect was a stopped job rather than a silent result**. That is worth protecting specifically: the
renderer check, the endpoint rule, the ledger's stale-revision refusal. Each looks like overhead
until the day it fires.

The opposite is also true and less comfortable: **three of this session's mechanisms reported success
while doing nothing** — the pip cache twice, the VRAM cap for its entire existence. All three were
mine, all three were caught only by measuring the effect rather than reading the log. Assume the
next one exists and has not been caught yet.

---

# Addendum, same day, after the first two production cells completed

§1 above catalogues **one** failure shape — a bound asserted from samples taken inside a single
regime. The hours after it was written produced **two more, both distinct from it and from each
other**, and naming them is worth more than the individual corrections.

## Shape 2: reading a scale as a result

Twice, an hour apart:

- **"`idaac` did not learn Door"** — because its curve ended where it began. A random policy scores
  **2.0** on that axis; `idaac` reached **12-25x** it. The real finding was a *plateau after fast
  early learning*, which is nearly the opposite and far more useful, and it needed one number I had
  not measured.
- **"the gap to RL-ViGen's own algorithms is real"** — reasoning from Figure 22's 0-500 y-axis.
  That is the **plot's range**. Neither vendored PDF reports a numeric Door return anywhere; the
  results live inside figures. The claim had to be withdrawn outright.

**Both errors made our work look worse than the evidence supported.** That is the direction that
survives review, because it reads as appropriate modesty. Watch for it specifically.

The guard is cheap: before writing "X is N% of Y" or "X failed", say what Y *is* and where it came
from. If Y is an axis bound, a configured maximum, or a number never seen reported, the comparison
is not available. And **measure the floor** — a curve without a random baseline cannot distinguish
"did not learn" from "plateaued high".

## Shape 3: claiming novelty I am structurally unable to check

**Three times in one session**, I nearly published as new something the codebase already documented,
in two cases better than I was about to:

- **`eval-hard` above `eval-medium`**, 8 SE apart at every stamp. `rlgen/protocol.py:30-35` already
  said the modes differ in *which* nuisance factors are active rather than in magnitude, that the
  ordering does not imply rank-ordered returns, and that a sibling project saw 3 of 12 ordered.
- **"no durable second location exists on this host"** — `run_on_production_host.sh:405-437` already
  counted filesystems that could hold a result, already drew the second-copy versus
  second-failure-domain distinction, and already called it an owner-level property.
- **A plan item I called unimplemented** that `families.json` already covered.

An agent writing from its own context **cannot** check breadth. "Nobody has noticed this" is not a
claim I can make. `python scripts/where_is_this_decided.py <term>` costs seconds, and when the
codebase already covers it the right output is smaller and better: **cite the existing treatment and
add only the new data point.**

*(It worked once it became a reflex: checking before proposing the `ppo_epoch` 10 → 3 arm found
`bt1djeamji7gilgnndft`, a prior pilot that already tested `ppo_epoch=3` and showed substantially
higher returns. Not a duplicate of the arm, but evidence in the same direction that would have been
rediscovered instead of cited.)*

## What I would actually watch now

1. **`ppg`'s curve as it completes.** It gets 293 policy updates for 600k frames instead of 8,192.
   If its return is **still climbing at the end** rather than flattening, the run is update-limited,
   and the post-fix re-run should be expected to go substantially higher — not merely look tidier.
   If it flattens, something else is also wrong.
2. **The two rows `idaac` loses at the reaper.** Recovering them from `snapshot.pt` is also the
   standalone-evaluation experiment note 28 wants proven. Check the recovered rows carry the same
   `evaluator_revision` as the 42 before them.
3. **Whether `drqv2` plateaus in the same 25-50 band.** Two baselines from different families
   stopping at the same number would mean the ceiling is the harness or the scene set, not the
   algorithm. That is the single most valuable thing the next run can tell us, and it is why
   `drqv2` should be next rather than a fourth added baseline.
4. **`success_rate` staying 0.000 everywhere.** It is not the axis RL-ViGen judges Robosuite on, so
   it is not evidence of failure — but if it is still 0.000 across every baseline at the end of the
   battery, the task configuration deserves its own look before the results are written up.
