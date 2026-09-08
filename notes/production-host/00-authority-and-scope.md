# Authority and scope

## The machine

`cds2` is the production host for this project. `notes/remote-infra.txt` is a captured terminal
session from it: `nproc` 16, Intel Xeon Gold 6154 (8 cores/socket × 2 sockets), 125 GB total /
113 GB available RAM, 2× Tesla V100-SXM2-32GB.

The user account is most likely `varaksin_as`. Confirm rather than assume.

## What being listed in the guide does NOT mean

The Netbird guide (`01-connection.md`) enumerates several machines: `aicenter1`, `aicenteritl`,
`ccmplanner`, `cds2`, `cdsserver`, `aicenter2`, `aicenter3`.

**Being reachable is not permission to use.** Only `cds2` has been named for this work. Every other
host in that table is someone else's, and its presence in a connectivity document says nothing
about whether we may run on it. Do not connect to, probe, benchmark or "just check" any of them.

The same applies within `cds2`: a GPU that is idle is not thereby ours, a directory that is
readable is not thereby ours to read, and a container that exists is not thereby ours to touch.

**No document in this repository may ever be written to imply otherwise.** If a future note says
"the available machines are …" or "you can use …", that note is wrong and should be corrected
rather than followed.

## Authorisation is per-action, not once

Access having been granted is not a standing licence. Each new *kind* of action — a first
container, a first GPU claim, a first long run, a first large download — is its own decision, taken
by the procedure in `06-before-any-action.md`.

## When access is missing

If a command is refused, a path is unreadable, or a resource is unavailable: **stop**. Do not look
for another route, another account, another host, or a permission workaround. The absence is
information — most likely context that was not shared — and routing around it is exactly the
behaviour that gets an account suspended on a shared research machine.
