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

Two sets of posts, never mixed and always labelled:

- FIXTURE (feed/kol/posts.json, the default): 20 posts written for this demo
  by fictional accounts. Each voice stakes its own story.
- REAL (feed/kol/real/posts.json, --posts real): public posts from Mastodon's
  hashtag timelines, fetched by posts_fetch.py and committed as a snapshot,
  each with its url. The posters staked nothing: the agent reads every post
  (by the rules, or by a model with VOUCH_READER=model, see reader.py), and
  for each post that states a figure the 10-Q can confirm, the agent itself
  stakes on the story. A handle is shortened ("ro…@mastodon.social") unless
  --full-handles; the post's url is kept in full.

Live posts from X are not read.

    python -m vouchrh.kol --rpc http://127.0.0.1:8545 --key <anvil key> --out feed/feed-kol.json
    VOUCH_READER=model VOUCH_READER_URL=http://127.0.0.1:11434/v1 VOUCH_READER_MODEL=qwen2.5:7b-instruct \\
      python -m vouchrh.kol --posts real --rpc http://127.0.0.1:8545 --key <anvil key> --out feed/feed-kol-real.json
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
REAL = ROOT / "feed" / "kol" / "real" / "posts.json"
AGENT = "Vouch agent"      # who stakes on a real post's story: the agent, never the poster
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


def load_real(path: Path = REAL) -> dict:
    snap = json.loads(Path(path).read_text())
    if not snap.get("label", "").startswith("REAL"):
        raise ValueError(f"{path} must say it holds real posts")
    from .posts_fetch import sha
    for p in snap["posts"]:
        if sha(p["text"]) != p["sha256"]:
            raise ValueError(f"{p['url']}: the stored text does not hash to its sha256")
    return snap


def short_handle(acct: str, full: bool = False) -> str:
    """'robert@mastodon.social' -> 'ro…@mastodon.social': enough to tell posts apart, not to name anyone."""
    if full:
        return acct
    name, _, instance = acct.partition("@")
    return f"{name[:2]}…@{instance}" if instance else f"{name[:2]}…"


_URL = re.compile(r"https?://\S+")
# A sentence ends at . ! or ? after a lower-case letter, a digit or a closing
# mark, so headline abbreviations ("REV. $12.56B, EST. $12.58B") stay whole.
_SENTENCE = re.compile(r"(?<=[a-z0-9%)\"”'][.!?])\s+")
_CLAUSE = re.compile(r",\s+|;\s+|\s+[—–-]{1,2}\s+|:\s+")
_QUARTER = {"first": "Q1", "second": "Q2", "third": "Q3", "fourth": "Q4"}
_SPAN = {"3": "three", "6": "six", "9": "nine", "12": "twelve"}
# Words that say nothing about which figure a sentence is about.
_PLAIN = {"that", "this", "with", "from", "have", "been", "were", "their", "they", "more", "than", "into", "over",
          "about", "after", "also", "just", "only", "year", "years", "quarter", "months", "three", "six", "ended",
          "company", "companies", "billion", "million", "tesla", "amazon", "netflix", "palantir", "compared", "same",
          "period", "june", "july", "august", "during"}


def figure_sentence(text: str, figure: str | None, value: str | None) -> str:
    """The clause of a post that carries the figure, without links: what the
    agent stakes on is that one statement, not every figure in the post."""
    lines = [ln for ln in _URL.sub("", text).split("\n") if ln.strip()]
    sentences = [x.strip() for ln in lines for x in _SENTENCE.split(ln) if x.strip()]
    clauses = [(c.strip(), x) for x in sentences for c in _CLAUSE.split(x) if c.strip()]

    def whole(i: int) -> str:
        # a clause that starts in lower case continues the one before it ("..., reaching $1.94B")
        c, x = clauses[i]
        return f"{clauses[i - 1][0]}, {c}" if c[0].islower() and i and clauses[i - 1][1] is x else c

    for i, (c, _) in enumerate(clauses):
        if figure and figure in c:
            return whole(i)
    for i, (c, _) in enumerate(clauses):
        m = _MONEY.search(c)
        if m and value and money(m.group(1), m.group(2)) == value:
            return whole(i)
    return sentences[0] if sentences else ""


def periods(s: str) -> str:
    """A post's period the way the check reads one: "2Q" and "second quarter" as
    "Q2", "3 months" as "three months"."""
    s = re.sub(r"\b([1-4])Q\b", r"Q\1", s)
    s = re.sub(r"(?i)\b(first|second|third|fourth)[- ]quarter\b", lambda m: _QUARTER[m.group(1).lower()], s)
    return re.sub(r"(?i)\b(3|6|9|12)[- ]months?\b", lambda m: f"{_SPAN[m.group(1)]} months", s)


