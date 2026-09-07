# External-review artifact blueprint

Status: blueprint plus implemented source-review builder. This file defines the review contract;
`scripts/build_external_review_artifact.py` now implements its core directory, provenance,
selection, exclusion, symlink, and privacy rules. It is not an artifact, does not freeze the tree,
and does not authorize a remote run.

The artifact has two review labels and must never blur them:

- **SOURCE-FIDELITY REVIEW NOW**: whether each active baseline is the method it claims to be,
  what the primary paper/source actually specifies, and whether the current port is an exact
  match, a contextual variant, an adaptation, a conflict, or unspecified. This can be reviewed
  from source/configuration/reference material before production jobs.
- **FINAL PRODUCTION-READINESS REVIEW LATER**: whether the frozen payload, effective commands,
  host/runtime, checkpoints, delivery records, evaluation outputs, seeds, resource envelope, and
  final report justify production claims. This label cannot be promoted by source inspection.

The external reviewer is permitted to ingest a large machine-readable directory. The builder must
therefore preserve raw relevant evidence and navigation metadata, not replace source with a short
narrative or a context-sized excerpt.

## 1. Artifact contract

The deliverable is a directory, not a single archive. A zip/tar may be made later as a transport
copy, but the directory and its manifests are authoritative.

```text
many-gens-rl-vigen-review/
├── README-ARTIFACT.md
├── artifact-manifest.json
├── included-files.jsonl
├── excluded-files.jsonl
├── symlinks.jsonl
├── source-status.porcelain-v1.txt
├── source-provenance.json
├── review/
│   ├── prompt.md
│   ├── question-index.jsonl
│   ├── response-schema.json
│   ├── response-template.jsonl
│   ├── phase-map.json
│   └── reading-order.json
├── effective-config/
│   ├── README.md
│   ├── planned-source-resolution.json
│   ├── source-environment.json
│   └── final-run-capture/README.md
├── source-closure/
│   ├── README.md
│   ├── closure-index.json
│   ├── rlvigen.json
│   ├── dmc_gb.json
│   ├── idaac.json
│   ├── alda.json
│   ├── ppg.json
│   ├── ibac_sni.json
│   └── ctrl.json
├── reference/
│   ├── primary-source-index.json
│   ├── papers/...
│   ├── supplements/...
│   └── official-source/...
├── project/
│   ├── README.md
│   ├── instruction.md
│   ├── HANDOFF.md
│   ├── docs/**
│   ├── scripts/**
│   ├── tests/**
│   ├── datasphere/native/**
│   ├── setup/**
│   ├── runnable/**
│   ├── RL-ViGen-upstream/**
│   ├── rlgen/**
│   ├── third_party/**
│   ├── ext/**                 # relevant original sources/references only
│   ├── baselines/**
│   ├── configs/**
│   ├── compute/**
│   ├── tools/**
│   ├── mutants/**
│   └── research/**
└── results/
    ├── README.md
    └── source-review-samples/**
```

The tree above is the target review-package shape. The current builder emits the root manifests,
provenance files, and the selected project/reference tree directly; it does not invent a separate
`review/`, `effective-config/`, or `source-closure/` hierarchy. The copied `notes/`, `docs/`,
configuration, and source files remain available for capable machine review, while a future final
production package may add the phase-specific delivery records.

`included-files.jsonl` is the exact file list for the built tree; the directory globs above are
the inclusion rule, not a claim that a reviewer should infer omitted files. Every included regular
file gets its relative path, byte size, mode, SHA-256, source-relative path, and phase labels.

`artifact-manifest.json` must be at the artifact root and retain the rule from
`notes/review-artifact-spec.md:23-49`:

> **Absence must never be indistinguishable from deletion.**

At minimum it contains `artifact_built`, `source_commit`, `source_branch`, `tree_dirty`, the
complete unique `uncommitted_paths` list, `included_fully`, and an `excluded` array. Each excluded
entry contains `pattern`, `reason`, `present_in_project: true`, count, bytes, and a pointer to the
corresponding exact records in `excluded-files.jsonl`. The exclusion list must include directories,
regular files, and symlinks; a directory scan that only sees `Path.is_file()` is insufficient.

