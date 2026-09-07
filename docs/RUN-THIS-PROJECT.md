# Run this project

From `git clone` to a submitted production run, in order. Each step says what proves it worked.

This replaces knowing which of ~30 documents in `notes/` to read. Where a step has a caveat that
would otherwise look like a failure, it is stated at that step rather than left to be discovered.

**What this repository is.** Twelve published RL generalization baselines, each at its authors' own
settings, trained and evaluated on one task (robosuite Door) through one shared evaluator, so that
their generalization numbers can be compared. `docs/RESEARCH-FRAME.md` states the claim;
`docs/EVAL-PROTOCOL.md` states the measurement protocol.

**What it deliberately does not carry.** The twelve upstream repositories, the Places365 overlay
dataset, checkpoints, results and payload archives are all absent from git. Steps 1 and 3 below
reconstruct or provision them. That is why a fresh clone is small.

---

## 0. Requirements

| | |
|---|---|
| OS | **Linux** for the full path. macOS can do everything except reconstruct RL-ViGen — see step 1. |
| Python | 3.10 (the container pins it; `datasphere/native/source-lock.json` records the image) |
| GPU | Not needed to reconstruct or verify. Needed to run cells. |
| Disk | ~4 GB for sources; ~25 GB more if you provision the Places365 train split |

---

## 1. Reconstruct the pinned sources

```bash
python3 setup/bootstrap_sources.py      # clone each upstream at its pin, apply this project's patch
python3 setup/verify_sources.py         # re-derive and check, offline
```

`setup/source-reconstruction.json` is the manifest: per family, the upstream URL, the exact commit
and tree, the patch and its hash, and the paths excluded from the closure hash.

**Proves it worked:** `verify_sources.py` prints `source reconstruction verified`.

**On macOS it will also print** `NOT VERIFIED HERE: rlvigen ...`. That is correct and expected, not
a failure: upstream RL-ViGen contains both `cfgs/task/TwoArmHandover.yaml` and
`cfgs/task/TwoArmHandOver.yaml`, which a case-insensitive filesystem cannot both materialize. The
other six families verify normally. **This one step is unproven on Linux by us** — we had no
case-sensitive host — so it is the single external proof this repository still owes.

Per family: `python3 setup/bootstrap_sources.py --family idaac`.

Reconstruction never overwrites: a destination that already exists is verified and kept, and a
partial or modified one is refused.

## 2. Build the environment

```bash
bash setup/install.sh                   # into ./.venv, or VENV=/path bash setup/install.sh
```

Environment only. It no longer acquires source — step 1 is the sole authority for that — and it
refuses to build on an RL-ViGen tree that does not match its manifest.

**Proves it worked:** the script ends with its own `6/6 VERIFY` block, which builds a real
environment in every mode and fails if any does not report the mode it was asked for.

## 3. Provision Places365 (only for `svea`, `sgqn`, `soda`)

The overlay distribution IS the augmentation mechanism for those three, so it is a
learning-affecting input, and the decided production value is the upstream **train** split
(`notes/DECISION-SHEET.md` A22).

```bash
bash setup/fetch_overlay_dataset.sh          # ~24 GB, train split, into ./data
python3 setup/verify_datasets.py --split train
```

**Proves it worked:** `dataset usable: PASS` with `class directories: 365`.

The other nine baselines need none of this, and a clone with no Places365 is still a correctly
reconstructed clone — `verify_sources.py` and `verify_datasets.py` are deliberately separate
commands for that reason.

`bash setup/fetch_overlay_dataset.sh data val` fetches the ~2 GB validation split instead, which is
enough for a functional probe and is **not** admissible for production.

## 4. Build a payload and check it

A payload is the code archive a run executes. It is built from the working tree and carries the
evaluator identity.

```bash
python3 datasphere/native/contract.py build-payload --family idaac --out payload.tgz
python3 datasphere/native/contract.py verify-payload --payload payload.tgz --require-evaluator-identity
python3 datasphere/native/contract.py verify-evaluator-binding --payload payload.tgz
```

**Proves it worked:** both verify commands exit 0, and the second prints the `evaluator_revision`
the payload will stamp into every record it produces.

## 5. Submit a run

Two routes. **Pick the one that matches your compute**; they are not alternatives to each other for
the same host.

### 5a. Your own Linux host with Docker and a GPU — the portable route

This is the route to use if you have a machine, and it needs no account anywhere:

```bash
CELLS=drqv2:1 FRAMES=10000 TASK=Door SEED=1 \
NATIVE_HOST_PROFILE=<your-profile> \
ENDPOINT_EVAL=1 ENDPOINT_EVAL_REGIMES=train,eval-easy ENDPOINT_EVAL_SCENES=0 \
  bash datasphere/native/run_on_production_host.sh \
    payload.tgz result.tgz rlvigen-door2-90d8b8c4.tgz [places365.tgz]
```

Argument order is `PAYLOAD RESULT [RLVIGEN] [PLACES365]`. Read
`notes/RUNNING-ON-PRODUCTION-HOST.md` before a production-length cell: it covers detaching,
packing, GPU pinning and the arrival checklist, and `datasphere/native/preflight_production_host.sh`
runs eight mechanical host checks that must all pass first.

**Proves it worked:** `result.tgz` and `records.jsonl` land on the host, and the log carries
`NATIVE_CELL_COMPLETED` for every requested cell.

### 5b. Yandex DataSphere — the route this project used

`datasphere/native/job.sh` wraps `datasphere project job execute`, with admission checks
(tier, memory, payload compatibility, container digest) run before anything uploads.

```bash
DATASPHERE_PROJECT=<your-project-id> bash datasphere/native/job.sh submit <config>.yaml
```

The project ID defaults to ours, which you cannot submit to — set `DATASPHERE_PROJECT`. The
`cfg-*.yaml` files in `datasphere/native/` are the worked examples; copy the closest one.

## 6. Know whether you are allowed to launch

```bash
python3 scripts/production_gates.py
```

Prints every gate as PASS / FAIL / OWNER and ends with a launchability verdict. FAIL means a
mechanical defect; OWNER means a decision that is recorded but deliberately not closed in code, so
that it stays visible if production goes wrong. `notes/DECISION-SHEET.md` carries the reasoning for
each, and `notes/DECISIONS-IF-PRODUCTION-GOES-WRONG.md` says which symptom would indict which
judgement.

```bash
python3 -m pytest tests/ -q     # the full static suite
python3 scripts/requirements.py # whether the research requirements are met, and where they are not
```

---

## Where to look when something is wrong

| Question | File |
|---|---|
| What is the measurement protocol? | `docs/EVAL-PROTOCOL.md` |
| What is claimed, and how strongly? | `docs/RESEARCH-FRAME.md`, `notes/CLAIMS-LEDGER.md` |
| Why is this baseline configured this way? | `notes/DECISION-SHEET.md` |
| Are the twelve actually comparable? | `notes/SAME-AXES-VERDICT.md`, `scripts/audit_comparability_seam.py` |
| How do I run on a bare host? | `notes/RUNNING-ON-PRODUCTION-HOST.md` |
| What did we change in each upstream, and why? | `runnable/_patches/*.patch`, `scripts/deviations.py` |
| What is still unproven? | `notes/HANDOFF.md` |
