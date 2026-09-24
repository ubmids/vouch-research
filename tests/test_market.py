"""A whole round on a real EVM (anvil), against real SEC filings from the cache.

The claims are real sentences from real 10-Qs; the analysts are scripted so the
test can say which must be slashed. What is asserted is the thing the product
promises: honest research keeps its bond, every way of lying loses it, and not
a unit of stablecoin is created or lost on the way.
"""
import os, shutil, socket, subprocess, sys, time
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

ANVIL = shutil.which("anvil") or os.path.expanduser("~/.foundry/bin/anvil")
KEY0 = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


@pytest.fixture(scope="module")
def chain():
    if not os.path.exists(ANVIL):
        pytest.skip("anvil not installed")
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    proc = subprocess.Popen([ANVIL, "--silent", "--port", str(port)])
    try:
        from vouchrh.chain import Chain
        for _ in range(50):
            try:
                c = Chain(f"http://127.0.0.1:{port}", KEY0); c.w3.eth.block_number; break
            except Exception:
                time.sleep(0.1)
        yield c
    finally:
        proc.terminate(); proc.wait(timeout=10)


def test_honest_research_keeps_its_bond_and_every_lie_loses_it(chain):
    from vouchrh.market import run, CHALLENGER
    from vouchrh.chain import USD
    r = run(chain, tickers=("TSLA", "AMD"), per_ticker=2, log=lambda *_: None)
    by = {s["analyst"]: s for s in r["standings"]}
    assert by["Diligent"]["slashed"] == 0 and by["Diligent"]["bonded"] == 500
    for liar in ("Misreader", "Embellisher", "Fabricator"):
        assert by[liar]["cleared"] == 0, liar
        assert by[liar]["slashed"] == 4, liar
    slashed_total = sum(f["stake"] for f in r["claims"] if f["verdict"] == "slashed")
    held = chain.usdg.functions.balanceOf(chain.market.address).call() / USD
    paid = chain.usdg.functions.balanceOf(CHALLENGER).call() / USD
    assert paid + r["reader_pool"] == slashed_total
    assert held == sum(s["bonded"] for s in r["standings"]) + r["reader_pool"]


def test_the_chain_holds_the_hash_of_exactly_the_published_words(chain):
    from vouchrh.market import run
    r = run(chain, tickers=("NFLX",), per_ticker=1, log=lambda *_: None)
    for f in r["claims"]:
        on_chain = chain.market.functions.claim(f["id"]).call()
        assert "0x" + on_chain[4].hex() == f["hash"]
