# Where pre-production actually stands

Written 2026-09-05, after reviews 6, 7 and 8. Ordered by review 7's priority list, which is the
clearest sequencing the project has received, with our real position against each item.

`python scripts/production_gates.py` recomputes the machine-checkable half of this from the tree.
At the Codex handoff on 2026-09-05 it reads **27 pass / 2 fail / 11 waiting on the owner**. The
failures are the unresolved IBAC forced-fork/worker-reseeding path and the intentionally uncommitted
shared tree; the latter cannot be closed while concurrent edits are still landing.


## Superseding update, 2026-09-08 evening

The gate figures in the paragraph above are from the 2026-09-05 Codex handoff and are stale.
`production_gates.py` now reads **35 pass / 0 fail / 10 waiting on the owner** once the tree is
committed (the single failure is the tree-freeze gate, which is uncommitted work by definition).

**The next action is no longer a gate.** It is the renderer, and then the chain:

1. **Re-run one `idaac` cell on card 0.** The 2026-09-08 attempt died at the renderer check with
   `software EGL renderer: llvmpipe`; `run_on_production_host.sh` now sets
   `NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics`, which was verified on the host to be what
   makes `libEGL_nvidia` appear. That fix is **unverified end to end** — no cell has run since.
2. **Build the two environments first, or accept ~2.5 h of `pip` per attempt.**
   `datasphere/native/build-env.sh`. Its orchestration is smoke-tested; a full build is not.
3. **Then the chain**: train → durable checkpoint → fresh-process reload → endpoint grid → records
   → statistics. Still never completed on any host at any length. This is owner-decision item 6 and
   nothing below it should be trusted until it runs once.
4. **Then R_A/R_B renderer parity** (`DECISIONS-IF-PRODUCTION-GOES-WRONG.md` §8), for which the
   cheap first cut — render a few fixed-seed observations on both hosts and diff them — should come
   before the three-step probe, because it would have caught the `llvmpipe` fallback for nothing.

---

## Done this session

| # | review 7's item | state |
|---|---|---|
| 1 | Fix the payload contract, add a dependency-closure test | **done.** `rlgen/protocol.py` ships; `tests/test_payload_contract_covers_provenance.py` asserts every evaluator-revision member is a declared payload member, and was verified failing on the real defect |
| 2 | Fix PPG's witness/diagnostic timing | **done**, and measured: a real ppg venv now returns `diagnostics_available: True` with the full field set after a complete episode. Pinned by a structural test over all seven `run_scene*` |
| 3 | Fix CTRL's train/eval RNG separation | **rejected, with reason.** The key advance is upstream's own (`ext/ctrl_public/train_ppo.py:193,202`); patching it would be our deviation. The gate that called a string search "RNG isolation" was the real defect and now states what it verifies |
| 4 | Make record completeness real; remove the duplicate diagnostic helper | **done.** `eval_grid`'s weaker copy deleted in favour of `eval_provenance`'s validating one; `eval_episode_ids` now reach every record; the gate that matched the loop variable `episode_index` now matches the emitted key |
| 5 | Attach run provenance to offline rows; fix evaluator identity | **done as of 2026-09-05; identity scheme superseded 2026-09-06.** Offline rows are enriched from `run_manifest.json` during bundling (loud, non-fatal if absent — tested both paths); `families.json` joined `REVISION_MEMBERS` because omitting per-family eval configuration made the revision *under*-sensitive at the time. **CORRECTIONS.md #94**: that same join also made `NATIVE_HOST_PROFILE` (a training-only override) move every family's evaluator revision, so no validation done under one host profile could ever read as current under another. Identity schema bumped to 2: `families.json`'s descriptor no longer feeds `evaluator_config_revision` at all — the resolved per-row scope and each family's own static runtime-closure files already cover what matters for evaluation. This row's "done" no longer describes the live mechanism; see `evaluator_identity.py`'s own module docstring for the current one. |

Plus, outside that list: **IBAC-SNI's `--beta` was never passed**, so it ran at 1.0 against the
1e-4 the fidelity table claimed. Fixed, pinned, and generalised into a new instrument —
`scripts/audit_executed_hyperparameters.py`, now a gate — which asks the question no existing audit
asked: *does the value we claim actually reach the process?* It immediately found three more
(SGQN's `aux_lr`, `sgqn_quantile`, `aux_beta`, whose "FIXED" values describe the legacy `rlgen/`
path rather than the production one).

## Blocked on you, in the order that unblocks the most

