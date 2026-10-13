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
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

FUZZY_FLOOR = 0.95

# In a financial filing a quote that is 97% right can be 100% wrong: change one
# digit and SequenceMatcher barely notices. So a near-match is only accepted if
# every figure in the quote, and its scale, appears exactly in the matched span.
# Digits are ASCII on purpose ([0-9], not \d): Python's \d also matches other
# scripts' digits, JavaScript's does not, and the CRE workflow must agree.
_FIGURE = re.compile(r"[0-9][0-9,]*(?:\.[0-9]+)?%?|\b(?:thousand|million|billion|trillion)\b")


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


# ---- checking the claim as written, not only its quote ----------------------
#
# A quote can be real and the claim built on it still wrong. Our own language-
# model analyst proved it: ten quotes out of ten found word for word in the
# filings, and half of its one-line summaries still misstated the period or the
# direction ("$274 million for Q2" from a sentence where $274 million is the
# six-month figure). The summary is what a reader reads, so it is checked too,
# deterministically, against the quote it cites.

_SPAN = {"three": 3, "six": 6, "nine": 9, "twelve": 12}
_MONTH = {m: i for i, m in enumerate(
    "january february march april may june july august september october november december".split(), 1)}
_DATE = r"([A-Z][a-z]+) ([0-9]{1,2}), ([0-9]{4})"
_MULTI = re.compile(r"\b(three|six|nine|twelve) and (three|six|nine|twelve) months ended " + _DATE)
_SINGLE = re.compile(r"\b(three|six|nine|twelve) months ended " + _DATE)
_AMOUNT = re.compile(r"\$\s?\(?[0-9][0-9,]*(?:\.[0-9]+)?\)?(?:\s(?:thousand|million|billion|trillion))?|[0-9][0-9,]*(?:\.[0-9]+)?\s?%")
_SCALE = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}


