# Adversarial review: FAITHFULNESS / INTEGRATION-DELTA / contract docs

**Written 2026-08-24. This is a dated snapshot, not a living document.** It states what one review
pass found on that date and is not maintained. Check any claim here against the live document
before acting on it.

Scope: one pass, reading-and-grepping only, no runs. Effort concentrated on `FAITHFULNESS.md`,
with `INTEGRATION-DELTA.md` and `COMPARABILITY_CONTRACT.md` sampled. Confidence labels are
CONFIRMED (I checked the primary artifact), LIKELY (strong indirect evidence), SUSPICION (a smell,
unverified).

---

## F1 — `FAITHFULNESS.md` never says it describes the superseded port. CONFIRMED. Highest severity.

**Where** Whole document; most concretely `docs/FAITHFULNESS.md` §2–§4.

**What it says** Per-algorithm divergences, fixes and pipeline audits, stated in the present tense
as facts about what this project runs.

**Why this is wrong** On 2026-08-17 the project changed direction: the null became the original
repository, cloned, running its own `train.py`, and the port under `rlgen/` was superseded.
`PROJECT-INDEX.md:14-20` states this prominently. `FAITHFULNESS.md` does not state it anywhere.

Measured across the six claim-bearing docs:

| document | `rlgen/` references | mentions "superseded" |
|---|---|---|
| **`FAITHFULNESS.md`** | **25** | **0** |
| `COMPARABILITY_CONTRACT.md` | 31 | 1 (plus a header scoping it as "the older framing") |
| `VALIDATION.md` | 20 | 1 |
| `ORIGINAL_LOCATIONS.md` | 12 | 3 |
| `INTEGRATION-DELTA.md` | 8 | 5 |
| `PREMISES.md` | 1 | 0 |

**It is the only document of the six that carries a large `rlgen/` surface and never once tells the
reader those references describe a retired machine.** Its date stamps confirm the vintage:
14 × `2026-08-10`, 11 × `2026-08-13`, 17 × `2026-08-14`, 1 × `2026-08-24` — essentially all of its
verified content predates the supersession.

This matters because of where the index points readers. `PROJECT-INDEX.md:42` routes to this file
*"Before quoting any baseline's result as that method's result"* — i.e. it is the designated
authority for exactly the question its stale half cannot answer.

A whole class of its findings is about a mechanism the clone path does not possess. The
`aux_beta` / `aux_lr` "config-reachability" audits reason about `rlgen/registry.py` `defaults`
dicts and whether `configs/vigen.yaml` can reach a constructor kwarg. The clone path has no
registry and no `configs/vigen.yaml`; it runs upstream hydra. Those audits are not wrong, they are
about a different program.

**How I checked** `grep -c "rlgen/"` and `grep -ci superseded` over each doc; `grep -o "2026-08-[0-9][0-9]"`
piped to `sort | uniq -c`; read `PROJECT-INDEX.md:14-20` and `:42`.

**Suggested fix** A scoping header, in the shape `COMPARABILITY_CONTRACT.md:3-8` already uses.
Naming which sections describe the port and which survive to the clones would be better, but the
header alone removes the trap.

---

## F2 — The SGQN `aux_lr` fix does not reach the live clone path. CONFIRMED. High severity.

**Where** `docs/FAITHFULNESS.md` §2, the `sgqn` block (the "critical finding" and the RESOLVED
block above it).

**What it says** That `aux_lr` was a 1000× defect (`0.3` vs canonical `3e-4`), that we inherited
it, and — verbatim — *"**FIXED 2026-08-10**: `configs/vigen.yaml` now sets `aux_lr: 8.0e-5` and
`sgqn_quantile: 0.9`"*, with the fix target justified at length as Table 6's robosuite values.

**Why this is wrong** That fix edits the superseded port's config. The live clone path never reads
it:

- `runnable/_launch/rlvigen.sh:23` — `CFG="${AGENT}_config"`, so `sgqn` → `sgqn_config`.
- `runnable/_launch/rlvigen.sh:76-77` — `exec "$PY" train.py --config-name "$CFG" env=robosuite ...`,
  run with cwd `$RLV` (the upstream tree).
- `EXTRA_OVERRIDES` (`rlvigen.sh:50,53`) contains only `replay_buffer_num_workers=0` or nothing.
  **No `aux_lr` and no `sgqn_quantile` override exists anywhere on the launch path.**
- `RL-ViGen-upstream/cfgs/sgqn_config.yaml:54,56` — `aux_lr: 1e-4`, `sgqn_quantile: 0.93`.

So a `sgqn` clone run uses **`aux_lr: 1e-4`, `sgqn_quantile: 0.93`** — matching neither the paper's
Table 6 (8e-5 / 0.9) that the doc argues for at length, nor canonical (3e-4 / 0.95), nor the `0.3`
trap. A reader consulting this file before quoting an SGQN number would believe it ran at the
tuned-on-this-benchmark values. It did not.

