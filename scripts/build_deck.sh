#!/bin/bash
# Exports docs/deck/bli.html to docs/bli/deck.pdf (1920x1080 pages) in headless
# Chrome, with the name from design/assets/brand.json, the journal screenshot
# taken fresh from web/ (FEED, default feed-kol-real.json), and the test counts
# given as FORGE and PYBUN (e.g. FORGE=57 PYBUN=96 bash scripts/build_deck.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
CHROME=${CHROME:-"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"}
FEED=${FEED:-feed-kol-real.json}
: "${FORGE:?set FORGE to the Foundry test count}" "${PYBUN:?set PYBUN to the Python + Bun test count}"
NAME=$(python3 -c 'import json;print(json.load(open("design/assets/brand.json"))["name"])')
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"; kill ${SRV:-} ${WSRV:-} 2>/dev/null || true' EXIT
port() { python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])'; }
headless() {   # out flag url...
  local prof="$TMP/prof-$RANDOM" out=$1; shift
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --blink-settings=preferredColorScheme=1 \
    --user-data-dir="$prof" --virtual-time-budget=8000 "$@" >/dev/null 2>&1 &
  local pid=$! i
  for i in $(seq 1 90); do [ -s "$out" ] && break; sleep 0.5; done
  sleep 1; kill "$pid" 2>/dev/null || true; pkill -f "user-data-dir=$prof" 2>/dev/null || true
  [ -s "$out" ] || { echo "failed: $out" >&2; exit 1; }
}
WP=$(port); python3 -m http.server "$WP" --bind 127.0.0.1 --directory web >/dev/null 2>&1 & WSRV=$!
mkdir -p "$TMP/www"; sleep 1
headless "$TMP/j.png" --window-size=1440,1100 --screenshot="$TMP/j.png" "http://127.0.0.1:$WP/?feed=$FEED&view=journal"
# keep the first case file: drop the page header above it
python3 - "$TMP/j.png" "$TMP/www/journal.png" <<'PY' 2>/dev/null || cp "$TMP/j.png" "$TMP/www/journal.png"
import subprocess, sys
subprocess.run(["sips", "-c", "620", "1400", "--cropOffset", "405", "20", sys.argv[1], "--out", sys.argv[2]], check=True, capture_output=True)
PY
sed -e "s/__NAME__/$NAME/g" -e "s/__FORGE__/$FORGE/g" -e "s/__PYBUN__/$PYBUN/g" docs/deck/bli.html > "$TMP/www/bli.html"
P=$(port); python3 -m http.server "$P" --bind 127.0.0.1 --directory "$TMP/www" >/dev/null 2>&1 & SRV=$!
sleep 1
rm -f docs/bli/deck.pdf
headless docs/bli/deck.pdf --no-pdf-header-footer --print-to-pdf=docs/bli/deck.pdf "http://127.0.0.1:$P/bli.html"
cp "$TMP/www/journal.png" docs/deck/journal.png
echo "docs/bli/deck.pdf: $(python3 -c 'import re;d=open("docs/bli/deck.pdf","rb").read();print(len(re.findall(rb"/Type\s*/Page[^s]",d)))') pages"
