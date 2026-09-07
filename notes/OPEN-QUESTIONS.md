# Open questions — research questions, not owner decisions

Distinct from [`DECISION-SHEET.md`](DECISION-SHEET.md): those need a preference or an authority.
These need **an answer**, and anyone can find it. They are collected because each was discovered in
passing and would otherwise be lost in a paragraph.

| # | question | why it matters | where to look |
|---|---|---|---|
| Q1 | **Which DrQ-v2 difficulty tier does Door belong to, and where does the running value come from?** *(sharpened 2026-09-05: the literal `linear(1.0,0.1,100000)` is **not in RL-ViGen's shipped configs at all**. The only occurrences in this tree are `configs/vigen.yaml:57` — the **superseded** port — which sets 100000 with a comment that Lift needs an override, and `rlgen/registry.py:188`, which defaults to **500000**. Yet a real clone-era job composed 100000, so its clone-era provenance is unestablished. Two sub-questions: where does the clone-era value come from, and is 100000 or 500000 right for Door?)* | The composed config resolves `stddev_schedule: linear(1.0, 0.1, 100000)` — the short-horizon form. `FAITHFULNESS` says the schedule was "FIXED 2026-08-10" from the wrong tier, but records what changed, not *to what*. If Door warrants a longer schedule, exploration noise decays ~5× too fast for five baselines | DrQ-v2's task→tier mapping; RL-ViGen's robosuite config |
| Q2 | ~~Units of the published sheet~~ **ANSWERED 2026-09-05.** `scripts/rlvigen_reference.py` (fixed to find the asset) states: *"These are RETURNS. The benchmark does not publish success rates for robosuite, which is C33."* The Lift puzzle also dissolves — our Lift floor is 6.56 and the weak methods score below it, which shaped reward makes coherent | resolved |
| Q3 | **Should `ctrl`'s MYOW index be `k_idx + 1` rather than `0 + 1`?** | `algo.py:238` draws from the *single* nearest neighbouring cluster `myow_k` times instead of iterating the k nearest. Written as `0 + 1`, which suggests a loop variable was intended. **`ext/ctrl_public/algo.py:222` is identical**, so it is upstream's — we reproduce it faithfully, but the MYOW term is less diverse than the formulation implies | CTRL paper's MYOW description |
| Q4 | **Is production `num_seed_frames` 4000 or 600?** | `cfgs/config.yaml` says 4000; a real job's composed config said **600**. At a 10k budget that is 40% vs 6% of the run spent on a random policy — and my reasoning about why short runs sit at the floor used 4000 | a production-shaped job's `.hydra/config.yaml` |
| Q5 | **Does `FAITHFULNESS` really claim IDAAC matches a continuous-control precedent?** | Review 4 says it claims rollout 2048 / γ=0.99 / lr 3e-4 / 10 epochs while production runs the Procgen family (γ=0.999, lr 5e-4, 1 epoch). The executed values match the Procgen half; I could not locate the precedent text | `FAITHFULNESS.md`; IDAAC paper's continuous-control section |
| Q6 | **Do the `medium`/`low` faithfulness rows hold?** | The reconciliation covered `high` and the two marked FIXED. `rad`, `alda`, `drq`, `ibac_sni` detail rows remain unchecked; SODA was closed 2026-09-07 against its paper, read-only DMC-GB source, and active launcher path | [`faithfulness-reconciliation.md`](faithfulness-reconciliation.md) |

**Rule for this page:** an answer moves the row out of here and into the surface it belongs to —
usually [`faithfulness-reconciliation.md`](faithfulness-reconciliation.md) or
[`CLAIMS-LEDGER.md`](CLAIMS-LEDGER.md). A question that turns out to need a *preference* moves to the
decision sheet instead.
