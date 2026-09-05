"""Checkpoint writes that cannot crash a multi-hour training run, and cannot leave a torn file.

ENABLES-class, in this project's own taxonomy (see P18/P19/P6): it changes what survives a disk or
I/O failure, never what is learned. `write_fn` is called with the SAME object the caller already
built (`torch.save(obj, ...)` becomes `torch.save(obj, tmp)`), so on the golden path -- disk has
space, the write succeeds -- behaviour is byte-for-byte identical to before. No gradient, optimizer
step, environment interaction, or random draw is touched. The wait-then-skip policy under real
disk pressure is the one place this can change what evidence a run produces (a missing stamp rather
than a crash); that skip is loud in training.log (`SAFE_CHECKPOINT_SKIPPED`) but is NOT YET a
structured field in records.jsonl -- adding that touches a frozen evaluator code member, so it is
left as a documented, findable log fact rather than done here. If a production run ever exercises
this path, check training.log at that stamp before trusting the curve there.

Every family here calls `torch.save` (or, for ctrl, writes serialized bytes) straight at the final
path. Two failure modes follow directly from that, and both are worse the longer the run has been
going: (1) the write is interrupted partway -- OOM, SIGKILL, disk full mid-write -- and the file at
that path, which a resume or an evaluator will load NEXT, is now corrupt, not merely missing; (2) the
disk fills and `torch.save` raises `OSError(ENOSPC)`, which is an unhandled exception in the middle
of a training loop and kills the process outright, discarding every GPU-hour since the last
checkpoint that DID complete.

The policy, stated because it is a real decision and not merely a mechanism: WAIT for space up to a
bound, log loudly, then SKIP this stamp rather than raise. A checkpoint not written once is
recoverable at the next stamp (or the run simply has one fewer curve point); a training process
killed by an unhandled OSError, hours from its own endpoint, is not recoverable at all.

Imported from `runnable/_shim`, already on PYTHONPATH for five of seven families; the other two
(ppg, ibac_sni) had it added alongside this file.

MARGIN IS SIZE-AWARE, not a flat constant (2026-09-05 revision). A flat multi-GiB floor is safe
against false ENOSPC crashes but creates the opposite failure on a small host: a checkpoint that
would easily fit gets skipped forever because "free space" never clears an arbitrary constant that
has nothing to do with what is actually being written. `safe_torch_save` now serializes to memory
first, measures the REAL size, and requires only a small safety multiple of that -- so a 100 MB
checkpoint needs ~300 MB free, not 2 GiB, regardless of host size.

TWO ENVIRONMENT ESCAPE HATCHES, because an automated margin or a `shutil.disk_usage` reading can
itself be wrong, and the fix for "the machine's logic is misjudging this situation" must not be a
code change on a running job:
  SAFE_CHECKPOINT_FORCE=1              -- skip the disk check entirely; write is still atomic
  SAFE_CHECKPOINT_MIN_FREE_BYTES=<int> -- override the computed threshold with an exact value
Both are read fresh on every call, so they take effect on a job already running without a restart.
"""
import io
import os
import shutil
import time

#: Used only when the caller cannot supply `expected_bytes` (e.g. a `write_fn` whose output size
#: isn't known in advance). Comfortably above the largest checkpoint measured in this project
#: (~104 MB, drqv2/alda).
DEFAULT_MIN_FREE_BYTES = 2 * 1024 ** 3
#: Multiplier applied to a KNOWN object size: covers the tmp file briefly coexisting with the old
#: one during the atomic swap, plus filesystem overhead, without demanding a flat multi-GiB floor
#: that has nothing to do with what is actually being written.
SIZE_SAFETY_FACTOR = 3
#: A tiny checkpoint (ctrl's msgpack states can be small) still deserves SOME margin.
MIN_MARGIN_FLOOR_BYTES = 64 * 1024 ** 2
#: Bounded deliberately small. A stamp's checkpoint is one of twelve; losing one costs a point on a
#: curve. But `max_wait_seconds` is spent OUT OF the job's own `timeout --foreground` budget, and if
#: disk pressure is not transient but PERSISTENT, waiting long at every stamp would itself handicap
#: the run -- fewer real training steps completed, for a mechanism whose whole purpose is protecting
#: training steps already taken. 300s x 12 stamps is at most one hour of a run typically 5-45h;
#: 1800s x 12 would be up to six.
DEFAULT_MAX_WAIT_SECONDS = 300
#: For the ONE guaranteed terminal save per run, not intermediate stamps. Asymmetric on purpose:
#: losing an intermediate stamp costs one point on a curve, so 5 minutes is enough margin before
#: moving on. Losing the terminal save costs the entire multi-hour-to-multi-day run's reportable
#: result. 30 minutes is long enough for a human to notice a full-disk job and actually clear space,
#: short enough to stay a small fraction of even the shortest production cell (~5h).
TERMINAL_MAX_WAIT_SECONDS = 1800
DEFAULT_POLL_SECONDS = 30


