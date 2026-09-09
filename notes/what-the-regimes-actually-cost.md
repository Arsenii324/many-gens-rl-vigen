# What each evaluation regime actually costs, measured with its noise floor

**2026-09-09**, from `results/records/card0-20260909-035152__records.jsonl` (`idaac`, 569 rows) and
the live `ppg` curve. Every gap below is stated in standard errors, because three times today I read
a difference without one and got the sign or the significance wrong.

## The endpoint, `idaac` at 598,016 frames, 400 episodes per regime

| regime | return | **SE** | gap vs train | **σ** | verdict |
|---|---:|---:|---:|---:|---|
| train | 33.69 | ± 1.86 | — | — | — |
| eval-easy | 31.58 | ± 1.98 | 2.11 | **0.8** | **not detectable** |
| eval-medium | 11.55 | ± 0.63 | 22.14 | **11.3** | large, unambiguous |
| eval-hard | 18.47 | ± 1.25 | 15.22 | **6.8** | large, unambiguous |

*(n = **200** per regime, and the SE is the **pooled** standard deviation over those 200 episodes.)*

**This table is the third version of itself, and the sequence is the lesson.**

1. **"eval-easy 93.7 % retention"** — a ratio, which always produces a number whether or not the two
   quantities differ. It reads as a measured 6 % drop.
2. **1.2 σ, n=400** — wrong twice over. `eval_grid.py` emits ten per-scene rows *and* a pooled row,
   and I episode-weighted all eleven, so 200 distinct episodes were counted as 400 and every SE was
   understated by √2.
3. **0.9 σ, n=200, per-scene SD** — n fixed, SD still wrong: averaging per-scene SDs discards
   **between-scene** variance, and on this task the scene means span **11.84 to 49.44**. That
   understated the SE by a further 1.11x-1.40x.
4. **0.8 σ, n=200, pooled SD** — correct. The pooled row already carried it:
   `eval_grid.py:1261` builds it from `np.concatenate(per_scene)` with `pooled.std(ddof=1)`, at no
   extra evaluation cost, and marks itself with `native.aggregate_over_scenes`.

**Every iteration moved the same way — toward less significance.** 1.2 → 0.9 → 0.8; 16.9 → 12.6 →
11.3; 10.4 → 8.0 → 6.8. The verdicts survived all three, but confidence was overstated at every step
before the last, and the authoritative statistic was sitting in the records the whole time.

## The same question across the whole curve, not just the endpoint

Per stamp, 11 scene sets x 3 episodes = 33 episodes per regime, SE ≈ 2.6:

| | mean gap | stamps beyond 2 σ |
|---|---:|---|
| `idaac`, train vs **eval-easy** | **+0.13 SE** | 2 of 11, **in opposite directions** |
| `ppg`, train vs **eval-easy** | **+0.17 SE** | **0 of 10** |
| `idaac`, train vs **eval-medium** | 8-12 σ at nearly every stamp | 9 of 11 |
| `ppg`, train vs **eval-medium** | +1.47 SE | 6 of 10 |

**`eval-easy` costs neither family anything measurable, at any point in training.** Two different
algorithms, both scored in `sample` mode under the same evaluator, reaching the same conclusion
independently. That is a statement about **the benchmark's easy regime**, not about a policy: the
perturbation it applies does not challenge either of these agents.

## `eval-medium` is not a gap that develops — it is there from the first measurement

`idaac`, train against eval-medium, per stamp:

| frame | 51,200 | 100,352 | 200,704 | 251,904 | 350,208 | 550,912 |
|---|---:|---:|---:|---:|---:|---:|
| train | 24.66 | 12.21 | 27.10 | 34.07 | **50.32** | 24.74 |
| eval-medium | 5.11 | 9.46 | 5.80 | 4.84 | 11.49 | 7.16 |
| σ | **11.8** | 2.0 | 9.6 | 11.8 | **11.8** | 7.7 |

**`eval-medium` sits flat at roughly 7.4 for the entire run** — no trend, against a random-policy
baseline of 1.54 — while train swings between 12 and 50. The two stamps where the gap looks small
(2.0 σ, 2.5 σ) are the two where *train* dipped, not where eval-medium rose.

So the honest description is not "the policy generalises less well as it trains". It is: **the policy
improves on training scenes and does not improve at all under the medium perturbation, from the
earliest point measured.**

## What this does and does not license

**Licensed:** the `eval-easy` result, twice independently. And the shape of `idaac`'s medium
behaviour, which rests on eleven stamps of its own curve.

**Not licensed:** ranking `ppg` against `idaac`. `ppg`'s eval-medium reaches 17.85 at frame 350,208
where `idaac`'s is 11.49, and `ppg`'s train is 27.55 against `idaac`'s 50.32 — which *looks* like ppg
generalising better while performing worse. Both are `sample` mode so the estimand matches, but they
are different algorithms with different networks, `ppg`'s own optimisation is not the one its config
declared, and `scripts/comparison_blocks.py` is what adjudicates such a pairing. Recorded as an
observation to be checked when both families have a clean run, not as a result.

**Also not licensed:** anything about `eval-hard` beyond its endpoint number. It scores *above*
`eval-medium`, which `rlgen/protocol.py:30-35` already explains — the modes differ in which nuisance
factors are active, not in magnitude, so the returns are not expected rank-ordered.
