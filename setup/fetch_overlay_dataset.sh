#!/usr/bin/env bash
# Places365 for the overlay augmentation used by SVEA, SGQN and SODA.
#
#   bash setup/fetch_overlay_dataset.sh [DEST] [val|train]
#
# [Claude 2026-09-07, DECISION-SHEET A22 DECIDED] PRODUCTION USES `train`. The header below argued
# for val on size, and that argument no longer holds: the overlay distribution IS the mechanism for
# these three baselines, so drawing it from the validation partition is a learning-affecting
# deviation, and the cost is the easyformat package rather than the large-resolution archive.
#
# Note the number in the original text: "~24 GB against val's ~2 GB". That was right, and it sat
# in this file the whole time. A later revision of A22 priced the alternative at 105 GB -- the
# high-resolution archive, which this pipeline never needed since the loader crops to 84x84 -- and
# nearly kept the deviation on a cost that our own tooling already contradicted.
#
# WHAT THE ORIGINAL HEADER ARGUED, kept because the correction is the point. "The images are
# nuisance, not labels, so there is no train/test leakage argument for preferring the train split."
# True, and it answers a question nobody asked: the reason to use train is not leakage, it is that
# `use_val=False` is what the released loaders do, and these three methods' published behaviour is
# defined against that population (~1.8M images, not 36,500).
#
# THIS REMAINS A DECLARED PROTOCOL CHOICE: `overlay_dataset_split` goes into the protocol card, so
# a run that used val and a run that used train are not silently comparable.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-$REPO/data}"
SPLIT="${2:-train}"
case "$SPLIT" in
  val)   URL="http://data.csail.mit.edu/places/places365/val_256.tar"; SIZE="~2 GB";;
  train) URL="http://data.csail.mit.edu/places/places365/places365standard_easyformat.tar"; SIZE="~24 GB";;
  *) echo "unknown split: $SPLIT (expected val or train)" >&2; exit 2;;
esac

mkdir -p "$DEST"
if [[ -d "$DEST/places365_standard/$SPLIT" ]]; then
  echo "already present: $DEST/places365_standard/$SPLIT"
elif [[ "$SPLIT" == "train" ]]; then
  # The easyformat archive already contains places365_standard/{train,val} as ImageFolder trees,
  # so it needs no flat-dump repair -- unlike val_256, handled below.
  echo ">>> $SIZE from $URL"
  curl -L --fail -o "$DEST/places365standard_easyformat.tar" "$URL"
  tar -xf "$DEST/places365standard_easyformat.tar" -C "$DEST"
  rm -f "$DEST/places365standard_easyformat.tar"
  echo "extracted: $DEST/places365_standard/train"
else
  echo ">>> $SIZE from $URL"
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