**[Rewritten 2026-09-05 after Codex's Q16 — the previous version said the V100 targets were "NOT
YET APPLIED" and that intermediate evaluation was unscheduled. Both are now false in the tree.]**

What is **already applied and executable**, awaiting only your ratification:

- **The v100 host profile exists and resolves** — `NATIVE_HOST_PROFILE=v100` gives idaac 16, ppg 8,
  ibac_sni 16, and RL-ViGen replay **620,000** (non-evicting at this budget, two-cell packing; the
  1,000,000 option is preserved and costs one cell instead of two). The DataSphere-safe base is
  untouched, so probes are unaffected.
- **Both evaluation scopes are scheduled** — `production_env()` enables the endpoint grid
  (4 x 10 x 20) and the 50k trajectory grid, and the runner runs them with separate settings and
  distinct record labels. The earlier "possible but not scheduled" defect is closed.
- **Determinism stays on** — the bounded ON/OFF timing comparison measured 118 s versus 120 s, so
  the observed overhead was negligible for that cell. A repeat showed the ON arm matching OFF, so
  the earlier attribution of return changes to the flag is withdrawn: repeated CUDA evaluation is
  variable even with determinism enabled. Keep the flag, but do not claim bit-reproducible returns.

What genuinely still needs **you**:

1. **Ratify the applicable rows on A1-A28.** Every row now carries a default that is what a run will actually do. The two
   with real money attached are **A20** (trajectory depth: 176 / 291 / 579 GPU-h for 3 / 5 / 10
   episodes per stamp) and **A14** (620k versus 1M replay, which is two cells versus one).
2. **The commit — but not yet.** Better once the configuration stops moving, so the SHA describes
   the code that produced the results rather than a snapshot mid-change.
3. **The canary**, refined: `drqv2` first at ~9.1 h for the RAM envelope; `idaac` at ~7.5 h only
   after the repaired T1 path has its post-fix CUDA smoke. Do not use `soda` at 54 h as the first
   setup canary.

## Then, in this order — and not before, because each depends on the one above

4. **Freeze the evaluator revision**, then revalidate every distinct evaluator family once under it.
   **Zero of seven current-revision family burdens are currently discharged** — the earlier
   drqv2/idaac evidence is on superseded evaluator revisions and cannot certify this one.
5. **The IBAC pilot at the final configuration.** The repaired `procs=16` path now completes a
   bounded functional smoke on `gt4i.1` (job `bt1djai23kme336auat4`) and the measured process tree
   fits its 27 GiB RAM. That is not a competence pilot: run A1 at the exact final settings on the
   production V100 host, because `gt4.1` is too small and a `procs=1` pilot measures a different
   process/batch geometry. Do not promote `procs=1` to the production default.
6. **Re-measure the renderer baseline as a three-step comparison** — current evaluator here (R_A),
   same checkpoint and container on the production host (R_B), compare — *not* against the archived
   480.6, which `RESULTS-VALIDITY` invalidates for exactly this purpose.
7. **One 600k canary** end to end: train → checkpoint retention → clean reload → full grid →
   lightweight records → analysis.

## What would still make all of this wrong

The `beta` defect is the shape to fear: a value researched, sourced, written into the fidelity
table, and never wired to the process. It survived five external reviews, an audit reporting
"12/12 genuine", and a ledger that cites its value. The new gate closes that class **only for
parameters FAITHFULNESS states as `name: value` in live prose** — 19 claims remain `UNLOCATED`
because they live in YAML specs, config objects, or are computed at runtime. Those 19 are the most
likely place for the next finding of this size.

## Added after the first pass

- **A19** — PPG's `n_pi` has no faithful setting at 600k (upstream would reach zero auxiliary
  phases; we reach nine, or four on the production host). A fork, not a defect; default is to keep
  32 and name the row accordingly.
- **A20** — [SUPERSEDED: now scheduled; `production_env()` enables both scopes and the runner runs them separately. What follows describes the state when the defect was found.] intermediate evaluation was possible but **not scheduled**. Checkpoints are retained at a
  uniform 50k cadence, but `CURVE_EVAL=1` is never set in the production schedule, so the fleet
  would produce one endpoint evaluation per cell and eleven unevaluated checkpoints.

## Verification state at session close, 2026-09-05 (overnight, final)

    python -m pytest tests/ -q          1443 tests, 115 files — historical full-suite result
    python scripts/production_gates.py  27 pass / 2 fail / 11 owner — current live result
    python scripts/requirements.py                    exit 0
    python scripts/audit_eval_cadence.py --check      12/12 anchors hold
    python scripts/audit_implementations.py           12/12 genuine (5 PRESENCE ONLY)
    python scripts/audit_executed_hyperparameters.py  exit 0, 2 legacy claims listed with reasons
    python scripts/open_decisions.py                  22 decision items; decision sheet A1-A28

