#!/usr/bin/env bash
# [Claude 2026-09-08] Fire the single re-attestation wave after the closure batch.
#
# Seven families, seven cells, submitted together. They are one wave and not seven because the
# batch moved `scripts/eval_provenance.py` (a CODE_MEMBER shared by all seven) and
# `datasphere/native/families.json` (a CONFIG_MEMBER, likewise), so every revision moved at once.
#
# Payloads are built HERE rather than in advance, deliberately: a payload built before the tree
# stopped moving is a payload that binds to a tree nobody will run, and `contract.py`'s
# verify-evaluator-binding would refuse it at submit -- correctly, and after the build time was
# already spent.
#
# gt4i.1 refuses the 8th concurrent job, so seven is the maximum that fits in one pass.
set -euo pipefail
cd "$(dirname "$0")/../.."
export GRPC_DNS_RESOLVER=native
BP="${BP:-/Users/a2mogus/build-projs/barannikov-work/.venv/bin/python}"

for fam in rlvigen dmc_gb idaac alda ppg ibac_sni ctrl; do
  payload="datasphere/native/payload-v205-${fam}.tgz"
  [[ -f "$payload" ]] || "$BP" datasphere/native/contract.py build-payload \
      --source . --output "$payload" --families "$fam" >/dev/null
  echo "=== $fam"
  bash datasphere/native/job.sh submit "datasphere/native/cfg-${fam}-attest-v205.yaml" | tail -1
done
echo
echo "When they land:"
echo "    bash datasphere/native/collect-wave.sh --from-submissions v205"
echo
echo "That diagnoses each job, installs its records, populates the evaluator ledger and reports"
echo "the gate -- and REFUSES rather than skips on a job that is not SUCCESS, emitted no records,"
echo "or whose records the ledger rejects as describing a superseded tree. It exits non-zero if"
echo "any family was not collected, so a short ledger cannot be reported as 7/7."
