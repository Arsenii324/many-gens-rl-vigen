# What the harness does, end to end — a model you can check

Written 2026-09-16 from tracing the code, not from memory. Every claim here names the file that
establishes it, so a reader can disagree with the source rather than with me. Where a thing is
NOT established, it says so.

Scope: one production cell, from a payload archive to a row in the evaluator ledger — including the
paths that are not the golden one, because those are where this project has lost runs.

---

## 1. The shape of a cell

```
launch-card-cell.sh   (host; arms watches, refuses bad conditions)
  └─ run_on_production_host.sh   (host; mounts, env allow-list, docker run)
       └─ run_probe.sh   (in container; the cell itself)
            ├─ bootstrap: apt + pip                      ~10-50 min, unpinned apt
            ├─ run_measured → the family's own train.py  BLOCKING
            ├─ verify_final_evaluation
            ├─ family.py retain          ← checkpoints leave the run dir
            ├─ family.py check-finite    ← refuses a NaN'd snapshot before any GPU spend
            ├─ run_curve_eval_with_policy    if CURVE_EVAL=1
            ├─ run_endpoint_eval             if ENDPOINT_EVAL=1
            └─ collect_record_delivery   ← merges everything into records_delivery.jsonl
```

**All evaluation is post-training and sequential** (`run_probe.sh:506-538`). There is no parallel
evaluator and no rolling eval from our harness.

## 2. Where bytes live, and what survives a kill

| path (container) | host | survives container death |
|---|---|---|
| `/tmp/native-work` | `NATIVE_WORK_HOST_DIR` | **yes**, bind-mounted (`run_on_production_host.sh:775`) |
| `/tmp/native-out` | `NATIVE_OUT_HOST_DIR` | **yes**, bind-mounted (`:774`) |
| container layer | — | no |

Both mounts exist because of a measured loss: *"a container killed at hour 20 of a 27-hour drqv2
cell lost every checkpoint; only training.log was durable"* (`:604-622`). The families write
checkpoints under `$work_root/runs/<cell>`, and they reach `native-out` only when `retain` runs,
which is AFTER training. Mounting only `native-out` was not enough, and the comment says so.

**The one thing still lost on a kill is DELIVERY.** `collect_record_delivery` runs last; a cell
reaped before it leaves per-cell `offline_eval_*.jsonl` on the mount with nothing assembling them
(`launch-card-cell.sh:110`). That is why the reaper is progress-aware and why the watch budget
matters.

## 3. Seeds, and what is actually reproducible

- **Placement** is per-episode content-addressed:
  `placement_condition_seed(eval_seed, scene_id, episode_index)` via `SeedSequence`, re-seeded
  before every episode (`eval_grid.py:230-241`). It omits the REGIME deliberately, so every regime
  sees identical initial conditions and train-vs-eval is a paired comparison.
- **torch is NOT re-seeded per episode.** It is seeded once at family setup (`eval_grid.py:221`).
  For the three SAMPLING baselines (idaac, ppg, ibac_sni) the action stream therefore depends on
  how much torch RNG was consumed before a cell.
- **Measured consequence:** two byte-identical invocations gave 25.794515705108644 and
  26.052958893775940 — a spread of **0.095 SE** at n=20. Small, but exact reproduction is
  impossible and any claim of it is false. See `endgame/RESOLVED-ppg-reeval-is-within-evaluator-noise.md`.

## 4. The eval grid, as actually run

Set INSIDE the container by `production_env` from `families.json`, not by the launcher:

```
CURVE_EVAL_REGIMES  = train,eval-easy,eval-medium,eval-hard      (4)
CURVE_EVAL_SCENES   = 0..9        → 11 scene sets (ten scenes plus the pooled set)
CURVE_EVAL_EPISODES = 3           A20, 2026-09-05 -- three, not the five an older note recommends
ENDPOINT_EVAL_EPISODES = 20
ENDPOINT_EVAL_POLICY_MODES = native,mode        ← TWO passes
```