`source-provenance.json` records the actual current commit, branch, status, source-root identity,
builder version/hash, scan start/end, Python/tool versions, and a source-tree digest. The builder
must abort if the source file set or hashes change during the copy. A dirty tree is allowed for the
source-fidelity phase only when its exact dirty paths are carried forward; it is not a production
freeze.

## 2. Exact project inclusion and exclusion rules

### Included completely for source review

These are copied preserving relative paths and regular-file bytes:

- `docs/**`, `scripts/**`, `tests/**`, `datasphere/native/**`, and `setup/**`.
- `runnable/**` including launchers, patches, source, configs, XML/YAML/JSON, and test fixtures.
- `RL-ViGen-upstream/**` including the Door task/environment/config source and all assets that are
  imported or opened by the reviewed Door path.
- `rlgen/**`, `third_party/**`, `baselines/**`, `configs/**`, `compute/**`, `tools/**`,
  `mutants/**`, and `research/**`.
- Root research/contract files: `README.md`, `instruction.md`, `TASK.md`, `RIGOR.md`,
  `VALIDATION.md`, `STATUS-AGAINST-THE-GOAL.md`, `PREMISES.md`, `HANDOFF.md`,
  `RECOVERY-HANDOFF.md`, `CLAUDE.md`, `requirements*.txt`, `pytest.ini`, and any other root
  source/config file. Root files are enumerated, not selected by extension.
- `notes/**` that records scientific decisions, claims, protocol, review triage, and production
  requirements, including `notes/review-artifact-spec.md`, `notes/DECISION-SHEET.md`,
  `notes/NEXT-ACTIONS.md`, `notes/PRODUCTION-RUNBOOK.md`, and `notes/ai-help-*.md`.

### Relevant original materials

The package includes full bytes plus hashes for the original evidence, not only links:

- `ext/baseline_resources/**` and `ext/papers-sorted/**`, excluding only their duplicate corpus
  when the canonical copy is present; duplicates still appear in the exclusion manifest.
- The official/source trees currently used by the project: `ext/drqv2/**`, `ext/drq/**`,
  `ext/SGQN/**`, `ext/curl/**`, `ext/rad/**`, `ext/ALDA_Official/**`, `ext/idaac/**`,
  `ext/phasic-policy-gradient/**`, `ext/IBAC-SNI/**`, `ext/ctrl_public/**`, `ext/ctrl_rl/**`,
  `ext/rl_vigen/**`, `ext/dmcontrol-generalization-benchmark/**`, `ext/robosuite/**`,
  `ext/secant_robosuite/**`, `ext/pytorch-a2c-ppo-acktr-gail/**`, `ext/baselines/**`, and
  any other path named by `families.json`, `source-lock.json`, `ORIGINAL_LOCATIONS.md`, or a
  generated closure manifest.
- The package may exclude known unrelated `ext/ctrl_WRONG_llm_critic_2502.03492/**` and
  `ext/_duplicates/**`, but must state that explicitly with counts/hashes. It must not exclude all
  of `ext/`: the live IDAAC descriptor uses `ext/baselines` in
  `datasphere/native/families.json:322-333`, and the evaluator closure uses
  `ext/baselines/baselines` in `datasphere/native/evaluator_identity.py:71-77`.

### Excluded, but always declared

The default exclusions are:

- `.git/**` and nested clone `.git/**` history, with commit/source-lock hashes retained.
- `*.tgz`, trained `*.pt`/`*.pth`/equivalent weights, datasets, replay buffers, generated logs,
  caches, and temporary run directories.
- `__pycache__/**`, `.pytest_cache/**`, `.DS_Store`, and unrelated media/screenshots/videos.
- The private collaboration surfaces `.claude/**`, `notes/ask-claude.md`,
  `notes/claude-answers.md`, raw session transcripts, and any mailbox/credential material.
  Scientific decision and review records are included; private coordination is not.
- Generated `results/**` is excluded from this source-fidelity builder. Its omission is recorded
  path-by-path, because current records predate later evaluator revisions and must not be mistaken
  for final evidence. A future FINAL PRODUCTION-READINESS package may include frozen records,
  manifests, curves, and delivery status after revalidation/freeze.

