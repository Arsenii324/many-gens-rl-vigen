# What the harness does, end to end — a model you can check

Written 2026-09-16 from tracing the code, extended 2026-09-19 with the launch chain before the
container (§0) and the value-resolution trace inside it (§1b). Every claim names the file that
establishes it. New statements tag how they're known: `[read in code 2026-09-19]`, `[executed]`
(an actual host run), or `[doc claims, not re-verified]`.

Scope: one production cell, from a payload archive to a row in the evaluator ledger — including the
paths that are not the golden one, because those are where this project has lost runs.

---

## 0. Before the container

```
wait-and-train-v4.sh (host, optional)
  └─ train-production-cell-v5.sh / -v6.sh (host)
       └─ launch-card-cell.sh (host)
            └─ run_on_production_host.sh (host)
                 └─ docker run → run_probe.sh, §1
```

**`wait-and-train-v4.sh`**, optional, launches only after `HOLD` (10) one-minute samples with no
foreign holder and `NEED` (11421) MiB free (`host-scripts/wait-and-train-v4.sh:37-38`), then
forwards `CARD FAMILY BASELINE SEED EXPECT_OURS VRAM_MIB` to whichever wrapper `WRAPPER` names
(`:184-186`). **`WRAPPER` defaults to v5**: `WRAPPER="${WRAPPER:-train-production-cell-v5.sh}"`
(`:51`). v5 hardcodes its payload path (`"$R/payload-v214-$FAMILY.tgz"`, v5 `:65`) and has no
Places365 handling; a Places365 baseline (svea, sgqn, soda) needs
`WRAPPER=train-production-cell-v6.sh` explicitly, or the waiter launches the wrong wrapper with the
wrong payload and no corpus — **(1) the wrapper trap**: v5 cannot take `PAYLOAD` or `PLACES365_DIR`
at all, the two knobs v6 adds. [read in code 2026-09-19]

**v5/v6** map operator names onto the `NATIVE_*`/`CELLS` names the rest of the chain reads (both
`env CARD=... NATIVE_YIELD_ON_PROCESSES=... NATIVE_EXPECT_OURS=...` at `:58`):

| operator name | becomes | default | file:line |
|---|---|---|---|
| `CARD` | `CARD` | `0` | v5/v6 `:58` |
| `YIELD_PROCS` | `NATIVE_YIELD_ON_PROCESSES` | `0` | v5/v6 `:58` |
| `EXPECT_OURS` | `NATIVE_EXPECT_OURS` | `8` | v5/v6 `:58` |
| `VRAM_MIB` | `NATIVE_VRAM_CAP_MIB` | `4096` | v5/v6 `:62` |
| `TIMEOUT_S` | `CELL_TIMEOUT_SECONDS` | `43200` | v5/v6 `:61` |
| `FAMILY`,`BASELINE`,`SEED` | `CELLS="$BASELINE:$SEED"`, `SEED` | `ibac_sni`,`ibac_sni`,`101` | v5 `:53,60`, v6 `:42,60` |
| `PLACES365_DIR` (v6 only) | `NATIVE_PLACES365_DIR_HOST` + `NATIVE_PLACES365_SPLIT=train` | unset | v6 `:49-52` |
| — (v6 only) | `PAYLOAD` overridable, default `$R/payload-v214-$FAMILY.tgz` | v5's hardcode | v6 `:44` |

[read in code 2026-09-19]. Both hardcode `NATIVE_ALLOW_SHARED_CARD=1 NATIVE_HOST_PROFILE=v100
NATIVE_PRODUCTION=1 NATIVE_ACCEPT_SAME_DEVICE=1 ENDPOINT_EVAL=1` (v5/v6 `:59-64`) — a stance, not a
knob. **`launch-card-cell.sh`** sizes the watch budget from `CELL_TIMEOUT_SECONDS` plus a bootstrap
allowance plus an eval allowance read from `family.py production-env` (`:140-155`), arms the three
watcher containers (§5, §6), then calls `run_on_production_host.sh` (`:475`), which reads the
pinned image from `source-lock.json` (`:285`) and runs `docker run` (`:880-893`). [read in code
2026-09-19]

**(2) Two code sources.** Everything above runs from the host's own checkout under
`~/rlvigen-work/` — flattened copies of the wrapper scripts (`wait-and-train-v4.sh:131,186`
`"$HOME/rlvigen-work/$WRAPPER"`; v5/v6 `cd "$R/repo"`, v5 `:52`, v6 `:41`). `run_probe.sh`,
`family.py`, `families.json` and everything after `docker run` execute from the **payload** archive
extracted inside the container (`run_on_production_host.sh:886-892`: `tar xzf code.tgz -C code; cd
code; bash datasphere/native/run_probe.sh ...`). A fix ships by a different route depending on
which side of `docker run` it is on; the host checkout's `git log` is not evidence of what runs
there — compare file hashes. [read in code 2026-09-19; same correction in
`notes/OPERATOR-GUIDE.md:283-285`, written 2026-09-19]

