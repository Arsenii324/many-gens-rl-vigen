# 30 — Did we crowd anyone out? Measured, per cell, from the sampler

**2026-09-10.** Eight cells ran on card 0 today. This is the audit of what they took, from each
cell's own `resources.json` rather than from recollection.

## The three resources, separately

| resource | worst we reached | host capacity | verdict |
|---|---|---|---|
| **VRAM** | **32,435 MiB — 329 MiB free** (`ctrl` at v100) | 32,768 MiB | **overused, once** |
| RAM (process-tree RSS) | 28.02 GiB (`ctrl` at v100) | 125 GiB, 112 available | comfortable |
| disk | never below **264.7 GiB free** | 20 TB, ~289 GiB free at start | comfortable |

**The `Bus error` that killed `svea` was not host memory.** It was `/dev/shm` at Docker's 64 MB
default — a limit *inside our own container*, invisible from the host and unrelated to what anyone
else had.

## Co-tenancy: we were rarely alone, and it mattered less than it looks

| cell | samples | co-tenant present | peak card VRAM while co-tenanted | min free VRAM |
|---|---:|---:|---:|---:|
| `ppg` | 221 | **100 %** | 8,025 MiB | 24,743 MiB |
| `idaac` | 428 | **100 %** | 2,642 MiB | 30,126 MiB |
| `alda` | 631 | **100 %** | 2,401 MiB | 30,367 MiB |
| `ibac_sni` | 73 | **100 %** | 7,423 MiB | 25,345 MiB |
| `soda` | 587 | **100 %** | 2,533 MiB | 30,235 MiB |
| `svea` | 88 | **100 %** | 1,459 MiB | 31,309 MiB |
| `ctrl` (datasphere) | 76 | 0 % | — | 20,053 MiB |
| **`ctrl` (v100)** | 185 | **0 %** | — | **329 MiB** |

**Six of eight cells shared the card for every single sample.** During all of them the card never
went past **8,025 MiB used** and never had less than **24.7 GiB free**. On `ibac_sni` our own
process held 1,583 MiB while the card showed 7,423 — the other 5.8 GiB was somebody else's, and we
sat beside it without contending.

## The one real exposure, and why it did no harm

`ctrl` at the **v100** profile is `num_envs=64`. It took **32,435 of 32,768 MiB — 99 % of the card,
329 MiB free.** Any neighbour allocating at that moment would have failed, and on a shared card the
process that asks *second* is the one that dies.

**It did no harm only because nobody else was there**: co-tenant present in **0 of 185 samples**.
That is luck, not design, and it is the reason the yield watch exists — it fired at
`free memory 1210 MiB is below the 4000 MiB floor` and stopped our own cell.

**Rule this fixes in writing: `ctrl` at v100 and `ppg` at its auxiliary phase (26,653 MiB) must
never be scheduled on a card that is not ours outright.** `ctrl` at the `datasphere` profile
(`num_envs=16`) peaks at 12,710 MiB and left 20 GiB free — that is the co-tenantable configuration,
and it is what the attestation wave uses.

## What the numbers say about the battery

The battery is one cell at a time on card 0. Only two of the twelve baselines are whole-card jobs at
their production profiles, and both are identifiable in advance. Everything else measured today sits
under 8 GiB of VRAM and leaves the card usable by someone else — which is the condition the
[upper-bound rule](10-resource-upper-bound-rule.md) actually asks for.
