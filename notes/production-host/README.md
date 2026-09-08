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

## The three that override everything else

1. **All work happens strictly inside a Docker container.** Install into the container, never the
   host. See `03`.
2. **Never install, update, change or remove anything on the host** — no `apt-get`, `brew`, `pip`
   outside a container, no conda, no drivers, no package manager of any kind. See `02`.
3. **Never cause another user's process to fail.** Not by OOM, not by CUDA OOM, not by filling a
   disk, not by taking every core, not by claiming a GPU someone is using. See `04`.

## If something blocks

A GPU is occupied, RAM is tight, a path is unreadable, a permission is missing — **that is a stop,
not a puzzle**. Do not work around it. It may encode context nobody wrote down. Report it and wait.
Losing time to a block is cheap; the alternative is not.

## The standing bias

When an action is uncertain, the resolution is always *verify by reading, then act* — never *run
it and see*. A tight debugging loop or a "temporary" step is a reason to be **more** careful, not
less. This project has already shipped several instruments that silently did nothing; on a shared
machine the same class of mistake takes someone else's job down with it.
