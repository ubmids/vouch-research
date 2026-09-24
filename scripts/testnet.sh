#!/bin/bash
# The real round, on a public Arbitrum chain. One command once the wallet has
# test ETH from the faucet:
#
#   bash scripts/testnet.sh                 # Robinhood Chain testnet (default)
#   CHAIN=arbitrum-sepolia bash scripts/testnet.sh
#
# Deploys the contracts, runs every analyst over the latest 10-Q of each stock
# token (the language-model analyst too, if Ollama is running), publishes the
# feed with explorer links, and redeploys the page. Stops at the first failure.
set -euo pipefail
cd "$(dirname "$0")/.."

case "${CHAIN:-robinhood}" in
  robinhood)        RPC=https://rpc.testnet.chain.robinhood.com; FAUCET=https://faucet.testnet.chain.robinhood.com ;;
  arbitrum-sepolia) RPC=https://sepolia-rollup.arbitrum.io/rpc;  FAUCET="https://www.alchemy.com/faucets/arbitrum-sepolia" ;;
  *) echo "CHAIN must be robinhood or arbitrum-sepolia"; exit 1 ;;
esac
KEYFILE="$HOME/.config/vouch-rh/testnet.key"
[ -s "$KEYFILE" ] || { echo "no wallet at $KEYFILE"; exit 1; }
ADDR=$(cat "$HOME/.config/vouch-rh/address")
BAL=$(~/.foundry/bin/cast balance "$ADDR" --rpc-url "$RPC")
echo "wallet $ADDR  balance $BAL wei on ${CHAIN:-robinhood}"
if [ "$BAL" = "0" ]; then
  echo "No test ETH yet. Paste the address above into $FAUCET, then run this again."
  exit 1
fi

~/.foundry/bin/forge build >/dev/null
MODEL=""
curl -s -m 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && MODEL="--model"
PYTHONPATH=agent .venv/bin/python -m vouchrh.market --rpc "$RPC" --key "$(cat "$KEYFILE")" \
  --per-ticker "${PER_TICKER:-2}" $MODEL --out feed/feed.json
PYTHONPATH=agent .venv/bin/python -m vouchrh.publish feed/feed.json web/feed.json
(cd web && vercel deploy --prod --yes >/dev/null) && echo "published: https://vouch-feed.vercel.app"
