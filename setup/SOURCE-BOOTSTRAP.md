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