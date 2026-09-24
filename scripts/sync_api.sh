#!/bin/bash
# The hosted verify API runs the same verifier and EDGAR client as the market.
# Vercel deploys web/ only, so the two modules are copied in, verbatim, with a
# header; tests/test_api.py fails if a copy ever drifts from its source.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p web/api/_vouchcore
for m in verifier edgar; do
  { echo "# GENERATED from agent/vouchrh/$m.py by scripts/sync_api.sh. Do not edit."; cat "agent/vouchrh/$m.py"; } > "web/api/_vouchcore/$m.py"
done
touch web/api/_vouchcore/__init__.py
echo "synced verifier.py and edgar.py into web/api/_vouchcore"
