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

---

## Addendum: the first completed full suite, and why the wave is one job before it is seven

**The full suite had never been run to completion in this tree.** The `release suite green` gate
says so in its own text — it runs the fast audits only. The first complete run reported **14
failures**, and roughly half predate this session:

- `test_row_closure_audit`'s fixture used `execution_kind="production"`, the same string
  `audit_row_closure.py` compared against, which `contract.py` can never emit. Test and code
  agreed with each other and both disagreed with reality, so `--strict` could not fail — a
  synthetic mixed-closure production row passed it. This is the check standing behind A24/A25's
  no-pooling rule.
- `test_host_profile_gate_is_not_vacuous` asserted `-ge 600000` was globally absent after
  stripping one guard. Four unrelated guards use that threshold, so the fixture asserted its own
  inertness rather than the gate's behaviour.
- `test_datasphere_native_contract` sliced the runner on `"\nelse\n  run_cell_list"`, which
  stopped being that branch's first line when `require_accelerator` was inserted ahead of it.
- `test_eval_grid_action_provenance` matched ANY `.observe()`, so ppg's `venv.observe()` counted
  as the action probe and the probe's construction looked like it came after its own first use.

**That is the same shape as the CTRL defect**: internal consistency with nothing anchoring it
outside our own files. Every fix above either anchors the check against an external source
(`contract.py`'s vocabulary, the upstream evaluator) or makes it structural instead of textual.

### Consequence for the wave

The seven-family wave is deliberately **not** submitted as seven jobs. The shared-core changes
this session — CTRL's policy mode and P21 — are validated on **one** job first, `dmc_gb` via
`soda`, because that single cell exercises the most machinery that has never run: the Places365
train path end to end, P21's revision stability, and the `RLVIGEN_IMAGE_SIZE` repair. The
remaining six follow only if it lands.

A seven-job wave submitted before that check is how a shared-core mistake gets paid for seven
times, and the suite above is a fair warning that shared-core mistakes are what this session has
been finding.

---

## The observation-geometry chain, traced — and the part of it that is not yet observed

Asked whether the frame-stack values can be trusted or whether something overrides them. Traced
end to end rather than read off the table, because the chain used to be long and one link of it
was silently wrong until today.

**One command answers this now** -- `python3 scripts/audit_observation_geometry.py` prints
declared / executed / observed per baseline, names the stale pre-fix records so none is read
as a measurement, and lists the baselines the runtime assertion has never run for. It exists
because the answer used to take the five-step trace below, and every one of those steps has
been wrong at some point.

**The chain, as it now stands:**

1. **Declared once.** `rlgen/protocol.py::OBSERVATION_GEOMETRY`, `(image_size, frame_stack)` per
   baseline. 10 of 12 stack three frames; `ctrl` and `ibac_sni` are single-frame, which is their
   released Procgen geometry.
2. **Training.** `family.py command` emits `--frame_stack 3` explicitly for `ppg` and `idaac`. The
   other five families take their own clone's default and pass nothing. `ppg_cell.sh` — the
   launcher `family.py` actually names — **refuses to start** without an explicit `--frame_stack`
   (`:?ppg_cell needs --frame_stack`), so it cannot silently inherit a wrong one.
3. **Evaluation.** Since the authority fix of 2026-09-07, `eval_grid.py` reads
   `OBSERVATION_GEOMETRY` DIRECTLY. `--frame-stack` is no longer a passthrough that can redefine
   the declaration; a value contradicting the protocol raises. Before that fix the two flags
   defaulted to dmc_gb's `100/3` and `run_probe.sh` passed neither, so **every family's
   `evaluator_scope` was stamped with dmc_gb's geometry** — the `(3, 100)` pairs still visible in
   older records are that bug, not a measurement.
4. **Runtime.** All seven family paths call `verify_runtime_observation_geometry`, which compares
   the ACTUAL observation tensor against the declared pair and raises on mismatch. This is not
   decorative: it fired on `rad` today — "expected 9 channels in CHW at 100x100, observed
   (9, 84, 84)" — and that is what exposed the missing `RLVIGEN_IMAGE_SIZE` in the eval paths.
5. **Recorded.** `evaluator_scope` stamps the pair per baseline, so a record says which geometry
   produced it.

**Nothing overrides the declared value.** `run_probe.sh` sets no frame-stack variable at all.

### What is NOT yet observed

The runtime assertion only runs when a cell is evaluated, so it is evidence only for baselines
that have produced a record. Five of twelve never have:

| baseline | declared | status |
|---|---|---|
| drqv2, rad, alda, ppg, idaac, ibac_sni, ctrl | — | **observed**: a record carries the declared pair |
| svea, soda | (3,84), (3,100) | covered by the v196 wave |
| **drq, curl, sgqn** | (3,84) | **never run; first checked during production** |

For those three the geometry is declared and *would* be checked, not verified. The exposure is
bounded — a mismatch fails the cell loudly rather than producing a wrong number, which is exactly
what happened to `rad` — but it is not proof, and it should not be described as if it were.
