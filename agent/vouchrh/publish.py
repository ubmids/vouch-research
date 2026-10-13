"""Turn a round's feed into what the web page shows.

Adds, for every claim, the passage of the filing it is about (the quote itself
when it is genuine, otherwise the real sentence it was doctored from), and the
verifier's full answer; marks the trading agent's paper positions to market. The page never recomputes anything: it shows what the
check found, so what a judge reads is what the chain acted on.

    python -m vouchrh.publish feed/feed.json web/feed.json
"""
from __future__ import annotations

import json
import sys
from difflib import SequenceMatcher

from . import edgar
from .analysts import facts
from .verifier import figures, normalize, verify_quote

CHAINS = {
    31337: {"name": "Local devnet (anvil)", "explorer": None, "rpc": None},
    46630: {"name": "Robinhood Chain testnet", "explorer": "https://explorer.testnet.chain.robinhood.com",
            "rpc": "https://rpc.testnet.chain.robinhood.com"},
    421614: {"name": "Arbitrum Sepolia", "explorer": "https://sepolia.arbiscan.io", "rpc": "https://sepolia-rollup.arbitrum.io/rpc"},
}


def mark(feed: dict, quote=None) -> dict:
    """Mark the agent's open paper trades to the latest price, where both the
    entry price and a current one are known. Paper P&L only; nothing moved."""
    from . import prices
    quote = quote or prices.latest
    for j in feed.get("journal", []):
        p = (j.get("reasoning") or {}).get("price")
        if j.get("status") != "opened" or not p:
            continue
        now = quote(j["ticker"])
        if now:
            sign = 1 if j["side"] == "long" else -1
            j["mark"] = now
            j["pnl"] = round(j["notional"] / 1e6 * (float(now["price"]) / float(p["price"]) - 1) * sign, 2)
    return feed


def _passage(text: str, anchor: str, reach: int = 220) -> dict:
    """The matched sentence with at most one short sentence of context either
    side. Where the neighbour is a table (no sentence end within reach), none."""
    i = text.find(anchor)
    lo = text.rfind(". ", 0, max(0, i - 2))
    before = text[lo + 2: i] if lo >= 0 and i - lo <= reach else ""
    j = i + len(anchor)
    hi = text.find(". ", j + 1)
    after = text[j: hi + 1] if hi >= 0 and hi - j <= reach else ""
    return {"before": before, "match": anchor, "after": after}


def enrich(feed: dict) -> dict:
    texts, sentences = {}, {}
    for c in feed["claims"]:
        t = c["ticker"]
        if t not in texts:
            texts[t] = " ".join(edgar.latest(t).text().split())
            sentences[t] = [f.sentence for f in facts(texts[t])]
    fix = lambda h: h if not h or h.startswith("0x") else "0x" + h      # web3 7 drops the prefix
    for c in feed["claims"]:
        c["tx_post"], c["tx_judge"] = fix(c.get("tx_post")), fix(c.get("tx_judge"))
        if c.get("desk"):
            c["desk"]["tx"] = fix(c["desk"]["tx"])
        text = texts[c["ticker"]]
        check = verify_quote(c["quote"], text)
        genuine = normalize(c["quote"]) in normalize(text)
        if genuine and c["quote"] in text:
            source = c["quote"]
        else:
            source = max(sentences[c["ticker"]], key=lambda s: SequenceMatcher(None, s, c["quote"]).ratio())
        similarity = SequenceMatcher(None, normalize(source), normalize(c["quote"])).ratio()
        c["source"] = _passage(text, source) if similarity >= 0.6 and source in text else None
        c["similarity"] = round(similarity, 4)
        c["figures_quote"] = figures(c["quote"])
        c["figures_source"] = figures(source) if c["source"] else []
        c["check"] = {"verified": check.verified, "method": check.method, "score": check.score}
    feed["chain"] = CHAINS.get(feed["chain_id"], {"name": f"chain {feed['chain_id']}", "explorer": None, "rpc": None})
    mark(feed)
    feed["filings"] = {t: {"accession": f.accession, "form": f.form, "filed": f.filed, "period": f.period, "url": f.url}
                       for t in texts for f in [edgar.latest(t)]}
    return feed


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    out = enrich(json.load(open(src)))
    json.dump(out, open(dst, "w"), separators=(",", ":"))
    n = len(out["claims"])
    print(f"{dst}: {n} claims, {sum(1 for c in out['claims'] if c['source'])} with their filing passage")
