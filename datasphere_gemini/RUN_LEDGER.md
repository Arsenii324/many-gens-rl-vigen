# Master DataSphere Run Ledger

**Maintained by Gemini** (`projects/many-gens-rl-vigen/datasphere_gemini/RUN_LEDGER.md`)  
**Hardware Spec for All Jobs**: DataSphere `gt4i.1` (8 vCPUs Intel Ice Lake, 1× NVIDIA L4 24 GB, 32 GB RAM).

---

## 1. Complete Session Job Catalog

| Job ID | Tag / Category | Code Nature | Duration | Outcome | Ground-Truth Notes & Findings |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`bt1p0143a5k2qgqu1m2f`** | `[CALIBRATION]` | Infrastructure Test Script | 264s | `SUCCESS` | Verified PyTorch 2.1 CUDA 12.1, NVIDIA L4 GL drivers, and MuJoCo EGL offscreen rendering on Panda robot. |
| **`bt146mf3mg0pk82sf4lq`** | `[SYNTH-ABLATION]` | **Synthetic** Microbenchmarks (`profile_worker.py`) | 635s | `SUCCESS` | Synthetic systems profiling for CPU context switching and CUDA streams across 4 simulated workers at varying resolutions ($84\times 84$ to $256\times 256$). **NOT real RL training.** |
| **`bt1jjfj5hd2157rn4e4d`** | `[REAL-STANDALONE-1]` | Authentic Paper Code (5k Steps) | 410s | `PARTIAL FAIL` | **DrQ-v2**: Succeeded (5,000 frames).<br>**ALDA**: Failed (`ModuleNotFoundError: colorlog`).<br>**PPG**: Failed (`ModuleNotFoundError: mpi4py`).<br>**IDAAC**: Failed (`ModuleNotFoundError: procgen`). |
| **`bt1ju1fu6bcoa5gkcrki`** | `[REAL-CONCURRENT-25K]` | Authentic Paper Code (Concurrent 25k) + 2.0s Memory Daemon | 423s | `PARTIAL FAIL` | Container exited 0, but 3/4 processes crashed at launch (`gym3`, `common`, `env`). **IDAAC** stepped to 2,816 before crashing on `evaluate`. **Memory graph after $t=28\text{s}$ was idle system state.** |
| **`bt19euj6qqrkmv5f7i2a`** | `[REAL-STANDALONE-2]` | Authentic Paper Code (5k Steps, Added MPI) | 701s | `PARTIAL FAIL` | **DrQ-v2**: Succeeded (5,000 frames, logged evals).<br>**IDAAC**: Failed (`--save_interval` unrecognized).<br>**PPG**: Failed (`ModuleNotFoundError: gym3`).<br>**ALDA**: Failed (`KeyError: 'seed'`). |
| **`bt1u6l0579t4frga1n0d`** | `[REAL-STANDALONE-3]` | Authentic Paper Code (5k Steps, Re-verified) | 701s | `PARTIAL FAIL` | **DrQ-v2**: Succeeded (5,000 frames).<br>**IDAAC**: Failed (`AttributeError: module 'numpy' has no attribute 'bool'`).<br>**PPG**: Failed (`ModuleNotFoundError: procgen` in `envs.py`).<br>**ALDA**: Failed (`ModuleNotFoundError: einops`). |
| **`bt10ib01b51ruq1lgt54`** | `[REAL-STANDALONE-4]` | Authentic Paper Code (All 4 Baselines) | 1320s | `PARTIAL SUCCESS` | **DrQ-v2**: Succeeded (5,000 steps + eval sweep).<br>**IDAAC**: Succeeded (2,816 steps + eval sweep, reward 7.36).<br>**PPG**: Succeeded (5,000 steps, value optimization).<br>**ALDA**: Failed on `ModuleNotFoundError: sklearn`. |

---

## 2. Hardware Memory & Throughput Truth Status

* **Synthetic Data Demarcation**: Any FPS numbers derived from `bt146mf3mg0pk82sf4lq` (`ablation4_summary.json`) are synthetic systems proxies, NOT baseline training numbers.
* **Empirical Ground-Truth Measured Numbers**:
  * **DrQ-v2**: $1.73\text{ FPS}$ with zero-shot evaluation sweeps; $\approx 10\text{ FPS}$ during pure rollout stepping.
  * **IDAAC**: $\approx 45\text{ FPS}$ stepping rate on Robosuite Door.
  * **PPG & ALDA**: True baseline FPS will be extracted strictly from the output logs of `bt10ib01b51ruq1lgt54`.
| **`bt15pmakjuhgqvkif0oj`** | `[ALDA-STANDALONE-1]` | Authentic Paper Code (ALDA 5k Steps) | 1050s | `PARTIAL FAIL` | Container finished `SUCCESS`, but ALDA threw `ModuleNotFoundError: seaborn` from `disentangle/utils/metrics.py:7`. |
