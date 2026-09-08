# What the operator path actually does — and what is wasteful about it

Read from `datasphere/native/run_on_production_host.sh` and `run_probe.sh`, not inferred.

## The flow, exactly

1. **A repo checkout must exist on the host.** The wrapper contains **no `cd`** and reads
   `datasphere/native/source-lock.json` and `datasphere/native/family.py` by *relative path*, so it
   has to be invoked from the repository root on `cds2`. This is true regardless of how the payload
   arrives.
2. It takes a **payload tarball** as argv 1 (`code.tgz`), plus optional RL-ViGen and Places365
   archives as argv 3 and 4.
3. `WORKDIR="$(mktemp -d)"`, `trap 'rm -rf "$WORKDIR"' EXIT`, copies those archives in, and mounts
   the directory at `/work`.
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
