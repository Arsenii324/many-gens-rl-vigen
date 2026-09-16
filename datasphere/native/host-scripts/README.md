# Host scripts — the authoritative copy

These are deployed to `~/rlvigen-work/` on the production host (`varaksin_as@100.98.2.11`) and
invoked there. **This directory is the source of truth; the host is a deployment.**

They were committed on 2026-09-16 because until that day they existed **only on the host**. 28
scripts, including everything then driving production — `curve-sweep-v3.sh`,
`train-production-cell-v5.sh`, `reeval-cell-cached.sh` — had no copy anywhere else. A lost home
directory would have taken the entire operational toolchain with it.

Operational instructions are in [`notes/OPERATOR-GUIDE.md`](../../../notes/OPERATOR-GUIDE.md).
This file only says which script is which.

## Live — these are the ones to use

| script | what it does |
|---|---|
| `train-production-cell-v5.sh` | one 600k production cell: train + endpoint grid. Takes `CARD` and `YIELD_PROCS` as parameters, which v4 hardcoded |
| `curve-sweep-v3.sh` | evaluates every retained checkpoint of a run, several cells at a time; skips stamps whose result already exists |
| `reeval-cell-cached.sh` | one eval cell against one checkpoint, with the pip cache mounted |
| `self-vram-cap.sh` | stops **our** container, by exact name, when **our** GPU usage crosses a cap. Also committed at `datasphere/native/self-vram-cap.sh` |
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
