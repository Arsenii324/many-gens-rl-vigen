# Working here alongside another agent

Two agents have worked this tree concurrently. These rules were each learned from something that
went wrong, and they are cheap to follow and expensive to rediscover.

## The mailbox

`ask-claude.md` (Codex writes) and `claude-answers.md` (Claude writes). **Single-writer files**, so
concurrent appends cannot lose a message. They are **append-only logs, not state** — state belongs in
the surfaces listed in [`START-HERE.md`](START-HERE.md), because reconstructing a position from a
775-line conversation log is exactly the failure the surfaces exist to prevent.

## Default-and-announce, never ask-and-wait

An autonomous agent may never answer a coordination question. So every handoff carries **the default
that will be taken absent a reply**, and then it is taken. Asking "pick one and say so" stalls work
on a reply that may not come.

## Do not overwrite an older record on a fresh claim

**The rule with a scar.** I told Codex `ppg`'s rollout gap was 8×; it edited `families.json`'s
`constants_note` accordingly, replacing text that was **correct** — the original had it right at
32×, sourced from `mpiexec -np 4`. A note that has survived scrutiny outranks a claim made an hour
ago. **Check the clone before overwriting a record**, and state your confidence when handing over a
number that contradicts one.

## Know which files are shared, and which tool answers that

`git status` does **not** see the clones — `.gitignore:35` is `runnable/*/` and each clone carries
its own `.git`. Empty output means *not tracked*, not *unmodified*. Use `scripts/deviations.py`.

## The descriptor serves two machines

`families.json`'s `constants` and `production` blocks feed **both** the probe fleet and production.
Any production-shaped value written there takes effect on the next probe — 16 processes on a 4-core
tier, or a 38.8 GiB buffer against a 27 GiB ceiling. See [`MIGRATION-T4-TO-V100.md`](MIGRATION-T4-TO-V100.md).

## Verify a green check before repeating it

Both agents have shipped false passes. When one of us reports a gate as PASS, the other should
confirm what the check actually inspects — twice now the answer was "not the surface that failed".
