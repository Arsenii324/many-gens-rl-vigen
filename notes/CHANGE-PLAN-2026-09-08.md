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

### FALSIFIED 2026-09-08 by job `bt116j2650ohtkj8ev7q`. The change is kept; its justification is not.

The cell ran WITH the small-gain init -- verified by grepping the shipped payload, not assumed --
and the clip rate did not fall:

| | old init | new init |
|---|---:|---:|
| `action_clip_rate_coordinate` | 0.468 | **0.4925** |
| analytic `boundary_fraction` from `mean_log_std` | 0.330 | 0.3176 |
| excess | +0.138 | **+0.175** |

So the prediction that motivated the change was wrong, and the direction is if anything slightly
against it. The mechanism reasoning survives: `action_raw_min` reaches **-6.63** at
`sigma ~ 1.0`, and over 17,500 coordinate draws from N(0,1) the expected extreme is |z| ~ 4.1, so
that value needs a genuine **mean offset**, not a tail event. The mean really is off-centre. What
is falsified is that the INITIALIZATION is what puts it there: at 10112 frames the head has taken
~79 updates, and where the mean sits is by then a learned quantity, not an inherited one.

**Kept, on the argument that does not depend on the falsified prediction.** `torch_rl`'s
`initialize_parameters` was written for a head feeding a discrete softmax, where output scale is
nearly irrelevant; ours is a Gaussian mean, where output scale *is* the action. That is the same
condition-transplanted-across-a-domain-boundary shape as A43 and A47, and it holds independently of
what the clip rate did. `orthogonal(0.01)` is also what every other continuous-action baseline here
uses. Keeping a change whose stated benefit did not appear is only defensible because the
justification was never only the benefit -- and that has to be said out loud rather than quietly
re-labelled.

**What is now open, and it is a better question than the one I asked.** Why does ibac_sni's action
mean run off-centre within eighty updates when idaac's and ppg's do not? Candidates, none tested:
the VIB bottleneck's KL term acting on a 256-d latent the head reads directly; the absence of any
observation normalization beyond `/255`; or reward normalization -- ibac_sni trains on RAW reward
while idaac and ppg both normalize, so its advantage scale is whatever Door's returns happen to be.
The 102400-frame pilot (`bt1leljqi6n7osmcdb77`) is 10x longer and will show whether the offset
grows, stalls or decays.

---

## 3. `--batch-size` -- WITHDRAWN. It is correct in production; only the DataSphere tier degenerates

**This item was wrong, and it is the third time in this session the same mistake produced one.**
It read `--batch-size 256` against the BASE descriptor, found it inert, and filed it as a defect of
the same class as A49's inert constant. Base is the DataSphere tier. Production is `v100`.

Verified by executing the slicing arithmetic in
`torch_rl/torch_rl/torch_rl/algos/ppo.py:203-204` against both profiles:

| profile | `procs` | rollout | minibatches | sizes |
|---|---:|---:|---:|---|
| base (DataSphere) | 1 | 128 | **1** | [128] -- full-batch, `--batch-size` inert |
| **v100 (production)** | **16** | **2048** | **8** | [256, 256, 256, ...] |

Eight minibatches of exactly 256. That is `torch_rl`'s own released rollout shape, reproduced
exactly. **`--batch-size 256` is not a dead flag; it is the correct flag, degenerating only on a
tier production does not use.**

