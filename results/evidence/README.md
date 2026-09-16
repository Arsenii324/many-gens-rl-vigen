# Evidence bundles

A claim here keeps its evidence **in the repository**. The alternative is a pointer to a host log
that will be reclaimed. Each bundle answers one question and holds everything needed to check the
answer without re-running anything:

| file | what it is |
|---|---|
| `CLAIM.md` | the argument. It has four required sections: Status, Chain, What this does not show, and Falsifier. It cites facts as `fact:<key>` and excerpts as `raw/<name>.txt` |
| `capture.sh` | the recipe. Running it again re-takes every excerpt; it refuses if a source is gone |
| `manifest.json` | per excerpt: source (host path, size, mtime, SHA-256; or repo file hash; or command plus hashes of the repo files it names), the exact extraction command, matched and shown line counts, and the excerpt's own hash. It also lists the **facts**, each bound to an anchor substring |
| `raw/<name>.txt` | the verbatim excerpt, headed by its provenance |

## Index

| bundle | question | status |
|---|---|---|
| [ppg-nminibatch-declared-32-executed-1](ppg-nminibatch-declared-32-executed-1/CLAIM.md) | ppg declared `--nminibatch 32`. What executed, and is the executed run faithful? | resolved (policy phase) |
| [evaluator-run-to-run-noise-ppg](evaluator-run-to-run-noise-ppg/CLAIM.md) | Re-evaluating the same ppg checkpoint gave a different mean. Changed estimand, or evaluator noise? | resolved (noise, 0.095 SE; placements identical, actions differ) |
| [ppg-600k-rows-bind-to-host-weights](ppg-600k-rows-bind-to-host-weights/CLAIM.md) | Do the 616 committed ppg 600k rows name the weights the run saved, at the right stamps? Do the curve end and the endpoint read the same model? | resolved (all bound; same tensors, different files) |
| [idaac-600k-endpoint-binds-to-host-weights](idaac-600k-endpoint-binds-to-host-weights/CLAIM.md) | Which of four host idaac snapshots do the 88 committed endpoint rows evaluate? Did that run finish? Are all regimes and modes covered? | resolved (card0-20260909-035152; 598,016; 11 per regime and mode) |
| [ppg-aux-phase-8-minibatches-per-epoch](ppg-aux-phase-8-minibatches-per-epoch/CLAIM.md) | What auxiliary-phase geometry does production PPG execute, against Table A.1 and both release configurations? | resolved (geometry); consequence traced |

## Finding something

- **By question:** use the index above. Each bundle is also cited from its row in
  `docs/resolved-register.json`.
- **By number:** `grep -r '"value": "293"' results/evidence/*/manifest.json` finds the fact and
  its excerpt. `grep -rn 'IC=600064' results/evidence/*/raw/` finds the raw line.
- **By source:** `grep -l 'card0-20260909-115331' results/evidence/*/manifest.json` lists every
  bundle that quotes that run.

## Checking

```bash
pytest tests/test_evidence_bundles_hold.py        # hashes, anchors, headers, claim-to-fact links
python scripts/recheck_evidence.py                # are the sources still there, unchanged?
python scripts/recheck_evidence.py --local-only   # without contacting the host
```

The test checks that the evidence is intact and that the claim cites only recorded facts. It
cannot check that the reasoning is right. That is what "What this does not show" and "Falsifier"
are for.

`recheck_evidence.py` reports each source as one of:

- `SAME`: unchanged.
- `DRIFT`: the source changed. The excerpt still shows what it said at capture time.
- `GONE`: the excerpt is now the only copy.
- `INPUTS`: the repo files a command names have changed.
- `HEAD`: a command with no named inputs.

## Adding a bundle

1. Write `capture.sh` first, one `C $S <name> ...` line per excerpt (copy an existing one). Use:
   - `--host-path '~/...'` in single quotes, so the local shell does not expand `~`;
   - `--local-path` for repo files;
   - `--command` for git history, PDF text, or a probe's output.
   Cut each source with `--grep` or `--lines A:B`. Both print source line numbers.
2. Bind every number the claim will use: `--fact key=value --anchor 'text in the excerpt'`. An
   anchor with a `header:` prefix is looked up in the provenance header instead of the body, e.g.
   `header:# matched-lines: 293 `. Keep the trailing space so 293 cannot match 2930.
3. **Absence is evidence too.** Use `--allow-empty` with `--anchor 'header:# matched-lines: 0 '`.
   The tool runs the source command alone first, so a failing command cannot pass as "no
   matches".
   For long lines such as JSON rows, add `--only-matching` to keep only the matched fields.
   A capture can read excerpts already taken, e.g. `--command "sed '1,/^#---/d' raw/a.txt"`.
   That is how a diff or a recomputation over captured data becomes evidence itself.
4. Run `bash results/evidence/<slug>/capture.sh`. Write `CLAIM.md`. Add the bundle to the index
   above. Cite its `raw/` lines from the register row, with `evidence_expect`.

### Rules the tool enforces

- **Host commands.** On the host it runs `test`, `stat`, `sha256sum`, `cat`, `grep`, `sed`, `head`,
  `wc` and `tar`, and nothing else: no python, no writes.
- **Anchors.** A fact whose anchor is not in its excerpt is refused at capture time and again in
  the test. The body/header split exists because the header quotes the grep pattern, and an
  anchor must not be "found" in the command that searched for it.
- **Truncation.** A capped excerpt says `TRUNCATED`, and `matched-lines` is always the full count.
- **Removing an excerpt** means deleting `raw/<name>.txt`, its `manifest.json` entry and its
  facts, and its line in `capture.sh`. The test fails while any of the three disagree.
- **No loops in `capture.sh`.** Every excerpt name must appear literally as `C $S <name> `, so the
  test can prove each excerpt is re-takeable. Write repeated captures out in full.
