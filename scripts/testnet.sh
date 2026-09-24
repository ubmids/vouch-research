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
  robinhood)        RPC=https://rpc.testnet.chain.robinhood.com; FAUCET=https://faucet.testnet.chain.robinhood.com
                    USDG=0x7E955252E15c84f5768B83c41a71F9eba181802F ;;
  arbitrum-sepolia) RPC=https://sepolia-rollup.arbitrum.io/rpc;  FAUCET="https://www.alchemy.com/faucets/arbitrum-sepolia"
                    USDG=0xFFC95faa3d63Cde504a05B567C600B78C0b41892 ;;
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

# Bond in real Paxos USDG when the wallet holds some (faucet.paxos.com), sized
# to what it holds; otherwise the market deploys its test stand-in.
TOKEN_ARGS=()
RAW=$(~/.foundry/bin/cast call "$USDG" "balanceOf(address)(uint256)" "$ADDR" --rpc-url "$RPC" | awk '{print $1}')
if [ "${RAW:-0}" -gt 0 ]; then
  USD=$(python3 -c "print($RAW/1e6)")
  # six wallets (five analysts and the trading agent) share it
  BOND=$(python3 -c "print(round($RAW/1e6*0.13, 2))"); STAKE=$(python3 -c "print(round($RAW/1e6*0.13/12, 2))")
  echo "USDG balance $USD: bonding in real USDG ($BOND per analyst, $STAKE per claim)"
  TOKEN_ARGS=(--token "$USDG" --bond "$BOND" --stake "$STAKE" --trade "$STAKE")
else
  echo "No USDG in the wallet (faucet.paxos.com): bonding in the test stand-in instead"
fi
MODEL=""
curl -s -m 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && MODEL="--model"
PYTHONPATH=agent .venv/bin/python -m vouchrh.market --rpc "$RPC" --key "$(cat "$KEYFILE")" \
  --per-ticker "${PER_TICKER:-2}" $MODEL "${TOKEN_ARGS[@]}" --out feed/feed.json
PYTHONPATH=agent .venv/bin/python -m vouchrh.publish feed/feed.json web/feed.json
(cd web && vercel deploy --prod --yes >/dev/null) && echo "published: https://vouch-feed.vercel.app"
