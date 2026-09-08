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

---

# Extension — what the sweep returned (agents A and B; C still running)

Agent A verified the enumerated axes against source across all twelve. Agent B read all 27 review
files and diffed the inventory against `notes/PARAMETER-REVIEW-CONSENSUS-MATRIX.md`. Items 8-15
below are theirs, re-verified here before being written down where a re-verification was cheap.

**Both agents were briefed mid-run with a correction that turned out to matter**: base values in
`families.json` are the DataSphere ones, and the `v100` host profile is production. Neither brief
said so originally. That is the same error that produced two wrong versions of item 1, and it was
replicated into the briefs before either agent had returned.

## 8. CTRL declares six constants that reach nothing — same class as A43 and A49

`families.json` `ctrl.constants` declares `num_clusters`, `n_att_heads`, `embedding_type`, `lr`,
`lr_ctrl`, `max_grad_norm`. None appears in `options` or `positional`, and `runnable/_launch/ctrl.sh`
does not hardcode them either. The process runs on `train_ppo.py`'s own `absl.flags` defaults.

No number is currently wrong, because each default happens to equal its declared value. That is
precisely what makes it dangerous: **A45 already recommends changing `lr_ctrl`**, and editing the
JSON field would do nothing at all while looking like it had. `--batch-size` (item 3) and A43's
`lr` are the same defect; this is its third instance, so it is a class, not three accidents.

**Decision: template them into `options`.** Not delete them. A descriptor that stays silent about
values production actually runs is worse than one that repeats a default, and templating is what
A49 did for `ibac_sni`'s `lr`. Verify each flag name against `train_ppo.py` before adding it — an
`absl` flag that does not exist is a hard failure at startup, which is the good outcome, but it
should be found here rather than on the host.

**And close the class, not the instance.** Extend `scripts/audit_executed_hyperparameters.py`
(item 7) to fail when any `constants` key is absent from both `options` and `positional` and is not
listed as deliberately inert. Three instances found by hand is the signal that hand-checking is the
wrong instrument.

## 9. The five RL-ViGen baselines do not share one encoder, and their group label says they do

| baseline | encoder | conv layers | repr_dim |
|---|---|---:|---:|
| drqv2, drq | `Encoder` (`drqv2.py:48-67`) | 4 | 39,200 |
| svea | `SharedCNN` (`svea.py:85-108`) | 11 | 14,112 |
| curl, sgqn | `CNNEncoder` + `Linear(39200, 512)` | 4 + projector | 512 |

Three architectures inside one group. `families.json`'s provenance strings call it "RL-ViGen's
DrQ-v2/DDPG-style backbone", which is true only of the Actor/Critic heads (`feature_dim=50`,
`hidden_dim=1024` — those really are identical).

**Decision: keep the encoders, fix what is claimed about them.** Each trunk is its own method's
published choice — SVEA's 11-layer stack is DMC-GB's convention that SVEA was built on, CURL's
projector is part of CURL. Equalising them would be less faithful, by exactly the rule item 5 uses.

What must change is two claims:

- the provenance strings, which assert a shared backbone that does not exist;
- `scripts/comparison_blocks.py`'s group name, **"off-policy, differing in augmentation"**. That
  label asserts one axis of difference. There are two. A reader comparing `svea` with `drqv2`
  cannot attribute the gap to overlay augmentation when the encoder is also 11 layers against 4.

This does **not** become a blocking axis. Blocking on encoder architecture would empty the group,
and it would be the wrong operation anyway: the encoder is part of the method, not a condition
imposed on it. The fix is an honest label plus a stated caveat, which is the same treatment
`reward scale` already gets.

## 10. The online-eval sentinel does not disable evaluation — VERIFIED HERE

`RL-ViGen-upstream/utils.py:81-87`:

    def __call__(self, step):
        if self._every is None:
            return False
        every = self._every // self._action_repeat
        if step % every == 0:
            return True

