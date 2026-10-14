"""The CRE workflow's report, delivered to the contract.

The workflow test (cre/vouch-verifier/workflow.test.ts) runs the handler in the
Chainlink CRE SDK's test runtime and writes the raw report the SDK built for
the AI's wrong-quarter claim. Here that exact byte string goes through a
forwarder on anvil, laid out as Chainlink's mock forwarder takes it, into
BondedClaims.onReport: the claim is slashed with the workflow's reason and the
filing hash it committed to.
"""
import json
import os
import shutil
import subprocess
import tempfile

import pytest

WF = os.path.join(os.path.dirname(__file__), "..", "cre", "vouch-verifier")
BUN = shutil.which("bun") or os.path.expanduser("~/.bun/bin/bun")


@pytest.fixture(scope="module")
def report():
    if not os.path.exists(BUN) or not os.path.exists(os.path.join(WF, "node_modules")):
        pytest.skip("bun or the workflow's node_modules not installed (cd cre/vouch-verifier && bun install)")
    out = tempfile.mkdtemp()
    r = subprocess.run([BUN, "test", "workflow.test.ts"], cwd=WF, env={**os.environ, "VOUCH_REPORT_OUT": out},
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    path = os.path.join(out, "wrong-quarter.json")
    if not os.path.exists(path):
        pytest.skip("the EDGAR cache has no TSLA 10-Q, so the workflow test skipped")
    return json.load(open(path))


def test_the_sdk_built_report_settles_the_claim_through_the_forwarder(chain, report):
    from eth_utils import keccak
    from vouchrh import edgar
    from vouchrh.chain import USD

    d = chain.deploy()                       # local forwarder; no workflow identity, like CRE's mock forwarder
    acct = chain.verifier
    chain.onboard(acct, 500 * USD)
    words = report["claim"].encode()
    for i in range(6):                       # the workflow test reported on claim #6
        chain.post(acct, "TSLA", "0001628280-26-049270", f"filler {i}".encode(), 25 * USD)
    cid, _ = chain.post(acct, "TSLA", "0001628280-26-049270", words, 25 * USD)
    assert cid == 6
    raw = bytes.fromhex(report["raw"][2:])
    tx = chain.send(acct, chain.forwarder.functions.report(d.market, raw, b"", []))
    assert tx.status == 1
    s = chain.settlement(cid)
    assert s["status"] == "slashed"
    assert s["reason"] == "wrong quarter: the period ended in June, the claim says Q3 2026"
    assert s["evidence"] == "0x" + keccak(edgar.canonical(edgar.latest("TSLA").raw())).hex()


MOCK_FORWARDER = "0x0b93082D9b3C7C97fAcd250082899BAcf3af3885"   # Chainlink CRE, Robinhood Chain testnet
RH_RPC = "https://rpc.testnet.chain.robinhood.com"


@pytest.mark.skipif(not os.environ.get("VOUCH_FORK"), reason="set VOUCH_FORK=1 to fork Robinhood Chain testnet")
def test_chainlinks_own_mock_forwarder_delivers_it_on_a_fork_of_robinhood_testnet(report):
    """The same bytes, through Chainlink's deployed MockKeystoneForwarder, on a
    local fork of Robinhood Chain testnet: nothing is sent to the real chain."""
    import socket, subprocess, time
    from conftest import ANVIL, KEY0
    from vouchrh.chain import Chain, USD
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    proc = subprocess.Popen([ANVIL, "--silent", "--port", str(port), "--fork-url", RH_RPC])
    try:
        for _ in range(100):
            try:
                c = Chain(f"http://127.0.0.1:{port}", KEY0); c.w3.eth.block_number; break
            except Exception:
                time.sleep(0.2)
        assert c.chain_id == 46630
        d = c.deploy(forwarder=MOCK_FORWARDER)
        c.onboard(c.verifier, 500 * USD)
        for i in range(6):
            c.post(c.verifier, "TSLA", "0001628280-26-049270", f"filler {i}".encode(), 25 * USD)
        cid, _ = c.post(c.verifier, "TSLA", "0001628280-26-049270", report["claim"].encode(), 25 * USD)
        tx = c.send(c.verifier, c.forwarder.functions.report(d.market, bytes.fromhex(report["raw"][2:]), b"", []))
        assert tx.status == 1
        st = c.settlement(cid)
        assert st["status"] == "slashed" and st["reason"].startswith("wrong quarter")
    finally:
        proc.terminate(); proc.wait(timeout=10)
