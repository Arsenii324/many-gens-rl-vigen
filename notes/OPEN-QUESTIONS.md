# Open questions — research questions, not owner decisions

Distinct from [`DECISION-SHEET.md`](DECISION-SHEET.md): those need a preference or an authority.
These need **an answer**, and anyone can find it. They are collected because each was discovered in
passing and would otherwise be lost in a paragraph.

| # | question | why it matters | where to look |
|---|---|---|---|
| Q1 | ~~Which DrQ-v2 difficulty tier does Door belong to, and where does the running value come from?~~ **ANSWERED 2026-09-07.** The active launcher selects `cfgs/config.yaml` for `drqv2` or the corresponding released-code config for the other four, then composes `task@_global_=Door`. `Door.yaml` inherits `task/easy.yaml`, which supplies `stddev_schedule: linear(1.0,0.1,100000)`; fresh Hydra composition of all five active configs confirms that value reaches `agent.stddev_schedule`. The old `500000` value belongs to the medium preset, and `configs/vigen.yaml` is a superseded port. | Active composition is 100000 for Door; this answers provenance, not schedule optimality for every future horizon | `runnable/_launch/rlvigen.sh`; `RL-ViGen-upstream/cfgs/task/Door.yaml`; `RL-ViGen-upstream/cfgs/task/easy.yaml`; fresh Hydra composition |
| Q2 | ~~Units of the published sheet~~ **ANSWERED 2026-09-05.** `scripts/rlvigen_reference.py` (fixed to find the asset) states: *"These are RETURNS. The benchmark does not publish success rates for robosuite, which is C33."* The Lift puzzle also dissolves — our Lift floor is 6.56 and the weak methods score below it, which shaped reward makes coherent | resolved |
| Q3 | **Should `ctrl`'s MYOW index be `k_idx + 1` rather than `0 + 1`?** | `algo.py:238` draws from the *single* nearest neighbouring cluster `myow_k` times instead of iterating the k nearest. Written as `0 + 1`, which suggests a loop variable was intended. **`ext/ctrl_public/algo.py:222` is identical**, so it is upstream's — we reproduce it faithfully, but the MYOW term is less diverse than the formulation implies | CTRL paper's MYOW description |
| Q4 | ~~Is production `num_seed_frames` 4000 or 600?~~ **ANSWERED 2026-09-07.** Fresh Hydra composition of every active RL-ViGen config with the production Door launcher overrides gives `num_seed_frames: 4000`. The `600` value belongs to an explicitly overridden historical determinism/short-probe job, not the production descriptor or launcher. | Production five-family value is 4000; the short probe remains valid historical evidence and must not be used as production provenance | `runnable/_launch/rlvigen.sh`; `RL-ViGen-upstream/cfgs/*_config.yaml`; fresh Hydra composition |
| Q5 | **Does `FAITHFULNESS` really claim IDAAC matches a continuous-control precedent?** | Review 4 says it claims rollout 2048 / γ=0.99 / lr 3e-4 / 10 epochs while production runs the Procgen family (γ=0.999, lr 5e-4, 1 epoch). The executed values match the Procgen half; I could not locate the precedent text | `FAITHFULNESS.md`; IDAAC paper's continuous-control section |
| Q6 | **Do the `medium`/`low` faithfulness rows hold?** | The reconciliation covered `high` and the two marked FIXED. `rad`, `alda`, `drq`, `ibac_sni` detail rows remain unchecked; SODA was closed 2026-09-07 against its paper, read-only DMC-GB source, and active launcher path | [`faithfulness-reconciliation.md`](faithfulness-reconciliation.md) |

**Rule for this page:** an answer moves the row out of here and into the surface it belongs to —
usually [`faithfulness-reconciliation.md`](faithfulness-reconciliation.md) or
[`CLAIMS-LEDGER.md`](CLAIMS-LEDGER.md). A question that turns out to need a *preference* moves to the
decision sheet instead.
