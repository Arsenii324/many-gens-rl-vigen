# Before any action

Every host action is formulated explicitly and reasoned about **before** it is taken. Not narrated
afterwards. This applies to the first container, the first GPU claim, the first large write — and
to the small step in the middle of debugging, which is where care is usually dropped.

## The procedure

**1. State the action exactly.** The literal command, with every flag and path resolved. Not "run
the cell" — the actual argv, including which GPU, which directories, which limits.

**2. State what it touches.** Which host paths are written, which are mounted and whether
read-only, which devices are claimed, what is downloaded and how large, what is installed and
where.

**3. Walk the concern list.** These are mandatory to consider, and the list is a floor, not a
ceiling — judgement is required beyond it:

- another user's **disk** — filling it, or writing outside our own directory
- another user's **processes** — signalling, starving, or evicting them
- another user's **GPU processes** — claiming a card in use, or growing into their VRAM
- **RAM / VRAM exhaustion**, including transient peaks in a phase nobody is watching
- **CUDA OOM**, ours or theirs
- **desynchronisation** of any shared state
- **Docker**: images, containers, volumes, the daemon, the build cache
- **system state**: `/etc`, systemd, services, mounts
- **environment**: `PATH`, shell profiles, environment files
- **libraries, packages, distribution state, drivers**
- anything else this specific action could plausibly reach

**4. Decide whether each concern is resolved.** Resolved means a reason it cannot happen, or a
concrete limit that prevents it. "Probably fine" is not resolved. "It worked last time" is not
resolved.

**5. If any concern is unresolved, do not act.** Either resolve it first, or stop and report.

## Verify by reading, never by running

Where an action's behaviour is uncertain — an opaque pipeline that picks a directory to mount, a
download of unknown size, a phase that might allocate a lot of VRAM — **read the code and the
scripts with your own eyes** and establish what it does. Do not run it to find out.

This repository is large and parts of it are entangled. `07-this-repo-s-own-hazards.md` documents
the specific places where a default is dangerous on a shared machine, found by exactly this method.
It is not complete. Anything not listed there is unexamined, not safe.

## Stopping is a valid outcome

A GPU is occupied. RAM is tighter than expected. A permission is missing. Something does not match
what the docs say. **Stop.** Report what was found and wait. Do not relax any rule in this
directory to get past it — a blocked run costs hours; the alternative costs somebody else's work
and possibly the account.