**(3) The allow-list is the only crossing point.** `run_on_production_host.sh:811-829` is the
`for name in CELLS FRAMES TASK SEED ...; do ... -e "$name=$value"; done` loop (plus a few explicit
`-e` statements, e.g. `RLVIGEN_ARCHIVE` at `:602`); a variable off it is dropped silently.
`RESUME_SNAPSHOT` (`run_probe.sh:361-371`) is **not on this list**. [read in code 2026-09-19] It
DOES reach a cell via the separate DataSphere `job.sh`/`cfg-*.yaml` path —
`cfg-drqv2-resume-v43.yaml:22` sets `RESUME_SNAPSHOT=${RESUME}` in a `cmd:` block that path forwards
whole — so the gap is specific to this five-script host chain, not the repository. [read in code
2026-09-19; corrects `notes/inventory-2026-09-19/code.md:237`'s "absent from every… `cfg-*.yaml`"]

**(4) The dry run stops before the container.** `NATIVE_HOST_DRY_RUN=1` returns at
`run_on_production_host.sh:865-877`, before the real `docker run` at `:880` — it exercises none of
the in-container logic. On 2026-09-19 `svea` s101 died on a `run_probe.sh` Places365 path no dry run
could have reached (`PLACES365_EXPECTED_COUNT` required even for a mounted corpus); fixed in commit
`6458c05`. [read in code 2026-09-19; commit verified in `git log`/`git show`]

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

## 1b. How a value reaches the training process

Lowest to highest precedence (`datasphere/native/family.py`, read in full 2026-09-19):

1. **families.json base descriptor** — `family.py:34` `json.loads((path or
   DESCRIPTORS).read_text())`.
2. **`host_profiles.<profile>` override** (`NATIVE_HOST_PROFILE`, default `"datasphere"`), merged
   per SECTION not deeply — `family.py:64` `override = entry.get("host_profiles",
   {}).get(host_profile(path, profile), {})`. Only `rlvigen`, `ibac_sni`, `ctrl` declare a `v100`
   block (`families.json:48,768,929`); `dmc_gb`, `idaac`, `alda` have no `host_profiles` key, and
   `ppg`'s is `{}` (`:607`) — for those four, `NATIVE_HOST_PROFILE=v100` changes nothing, a fact
   about the descriptors, not a defect. [read in code 2026-09-19]
3. **Caller `fields` over descriptor `constants`** — `family.py:150` `{**entry.get("constants",
   {}), **fields}`; `run_probe.sh` always passes `--frames/--seed/...` explicitly, so `family.py`'s
   own argparse defaults never fire here.
4. **Derived fields, filled only if absent** — `family.py:139` `merged.setdefault("save_every",
   merged.get("frames", ""))`.
5. **Production-scale overlay, one shell layer up** — `run_probe.sh:829` `if [[ -z "$current" ]];
   then` exports a `production_env()` value only if unset; strict mode refuses a disagreement
   instead, automatic at `FRAMES>=600000` (`:819-821`).
6. **`NATIVE_EXTRA_OVERRIDES`, appended as extra argv tokens** — highest precedence, outside
   `family.py` entirely: `run_probe.sh:508` `bash "${argv[@]}"
   ${extra_overrides[@]+"${extra_overrides[@]}"}`.
7. **`render()`** — `family.py:118` `template.format(**fields)`, raising via `fail()` on an
   unresolved key rather than defaulting.

[read in code 2026-09-19]

`NATIVE_EXTRA_OVERRIDES` is produced from a descriptor's `replay_capacity`/`replay_capacity_option`
pair, to cap an off-policy replay buffer at production scale (`family.py:730,734`:
`out["NATIVE_EXTRA_OVERRIDES"] = render(option, {"replay_capacity": str(capacity)})`), lands last in
the executed argv (`run_probe.sh:508`), and is recorded TWICE in `effective_config.json`: under
`"argv"` (`run_probe.sh:491`) and again under `"extra_overrides"` (`:492`), so its provenance
survives without diffing two argv lists. **[executed]** the real `svea` s101 cell run on 2026-09-19
(`runs/card1-20260919-204235/native-out/cells/svea-s101/effective_config.json`) carries
`"replay_buffer_size=620000"` in both fields. **The rule this implies**: a cell's own
`effective_config.json` is the authority on what actually ran — above `families.json`, above a
wrapper's default, above this document — written once, when the argv is known
(`run_probe.sh:424-501`), never re-derived downstream. [read in code 2026-09-19]

**Double defaults, re-confirmed**:

| variable | production-wrapper default | `run_probe.sh` / `family.py` default |
|---|---|---|
| `SEED` | `101` (v5 `:53`, v6 `:42`) | `1` (`run_probe.sh:854,1437`; `family.py:1335`) |
| `FRAMES` | `600000` (v5 `:54`, v6 `:43`) | `10000` (`run_probe.sh:738` +8 sites; `family.py:1331`) |
| `EVAL_EVERY_FRAMES` | not set — rlvigen's online eval is disabled at production scale (§4) | `$frames` (`run_probe.sh:878`) vs `50000` in `launch-card-cell.sh:165`'s stamp estimate |
| `NATIVE_EXPECT_OURS` | `8` (v5/v6 `:58`) | `$_cell_count` = `1` for a serial run (`launch-card-cell.sh:90`) |

[read in code 2026-09-19]

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
- **torch is NOT re-seeded per episode.** [Corrected 2026-09-20: this said "seeded once at family
  setup".] It is re-seeded at the start of every ROW — each `run_scene_*` begins with
  `seed_the_placement_rng`, an absolute reset of `random`, `numpy` and torch (`eval_grid.py:221`) —
  and not again between the episodes inside that row. So rows are independent of the order they run
  in, which is what makes evaluating them in parallel possible.
  For the three SAMPLING baselines (idaac, ppg, ibac_sni) the action stream inside a row therefore
  depends on the episodes before it in that SAME row. [2026-09-20: this sentence used to say "how
  much torch RNG was consumed before a cell"; with an absolute reseed per row that cannot be the
  mechanism. The measured spread below is real and its cause is now OPEN — GPU kernel
  nondeterminism in the sampling path is the obvious candidate and is untested.]
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

[Corrected 2026-09-20.] That count is ~10% high and the per-episode time correspondingly low: the
11th "pooled" row per regime is a concatenation of the ten per-scene results already in hand
(`scripts/eval_grid.py:1305`), not new rollouts, so a row set is 40 rollout rows, not 44. Real
counts: curve 13 x 40 x 3 = 1,560; endpoint 40 x 20 = 800 per pass, and the second (`mode`) pass
exists only for `idaac`, `ppg`, `ibac_sni`. So ~2,360 episodes for nine baselines and ~3,160 for
those three. The measured `idaac` cell: 4.95 h training, 4.60 h curve evaluation, 5.52 h endpoint
grid (`launch-card-cell.sh:98-105`). **Evaluation is one process on one CPU core with the GPU
nearly idle** (841 MiB, single-digit utilisation) — that, not the grid's size, is why it costs
twice the training time of a fast baseline.

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

**What no guard bounds: host RAM.** `notes/OPERATOR-GUIDE.md:265`: "Host RAM is not checked by the
launcher... a cell's RAM figure with what the host has free." The only RAM check in this chain is
`wait-and-train-v4.sh`'s `MIN_RAM_GIB` (`:59`, default `0` = off; checked at `:170-177`), and a hand
launch or a direct v5/v6 launch bypasses it — it lives only in the optional waiter. [read in code
2026-09-19] **No native (RL-ViGen) cell's host RAM has been measured on this host** —
`OPERATOR-GUIDE.md`'s resource table (§4c.1) marks `drqv2`, `drq`, `curl`, `svea`, `sgqn`, `soda`
"never measured here"; the ~40 GiB quoted there is 36.7 GiB computed replay plus a 3.3 GiB peak
measured on DataSphere for `svea` — a different baseline, a different host, not this one. [doc
claims, not re-verified beyond the cited table]

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
- **The evaluator's per-family branches.** `scripts/eval_grid.py`'s `run_scene_dmc_gb/idaac/ppg/
  ibac_sni/alda/ctrl` (`:379,480,647,749,884,1036`) and the bare `run_scene` it imports for rlvigen
  (`:82`, from `scripts/eval_across_scenes.py`) are not traced here, nor are
  `datasphere/native/normalize_curves.py`'s seven per-family curve-log parsers (`read_rlvigen`,
  `read_dmc_gb`, `read_idaac`, `read_alda`, `read_ppg`, `read_ibac_sni`, `read_ctrl`,
  `:260,291,316,340,402,468,498`) — each is called, none read past its signature. [read in code
  2026-09-19]
- **A seam found and fixed today.** `scripts/record_host_run.py` took the seed only from an argv
  `--seed VALUE` token; rlvigen's own hydra template renders `seed=101` and never matches, so every
  rlvigen host-run entry would have recorded seed `None` and been bucketed under seed `0`
  (`scripts/campaign_status.py:151,178`). Fixed in commit `415687c` (2026-09-19) by reading
  `effective_config.json["seed"]` first (`scripts/record_host_run.py:63-67`), falling back to argv
  only if absent. [read in code 2026-09-19]
