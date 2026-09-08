# Absolute prohibitions

These have no exception path. There is no debugging situation, no "just this once", and no
temporary state in which any of them becomes acceptable. If one of them looks necessary, the
correct action is to **stop and report**, not to weigh it.

## Never change the host system

- No `apt-get` / `apt` install, remove, update, upgrade or `dist-upgrade`
- No `brew` anything
- No `pip` / `pip3` / `conda` / `mamba` install or update **outside a container**
- No `npm`, `cargo`, `gem`, or any other package manager
- No editing of system configuration, `/etc`, systemd units, shell profiles, or environment files
- No changes to Python, CUDA, cuDNN, or any shared library or toolchain
- **No driver changes of any kind.** Not an update, not a reinstall, not a module reload

The host's environment is shared and someone else's work depends on its exact state. A library
version bump that is invisible to us can silently change another person's results, or break a job
that has been running for two days.

## Never touch what is not ours

- No stopping, killing or signalling processes we did not start
- No modifying, moving or deleting files outside our own directory
- No writing into shared or global locations
- No `docker rm` / `docker rmi` / `docker prune` on anything we did not demonstrably create
  (see `03-docker-discipline.md` for what "demonstrably" requires)

## Never work around a refusal

If something is denied — a permission, a device, a path, a quota — that is the end of the attempt.
`sudo` is not a tool here. Neither is another account, another host, or a different route to the
same resource. The refusal probably encodes context that was not shared.

## Never guess before a destructive or irreversible step

Deleting, overwriting, moving, killing, or reconfiguring anything requires **reading the actual
current state first**, with our own eyes, in that moment. Not memory of it, not an assumption from
how the code usually behaves, not "it should be the tmp dir". A tight loop or a throwaway step is a
reason for more rigour, not less.
