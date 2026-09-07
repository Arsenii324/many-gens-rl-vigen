# Running a cell on the production host

Operator runbook for `varaksin_as@cds2` (`notes/remote-infra.txt`: 16 cores, 113 GiB RAM,
2x Tesla V100-SXM2-32GB, plain SSH). The host is not behind DataSphere's job API, so `job.sh`,
`contract.py`'s submit path and every `cfg-*.yaml` are inapplicable here — those talk to
`datasphere project job execute`. What runs a cell on this host is
`datasphere/native/run_on_production_host.sh`, which invokes the same `run_probe.sh` inside the
same digest-pinned container image a DataSphere job uses.

Rationale, defect history and the decisions still awaiting the owner:
[`PRODUCTION-HOST-RATIFICATION.md`](PRODUCTION-HOST-RATIFICATION.md). Sequencing — what to run in
what order — stays in [`MIGRATION-T4-TO-V100.md`](MIGRATION-T4-TO-V100.md) steps 1-8 and
[`PRODUCTION-RUNBOOK.md`](PRODUCTION-RUNBOOK.md). This file is only the mechanism.

## 1. Preconditions, checked on the host every time

```bash
ssh varaksin_as@cds2
nvidia-smi                  # which GPU is free NOW; remote-infra.txt's snapshot is stale by design
df -h /path/for/the/run     # see §5 for how much is needed
docker run --rm --gpus all nvidia/cuda:12.2.2-runtime-ubuntu22.04 nvidia-smi
```

The last one is the real check: `nvidia-smi` working on the host does **not** prove
`docker run --gpus` works — that needs `nvidia-container-toolkit` installed and the Docker daemon
configured for it. If the SSH user is not in the `docker` group, every command below needs `sudo`.

## 2. Build and transfer the payload

Build it locally, exactly as for any DataSphere job — do not invent a transfer path (this repo has
no configured git remote):

```bash
python datasphere/native/contract.py build-payload --source . \
    --output payload-vNNN-<family>.tgz --families <family>
python datasphere/native/contract.py verify-payload --archive payload-vNNN-<family>.tgz \
    --require-evaluator-identity
python datasphere/native/contract.py verify-evaluator-binding --archive payload-vNNN-<family>.tgz
scp payload-vNNN-<family>.tgz rlvigen-door2-90d8b8c4.tgz varaksin_as@cds2:~/
```

The payload is source only — the allowlist in `contract.py` (`BASE_ALLOWED` plus the family's
`payload_members`) rejects any path containing `results`, `logs`, `models`, `data`, `wandb`,
`.git`, `.venv`, `__pycache__`, and the names `wandb_key.txt`, `.netrc`, `id_rsa`, `id_ed25519`.
Everything third-party — apt packages, the pip environment, RL-ViGen upstream — is fetched inside
the container at run time by `run_probe.sh`, so **the host needs outbound network access**.

## 3. Run one cell

Copy the environment block verbatim from whichever `cfg-*.yaml` is the template for this cell; the
script forwards an allow-list of exactly those variables and nothing else.

```bash
CELLS=drqv2:1 FRAMES=600000 TASK=Door SEED=1 \
NATIVE_PRODUCTION=1 NATIVE_HOST_PROFILE=v100 \
SAVE_EVERY_FRAMES=50000 EVAL_EVERY_FRAMES=50000 EVAL_EPISODES=10 ENDPOINT_EVAL=1 \
DOCKER_GPUS='"device=1"' \
NATIVE_OUT_HOST_DIR=/data/runs/drqv2-s1 \
  bash datasphere/native/run_on_production_host.sh \
    payload-vNNN-rlvigen.tgz result-drqv2-s1.tgz rlvigen-door2-90d8b8c4.tgz
```

`NATIVE_PRODUCTION=1` and `NATIVE_HOST_PROFILE` are **mandatory at 600k** — `run_probe.sh` refuses
without them, because `apply_production_settings` would otherwise apply nothing and train a full
run at probe-scale cadence and replay settings while looking successful. The script raises both
refusals itself, before the container bootstrap is paid for.