If an excluded binary is needed to verify a Door source path, the builder copies it into the
relevant `source-closure/<family>/` evidence area or records its exact external path/hash and the
reason it cannot be transported. A symlink is never silently dereferenced or dropped: its relative
target, target type, resolved target (if inside the project), and inclusion/exclusion decision are
recorded in `symlinks.jsonl`.

## 3. Seven family closures for all twelve active baselines

The closure index is generated from the live `FAMILY_RUNTIME_MEMBERS`, `families.json` descriptor,
launcher, payload members, patch, import gate, and resolved imports. It must list every path with a
role (`evaluator`, `training`, `environment`, `descriptor`, `launcher`, `patch`, `reference`, or
`asset`) and a hash. The following is the minimum named closure; the full source directories above
remain included so a missing dynamic edge is reviewable.

| active baseline(s) | family | minimum current closure to enumerate | primary/reference closure |
|---|---|---|---|
| `drqv2`, `svea`, `drq`, `sgqn`, `curl` | `rlvigen` | `RL-ViGen-upstream/algos/**`, `RL-ViGen-upstream/wrappers/**`, `RL-ViGen-upstream/envs/robosuiteVGB/robosuitevgb/**`, `RL-ViGen-upstream/envs/robosuiteVGB/cfg/robo_config.yaml`, `.../cfg/setting/robo_setting.yaml`, `RL-ViGen-upstream/utils.py`, `runnable/_launch/rlvigen.sh`, `runnable/_shim/**`, `runnable/_patches` and `setup/**` | `ext/drqv2/**`, `ext/drq/**`, `ext/SGQN/**`, `ext/curl/**`, `ext/baseline_resources/{01,02,03,04,05}_*/**`, `ext/papers-sorted/{DrQ-v2,DrQ,SVEA,SGQN}/**`, plus RL-ViGen paper/supplement |
| `rad`, `soda` | `dmc_gb` | `runnable/dmc_gb/src/algorithms/**`, `src/env/**`, `src/utils.py`, `src/augmentations.py`, `runnable/_launch/dmc_gb.sh`, `runnable/dmc_gb/setup/**`, shared Door source, and `runnable/_patches/dmc_gb.patch` | `ext/rad/**`, `ext/baseline_resources/{06,07}_*/**`, `ext/papers-sorted/RAD/**`, `ext/papers-sorted/SODA/**` if present, and the official DMC generalization benchmark source |
| `idaac` | `idaac` | `runnable/idaac/ppo_daac_idaac/**`, `runnable/idaac/train.py`, `runnable/idaac/test.py`, `runnable/_shim/no_tf/**`, `runnable/_launch/idaac.sh`, `runnable/_patches/idaac.patch`, `ext/baselines/baselines/**`, shared Door source | `ext/idaac/**`, `ext/baselines/**`, IDAAC paper and supplementary material |
| `alda` | `alda` | `runnable/alda/trainers/**`, `common/**`, `autoencoders/**`, `disentangle/**`, `dmcontrol_generalization_benchmark/src/env/**`, `src/utils.py`, `src/augmentations.py`, `specs/train_alda_robosuite_door.yaml`, `third_party/alda/models/**`, `runnable/_shim/alda_models/models/**`, launcher/patch/shared Door source | `ext/ALDA_Official/**`, ALDA paper/supplement, and DMC benchmark source |
| `ppg` | `ppg` | `runnable/ppg/phasic_policy_gradient/**`, including `__init__.py` and its explicit `train.py` evaluator exception, `runnable/_launch/{ppg.sh,ppg_cell.sh,ppg_eval.py}`, patch, shared Door source | `ext/phasic-policy-gradient/**`, PPG paper/supplement/reference source |
| `ibac_sni` | `ibac_sni` | `runnable/ibac_sni/torch_rl/utils/**`, `torch_rl/torch_rl/torch_rl/**`, `model.py`, `bottleneck.py`, `ibac_sni_runtime.py`, launcher/cell launcher/patch, `ext` IBAC worker/policy source, shared Door source | `ext/IBAC-SNI/**`, IBAC-SNI paper, CRC appendix and rebuttal |
| `ctrl` | `ctrl` | `runnable/ctrl/{algo.py,models.py,buffer.py,vec_env.py}`, `runnable/_shim/**`, launcher/cell launcher, patch, shared Door source; exclude run-generated `door.xml` from static identity but record it as a run artifact | `ext/ctrl_public/**`, `ext/ctrl_rl/**`, CTRL paper/supplement/source |

