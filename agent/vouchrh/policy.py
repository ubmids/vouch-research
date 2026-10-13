"""The trading agent's policy: from research claims to a paper trade, by rules
anyone can re-run.

The agent reads every claim posted about a stock, like a reader following
several analysts at once. Each claim gives at most one signal:

  change    did the figure rise or fall? Taken from the direction words next to
            the figure in the cited sentence or the claim's own summary (which
            the check has already held to the sentence), or from the sentence's
            own comparison ("$8.63 billion ..., compared to $7.12 billion").
  polarity  is rising good or bad for the company? Revenue, income, cash from
            operations: good. Losses, expenses, debt, amortisation: bad.
            Anything else (capital spending, a commitment, a balance) has no
            polarity, so it gives no signal; the agent does not guess.

  signal = change x polarity, so +1 bullish, -1 bearish, 0 none.

Net signal above zero is a long, below zero a short, zero is no trade. Size is
a fixed paper amount per claim that carries a signal. Every input is a claim's
published words; there is no model and no randomness, so the same claims give
the same trade, and the reasoning record hashes to the same bytes.
"""
from __future__ import annotations

import json
import re

from eth_utils import keccak

from .verifier import _direction_near, amount, amounts

POLICY = "vouch-desk-policy/1"
RULE = ("signal per claim = change x polarity; long if the net signal is above zero, short if below, "
        "no trade at zero; size = per-claim notional x claims that carry a signal")

_GOOD = re.compile(r"(?i)\b(revenues?|sales|net income|operating income|gross (?:profit|margin)|profit|"
                   r"cash flows? (?:provided by|from) operat\w*|operating cash flows?|free cash flow|bookings|backlog)\b")
_BAD = re.compile(r"(?i)\b(loss(?:es)?|expenses?|costs?|debt|borrowings?|impairments?|amortization|"
                  r"depreciation|restructuring|liabilit(?:y|ies)|(?:income )?tax(?:es)?|provision)\b")
_PRIOR = re.compile(r"(?i)\b(?:compared (?:to|with)|from|versus|vs\.?)\s+(?:losses of |income of |the )?"
                    r"(\$\s?\(?[0-9][0-9,]*(?:\.[0-9]+)?\)?(?:\s(?:thousand|million|billion|trillion))?)")


_HYPOTHETICAL = re.compile(r"(?i)\b(would|could|if)\b")


def _change(c: dict) -> tuple[int, str]:
    if _HYPOTHETICAL.search(c["quote"]):
        return 0, "a hypothetical, not a result"
    for text, where in ((c.get("summary") or "", "the summary"), (c["quote"], "the filing's sentence")):
        d = _direction_near(text, c["value"]) if text else None
        if d:
            return (1 if d == "up" else -1), f"{where} says it went {d}"
    v = amount(c["value"])
    m = _PRIOR.search(c["quote"])
    if v is not None and m:
        prior = amount(m.group(1))
        before = amounts(c["quote"][: m.start()])
        # the claimed figure must be the one being compared, i.e. the latest stated before "compared to"
        if prior and before and abs(before[-1] - v) < 1e-6 * max(1, v) and prior != v:
            return (1 if v > prior else -1), f"{c['value']} against {m.group(1)} in the prior period"
    return 0, "no change stated"


_COST_OF = re.compile(r"(?i)\bcosts? of\b[^.$]{0,40}$")
_INCREASE_IN = re.compile(r"(?i)^\s*(?:increase|decrease|rise|decline|reduction)s? in (?:the |our )?")


def _polarity(c: dict) -> tuple[int, str]:
    # What the figure measures. "a $161 million increase in the provision for
    # income taxes" names it after the figure; otherwise it is the revenue-like
    # or cost-like words closest before it. "Cost of ... revenue" is a cost.
    q, v = c["quote"], c["value"]
    at = q.find(v.split()[0]) if v else -1
    if at < 0:
        at = len(q)

    def kind(m, pol):
        if pol == 1 and _COST_OF.search(q[: m.start()]):
            return -1, "cost of " + m.group(1).lower()
        return pol, m.group(1).lower()

    after = _INCREASE_IN.match(q[at + len(v):]) if v else None
    if after:
        rest = q[at + len(v) + after.end():]
        hits = [(m.start(), pol, m) for pattern, pol in ((_GOOD, 1), (_BAD, -1)) for m in pattern.finditer(rest)]
        if hits:
            _, pol, m = min(hits, key=lambda h: h[0])
            return pol, m.group(1).lower()
    best = None
    for pattern, pol in ((_GOOD, 1), (_BAD, -1)):
        for m in pattern.finditer(q[:at]):
            d = at - m.end()
            if best is None or d < best[0]:
                best = (d, *kind(m, pol))
    if best is None:
        metric = c.get("metric") or ""
        good, bad = _GOOD.search(metric), _BAD.search(metric)
        if good and not bad:
            return 1, good.group(1).lower()
        if bad and not good:
            return -1, bad.group(1).lower()
        return 0, "neither revenue-like nor cost-like"
    return best[1], best[2]


def signal(c: dict) -> dict:
    ch, why_ch = _change(c)
    pol, why_pol = _polarity(c)
    s = ch * pol
    if s:
        tone = "bullish" if s > 0 else "bearish"
        why = f"{why_pol} {'up' if ch > 0 else 'down'} ({why_ch}): {tone}"
    elif pol == 0:
        why = f"no signal: {why_pol}"
    else:
        why = f"no signal: {why_pol}, {why_ch}"
    return {"signal": s, "why": why}


def thesis(ticker: str, claims: list[dict], per_claim: int) -> dict:
    """What the agent would do on these claims, and why, in order."""
    evidence = []
    for c in sorted(claims, key=lambda c: c["id"]):
        s = signal(c)
        evidence.append({"claim": c["id"], "hash": c["hash"], "analyst": c["analyst"], "value": c["value"],
                         **s})
    net = sum(e["signal"] for e in evidence)
    carrying = sum(1 for e in evidence if e["signal"])
    side = "long" if net > 0 else "short" if net < 0 else None
    return {"ticker": ticker, "side": side, "net": net, "per_claim": per_claim,
            "notional": per_claim * carrying if side else 0, "evidence": evidence}


def record(t: dict, price: dict | None, dropped: list[dict]) -> dict:
    """The reasoning record the trade commits to. Its keccak256 goes on-chain."""
    return {"policy": POLICY, "rule": RULE, "ticker": t["ticker"], "side": t["side"], "net_signal": t["net"],
            "per_claim": t["per_claim"], "notional": t["notional"], "evidence": t["evidence"], "dropped": dropped,
            "price": price}


def canonical(rec: dict) -> bytes:
    return json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(rec: dict) -> bytes:
    return keccak(canonical(rec))
