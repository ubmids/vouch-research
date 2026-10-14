"""The agent's model-driven decision path, against a fake OpenAI-compatible
server (no model runs here). The rules stay the default and the fallback.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from test_market import quote

CLAIMS = [
    {"id": 3, "hash": "0x" + "33" * 32, "analyst": "Diligent", "metric": "revenue", "value": "$22.5 billion",
     "summary": "", "quote": "Total revenues increased $2.1 billion, or 10%, to $22.5 billion."},
    {"id": 7, "hash": "0x" + "77" * 32, "analyst": "Model", "metric": "depreciation", "value": "$1.37 billion",
     "summary": "", "quote": "Depreciation expense during the three and six months ended June 30, 2026 was "
                             "$1.37 billion and $2.71 billion, respectively."},
]


class Fake:
    """An OpenAI-compatible /chat/completions. `reply(ids)` says what it answers."""

    def __init__(self, reply):
        self.reply, self.seen = reply, []
        fake = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.seen.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
                user = body["messages"][-1]["content"]
                ids = [r["id"] for r in json.loads(user.split("Claims:\n", 1)[1])]
                out = json.dumps({"choices": [{"message": {"role": "assistant", "content": fake.reply(ids)}}]})
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(out.encode())

            def log_message(self, *a):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"

    def cfg(self, **kw):
        return {"kind": "model", "url": self.url, "model": "fake-1", "key": "sk-test-not-recorded", "timeout": 5, **kw}


def bullish(ids):
    return json.dumps({"claims": [{"id": i, "reading": "bullish", "why": "up"} for i in ids], "side": "long",
                       "why": "all up"})


@pytest.fixture
def fake():
    f = Fake(bullish)
    yield f
    f.server.shutdown()


def test_the_rules_are_the_default_and_their_record_is_unchanged(monkeypatch):
    from vouchrh import decide, policy
    monkeypatch.delenv("VOUCH_DECIDER", raising=False)
    cfg = decide.config()
    assert cfg["kind"] == "rules"
    t = decide.thesis("TSLA", CLAIMS, 100, cfg)
    assert t == policy.thesis("TSLA", CLAIMS, 100)
    assert decide.record(t, None, []) == policy.record(t, None, [])   # earlier rounds keep their hashes


def test_a_model_decides_and_the_record_keeps_what_it_was_sent_and_said(fake):
    from vouchrh import decide
    t = decide.thesis("TSLA", CLAIMS, 100, fake.cfg())
    assert t["side"] == "long" and t["notional"] == 200
    assert [e["signal"] for e in t["evidence"]] == [1, 1]          # the model's readings, not the rules'
    d = t["decider"]
    assert d["kind"] == "model" and d["model"] == "fake-1" and d["output"] == bullish([3, 7])
    req = fake.seen[0]
    assert req["path"] == "/v1/chat/completions" and req["body"]["temperature"] == 0
    assert req["auth"] == "Bearer sk-test-not-recorded"
    rec = decide.record(t, None, [])
    assert rec["policy"] == decide.MODEL_POLICY
    assert "sk-test" not in json.dumps(rec)                        # the key is never in the hashed record
    assert all(ok for _, ok in decide.replay(rec, {c["id"]: c for c in CLAIMS}))


def test_an_edited_model_record_is_caught():
    from vouchrh import decide
    f = Fake(bullish)
    try:
        rec = decide.record(decide.thesis("TSLA", CLAIMS, 100, f.cfg()), None, [])
    finally:
        f.server.shutdown()
    claims = {c["id"]: c for c in CLAIMS}
    wrong_side = json.loads(json.dumps(rec))
    wrong_side["side"] = "short"
    assert not decide.replay(wrong_side, claims)[2][1]
    other_reply = json.loads(json.dumps(rec))
    other_reply["decider"]["output"] = other_reply["decider"]["output"].replace('"long"', '"short"')
    checks = dict(decide.replay(other_reply, claims))
    assert not all(checks.values())
    other_words = {**claims, 3: {**claims[3], "value": "$99 billion"}}
    assert not decide.replay(rec, other_words)[0][1]                # sent words must be the cited claims'


@pytest.mark.parametrize("reply, why", [
    (lambda ids: "I think you should buy.", "JSONDecodeError"),
    (lambda ids: json.dumps({"claims": [], "side": "long"}), "every claim"),
    (lambda ids: json.dumps({"claims": [{"id": 99, "reading": "bullish"}], "side": "long"}), "bad claim reading"),
    (lambda ids: json.dumps({"claims": [{"id": i, "reading": "bullish"} for i in ids], "side": "buy"}), "side"),
])
def test_a_reply_that_is_not_a_decision_falls_back_to_the_rules(reply, why):
    from vouchrh import decide, policy
    f = Fake(reply)
    try:
        t = decide.thesis("TSLA", CLAIMS, 100, f.cfg())
    finally:
        f.server.shutdown()
    assert {k: v for k, v in t.items() if k != "decider"} == policy.thesis("TSLA", CLAIMS, 100)
    assert t["decider"]["kind"] == "rules" and why in t["decider"]["fallback_reason"]


def test_no_server_or_no_settings_falls_back_to_the_rules():
    from vouchrh import decide
    down = decide.thesis("TSLA", CLAIMS, 100, {"kind": "model", "url": "http://127.0.0.1:9/v1", "model": "m",
                                               "key": "", "timeout": 2})
    assert down["decider"]["kind"] == "rules" and down["decider"]["fallback_reason"]
    unset = decide.thesis("TSLA", CLAIMS, 100, decide.config({"VOUCH_DECIDER": "model"}))
    assert "must both be set" in unset["decider"]["fallback_reason"]
    with pytest.raises(ValueError):
        decide.config({"VOUCH_DECIDER": "vibes"})


def test_whatever_the_model_says_the_desk_still_refuses_failed_claims(chain, fake, monkeypatch):
    """A model that reads every claim as bullish still cannot trade on a slashed
    one: the desk reverts, the agent asks again without it, and the trail re-verifies."""
    from vouchrh.journal import verify
    from vouchrh.market import finish, run
    monkeypatch.setenv("VOUCH_DECIDER", "model")
    monkeypatch.setenv("VOUCH_DECIDER_URL", fake.url)
    monkeypatch.setenv("VOUCH_DECIDER_MODEL", "fake-1")
    feed = finish(chain, run(chain, tickers=("TSLA",), per_ticker=2, log=lambda *_: None),
                  log=lambda *_: None, quote=quote)
    j = feed["journal"][0]
    assert j["status"] == "opened" and j["attempts"], "refused at least once, then traded"
    assert j["reasoning"]["decider"]["kind"] == "model"
    slashed = {c["id"] for c in feed["claims"] if c["verdict"] == "slashed"}
    assert slashed and not slashed & {e["claim"] for e in j["reasoning"]["evidence"]}
    results = verify(feed, chain, edgar_check=False)
    assert results and all(r["ok"] for r in results), [r["check"] for r in results if not r["ok"]]
    assert any("model's recorded reply" in r["check"] for r in results)
