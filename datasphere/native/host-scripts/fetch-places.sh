set -uo pipefail
DEST=/work/places365
mkdir -p "$DEST"
echo "=== free before ==="; df -h /work | tail -1
apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq curl >/dev/null 2>&1
echo "=== downloading places365standard_easyformat.tar (~24 GB) ==="
curl -L --fail --retry 3 -o "$DEST/places365standard_easyformat.tar" \
  http://data.csail.mit.edu/places/places365/places365standard_easyformat.tar
echo "  curl rc=$?  size=$(du -h "$DEST/places365standard_easyformat.tar" 2>/dev/null | cut -f1)"
echo "=== sha256 ==="; sha256sum "$DEST/places365standard_easyformat.tar" | cut -c1-64
echo "=== extracting ==="
tar -xf "$DEST/places365standard_easyformat.tar" -C "$DEST"
echo "  tar rc=$?"
echo "=== result ==="; du -sh "$DEST"/* 2>/dev/null | head -5
find "$DEST" -maxdepth 2 -type d | head -5
echo "=== free after ==="; df -h /work | tail -1
echo "=== DONE ==="
