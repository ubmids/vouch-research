"""KOL mode on real posts: the Mastodon fetch, the post reader (rules, or a
model behind a fake OpenAI-compatible server; no model runs here), the
recorded reply that re-verify checks, and a round the agent stakes itself."""
import json
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from vouchrh import kol, posts_fetch, reader

PAGE = json.loads((Path(__file__).parent / "data" / "mastodon_tag_AMD.json").read_text())
TSLA = ("FrUD's Take:\n\n\"The clearest driver of that shrinking profit is regulatory credits. Tesla booked just "
        "$146 million in credit revenue in Q2, down 67% from $439 million a year ago.\"\n\n$TSLA $SPCX")


class Fake:
    """An OpenAI-compatible /chat/completions; `reply(post_text)` says what it answers."""

    def __init__(self, reply):
        self.reply, self.seen = reply, []
        fake = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.seen.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
                text = body["messages"][-1]["content"].split("Post:\n", 1)[1]
                out = json.dumps({"choices": [{"message": {"role": "assistant", "content": fake.reply(text)}}]})
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(out.encode())

            def log_message(self, *a):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"

    def cfg(self):
        return {"kind": "model", "url": self.url, "model": "fake-reader-1", "key": "sk-test-not-recorded", "timeout": 5}


def checkable(text):
    """Reads the first scaled $ figure in a post as a checkable Q2 figure, the way a model might."""
    import re
    m = re.search(r"\$[0-9][0-9,.]*\s?(?:B|M|billion|million)\b", text)
    t = next((t for t in reader.TICKERS if t in text), None) or \
        next((t for n, t in kol.NAMES.items() if n.lower() in text.lower()), None)
    return json.dumps({"ticker": t, "figure": m.group(0) if m else None, "period": "Q2" if "Q2" in text else None,
                       "sentiment": "bearish", "conviction": "medium", "urgency": "normal",
                       "checkable": bool(m and t), "why": "a reported figure"})


@pytest.fixture
def fake():
    f = Fake(checkable)
    yield f
    f.server.shutdown()


# ---- the fetch ---------------------------------------------------------------------------

def test_the_fetch_keeps_posts_in_the_window_that_name_a_company_and_state_a_figure():
    stats = {}
    got = posts_fetch.parse(PAGE["statuses"], "mastodon.social", "2026-10-15T00:00:00Z", stats=stats)
    assert len(stats["naming"]) == 4                       # all four name AMD
    assert [p["account"] for p in got] == ["sheepfreak@pixelfed.social"]   # only one states a figure ("3B")
    p = got[0]
    assert p["instance"] == "pixelfed.social" and p["url"].startswith("https://pixelfed.social/")
    assert "<" not in p["text"] and "\n\n\n" not in p["text"] and "AMD Radeon" in p["text"]
    assert p["sha256"] == posts_fetch.sha(p["text"]) and p["fetched_at"] == "2026-10-15T00:00:00Z"
    assert posts_fetch.parse(PAGE["statuses"], "mastodon.social", "x", since="2026-08-06") == []   # outside the window


def test_html_is_stripped_and_a_local_account_gets_its_instance():
    s = {"id": "1", "created_at": "2026-07-23T10:00:00.000Z", "url": "https://mastodon.social/@ab/1", "uri": "u",
         "content": "<p>Tesla revenue <b>$28.24&nbsp;billion</b> in Q2 &amp; more<br>next line</p><p>para</p>",
         "spoiler_text": "", "account": {"acct": "ab"}}
    [p] = posts_fetch.parse([s], "mastodon.social", "t")
    assert p["text"] == "Tesla revenue $28.24 billion in Q2 & more\nnext line\n\npara"
    assert p["account"] == "ab@mastodon.social" and p["instance"] == "mastodon.social"


def test_the_fetch_jumps_to_a_date_pages_back_and_stops_at_the_cap():
    assert posts_fetch.snowflake(posts_fetch.day("2026-09-15")) >> 16 == 1789430400000
    calls = []

    def page(url):
        calls.append(url)
        if "mstdn.social" in url:
            raise urllib.error.HTTPError(url, 422, "Unprocessable", {}, None)
        return PAGE["statuses"]                       # fewer than 40: the timeline ends here

    jobs = [("mstdn.social", "AMD", "2026-08-06", 3), ("mstdn.social", "TSLA", "2026-08-06", 3),
            ("mastodon.social", "AMD", "2026-08-06", 3), ("mastodon.social", "Tesla", "2026-08-06", 3)]
    snap = posts_fetch.fetch(jobs, max_requests=2, pause=0, log=lambda *_: None, fetch_page=page)
    assert len(calls) == 2                            # the dead instance is asked once, then the cap stops it
    assert f"max_id={posts_fetch.snowflake(posts_fetch.day('2026-08-06'))}" in calls[1]
    assert snap["label"].startswith("REAL") and snap["counts"]["kept"] == len(snap["posts"]) == 1
    assert "error" in snap["requests"][0] and snap["requests"][1]["statuses"] == 4
    assert len(posts_fetch.plan()) and all(n <= 5 for *_, n in posts_fetch.plan())


