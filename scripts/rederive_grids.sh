#!/usr/bin/env bash
# Re-derive every retention grid deterministically, after C69.
#
#   bash scripts/rederive_grids.sh            # all discovered checkpoints, both regimes
#   bash scripts/rederive_grids.sh --dry-run  # print what would run
#
# WHY THIS EXISTS
#
# Every grid in `results/regime-retention/` was measured while `scripts/eval_across_scenes.py`
# left the global numpy RNG unseeded, so `UniformRandomSampler` placed the door -- and
# `robots/robot.py:131` perturbed the arm's starting joints -- from whatever process state
# happened to exist (C69). Those grids measure real episodes and are not discarded, but no two of
# them are a controlled comparison and none of them reproduces.
#
# `run_scene` now seeds per scene from the run's base seed, so every scene sees the SAME placement
# sequence. That is what turns the scene axis into an intervention rather than an observation:
# mode and geometry are held, only scene identity varies. Re-deriving is therefore not
# bookkeeping -- it is the first time these numbers answer the question the design intends.
#
# WHAT IT DELIBERATELY DOES NOT DO
#
# It does not overwrite `results/regime-retention/`. Those grids are evidence about what was
# measured and when, and C67's byte-identity finding lives in them. New grids land in
# `results/regime-retention-c69/`; promoting them is a separate, deliberate act.
#
# RESOURCE RULE, NOT A PREFERENCE
#
# Runs are SEQUENTIAL. `docs/local-envs.md` caps concurrent rendering runs at two on this machine,
# measured: three drove it to 10.1 GB of swap out of 11.3, and the cause is wired GPU memory
# rather than resident set, so it does not show up in the obvious place.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/results/regime-retention-c69"
PY="${PY:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}"
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1
mkdir -p "$OUT"

# Discovered, never hardcoded. A first version listed one cell by hand AND discovered the rest,
# which duplicated it; the dry run caught that, which is what the dry run is for.
#
# The label keys on the SNAPSHOT FILE, not its directory. The archived 2026-08-18 run holds
# `snapshot.pt`, `snapshot_50k_frames.pt` and `snapshot_100k_frames.pt` in ONE directory, so
# labelling by directory collapsed three checkpoints -- two of them different training steps --
# into a single name. The later ones would then have hit the skip-if-exists branch and vanished
# while the script reported success. The existing grid's own stem is reused, since that is the
# name every document already refers to.
cd "$ROOT" || exit 1

# `while read` rather than `mapfile`: macOS ships bash 3.2, where `mapfile` does not exist and
# fails with "command not found" -- then `set -u` turns the empty array into a second error and
# the script exits before running anything. Caught by the dry run.
CELLS=()
while IFS= read -r line; do
  [ -n "$line" ] || continue
  snap="${line%%|*}"; label="${line##*|}"
  if [ ! -f "$ROOT/$snap" ]; then
    echo "  !! missing checkpoint, skipped: $snap"
    continue
  fi
  CELLS+=("$snap|$label")
done < <("$PY" "$ROOT/scripts/_discover_grid_checkpoints.py")

# Cost, so nobody starts this without knowing. Measured 2026-08-25: one 20-episode x 10-scene grid
# took ~25 min on this M2 Pro under light load. 7 checkpoints x 2 regimes = 14 grids is therefore
# **roughly 6 hours** sequential (the echo below floors to 5h via integer division). Resumable --
# existing outputs are skipped -- so it can be run in pieces; `--dry-run` shows what is left.
echo "== re-deriving ${#CELLS[@]} checkpoints x 2 regimes, sequentially =="
echo "== ~25 min per grid measured; $(( ${#CELLS[@]} * 2 )) grids => roughly $(( ${#CELLS[@]} * 2 * 25 / 60 ))h. Resumable: existing files are skipped. =="
fail=0
for entry in "${CELLS[@]}"; do
  snap="${entry%%|*}"; label="${entry##*|}"
  for mode in train eval-easy; do
    dest="$OUT/${label}__${mode}.json"
    if [ -f "$dest" ]; then echo "  skip (exists): ${label}__${mode}"; continue; fi
    echo "  -> ${label} / ${mode}"
    [ "$DRY" = "1" ] && continue
    "$PY" "$ROOT/scripts/eval_across_scenes.py" \
      --snapshot "$ROOT/$snap" --mode "$mode" --episodes 20 --seed 0 \
      --json "$dest" > "$OUT/${label}__${mode}.log" 2>&1 \
      || { echo "     FAILED (see ${label}__${mode}.log)"; fail=$((fail+1)); }
  done
done

echo "== done; $fail failure(s) =="
# Non-zero on any failure. A re-derivation that silently skipped half its grids and exited 0 would
# read as "the archive is deterministic now", which is the exact failure class this script exists
# to clean up after.
exit $(( fail > 0 ))
