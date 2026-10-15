#!/bin/bash
# Publishes web/ to the existing Vercel project "vouch-feed" (vouch-feed.vercel.app).
#
#   bash scripts/deploy_web.sh          # checks only: says what would go live, deploys nothing
#   bash scripts/deploy_web.sh --go     # the same checks, then `vercel deploy --prod`
#
# Needs the Vercel CLI logged in to the account that owns vouch-feed (`vercel whoami`).
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PATH:$HOME/.bun/bin"
fail() { echo "✗ $*" >&2; exit 1; }
ok() { echo "✓ $*"; }
GO=; [ "${1:-}" = --go ] && GO=1

command -v vercel >/dev/null || fail "install the Vercel CLI: npm i -g vercel"
# The project link: the one the live site was deployed from (orgId + projectId, no secrets).
if [ ! -s web/.vercel/project.json ]; then
  mkdir -p web/.vercel
  printf '%s\n' '{"projectId":"prj_pRV0u0sjRGvx30pP5OELwa09WNxR","orgId":"team_AdSoQ03EA2Z8Z03TiIyiCaoR","projectName":"vouch-feed"}' > web/.vercel/project.json
fi
ok "linked to Vercel project $(python3 -c 'import json;print(json.load(open("web/.vercel/project.json"))["projectName"])') (web/.vercel is git-ignored)"

# What the page will show
python3 - <<'PY' || fail "web/feed.json is missing or unreadable"
import json
f = json.load(open("web/feed.json"))
v = [c["verdict"] for c in f["claims"]]
print(f"✓ web/feed.json: {f['chain']['name']} (chain {f['chain_id']}), market {f['contracts']['market']}, "
      f"{len(v)} claims, {v.count('cleared')} cleared, {v.count('slashed')} slashed, "
      f"journal: {'yes' if f.get('journal') else 'no'}, settled by: {f.get('settled_by') or 'the v1 verifier key'}")
PY
for f in feed-local.json feed-kol.json feed-kol-real.json feed-kol-real-rules.json; do
  [ -s "web/$f" ] && ok "also published: ?feed=$f" || echo "· not present: web/$f"
done
[ -s web/brand.js ] && ok "name: $(sed -n 's/.*name: "\([^"]*\)".*/\1/p' web/brand.js)"

# The browser's copy of the agent's rules must be the built one (the parity test checks this too)
TMPJS=$(mktemp); bash scripts/build_web.sh "$TMPJS" >/dev/null
cmp -s <(tail -n +2 "$TMPJS") <(tail -n +2 web/vouch-policy.js) || fail "web/vouch-policy.js is stale: run bash scripts/build_web.sh"
rm -f "$TMPJS"; ok "vouch-policy.js matches the policy source"
# The hosted check must be the same check as the agent's
for m in verifier edgar; do
  diff -q <(tail -n +2 "web/api/_vouchcore/$m.py") "agent/vouchrh/$m.py" >/dev/null || fail "web/api/_vouchcore/$m.py drifted: run bash scripts/sync_api.sh"
done
ok "web/api matches agent/vouchrh (verifier, edgar)"
[ ! -e web/_phone.html ] || fail "remove web/_phone.html (a local test page)"
# The SEC contact may live only in the hosted check's EDGAR client (web/api, sent to sec.gov); never in a page.
grep -rl "@gmail\.com\|djmceventconsortium\|PRIVATE KEY" web --include=*.js --include=*.html --include=*.json >/dev/null 2>&1 && fail "an email address or key is in a page or feed in web/" || ok "no email address or key in the pages or feeds"
grep -rl "djmceventconsortium" web >/dev/null 2>&1 && fail "a forbidden address is in web/" || true

if [ -z "$GO" ]; then
  echo
  echo "Checks passed. Nothing was deployed. To publish: bash scripts/deploy_web.sh --go"
  exit 0
fi
vercel whoami >/dev/null 2>&1 || fail "not logged in to Vercel: run 'vercel login'"
(cd web && vercel deploy --prod --yes)
echo "Live: https://vouch-feed.vercel.app  (check /?journal and /?record=TSLA logged out)"
