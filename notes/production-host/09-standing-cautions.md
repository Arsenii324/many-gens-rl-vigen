# Standing cautions

**This list is not exhaustive and never will be.** It is a set of the ones that actually matter,
kept dense on purpose. Treat it as a floor for judgement, never as the boundary of it: an action
not named here is *unexamined*, which is not the same as safe.

**It must grow.** The code changes, the hosts change, the phases change. Every time a new hazard is
met — or a near miss, or a defect found by reading — **add it here in the same commit as the fix**.
A caution list that stopped growing has stopped describing the system. Adding a line is cheap;
rediscovering an entry the hard way is not.

---

## Never, without an exception path

- Change **anything** on a host: packages, drivers, libraries, distribution state, `/etc`, systemd,
  shell profiles, environment files. No `apt`, `brew`, `conda`, host-level `pip`.
- Use a GPU, machine, or time window not assigned to you. Idle is not free.
- Delete a container, image, volume or file without positive proof you created it **and** that it
  did not exist beforehand. `prune` of any kind: never.
- Signal, kill or starve a process you did not start.
- Read, list or traverse other users' directories, containers, images or logs. No `ps aux`.
- Work around a refusal — permission, quota, device, path. A refusal is information.
- `sudo`, on a shared machine, for anything.
- Run a cell whose projected wall clock exceeds the remaining GPU assignment.

## Before acting — the questions that catch the most

- **What exactly does this command expand to?** Resolve every variable and path first. Not "the
  tmp dir" — the literal string.
- **Which host paths become writable mounts?** Derived paths are the trap: this repo's mounts come
  from `dirname "$RESULT"`.
- **What does this default to if I don't set it?** `--gpus` defaults to **all**. Defaults are where
  the damage lives, because nobody reads them.
- **How large is this download / write, and is the space there?** Before, not after.
- **What is the peak, not the average?** Transient allocations in a downstream phase have already
  bitten this project (8.27 GiB inside XLA autotuning, mid-run).
- **Is this figure measured or extrapolated?** `ctrl`'s 54.28 GiB is `13.57 × 4`. Treat every
  extrapolation as unproven.
- **Does this take every core?** 16 workers on a 16-core shared host is exclusive use whether or
  not it was meant to be.
- **What happens if this dies halfway?** Off-policy cells cannot resume: replay is not persisted,
  so a cut-off cell restarts from frame 0 and the elapsed GPU-time is simply lost.
- **Is this reversible, and by whom?** If undoing it needs an admin, it is not ours to do.
- **What time is it in the owner's timezone?** UTC+3. Near midnight this changes which day's
  assignment applies.

## Failure modes this project has actually produced

Each of these shipped, looked fine, and was found later. They are the shape to watch for.

- **An instrument that could not run, reading as one that ran and passed.** A watcher not in the
  payload, guarded by `-f` so it silently never started. A gate whose failure branch was
  unreachable. An audit comparing against a string the code could not emit.
- **A guard whose failure path assumed a command fails cleanly.** `stat` succeeding with garbage
  meant the `unreadable` branch never fired.
- **One number with two homes.** `SAVE_EVERY` vs `SAVE_EVERY_FRAMES`; `RUNNER_CONTRACT` in
  `contract.py` and again as a literal in `run_probe.sh`. Both cost jobs.
- **A watchdog measuring the wrong quantity.** Stall detection read a stdout buffer's flush cadence,
  not process liveness, and killed two healthy cells.
- **A check that watched the variance while the failure was in the mean.**
- **A default nobody read.** `RLVIGEN_PLACES_WORKERS` defaulted to the value its own comment blamed
  for heap corruption.
- **A "diagnostic" run in a regime production never uses.** `procs=1` pilots cannot settle a
  `procs=16` question.
- **A threshold invented by me, applied under the project's name.** State whose criterion it is.
- **Data collected and never read.** `resources.json` carried per-process GPU memory for every cell
  ever run, while the VRAM column of every planning table said "unmeasured". Before concluding a
  quantity is unknown, check whether something is already recording it.

## Judgement, when nothing above applies

- **Verify by reading, not by running.** Especially for opaque pipelines, unknown download sizes,
  anything that selects a directory or claims a device. "Run it and see" is not available on a
  shared machine.
- **A tight loop or a temporary step is a reason for more rigour, not less.** Most damage is done
  in the step someone thought didn't count.
- **Stopping is a valid outcome.** A block may encode context nobody wrote down. Report and wait.
- **Absence of evidence is not evidence.** "No error" is not "it worked"; check the artefact.
- **Say which claims are verified and which are assumed**, every time. The assumed ones are where
  the next failure is.
