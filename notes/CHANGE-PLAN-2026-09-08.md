# Change plan — what to change, what to keep, and why

**Status: OPEN and INCOMPLETE.** Three agents are sweeping the axis space (matrix × 12 verified
against source; all 27 reviews → inventory diffed against the matrix; from-first-principles walk of
all twelve training loops). Everything below comes from verification done by hand in this session
and will be extended, not replaced, when they land.

Nothing here is implemented yet. Items 1–4 touch `families.json` or a clone, which moves evaluator
revisions, so they land as **one batch** — the difference between one attestation wave and four.

---

## 1. `ibac_sni` base `procs`: the REASON is stale, the VALUE is not

**First conclusion, and it was wrong.** I read `families.json`'s base note — dated 2026-09-02,
reason: *"With 2 it dies at torch_rl.PPOAlgo's parallel env setup with EOFError"* — alongside the
`v100` reason recording that the spawn/factory repair landed and *"the bounded Linux/EGL procs=16
functional smoke passed on gt4i.1 (`bt1djai23kme336auat4`)"*, and concluded the base value was a
leftover that should be raised to 16.

**Physical evidence says otherwise.** From `resources.json` in retained cells:

| tier | `logical_cpu_count` | families on it |
|---|---:|---|
| `gt4.1` | **4** | ibac_sni, idaac, ppg |
| `gt4i.1` | **8** | ctrl, alda, dmc_gb, rlvigen |

Neither DataSphere tier has 16 cores. `procs=16` there is 4x or 2x oversubscription. The repair
made `procs>1` *runnable*; it did not make 16 *appropriate* on 4 CPUs.

**So both halves need stating separately.**

- **The recorded reason is stale and must be replaced.** The EOFError it cites was repaired, and
  leaving it as the justification is the same stale-prose defect this project keeps finding — it
  invites exactly the wrong conclusion I drew from it. Re-derive it from core count.
- **The value stays 1** on DataSphere.
- **The `v100` override to 16 assumes the production host has >=16 cores. That is unverified here**
  and belongs in the host runbook's measurement list beside renderer parity and throughput.

**The structural consequence stands, and gets sharper.** DataSphere cells cannot reproduce
production's update structure, because production's `procs=16` needs cores DataSphere does not
have:

| | rollout | minibatches | grad steps/rollout | updates/frame |
|---|---:|---:|---:|---:|
| DataSphere, `procs=1` | 128 | **1 — `--batch-size 256` exceeds the rollout, so it is inert** | 4 | 0.0312 |
| production, `procs=16` | 2048 | 8 | 32 | 0.0156 |

Full-batch updates at twice production's update-to-data ratio. Therefore **the "exact-final IBAC
competence" pilot review 27 §10 asks for cannot be run pre-production at all** — on DataSphere it
would exercise a different optimizer path. It requires the V100. That is a scheduling fact for the
owner, not something to fix in this repository.

**Method note, worth more than the item.** I derived a change from two pieces of project prose and
the physical evidence contradicted it. The prose was stale in a way that pointed at the wrong
action, and one `resources.json` settled it. Prefer the artifact over the note describing it —
including when the note is this project's own.

## 2. `ibac_sni` policy-head initialization → small-gain

**Evidence.** `torch_rl/model.py:12-18`'s `initialize_parameters` normalizes every `Linear` layer's
weight rows to unit norm, including the policy head. Measured consequence, from this wave's records:

| baseline | coord clip rate | predicted from its own `log_std` | excess |
|---|---:|---:|---:|
| ctrl | 0.000 (`raw_max` 0.16) | — | — |
| idaac | 0.350 | 0.320 | +0.030 |
| ppg | 0.327 | 0.317 | +0.010 |
| **ibac_sni** | **0.468** | 0.330 | **+0.138** |

idaac and ppg clip exactly as much as an untrained std≈1 Gaussian must — initialization, not a
defect. ibac_sni's excess is not explained by its `log_std`; its action mean is off-centre.
`runnable/ctrl/models.py:23` shows the convention every other continuous-action baseline uses:
`nn.initializers.orthogonal(0.01)`.

**Decision: change.** The Gaussian head is *our* continuous-action adaptation — torch_rl's head fed
a discrete softmax, where output scale is nearly irrelevant. Its initialization was therefore never
chosen, only inherited across a domain boundary where the condition fails. Same shape as A43 and
A47.

