# Change plan — what to change, what to keep, and why

**Status: OPEN and INCOMPLETE.** Three agents are sweeping the axis space (matrix × 12 verified
against source; all 27 reviews → inventory diffed against the matrix; from-first-principles walk of
all twelve training loops). Everything below comes from verification done by hand in this session
and will be extended, not replaced, when they land.

Nothing here is implemented yet. Items 1–4 touch `families.json` or a clone, which moves evaluator
revisions, so they land as **one batch** — the difference between one attestation wave and four.

---

## 1. `ibac_sni` `procs` — one line of stale prose, and nothing else

This item shrank twice under challenge. Both earlier versions are kept, because the way they were
wrong is the useful part.

**Version 1: "base `procs` is stale, raise it to 16."** Read from `families.json`'s base note
(dated 2026-09-02, blaming an EOFError) plus the `v100` reason (recording that the spawn/factory
repair passed a `procs=16` smoke). Wrong: `resources.json` from retained cells shows `gt4.1` has
**4** logical CPUs and `gt4i.1` has **8**. Neither DataSphere tier has 16. The repair made
`procs>1` runnable; it did not make 16 appropriate on 4 cores. **The value stays 1 there.**

**Version 2: "the `v100` override to 16 assumes >=16 cores, unverified here."** Also wrong.
`notes/remote-infra.txt` is a captured session from the production host:

    varaksin_as@cds2:~$ nproc
    16
    CPU(s): 16   Core(s) per socket: 8   Socket(s): 2   Intel Xeon Gold 6154
    Mem: 125 total, 113 available

`procs=16` is grounded in a measured core count from the real machine.

**And the pilot is already scheduled.** `notes/RUNNING-ON-PRODUCTION-HOST.md` step 5: *"Run the
exact IBAC-SNI competence pilot. Use the intended production settings (`procs=16`, Impala trunk,
`beta=1e-4`, entropy `0`) and predeclared internal health/learning criteria."*
`notes/DECISIONS-IF-PRODUCTION-GOES-WRONG.md` gate 1 names the same thing as its cheapest test, and
`production_gates.py` carries it as an OWNER gate. It is exactly the "once the production machine
exists" series, and it was already in it.

**What actually remains, and it is one thing:** the base note still justifies `procs=1` with a
fault that was subsequently repaired. That is stale prose pointing at the wrong action — it is what
produced version 1 above. **Re-derive the reason from the tier's core count (4 on `gt4.1`).** The
value does not change.

**Worth keeping regardless of the item**, because it is not written down elsewhere in these terms:
DataSphere cannot reproduce production's update structure, and the arithmetic says why.

| | rollout | minibatches | grad steps/rollout | updates/frame |
|---|---:|---:|---:|---:|
| DataSphere, `procs=1` | 128 | **1 — `--batch-size 256` exceeds the rollout, so it is inert** | 4 | 0.0312 |
| production, `procs=16` | 2048 | 8 | 32 | 0.0156 |

Full-batch updates at twice production's update-to-data ratio. This is the mechanism behind the
already-scheduled requirement that the competence pilot run on the V100 — the runbook says to do it
there; this says what would be measured wrong if it were done here instead.

**Method note, and it is the whole lesson of this item.** Three times in this session I declared
something unexamined or unverified that the project had already examined: `BOOTSTRAP_SECONDS`
(prose vs code), reward normalization (12 review files discuss it), and now this (two docs, one of
them a terminal capture from the host). Asserting absence is a claim like any other and needs the
same evidence as asserting presence. **Read the docs that would close a gap before reporting the
gap.**

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
