# State at the pause, 2026-09-10

Work paused here by the owner for ~24h. This records what is true at the pause so resumption does
not begin by re-deriving it. Everything below was verified in the last hour, not recalled.

## Tree

Clean at `2e01cb4`. Gates: **35 pass, 1 fail, 10 owner**. The single FAIL was
`source tree frozen` on my own uncommitted files and is closed by that commit — re-run
`scripts/production_gates.py` to confirm rather than trusting this line.

## Attestation wave v212 — 5/7

Validated on their CURRENT closures: `rlvigen`, `idaac`, `alda`, `ppg`, `ibac_sni`.

Outstanding:

- **`dmc_gb` (soda)** — was mid-run at the last observation (`S:2000/10000`). No
  `attest-v212-dmc_gb__records.jsonl` exists yet, so it had not been collected. Collect with
  `datasphere/native/collect-wave.sh`, which REFUSES a non-SUCCESS job rather than skipping it.
- **`ctrl`** — refused by `populate_evaluator_ledger.py`, correctly. Its cause is the one row in
  `docs/RESOLVED-REGISTER.md` still marked `traced`, not `resolved`: the lead is **GPU architecture
  (sm_70)**, not a package version. The jaxlib pin was my misdiagnosis and is reverted; do not
  re-pin it. `jax[cuda12] 0.4.35 depends on jaxlib==0.4.34` is upstream's intended pairing, and
  pinning 0.4.35 makes ctrl uninstallable (`ResolutionImpossible`).
  The queued probe `~/rlvigen-work/run-volta-probe-when-free.sh` is what tests the sm_70
  hypothesis; it had not reported at the pause.

## What changed this session, and the one thing to carry forward

`docs/RESOLVED-REGISTER.md` now exists and is indexed from `START-HERE.md` §5 and gated by
`gate_resolved_register_holds`. Read it before re-deriving a settled question.

The finding worth carrying: **a revert has two halves.** `production-schedule-v100.json` was left
describing a `families.json` that no longer existed, because the artifact was regenerated while the
jaxlib pin was live and never re-synced after the revert. `git status` was clean and the source
diff was empty — every source-level check called the revert complete. Only running the generator
disagreed. When a revert touches anything a generator reads, re-run the generator comparison
(`production_gates.py`, or `plan_production.py --host-profile v100 --sync-schedule`), because git
cannot see the generated half.

## Not done, deliberately

Nothing was launched at the pause, and nothing new was started after the owner's message. No
container was created, deleted or left orphaned by this last stretch.
