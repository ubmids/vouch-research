"""One round of the market, end to end.

Each analyst reads the latest quarterly filing of each stock token and posts
bonded claims. Each claim is checked against the filing it cites and the
verdict reaches the market the only way the market accepts one: as a report
through the forwarder. Then a trading agent reads every claim and opens paper
trades only on what cleared, journalling why. The output is the feed: every
claim, its words, the hash the chain holds, the verdict, the transactions
behind it, and the agent's journal.

    python -m vouchrh.market --rpc http://127.0.0.1:8545 --key <deployer key>
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
from eth_utils import keccak

from . import edgar
from .analysts import CAST, facts
from .chain import USD, Chain
from .policy import signal
from .verifier import audit_claim

TOKENS = ("TSLA", "AMZN", "PLTR", "NFLX", "AMD")    # the stock tokens on Robinhood Chain testnet
KEYS = Path(os.path.expanduser("~/.config/vouch-rh/analysts.json"))
# Who wrote the verdicts, said the same way on the page, in the feed and in the docs.
SETTLED_BY = {
    "local": "the Python check, through a local forwarder",
    "cre": "the Chainlink CRE workflow (CRE CLI simulation, one local node, through Chainlink's mock forwarder)",
    "sdk": "the CRE workflow in Chainlink's SDK test runtime, via a local forwarder",
}


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


def choose_facts(tickers=TOKENS, per_ticker: int = 2, seed: int = 7, pool: str = "tradable") -> list:
    """The facts a round's analysts write about: (ticker, filing, text, every
    fact, the picks) per stock. pool="tradable" prefers figures a trader moves
    on (revenue, income, costs that rose or fell). pool="all" samples every
    fact, as the published testnet round of 24 September did: with the same
    seed it picks the same ten facts, so the AI analyst sees the prompts it saw
    then (tests/test_preflight.py holds this to the published feed)."""
    rng = random.Random(seed)
    out = []
    for t in tickers:
        filing = edgar.latest(t)
        text = filing.text()
        found = facts(text)
        if pool == "all":
            candidates = found
        else:
            tradable = [f for f in found if signal({"value": f.value, "quote": f.sentence, "metric": f.metric})["signal"]]
            candidates = tradable if len(tradable) >= per_ticker else found
        out.append((t, filing, text, found, rng.sample(candidates, min(per_ticker, len(candidates)))))
    return out


def run(chain: Chain, tickers=TOKENS, per_ticker: int = 2, stake: int = 25 * USD, bond: int = 500 * USD,
        seed: int = 7, fund_wei: int | None = None, log=print, with_model: bool = False,
        token: str | None = None, trade: int = 100 * USD, forwarder: str | None = None, settle: str = "local",
        window: int = 3600, workflow_owner: str | None = None, workflow_name: str | None = None,
        pool: str = "tradable", cast: list | None = None, settled_by: str | None = None) -> dict:
    """Post a round of claims. With settle="local" the verdicts are delivered at
    once through the forwarder, computed by the Python check (anvil, or a
    public chain without the CRE CLI). With settle="cre" the claims are only
    posted; the Chainlink CRE workflow settles them (cre/), and finish() picks
    the round up from the chain afterwards. settle="sdk" also only posts: the
    workflow's own handler, in the CRE SDK's test runtime, then builds every
    verdict report (scripts/sdk_round.sh)."""
    # Read every filing before anything is spent: a round that cannot fetch
    # its evidence should fail here, not after the deploy.
    chosen = choose_facts(tickers, per_ticker, seed, pool)
    cast = list(cast or CAST)
    if with_model:
        # Asked for the model and it is not there: stop, rather than run a round
        # without the AI analyst and find out after the gas is spent.
        from . import llm
        if not llm.available():
            raise SystemExit(f"no {llm.MODEL} at {llm.HOST}: start Ollama with it, or run without --model")
        cast.insert(1, llm.Model)
    # On a public chain the market lives at one address, so its record builds
    # up round after round. The addresses are public and live in the repo.
    record = Path(__file__).resolve().parents[2] / "deployments" / f"{chain.chain_id}.json"
    if chain.chain_id != 31337 and record.exists() and json.loads(record.read_text()).get("forwarder"):
        from .chain import Deployed
        deployed = chain.attach(Deployed(**json.loads(record.read_text())))
        log(f"  market at {deployed.market} (existing)")
    else:
        from .chain import workflow_name_bytes
        deployed = chain.deploy(min_stake=min(10 * USD, stake), challenge_bond=max(1, stake // 5), token=token,
                                forwarder=forwarder, window=window, owner=workflow_owner,
                                name=workflow_name_bytes(workflow_name) if workflow_name else bytes(10))
        if chain.chain_id != 31337:
            record.parent.mkdir(exist_ok=True)
            record.write_text(json.dumps(asdict(deployed), indent=1))
        log(f"  market deployed at {deployed.market}, verdicts only from forwarder {deployed.forwarder}")
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

    start_block = chain.w3.eth.block_number
    feed = []
    for t, filing, text, found, picks in chosen:
        raw = filing.raw()
        for fact in picks:
            for agent, acct in analysts:
                c = agent.claim(t, filing.accession, fact, found)
                cid, posted = chain.post(acct, c.ticker, c.accession, c.canonical(), stake)
                verdict = audit_claim(c.value, c.quote, text, c.summary, c.metric)
                row = {
                    "id": cid, **asdict(c), "hash": "0x" + c.digest().hex(), "filing_url": filing.url,
                    "analyst_kind": agent.kind, "filed": filing.filed, "stake": stake / USD,
                    "analyst_address": acct.address, "local_verdict": "slashed" if verdict.fraudulent else "cleared",
                    "reason": verdict.reason, "match": verdict.quote_check.method, "score": verdict.quote_check.score,
                    "tx_post": posted,
                }
                if getattr(agent, "provenance", None):
                    row["replayed_from"] = agent.provenance(c)
                if settle == "local":
                    row["tx_judge"] = chain.report(cid, c.digest(), verdict.fraudulent, keccak(edgar.canonical(raw)), verdict.reason)
                feed.append(row)
                log(f"  #{cid:<3} {t:5} {agent.name:12} {c.value:>16}  {'SLASH ' if verdict.fraudulent else 'clear '} {verdict.reason}")
    standings = [{"analyst": a.name, "kind": a.kind, "address": acct.address} for a, acct in analysts]
    return {"chain_id": chain.chain_id, "contracts": asdict(deployed), "generated": int(time.time()),
            "settled_by": settled_by or SETTLED_BY[settle],
            "from_block": start_block, "standings": standings, "claims": feed, "trade_size": trade, "fund_wei": fund_wei}


def deliver(chain: Chain, feed: dict, reports: list, log=print) -> None:
    """Send reports the workflow's handler built (in the CRE SDK test runtime)
    through the forwarder, byte for byte as the SDK produced them. Each claim
    keeps the workflow's own log lines from that run."""
    by = {c["id"]: c for c in feed["claims"]}
    feed["sdk_runtime"] = ("Every verdict is a report built by the CRE workflow's handler (cre/vouch-verifier/workflow.ts) "
                           "in Chainlink's CRE SDK test runtime: one process plays every node, SEC's files come from "
                           "the round's EDGAR cache, nothing is signed. The runtime's EVM write is a mock (its log says "
                           "0x00…); the report was then sent through the local forwarder in tx_judge. "
                           "Not a CRE CLI simulation and not a DON.")
    for r in reports:
        c = by[r["id"]]
        tx = chain.send(chain.verifier, chain.forwarder.functions.report(chain.market.address, bytes.fromhex(r["raw"][2:]), b"", []))
        c["tx_judge"] = "0x" + tx.transactionHash.hex().removeprefix("0x")
        c["workflow_log"] = r.get("logs", [])
        log(f"  #{r['id']:<3} {'SLASH ' if r['fraudulent'] else 'clear '} {r['reason']}  (report from the SDK runtime)")


