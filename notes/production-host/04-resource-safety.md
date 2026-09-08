# Resource safety

**Assume nothing is free.** Not the GPU, not VRAM, not RAM, not the cores, not the disk. Every one
of them is shared, and the failure mode is not our job dying — it is someone else's.

## The rule that subsumes the rest

**No action of ours may cause another process to fail.** Not an OOM kill, not a CUDA OOM, not a
disk-full write error, not eviction from page cache, not starvation on the run queue. If an action
*could* do that and we cannot show it will not, it is not taken.

## GPU and VRAM

`cds2` has 2× Tesla V100-SXM2-32GB.

- **Check occupancy before claiming anything**: `nvidia-smi`. Read used VRAM, running processes and
  utilisation on **both** cards.
- **Never take a card that is in use, and never take both.** Pin one, at the Docker level:
  `DOCKER_GPUS='"device=N"'` where `N` is a card verified free in that moment.
- `CUDA_VISIBLE_DEVICES` is **not** sufficient on its own — a library that ignores it still sees
  every attached card. Pin with `--gpus`, which is what actually limits the container.
- An idle card is not thereby ours. Someone may be between phases, or queued.
- Leave VRAM headroom. A run sized to the last free megabyte OOMs the moment another process grows.

## RAM

113 GB available, shared.

- Know the cell's expected peak **before** starting it. `families.json` carries measured
  `fixed_peak_gib` per family with `memory_margin_gib`.
- Treat any figure marked as an extrapolation as unproven — see `07` for the specific one.
- Watch it while it runs. A projection is not a measurement.

## CPU

16 logical cores, shared.

- **Do not take all of them.** A configuration that requests 16 workers on a 16-core shared machine
  starves every other user on it, and this repo has exactly such a configuration (`07`).
- Cap deliberately: `--cpus` on the container, `OMP_NUM_THREADS` / `MKL_NUM_THREADS` in the
  environment. `run_on_production_host.sh` forwards both.

## Disk

- Check free space before writing, and know what the job will write.
  `run_on_production_host.sh` refuses below `NATIVE_DISK_FLOOR_GB` and prints its estimate.
- Replay episode files dominate: ~35.5 GiB for one off-policy cell, plus checkpoints counted three
  times over, plus the payload and wheels.
- **Filling a shared disk breaks every writer on the machine at once**, including jobs mid-write
  that will lose hours. This is the highest-blast-radius mistake available here.
- Places365 is ~24 GB. Know where it is going and that the space exists first.

## Monitoring is continuous, not a precondition

Check before, and keep checking during. A long run's footprint changes: replay grows, a curve
evaluation allocates, an XLA autotuner takes scratch VRAM in one transient phase. This project has
already seen an 8.27 GiB transient allocation appear mid-run from a downstream code path nobody was
watching. "It was fine at the start" is not a state that holds.
