"""KOL mode: the trading agent as a news checker.

Market voices post stories about the stock tokens on Robinhood Chain ("$TSLA
services revenue up $1.54B in Q2"). The agent reads each post the way RYO's
Multi-KOL direction describes, by transparent rules: which token, which
figure, which period, and the voice's sentiment, conviction and urgency. Then
it does what a news checker does and a KOL feed does not: it finds the
sentence of the issuer's 10-Q that the story's figure must come from, and
puts the story through Vouch's check as a staked claim (the same post, check
and desk path as every analyst). A story that misstates the figure, the
quarter or the direction is slashed, and the desk refuses any trade that
leans on it. Only voices whose story held move the agent's position.

The posts are a FIXTURE (feed/kol/posts.json): written for this demo, by
fictional accounts. Live posts from X are not read here.

    python -m vouchrh.kol --rpc http://127.0.0.1:8545 --key <anvil key> --out feed/feed-kol.json
"""
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict
from pathlib import Path

from eth_utils import keccak

from . import edgar
from .analysts import facts
from .chain import USD, Chain
from .claims import Claim
from .verifier import audit_claim, sentences

ROOT = Path(__file__).resolve().parents[2]
POSTS = ROOT / "feed" / "kol" / "posts.json"
NAMES = {"TESLA": "TSLA", "AMD": "AMD", "AMAZON": "AMZN", "PALANTIR": "PLTR", "NETFLIX": "NFLX"}

_CASHTAG = re.compile(r"\$([A-Z]{2,5})\b")
_MONEY = re.compile(r"\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)\s?(B|bn|billion|M|mn|million|K|thousand)\b")
_UNIT = {"b": "billion", "bn": "billion", "billion": "billion", "m": "million", "mn": "million", "million": "million",
         "k": "thousand", "thousand": "thousand"}
# The reading rules. Each is a word list anyone can read; nothing is learned.
_BULL = re.compile(r"(?i)\b(moon|all in|loading up|printing|monster|eating share|cash machine|real money|record|"
                   r"buy now|paying off|smashed|get in|diamond hands|biggest|sleeper|win)\b")
_BEAR = re.compile(r"(?i)\b(short it|crushed|dead weight|is over|dump|sell|overvalued)\b")
_HIGH_CONVICTION = re.compile(r"(?i)(all in|loading up|short it|!!|diamond hands|do not miss)")
_LOW_CONVICTION = re.compile(r"(?i)\b(hearing|if true|maybe|rumou?r)\b")
_URGENT = re.compile(r"(?i)\b(before the open|today|now|right now|do not miss)\b")


def load(path: Path = POSTS) -> dict:
    fx = json.loads(Path(path).read_text())
    if not fx.get("label", "").startswith("FIXTURE"):
        raise ValueError(f"{path} must say it is a fixture")
    return fx


def money(figure: str, unit: str) -> str:
    """'$1.54B' as the filing writes it: '$1.54 billion'."""
    return f"${figure} {_UNIT[unit.lower()]}"


def read(text: str) -> dict:
    """What the agent takes from a post, by the rules above."""
    tag = _CASHTAG.search(text)
    ticker = tag.group(1) if tag else next((t for n, t in NAMES.items() if re.search(rf"\b{n}\b", text, re.I)), None)
    m = _MONEY.search(text)
    bull, bear = len(_BULL.findall(text)), len(_BEAR.findall(text))
    return {
        "ticker": ticker,
        "value": money(m.group(1), m.group(2)) if m else None,
        "sentiment": "bullish" if bull > bear else "bearish" if bear > bull else "neutral",
        "conviction": "high" if _HIGH_CONVICTION.search(text) else "low" if _LOW_CONVICTION.search(text) else "medium",
        "urgency": "urgent" if _URGENT.search(text) else "normal",
        "rule": "ticker = cashtag or company name; figure = first $ amount; sentiment, conviction and urgency "
                "from fixed word lists (agent/vouchrh/kol.py)",
    }


def story(text: str) -> str:
    """The post as a checkable statement: its own words, with each figure
    written the way the filing writes it, so '$1.54B' is checked as $1.54 billion."""
    return _MONEY.sub(lambda m: money(m.group(1), m.group(2)), text)


def _words(s: str) -> set:
    return {w for w in re.findall(r"[a-z&]{4,}", s.lower())}


def ground(statement: str, value: str, text: str) -> str:
    """The filing sentence the story's figure must come from: the sentence that
    states it, closest in wording to the story. If no sentence states it, the
    closest sentence about the same thing, so the check says the figure is
    not there rather than guessing."""
    want = _words(statement)
    with_value = [s for s in sentences(text) if value in s]
    pool = with_value or [f.sentence for f in facts(text)]
    return max(pool, key=lambda s: len(want & _words(s))) if pool else ""


