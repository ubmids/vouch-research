"""Deterministic claim verifier — the non-LLM trust gate of Vouch.

A worker agent attests a claim about a real-world-asset document and MUST
back it with a verbatim quote from the source. This module checks that quote
character-by-character (after normalization) against the source text. No
model calls, no randomness — fully reproducible. A fabricated or altered
quote fails here, which is what lets the challenger slash a lying worker.

Carried over from Vouch on Casper (itself ported from the GreenLight
clinical-criteria citation verifier), with one rule added for SEC filings: a
near-match may not differ in any figure. Ported from GreenLight; normalization
handles real PDF-extraction artifacts (line-break hyphenation, smart quotes,
collapsed whitespace) so authentic quotes never false-fail.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

FUZZY_FLOOR = 0.95

# In a financial filing a quote that is 97% right can be 100% wrong: change one
# digit and SequenceMatcher barely notices. So a near-match is only accepted if
# every figure in the quote, and its scale, appears exactly in the matched span.
_FIGURE = re.compile(r"\d[\d,]*(?:\.\d+)?%?|\b(?:thousand|million|billion|trillion)\b")


def figures(text: str) -> list[str]:
    return [f.replace(",", "") for f in _FIGURE.findall(text)]


def _figures_hold(quote: str, span: str) -> bool:
    have = figures(span)
    for f in figures(quote):
        if f not in have:
            return False
        have.remove(f)
    return True


def normalize(text: str) -> str:
    t = text.replace("‘", "'").replace("’", "'")
    t = t.replace("“", '"').replace("”", '"')
    t = t.replace("–", "-").replace("—", "-")
    t = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", t)  # de-hyphenate line breaks
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


@dataclass
class QuoteCheck:
    verified: bool
    method: str  # "exact" | "fuzzy" | "none"
    score: float


def verify_quote(quote: str, source_text: str) -> QuoteCheck:
    """Is `quote` genuinely present in `source_text`?"""
    q = normalize(quote)
    src = normalize(source_text)
    if not q:
        return QuoteCheck(False, "none", 0.0)

    if q in src:
        return QuoteCheck(True, "exact", 1.0)

    words = q.split()
    if len(words) < 3:
        return QuoteCheck(False, "none", 0.0)  # too short to fuzzy-trust
    anchor = min(words, key=lambda w: src.count(w) if src.count(w) > 0 else 10**6)
    if src.count(anchor) == 0:
        return QuoteCheck(False, "none", 0.0)
    # Line the quote up on each place its rarest word occurs, then compare a
    # span of about the quote's own length. (An unaligned window twice the
    # quote's size caps the ratio near 0.7, so near-matches could never pass.)
    offset = q.find(anchor)
    best, best_span = 0.0, ""
    start = 0
    while True:
        i = src.find(anchor, start)
        if i == -1:
            break
        base = max(0, i - offset)
        for slack in (0, -len(q) // 20, len(q) // 20):
            span = src[base : base + len(q) + slack]
            r = SequenceMatcher(None, q, span).ratio()
            if r > best:
                best, best_span = r, span
        start = i + 1
    if best >= FUZZY_FLOOR:
        if not _figures_hold(q, best_span):
            return QuoteCheck(False, "figures-differ", round(best, 4))
        return QuoteCheck(True, "fuzzy", round(best, 4))
    return QuoteCheck(False, "none", round(best, 4))


@dataclass
class Verdict:
    """Result of auditing a worker's attestation."""
    fraudulent: bool
    reason: str
    quote_check: QuoteCheck


def audit_attestation(claimed_value: str, quote: str, source_text: str) -> Verdict:
    """Challenger logic: an attestation is fraudulent if its supporting quote
    is not genuinely in the source, OR if the claimed value isn't grounded in
    that quote. Deterministic — the slash decision must be reproducible."""
    qc = verify_quote(quote, source_text)
    if not qc.verified:
        return Verdict(True, "supporting quote not found in source document", qc)
    if normalize(claimed_value) not in normalize(quote):
        return Verdict(True, "claimed value not grounded in the cited quote", qc)
    return Verdict(False, "quote verified and value grounded", qc)
