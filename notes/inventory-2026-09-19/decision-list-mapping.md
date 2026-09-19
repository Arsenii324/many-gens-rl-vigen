> **Executor output, not a finding of record.** Produced 2026-09-20. Maps `scripts/open_decisions.py` and `production_gates.py` against CURRENT-STATE §7b: 87 tool items, 9 hand-listed items, no cross-citation in either direction. Not re-checked by the lead beyond reading the tool output itself.

# Mapping the project's owner-decision lists onto each other

Read-only. Repo: `.../ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen`.
Both reporters run from repo root with `/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python`,
output captured to this folder, ANSI-stripped with `sed -E 's/\x1b\[[0-9;]*[a-zA-Z]//g'`.
Re-run fresh 2026-09-20 per the coordinator's note that the repo moved since the first capture
(host crashed ~21:25 MSK 19 Sep, rebooted 22:05, nothing of ours running now). Diff against the
first capture: `open_decisions.py` output byte-identical in substance (23 decisions, 55 sheet
items); `production_gates.py` moved from "35 pass, 2 fail, 9 owner" to **"36 pass, 1 fail, 9
owner"** — `source tree frozen` flipped FAIL→PASS (tree is clean now); `resolved register holds`
still FAILs. §7b's own text is unchanged in substance from the first read (item 4 already showed
"risk accepted, item closed" both times) — only its line numbers shifted, +15, because content
earlier in the file grew (the new §2 host-crash paragraph). Re-read fresh as instructed; all
citations below use the current line numbers.

## NOT CHECKED / limits

1. I did not read `scripts/requirements.py` end to end — only the `CHECKS` dict wiring and the
   `r6`/`r7` bodies `judgement_requirements()` actually calls. `r1`–`r5` were read only through
   `open_decisions.py`'s own captured output line, not their source.
2. I did not open all 112 rows of `docs/CONSTRUCTION.md`'s register individually — I verified the
   *count* (112 rows, 15 with "your decision") by `grep -c`, and read the specific rows I quote.
3. I did not read `docs/RESEARCH-FRAME.md` and `docs/INTEGRATION-DELTA.md` in full — I ran
   `scripts/decisions.py`'s own `parse()` in a Python one-liner to get its 12 §4 blocks and their
   settled state, and read the one unsettled block (C76) directly for its exact wording.
4. I did not read `notes/DECISION-SHEET.md`'s 55 items' full bodies — only the table-row and
   heading-revision formats (for the copyable format in item 4 of the brief) and a sample of the
   `A1`/`A9`/`A20`/`A35`/`A36` entries used to verify the parser's actual behaviour.
5. The **"ANALYSIS INCOMPLETE" bucket is empty (0 items)** even though `decision_sheet_with_status`'s
   own docstring names A35–A37 as the intended example. Checked directly: `A35`'s heading is
   `### A35 OPEN, 2026-09-06 (analysis completed same entry) — ...` (`notes/DECISION-SHEET.md:1709`)
   — the regex's status group captures `OPEN`, not `ANALYSIS INCOMPLETE` (that phrase appears only
   in prose below the heading, `:1719`, which the regex never reads). This is a factual mismatch
   between the function's documented intent and its current output, reported because it directly
   affects "how many items a source yields," not a claim about which behaviour is correct.
6. **`open_decisions.py --strict` is dead code.** `argparse` declares it (`open_decisions.py:197`)
   and the docstring claims "exit 1 if anything is waiting on ME instead" (`:5`), but the flag is
   never read again anywhere in the file — `main()` always `return 0` (`:250`). Not exercised by
   either capture (neither run used `--strict`), noted because the brief asked for the parsing
   rules exactly as the code has them, not as documented.
7. I did not check `notes/DECISIONS-IF-PRODUCTION-GOES-WRONG.md`'s, `notes/OWNER-DECISIONS-2026-09-08.md`'s,
   or `notes/owner-decisions-recommended.md`'s full bodies against §7b line by line — only their
   headers, dates, superseded markers, and whether the two target scripts reference them (they do
   not; confirmed by `grep` over `scripts/open_decisions.py` and `scripts/production_gates.py`
   finding zero mentions of any of the three filenames).