def test_the_committed_snapshot_is_real_hashed_and_kept_apart_from_the_fixtures():
    snap = kol.load_real()
    assert snap["label"].startswith("REAL") and snap["posts"]
    assert all(p["url"].startswith("https://") and p["account"] and p["created_at"] for p in snap["posts"])
    assert all("2026-07-15" <= p["created_at"][:10] < "2026-09-15" for p in snap["posts"])
    assert kol.load()["label"].startswith("FIXTURE")
    with pytest.raises(ValueError):
        kol.load(kol.REAL)                           # real posts never pass as the fixture, nor the other way
    with pytest.raises(ValueError):
        kol.load_real(kol.POSTS)


def test_handles_are_shortened_unless_asked():
    assert kol.short_handle("robert@mastodon.social") == "ro…@mastodon.social"
    assert kol.short_handle("sleepindogo.bsky.social@bsky.brid.gy") == "sl…@bsky.brid.gy"
    assert kol.short_handle("robert@mastodon.social", full=True) == "robert@mastodon.social"


# ---- the reader --------------------------------------------------------------------------

def test_the_rules_are_the_default_reader():
    cfg = reader.config({})
    assert cfg["kind"] == "rules"
    r = reader.read(TSLA, cfg)
    assert (r["ticker"], r["figure"], r["value"], r["period"], r["checkable"]) == \
        ("TSLA", "$146 million", "$146 million", "Q2", True)
    assert r["reader"] == {"kind": "rules"}
    assert all(ok for _, ok in reader.replay(r, TSLA))
    with pytest.raises(ValueError):
        reader.config({"VOUCH_READER": "vibes"})


def test_a_model_reads_a_post_and_the_record_keeps_what_it_was_sent_and_said(fake):
    r = reader.read(TSLA, fake.cfg())
    assert (r["ticker"], r["figure"], r["value"], r["period"], r["checkable"]) == \
        ("TSLA", "$146 million", "$146 million", "Q2", True)
    rd = r["reader"]
    assert rd["kind"] == "model" and rd["model"] == "fake-reader-1" and rd["output"] == checkable(TSLA)
    assert rd["messages"] == reader.messages(TSLA)
    assert rd["messages_sha256"] == reader.sha(reader.canonical(rd["messages"]))
    assert rd["output_sha256"] == reader.sha(rd["output"])
    req = fake.seen[0]
    assert req["path"] == "/v1/chat/completions" and req["body"]["temperature"] == 0
    assert req["auth"] == "Bearer sk-test-not-recorded" and "sk-test" not in json.dumps(r)
    assert all(ok for _, ok in reader.replay(r, TSLA))


def test_an_edited_reading_reply_or_post_is_caught(fake):
    r = reader.read(TSLA, fake.cfg())
    edited = json.loads(json.dumps(r))
    edited["value"] = "$1.46 billion"
    assert not dict(reader.replay(edited, TSLA))["the model's recorded reply gives exactly this reading"]
    other = json.loads(json.dumps(r))
    other["reader"]["output"] = other["reader"]["output"].replace("bearish", "bullish")
    assert not all(ok for _, ok in reader.replay(other, TSLA))         # the hash no longer matches
    assert not reader.replay(r, TSLA.replace("146", "164"))[0][1]       # sent words must be the post's
    assert reader.fingerprint(r) != reader.fingerprint(edited)


@pytest.mark.parametrize("reply, why", [
    (lambda t: "It is about Tesla.", "JSONDecodeError"),
    (lambda t: json.dumps({"ticker": "TSLA", "sentiment": "angry"}), "sentiment"),
])
def test_a_reply_that_is_not_a_reading_falls_back_to_the_rules(reply, why):
    f = Fake(reply)
    try:
        r = reader.read(TSLA, f.cfg())
    finally:
        f.server.shutdown()
    assert r["reader"]["kind"] == "rules" and why in r["reader"]["fallback_reason"]
    assert {k: v for k, v in r.items() if k != "reader"} == reader.by_rules(TSLA)


