# 18 — The watch that would have expired first

**2026-09-08, during the second `idaac` cell on card 0.** Nothing failed. That is the point of this
entry: the run was proceeding normally, both instruments were reporting healthy, and the monitoring
was already useless. It took reading the arithmetic rather than the status lines to see it.

## The near-miss

The cell was launched at 20:14 with both card watches armed for `--max-seconds 4500`. That number
came from an assumed ten-minute `apt`/`pip` bootstrap.

Fifty-one minutes in, the bootstrap was still downloading `nvidia_cudnn_cu12` (731.7 MB), having
already spent 14m15s on `nvidia_cublas_cu12` alone (410.6 MB). Measured download rates across the
wheels in this job's log ranged from **162 kB/s to 835 kB/s**, and the torch CUDA stack is about
2.5 GB. The distribution is the wrong way round: the *largest* wheels drew the *slowest* rates, so
`nvidia_cudnn_cu12` (731.7 MB at 161.6 kB/s) took roughly 75 minutes by itself.

Two measurement notes, both of which cost me a wrong reading before I checked them. First, `pip`
detects a non-tty and prints only COMPLETED progress bars, so the log's last bar belongs to the
previous wheel and looks frozen while the current one downloads; container layer growth
(`docker ps -s`) is the honest progress signal. Second, an early rate quoted from the first few
wheels (395-835 kB/s) was simply wrong once cudnn landed -- a range measured before the worst case
exists is not a range.

So the sequence would have been:

| time | event |
|---|---|
| 20:14 | cell starts; card 0 at 0 MiB, watchers armed for 4500s |
| 21:29 | **both watches expire and exit 0**, reporting a clean run |
| ~22:00+ | the cell finally reaches the GPU |
| — | the entire GPU phase runs with no exclusivity watch and no yield daemon |

Both instruments would have exited zero. The exclusivity watcher would have printed its loud
end-of-watch banner, which is designed to be noticed — but it would have printed it into a log
nobody had reason to re-read, an hour before the thing it was guarding began. This is the project's
own defect class (*an instrument that could not run must never read as one that ran*) appearing
inside the instruments themselves.

**Also missed at launch:** `run_on_production_host.sh`'s own header, line 62, says a foreground
`docker run` dies on SSH SIGHUP while dockerd keeps the container alive, and prescribes `nohup`
around the whole script. The launch did not use it. The outer `timeout 5400 ssh` would have fired
at 21:44, killing the script before its stand-down and result-retrieval steps while the cell kept
running unattended.

## What was changed

1. **`--must-cover-seconds` on both watchers.** The caller declares what the watch must cover; the
   watcher refuses to arm when its budget is shorter, printing the shortfall as a number
   (`8100s before the work does`) rather than a complaint. Exit **3**, deliberately distinct from
   exit 2 (*cannot read the card*) — those need different fixes, and collapsing them would send
   someone hunting a driver problem when the answer is a larger number.
2. **`datasphere/native/launch-card-cell.sh`.** Tonight's launch was typed by hand; the card index
   appeared three times (`--gpus`, and `--device` on each watcher) with nothing checking they
   agreed. The launcher derives every one of them from `CARD`, and derives the watch budget from
   `CELL_TIMEOUT_SECONDS + NATIVE_BOOTSTRAP_ALLOWANCE_SECONDS + slack`. The bootstrap allowance
   defaults to 9000s, pessimistic on purpose: over-covering costs one idle poll per 20s,
   under-covering costs the watch.
3. **The `cell-active` marker is now retracted.** Creating it closed the bootstrap blind spot;
   never removing it left the mirror image, where a neighbour taking the card we had just *vacated*
   would read as a breach — a false alarm fired at exactly the moment the card is legitimately
   theirs. Both watchers accept `--stop-when-inactive` and stand down cleanly, with wording distinct
   from the timer expiry, which is an alarm rather than a designed ending. Neither stands down if
   the marker never appeared: a cell that dies during bootstrap leaves the card unwatched, which is
   when a watch matters most.
