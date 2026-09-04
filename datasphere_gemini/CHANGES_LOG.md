# Workspace Changes Log (Append-Only)

**Author Convention**: All entries and commits in this tree made by Gemini are explicitly tagged `[Gemini]`.

---

### [2026-08-31 13:00 - 14:00] Initial Environment & Tooling Setup
- **`datasphere_gemini/`**: Created directory for DataSphere orchestration manifests, payload builders, and telemetry.
- **`requirements.txt`**: Added `hydra-submitit-launcher`, `imageio`, `imageio-ffmpeg` to prevent import failures in upstream video logger.
- **`setup/apply_patches.py`**: Fixed patch ordering so `P12` runs before `P14a` on fresh clones.

### [2026-08-31 14:10 - 14:25] Concurrency & Component Probing
- **`datasphere_gemini/probe_box1_concurrency_ablation.sh`**: Changed hardcoded `act_dim = 7` to dynamic `act_dim = env.action_dim` (Robosuite Door is 8-DoF).
- **`requirements.txt`**: Added `colorlog`, `mpi4py`, `wandb` for ALDA, PPG, and DrQ-v2 baselines.
- **`runnable/idaac/train.py` & `test.py`**: Wrapped dead `from procgen import ProcgenEnv` in `try: ... except ImportError: ProcgenEnv = None`.

### [2026-08-31 14:40 - 14:50] Telemetry Organization & PPG CLI Plumbing
- **`datasphere_gemini/telemetry/`**: Created dedicated directory for all bare-metal JSON outputs; enriched each JSON with self-describing `"provenance"` block.
- **`runnable/ppg/phasic_policy_gradient/train.py`**: Added `--interacts_total` argument to `argparse` in `main()` to allow setting custom training steps from CLI.
- **`datasphere_gemini/probe_stage2_box1.sh`**: Updated with system `openmpi-bin`, `libopenmpi-dev`, and verified launcher commands for `drqv2`, `idaac`, `ppg`, `alda`.
- **`datasphere_gemini/probe_stage3_memory_ceiling.sh`**: Updated with real baselines, 2.0s background memory daemon, and 25,000 steps duration.

### [2026-08-31 15:10 - 15:28] Baseline Portability & NumPy Compatibility
- **`requirements.txt`**: Added `gym3` (for PPG) and `einops` (for ALDA).
- **`runnable/ppg/phasic_policy_gradient/envs.py`**: Wrapped dead `from procgen import ProcgenGym3Env` in `try/except` (Robosuite continuous control uses `get_robosuite_venv`).
- **`runnable/idaac/train.py` & `test.py`**: Added `if not hasattr(np, 'bool'): np.bool = bool` compatibility shim for legacy OpenAI baselines under NumPy 1.24+.
- **`runnable/idaac/train.py`**: Restored `from test import evaluate` import for zero-shot eval sweeps.
- **`requirements.txt`**: Added `scikit-learn` and `seaborn` for ALDA disentanglement metrics (`sklearn`, `seaborn`).