Every fix landed today was verified by **restoring the defect and watching the test fail** — the
payload contract, the ppg collection order, the ctrl reward units, the ibac beta, and the tightened
placement gate. Two of my own instruments silently swallowed real findings while reporting success
during that work; both are recorded in `CORRECTIONS.md` #24-25.

---

## Overnight session, 2026-09-05: four stacked defects, found by running

**The headline: the shared evaluator could not complete a CUDA evaluation for any family, and the
suite was green throughout.** Four defects sat in a single job's path, each invisible until the one
in front of it was fixed:

| # | defect | scope | how it was found |
|---|---|---|---|
| 1 | `contract.py` never shipped `rlgen/protocol.py`, which the evaluator-revision stamp requires | **all seven families** | external review 6; confirmed by two dead jobs |
| 2 | regime read-back guard raised on every construction | **idaac and ctrl** — 2 of the 6 families using it | building every family's real env locally |
| 3 | agent device placement moved nothing for an `nn.Module`-shaped agent | idaac (ppg had a name-keyed branch) | the job got further and died in the policy |
| 4 | `use_deterministic_algorithms(True)` raises at the first CuBLAS op without `CUBLAS_WORKSPACE_CONFIG` | **every family** — `eval_across_scenes.py:146` too | the job got further still |

All four are fixed, each verified by restoring the defect and watching a test fail. **Defect 4 means
no CUDA evaluation with determinism has completed since C70 landed**, which also explains why
throughput under the current evaluator was never measured — every attempt died before finishing an
episode.

### What changed structurally

- `tests/test_family_env_smoke.py` — constructs **every** family's real evaluation env and runs the
  real strict guard, in ~7 seconds, no checkpoint and no GPU. Three of the four defects above lived
  in code no test had ever executed.
- `tests/test_family_regime_readback.py`, `test_agent_device_placement.py`,
  `test_cublas_determinism_config.py`, `test_payload_contract_covers_provenance.py` — one per defect.
- `scripts/audit_job_budgets.py` (gate) — a config whose timeout cannot fit its own episode count.
- `scripts/refresh_clone_patches.py` (gate) — `RECOVERY-HANDOFF` claims the clones are reproducible
  from `ext/` plus the patch snapshots; **five of six had drifted** and nothing checked.
- `scripts/audit_executed_hyperparameters.py` (gate) — does a value we CLAIM reach the process.

### The next thing to do, and it is cheap

**Run the determinism A/B.** `RLGEN_DETERMINISTIC_EVAL=0` now exists precisely so this is a config
change rather than an evaluator edit. Both arms can execute for the first time. The cost of
determinism on this workload is unknown and it is real — `:4096:8` disables the fast CuBLAS paths —
and at 28,800 endpoint episodes the answer decides whether keeping determinism is affordable.

Then, and only then, revalidate every distinct evaluator family once under one frozen revision. Do
not spend on a second family until `bt1aj1snkvadphens74o` (idaac, 10 episodes) proves the chain runs
end to end.

## Concurrent work with Codex, same night (Q3–Q12)

Codex ran in parallel and its questions found several real holes in what I had just built. Worth
recording because the pattern was consistent: **it caught the things that looked finished.**

| raised | finding | outcome |
|---|---|---|
| Q7 | the training path had **no terminal endpoint grid** — a training job produced trajectory rows and no reportable number | `run_endpoint_eval()` added, with `ENDPOINT_EVAL_*` scope independent of `CURVE_EVAL_*`, and `--eval-scope` labels so the two cannot be pooled |
| Q8 | the effective config could only be reconstructed from `families.json`, which is **wrong after any descriptor edit** — and descriptors changed three times that night | per-cell `effective_config.json` written at the moment the argv is known; fails the cell if it cannot be written |
| Q10 | that artifact was written **before** the cell environment was resolved, and `run_curve_eval` logged failures then **returned success** | artifact moved after resolution and now records `cell_environment`; a partial trajectory fails a production cell (`CURVE_EVAL_STRICT` defaults to `ENDPOINT_EVAL`) |
| Q11 | `cfg-idaac-determinism-off-v106.yaml` pointed at a payload the bumped contract now rejects | not submitted; awaiting one fresh payload after Codex's runner edits settle |
| Q12 | the Door floor `1.82` was live in **five places** while the measurement had moved to 1.842 | one home — `rlvigen_reference.DOOR_RANDOM_FLOOR` — imported, failing loudly rather than defaulting |

Codex independently implemented the **producer** side of the endpoint/curve split in
`family.py::production_env()` while I implemented the **consumer** side in `run_probe.sh`. The
variable names matched exactly, because both followed the descriptor's `offline_eval_*` naming.
That was luck, not design, and it is worth not relying on again.

