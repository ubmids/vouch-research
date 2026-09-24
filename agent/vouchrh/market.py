"""One round of the market, end to end.

Each analyst reads the latest quarterly filing of each stock token, posts
bonded claims, and the verifier audits every one against the filing it cites,
clearing it or slashing it on-chain. The output is the feed: every claim, its
words, the hash the chain holds, the verdict, and the transactions behind it.

    python -m vouchrh.market --rpc http://127.0.0.1:8545 --key <verifier key>
"""
from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import asdict
from pathlib import Path

from eth_account import Account

from . import edgar
from .analysts import CAST, facts
from .chain import USD, Chain
from .verifier import audit_attestation

TOKENS = ("TSLA", "AMZN", "PLTR", "NFLX", "AMD")    # the stock tokens on Robinhood Chain testnet
CHALLENGER = "0x000000000000000000000000000000000000c0DE"


def run(chain: Chain, tickers=TOKENS, per_ticker: int = 2, stake: int = 25 * USD, bond: int = 500 * USD,
        seed: int = 7, fund_wei: int = 10**16, log=print) -> dict:
    rng = random.Random(seed)
    deployed = chain.deploy()
    analysts = []
    for i, A in enumerate(CAST):
        acct = Account.from_key(bytes([i + 1]) * 32 if chain.chain_id == 31337 else Account.create().key)
        chain.fund(acct.address, fund_wei)
        chain.onboard(acct, bond)
        analysts.append((A(seed=seed), acct))
        log(f"  {A.name:12} {acct.address}  bonded {bond // USD} tUSDG")

    feed = []
    for t in tickers:
        filing = edgar.latest(t)
        text = filing.text()
        found = facts(text)
        picks = rng.sample(found, min(per_ticker, len(found)))
        for fact in picks:
            for agent, acct in analysts:
                c = agent.claim(t, filing.accession, fact, found)
                cid, posted = chain.post(acct, c.ticker, c.accession, c.digest(), stake)
                verdict = audit_attestation(c.value, c.quote, text)
                if verdict.fraudulent:
                    judged = chain.slash(cid, CHALLENGER, verdict.reason)
                else:
                    judged = chain.clear(cid)
                feed.append({
                    "id": cid, **asdict(c), "hash": "0x" + c.digest().hex(), "filing_url": filing.url,
                    "filed": filing.filed, "stake": stake / USD, "analyst_address": acct.address,
                    "verdict": "slashed" if verdict.fraudulent else "cleared", "reason": verdict.reason,
                    "match": verdict.quote_check.method, "score": verdict.quote_check.score,
                    "tx_post": posted, "tx_judge": judged,
                })
                log(f"  #{cid:<3} {t:5} {agent.name:12} {c.value:>16}  {'SLASH ' if verdict.fraudulent else 'clear '} {verdict.reason}")

    standings = [{"analyst": a.name, "address": acct.address, "bonded": chain.bonded(acct.address) / USD,
                  "cleared": sum(1 for f in feed if f["analyst"] == a.name and f["verdict"] == "cleared"),
                  "slashed": sum(1 for f in feed if f["analyst"] == a.name and f["verdict"] == "slashed")}
                 for a, acct in analysts]
    return {"chain_id": chain.chain_id, "contracts": asdict(deployed), "generated": int(time.time()),
            "reader_pool": chain.reader_pool() / USD, "standings": standings, "claims": feed}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m vouchrh.market")
    ap.add_argument("--rpc", default="http://127.0.0.1:8545")
    ap.add_argument("--key", required=True, help="the verifier's private key (it also deploys)")
    ap.add_argument("--per-ticker", type=int, default=2)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "feed" / "feed.json"))
    args = ap.parse_args(argv)
    result = run(Chain(args.rpc, args.key), per_ticker=args.per_ticker)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1))
    print(f"-> {args.out}  ({len(result['claims'])} claims, reader pool {result['reader_pool']} tUSDG)")


if __name__ == "__main__":
    main()
