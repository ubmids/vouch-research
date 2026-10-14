"""The trading agent and its journal: every paper trade, the claims behind it,
and a way for anyone to redo the whole chain of reasons.

The agent reads every claim posted about a stock, as a reader follows several
analysts. It forms a thesis with the rules in policy.py and asks the desk to
open a paper position citing everything it relied on. The desk asks Vouch
about each cited claim; if one failed the check the trade reverts, naming that
claim. The agent drops it, records the refusal (the reverted transaction is
the proof), re-forms its thesis on what is left, and tries again. What
survives is a trade backed only by research that passed, and a journal entry
that says, in order:

    claim (exact words, hash on-chain) -> filing sentence (SEC EDGAR)
      -> verdict (who wrote it, against which filing bytes, which transaction)
      -> thesis (signal per claim, the rule) -> trade (transaction, entry id)

The whole reasoning record is hashed and the hash is stored with the trade,
so it cannot be rewritten afterwards. `verify` walks the trail backwards
against the chain and EDGAR and re-runs the policy:

    python -m vouchrh.journal verify feed/feed.json --rpc http://127.0.0.1:8545
"""
from __future__ import annotations

import argparse
import json
import sys

from eth_utils import keccak
from web3.logs import DISCARD

from . import decide, edgar, policy, prices
from .chain import USD, Chain
from .verifier import audit_claim

SIDE = {"long": 0, "short": 1}


def trade(chain: Chain, agent, claims: list[dict], per_claim: int = 100 * USD, log=print,
          quote=prices.latest) -> list[dict]:
    """Run the agent over a round's claims, stock by stock. Returns the journal.
    It decides by the rules unless VOUCH_DECIDER=model (see decide.py)."""
    cfg = decide.config()
    by: dict[str, list[dict]] = {}
    for c in claims:
        by.setdefault(c["ticker"], []).append(c)
    journal = []
    for ticker, read in by.items():
        verdict_tx = {c["id"]: c.get("tx_judge") for c in read}
        cited = sorted(read, key=lambda c: c["id"])
        dropped: list[dict] = []
        price = quote(ticker)
        entry = {"ticker": ticker, "read": [c["id"] for c in read], "status": "no trade", "attempts": []}
        while cited:
            t = decide.thesis(ticker, cited, per_claim, cfg)
            if not t["side"]:
                break
            for e in t["evidence"]:
                e["verdict_tx"] = verdict_tx.get(e["claim"])
            rec = decide.record(t, price, dropped)
            h = policy.digest(rec)
            ids = [e["claim"] for e in t["evidence"]]
            out = chain.act(agent, ticker, SIDE[t["side"]], t["notional"], ids, h)
            if out["acted"]:
                entry.update(status="opened", entry=out["entry"], tx=out["tx"], side=t["side"], notional=t["notional"],
                             reasoning=rec, reasoning_hash="0x" + h.hex())
                log(f"  {ticker:5} {t['side'].upper():5} {t['notional'] / USD:>6.0f} USD paper on claims {ids} "
                    f"after {len(dropped)} refusals  tx {out['tx'][:12]}")
                break
            refused = out["claim"]
            bad = next((c for c in cited if c["id"] == refused), None)
            if bad is None:
                # Reverted for a reason that names no claim: never guess which one.
                # Stop on this stock and say so.
                entry["status"] = "error"
                entry["error"] = {"error": out["error"], "tx": out["tx"]}
                log(f"  {ticker:5} stopped: the desk reverted ({out['error']}) without naming a claim")
                break
            miss = {"claim": refused, "error": out["error"], "tx": out["tx"], "verdict": bad.get("verdict"),
                    "reason": bad.get("reason"), "side_before": t["side"]}
            dropped.append(miss)
            entry["attempts"].append({"cited": ids, "side": t["side"], **miss})
            cited = [c for c in cited if c["id"] != refused]
        if entry["status"] != "opened":
            final = t if cited and not t["side"] else decide.thesis(ticker, cited, per_claim, cfg)
            entry["reasoning"] = decide.record(final, price, dropped)
            log(f"  {ticker:5} no trade: what is left gives no direction ({len(dropped)} refusals)")
        journal.append(entry)
    return journal


# ---- re-verify the trail ---------------------------------------------------------------

def _receipt(chain: Chain, tx: str):
    return chain.w3.eth.get_transaction_receipt(tx)