def claim_of(post: dict, filing, text: str, found) -> tuple[Claim, dict]:
    r = read(post["text"])
    said = story(post["text"])
    quote = ground(said, r["value"] or "", text)
    metric = next((f.metric for f in found if f.sentence == quote), " ".join(quote.split()[:8]))
    return Claim(r["ticker"], filing.accession, metric, r["value"] or "", quote, post["handle"], said), r


def run(chain: Chain, posts: list | None = None, stake: int = 25 * USD, bond: int = 500 * USD, settle: str = "local",
        log=print, trade: int = 100 * USD, fund_wei: int | None = None) -> dict:
    """Post every story as a staked claim, by its voice. settle="local": the
    Python check's verdict now, through the forwarder; settle="sdk": post only,
    for the workflow's handler in the CRE SDK test runtime (scripts/sdk_round.sh)."""
    from .market import SETTLED_BY, _wallet
    fx = load()
    posts = posts if posts is not None else fx["posts"]
    readings = [(p, read(p["text"])) for p in posts]
    tickers = sorted({r["ticker"] for _, r in readings if r["ticker"]})
    filings = {t: edgar.latest(t) for t in tickers}           # every filing first: no gas before the evidence
    texts = {t: (f.raw(), f.text()) for t, f in filings.items()}
    deployed = chain.deploy(min_stake=min(10 * USD, stake), challenge_bond=max(1, stake // 5))
    log(f"  market deployed at {deployed.market}, verdicts only from forwarder {deployed.forwarder}")
    voices, feed = {}, []
    start_block = chain.w3.eth.block_number
    for p, r in readings:
        if not r["ticker"] in filings:
            log(f"  {p['handle']}: no stock token named, skipped")
            continue
        if p["handle"] not in voices:
            acct = _wallet(chain, p["handle"], 20 + len(voices))
            need = fund_wei if fund_wei is not None else (10**16 if chain.chain_id == 31337 else 3 * 10**14)
            if chain.w3.eth.get_balance(acct.address) < need:
                chain.fund(acct.address, need)
            chain.onboard(acct, bond)
            voices[p["handle"]] = acct
        acct = voices[p["handle"]]
        f = filings[r["ticker"]]
        raw, text = texts[r["ticker"]]
        c, reading = claim_of(p, f, text, facts(text))
        cid, posted = chain.post(acct, c.ticker, c.accession, c.canonical(), stake)
        v = audit_claim(c.value, c.quote, text, c.summary, c.metric)
        row = {"id": cid, **asdict(c), "hash": "0x" + c.digest().hex(), "filing_url": f.url, "analyst_kind": "kol",
               "filed": f.filed, "stake": stake / USD, "analyst_address": acct.address,
               "local_verdict": "slashed" if v.fraudulent else "cleared", "reason": v.reason,
               "match": v.quote_check.method, "score": v.quote_check.score, "tx_post": posted,
               "post": {"handle": p["handle"], "text": p["text"], "fixture": True}, "reading": reading}
        if settle == "local":
            row["tx_judge"] = chain.report(cid, c.digest(), v.fraudulent, keccak(edgar.canonical(raw)), v.reason)
        feed.append(row)
        log(f"  #{cid:<3} {c.ticker:5} {p['handle']:17} {c.value:>15}  {reading['sentiment']:8} "
            f"{'SLASH ' if v.fraudulent else 'clear '} {v.reason}")
    standings = [{"analyst": h, "kind": "kol", "address": a.address} for h, a in voices.items()]
    return {"chain_id": chain.chain_id, "contracts": asdict(deployed), "generated": int(time.time()),
            "settled_by": SETTLED_BY[settle], "mode": "kol", "fixture": fx["label"], "from_block": start_block,
            "standings": standings, "claims": feed, "trade_size": trade, "fund_wei": fund_wei}


def main(argv=None):
    from .market import finish
    ap = argparse.ArgumentParser(prog="python -m vouchrh.kol")
    ap.add_argument("--rpc", default="http://127.0.0.1:8545")
    ap.add_argument("--key", required=True)
    ap.add_argument("--settle", choices=("local", "sdk"), default="local")
    ap.add_argument("--out", default=str(ROOT / "feed" / "feed-kol.json"))
    args = ap.parse_args(argv)
    chain = Chain(args.rpc, args.key)
    result = run(chain, settle=args.settle)
    if args.settle == "local":
        result = finish(chain, result)
    else:
        txs = Path(args.out).with_suffix(".posts.txt")
        txs.write_text("".join(f"{c['id']} {c['tx_post']}\n" for c in result["claims"]))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1))
    print(f"-> {args.out}  ({len(result['claims'])} stories)")


if __name__ == "__main__":
    main()