Extra file inputs (a checkpoint for an offline grid, a resume snapshot) are
`EXTRA_MOUNT_N=HOST_PATH:CONTAINER_PATH:ENV_VAR_NAME`, e.g.
`EXTRA_MOUNT_1=s2-snapshot-100000.pt:/work/snap.pt:OFFLINE_EVAL_SNAPSHOT`.

**GPU pinning belongs at the Docker level.** `DOCKER_GPUS='"device=1"'` attaches exactly one card.
`CUDA_VISIBLE_DEVICES` is deliberately not forwarded: it would look like it pinned the run while
the container still had both cards attached, and a library that ignores it could still reach the
occupied GPU.

**Long runs must be detached.** `docker run` here is foreground; `dockerd` keeps the container
alive across an SSH drop but this script dies with its session before retrieving results. Wrap the
whole script, not the docker command:

```bash
nohup bash datasphere/native/run_on_production_host.sh ... > run.log 2>&1 &
```

## 4. Packing two cells

Packing is **one container with two cells**, not two invocations:

```bash
CELLS=drqv2:1,drqv2:2 NATIVE_CONCURRENT=1 ... bash datasphere/native/run_on_production_host.sh ...
```

`run_probe.sh` runs a comma-separated `CELLS` list concurrently when `NATIVE_CONCURRENT=1` and
serially otherwise. Two separate invocations would each pay their own bootstrap, neither would see
the other's memory use, and nothing would arbitrate between them.

Two constraints:

- **Co-scheduling.** `run_probe.sh`'s `check-co-schedulable` refuses families that cannot share one
  Python environment. `ctrl` is JAX and strips torch — `jax[cuda12]`'s cudnn 9 and torch's pinned
  cudnn 8.9.2.26 have no common version. Pack within a family, not across.
- **Headroom first.** `MIGRATION-T4-TO-V100.md` step 4 gates packing on measured peak RAM/CPU from
  step 2. The script sets no `--memory` or `--cpus`: a cap guessed before that measurement would
  convert an honest overcommit into an OOM-kill mid-run.

## 5. Disk

Per off-policy cell, roughly **25 GB**:

| what | size | where |
|---|---|---|
| replay episode files | ~19 GB (`replay_capacity` 300000 x 63,504 B per transition) | container-local run dir, never retained |
| retained checkpoints | 1.7 GiB (`drqv2`) to 3.2 GiB (`drq`) | `NATIVE_OUT_HOST_DIR` |
| result archive | comparable to the retained set | wherever `$2` points |

`preserve_snapshots=100000` keeps six of the twelve saves a 600k run makes, plus the endpoint.
On-policy families (`idaac`, `ppg`, `ctrl`, `ibac_sni`) hold no replay and need a small fraction of
this. The script refuses a production-scale cell below **60 GB free** on `NATIVE_OUT_HOST_DIR`'s
filesystem (`NATIVE_DISK_FLOOR_GB` overrides); it reports free space on every run.

The host's actual free disk has never been measured — `remote-infra.txt` records RAM and GPUs, not
`df`. Check it before scheduling anything, not after.

## 6. What survives an interruption — and what a checkpoint actually is

**No baseline saves its replay buffer.** For RL-ViGen this is upstream's own behaviour, not a
project choice: `_save_snapshot` is hardcoded `False` (`replay_buffer.py:94`), and `save_snapshot`
persists `['agent', 'timer', '_global_step', '_global_episode']` only
(`RL-ViGen-upstream/train.py:354`). So what a resume gives you differs by family:

