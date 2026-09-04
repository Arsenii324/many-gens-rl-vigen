Written 2026-09-03. Recovered from the session transcript, not authored fresh.

# The points list — production readiness (I), defaults (J), specific entries (K)

**Why this file exists.** This list governed a long working session and existed **only in
conversation**. It was never written to disk, so when the context was summarised the labels
survived (`I1`, `I6`, `J3`, `K3`) and the content did not. Asked later what the list was, I
matched the labels against `INTEGRATION-DELTA.md`'s I/J/K/M faithfulness ledger — a **different
list that happens to use the same letters** — and reported that as the answer. That was wrong, and
it is the reason this file now exists: *a working list that steers a session is a document, not a
message.*

Recovered by grepping the transcript at
`~/.claude/projects/-Users-a2mogus-build-projs-ccm-intro/d037da9e-*.jsonl`.

## I — production readiness

| # | item | status 2026-09-03 |
|---|---|---|
| I1 | The DataSphere job wall-clock limit is unknown | **partly answered, empirically.** Jobs ran to 5.1h (`rlvigen`, five cells) with a 6h `timeout` and were not killed by the platform. The *platform's* limit is still unknown; what is now known is that 6h is reachable |
| I2 | Resumability — half-present, and nobody has used it | **used, and it failed twice.** `RESUME_SNAPSHOT` was exercised by the checkpoint-defect investigation: v43 died on an empty replay buffer, v45 on the same after a `num_seed_frames` workaround. Resumption restores `_global_step` but not the buffer, so an update fires immediately against nothing. **Still not production-usable** |
| I3 | Result archive size at production length, and where checkpoints live afterwards | **measured, and now extrapolated from a single-cell 100k run.** A five-cell 10k `rlvigen` job returned **791 MB**; the three-cell 100k endurance pack **207 MB**; single short cells 20–70 KB. `bt15e9v1k2ngmb71hnjn` (one `drqv2` cell, 100k) returned **296 MB**, broken down: **199 MB checkpoints** (2 stamps × 104 MB, confirming C60's 50k cadence), **99 MB** terminal snapshot, **21 MB** tensorboard, everything else under 100 KB. At 6e5 the cadence yields 12 stamps, so a cell is **~1.5 GB** and 12 baselines × 3 seeds is **~53 GB** — against ~30 GB free on this laptop. **So the archives cannot all come home, and this is now arithmetic rather than a worry.** `EVAL-PROTOCOL.md` §6's rule (checkpoints stay remote, records come back) is the only shape that fits; `RECORDS_OUT` is the mechanism, and it was **broken for eval-only jobs until 2026-09-04** — it copied the training normalizer's output, which is empty when a job has no training cells |
| I4 | The production command shape has never been run | **run, 12/12 at 10k, and now once at 100k.** The pre-production pass executed the real command shape across seven jobs and all twelve baselines: payload + archive input, budget gate, import gate, cells, finiteness probe, retention, result archive. `bt15e9v1k2ngmb71hnjn` then ran it at **100k** for `drqv2` — 10× the pre-production budget, 201 records, finite checkpoint, no platform kill — which is the first evidence the shape survives a length where I3 and I1 both start to bite. It is **still not production length** (6e5 is another 6×), and one cell is not twelve |
| I5 | Simultaneous checkpoint writes under packing | **still untested.** The five-cell job ran cells **sequentially** — `NATIVE_CONCURRENT` was left unset, deliberately, to keep replay memory bounded. Packing *with* concurrency remains unexercised |
| I6 | Divergence policy for a long run | **default set** (C57): a non-finite checkpoint fails its cell, is never reported, and is **not** auto-retried at another seed — retry-until-finite conditions the result set on convergence and turns a stability property into a survivorship artefact |
| I7 | The evaluation pass is a second production run | **costed.** The four-regime × ten-scene grid (400 episodes) took ~1h for ~168 RUB. At 10k budgets evaluation ran **2–3× the training steps**, which is why the pass overran my estimate — I costed training and ignored evaluation |
| I8 | Seed allocation, and what a seed indexes | **untouched.** Related to §3b #4 (seeds 1 → 3–5), which is an owner decision |
| I9 | A correction to the cost model, in our favour | **confirmed, and larger than thought.** DataSphere's `Created at` includes **queue** time; billing it as compute overstated spend by ~40% in my own reporting (2,837 claimed vs 2,057 actual). Completed short cells cost 38–70 RUB each |

## J — defaults

| # | item | status |
|---|---|---|
| J1 | The coupling that decides most of the rest | **not re-derived.** Almost certainly the claim in `RESEARCH-FRAME.md` — "published implementations at their authors' own settings" — which answers C1/C2 and much else |
| J2 | Defaults, item by item | **largely done, out of order.** Defaults now recorded for C1, C2, C3, C4, C16, C29, C30, C43, C45, C54, C57, C58, C60, C61, C95 — every one still `OPEN`, because recording a default is not making the decision |
| J3 | Not grounded — I will not invent a default for these | **honoured.** C48 and C84 are left alone: both are *findings*, and a "default" for a finding is a category error |

## K — specific entries

| # | item | status |
|---|---|---|
| K1 | C61 — entropy coefficient, read in full | **done, and measured.** A live `ibac_sni` cell shows entropy rising **monotonically** 9.944 → 10.761 over 79 updates (σ 1.002 → 1.126). Default revised on the owner's ruling: adapt the coefficient/method for the continuous case rather than transcribe a categorical one |
| K2 | C84 — `drq`'s zero policy scale, and P17 already changed its facts | **untouched.** Named in J3's spirit as a finding needing a debugger, not a default |
| K3 | The remainder | **unknown.** The transcript preserves the heading but not the contents; treat as unrecovered |

## What this list is not

It is not the register (`CONSTRUCTION.md`), the ranked knobs (`STATUS-AGAINST-THE-GOAL.md` §3b),
the stages (`STAGES.md`), or the faithfulness ledger (`INTEGRATION-DELTA.md`'s I/J/K/M). Those are
four other lists. The overlap in labels between this file's I/J/K and the faithfulness ledger's
I/J/K/M is a **collision, not a correspondence**, and it has already caused one wrong answer.
