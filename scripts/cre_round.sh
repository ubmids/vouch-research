#!/bin/bash
# A round on Robinhood Chain testnet, settled by the Chainlink CRE workflow in
# the CRE CLI's simulator. Run it on any machine with the testnet wallet, after
# `cre login` (or with CRE_API_KEY set). Simulation needs no deploy access.
#
#   bash scripts/cre_round.sh --preflight    # every check, nothing spent: run this first
#   bash scripts/cre_round.sh                # the round: 2 claims per stock token, 5 analysts
#   PER_TICKER=1 bash scripts/cre_round.sh   # a quicker round
#   bash scripts/cre_round.sh --new-wallet   # make a testnet wallet if this machine has none
#
# In two halves, when the CRE login comes later (claims wait, unsettled, for the
# 7-day window; a verdict lands whenever it arrives while a claim is pending):
#   bash scripts/cre_round.sh --post                    # no CRE login needed: deploy and post on testnet
#   bash scripts/cre_round.sh --settle cre/runs/<run>   # after `cre login`: the workflow settles them
#
# The AI analyst (ANALYST_MODEL):
#   live    (default) Qwen 2.5 7B through Ollama writes its claims now. The
#           preflight first asks it the exact question behind the published
#           wrong-quarter claim and stops unless it writes that claim again.
#   replay  re-post the claims Qwen wrote in the published round of 24 Sep,
#           word for word (their hashes match the v1 market's), labelled replayed.
#   none    scripted analysts only.
#
# What it does:
# 0. preflight, before any gas: tools, wallet balance, CRE login, SEC reachable,
#    the analyst model, the contracts and the workflow's WASM build;
# 1. deploys a market whose only verdict source is Chainlink's mock forwarder on
#    Robinhood Chain testnet (the one `cre workflow simulate --broadcast` writes
#    through) and posts the round's claims;
# 2. runs `cre workflow simulate` once WITHOUT --broadcast on the first claim and
#    stops if it fails; then, for every Posted event, runs it with --broadcast:
#    EDGAR fetch, the check, and a verdict transaction through the forwarder.
#    A claim whose simulation fails or writes no verdict is listed, not hidden;
#    with no verdict written at all the round stops before step 3;
# 3. reads every verdict back from the chain, lets the trading agent trade on
#    what cleared, re-verifies its journal, and rebuilds the feed.
# Everything lands in cre/runs/<run>/: env.txt (versions, wasm hash, account),
# one log per simulation, the journal check. That folder is the CRE evidence.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)

RPC=${VOUCH_RPC:-https://rpc.testnet.chain.robinhood.com}
EXPLORER=https://explorer.testnet.chain.robinhood.com
# Chainlink CRE forwarders on Robinhood Chain testnet (docs.chain.link/cre, forwarder directory)
MOCK_FORWARDER=${VOUCH_FORWARDER:-0x0b93082D9b3C7C97fAcd250082899BAcf3af3885}   # simulation (--broadcast)
KEYFILE=${VOUCH_KEYFILE:-$HOME/.config/vouch-rh/testnet.key}
PY=${VOUCH_PY:-$ROOT/.venv/bin/python}
ANALYST_MODEL=${ANALYST_MODEL:-live}
PER_TICKER=${PER_TICKER:-2}
FEED=${VOUCH_FEED:-feed/feed.json}
POSTS=${FEED%.json}.posts.txt
# A 50-claim round measured at about 0.002 ETH on Robinhood Chain testnet (0.01 gwei;
# a verdict transaction is about 106k gas); ask for half as much again.
MIN_WEI=${MIN_WEI:-3000000000000000}
export PATH="$PATH:$HOME/.bun/bin:$HOME/.cre/bin:$HOME/.local/bin:$HOME/.foundry/bin"   # yours first

fail() { echo "✗ $*" >&2; exit 1; }
ok() { echo "✓ $*"; }

MODE=round
case "${1:-}" in
  "") ;;
  --preflight) MODE=preflight ;;
  --new-wallet) MODE=wallet ;;
  --post) MODE=post ;;
  --settle) MODE=settle; SETTLE_RUN=${2:-}; [ -d "$SETTLE_RUN" ] || fail "usage: bash scripts/cre_round.sh --settle cre/runs/<run>" ;;
  *) fail "usage: bash scripts/cre_round.sh [--preflight | --new-wallet | --post | --settle cre/runs/<run>]" ;;
