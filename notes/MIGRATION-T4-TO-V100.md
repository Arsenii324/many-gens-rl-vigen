# Migration surface — everything that changes when the runner moves to the V100 host

This is the **host-delta** category: values, assumptions and checks that are correct on DataSphere
and wrong on the production host, or vice versa. It exists because those deltas were scattered
across five documents and one JSON key, and **the expensive failure mode is applying half of them.**

**Measured production host** (`notes/remote-infra.txt`, 2026-09-05): 16 cores (2×8 Xeon Gold 6154
@3.0 GHz, 1 thread/core), **113 GB available RAM**, **2× Tesla V100-SXM2-32GB**. **GPU 0 is occupied
by another user** (15.1 GB, 67% util); GPU 1 free.

**Development platform**: DataSphere `gt4.1` (4 cores, 14.5 GiB usable, T4) and `gt4i.1` (8 cores,
27 GiB usable, L4).

**Bounded DataSphere V100 validation allocation** (owner-authorized 2026-09-05, raised twice
since): `g1.1` only, with a cumulative hard ceiling of **7.0 GPU-hours (420 minutes)** as of
2026-09-06 (`datasphere/native/job.sh`'s `V100_BUDGET_CAP_MINUTES`, raised 120→240→420; check
`job.sh v100-budget status` for what's actually left, not this number, since it only records the
cap). This is a pre-production validation allowance, not the production host and not authority to
begin the fleet. Before a `g1.1` submission, the local ledger must reserve its declared wall-time
within whatever remains of the cap; after it ends, record the observed job lifetime and reconcile
the reservation. The
first permitted use remains a frozen-current evaluator/renderer or resource control, never an
unbounded exploratory retry. `g1.1`'s V100 hardware does **not** make it the production
`NATIVE_HOST_PROFILE=v100`: that profile represents the separate 16-core, 113-GiB owner host,
whereas `g1.1` has 8 vCPUs and 48–96 GiB RAM. A g1.1 evaluator/renderer control therefore keeps
the DataSphere profile unless it declares and fits a specifically justified alternative shape.

---

## Why this is a surface and not a checklist item

**One descriptor serves two machines with incompatible limits.** `families.json`'s `constants` and
`production` blocks feed *both* the probe fleet and production; `family.py` reads one of each. There
is no dimension saying "this value on DataSphere, that value on the V100."

The two failure directions are **not** symmetric:

- **Too large on DataSphere** → OOM or thrash. Loud. `alda` was SIGKILLed exactly this way.
- **Too small on the V100** → runs perfectly and quietly measures a **32×-rescaled PPG**. Silent,
  and it produces valid-looking numbers of the wrong experiment.

So the risk to guard is not breakage; it is a successful run of something we did not intend.

**The real fix is now built**: `families.json` declares the `datasphere` and `v100` profiles, and
`NATIVE_HOST_PROFILE` selects the latter explicitly. `family.py` resolves the selected profile into
the training command and production environment; `run_manifest.json` records its name; and the
profile is folded into the fixed-width evaluator revision hash. Thus normal revision-equality
checks reject DataSphere and V100 rows rather than relying on every analysis tool to notice a
manifest field. The default remains `datasphere`, so existing probe configs cannot inherit V100
values accidentally.

## The deltas, all of them

### 1. Parallelism — selected by the explicit `v100` profile, never by default

| baseline | source | current (DataSphere-safe) | V100 target | effect |
|---|---:|---:|---:|---|
| `ibac_sni` | 16 procs | 1 | **16** | **matches upstream exactly; 16× gap closed** |
| `idaac` | 64 procs | 4 | **16** | 16× → 4× |
| `ppg` | 4 MPI × 64 = 256 envs | 8 | **8** | remains 32×; preserves the published continuous-control auxiliary-phase cadence |
| `ctrl` | 64 envs | 16 | **64** | upstream parallelism restored; must be measured directly, not extrapolated |

16 cores will not host 64 or 256 robosuite environments, so `idaac` and `ppg` remain declared
deviations — smaller ones. `ibac_sni` is the one that closes completely.

### 2. Replay capacity — the adaptation that disappears

`production.replay_capacity` is **300,000** because no DataSphere tier holds the **38.8 GiB** an
uncapped cell needs at 600k (`gt4i.1` ≈ 27 GiB). With **113 GB**, one uncapped cell fits comfortably
and two fit at 77.6 GiB.

**Target: 620,000** — this is what the `v100` profile actually resolves to as of 2026-09-05, not
1,000,000. `action_repeat=1` (`rlvigen.sh:78`) means a 600,000-frame budget produces 600,000 agent
steps plus ~1,200 reset entries, so **620,000 never evicts** and restores uniform-over-the-run
sampling for `drqv2`, `drq`, `svea`, `sgqn`, `curl` in full. It costs **40.0 GiB per cell against
62.4 at 1M**, which is the difference between **two** RL-ViGen cells per host and **one**.

**The 1,000,000 exception, retained:** it is behaviourally identical to 620,000 at this budget and
becomes meaningful only if the **frame budget is raised above ~620k**. If that happens, 1M is the
right target and the packing cost is the price of it. At 600k it buys nothing.

The `v100` override applies the value to the `production` block — not a top-level lookalike.
`family.py` resolves `production.replay_capacity`; a top-level key of the same name would be a
no-op that leaves two disagreeing values in one file.

### 3. Renderer — C95, and it is a gate not a note