def finish(chain: Chain, feed: dict, log=print, quote=None) -> dict:
    """Read every verdict back from the chain, then let the trading agent work.
    Whoever settled the claims, what the feed shows is what the chain holds."""
    from . import journal, prices
    for f in feed["claims"]:
        s = chain.settlement(f["id"], feed.get("from_block"))
        f["verdict"] = s["status"] if s["status"] in ("cleared", "slashed") else "pending"
        f["tx_judge"] = s["tx"] or f.get("tx_judge")
        f["evidence"], f["workflow_id"] = s["evidence"], s["workflow_id"]
        f["checked"] = f["verdict"] != "pending" and int(s["evidence"], 16) != 0   # cleared by default is not checked
        if s.get("reason"):
            f["reason"] = s["reason"]
        f["agrees"] = f["verdict"] == f.get("local_verdict")
    pending = sum(1 for f in feed["claims"] if f["verdict"] == "pending")
    if pending:
        log(f"  {pending} claims have no verdict on-chain yet")

    # The trading agent: it acts on research only through the desk, which asks
    # Vouch whether each claim it cites is cleared.
    trader = _wallet(chain, "trading agent", 90)
    fund_wei = feed.get("fund_wei")
    need = fund_wei if fund_wei is not None else (10**16 if chain.chain_id == 31337 else 3 * 10**14)
    if chain.w3.eth.get_balance(trader.address) < need:
        chain.fund(trader.address, need)
    feed["journal"] = journal.trade(chain, trader, [f for f in feed["claims"] if f["verdict"] != "pending"],
                                    per_claim=feed.get("trade_size", 100 * USD), log=log, quote=quote or prices.latest)
    for f in feed["claims"]:
        f["desk"] = None
    for j in feed["journal"]:
        for a in j["attempts"]:
            c = next(c for c in feed["claims"] if c["id"] == a["claim"])
            c["desk"] = {"acted": False, "error": a["error"], "tx": a["tx"], "ticker": j["ticker"]}
        if j["status"] == "opened":
            for e in j["reasoning"]["evidence"]:
                c = next(c for c in feed["claims"] if c["id"] == e["claim"])
                c["desk"] = {"acted": True, "error": None, "tx": j["tx"], "entry": j["entry"], "side": j["side"],
                             "signal": e["signal"], "ticker": j["ticker"]}
    acted = sum(1 for j in feed["journal"] if j["status"] == "opened")
    refused = sum(len(j["attempts"]) for j in feed["journal"])
    log(f"  trading agent: {acted} paper trades, {refused} refusals on-chain")

    feed["trader"] = trader.address
    feed["standings"] = [{**s, "bonded": chain.bonded(s["address"]) / USD,
                          # as the contract counts: cleared means checked and true
                          "cleared": sum(1 for f in feed["claims"] if f["analyst"] == s["analyst"] and f["verdict"] == "cleared" and f["checked"]),
                          "cleared_unchecked": sum(1 for f in feed["claims"] if f["analyst"] == s["analyst"] and f["verdict"] == "cleared" and not f["checked"]),
                          "slashed": sum(1 for f in feed["claims"] if f["analyst"] == s["analyst"] and f["verdict"] == "slashed")}
                         for s in feed["standings"]]
    feed["reader_pool"] = chain.reader_pool() / USD
    return feed


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m vouchrh.market")
    ap.add_argument("--rpc", default="http://127.0.0.1:8545")
    ap.add_argument("--key", required=True, help="the deployer's private key (it also funds the analysts)")
    ap.add_argument("--per-ticker", type=int, default=2)
    ap.add_argument("--model", action="store_true", help="add the local language-model analyst (Ollama)")
    ap.add_argument("--token", help="bond in this ERC-20 (e.g. Paxos USDG) instead of deploying the test stand-in")
    ap.add_argument("--forwarder", help="accept verdicts from this forwarder (Chainlink's on a public chain)")
    ap.add_argument("--settle", choices=("local", "cre", "sdk"), default="local",
                    help="local: deliver the Python check's verdicts through the forwarder now; cre: post only, "
                         "the CRE workflow settles (cre workflow simulate), then run again with --finish; "
                         "sdk: post only, the workflow's handler in the CRE SDK test runtime builds the reports "
                         "(scripts/sdk_round.sh)")
    ap.add_argument("--pool", choices=("tradable", "all"), default="tradable",
                    help="which facts the analysts write about; 'all' picks the published 24 Sep round's facts")
    ap.add_argument("--replay-model", metavar="FEED",
                    help="re-post the language model's claims recorded in FEED, word for word, labelled as replayed")
    ap.add_argument("--finish", help="a posted round's feed: read its verdicts from the chain and trade on them")
    ap.add_argument("--deliver", metavar="REPORTS",
                    help="with --finish: first send each report the workflow built in the CRE SDK test runtime "
                         "(cre/vouch-verifier/sdk-round.ts) through the forwarder")
    ap.add_argument("--window", type=int, default=3600, help="challenge window in seconds (a CRE round needs time to settle)")
    ap.add_argument("--workflow-owner", help="production: accept reports only from this CRE workflow owner")
    ap.add_argument("--workflow-name", help="production: ... and this workflow name")
    ap.add_argument("--bond", type=float, default=500, help="each analyst's bond, in token units")
    ap.add_argument("--stake", type=float, default=25, help="stake per claim, in token units")
    ap.add_argument("--trade", type=float, default=100, help="the trading agent's paper size per claim with a signal")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "feed" / "feed.json"))
    args = ap.parse_args(argv)
    chain = Chain(args.rpc, args.key)
    if args.finish:
        from .chain import Deployed
        result = json.loads(Path(args.finish).read_text())
        chain.attach(Deployed(**result["contracts"]))
        if args.deliver:
            deliver(chain, result, json.loads(Path(args.deliver).read_text()))
        result = finish(chain, result)
    else:
        cast = None
        if args.replay_model:
            from . import analysts, llm
            cast = list(analysts.CAST)
            cast.insert(1, llm.replayed(args.replay_model))
        result = run(chain, per_ticker=args.per_ticker, with_model=args.model, token=args.token,
                     bond=int(args.bond * USD), stake=int(args.stake * USD), trade=int(args.trade * USD),
                     forwarder=args.forwarder, settle=args.settle, window=args.window,
                     workflow_owner=args.workflow_owner, workflow_name=args.workflow_name,
                     pool=args.pool, cast=cast)
        if args.settle == "local":
            result = finish(chain, result)
        elif args.model and not any(c["analyst_kind"] == "model" for c in result["claims"]):
            raise SystemExit("--model was asked for but the model wrote no claims; stopping before any verdict")
        else:
            txs = Path(args.out).with_suffix(".posts.txt")
            txs.write_text("".join(f"{c['id']} {c['tx_post']}\n" for c in result["claims"]))
            print(f"posted {len(result['claims'])} claims; their transactions are in {txs} for the CRE workflow")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1))
    print(f"-> {args.out}  ({len(result['claims'])} claims, reader pool {result.get('reader_pool', 0)} tUSDG)")


if __name__ == "__main__":
    main()