def _topic(s: str) -> set:
    """The words that say what a sentence is about, with a plural's s dropped ("revenues" is "revenue")."""
    return {w[:-1] if w.endswith("s") and len(w) > 4 else w for w in _words(s)} - _PLAIN


def ground_real(statement: str, value: str, text: str) -> str:
    """The filing sentence a real post's figure must come from: a sentence that
    states the figure and is about the same thing (at least one word in common
    besides the company, the period and the scale). A sentence that only shares
    the number ("$3 billion" of ad revenue against a $3 billion credit line) is
    not the source; then the closest sentence about the same thing is cited,
    and the check says the figure is not there."""
    want = _topic(statement)
    with_value = [s for s in sentences(text) if value in s]
    best = max(with_value, key=lambda s: len(want & _topic(s)), default=None)
    if best is not None and want & _topic(best):
        return best
    pool = [f.sentence for f in facts(text) if f.sentence not in with_value]
    return max(pool, key=lambda s: len(want & _topic(s))) if pool else (best or "")


def confirmable(statement: str, value: str, text: str) -> bool:
    """Whether the 10-Q has a sentence that states this figure about the same
    thing. The check reads sentences, not tables, so a figure the filing gives
    only in a table (Amazon's and Netflix's headline totals, for example) can
    be neither confirmed nor refuted by it. The agent does not stake on those:
    a stake it would lose for the check's blind spot proves nothing about the post."""
    want = _topic(statement)
    return any(want & _topic(s) for s in sentences(text) if value in s)


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


def claim_of_real(post: dict, reading: dict, filing, text: str, found, full_handles: bool = False) -> Claim:
    """The agent's own claim about a real post: the clause of the post that
    carries the figure, with the figure and period written as the filing and
    the check write them (and the post's period added when the post names it
    elsewhere), grounded in the 10-Q sentence it must come from."""
    said = periods(story(figure_sentence(post["text"], reading.get("figure"), reading["value"])))
    if reading.get("period") and reading["period"] not in said and periods(reading["period"]) not in said:
        said = f"{said} ({periods(reading['period'])})"
    quote = ground_real(said, reading["value"], text)
    metric = next((f.metric for f in found if f.sentence == quote), " ".join(quote.split()[:8]))
    analyst = f"{AGENT} (post by {short_handle(post['account'], full_handles)})"
    return Claim(reading["ticker"], filing.accession, metric, reading["value"], quote, analyst, said)


