# 19 — The environment and the run are different lifecycles

**2026-09-08.** Everything fixed on this host today — watch budgets sized for a two-hour bootstrap,
a reaper for a hung `pip`, a persistent wheel cache — is an accommodation to one structural mistake,
not a fix for it. This note names the mistake and designs the replacement.

## The mistake

Every cell rebuilds, from scratch, an environment that is identical across cells. Measured on this
run:

| phase | cost |
|---|---|
| `apt-get` | **71 s** (17:14:24 → 17:15:35) |
| `pip install` | **> 2 hours**, 1710 MB across 32 wheels, 0 retries, 0 resolver backtracking |
| training, 10k frames | minutes |

So a short cell is ~95% bootstrap. And none of it survives: the container is `--rm`, `--no-cache-dir`
is set, and the only mounts are results and the sentinel directory. The host's `~/.cache/pip` does
not exist. **The next cell re-downloads all 1710 MB**, and so does the one after — seven attestation
families and twelve baselines, every time.

`apt` is 71 seconds and is not the problem. `pip` is the whole problem. That single measurement
decides the design below, because it rules out the heavier fixes.

## What the design is constrained by, measured rather than assumed

1. **There are exactly TWO distinct requirement sets**, not seven and not twelve. Eleven baselines
   hash to one set; `ctrl` alone hashes to another, because it is JAX and strips `torch`
   (jax[cuda12]'s cuDNN 9 and torch's pinned 8.9.2.26 have no common version). Note 14 proposed
   "one venv per family, which is the natural shape anyway" — the natural shape is two.
2. **No family adds pip packages of its own.** `family.py pip-requirements` is empty for every
   family checked, so the two sets are the entire story.
3. **There are exactly two editable installs**, `--no-deps -e` of
   `RL-ViGen-upstream/third_party/robosuite` and `envs/robosuiteVGB`, from the payload's own tree.
4. **The payload extracts to `/tmp/native-work`, which is a bind mount.** The host directory behind
   it is randomised per run; the *container* path is identical on every run. This is the fact that
   makes the whole design work, and it is why point 3 is not fatal.
5. The base image is already digest-pinned:
   `nvidia/cuda:12.2.2-runtime-ubuntu22.04@sha256:94c1577b2cd9dd6c0312dc04dff9cb2fdce2b268018abc3d7c2dbcacf1155000`.

## The design: two prebuilt venvs on a host bind mount, built once from inside the pinned image

```
~/rlvigen-env/
  torch-<reqhash8>-<imgdigest12>/   ← 11 baselines      mounted :ro at /opt/rlvigen-env
  jax-<reqhash8>-<imgdigest12>/     ← ctrl              mounted :ro at /opt/rlvigen-env
```

Each directory holds a venv plus `ENVIRONMENT.json` (requirements hash, base image digest,
`resolved_packages`, build timestamp). At run time the cell mounts one **read-only**, activates it,
and skips `pip` entirely.

The venv is built **at the same container path it is later mounted at** (`/opt/rlvigen-env`), because
a venv's `bin/python` shebang and its `pyvenv.cfg` carry absolute paths. Build path and run path must
be the same string or the venv is subtly broken.

### Why not a baked image

`apt` is 71 s, so an image buys almost nothing beyond what the venv already gives. Against that: an
image lives in the shared `docker images` namespace on a machine we do not own, the build writes
layers to the same 99%-full filesystem, and two requirement sets means two images plus the base.
The venv is plain files in our own `$HOME` — deletable with `rm -rf`, invisible to everyone else.

### Why not `docker commit`

Rejected on provenance, not on cost. A commit's contents come from live mutations in a running
container and cannot be regenerated from anything checked in. It would trade `gate_environment_
manifest`'s current hole for a worse one.

## The four hard parts, and how each resolves

**1. The editable installs, which are what a read-only shared venv would normally die on.**
`pip install -e` writes an absolute path into site-packages. It cannot be run against a `:ro` venv,
and the path has to be right. It resolves because the path is *stable*:
`/tmp/native-work/RL-ViGen-upstream/...` on every run. So the two editable installs are baked in at
BUILD time, and at run time the bind mount supplies that run's own tree behind the same path. The
venv holds the pointer; the payload holds the code.

This must be verified at both ends rather than assumed: at build time, that the editable finder's
mapping is exactly that path; at run time, that the path exists **before the first import**.
Otherwise the failure surfaces as an `ImportError` deep inside a GPU call, which is the worst place
to learn about a mount.

