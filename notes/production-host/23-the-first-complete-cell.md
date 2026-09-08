# 23 — The first complete cell on the production host

**2026-09-09, `idaac:101`, 10k requested frames, card 0.** The first cell on `cds2` to reach the
GPU and run the whole chain. What it proves, what it cost, and the two things I got wrong reading it.

## The chain completed

```
=== NATIVE_ENDPOINT_EVAL_COMPLETED idaac frame=8192 policy_mode=native ===
=== NATIVE_CELL_COMPLETED idaac-s101 ===
=== NATIVE_RECORDS_EMITTED 6 rows -> records_delivery.jsonl ===
native probe completed successfully
```

Train → durable checkpoint → fresh-process reload → endpoint grid → records. That sequence had
never completed on any host at any length; owner-decision item 6 has now been exercised once, at
smoke scale.

**The renderer is real.** `native-out/egl.json`:

```json
{"renderer": "Tesla V100-SXM2-32GB/PCIe/SSE2", ...}
```

Not `llvmpipe`. The `libnvidia-gpucomp` injection and the EGL vendor ICD work end to end, and the
artifact records which renderer produced the pixels.

**The endpoint rule is confirmed empirically.** 10000 requested → **8192 executed**, exactly
`floor(10000 / 2048) * 2048` for `num_processes=1, num_steps=2048`. Predicted before the run from
`family.py expected-endpoint`; matched after.

## What was measured

| | |
|---|---|
| GPU utilisation | mean 5.9%, max 8% |
| GPU memory | 831 MiB (cap 2048, measured need 1204) |
| container CPU | 124% — 1.24 of 16 cores |
| container RAM | 2.3 GiB of 126 |
| wall clock | ~10 min end to end, of which ~6 min bootstrap |

The bootstrap was **~6 minutes**, not the ~2.5 hours seen on 2026-09-08. Same host, same payload
shape. The earlier figure was a slow network period, not a property of the job — recorded here
because note 19 sizes a bootstrap allowance from it and that allowance is now known to be
pessimistic by an order of magnitude on a good night.

## The records, and the learning signal

Six rows: two from IDAAC's own in-training evaluator, four from the offline grid (two regimes ×
two row variants — `episode_diagnostics` and `aggregate_over_seeds`).

| phase | regime | frame | episodes | mean | sd |
|---|---|---|---|---|---|
| eval | eval-easy | 2048 | 10 | 2.2907 | absent |
| eval | eval-easy | 8192 | 10 | 4.7005 | absent |
| offline-eval | train | 8192 | 5 | 1.6046 | 1.2549 |
| offline-eval | eval-easy | 8192 | 5 | 3.3846 | 3.2127 |

`success_rate` is 0.0 everywhere, which is what 8192 frames on Door should give. The eval-easy
return roughly doubles between frame 2048 and 8192 — a signal, not a result.

**Train metrics are rich.** The progress CSV carries `test/mean_episode_reward`,
`test/median_episode_reward`, `test/success_rate`, `train/action_loss`, `train/adv_loss`,
`train/approx_kl_k3`, `train/boundary_fraction`, `train/clf_loss` and more.

## The one real defect, and two I invented

**Real: a completed cell reported failure.** After `native probe completed successfully`:

```
cp: cannot open '.../out/records.jsonl' for reading: Permission denied
=== CELL EXIT=1
```

The container runs as root, so bind-mounted outputs are root-owned and some are `0600` --
`records.jsonl` and `run_manifest.json`. `result.tgz` is `0644` and copied fine, which is what made
this partial rather than obvious. The wrapper now chowns the output directory back to the invoking
user from a throwaway container before copying. Same root-ownership class as the `build-env.sh` bug
found hours earlier, in a different place.

**Invented, twice, by my own diagnostics.** I reported the offline-eval rows as byte-identical
duplicates; they differ in `native` and are two deliberate row variants. I then reported
`episode_return_sd = 0.0000` as suspicious zero variance; the value is `None` -- correctly absent,
because IDAAC's in-training evaluator does not emit a per-episode spread. Both came from printing
`r.get("episode_return_sd") or 0`, which renders `None` as `0`.

**The lesson is not "be careful with formatting".** `x or 0` collapses *absent* into *zero*, and
absent-versus-zero is the distinction measurement exists to preserve. A diagnostic that erases it
manufactures findings, and I acted on two of them before checking the raw values. Print `repr`, or
print nothing.