Every attest and cover cfg sets `EVAL_EVERY_FRAMES=2147483647` to turn evaluation off. At step 0,
`0 % 2147483647 == 0` is **True**, so one full eval sweep runs before training starts. Agent B
found it in review 21; it is confirmed directly from source here, and v197's svea log shows
`Now the mode is eval-easy` seven times immediately after env construction, which is what that
sweep looks like.

Two consequences, and the second is the one that matters:

1. every "eval disabled" cell has been paying for one eval sweep it did not intend;
2. that sweep **draws from the Door-placement RNG before training begins**, so the training run is
   not the run the manifest describes. It affects `rlvigen`, `rad`, `soda`, `alda`.

**Decision: pass `None` rather than a sentinel.** `Every` already returns `False` for `None`, which
is the behaviour the sentinel was reaching for. Changing the comparison itself (`step > 0 and ...`)
would also suppress a *deliberate* step-0 baseline evaluation, which is a real thing to want; the
defect is the encoding of "off", not the semantics of `Every`.

`utils.py` is a `FAMILY_RUNTIME_MEMBER` for `rlvigen`, so this moves that family's revision. Its
counterparts in `dmc_gb` and `alda` move theirs. Batch accordingly.

## 11. `docs/FAITHFULNESS.md` disagrees with source on two `sgqn` numbers

Lines 366-367, 403-404 and 1042 give `aux_lr = 8.0e-5` as resolved; `cfgs/sgqn_config.yaml:54`
ships `1e-4`, and A41 kept the shipped value. Line 340 lists the canonical quantile as `.90`;
A41-EXTENDED read the paper and found `0.95`/`0.98` per task. The doc records a superseded
resolution and a superseded reading. **Fix the doc.** It is the file most likely to be quoted by
someone who does not re-derive.

## 12. Disclosures, not changes

- **PPG has no gradient clipping at all** (grep-verified across `phasic_policy_gradient/`), while
  `idaac`, `ibac_sni` and `ctrl` all clip at `0.5`. Absence, not omission — but it should be stated,
  because three of four siblings clipping makes the fourth look like an oversight.
- **PPG's GAE λ = 0.95 is a bare literal at `train.py:95`**, reachable from neither `families.json`
  nor a CLI flag. It agrees with every other on-policy baseline, so nothing is wrong; what is worth
  recording is that it *could not* be changed through the mechanism every other PPG parameter uses.
- **The SAC three run a two-speed target update** — `critic_tau=0.01` with a separate, slower
  `encoder_tau=0.05` — that the DrQ-v2 lineage has no counterpart for. `rad`, `soda` and `alda`
  share it; `drqv2`/`svea`/`sgqn`/`curl` Polyak one target at a single rate.
- **`rad`/`soda` and `alda` share one catch-up idiom**: `num_updates = init_steps if step ==
  init_steps else 1`. The project files this under ALDA; it is inherited SAC-loop convention across
  three baselines, and UTD arithmetic for any of them should use the same reasoning.
- **`idaac`'s `--eps` flag is documented as "RMSprop optimizer epsilon" and configures Adam**
  (`algo/ppo.py:33`). Upstream's own vestigial help text. Record it so nobody "corrects" the value
  from the wrong optimizer's conventions.

## 13. What agent B found that the matrix had dropped

Twenty items; the ones that are project-actionable rather than historical:

- **Terminal-checkpoint integrity.** `safe_checkpoint.py` makes a failed write non-fatal — right for
  periodic saves, wrong for the terminal one, and callers ignore the return either way. A failed
  600k write leaves a stale 550k checkpoint that retention accepts on size and the evaluator scores
  as "600k". Verify before production; this changes what an endpoint number means.
- **Retention is not invariant to a reward offset**, and Door's floor is non-zero. The floor-adjusted
  form is already adopted (`DECISIONS-IF-PRODUCTION-GOES-WRONG.md` gate 3); the matrix has no record
  of it, which is how it came back as a finding.
