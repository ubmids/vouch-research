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
