# Raw subagent outputs — verbatim, unedited

**Do not edit these files.** Each is one subagent's report exactly as it was returned, preserved
before any synthesis, so that the synthesized documents one directory up can always be checked
against what was actually said.

Nothing here has been merged, reconciled, trimmed, or re-verified. Two of these files cover the
same four libraries and disagree in places; that disagreement is information and is preserved
rather than resolved. Claims marked `UNVERIFIED` are the reports' own admissions.

| file | job | landed |
|---|---|---|
| `broad-sweep-14-libraries.md` | SKRL, SB3 + sb3-contrib + Zoo + sbx, Tianshou, jaxrl/jaxrl2/jaxrl_m, CleanRL, PureJaxRL, Brax, Acme, Dopamine, Pearl, Mushroom-RL, garage, AgileRL | 2026-08-17 |
| `cleanrl.md` | CleanRL as a fidelity reference for PPG and the other baselines | 2026-08-17 |
| `pearl-dopamine-acme-mushroom-run1.md` | Pearl / Dopamine / Acme / Mushroom-RL, first pass | 2026-08-17 |
| `pearl-dopamine-acme-mushroom-run2.md` | Pearl / Dopamine / Acme / Mushroom-RL, second pass | 2026-08-17 |
| `torchrl.md` | TorchRL (`pytorch/rl`) in depth — coverage, fidelity, the join question, heads, metrics, robosuite | 2026-08-17 |
| `pytorch-ecosystem-agy.md` | torchtune / torchforge / torchbeast / PyTorch recipes (agy, `gemini-3.6-flash-high`) | 2026-08-17 |
| `_brief-given-to-jobs.md` | the shared brief every job above was handed, so their answers can be read against what was actually asked | — |

A fifth job from the same batch — a blind recovery of this project's *own* past findings — is a
different subject and lives at `docs/audit-crosscheck/raw/past-findings-crosscheck.md`.

**The TorchRL sweep landed 2026-08-17 and is in `torchrl.md`.** It is the most consequential file
here: it is the only report that went looking for *evidence about the consequences of sharing*
rather than for feature coverage, and it found roughly twenty cited instances in which a shared
component silently changed an algorithm's numbers in the field's flagship modular library.

Note that `broad-sweep-14-libraries.md` and `pearl-dopamine-acme-mushroom-run{1,2}.md` overlap on
four libraries and were produced independently. That is three readings of the same four repos.
They are all kept.

**Where run1 and run2 actually differ**, having compared them line by line — so nobody has to
redo it, and so "they disagree" is a checkable statement rather than a caveat:

- run2 alone quotes Dopamine's `docs/README.md:213-217` — *"we decided to keep a relatively flat
  class hierarchy, with no abstract base class… we recommend modifying the agent code directly"*
  — which is the most on-point design quote in either file.
- run2 alone reports Dopamine's `PPOActorNetwork` state-independent log_std (`scale_diag` fed a
  constant input, `kernel_init=zeros`, commented *"state independent and initialized to zero"*),
  which is direct precedent for our four authored heads.
- run2 alone reads Mushroom-RL's `Core.learn()` as one shared trainer every algorithm runs
  through, and draws the consequence: a quirk in `Core` is shared across every algorithm's
  numbers.
- run1 alone carries the fuller Acme cross-check — the complete `acme/agents/jax/` listing and
  the `docs/user/agents.md` table confirming DrQ/DrQ-v2 were never promoted to documented agents.
- run1 alone calls Dopamine's per-agent file layout *"closer to the group's own
  duplication-friendly null hypothesis than to a fully modular actor/learner split."*

They agree on every coverage verdict, which is the load-bearing claim. They differ in what each
happened to extract. Neither supersedes the other, and the divergence is a useful measure of how
much one subagent pass can be expected to miss.