The generalization is worth more than the item. Across all seven families there are exactly **two** `v100` **constants** overrides (three
further overrides live in the `production` section: `rlvigen.replay_capacity`,
`rlvigen.preserve_snapshots`, and `ctrl.host_memory_model`):

    ibac_sni.procs      1  -> 16     (matches torch_rl's released default rollout)
    ctrl.num_envs      16  -> 64     (matches CTRL's released default, 64 x 256 = 16,384)

Both are the values the DataSphere tier was infra-bound *away* from. So the "infra-bound
compromise" framing that appears throughout this project's prose is a statement about the
**pre-production tier only** -- at production, both baselines run their own upstream parallelism
exactly. Anything that reads `procs=1` or `num_envs=16` as a fidelity compromise in the write-up is
describing a machine we are not going to publish results from.

What remains actionable is one sentence, not a change: the base descriptor should say the batch
size is inert *there*, so nobody rediscovers this as a defect. The production behaviour needs no
fix because it is already right.

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

---

# The ibac_sni frame-stack pilot INDICTS, and the instrument nearly missed it

`bt1leljqi6n7osmcdb77`, 102400 frames, carrying `frame_stack=3`, A43's `lr`, A47's latent width and
today's small-gain policy head.

**It passed the criterion as first written, and it should not have.** `gaussian_boundary_fraction`
derives the clip rate from `log_std` and assumes a ZERO MEAN. The cell had `sigma 1.073`, so the
analytic rate was **0.351** and the check said healthy — while the evaluator's own measurement said:

| | 10112 frames | 102400 frames |
|---|---:|---:|
| `action_clip_rate_coordinate` | 0.443 | **0.857** |
| `action_clip_rate_vector` | 0.983 | **1.0000** |
| `action_raw_min` | -6.63 | **-10.43** |

Every action vector has a clipped coordinate. Inverting 0.857 at `sigma 1.073` puts the mean about
**2.1 action units outside** a [-1, 1] space. The policy is degenerating through the MEAN while the
instrument watched the VARIANCE — the same shape as the failure it was built for, where
`PRODUCTION-RUNBOOK` watched NaN and the failure was in sigma. `read_stack_pilot.py` now prefers
the measured quantity over the modelled one and indicts on it.

## The control, and why it is not conclusive yet

Across every record in the corpus at ~10k frames:

| group | coord clip | vector clip |
|---|---:|---:|
| squashed / clamped heads — alda, curl, drq, drqv2, rad, sgqn, soda, svea | **0.000** | 0.000 |
| ctrl | 0.242 | 0.700 |
| ppg | 0.323 | 0.940 |
| idaac | 0.346 | 0.949 |
| ibac_sni | 0.443 | 0.983 |

So substantial clipping is a **property of the unsquashed group**, not an ibac_sni defect — the
eight bounded heads clip exactly zero. ibac_sni is the highest of the four, and it doubled between
10k and 102k.

**What is missing is the control at the same length.** There is no idaac or ppg run at 102400
frames, so "0.857 at 102k" cannot yet be separated from "what any unsquashed head does at 102k on
Door". The `ctrl` pilot (`bt1hvkmei18hasgj5bbv`) is that control — same length, same task,
unsquashed head, and its 10k value is the lowest of the four. **Do not spend a re-pilot cell before
it lands.**

A43's disambiguation order stands if the control confirms this is ibac_sni-specific: revert `lr`
first, re-pilot, and if the failure survives that it is the stack. Note that today's init change is
now a fifth variable in that stack, and the 10k evidence says it moved the clip rate the wrong way
by 0.024 — so it should be reverted alongside `lr`, not held constant.

**What passed.** Finiteness, and the sigma runaway that `PRODUCTION-RUNBOOK:18` records did NOT
recur: 0.318 -> 0.351 over the run, against the 4.3 of the historical failure. `entropy_coef=0` is
holding. The authored three-frame stack ran 102400 frames without crashing, which is the narrow
thing the pilot was scheduled to establish.

---

# The ctrl frame-stack pilot HUNG, the watchdog caught it, and the cause is the CUDA pairing

`bt1hvkmei18hasgj5bbv`, 102400 frames. Killed by the stall watchdog built earlier today after
**1800s of silence** — its first real opportunity, and the only reason this cost 30 minutes rather
than the full 10933s cell timeout it would otherwise have burned in full.

What it hung in, from its own log:

    Allocator (GPU_0_bfc) ran out of memory trying to allocate 8.27GiB
    conv_algorithm_picker.cc:770  Results mismatch between different convolution algorithms.
      This is likely a bug/unexpected loss of precision in cudnn.
    Device: NVIDIA L4   Driver: 12.2.0   Runtime: 12.9.0   cudnn: 9.25.1

**Driver 12.2.0 against runtime 12.9.0**, and that is not a coincidence. The environment-drift
audit run a few hours earlier measured that `ctrl` is the ONE family whose JAX stack pulls the CUDA
**12.9** wheels while every torch family pins **12.1** — the single largest cross-family
environment difference in the corpus, and at the time it read as a harmless consequence of each
family's own requirements. It is the risk `gate_environment_manifest` names, and it surfaced as a
deadlock inside cudnn autotuning rather than as an import error.

**Not caused by anything changed today.** `ctrl`'s 10000-frame attest cell
(`bt1d8jicbkdu1jv87ogp`) succeeded on the same stack with the same three-frame geometry, so this is
a path reached only at length. `train_ppo.py`'s fail-closed terminal save runs at the end and was
never reached.

**Re-submitted as `bt17gfr8pq5astv4g3n3`** with `XLA_FLAGS=--xla_gpu_autotune_level=0`, which skips
the algorithm benchmarking that deadlocks. That is a **diagnostic, not a production setting**: if
it completes, the diagnosis is confirmed, and the real fix is the driver/runtime pairing on the
production image — which is the baked-image work `gate_environment_manifest` already says is
needed, now with a concrete failure behind it instead of a hypothetical.

**Consequence for the ctrl control.** The comparison that would tell us whether ibac_sni's 0.857
clip rate is ibac_sni-specific or just what an unsquashed head does at 102k is not available yet.
Both pilots remain open.

## One observation on ibac_sni's drifting mean, with its control missing

From its own recorded diagnostics, averaged over the wave:

    grad_norm       13.91      against max_grad_norm 0.5
    kl               5.29      the VIB bottleneck KL, weighted by beta 1e-4, so ~5e-4 of the loss
    approx_kl_k3     0.0064    the POLICY KL, and it is normal

So the gradient-norm clip is **fully binding on essentially every update**, at roughly 28x. When a
clip binds that hard the step direction survives and the magnitude is pinned at 0.5, so the policy
marches at a constant rate in whatever direction the gradient points — which is a mechanism that
would move a mean steadily outward over eighty thousand frames.

**This is one number with no control and should not be treated as a diagnosis.** `idaac`, `ppg`
and `ctrl` do not emit `grad_norm` into the record at all, so there is nothing to compare it
against, and `max_grad_norm=0.5` is shared by three of the four. A 28x clip ratio might be normal
for all of them on Door.

Making the on-policy four log comparable optimizer diagnostics is the obvious next step and is
**deliberately not done now**: those files are family runtime members, so it would move three
evaluator revisions and void the 7/7 attestation for a hypothesis with a single data point behind
it. It belongs in the same batch as the `eval_provenance.py` import fix — the next one that already
touches a closure member.

---

# Course correction: the ibac_sni clip finding does not block production, and the procs=1 pilots cannot settle it

Prompted by the right question — *why the diagnostic; why not run as-is in production?* Two things
were conflated, and separating them removes about three hours from the schedule.

## The frame-stack gate is MET, and I indicted it on a threshold I invented

`DECISIONS-IF-PRODUCTION-GOES-WRONG`'s frame-stack section asks for *"one short cell each, read for
non-degenerate learning rather than a score"*, because `ctrl` and `ibac_sni` run **authored**
stacking code that had never trained. `bt1leljqi6n7osmcdb77` ran 102400 frames with finite losses
and a stable `sigma` of 1.073. **The authored stacking code works. That is what the gate asked.**

What indicted it was `MEASURED_CLIP_INDICTS = 0.60` in `scripts/read_stack_pilot.py` — a number
**I chose**, reasoning "twice what having no policy costs you". It is not the project's criterion.
The project's words are *"non-collapsed action distribution"*, and at `sigma` 1.073 the
distribution is not collapsed; it is off-centre. Those are different findings, and mine was the
stricter one applied under the other's name.

## And the pilots run a regime production does not

    pilot tier   procs= 1   rollout=  128   minibatches=1   (full-batch PPO)
    v100         procs=16   rollout= 2048   minibatches=8   (torch_rl's own released shape)

Every ibac_sni pilot available on the DataSphere tiers is `procs=1`, because `gt4.1` has 4 logical
CPUs and `gt4i.1` has 8. So v207 (init reverted) and the planned v208 (lr reverted) would each
spend 3.6 hours isolating a variable **in an update structure production never runs** — full-batch
against eight minibatches, at twice the update-to-data ratio. A variable that mattered there might
not matter at production, and vice versa. Tuning against it is tuning against the wrong thing.

**v208 was written and deliberately not submitted.** v207 is already executing and is left to
finish: it costs nothing further and gives a clean matched isolation of the init against v200's
0.857 at the same frame count. It is **informative, not blocking**.

## Where the finding actually belongs

Gate 1, `ibac_sni competence` — an OWNER gate, whose test `notes/RUNNING-ON-PRODUCTION-HOST.md`
step 5 already schedules **at the production settings**, `procs=16`. That is the only place the
question can be answered. Step 5a now tells the operator to read
`action_clip_rate_coordinate` there, with the fleet calibration attached.

## What this means for running as-is

**Production should run ibac_sni as it stands.** It is the authors' own PyTorch branch on their own
CoinRun trunk; a faithfully implemented method that performs badly is a result, not a defect, and
that sentence is the project's own. Adjusting it now, against a pilot regime production does not
use, on a threshold I invented, would be exactly the outcome-dependent tuning gate 4 forbids.

**Pre-production is therefore complete when the seven attests and the `ctrl` frame-stack pilot
land — about 10:05 — not when the ibac_sni arms finish at 12:10.**

---

# The ctrl frame-stack pilot PASSES, and it sharpens the ibac_sni reading

`bt1ee0lr7n3gu2sqe3le`, 102400 frames, `frame_stack=3`, no `XLA_FLAGS` — the third attempt, after
two were killed by a stall watchdog that was reading a stdout buffer's flush cadence rather than
the process. Every check passes:

    FINITE                     5 loss series, 24 rows -- a real trajectory, not one point
    NOT SATURATED (measured)   action_clip_rate_coordinate 0.000, vector 0.0000
    NOT SATURATED (analytic)   boundary fraction 0.318 -> 0.326, sigma 1.02
    NOT COLLAPSED              sigma 1.018
    SEPARATION                 late-window return 17.36 against the 1.842 floor, +5.47 floor-sd

The separation row is informational by design and is still worth stating: **+5.47 floor-sd is real
learning**, not merely survival, at 1.3% of `ctrl`'s own training horizon.

**The authored three-frame stacking works.** Both baselines that had no stacking mechanism on the
Door path before 2026-09-08 have now trained with authored stacks — `ibac_sni` for 102400 frames
finite and stable, `ctrl` for 102400 frames while learning. That is what the gate asked, and it is
met for both.

**And the contrast is the sharpest evidence yet that `ibac_sni`'s saturation is its own:**

| at 102400 frames | coord clip | vector clip | late return |
|---|---:|---:|---:|
| `ctrl` | **0.000** | 0.0000 | **17.36** |
| `idaac` | 0.384 | 0.962 | — |
| `ibac_sni` | **0.857** | 1.0000 | 1.80 (at floor) |

Three unsquashed continuous heads, same task, same length. One clips nothing and learns, one sits
flat at its 10k value, one doubles and stays at the floor. Whatever drives `ibac_sni` is not the
head type, not the task and not the horizon — which is exactly what gate 1 exists to test at
`procs=16` on the host, and exactly why tuning it here against a `procs=1` regime would have been
tuning against the wrong thing.
