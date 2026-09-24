"""The hosted API: same check as the market, and the copies never drift."""
import os, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_the_api_runs_the_same_verifier_as_the_market():
    for m in ("verifier", "edgar"):
        src = open(os.path.join(ROOT, "agent", "vouchrh", f"{m}.py")).read()
        copy = open(os.path.join(ROOT, "web", "api", "_vouchcore", f"{m}.py")).read()
        assert copy.split("\n", 1)[1] == src, f"web/api/_vouchcore/{m}.py drifted: run scripts/sync_api.sh"


def test_the_api_answers_like_the_market():
    sys.path.insert(0, os.path.join(ROOT, "web", "api"))
    os.environ["VOUCH_CACHE"] = os.path.join(ROOT, ".cache", "edgar")   # reuse the local cache
    import importlib, verify
    importlib.reload(verify)
    q = ("Depreciation expense during the three and six months ended June 30, 2026 was "
         "$1.37 billion and $2.71 billion, respectively.")
    code, ok = verify.verify({"ticker": "tsla", "value": "$1.37 billion", "quote": q, "summary": "Q2 2026 depreciation was $1.37 billion."})
    assert code == 200 and ok["verdict"] == "cleared", ok
    code, bad = verify.verify({"ticker": "TSLA", "value": "$1.37 billion", "quote": q, "summary": "Q3 2026 depreciation was $1.37 billion."})
    assert bad["verdict"] == "slashed" and bad["reason"].startswith("wrong quarter"), bad
    code, err = verify.verify({"ticker": "TSLA"})
    assert code == 400 and "missing" in err["error"]
