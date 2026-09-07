The next move should be a controlled repair/freeze pass, not more exploratory auditing. The uploaded artifact is from `main@4cd1587` and is dirty by three paths, so first treat it as a very good snapshot of Claude’s intermediate state, not necessarily the latest live checkout.

The most important conclusion from reviewing the artifact is that Claude was on a productive track, but the project should deliberately break the current v194 “freeze.” There are correctness defects worth fixing before any evaluator wave is allowed to become final.

### My current assessment

| Area | Current status | What I would do |
|---|---|---|
| CTRL native evaluation | **Wrong** | Change native to deterministic mode/mean |
| IDAAC native evaluation | Correct stochastic | Keep |
| IBAC native evaluation | Correct stochastic for `torch_rl` lineage | Keep |
| PPG native evaluation | Sampling reasonable, provenance overstated | Keep sampling; fix wording |
| Deterministic secondary pass | Good design | Keep |
| `run_on_production_host.sh` RL-ViGen/Places interface | **Broken** | Fix before any bare-V100 run |
| Per-cell GPU assignment through wrapper | **Broken** | Forward `NATIVE_CELL_DEVICES` |
| Places365 train acquisition | Mostly correct | Preserve train decision |
| Places365 train execution in `run_probe.sh` | **Broken/inconsistent** | Repair end-to-end |
| Renderer parity | Unproven | Measure on final V100 closure |
| CTRL64 memory | Extrapolated | Measure on V100 |
| IBAC16 runnability | Proven | Competence still needs pilot |
| 600k pipeline | Not proven end-to-end | DrQ-v2 canary after host gates |
| Clean GitHub source bootstrap | Mostly good | Finish usability/verification cleanup |
| Final evaluator attestations | Not final anymore | One new 7-family wave after fixes |

The CTRL finding is particularly solid. The pinned upstream CTRL evaluator explicitly uses the greedy branch, whereas the artifact's `eval_grid.py` currently says native CTRL samples and executes `sample=(policy_mode != "mode")`. Upstream CTRL's evaluation is deterministic. 

IDAAC and IBAC do not need the same change: their released evaluation paths sample.   PPG's released `PpoModel.act()` samples, but OpenAI did not supply a distinct evaluator from which to establish a stronger evaluation-time claim. 

So I would not switch everybody to deterministic. Preserve the protocol you had converged on: source/native primary estimator plus deterministic standardized secondary estimator.

## The sequencing I would use

1. **Stop treating v194/v195 as prospective final certification.**
2. **Make all remaining evaluator-closure corrections in one batch.**
3. **Repair production runner contracts without touching learning behavior.**
4. **Finish the GitHub/publication path separately.**
5. **Freeze once.**
6. **Run exactly one final seven-family evaluator-attestation generation.**
7. **Move to the V100 host measurements.**
8. **Run the full 600k canary.**
9. **Only then release the fleet.**

That order matters more than almost any individual code detail.

### Current v194/v195 jobs

I would not preserve an incorrect evaluator just because the v194 wave is running. The project notes themselves already learned this lesson several times: v191/v192/v193 produced successful jobs whose records were stale on arrival because shared evaluator files changed while the wave was running.

CTRL now provides a legitimate reason to change `scripts/eval_grid.py`. That is a shared evaluator `CODE_MEMBER`, so once you fix it, all seven current evaluator revisions change. Therefore the present v194 results cannot be the final attestations even for families unrelated to CTRL.

If the current jobs are already close to completing and cost only minutes, there is no need to frantically cancel them. They can remain diagnostic evidence. What I would not do is populate them as the final 7/7 ledger and then pretend later that only CTRL needs refreshing.

The v195 Places jobs are similarly useful as path diagnostics. They do not establish that your actual ~1.8M-image, 365-class production train population is correctly provisioned. At best, the small representative asset proves the train branch can execute.

And, in this artifact, that train branch still has an obvious contradiction which may cause those jobs to fail anyway.

## Repair the evaluator first

The CTRL repair should be small.

