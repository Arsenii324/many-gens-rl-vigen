set -uo pipefail
DEST=/work/places365
mkdir -p "$DEST"
echo "=== extracting the fixture ONCE into the canonical folder ==="
tar xzf /work/places365-train-attest.tgz -C "$DEST"
echo "  rc=$?"
echo "=== shape ==="
find "$DEST" -maxdepth 2 -type d | head -6
echo "  train files: $(find "$DEST/train" -type f 2>/dev/null | wc -l)"
echo "  size: $(du -sh "$DEST" | cut -f1)"