def _free_bytes(path: str) -> int:
    directory = os.path.dirname(os.path.abspath(path)) or "."
    return shutil.disk_usage(directory).free


def _env_int(name):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"SAFE_CHECKPOINT_BAD_ENV {name}={raw!r} is not an integer; ignoring it", flush=True)
        return None


def safe_write(path, write_fn, *, min_free_bytes=None, expected_bytes=None,
              max_wait_seconds=DEFAULT_MAX_WAIT_SECONDS, poll_seconds=DEFAULT_POLL_SECONDS,
              label="checkpoint") -> bool:
    """Write via `write_fn(tmp_path)`, then atomically rename onto `path`.

    The required free space is, in priority order: `SAFE_CHECKPOINT_MIN_FREE_BYTES` (env override,
    always wins), else an explicit `min_free_bytes` from the caller, else
    `max(MIN_MARGIN_FLOOR_BYTES, expected_bytes * SIZE_SAFETY_FACTOR)` when `expected_bytes` is
    known, else the flat `DEFAULT_MIN_FREE_BYTES`.

    `SAFE_CHECKPOINT_FORCE=1` skips the space check entirely -- the write is attempted regardless,
    still atomic, still exception-safe. For when the automated measurement or margin is itself
    judged wrong for a specific host, without needing a code change on an already-running job.

    Never raises: any exception from the disk-space check or the write itself is caught, logged
    with a grep-able marker, and reported as a skip (return False) -- because the one thing worse
    than a missed checkpoint is a training loop that dies over one.
    """
    path = str(path)
    tmp = path + ".tmp-writing"

    env_override = _env_int("SAFE_CHECKPOINT_MIN_FREE_BYTES")
    if env_override is not None:
        needed = env_override
    elif min_free_bytes is not None:
        needed = min_free_bytes
    elif expected_bytes is not None:
        needed = max(MIN_MARGIN_FLOOR_BYTES, int(expected_bytes * SIZE_SAFETY_FACTOR))
    else:
        needed = DEFAULT_MIN_FREE_BYTES

    forced = os.environ.get("SAFE_CHECKPOINT_FORCE", "").strip() == "1"

    if not forced:
        waited = 0
        while True:
            try:
                free = _free_bytes(path)
            except OSError as error:
                print(f"SAFE_CHECKPOINT_FAILED label={label} path={path} "
                      f"stage=disk_check error={type(error).__name__}: {error}", flush=True)
                return False
            if free >= needed:
                break
            if waited >= max_wait_seconds:
                print(f"SAFE_CHECKPOINT_SKIPPED label={label} path={path} "
                      f"free={free} needed={needed} waited={waited}s -- set "
                      f"SAFE_CHECKPOINT_FORCE=1 to write anyway, or "
                      f"SAFE_CHECKPOINT_MIN_FREE_BYTES to change the threshold", flush=True)
                return False
            print(f"SAFE_CHECKPOINT_WAITING label={label} path={path} "
                  f"free={free} needed={needed} waited={waited}s", flush=True)
            time.sleep(poll_seconds)
            waited += poll_seconds
    try:
        write_fn(tmp)
        os.replace(tmp, path)  # atomic on POSIX when tmp and dest share a filesystem, which they do
        return True
    except Exception as error:
        print(f"SAFE_CHECKPOINT_FAILED label={label} path={path} "
              f"stage=write error={type(error).__name__}: {error}", flush=True)
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        return False


def safe_torch_save(obj, path, torch_kwargs=None, **kwargs) -> bool:
    """Drop-in-safer replacement for `torch.save(obj, path, **torch_kwargs)`.

    `torch_kwargs` forwards to the underlying `torch.save` (e.g. `pickle_protocol=-1`); everything
    else in `kwargs` controls `safe_write`'s own policy (`min_free_bytes`, `label`, etc).

    CAUGHT LIVE, on a real remote job, 2026-09-05: this used to hardcode `label="torch.save"` as a
    keyword argument WHILE ALSO forwarding a caller's own `label=...` through `**kwargs` -- a direct
    collision, `TypeError: got multiple values for keyword argument 'label'`. Every one of the
    eleven call sites this module was wired into passes `label=` explicitly, so this crashed on
    EVERY real checkpoint write, unconditionally -- the one thing this module exists to never do.
    `kwargs.setdefault` lets the caller's label win without ever colliding.

    Serializes to an in-memory buffer FIRST, both so the required margin can be sized to the REAL
    object (not a flat guess) and so the on-disk write is one fast buffer write rather than pickling
    incrementally to disk -- a smaller window for an interrupt to land mid-write.
    """
    import torch
    kwargs.setdefault("label", "torch.save")
    buffer = io.BytesIO()
    torch.save(obj, buffer, **(torch_kwargs or {}))
    payload = buffer.getvalue()
    kwargs.setdefault("expected_bytes", len(payload))
    return safe_write(path, lambda tmp: open(tmp, "wb").write(payload), **kwargs)
