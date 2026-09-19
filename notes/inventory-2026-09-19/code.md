> **Executor output, not a finding of record.** Produced 2026-09-19 by a read-only Sonnet executor. Re-checked by the lead: the v4 waiter defaulting to the v5 wrapper, `RESUME_SNAPSHOT` missing from the env allowlist, 219 `cfg-*.yaml`, the two empty oddly named root directories, the allowlist location. Everything else is unverified until someone re-runs the command beside it. Its own "not covered" list is at the top.

# Code inventory: live vs superseded — many-gens-rl-vigen

Repository: `/Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen`
Method: read the 5 named chain scripts + laptop-side scripts in full (except `run_probe.sh`/`family.py`,
grepped per instructions); one further hop for anything new found; `grep -rl`/`git log`/`git ls-files`/`find`/`stat`
for classification and file facts. No script was executed. No file was edited.

## What this does NOT cover (read this before the tables)
- `run_probe.sh` (2,831 lines) and `family.py` (1,555 lines) were **grepped, not read end to end** (per
  task instructions: `python3 `, `bash `, `source `, `import `, `open(`, `.json`, `.yaml`, `.sh` and context
  around hits). A call embedded in a code path the grep patterns don't match (e.g. a dynamically built
  string) could be missed.
- `families.json` (1,129 lines, 7 family blocks) was sampled, not read in full — I confirmed the `launcher`/
  `repository`/`cwd`/`host_profiles` keys exist for all 7 families and read one family's `host_profiles`
  block (rlvigen, lines 48–58) as a worked example. Per-family numeric defaults beyond that are **not**
  exhaustively catalogued.
- `runnable/` (3,883 files, only 24 git-tracked) and `RL-ViGen-upstream/` (third-party) were **not** walked
  past confirming they are the live chain's terminus (via `families.json`'s `launcher`/`repository`/`cwd`
  keys). Per the task, this is where the walk stops.
- Task C's family.py/families.json defaults are illustrative, not exhaustive (task allowed capping; I did
  not attempt to enumerate every `host_profiles` override across all 7 families).
- I did not open the two oddly-shaped root **directories** in §B5 beyond listing their path components —
  correctly interpreting them as directories rather than files (the task described them as files) is itself
  a finding, noted there.
- Everything below is from reading files and running `grep`/`find`/`stat`/`git`. Anything not directly
  read is marked **(inferred)**.

---

## A. Live chain walk (file:line for every hop)

