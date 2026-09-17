# Host scripts — the authoritative copy

These are deployed to `~/rlvigen-work/` on the production host (`varaksin_as@100.98.2.11`) and
invoked there. **This directory is the source of truth; the host is a deployment.**

They were committed on 2026-09-16 because until that day they existed **only on the host**. 28
scripts, including everything then driving production — `curve-sweep-v3.sh`,
`train-production-cell-v5.sh`, `reeval-cell-cached.sh` — had no copy anywhere else. A lost home
directory would have taken the entire operational toolchain with it.

Operational instructions are in [`notes/OPERATOR-GUIDE.md`](../../../notes/OPERATOR-GUIDE.md) —
the end-to-end map: stages, what produces what, the container topology, and which tool belongs
to which stage. The executable procedure it points into is
[`notes/RUNNING-ON-PRODUCTION-HOST.md`](../../../notes/RUNNING-ON-PRODUCTION-HOST.md).

[Claude 2026-09-17] That link was dangling until today: this README named OPERATOR-GUIDE.md
and no such file existed, so the one pointer a host operator is most likely to follow led
nowhere. Found by sweeping every internal .md link in the repo; it was the only genuinely
broken one of 212.
This file only says which script is which.

## Deploying a change back to the host

The host copy is a deployment, so a change here is not in effect until it is copied over. Two rules
govern when that copy may happen, and both were learned the hard way.

**Never overwrite a script whose cell is running.** bash reads a script incrementally, so replacing
the file under a running shell makes it resume at a byte offset that no longer means what it did.
The symptom is a syntax error reported at a line that is fine, on a file that passes `bash -n`. Wait
for the cell, then deploy.

**Check drift before you trust either copy:**

```bash
ssh varaksin_as@100.98.2.11 'cat ~/rlvigen-work/train-production-cell-v5.sh' \
  | diff - datasphere/native/host-scripts/train-production-cell-v5.sh
```

Empty output means they agree. If they differ, find out which way before copying: these files lived
only on the host until 2026-09-16, so the host copy has been the newer one before.

### Pending deployment

- `self-vram-cap.sh` — **the host copy still carries a disproven number in its header.** It states
  22,675 MiB as "The true figure, measured" for ibac_sni and concludes the family "cannot share a
  card with a co-tenant larger than ~6 GiB". That figure was a colleague's memory on a shared card;
  ibac_sni was measured at **7,421 MiB** on an exclusive card on 2026-09-16 and has since trained a
  full 600k cell. The two copies in this repo had also drifted from each other; they now agree, and
  **0 executable lines differ** between them and the host — the whole divergence is comment.
  Deploy once no `self-vram-cap.sh` instance is running.
- `train-production-cell-v5.sh` — the repo copy's header was corrected on 2026-09-16 to retract
  "between launch and finish, nothing on the host enforces headroom" (the memory floor *is* armed
  for the life of every cell; only the host-side PID neighbour yield is skipped in shared mode).
  **Comment-only: 0 executable lines changed**, so the running cell is unaffected and the deploy can
  wait. Copy it over once `ibac_sni-s101-prod` finishes.

## Live — these are the ones to use

| script | what it does |
|---|---|
| `train-production-cell-v5.sh` | one 600k production cell: train + endpoint grid. Takes `CARD` and `YIELD_PROCS` as parameters, which v4 hardcoded |
| `curve-sweep-v3.sh` | evaluates every retained checkpoint of a run, several cells at a time; skips stamps whose result already exists |
| `reeval-cell-cached.sh` | one eval cell against one checkpoint, with the pip cache mounted |
| `self-vram-cap.sh` | stops **our** container, by exact name, when **our** GPU usage crosses a cap. Also committed at `datasphere/native/self-vram-cap.sh` |
| `watch-cell.sh` | **runs on the laptop.** Watches one cell: stop marker, result, disk against the cell's own floor, stall, occupancy logger, new groups. `trip` exits on the first actionable event; `beat` also prints a heartbeat. This is the watcher that actually ran production on 2026-09-17, committed with only its run paths parameterised, and checked three ways before commit: it fired in 2 s on a cell the floor really stopped, it stayed silent on a healthy live cell, and it refuses to start without its parameters |
| `neighbour-yield.sh`, `host-run.sh` | supporting; the host copies differ from the `datasphere/native/` copies and these are what actually ran |

## Superseded — do not start these

`train-production-cell.sh` and `-v2`, `-v3`, `-v4`; `curve-sweep.sh`, `curve-sweep-v2.sh`;
`reeval-cell.sh` (replaced by `-cached`).

Why so many versions: **rule — never write to a script that may be executing.** Bash reads a
script by byte offset as it runs, so editing in place corrupts a live run. Each version bump here
is that rule being followed. Keeping the old ones costs nothing and preserves what actually ran.

### The waiters, which need a warning rather than a row

`ibac-waiter.sh`, `launch-ibac-when-roomy.sh`, `launch-when-free.sh`, `chain-when-card-free.sh`
sit armed and launch when a card frees. On 2026-09-16 `ibac-waiter.sh`, armed hours earlier and
forgotten, fired fifteen seconds before a deliberate launch and put two 600k `ibac_sni` cells with
16 workers each on one 16-core host. Neither errored; the only symptom was halved throughput.
**Disarm every waiter before launching by hand**, and resolve PIDs from `/proc/<pid>/cmdline`
`argv[1]` rather than `pgrep -f`, which matches your own ssh shell.

## Diagnostic / one-shot, kept for provenance

`jax-volta-probe.sh`, `jax-volta-probe-v2.sh`, `jax-cudnn-diag.sh`, `jax-cudnn-pin.sh`,
`run-volta-probe-when-free.sh` — the ctrl/cuDNN-on-Volta investigation, now resolved.
`attest-chain.sh`, `attest-retry.sh`, `attest-retry2.sh`, `attest-v212.sh`, `attest-v213-ctrl.sh`,
`ctrl-retry.sh` — the v212/v213 attestation wave.
`fetch-places.sh`, `extract-places-once.sh`, `verify-places-folder.sh` — Places365 setup; the
dataset is already in place, so re-running these is not part of normal operation.

Read any of them before rerunning. Several target a problem that has since been fixed.
