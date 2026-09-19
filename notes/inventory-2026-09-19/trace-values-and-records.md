> **Executor output, not a finding of record.** Produced 2026-09-19 by a read-only Sonnet executor, by reading code only (nothing executed). Re-checked by the lead: host-profile coverage per family (`rlvigen`, `ibac_sni`, `ctrl` have a `v100` block; `dmc_gb`, `idaac`, `alda`, `ppg` have none), `NATIVE_EXTRA_OVERRIDES` recorded in the live `svea` cell as `replay_buffer_size=620000` both in `argv` and under `extra_overrides`, and the endpoint fallback at `production_reading.py:200`. Its own NOT CHECKED list is at the top; the per-family evaluator branches and parsers are in it.

# Trace: value resolution and evaluation-to-table pipeline — many-gens-rl-vigen

READ-ONLY. Nothing executed, nothing edited in the repository. All claims below carry file:line and a
verbatim excerpt unless marked **(inferred)**.

## NOT CHECKED / limits (read this first)

- `scripts/eval_grid.py` (1,592 lines): read the row-builder (`_run_grid`, ~1140-1330) and `main()`'s
  arg parsing / context dict (~1338-1589) in full. The seven per-family branches it calls
  (`run_scene_idaac`, `run_scene_ctrl`, `run_scene_alda`, `run_scene_ibac_sni`, `run_scene_ppg`,
  `run_scene_dmc_gb`, `run_scene`) were **not** read — I only confirmed they're called and what they
  return (`returns, successes, flags`).
- `datasphere/native/normalize_curves.py` (695 lines): read the shared `record()` envelope (~140-220)
  and grepped for every `frame=`/`"frame"` site to find type inconsistencies. The seven per-family
  curve-parsing branches (rlvigen/dmc_gb/idaac/alda/ppg/ibac_sni/ctrl, each parsing a different log
  format) were **not** read end-to-end.
- `scripts/eval_across_scenes.py` and `scripts/eval_provenance.py`: confirmed as imports of
  `eval_grid.py`, contents **not opened** this round.
- `scripts/production_run_register.py`, `scripts/audit_attempt_ledger.py`,
  `scripts/audit_record_frame_provenance.py`: **not opened** this round (out of the requested scope,
  which stops at `production_reading.py`); `record_host_run.py`'s docstring says the register is
  generated from `results/records/`, not independently verified here.
- No on-disk data was inspected — `results/records/*.jsonl`, `results/host-runs.jsonl`,
  `results/submissions.jsonl`, and any real `effective_config.json` are **code-only** claims about what
  the writers would produce, not observations of what they contain today.
- `families.json`: read rlvigen's full family block (all ~146 lines) and dmc_gb's `production` block
  partially; ppg/ibac_sni/ctrl/alda were sampled only for `host_profiles` presence (via a one-line
  Python read of the parsed JSON, not by reading their raw JSON text) and their `constants`/`options`
  blocks were **not** individually read.
- Part C is not an exhaustive grep of every `.get(x, default)` in every file touched — it's what turned
  up while reading Parts A and B for their stated purpose, ranked by consequence. I found fewer than the
  40-item cap (about 20 defensible entries); **I did not hit the cap**, so this is not a truncated list,
  but it is also not a certified-complete one.

---

## Part A — value resolution inside the container

### A.0 The functions, read in full

`datasphere/native/family.py`:
- `load()` (`:33-35`), `descriptor()` (`:38-42`), `host_profile()` (`:45-57`), `resolved_descriptor()`
  (`:60-75`), `substitutions()` (`:112-113`), `render()` (`:116-121`), `full_fields()` (`:124-140`),
  `with_constants()` (`:143-150`), `command()` (`:153-159`) — all read in full.
- `production_env()` (`:640-742`) and `production()` (`:241-243`) also read in full, because
  `full_fields`/`resolved_descriptor` alone don't explain the three known-answer values; the production
  overlay is a separate, later-applied layer (see A.1 step 5).

`run_probe.sh`: read `:1-65` (profile-default bootstrap, `normalize_eval_sentinel`), `:320-524`
(`run_one_cell`, the argv build and the `effective_config.json` writer), `:790-841`
(`require_production_configuration`, `apply_production_settings`), `:843-883` (`--run-cells` entry, the
`run_eval_every` resolution), and `:2150-2220` (`RLVIGEN_PLACES_WORKERS` default) — all in full for
those ranges.

### A.1 Precedence order (lowest to highest — what wins when two layers set the same key)

1. **families.json base descriptor**, per family — `constants`, `production`, `environment`,
   `positional`, `options`. Loaded by `load()`/`descriptor()`.
   `family.py:33-35`
   ```python
   def load(path: Path | None = None) -> dict:
       descriptors = json.loads((path or DESCRIPTORS).read_text())
   ```