The closure must include both the source file and the reason it is included. It must not turn a
training-only file into evaluator identity merely because it is convenient to copy it.

## 4. Effective configuration and final-run evidence

### SOURCE-FIDELITY REVIEW NOW

`effective-config/planned-source-resolution.json` contains one entry per active baseline and one
shared-protocol entry. It is generated from the actual current `families.json`, YAML config, launcher,
patch/source-lock, and evaluator command. Every field is marked `planned`, `observed`, or
`not-applicable`; planned values are never represented as a run observation. Required fields:

- baseline/family/task; source commit and schema-2 evaluator identity;
- exact rendered argv, working directory, Python path, package/dependency pins, and all allowlisted
  environment variables, with secrets redacted but names and redaction reason retained;
- host profile/tier, GPU class, process/env count, replay capacity, RAM/VRAM/disk assumptions,
  timeout and reservation, frame/step/action accounting, rollout/update quantum, batch/minibatch,
  evaluation and checkpoint cadence;
- observation shape/channels/stack, crop/resize/scaling/augmentation, action dimension/transform,
  termination/truncation, seed, checkpoint selector, output bindings, and required curves/metrics;
- descriptor hash, effective-config hash, source-closure hash, payload identity expectation, and
  the exact source path/line that supplies every non-derived value.

### FINAL PRODUCTION-READINESS REVIEW LATER

Each actual cell contributes a captured directory under `effective-config/final-run-capture/`:

```text
<job>/<family>/<seed>/
  run_manifest.json
  effective_config.json
  argv.json
  environment-allowlisted.json
  package-versions.txt
  resource-envelope.json
  checkpoint-manifest.json
  evaluator-identity.json
  payload-manifest.json
  delivery-manifest.json
  records-index.json
```

These are copied from the run, never reconstructed from a later descriptor. The production packet
also needs job ID/tier/timeout, full seed list, endpoint and intermediate checkpoint evidence,
offline-evaluation records, train/eval curves, failure/retry history, final archive hash, and the
record-delivery classification. Historical or pre-fix rows are retained only with their schema,
identity, and validity status.

## 5. Reviewer question and response schema

`review/question-index.jsonl` has one stable row for every material decision, not one prose question
per algorithm. Required fields:

```json
{
  "id": "PPG.OBS.RESOLUTION.001",
  "phase": "SOURCE-FIDELITY REVIEW NOW",
  "baseline": "ppg",
  "family": "ppg",
  "axis": "observation geometry",
  "claim": "the current observation resolution/channels/stack matches the source design point",
  "current_value": "...",
  "source_evidence": ["reference/...", "project/..."],
  "current_evidence": ["project/..."],
  "question": "What does the primary source actually specify, and is this current setting ...?",
  "acceptance": "one of the five controlled classifications with citations",
  "owner_or_internal": false
}
```

Every baseline gets rows for: provenance; task/action/observation geometry; transforms and
termination; architecture/backbone/head; objective and every coefficient; augmentation;
optimizer/schedule/batch/rollout/update/parallelism; entropy/exploration/log-std; frame and step
accounting; evaluation/checkpoint/reporting; and any source-versus-paper disagreement. Shared rows
cover RL-ViGen Door, renderer, scene/regime split, seeds, endpoint/intermediate estimands, and
records delivery.

`review/response-schema.json` requires:

```json
{
  "id": "PPG.OBS.RESOLUTION.001",
  "classification": "EXACT SOURCE MATCH",
  "source_type": "paper | official_code | supplement | current_tree | not_specified",
  "source_citations": [{"path": "...", "page_or_section": "...", "line": "..."}],
  "observed_current": "...",
  "observed_source": "...",
  "difference_and_context": "...",
  "materiality": "identity | result | protocol | none | unknown",
  "confidence": "high | medium | low",
  "action": "none | declare_variant | repair | owner_decision | production_measurement",
  "unseen_or_missing_evidence": []
}
```

