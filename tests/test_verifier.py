"""The verifier against a real SEC filing, and against the one edit a fuzzy
match is weakest at: a single changed figure."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))
from vouchrh.verifier import audit_attestation, verify_quote, figures

# A paragraph from Tesla's 10-Q for the quarter ended 30 June 2026 (accession
# 0001628280-26-049270), with the page furniture an HTML-to-text pass leaves.
FILING = ("Automotive regulatory credits revenue decreased $293 million, or 67%, in the three months "
          "ended June 30, 2026 as compared to the three months ended June 30, 2025. Services and other "
          "revenue increased $1.54 billion, or 50%, in the three months ended June 30, 2026 as compared "
          "to the three months ended June 30, 2025. Services and other revenue increased $2.64 billion, "
          "or 46%, in the six months ended June 30, 2026 as compared to the six months ended June 30, 2025.")
REAL = ("Services and other revenue increased $1.54 billion, or 50%, in the three months ended "
        "June 30, 2026 as compared to the three months ended June 30, 2025.")


def test_an_honest_claim_passes():
    v = audit_attestation("$1.54 billion", REAL, FILING)
    assert not v.fraudulent and v.quote_check.method == "exact"


def test_a_wrong_value_behind_a_real_quote_is_caught():
    assert audit_attestation("$2.54 billion", REAL, FILING).fraudulent


def test_an_invented_sentence_is_caught():
    assert audit_attestation("80%", "Services revenue grew 80% on robotaxi subscriptions.", FILING).fraudulent


def test_extraction_noise_still_passes():
    # What HTML/PDF extraction really does: a word hyphenated across a line
    # break, doubled spaces, and a curly apostrophe. Normalisation absorbs it.
    noisy = REAL.replace("as compared", "as com-\npared").replace("three months", "three  months", 1)
    assert verify_quote(noisy, FILING).method == "exact"


def test_a_near_match_with_the_same_figures_passes():
    # A quote missing one small word is still the filing's sentence: fuzzy, and
    # allowed, because every figure in it is exactly the filing's.
    check = verify_quote(REAL.replace("in the three months", "in three months", 1), FILING)
    assert check.verified and check.method == "fuzzy", check


def test_one_changed_figure_never_passes_as_a_near_match():
    # Every single-figure edit of the real quote must fail, however similar it looks.
    for old, new in [("1.54", "1.64"), ("1.54", "1.45"), ("50%", "56%"), ("billion", "million"),
                     ("2026", "2025"), ("three months", "six months")]:
        doctored = REAL.replace(old, new, 1)
        check = verify_quote(doctored, FILING)
        assert not check.verified, (old, new, check)


def test_a_quote_stitched_from_the_neighbouring_sentence_is_caught():
    # Real words, real figures, wrong period: the six-month number with the three-month wording.
    stitched = REAL.replace("$1.54 billion, or 50%", "$2.64 billion, or 46%")
    assert not verify_quote(stitched, FILING).verified


def test_figures_are_read_with_their_scale():
    assert figures("increased $1.54 billion, or 50%") == ["1.54", "billion", "50%"]


# ---- the claim as written -------------------------------------------------
# Every case below is a real mistake our own language-model analyst made on a
# real 10-Q in September 2026, next to the correct version of the same claim.
from vouchrh.verifier import audit_claim

SBC = ("For the three and six months ended June 30, 2026, we recorded $138 million and $274 million, "
       "respectively, of stock-based compensation expense related to these grants, net of forfeitures.")
GAMING = ("Gaming net revenue of $779 million for the three months ended June 27, 2026 decreased by 31% "
          "compared to net revenue of $1.1 billion for the prior year period, primarily due to lower demand.")
BORROW = ("There were $455 million and $325 million of borrowings outstanding under these facilities as of "
          "December 31, 2025 and June 30, 2026, which were included in accrued expenses and other.")
MARKETING = "Sales and marketing costs increased by $293 million for the six months ended June 30, 2026."


def _slash(value, quote, summary, source=None):
    return audit_claim(value, quote, source or quote, summary).fraudulent


def test_the_six_month_figure_called_a_quarter_is_caught():
    assert _slash("$274 million", SBC, "Tesla recorded $274 million of stock-based compensation in Q2 2026.")
    assert not _slash("$138 million", SBC, "Tesla recorded $138 million of stock-based compensation in Q2 2026.")
    assert not _slash("$274 million", SBC, "Tesla recorded $274 million of stock-based compensation in the six months to June.")


def test_the_wrong_quarter_is_caught():
    assert _slash("$779 million", GAMING, "Gaming net revenue for Q3 2026 was $779 million.")
    assert not _slash("$779 million", GAMING, "Gaming net revenue for Q2 2026 was $779 million.")


def test_a_balance_given_the_other_date_is_caught():
    assert _slash("$455 million", BORROW, "Borrowings of $455 million as of June 30, 2026.")
    assert not _slash("$455 million", BORROW, "Borrowings were $455 million as of December 31, 2025.")
    assert not _slash("$325 million", BORROW, "Borrowings were $325 million as of June 30, 2026.")


def test_a_summary_may_not_add_figures():
    assert _slash("$138 million", SBC, "Stock-based compensation was $138 million, up from $54 million a year earlier.")


def test_a_summary_may_not_reverse_the_quote():
    assert _slash("$779 million", GAMING, "Gaming net revenue rose to $779 million.")
    assert not _slash("$779 million", GAMING, "Gaming net revenue fell to $779 million.")


def test_a_fragment_is_not_a_quote():
    source = "Overall, costs rose. " + MARKETING
    assert _slash("$293 million", "increased by $293 million for the six months ended June 30, 2026.", "", source)
    assert not _slash("$293 million", MARKETING, "", source)


def test_arithmetic_on_the_sentence_is_allowed_and_nothing_else():
    fx = ("Interest and other income (expense) increased in the three months ended June 30, 2026 primarily due "
          "to foreign exchange losses of $17 million, net of the impacts of derivatives and hedging, compared to "
          "losses of $36 million for the corresponding period in 2025.")
    assert not _slash("$17 million", fx, "Foreign exchange losses fell by $19 million to $17 million in the quarter.")
    assert _slash("$17 million", fx, "Foreign exchange losses fell by $21 million to $17 million in the quarter.")
