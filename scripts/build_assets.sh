#!/bin/bash
# Renders every submission image from design/assets/card.html and the live page
# (web/), in the Exhibit design (design/DESIGN.md), with the name from
# design/assets/brand.json. Output: docs/assets/ and docs/cover.png.
#
#   bash scripts/build_assets.sh            # gallery from feed.json if it has a journal, else feed-local.json
#   FEED=feed-kol-real.json bash scripts/build_assets.sh
#   VIDEO_ONLY=1 bash scripts/build_assets.sh     # cover, thumbnail and video cards only
#
# Needs Google Chrome and Python 3. Uses the network only for Google Fonts.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
CHROME=${CHROME:-"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"}
[ -x "$CHROME" ] || CHROME=$(command -v google-chrome || command -v chromium || true)
[ -n "$CHROME" ] || { echo "Chrome not found: set CHROME" >&2; exit 1; }
OUT=docs/assets
mkdir -p "$OUT/video" "$OUT/gallery"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"; [ -n "${SRV:-}" ] && kill "$SRV" 2>/dev/null; [ -n "${CSRV:-}" ] && kill "$CSRV" 2>/dev/null || true' EXIT

# brand.json -> query string (the one place the name lives for images)
BRANDQ=$(python3 -c 'import json,urllib.parse;b=json.load(open("design/assets/brand.json"));print(urllib.parse.urlencode({k:b[k] for k in ("name","site","repo")}))')
FEED=${FEED:-$(python3 -c 'import json;f=json.load(open("web/feed.json"));print("feed.json" if f.get("journal") else "feed-local.json")')}
CHAIN=$(python3 -c "import json;print(json.load(open('web/$FEED'))['chain']['name'])")

# shot <out.png> <WxH> <url> [transparent]
shot() {
  local out=$1 size=$2 url=$3 bg=()
  [ "${4:-}" = transparent ] && bg=(--default-background-color=00000000)
  local prof="$TMP/prof-$RANDOM"
  rm -f "$out"
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files --force-device-scale-factor=1 \
    --blink-settings=preferredColorScheme=1 ${bg[@]+"${bg[@]}"} --user-data-dir="$prof" --window-size="$size" \
    --virtual-time-budget=6000 --screenshot="$out" "$url" >/dev/null 2>&1 &
  local pid=$! i
  for i in $(seq 1 60); do [ -s "$out" ] && break; sleep 0.5; done
  sleep 1; kill "$pid" 2>/dev/null || true; pkill -f "user-data-dir=$prof" 2>/dev/null || true
  [ -s "$out" ] || { echo "failed: $out" >&2; exit 1; }
  echo "  $out"
}
# The template is served over HTTP (Google Fonts do not load into a file:// page).
mkdir -p "$TMP/www"; cp design/assets/card.html "$TMP/www/"
CPORT=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')
python3 -m http.server "$CPORT" --bind 127.0.0.1 --directory "$TMP/www" >/dev/null 2>&1 &
CSRV=$!
sleep 1
card() { echo "http://127.0.0.1:$CPORT/card.html?$BRANDQ&$1"; }
enc() { python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$1"; }

echo "cover, thumbnail, end card"
shot "$OUT/cover.png" 1920,1080 "$(card mode=cover)"
cp "$OUT/cover.png" docs/cover.png
sips -s format png -z 720 1280 "$OUT/cover.png" --out "$OUT/thumbnail.png" >/dev/null 2>&1 || cp "$OUT/cover.png" "$OUT/thumbnail.png"
cp "$OUT/cover.png" "$OUT/video/title.png"
shot "$OUT/video/end.png" 1920,1080 "$(card mode=end)"

echo "video overlays (transparent)"
shot "$OUT/video/lower-founder.png" 1920,1080 "$(card "mode=lower&who=$(enc 'Subomi Olagoke')&role=$(enc 'Builder of {name}')")" transparent
i=0
for t in "The record of reliance" "Exhibit 6" "Why a lawyer should care" "The check is a Chainlink CRE workflow" "The reasoning trail" "What it proves, and what it doesn't"; do
  i=$((i + 1))
  shot "$OUT/video/section-$i.png" 1920,1080 "$(card "mode=section&n=$(enc "Part $i")&title=$(enc "$t")")" transparent
done
shot "$OUT/video/caption-simulation.png" 1920,1080 "$(card "mode=caption&title=Simulation&sub=$(enc 'Chainlink CRE CLI simulation on Robinhood Chain testnet')")" transparent
shot "$OUT/video/caption-replayed.png" 1920,1080 "$(card "mode=caption&title=Replayed&sub=$(enc "Qwen 2.5's own words from 24 Sep, posted again word for word")")" transparent
shot "$OUT/video/caption-sdk.png" 1920,1080 "$(card "mode=caption&title=$(enc 'SDK test runtime')&sub=$(enc 'Not a CRE simulation: the workflow code in the SDK test runtime, local devnet')")" transparent

if [ -n "${VIDEO_ONLY:-}" ]; then echo "done (VIDEO_ONLY: gallery skipped)"; exit 0; fi
echo "gallery, from web/$FEED ($CHAIN)"
PORT=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')
python3 -m http.server "$PORT" --bind 127.0.0.1 --directory web >/dev/null 2>&1 &
SRV=$!
sleep 1
W="http://127.0.0.1:$PORT"
F="feed=$FEED"
LEAD=$(python3 -c "import json;cs=json.load(open('web/$FEED'))['claims'];print(next((c['id'] for c in cs if c.get('analyst_kind')=='model' and c['verdict']=='slashed'),cs[0]['id']))")
TICK=$(python3 -c "import json;cs=json.load(open('web/$FEED'))['claims'];print(next(c['ticker'] for c in cs if c['id']==$LEAD))")
shot "$TMP/www/g1.png" 1440,1500 "$W/?$F&claim=$LEAD&view=claim"
shot "$TMP/www/g2.png" 1440,733 "$W/?$F&claim=$LEAD"
shot "$TMP/www/g3.png" 1440,1400 "$W/?$F&view=journal"
shot "$TMP/www/g4.png" 1240,1300 "$W/?$F&record=$TICK"
shot "$TMP/www/g5.png" 1440,733 "$W/?$F&tour=3"
SUB=$(enc "$CHAIN round")
n=0
for spec in "g1|The claim record|exhibit $LEAD, its source, the verdict" "g2|Every exhibit|each claim checked against the SEC filing" "g3|The agent's case file|refused, relied on, re-verifiable" "g4|Record of reliance|one page counsel can keep" "g5|How it works|one claim, start to finish"; do
  IFS='|' read -r g title sub <<<"$spec"
  n=$((n + 1))
  shot "$OUT/gallery/$n.png" 1920,1080 "$(card "mode=gallery&img=$g.png&title=$(enc "$title")&sub=$(enc "$sub · ")$SUB")"
  sips -s format jpeg -s formatOptions 88 "$OUT/gallery/$n.png" --out "$OUT/gallery/$n.jpg" >/dev/null 2>&1 && rm "$OUT/gallery/$n.png"
done
echo "done"
