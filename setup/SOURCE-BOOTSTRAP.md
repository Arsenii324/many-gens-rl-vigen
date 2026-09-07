# Clean source bootstrap

A fresh checkout can reconstruct source trees without copying local `ext/` or
`runnable/*` directories.

```bash
python3 setup/bootstrap_sources.py
python3 setup/verify_sources.py
```

The bootstrap clones public repositories at full commit IDs, checks each
pristine Git tree, applies the tracked adaptation, materializes the current
runtime layout, and verifies normalized source hashes before publication.

Reconstruct one family only:

```bash
python3 setup/bootstrap_sources.py --family idaac
python3 setup/verify_sources.py --family idaac
```

`idaac` also reconstructs its OpenAI Baselines auxiliary source. ALDA moves
its `models` package to `third_party/alda/models`, matching the launcher and
payload contract. Generated logs, results, datasets, checkpoints, and
Places365 are not downloaded.

RL-ViGen has two upstream files whose names differ only by case. Full
reconstruction therefore requires Linux or another case-sensitive filesystem.
The command refuses early on macOS instead of silently dropping one file.

Production remains separate. Native production uses the hash-checked
`rlvigen-door2-90d8b8c4.tgz` input and family payload contracts. Bootstrap does
not submit jobs and does not make production depend on live GitHub access.

The source manifest is `setup/source-reconstruction.json`. The older
`compute/*/PINS.json` files remain identical compatibility inputs for legacy
smoke scripts; tests require their URL and full-commit projection to match the
manifest.

## Known gap found on replay, 2026-09-07 (Claude)

`python setup/verify_sources.py` run against the WORKING tree reports:

    error: wrong source commit at .../runnable/alda

**This is not a provenance problem with alda, and the pin is correct.** The shipped clones under
`runnable/` are project-created SNAPSHOT repositories, not clones of upstream history:
`runnable/alda` contains exactly one commit, `f9609c2`, whose message is

    PRISTINE: ALDA_Official @ 8dcc968, as cloned

So the upstream identity lives in the commit *message*, while `HEAD` is a locally minted SHA that
can never equal the upstream pin. `verify_all` compares `HEAD` to the pin, which is the right check
for a freshly BOOTSTRAPPED tree and the wrong one for a snapshot clone.

Consequences, stated so neither is assumed:

- **The bootstrap path is unaffected.** A fresh `bootstrap_sources.py` clone checks out the pinned
  commit directly, so `HEAD` does equal the pin there. Luna's six-family PASS was against that path.
- **`verify_sources.py` cannot currently be used as a health check on a working checkout**, which is
  the way a new contributor would most naturally reach for it. Either it should detect a snapshot
  repository and verify the recorded pin instead, or it should refuse that input explicitly rather
  than reporting a wrong-commit error that reads like corruption.

Not fixed here: the replay onto current main was kept to a clean cherry-pick, and changing the
verifier's semantics is a decision about what it certifies rather than a defect in the replay.
