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

## Snapshot-repo verification, closed 2026-09-07

`runnable/` ships project-created SNAPSHOT repositories, not clones of upstream history:
`runnable/alda`, for instance, contains exactly one commit, `f9609c2`, whose message is

    PRISTINE: ALDA_Official @ 8dcc968, as cloned

so the upstream identity lives in the commit *message*, while `HEAD` is a locally minted SHA that
never equals the upstream pin. `verify_sources.py` used to compare `HEAD` to the pin only, which is
correct for a freshly bootstrapped tree but rejected every snapshot clone with a "wrong source
commit" error that read like corruption.

`bootstrap_sources.py::_verify_destination` now accepts a matching `HEAD^{tree}` when `HEAD`
differs from the pinned commit -- tree equality is as strong a content proof as commit equality for
a repo whose only divergence is its locally-authored HEAD commit -- and skips git-identity checks
entirely when the destination carries no `.git` of its own (a destination without its own `.git`
was otherwise checked, via `git -C`'s walk-up behaviour, against *this* project's HEAD). The
closure-hash check runs unconditionally either way, so content is still proven in every case.

`python setup/verify_sources.py` therefore runs cleanly against both a fresh `bootstrap_sources.py`
checkout and the shipped snapshot repositories under `runnable/`. RL-ViGen remains the one family
`verify_all` cannot verify on a case-insensitive filesystem (see above); it is reported by name as
`NOT VERIFIED HERE` rather than as a hash mismatch.
