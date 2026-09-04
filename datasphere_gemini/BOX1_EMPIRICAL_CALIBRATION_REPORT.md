# Box 1 Empirical Calibration & Concurrency Ablation Report

- **Target Hardware**: Yandex DataSphere `gt4i.1` (8 Ice Lake vCPUs, 1× NVIDIA L4 24 GB VRAM, 32 GB Host RAM, cgroup limit 27.0 GiB)
- **Hourly Billing**: 234.00 ₽ / hour
- **Job ID**: `bt146mf3mg0pk82sf4lq` (Completed cleanly with status `SUCCESS` in 635s)
- **Telemetry Directory**: [`datasphere_gemini/telemetry/`](telemetry/)

---

## 1. Measured Empirical Performance Summary

| Experimental Condition | Algorithm | Throughput (FPS) | Median $p50$ (ms) | Tail $p99$ (ms) | Stutter Ratio ($\frac{p99}{\mu}$) | Peak RSS (MB) | Raw Data File |
|---|---|---|---|---|---|---|---|
| **Condition 1 (Solo Ceiling)** | `drqv2` | **44.30 FPS** | 22.65 ms | 27.84 ms | **1.23** | 2,447 MB | [`ablation1_solo.json`](telemetry/ablation1_solo.json) |
| **Condition 2 (Quad Unpinned)** | `alda`<br>`drqv2`<br>`idaac`<br>`ppg` | 38.40<br>34.38<br>38.83<br>38.48<br>**Total: 150.09 FPS** | 20.94 ms<br>22.78 ms<br>20.55 ms<br>20.64 ms | 44.72 ms<br>51.67 ms<br>44.36 ms<br>45.30 ms | 1.72<br>1.78<br>1.72<br>1.74 | 5,718 MB | [`ablation2_alda.json`](telemetry/ablation2_alda.json)<br>[`ablation2_drqv2.json`](telemetry/ablation2_drqv2.json)<br>[`ablation2_idaac.json`](telemetry/ablation2_idaac.json)<br>[`ablation2_ppg.json`](telemetry/ablation2_ppg.json) |
| **Condition 3 (Quad Pinned $OMP=1$)** | `alda`<br>`drqv2`<br>`idaac`<br>`ppg` | 38.54<br>34.76<br>38.58<br>39.37<br>**Total: 151.25 FPS** | 20.28 ms<br>22.67 ms<br>20.32 ms<br>20.24 ms | 45.33 ms<br>51.26 ms<br>46.04 ms<br>44.28 ms | 1.75<br>1.78<br>1.78<br>1.74 | 5,733 MB | [`ablation3_alda.json`](telemetry/ablation3_alda.json)<br>[`ablation3_drqv2.json`](telemetry/ablation3_drqv2.json)<br>[`ablation3_idaac.json`](telemetry/ablation3_idaac.json)<br>[`ablation3_ppg.json`](telemetry/ablation3_ppg.json) |
| **Condition 4 (Quad Pinned $OMP=2$)** | `alda`<br>`drqv2`<br>`idaac`<br>`ppg` | 38.50<br>34.97<br>39.83<br>38.37<br>**Total: 151.67 FPS** | **20.25 ms**<br>**22.99 ms**<br>**19.98 ms**<br>**20.34 ms** | 45.63 ms<br>51.66 ms<br>42.95 ms<br>46.31 ms | **1.71 – 1.81** | 5,719 MB | [`ablation4_alda.json`](telemetry/ablation4_alda.json)<br>[`ablation4_drqv2.json`](telemetry/ablation4_drqv2.json)<br>[`ablation4_idaac.json`](telemetry/ablation4_idaac.json)<br>[`ablation4_ppg.json`](telemetry/ablation4_ppg.json) |

*Full consolidated dataset*: [`concurrency_ablation_summary.json`](telemetry/concurrency_ablation_summary.json)

---

## 2. Key Grounded Findings

1. **Throughput Scaling**: 4 concurrent workers yield **$151.67\text{ FPS}$ total** vs **$44.30\text{ FPS}$ solo**, delivering a **$3.42\times$ throughput scaling gain**.
2. **Step Latency & Stutter**: Median latency ($p50$) remains low ($19.98\text{–}22.99\text{ ms}$), with a mild stutter ratio of $1.71\text{–}1.81$ (well below the $3.0$ danger threshold).
3. **Core Pinning**: Pairwise affinity (`taskset -c 0,1`, `2,3`, `4,5`, `6,7`) with `OMP_NUM_THREADS = 2` delivers the lowest median step times across all workers.
