# 24 — What a yield actually costs, and why it is not a small number

**2026-09-09.** The co-tenancy design assumes yielding is cheap: the cell stops, "artifacts written
so far are durable on the bind mounts", and we try again later. The first half is true. The second
is not, and the difference decides how long a single cell may safely be.

## There is no resume path for the added baselines

Checked directly in the trainers:

| baseline | saves checkpoints | loads one to continue |
|---|---|---|
| `idaac` | yes (`save_interval_frames`, `safe_torch_save`) | **no** — `train.py` has no `torch.load` of an agent |
| `ppg` | yes | **no** — no `torch.load`/`resume` anywhere |
| RL-ViGen family (`drqv2` etc.) | yes | yes — `train.py:380` auto-resumes from `snapshot.pt` in the run directory |

`run_probe.sh` does have a `RESUME_SNAPSHOT` hook (line ~363), but it is RL-ViGen-specific — it
plants `snapshot.pt` where RL-ViGen's own loop looks — and it was built for the
checkpoint-reproduction experiment, not for yield recovery. **`run_on_production_host.sh` does not
forward it at all** (zero occurrences), so on the production host it cannot be set even for the
family that could use it.

## So a yielded `idaac` run does not lose "the remainder". It loses everything.

A cell yielded at hour four of five has written checkpoints at 50k, 100k, ... 250k, and those are
real: they can be evaluated offline at those frame counts. What cannot happen is *reaching 600k*.
The next attempt starts at frame 0.

That reframes the trade. Yielding is the right thing to do for a neighbour and the mechanism should
stay. But "we yield, and pick it up later" is not what happens for two of the three added
baselines, and any plan that assumes it is will silently lose whole days.

## What follows for the campaign

- **The risk is bounded by run length, not by politeness.** A 5-hour `idaac` cell is a 5-hour bet
  that no co-tenant arrives. Observed so far: one arrival in roughly eight hours on card 0, brief.
- **`drqv2` is the cheapest long run to attempt**, not only because it is the RL-ViGen-native
  validity check but because it is the one family that could actually resume — if the wrapper
  forwarded `RESUME_SNAPSHOT`, which is a one-line change and is **not** made here, because
  enabling resume mid-campaign changes what a "run" means and that is an owner-level decision.
- **The memory floor is the yield we will actually hit**, and it fired once against *our own*
  packed pair rather than a neighbour. Sizing the cap correctly (note 22) removes most of that
  exposure; it does not remove a real co-tenant.
- **Do not treat checkpoints as progress toward an endpoint.** They are evaluable artifacts at the
  frames they name. `family.py`'s endpoint rule is about the frame a run *finished* at, and a
  yielded run finished nowhere.

## What is not established

Whether `idaac` or `ppg` could be made to resume. Neither trainer reads a checkpoint today, and
adding that is an upstream-fidelity change of exactly the kind `docs/RUNNABLE-ORIGINALS.md` counts
as an authored deviation — so it is a question for the owner, not a repair to make quietly.