Allowed classifications are exactly: `EXACT SOURCE MATCH`, `SOURCE VARIANT WITH CONTEXT`,
`UNSUPPORTED/NECESSARY ADAPTATION`, `SOURCE CONFLICT`, and `NOT SPECIFIED`. A reviewer may not
silently use absence from the artifact as `NOT SPECIFIED`; the exclusion manifest is checked first.

## 6. Reading order without shrinking the evidence

There is no source truncation or single-context chunking. `review/reading-order.json` groups paths
for navigation only:

1. manifest/provenance/exclusions and the shared protocol;
2. RL-ViGen shared environment and the five RL-ViGen baselines;
3. DMC family (`rad`, `soda`), then ALDA;
4. IDAAC and PPG, including the complete three-stack/one-stack source and config evidence;
5. IBAC-SNI and CTRL;
6. cross-baseline metric, seed, checkpoint, delivery, and production-readiness questions.

Each group points to raw files and stable question IDs. A reviewer can process groups separately,
but no group is a substitute for the full directory. A final synthesis must preserve disagreements
and cite the response IDs that support it.

## 7. What can be submitted now versus what must wait

### Submit now: SOURCE-FIDELITY REVIEW NOW

Submit the source closure, all listed primary papers/supplements/official sources, the complete
current docs/scripts/tests/configs/launchers/patches, current family/evaluator descriptors, planned
effective-config resolutions, source hashes, and the question/response schema. The current tree is
dirty (`git rev-parse HEAD` was `1df70b89479c7bc9896dff921e66139a6edffa32` at blueprint review),
so the packet must declare its exact dirty paths and must not call itself a frozen production tree.

This phase can resolve method identity, source-versus-code conflicts, necessary Door/action-space
adaptations, and questions about whether a setting is actually specified by a source.

### Hold: FINAL PRODUCTION-READINESS REVIEW LATER

Do not submit final claims until there is a clean/frozen source commit and fresh payload, complete
schema-2 evaluator revalidation, patch/source closure acceptance, final effective run manifests,
the authorized production jobs and their endpoint/intermediate checkpoint archives, all planned
seeds, resource/disk/process evidence, renderer/host evidence, and complete delivery/metric
validity checks. The final packet must distinguish archive-only records, failed delivery, historical
records, and eligible final records. A source-fidelity pass cannot substitute for any of these.

## 8. Historical Gemini-builder audit and current implementation

Audited in full: `/Users/a2mogus/.gemini/antigravity-cli/brain/cf9250b1-64f1-4362-962b-b7f8ad9948bd/scratch/build_proper_review_artifact.py` (371 lines). It was not executed. Its defects
below are historical design input; the current implementation is
`scripts/build_external_review_artifact.py`, tested by
`tests/test_external_review_artifact.py`.

### Good intentions that should be retained

- It reads the correct exclusion principle and copies `docs`, `scripts`, `tests`, `datasphere/native`,
  `setup`, source trees, and configs in broad strokes (lines 8-23, 46-99).
- It performs per-file SHA-256 comparison after copying (lines 161-180).
- It records commit/branch/dirty state in principle (lines 146-150, 191-209).

### Confirmed defects and omissions

1. **Stale provenance and non-portable destructive paths.** The docstring hardcodes commit
   `12f632...` (line 12), while the live tree was `1df70b89479c7bc9896dff921e66139a6edffa32`;
   all source/output paths are hardcoded absolute paths (35-38), with no CLI root/output or
   path-safety validation.
2. **Destructive rebuild.** Existing destination is recursively deleted (109-111), an existing zip
   is unlinked (353-356), and a symlink is unlinked (347-350). This is unsafe for a shared workspace,
   cannot recover a prior artifact, and is unnecessary. Build into a unique temporary sibling,
   refuse an existing output by default, then atomically rename only after validation; never delete
   an unrelated path.
3. **Symlink loss and incomplete scan.** `all_files` includes only `p.is_file()` (115). The live
   project has symlinks including `datasphere/native/places365-val.tgz`,
   `runnable/alda/dmcontrol_generalization_benchmark/datasets`, `runnable/dmc_gb/data`, and
   `runnable/_shim/alda_models/models`. `copy2` (159) dereferences file symlinks, while directory
   symlinks disappear with no manifest. Add explicit symlink enumeration and preserve or declare
   each target.
