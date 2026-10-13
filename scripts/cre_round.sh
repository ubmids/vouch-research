#!/bin/bash
# A round on Robinhood Chain testnet, settled by the Chainlink CRE workflow.
# Run on the machine that holds the testnet wallet (~/.config/vouch-rh/), after
# `cre login` (a free Chainlink account; simulation needs no deploy access).
#
#   bash scripts/cre_round.sh                # 2 claims per stock token, 5 analysts
#   PER_TICKER=1 bash scripts/cre_round.sh   # a quicker round
#
# 1. deploys a market whose only accepted verdict source is Chainlink's CRE
#    forwarder on Robinhood Chain testnet (the mock one that `cre workflow
#    simulate --broadcast` writes through), and posts the round's claims;
# 2. for every Posted event, runs the vouch-verifier workflow in the CRE CLI's
#    simulator against that transaction: EDGAR fetch, the check, and a real
#    verdict transaction on Robinhood Chain through the forwarder;
# 3. reads every verdict back from the chain, lets the trading agent trade on
#    what cleared, re-verifies its journal, and republishes the feed.
# Logs of every simulation land in cre/runs/ (the CRE evidence for the submission).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)

RPC=https://rpc.testnet.chain.robinhood.com
EXPLORER=https://explorer.testnet.chain.robinhood.com
# Chainlink CRE forwarders on Robinhood Chain testnet (docs.chain.link/cre, forwarder directory)
MOCK_FORWARDER=0x0b93082D9b3C7C97fAcd250082899BAcf3af3885      # simulation (--broadcast)
KEYFILE="$HOME/.config/vouch-rh/testnet.key"
PY="$ROOT/.venv/bin/python"
export PATH="$HOME/.bun/bin:$HOME/.cre/bin:$HOME/.foundry/bin:$PATH"

[ -s "$KEYFILE" ] || { echo "no wallet at $KEYFILE"; exit 1; }
command -v cre >/dev/null || { echo "install the CRE CLI: curl -sSL https://app.chain.link/cre/install.sh | bash"; exit 1; }
command -v bun >/dev/null || { echo "install bun: curl -fsSL https://bun.sh/install | bash"; exit 1; }
cre whoami >/dev/null 2>&1 || { echo "log in first: cre login"; exit 1; }

forge build >/dev/null
(cd cre/vouch-verifier && bun install >/dev/null)
mkdir -p cre/runs
RUN=cre/runs/$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$RUN"

# ---- 1. deploy and post -------------------------------------------------------
# A fresh market each CRE round: keep the previous deployment record beside it.
[ -f deployments/46630.json ] && mv deployments/46630.json "deployments/46630-$(date -u +%Y%m%d%H%M%S).json"
MODEL=""
curl -s -m 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && MODEL="--model"
PYTHONPATH=agent "$PY" -m vouchrh.market --rpc "$RPC" --key "$(cat "$KEYFILE")" --forwarder "$MOCK_FORWARDER" \
  --settle cre --window 21600 --per-ticker "${PER_TICKER:-2}" $MODEL --out feed/feed.json | tee "$RUN/post.log"
MARKET=$("$PY" -c "import json;print(json.load(open('deployments/46630.json'))['market'])")
echo "market $MARKET  ($EXPLORER/address/$MARKET)"

# ---- 2. the workflow settles every claim ----------------------------------------
"$PY" - "$MARKET" <<'EOF'
import json, sys
p = "cre/vouch-verifier/config.staging.json"
c = json.load(open(p)); c["market"] = sys.argv[1]
json.dump(c, open(p, "w"), indent=2); open(p, "a").write("\n")
EOF
umask 077
printf 'CRE_ETH_PRIVATE_KEY=%s\n' "$(sed 's/^0x//' "$KEYFILE")" > cre/.env
trap 'rm -f "$ROOT/cre/.env"' EXIT
cd cre
cre workflow build ./vouch-verifier -o "$ROOT/$RUN/vouch-verifier.wasm" | tee "$ROOT/$RUN/build.log"
while read -r ID TX; do
  echo "== claim #$ID  posted in $TX"
  cre workflow simulate ./vouch-verifier --target staging-settings --non-interactive \
    --trigger-index 0 --evm-tx-hash "$TX" --evm-event-index 0 --broadcast \
    --wasm "$ROOT/$RUN/vouch-verifier.wasm" 2>&1 | tee "$ROOT/$RUN/claim-$ID.log" | grep -E "USER LOG|verdict|error|Error" || true
done < "$ROOT/feed/feed.posts.txt"
cd "$ROOT"

# ---- 3. read the chain, trade, verify, publish -----------------------------------
PYTHONPATH=agent "$PY" -m vouchrh.market --rpc "$RPC" --key "$(cat "$KEYFILE")" --finish feed/feed.json --out feed/feed.json \
  | tee "$RUN/finish.log"
PYTHONPATH=agent "$PY" -m vouchrh.publish feed/feed.json web/feed.json
PYTHONPATH=agent "$PY" -m vouchrh.journal verify feed/feed.json --rpc "$RPC" | tee "$RUN/journal-verify.txt"
echo
echo "CRE evidence: $RUN (one simulation log per claim, the wasm hash in build.log)"
echo "Feed rebuilt in web/feed.json. Publish when happy: (cd web && vercel deploy --prod)"
