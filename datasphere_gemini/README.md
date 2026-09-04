# DataSphere 500k Benchmark Execution (Authored by Gemini)

> **Author**: Gemini 3.7 Flash
> **Target**: Yandex DataSphere project `bt12q57tmrs03pnt8drc` on `gt4i.1` (1× Tesla T4i / NVIDIA L4, 8 vCPUs Ice Lake, 27.0 GiB cgroup RAM, 24 GB VRAM)
> **Goal**: A robust, leak-free, high-throughput 500k-frame training & evaluation execution for the standard benchmark setting.

---

## 1. System Design & Bottleneck Mitigations

1. **Replay Buffer & RAM Sizing**:
   * RL-ViGen flushes episode transitions to disk `.npz` chunks in `buffer/` and samples mini-batches dynamically.
   * Process RSS stays around **~2.5–3.5 GiB RAM**, safely under the **27.0 GiB cgroup limit**.
   * A single run or a 2-run packed configuration uses <8 GiB RAM total, preventing Linux OOM-killer invocations.

2. **CPU / Thread Contention**:
   * The 8 Ice Lake vCPUs are protected from thread thrashing by explicitly setting:
     ```bash
     export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
     ```
   * Prevents multiple processes from spawning $3 \times 8 = 24$ competing threads.

3. **Checkpoint Preservation (Addressing C68 & C77)**:
   * Upstream RL-ViGen overwrites `snapshot.pt` at every 50k interval.
   * `train_500k_job.sh` launches a background snapshot monitor that copies checkpoints at steps `50k`, `100k`, `200k`, `300k`, `400k`, `500k` to distinct preserved files (`snapshot_50k.pt`, `snapshot_100k.pt`, ...), ensuring intermediate weights are permanently saved.

4. **Multi-Channel Observability**:
   * **W&B**: Live metrics synced directly to Weights & Biases (API key delivered via private input file `wandb_key.txt`, never exposed in YAML/CLI args).
   * **TensorBoard**: Event files captured and archived in `result.tgz`.
   * **CSV Logs**: `train.csv` and `eval.csv` tracked in real-time.

5. **Hardware Rendering & CUDA Verification**:
   * Hardware EGL rendering (`MUJOCO_GL=egl`) verified against software fallback before training starts.
   * CUDA compute throughput verified via PyTorch matmul gate.

---

## 2. Launch Commands

### A. Single SVEA 500k Run (`cfg-500k-svea.yaml`)
```bash
cd projects/many-gens-rl-vigen/datasphere_gemini
bash build_payload.sh
GRPC_DNS_RESOLVER=native datasphere project job execute -p bt12q57tmrs03pnt8drc -c cfg-500k-svea.yaml
```

### B. Packed 2-Algorithm 500k Run (`cfg-500k-packed.yaml` — SVEA + DrQ-v2)
```bash
cd projects/many-gens-rl-vigen/datasphere_gemini
bash build_payload.sh
GRPC_DNS_RESOLVER=native datasphere project job execute -p bt12q57tmrs03pnt8drc -c cfg-500k-packed.yaml
```

---

## 3. Pulling Results

```bash
python ds_pull.py --job-id <JOB_ID> --output-dir ./out_500k
```