8. The reverse-direction table (item 3 below) marks §7b-mention status by keyword/topic search over
   the two captured outputs and by grepping §7b's own text for `C\d+`, `A\d+`, `R\d` and gate-name
   phrases — not by re-reading each of the 87 items' surrounding context for an unquoted paraphrase
   that a keyword search would miss. A few PARTLY calls could in principle be undercounted CARRIEDs
   for the same reason noted in the prior sweep.
9. I did not run `pytest tests/` or any other test/verification script — only the two named
   read-only reporters, per the one exception granted.
10. `docs/EVAL-PROTOCOL.md:490`, cited by the current `resolved register holds` FAIL, was not
    separately opened to verify the "does not contain 'A20 decided'" claim; taken as reported by
    the gate itself.

## 1. `scripts/open_decisions.py`'s exact source list

The module docstring (`open_decisions.py:7-24`) claims **four** sources. The code actually reads
**six** distinct files/behaviours; two are not in the docstring's list at all.

| # | Source (file) | Parsing rule (function, file:line) | Excerpt | Items yielded (this capture) |
|---|---|---|---|---|
| 1 | `docs/CONSTRUCTION.md` (register) | `register_items()`, `open_decisions.py:52-64`. Line must start `"| [C"`; splits on `\|`; needs ≥6 cells; `cid = re.match(r"\[(C\d+)\]", cells[1])`; included if `"your decision" in cells[-2].lower()`. | Row format (`docs/CONSTRUCTION.md:112`): `\| [C1](#c1) \| Time-limit handling splits 3 / 9 \| INHERITED + FALSE-CERT \| **OPEN** \| your decision \|` | **15** (of 112 total register rows) |
| 2 | `docs/RESEARCH-FRAME.md` / `docs/INTEGRATION-DELTA.md` (§4 branch points) | `pending_branch_points()`, `:67-72`, delegates to `scripts/decisions.py:parse()` (`BLOCK`/`ROW` regex at `decisions.py:44-46`) and returns entries where `not x["settled"]`; `settled` = Choice cell non-empty AND none of `UNDECIDED_MARKERS` (`decisions.py:110-117`, e.g. `"not made"`, `"the owner's"`, `"pending"`). | Unsettled Choice cell (`docs/RESEARCH-FRAME.md:307`): `\| **Choice** \| **NOT MADE — the owner's.** Recorded as a branch point rather than resolved... \|` | **1** (of 12 total §4 blocks parsed; 11 settled) |
| 3 | `scripts/requirements.py` (`R1`–`R7`) | `judgement_requirements()`, `:74-84`. Calls each `CHECKS[rid]` function; keeps results whose state is `NEEDS JUDGEMENT`, `PARTLY`, or `NOT MET`. | `r6()` (`requirements.py:238-248`): `return ("NEEDS JUDGEMENT" if n == 12 else "NOT MET", ...)`, docstring: "status stays NEEDS JUDGEMENT because choosing that budget is the owner's call" | **4** (R3, R5, R6, R7; R1/R2/R4 are MET, not printed) |
| 4 | `docs/FAITHFULNESS.md` §5 | `fidelity_items()`, `:87-112`. Splits the "## 5. What would raise fidelity most" section on numbered items; drops struck-through (`~~`) or `RESOLVED` items; drops items whose `**Whose:**` annotation contains "mine"; tags the rest `[owner-marked]` if a `**Whose:**` annotation exists at all. | Item with owner tag (`docs/FAITHFULNESS.md:1184,1199`): `9. **Decide the entropy coefficient...` ... `**Whose:** the owner's —` | **3** (items 8, 9, 10; items 1-7, 11 are struck through, resolved, or `mine`) |
| 5 | `docs/REGISTER.md` (findings) — **NOT in the docstring's "four places," and explicitly NOT counted as a decision** | `undispositioned_findings()`, `:119-141`. Row format `\| date \| finding \| locator \| status \| note \|`; keeps rows whose 4th cell (status) lowercases to `"open"`. Docstring (`:122-127`): "Added 2026-09-02... this tool's own disclaimer... was understating the problem." | — | **25** (printed separately, "Not decisions and not counted above") |
| 6 | `notes/DECISION-SHEET.md` — **NOT in the docstring's "four places," added later** | `decision_sheet_with_status()`, `:156-192`. Two passes: (a) table rows `\|\s*\*\*(A\d+)\*\*\s*\|\s*([^|]+?)\s*\|`; (b) heading revisions `^#+\s*(A\d+)\s*([A-Z][A-Z ]*[A-Z])?,?[^\n]*?—\s*([^\n]+)$`, which supersede/append to (a) and can set a status word. Docstring (`:144-152`): "which this script could not see until 2026-09-05... the project had TWO decision surfaces that did not know about each other." | Table row (`notes/DECISION-SHEET.md:20`): `\| **A1** \| Run an IBAC-SNI pilot... \| **Yes — 100k, one seed.**... \| ~1 job-hour \|` | **55** (all in the plain "DECISION SHEET" bucket; the "ANALYSIS INCOMPLETE" bucket the function's own docstring names is currently empty — see NOT CHECKED #5) |

