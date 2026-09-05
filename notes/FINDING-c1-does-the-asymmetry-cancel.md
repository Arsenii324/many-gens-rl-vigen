# Does C1's 9-vs-3 truncation asymmetry cancel in the metrics this project actually reports?

Found 2026-09-05/06, in answer to a direct challenge: is [C1](../docs/CONSTRUCTION.md#c1) actually
worked through, or is "declare and quantify" being left as formalism? This is the "quantify" half,
which nothing in `CONSTRUCTION.md`, `RESEARCH-FRAME.md`, or `EVAL-PROTOCOL.md` had yet attempted.

## The question, precisely

C1: on Door, every episode ends by time limit, never by an early termination. Nine baselines
(`drqv2 svea sgqn curl drq ctrl idaac ppg ibac_sni`) zero the value bootstrap at that time limit,
treating it as terminal — biasing every one of their critics' targets downward, on every episode,
throughout training. Three (`rad soda alda`) bootstrap through it correctly. The standing DEFAULT
(`CONSTRUCTION.md#c1`, set 2026-09-03) is: keep each repository's own handling, **declare it beside
every result, and never rank across the split**.

The question is whether that discipline is load-bearing, or whether the bias happens to wash out
of the actual reported quantities anyway — `R_train`, `R_OOD`, `Δ = R_OOD − R_train`, success rate,
retention, and floor-adjusted retention (`EVAL-PROTOCOL.md:23`).

## First fact, checked rather than assumed: the bias cannot enter through the measurement

`evaluate()` (`runnable/dmc_gb/src/train.py:14-30`, and every other family's equivalent) computes
every reported quantity by rolling out the **already-frozen, deterministic policy** and summing
real environment reward and a real `_check_success()` flag. No value function, no TD target, no
bootstrap of any kind appears anywhere in that loop. So C1 cannot bias the *arithmetic* of a
reported number — it can only bias *which policy* the training run converged to. Every
downstream question is therefore about policy quality, not measurement mechanics.

## Second fact: neither a difference nor a ratio is protected by construction

The project already reports both a **difference** (`Δ = R_OOD − R_train`) and a **ratio**
(retention). Both have a superficially appealing cancellation story, and the two stories are
mutually exclusive:

- **If** C1's effect on a policy's achieved return were a constant **additive** shift, the same
  in every regime (train, eval-easy, eval-hard) — `R_train → R_train + β`, `R_OOD → R_OOD + β` —
  then `Δ` would be exactly invariant to it, and retention (a ratio) would **not** be.
- **If** instead the effect were a constant **multiplicative** factor — `R → R·(1+β)` in every
  regime — retention would be exactly invariant, and `Δ` would **not** be.

Both are strong, unverified structural assumptions about how a training-time bias propagates
through non-linear function approximation into policy behavior across environments the policy was
never shown during training. Neither is implied by anything about how PPO/SAC actually learn, and
there is no argument in this project (or, as far as this audit found, in the literature this
project cites) that either holds even approximately. **Reporting both Δ and retention is not
redundant, and it is not a hedge that protects the pair jointly** — at most one of the two escape
routes can be true for any single, specific way the bias actually manifests, and it may be neither
(the true effect of a downward-biased critic target on final policy behavior is generally
regime-dependent in a way that has no reason to be either additive or multiplicative).

**Absolute quantities — `R_train`, `R_OOD`, success rate — have no cancellation story at all.**
They are exactly what the confound enters through; nothing about summing raw environment reward
"nets out" a policy-quality difference caused by a training-time bootstrap error.

## Verdict

**No, it does not provably cancel for any of the six reported quantities**, and the project should
not treat it as if it does. The honest position, matching what `CONSTRUCTION.md#c1`'s DEFAULT
already commits to operationally (declare, never rank across), is:

- Within-group comparisons (9-vs-9, or 3-vs-3) are unaffected — every row shares the same
  time-limit convention, so whatever the bias's shape, it is common to the whole comparison.
- Any comparison that mixes a "terminal" baseline against a "bootstrap" baseline on the SAME
  metric column (raw return, success rate, Δ, retention, or floor-adjusted retention — all six)
  carries an unquantified confound of unknown sign and magnitude. Nothing here shows it is large;
  nothing here shows it is small. That is exactly why "declare, don't equalize" is the right
  policy default and "assume it cancels" would not be — the second claim requires an assumption
  this analysis shows is not free, and no evidence in this project supports it either way.
- **This can only be resolved empirically**, not analytically: rerun one of the nine baselines
  (cheapest: whichever "terminal" clone is fastest per cell) with truncation-as-bootstrap patched
  in, holding everything else fixed, and measure the actual shift in `R_train`, `R_OOD`, `Δ`, and
  retention. That is the one path from "unquantified" to "quantified" that C1's own DEFAULT calls
  for and that nothing in this project has done yet. Left here as the concrete next step rather
  than repeating the "declare and quantify" phrase without acting on the second half of it.

## A real, separate gap found while checking this, and fixed

Checking *whether* the split is actually kept out of cross-baseline tables (as opposed to merely
being declared as a policy) surfaced a genuine, independent bug: **`scripts/results_table.py` and
`scripts/preprod_table.py` — the actual table-generating code — had no mechanism at all to detect
or flag a table that pools rows across the C1 split.** `results_table.py` already carries guards
for several other comparability defects (C17's floor, C47/C55's denominator rule, C62's shaping
ceiling, the resolution-floor column) but nothing for C1, despite C1 being rated "the largest
comparability defect found" in `CONSTRUCTION.md`.

This had not yet produced a wrong table: today's only populated `CELLS` entries (`drqv2`, `svea`,
`drq`) are all in the "terminal" group, so no mixing has actually happened. But `rad`, `soda`, and
`alda` — all three "bootstrap" baselines — are explicitly listed in `results_table.py`'s own
`ABSENT` dict as "no cell run at the 105k protocol yet," meaning a cell for any of them is
anticipated, and the moment one is added the table would silently pool it against the nine with no
warning, exactly the failure C1's DEFAULT exists to prevent.

**Fixed**: `results_table.py` now reads `TIME_LIMIT_HANDLING` from `rlgen/protocol.py` (same
mechanism `scripts/audit_comparability_seam.py::truncation()` already uses), tags each row with
its group, and — if a table's rows ever span more than one group — prints a loud, named warning
(which baselines, which groups) and fails `--strict`. Two tests added to
`tests/test_results_table.py`: one synthesizes a mixed-group table and confirms the warning fires
and `--strict` exits 1; one confirms today's real, uniform table does not spuriously warn. Both
pass; the file's `@needs_results`-gated tests still correctly skip in this tree (no retention
grids present here).

See `notes/CORRECTIONS.md` #81 for the fix record.