Also from that exchange, and still open: **`EVALUATOR_REVISION` cannot see the host profile.** A
runtime-selected profile means the same `families.json` bytes produce two materially different
experiments — IDAAC 4 procs versus 16, replay 300k versus 1M — under one identical revision hash.
The per-cell artifact and the manifest both record it, but nothing yet *refuses* to pool across it.
Folding the profile into the revision string is the cheapest fix and it is Codex's file to change.


## Historical state, end of the overnight session

The following block is retained as an audit trail. Its counts and job-status wording are
superseded by the current gate summary at the top of this file and by the live DataSphere status,
so it is not an operational checklist.

    python -m pytest tests/ -q                        1443 tests, 115 files — exit 0
    python scripts/production_gates.py                22 pass / 1 fail / 10 owner
    python scripts/requirements.py                    exit 0
    python scripts/audit_eval_cadence.py --check      12/12 anchors hold
    python scripts/audit_executed_hyperparameters.py  exit 0
    python scripts/audit_job_budgets.py               exit 0
    python scripts/refresh_clone_patches.py --check   all six snapshots current
    python scripts/audit_comparability_seam.py        exit 0, no underived axis

**The single failing gate is `source tree frozen` — the uncommitted tree, which is A11 and yours.**
Every other technical gate passes. Ten remain owner-gated by design.

**The evaluator chain is proven end to end**: `bt1aj1snkvadphens74o` completed on CUDA in 607s and
returned records carrying complete diagnostics, working determinism, episode identifiers and run
provenance. That is the first time this has happened, and it took fixing four defects that were
stacked one behind another.

**What is still not measured, and should be the first thing bought:** the cost of determinism.
`RLGEN_DETERMINISTIC_EVAL=0` and the `NATIVE_OFFLINE_EVAL_SECONDS` marker exist so the A/B is a
subtraction rather than an inference. Codex is building the fresh payload (contract 13); the B arm
is `cfg-idaac-determinism-off-v106.yaml`, which must be repointed at that payload before use.

---

## Overnight 2026-09-05 → where pre-production actually stands

**Done and provable from the tree:**

- **Evaluator code revision FROZEN** at `4a77df8be2c5a197...`, unconditionally — both decisions that
  could still have moved a code member (A21 scene-in-seed, diagnostics fail-closed) are persisted.
  `evaluator_config_revision` is separate and moved twice today, which is the point of the split.
- **Memory certification**: was one family measured out of seven, silently passing the other six.
  Now four are measured from job logs already paid for; `rlvigen` and `dmc_gb` are **deliberately
  left uncertified** with reasons, because a family peak taken from its lightest member is not a
  peak.
- **Three new gates** — submission configs runnable, production names its host, and ibac's
  second-order RNG defect folded into the existing procs gate so a fork→spawn fix cannot flip it
  green while 16 workers still share one placement stream.
- **The diagnostic tests no longer swallow defects** — 8 `except Exception -> skip` sites now decide;
  all 12 pass and none skips on this machine.
- **A22 opened** for the Places365 validation split, which had no decision row anywhere.

**In flight** (all on `gt4i.1`, after three jobs were lost to a tier the descriptor already knew
was too small): ctrl `bt1s3hm3166ge2kgg93c`, alda `bt1pb2kceart31caaqkq`, drqv2
`bt11auoe27bldreg229k`.

**Then pre-production was expected to be done except what only the owner or the production host
could settle:**

1. Ratify A1–A22 (`python scripts/open_decisions.py`).
2. Commit the tree — 155 uncommitted paths, and the count grows every session. This is the one
   failing gate that is neither mine to fix nor blocked on hardware.
3. Production-host work: IBAC pilot at the corrected β, the R_A→R_B renderer control, the Docker
   digest pin, V100 throughput. Owner has prohibited substituting a DataSphere V100 for these.
4. Canary — **REVISED, superseding the `idaac`-first order below and at line 53**: `drqv2` first
   (~9.1 h), `idaac` only after review 11/12's T1 (a live rollout-storage episode-identity defect,
   handed to Codex) is repaired and verified with a real integration test. Canarying a family with
   a known-live storage bug tests the defect, not the pipeline — see `DECISION-SHEET.md` A10's
   2026-09-05 caveat. **Not** `soda` first either way: it is 54 h, and a canary whose purpose is
   finding setup faults should not be the longest cell in the campaign.

**The one thing I would put in front of the canary**, added today: a repeat-run variance
measurement. A frozen evaluator does not reproduce itself — MuJoCo and EGL sit outside Torch's
determinism scope, measured spread 0.77% on `train`, exactly 0 on `eval-easy`. Any "X beats Y" needs
a margin above that floor, and the floor is currently known for one family and two regimes.
