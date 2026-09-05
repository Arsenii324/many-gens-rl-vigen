# R7 — the acceptance test, written for someone who has not seen this repo

R7 asks for the clone-to-curve path run **end to end on a clean machine by a person who has not read
the project**, timed and recorded. `scripts/requirements.py` can confirm every mechanical link
exists; it cannot perform this. Nothing described what that person runs, so this is that.

**This is a skeleton, not a finished script.** Two of its steps depend on decisions still open
(budget, and whether Lift is in scope). It is written now because an acceptance test designed after
the run is designed to pass.

---

## What the person should be given

- the repository at **one committed hash** (currently impossible — the tree is uncommitted, which is
  itself the `source tree frozen` gate's failure);
- the container **image digest**, not a tag;
- the `rlvigen-door2-*.tgz` asset and its checksum;
- this file. **Nothing else.** If they need to ask, that is a finding.

## The sequence, and what should be observed at each step

| # | step | what they run | what they should see |
|---|---|---|---|
| 1 | environment | build from the pinned digest | image builds; `MUJOCO_GL=egl` present |
| 2 | integrity | `python -m pytest tests/ -q` | green, **no expected-failure caveat** — if we still say "green except one", the test suite is not an acceptance instrument |
| 3 | readiness | `python scripts/production_gates.py` | every gate PASS or OWNER; **no FAIL** |
| 4 | one short cell | one baseline at a small budget through the standard runner | `NATIVE_CELL_COMPLETED`; a checkpoint; a training curve |
| 5 | evaluate it | the offline grid on that checkpoint | records, one row per episode, carrying checkpoint hash and evaluator revision |
| 6 | plot | the shared plotting routine over the retained curve | a figure without per-algorithm branching |
| 7 | timing | record wall-clock for 1–6 | the number R7 actually asks for |

## What counts as a failure of the test, not of the person

- any step requiring knowledge not in this file;
- a gate reporting PASS that the person cannot verify from the output;
- a "known" test failure they must be told to ignore;
- records that cannot be joined to the checkpoint that produced them.

## Why step 2's caveat matters more than it looks

The suite's steady state has been "green except one deliberate failure". For a person who has not
seen the repo, that is indistinguishable from a broken build — and for us it trains the habit of
reading red as normal. Either mark it `xfail` with its reason or fix the link, before anyone is asked
to run this.

## Known blockers to attempting R7 today

1. **No immutable commit** — the tree has uncommitted paths, so there is no hash to hand over.
2. **Four gates FAIL** (see `production_gates.py`), so step 3 cannot pass.
3. **The container digest is not pinned** — `source-lock.json` carries an image tag.

None is deep; all are prerequisites rather than research.