Current native behavior effectively does:

```python
sample=(policy_mode != "mode")
```

For CTRL, `native` should resolve to deterministic. In your continuous adaptation, the appropriate analogue of upstream discrete argmax is the continuous policy's deterministic mode/mean.

I would update the source-derived identity to something conceptually equivalent to:

```text
CTRL native = mode
IDAAC native = sample
PPG native = sample
IBAC-SNI native = sample
```

with the PPG qualification documented separately.

Do not remove the explicit `--policy-mode mode` facility. It remains valuable because IDAAC, IBAC and PPG then have a common deterministic sensitivity estimator. For CTRL, that secondary estimator simply coincides with native.

I would also fix the current CTRL comment while touching `eval_grid.py`: it presently argues for sampling because the training reporting path sampled. That is the wrong provenance criterion given your decision to reproduce actual evaluation-time convention.

PPG's comment should also become more precise in the same edit, because `eval_grid.py` will already be changing and therefore its hash is already invalidated. Something like:

> OpenAI's release contains no dedicated evaluation runner. Native sampling follows the only released `PpoModel.act()` convention; it is not claimed to be independently verified evaluation-time behavior.

After that commit, stop editing evaluator code unless a test exposes an actual defect. In particular, don't do later comment-cleanup passes in `eval_grid.py`: comment bytes still alter a whole-file evaluator hash.

## The bare-V100 wrapper has two genuine P0 interface bugs

This is not a comment disagreement. The executable code is inconsistent.

`run_on_production_host.sh` currently defines its third argument as the RL-ViGen source archive:

```text
$3 = rlvigen-door2-90d8b8c4.tgz
```

It copies it to `/work/rlvigen.tgz` and appends that filename to the positional argument vector.

But `run_probe.sh` defines:

```text
$1 = code
$2 = result
$3 = asset_archive
```

and `$3` is the Places365 asset.

RL-ViGen source acquisition is independent of that positional argument. It checks:

```text
RLVIGEN_ARCHIVE
```

instead.

The host wrapper currently does not set that environment variable.

So the wrapper has misunderstood the interface it claims to mirror.

I would make the boundary explicit rather than clever. Conceptually the host wrapper needs two distinct inputs:

```text
RL-ViGen pristine source archive
Places365 external dataset/archive
```

They must never share a positional slot.

The minimum compatible correction would be:

```text
arg3 = RL-ViGen archive
arg4 = Places archive, when needed
```

Then the wrapper should mount/copy arg3 and export:

```text
RLVIGEN_ARCHIVE=/work/rlvigen.tgz
```

while only arg4 becomes `run_probe.sh`'s third positional argument.

An even cleaner production-host design would be to keep the full Places train set already extracted on the host and bind-mount it read-only. That avoids unpacking ~21 GB for every production container. For example, conceptually:

```text
PLACES365_ROOT_HOST=/data/places
       ↓ bind mount
/datasets/places365
       ↓
NATIVE_PLACES365_ROOT=/datasets/places365
```

DataSphere can retain its archive-based input path for bounded probes.

I would favor this if it can be added cleanly without making `run_probe.sh` bifurcate into two unrelated implementations. The host's persistent dataset is the natural way to use a 21 GB external dependency.

### GPU packing

The second wrapper bug is simpler.

`run_probe.sh` already implements:

```text
NATIVE_CELL_DEVICES=0,1
```

and wraps each concurrent cell in the corresponding `CUDA_VISIBLE_DEVICES`.

But the host wrapper's explicit environment allowlist does not forward `NATIVE_CELL_DEVICES`.

So the code containing the packing solution never receives its configuration.

Add it to the allowlist.

Keep the distinction between:

```text
DOCKER_GPUS
```

which controls which physical GPUs the whole container can see, and:

```text
NATIVE_CELL_DEVICES
```

which assigns visible devices among cells inside that container.

For a single cell you can expose exactly one physical GPU at Docker level. For a deliberately packed two-cell experiment, expose the two approved GPUs and assign one logical device to each cell.