4. **A persistent pip wheel cache**, `NATIVE_PIP_CACHE_HOST` → `/root/.cache/pip`.

## On the cache, because the original reasoning was not wrong

`--no-cache-dir` was added the same day, with a measured justification: an in-container cache costs
3.0 GB in the writable layer, and `docker run --rm` discards that layer the moment the cell ends, so
the cache buys nothing. Every clause of that is true.

What it missed is that the layer is not the only place a cache can live. The cost it avoided was
real; the cost it chose instead — re-downloading ~2.5 GB per cell, per family, on a shared uplink —
is larger and recurs. Twelve baselines and seven attestation families pay it every time.

A host-side bind mount inverts the trade: nothing in the container layer, ~2.5 GB once on a
filesystem with 317 GB free, and every later cell resolves from disk. It is opt-in, so a host that
genuinely cannot spare the space keeps exactly today's behaviour. This is worth recording as a
reasoning failure rather than a coding one: the argument was sound and the option set was too small.

## Contract 18

`run_probe.sh` now reads `NATIVE_PIP_CACHE` and retracts the marker, so a payload built before this
paired with a host script after it would mount a cache the runner ignores, and the reverse would
leave the marker set forever. Neither fails loudly by itself — which is what the contract number is
for. Bumped in **both** homes (`contract.py` and `run_probe.sh --require-runner-contract`).

## Before the next launch

- Deploy the updated repo to `~/rlvigen-work/repo`. The watchers run from that mount, not from the
  payload, so `--must-cover-seconds` and `--stop-when-inactive` do not exist on the host until it is
  refreshed, and `launch-card-cell.sh` would fail arming them.
- Build a **contract 18** payload; `payload-idaac-c17.tgz` will be refused.
- Set `NATIVE_PIP_CACHE_HOST=$HOME/.cache/pip-rlvigen`. The first cell still pays the download; every
  one after it does not.
- Launch under `nohup`, as `run_on_production_host.sh:62` has said all along.

## What this does not change

The 51-minute figure is what was observed while the cell was still running, not a final bootstrap
time. The card was at 0 MiB throughout, so none of this cost the machine anything but bandwidth, and
card 1's neighbour was unaffected.


## How this cell actually ended, 2026-09-08 22:51

It never reached the GPU. After roughly two and a half hours it finished `pip` -- the run directory
holds `resolved_packages.json`, so the environment installed cleanly -- and then died at the
renderer check:

    RuntimeError: software EGL renderer: llvmpipe (LLVM 15.0.7, 256 bits)

`llvmpipe` is Mesa CPU rasterisation. The container had CUDA and no NVIDIA EGL, because docker's
`--gpus` sets `NVIDIA_DRIVER_CAPABILITIES=compute,utility` and nothing in this repo had ever added
`graphics`. Measured afterwards on the same host, image and card: the default yields no
`libEGL_nvidia`; `compute,utility,graphics` yields `libEGL_nvidia.so.580.126.09`. DataSphere set
this for us, which is why two hundred jobs never surfaced it and the first host cell did.

**This is the argument for letting the run finish rather than killing it.** The defect is invisible
to every static check in the repo — it is a platform default nobody wrote down — and it would have
been found by exactly one thing: running a cell far enough to render. It cost two hours of a
126 kB/s trickle on an idle card.

Three consequences worth separating:

- The `cell-active` marker never appeared, so both watchers correctly reported `0/1 process(es)`
  throughout and never raised a false breach on a card we never touched. The bootstrap-window fix
  behaved exactly as designed on its first real test.
- `--rm` removed the container the moment it exited, so the diagnosis came entirely from the bind
  mounts. The mounts are what made this recoverable; the container was gone before I looked.
- Had the renderer check not existed, this cell would have trained on software-rendered pixels and
  produced a record that looked ordinary. The refusal is the reason this is a stopped job instead
  of a corrupted result.