- **The raw-vs-executed action seam generalizes to `idaac` and `ibac_sni`**, not just `ctrl`.
  Item 6 measures all three; that measurement is the answer, and it should live where the seam is
  discussed rather than only here.
- **Reviews 17, 19 and 20 independently state a wrong SGQN quantile** (`0.90`/`0.70`), none citing a
  page. A41-EXTENDED read the paper and found `0.95`/`0.98`, with no value at all given for the
  consistency weight. Three independent reviews agreeing is not evidence; keep A41-EXTENDED
  prominent for exactly that reason.
- **The gemini review claims to have read `evaluation_score.xlsx`** and reports published eval-easy
  means (floor 1.82, drqv2 3.6, curl 6.6, drq 14.0, svea 268.8, sgqn 391.4). If real, this is the
  external anchor twenty reviews ask for. It is a self-flagged weak-model source and no other review
  reports these figures. **Verify against the file itself before any of it is repeated** — gate 6
  already uses the 3.6/range-1-7 figure, so the two must be reconciled rather than averaged.

## 14. Sequencing — and why `svea` does not run yet

`svea`'s v197 cell ERRORed (`bt12f5us5h120laajpme`), so `rlvigen` is the one family of seven with no
current attestation. The reflex is to re-run it immediately. That is wrong here.

Items 8, 9, 10 and 11 touch `families.json` (a `CONFIG_MEMBER`, which moves **every** family's
revision) and `RL-ViGen-upstream/utils.py` (a `rlvigen` runtime member). Running `svea` now buys one
attestation that the next batch invalidates. `cfg-rlvigen-attest-v198.yaml` is built, fixed and
ready; it waits for the tree to stop moving. This is the rule the project already wrote down after
the 2026-09-07 generation loss, and agent C has not reported yet.

## 15. What the v197 `svea` failure actually cost, and the two defects behind it

Not a slow run. `bt12f5us5h120laajpme` trained to 8500 of 10000 frames at 6.08 fps in about 15
minutes, then hit `malloc_consolidate(): unaligned fastbin chunk detected` — glibc detecting an
already-corrupt heap — in a forked Places365 DataLoader worker inside `random_overlay`. The worker
took `SIGABRT`; `DataLoader worker (pid 23921) is killed by signal: Aborted.` surfaced at
`svea.py:299`.

**Defect one: a default set today against its own documented rationale.** `run_probe.sh` began
forwarding `RLVIGEN_PLACES_WORKERS` on 2026-09-08 with a default of `8`. P19's comment in
`utils.py`, four lines above the value it was read from, blames `8` for this exact corruption. Every
cfg that ever completed on the overlay path sets `0`. Fixed: the runner default is now `0`, and
`cfg-rlvigen-attest-v198.yaml` pins it explicitly.

The corruption is **intermittent**, which is the part worth keeping. `bt1utl06n6mqffrt2jdn`
(`cfg-sgqn-cover-v197`) ran the same overlay path, the same 10000 frames, the same absent dial and
therefore the same 8 workers, on the same tier in the same hour — and exited SUCCESS in 2381s. One
clean run at 8 is not evidence that 8 is safe; a 600k-frame production cell samples the race 60
times more often than a 10k smoke does.

**Defect two, not yet fixed: a dead cell does not die.** The worker aborted around 03:20 and the
process hung until `CELL_TIMEOUT_SECONDS` killed it at 05:06:19. Of 7800 seconds, roughly 1200 were
work. Every failure of this class costs a full cell timeout regardless of when it fails.

That reframes the budget question, and `sgqn`'s 2381s answers it: an `rlvigen` attest cell is a
**40-minute** job, not a three-hour one. v198's timeout is cut to 3600s cell / 4200s outer — about
1.5x the measured duration — so a hang costs an hour instead of three. `FRAMES` stays at 10000
rather than dropping toward `min_frames` 4001, for one specific reason: the corruption appeared at
~8500 frames, and a 4500-frame budget would attest the evaluator without ever entering the region
where the fix is under test.