def test_a_figure_the_post_does_not_state_is_not_checkable():
    out = json.dumps({"ticker": "TSLA", "figure": "$9.99 billion", "period": "Q3 2026", "sentiment": "bullish",
                      "conviction": "high", "urgency": "urgent", "checkable": True})
    r = reader.parse(out, TSLA)
    assert not r["checkable"] and "not in the post" in r["not_checkable"]
    assert r["period"] is None                                          # a period the post never wrote is dropped
    per_share = reader.parse(out.replace("$9.99 billion", "$146"), TSLA)
    assert not per_share["checkable"] and per_share["value"] is None
    assert reader.value_of("$1.54B") == "$1.54 billion" and reader.value_of("587 million") == "$587 million"


def test_a_post_with_no_figure_is_read_by_the_rules_without_asking(fake):
    r = reader.read("Tesla is going to the moon. $TSLA", fake.cfg())
    assert not fake.seen and r["reader"]["kind"] == "rules" and "model_not_asked" in r["reader"]


# ---- the round ---------------------------------------------------------------------------

def test_a_real_round_the_agent_stakes_and_reverifies(chain, fake):
    from vouchrh.journal import verify
    from vouchrh.market import finish
    snap = kol.load_real()
    posts = [next(p for p in snap["posts"] if needle in p["text"])
             for needle in ("$146 million", "$28.24 billion", "Netflix Paid $587 Million", "Tesla recalls")]
    feed = kol.run_real(chain, {**snap, "posts": posts}, log=lambda *_: None, reader_cfg=fake.cfg())
    feed = finish(chain, feed, log=lambda *_: None, quote=lambda t: None)
    assert feed["source"] == "real" and feed["fixture"] is None and feed["real"].startswith("REAL")
    assert feed["reader"]["model"] == "fake-reader-1" and feed["reader"]["system_sha256"] == reader.sha(reader.SYSTEM)
    assert len(feed["posts_read"]) == len(posts) and all("messages" not in p["reading"]["reader"] for p in feed["posts_read"])
    assert feed["claims"] and all(c["agrees"] for c in feed["claims"])
    agent = feed["standings"][0]
    assert len(feed["standings"]) == 1 and agent["analyst"] == kol.AGENT
    for c in feed["claims"]:
        assert c["analyst_kind"] == "kol_real" and c["analyst_address"] == agent["address"]
        assert c["post"]["real"] and not c["post"]["fixture"] and c["post"]["url"].startswith("https://")
        assert "…@" in c["post"]["handle"] and c["post"]["handle"] in c["analyst"] and "account" not in c["post"]
        assert c["reading"]["reader"]["kind"] == "model" and c["value"] == c["reading"]["value"]
    assert agent["cleared"] + agent["cleared_unchecked"] + agent["slashed"] == len(feed["claims"])
    for j in feed["journal"]:
        bound = j["reasoning"]["readings"]
        assert [b["claim"] for b in bound] == sorted(j["read"])
        assert all(b["post_url"].startswith("https://") and b["reader"] == "model" for b in bound)
    results = verify(feed, chain, edgar_check=False)
    assert results and all(r["ok"] for r in results), [r for r in results if not r["ok"]]
    assert any("recorded reply gives exactly this reading" in r["check"] for r in results)
    # A reading edited after the trade no longer matches the hash the desk stored.
    c = feed["claims"][0]
    c["reading"]["sentiment"] = "bullish" if c["reading"]["sentiment"] != "bullish" else "bearish"
    bad = [r for r in verify(feed, chain, edgar_check=False) if not r["ok"]]
    assert bad and any("commits to how the agent read" in r["check"] for r in bad)


def test_a_figure_only_in_a_table_is_not_staked():
    # The check reads sentences, not tables: a figure the filing gives only in a
    # table can be neither confirmed nor refuted, so the agent does not stake on it.
    from vouchrh import kol
    text = ("Total net sales 167,702 200,606 323,369 382,125. "
            "Net sales increased 20% to $200.6 billion in the second quarter.")
    assert kol.confirmable("Amazon Q2 net sales $200.6 billion", "$200.6 billion", text)
    assert not kol.confirmable("Amazon Q2 net sales $200.6 billion", "$200.6 billion", "Total net sales 167,702 200,606 323,369 382,125.")
    # the same number about something else is not a source
    assert not kol.confirmable("Netflix ad revenue tracks to $3 billion", "$3 billion",
                               "The Company entered into a five-year, $3 billion unsecured revolving credit facility.")
