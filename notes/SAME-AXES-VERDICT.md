# Is the same-axes goal reached? No — and this states exactly how, and what we report if it stays that way

`scripts/requirements.py` reads **R3 NOT MET**. That is the project's central research claim, so it
gets its own page rather than a line inside a plan. Written 2026-09-07 after the owner asked whether
the case of the goal *not* being reached had been considered; it had not been written down, and
"silently dropping it" is exactly what an unstated failure mode is.

## The verdict, in the project's own terms

`scripts/audit_comparability_seam.py --host-profile v100` classifies twenty derived axes:

- **UNITS** — decides what a number MEANS. A split makes the numbers incommensurable, and *no
  declaring or rescaling repairs it*: the split must be removed or converted.
- **CONDITIONS** — decides what was MEASURED. A split makes a difference unattributable, which
  declaring and quantifying does address.

Current state: **UNITS 6 of 7 uniform. CONDITIONS 1 of 13 uniform.**

The CONDITIONS spread is by design and is what `RESEARCH-FRAME.md` claims: twelve published
implementations at their authors' own settings differ in frame stack, action repeat, crop policy,
replay capacity, warmup, update density and learning-rate schedule. Each is declared.

**The one UNITS split is `evaluation policy mode`**: eight baselines report
E[return | a = argmax π]; `idaac`, `ppg`, `ibac_sni` and `ctrl` report E[return | a ~ π], because
`eval_grid.py` deliberately reproduces each family's own reporting path. Those are different
estimands of different objects. **This alone makes R3 NOT MET.**

## What would make it MET, and what it costs

Run the deterministic second endpoint pass for the four sampling families —
`ENDPOINT_EVAL_POLICY_MODES=native,mode`, already implemented and wired, requested by `family.py` for
exactly those four. **28.7 GPU-h against a campaign near 893, about 3%.** Then every cross-group
comparison uses the mode-taking pass and the axis is uniform where it is used.

Two things must be true and neither is yet:

1. **The `mode` pass must have executed at least once.** It is implemented, its scope canonicalises
   with a distinct revision, and it has never run. It would otherwise debut during the campaign.
2. **The forced-scope ledger question must be decided.** Wave configs attest the NATIVE scope only.
   Whether the forced scope also needs an attestation is a second entry shape, and a decision.

## If it stays NOT MET — the fallback, stated in advance

Deciding this after seeing results is how a paper acquires a convenient conclusion. So, in advance:

**Report the twelve as two blocks, and rank only within a block.**

- **Block A, deterministic reporters** (drqv2, svea, drq, sgqn, curl, rad, soda, alda) — the
  augmentation and representation-learning comparisons, 16 of A25's 25 primary pairs, unaffected.
- **Block B, sampling reporters** (idaac, ppg, ibac_sni, ctrl) — the on-policy PPO comparisons, 6
  pairs, internally comparable.
- **No cross-block ranking, and say why in the caption**, not only in an appendix: the two blocks
  measure different quantities of the policy, and this project chose each method's own reporting
  path over a harmonised one.

What that costs: A25's three fixed cross-group contrasts (`idaac` vs `svea`, `idaac` vs `curl`, plus
the group-aggregate) become descriptive rather than inferential. The mechanism question — does an
on-policy regulariser generalise better than an augmentation — is then **not answered by this
fleet**. That is a real reduction in scope and is the honest price of the fidelity choice, which is
why the 3% remedy is strongly preferred.

**What is NOT an acceptable resolution**: harmonising the four families onto the mode silently, or
reporting a cross-block ranking with a footnote. The first replaces each family's own reporting path
with ours, which is the deviation `EVALUATOR-DELTA.md` exists to prevent; the second is a UNITS
split treated as though declaring it were enough, which the audit's own rule denies.

## Why this was nearly missed

Every instrument needed to see it already existed. `audit_eval_state.py` measured the split per
reporting path from 2026-09-04; every record carried `conventions.eval_policy_mode`; `eval_grid.py`
said in a comment that the modes must not be pooled. What did not exist was the axis in the
comparability list, so no summary ever showed it — and `preprod_table.py` printed both blocks in one
table without warning. Same shape as the other defects this week: **the evidence existed and nothing
acted on it.**
