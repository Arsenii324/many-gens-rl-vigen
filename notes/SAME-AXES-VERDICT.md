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

---

## Revision, 2026-09-07 (later) — CTRL was on the wrong side of the split, and the owner has ruled

Two things changed after the page above was written, and both change what R3 means here.

### 1. CTRL's native rule was wrong, and correcting it moves the split from 8/4 to 9/3

The page above listed `ctrl` among the four sampling reporters. That was a defect, not a fact.
External review 24 and the owner's own source check found it independently, and it was then
confirmed directly against the pinned upstream: `runnable/ctrl/evaluate_ppo.py:84` calls
`select_action(..., greedy=True)`, whose greedy branch is `logits.argmax(1)` (:71-72). **CTRL's
released evaluator is deterministic.**

The 2026-09-04 entry that set it to `sample` reasoned from `train_ppo.py:244,253`, which pass
`sample=True` — but those are TRAINING calls. The criterion this evaluator reproduces is each
baseline's own EVALUATION-time rule. The earlier audit had even *seen* `evaluate_ppo.py`'s greedy
helper and dismissed it as "discrete-only and the wrong function to call", which confuses the
helper's action-space support with its selection rule. The rule is greedy; `pi.mode()` is its
continuous analogue.

Corrected in `evaluator_identity.py`, `eval_grid.py`, `normalize_curves.py` and
`audit_eval_state.py` in one batch. Three of our own files had agreed with each other and were
wrong together, which is precisely what an internal-consistency test cannot catch — so
`tests/test_native_policy_mode_provenance.py` now anchors each family's native rule against the
vendored upstream source rather than against another of our tables.

**The blocks are now:**

- **Block A, deterministic reporters (9)** — drqv2, svea, drq, sgqn, curl, rad, soda, alda, **ctrl**
- **Block B, sampling reporters (3)** — idaac, ppg, ibac_sni

### 2. The owner has ruled that this is not an axis problem

Verbatim: *"maybe it's that the argmax vs proportional is an okay difference. Especially if
originally so. I don't treat it as an axis problem."* And on the protocol: *"let's do the primaries
now, no secondaries."*

That is a decision on the estimand question, and it is the owner's to make. It rests on a condition
— "especially if originally so" — which is now **verified per family**, and the verification is the
reason this can be accepted rather than merely asserted:

| family | native rule | released evaluator it is derived from | verified |
|---|---|---|---|
| idaac | sample | `model.py:332` `act(self, inputs, deterministic=False)`, `test.py` omits the flag | yes |
| ibac_sni | sample | `torch_rl/scripts/evaluate.py`'s `--argmax` is store_true, default off | yes |
| ctrl | **mode** | `evaluate_ppo.py:84` `select_action(..., greedy=True)` | yes |
| ppg | sample | **no dedicated evaluation runner exists upstream** | **NO** |

**PPG is the one family whose `native` rests on a rollout convention rather than on an evaluator.**
OpenAI's release ships no evaluator; native sampling follows the only released `PpoModel.act()`
convention. That is stated in `eval_grid.py`'s own docstring now rather than left implied, because
it is the single weakest link in the "originally so" condition the owner's ruling depends on.

### What this means for `scripts/requirements.py`

**R3 still reads NOT MET, and it is deliberately left that way.** The mechanical check measures
axis uniformity, and one UNITS axis still splits 9/3. The owner's ruling is that the split is
acceptable, not that it is absent — those are different statements, and encoding the second to
make a gate go green would delete the evidence a reader needs if the fleet's cross-block numbers
later look strange. Per the standing instruction on ratification: record the judgement, do not
close it in code.

### What gets reported, decided in advance

The fallback stated on this page is now the operative plan, not the contingency:

- **Rank within a block; do not rank across blocks.**
- Say why in the caption, not only in an appendix: the two blocks measure different quantities of
  the policy, and this project chose each method's own reporting path over a harmonised one.
- A25's three fixed cross-group contrasts (`idaac` vs `svea`, `idaac` vs `curl`, and the
  group aggregate) are **descriptive**, not inferential.
- The mechanism question — does an on-policy regulariser generalise better than an augmentation —
  is **not answered by this fleet**. That is the price of the fidelity choice and it is stated
  here rather than discovered in review.

**No secondary deterministic pass is scheduled** (owner: "no secondaries"). `--policy-mode mode`
remains implemented and reachable for the three Block B families, so the check remains available
at 3% of campaign cost if a cross-block claim ever becomes necessary. It is not removed, and it is
not run.
