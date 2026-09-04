# DataSphere — bring-up, verified 2026-08-10

Project `bt12q57tmrs03pnt8drc`, community `bt19h0cm8nqhr7489r9o`. `gt4.1` = 1× Tesla T4, 4 vCPU,
31 GB RAM, ~$1.38/h. (`gt4i.1` is the interruptible variant.)

Everything here has run. Nothing in this directory is a plan.

## Order of operations, and why it is this order

**1. Prove the return path before spending GPU time.** `cfg-pullback.yaml` on `c1.4` (CPU) writes
a 40 MB payload plus a manifest and exits. `verify_pullback.py` then checks the sha256 computed on
the box against the bytes extracted locally.

This is not ceremony. **The first attempt reported SUCCESS while returning nothing useful** — `dd
bs=1m` is a BSD spelling GNU coreutils rejects, so the payload was never created, and the pack
guard only checked that `tar` exited 0, which it did over the three small files that existed. The
manifest came back with empty fields and the CLI said "job completed successfully". The guard
tested the wrong proposition: *did the packing command run*, not *did I return what I promised*.
Discovering that at the end of a training run is the expensive version of the same bug.

`verify_pullback.py` was checked against those known-bad artifacts first, and rejected them,
before being trusted on good ones.

**2. Probe capability, still without training.** `cfg-probe.yaml` on `gt4.1`, 453 s, ~$0.18:

| check | result |
|---|---|
| clone RL-ViGen @ pinned commit | **38 s** for 1.8 GB — cloning per job is cheap; no cached dataset needed |
| pip install (torch cu121 + our pins) | 285 s |
| `apply_patches.py`, then `--check` | four patches applied and verified *(as of that job; P5 was added later, and `--check` now diffs the whole tree)* |
| import doctor | ALL OK |
| GL gate | `GL_RENDERER = Tesla T4/PCIe/SSE2`, `software_fallback: False` |
| CUDA gate | torch 2.5.1+cu121, `cuda_available=True`, 2457 GFLOP/s |
| **protocol hash** | `b5ba34d393766d6e` — **equalled the laptop's at the time of this job**, which is the finding: remote and local compute the same hash, so their numbers pool. The value itself has since moved to `c0d7bc7c…` (env_patches gained P4 then P5); the agreement is the result, not the digits. |
| regimes | all 6 (Door/Lift × train/eval-easy/eval-hard) construct and self-report |
| throughput | train **77.9 steps/s** (12.84 ms), eval-hard **86.5 steps/s** (11.56 ms) |
| end-to-end `rlgen.evaluate` | ran against the real simulator, returned per-scene returns |

Full log: `probe-bt1jam2lnoc02iufe20b.log`. Numbers: `throughput.json`.

**3. Only then, a bounded real run.** Not done yet.

## The render answer

The image is **not custom**: stock `nvidia/cuda:12.2.2-runtime-ubuntu22.04`, plus
`apt-get install libglvnd0 libgl1 libegl1 libglew-dev libosmesa6`, plus `MUJOCO_GL=egl`.

It renders because the platform currently injects the full graphics driver stack into every
container. That injection was **absent on 2026-07-29 and present from 2026-08-01**
(`ccm-intro/docs/compute-yandex-datasphere.md` §6) — platform behaviour that has already flipped
once inside a week. It still holds on 2026-08-10.

If it reverts, the GL gate aborts at ~7 minutes rather than rendering in software for hours. The
documented alternative that *requests* graphics explicitly is
`nvidia/cudagl:11.4.2-runtime-ubuntu20.04`, but its Ubuntu 20.04 base gives Python 3.8, below what
this repo's source assumes — hence the 22.04 CUDA image plus the gate.

`libegl1` alone is not enough: without `libgl1` you get a context and no way to draw through it
(`'NoneType' object has no attribute 'glGetError'`).

## Sizing, from the measurement

At 77.9 env steps/s, **500k frames is ~1.8 h of pure env stepping** per run before any learning.
Rendering is ~12% of a step and physics ~88%, both CPU-bound — so the lever is packing several
runs per box, not a bigger GPU.

## Two gates that are worth their lines

Both earned in the sibling project (`../../gen-rebuttal/vigen-idaac/datasphere/`):

1. **GL gate** — build a robosuite env *first* (that is what establishes the EGL context), then
   read `GL_RENDERER`. A software fallback and a crashed probe are **different verdicts** and are
   reported separately; conflating them once produced a false "software rendering" diagnosis.
2. **CUDA gate** — `torch.cuda.is_available()` is *not* implied by the GL gate. The sibling
   rendered on an NVIDIA L4 while torch saw no GPU and trained ~60× slower on CPU, with every
   other check green.

## Things that will bite the next person

- **`outputs:` upload only when the job ENDS.** A job killed by a platform limit returns nothing,
  and a `trap … EXIT` does not save you — there is no end to trap. (An earlier note in this
  repo's HANDOFF claimed the sibling used such a trap; it does not, and `grep -n trap` over its
  whole `datasphere/` returns nothing.) The real mitigations are bounded jobs and a live side
  channel — the sibling pushed checkpoints to W&B mid-run via `CKPT_TO_WANDB=1`.
- **`download-files` silently skips anything past a client-side 1 GiB total and still exits 0.**
  Use the sibling's `ds_pull.py`, which raises the cap and then verifies each expected file.
- **The balance endpoint is unreliable** — `unitBalance` returned `{}` here and `5000000`
  (unchanged through 33 minutes of real T4 time) in the sibling. Estimate spend from
  `finished_at − created_at` instead.
- **Job overhead is ~2 min** wall for a 2 s job: ~43 s to the first line, ~60 s from exit to
  artifacts. Do not benchmark anything shorter than that.
- **Every env teardown logs `EGLError(EGL_NOT_INITIALIZED)`** from `MjRenderContext.__del__`.
  These are "Exception ignored in" garbage-collection messages after the work is done, not
  failures. They make a healthy log look alarming.
- **Our robosuite pin is mujoco 2.3.7, the sibling's is 2.3.0.** Ours is load-bearing: 3.x breaks
  every eval mode. Do not copy their pin.
- **We cannot use the sibling's pip-robosuite-plus-overlay shortcut.** `requirements.txt` records
  that PyPI robosuite differs from RL-ViGen's fork in 761 files, with `Custom01..Custom40`
  resolved through XML only the fork carries. The box clones and installs the fork editable,
  exactly as `setup/install.sh` does.

## Secrets

No key is committed here, and none should be. The W&B key lives at `ccm-intro/secrets/` and must
reach a job as an **input file**, never as a config value or a command-line argument — otherwise
it lands in the job yaml and in `ps`.
