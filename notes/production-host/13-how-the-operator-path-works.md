# What the operator path actually does — and what is wasteful about it

Read from `datasphere/native/run_on_production_host.sh` and `run_probe.sh`, not inferred.

## The flow, exactly

1. **A repo checkout must exist on the host — and a `git clone` alone is NOT one.**

   [Claude 2026-09-08, verified on the host] `git ls-files runnable/alda` returns **zero**. So do
   `ctrl`, `idaac`, `ppg`, `ibac_sni`, `dmc_gb` — and `RL-ViGen-upstream` is gitignored too. The
   repository is 1180 tracked files and ~156 MB; the seven baseline trees it *runs* are ~860 MB
   that live in none of them. A clone gives you the harness and none of the code under test, and
   nothing in the clone says so.

   The reconstruction step is `python3 setup/bootstrap_sources.py`, which shallow-fetches seven
   public upstreams at pinned commits, hash-verifies each patch, applies them, and hashes the
   materialized tree against `setup/source-reconstruction.json`. It refuses to overwrite an
   existing destination, so it is safe to re-run but will not repair a half-finished tree — remove
   the partial destination first, deliberately.

   Order on a fresh host, all of it from inside a container against a volume in our own home:

   ```
   git clone https://github.com/Arsenii324/many-gens-rl-vigen.git repo   # ~156 MB
   cd repo && python3 setup/bootstrap_sources.py                        # ~860 MB more
   python3 setup/verify_sources.py
   ```

   `bootstrap_sources.py` requires a **case-sensitive filesystem** for RL-ViGen (upstream ships
   both `cfgs/task/TwoArmHandover.yaml` and `TwoArmHandOver.yaml`). cds2's ext4 satisfies it; a
   macOS working copy does not, which is why the Linux reconstruction proof could only ever be
   closed on the host.

6. **The wrapper contains no `cd`** and reads
   `datasphere/native/source-lock.json` and `datasphere/native/family.py` by *relative path*, so it
   has to be invoked from the repository root on `cds2`. This is true regardless of how the payload
   arrives.
2. It takes a **payload tarball** as argv 1 (`code.tgz`), plus optional RL-ViGen and Places365
   archives as argv 3 and 4.
3. Stages the archives in a directory **beside `$RESULT`** (`NATIVE_WORKDIR_PARENT` overrides),
   under an `EXIT` trap that removes it, and mounts it at `/work`. This was `mktemp -d` — i.e.
   `/tmp` — until 2026-09-08; the problem was not `/tmp` as such but that `check_disk` validated
   `$NATIVE_WORK_HOST_DIR` and *nothing else*, so the mount taking the single largest write was
   never checked. It is now checked, and a `tmpfs`/`ramfs` staging directory is refused outright.
4. `docker run --rm ... "$IMAGE" bash -c 'apt-get install python3 python3-pip git; tar xzf
   code.tgz; bash datasphere/native/run_probe.sh ...'`
5. `run_probe.sh`, **inside** the container, runs a *second* `apt-get install` (11 packages:
   libglvnd0, libgl1, libegl1, libglew-dev, libosmesa6, …) and `pip install -r requirements`,
   **including torch**.
6. The container exits and `--rm` deletes it. `result.tgz` is copied out to `$RESULT`. The workdir
   is removed by the trap.

## So: the environment is rebuilt from scratch on every cell

Nothing persists between runs except the image and the checkout. Every cell pays:

- two `apt-get install` passes,
- a full `pip install` including torch,
- and writes all of it into a fresh container layer under `/var/lib/docker` — **on the shared `/`**.

That is the ~600 s bootstrap seen on every DataSphere job, and it is **36 times** across the
campaign.

**It is inherited, not designed.** On DataSphere every job got a fresh VM, so rebuilding was the
only option. On a persistent host it is waste: repeated multi-GB downloads and repeated writes to a
shared filesystem, for an environment that does not change between cells.

## The fix is already an open gate

`gate_environment_manifest` reads OWNER because *"the job still runs apt-get/pip inside it, so the
EXECUTED environment is not frozen and two jobs from this digest can differ."* Its stated closure
is **a baked final image with no runtime package mutation**.

Baking that image solves four things at once:

| | |
|---|---|
| the gate | the executed environment becomes frozen by construction |
| disk | one image, once — instead of a container layer full of packages per cell |
| time | container start is immediate; ~600 s × 36 disappears |
| reproducibility | every cell runs bit-identical dependencies, provably |

**This, not the payload mechanism, is the change worth making before the campaign.**

## Where the payload fits, and why it is not the thing to replace

`code.tgz` is ~250 KB and carries the family's code. Its value is not transport — it is that
`contract.py verify-payload` and `verify-evaluator-binding` tie a returned record to a **specific
tree**, which is what makes an attestation mean anything.

## Cloning inside the container: viable now, with one condition

The repository is **public** as of 2026-09-08, so a clone needs no credentials on the host — which
removes the objection that mattered (putting credentials there would be configuring the host).

It still does not remove the need for a checkout to launch from, and a bare `git clone` of a branch
has no binding between the code and the record. **A clone pinned to an exact commit does**, and
that is the design to write if the payload path is ever replaced: pin the commit, record it in the
run manifest, and have the evaluator-identity check run against the cloned tree exactly as it does
against an extracted payload.

Until that exists, the payload path stays, because it is the one whose records can be attested.
