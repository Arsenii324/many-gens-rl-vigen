# Open questions from the owner, and what followed from each

Not a yes/no list. Each row records what the question actually turned up, because several of them
turned up something other than their own answer — three overturned a change I had already written
down, and one overturned a change I had already made.

Status: OPEN / ANSWERED / **REVERSED** (the question showed my position was wrong).

---

## Answered, with what followed

**"Why the procs=1? I'm very sure there was a way that was advocated for."** — REVERSED, twice.
First reading: base `procs` is stale, raise to 16. Wrong: `resources.json` shows `gt4.1` has 4
logical CPUs and `gt4i.1` has 8. Second reading: the `v100` override to 16 is unverified. Also
wrong: `notes/remote-infra.txt` is a captured session from the production host showing `nproc` 16,
and the competence pilot was already scheduled in the runbook and in `production_gates.py`. What
remains is one line of stale prose. **Followed from it:** the habit of declaring something
unexamined that the project had already examined — which then recurred twice more.

**"The project's prose might be stale in some sources."** — ANSWERED, and it was the most
productive question asked. It led to the docs sweep, which found `docs/FAITHFULNESS.md` has not
been touched since 2026-09-05 and is stale on **every** numeric claim about the on-policy four
(idaac's gamma/rollout/lr/num_processes, ppg's num_envs/lr, the frame-stack split, ctrl's cluster
count). Thirteen findings, four rated MISLEADING.

**"How could reward normalization have existed in none? It could have."** — REVERSED. Twelve review
files discuss it and review 2 gives it a numbered section. My committed text was accurate; three
conversational retellings had inflated it. Recorded as a memory.

**"Do the subagents differentiate between prod and not, and read docs like this?"** — REVERSED, and
it changed the sweep's output. My briefs never mentioned `host_profiles`, so both source-reading
agents were resolving BASE values and reporting them as production. Corrected mid-run; agent A
re-ran and its revised report overturned my change-plan item 3.

**"Is it already time to run svea? Do we not have changes incoming?"** — ANSWERED: no, and the
question was right. Four findings would have voided it. **Followed from it:** holding the run
exposed that the wave is 3 cells rather than 7, once the `families.json` edits were withdrawn.

**"Would it still run 3h? How can this be a thing just for a mock run?"** — ANSWERED, and the
number was wrong. `cfg-sgqn-cover-v197` is the same family, same overlay path, same 10000 frames,
same tier, same hour: SUCCESS in **2381s**. An rlvigen attest cell is a 40-minute job. Timeout cut
from 7800s to 3600s. **Followed from it:** the 7800s v197 svea cell spent ~1200s working and ~6600s
hung after a crash, which produced the stall watchdog.

**"What are the actual things that change learning, not just scaffold?"** — ANSWERED: two.
`ibac_sni`'s policy-head init, and the step-0 evaluation's RNG consumption. Everything else on my
list was declaration, prose, instrumentation or integrity. **Followed from it:** the list was
mostly paperwork and had been presented as though it weren't.

**"Is the policy-head init a real bottleneck?"** — ANSWERED, quantitatively. Inverting the measured
clip rate (sigma 1.027 from its own `log_std`, then solving the two-sided clip probability) puts
the initial |mean| at **0.818** on a [-1, 1] action space — 82% of the way to the bound before a
gradient step. Not slight. Changed.

**"Do we have the git-repo creation ready?"** — ANSWERED, and it surfaced something not asked
about: **the GitHub repo is PUBLIC**, 985 files including 91 `notes/` files, against CLAUDE.md's
"private by default for anything uploaded". Left for the owner; the command is in the chat.

**"What's rlvigen and is it even relevant?"** — ANSWERED: a family, not an algorithm — drqv2, svea,
sgqn, curl, drq share one payload and evaluator. **Followed from it:** my "not one shared DrQ-v2
backbone" claim was weaker than presented. `docs/COMPARABILITY_CONTRACT.md:254` already enumerates
the three encoder classes per file and line, and `docs/FAITHFULNESS.md:326` already records SVEA's.
Only the repr_dim numbers were unwritten.

**"Are you sure the terminal save fails?"** — REVERSED in framing. I have **not** observed a
failure. `safe_write` returns False on three paths and never raises, by design; `ctrl`'s
`_save_state` had no `return` at all, so its terminal caller could not check it. That is a
fail-open path verified in source, not an observed failure, and I described it as though it had
fired. All seven families were traced: five already fail-closed under Q18(b), ctrl and ppg were
not, and the exclusion appears nowhere in the 247-file prose corpus.

**"Research not just some claims but all."** — ANSWERED by instrument, not by reading: a corpus
check over all 247 prose files for every claim the four agents raised. Most were already recorded.
Genuinely absent from the entire corpus: ALDA's `AdamW(weight_decay=0.1)` on the trunk both actor
and critic read (zero hits for either term), the SAC families' two-speed `encoder_tau=0.05`, and
idaac's `--eps` labelled RMSprop while configuring Adam. All three are faithful upstream behaviour
— disclosures, not changes.

## Reversed by the question, in full

**The ctrl inert-constants change.** I added six flags to `ctrl.options` and then reverted them.
`tests/test_every_constant_reaches_the_process.py` already exempts exactly those six, with a second
test that reads `train_ppo.py` and fails the moment a declared value stops matching the default.
Simulated A45's proposed `lr_ctrl` edit against it: the test fails, which is the silent no-op I had
claimed it missed. Reverting kept `families.json` untouched, which is why the wave is 3 cells.

## Still open

- **`docs/FAITHFULNESS.md` rewrite.** Agent E's recommendation is to regenerate it from
  `families.json`/`protocol.py` outward rather than patch it. Not blocking a run.
- **Disclosures** for the three genuinely-unrecorded facts above.
- **The `ibac_sni` init at length.** Measured at 10k frames on a near-untrained policy. The
  production competence pilot is where it is actually tested.
- **Everything host-side**: renderer parity, ctrl 64-env memory, ibac_sni `procs=16` competence,
  Places365 full asset, the ~45 h `soda` canary (`notes/PRODUCTION-RUNBOOK.md:90`).
