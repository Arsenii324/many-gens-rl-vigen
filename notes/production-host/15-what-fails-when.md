# What fails when — the abort ladder from invocation to the first gradient step

Read this before deciding whether a bring-up step is cheap. "Does it fail fast?" has a precise
answer here, and the answer differs by two orders of magnitude depending on *which* thing is
wrong. Verified 2026-09-08 by reading `run_on_production_host.sh`, `run_probe.sh`, `family.py`,
`contract.py` and `runnable/_launch/*.sh` in full; line numbers are from that reading.

## Stage A — host side, before `docker run` (seconds, no GPU touched)

| check | file:line | fails with |
|---|---|---|
| `container_image` read from `source-lock.json` | `run_on_production_host.sh:97` | `set -e` |
| positional args present | `:99-100` | `set -e` |
| payload / RL-ViGen / Places365 archives exist | `:112-116` | `exit 2` |
| at ≥600k: `NATIVE_PRODUCTION`, `NATIVE_HOST_PROFILE`, `CELL_TIMEOUT_SECONDS` all set | `:122-147` | `exit 3` |
| `NATIVE_RESULT_MIRROR` set, and on a *different* device | `:161-207` | `exit 3` |
| staging directory not on `tmpfs`/`ramfs` | `:267-281` | `exit 4` |
| free disk ≥ `family.py disk-requirement`, on **both** the staging dir and the work dir | `:228-249`, called twice | `exit 4` |
| `EXTRA_MOUNT_*` files exist | `:363` | `exit 2` |

`NATIVE_HOST_DRY_RUN=1` stops here deliberately, after every guard, printing the exact mounts, env
and argv. **This is the whole of Stage A for free**, and it is the correct first step of any
bring-up: it proves the configuration without starting a container or touching a GPU.

## Stage B — in the container, before the expensive build (~30 s)

`run_probe.sh:791` calls `require_production_configuration` **before any `mkdir`, before any
`apt-get`** — so the production-scale knob refusals fire again inside the container, cheaply, for
a caller that bypassed the wrapper.

## Stage C — after payload extraction, still before `pip install` (~10 s)

The valuable band. All of these run at `run_probe.sh:1111-1230`, ahead of
`pip install --upgrade pip`:

- `SAVE_EVERY` vs `SAVE_EVERY_FRAMES` conflict → `exit 3`
- `contract.py verify-payload --require-runner-contract 14 --require-families … --require-evaluator-identity`
- `family.py check-budget` — refuses a frame budget below the family's floor
- `family.py check-co-schedulable` — refuses families that cannot share one environment
- `family.py check-memory` — **see the box below**

## Stage D — the ~600 s build

`apt-get`, `pip install -r requirements-for-this-job.txt`, excluded-requirement verification,
RL-ViGen provision (sha256-checked archive, or a 3-retry clone), `apply_patches.py`,
`verify-evaluator-binding`, `verify-robosuite-closure`.

A **per-family** apt/pip failure here is deliberately *not* fatal to the job
(`run_probe.sh:1264-1284`): it adds the family to `DEPENDENCY_BLOCKED`, and only that family's
cells fail (`:287-292`), with `NATIVE_IMPORT_GATE_SKIPPED` on stderr. The job still exits
non-zero. One family's broken dependency must not destroy another family's calibration in the
same job.

## Stage E — built, not yet training (~60 s)

RL-ViGen import check; GPU presence probe; **EGL software-renderer refusal** (llvmpipe/softpipe/
swiftshader are rejected — a soft renderer produces valid-looking frames slowly and wrongly);
Places365 provisioning with a split-deviation refusal at production scale and a loader-selection
verdict gated on a marker; per-family `import_gate`; and finally `require_accelerator()` at
`run_probe.sh:1674`, "the last moment before training", a hard `exit 3` if torch/JAX sees no GPU.

## Stage F — training

`runnable/_launch/rlvigen.sh` has **no validation of its own** — it is `set -euo pipefail`,
`PYTHONPATH`/`MUJOCO_GL`, then `exec python3 train.py`. The other launchers' `exit 1` checks
(`ppg_cell.sh:66`, `ibac_sni_cell.sh:36`, `ctrl_cell.sh:28-31`) are **post-training** completion
assertions, not pre-training gates.

---

## The one that is NOT fast, and it was a real hole — fixed 2026-09-08

`family.py check-memory` is the only memory preflight this runner has. It used to be called under
`if [[ "${NATIVE_HOST_PROFILE:-}" == "v100" ]]`, i.e. gated on one literal string.

`require_production_configuration` only requires that a profile be **named**, not that the name
match the hardware. So `NATIVE_HOST_PROFILE=datasphere FRAMES=600000` on this host passed every
refusal and ran **with no memory preflight at all** — the exact configuration that refusal's own
comment calls "honest and wrong". `family.py` records the price: ctrl certified for `gt4.1` that
way, SIGKILLed at 11.07 GiB RSS, job `bt1lhobnsq5lq4766np6`. A memory mismatch is invisible until
the OOM fires, which on a 45-hour cell is hours in.

