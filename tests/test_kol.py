"""KOL mode: posts by market voices, read by fixed rules, checked as staked
stories against the 10-Q, and only the ones that held move the agent."""
from vouchrh import kol


def test_the_posts_are_a_labelled_fixture_of_twenty():
    fx = kol.load()
    assert fx["label"].startswith("FIXTURE") and "fictional" in fx["label"]
    assert len(fx["posts"]) == 20 and len({p["handle"] for p in fx["posts"]}) == 20


def test_the_reading_rules():
    r = kol.read("$TSLA services and other revenue increased $1.54B, +50% in Q2 2026. Loading up before the open!")
    assert (r["ticker"], r["value"], r["sentiment"], r["conviction"], r["urgency"]) == \
        ("TSLA", "$1.54 billion", "bullish", "high", "urgent")
    r = kol.read("Tesla R&D expenses increased $782M in Q2 2026. Margins will get crushed.")
    assert (r["ticker"], r["value"], r["sentiment"]) == ("TSLA", "$782 million", "bearish")
    r = kol.read("Hearing $TSLA booked $12B of new backlog. Huge if true.")
    assert r["conviction"] == "low"
    assert kol.story("up $350M (+13%)") == "up $350 million (+13%)"


def test_each_story_gets_the_verdict_it_was_written_for():
    from vouchrh import edgar
    from vouchrh.analysts import facts
    from vouchrh.verifier import audit_claim
    want = {  # the posts that are wrong, and how
        "@deliveries_dan": "wrong quarter", "@leak_larry": "wrong quarter", "@amort_andy": "wrong quarter",
        "@tokenized_tess": "claimed value not grounded", "@fomo_frank": "claimed value not grounded",
        "@macro_mia": "claimed value not grounded",
        "@hype_hank": "the summary reverses", "@whale_watch_wu": "the summary reverses", "@bagholder_ben": "the summary reverses",
    }
    filings = {}
    for p in kol.load()["posts"]:
        t = kol.read(p["text"])["ticker"]
        if t not in filings:
            f = edgar.latest(t)
            filings[t] = (f, f.text())
        f, text = filings[t]
        c, _ = kol.claim_of(p, f, text, facts(text))
        v = audit_claim(c.value, c.quote, text, c.summary, c.metric)
        if p["handle"] in want:
            assert v.fraudulent and v.reason.startswith(want[p["handle"]]), (p["handle"], v.reason)
        else:
            assert not v.fraudulent, (p["handle"], v.reason)
            assert c.value in c.quote                           # grounded in the sentence that states it


def test_a_kol_round_trades_only_on_stories_that_held(chain):
    from vouchrh.journal import verify
    from vouchrh.market import finish
    feed = kol.run(chain, log=lambda *_: None)
    feed = finish(chain, feed, log=lambda *_: None, quote=lambda t: None)
    assert feed["mode"] == "kol" and feed["fixture"].startswith("FIXTURE")
    assert len(feed["claims"]) == 20 and all(c["agrees"] and c["post"]["fixture"] for c in feed["claims"])
    by = {c["id"]: c for c in feed["claims"]}
    opened = [j for j in feed["journal"] if j["status"] == "opened"]
    assert opened
    for j in feed["journal"]:
        assert all(by[e["claim"]]["verdict"] == "cleared" for e in j["reasoning"]["evidence"])
        assert all(by[a["claim"]]["verdict"] == "slashed" for a in j["attempts"])   # each refusal was a wrong story
    hype = next(c for c in feed["claims"] if c["analyst"] == "@deliveries_dan")    # high conviction, wrong quarter
    assert hype["reading"]["conviction"] == "high" and hype["desk"]["acted"] is False
    results = verify(feed, chain, edgar_check=True)
    assert results and all(r["ok"] for r in results), [r for r in results if not r["ok"]]
