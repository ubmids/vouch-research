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
import os
import random
import time
from dataclasses import asdict
from pathlib import Path

from eth_account import Account

from . import edgar
from .analysts import CAST, facts
from .chain import USD, Chain
from .verifier import audit_claim

TOKENS = ("TSLA", "AMZN", "PLTR", "NFLX", "AMD")    # the stock tokens on Robinhood Chain testnet
CHALLENGER = "0x000000000000000000000000000000000000c0DE"
KEYS = Path(os.path.expanduser("~/.config/vouch-rh/analysts.json"))


def _wallet(chain: Chain, name: str, index: int):
    """Anvil gets throwaway keys. A public chain keeps one wallet per analyst
    across rounds, kept beside the verifier key and never in the repo, so a
    track record accumulates where anyone can read it."""
    if chain.chain_id == 31337:
        return Account.from_key(bytes([index + 1]) * 32)
    keys = json.loads(KEYS.read_text()) if KEYS.exists() else {}
    if name not in keys:
        keys[name] = Account.create().key.hex()
        KEYS.parent.mkdir(parents=True, exist_ok=True)
        KEYS.write_text(json.dumps(keys, indent=1))
        KEYS.chmod(0o600)
    return Account.from_key(keys[name])


def run(chain: Chain, tickers=TOKENS, per_ticker: int = 2, stake: int = 25 * USD, bond: int = 500 * USD,
        seed: int = 7, fund_wei: int | None = None, log=print, with_model: bool = False) -> dict:
    rng = random.Random(seed)
    # On a public chain the market lives at one address, so its record builds
    # up round after round. The addresses are public and live in the repo.
    record = Path(__file__).resolve().parents[2] / "deployments" / f"{chain.chain_id}.json"
    if chain.chain_id != 31337 and record.exists():
        from .chain import Deployed
        deployed = chain.attach(Deployed(**json.loads(record.read_text())))
        log(f"  market at {deployed.market} (existing)")
    else:
        deployed = chain.deploy()
        if chain.chain_id != 31337:
            record.parent.mkdir(exist_ok=True)
            record.write_text(json.dumps(asdict(deployed), indent=1))
        log(f"  market deployed at {deployed.market}")
    cast = list(CAST)
    if with_model:
        from . import llm
        if llm.available():
            cast.insert(1, llm.Model)
        else:
            log(f"  (no local model at {llm.HOST}; running the scripted analysts only)")
    analysts = []
    for i, A in enumerate(cast):
        acct = _wallet(chain, A.name, i)
        # a round costs each analyst well under 0.0003 ETH at testnet gas prices
        need = fund_wei if fund_wei is not None else (10**16 if chain.chain_id == 31337 else 3 * 10**14)
        if chain.w3.eth.get_balance(acct.address) < need:
            chain.fund(acct.address, need)
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
                verdict = audit_claim(c.value, c.quote, text, c.summary, c.metric)
                if verdict.fraudulent:
                    judged = chain.slash(cid, CHALLENGER, verdict.reason)
                else:
                    judged = chain.clear(cid)
                feed.append({
                    "id": cid, **asdict(c), "hash": "0x" + c.digest().hex(), "filing_url": filing.url,
                    "analyst_kind": agent.kind,
                    "filed": filing.filed, "stake": stake / USD, "analyst_address": acct.address,
                    "verdict": "slashed" if verdict.fraudulent else "cleared", "reason": verdict.reason,
                    "match": verdict.quote_check.method, "score": verdict.quote_check.score,
                    "tx_post": posted, "tx_judge": judged,
                })
                log(f"  #{cid:<3} {t:5} {agent.name:12} {c.value:>16}  {'SLASH ' if verdict.fraudulent else 'clear '} {verdict.reason}")

    standings = [{"analyst": a.name, "kind": a.kind, "address": acct.address, "bonded": chain.bonded(acct.address) / USD,
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
    ap.add_argument("--model", action="store_true", help="add the local language-model analyst (Ollama)")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "feed" / "feed.json"))
    args = ap.parse_args(argv)
    result = run(Chain(args.rpc, args.key), per_ticker=args.per_ticker, with_model=args.model)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1))
    print(f"-> {args.out}  ({len(result['claims'])} claims, reader pool {result['reader_pool']} tUSDG)")


if __name__ == "__main__":
    main()