def verify(feed: dict, chain: Chain, edgar_check: bool = True) -> list[dict]:
    """Walk every journal entry back to the filing. Returns a list of checks;
    each is {"entry", "check", "ok", "detail"}."""
    claims = {c["id"]: c for c in feed["claims"]}
    out = []

    def check(entry, name, ok, detail=""):
        out.append({"entry": entry, "check": name, "ok": bool(ok), "detail": detail})

    texts: dict[str, tuple[bytes, str]] = {}
    for j in feed.get("journal", []):
        tag = f"{j['ticker']} #{j.get('entry', '-')}"
        rec = j["reasoning"]
        accounted = sorted([e["claim"] for e in rec["evidence"]] + [d["claim"] for d in rec["dropped"]])
        check(tag, "every claim the agent read is either cited or refused (none quietly left out)",
              sorted(j["read"]) == accounted or j["status"] == "error", f"read {sorted(j['read'])}, accounted {accounted}")
        for a in j.get("attempts", []):
            r = _receipt(chain, a["tx"])
            check(tag, f"refusal of claim #{a['claim']} reverted on-chain", r.status == 0, a["tx"])
            unchecked = chain.market.functions.verdict(a["claim"]).call()[1] == bytes(32)
            check(tag, f"claim #{a['claim']} failed the check (or was never checked)",
                  not chain.market.functions.isCleared(a["claim"]).call() or unchecked)
        if j["status"] == "error":
            check(tag, "the agent stopped on a refusal that named no claim", False, str(j.get("error")))
            continue
        by_model = rec.get("decider", {}).get("kind") == "model"
        if by_model:   # a model is not re-run; its recorded input and reply are checked instead
            for name, ok in decide.replay(rec, claims):
                check(tag, name, ok)
        if j["status"] != "opened":
            if not by_model:
                again = policy.thesis(j["ticker"], [claims[e["claim"]] for e in rec["evidence"]], 0)
                check(tag, "re-running the policy gives no trade too", again["side"] is None)
            continue
        on = chain.desk.functions.journal(j["entry"]).call()
        h = policy.digest(rec)
        check(tag, "reasoning record hashes to what the desk stored", "0x" + on[6].hex() == "0x" + h.hex(), "0x" + h.hex())
        check(tag, "the desk's citations are the record's evidence", list(on[8]) == [e["claim"] for e in rec["evidence"]])
        check(tag, "the desk's ticker, side and notional are the record's",
              (on[5], on[1], on[4]) == (j["ticker"], SIDE[rec["side"]], rec["notional"]))
        r = _receipt(chain, j["tx"])
        opened = chain.desk.events.Opened().process_receipt(r, errors=DISCARD)
        check(tag, "the trade's transaction opened this entry", r.status == 1 and opened and opened[0].args.entry == j["entry"], j["tx"])
        for e in rec["evidence"]:
            c = claims[e["claim"]]
            words = keccak(_canonical(c))
            onc = chain.market.functions.claim(c["id"]).call()
            check(tag, f"claim #{c['id']} words hash to the on-chain hash", onc[4] == words)
            check(tag, f"claim #{c['id']} is cleared on-chain", chain.market.functions.isCleared(c["id"]).call())
            if e.get("verdict_tx"):
                vr = _receipt(chain, e["verdict_tx"])
                ids = [ev.args.id for ev in chain.market.events.Cleared().process_receipt(vr, errors=DISCARD)]
                check(tag, f"claim #{c['id']} verdict transaction cleared it", c["id"] in ids, e["verdict_tx"])
            v = chain.market.functions.verdict(c["id"]).call()
            if edgar_check:
                if c["accession"] not in texts:
                    f = next((f for f in edgar.filings(c["ticker"], ("10-Q", "10-K"), 40) if f.accession == c["accession"]), None)
                    if f is None:
                        check(tag, f"claim #{c['id']} cites a filing EDGAR lists for {c['ticker']}", False, c["accession"])
                        continue
                    texts[c["accession"]] = (f.raw(), f.text())
                raw, text = texts[c["accession"]]
                if v[1] != bytes(32):
                    check(tag, f"claim #{c['id']} verdict evidence is the filing EDGAR serves", v[1] == keccak(edgar.canonical(raw)))
                again = audit_claim(c["value"], c["quote"], text, c.get("summary", ""), c.get("metric", ""))
                check(tag, f"claim #{c['id']} re-checked against the filing: holds", not again.fraudulent, again.reason)
        if by_model:
            continue
        again = policy.thesis(j["ticker"], [claims[e["claim"]] for e in rec["evidence"]], rec["per_claim"])
        check(tag, "re-running the policy gives the same trade", (again["side"], again["notional"]) == (rec["side"], rec["notional"]),
              f"{again['side']} {again['notional'] / USD:.0f} USD")
    return out


def _canonical(c: dict) -> bytes:
    from .claims import Claim
    fields = {k: c.get(k, "") for k in ("ticker", "accession", "metric", "value", "quote", "analyst", "summary")}
    return Claim(**fields).canonical()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m vouchrh.journal")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify", help="re-verify every journal entry against the chain and EDGAR")
    v.add_argument("feed")
    v.add_argument("--rpc", required=True)
    v.add_argument("--no-edgar", action="store_true", help="skip re-fetching filings")
    args = ap.parse_args(argv)
    feed = json.load(open(args.feed))
    chain = Chain(args.rpc, "0x" + "11" * 32)
    from .chain import Deployed
    chain.attach(Deployed(**feed["contracts"]))
    results = verify(feed, chain, edgar_check=not args.no_edgar)
    last = None
    for r in results:
        if r["entry"] != last:
            print(f"\n{r['entry']}")
            last = r["entry"]
        print(f"  {'✓' if r['ok'] else '✕'} {r['check']}" + (f"  ({r['detail']})" if r["detail"] and not r["ok"] else ""))
    bad = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(bad)} of {len(results)} checks hold")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