esac
WINDOW=${WINDOW:-21600}
[ "$MODE" = post ] && WINDOW=${WINDOW_POST:-604800}

[ -x "$PY" ] || fail "no Python at $PY: python3 -m venv .venv && .venv/bin/pip install 'web3>=7,<8' pytest"

if [ "$MODE" = wallet ]; then
  if [ -s "$KEYFILE" ]; then echo "a wallet already exists at $KEYFILE"; else
    mkdir -p "$(dirname "$KEYFILE")"; (umask 077; "$PY" -c "from eth_account import Account; print(Account.create().key.hex())" > "$KEYFILE")
    echo "new testnet wallet written to $KEYFILE (mode 600; never commit it)"
  fi
  "$PY" -c "import sys; from eth_account import Account; print('address:', Account.from_key(open(sys.argv[1]).read().strip()).address)" "$KEYFILE"
  echo "fund it at https://faucet.testnet.chain.robinhood.com (about 0.003 ETH covers a round)"
  exit 0
fi

if [ "$MODE" = settle ]; then
  RUN=$(cd "$SETTLE_RUN" && pwd)
  [ -s "$RUN/round.env" ] || fail "$RUN has no round.env: was it made with --post?"
  # shellcheck disable=SC1091
  . "$RUN/round.env"
  command -v cre >/dev/null || fail "install the CRE CLI: curl -sSL https://app.chain.link/cre/install.sh | bash"
  WHO=$(cre whoami 2>&1) || fail "not logged in to CRE: run 'cre login' (docs/bli/OWNER_TODO.md)"
  ok "CRE account: $(echo "$WHO" | grep -iE "email|org|user" | head -2 | tr -s ' ' | tr '\n' ' ')"
  { echo "settled_utc: $(date -u +%FT%TZ)"; echo "cre_whoami: |"; echo "$WHO" | sed 's/^/  /'; } >> "$RUN/env.txt"
  echo "settling market $MARKET from $RUN"
else
# ---- 0. preflight: nothing below spends gas until step 1 --------------------------
command -v cre >/dev/null || fail "install the CRE CLI: curl -sSL https://app.chain.link/cre/install.sh | bash"
command -v bun >/dev/null || fail "install bun: curl -fsSL https://bun.sh/install | bash"
command -v forge >/dev/null && command -v cast >/dev/null || fail "install Foundry: curl -L https://foundry.paradigm.xyz | bash && foundryup"
ok "tools: $(cre version 2>&1 | tail -1), bun $(bun --version), $(forge --version | head -1)"

[ -s "$KEYFILE" ] || fail "no wallet at $KEYFILE (copy yours there, or: bash scripts/cre_round.sh --new-wallet)"
ADDR=$("$PY" -c "import sys; from eth_account import Account; print(Account.from_key(open(sys.argv[1]).read().strip()).address)" "$KEYFILE")
BAL=$(cast balance "$ADDR" --rpc-url "$RPC") || fail "cannot reach $RPC"
"$PY" -c "import sys; sys.exit(int(sys.argv[1]) < int(sys.argv[2]))" "$BAL" "$MIN_WEI" \
  || fail "wallet $ADDR has $BAL wei; a round needs about $MIN_WEI. Faucet: https://faucet.testnet.chain.robinhood.com"
ok "wallet $ADDR: $BAL wei"

if [ "$MODE" = post ]; then
  WHO="(not logged in: --post needs no CRE login; --settle does)"
  ok "CRE login: not needed to post"