### Seed chain, verified
1. **`host-scripts/wait-and-train-v4.sh`** (220 lines, read in full).
   - `:51` `WRAPPER="${WRAPPER:-train-production-cell-v5.sh}"` — **the actual default is v5, not v6.**
     v6 is only reached if a caller explicitly passes `WRAPPER=train-production-cell-v6.sh` (needed for
     Places365 baselines svea/sgqn/soda per v6's own header). The lead's seed chain names v6; by default,
     the live path runs through **v5**, which I added to the live set.
   - `:131` `[ -f "$HOME/rlvigen-work/$WRAPPER" ]` — invokes whichever wrapper is resolved, as a **host
     path** (`~/rlvigen-work/…`), not a repo-relative path. This is a deploy-time flattening this repo does
     not model (the repo keeps these under `host-scripts/`); I infer the host has a flat copy — **(inferred)**.
   - `:186` `bash "$HOME/rlvigen-work/$WRAPPER"` — the launch itself.
   - `:198` `bash "$HOME/rlvigen-work/self-vram-cap.sh" "$c" "$CARD" "$VRAM_MIB" …` — arms the self-cap
     watcher. `datasphere/native/host-scripts/self-vram-cap.sh` and `datasphere/native/self-vram-cap.sh`
     are byte-identical (`diff` exit 0), so it doesn't matter which one the flattened host copy traces to.

2. **`host-scripts/train-production-cell-v6.sh`** (71 lines, read in full) and, because of finding 1,
   **`host-scripts/train-production-cell-v5.sh`** (71 lines, read in full — v6's header says it is "v5
   with exactly two knobs added").
   - v5 `:65` / v6 `:66`: `bash datasphere/native/launch-card-cell.sh "$PAYLOAD_OR_DERIVED" "$A/$TAG-result.tgz" "$HOME/rlvigen-assets/rlvigen-door2-90d8b8c4.tgz"` — both reach the same next hop.

3. **`datasphere/native/launch-card-cell.sh`** (479 lines, read in full).
   - `:142` `docker run … python3 datasphere/native/family.py production-env --cells "$CELLS"` (only when `NATIVE_PRODUCTION=1`).
   - `:184` `NEIGHBOUR_YIELD="${NATIVE_NEEDBOUR_YIELD:-$REPO/datasphere/native/neighbour-yield.sh}"` (default path is the **top-level** copy, not `host-scripts/neighbour-yield.sh` — see §B1 finding).
   - `:239` `python3 scripts/watch_gpu_headroom.py --preflight …`
   - `:251` `python3 scripts/watch_card_exclusivity.py …`
   - `:297` `python3 scripts/yield_gpu_to_neighbour.py …`
   - `:323` `nohup bash "$NEIGHBOUR_YIELD" …` (host-side, not containerised).
   - `:424` `python3 datasphere/native/family.py disk-requirement --cells "$CELLS" …`
   - `:453` `python3 scripts/watch_disk_headroom.py …`
   - `:475` `bash datasphere/native/run_on_production_host.sh "$PAYLOAD" "$RESULT" …` — the main next hop.

4. **`datasphere/native/run_on_production_host.sh`** (948 lines, read in full).
   - `:285` `IMAGE="$(helper_python -c "import json,pathlib; print(json.loads(pathlib.Path('datasphere/native/source-lock.json').read_text())['container_image'])")"` — reads `source-lock.json`. **This exact string is the origin of the oddly-named root directory in §B5.**
   - `:506` `helper_python datasphere/native/family.py disk-requirement --cells … --profile …`
   - `:811–829` the env-forwarding allowlist loop (see §D).
   - `:880–893` `docker run … bash -c 'apt-get … ; bash datasphere/native/run_probe.sh $INNER_ARGS'` — the main next hop, run **inside the container**.

5. **`datasphere/native/run_probe.sh`** (2,831 lines, grepped per instructions — `python3 `, `bash `,
   `source `, `import `, `.json`/`.yaml` literals). New calls found (all inside the container):
   - `:38,331,347,381` — `python3 "$FAMILY_TOOL"` where `FAMILY_TOOL="${FAMILY_TOOL:-datasphere/native/family.py}"` (seed).
   - `:102` `python3 datasphere/native/measure_resources.py`
   - `:229` `python3 scripts/watch_policy_health.py`
   - `:1132,1204,1261,1353` `python3 scripts/eval_grid.py` (curve/endpoint eval).
   - `:1459,1828,1832,1836,2146,2627` `python3 datasphere/native/contract.py …` (multiple subcommands, incl. `verify-robosuite-closure --closure datasphere/native/robosuite-import-closure.json` at `:1836`, alongside root file `requirements-native.txt`).
   - `:1727` `python3 -c "…json.load(open('datasphere/native/rlvigen-source.json'))…"`
   - `:1820–1821` `python3 setup/apply_patches.py` / `--check` (seed; also re-applied inside the container, not just at build time).
   - `:1897` `cp datasphere/native/vram_cap.py "$vram_cap_dir/sitecustomize.py"` — installs it as a Python `sitecustomize`, so it auto-loads for every interpreter in the cell.
   - `:2209–2217` `python3 datasphere/native/configure_places365_val.py` (×4 invocations).
   - `:2516` `json.loads(Path("datasphere/native/families.json").read_text())` — direct read, not via `family.py`.
   - `:2585` `python3 datasphere/native/normalize_curves.py`
   - No `bash <script>.sh` calls found anywhere in `run_probe.sh` — it never spawns another shell script, only Python.

6. **`datasphere/native/family.py`** (1,555 lines, grepped per instructions).
   - `:26` `DESCRIPTORS = HERE / "families.json"` — its only repo data dependency.
   - `:431,519` `Path(__file__).resolve().with_name("plan_production.py")` — dynamically imports `plan_production.py` (new node).
   - `:992,1290` `subprocess.run([sys.executable, "-c", …], env=…)` — runs **inline** Python strings (`import_gate`, `FINITENESS_PROBE`), not a call to `scripts/check_checkpoint_finite.py` despite its own docstring at `:1268` calling that script "the project's instrument for this" — **doc/code mismatch inside family.py itself**, worth flagging per the runbook's "every disagreement is itself a finding" rule.
   - No `.sh` calls, no `import` of other repo modules beyond stdlib.

### One more hop (per new file found above)
- `scripts/watch_gpu_headroom.py`, `watch_card_exclusivity.py`, `yield_gpu_to_neighbour.py`, `watch_disk_headroom.py`: stdlib-only imports (`argparse`, `json`, `subprocess`, `sys`, `time`). No further repo nodes.
- `datasphere/native/neighbour-yield.sh` (104 lines, read in full): only `docker`/`nvidia-smi`, no repo file calls.
- `datasphere/native/configure_places365_val.py`, `measure_resources.py`, `normalize_curves.py`: stdlib-only imports; no new repo nodes.
- `scripts/eval_grid.py` (`:72,79,81–83`): imports `datasphere.native.evaluator_identity`, `rlgen.protocol` (`OBSERVATION_GEOMETRY`), `scripts.eval_across_scenes`, `scripts.eval_provenance` — **4 new nodes**, added to live set, not expanded further (stop, per "one more hop").
- `scripts/watch_policy_health.py` (`:57`): `from metrics import gaussian_boundary_fraction` → `scripts/metrics.py` — **1 new node**, not expanded further.
- `datasphere/native/contract.py` (laptop seed, 948-ish lines skimmed for imports/refs): `:17,22–23` imports `datasphere/native/evaluator_identity.py` directly (also dynamically via `importlib` as a fallback); `:37–54` a `PAYLOAD_FILES`-type manifest listing `evaluator_identity.py`, `families.json`, `plan_production.py`, `robosuite-import-closure.json`, `rlvigen-source.json`, `source-lock.json`, `vram_cap.py` as files the payload build must bundle — confirms these all travel to the container together.
- `datasphere/native/build-env.sh` (159 lines, read in full): `:40,88` `python3 datasphere/native/family.py filtered-requirements …`; `:104` reads `/repo/setup/source-reconstruction.json`; `:107–108` `python3 setup/apply_patches.py [--check]`.
- `setup/apply_patches.py`, `setup/bootstrap_sources.py`: stdlib-only imports (plus `subprocess` in bootstrap_sources.py, used to `git clone`/`git checkout` RL-ViGen-upstream — third-party, stop).
- `scripts/production_run_register.py` (`:45`): `from audit_attempt_ledger import _TERMINAL_HINTS` — already-known seed.
- `scripts/production_reading.py` (`:65–66`): `import campaign_status as cs` (seed) and `from regime_retention_report import MIN_DENOM_SUCCESS` → **1 new node**, `scripts/regime_retention_report.py`.
- `scripts/production_gates.py` (`:43`): imports `datasphere.native.evaluator_identity` (already found via `eval_grid.py`); `:1328` also `subprocess`-invokes `datasphere/native/plan_production.py --host-profile v100 --sync-schedule` directly.
- `datasphere/native/collect-host-run.sh` (346 lines, read in full): no `python3`/`bash` calls to other repo scripts in its executed path — `scripts/assemble_reaped_delivery.py` and `scripts/explain_delivery_size.py` are named only inside operator-facing `echo` diagnostic text (e.g. `:105,165`), **never actually invoked**. Its only repo dependency is reading run-directory artifacts it doesn't itself compute.

### Live set size
**~45 distinct named files/configs**, terminating in two directories the walk stops at rather than expands:
`runnable/` (this project's own baseline-launcher code — confirmed via `families.json`'s `launcher`/`repository`/
`cwd` keys for all 7 families, e.g. `:24` rlvigen→`runnable/_launch/rlvigen.sh`, `:171` dmc_gb, `:285` idaac,
`:475` alda, `:589` ppg, `:755` ibac_sni, `:906` ctrl) and `RL-ViGen-upstream/` (vendored third-party, per task
instructions not expanded).

---

## B. Group classification

### B1. `datasphere/native/host-scripts/*` (34 files, excluding `README.md`)
- **LIVE (4):** `wait-and-train-v4.sh`, `train-production-cell-v5.sh`, `train-production-cell-v6.sh`, `self-vram-cap.sh`.
- **REFERENCED (8):** `capacity-check.sh`, `curve-sweep-v3.sh`, `fetch-places.sh`, `host-run.sh`, `neighbour-yield.sh`, `wait-and-train-v3.sh`, `watch-capacity.sh`, `watch-cell.sh` — all hit in `notes/OPERATOR-GUIDE.md` and/or `tests/`.
  - **Finding:** `host-scripts/neighbour-yield.sh` is referenced by `tests/test_card_one_must_process_yield.py`, but it is a **different, older script** than the one the live chain actually uses (`datasphere/native/neighbour-yield.sh`, the `launch-card-cell.sh:184` default). `diff` shows the host-scripts copy hardcodes card 0 (`grep -E '^(cell-c0-|rlvigen-)'`, `nvidia-smi -i 0`) and has no `STOP_CONTAINER` parameter, while the live top-level copy takes `CARD` and `STOP_CONTAINER` as arguments (added 2026-09-15 per its own header). Whether that test actually exercises the live behavior needs the test file itself checked — **not read here**.
- **UNREFERENCED (22):** `attest-chain.sh`, `attest-retry.sh`, `attest-retry2.sh`, `attest-v212.sh`, `attest-v213-ctrl.sh`, `ctrl-retry.sh`, `curve-sweep-v2.sh`, `curve-sweep.sh`, `extract-places-once.sh`, `ibac-waiter.sh`, `jax-cudnn-diag.sh`, `jax-cudnn-pin.sh`, `jax-volta-probe-v2.sh`, `jax-volta-probe.sh`, `reeval-cell-cached.sh`, `reeval-cell.sh`, `run-volta-probe-when-free.sh`, `train-production-cell-v2.sh`, `train-production-cell-v3.sh`, `train-production-cell-v4.sh`, `train-production-cell.sh`, `verify-places-folder.sh`.
- Greps run: `grep -rlI -F "<filename>" tests/ notes/OPERATOR-GUIDE.md docs/RUN-THIS-PROJECT.md CLAUDE.md`, one filename at a time.

### B2. `datasphere/native/*.sh` and `*.py` (25 `.sh` + 9 `.py` = 34, excluding `host-scripts/`, `cfg-*.yaml`, `*.json`)
- **LIVE (7 sh + 8 py = 15):** sh: `build-env.sh`, `collect-host-run.sh`, `launch-card-cell.sh`, `neighbour-yield.sh`, `run_on_production_host.sh`, `run_probe.sh`, `self-vram-cap.sh`. py: `configure_places365_val.py`, `contract.py`, `evaluator_identity.py`, `family.py`, `measure_resources.py`, `normalize_curves.py`, `plan_production.py`, `vram_cap.py`.
- **REFERENCED (7 sh + 1 py = 8):** `battery-chain.sh`, `collect-wave.sh`, `gpu-occupancy-log.sh`, `host-run.sh`, `job.sh`, `preflight_production_host.sh`, `prod-monitor-laptop.sh`; `summarize_result.py` (→ `tests/test_record_delivery.py`).
  - **Key finding:** `job.sh` is the single most heavily-referenced non-live file found in this whole inventory — 9 test files plus `docs/RUN-THIS-PROJECT.md` — yet `run_on_production_host.sh`'s own header (`:5–10`) states outright that `job.sh`, `contract.py`'s DataSphere-job path, and the `cfg-*.yaml` configs all assume the DataSphere job-submission API, which the production host (`cds2`) doesn't run at all; `run_on_production_host.sh` exists specifically to bypass that path. So `job.sh` is thoroughly tested and documented, but is **not** on the production path this task defines as live.
- **UNREFERENCED (11 sh):** `booking-watchdog.sh`, `cell-heartbeat.sh`, `chain-when-card-free.sh`, `curve-sweep.sh`, `fire-wave-v205.sh`, `launch-ibac-when-roomy.sh`, `launch-when-free.sh`, `reeval-cell.sh`, `reeval-ppg.sh`, `require_container.sh`, `train-production-cell.sh`.

### B3. `datasphere/native/cfg-*.yaml` (219 files total)
Counts per prefix family (from filename, `cfg-<prefix>-*`):
idaac 32, ctrl 25, alda 22, drqv2 20, ppg 17, rlvigen 15, ibac_sni 14, preprod 12, dmc_gb 12, offline 6,
renderer 4, guard 4, codex 4, onpolicy 3, curve 3, ckpt 3, svea 2, soda 2, sgqn 2, rad 2, metrics 2, drq 2,
curl 2, c61 2, shape 1, impala 1, ibac 1, endurance 1, dmcgb 1, dmc 1, and `cfg-preflight.yaml` (no
second-hyphen prefix) 1.
- **LIVE: 0.** None of the 219 configs are called anywhere in the live chain — the whole `cfg-*.yaml` family
  feeds the DataSphere job-submission API (`job.sh`), the alternate path `run_on_production_host.sh`
  explicitly bypasses.
- **REFERENCED (strict — hit in `tests/`, `notes/OPERATOR-GUIDE.md`, `docs/RUN-THIS-PROJECT.md`, or `CLAUDE.md`): 14 / 219** — all 14 via `tests/`: `cfg-ctrl-diag-v159.yaml`, `cfg-dmcgb-calibration-v22.yaml`, `cfg-drqv2-calibration-a{,-v11,-v12,-v14,-v15,-v16,-v17,-v18}.yaml` (8 files), `cfg-offline-eval-s2-full-v50.yaml`, `cfg-preflight.yaml`, `cfg-rlvigen-trio-calibration-v21.yaml`, `cfg-svea-asset-calibration-v20.yaml`.
- **UNREFERENCED (strict): 205 / 219.**
- **Referenced anywhere outside themselves (broad, per the task's second clause — any file in the repo, not just tests/docs):** 119 / 219, mostly other `cfg-*.yaml` files' own comments, `notes/*.md` session logs (`notes/one-offs/CODEX-FOUNDATION-2-SESSION-LOG.md` alone accounts for a large share), and `results/submissions.jsonl`. This is historical/narrative cross-reference, not code that reads the file.
- Greps run: for each of the 219 basenames, `grep -rlI -F "<name>" . --exclude-dir=.git`, excluding the file's own path, then intersected with the strict set.

### B4. `scripts/*` (106 files, excluding `__pycache__`)
- **LIVE (18):** `audit_attempt_ledger.py`, `audit_record_frame_provenance.py`, `campaign_status.py`, `eval_across_scenes.py`, `eval_grid.py`, `eval_provenance.py`, `metrics.py`, `production_gates.py`, `production_reading.py`, `production_run_register.py`, `record_host_run.py`, `regime_retention_report.py`, `watch_card_exclusivity.py`, `watch_disk_headroom.py`, `watch_gpu_headroom.py`, `watch_policy_health.py`, `yield_gpu_to_neighbour.py`, and `__init__.py` (required for `from scripts import eval_across_scenes` in `eval_grid.py:81` to resolve as a package import).
- **REFERENCED (68):** the large majority of the remaining files (`audit_*`, `probe_*`, `verify_*`, most others) — each hit at least one file under `tests/` by filename.
- **UNREFERENCED (20):** `_discover_grid_checkpoints.py`, `audit_payload_freshness.py`, `check_checkpoint_finite.py`, `classify_drift_frames.py`, `collect_attestation_wave.py`, `evidence_pair_eval_grids.py`, `measure_vram_bounds.py`, `probe_heads.py`, `probe_level_seed_decodable.py`, `probe_ppg_aux_minibatches.py`, `probe_regimes.py`, `probe_success_control.py`, `probe_torch_checkpoint_equivalence.py`, `read_stack_pilot.py`, `record_measured_peak.py`, `rederive_grids.sh`, `run_collapse_rate.sh`, `run_regime_retention.sh`, `verify_vram_cap.py`, `watch_training_frames.py`.
  - **Finding:** `check_checkpoint_finite.py` and `measure_vram_bounds.py` are both **named in comments** inside live-chain files (`family.py:1268` and `train-production-cell-v5.sh:43` respectively) as if they were the operative tool, but neither is actually invoked by the live chain nor hit by any test/doc — see the family.py doc/code mismatch noted in §A.
- Greps run: same pattern as B1/B2, one filename at a time against `tests/`, `notes/OPERATOR-GUIDE.md`, `docs/RUN-THIS-PROJECT.md`, `CLAUDE.md`.

### B5. Repo-root files
- `*.py` (3, all git-tracked): `nd_ln_style_train.py`, `plot.py`, `train.py` — none called by the live chain. `nd_ln_style_train.py` and `plot.py` are distinctly named and genuinely hit in `tests/`/`README.md`. `train.py` also gets grep hits, but the string `train.py` also matches every baseline's own `runnable/<family>/train.py`-style path inside test files, so I can't confirm those hits are about the **root** `train.py` specifically without reading each test — reported as REFERENCED with that caveat rather than asserted cleanly.
- `*.sh`: **none** at repo root.
- `*.tgz` (25 entries, **all untracked** — `.gitignore:51-52` covers `datasphere/native/payload-*.tgz` and `*.tgz` generally): `alda-payload-v1.tgz` (51 MB), `dmcgb-payload-v22.tgz` (12 MB), 9× `native-payload-v{13,14,15,16,17,18,19,20,21,23,24,28}.tgz` (mostly 51–76 KB, `v24` is 12 MB), `payload-alda-v32.tgz` (38 MB), `payload-ctrl-v29.tgz`/`v31.tgz` (~110 KB each), `payload-dmcgb-idaac-v25.tgz` (17 MB), `payload-onpolicy-v26.tgz`/`v29.tgz`/`v30.tgz` (~95 MB each), `result.tgz` (64.8 MB), plus 3 **symlinks** (not real archives): `places365-train-attest.tgz` → `/Users/a2mogus/build-projs/rlgen-assets/places365-train-attest.tgz`, `places365-val.tgz` → same tree, `rlvigen-door2-90d8b8c4.tgz` → same tree.
- **Oddly-named entries — these are two DIRECTORIES, not files as the task described them:**
  1. `./import json,pathlib; print(json.loads(pathlib.Path('datasphere` — a directory tree 2 levels deep (`.../native`), 96/64 bytes, mtime 2026-09-08 19:11, **not tracked and not gitignored** (git shows nothing for it at all, because it contains no file — every level, including the leaf, is an empty directory; git tracks files, not empty directories).
  2. A directory whose name is the **literal multi-line string** `\n    set -euo pipefail\n    apt-get -qq update\n    apt-get -qq install -y python3 python3-pip git\n    mkdir -p code && tar xzf code.tgz -C code\n    cd code\n    bash datasphere`, nested 9 levels deep ending in `.../native/run_probe.sh/work/code.tgz/work/out/result.tgz/work`, mtime 2026-09-07 10:17, likewise untracked/ungitignored/empty-leaf.
  - **These are not coincidental strings.** Fragment 1 is character-for-character the `helper_python -c` invocation at `run_on_production_host.sh:285` (`import json,pathlib; print(json.loads(pathlib.Path('datasphere/native/source-lock.json')...`). Fragment 2 is character-for-character the `bash -c "…"` heredoc body at `run_on_production_host.sh:886-892`, and its nested path components (`/work`, `code.tgz`, `/work/out`, `result.tgz`, `/work` again) match that same block's positional/container arguments one-for-one. **(inferred)**: something ran `mkdir -p` (or Python's `os.makedirs`/`pathlib.mkdir(parents=True)`) using one of these command strings, or a list of its words/arguments, as a **path** rather than as a command to execute — most likely a bug in a dry-run/debug harness that was building a directory name from `run_on_production_host.sh`'s own dry-run echo output or from `sys.argv`/a docker command list, splitting on `/`. I did not find the actual script that produced this by reading `run_on_production_host.sh:851-877`'s `NATIVE_HOST_DRY_RUN` block, which prints exactly this content but (as read) only `echo`s it — I did not locate a second script that consumes that output and mkdir's from it. Root cause not identified; only the resemblance to these two exact source locations is established by direct comparison, not inference about intent.

### B6. Top-level directories
| Path | Files | Git-tracked | Last commit | Live-set reference |
|---|---|---|---|---|
| `datasphere_gemini/` | 133 | 132 | 2026-09-08 | None found (grepped all ~37 live-chain files: no hit). |
| `runnable/` | 3,883 | 24 | 2026-09-10 | **Yes** — the live chain's terminus. `families.json` names it as `launcher`/`repository`/`cwd` for all 7 families, e.g. `:24,171,285,475,589,755,906`. Only 24/3,883 files are git-tracked; the rest (vendored per-baseline deps/checkpoints/caches) are untracked — **(inferred)** cause, not verified by opening them. |
| `compute/` | 26 | 23 | 2026-09-07 | None found. |
| `tools/` | 11 | 7 | 2026-09-04 | None found. |
| `research/` | 12 | 11 | 2026-09-04 | None found. |
| `baselines/` | 28 | 27 | 2026-09-07 | None found directly — a `baselines/` **string** appears in `evaluator_identity.py:74` and `run_on_production_host.sh:561`, but both refer to `ext/baselines/baselines` inside a payload's `ext/` tree, a different path, not this top-level directory. |
| `rlgen/` | 135 | 75 | 2026-09-08 | **Yes** — `rlgen/protocol.py` (`OBSERVATION_GEOMETRY`) is imported by `scripts/eval_grid.py:79`, which is live. |
| `mutants/` | 9 | 4 | 2026-09-04 | None found. |
| `float32` | — | tracked | — | **Not a directory.** It is a 0-byte regular file at repo root (`-rw-r--r-- … 0 … float32`). The task listed it among top-level directories; that assumption doesn't hold. |

---

## C. Parameter defaults in the live chain

Chain scripts covered: the 5 named seeds + `train-production-cell-v5.sh` (added per §A finding 1). `run_probe.sh` capped at the defaults below (most relevant; not exhaustive — the file has ~90 distinct env-var reads).

| Variable | File:line | Default | Consumed downstream by |
|---|---|---|---|
| `WRAPPER` | `wait-and-train-v4.sh:51` | `train-production-cell-v5.sh` | itself, `:186` |
| `NEED` | `wait-and-train-v4.sh:37` | `11421` | itself (`clear_streak`) |
| `HOLD` | `wait-and-train-v4.sh:38` | `10` | itself |
| `MIN_DISK_GIB` | `wait-and-train-v4.sh:41` | `60` | itself |
| `MIN_RAM_GIB` | `wait-and-train-v4.sh:59` | `0` (off) | itself |
| `FAMILY`/`BASELINE` | v5 `:53`, v6 `:42` | `ibac_sni` | `launch-card-cell.sh` `CELLS` |
| **`SEED`** | v5 `:53`, v6 `:42` | **`101`** | `launch-card-cell.sh` → `run_on_production_host.sh` → `run_probe.sh` |
| **`SEED`** | `run_probe.sh:1437` (`seed="${SEED:-1}"`); also `:854` `DEFAULT_SEED="${SEED:-1}"` | **`1`** | `family.py command --seed`, `cell_seed()` fallback |
| **`SEED`** | `family.py:1335` (`--seed`, argparse default) | **`"1"`** | only fires if `family.py command` is invoked directly without `--seed` |
| **→ CONFLICT:** `SEED` defaults to `101` in the production wrappers vs `1` in `run_probe.sh`/`family.py`. Not usually observable (the wrappers always set `SEED` explicitly, which is forwarded via the `run_on_production_host.sh:811-829` allowlist), but a direct/manual invocation of `run_probe.sh` or `family.py` without the wrappers gets a materially different seed (1, not 101). |
| **`FRAMES`** | v5 `:53`, v6 `:42` | **`600000`** | `launch-card-cell.sh`, `run_on_production_host.sh`, `run_probe.sh` |
| **`FRAMES`** | `run_probe.sh:738,790,803,819,859,880,1386,1497,2098` (7+ sites, all `${FRAMES:-10000}`) | **`10000`** | production-scale gating, `family.py check-budget`/`command` |
| **`FRAMES`** | `family.py:1331` (`--frames` argparse default) | **`"10000"`** | only fires on a direct `family.py command` call |
| **→ CONFLICT:** `FRAMES` defaults to `600000` in the production wrappers vs `10000` everywhere in `run_probe.sh`/`family.py`. Same mitigating note as `SEED` — the wrapper always sets it explicitly in the normal path. |
| `EVAL_EVERY_FRAMES` | `run_probe.sh:878` (`${EVAL_EVERY_FRAMES:-${FRAMES:-10000}}`), `:1417` (`${EVAL_EVERY_FRAMES:-$frames}`) | defaults to **the run's own `$frames`** (i.e. eval once, at the end) | `family.py command --eval-every` |
| `EVAL_EVERY_FRAMES` | `launch-card-cell.sh:157` (`_c_scenes` computation) and `:165` (`${EVAL_EVERY_FRAMES:-50000}`) | **`50000`** | `_stamps` (watch-budget stamp-count estimate) |
| **→ CONFLICT:** if `EVAL_EVERY_FRAMES` is left unset, `run_probe.sh` behaves as "no periodic eval" (defaults to the whole frame budget) while `launch-card-cell.sh`'s watch-budget arithmetic assumes a fixed cadence of every 50,000 frames when sizing `EVAL_ALLOWANCE`. Not dangerous in the direction it fails (over-provisions the watch budget rather than under), but the two files disagree about what "unset" means. |
| `EVAL_EPISODES` | `run_probe.sh:881,1419` | `2` | `family.py command --eval-episodes` |
| `EVAL_EPISODES` (argparse) | `family.py:1333` | `"2"` | matches; only fires standalone |
| `CURVE_EVAL_EPISODES` | `launch-card-cell.sh:166` | `3` | eval-workload arithmetic; also read directly in `run_probe.sh:1212` |
| `ENDPOINT_EVAL_EPISODES` | `launch-card-cell.sh:167` | `20` | eval-workload arithmetic; also `run_probe.sh:1141` |
| `ENDPOINT_EVAL_POLICY_MODES` | `launch-card-cell.sh:160` | `native` (1 mode) | `_e_modes` count — flagged in the script's own comment (`:104-111`) as previously omitted, causing an 11x watch-budget underestimate that reaped a live cell mid-eval |
| `CURVE_EVAL_REGIMES` | `launch-card-cell.sh:156` | `train,eval-easy` | `_c_regimes` |
| `ENDPOINT_EVAL_REGIMES` | `launch-card-cell.sh:158` | `train,eval-easy,eval-medium,eval-hard` | `_e_regimes` |
| `NATIVE_SECONDS_PER_EVAL_EPISODE` | `launch-card-cell.sh:168` | `12` | `_derived` watch-budget seconds |
| `NATIVE_WATCH_SLACK_SECONDS` | `launch-card-cell.sh:91` | `900` | `WATCH_SECONDS` |
| `NATIVE_BOOTSTRAP_ALLOWANCE_SECONDS` | `launch-card-cell.sh:71,73` | `600` (with `NATIVE_VENV_HOST`) or `9000` (without) | `MUST_COVER`/`WATCH_SECONDS` |
| `NATIVE_REAP_MAX_GRACE_SECONDS` | `launch-card-cell.sh:375` | `10800` | reaper subshell |
| `NATIVE_REAP_STALL_SECONDS` | `launch-card-cell.sh:376` | `900` | reaper subshell |
| `NATIVE_NEED_MIB` | `launch-card-cell.sh:232,240` | `4000` | preflight `--need-mib` |
| `NATIVE_FLOOR_MIB` | `launch-card-cell.sh:301` | `4000` | yield-watch `--floor-mib` |
| **`EXPECT_OURS`/`NATIVE_EXPECT_OURS`** | v5 `:58`, v6 `:58` (`NATIVE_EXPECT_OURS="${EXPECT_OURS:-8}"`) | **`8`** | `launch-card-cell.sh` `EXPECT_OURS` |
| **`NATIVE_EXPECT_OURS`** | `launch-card-cell.sh:90` (`EXPECT_OURS="${NATIVE_EXPECT_OURS:-$_cell_count}"`) | **`$_cell_count`, which is `1`** for a serial (non-packed) run | exclusivity/yield watchers `--expect-ours` |
| **→ CONFLICT:** two different fallback values (8 vs 1) for "how many of our own processes belong on the card" across the production wrapper and the bare launcher — not usually observed because the wrapper always sets it, but the disagreement is real if `launch-card-cell.sh` is invoked directly. |
| `NATIVE_DISK_ALLOWANCE_GIB` | `launch-card-cell.sh:433,436` | derived (`2× family.py disk-requirement`), or `40` if that computation fails | disk watch floor |
| `NATIVE_DISK_ABS_FLOOR_GIB` | `launch-card-cell.sh:439` | `50` | disk watch floor |
| `NATIVE_HELPER_IMAGE` | `launch-card-cell.sh:120`, `run_on_production_host.sh:277` | `python:3.11-slim` | helper containers (both files, same value — consistent, not a conflict) |
| `NATIVE_HOST_PROFILE` | `launch-card-cell.sh:425` (`--profile "${NATIVE_HOST_PROFILE:-datasphere}"`), `family.py:53` (`os.environ.get("NATIVE_HOST_PROFILE", "datasphere")`) | `datasphere` | consistent between the two call sites |
| `NATIVE_HOST_PROFILE` (production) | `run_on_production_host.sh:315-318` | **no default — refused if unset** at `FRAMES>=600000` | intentional: not a conflict, a stricter rule at production scale |
| `CELL_TIMEOUT_SECONDS` | `launch-card-cell.sh:57` | **no default — `${VAR:?...}` required** | intentional, same at `run_on_production_host.sh:328` |
| `NATIVE_SHM_SIZE` | `run_on_production_host.sh:777` | `2g` | container `--shm-size` |
| `NATIVE_VRAM_CAP_MIB` | v5/v6 `:62` (`"${VRAM_MIB:-4096}"`) | `4096` | forwarded into container via allowlist (`:827`) |
| `DISK_ABS_FLOOR/DISK_FLOOR_GIB` derivation | `run_on_production_host.sh:472-537` | `60` GB generic fallback if `family.py disk-requirement` fails (below production scale only; refuses at production scale) | `check_disk()` |
| `SAVE_EVERY` vs `SAVE_EVERY_FRAMES` | `run_probe.sh:1429-1436` | **already has an explicit conflict guard** (`NATIVE_KNOB_CONFLICT` exit 3 if both set and disagree; `NATIVE_KNOB_ALIAS` warning if only the old name is set) — cited here as precedent that this exact double-default failure mode has bitten this project before (its own comment: a 2026-09-04 incident where the mismatch produced a false SUCCESS). |
| `TASK` | v5/v6 `:60/:64` | **hardcoded `TASK=Door`**, not a `${TASK:-default}` — overrides any caller-set `TASK` unconditionally | `launch-card-cell.sh` → container |
| `TASK` | `run_probe.sh` (`${TASK:-Door}`, several sites), `family.py:1330` (`--task` argparse default `"Door"`) | `Door` | consistent with the wrapper's hardcode in the one case that matters (production) |

---

## D. Variables set/documented by a chain script but absent from the container env allowlist

`run_on_production_host.sh:811-829` is the only mechanism that forwards arbitrary env vars into the cell
container (plus a handful of explicit `-e` statements elsewhere in the same file for `RLVIGEN_ARCHIVE`,
`RECORDS_OUT`, `NATIVE_PLACES365_DIR`, `NATIVE_VENV`, `NATIVE_IMAGE_DIGEST`, `NATIVE_PIP_CACHE`,
`DEBIAN_FRONTEND`, `TZ`, `MUJOCO_GL`, `NVIDIA_DRIVER_CAPABILITIES`). I cross-checked every env-var-looking
token `run_probe.sh` reads (93 distinct tokens, grepped) against this combined set.

- **`RESUME_SNAPSHOT` — confirmed gap.** `run_probe.sh:361-371` reads it (`if [[ -n "${RESUME_SNAPSHOT:-}" && -f "${RESUME_SNAPSHOT}" ]]; then cp "$RESUME_SNAPSHOT" "$run_dir/snapshot.pt"; …`), with its own header comment (`:361`, dated 2026-09-03) documenting it as a real, deliberate feature ("places a checkpoint where RL-ViGen's train.py will find it"). It is **absent from the `run_on_production_host.sh:811-829` allowlist**, absent from the explicit `-e` list, and — I grepped the whole repo for the string — **absent from every other file in the repository** (`.py`, `.sh`, `.yaml`, `.json`, `.md`): no `cfg-*.yaml`, no test, no doc, nothing sets it or shows how to set it. The only theoretical path to reach the container is the generic `EXTRA_MOUNT_N=host:container:ENVVAR` mechanism (`run_on_production_host.sh:787-799`, documented at `:603-606` with `OFFLINE_EVAL_SNAPSHOT` as its own worked example, not `RESUME_SNAPSHOT`), and nothing in the repo does that either. As things stand, `RESUME_SNAPSHOT=/some/path` set on any of the 5 chain scripts would silently never reach `run_probe.sh`.
- **`PREFLIGHT_ONLY`** — read by `run_probe.sh` at `:2273,2296,2334,2355` and also absent from the allowlist, but I did not find it **set or documented by any of the 5 named chain scripts** (only inside `run_probe.sh` itself), so it doesn't meet this task's criterion for a D-finding cleanly — noting it only as a weaker, secondary observation.
- Everything else `run_probe.sh` reads that isn't in the allowlist (`BLOCKED_FAMILIES`, `DEFAULT_SEED`, `DEPENDENCY_BLOCKED`, `EXECUTION_KIND`, `FAILED_CELLS`, `FAMILY_TOOL`, `NATIVE_PIP_CACHE_DISCIPLINE`, `NATIVE_VENV_DISCIPLINE`, `PIP_CACHE_FLAGS`, `PYTHONPATH`, `REPO`, `RLV`, `RLVIGEN_COMMIT`) is, on inspection, a variable `run_probe.sh` **sets/exports/derives internally** for its own later use, or (for `REPO`, `RLV`) a token that only appears inside a code **comment**, not a live read — not a caller-facing knob, so not a D-finding.
- Host-side-only variables (`NATIVE_ALLOW_SHARED_CARD`, `NATIVE_YIELD_ON_PROCESSES`, `NATIVE_EXPECT_OURS`, `DOCKER_GPUS`, `NATIVE_RESULT_MIRROR`, `NATIVE_WORKDIR_PARENT`, `NATIVE_PLACES365_DIR_HOST`, `NATIVE_VENV_HOST`, `NATIVE_PIP_CACHE_HOST`, `NATIVE_SHM_SIZE`, `NATIVE_HOST_DRY_RUN`, `NATIVE_ACCEPT_*`, watch-budget tunables) are correctly **not** in the allowlist — I confirmed none of them appear in `run_probe.sh`'s own env-var reads, so they aren't gaps, they're host/launcher-only by design.

---

## Assumptions and inferences (collected)
1. `${HOME}/rlvigen-work/…` paths in `wait-and-train-v4.sh` imply a flattened deploy of `host-scripts/*`
   content directly under `~/rlvigen-work/` on the production host — **(inferred)**, not verified (no SSH access, per the task's own scope).
2. The two oddly-shaped root directories in §B5 are almost certainly produced by something that used a
   `run_on_production_host.sh` command string (or its dry-run output / positional args) as a filesystem path
   rather than executing it — the string match is exact, but which script actually ran `mkdir -p` with it is
   **not identified** — **(inferred)** resemblance only, root cause unconfirmed.
3. `runnable/`'s 3,859 untracked-of-3,883 files are assumed to be vendored per-baseline dependencies/caches
   rather than something else — **(inferred)** from the git-tracked ratio and `families.json`'s per-family
   `cwd`/`pythonpath` entries pointing there; contents not opened.
4. B5's `train.py` REFERENCED classification is uncertain: the grep hits could be matching other files' own
   `train.py` (e.g. `runnable/<family>/train.py`) mentioned inside test files, not the root file specifically.