**Total printed as "waiting on a decision": 23** (sources 1-4: 15+1+4+3). Sources 5 and 6 are
printed in the same run but explicitly separated: 25 findings ("not decisions... not counted
above") and 55 sheet items (no separate "N waiting" line of their own — only the bucket header
count). **`notes/DECISION-SHEET.md` A-items ARE read by `open_decisions.py`**, confirmed by source
(`decision_sheet_with_status`, called from `main()` at `:231`) and by the captured output itself
(the "DECISION SHEET" section, 55 rows, `A1`...`A58`).

## 2. The nine §7b items, cross-referenced

`notes/CURRENT-STATE-AND-RESPONSIBILITY.md` §7b, current lines 238-369.

| # | Short title | §7b status (file:line) | In `open_decisions.py`? | In a `production_gates.py` OWNER gate? |
|---|---|---|---|---|
| 1 | Budget vs scope (competence-gate finding) | OPEN — "a research-direction call, not a mechanical one" (`:238-269`) | **INVISIBLE**. Searched `open_decisions.clean.txt` for `competence\|budget vs scope\|600k\|shaped return`: only hits are `A19` (ppg aux cadence at 600k budget) and `A23` (δ, the competence-threshold offset) — different, narrower questions, not this fleet-wide budget-vs-scope call. | **PARTLY**. `OWNER ibac_sni competence` (line 19 of capture): "No exact-final procs=16 V100 competence evidence exists. Needs a pilot..." — this is whether *one baseline's config* has been piloted long enough to prove it *can* learn; §7b item 1 is whether *600k frames is enough, fleet-wide*, given every completed cell already trains but plateaus at ~0 success. Different question, same word. |
| 2 | Vacancy rule on card 0 | Owner answered (partial: scoping only) — "this is future-operator guidance only... not something to operationalise now" (`:270-280`) | **INVISIBLE**. `vacancy\|card 0\|co-tenant`: 0 hits in either capture (179 lines searched total). | **INVISIBLE**. Same search, 0 hits in `production_gates.clean.txt`. |
| 3 | `ppg` seed 1 off-schedule | Owner answered (partial: priority only, not the choice) — "lowest priority — handle last, after everything else" (`:281-288`) | **INVISIBLE**. `seed 1\|off-schedule\|ppg seed`: 0 hits. | **PARTLY**. `OWNER seed policy frozen` (line 24): "operational default is fixed n=3 for every reported row... awaiting formal owner ratification" — the *general* n=3-per-baseline policy, not this baseline-specific "seed 1 reads as MISSING" anomaly. |
| 4 | Upstream-source archive risk | **CLOSED** — "risk accepted, item closed" (`:289-310`), quoting the owner verbatim | **INVISIBLE**. `archive\|backup\|mirror\|upstream-source`: 0 real hits (the two `archive`/`archived` hits in the gates capture are about `audit_environment_drift.py`'s measurement archives and an archived *drqv2 number*, unrelated). | **INVISIBLE**. Same, 0 real hits. |
| 5 | `ctrl` in-loop eval cost | OPEN (recorded as a recommendation, no "Owner's answer" tag) (`:311-323`) | **INVISIBLE**. `in-loop\|eval cost`: 0 hits. | **INVISIBLE**. Same, 0 hits; nearest gate (`v100 schedule matches descriptor`) is PASS and about a different question. |
| 6 | `ctrl` needs an empty card + floor decision | Owner answered (partial: direction only, "the value is not") — "no such card exists, so the floor has to be lowered for `ctrl`" (`:324-338`) | **INVISIBLE**. `empty card\|floor.*ctrl\|4,000 MiB\|4000 MiB`: 0 hits. | **INVISIBLE**. Same, 0 hits — no gate names `ctrl`'s VRAM floor specifically. |
| 7 | Stopped-cell continuation (resume policy) | OPEN, no owner-answer tag (`:339-343`); the closing paragraph (`:368-369`) answers only item 7's *replay-buffer* sub-question, verbally, not the main "may a continued run stand in for a seed" question | **PARTLY**. `resume\|replay buffer`: one hit — a `docs/REGISTER.md` **finding** (2026-09-02, "RL-ViGen resumes automatically and does not save its replay buffer..."), printed in the FINDINGS section, which `open_decisions.py` itself says is "Not decisions and not counted above." Related topic, not a decision item, and not the same question (the finding is about one family's mechanism; §7b item 7 is the fleet-wide policy choice). | **INVISIBLE**. 0 hits. |
| 8 | `build-env.sh` prebuilt environment (O9) | **CLOSED 2026-09-19, no decision needed** (`:344-361`) — turned out to need no decision at all | **INVISIBLE**. `build-env\|O9\|prebuilt`: 0 hits. This item's own history line cites `OPERATOR-GUIDE.md §11.4 O9` — a *third* ledger (`OPERATOR-GUIDE.md`'s own "O-numbered" item list) that neither tool reads at all. | **INVISIBLE**. Same, 0 hits. |
| 9 | Repository public on GitHub, no LICENSE, no CI | OPEN — "Neither is a technical gap; both are policy calls" (`:362-364`) | **INVISIBLE**. `license\|\bCI\b\|github`: 0 hits. | **INVISIBLE**. Same, 0 hits. |

