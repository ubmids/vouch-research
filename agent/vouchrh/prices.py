"""Reference prices for paper trades.

A paper trade needs a price to be marked against. This reads the last trade
price of the listed stock from a public quote endpoint, and says where it came
from. It is the agent's own observation, recorded in the reasoning record the
trade hashes on-chain; nothing attests it. If the endpoint cannot be reached
the trade is still journalled, without a price, and no P&L is shown.

Set VOUCH_PRICES=off to never call out (tests, offline rounds).
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

SOURCE = "Yahoo Finance chart API, regularMarketPrice (unattested)"


def latest(ticker: str) -> dict | None:
    if os.environ.get("VOUCH_PRICES", "on") == "off":
        return None
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1d&interval=1d"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (vouch paper desk)"})
        with urllib.request.urlopen(req, timeout=15) as r:
            meta = json.loads(r.read())["chart"]["result"][0]["meta"]
        # A string, so the record hashes the same in any language (no float formatting).
        return {"ticker": ticker, "price": f"{meta['regularMarketPrice']:.2f}", "currency": meta.get("currency", "USD"),
                "at": int(meta.get("regularMarketTime") or time.time()), "source": SOURCE}
    except Exception:
        return None
