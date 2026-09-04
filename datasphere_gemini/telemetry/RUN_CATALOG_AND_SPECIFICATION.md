# Exhaustive Telemetry Run Catalog & Specification

This document defines the complete provenance and specification for every empirical run recorded in `datasphere_gemini/telemetry/`.

---

## 1. Hardware & Platform Substrate
- **Cloud Provider**: Yandex DataSphere
- **Instance Type**: `gt4i.1`
- **CPU Substrate**: 8 vCPUs (Intel Xeon Ice Lake @ 2.80 GHz, 4 physical cores, 2 threads/core)
- **Host Memory**: 32.0 GB Physical RAM (cgroup hard limit: 27.0 GiB)
- **GPU Accelerator**: 1× NVIDIA L4 (AD104GL, 24.0 GB VRAM, PCIe Gen4, FP32 compute: 30.3 TFLOPS)
- **NVIDIA Driver**: 535.161.07 | **CUDA Version**: 12.2 (PyTorch cu121 wheels)
- **Operating System**: Ubuntu 22.04 LTS (Linux kernel 5.15.0)
- **Rendering Context**: EGL offscreen hardware accelerated (`MUJOCO_GL=egl`, `PYOPENGL_PLATFORM=egl`, `EGL_DEVICE_ID=0`)

---

## 2. Shared Environment & Simulation Parameters
- **Simulation Engine**: MuJoCo 2.3.7
- **Robotics Suite**: Robosuite 1.4 (vendored RL-ViGen fork)
- **Task**: `Door` manipulation task
- **Robot Model**: Franka Emika Panda (7 revolute arm joints + 1 parallel gripper actuator)
- **Action Space**: Continuous 8-dimensional space (`Box(-1.0, 1.0, (8,))`)
- **Control Frequency**: 20 Hz
- **Simulation Time-step**: 0.002s (10 physics steps per control step)
- **Episode Horizon**: 500 steps (max 25 seconds of simulation time)
- **Reward Function**: Dense shaped reward (`reward_shaping=True`)
- **Action Repeat**: 1 (every action executed for exactly 1 control step)

---

## 3. Individual Run Specifications

### Run 1: Solo Ceiling Baseline
- **File**: [`ablation1_solo.json`](ablation1_solo.json)
- **Algorithm Simulated**: DrQ-v2
- **Observation Geometry**: $84 \times 84 \times 3$, Frame Stack = 3 (Tensor shape: `[1, 9, 84, 84]`)
- **Process Concurrency**: 1 Worker (Solo)
- **Process CPU Affinity**: Unpinned (All 8 vCPUs accessible)
- **Thread Allocation**: `OMP_NUM_THREADS = 4`, `MKL_NUM_THREADS = 4`
- **Batch Size & Optimization**: Batch size 128, Adam optimizer ($lr = 10^{-4}$), update step every 2 env steps.
- **Measured Outputs**: $44.30\text{ FPS}$, Mean latency $22.57\text{ ms}$, Median $p50 = 22.65\text{ ms}$, Tail $p99 = 27.84\text{ ms}$, Stutter ratio $1.23$, Peak RSS $2{,}447\text{ MB}$.

---

### Run 2: Quad Workers - Unpinned OS Default
- **Files**: [`ablation2_alda.json`](ablation2_alda.json), [`ablation2_drqv2.json`](ablation2_drqv2.json), [`ablation2_idaac.json`](ablation2_idaac.json), [`ablation2_ppg.json`](ablation2_ppg.json)
- **Algorithms Simulated**: `alda` (64px, 3-stack), `drqv2` (84px, 3-stack), `idaac` (64px, 1-stack), `ppg` (64px, 1-stack)
- **Process Concurrency**: 4 Workers launched simultaneously (`&` in background, synchronized at step 1000)
- **Process CPU Affinity**: Unpinned (Default Linux CFS scheduler across all 8 vCPUs)
- **Thread Allocation**: `OMP_NUM_THREADS = 2` (8 total math threads across 4 processes)
- **Measured Outputs**:
  - `alda`: 38.40 FPS | $p50 = 20.94\text{ ms}$ | $p99 = 44.72\text{ ms}$ | Stutter $1.72$ | RSS $5{,}628\text{ MB}$
  - `drqv2`: 34.38 FPS | $p50 = 22.78\text{ ms}$ | $p99 = 51.67\text{ ms}$ | Stutter $1.78$ | RSS $2{,}452\text{ MB}$
  - `idaac`: 38.83 FPS | $p50 = 20.55\text{ ms}$ | $p99 = 44.36\text{ ms}$ | Stutter $1.72$ | RSS $5{,}718\text{ MB}$
  - `ppg`: 38.48 FPS | $p50 = 20.64\text{ ms}$ | $p99 = 45.30\text{ ms}$ | Stutter $1.74$ | RSS $5{,}718\text{ MB}$
  - **Aggregate**: $150.09\text{ FPS}$ total.