Note the doc's own reasoning still holds *for the port* — the `0.3` trap was real there precisely
because the port bypassed hydra. The clone restores hydra, which is why the trap is gone and the
fix is simultaneously moot. Both halves are individually correct; the join is what misleads. This
is the exact failure shape `SYSTEM.md`'s "known weaknesses" section says every defect here has had.

**How I checked** Read `runnable/_launch/rlvigen.sh` lines 23, 50, 53, 55-77; `grep -n "aux_lr\|sgqn_quantile" RL-ViGen-upstream/cfgs/*.yaml`.

**Not checked, and worth someone's time** Whether any archived `sgqn` result was produced under the
port (8e-5) or the clone (1e-4). If both exist, they are not the same arm.

---

## F3 — `drqv2` stddev-schedule defect stated as live, 30 lines after being marked FIXED. CONFIRMED. Medium.

**Where** `docs/FAITHFULNESS.md` §2 `drqv2` block, second bullet of "Two divergences, both `[OURS]`".

**What it says, present tense** *"**`stddev_schedule: linear(1.0,0.1,500000)`** is DrQ-v2's
**medium-tier** string, whose budget is 3.1M frames — noise finishes annealing at 16% of training.
Paired with our 500k budget it finishes at the last frame, so the agent never trains under low
noise."*

**Why this is wrong** §0a's knob table in the same file records it as **FIXED 2026-08-10** to
`linear(1.0,0.1,100000)`, and consequence 4 under that table describes the fix in detail. The §2
bullet was never updated and reads as a live defect.

Separately, on the live clone path the value is correct anyway but *for a reason the doc does not
give*: `RL-ViGen-upstream/cfgs/task/Door.yaml:1-3` declares `defaults: [easy, _self_]`, and
`cfgs/task/easy.yaml:2` sets `stddev_schedule: 'linear(1.0,0.1,100000)'`. So the clone gets 100000
**by upstream inheritance**, not by our fix. Anyone reading either the §2 bullet or the §0a fix
note would have the wrong mechanism in mind.

**Why it is worth listing despite the value being right** The doc itself flags this failure mode
in §3's `drq` block: *"Fourth instance this session of one stale claim surviving in one place after
being corrected in another — grepping for a defect's description keeps missing restatements of its
conclusion elsewhere in the same document."* F3 and F4 are the fifth and sixth instances, in that
same document, of that same pattern.

**How I checked** Read `docs/FAITHFULNESS.md` §0a table and §2; `cat RL-ViGen-upstream/cfgs/task/Door.yaml`;
`grep -rn "stddev_schedule" RL-ViGen-upstream/cfgs/task/*.yaml`.

---

## F4 — `drqv2` replay capacity listed as a live divergence after being retracted twice. CONFIRMED. Medium.

**Where** `docs/FAITHFULNESS.md` §2 `drqv2` block, first bullet of "Two divergences, both `[OURS]`".

**What it says** *"**replay capacity 1e5**, where DrQ-v2 uses **1e6** ... At 500k frames a 1e5
buffer holds the most recent 20% and evicts the rest."* — presented as a live `[OURS]` divergence
with a stated consequence.

**Why this is wrong** Retracted in two other places in the same file. The §0 summary row for
`drqv2` reads *"replay 1e5 vs 1e6 (retracted, see below)"*, and §0a's knob table says
*"**RETRACTED as a finding.** RL-ViGen's replay is disk-backed ... Not a deviation worth fixing."*
The §2 bullet carries no retraction marker, and its header still counts "**Two** divergences".

**How I checked** Read all three passages in `docs/FAITHFULNESS.md`.

---

## F5 — The `5e5` training budget appears throughout and matches no current run. CONFIRMED. Low-medium.

