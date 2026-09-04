#!/usr/bin/env bash
# Places365 for the overlay augmentation used by SVEA, SGQN and SODA — VALIDATION split.
#
# WHY VAL AND NOT TRAIN. The augmentation pastes a random natural image behind the scene as a
# distractor. The images are nuisance, not labels, so there is no train/test leakage argument for
# preferring the train split — and `places365_standard/train` is ~24 GB against val's ~2 GB.
# The size difference is the whole reason this script exists; the repo owner declined the 24 GB.
#
# THIS IS A DECLARED PROTOCOL CHOICE, not a silent one: `overlay_dataset_split` goes into the
# protocol card, so a run that used val and a run that used train are not silently comparable.
#
#   bash setup/fetch_overlay_dataset.sh [DEST]
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-$REPO/data}"
URL="http://data.csail.mit.edu/places/places365/val_256.tar"

mkdir -p "$DEST"
if [[ -d "$DEST/places365_standard/val" ]]; then
  echo "already present: $DEST/places365_standard/val"
else
  echo ">>> ~2 GB from $URL"
  curl -L --fail -o "$DEST/val_256.tar" "$URL"
  mkdir -p "$DEST/places365_standard"
  tar -xf "$DEST/val_256.tar" -C "$DEST/places365_standard"
  # torchvision's ImageFolder requires root/<class>/<image>, and val_256 is a FLAT dump of
  # images. The overlay discards labels entirely (`imgs, _ = next(places_iter)`), so a single
  # nested folder is enough and is not a semantic choice. Without it ImageFolder raises
  # "Couldn't find any class folder", which is how this was found -- on a real run, after the
  # frame-0 evaluation had already been written.
  mkdir -p "$DEST/places365_standard/val/images"
  mv "$DEST/places365_standard/val_256"/*.jpg "$DEST/places365_standard/val/images/" 2>/dev/null || true
  rmdir "$DEST/places365_standard/val_256" 2>/dev/null || true
  rm -f "$DEST/val_256.tar"
fi

# RL-ViGen resolves the overlay path through its own cfgs/aug_config.cfg -> "datasets".
CFG="$REPO/RL-ViGen-upstream/cfgs/aug_config.cfg"
python3 - "$CFG" "$DEST" <<'PY'
import json, sys
cfg, dest = sys.argv[1], sys.argv[2]
d = json.load(open(cfg))
if dest not in d.get("datasets", []):
    d.setdefault("datasets", []).insert(0, dest)
    json.dump(d, open(cfg, "w"), indent=2)
    print(f"registered {dest} in {cfg}")
else:
    print(f"{dest} already registered")
PY

echo
echo "verify:  python setup/install_assets.py --check"
echo "then:    bash baselines/svea/train.sh Door 0 --smoke"