4. **The blanket `ext/` exclusion is wrong for active provenance.** Lines 69-71 omit all external
   sources, but `families.json:322-333` names `ext/baselines` as IDAAC payload/import input and
   `evaluator_identity.py:71-77` hashes `ext/baselines/baselines`. The builder would make IDAAC
   and its evaluator closure unauditable. Include relevant official source trees or copy their
   exact closure and record all remaining exclusions.
5. **“Included fully” is false.** Manifest lines 211-227 claim full `runnable/**`,
   `RL-ViGen-upstream/**`, and native content, although classification deliberately excludes
   binary/assets, `.tgz`, weights, caches, and media. List precise patterns, not contradictory
   full-directory claims.
6. **Exclusions are not exact.** Only eight sample paths per category are retained (133-138); the
   manifest does not enumerate every omitted path. `cache_or_git` combines `.git`, `__pycache__`,
   and `.pytest_cache`, but the manifest represents it as `.git/**` only (229-237). The
   `other_unclassified` category has no manifest entry at all. Add `excluded-files.jsonl` and a
   root summary with one exact record per omitted file/directory/symlink.
7. **No actual test transcript.** The docstring promises one (22), but the script never runs
   pytest or writes a transcript. A transcript must be supplied as a separately labelled observed
   artifact, not asserted in README text.
8. **No generated review protocol.** It writes only `artifact-manifest.json` and a README
   (293-345). It lacks source-closure manifests, effective-config requirements/captures,
   question IDs, response schema, phase labels, primary-source index, and final-run evidence
   manifests defined above.
9. **No drift or reproducibility proof.** It records status before copying (146-150) but never
   rechecks status/file set/hashes after copying. It verifies only included regular-file bytes;
   excluded files, symlinks, modes, manifest inputs, and concurrent edits can change unnoticed.
   The zip is not checked against the directory and has no archive hash/member manifest.
10. **Sensitive-data safety is absent.** It includes `.claude` via the fully included set (49) and
    all root/notes files (70-97), with no secret scan, redaction policy, or mailbox exclusion. A
    review package must reject credential-like values, exclude private collaboration surfaces, and
    emit a scan report without copying secret contents.
11. **Unlabelled historical results.** `results` is included wholesale (49, 74-75), although old
    records may predate identity/delivery repairs. They must be indexed with validity/schema status,
    or reduced to labelled samples for source review and reserved for the final frozen package.
12. **Unused policy signal and hardcoded claims.** `ALLOWED_CODE_TEXT_EXTS` (40-44) has no effect;
    README size claims and “100%” language are not checked against a reproducible manifest. The
    builder must derive all claims from measured output and fail if the declared inclusion/exclusion
    rules and actual records differ.

### Safe implementation shape now applied, and remaining final-package work

- The current builder accepts explicit `--source`, `--output`, and `--mode`; output must not exist,
  must be outside the source root, and publication claims the destination with `mkdir` so a
  concurrent empty directory cannot be replaced by `rename()`.
- Capture a complete pre-scan of regular files, directories, symlinks, modes, hashes, git status,
  and exclusion decisions. Copy to a unique staging directory without following symlinks.
- The current builder generates exact included/excluded/symlink manifests, source status and
  provenance, rescans the source, and aborts on selection, size, mode, target, or included-byte
  drift. It verifies regular files without following source symlinks and preserves file modes.
- Build an optional archive into a new unique path only after the directory passes; hash it and
  verify its member list against `included-files.jsonl`. Never unlink or recursively delete an
  existing path.
- The current builder fails closed on credential-like source paths, private coordination paths,
  and forbidden transcript paths. It redacts absolute or credential-like symlink targets while
  retaining a target fingerprint and classification. It is a name/path safety gate, not a proof
  that arbitrary innocently named text contains no secret; inspect any supplied external
  transcript before sharing.
- The current narrow tests cover: excluded-file completeness, symlink recording and target
  redaction, IBAC's
  `ext/baselines` closure, dirty-path provenance, source-drift refusal, output-collision refusal,
  no destructive calls, mode preservation, private/credential transcript refusal, and phase-label
  separation. Archive transport and final-package result capture remain separate work.
