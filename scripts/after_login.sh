#!/bin/bash
# The one command after Subomi's `cre login`: settle the posted testnet round
# with the Chainlink CRE workflow (CRE CLI simulation, test ETH only), then
# refresh everything that reports it. Deploys nothing and commits nothing.
#
#   bash scripts/after_login.sh                       # the latest cre/runs/*-posted round
#   bash scripts/after_login.sh cre/runs/<run>-posted
#
# Steps: cre_round.sh --settle (a dry run, then one simulation per claim, the
# trading agent, the journal check, web/feed.json) -> round_docs.py (README,
# BUIDL, deck text, docs/bli/TESTNET_ROUND.md) -> build_assets.sh -> build_deck.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
RUN=${1:-$(ls -d cre/runs/*-posted 2>/dev/null | tail -1)}
[ -n "$RUN" ] && [ -d "$RUN" ] || { echo "✗ no posted round in cre/runs" >&2; exit 1; }
export PATH="$PATH:$HOME/.cre/bin:$HOME/.bun/bin:$HOME/.foundry/bin"
cre whoami >/dev/null 2>&1 || { echo "✗ not logged in to CRE: run ~/.cre/bin/cre login first (docs/bli/OWNER_TODO.md)" >&2; exit 1; }
[ -s "$RUN/vouch-verifier.wasm" ] || { echo "✗ $RUN/vouch-verifier.wasm is missing (it is not committed): rebuild it with (cd cre && cre workflow build ./vouch-verifier -o $PWD/$RUN/vouch-verifier.wasm)" >&2; exit 1; }

echo "== 1. settle $RUN"
bash scripts/cre_round.sh --settle "$RUN"
echo "== 2. the docs"
python3 scripts/round_docs.py "$RUN"
echo "== 3. images (cover, gallery from the settled feed, video cards)"
nice -n 5 bash scripts/build_assets.sh
echo "== 4. the deck"
FORGE=${FORGE:-57} PYBUN=${PYBUN:-100} nice -n 5 bash scripts/build_deck.sh
echo
grep -E "verdicts_written|no_verdict" "$RUN/env.txt" || true
echo "Changed files:"; git status --short | sed 's/^/  /'
echo "Next: review, then commit; publish with bash scripts/deploy_web.sh --go when told."
