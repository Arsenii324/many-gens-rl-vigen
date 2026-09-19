> **Executor output, not a finding of record.** Produced 2026-09-19 by a read-only Sonnet executor (four parallel forks) over the 206 owner messages of 16–19 Sep, extracted mechanically from the session transcript. It searched a FIXED file set (47 files) and cannot see Claude Code auto-memory, so a NOT FOUND means "not in those files". Re-checked by the lead with repo-wide greps over 231 files: the `ppg` rollout-quantum ruling, "do not stop healthy cells", "no-yield is not a right policy" and the `varaksin_as`-home-only scope are confirmed absent as rulings and were added to CURRENT-STATE §4 the same evening. The remaining NOT FOUND / PARTIAL rows are NOT yet triaged.

# Owner statement sweep — M1288–M1493 (16–19 Sep 2026)

Read-only. Repository: `/Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen`.
Source: `owner-messages-0916-0919.md`, 206 messages (M1288–M1493, fully contiguous, no gaps).
Method calibrated first against the coordinator's three known answers — all three reproduced
correctly (see the coordinator's feedback and Counts §e). Work was fanned out to four parallel
forks (M1288–1339, M1340–1391, M1392–1443, M1444–1493), each doing full per-message extraction and
repo classification against the same required file set; this file merges their four outputs and
adds a cross-batch reconciliation pass.

## (a) NOT CHECKED / limits

1. **CARRIED/PARTIAL/NOT FOUND searches were restricted to the 9 required files/globs**
   (`CLAUDE.md`, `notes/CURRENT-STATE-AND-RESPONSIBILITY.md`, `notes/ACCOUNTABILITY.md`,
   `notes/OPERATOR-GUIDE.md`, `notes/HANDOFF.md`, `notes/production-host/*.md` [39 files],
   `docs/EVAL-PROTOCOL.md`, `docs/RESEARCH-FRAME.md`, `notes/DECISION-SHEET.md` — 47 files total).
   Several items marked NOT FOUND or PARTIAL here were confirmed (by the sweep itself, as an aside)
   to be fully CARRIED just outside this set — e.g. the `$MG` env var lives in
   `notes/one-offs/CODEX-FOUNDATION-2-SESSION-LOG.md` and `notes/METRIC-INVENTORY-VERDICT-2026-09-05.md`;
   the seven-family online-eval table lives in `notes/FINDING-online-eval-per-family.md`; the
   doc-surfaces index is `notes/START-HERE.md` itself (only referenced, not searched, since it is
   not in the required list). This is the single largest source of "gaps" below — many are gaps in
   the *required 9-file scope*, not gaps in the repo as a whole.
2. **I did not personally re-run every one of the ~91 individual classification judgments** against
   the live files. I spot-checked the three calibration examples (all reproduced exactly) plus a
   handful of cross-cutting facts myself directly (ppg 50k/100k cadence, absence of any
   "continue autonomously" text in the required set, `$MG` absence in the required set), and read
   all four batch outputs in full for internal consistency, but the bulk of the ~47-file × ~83-statement
   grep work was done by the four forks, not re-verified line-by-line by me.
3. **"Messages with a durable statement" totals use slightly inconsistent per-fork conventions**
   for queue-duplicate messages (fold into "no durable statement" vs. count as "has content, no new
   statement"). This affects only that one summary number, not the CARRIED/PARTIAL/NOT FOUND/SUPERSEDED
   totals, which count each underlying statement once regardless of how many messages restate it.
4. **SUPERSEDED was checked exhaustively within each batch's own ~50-message range**; I additionally
   read across all four batches myself once, looking for a later message reversing an earlier
   statement from a *different* batch, and found none — but this cross-batch pass was a single
   read-through, not a pairwise check of all ~83 statements against all 206 messages.
5. **A few multi-part owner messages (e.g. M1425, M1464) produced more classification sub-judgments
   than the "distinct statements" tally counts**, because several sub-points in one message were
   each classified separately. Batch 3 flagged this explicitly; batch 4 shows the same arithmetic
   pattern (CARRIED+PARTIAL+NOT FOUND exceeds the distinct-statement count) without flagging it —
   both are correct at the sub-point level; only the top-line "distinct statements" count undercounts
   sub-points relative to the CARRIED/PARTIAL/NOT FOUND/SUPERSEDED totals actually assigned.
6. **`<cross-session-message>` blocks (a peer Claude fork, not the owner) and harness-injected
   boilerplate** (Stop-hook confirmations at M1290, permission-laundering policy text repeated after
   every peer message, usage-limit-reset notices) were excluded from scoring as owner statements
   throughout. This is a judgment call consistently applied, not something the task instructions
   spelled out verbatim.
7. **M1386** references a file outside this repository
   (`~/build-projs/ccm-intro/docs/anthropic-prompting.md`) — marked NOT CHECKED rather than searched.
8. **PARTIAL classifications rest on `grep` keyword passes**, not a full read of every candidate
   `production-host/*.md` file for paraphrased (non-keyword-matching) coverage. A few PARTIALs could
   be undercounted CARRIEDs if the carrying sentence uses different wording than the grep pattern
   tried.
9. **Timestamps**: message headers are UTC; several message bodies reference MSK times. Not
   reconciled since no classification depended on the distinction.
10. **M1480 and M1487/M1488** contain large blocks of pasted material about a *different* project
    (Fable/Sonnet "advisor pattern" dialogue). Only the owner's own framing sentences around those
    blocks were extracted, per instructions; the pasted content itself was read (to identify the
    boundary) but not scored.

## (b) Per-message extraction and classification

### Batch 1 (M1288–M1339)

**M1288** (08:52 turn) — "Why did you go sleep? I'd assume you'd have a recurrent monitor locally forever" → standing expectation: a recurrent local monitor should always run. Search: `recurrent monitor|monitor.*forever|local.*monitor` over the 47 required files → 0 hits. **NOT FOUND.**

**M1289** (08:53 mid-turn) — Goal-hook text: "Optimally utilize the provided communal host's resources for the highest-impact results till the deadline... Work no less than till 9:00 with active monitoring (ensure you don't sleep for a long time) and don't stop on 9:00 unless objective circumstance." Recurs verbatim at M1296, M1306, M1347 (flagged as duplicates below). Search: `deadline is soft|work no less than till 9|don't stop on 9` → 0 hits. **NOT FOUND** (a session Stop-hook condition, not obviously doc-shaped content, but searched as specified regardless).

**M1290** (08:53 turn) — Hook-system boilerplate confirming M1289. Not owner-typed. `M1290: no durable statement (system/hook boilerplate)`

**M1291** — "I wonder if the environment's own backgrounding capability helps." Speculative aside. `M1291: no durable statement`

**M1292** — "/loop This is a reminder to keep prod in check." Standing preference for recurring prod checks. Search: `keep prod in check` → 0 hits. **NOT FOUND** (slash-command usage pattern, not doc-shaped content).

**M1293** — "Is compute use optimal? Continue." Routine check-in. `M1293: no durable statement`

**M1294** — "Wait. Did we kill any of the others' containers on the remote?" Standing concern: never harm another user's containers. **PARTIAL** — `notes/production-host/04-resource-safety.md:8` carries the general principle ("No action of ours may cause another process to fail") but not this specific incident-check as a standing gate.

**M1295** — "yeah oom or cuda oom would be bad" → **CARRIED** — `notes/production-host/04-resource-safety.md:8` ("No action of ours may cause another process to fail. Not an OOM kill, not a CUDA OOM..."); also `notes/production-host/06-before-any-action.md:23` ("CUDA OOM, ours or theirs").

**M1296** — duplicate of M1289 (queue artifact), no new content.

**M1297** — "How are we? Continue." `M1297: no durable statement`

**M1298** — "Continue autonomously. The user is away and won't accept an intermediate response/report or ask questions." Recurs near-verbatim across the whole corpus (M1303, M1337, M1365/66, M1422, M1439, M1457/8/68, etc.). Search: `user is away|won't accept an intermediate|continue autonomously` → 0 hits. **NOT FOUND** in any of the 47 required files.

**M1299** — "/fork ...note it down. Design the proper way to have it retrievable, approachable, workable by you... Note down the whole evidence; a random claim can be wrong or false." Standing preference: durable notes must be structured/retrievable and evidence-backed, not bare claims. **PARTIAL** — the general evidentiary principle exists project-wide (e.g. `docs/RIGOR.md`, outside the required set: "A claim needs evidence produced by a procedure that could have produced the opposite claim"), but no required file states the "retrievable, not just noted" framing itself.

**M1300** — Harness explanation of fork/SendMessage mechanics. `M1300: no durable statement (harness text)`

**M1301, M1302** — turn-scoped, no durable content.

**M1303** — duplicate of M1298.

**M1304, M1305, M1308, M1318–M1320, M1322–M1323, M1326** — `<cross-session-message>` blocks from a peer fork. Not owner's words. `no durable statement (peer/fork message)` for each.

**M1306** — duplicate of M1289.

**M1307** — "Why do they hold both cards? Did we yield own cards or did we have none and they could have taken?" Question, see Questions list.

**M1309, M1321** — peer message + harness permission-laundering boilerplate (repeated verbatim). Not owner-authored.

**M1310** — "Was card 0 really always taken?" routine question.

**M1311** — "Now when ours is booked, you'd rather have less automatic yields if anything. Have a close monitor... If any card is free for one of our runs, please try take." **PARTIAL** — `notes/production-host/33-what-we-actually-have-2026-09-16.md:141-153` directly engages this exact tension with a *later, refined* finding: "A card that just became free is not a free card... Declining to launch was the higher-value action, and that is the opposite of what 'use the free card' suggests." Reported PARTIAL because the literal instruction is revised by the doc's own later measurement, not carried as stated. (See Contradictions.)

**M1312** — "I mean not an on-host you'd not read; the one that'd actually report to you." Search: `report to|reports to you` → 0 hits. **NOT FOUND.**

**M1313** — "we could use even less [margin] couldn't we. Due to limited compute, really use the most out of it." **PARTIAL / in tension** — `notes/production-host/04-resource-safety.md` and `10-resource-upper-bound-rule.md` instead emphasize leaving headroom, never running near a bound. Tension not resolved anywhere. (See Contradictions.)

**M1314** — "Make sure the monitor command actually works, e.g. try test it with setting different margins... before setting on it as the long running one." Search: `test.*monitor|margins` → 0 hits. **NOT FOUND.**

**M1315–M1317** — "What's the next runs you would run anyway? Eval, train, of what? Seeds?" Question thread, see Questions list.

**M1324** — "colleague could e.g. restart theirs work on card 1. SO don't be super-taking everything on it... maybe not interfere?" **PARTIAL** — co-tenancy is a major theme (`16-host-work-log.md:171`, `17-first-real-cell-plan.md:65` — an earlier, more permissive owner ruling: "slowing a co-tenant is acceptable; the memory half is not"), but this specific 09-16 refinement is not itself stated in the required set.

**M1325** — "'no-yield' isn't a right policy I think." Search: `no-yield|yield polic` → 0 hits. **NOT FOUND** for the explicit ruling (OOM-bad-regardless-of-whose half is covered by the M1295 citation).

**M1327** — "Does this fork even still work... Do we have our work on github pushed? ... operator's guide is old/stale now?" Questions, see Questions list.

**M1328, M1329** — "Please do a full effort... starting from the operator's guide... Polish it at your best." Standing directive (comprehensive operator-guide effort), not project-domain content — **NOT FOUND** as literal text (expected; this is an instruction about how to work).

**M1330** — "What's on card one btw?" routine question.

**M1331, M1332** — "You're too early to 'write authoritatively'... treat the current version as a draft... don't 'just write the guide'... Did you REWRITE the operator's guide? ... neither take it as authoritative... nor scrap it." **NOT FOUND** — `notes/OPERATOR-GUIDE.md` contains no self-declared "draft, not authoritative" caveat; it reads as finished throughout.

**M1333** — "make a system through which all concerns... would be explicitly route to success." Search: `route to success|is a system\b` → 0 hits. **NOT FOUND.**

**M1334** — "Don't commit to 'it's done' early; really don't." **PARTIAL** — `notes/ACCOUNTABILITY.md`'s whole-document theme ("An item moves to DONE only with a short report of how it is done and what verified it") carries the spirit, not this specific 09-16 admonition.

**M1335** — (a) "Place definitions before usage of words/terms... to ensure there's a real 'start' to read from." Search: `definitions before usage|first-hand context` → 0 hits. **NOT FOUND.**
(b) FACT: "In every shell, MG is set to .../many-gens-rl-vigen automatically and it will never change; you can use the alias." Search: `MG=|\$MG\b` over the 47 required files → 0 hits. **NOT FOUND in the required set** (exists outside it: `notes/METRIC-INVENTORY-VERDICT-2026-09-05.md:11`, `notes/one-offs/CODEX-FOUNDATION-2-SESSION-LOG.md:11733` — neither is a required file, and `CLAUDE.md` itself never mentions `$MG`).

**M1336** — same theme as M1333/M1335(a).

**M1337** — comprehensive self-driven verification directive; instruction about how to work, not searched.

**M1338** — "Neither 'reuse' or 'integrate' by default, nor duplicate randomly... don't have the operator's set truncated." Search: `duplicate randomly|default.*reuse` → 0 hits. **NOT FOUND.**

**M1339** — "don't treat the 'gaps' narrowly... Discovery, planning and multi-step research and understanding are to be before." Search: `treat.*gaps narrowly|discovery.*before` → 0 hits. **NOT FOUND.**

### Batch 2 (M1340–M1391)

**M1340** — "If the project has a flaw that made the discovery worthy, you can fix it, naturally, leanly and without harm." **PARTIAL** — `CLAUDE.md:125` carries "leanly" only re: the superpowers plugin, not this permission-to-fix-flaws statement. Ran `leanly|without harm` over all 9 required files — no line states this standing permission.

**M1341–M1343** — routine continue/status, one question thread (co-tenancy unmanageable?), see Questions.

**M1344** — "let's assume this part is not to be overformalized but would be left as, like, 'places365 in format ... should reside at ...' at its core" → **CARRIED**. `notes/OPERATOR-GUIDE.md:501` gives exactly this plain form (`PLACES365_DIR=...`) under "5.3 Launching a Places365 baseline."

**M1345, M1346** — context-tied, not independently durable.

**M1347** — duplicate of M1289 (batch 1).

**M1348, M1349, M1350** — status/correction-seeking questions, see Questions.

**M1351, M1352** — "/loop 30min How's prod?..." Standing ~30-min check-in cadence. **NOT FOUND** — `30.min|30-min|every 30 minutes` over 40 files: all hits are unrelated measurement narratives (e.g. `production-host/17-first-real-cell-plan.md:197`), no standing monitoring-cadence policy recorded.

**M1353, M1354** — loop firings, no new content beyond M1351.

**M1355** — system-generated usage-limit-reset notice, not owner-typed.

**M1356, M1357** — status questions.

**M1358, M1359** — "Assume a new operator would run the whole thing e2e on host without having access to you... Flesh out this path at all parts... [not] just the readme and 2-3 'most interesting' scripts... nor just scatter attention across random scripts without fleshing out the integration between them." → **CARRIED**. `notes/OPERATOR-GUIDE.md:2069-2080` (its own opening): "This file is the **map**: what exists, what produces what, what runs after what, and which tool belongs to which stage."

**M1360** — "Yeah, don't be stopping health cells. Continue" Standing ruling: don't stop health/monitor cells. **NOT FOUND** — `health.cell|health-check|don't stop.*health|stand.down|stood down` over 40 files: no such standing rule recorded (reads as an in-the-moment correction).

**M1361–M1363** — status questions.

**M1364** — "do we have some local residual files... Answer, don't delete, and continue normally." → **CARRIED**. `notes/ACCOUNTABILITY.md:78` (row C1): "'Do we have local residual files that take a lot of space? Answer, don't delete' | DONE (answered) | Deletion of the scratchpad clonetest (287 MB) postponed until the user returns, as allowed." Near-verbatim.

**M1365, M1366** — "Don't delete things; you can delete ones that are 100% not useful but you can also postpone it till user returns." → **CARRIED**, same citation as M1364.

**M1367** — "are we ready for the operator? If you explicitly place a boundary of what you've tested, and what not and why" → **CARRIED**. `notes/OPERATOR-GUIDE.md:518` ("**What is still untested**, stated so it is not discovered at hour nine") and `:973`.

**M1368–M1370** — "the tools you actually used are real trusted and debugged, but realistically, operator tools are only proposed?... put the things you're actually sure in, not a random layer of... untested scripts." **PARTIAL** — `OPERATOR-GUIDE.md` §5.2 is explicitly "copied from the sessions that ran it on 2026-09-16/17," and Places365 is marked untested (M1367's citation), but no single line states "prefer actually-run practice over untested proposed layers" as a general editorial rule — followed in practice, not asserted as a rule.

**M1371, M1372** — status questions.

**M1373** — no durable statement.

**M1374** — "is the operator's thing super good e2e for all practical purposes? If not, make it so." → **CARRIED** as the same standing goal as M1358/M1381.

**M1375** — no durable statement.

**M1376** — "do you not have a monitor checking prod just in case compute drops?... don't run things too early on it just in case the free part is transient, but don't make you not notice it without a reminder from my side." **PARTIAL** — waiters/monitors are extensively documented in `notes/CURRENT-STATE-AND-RESPONSIBILITY.md` (lines 28, 61, 226-229, 307-308), but this specific caution/non-silent-miss trade-off is not itself stated as a policy.

**M1377** — "Do we have all evals finished... Why is ibac_sni unrecoverable?" Questions.

**M1378** — "Are you sure we DO NOT checkpoint optimizer state?" (recurring theme, see Questions and later batches). Plus rulings: → **CARRIED** (harm/OOM): `notes/production-host/04-resource-safety.md:8`, reinforced `notes/OPERATOR-GUIDE.md:617` ("never CUDA OOM, including other people's jobs"). → **CARRIED** (off-golden-path): `notes/OPERATOR-GUIDE.md:916` ("### 10.4 Off the golden path"). → **PARTIAL** (ground claims in actually-used practice): see M1368–1370.

**M1379** — "Why do you not use project-wide docs? Do we not have them?" Question — `notes/START-HERE.md` is the actual project-wide index but is outside the required file list.

**M1380** — no durable statement.

**M1381** — "if something remains out of reach (like Places365 download-checking does...), catalogize all, narrow each to the isolated part, and leave a clean label for the operator." → **CARRIED** (Places365 specifically): `notes/OPERATOR-GUIDE.md:1011` ("**Places365 on the host.** The ~24 GB corpus has never been placed there") + `:1028` ("**O1**... **CLOSED 2026-09-18 10:50**" — see Contradictions/timing note). **PARTIAL** (the general "clean label for every out-of-reach item" mechanism): done ad hoc per item, not as a declared system.

**M1382** — origin of the ACCOUNTABILITY.md mechanism: "You can make an accountability.md doc where you have the taskset noted down and once it's done, you make a slight report on how it's already done..." → **CARRIED, precisely**. `notes/ACCOUNTABILITY.md:1-6` and independently `CLAUDE.md` under "## Keeping a multi-part request whole," explicitly tagged "(Owner's suggestion, 2026-09-17.)"

**M1383, M1384** — "Use superpowers plugin... use leanly... extract just the helpful bits... If not needed to use, you could skip it." → **CARRIED**. `CLAUDE.md:123-127`: "The superpowers plugin skills... are optional and best used leanly... take what helps... or skip them."

**M1385** — "Record this in the project's frame setting doc... one should not dump prose of thoughts there or place overly decisive local claims... without narrowing it prematurely to a locked-in decision." → **CARRIED**. `CLAUDE.md`'s "## Keeping a multi-part request whole" section is framed as "Considerations to weigh against the request in front of you, not a procedure."

**M1386** — references `~/build-projs/ccm-intro/docs/anthropic-prompting.md` — **NOT CHECKED** (outside repo/scope).

**M1387** — question, no independent content.

**M1388** — "We have places365 on the host don't we?" — factual assumption. See Contradictions (timing mismatch, resolved same day).

**M1389** — question.

**M1390, M1391** — "which of these are not needed? Bring up candidates; then for each review critically if it should be in fact kept." **PARTIAL** — `notes/ACCOUNTABILITY.md` tracks disk items generally (C1) but this specific 66 GB candidate-review process is not documented as a completed/tracked row in the narrow set searched.

### Batch 3 (M1392–M1443)

**M1392** — "if we had both tar and untarred version there, we rather delete one of the two." → **CARRIED** — `notes/ACCOUNTABILITY.md:296` (row T4): "Whether 'delete one of tar/untarred if we have both' was ever acted on. Checked, closed with an honest limit."

**M1393** — "we did try to mount Places365 through the shared-mount folder. Are you sure it's not there?" **NOT FOUND** — `shared-mount|shared mount` over all 47 required files: 0 hits.

**M1394** — "wrap up; I'll tell to plan (separately), compact context and switch to Sonnet." **NOT FOUND** — session-scoped/ephemeral by nature; `Sonnet|compact` over `notes/HANDOFF.md notes/CURRENT-STATE-AND-RESPONSIBILITY.md notes/ACCOUNTABILITY.md` gives only self-referential hits.

**M1395** — "'not just home' I meant only the varaksin_as user folder." **NOT FOUND** — the username itself is documented (`production-host/00-authority-and-scope.md:9`), but this narrow disk-check-scope point is not distinguished from the broader privacy rule anywhere.

**M1396** — recurring status question, see Questions.

**M1397** — wants "mechanisms... that would allow the operator to understand and/or fix problems." → **CARRIED** — `notes/OPERATOR-GUIDE.md:119` table header: "stage | target state | artifact (exact path) | consumer | proves it worked | redo only this stage | does NOT leave."

**M1398, M1399** — "'any host but cds2' no won't happen; if the operator does it it's their problem." → **CARRIED** — `notes/ACCOUNTABILITY.md:186-187` (C5). Matches the coordinator's calibration example exactly.

**M1400, M1401, M1403, M1406, M1408** — slash-command/routine, no durable content.

**M1402** — "Do we really need it? Would we not rather instruct the operator to do this thing?" **PARTIAL** — "instruct the operator" pattern is pervasive, but the general principle ("prefer instructing over automating") is not itself stated as a rule.

**M1404, M1405, M1412, M1413** — HOST RULE: "not to install anything on the host globally... All when a library is needed should only be done through dockers." → **CARRIED** — `notes/production-host/02-absolute-prohibitions.md:9,11,15` and `03-docker-discipline.md`.

**M1407** — underspecified nuance, folded into Questions.

**M1409–M1411** — status questions.

**M1414** — "Are we too high on swap memory thrashing (real use)?" **NOT FOUND** — `swap` over all 47 required files: 0 hits.

**M1415, M1416, M1417** — status questions.

**M1418** — "How does the proposed (operator-bundle-specific) stuff relate with the concrete stuff... you remember using?" **PARTIAL** — `OPERATOR-GUIDE.md` grounds itself in real practice (§5.2 "copied from the sessions that ran it") but no line states the reconciliation as a checked claim.

**M1419** — "Do we checkpoint optimizers? What will take disk space?... Does it reuse same 'mount directory' practice as ours?" → **CARRIED** (optimizer question) — `notes/OPERATOR-GUIDE.md:656-661` per-baseline table (e.g. "`ppg` | ...the optimizers are not on it"; "`rlvigen` | ...and their Adam optimizers... | **automatic**"). Other sub-questions CARRIED generally in `OPERATOR-GUIDE.md`, not re-verified line by line.

**M1420** — "How would the operator know to use the tooling... at a cold start?" → **CARRIED** — `OPERATOR-GUIDE.md` opening: "You are here because you have this repository and a production host, and nothing else... Read this once, top to bottom, before running anything."

**M1421** — checkpoint frequency → **CARRIED** (`notes/ACCOUNTABILITY.md:254-261`, `OPERATOR-GUIDE.md:645`); disk-floor-too-harsh → **PARTIAL** (see M1430); online-eval-default → **PARTIAL** (`ACCOUNTABILITY.md:262-263` covers `ctrl` only within the required set; the full 7-family table is in `FINDING-online-eval-per-family.md`, outside scope).

**M1422** — "Keep your efforts accountable" → **CARRIED** — existence/structure of `notes/ACCOUNTABILITY.md` itself.

**M1423** — end-to-end rigorous validation directive → **CARRIED as an ongoing practice** (dated entries through 2026-09-19 in both `OPERATOR-GUIDE.md` and `ACCOUNTABILITY.md`; no single "complete" line, correctly, since the campaign was still running).

**M1424** — "A) remaining holes... B) is everything beyond them super-ready" → **CARRIED** (the mechanism) — `OPERATOR-GUIDE.md:1024`: "Each entry names **the part** that is missing, **why** it has not been done, **the target state**."

**M1425** — disk-floor-too-harsh concern → **CARRIED** — `OPERATOR-GUIDE.md:623-629` names the exact scenario and the lever (`NATIVE_DISK_ALLOWANCE_GIB`). Notification-channel question → **PARTIAL**. ppg-50k question → **CARRIED** (M1426). automatic=manual-eval question → **NOT FOUND** (`automatic.*eval.*manual|manual.*eval.*same` over 47 files: 0 hits).

**M1426, M1432, M1436, M1437** — "Are you very sure ppg isn't each 50k?... where was it embedded in code" → **CARRIED**, unusually completely. `notes/ACCOUNTABILITY.md:254-261`: records the AI being wrong twice ("100,000, never overridden" then "neither 50k nor 100k") before confirming `--ic_per_save 50000` from the real executed argv.

**M1427** — "the runs' descriptions can be confident and look right, but in fact be quite obscure." **PARTIAL** — the workspace-root `CLAUDE.md` (one level up, outside this project's own `CLAUDE.md`) carries "checkpoint's saved args outrank the README, the README outranks the prose" generally; this project's own `CLAUDE.md` doesn't restate it, though `ACCOUNTABILITY.md`'s practice (M1426) demonstrably follows it.

**M1428, M1441** — "we had an index of the layers/'surfaces' but I don't remember where." → **CARRIED** — `notes/CURRENT-STATE-AND-RESPONSIBILITY.md:6`: "`START-HERE.md` indexes what each surface is *for*." "Two repo copies" fact → **NOT FOUND** — `native-recovery|recovery-workspace` over all 47 required files: 0 hits; none of the required docs name the sibling tree or the fork/recovery relationship.

**M1429** — "Be very careful and make sure the deletion command resolves properly with all screening... special signs." **PARTIAL** — the episode's outcome is recorded (`ACCOUNTABILITY.md:296`), the general standing rule (verify deletion-command resolution before running) is not stated as a reusable principle.

**M1430** — "some operator might want to soften the disk or yield bounds" (single-cell case) → **CARRIED**, same citation as M1425. Multi-run-at-once variant ("I launch 4 runs... halt unresumable") → **PARTIAL**, not separately spelled out.

**M1431, M1433** — questions, see Questions list.

**M1434** — "'the endpoint grid itself is 96s end-to-end' what's 96s? I don't believe 96s" → **CARRIED** — `notes/production-host/37-what-a-cell-actually-costs-in-wall-clock.md:4,11,15`: "Written after giving the owner a wrong number with false confidence ('the endpoint grid is 96s end to end') and being pushed to check it."

**M1435** — "any auto-stopping... should be very very obvious and explicit to the operator." → **CARRIED** — `OPERATOR-GUIDE.md:607`, "6b.1 Every auto-stop, with its knob, in one place," table follows.

**M1436, M1443** — eval-vs-train time questions → **CARRIED** (the "roughly double" fact) — `production-host/28-eval-is-sixty-percent-of-a-cell.md:17` and `37-*.md:32`. The specific x6/x12-checkpoint-count mechanism question → **NOT FOUND**.

**M1438** — "the ppg rollout quantum is different and shouldn't be changed unless I explicitly say later." **NOT FOUND** as a standing constraint — `ACCOUNTABILITY.md:261` explains what the quantum *is*, not a do-not-touch-without-permission rule.

**M1439, M1440, M1442** — recurring boilerplate / meta-question / owner-OKs-existing-practice; no independent content beyond what's covered elsewhere.

### Batch 4 (M1444–M1493)

**M1444** — "Are you sure in the 'push' mechanism?... is it really really handled with the push?" **PARTIAL** — no row addresses push-reliability for entangled/gitignored/patched code specifically in the 9 assigned files.

**M1445** — ACCOUNTABILITY reference → **CARRIED**, same citation as M1382.

**M1446, M1447** — repo-hygiene concern (gitignored/patched code). **PARTIAL** — mechanism documented in `docs/ORIGINAL_LOCATIONS.md`/`docs/RUNNABLE-ORIGINALS.md` (outside scope); the "is push safe for this" claim is not checked in any of the 9 assigned files.

**M1448** — doubt about doc-surface mapping (`START-HERE.md` vs `production-host/README.md`). **PARTIAL** — resolved by the owner's own later message (M1455), not by any doc; `grep -rln "scientific fidelity" notes/production-host/README.md` → 0 hits, consistent with the owner's suspicion.

**M1449** — question, see Questions.

**M1450** — "it feels process-oriented not result-oriented." **NOT FOUND** — `result-oriented|process-oriented` over `CLAUDE.md notes/ACCOUNTABILITY.md notes/HANDOFF.md`: 0 hits.

**M1451** — "hierarchy of passing arguments... a file of 'clean model'?" **NOT FOUND** — `hierarchy of passing arguments|argument hierarchy|clean model` over 5 files: 0 hits (no dedicated precedence-order file in the assigned set).

**M1452** — thoroughness/entangled-control-flow preference. **PARTIAL** — echoed in `ACCOUNTABILITY.md`'s general standard, not stated as its own rule.

**M1453, M1454** — duplicate concerns, route to ACCOUNTABILITY.md.

**M1455** — ACCOUNTABILITY reference (duplicate) + resolves M1448.

**M1456** — monitor-noise preference probe. **NOT FOUND** — `report nothing|monitor.*quiet|monitor.*noise` over `notes/production-host/*.md notes/CURRENT-STATE-AND-RESPONSIBILITY.md`: 0 hits.

**M1457, M1458, M1459, M1460, M1461, M1462, M1463** — reinforcements of the ACCOUNTABILITY/standing-concerns mechanism → **CARRIED**, same citation as M1445.

**M1464** — '4' local-copy-backup → **CARRIED**, `notes/CURRENT-STATE-AND-RESPONSIBILITY.md:245-246` (coordinator's calibration example, reproduced independently). '5' run-time-arithmetic question → NOT FOUND, see Questions. '6' lower-floor-for-ctrl → **CARRIED**, `notes/CURRENT-STATE-AND-RESPONSIBILITY.md:276`. '7' optimizer/buffer question → **NOT FOUND** across 5 files. '8'/'9' clarification/ack, no content.

**M1465** — generalizes the cds2 ruling to "external/blocked" items broadly. **PARTIAL** — `ACCOUNTABILITY.md:186-187` (C5) carries the specific cds2 instance; the general principle is not written as a standing rule.

**M1466** — question, see Questions.

**M1467** — rl4vla/co-tenant future-guidance → **CARRIED**, `notes/CURRENT-STATE-AND-RESPONSIBILITY.md:225-229` (near-exact match). ppg seed-set `{1,102,103}` → **CARRIED**, `notes/CURRENT-STATE-AND-RESPONSIBILITY.md:232` (near-verbatim); priority nuance ("have it done latest... slight reproducibility but slight") → **PARTIAL**, not captured. ctrl in-loop eval cost question → see Questions.

**M1468** — "main researcher and the holder of the frame... don't go overboard with blanket operations." **NOT FOUND** — `main researcher|holder of the frame|blanket operation` over 6 files: 0 real hits (one false-positive on an unrelated `fork()` mention).

**M1469** — leanness-vs-understanding balance. **PARTIAL** — ACCOUNTABILITY mechanism itself CARRIED; this specific balance not stated. `grep -n "lean" notes/ACCOUNTABILITY.md` → 0 hits.

**M1470** — "not doing the heavy-results decisions for me like big deletes, big runs." **NOT FOUND** — `big delet|heavy-results|super-unintended|unintended consequence` over 41 files: 0 hits (consistent in spirit with the already-CARRIED container/image deletion rule, but this broader boundary is not itself written down).

**M1471, M1472** — rl4vla/co-tenant half → **CARRIED**, same as M1467. "deletion/rm fine if careful" / "non-decisions vs decisions" clarification → **NOT FOUND**, same grep as M1470.

**M1473** — no durable statement.

**M1474** — "if [monitors] could need to rearm, you can." **NOT FOUND** as written permission — `rearm` over 40 files: 0 hits.

**M1475** — "Recognize the list of surfaces... Be very thorough and rigorous." **PARTIAL** — `notes/HANDOFF.md:1-9` states the compaction-survival purpose functionally but not this exact rule.

**M1476** — "use an actual big handoff doc... don't [place assumptions] as if they were the ground truth." → **CARRIED** — `notes/HANDOFF.md:1858-1862`: "Marked throughout: VERIFIED... vs WRITTEN-NOT-COMMITTED... vs PLAN/ASSUMPTION (my own reasoning or intention, not a fact — do not treat as settled)."

**M1477** — question, see Questions.

**M1478** — "What's the payload size btw?" **NOT FOUND** — `payload size|payload.*MB|payload.*GB` over 5 files: 0 hits.

**M1479** — "owner-facing questions" ledger expectation. **PARTIAL** — `owner-facing` appears in 0 of the 9 files; content partially present in `notes/DECISION-SHEET.md` / `CURRENT-STATE-AND-RESPONSIBILITY.md` §7b, just not labelled that way.

**M1480** — mostly out-of-scope pasted material about a different project (see NOT CHECKED item 10). Owner's own framing: "we're the two who work on the project; host security is important" → **PARTIAL** (host security extensively CARRIED in `production-host/*.md`; the self-conception framing itself is NOT FOUND, same grep as M1468). "only act once the project structure is understood" → **NOT FOUND**.

**M1481** — directive, no new content.

**M1482** — "be more foundational and careful... not diving implementation-first." **NOT FOUND** — `step back|fresh view|foundational` over 4 files: 0 hits.

**M1483, M1484** — Claude Code subagent-workflow meta-questions, out of project-doc scope.

**M1485** — full-autonomy-expectation question, answered only by the Stop-hook goal text (M1289), a session mechanism not a repo doc.

**M1486** — "Why did you not note the things I noted... until I asked directly?" **NOT FOUND** as a distinct written rule beyond the general ACCOUNTABILITY mechanism.

**M1487** — Sonnet-subagent-trust concern. **PARTIAL** — `CLAUDE.md:122-127` carries "superpowers, used leanly" (from M1383/84) but not this specific asserting-vs-verifying trust concern; `ACCOUNTABILITY.md:6` ("Written is not verified") is close in spirit but about task-closure generally.

**M1488** — wrapper only ("another Fable wrote this, but it was another project"); pasted content excluded. No durable statement for this project.

**M1489, M1490, M1491, M1492** — questions, see Questions list.

**M1493** — no durable statement.

## (c) Questions (all batches; substantive owner questions and repo-answer status)

| Msg | Question | Repo answer? |
|---|---|---|
| M1294 | Did we kill any of the others' containers on the remote? | No standing incident-log answer in the required set. |
| M1307 | Why do they hold both cards? Did we yield own cards? | Not answered as a standing fact in the required set. |
| M1310 | Was card 0 really always taken? | Not found. |
| M1315–17 | What's the next runs? Eval, train, of what? Seeds? | Not answered as a standing 09-16 plan in the required set. |
| M1327 | Is the fork still running? Work pushed to github? Guide stale? | Not found (push status is a `git log` fact, not doc-carried). |
| M1330 | What's on card one? | Point-in-time, no standing answer expected. |
| M1342/43 | Is co-tenancy unmanageable on both GPUs? Does the peer fork still need to run? | Not found in the 9 required files. |
| M1344 | Is the ctrl 4000 MiB floor pessimistic — could it be 0? | Floor value documented; the "could it be 0" question not found. |
| M1348 | What do you report as fully finished? | No single line; likely chat-only. |
| M1350 | "expires every 30 minutes" — why? | Not found. |
| M1363 | Can `ibac_sni` s102 attempt 2 restart, or only partial? | Not found in the 9 required files. |
| M1377 | Why is `ibac_sni` unrecoverable? | Not found. |
| M1378/1419/1421/1464/1467 | Do we checkpoint optimizer state? Does off-policy save its buffer? | **Yes** for the "do we checkpoint" half — `notes/OPERATOR-GUIDE.md:656-661`; the buffer-discard sub-question — NOT FOUND. |
| M1379 | Why do you not use project-wide docs? | `notes/START-HERE.md` is the actual index but is outside the required scope. |
| M1388 | We have Places365 on the host don't we? | No at the time (`OPERATOR-GUIDE.md:1011`), resolved same day (`:1028`). |
| M1393 | Was Places365 mounted via the shared-mount folder already? | Not found. |
| M1396/1417/1423/1431/1457/1461 | Is the operator package/version super-ready? | Answered as an ongoing, dated practice, never as a single "done" line (correctly, since work continued). |
| M1414 | Are we too high on swap/thrashing? | Not found — "swap" absent from the required set entirely. |
| M1421/1425/1431 | Does online eval run by default for idaac/ctrl? | Partial — `ACCOUNTABILITY.md:262-263` covers ctrl only in-scope; full 7-family table is outside scope. |
| M1425/1433 | Are automatic after-train eval and manual re-eval the same mechanism? | Not found. |
| M1428/1441 | Is there an index of doc "surfaces"? | **Yes** — `notes/CURRENT-STATE-AND-RESPONSIBILITY.md:6` → `START-HERE.md`. |
| M1436/1443 | Is eval really ~2x training time, and why (x6/x12 mechanism)? | The "what" — yes (`production-host/28`, `/37`); the per-checkpoint mechanism — not found. |
| M1444/1446 | Is the git-push mechanism sorted out for entangled/patched code? | Not found in the 9 required files. |
| M1449 | If ctrl runs "every step" online eval and also has an endpoint grid, are we good? | Not found. |
| M1451/1453 | What's the argument-passing hierarchy? Is there a "clean model" file for it? | Not found — no dedicated precedence file in scope. |
| M1464'5' | Was x3-seeds + x2-eval = x5 the calculated expected run time? | Not found verbatim in scope (arithmetic exists in `PRODUCTION-CALENDAR.md`, outside scope). |
| M1466 | Is it a special "only ever build the superset" policy? | Not found. |
| M1467 | What's best for ctrl in-loop eval cost? | Not found as a settled recommendation. |
| M1477 | Was everything written to the handoff, not other docs? | Both `HANDOFF.md` and `CURRENT-STATE-AND-RESPONSIBILITY.md` were actively updated 2026-09-19; no line explicitly answers the "also needed?" framing. |
| M1478 | What's the payload size? | Not found. |
| M1483 | Sonnet subagent bounded-investigation / persistent-reuse patterns? | Out of project-doc scope (Claude Code workflow, not a project fact). |
| M1489/90/91/92 | Are owner-facing items delayed pending understanding? What's the task list and its order? | `ACCOUNTABILITY.md` is the designated surface; whether it holds this *specific* ordering requires reading its live contents, not a static grep. |

## (d) Contradictions

1. **M1313** ("Due to limited compute, really use the most out of it" — tighten resource margins) vs. **`notes/production-host/10-resource-upper-bound-rule.md`** (title thesis: "If you do not know an upper bound on the resources you will occupy, do not run it") and **`04-resource-safety.md:8`** (leave headroom). Direct tension, unreconciled in either document.
2. **M1311** ("If any card is free for one of our runs, please try take") vs. **`notes/production-host/33-what-we-actually-have-2026-09-16.md:141-153`** ("A card that just became free is not a free card... Declining to launch was the higher-value action, and that is the opposite of what 'use the free card' suggests"). Reads as a later, measurement-grounded refinement rather than a disagreement with the owner, but the document itself frames it as "the opposite of" the naive instruction.
3. **M1388** ("We have places365 on the host don't we?", 2026-09-18 06:38) vs. **`notes/OPERATOR-GUIDE.md:1011`** ("The ~24 GB corpus has never been placed there"). Not a standing contradiction — `:1028` shows the gap was closed the same day at 10:50, after the owner's question. Flagged as a timing mismatch, not a doc defect.

No further contradictions were found in batches 3 or 4; several apparent conflicts (e.g. M1464'6' "lower the floor" vs. the general "no room means wait, never lower a floor" rule at `notes/CURRENT-STATE-AND-RESPONSIBILITY.md:144`) were checked and found to be correctly-scoped exceptions stated in the same document (`:278`: "a lowered floor only makes sense on a card with no co-tenant"), not reversals.

## (e) Counts

- **Messages covered: 206 of 206** (M1288–M1493, every id appears in §b).
- **Messages with durable content** (self-reported per batch, conventions differ slightly on duplicates — see NOT CHECKED item 3): batch 1 = 22/52, batch 2 = 34/52, batch 3 = 24/52, batch 4 = 27/50 → **107/206 (52%)**.
- **Distinct durable statements/claims extracted**: 22 + 21 + 21 + 19 = **83** (a few multi-part messages split into more sub-judgments than this top-line count — see NOT CHECKED item 5).
- **Classification totals** (sub-point-level; sums to more than 83 because some statements split into sub-parts each classified separately):
  - **CARRIED: 32** (batch 1: 2, batch 2: 11, batch 3: 13, batch 4: 6)
  - **PARTIAL: 24** (6, 5, 5, 8)
  - **NOT FOUND: 34** (14, 4, 7, 9)
  - **SUPERSEDED: 0** (checked within every batch and once across all four in a merge pass — none found)
  - **NOT CHECKED (as its own outcome, not a limits note): 1** (M1386, references a file outside the repo)
- **Calibration check**: the coordinator's three known answers were reproduced independently by this sweep — cds2/operator's-problem (M1398/99, batch 3) → CARRIED, `notes/ACCOUNTABILITY.md:186-187`; local-copy-backup (M1464'4', batch 4) → CARRIED, `notes/CURRENT-STATE-AND-RESPONSIBILITY.md:245-246`; never-delete-container-without-proof → CARRIED, `notes/production-host/09-standing-cautions.md:19-20` (verified directly by the coordinating pass before forking, not independently re-found by a specific message in this corpus since no message in M1288–M1493 restates that particular rule).
- **Contradictions found: 3** (2 standing/unreconciled, 1 timing-mismatch already resolved same day).
