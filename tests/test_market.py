"""A whole round on a real EVM (anvil), against real SEC filings from the cache.

The claims are real sentences from real 10-Qs; the analysts are scripted so the
test can say which must be slashed. What is asserted is the thing the product
promises: honest research keeps its bond, every way of lying loses it, and not
a unit of stablecoin is created or lost on the way.
"""
PRICE = {"TSLA": "376.11", "AMD": "160.00", "NFLX": "1200.00"}


def quote(t):
    return {"ticker": t, "price": PRICE.get(t, "100.00"), "currency": "USD", "at": 1791909803, "source": "test"}


def round_(chain, **kw):
    from vouchrh.market import run, finish
    return finish(chain, run(chain, log=lambda *_: None, **kw), log=lambda *_: None, quote=quote)


def test_honest_research_keeps_its_bond_and_every_lie_loses_it(chain):
    from vouchrh.chain import USD
    r = round_(chain, tickers=("TSLA", "AMD"), per_ticker=2)
    by = {s["analyst"]: s for s in r["standings"]}
    assert by["Diligent"]["slashed"] == 0 and by["Diligent"]["bonded"] == 500
    for liar in ("Misreader", "Embellisher", "Fabricator"):
        assert by[liar]["cleared"] == 0, liar
        assert by[liar]["slashed"] == 4, liar
    slashed_total = sum(f["stake"] for f in r["claims"] if f["verdict"] == "slashed")
    held = chain.usdg.functions.balanceOf(chain.market.address).call() / USD
    assert r["reader_pool"] == slashed_total          # nobody challenged: every slashed unit backs readers
    assert held == sum(s["bonded"] for s in r["standings"]) + r["reader_pool"]


def test_every_verdict_arrived_through_the_forwarder_and_says_which_filing(chain):
    from eth_utils import keccak
    from vouchrh import edgar
    r = round_(chain, tickers=("NFLX",), per_ticker=1)
    raw = keccak(edgar.canonical(edgar.latest("NFLX").raw()))
    for f in r["claims"]:
        assert f["agrees"], f                         # the chain holds what the check said
        assert f["evidence"] == "0x" + raw.hex()      # and commits to the bytes EDGAR served, less its CDN tag
        receipt = chain.w3.eth.get_transaction_receipt(f["tx_judge"])
        assert receipt["to"] == chain.forwarder.address


def test_the_chain_holds_the_hash_and_the_words_that_were_published(chain):
    r = round_(chain, tickers=("NFLX",), per_ticker=1)
    for f in r["claims"]:
        on_chain = chain.market.functions.claim(f["id"]).call()
        assert "0x" + on_chain[4].hex() == f["hash"]
        posted = chain.market.events.Posted().process_receipt(chain.w3.eth.get_transaction_receipt(f["tx_post"]))[0]
        from vouchrh.journal import _canonical
        assert posted.args.claim == _canonical(f)     # the words themselves are in the record


def test_the_trading_agent_acts_only_on_cleared_research(chain):
    r = round_(chain, tickers=("TSLA", "NFLX", "AMD"), per_ticker=2)
    claims = {c["id"]: c for c in r["claims"]}
    opened = [j for j in r["journal"] if j["status"] == "opened"]
    assert opened
    for j in r["journal"]:
        for a in j["attempts"]:
            assert claims[a["claim"]]["verdict"] == "slashed" and a["error"] == "NotCleared"
            assert chain.w3.eth.get_transaction_receipt(a["tx"]).status == 0     # refused on-chain
        if j["status"] == "opened":
            assert all(claims[e["claim"]]["verdict"] == "cleared" for e in j["reasoning"]["evidence"])


def test_a_cre_round_posts_first_and_reads_its_verdicts_back_from_the_chain(chain, tmp_path):
    """The path scripts/cre_round.sh takes: post only (--settle cre), let the
    workflow settle (here: reports laid out as the CRE workflow builds them,
    through the forwarder), then --finish reads everything from the chain."""
    from eth_utils import keccak
    from vouchrh import edgar
    from vouchrh.market import run, finish
    from vouchrh.verifier import audit_claim
    posted = run(chain, tickers=("TSLA",), per_ticker=2, settle="cre", log=lambda *_: None)
    assert all("tx_judge" not in c for c in posted["claims"])
    assert posted["settled_by"].startswith("the Chainlink CRE workflow")
    f = edgar.latest("TSLA")
    raw, text = f.raw(), f.text()
    for c in posted["claims"]:                       # what each DON node computes, then the report
        v = audit_claim(c["value"], c["quote"], text, c["summary"], c["metric"])
        chain.report(c["id"], bytes.fromhex(c["hash"][2:]), v.fraudulent, keccak(edgar.canonical(raw)), v.reason)
    done = finish(chain, posted, log=lambda *_: None, quote=quote)
    for c in done["claims"]:
        assert c["verdict"] in ("cleared", "slashed") and c["agrees"], c
        assert c["tx_judge"] and c["reason"]
    assert done["journal"] and all(j["status"] in ("opened", "no trade") for j in done["journal"])