else
  WHO=$(cre whoami 2>&1) || fail "not logged in to CRE: run 'cre login', or export CRE_API_KEY (app.chain.link, Account Settings)"
  ok "CRE account: $(echo "$WHO" | grep -iE "email|org|user" | head -2 | tr -s ' ' | tr '\n' ' ')"
fi

if [ -z "${VOUCH_SKIP_SEC_CHECK:-}" ]; then   # (the script's own tests skip it)
  UA=$(PYTHONPATH=agent "$PY" -c "from vouchrh.edgar import CONTACT; print(CONTACT)")
  SEC=$(curl -s -o /dev/null -w "%{http_code}" -A "$UA" https://data.sec.gov/submissions/CIK0001318605.json) || SEC=000
  [ "$SEC" = 200 ] || fail "SEC EDGAR answered $SEC for the TSLA index (with User-Agent \"$UA\")"
  ok "SEC EDGAR reachable"
fi

MODEL_FLAGS=()
case "$ANALYST_MODEL" in
  live)
    # mmfarm's own Ollama on :11434 runs on a GPU that is not ours: use a CPU
    # server of your own on another port (see docs/bli/CHECKLIST.md).
    case "$(hostname)" in mmfarm|mastermoldfarm) SHARED=1 ;; *) SHARED= ;; esac
    if [ -n "$SHARED" ] && [ "${OLLAMA_HOST:-http://127.0.0.1:11434}" = "http://127.0.0.1:11434" ]; then
      fail "on mmfarm, set OLLAMA_HOST to your own Ollama (not :11434), or use ANALYST_MODEL=replay"
    fi
    PYTHONPATH=agent "$PY" -m vouchrh.llm --dry-run \
      || fail "the model did not write the published wrong-quarter claim, so a live round would have no hero. Re-run with ANALYST_MODEL=replay (the 24 Sep words, labelled) or ANALYST_MODEL=none"
    ok "the AI analyst writes the hero claim again"
    MODEL_FLAGS=(--model) ;;
  replay)
    MODEL_FLAGS=(--replay-model web/feed.json)
    ok "the AI analyst's claims are the 24 Sep round's, re-posted word for word (labelled replayed)" ;;
  none) ok "no AI analyst in this round" ;;
  *) fail "ANALYST_MODEL must be live, replay or none" ;;
esac

forge build >/dev/null
(cd cre/vouch-verifier && bun install >/dev/null)
RUNS=${VOUCH_RUNS:-$ROOT/cre/runs}
SUFFIX=; [ "$MODE" = preflight ] && SUFFIX=-preflight; [ "$MODE" = post ] && SUFFIX=-posted
RUN=$RUNS/$(date -u +%Y%m%dT%H%M%SZ)$SUFFIX
mkdir -p "$RUN"
(cd cre && cre workflow build ./vouch-verifier -o "$RUN/vouch-verifier.wasm") > "$RUN/build.log" 2>&1 \
  || { cat "$RUN/build.log"; fail "cre workflow build failed"; }
WASM_HASH=$(awk '/Binary hash:/ {print $3}' "$RUN/build.log")
ok "workflow built: $WASM_HASH"

