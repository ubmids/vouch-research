"""POST /api/verify: check one research claim against the company's SEC filing.

Any agent, on-chain or off, can ask before it acts. The answer comes from the
same deterministic check Vouch settles stakes with, so it is the answer the
market would give.

    curl -s https://vouch-feed.vercel.app/api/verify -H 'content-type: application/json' -d '{
      "ticker": "TSLA", "value": "$1.37 billion",
      "quote": "Depreciation expense during the three and six months ended June 30, 2026 was $1.37 billion and $2.71 billion, respectively.",
      "summary": "Tesla depreciation was $1.37 billion in Q2 2026."}'
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

os.environ.setdefault("VOUCH_CACHE", "/tmp/edgar")          # the only writable place on Vercel
sys.path.insert(0, os.path.dirname(__file__))
from _vouchcore import edgar                                  # noqa: E402
from _vouchcore.verifier import audit_claim                   # noqa: E402

USAGE = {
    "POST": "/api/verify",
    "body": {"ticker": "TSLA", "value": "$1.37 billion", "quote": "a whole sentence from the filing",
             "summary": "optional: the line readers see", "metric": "optional", "accession": "optional; default latest 10-Q"},
    "returns": {"verdict": "cleared | slashed", "reason": "why", "filing": "the document it was checked against"},
}


def verify(body: dict) -> tuple[int, dict]:
    missing = [k for k in ("ticker", "value", "quote") if not str(body.get(k, "")).strip()]
    if missing:
        return 400, {"error": f"missing {', '.join(missing)}", "usage": USAGE}
    ticker = str(body["ticker"]).upper().strip()
    try:
        pool = edgar.filings(ticker, ("10-Q", "10-K"), 8)
    except KeyError as e:
        return 404, {"error": str(e)}
    want = str(body.get("accession", "")).strip()
    filing = next((f for f in pool if f.accession == want), None) if want else next((f for f in pool if f.form == "10-Q"), pool[0] if pool else None)
    if filing is None:
        return 404, {"error": f"no filing {want or '10-Q'} for {ticker}"}
    v = audit_claim(str(body["value"]), str(body["quote"]), filing.text(),
                    str(body.get("summary", "")), str(body.get("metric", "")))
    return 200, {
        "verdict": "slashed" if v.fraudulent else "cleared", "reason": v.reason,
        "match": v.quote_check.method, "similarity": v.quote_check.score,
        "filing": {"ticker": ticker, "form": filing.form, "accession": filing.accession,
                   "filed": filing.filed, "period": filing.period, "url": filing.url},
        "checker": "vouch deterministic check · no model in the loop",
    }


class handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict):
        body = json.dumps(payload, indent=1).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        self._send(200, {"service": "Vouch verify", "usage": USAGE})

    def do_POST(self):
        try:
            n = min(int(self.headers.get("content-length", 0)), 20_000)
            body = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return self._send(400, {"error": "send a JSON object", "usage": USAGE})
        try:
            code, payload = verify(body)
        except Exception as e:  # EDGAR down, a malformed filing: say so, do not guess
            code, payload = 502, {"error": f"could not check the claim: {type(e).__name__}"}
        self._send(code, payload)
