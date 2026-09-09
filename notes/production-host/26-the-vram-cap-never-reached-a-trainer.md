# 26 — The VRAM cap has never reached a trainer, and a cap is the wrong instrument anyway

**2026-09-09.** Two findings, the second more important than the first.

## 1. The cap reaches our monitors, not our trainers

`ppg` was launched with `NATIVE_VRAM_CAP_MIB=10240`. The log printed
`NATIVE_VRAM_CAP_APPLIED 10240 MiB` three times. The trainer then reached **26653 MiB**.

Read directly from `/proc/<pid>/environ` inside our own container:

```
pid=3733  cap_on_pythonpath=1   python3 datasphere/native/measure_resources.py ...
pid=3745  cap_on_pythonpath=1   python3 scripts/watch_policy_health.py ...
pid=3890  cap_on_pythonpath=0   python3 -m phasic_policy_gradient.train --env_name robosuite:Door ...
```

The three "applied" lines came from **our own monitoring helpers**. The process that allocates never
had the cap module on its path.

**Cause: every one of the nine family launchers overwrites `PYTHONPATH`.**

```
runnable/_launch/ppg_cell.sh:74   export PYTHONPATH="$REPO/runnable/ppg:$REPO/runnable/_shim"
```

and the same shape in `alda.sh`, `ctrl.sh`, `dmc_gb.sh`, `ibac_sni.sh`, `ibac_sni_cell.sh`,
`idaac.sh`, `ppg.sh`, `rlvigen.sh` — none preserves `${PYTHONPATH:+:$PYTHONPATH}`.

This is the **third** instance of the same defect in one day: `run_probe.sh` discarded the cap the
same way, then `runnable/_shim`'s own `sitecustomize` shadowed it, and now the family launchers drop
it again one level further down. **Every "capped" claim in this repo is void**, including the flat
2644 MiB of the idaac 600k run — that was idaac's natural footprint, not enforcement.

## 2. A per-process cap cannot be the protection, whatever path it takes

Even fixed, the mechanism is wrong, and the reason is the dilemma the owner named:

- **Too strict** and it OOMs. `idaac` and `ppg` cannot resume (note 24), so an allocator refusal at
  hour nine of ten destroys the run — and fragmentation makes a late refusal *more* likely than an
  early one, so the cap fails hardest exactly where the loss is largest.
- **Too loose** and it protects nobody. 10240 did not stop 26653.
- **And it cannot see everything.** `set_per_process_memory_fraction` bounds the caching allocator.
  EGL/MuJoCo render buffers and the CUDA context are outside it.

A cap is **coercive**: it makes our process fail. What is actually owed to someone who booked the
card is that *they* do not fail.

## The instrument that does work is the one already built

`scripts/yield_gpu_to_neighbour.py`'s **free-memory floor**:

- it is **cooperative** — it stops our cell cleanly, at a checkpoint boundary, with artifacts
  durable on the bind mounts, rather than raising OOM inside a training step;
- it is **external** — it measures the card, so it sees render buffers, contexts and other
  people's allocations, none of which a per-process allocator cap can see;
- it is **the right question** — "is free memory low enough that a neighbour would fail?" rather
  than "has our process exceeded a number we guessed?";
- it **cannot fail late from fragmentation**, because it never denies an allocation.

It has already fired correctly twice: once on a packed pair that had taken the card, once at
`free memory 2585 MiB is below the 4000 MiB floor`.

### What to do

1. **Stop quoting the cap as a safety property.** It is not one and never has been.
2. **Keep the floor as the protection**, and size it from what a co-tenant plausibly needs, not from
   what we would like to keep.
3. Fixing the nine launchers is a **hashed-tree edit** (`runnable/_launch/*` are payload members),
   so it moves payload hashes and is an owner decision — and it buys predictability, not safety.
4. `ppg` is a **whole-card job**: 26653 MiB of 32494 at its auxiliary phase. Schedule it alone.

---

## Confirmed from production, 2026-09-09 14:53 MSK — and the scope is narrower than "the shims are off"

The finding above was read from the code. It is now measured on two live production cells.

**The arithmetic needs no per-process attribution.** The two cells declare
`NATIVE_VRAM_CAP_MIB=4096` (`idaac`) and `NATIVE_VRAM_CAP_MIB=10240` (`ppg`); their sum is
**14336 MiB**. Card 0 reports **28108 MiB**. If both caps bound their trainers, the total could not
exceed the sum plus two CUDA contexts. It is 13.7 GiB over.

**This argument survives the reserved-versus-used trap**, which is worth stating because misreading
it produced a wrong packing verdict earlier the same day. `nvidia-smi memory.used` is the
allocator's *reserved* pool, so it overstates live usage — but a per-process memory fraction bounds
what the allocator may reserve at all. Reserved above the cap therefore proves the cap is not in
force, whichever way the reserved/live gap runs. A reading that is an overestimate of usage is still
a valid *lower* bound on the permitted ceiling.

## Where the cap DOES apply, which is why the verification is not lying

Counting `NATIVE_VRAM_CAP_APPLIED` in the `idaac` job log against the cell boundaries:

| window | APPLIED events |
|---|---|
| before `NATIVE_CELL_BEGIN` (lines <807) | 8 |
| the training window (807-1722) | 5 |
| after training, the curve and endpoint evaluation (>1722) | 15 |

The cap applies to the runner's own Python and to `eval_grid.py`, which `run_probe.sh` invokes
directly. It does not bound the trainer, which `runnable/_launch/*.sh` starts after replacing
`PYTHONPATH`. The five events inside the training window are short-lived helper processes, not a
trainer that would apply it once at import — and `ppg` holding roughly 21 GiB against a 10240 MiB
declaration settles which it is.

So `NATIVE_VRAM_CAP_IN_FORCE 4096 MiB, sitecustomize resolves` is **true of the process that printed
it and false of the process that matters**. That is the failure shape this project keeps meeting: a
check that agrees with our own code and with nothing outside it.

## What the clobber does NOT break, checked rather than assumed

All nine launchers replace `PYTHONPATH`, but **every one of them re-adds `$REPO/runnable/_shim`**:

```
idaac.sh     $REPO/runnable/idaac:$REPO/ext/baselines:$REPO/runnable/_shim/no_tf:$REPO/runnable/_shim
ppg_cell.sh  $REPO/runnable/ppg:$REPO/runnable/_shim
rlvigen.sh   $RLV:$RLV/algos:$RLV/envs/robosuiteVGB:$REPO/runnable/_shim
```

So `sitecustomize.py`, `safe_checkpoint.py`, the `wandb` stub and `no_tf` all still reach the
trainer. The earlier phrasing invited the reading that the shim layer is disabled in production; it
is not. **The single casualty is the VRAM-cap directory**, which `run_probe.sh` prepends and no
launcher re-adds.

`rlvigen.sh` also omits `third_party/robosuite`, which `run_probe.sh` does add. That one is inert:
`idaac.sh` names no RL-ViGen path at all and its cell has been training robosuite Door for eleven
hours, so robosuite is importable from the installed environment rather than from `PYTHONPATH` —
which is what `run_probe.sh:1731` already says, that the path entries are an optimisation rather
than a requirement.

**Consequence for the open item.** The defect is real, is confirmed in production, and is *narrow*:
it disables an instrument the ledger has already ruled to be the wrong instrument, and the
free-memory floor with a cooperative yield is what actually protects a co-tenant. Nothing here
argues for editing nine hashed launchers mid-campaign.