{
  echo "date_utc: $(date -u +%FT%TZ)"
  echo "git: $(git rev-parse HEAD)$(git diff --quiet || echo ' (uncommitted changes)')"
  echo "host: $(hostname) $(uname -sm)"
  echo "cre: $(cre version 2>&1 | tail -1)"
  echo "bun: $(bun --version)"
  echo "forge: $(forge --version | head -1)"
  echo "python: $("$PY" --version 2>&1)"
  echo "cre_sdk: $(cd cre/vouch-verifier && bun pm ls 2>/dev/null | grep -o '@chainlink/cre-sdk@[0-9.]*' | head -1)"
  echo "wasm_binary_hash: $WASM_HASH"
  echo "wasm_sha256: $(sha256sum "$RUN/vouch-verifier.wasm" | awk '{print $1}')"
  echo "rpc: $RPC"
  echo "forwarder: $MOCK_FORWARDER (Chainlink MockKeystoneForwarder: checks no signatures)"
  echo "wallet: $ADDR"
  echo "analyst_model: $ANALYST_MODEL${OLLAMA_HOST:+ at $OLLAMA_HOST}"
  [ "$ANALYST_MODEL" = live ] && echo "ollama_model: $(curl -s -m 3 "${OLLAMA_HOST:-http://127.0.0.1:11434}/api/tags" | "$PY" -c "import json,sys,os; m=os.environ.get('VOUCH_LLM_MODEL','qwen2.5:7b-instruct'); print(next((x['name']+' '+x['digest'] for x in json.load(sys.stdin)['models'] if x['name']==m), '?'))")"
  echo "cre_whoami: |"
  echo "$WHO" | sed 's/^/  /'
} > "$RUN/env.txt"

if [ "$MODE" = preflight ]; then
  ok "preflight passed; nothing was spent. Evidence of the build: $RUN"
  exit 0
fi

# ---- 1. deploy and post -------------------------------------------------------
# A fresh market each CRE round: keep the previous deployment record beside it.
CHAIN_ID=$(cast chain-id --rpc-url "$RPC")
REC=deployments/$CHAIN_ID.json
if [ -f "$REC" ]; then mv "$REC" "deployments/$CHAIN_ID-$(date -u +%Y%m%d%H%M%S).json"; fi
# --pool all: the published round's facts, so the AI analyst gets the same questions.
# A two-half round keeps its own feed in the run folder until it is settled.
if [ "$MODE" = post ]; then FEED=$RUN/feed.json; POSTS=${FEED%.json}.posts.txt; fi
PYTHONPATH=agent "$PY" -m vouchrh.market --rpc "$RPC" --key "$(cat "$KEYFILE")" --forwarder "$MOCK_FORWARDER" \
  --settle cre --window "$WINDOW" --per-ticker "$PER_TICKER" --pool all ${MODEL_FLAGS[@]+"${MODEL_FLAGS[@]}"} --out "$FEED" | tee "$RUN/post.log"
MARKET=$("$PY" -c "import json, sys; print(json.load(open(sys.argv[1]))['contracts']['market'])" "$FEED")
echo "market: $MARKET" >> "$RUN/env.txt"
echo "window_seconds: $WINDOW" >> "$RUN/env.txt"
echo "market $MARKET  ($EXPLORER/address/$MARKET)"
printf 'MARKET=%s\nFEED=%s\nPOSTS=%s\n' "$MARKET" "$FEED" "$POSTS" > "$RUN/round.env"
if [ "$MODE" = post ]; then
  echo "posted: $(wc -l < "$POSTS" | tr -d ' ') claims (claim id and transaction in $POSTS)"
  ok "posted; nothing is settled yet. After 'cre login', within the $((WINDOW / 86400))-day window:"
  echo "   bash scripts/cre_round.sh --settle ${RUN#$ROOT/}"
  exit 0
fi
fi   # end of: not --settle

# ---- 2. the workflow settles every claim ----------------------------------------
# The workflow's config for this round (the staging config, pointed at this
# market) stays with the run's evidence.
# The simulator reads cre/.config.run.json (git-ignored, removed on exit), which
# carries the SEC contact from agent/vouchrh/edgar.py; the run folder keeps the
# same config with that one field redacted.
PYTHONPATH=agent "$PY" - "$MARKET" "$RUN/config.json" "$ROOT/cre/.config.run.json" <<'EOF'
import json, sys
from vouchrh.edgar import CONTACT
c = json.load(open("cre/vouch-verifier/config.staging.json")); c["market"] = sys.argv[1]
open(sys.argv[3], "w").write(json.dumps({**c, "userAgent": CONTACT}, indent=2) + "\n")
open(sys.argv[2], "w").write(json.dumps({**c, "userAgent": "Vouch research prototype (SEC contact, from agent/vouchrh/edgar.py)"}, indent=2) + "\n")
EOF
umask 077
printf 'CRE_ETH_PRIVATE_KEY=%s\n' "$(sed 's/^0x//' "$KEYFILE")" > cre/.env
trap 'rm -f "$ROOT/cre/.env" "$ROOT/cre/.config.run.json"' EXIT
simulate() {   # claim tx, log file, extra flags... (--wasm is relative: the CLI caps it at 97 characters)
  local tx=$1 log=$2; shift 2
  (cd cre && cre workflow simulate ./vouch-verifier --target staging-settings --non-interactive -e "$ROOT/cre/.env" \
    --trigger-index 0 --evm-tx-hash "$tx" --evm-event-index 0 --wasm "../../${RUN#"$ROOT"/}/vouch-verifier.wasm" \
    --config "$ROOT/cre/.config.run.json" "$@") \
    < /dev/null > "$log" 2>&1
}

read -r ID0 TX0 < "$POSTS"
echo "== dry run, no broadcast: claim #$ID0"
simulate "$TX0" "$RUN/dry-run-claim-$ID0.log" || { tail -20 "$RUN/dry-run-claim-$ID0.log"; fail "the simulation failed before any verdict was sent (log: $RUN/dry-run-claim-$ID0.log)"; }
grep -qE "verdict: (SLASH|CLEAR)" "$RUN/dry-run-claim-$ID0.log" || { tail -20 "$RUN/dry-run-claim-$ID0.log"; fail "the simulation printed no verdict (log: $RUN/dry-run-claim-$ID0.log)"; }
ok "dry run: $(grep -oE "verdict: (SLASH|CLEAR)[^;]*" "$RUN/dry-run-claim-$ID0.log" | head -1)"

TOTAL=0; WRITTEN=0; FAILED=()
while read -r ID TX; do
  TOTAL=$((TOTAL + 1))
  LOG="$RUN/claim-$ID.log"
  echo "== claim #$ID  posted in $TX"
  if simulate "$TX" "$LOG" --broadcast && grep -q "verdict for claim #$ID written: 0x" "$LOG" \
     && ! grep -q "WARNING: BondedClaims refused" "$LOG"; then
    WRITTEN=$((WRITTEN + 1))
    grep -E "verdict" "$LOG" | sed 's/^/   /' | head -3
  else
    FAILED+=("$ID")
    echo "   ✗ no verdict written for claim #$ID (log: $LOG)"
    tail -5 "$LOG" | sed 's/^/     /'
  fi
done < "$POSTS"
echo "verdicts_written: $WRITTEN of $TOTAL" | tee -a "$RUN/env.txt"
[ ${#FAILED[@]} -eq 0 ] || echo "no_verdict: ${FAILED[*]+${FAILED[*]}}" | tee -a "$RUN/env.txt"
[ "$WRITTEN" -ge 1 ] || fail "the workflow wrote no verdict, so the round stops here (logs in $RUN)"
if [ ${#FAILED[@]} -gt 0 ]; then
  echo "Retry one: (cd cre && cre workflow simulate ./vouch-verifier --target staging-settings --non-interactive -e .env --trigger-index 0 --evm-tx-hash <tx> --evm-event-index 0 --config .config.run.json --broadcast)"
  echo "(cre/.env and cre/.config.run.json are removed when this script exits; recreate them as in step 2.) Continuing: those claims show as pending."
fi

# ---- 3. read the chain, trade, verify, publish -----------------------------------
PYTHONPATH=agent "$PY" -m vouchrh.market --rpc "$RPC" --key "$(cat "$KEYFILE")" --finish "$FEED" --out "$FEED" \
  | tee "$RUN/finish.log"
[ "$FEED" = feed/feed.json ] || cp "$FEED" feed/feed.json
PYTHONPATH=agent "$PY" -m vouchrh.publish feed/feed.json web/feed.json
PYTHONPATH=agent "$PY" -m vouchrh.journal verify "$FEED" --rpc "$RPC" | tee "$RUN/journal-verify.txt"
echo
echo "CRE evidence: $RUN (env.txt, one simulation log per claim, the dry run)"
echo "Feed rebuilt in web/feed.json. Publish when happy: (cd web && vercel deploy --prod)"