Do not infer from an old note that GPU 0 is still occupied. Recheck `nvidia-smi` at run time.

## Fix Places365 as one coherent path

The scientific decision is now good: production should use Places365 train.

The public dataset setup is also substantially good:

`setup/fetch_overlay_dataset.sh` defaults to `train`, downloads `places365standard_easyformat.tar`, extracts with `tar -xf`, and expects:

```text
places365_standard/
    train/
    val/
```

`setup/verify_datasets.py` separately checks train and requires 365 class directories.

Those pieces should stay.

`run_probe.sh` is where the old val architecture remains embedded.

In the uploaded artifact it still:

```text
asset_dir="$work/places365-val"
tar ... -xzf ...
asset_images="$asset_dir/val/images"
```

and validates that val-shaped input before deciding whether `places_split=train`.

Then for train it assumes:

```text
$asset_dir/train
```

whereas canonical easyformat extraction is:

```text
$asset_dir/places365_standard/train
```

Most decisively, after configuring the loader for `places_split`, it unconditionally checks that the loader root equals:

```text
$dataset_root/places365_standard/val
```

That makes the final assertion contradict the intended train configuration.

I would rewrite this block around one resolved partition path rather than progressively patching val assumptions.

Conceptually:

```text
places_split = train | val
dataset_root = canonical root
partition = dataset_root/places365_standard/$places_split

verify partition
configure both loaders for $places_split
load one batch
assert actual loader root == partition
```

For the full easyformat train archive, use the archive's real root rather than creating alternate symlink layouts unless needed for backward-compatible probe assets.

Also use an extraction operation that handles the actual archive supplied. The canonical easyformat asset is `.tar`; hardcoding `tar -xzf` assumes gzip. `tar -xf` is the appropriate canonical path for that file.

The tiny v195 train-attestation archive can remain a specialized diagnostic fixture, but label it correctly: **train loader-path attestation**, not production Places365 dataset certification.

The full production dataset should separately pass:

```bash
python setup/verify_datasets.py --split train
```

against 365 class directories before any of SVEA/SGQN/SODA starts.

### Don't rename everything right now

`configure_places365_val.py` is now awkwardly named and its top docstring still says validation-only even though its implementation supports `--split train`.

I would fix misleading prose if it is outside an expensive identity boundary, but I would not rename the file immediately before final certification unless there is a genuine usability benefit. A rename creates unnecessary references to update. Functional correctness matters more.

## Then freeze evaluator closure once

After the CTRL change, update whatever current tests/gates bind evaluation policy mode. In particular, don't allow the following failure mode again:

```text
eval_grid.py says sample
evaluator_identity.py says sample
=> internal consistency gate passes
```

while upstream evaluation is deterministic.

You need one source-derived invariant, whether encoded in a small test, a provenance table, or an immutable expectations map.

It does not need to become a huge new framework. Something as simple as a test asserting:

```text
family_eval_policy_mode("ctrl") == "mode"
```

with provenance documentation pointing to `ctrl_public/evaluate_ppo.py` is enough.

Then calculate the final evaluator revisions and begin a fresh seven-family attestation wave.

I would explicitly mark earlier v194/v195 records as something like:

```text
PRE_FIX_DIAGNOSTIC
```

rather than deleting useful execution evidence, but they should never satisfy the final-current-attestation gate.

## GitHub/source reconstruction is a separate lane

The Luna work here is much better than it first appeared.

One thing I would correct from the earlier handoff: `SOURCE-BOOTSTRAP.md` describes a “known gap” where shipped snapshot repositories fail because their locally minted commit SHA is not the upstream commit. But the current `bootstrap_sources.py` in this artifact already contains logic addressing exactly that case.

Its verifier accepts a snapshot when its committed Git **tree** equals the pristine upstream tree even if its commit ID differs:

```python
if head != entry["commit"] and tree != entry["tree"]:
    ...
if tree != entry["tree"]:
    ...
```

It then separately verifies the normalized post-patch working-tree hash.

That is a fairly sensible construction:

```text
Git HEAD/tree → provenance of pristine base
working-tree normalized hash → adapted project source closure
```

So I would **not** immediately redesign verifier semantics based on the stale "Known gap" prose. First run it against the actual current shipped snapshots. The documentation may simply be behind the code.

There is, however, one real implementation defect: `bootstrap(root=...)` pretends to support an alternate project root but repeatedly uses module-global `ROOT` internally for destinations, patch paths, case sensitivity, and verification.

That is why one of Luna's disposable safety probes accidentally targeted the real project.

Either make `root` genuinely authoritative throughout, or remove the misleading parameter. I prefer making it real, because isolated clean-clone tests are valuable.

The test suite for reconstruction is also thin. It currently proves the manifest, pin projection, normalized hashing, basic case-sensitive detection, exact-clone wrong-commit rejection, patch hash rejection, and publish refusal. Before public release I would add focused fixture tests for partial existing trees, modified existing trees, missing/modified closure files, IDAAC auxiliary absence, ALDA relocation absence, byte identity of both PINS files, and actual RL-ViGen case-insensitive refusal.

No need for those tests to hit GitHub.

### `install.sh` still creates two competing onboarding paths

This is the other meaningful GitHub usability issue.

The new public contract says:

```bash
python setup/bootstrap_sources.py
python setup/verify_sources.py
```

but `setup/install.sh` still independently:

```text
clones RL-ViGen
installs it
applies RL-ViGen patches
```

and knows nothing about DMCGB, ALDA, PPG, IDAAC, IBAC, CTRL or OpenAI Baselines.

That means a new user has two different answers to "how do I get the source?"

Converge them before publication. I would make `bootstrap_sources.py` the sole authority for obtaining/adapting source, and let `install.sh` handle Python/environment installation and runtime/environment verification.

If `install.sh` wants convenience, it can invoke bootstrap when required source trees are absent rather than implement its own RL-ViGen cloning logic.

The public flow should become approximately:

```text
source bootstrap
source verification
environment installation
external dataset provisioning if needed
dataset verification
```

The user should not need to know which of seven source families is ignored by Git.

### README needs a publication pass

The artifact's README still says:

> fetches the val split, ~2 GB rather than the 24 GB train split — a declared protocol choice

which is now false.

Fix that.

More broadly, the top-level README appears to retain substantial legacy descriptions of the unified `rlgen` harness while your actual production architecture is much more nuanced. You don't need to delete historical explanation, but put a short current quickstart near the top so a new person does not need to reverse-engineer which instructions are superseded.

The public contract should make clear that Places365 is intentionally external.

## What I would not reopen

There is a large amount of resolved work that another agent could waste days revisiting.

PPG's production rollout geometry is now 1×2048. The old 8×256 finding is obsolete.

IDAAC's old 16×256/one-stack concerns are superseded by the current continuous-control comparator geometry.

SODA's auxiliary LR issue has been repaired.

CTRL's old 16-env memory-accounting bug is repaired in the planner; the remaining issue is empirical validation of 64 envs, not another arithmetic redesign.

ALDA's source-primary setting is UTD 1.0. Do not resurrect UTD .25 because it once looked more stable.

RL-ViGen's CURL/SVEA/SGQN identities should remain explicitly benchmark-release variants rather than being "corrected" into canonical original algorithms.

IBAC is still a deliberate hybrid Door port. Do not tune it toward performance after seeing a low pilot unless there is evidence of a broken implementation.

Do not harmonize all action policies into deterministic or all into stochastic.

Do not equalize optimizer-update-per-frame ratios across methods by manually inventing new epoch/minibatch settings. Report that as a method/domain comparability seam.

Do not make Places365 part of Git or source bootstrap.

Do not expand to Lift right now.

## Host phase after the final evaluator freeze

Once the final seven-family evaluator wave is green on a truly frozen closure, move to the V100 host.

The order in the migration document is basically right, with one adjustment: make sure the wrapper fixes are already landed before using that wrapper for any supposedly evidentiary host run.

