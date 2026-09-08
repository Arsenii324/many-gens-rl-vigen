# The production host: read this entire directory before touching anything

`cds2` is a **university communal machine** with strict GPU and environment control, shared with
other people's running work. Nothing in this directory is advisory.

**Read every file here in full before any host action.** Not a skim, and not this README alone —
it is an index, not a summary. The per-file rules carry the specifics that make them enforceable,
and the specifics are where the harm is.

| file | what it governs |
|---|---|
| [`00-authority-and-scope.md`](00-authority-and-scope.md) | which machine, on whose authority, and what "documented" does NOT mean |
| [`01-connection.md`](01-connection.md) | Netbird, the address table, and what the guide does and does not say |
| [`02-absolute-prohibitions.md`](02-absolute-prohibitions.md) | the things that are never done, with no exception path |
| [`03-docker-discipline.md`](03-docker-discipline.md) | all work inside a container; what may be deleted and the proof required |
| [`04-resource-safety.md`](04-resource-safety.md) | GPU, VRAM, RAM, CPU, disk — assume none of it is free |
| [`05-privacy-and-non-alarm.md`](05-privacy-and-non-alarm.md) | what not to look at, and why looking is itself a hazard |
| [`06-before-any-action.md`](06-before-any-action.md) | the mandatory pre-action procedure |
| [`07-this-repo-s-own-hazards.md`](07-this-repo-s-own-hazards.md) | **specific dangerous defaults in OUR code**, read before running any of it |
| [`08-gpu-assignment-and-time.md`](08-gpu-assignment-and-time.md) | **the GPU assignment schedule**, and why every time must be stated in UTC+3 |
| [`09-standing-cautions.md`](09-standing-cautions.md) | the dense list — a floor for judgement, and one that must keep growing |
| [`10-resource-upper-bound-rule.md`](10-resource-upper-bound-rule.md) | **the upper-bound rule** — it subsumes much of `04`; VRAM now measured |
| [`11-host-state-2026-09-08.md`](11-host-state-2026-09-08.md) | **a read of the actual host, and TWO live blockers** — re-read before each session |

## The rule that comes before the others

**If you do not know an upper bound on what you will occupy, do not run it. If anything else is on
the GPU, CPU, RAM or disk — theirs, or not certainly yours, or even certainly yours — and you are
not sure the remainder covers your whole run, do not run yours.** Peaks combine, and CUDA OOM
happens at the combined peak, not at typical usage. [`10`](10-resource-upper-bound-rule.md).

**We do not currently satisfy this for VRAM**: six of seven families have no VRAM measurement at
all. That blocks the first shared-GPU cell until it is closed.

## The three that override everything else

1. **All work happens strictly inside a Docker container.** Install into the container, never the
   host. See `03`.
2. **Never install, update, change or remove anything on the host** — no `apt-get`, `brew`, `pip`
   outside a container, no conda, no drivers, no package manager of any kind. See `02`.
3. **Never cause another user's process to fail.** Not by OOM, not by CUDA OOM, not by filling a
   disk, not by taking every core, not by claiming a GPU someone is using. See `04`.
4. **Use only the GPU assigned to you, on the machine and day it was assigned.** Idle is not free,
   and a similar name is not the same machine. See `08`.
5. **No list here is complete.** `09` is a floor for judgement, not its boundary, and it is meant to
   grow — a new hazard gets added in the same commit as its fix.

## If something blocks

A GPU is occupied, RAM is tight, a path is unreadable, a permission is missing — **that is a stop,
not a puzzle**. Do not work around it. It may encode context nobody wrote down. Report it and wait.
Losing time to a block is cheap; the alternative is not.

## The standing bias

When an action is uncertain, the resolution is always *verify by reading, then act* — never *run
it and see*. A tight debugging loop or a "temporary" step is a reason to be **more** careful, not
less. This project has already shipped several instruments that silently did nothing; on a shared
machine the same class of mistake takes someone else's job down with it.