def run_real(chain: Chain, snap: dict | None = None, stake: int = 25 * USD, bond: int = 500 * USD,
             settle: str = "local", log=print, trade: int = 100 * USD, fund_wei: int | None = None,
             reader_cfg: dict | None = None, full_handles: bool = False) -> dict:
    """Real posts: the agent reads every post, and stakes on each story that
    states a figure the 10-Q can confirm. One wallet, the agent's, posts them all."""
    from . import reader
    from .market import SETTLED_BY, _wallet
    snap = snap or load_real()
    cfg = reader_cfg or reader.config()
    read_all = []
    for p in snap["posts"]:
        r = reader.read(p["text"], cfg)
        read_all.append((p, r))
        log(f"  read {short_handle(p['account'], full_handles):28} {r['reader']['kind']:5} "
            f"{r['ticker'] or '-':5} {r.get('value') or '-':>16} {'checkable' if r['checkable'] else ''}")
    candidates = [(p, r) for p, r in read_all if r["checkable"]]
    filings = {t: edgar.latest(t) for t in sorted({r["ticker"] for _, r in candidates})}   # evidence before gas
    texts = {t: (f.raw(), f.text()) for t, f in filings.items()}
    def said_of(p, r):
        said = periods(story(figure_sentence(p["text"], r.get("figure"), r["value"])))
        return said
    unconfirmable = {id(r) for p, r in candidates if not confirmable(said_of(p, r), r["value"], texts[r["ticker"]][1])}
    staked = [(p, r) for p, r in candidates if id(r) not in unconfirmable]
    log(f"  {len(candidates)} posts state a checkable figure; {len(staked)} of them have a 10-Q sentence that states it "
        f"(the rest give a figure the filing reports only in a table, or not at all: read, not staked)")
    deployed = chain.deploy(min_stake=min(10 * USD, stake), challenge_bond=max(1, stake // 5))
    log(f"  market deployed at {deployed.market}, verdicts only from forwarder {deployed.forwarder}")
    start_block = chain.w3.eth.block_number
    acct = _wallet(chain, AGENT, 20)
    need = fund_wei if fund_wei is not None else (10**16 if chain.chain_id == 31337 else 3 * 10**14)
    if chain.w3.eth.get_balance(acct.address) < need:
        chain.fund(acct.address, need)
    chain.onboard(acct, max(bond, stake * len(staked)))
    feed = []
    for p, r in staked:
        f = filings[r["ticker"]]
        raw, text = texts[r["ticker"]]
        c = claim_of_real(p, r, f, text, facts(text), full_handles)
        cid, posted = chain.post(acct, c.ticker, c.accession, c.canonical(), stake)
        v = audit_claim(c.value, c.quote, text, c.summary, c.metric)
        post = {"handle": short_handle(p["account"], full_handles), "url": p["url"], "instance": p["instance"],
                "created_at": p["created_at"], "text": p["text"], "sha256": p["sha256"], "real": True, "fixture": False}
        if full_handles:
            post["account"] = p["account"]
        row = {"id": cid, **asdict(c), "hash": "0x" + c.digest().hex(), "filing_url": f.url, "analyst_kind": "kol_real",
               "filed": f.filed, "stake": stake / USD, "analyst_address": acct.address,
               "local_verdict": "slashed" if v.fraudulent else "cleared", "reason": v.reason,
               "match": v.quote_check.method, "score": v.quote_check.score, "tx_post": posted,
               "post": post, "reading": r}
        if settle == "local":
            row["tx_judge"] = chain.report(cid, c.digest(), v.fraudulent, keccak(edgar.canonical(raw)), v.reason)
        feed.append(row)
        log(f"  #{cid:<3} {c.ticker:5} {post['handle']:28} {c.value:>15}  {r['sentiment']:8} "
            f"{'SLASH ' if v.fraudulent else 'clear '} {v.reason}")
    model = next((r["reader"] for _, r in read_all if r["reader"]["kind"] == "model"), None)
    trail = []
    for p, r in read_all:                      # every post read, staked or not, and how it was read
        rd = {k: v for k, v in r["reader"].items() if k != "messages"}   # rebuilt from the text by replay
        trail.append({"url": p["url"], "handle": short_handle(p["account"], full_handles), "created_at": p["created_at"],
                      "text": p["text"], "sha256": p["sha256"], "reading": {**r, "reader": rd},
                      "reading_sha256": reader.fingerprint(r), "staked": r["checkable"] and id(r) not in unconfirmable,
                      **({"not_staked": "no sentence of the 10-Q states this figure about this (the check reads sentences, not tables)"}
                         if id(r) in unconfirmable else {})})
    return {"chain_id": chain.chain_id, "contracts": asdict(deployed), "generated": int(time.time()),
            "settled_by": SETTLED_BY[settle], "mode": "kol", "source": "real", "fixture": None,
            "real": snap["label"], "snapshot": {"source": snap.get("source"), "window": snap.get("window"),
                                                "posts": len(snap["posts"]), "requests": len(snap.get("requests", []))},
            "reader": {"kind": cfg["kind"], "model": model["model"] if model else None,
                       "endpoint": model["endpoint"] if model else None,
                       "system": reader.SYSTEM if model else None,
                       "system_sha256": reader.sha(reader.SYSTEM) if model else None,
                       "rules": "agent/vouchrh/kol.py read (word lists)"},
            "from_block": start_block, "posts_read": trail,
            "standings": [{"analyst": AGENT, "kind": "agent", "address": acct.address}],
            "claims": feed, "trade_size": trade, "fund_wei": fund_wei}


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
    ap.add_argument("--posts", choices=("fixture", "real"), default="fixture",
                    help="fixture: the 20 written posts (each voice stakes); real: the Mastodon snapshot in "
                         "feed/kol/real/posts.json (the agent stakes; read by VOUCH_READER, see reader.py)")
    ap.add_argument("--snapshot", default=str(REAL), help="with --posts real: the snapshot to read")
    ap.add_argument("--full-handles", action="store_true", help="with --posts real: show posters' full handles")
    ap.add_argument("--out", default=str(ROOT / "feed" / "feed-kol.json"))
    args = ap.parse_args(argv)
    chain = Chain(args.rpc, args.key)
    if args.posts == "real":
        result = run_real(chain, load_real(Path(args.snapshot)), settle=args.settle, full_handles=args.full_handles)
    else:
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
