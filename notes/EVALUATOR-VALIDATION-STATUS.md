# Which families are validated on the CURRENT evaluator, and how

> **Superseding update, 2026-09-07:** the final v185 endpoint wave completed for all seven
> evaluator families, including CTRL (`bt10tugtltvqoi2ag2cj`). Its seven retained JSONL
> artifacts are in `results/validation/`, and `production_gates.py` now accepts **7/7 current
> closures**. The stale table and 0/7 wording below are historical evidence from before that
> wave; do not read them as current state.

**STALE 2026-09-05, external review 14 §9-adjacent finding (P1): this document's table below is
historical evidence, not a live validation ledger. It claims several families "VALIDATED, current
revision" against `a8664a7f98dc3311`, which is no longer the current revision — many edits have
landed since (this session's disk-safety, IDAAC episode-identity, PPG cadence, and
provenance-closure fixes among them). `python scripts/production_gates.py`'s "shared evaluator
validated" row and `datasphere/native/validated_evaluator_families.json` are authoritative: they
compute the current revision live and currently report 0/7 on it. The old JOB IDs and per-family
path evidence remain useful, but do not read the historical "current"/verdict column as a present
claim.**

The evaluator identity repair is locally implemented and tested: payloads bind static family
closure/configuration, and rows bind resolved canonical measurement scope and revisions. This
does not move the remote verdict: 0/7 families are validated against the current closure. The live
gate now also requires a `functional_endpoint` scope attestation and SHA256-bound retained records;
this allows shallow endpoint functionality validation without presenting it as final production
metric depth. Dynamic import manifests remain review evidence rather than complete static proof,
and the records artifact still requires human review for source/job correctness.

One historical table is retained for job/path evidence, because "the evaluator works" was believed
for weeks while two families could not construct an environment at all.

**Criterion**: a job on CUDA, under the current contract-13 payload, that returns records carrying
complete diagnostics, working determinism, episode identifiers and run provenance.

**The revision matters as much as the verdict.** A family validated under a superseded revision has
not been validated under the one the fleet will run, which is the whole point of stamping it.
The historical table's revision is **`a8664a7f98dc3311`**; it is not the current tree revision.

| family | job | revision | complete records? | verdict |
|---|---|---|---|---|
| `ppg` | `bt1ag9egnoj6n8qvsdkj` | **a8664a7f98dc — current** | yes | **VALIDATED, current revision** |
| `ibac_sni` | `bt1jb9bpfb469s1l9602` | **a8664a7f98dc — current** | yes | **VALIDATED, current revision** |
| `dmc_gb` (rad, soda) | `bt1s4q60d8nsvd4771l5` | **a8664a7f98dc — current** | yes, `scope: endpoint` | **VALIDATED, current revision** |
| `idaac` | `bt1baht74a35e6uq582c`, `bt1e78hbs4s946aje3q9` | 4ad7d3b878ad — superseded | yes | path proven; **needs a current-revision run** |
| `idaac` | `bt1aj1snkvadphens74o` | 8d5c1dd0b4b3 — superseded | yes | path proven; superseded |
| `ctrl` | — | — | — | **not yet** — and its double-reset was only fixed 2026-09-05, so any earlier run is void |
| `alda` | — | — | — | **not yet** |
| `rlvigen` (5 baselines) | — | — | — | **not yet** |

Local evidence, which is necessary and **not** sufficient — it cannot see CUDA-only failures, and
three of the four defects found on 2026-09-05 were CUDA-path:

- all six families using the shared guard construct and pass **strict regime verification**
  (`tests/test_family_env_smoke.py`)
- `ppg`, `ctrl`, `idaac` expose **complete episode diagnostics** after a full episode
- placement conditions are **reproducible and scene-specific** (same seed+scene gives identical
  witnesses; a different scene differs)

## What validation can and cannot conclude

**It cannot use exact equality.** Two runs of the identical configuration — same revision, payload,
checkpoint, `det=True` — produced different returns on 2 of 5 episodes
(`bt1baht74a35e6uq582c` against `bt1e78hbs4s946aje3q9`). Determinism governs torch kernels, not
MuJoCo or EGL, and Door is threshold-sensitive.

So a family is "validated" here in the sense that **the path executes and the record is complete**,
not that a number is reproducible. Any agreement criterion — the discharge comparison especially —
needs a predeclared tolerance exceeding the run-to-run variance, and **that variance is not yet
measured**: one pair of runs is an anecdote. Three repeats of one cell would give it.

## Can the evaluator be frozen now? Only conditionally — stated precisely

After splitting code from configuration, `families.json` edits (A14, A20) **no longer** void a code
validation. But two open decisions still touch **code** members:

| decision | if chosen | file | moves code revision? |
|---|---|---|---|
| **A21 option 2** — drop `scene_id` from the placement seed so scene contrasts are paired | `placement_condition_seed` changes | `scripts/eval_grid.py` | **yes** |
| **Diagnostics fail-closed** (review 10 #5) — refuse a cell with `diagnostics_available: false` | the tolerant branch changes | `scripts/eval_provenance.py` | **yes** |
| A14 host profiles / A20 curve depth | descriptor only | `families.json` | no, after the split |
| A17 beta | launcher only | `runnable/_launch/ibac_sni.sh` | no |
| ibac fork -> spawn experiment | clone only | `torch_rl/scripts/train.py` | no |

**So validation done now is conditional on A21 staying at option 1 and diagnostics staying
tolerant.** That is a defensible bet — both are my recommended defaults — but it is a bet, and the
cost of losing it is re-running roughly seven ~10-minute functional jobs, not a campaign.

**What would make it unconditional** is ratifying those two decisions first. If the owner wants
certainty over speed, that is the order; if speed, validate now and accept a possible redo. I am
proceeding on the second, and recording it here so the choice is visible rather than implied.

## FROZEN — evaluator code revision, 2026-09-05

    evaluator_code_revision = 4a77df8be2c5a197484237f2e7f11141ce3f9c371351d6e7c687cf0ae1440e82

**This is now unconditional, not a bet.** The two open decisions that could still have moved a code
member have been decided and persisted rather than left as defaults:

- **A21 -> option 1** (keep `scene_id` in the placement seed). No code change: the headline estimand
  aggregates over scenes and gains from 200 distinct placements rather than 20, while scene
  heterogeneity is explicitly secondary. The caveat that a per-scene row may describe a cell but not
  rank scenes is in `CLAIMS-LEDGER`.
- **Diagnostics -> fail CLOSED in production** (`eval_provenance.py`). A row without realized
  placement cannot support a paired-condition claim, and that loss is unrepairable after a fleet.
  Safe to close because five families are **measured** to return complete diagnostics; if `alda` or
  the RL-ViGen five do not, a failed validation cell is how we should learn it. Exploratory probes
  stay tolerant, keyed on `ENDPOINT_EVAL`.

Everything still open — A14 host profiles, A20 curve depth, A17 beta, the ibac fork/spawn
experiment — touches `families.json`, a launcher or a clone, **none of which is a code member**. So
ratification can now proceed without voiding a single validation.

**Validate every family against this hash.** A run whose `evaluator_code_revision` differs is not
evidence about the fleet's evaluator.

### In flight, 2026-09-05 — the last three families

| job | family | payload | revision |
|---|---|---|---|
| `bt1lhobnsq5lq4766np6` | ctrl | v114 | pre-freeze |
| `bt1piail8l4ilcm5gj24` | alda | **v116** | **frozen** |
| `bt1fsqo2pv5ug4jlak6i` | rlvigen (drqv2 standing for the five) | **v116** | **frozen** |

ctrl runs the pre-freeze payload because it was submitted before the last decision landed. That is
acceptable for what it tests -- the double-reset fix and the first CUDA execution of that family --
and the only code delta since is the diagnostics *tolerance*, which cannot change a run that
produces diagnostics. If ctrl comes back green, its evidence stands; if the distinction is ever
load-bearing for a claim, re-run it at v116 rather than arguing the delta is small.

Timestamps in `job list` read as `2026-09-19`; that is the platform's clock rendering, not our date.
CORRECTIONS #25 is the near-miss where I misread it and almost cancelled a healthy job.

## The noise floor a frozen evaluator still has, and why "validated" cannot mean "reproducible"

Raised as a synthesis point no external review named: **the same evaluator gives different answers
to itself.** Reviews 7, 9 and 10 all recommend "freeze the evaluator, then validate every family
once", and that sequence is right — but it must not be read as making a number repeatable.

Measured here (CORRECTIONS #37/#38): two jobs with byte-identical `evaluator_revision`,
`payload_sha256`, `checkpoint_sha256` and `deterministic_algorithms=true` produced **different
per-episode returns**. Four replicates since:

- `eval-easy`: byte-identical across runs.
- `train`: spread **0.1165, or 0.77%** of the mean.

The cause is outside Torch's determinism scope entirely: MuJoCo physics and EGL rendering are not
covered by `use_deterministic_algorithms(True)`, and `CUBLAS_WORKSPACE_CONFIG` does nothing for
them. This is why A37's original attribution was wrong — I credited the determinism flag with a
difference it did not cause, then two ON runs differed identically and removed the flag as the
variable.

**What this means for the protocol, and it is not yet written anywhere else:**

1. **Validation means the path executes and the record is complete** — not that the number repeats.
   That is the definition already used in this file; this section is why it has to be.
2. **Any claim of the form "X beats Y" needs a margin exceeding this floor.** 0.77% on the train
   regime is the only floor we have measured, on one family. It is not established for the other
   six, and the two regimes differ (eval-easy was exactly reproducible, train was not) — which is
   itself interesting, since it suggests the variance enters through scene/physics diversity rather
   than through the renderer alone.
3. **A repeat-run variance measurement belongs in the campaign**, not after it. Cheapest form: the
   endpoint grid run twice for one family per regime, which the calendar can absorb.

Not yet decided, and deliberately left open rather than defaulted: whether to spend a second
endpoint pass on **every** family, or to measure the floor on two families and assume it transfers.

## Revised freeze, 2026-09-05 (later) — the freeze moved once, for cause

    4bef9881a418c2d88a450d38a902bd3aa159d724a651741917935caa826435d2

CORRECTIONS #47: `eval_grid.py` built a JAX shape from a descriptor string, so **every ctrl
evaluation died at checkpoint load**. A freeze that preserves a fatal defect is worth nothing, so it
moved. The delta is confined to `_ctrl_train_state`, which only ctrl executes.

### Results so far

| family | job | verdict |
|---|---|---|
| **drqv2** (rlvigen) | `bt11auoe27bldreg229k` | **VALIDATED** — 5 episodes x 2 regimes, complete `episode_diagnostics`, distinct `placement_condition_seeds` and witnesses, `eval_episode_ids` present, **physically PAIRED, 0 unpaired**. Taken on the *previous* hash; the diff does not touch this path. |
| alda | `bt1pb2kceart31caaqkq` | executing |
| ctrl | `bt1t3njt0m37dujrio2u` | resubmitted at the new hash after #47 |

**What the ctrl sequence cost, and what it bought:** three failures, each hiding the next. A tier the
descriptor already declared too small (SIGKILL at 13.57 GiB) hid a training run that completes, which
hid an evaluator that cannot load a checkpoint at all. Only the third is a defect in the science;
the first two were configuration, and both are now mechanically prevented. **The evaluation path of
the family whose evaluator was rewritten this session had never once executed end to end.**

### alda VALIDATED, 2026-09-05

`bt1pb2kceart31caaqkq`. 4 endpoint rows, 5 episodes each, **all `diagnostics_available: true`**,
5 distinct `placement_condition_seeds`, `_run_provenance` attached, **physically PAIRED, 0 unpaired**.
Peak RSS 14.73 GiB, exit 0 — confirming the recorded `fixed_peak_gib` exactly, and confirming that
`gt4i.1` is the right tier for this family.

**This settles the risk I took when making diagnostics fail-closed.** The stated fear was that a
family whose wrapper sits behind a vector boundary would return nothing and a production cell would
now refuse rather than record. alda is that family, and the diagnostics come through complete.

### The remaining work for a clean single-hash claim

**Update: the four jobs below all SUCCEEDED after this table was written and it was not updated at
the time — caught only when the user asked "have we acted on this doc?". Corrected now.**

| family | covered by | status |
|---|---|---|
| ctrl | `bt1t3njt0m37dujrio2u` | **VALIDATED**, current hash. 4 endpoint rows, diagnostics complete, 5 distinct placement seeds, physically PAIRED, 0 unpaired |
| rlvigen | `bt1anj1cm0ni7p20ted3` (svea) | **VALIDATED**, current hash, same evidence shape. Supersedes drqv2's old-hash run; svea also gave the family's first real memory measurement (3.33 GiB) |
| dmc_gb | `bt1fttbvedaunks2r7eh` (rad) | **VALIDATED**, current hash, same evidence shape. Memory measured at 2.64 GiB |
| idaac | `bt1mjgl6r12pir8jnhe5` | **VALIDATED**, current hash, same evidence shape |
| **alda** | `bt1pb2kceart31caaqkq` (old hash only) | **still needs a re-run on the current hash** — the #47 diff does not touch alda's path, so this is confidence rather than risk, but the clean claim ("every family measured on the hash the fleet runs") is not yet true for alda specifically |
| **ppg** | `bt1ek01uo43rskotpm8b` | in flight |
| **ibac_sni** | `bt10rvhafr2muvjkpc9g` | in flight (resubmitted after CORRECTIONS #49 — a malformed override killed the first attempt) |

**So: 4 of 7 cleanly closed, alda one mechanical re-run from closed, ppg and ibac_sni pending their
current jobs.** All seven families have now been proven to execute their endpoint path at least once
since the freeze; what remains is making every one of them current on the SAME hash simultaneously.

### Suite green at the frozen revision, 2026-09-05

`pytest tests/ -q` exits **0** against code revision
`4bef9881a418c2d88a450d38a902bd3aa159d724a651741917935caa826435d2` — roughly 1497 tests, including
everything added overnight: the fail-closed diagnostics, the submission-config auditor, the
production host guard executed rather than merely present, the descriptor-string scan that catches
CORRECTIONS #47's class, and the real-environment tests that now fail on defects instead of skipping.

Read the **`PYTEST_EXIT` line**, not the wrapper's exit code. Suite v15 was reported by the harness
as "exit code 0" while pytest itself had exited 1 — the wrapper's status is the `echo`'s, not
pytest's. That is why every suite run here appends its own exit code to the log.
