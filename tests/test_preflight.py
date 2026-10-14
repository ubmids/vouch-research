"""What scripts/cre_round.sh checks before it spends anything, and the two ways
the AI analyst can be in a round: the model asked again (only if it writes the
published claim again), or its published words re-posted, labelled."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
PUBLISHED = os.path.join(ROOT, "web", "feed.json")
HERO = {"sentence": 2, "value": "$1.37 billion", "metric": "Depreciation expense for three months ended June 30, 2026",
        "summary": "Depreciation for Q3 2026 was $1.37 billion."}
RIGHT = {**HERO, "summary": "TSLA's depreciation was $1.37 billion in Q2 2026."}


def published():
    return json.load(open(PUBLISHED))


def test_pool_all_picks_the_published_rounds_facts():
    """The 13 Oct change preferred 'tradable' facts, which dropped Tesla's
    depreciation sentence: a CRE round could not ask the model about it."""
    from vouchrh.llm import HERO_SENTENCE
    from vouchrh.market import choose_facts
    feed = published()
    chosen = choose_facts(per_ticker=2, seed=7, pool="all")
    for t, filing, text, found, picks in chosen:
        diligent = [c["quote"] for c in feed["claims"] if c["ticker"] == t and c["analyst"] == "Diligent"]
        assert [f.sentence for f in picks] == diligent, t
    tsla = next(p for t, *_, p in chosen if t == "TSLA")
    assert HERO_SENTENCE in [f.sentence for f in tsla]
    tradable = next(p for t, *_, p in choose_facts(("TSLA",), 2, 7, "tradable"))
    assert HERO_SENTENCE not in [f.sentence for f in tradable]   # why the round needs pool="all"


class _Ollama:
    """A stand-in for Ollama's /api/tags and /api/chat that answers one fixed claim."""

    def __init__(self, answer: dict):
        outer = self
        self.prompts = []

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, body):
                b = json.dumps(body).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

            def do_GET(self):
                self._send({"models": [{"name": "qwen2.5:7b-instruct", "digest": "stub"}]})

            def do_POST(self):
                req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.prompts.append(req)
                self._send({"message": {"content": json.dumps(answer)}})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


@pytest.fixture
def ollama(monkeypatch):
    made = []

    def start(answer):
        o = _Ollama(answer)
        made.append(o)
        from vouchrh import llm
        monkeypatch.setattr(llm, "HOST", o.url)
        return o
    yield start
    for o in made:
        o.close()


def test_the_dry_run_passes_only_when_the_model_writes_the_hero_again(ollama):
    from vouchrh import llm
    o = ollama(HERO)
    lines = []
    assert llm.dry_run(log=lines.append)
    assert "the hero claim reproduces" in lines[-1]
    # it asked what the round asks: the depreciation sentence among its neighbours, at temperature 0, seed 7
    ask = o.prompts[0]
    assert ask["options"]["temperature"] == 0 and ask["options"]["seed"] == 7
    assert llm.HERO_SENTENCE in ask["messages"][1]["content"]


def test_the_dry_run_fails_when_the_model_writes_a_correct_claim(ollama):
    from vouchrh import llm
    ollama(RIGHT)
    lines = []
    assert not llm.dry_run(log=lines.append)
    assert "NOT the published claim" in lines[-1]


def test_the_dry_run_fails_with_no_model(monkeypatch):
    from vouchrh import llm
    monkeypatch.setattr(llm, "HOST", "http://127.0.0.1:9")
    lines = []
    assert not llm.dry_run(log=lines.append)
    assert "no qwen2.5:7b-instruct" in lines[0]


def test_a_round_asked_for_the_model_stops_before_deploying_when_it_is_missing(monkeypatch):
    from vouchrh import llm
    from vouchrh.market import run
    monkeypatch.setattr(llm, "HOST", "http://127.0.0.1:9")

    class NoChain:          # anything touching the chain would fail loudly
        chain_id = 46630
    with pytest.raises(SystemExit, match="no qwen2.5"):
        run(NoChain(), tickers=("TSLA",), with_model=True, log=lambda *_: None)


def test_replayed_claims_are_the_published_words_with_their_provenance():
    from vouchrh import analysts, llm
    from vouchrh.market import choose_facts
    Replayed = llm.replayed(PUBLISHED)
    feed = published()
    a = Replayed(seed=7)
    got = []
    for t, filing, text, found, picks in choose_facts(per_ticker=2, seed=7, pool="all"):
        for fact in picks:
            c = a.claim(t, filing.accession, fact, found)
            got.append((c, a.provenance(c)))
    model = [r for r in feed["claims"] if r["analyst_kind"] == "model"]
    assert len(got) == len(model) == 10
    for (c, prov), r in zip(got, model):
        assert "0x" + c.digest().hex() == r["hash"] == prov["hash"]     # the words the v1 market stored
        assert prov["claim"] == r["id"] and prov["market"] == feed["contracts"]["market"]
    hero = next(c for c, p in got if p["claim"] == 6)
    assert hero.summary == "Depreciation for Q3 2026 was $1.37 billion."
    assert Replayed.kind == "model" and Replayed.name == "Qwen 2.5 7B"
    assert analysts.Diligent.kind == "scripted"