First run host preflight and inspect the actual GPUs. Confirm the pinned container digest and exact source/evaluator revision.

Then renderer parity. This remains the strongest empirical blocker because your own history showed same-checkpoint behavior differing by roughly `131.5` versus `13.85` under a renderer/platform change.

The correct control is not "can V100 render Door?" It is:

```text
same checkpoint
same final evaluator
same source
same final container
same seeds/scenes
trusted host → R_A
V100 host     → R_B
```

with platform as the intended changed factor.

Before involving the policy, I would also render a few fixed-seed observations on both hosts and compare them. Exact hashes if truly deterministic; otherwise pixel statistics/differences with carefully controlled renderer configuration. That can localize a mismatch before you blame an RL policy.

Next, measure CTRL at actual `num_envs=64`. The current ~54.28 GiB estimate is just `13.57 × 4`. JAX/XLA memory need not scale linearly, so a real peak measurement is what licenses that configuration and any packing plan.

Then IBAC's exact-final competence pilot at `procs=16`. Runnability has already been established. The outstanding question is whether the exact production configuration is functionally learning, not whether an old procs=1 configuration once did something.

Do not define competence by "must achieve a pleasing score." Predefine a modest sanity criterion around non-degenerate learning / finite losses / meaningful policy behavior. A bad but correctly functioning method is still a result.

Then run the DrQ-v2 600k canary all the way through:

```text
train
→ durable intermediate checkpoints
→ terminal checkpoint
→ package/retrieve
→ fresh-process checkpoint reload
→ full endpoint grid
→ deterministic secondary where applicable
→ curve records
→ normalization/statistics
→ delivery/eligibility classification
```

This canary is much more valuable than another 10k smoke because it tests the paths that only become relevant after hours of operation: disk, checkpoint durability, replay, packaging, reload, endpoint evaluation, and records.

Only after that would I permit the full fleet.

## A few operational refinements

The current wrapper has a good idea that should survive: mount `/tmp/native-work` and `/tmp/native-out` to host storage so checkpoints survive a container failure. Verify it with the canary rather than trusting the comments describing it.

Treat no finite low return as an automatic restart condition. Restart on process/infrastructure corruption, NaN/Inf, invalid checkpoint, renderer/source mismatch, or equivalent fail-closed conditions. Same training seed on retry.

Resume only where checkpoint state is complete enough to reproduce training state: network, optimizers, schedules, RNG, replay where relevant. Otherwise restart the same seed from frame zero.

Keep failed attempts and their evidence. Never silently replace a failed seed with another seed.

For SVEA/SGQN/SODA, verify the full Places train dataset once on the host before running them. Don't repeatedly perform a million-image integrity scan per cell.

## What I would ask the active agent to achieve before Claude returns

The best intermediate stopping point is not "everything done." It is a clean software freeze candidate.

That means the live tree has:

```text
CTRL native deterministic
PPG provenance wording accurate
evaluator identity consistent
bare-host RL-ViGen and Places inputs separated
NATIVE_CELL_DEVICES forwarded
Places train path internally coherent
source bootstrap root semantics fixed or made explicit
README/source-bootstrap docs current
no unrelated scientific settings changed
```

Then run the local/static test suite on your side, inspect the diff, and commit that as the candidate closure.

At that point Claude can return to a much simpler problem: review one candidate diff rather than continue discovering defects while jobs are running.

I would not submit another final evaluator wave until that commit exists.

### The decision boundary

If I had to reduce all of this to one rule:

**Software correctness first; one evaluator freeze second; host evidence third; production canary fourth; fleet last.**

Right now the project is still in the first stage because the uploaded artifact contains a confirmed wrong CTRL evaluation estimator and two bare-host production interface defects. Those are worth fixing even if it sacrifices the current attestation generation.

The project is much closer than the long history makes it look. Most of the difficult method-specific fidelity questions are already settled. The remaining risk is now mainly execution discipline: avoiding another cycle where a validation wave starts before the last correctness changes are actually finished.