A container-trained checkpoint read under a different renderer gave **131.5 vs 13.85**. The rule
survives the move; the *measurement* does not. Because the environment is ours to choose:

- build the image to match the validated renderer (`MUJOCO_GL=egl`);
- pin the **image digest**, not a mutable tag;
- **reproduce one known cell before the fleet** — first remeasure a checkpoint on the current
  evaluator/container to establish R_A, then evaluate that exact checkpoint on V100 as R_B. The
  archived 480.6 predates measurement-affecting evaluator fixes, so it is not a renderer control.

### 4. Throughput model — every FPS figure is T4-derived

`plan_production.MEASURED_FPS_GT4_1` was measured on `gt4.1`. A V100 is typically 1.5–2× a T4 for
fp32, but **that factor is assumed and swings the schedule by a factor of two**. Measure it with one
short cell on arrival. Note that applying §1 changes throughput again — more environments collect
frames faster when cores allow — so the model must be recomputed *after* the host targets are
applied, not before.

### 5. Scheduling — GPU 0 is not free

A13's calendar assumed two V100s. With one, **9–14 days becomes 18–28**. Confirm whether GPU 0
frees before scheduling; if not, prefer the longest cells first (`soda` 45 h, `rad` 24 h, `sgqn`
22 h) so an envelope failure surfaces on day 1–3 rather than day 12.

### 6. Gates that are DataSphere-scoped and must not be read as production checks

`scheduler RAM invariant`, the tier table, grant/RUB arithmetic. They protect the probes we still
run here. Their production analogue is §3 above.

## Migration order

This list is host mechanics only — the steps that change because the machine changed. It assumes
[`review-11-12-gemini-triage.md`](review-11-12-gemini-triage.md)'s own "Recommended dependency
order" (T1–T30, a *different* ordering, for defect repair and design-point decisions) has already
been worked through its steps 1–5, since several of *those* items are silent prerequisites here:
its T13 is this list's step 2, its T9 is this list's step 4, and its T10/T14 belong before step 2 as
well. Corrected 2026-09-05: this list previously ended at "schedule the fleet" with no canary step
of its own — a real gap against the other order's step 7, closed below as step 6.

1. Confirm GPU availability and measure the V100/T4 factor (one short cell). **Also measure CTRL
   at its restored `num_envs=64` here, not just confirm it launches.** `families.json`'s "~54 GiB"
   for 64 envs is a LINEAR EXTRAPOLATION from the measured 16-env peak (13.57 GiB x 4), never
   measured directly — external review 14 section 10 named this specifically: "JAX memory behavior
   cannot safely be extrapolated linearly." 113 GiB host RAM gives real headroom over 54 GiB, but a
   superlinear XLA buffer/compilation cost at 4x the batch size is not ruled out by that margin
   alone. One real measurement here, before trusting the packing plan, closes it.
2. Build and **digest-pin** the image, then verify the renderer as a **three-step control**, NOT by
   reproducing the archived 480.6 — that number predates per-episode condition seeding, deterministic
   kernels and strict regime verification, so a mismatch against it would confound renderer with
   evaluator revision, which is the one thing this probe exists to separate:
   **(a)** re-measure the chosen checkpoint on the CURRENT evaluator, wherever it can run today, to
   get `R_A`; **(b)** measure the same checkpoint, evaluator and container on the production host to
   get `R_B`; **(c)** compare `R_A` with `R_B`, where the platform is then the only changed factor.
3. Select `NATIVE_HOST_PROFILE=v100`, which applies §1 and §2 **together** to resolved constants
   and production settings; verify the manifest carries `host_profile: v100`.
4. Recompute `plan_production` and regenerate the schedule whenever a descriptor changes. The
   current checked-in V100 schedule is at 600k; it is still a throughput estimate until a V100
   resource/throughput control measures each relevant runtime shape.
5. Re-run `scripts/production_gates.py` and confirm nothing DataSphere-scoped is being read as a
   production pass.
6. **Run the `ibac_sni` competence pilot at the final geometry, `procs=16`, on this host** —
   `production_gates.py`'s own standing OWNER item ("ibac_sni competence": `entropy_coef=0` removes
   the runaway, measured, but the evidence so far is ~25k frames with zero success events, at
   `procs=1` — a different rollout geometry, not the production one). DataSphere's `gt4i.1` tier
   proved only a short functional smoke (the process path is runnable, not that it competes); this
   is the one pilot that genuinely cannot be reached from DataSphere at all, since `procs=16`
   needs this host's core count and RAM to sustain long enough to show learning. Long enough means
   past the point the existing ~25k-frame evidence stops, not another short smoke.
7. Run the T15 canary — train → stamp → retrieve → **fresh-process** reload → full grid → records —
   end to end on this exact frozen evaluator, image and host. This is the step that turns "the
   pieces each work" into "the pipeline works"; nothing before it has run the whole loop at
   production scale. Only a pass licenses step 8.
8. Only then schedule the fleet.

**Separately, not a host-migration step**: `scripts/requirements.py`'s R7 needs someone who has not
seen this repository to run the documented clone-to-curve path end to end, on a clean machine,
timed. No amount of work on this host substitutes for it — it is a different kind of check (a human
acceptance test, not a resource or renderer control) and belongs on the pre-production checklist
independently of when the steps above happen.

**If you apply only some of §1–§2, say which in the records.** A run at 16 `ibac_sni` processes with
a 300k replay cap is a third configuration that neither machine was analysed for.