| family | baselines | checkpoint contents | resume from a stamp is |
|---|---|---|---|
| `rlvigen` | drqv2, svea, sgqn, drq, curl, pieg | agent (networks + optimizers), timer, step, episode | **not a full restart** — replay starts empty |
| `dmc_gb` | rad, soda | networks + optimizers | **not a full restart** — `utils.ReplayBuffer` is in-memory, capacity `train_steps`, never persisted |
| `alda` | alda | networks + optimizers (`sac_*_step_*.pt`) | **not a full restart** — 15.3 GiB working set is in memory |
| `idaac` | idaac | `[actor_critic, envs.ob_rms]` | effectively complete — on-policy, no buffer; observation normalisation stats are carried |
| `ppg` | ppg | model`<N>`.jd via `LogSaveHelper` | effectively complete — on-policy |
| `ctrl` | ctrl | flax `to_bytes(train_state)`, optax state included | effectively complete — on-policy |
| `ibac_sni` | ibac_sni | `model.pt` | effectively complete — on-policy |

Consequence for the nine off-policy cells: an interrupted run resumed from its last stamp is **a
different experiment** from an uninterrupted one, because the agent restarts against an empty
buffer. Rerun the seed from zero instead — which is also what `EVAL-PROTOCOL.md`'s missing-run
policy already says (rerun a crashed seed under the identical seed; no post-hoc replacement seeds).
Resume exists for on-policy families and for deliberate continuation experiments, not as crash
recovery for off-policy training.

Partial output *is* durable: the script bind-mounts the container's `/tmp/native-out` onto
`NATIVE_OUT_HOST_DIR`, so every checkpoint, `training.log` and per-cell run directory lands on host
storage as it is written. Without it, `run_probe.sh` copies nothing out until its closing
`tar -czf "$result" -C "$out" .`, and a container killed before that line loses everything. The
mount also makes `python scripts/watch_divergence.py --run <dir>` usable against a live run.

The replay episode files are **not** on that mount — they live in the container-local work
directory and are gone when the container is. That is deliberate: they are ~19 GB per cell and
nothing downstream reads them.

## 7. Checkpoint cadence and the reward curve

Saves happen every `SAVE_EVERY_FRAMES` (50k at production), so a 600k cell writes twelve stamps
plus the endpoint. `family.py retain` then applies `preserve_snapshots=100000`, keeping six plus
the endpoint, and the in-container curve evaluation runs against what retention kept. **So the
reported curve is seven points at 100k spacing, not thirteen at 50k** — a deliberate choice
(`families.json`: "keeping all twelve would double that for a curve twice as dense as any plot
needs"), but a disk decision that sets a presentation parameter. If a denser published curve is
wanted, raise `preserve_snapshots` and repeat the disk arithmetic in §5.

The checkpoints are full training state (optimizers included, 104.1 MB for `rlvigen`) because that
is upstream's own save format; curve evaluation reads only the policy from them. Keeping the
format is a fidelity choice, and the disk cost it implies is already handled by the preserve
cadence and by `CURVE_EVAL_DISCARD_WEIGHTS=1`, which deletes each intermediate once evaluated and
leaves the terminal `snapshot.pt` untouched.

## 8. Retrieve and process

`result.tgz` lands at `$2`; `records.jsonl` beside it; the live run directory stays at
`NATIVE_OUT_HOST_DIR`. The archive shape is identical to a DataSphere job's by construction, so
process it the way `job.sh diagnose` does internally. Weights stay on the host: C95 forbids
evaluating a container-trained checkpoint on the laptop, since the renderer differs (EGL there,
glfw here). Records travel; weights do not.

## What this does NOT establish

- **Never executed on `cds2`.** No SSH access from the session that wrote it. Every command is
  derived from `run_probe.sh`'s own exercised contract and ordinary `docker run` semantics.
- **Outbound network access, Docker, and NVIDIA Container Toolkit on the host are assumed** — §1's
  checks are how you find out, and they have not been run.
- **Free disk on the host is unknown**, so §5's floor has never been checked against reality.
- **Concurrent use of the host is the owner's to arbitrate.** This script reserves nothing.
