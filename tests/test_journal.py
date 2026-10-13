"""The trading agent's journal: every trade cites cleared claims, the trail
re-verifies end to end, and any edit to it is caught.
"""
import copy

import pytest

from test_market import quote


@pytest.fixture(scope="module")
def feed(chain):
    from vouchrh.market import run, finish
    return finish(chain, run(chain, tickers=("TSLA", "NFLX", "AMD"), per_ticker=2, log=lambda *_: None),
                  log=lambda *_: None, quote=quote)


def _fails(results):
    return [r["check"] for r in results if not r["ok"]]


def test_the_whole_trail_re_verifies_against_the_chain_and_edgar(chain, feed):
    from vouchrh.journal import verify
    results = verify(feed, chain)
    assert results and not _fails(results)
    assert any(j["status"] == "opened" for j in feed["journal"])


def test_every_trade_cites_claim_ids_and_their_verdict_transactions(feed):
    for j in feed["journal"]:
        if j["status"] != "opened":
            continue
        assert j["reasoning"]["evidence"]
        for e in j["reasoning"]["evidence"]:
            assert isinstance(e["claim"], int) and e["hash"].startswith("0x") and e["verdict_tx"].startswith("0x")
        assert j["reasoning"]["price"]["price"] == quote(j["ticker"])["price"]


def test_an_edited_reasoning_record_no_longer_matches_the_chain(chain, feed):
    from vouchrh.journal import verify
    bad = copy.deepcopy(feed)
    j = next(j for j in bad["journal"] if j["status"] == "opened")
    j["reasoning"]["evidence"][0]["why"] = "the agent had a hunch"
    assert "reasoning record hashes to what the desk stored" in _fails(verify(bad, chain, edgar_check=False))


def test_edited_claim_words_no_longer_match_the_chain(chain, feed):
    from vouchrh.journal import verify
    bad = copy.deepcopy(feed)
    j = next(j for j in bad["journal"] if j["status"] == "opened")
    cid = j["reasoning"]["evidence"][0]["claim"]
    c = next(c for c in bad["claims"] if c["id"] == cid)
    c["value"] = c["value"].replace("$", "$1")
    fails = _fails(verify(bad, chain, edgar_check=False))
    assert f"claim #{cid} words hash to the on-chain hash" in fails


def test_the_refused_claims_are_the_ones_that_failed_the_check(feed):
    claims = {c["id"]: c for c in feed["claims"]}
    refused = [a for j in feed["journal"] for a in j["attempts"]]
    assert refused
    for a in refused:
        assert claims[a["claim"]]["verdict"] == "slashed"
        assert a["reason"] == claims[a["claim"]]["reason"]


# ---- the policy, without a chain -----------------------------------------------------

def _c(i, value, quote_, summary="", metric="", analyst="A"):
    return {"id": i, "hash": f"0x{i:064x}", "analyst": analyst, "value": value, "quote": quote_, "summary": summary,
            "metric": metric}


REV_UP = _c(1, "$932 million", "Revenue increased by $932 million, or 93%, for the three months ended June 30, 2026 "
                               "compared to the same period in 2025.")
COST_UP = _c(2, "$782 million", "Research and development expenses increased $782 million, or 49%, in the three "
                                "months ended June 30, 2026 as compared to the three months ended June 30, 2025.")
COST_OF = _c(3, "$3.30 billion", "Cost of automotive sales revenue increased $3.30 billion, or 24%, in the three months "
                                 "ended June 30, 2026 as compared to the three months ended June 30, 2025.")
TAX = _c(4, "$161 million", "The impact of higher operating income was partially offset by a $161 million increase "
                            "in the provision for income taxes.")
FLAT = _c(5, "$8.28 billion", "Capital expenditures amounted to $8.28 billion during the six months ended June 30, 2026.")
IF = _c(6, "$14 million", "A 1% increase in SOFR as of June 30, 2026, would increase our annual interest expense by "
                          "approximately $14 million.")


def test_signals_read_what_the_figure_measures():
    from vouchrh.policy import signal
    assert signal(REV_UP)["signal"] == 1
    assert signal(COST_UP)["signal"] == -1
    assert signal(COST_OF)["signal"] == -1          # cost of revenue is a cost
    assert signal(TAX)["signal"] == -1              # the figure is the tax provision, not operating income
    assert signal(FLAT)["signal"] == 0              # capital spending: no polarity, no guess
    assert signal(IF)["signal"] == 0                # a sensitivity, not a result


def test_the_thesis_is_repeatable_and_drops_to_no_trade_at_zero():
    from vouchrh.policy import digest, record, thesis
    t1, t2 = thesis("TSLA", [REV_UP, FLAT], 100), thesis("TSLA", [FLAT, REV_UP], 100)
    assert t1 == t2 and t1["side"] == "long" and t1["notional"] == 100
    assert digest(record(t1, None, [])) == digest(record(t2, None, []))
    assert thesis("TSLA", [REV_UP, COST_UP], 100)["side"] is None
    assert thesis("TSLA", [COST_UP, COST_OF], 100)["side"] == "short"


def test_a_fabricated_story_can_flip_the_trade_until_the_desk_refuses_it():
    from vouchrh.policy import thesis
    fake = _c(7, "$954 million", "Revenue increased $954 million driven by record demand for AI-enabled products in "
                                 "every region.", analyst="Fabricator")
    assert thesis("X", [COST_UP, fake, fake | {"id": 8}], 100)["side"] == "long"    # believing everything
    assert thesis("X", [COST_UP], 100)["side"] == "short"                          # on what survived the check