**2. Silent staleness.** A venv built under one base image and run under another is wrong in ways
that do not announce themselves. So `ENVIRONMENT.json` records the base image digest and the
requirements hash, the directory name encodes both, and the runner **refuses** when the mounted
venv's recorded digest does not match the image it is running in.

The refusal must not fall back to `pip`. A silent fallback would restore the two-hour bootstrap
invisibly, and the only symptom would be the bill. Same discipline as `RUNNER_CONTRACT`: two homes,
and drift is fatal rather than absorbed.

**3. Does this actually close `gate_environment_manifest`?** Partly, and the note must say which
part. Mounted `:ro`, the run *cannot* mutate its environment, so the pip half is frozen by
construction rather than by intention, and `audit_environment_drift.py` should then find zero
within-family drift because zero is the only thing it can find. **`apt` still runs at run time**,
installing system libraries. That hole is smaller and differently shaped, and claiming full closure
would be exactly the overstatement this project keeps catching.

**4. Packing.** Two cells on one host share the venv read-only, with no write contention — and this
removes today's situation where two packed containers each install their own 3 GB.

## Disk, computed

| | now | with venvs |
|---|---|---|
| per running container | ~3 GB, discarded | ~0 |
| permanent | 0 | ~6 GB (two venvs) |
| N concurrent cells | N × 3 GB | ~6 GB flat |

317 GB free, so 6 GB is 1.9% — and it is disk-*negative* from two concurrent cells onward. The
one-time build downloads the same bytes this run is already paying.

## What this does to today's patches

- The wheel cache (`NATIVE_PIP_CACHE_HOST`) stops mattering on the normal path, and should be
  **kept anyway**: the venv *build* uses it, so a rebuild after a requirements change is fast. It
  was the right mechanism at the wrong layer.
- `NATIVE_BOOTSTRAP_ALLOWANCE_SECONDS` drops from 9000 to a few hundred, so the watch budgets and
  the reaper window shrink to something proportionate.
- `--must-cover-seconds` stays. It is correct regardless of how long bootstrap takes; that is the
  point of it.
- The `cell-active` retraction added today for a false-alarm reason also solves detachment: with
  `--stop-when-inactive`, an SSH drop no longer strands the watchers, because they stand down when
  the cell says it is finished rather than when the launching script says so.

## Migration, ordered so nothing is trusted before it is proven

1. Build the torch venv once from the pinned image into `~/rlvigen-env/`, capturing
   `ENVIRONMENT.json`.
2. Run one cell against it and compare its `resolved_packages.json` **byte for byte** against a
   current-style run's. A difference means the venv is not the environment we have been testing,
   and that is a finding rather than a rounding.
3. Only then wire the digest refusal and make the venv the default path.
4. Build the jax venv for `ctrl` the same way, and check `check-co-schedulable` still refuses to
   pack the two stacks together.
5. Re-measure bootstrap and set the allowance from evidence.

## Implemented, 2026-09-08

| piece | file |
|---|---|
| the builder | `datasphere/native/build-env.sh` |
| activation + refusals | `datasphere/native/run_probe.sh` (`NATIVE_VENV`), contract **19** |
| read-only mount, digest forwarding | `datasphere/native/run_on_production_host.sh` (`NATIVE_VENV_HOST`) |
| budget collapse 13500s → 5100s | `datasphere/native/launch-card-cell.sh` |
| tests | `tests/test_prebuilt_venv_refuses_rather_than_falls_back.py` |

Five refusals, every one executed in the tests rather than pattern-matched, and every one checked to
exit **without reaching pip**: no `ENVIRONMENT.json`; no interpreter; `NATIVE_IMAGE_DIGEST` not
forwarded (unverifiable is not fine); image digest mismatch; requirement-set mismatch. The
no-fallback property is the one that matters and it is mutation-tested — replacing the image-mismatch
`exit 3` with a quiet `unset NATIVE_VENV` makes the suite fail.

**Adoption is the owner's call** — note 14 flagged that this changes how every cell runs, and that
is still true. What is no longer open is whether it works or what it would cost; the decision is
now only whether to switch.

Nothing here has been run on the host yet. The migration order above is deliberate: step 2 compares
`resolved_packages.json` byte for byte against a pip-built run BEFORE the venv becomes the default,
because a prebuilt environment that differs from the one every result so far was produced in is a
finding, not a speedup.
