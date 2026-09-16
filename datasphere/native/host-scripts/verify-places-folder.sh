set -uo pipefail
cd /repo
python3 datasphere/native/contract.py check-asset --asset /assets/places365/train \
  --expected-count 1000 \
  --expected-sha256 c08327c5baf66746d2caf2f6f126c297fa421280d90a7d17eb903e7939dfed2e
echo "  check-asset rc=$?"