def sentences(text: str) -> list[str]:
    """The filing's sentences: split per line, then at ". " or "; " before a capital."""
    out = []
    for line in text.split("\n"):
        out += [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[A-Z(])", " ".join(line.split())) if s.strip()]
    return out


def amount(text: str) -> float | None:
    """'$1.37 billion' -> 1.37e9, '43 %' -> 43.0 (percent), '$(48) million' -> 48e6."""
    m = re.match(r"\$?\s?\(?([0-9][0-9,]*(?:\.[0-9]+)?)\)?\s?(%|thousand|million|billion|trillion)?", text.strip())
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    unit = m.group(2)
    return n if unit == "%" else n * _SCALE.get(unit or "", 1)


def amounts(text: str) -> list[float]:
    return [a for a in (amount(x) for x in _AMOUNT.findall(text)) if a is not None]


def _span_of_value(quote: str, value: str):
    """(months, end month, end year) the quote gives for this value, or None."""
    v = amount(value)
    multi, single = _MULTI.search(quote), _SINGLE.findall(quote)
    if multi and "respectively" in quote and v is not None:
        spans = [_SPAN[multi.group(1)], _SPAN[multi.group(2)]]
        # The figures come after the phrase ("... ended June 30, 2026, we recorded
        # $138 million and $274 million, respectively") or before it ("... was
        # $544 million and $1.1 billion for the three and six months ended ...").
        after = amounts(quote[multi.end():]) or amounts(quote[:multi.start()])[-len(spans):]
        for i, a in enumerate(after[: len(spans)]):
            if abs(a - v) < 1e-6 * max(1, v):
                return spans[i], _MONTH.get(multi.group(3).lower()), int(multi.group(5))
        return None
    if not multi and single:
        spans = {(_SPAN[s], _MONTH.get(mo.lower()), int(y)) for s, mo, _d, y in single}
        # "... compared to the six months ended June 30, 2025" names the prior
        # period too; the claimed figure belongs to the latest one.
        latest = max(spans, key=lambda s: (s[2], s[1] or 0))
        if len({s[0] for s in spans}) == 1:
            return latest
    return None


_ASOF_TWO = re.compile(r"\bas of " + _DATE + r" and " + _DATE)


def _date_of_value(quote: str, value: str):
    """(month, year) a balance belongs to in "as of A and B ... $X and $Y, respectively"."""
    m = _ASOF_TWO.search(quote)
    v = amount(value)
    if not m or v is None:
        return None
    dates = [(_MONTH.get(m.group(1).lower()), int(m.group(3))), (_MONTH.get(m.group(4).lower()), int(m.group(6)))]
    # Two figures and two dates pair up in order, with or without "respectively"
    # ("$455 million and $325 million ... as of December 31, 2025 and June 30, 2026").
    everything = amounts(quote)
    if len(everything) != 2 and "respectively" not in quote:
        return None
    vals = (amounts(quote[m.end():]) if len(everything) != 2 else everything)[:2]
    if len(vals) == 2 and vals[0] != vals[1]:
        for i, a in enumerate(vals):
            if abs(a - v) < 1e-6 * max(1, v):
                return dates[i]
    return None


def _claimed_date(text: str):
    m = re.search(r"\bas of ([A-Z][a-z]+)(?: [0-9]{1,2},)? ([0-9]{4})", text)
    return (_MONTH.get(m.group(1).lower()), int(m.group(2))) if m and m.group(1).lower() in _MONTH else None


def _claimed_period(text: str):
    """(months, quarter, year) a summary asserts, or None when it names none or several."""
    t = text.lower()
    if re.search(r"\b(three|six|nine|twelve) and (three|six|nine|twelve)\b", t):
        return None
    q = re.search(r"\bq([1-4])(?:\s*(?:fy)?\s*([0-9]{4}))?\b", t)
    if q:
        return 3, int(q.group(1)), int(q.group(2)) if q.group(2) else None
    m = re.search(r"\b(three|six|nine|twelve)[- ]months?\b", t)
    if m:
        return _SPAN[m.group(1)], None, None
    if re.search(r"\b(first half|half[- ]year|h1)\b", t):
        return 6, None, None
    if re.search(r"\b(quarter|quarterly)\b", t):
        return 3, None, None
    return None


def _label(p) -> str:
    months, q, year = p
    if q:
        return f"Q{q}{' ' + str(year) if year else ''}"
    return {3: "a quarter", 6: "six months", 9: "nine months", 12: "a year"}[months]


_UP, _DOWN = r"\b(increase[sd]?|rose|rise[sn]?|grew|grow(?:th|s)?|higher)\b", r"\b(decrease[sd]?|declined?|fell|fall(?:s|en)?|lower|drop(?:ped|s)?)\b"


def _direction_near(text: str, value: str, reach: int = 80):
    """'up', 'down' or None: the direction word closest to the figure, within reach."""
    v = amount(value)
    spots = [m.start() for m in _AMOUNT.finditer(text) if v is not None and amount(m.group(0)) is not None
             and abs(amount(m.group(0)) - v) < 1e-6 * max(1, v)]
    best = None
    for pos in spots:
        for word, pattern in (("up", _UP), ("down", _DOWN)):
            for m in re.finditer(pattern, text, re.I):
                d = abs(m.start() - pos)
                if d <= reach and (best is None or d < best[0]):
                    best = (d, word)
    return best[1] if best else None


def _foreign_digits(text: str) -> bool:
    """Digits other than 0-9 (Arabic-Indic, full-width, ...): figures the check cannot read."""
    return any(ch not in "0123456789" and unicodedata.category(ch) == "Nd" for ch in text)


def audit_claim(value: str, quote: str, source_text: str, summary: str = "", metric: str = "") -> Verdict:
    """The whole claim: its quote, its value, and what its summary says about them."""
    if any(_foreign_digits(t) for t in (value, quote, summary, metric)):
        return Verdict(True, "the claim writes a figure in digits other than 0-9", QuoteCheck(False, "none", 0.0))
    v = audit_attestation(value, quote, source_text)
    if v.fraudulent:
        return v
    q = normalize(quote)
    whole = {normalize(s) for s in sentences(source_text)}
    if q not in whole and not (v.quote_check.method == "fuzzy" and
                               any(SequenceMatcher(None, q, s).ratio() >= FUZZY_FLOOR for s in whole if abs(len(s) - len(q)) < 30)):
        return Verdict(True, "the quote is a fragment, not a whole sentence of the filing", v.quote_check)
    said = summary or ""
    if said:
        quoted = amounts(quote)
        # A figure is grounded if the sentence states it, or if it is the sum or
        # difference of two figures the sentence states ("losses of $17 million,
        # compared to $36 million" grounds "down $19 million"). Arithmetic anyone
        # can redo; a made-up number almost never lands on it.
        derived = {abs(x - y) for i, x in enumerate(quoted) for y in quoted[i + 1:]} | \
                  {x + y for i, x in enumerate(quoted) for y in quoted[i + 1:]}
        for a in amounts(said):
            if not any(abs(a - b) < 1e-6 * max(1, b) for b in (*quoted, *derived)):
                return Verdict(True, "the summary states a figure its quote does not contain", v.quote_check)
        # Gain against loss is checked across the sentence. Up against down only
        # near the claimed figure: a sentence can say income increased because
        # losses fell, and both are true.
        if re.search(r"\bgains?\b", said, re.I) and re.search(r"\bloss(es)?\b", quote, re.I) and not re.search(r"\bgains?\b", quote, re.I) \
                or re.search(r"\bloss(es)?\b", said, re.I) and re.search(r"\bgains?\b", quote, re.I) and not re.search(r"\bloss(es)?\b", quote, re.I):
            return Verdict(True, "the summary reverses what the quote says", v.quote_check)
        near_s, near_q = _direction_near(said, value), _direction_near(quote, value)
        if near_s and near_q and near_s != near_q:
            return Verdict(True, "the summary reverses what the quote says", v.quote_check)
    # The period a claim asserts is in its summary, or in a metric the analyst
    # wrote itself. A metric copied out of the quote asserts nothing new.
    own_metric = metric and normalize(metric) not in q
    claimed = _claimed_period(said) or (_claimed_period(metric) if own_metric else None)
    owns = _date_of_value(quote, value)
    says = _claimed_date(said) or (_claimed_date(metric) if own_metric else None)
    if owns and says and owns != says:
        name = lambda d: f"{[m for m, i in _MONTH.items() if i == d[0]][0].title()} {d[1]}"
        return Verdict(True, f"wrong date: the filing gives {value} as of {name(owns)}, the claim says {name(says)}", v.quote_check)
    actual = _span_of_value(quote, value)
    if claimed and actual:
        months, end_month, end_year = actual
        if claimed[0] != months:
            return Verdict(True, f"wrong period: the filing gives {value} for {_label((months, None, None))}, "
                                 f"the claim says {_label(claimed)}", v.quote_check)
        if claimed[1] and end_month and claimed[1] != (end_month - 1) // 3 + 1:
            month = [m for m, i in _MONTH.items() if i == end_month][0].title()
            return Verdict(True, f"wrong quarter: the period ended in {month}, the claim says {_label(claimed)}", v.quote_check)
        if claimed[2] and end_year and claimed[2] != end_year:
            return Verdict(True, f"wrong year: the period ended in {end_year}, the claim says {claimed[2]}", v.quote_check)
    return v