2. **`host_profiles.<profile>` override**, selected by `NATIVE_HOST_PROFILE` (default `"datasphere"`),
   merged **shallowly, per-section** (`constants`/`production`/`environment` each get one dict-spread
   merge; anything outside those three section names is refused).
   `family.py:52-53,64,71-75`
   ```python
   selected = selected or os.environ.get("NATIVE_HOST_PROFILE", "datasphere")
   ...
   override = entry.get("host_profiles", {}).get(host_profile(path, profile), {})
   ...
   for section in ("constants", "production", "environment"):
       if section in override:
           resolved[section] = {**entry.get(section, {}), **override[section]}
   ```
   **This is a per-key shallow merge, not deep**: if the override redeclares a key that itself holds a
   nested value, the override's value replaces it wholesale (there's no recursive merge below one level).
   **4 of 7 families have no override to apply at all** — `dmc_gb`, `idaac` and `alda` have no
   `host_profiles` key in their descriptor; `ppg`'s is present but empty (`families.json:607`,
   `"host_profiles": {}`). For these four, selecting `NATIVE_HOST_PROFILE=v100` changes **nothing**:
   `.get("host_profiles", {})` returns `{}`, `.get("v100", {})` on that returns `{}`, and the loop at
   `family.py:72-74` never fires. Only `rlvigen`, `ibac_sni` and `ctrl` declare a `v100` block
   (verified by parsing `families.json` and listing each family's `host_profiles` keys: `rlvigen ->
   ['v100']`, `dmc_gb -> MISSING KEY ENTIRELY`, `idaac -> MISSING KEY ENTIRELY`, `alda -> MISSING KEY
   ENTIRELY`, `ppg -> []`, `ibac_sni -> ['v100']`, `ctrl -> ['v100']`).

3. **Caller-supplied `fields` win over descriptor `constants`** — `with_constants()` puts `constants`
   first and `fields` second in a dict spread, so an identical key from the caller overrides the
   descriptor.
   `family.py:143,150`
   ```python
   def with_constants(entry: dict, fields: dict) -> dict:
       return {**entry.get("constants", {}), **fields}
   ```
   The caller here is `run_probe.sh:381-383`, which always passes `--family/--baseline/--task/--frames/
   --eval-every/--eval-episodes/--save-every/--seed/--run-dir` explicitly for every cell — so in the
   normal path `family.py`'s own argparse defaults (`--frames` default `"10000"` etc., `family.py:1331`)
   never fire; they only matter if `family.py command` is invoked directly.

4. **Derived fields, filled only if absent** — `full_fields()` computes `endpoint` from
   `expected_endpoint()` when `frames` is present and `endpoint` isn't already set, and defaults
   `save_every` to `frames` (or `""` if `frames` itself is absent) if not already set.
   `family.py:132-140`
   ```python
   merged = with_constants(entry, fields)
   if "frames" in merged and "endpoint" not in merged:
       merged["endpoint"] = str(expected_endpoint(family, int(merged["frames"]), path))
   merged.setdefault("save_every", merged.get("frames", ""))
   ```

5. **Production-scale overlay, applied at the SHELL level, one layer above family.py** —
   `apply_production_settings()` reads `family.py production-env`'s output (which is
   `production_env()`, itself built from `resolved_descriptor(...)["production"]`, i.e. layers 1-2
   already folded in) and exports each `KEY=VALUE` **only if that shell var is currently unset**; if it
   IS set and disagrees, strict mode (automatic at `FRAMES>=600000`) refuses the whole run.
   `run_probe.sh:811,822-839`
   ```python
   apply_production_settings() {
     [[ -n "${NATIVE_PRODUCTION:-}" ]] || return 0
   ...
       current="${!prod_key:-}"
       if [[ -z "$current" ]]; then
         export "$prod_key=$prod_value"
   ```
   So an operator/job-config env var that is already set **outranks** the families.json production
   block; the production block only fills gaps (or blocks the run outright in strict mode if it
   disagrees with what's already set).

6. **`NATIVE_EXTRA_OVERRIDES`, appended verbatim as extra argv tokens after everything above** —
   the single highest-precedence layer, and it operates entirely outside `family.py`; it exploits
   argparse's/hydra's "last repeated value wins" behavior.
   `run_probe.sh:404-414,508`
   ```python
   if [[ -n "${NATIVE_EXTRA_OVERRIDES:-}" ]]; then
     extra_overrides=(${NATIVE_EXTRA_OVERRIDES})
   ...
   bash "${argv[@]}" ${extra_overrides[@]+"${extra_overrides[@]}"} || return 1
   ```

7. **Final substitution** — `render()` does `template.format(**fields)` over whatever `fields` dict
   resulted from steps 1-4; a template referencing a key that isn't in the merged dict **fails loudly**
   (raises via `fail()`), which is the deliberate opposite of a silent default.
   `family.py:116-121`
   ```python
   def render(template: str, fields: dict) -> str:
       try:
           return template.format(**fields)
       except KeyError as error:
           fail(f"template {template!r} needs an unknown field: {error}")
   ```

### A.2 `NATIVE_EXTRA_OVERRIDES`

**What it can change:** anything expressible as an extra CLI token to the family's own launcher —
because it is appended raw to the rendered argv, it is not restricted to declared template fields at
all; it can add a flag the descriptor never mentions.

**Where it's produced (one real source found):** `production_env()` sets it from the descriptor's own
`replay_capacity`/`replay_capacity_option` pair, to cap the off-policy replay buffer at production scale.
`family.py:730-741`
```python
capacity = settings.get("replay_capacity")
option = settings.get("replay_capacity_option")
if capacity is not None:
    if option:
        out["NATIVE_EXTRA_OVERRIDES"] = render(option, {"replay_capacity": str(capacity)})
```
For rlvigen: `replay_capacity_option` = `"replay_buffer_size={replay_capacity}"` (`families.json:125`)
and, under the v100 profile, `replay_capacity` = `620000` (`families.json:51`, overriding the base
`300000` at `families.json:124`) → `NATIVE_EXTRA_OVERRIDES="replay_buffer_size=620000"`. For `dmc_gb`,
`replay_capacity_option` is `null` (`families.json:246`), so it is `NATIVE_PRODUCTION_UNAPPLIED`
instead (see below) — rad/soda run **uncapped** at production scale, by declared, reasoned choice, not
by omission.

**Where it's applied:** `run_probe.sh:404-414` reads the env var into a bash array; `:446` includes it
in what gets hashed into the `effective_config.json` argv capture; `:508` appends it to the executed
command.

**Is it recorded?** Yes, twice, deliberately:
- `run_probe.sh:491,508` — the **merged, executed** argv (post-override) is what `effective_config.json`
  stores under `"argv"`, per the file's own comment: "The captured argv is the EXECUTED one, overrides
  included" (`:433`), because an earlier version recorded the pre-override argv separately and it drifted
  from what actually ran.
- `run_probe.sh:492` — the override tail is **also** kept separately, so provenance ("this came from a
  job override, not the descriptor") stays legible without diffing two argv lists:
  ```python
  "extra_overrides": [a for a in os.environ.get("NATIVE_EXTRA_OVERRIDES", "").split() if a],
  ```

**The unreachable declared case:** when `replay_capacity` is set but no `replay_capacity_option` exists
to express it (declared-and-unreachable), `production_env()` records that fact instead of silently doing
nothing:
`family.py:736-741`
```python
out["NATIVE_PRODUCTION_UNAPPLIED"] = (
    f"replay_capacity={capacity} is declared for {family} but no option exposes it; "
    "capping needs a source change")
```
and `apply_production_settings()` echoes it rather than exporting it: `run_probe.sh:824-827`
(`NATIVE_PRODUCTION_UNAPPLIED` is treated as a log-only key, never `export`ed).

### A.3 Worked example — `svea:101`, profile `v100`, `FRAMES=600000`

`svea` is a baseline of family `rlvigen` (`families.json:88-93`). rlvigen's template
(`families.json:59-71`):
```
"positional": ["{baseline}", "{task}"],
"options": [
  "num_train_frames={frames}", "eval_every_frames={eval_every}", "num_eval_episodes={eval_episodes}",
  "seed={seed}", "use_wandb=False", "save_snapshot=True", "hydra.run.dir={run_dir}"
]
```

| Placeholder | Resolves to | Source (file:line) |
|---|---|---|
| `{baseline}` | `svea` | passed by caller, `run_probe.sh:341-343` |
| `{task}` | `Door` | `TASK` env default, `run_probe.sh:880` (`"${TASK:-Door}"`) |
| `{frames}` | `600000` | operator-set `FRAMES` env var, forwarded by `run_probe.sh:880` (`"${FRAMES:-10000}"` — not from families.json; families.json has no `frames` key) |
| `{eval_every}` | the **literal string `"null"`** | `families.json:129-130`: rlvigen's `production.eval_every` is JSON `null`, and `online_eval_disabled_spelling` is the **string** `"null"`. `production_env()` (`family.py:664-676`) sees `has_eval_option=True` and `eval_every is None`, so it sets `NATIVE_DISABLE_ONLINE_EVAL=1` and `NATIVE_ONLINE_EVAL_DISABLED_SPELLING="null"` instead of a numeric `EVAL_EVERY_FRAMES`. `run_probe.sh:861-876` then resolves `run_eval_every="${NATIVE_ONLINE_EVAL_DISABLED_SPELLING:-}"` = `"null"`, which becomes the rendered `eval_every_frames=null` — Hydra parses that to Python `None`, which is rlvigen's own upstream disable path (`utils.Every` returns `False` for cadence `None`). |
| `{eval_episodes}` | `20` | `families.json:133` (`"eval_episodes": 20`) → `production_env()` `family.py:722-726` → `EVAL_EPISODES=20` → `run_probe.sh:881` (`"${EVAL_EPISODES:-2}"`) |
| `{seed}` | `101` | passed explicitly by the wrapper chain (`host-scripts/train-production-cell-v5.sh:53`, `SEED="${SEED:-101}"`) |
| `use_wandb=False`, `save_snapshot=True` | literal, no placeholder | `families.json:68-69` |
| `{run_dir}` | a **runtime-constructed path**, e.g. `$work_root/runs/svea-s101` | **not** a families.json value — built by `run_probe.sh:359` (`local run_dir="$work_root/runs/$identifier"`) where `$work_root` is a host/container path (`/tmp/native-work` by default, `run_probe.sh:889` area) and `identifier` comes from `cell_id()` (`run_probe.sh:324`, `"%s-s%s"`). Resolved by reading the code, but it's a **path, not a constant** — I mark this **not a families.json-cited value** rather than UNRESOLVED, since its source code is fully identified. |

No placeholder was UNRESOLVED in the strict sense (source not found); `{run_dir}` is the only one whose
source is outside families.json entirely.

**`{save_every}` does not appear anywhere in rlvigen's own `options` template** — it is used only by
`dmc_gb`/`ctrl`/`alda`/`ibac_sni`/`idaac`/`ppg` (e.g. `families.json:193`, dmc_gb's `--save_freq
{save_every}`). For rlvigen, the training-time checkpoint cadence is upstream-hardcoded at
`train.py:309`'s `global_step % int(5e4) == 0` (quoted verbatim in `families.json:155`'s
`save_every_reason`: "NOT a choice... Recorded as 50000 because that is what the code does"). So the
**known-answer's `effective_config.json` field `save_every = 50000`** is real and traced fully, but it
does **not** drive rlvigen's behavior through the rendered argv at all — it flows: `families.json:149`
(`"save_every": 50000`) → `production_env()` `family.py:722-726` sets `SAVE_EVERY_FRAMES="50000"` →
`apply_production_settings` exports it (unset case) → `run_probe.sh:1436`
(`save_every="${SAVE_EVERY_FRAMES:-${SAVE_EVERY:-$frames}}"`) → per-cell `cell_save_every` (`:340`) →
captured directly into `effective_config.json`'s `"save_every"` field via `_EC_SAVE_EVERY`
(`run_probe.sh:448,481`). It is a **recorded fact about what the code does**, not a **parameter that
does it** — the descriptor's own `save_every_reason` says exactly this.

**`host_profile = v100`** comes straight from the `NATIVE_HOST_PROFILE` env var, which
`host-scripts/train-production-cell-v5.sh:61` hardcodes (`NATIVE_HOST_PROFILE=v100`), and
`effective_config.json`'s `"host_profile"` field is a **direct env-var read, not `family.py
host-profile`'s validated resolution**:
`run_probe.sh:484-488`
```python
# Same default as the record path and as family.host_profile(), which is the authority. These
# disagreed: this site stamped null where the record stamped "datasphere"...
"host_profile": os.environ.get("NATIVE_HOST_PROFILE", "datasphere"),
```
(the file's own comment documents a past instance of exactly the "same fact, two homes, briefly
disagreeing" defect this task is hunting for — already fixed at the time of reading, cited as
precedent).

**`runner_environment.RLVIGEN_PLACES_WORKERS = 0`** is a **plain shell default, not a families.json
value at all**:
`run_probe.sh:2206-2207`
```python
places_workers="${RLVIGEN_PLACES_WORKERS:-0}"
export RLVIGEN_PLACES_WORKERS="$places_workers"
```
then swept into `effective_config.json`'s `runner_environment` because its name matches the capture
prefix list at `run_probe.sh:463-465` (`"RLVIGEN_"` is one of the allowed prefixes) and it survives the
redaction/secret filters at `:469-473`. Its own 40-line header comment (`:2160-2205`) documents why `0`
and not upstream's `8`: a hardcoded-8 DataLoader worker count corrupted the glibc heap intermittently
(`malloc_consolidate(): unaligned fastbin chunk detected`) across multiple production and diagnostic
cells; `0` removes the forked worker entirely rather than reducing its odds.

### A.4 `effective_config.json`

**Writer:** `run_probe.sh:451-501`, an inline `python3 -c` block. **Top-level keys, as written:**
`cell`, `family`, `baseline`, `seed`, `task`, `frames_requested`, `save_every`, `eval_every`,
`eval_episodes`, `host_profile`, `argv`, `extra_overrides`, `runner_environment` (a filtered
prefix-matched dict of the container's own env, see A.3), `cell_environment` (the family-specific
environment `family.py environment` resolved for this cell, e.g. `ALDA_RESULTS` — `run_probe.sh:494-499`
and `family.py:744-752`).

**What it does NOT contain** (confirmed by reading the writer — nothing else is captured):
- **Upstream hydra/argparse defaults never touched by a families.json key or a CLI flag.** Only the
  keys named in the `options`/`positional` templates are rendered; anything the upstream training
  script defaults on its own (e.g. hydra config-file defaults for hyperparameters no `options` entry
  ever names — network width, optimizer betas, replay ratio, etc.) is invisible to this artifact. This
  is a structural gap, not a bug: the file only records what family.py's descriptor model expresses.
- **The unresolved template source vs. the rendered value distinction for anything besides
  `save_every`** — `effective_config.json` stores the numbers, not which layer of the A.1 precedence
  chain produced them (production overlay vs. descriptor base vs. CLI field vs. extra-override tail) —
  except for `extra_overrides`, which is the one layer given its own field precisely because that
  ambiguity had already caused a misreading (`run_probe.sh:433-444`, the PPG geometry probe incident).
- **The families.json `_reason` fields** (`save_every_reason`, `replay_capacity_reason`, etc.) — the
  human-readable justification for every value lives only in the source descriptor, never copied into
  the per-run artifact.
- **RL-ViGen's own hydra `.yaml` config tree contents** (third-party, not read this round; not
  expanded per task scope in the prior inventory either).

---

## Part B — from an evaluation episode to a printed number

### B.1 Where evaluation runs

`run_probe.sh` — endpoint: `:1132-1147` (`run_endpoint_eval`, calls `scripts/eval_grid.py --eval-scope
endpoint --append --out "$cell_out/offline_eval_endpoint${out_suffix}.jsonl"`, looped once per
`ENDPOINT_EVAL_POLICY_MODES` entry). Curve: `:1204-1217` (`run_curve_eval`, calls the same script
`--eval-scope curve --append --out "$cell_out/offline_eval_curve.jsonl"`, once per retained checkpoint
stamp).

### B.2 `scripts/eval_grid.py` writes the rows

The row schema is **not owned by `eval_grid.py`** — it imports the envelope from
`datasphere/native/normalize_curves.py` "by path, not by package" so both files can never define two
schemas:
`scripts/eval_grid.py:1328-1335`
```python
def _record_factory():
    """normalize_curves owns the record envelope; import it by path, not by package."""
    spec = importlib.util.spec_from_file_location(
        "normalize_curves", ROOT / "datasphere" / "native" / "normalize_curves.py")
    ...
    return module.record
```

Envelope defaults, `datasphere/native/normalize_curves.py:161-181`:
```python
base = {
    "schema": SCHEMA, "phase": "eval", "regime": None, "scene_set": None, "episodes": None,
    "episode_return_mean": None, "episode_return_sd": None, "success_rate": None,
    "checkpoint_sha256": None, "evaluator_revision": None, "evaluator_scope": None,
    "evaluator_scope_revision": None, "evaluator_measurement_revision": None,
    "provenance": None, "conventions": None, "native": {},
}
base.update(fields)
```

Per-row context, `scripts/eval_grid.py:1585-1587`:
```python
context = {"cell": f"{a.baseline}-s{a.seed}", "baseline": a.baseline,
           "family": a.family, "seed": a.seed, "eval_scope": a.eval_scope,
           "checkpoint_sha256": checkpoint_sha256}
```

Per-scene emitted row, `scripts/eval_grid.py:1254-1302` (field names as written): `phase="offline-eval"`,
`frame`, `regime`, `scene_set` (a string — either one scene number or the comma-joined pooled list),
`episodes`, `episode_return_mean`, `episode_return_sd`, `success_rate`, `evaluator_revision`,
`evaluator_code_revision`, `evaluator_config_revision`, `evaluator_scope`, `evaluator_scope_revision`,
`evaluator_measurement_revision`, and a nested `native` dict: `returns`, `successes`,
`episode_success`, `runtime_import_manifest`, `placement_condition_seeds`, `placement_witnesses`,
`policy_action_diagnostics`, `eval_episode_ids`, `episode_diagnostics`. A second, **pooled**, ten-scene
row is emitted per regime (`:1305-1318`) with `scene_set` = the comma-joined scene list — this is the
row `production_reading.py` later drops by design (B.5).

`EVALUATOR_REVISION` is computed by the SAME function both the writer and every downstream reader call
— no duplicated logic here:
`scripts/eval_grid.py:1491` `EVALUATOR_REVISION = evaluator_family_revision(ROOT, a.family)` — same
function `campaign_status._live_revisions()` calls (`scripts/campaign_status.py:60-64`).

### B.3 Rows into `records.jsonl` / `records_delivery.jsonl`

`normalize_curves.py` reads **training-cell** logs (per-family branches, not read this round) and writes
one row per training-curve point into `records.jsonl`:
`run_probe.sh:2583-2586`
```python
python3 datasphere/native/normalize_curves.py --directory "$target" \
    --output "$target/records.jsonl" || normalizer_status="$?"
```
`records.jsonl` therefore contains **only training-curve rows**, never the `offline_eval_*.jsonl`
files eval_grid.py wrote — those sit beside it in the cell/job output tree.

`collect_record_delivery()` (`run_probe.sh:2662-2789`) assembles the delivered bundle by concatenating,
in order: `records.jsonl`, every `offline_eval_*.jsonl` at the job root, and every
`cells/*/offline_eval_*.jsonl` (`:2729`). For the two `offline_eval_*` sources specifically, each row is
enriched with the run manifest **only if it doesn't already carry one**:
`run_probe.sh:2733-2759`
```python
row.setdefault("_run_provenance", manifest)
```
— training rows from `normalize_curves.py` already carry `_run_provenance` themselves (comment at
`:2719-2725`), so this is a **field the writer names differently by origin but the same key by the
time it's delivered**: not a mismatch, but worth noting as a place two different producers converge on
one field name only because this collector enforces it.

The result is written to `$out/records_delivery.jsonl` and, if `RECORDS_OUT` is set, also copied to that
external path (`run_probe.sh:2792-2802`).

### B.4 `collect-host-run.sh` on the laptop

`datasphere/native/collect-host-run.sh:57,61,63`:
```bash
RECORDS_DIR="${RECORDS_DIR:-results/records}"
JOB_ID="$(basename "${RUN_DIR%/}")"
DEST="$RECORDS_DIR/${JOB_ID}__records.jsonl"
```
and (`:62`, from the earlier read this session): `SRC="$RUN_DIR/native-out/records_delivery.jsonl"` —
it copies the **delivery** bundle (training + offline-eval rows, enriched), not `records.jsonl` alone;
its own header comment (`:27-48`, read in the prior session) documents a real incident where reading
`records.jsonl` instead silently produced near-empty output because that file holds only training rows.
`DEST` lands in `results/records/`, which is exactly the directory `campaign_status._records_index()`
globs (B.5) — this is the seam that makes the whole downstream table possible, and it depends on nobody
pointing `RECORDS_DIR` elsewhere without also telling `campaign_status.py`.

### B.5 `scripts/production_reading.py` — selection, grouping, gate

**Index build**, `scripts/campaign_status.py:85-103`:
```python
def _records_index() -> dict[tuple[str, int], list[dict]]:
    for path in (ROOT / "results" / "records").glob("*.jsonl"):
        ...
        baseline, seed = row.get("baseline"), row.get("seed")
        if baseline is None or seed is None:
            continue
        index[(baseline, int(seed))].append(row)
```
Keyed on the row's own `baseline`/`seed` fields — exactly the ones `eval_grid.py:1585-1586` writes.

**Cell state**, `scripts/campaign_status.py:185-200` (`state_of`): a cell is `DONE` only if a row exists
at the schedule's `endpoint` frame AND its `evaluator_revision` matches the CURRENT one
(`campaign_status.py:191`, `r.get("evaluator_revision") == live.get(family)`); otherwise `SUPERSEDED`
(stale evaluator), `PARTIAL`/`RUNNING`/`MISSING` from `results/host-runs.jsonl` and
`results/submissions.jsonl`.

**Endpoint default** — `scripts/production_reading.py:200`:
```python
endpoint = entry.get("executed_endpoint", schedule.get("frames"))
```
If a schedule row doesn't declare its own `executed_endpoint`, the code silently falls back to the
job-wide `frames`. This is consequential because `family.py`'s own `expected_endpoint()` rule
(mentioned in `run_probe.sh:509-512`, not re-read this round) says the executed endpoint is **not**
always the requested frame count — idaac floors to a rollout quantum, ppg overshoots to the next
segment. A schedule entry missing its own `executed_endpoint` for one of those two families would
silently compare against the wrong frame and read a genuinely-finished cell as `RUNNING`/`MISSING`
rather than `DONE`.

**Row filtering, `_by_scene`**, `scripts/production_reading.py:91-131`, drops (with a named, tallied
reason, not silently):
- `row.get("eval_scope") != "endpoint"` → `"not an endpoint row"` (drops curve rows)
- `_is_pooled(row)` (`scene_set` contains a comma) → `"pooled ten-scene row"`
- missing `conventions.eval_policy_mode`, `regime`, or the requested field → named reasons

`DROPPED_BY_DESIGN = frozenset({"not an endpoint row", "pooled ten-scene row"})` (`:88`) — everything
else that gets dropped is printed as UNREADABLE rather than silently absorbed into the same bucket
(`:272-281`).

**Competence gate**, `scripts/production_reading.py:161-176`, uses `MIN_DENOM_SUCCESS`, which lives at
`scripts/regime_retention_report.py:76`:
```python
MIN_DENOM_SUCCESS = 0.25
```
imported rather than restated (`production_reading.py:66`), because an earlier local copy of the
threshold drifted (the file's own comment, `:166-169`, describes a policy scoring 1/20 that passed a
looser gate and produced a fabricated-looking 0.947 retention ratio).

**Aggregation**, `EVAL-PROTOCOL §4c` per the module docstring: `Y` = one row's `episode_return_mean`
(already an average over episodes); `Ȳ` = mean over the ten per-scene `Y` values for one trained policy;
seeds, never scenes or episodes, are the replicates (`per_seed_means`, `:147-151`).

### B.6 Field-name / representation seams found

1. **The exact seam the coordinator named, confirmed and dated.** `scripts/record_host_run.py:63-73`:
   ```python
   # The cell's own top-level `seed` first: argv spelling differs per family (`--seed 101` for the
   # on-policy families, hydra's `seed=101` for rlvigen), and a None seed mis-keys the attempt
   # ledger, which groups on (baseline, seed).
   seed = str(cfg["seed"]) if cfg.get("seed") is not None else None
   for i, a in enumerate(argv):
       if seed is not None:
           break
       if a == "--seed" and i + 1 < len(argv):
           seed = argv[i + 1]
       elif isinstance(a, str) and a.startswith("seed="):
           seed = a.split("=", 1)[1]
   ```
   `git log` on this file: `415687c 2026-09-19 record_host_run: read the seed from the cell's own
   config, not only from an argv --seed flag` — fixed **today**, matching the coordinator's "until
   today" exactly. Before this commit, the function scanned `argv` for a literal `--seed VALUE` token
   only; rlvigen's own template renders `seed={seed}` (`families.json:67`, e.g. `seed=101`), which
   never matches `--seed`, so every rlvigen host-run entry would have recorded `seed=None` and
   `_host_ended()`/`_host_running()` (`campaign_status.py:151,178`, `int(row.get("seed") or 0)`) would
   have silently bucketed it under seed `0` instead — a fabricated cell that doesn't exist, indexed
   next to any REAL seed-0 attempt (none currently scheduled, but nothing prevents it structurally).
   This is now fixed by reading `effective_config.json`'s own top-level `"seed"` field first (which
   `run_probe.sh:478` writes uniformly regardless of family), and falling back to argv-scanning
   (both spellings) only if that's absent.

2. **`frame` is written as `int`, `str`, and `float` by different producers, and readers defend against
   all three rather than the writers agreeing on one.** `datasphere/native/normalize_curves.py:512,517`
   pass `frame=float(frame)` for at least one family's branch (not identified further this round; the
   surrounding per-family block was not read), while `eval_grid.py`'s `--frame` argparse type is `int`
   (`scripts/eval_grid.py:1348`). Every consumer that compares against a schedule's `endpoint` handles
   this by checking both forms rather than one: `scripts/campaign_status.py:189`
   (`r.get("frame") in (endpoint, str(endpoint))`) and `scripts/production_reading.py:208`
   (identical pattern). Numerically this tolerates the float case too (Python `600000.0 == 600000`), so
   it is not currently a live bug, but it is the same class of "two homes disagree on shape and the
   reader compensates" the coordinator flagged for `--seed`, and I could not rule out a case (e.g. a
   frame value that gets `str()`-ified with a trailing `.0` matched against a schedule that expects a
   bare int string) where the `in (endpoint, str(endpoint))` guard would miss.

3. **`host_profile` in `effective_config.json` is a raw env-var read, not `family.py host_profile()`'s
   validated resolution** (already flagged in A.3) — `run_probe.sh:488`'s own comment documents that
   this exact field disagreed with the "record path" default (`null` vs `"datasphere"`) until fixed;
   cited here again because it is precisely a same-fact-two-homes seam, now closed, in the same file
   family as the `--seed` one.

---

## Part C — silent defaults in Parts A and B (not capped; ~20 found, most consequential first)

1. **`family.py:64`** — `override = entry.get("host_profiles", {}).get(host_profile(path, profile), {})`
   — a family with no `host_profiles` key, or no entry for the selected profile, gets an **empty
   override silently**, not a refusal. Confirmed consequential: `dmc_gb`, `idaac`, `alda` have no
   `host_profiles` key at all; `ppg`'s is present but `{}`. Under `NATIVE_HOST_PROFILE=v100`, these four
   families' production runs use their base (non-v100-tuned) `constants`/`production` values,
   indistinguishable in `effective_config.json` from a family that was deliberately tuned and happens to
   need no change — the record has no field for "this family declares no v100 profile."

2. **`scripts/production_reading.py:200`** — `endpoint = entry.get("executed_endpoint",
   schedule.get("frames"))` — silently falls back to the job-wide requested frame count if a schedule
   row lacks its own executed (rounded) endpoint. Consequential for idaac/ppg specifically, whose
   executed endpoint is documented elsewhere (`run_probe.sh:509-512`) to differ from the requested one.

3. **`scripts/campaign_status.py:151,178`** — `key = (row.get("baseline"), int(row.get("seed") or 0))`
   in both `_host_ended` and `_host_running` — a host-run ledger entry with a missing/falsy seed is
   silently filed under seed `0` rather than refused or dropped. Directly the failure mode the
   `record_host_run.py` fix (B.6.1) exists to prevent at the write side; this is the same silent
   coercion still present at the read side.

4. **`run_probe.sh:2206`** — `places_workers="${RLVIGEN_PLACES_WORKERS:-0}"` — a real behavioral default
   (changes pixel-level augmentation and is documented as chosen for crash-safety, `:2160-2205`), but
   still a silent shell default: an operator who unsets or misspells the variable gets `0` with no
   distinguishing signal from a deliberate `0`.

5. **`family.py:139`** — `merged.setdefault("save_every", merged.get("frames", ""))` — if `frames` is
   itself absent from `fields`, `save_every` silently becomes the empty string `""` rather than failing;
   for a family whose `options` template contains `{save_every}` (dmc_gb, ctrl, alda, ppg, ibac_sni),
   this would render an empty-valued CLI flag rather than refuse at the point the ambiguity exists.

6. `run_probe.sh:878` — `run_eval_every="${EVAL_EVERY_FRAMES:-${FRAMES:-10000}}"` — two chained silent
   defaults (the online-eval cadence falls back to the frame budget, which itself falls back to `10000`).

7. `run_probe.sh:1436` — `save_every="${SAVE_EVERY_FRAMES:-${SAVE_EVERY:-$frames}}"` — three-deep
   fallback chain for the checkpoint cadence.

8. `run_probe.sh:340` — `local cell_save_every="${save_every:-$frames}"` — per-cell re-application of
   the same fallback, one call frame later.

9. `family.py:53` — `selected = selected or os.environ.get("NATIVE_HOST_PROFILE", "datasphere")` —
   silent default profile, though `host_profile()` does refuse loudly (`:55-56`) if the resolved name
   isn't in `_host_profiles` — so this default is silent, but an outright typo is not.

10. `family.py:676` — `out["NATIVE_ONLINE_EVAL_DISABLED_SPELLING"] = str(settings.get(
    "online_eval_disabled_spelling", "2147483647"))` — silently falls back to the numeric sentinel
    `2147483647` if a family declares no disabled-spelling value at all; `run_probe.sh:17-32`'s own
    header documents that this exact sentinel previously caused a real step-0 evaluation to run under a
    manifest claiming evaluation was off.

11. `record_host_run.py:82` — `"frames_requested": int(cfg.get("frames_requested") or 0) or None` —
    a genuinely-requested `0` frames and a missing field are indistinguishable in the ledger; both
    become `None`.

12. `scripts/eval_grid.py:1347` — `ap.add_argument("--seed", type=int, default=0, ...)` — silently
    seeds `0` if `eval_grid.py` is ever invoked without `--seed`; not observed to happen in the traced
    path (`run_probe.sh` always passes it), but present in the code.

13. `scripts/eval_grid.py:1348` — `ap.add_argument("--frame", type=int, default=None, ...)` — a `None`
    frame silently fails to match any `endpoint` comparison downstream rather than refusing at write
    time; again not observed to fire in the traced path.

14. `family.py:1332-1333` — `--eval-every` default `"10000"`, `--eval-episodes` default `"2"` — same
    class as #12, standalone-invocation-only defaults that the traced path never exercises but that
    exist in the same function this task was asked to read.

15. `scripts/production_reading.py:255` — `rates = [r for _, r in (success or {}).get((baseline, mode,
    regime), []) if r is not None]` then `succ = f"{statistics.fmean(rates):.3f}" if rates else "-"` —
    an empty rate list silently prints `"-"` rather than a distinguishable "no data" vs "zero success"
    marker (arguably fine, since `-` is visibly not a number, but it is an unflagged default path).

16. `run_on_production_host.sh`-adjacent (cited for completeness though outside A/B's five files):
    `family.py:1386` — `filtered.add_argument("--requirements", type=Path, default=Path(
    "requirements-native.txt"))` — silent default path, consistent with what callers always pass
    explicitly in the traced call site (`run_probe.sh:1836`).

I stopped at 16 rather than the 40 cap because further candidates I found (e.g. `normalize_curves.py`'s
`conventions` handling, `family.py`'s `substitutions()`) are **explicit non-defaults** — the code
comments at those sites say outright that a missing value is recorded as `None` on purpose, "rather
than carrying a default that would read as a measured fact" (`normalize_curves.py:184-186`) — which is
the opposite of what this section is asking for, so I did not pad the list with them.