**Caveat:** measured at 10k frames on near-untrained policies. Re-measure at production length;
`log_std` moves.

---

## 3. `--batch-size` inertness must be stated

Under the base profile `--batch-size 256` has no effect (item 1). A declared hyperparameter that
does nothing is the same class as the inert `constants` entry A49 found. If item 1 lands this
resolves itself; if base `procs` stays 1 for a host reason, the descriptor must say the batch size
is inert there.

---

## 4. `ibac_sni` provenance string — sharpen, in the opposite direction from review 27

Review 27 §9 recommends freezing it as a hybrid and not calling it a reproduction. Verified against
source, the current framing understates what we have:

- `runnable/ibac_sni` reconstructs from **microsoft/IBAC-SNI @ `6b3a58b`** — the authors' own
  repository, which ships *both* their PyTorch `torch_rl/` and the TF `coinrun/`.
- `nr_samples` appears in **0** files under `ext/IBAC-SNI/torch_rl` and **1** under
  `ext/IBAC-SNI/coinrun`. `softplus`, `sni_type` and `use_l2a` appear in torch_rl and **not** in
  coinrun.
- The command review 27 quotes as the authors' main-result command
  (`--l2 0.0001 -uda 1 --beta 0.0001 --nr-samples 12 --sni`) is `python3 -m coinrun.train_agent`,
  under `cd coinrun` — the **TF branch's** command, from `README.md` line ~109.
- Our launcher passes only flags `torch_rl` defines; `--nr-samples` and `--sni` appear in it solely
  as comments citing that README line.

**Decision:** state it as *the authors' own PyTorch implementation, run with the authors' own
CoinRun visual trunk because the task is pixel-based and torch_rl's native trunks are
MiniGrid-shaped* — and record that the 12-sample/L2/UDA machinery is a **CoinRun-branch feature
their PyTorch branch never had**, not a gap in our port. Correct A43's and A47's entries, which
lean on "reviews called this unreachable"; the reviews were comparing against the other branch.

---

## 5. Keep, with the rule that makes them consistent

**Rule: follow `torch_rl` — the implementation we run — unless the value's *condition* depends on
the architecture we replaced.**

| item | torch_rl | CoinRun | decision |
|---|---|---|---|
| learning rate | 7e-4 | 5e-4 | **changed (A43), consistent** — lr's condition is network scale, and we replaced the network |
| PPO epochs | 4 | 3 | keep 4 — data reuse, not architecture |
| rollout shape | 16 × 128 | 32 × 256 | keep — production's `procs=16` restores torch_rl's intended shape, *conditional on the V100 having the cores* (item 1) |
| cliprange decay | none | linear | keep constant — the same reasoning A43 used to decline lr decay; torch_rl has no schedule mechanism |
| gamma | 0.99 | 0.999 | keep 0.99 — task horizon, not architecture; 10 of 12 baselines use it from their own sources |

On gamma, declare what is true rather than implying a fit: Door's episode is 500 steps, so 0.99 is
an effective horizon of 100 and 0.999 is 1000. **Neither branch's gamma was chosen for this task.**

---

## 6. Record the clipping measurement

It currently exists only in conversation. It closes review 27 §11 for the baseline the review was
actually about: **CTRL — the only one whose representation objective conditions on the action —
does not clip at all.** The concern is real in principle and empty in fact for the case that
mattered. The other three are quantified against their own `log_std` above.

---

## 7. The structural one

`scripts/audit_executed_hyperparameters.py` checks **6 values** — only those `FAITHFULNESS.md`
happens to claim. That is why "are we in check on hyperparameters?" needed a three-agent sweep
instead of a command.

**Extend it to the enumerated axis set** once the agents land, so the question is answered by
running something. Every finding in this file was reachable by reading source; none of it was
reachable by running an instrument. That is the gap worth closing, because it is the one that lets
the next drift go unnoticed.

---

## Explicitly NOT changing

- **ctrl gamma 0.999** — its own paper's Table 2, and it is the one baseline that is not 0.99.
- **ctrl raw-vs-executed action** — measured zero clipping; see item 6.
- **entropy across the fleet** — ctrl 0.01 and idaac/ppg 0 are both source-backed; ibac_sni's 0 is
  an adaptation with both a mechanism (`log_std` is global and state-independent, so `H[q(a|z)]`
  does not depend on `z`) and a measurement behind it.
- **The nine OWNER gates** — they are the owner's, and a gate is not flipped to make a report green.
