"""The fallback round: verdicts built by the CRE workflow's own handler in the
CRE SDK test runtime (cre/vouch-verifier/sdk-round.ts), delivered through the
forwarder, with the AI analyst's published words replayed and labelled."""
import json
import os
import shutil
import subprocess

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
WF = os.path.join(ROOT, "cre", "vouch-verifier")
BUN = shutil.which("bun") or os.path.expanduser("~/.bun/bin/bun")


def test_the_workflow_handler_settles_a_round_and_the_hero_is_refused(chain, tmp_path, quote=lambda t: None):
    if not os.path.exists(os.path.join(WF, "node_modules")):
        pytest.skip("cd cre/vouch-verifier && bun install")
    from vouchrh import analysts, llm
    from vouchrh.market import deliver, finish, run
    cast = list(analysts.CAST)
    cast.insert(1, llm.replayed(os.path.join(ROOT, "web", "feed.json")))
    posted = run(chain, tickers=("TSLA",), per_ticker=2, settle="sdk", pool="all", cast=cast, log=lambda *_: None)
    assert posted["settled_by"] == "the CRE workflow in Chainlink's SDK test runtime, via a local forwarder"
    posts = tmp_path / "posts.txt"
    posts.write_text("".join(f"{c['id']} {c['tx_post']}\n" for c in posted["claims"]))
    out = tmp_path / "reports.json"
    r = subprocess.run([BUN, "test", "--timeout", "600000", "./sdk-round.ts"], cwd=WF, capture_output=True, text=True, timeout=900,
                       env={**os.environ, "VOUCH_RPC": chain.w3.provider.endpoint_uri, "VOUCH_MARKET": chain.market.address,
                            "VOUCH_POSTS": str(posts), "VOUCH_SDK_OUT": str(out)})
    assert r.returncode == 0, r.stdout + r.stderr
    reports = json.loads(out.read_text())
    assert [x["id"] for x in reports] == [c["id"] for c in posted["claims"]]
    deliver(chain, posted, reports, log=lambda *_: None)
    done = finish(chain, posted, log=lambda *_: None, quote=quote)
    assert all(c["agrees"] and c["checked"] for c in done["claims"])        # the TypeScript verdicts are the Python ones
    hero = next(c for c in done["claims"] if c.get("replayed_from", {}).get("claim") == 6)
    assert hero["summary"] == "Depreciation for Q3 2026 was $1.37 billion."
    assert hero["verdict"] == "slashed" and hero["reason"] == llm.HERO_REASON
    assert hero["desk"]["acted"] is False and hero["desk"]["error"] == "NotCleared"   # refused on-chain
    assert any("verdict: SLASH (wrong quarter" in line for line in hero["workflow_log"])
    assert "Not a CRE CLI simulation" in done["sdk_runtime"]
