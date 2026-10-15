#!/bin/bash
# The fallback round, for when `cre workflow simulate` cannot run (no CRE
# login): a local devnet (anvil) round whose every verdict is a report built by
# the CRE workflow's own handler in Chainlink's CRE SDK test runtime, delivered
# through a local forwarder. It is NOT a CRE CLI simulation and NOT a DON, and
# it says so in the feed (settled_by) and on the page.
#
#   bash scripts/sdk_round.sh            # writes web/feed-local.json
#   bash scripts/sdk_round.sh --kol      # KOL mode: 20 fixture posts as staked stories -> web/feed-kol.json
#   bash scripts/sdk_round.sh --kol-real # KOL mode on the real Mastodon snapshot (feed/kol/real/posts.json):
#                                        # the agent stakes on each checkable story -> web/feed-kol-real.json
#                                        # reads by VOUCH_READER (rules by default; model: see agent/vouchrh/reader.py)
#
# The AI analyst's claims are the ones Qwen 2.5 7B wrote in the published
# testnet round of 24 Sep, re-posted word for word and labelled as replayed
# (their words hash to the claim hashes the v1 market stored then). Everything
# else is fresh: the same five 10-Qs, the same facts (--pool all), the scripted
# analysts, the checks, the trading agent and its journal.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=${VOUCH_PY:-$ROOT/.venv/bin/python}
export PATH="$PATH:$HOME/.bun/bin:$HOME/.foundry/bin"
KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80   # anvil's well-known test key
MODE=analysts
if [ "${1:-}" = --kol ]; then MODE=kol; shift; fi
if [ "${1:-}" = --kol-real ]; then MODE=kol-real; shift; fi
case $MODE in
  kol) DEFAULT_OUT=web/feed-kol.json ;;
  kol-real) DEFAULT_OUT=web/feed-kol-real.json ;;
  *) DEFAULT_OUT=web/feed-local.json ;;
esac
OUT=${1:-$DEFAULT_OUT}
WORK=$(mktemp -d)
PORT=$("$PY" -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1])")
RPC=http://127.0.0.1:$PORT

anvil --silent --port "$PORT" &
ANVIL=$!
trap 'kill $ANVIL 2>/dev/null; rm -rf "$WORK"' EXIT
for _ in $(seq 50); do cast chain-id --rpc-url "$RPC" >/dev/null 2>&1 && break; sleep 0.1; done
forge build >/dev/null
(cd cre/vouch-verifier && bun install >/dev/null)

echo "== 1. post the round (no verdicts yet)"
if [ "$MODE" = kol ]; then
  PYTHONPATH=agent "$PY" -m vouchrh.kol --rpc "$RPC" --key "$KEY" --settle sdk --out "$WORK/feed.json"
elif [ "$MODE" = kol-real ]; then
  PYTHONPATH=agent "$PY" -m vouchrh.kol --posts real --rpc "$RPC" --key "$KEY" --settle sdk --out "$WORK/feed.json" \
    | grep -v "^  read " || true
  [ -s "$WORK/feed.json" ] || { echo "✗ the KOL round did not write a feed"; exit 1; }
else
  PYTHONPATH=agent "$PY" -m vouchrh.market --rpc "$RPC" --key "$KEY" --settle sdk --pool all \
    --replay-model web/feed.json --out "$WORK/feed.json"
fi
MARKET=$("$PY" -c "import json, sys; print(json.load(open(sys.argv[1]))['contracts']['market'])" "$WORK/feed.json")

echo "== 2. the workflow's handler, in the CRE SDK test runtime, builds a report per claim"
if ! (cd cre/vouch-verifier && VOUCH_RPC=$RPC VOUCH_MARKET=$MARKET VOUCH_POSTS=$WORK/feed.posts.txt \
  VOUCH_SDK_OUT=$WORK/reports.json bun test --timeout 600000 ./sdk-round.ts) > "$WORK/sdk.log" 2>&1; then
  tail -30 "$WORK/sdk.log"; echo "✗ the SDK runtime did not build every report"; exit 1
fi
grep -E "^#" "$WORK/sdk.log" | sed 's/^/   /'

echo "== 3. deliver the reports through the forwarder, trade, verify"
PYTHONPATH=agent "$PY" -m vouchrh.market --rpc "$RPC" --key "$KEY" --finish "$WORK/feed.json" \
  --deliver "$WORK/reports.json" --out "$WORK/feed.json"
PYTHONPATH=agent "$PY" -m vouchrh.journal verify "$WORK/feed.json" --rpc "$RPC" | tee "$WORK/journal-verify.txt" | tail -3
PYTHONPATH=agent "$PY" -m vouchrh.publish "$WORK/feed.json" "$OUT"
echo "-> $OUT"
