# Recording a finding so it stays true

Written 2026-09-10, from a day in which three separate "findings" turned out to be the existing code
being right and me being wrong, and one turned out to be right for a reason the first analysis had
inverted.

## The failure this addresses

An early record that is wrong is worse than no record, because it is cited. And the way this project
gets wrong records is **not** carelessness — it is stopping at the first layer that explains the
observation.

Today's worked example. `ppg` declared `--nminibatch 32` and executed `1`, logging a warning 293
times. Three defensible-looking conclusions, in order, each superseding the last:

1. **"The config is wrong, fix the declaration."** Stops at the log line.
2. **"The run is a severe under-optimisation of PPG."** Stops at the clamp. Written up, committed.
3. **The truth.** `1` reproduces PPG's released update density (0.00048828 steps/env-frame) *and*
   its per-step batch size (2048 samples) **exactly**. The clamp did not damage fidelity; the
   declared 32 would have, by 32×. The defect was the declaration, and the executed run was already
   faithful.

Conclusion 2 was recorded as settled and was inverted six hours later. Nothing about it looked
provisional.

## The rule

**A finding is recorded as RESOLVED only when the whole path from the observation to the executed
behaviour has been walked, and every step cites the producer.**

Concretely, before writing "resolved":

1. **Read the producer, not the consumer.** The value's origin, not the code that reads it. `ntrain`
   is `num_envs` because `Roller.singles_to_multi` stacks `(batch, time)` — that is the producer;
   the clamp is the consumer.
2. **Name the alternative that would make the current behaviour correct**, and rule it out
   explicitly. Conclusion 2 failed because "the executed value is right" was never posed.
3. **Compare against the method's own reference, not only against our declaration.** The declaration
   is a claim; upstream's released recipe is a fact.
4. **Check what already decided this.** `PARAMETER-REVIEW-CONSENSUS-MATRIX.md`,
   `OPEN-QUESTIONS-LEDGER.md`, `where_is_this_decided.py`. Today the answer was already in
   `FINDING-on-policy-update-density.md` and I nearly re-derived it wrongly.
5. **State what would falsify it.** A finding with no falsifier is an opinion.

## The three statuses, and only one of them is quotable

| status | means | may be cited as fact |
|---|---|---|
| `OBSERVED` | something in the artifacts looks wrong | **no** |
| `TRACED` | the mechanism is understood; the consequence is not settled | **no** |
| `RESOLVED` | the whole path is walked, the alternative is ruled out, a falsifier is stated | yes |

Most of what a session produces is `OBSERVED`. Writing it as `RESOLVED` is the error this file
exists to prevent.

## Making it mechanical, because discipline decays

Prose rules are not enforcement. Two things are:

- **`scripts/verify_note_citations.py`** — checks every `path:line` a note asserts: the file exists,
  the line exists, and the identifier the note names is still near it. Run fleet-wide it found
  **530 stale citations across 159 notes**. Cite with a **qualified path**: a bare `ppo.py:130` is
  ambiguous across nine files here, and that ambiguity is how a stale story survives a search that
  cannot say which file it read.
- **Convert the claim into a check.** A test that fails when the finding stops being true outlives
  any note. Today's `no_grad` finding is pinned by a test that executes the real function against
  `th2np`'s own expression; the `nminibatch` finding is pinned by a test asserting
  `nminibatch <= num_envs` against `families.json`. Neither can go quietly stale.

## Correct in place, and leave the reversal visible

When a `RESOLVED` record turns out wrong, **edit the original** — do not write a second note that
disagrees with it silently. A reader who finds the first one must learn from it that it was
superseded. Every correction today is inline, with the superseded reasoning left readable, because
*why* a careful analysis reached the wrong answer is usually the more transferable half.
