# What a review artifact must contain — corrections for the artifact-builder

Written 2026-09-05, from evidence: three external reviews audited an archive of this project, and
the archive's omissions produced **false findings that cost real reviewer effort and nearly cost us
a wrong decision**. This is the spec that prevents a repeat.

## The failure, stated precisely

The archive omitted `.git`, most non-`.py`/`.md` files, and many `.py` files inside the nested
clones. The reviewers behaved correctly given what they saw; the artifact misled them.

| what was omitted | what it caused |
|---|---|
| `.git` | Review 1 **P0 #1**: "the uploaded artifact is not the production repository it describes" — a top-line blocker that is false of the tree. |
| `rlgen/*.py`, `runnable/ibac_sni/*.py` | Same P0, plus Review 1 **P0 #2**: "28 collection errors; the advertised test gate is broken." The real tree has 76 and 72 `.py` files in those trees and the suite has **one** deliberate failure. |
| `families.json`, `production-schedule.json`, `run_probe.sh`, `source-lock.json`, `requirements-native.txt` | Reinforced both P0s and made the production path look absent. |
| the IBAC rollout/PPO sources | Review 1 **#14** could only be raised as "P0 **until verified**" — the single most severe algorithmic charge, which resolved *in our favour* the moment the real files were read (raw action stored and scored; ratio valid). |
| nested loader/transform sources | Review 2 **#15** had to be filed "unproven, not a bug". |
| idaac's env sources | Review 2 **#24** had to be filed "cannot label definitively; verify this", when the tree answers it outright. |

Two of five P0s in the first review, and the severity of a third, were **artifacts of the packaging**.

## The one rule that would have prevented all of it

**Absence must never be indistinguishable from deletion.**

Every reviewer treated a missing file as a missing *file in the project*, because nothing told them
otherwise. That is the correct default when the artifact makes no claim about its own completeness.

**So: ship an exclusion manifest, always.** A short machine-readable file at the archive root
declaring what was left out and why. With it, a reviewer can distinguish "not in the artifact" from
"not in the project", and every false finding above disappears without shipping a byte more code.

    {
      "artifact_built": "<ISO timestamp>",
      "source_commit": "<git rev-parse HEAD>",
      "tree_dirty": true,
      "uncommitted_paths": 48,
      "excluded": [
        {"pattern": ".git/**",            "reason": "history; 200 MB", "present_in_project": true},
        {"pattern": "runnable/*/**",      "reason": "vendored clones, ~200 MB",
         "present_in_project": true, "file_counts": {"runnable/ibac_sni": 76, "rlgen": 72}},
        {"pattern": "**/*.tgz",           "reason": "payload archives", "present_in_project": true}
      ],
      "included_fully": ["docs/**", "scripts/**", "tests/**", "datasphere/native/**"]
    }

`present_in_project: true` is the field that does the work. `file_counts` lets a reviewer see that
`runnable/ibac_sni` has 76 Python files rather than zero, which alone kills Review 1's P0 #1.

## What to include, in priority order

1. **The exclusion manifest above.** Cheapest item here and it prevents the largest class of error.
2. **The commit hash and dirty state.** All three reviews independently raised provenance ("no
   immutable commit meaning the code whose results we report"). That objection is *correct* and
   should survive — but it should be raised from a stated fact, not inferred from a missing `.git`.
3. **Everything under `docs/`, `scripts/`, `tests/`, `datasphere/native/`, `setup/`.** Small, and it
   is where the project's own reasoning lives.
4. **The algorithm sources that carry the claims** — for each baseline, the training loop, the
   policy/model definition, the rollout storage and the evaluator entry point. These are the files
   that decide whether an algorithm is what it says it is. Review 1 #14, Review 2 #7, #8, #24 all
   turned on exactly these, and three of the four could not be answered from the archive.
   Concretely, at minimum: `runnable/*/train*.py`, `**/algos/**.py`, `**/model.py`,
   `**/storage.py`, `**/envs.py`.
5. **Config and descriptor files** — `families.json`, `*.yaml`, `source-lock.json`,
   `requirements-native.txt`. Text, kilobytes, and they define what actually runs.
6. **A test-suite transcript** if the tests themselves are not runnable in the reviewer's
   environment: `pytest -q` output with the pass/fail counts. Review 1 spent a P0 on a broken gate
   that is not broken; one captured transcript answers it.

## What may safely be excluded

Vendored clone bulk beyond the files in (4), `.git` history, `*.tgz` payloads, datasets, images,
checkpoints, `results/records/*` beyond a sample. **All of it must still appear in the manifest.**

## The test that this spec is being followed

Before shipping an artifact, ask: *if the reviewer concludes "this file is missing from the
project", would they be wrong?* If yes, the manifest must say so. That single question is the whole
specification; everything above is its application.

## One thing to preserve

The reviews were more useful than a complete artifact alone would have produced, because each
reviewer was explicit about the limits of what it could see — Review 2 refused to count omitted-file
failures as defects, and Review 3 withdrew its predecessors' claims once given the real-tree triage.
**Ship the manifest so that discipline is aimed at real defects instead of packaging.**