**Summary: 0 of 9 fully VISIBLE, 2 PARTLY (items 1, 3, and a weaker PARTLY on item 7 via the
FINDINGS section, not the decisions section), 6-7 INVISIBLE** depending on whether item 7's
FINDINGS-section hit is counted as PARTLY or INVISIBLE (counted as PARTLY above, since a related
record does exist, just not as a decision).

## 3. The reverse direction — every tool item, and whether §7b mentions it

Checked first at the identifier level: grepped §7b's own text (`sed -n '238,369p'`) for `C[0-9]+`,
`\bA[0-9]+\b`, `\bR[0-9]\b`, and the nine gate-name phrases. Result: **§7b contains exactly one
such token, `C9`** (in item 4's citation `ACCOUNTABILITY.md C9/T1`) — and that `C9` is
**`notes/ACCOUNTABILITY.md`'s own internal numbering, not `docs/CONSTRUCTION.md`'s register**
(`docs/CONSTRUCTION.md`'s actual `C9` is "Reward normalisation in 3 of 12," status `MONITORED`,
unrelated to archive risk — confirmed `docs/CONSTRUCTION.md:120`). **Zero of §7b's tokens match any
of the 87 tool-output items by their tool-native identifier.**

Below, one line per tool item (87 total: 15 register + 1 branch point + 4 requirements + 3
fidelity + 55 sheet + 9 gates), marked by topic as well as identifier since identifier-matching
alone found none:

- **Register (15):** C1, C2, C4, C16, C29, C30, C43, C45, C48, C54, C57, C58, C60, C84, C97 — **none mentioned in §7b** (topics: time-limit handling, frame stack, float precision, W&B key, protocol hash, port-vs-clone contract, retention, scene count, RL-ViGen reproduction, checkpoint distribution, NaN divergence, training-data records, checkpoint cadence, drq policy collapse, ctrl parameter match — none overlap §7b's 9 topics).
- **Branch point (1):** C76 (P-C76, retention endpoint) — **not mentioned in §7b**.
- **Requirements (4):** R3, R5, R6, R7 — **none mentioned in §7b**.
- **Fidelity (3):** §5 item 8 (CTRL no independent verification), item 9 (PPO entropy coefficient), item 10 (ctrl/ppg checkpoint-as-published) — **none mentioned in §7b**.
- **Decision sheet (55):** A1-A58 (with gaps) — **none mentioned in §7b by tag**. Topically closest: **A19** (ppg aux cadence at 600k) and **A23** (competence-threshold offset δ) sit near §7b item 1's territory without being the same question or being cited; **A6** ("Seed policy") sits near §7b item 3 without being cited. All other 52 are on distinct topics (production canary, evaluator validation sequencing, Places365 split, per-baseline hyperparameter corrections, etc.) with no §7b overlap at all.
- **Owner gates (9):** `ibac_sni competence` (topically adjacent to §7b item 1, not cited), `estimands frozen`, `seed policy frozen` (topically adjacent to §7b item 3, not cited), `environment manifest`, `production canary`, `external RL-ViGen anchor`, `checkpoint rule frozen`, `production renderer verified`, `production scope frozen` — **none cited by name in §7b**; 7 of the 9 have no topical relation to any §7b item at all.

**Count of tool items §7b does not mention: 87 of 87** (0 cited by identifier; 3 are topically
adjacent without citation — A19/A23/ibac_sni-competence to item 1, A6/seed-policy-frozen to item 3
— everything else, including all 15 register items, the branch point, all 4 requirements, all 3
fidelity items, and 52 of 55 sheet items, has no relationship to §7b at all).

## 4. Copyable formats for the INVISIBLE §7b items

Given only the format an existing row uses — no drafted rows, no recommendation on which source fits best.

- **Items 2, 3, 5, 6, 7, 9** (vacancy rule, ppg seed-1, ctrl eval cost, ctrl floor, resume policy,
  license/CI) have **no existing register entry at all**, so the only route into
  `open_decisions.py` without adding a new source to the script itself is a **`docs/CONSTRUCTION.md`
  register row**, whose decision column must literally contain the substring `your decision`
  (case-insensitive), e.g. copying the exact shape of `docs/CONSTRUCTION.md:112`:
  `| [C<n>](#c<n>) | <one-line summary> | <origin tag, e.g. INHERITED/OURS/UNDECLARED> | **OPEN** | your decision |`
- Alternatively, any of the six could be written as a **`notes/DECISION-SHEET.md` row**, whose
  format (`register_items` is not involved here; `decision_sheet_with_status` is) is a markdown
  table row with the tag bolded in the first cell, matching `notes/DECISION-SHEET.md:20`:
  `| **A<n>** | <the question> | <recommended default> | <cost if agreed> |`
  — or, to carry a status word the way `A35` does, a heading matching
  `notes/DECISION-SHEET.md:1709`'s shape: `### A<n> <STATUS-WORD>, <date> — <one-line summary>`
  (the regex requires the status word to be `[A-Z][A-Z ]*[A-Z]`, i.e. all-caps with internal spaces
  allowed, immediately after the tag).
- A **§4 branch-point block** (the format `pending_branch_points()` reads) requires the exact table
  shown at `docs/RESEARCH-FRAME.md:303-307`: a bolded title line, then a two-column table headed
  `| §4 field | |`, with rows `| **Structural property...** | ... |`, `| **What the target actually
  offers** | ... |`, `| **Options** | ... |`, `| **Choice** | ... |`, `| **What would show the
  choice was wrong** | ... |` — and the Choice cell must contain one of `UNDECIDED_MARKERS`
  (`decisions.py:110-117`: `not yet made`, `not made`, `undecided`, `not decided`, `open`,
  `deferred`, `the owner's`, `owner's to make`, `pending`) to register as pending rather than
  settled, matching `docs/RESEARCH-FRAME.md:310`'s exact wording `**NOT MADE — the owner's.**`.
  This format is a much heavier lift than a register row or sheet row for a one-off host/ops
  decision (it is designed for a *reference's mechanism* argument, per `decisions.py`'s own
  `WANT` dict) — stated as fact about the format's shape, not a recommendation to use it.
- **Item 1** (budget vs scope) and **item 4** (already CLOSED) are not being asked about here since
  item 1 is PARTLY not INVISIBLE and item 4 is closed.
- **Item 8** (build-env.sh, O9) is closed, but for the record: its native ledger is
  `OPERATOR-GUIDE.md` §11.4's own O-numbered item list, which is a **fourth, uncounted format**
  neither `open_decisions.py` nor `production_gates.py` reads at all (not checked further — outside
  the two-source system this task maps).

## 5. The other owner-decision documents

| Document | Date | Declares itself superseded? | Read by `open_decisions.py` or `production_gates.py`? |
|---|---|---|---|
| `notes/DECISION-SHEET.md` | "Written 2026-09-05" (`:2`) | Not as a whole document. Individual lines are: e.g. `:108` "**A3 superseded by your steer** — report everything; the headline is provisional." | **Yes** — `open_decisions.py` (`decision_sheet_with_status`, confirmed above). Not read by `production_gates.py` (`grep -n "DECISION-SHEET" scripts/production_gates.py` → 0 hits). |
| `notes/OWNER-DECISIONS-2026-09-08.md` | "Written 2026-09-08" (`:3`) | No — `grep -in "superseded\|archived" notes/OWNER-DECISIONS-2026-09-08.md` → 0 hits. | **No** — 0 hits for the filename in either script's source. |
| `notes/owner-decisions-recommended.md` | Header dated "2026-09-06" wrapping an unedited "2026-09-05" document below it (`:1,3`) | Partially, in named sections only: `:1` "It is **not** superseded wholesale"; `:42` "...is superseded by CORRECTIONS #97/`C96`..."; `:238` "### §3c superseded — retention is demoted below a *difference*." | **No** — 0 hits for the filename in either script's source. |
| `notes/DECISIONS-IF-PRODUCTION-GOES-WRONG.md` (the fourth) | First commit 2026-09-07; content dated through "2026-09-08" (`:27`, `:178`) | Partially, in one section: `:221` "**Superseded.** This section used to record the judgement that `ctrl` and `ibac_sni` stay at `frame_stack=1`..." | **No** by either target script (0 hits for the filename in `open_decisions.py`/`production_gates.py`). Referenced only in *other* scripts' comments — `scripts/audit_job_budgets.py:222`, `scripts/read_stack_pilot.py:9,213`, `scripts/watch_policy_health.py:22` — as a citation of its reasoning, not a read of its content. Organized 1:1 around production_gates.py's "Nine gates read OWNER" framing (its own opening line), but the two files are not wired together. |

`notes/START-HERE.md:67-81` names its own "one surface" for decisions as of 2026-09-05:
`DECISION-SHEET.md` + `python scripts/open_decisions.py` + `owner-decisions-recommended.md` (for
reasoning) — it does **not** list `OWNER-DECISIONS-2026-09-08.md` or
`DECISIONS-IF-PRODUCTION-GOES-WRONG.md` at all, both written after that "one surface" note was
last touched by that section's own date stamp.