---

### Run 3: Quad Workers - Pinned Core Affinity ($OMP=1$)
- **Files**: [`ablation3_alda.json`](ablation3_alda.json), [`ablation3_drqv2.json`](ablation3_drqv2.json), [`ablation3_idaac.json`](ablation3_idaac.json), [`ablation3_ppg.json`](ablation3_ppg.json)
- **Process Concurrency**: 4 Workers launched simultaneously
- **Explicit CPU Affinity Masks**:
  - ALDA: `taskset -c 0,1` (Core 0 + hyperthread 1)
  - IDAAC: `taskset -c 2,3` (Core 1 + hyperthread 3)
  - PPG: `taskset -c 4,5` (Core 2 + hyperthread 5)
  - DrQ-v2: `taskset -c 6,7` (Core 3 + hyperthread 7)
- **Thread Allocation**: `OMP_NUM_THREADS = 1` (Single compute thread per core pair)
- **Measured Outputs**:
  - `alda`: 38.54 FPS | $p50 = 20.28\text{ ms}$ | $p99 = 45.33\text{ ms}$ | Stutter $1.75$ | RSS $5{,}639\text{ MB}$
  - `drqv2`: 34.76 FPS | $p50 = 22.67\text{ ms}$ | $p99 = 51.26\text{ ms}$ | Stutter $1.78$ | RSS $2{,}466\text{ MB}$
  - `idaac`: 38.58 FPS | $p50 = 20.32\text{ ms}$ | $p99 = 46.04\text{ ms}$ | Stutter $1.78$ | RSS $5{,}639\text{ MB}$
  - `ppg`: 39.37 FPS | $p50 = 20.24\text{ ms}$ | $p99 = 44.28\text{ ms}$ | Stutter $1.74$ | RSS $5{,}733\text{ MB}$
  - **Aggregate**: $151.25\text{ FPS}$ total.

---

### Run 4: Quad Workers - Pinned Core Affinity ($OMP=2$) [Optimal Selected Configuration]
- **Files**: [`ablation4_alda.json`](ablation4_alda.json), [`ablation4_drqv2.json`](ablation4_drqv2.json), [`ablation4_idaac.json`](ablation4_idaac.json), [`ablation4_ppg.json`](ablation4_ppg.json)
- **Process Concurrency**: 4 Workers launched simultaneously
- **Explicit CPU Affinity Masks**:
  - ALDA: `taskset -c 0,1`
  - IDAAC: `taskset -c 2,3`
  - PPG: `taskset -c 4,5`
  - DrQ-v2: `taskset -c 6,7`
- **Thread Allocation**: `OMP_NUM_THREADS = 2` (Both hyperthreads active per core pair)
- **Measured Outputs**:
  - `alda`: 38.50 FPS | $p50 = 20.25\text{ ms}$ | $p99 = 45.63\text{ ms}$ | Stutter $1.76$ | RSS $4{,}626\text{ MB}$
  - `drqv2`: 34.97 FPS | $p50 = 22.99\text{ ms}$ | $p99 = 51.66\text{ ms}$ | Stutter $1.81$ | RSS $2{,}447\text{ MB}$
  - `idaac`: 39.83 FPS | $p50 = 19.98\text{ ms}$ | $p99 = 42.95\text{ ms}$ | Stutter $1.71$ | RSS $5{,}719\text{ MB}$
  - `ppg`: 38.37 FPS | $p50 = 20.34\text{ ms}$ | $p99 = 46.31\text{ ms}$ | Stutter $1.78$ | RSS $4{,}626\text{ MB}$
  - **Aggregate**: $151.67\text{ FPS}$ total.