Per 600k cell: curve 13 stamps x 44 rows x 3 ep, endpoint 44 rows x 20 ep x 2 modes = **3,476
episodes**, ~17.4 h at the measured **11.65 s/episode**.

**The regimes are distributions, not a difficulty ladder.** `eval-medium` alone sets
`except_robot=False`, randomising the robot's own appearance; easy and hard perturb background and
lighting with the robot fixed. Measured for ppg: eval-medium scores BELOW eval-hard in both passes,
and 60% of its slots vary across passes against 0% for train and eval-easy
(`audit_eval_validity.py`). So eval-medium and eval-hard are **not paired**, and a paired claim
about them is not available.

## 5. The guards, and what each refuses

Every one of these fired at least once today, which is the only evidence that a guard works.

| guard | refuses | fired |
|---|---|---|
| preflight `--require-exclusive` | any foreign compute process on the card | card 1, when a colleague took it one minute after our smoke ended |
| preflight memory floor (4000 MiB) | starting without headroom | card 1 at 3010 MiB free |
| `--max-util` | a busy card | waived only with `NATIVE_ALLOW_SHARED_CARD=1`, together with exclusivity |
| disk watch | free space near a computed floor | armed at 106-138 GiB across tonight's cells |
| `NATIVE_PRODUCTION` scale check | production frames without the production flag | the first re-eval attempt |
| `NATIVE_PRODUCTION_STRICT` | **a trimmed protocol at production scale** | `CURVE_EVAL=0 expected=1` |
| result-mirror same-device | one failure domain for results | accepted explicitly, with reasons, for eval-only cells |
| `check-finite` | a NaN'd checkpoint, before any grid | not seen tonight |
| ledger `populate` | a record whose closure is not live | ctrl, repeatedly, until its cuDNN pin landed |

**The memory floor is never waived.** Utilisation contention costs time; memory exhaustion costs
someone else's run, and our per-process VRAM cap does NOT bind — `PYTHONPATH` is overwritten by all
nine family launchers, and ppg once reached 26,653 MiB under a 10,240 MiB cap.

## 6. Collection, which is not compute

`collect_record_delivery` writes `records_delivery.jsonl` to the mounted volume as the cell ends.
"Collection" is the separate, MANUAL step of copying that into `results/records/<job>__records.jsonl`
with `datasphere/native/collect-host-run.sh`. It runs on the operator's machine because the host
rule is docker and trivial shell only.

[Corrected 2026-09-19. This paragraph told the reader to run `populate_evaluator_ledger.py`.]
**Never run `populate_evaluator_ledger.py` by hand on a production run**: it records a family's
*attestation*, and `OPERATOR-GUIDE.md` §8 item 4 is the rule. The collector calls it itself
(`collect-host-run.sh:310`) and a production run being declined there is the correct outcome. Nothing is at risk while
uncollected; the bytes are already durable.

## 7. What this model does NOT cover

- **Resumption.** `families.json:160`: `keys_to_save` omits the replay buffer, so an off-policy run
  restarted from a snapshot is a different experiment. Splitting a long run across jobs is not
  available to the RL-ViGen five. Intermediate checkpoints remain EVALUABLE either way.
- **ctrl at the v100 profile.** 64 envs is the upstream count and the faithful one, modelled at
  54.28 GiB by linear extrapolation with "direct V100 measurement still required", and ~31 GB of a
  32 GB card. Fidelity and runnability disagree there and the disagreement is unmeasured.
- **The bootstrap.** apt and pip run per cell and are not pinned beyond the requirements hash;
  `gate_environment_manifest` carries this as OWNER and it is the reason ctrl's cuDNN had to be
  pinned by hand.
- **Throughput under packing.** 11.65 s/episode was measured on a card shared with one colleague.
  It is used for budgets and has not been re-measured under heavier packing.
