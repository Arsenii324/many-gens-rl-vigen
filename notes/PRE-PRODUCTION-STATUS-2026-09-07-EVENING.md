# Pre-production status, 2026-09-07 evening — the freeze candidate

Supersedes the in-flight-wave section of `PRE-PRODUCTION-STATUS-2026-09-07.md`. That page tracked
the v194 wave as the one that would earn 7/7. **It will not, and the reason is a correctness fix,
not a process failure.**

## Why v194 and v195 are diagnostics, not attestations

`ctrl`'s native evaluation rule was wrong. Its released evaluator is greedy
(`runnable/ctrl/evaluate_ppo.py:84` → `logits.argmax(1)`), and this project reported it as
sampling, on the strength of `train_ppo.py`'s TRAINING calls. Fixing it changes
`scripts/eval_grid.py` and `datasphere/native/evaluator_identity.py`, both shared closure members,
so **every** family's evaluator revision moved — including the six that have nothing to do with
CTRL. The v194 records and the two cancelled v195 Places365 jobs remain useful evidence of the
paths they exercised; they are not the final ledger.

That is the same rule that cost a generation earlier the same day, applied deliberately this time
rather than discovered: once a closure member changes, everything attested against the old one is
stale, and the honest move is to regenerate rather than to claim only the touched family needs it.

## What this session actually fixed

Defects, each found and then confirmed at its source rather than accepted from a report:

1. **`dmc_gb` evaluated at the wrong render size.** The endpoint, curve and offline eval paths
   invoke `eval_grid.py` directly, in `run_probe.sh`'s own shell, which never inherited
   `runnable/_launch/dmc_gb.sh`'s `RLVIGEN_IMAGE_SIZE=100`. Unset, robosuite renders at 84 and
   RAD's `random_crop` degrades to the identity by its own `crop_max <= 0` guard, while SODA's
   hard assert on size 100 refuses to run at all. Training was unaffected. The runtime geometry
   check caught it correctly; it was not a false positive.
2. **`ctrl` native policy mode** — above. The split is now 9 deterministic / 3 sampling.
3. **The production host wrapper could not express production.** It passed the RL-ViGen archive as
   `run_probe.sh`'s third positional, which is the Places365 asset, and never set
   `RLVIGEN_ARCHIVE`; and its forwarding list was missing 25 variables the runner reads, including
   `NATIVE_PLACES365_SPLIT`, both policy-mode knobs, `CELL_TIMEOUT_SECONDS` and
   `NATIVE_CELL_DEVICES`. Independently found by external review 24.
4. **The Places365 train branch had never executed.** After configuring the loader for
   `$places_split`, the runner asserted the loader root equalled a hardcoded `.../val`, so the
   decided production split failed its own check. It also forced gzip on an uncompressed archive
   and accepted only one of the two train layouts.
5. **`verify_sources.py` reported corruption on a healthy tree.** `git -C` walks up to the
   enclosing repository when a destination has no `.git`, so RL-ViGen was checked against this
   project's own HEAD; snapshot-style clones can never match HEAD by construction; `door.xml` is
   runtime-generated and was excluded for three families but not the other four.
6. **The comparability seam compared prose, not values**, on the policy-mode axis — six "values"
   where there are two.
7. **`bootstrap(root=...)` ignored its own argument**, which is how a disposable probe reached the
   real checkout.

Each is pinned by a test that anchors against something outside our own tables — the vendored
upstream source, or the runner's own text — because in the `ctrl` case three of our files agreed
with each other and were wrong together.

## The freeze candidate

`production_gates.py`: **32 pass, 0 fail, 9 owner.** No mechanical failures remain.

The nine OWNER rows are decisions, recorded at ratification grade and deliberately not closed in
code. `notes/DECISIONS-IF-PRODUCTION-GOES-WRONG.md` gives each one the symptom that would indict
it, the cheapest test that settles it, and what changing it later costs — written before any
production result exists, so no symptom can be matched to a convenient explanation afterwards.

**R3 reads NOT MET and stays that way.** The owner has ruled the policy-mode split acceptable
because each family's rule is its own published one; that is a ruling that the split is acceptable,
not that it is absent. `notes/SAME-AXES-VERDICT.md` carries the ruling, the per-family verification
it rests on, the one family where that verification is weakest (`ppg` ships no evaluator), and the
reporting consequence decided in advance: rank within a block, never across.

## What remains, in order

1. **One seven-family evaluator wave** against this frozen tree. Nothing else may change while it
   runs.
2. **Host measurements**, which need the machine: renderer parity as the three-step R_A/R_B probe,
   CTRL at a real `num_envs=64` rather than a 4× extrapolation, IBAC-SNI competence at `procs=16`
   against a criterion fixed in advance, and CPU packing measured solo-versus-packed before any
   two-cell plan.
3. **The 600k DrQ-v2 canary**, read as a chain rather than a score — it is the only thing that
   tests the parts which only fail after hours.
4. **The Linux RL-ViGen reconstruction proof**, the one external proof this repository still owes,
   unprovable on a case-insensitive filesystem.

Only then the fleet.