Now: the profile maps to a tier; `NATIVE_MEMORY_TIER` supplies one for any other profile; and at
production scale a profile yielding no tier **refuses** rather than skipping. Below production
scale it prints that the check did not run. The tier is not otherwise knowable inside a container
— it lives in the cfg yaml's `cloud-instance-type`, read only by
`scripts/audit_submission_configs.py`, at submit time, which the host path has no equivalent of.

| profile | frames | before | now |
|---|---|---|---|
| `v100` | 600000 | check-memory ran | check-memory runs |
| `datasphere` | 600000 | **silently skipped** | **refuses** (exit 3) |
| `datasphere` | 10000 | silently skipped | says it did not run |
| `datasphere` + `NATIVE_MEMORY_TIER=gt4i.1` | 600000 | silently skipped | check-memory runs on `gt4i.1` |

## The other slow failure is inherent, not a defect

A process that **hangs** rather than crashes can only be detected after a silence window.
`run_probe.sh:108-112` records job `bt12f5us5h120laajpme`: a Places365 DataLoader worker took
SIGABRT at ~8500 frames and the process sat there until the 7800 s cell timeout fired 105 minutes
later. The stall watchdog (`:127-160`, `CELL_STALL_SECONDS`, default 1800 s) shrinks that to ~30
minutes. It cannot shrink it to zero, and on a 45-hour cell 30 minutes of exposure is the design,
not a miss.

## Where a check silently did nothing — all closed 2026-09-08

`set -euo pipefail` aborts on a **non-zero exit**, never on a warning, so any deliberate
non-failure is a place a real problem becomes a note. These were the ones that mattered:

- `check_disk` returned 0 — the entire check skipped, with no output — when `df` failed or printed
  nothing. Now: refuses at production scale, and says plainly that nothing was verified below it.
- `check_disk` fell back to a generic 60 GB when `family.py disk-requirement` failed. 60 GB is
  ~10× idaac's real need and ~10 GiB short of soda's. Now: refuses at production scale.
- The `tmpfs` refusal's `case` had no default arm, so an unsupported `df -T` fell through in total
  silence, indistinguishable from a check that ran and passed. Now: says which it was.

The remaining `|| true`s are benign and each is commented at its site: a diagnostic print before a
real `exit 1` (`run_probe.sh:1221`), a `grep` whose match is already established (`:217`), a
checkpoint-stamp fallback (`:862`, `:976`), the result-mirror's *secondary* `records.jsonl` copy
(`run_on_production_host.sh:473` — the primary copy is fatal), and the Places365 loader verdict
(`:1598-1614`), which tolerates a C++ teardown crash *after* the comparison succeeded but still
`exit 3`s if the verification marker is absent.

---

## The reconstruction pin was wrong, and only the host could show it — 2026-09-08

`setup/bootstrap_sources.py` on cds2 failed with `source closure hash mismatch at .../rlvigen/output`.
The host was right and the pin was wrong.

| | records | `third_party/robosuite/robosuite/models/` |
|---|---:|---|
| Linux reconstruction, in a container on cds2 | **1145** | present |
| the macOS working copy the pin was computed from | 599 | **absent — 0 files** |

The 546 missing files are the arena, object and robot XML MuJoCo needs to build the Door task. The
manifest's `exclude` list drops six `models/assets/robots/*` subdirectories, not the tree, so those
files were **missing, not excluded**.

**No instrument had ever checked this pin, and that was by design rather than by accident.**
`verify_sources.py` prints `NOT VERIFIED HERE: rlvigen needs a case-sensitive filesystem` and
`gate_source_reconstruction_verifies` reports it as *pending, named not skipped*. Both behaved
correctly — this is the project's own rule that an instrument which cannot run must never read as
one that ran. The consequence is simply that the pin sat unverified until a machine existed that
could verify it, and the first one to try refused it.

**Cross-validated against an independent artifact** before repinning, rather than trusting one
Linux run: `rlvigen-door2-90d8b8c4.tgz` — the archive production has actually been running — holds
1146 files, and the Linux reconstruction agrees with it exactly but for
`cfgs/task/TwoArmHandOver.yaml` (the case-collision pair, where the archive kept the other spelling
because it too was built on macOS) and one `results` entry the manifest excludes.

So **production was never running a damaged tree**; the pin and the local working copy were the
damaged things. Repinned to `96a71cf6…` with the provenance recorded in the manifest itself,
including the instruction never to regenerate it on macOS — doing so would silently reinstate a
tree missing 546 files.

**What this says about the bring-up.** Rung 3 (container, no GPU, nothing installed) was supposed
to be a formality. It found a blocking defect in the documented provisioning path, on a filesystem
class that no local test could reach. That is the argument for the rung ladder, and it is why the
next rungs get run rather than reasoned about.