**Where** `docs/FAITHFULNESS.md` §0a knob table ("ours | 5e5") and the consequence paragraphs that
reason from it (consequence 3, consequence 4's "our **500k**").

**Why this is suspect** On the clone path, `num_train_frames` comes from
`cfgs/task/easy.yaml:1` → **1,100,000** unless overridden. And **no run on disk uses 5e5.** Every
`exp_local` run directory names its budget explicitly, and the values found are `1300`, `1200`,
`1300` (2026-08-17 smoke runs) and `120000` (the 2026-08-18 run behind C54/C62/C63). `5e5` is a
port-era config value describing neither the clone default nor any run this project has executed.

Consequence 4's whole argument — that annealing "finishes exactly at the final frame" — is computed
against the 500k budget. With the clone's 1.1e6 default or the actual 120k runs, that arithmetic
does not hold. The conclusion may survive; the stated derivation does not.

**How I checked** `grep -rn "num_train_frames" RL-ViGen-upstream/cfgs/task/*.yaml`; run directory
name under `RL-ViGen-upstream/exp_local/2026.08.18/`.

**Confidence note** CONFIRMED that the numbers differ. Whether any current claim depends on the
5e5 figure I did not trace — that is the follow-up.

---

## F6 — `COMPARABILITY_CONTRACT.md` says PART2 has six findings; it has seven. CONFIRMED. Low.

**Where** `docs/COMPARABILITY_CONTRACT.md:5-6`.

**What it says** *"`docs/PART2-METRIC-INVENTORY.md` carries the per-baseline account ... with six
findings"*.

**Why it is wrong** `docs/PART2-METRIC-INVENTORY.md` contains Findings 1 through 7; Finding 7
("RL-ViGen's own runner did not measure generalisation on robosuite at all") is at line 214.
`PROJECT-INDEX.md:17-19` correctly says seven. Classic count-drift: the contract's header was
written 2026-08-17 and Finding 7 was added afterwards.

**How I checked** `grep -o "seven findings\|six findings"` on both docs; `grep -n "Finding "` on PART2.

---

## F7 — Real citation drift in the reviewed docs. CONFIRMED (that the checker flags it); individual rows are leads. Low.

`python scripts/check_citations.py --content` reports roughly 98 `DRIFT`/`ABSENT` rows. Its
precision is ~57% per `SYSTEM.md`, so these are leads, not defects. The ones inside this review's
scope:

- `docs/FAITHFULNESS.md:396` cites `registry.py:327` for `curl`'s `defaults` dict; anchor `aux_beta`
  found at 356 (+29). Note the same paragraph separately cites `registry.py:356` for `sgqn` — so one
  of the two is now pointing at the other's line.
- ~~`docs/FAITHFULNESS.md:324` cites `algos/sgqn.py:172` with anchor `if self.consistency:` —
  reported ABSENT.~~ **Checked by hand: false positive, and the doc is right.**
  `RL-ViGen-upstream/algos/sgqn.py:172` reads
  `critic_loss += 0.9 * (F.mse_loss(Q1, masked_Q1) + F.mse_loss(Q2, masked_Q2))` — the value 0.9 is
  there, hardcoded and **ungated**, exactly as the consistency-weight table claims. The checker
  flagged it only because the anchor `if self.consistency:` is the *canonical* side's gate, whose
  absence in RL-ViGen's version is precisely the distinction the doc is drawing. The anchor was
  inherited from the neighbouring table row. **This is the ~43% false-positive rate behaving as
  documented — the row is checker noise, not doc drift.** Also confirmed in passing:
  `sgqn.py:120` is `def __init__(self, aux_lr=0.3, aux_beta=0.9, sgqn_quantile=0.95, **kwargs)`,
  matching the doc's constructor-default column exactly.
- `docs/FAITHFULNESS.md:323` cites `sgsac.py:67`; found at 61 (−6). Not hand-checked.
- `docs/INTEGRATION-DELTA.md:85,87,89,91,92,113,189` — seven rows against `ext/` references.

**Recommended** spot-check `FAITHFULNESS.md:324` by hand first; it is the only one of these whose
failure would move a stated value.

---

## Looked at and found clean

- `COMPARABILITY_CONTRACT.md` **does** scope itself honestly — its header (lines 3-8) names
  `PART2-METRIC-INVENTORY.md` as superseding and calls itself "the older framing". This is the
  pattern F1 recommends for `FAITHFULNESS.md`. Its 31 `rlgen/` references are a smell but the
  header disarms them.
- `INTEGRATION-DELTA.md` handles the port/clone split best of the set — 8 `rlgen/` references
  against 5 explicit "superseded" mentions.
- `FAITHFULNESS.md` §1's truncation/termination analysis is unusually well-sourced: it traces to
  `robosuite/environments/base.py:433` rather than repeating the three in-repo restatements, and it
  explicitly says three repetitions of one claim are not three checks. No defect found.
- `FAITHFULNESS.md` §0a's paper-vs-code table is verified from primary sources on both sides and
  says so, including the warning that `pdftotext -layout` misaligns the Adroit table. The
  `action_repeat` row agrees with what I found on the clone path.
- The `alda` `utd` finding (§3) correctly names the live launch path and is pinned by two tests,
  one of which builds through the real registry. It is the one fix in the file that explicitly
  verified reachability rather than assuming it.

## Not checked

- `PREMISES.md`, `ORIGINAL_LOCATIONS.md`, `VALIDATION.md`, `RUNNABLE-ORIGINALS.md`,
  `PART2-METRIC-INVENTORY.md` beyond the targeted greps reported above.
- `FAITHFULNESS.md` §4 (the PPO family, lines ~560-1174) was not read in full. Given that F1–F5 all
  sit in §0a–§3, §4 deserves the same pass — **it is the largest unreviewed surface in the file**,
  and its subject (`ppg`/`ibac_sni`/`ctrl` continuous heads) is the part with no reference
  implementation to check against.
- Whether any archived result was produced under the port's config rather than the clone's. F2
  makes this the highest-value follow-up.
