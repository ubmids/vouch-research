"""How the agent reads a market post: by the word-list rules in kol.py (the
default), or by a language model behind any OpenAI-compatible endpoint.

    VOUCH_READER=rules              the default: kol.read, re-runnable by anyone
    VOUCH_READER=model              ask a model, fall back to the rules on any failure
    VOUCH_READER_URL=http://host/v1 an OpenAI-compatible base URL (POST {url}/chat/completions)
    VOUCH_READER_MODEL=<name>       the model to ask
    VOUCH_READER_KEY=<key>          optional bearer key; never written to the record
    VOUCH_READER_TIMEOUT=60         seconds

A reading says which stock, which dollar figure (as the post writes it), which
period, the voice's sentiment, conviction and urgency, and whether the post
makes a claim about a figure that company's Q2 2026 10-Q reports. Only a
checkable reading becomes a staked claim.

A model is not re-run to check a reading. The record keeps the exact messages
sent, the model's id, its exact reply, and the sha256 of each; `replay`
rebuilds the messages from the post's stored text, checks the hashes, and
parses the recorded reply again to see it gives exactly the recorded reading.
Turning the reply into a reading is fixed code (parse below), so that step is
re-runnable even though the model is not. What nobody can check is that the
model would answer the same again; the record says which model answered.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from urllib.parse import urlparse

from . import decide, kol

TICKERS = ("TSLA", "AMZN", "NFLX", "PLTR", "AMD")
LEVELS = {"sentiment": ("bullish", "bearish", "neutral"), "conviction": ("high", "medium", "low"),
          "urgency": ("urgent", "normal")}
DEFAULT = {"sentiment": "neutral", "conviction": "medium", "urgency": "normal"}   # when the reply leaves one null
MODEL_RULE = ("a language model reads the post and returns ticker, figure, period, sentiment, conviction, urgency "
              "and whether the figure is checkable against the Q2 2026 10-Q; fixed code turns the reply into the "
              "reading (agent/vouchrh/reader.py parse); the messages and reply are recorded and hashed")
SYSTEM = """You read one public social-media post about a stock, for a trading agent. The agent acts only on
dollar figures it can check against the company's quarterly report to the SEC (its 10-Q) for the quarter
ended June 2026 (Q2 2026). The companies are Tesla (TSLA), Amazon (AMZN), Netflix (NFLX), Palantir (PLTR)
and AMD (AMD).

Reply with JSON only, exactly this shape:
{"ticker": "TSLA" | "AMZN" | "NFLX" | "PLTR" | "AMD" | null,
 "figure": "<the dollar amount exactly as the post writes it, e.g. \\"$1.54B\\", or null>",
 "period": "<the period exactly as the post writes it, e.g. \\"Q2 2026\\", or null>",
 "sentiment": "bullish" | "bearish" | "neutral",
 "conviction": "high" | "medium" | "low",
 "urgency": "urgent" | "normal",
 "checkable": true | false,
 "why": "<one short sentence>"}

Always give sentiment, conviction and urgency, even when nothing is checkable.
checkable is true only if the post states a dollar amount the company itself reported (revenue, income,
profit, cash flow, costs, expenses, capital spending and the like) for a period a Q2 2026 10-Q covers (the
quarter or the six months ended June 2026), so the figure can be looked up in that filing. It is false for
share prices, price targets, market value, forecasts, guidance, per-share amounts, pay, rumours and
figures about other companies. When checkable is true, figure is that dollar amount."""

# A post with no amount in millions or billions cannot carry a figure the agent
# would stake on (value_of below), so the model is not asked about it (fewer
# calls); the rules read it instead, and the record says so.
_FIGURE_HINT = re.compile(r"(?i)\d\s?(b|bn|billion|m|mn|million)\b")
# A dollar figure as a post may write it, with or without the $.
_FIGURE = re.compile(r"(?i)^\s*\$?\s?([0-9][0-9,]*(?:\.[0-9]+)?)\s?(b|bn|billion|m|mn|million)\s*$")


def config(env=os.environ) -> dict:
    kind = env.get("VOUCH_READER", "rules").strip().lower() or "rules"
    if kind not in ("rules", "model"):
        raise ValueError(f"VOUCH_READER must be 'rules' or 'model', not {kind!r}")
    return {"kind": kind, "url": env.get("VOUCH_READER_URL", "").rstrip("/"),
            "model": env.get("VOUCH_READER_MODEL", ""), "key": env.get("VOUCH_READER_KEY", ""),
            "timeout": float(env.get("VOUCH_READER_TIMEOUT", "60"))}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def messages(text: str) -> list[dict]:
    """The exact messages the model gets for a post: rebuilt from the post's text by `replay`."""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Post:\n" + text}]


def value_of(figure: str | None) -> str | None:
    """'$1.54B' or '1.54 billion' as the filing writes it: '$1.54 billion'. None if it is not a scaled dollar amount."""
    m = _FIGURE.match(figure or "")
    return kol.money(m.group(1), m.group(2)) if m else None


def _in_post(figure: str, text: str) -> bool:
    """The figure's digits appear in the post as written (a reply cannot invent one)."""
    digits = re.search(r"[0-9][0-9,]*(?:\.[0-9]+)?", figure)
    return bool(digits) and digits.group(0) in text


def parse(output: str, text: str) -> dict:
    """The model's reply as a reading, or ValueError if it is not one. Fixed code: replay runs it again."""
    body = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", output)
    out = json.loads(body)
    if not isinstance(out, dict):
        raise ValueError("the reply is not a JSON object")
    ticker = out.get("ticker")
    if ticker is not None and ticker not in TICKERS:
        ticker = None
    r = {"ticker": ticker}
    for k, allowed in LEVELS.items():
        if out.get(k) is None:
            out[k] = DEFAULT[k]
        if out.get(k) not in allowed:
            raise ValueError(f"{k} {out.get(k)!r} is not one of {allowed}")
        r[k] = out[k]
    figure = out.get("figure") if isinstance(out.get("figure"), str) else None
    period = out.get("period") if isinstance(out.get("period"), str) else None
    value = value_of(figure)
    checkable = out.get("checkable") is True
    why = str(out.get("why", ""))[:300]
    not_checkable = None
    if checkable and not ticker:
        not_checkable = "no stock token named"
    elif checkable and not value:
        not_checkable = f"the figure {figure!r} is not a dollar amount in millions or billions"
    elif checkable and not _in_post(figure, text):
        not_checkable = f"the figure {figure!r} is not in the post"
    r.update(figure=figure, value=value, period=period if period and period in text else None,
             checkable=checkable and not not_checkable, why=why)
    if not_checkable:
        r["not_checkable"] = not_checkable
    return r


def by_rules(text: str) -> dict:
    """The word-list reading (kol.read), with the fields a model reading has."""
    r = kol.read(text)
    m = kol._MONEY.search(text)
    period = re.search(r"(?i)\b(Q[1-4](?:\s?(?:20)?\d{2})?|(?:first|second) (?:quarter|half)(?: of)? 20\d{2})\b", text)
    r.update(figure=m.group(0) if m else None, period=period.group(0) if period else None,
             checkable=bool(r["ticker"] in TICKERS and r["value"]))
    return r


def read(text: str, cfg: dict | None = None, ask=decide.ask) -> dict:
    """The agent's reading of one post. Same fields whichever way it was read;
    `reader` says how, and for a model holds the exact messages and reply."""
    cfg = cfg or config()
    if cfg["kind"] == "rules":
        return {**by_rules(text), "reader": {"kind": "rules"}}
    who = {"model": cfg["model"], "endpoint": urlparse(cfg["url"]).netloc or cfg["url"]}
    if not cfg["url"] or not cfg["model"]:
        why = "VOUCH_READER_URL and VOUCH_READER_MODEL must both be set"
    elif not _FIGURE_HINT.search(text):
        return {**by_rules(text), "reader": {"kind": "rules", "model_not_asked": "no dollar figure in the post"}}
    else:
        msgs = messages(text)
        try:
            output = ask(cfg, msgs)
            r = parse(output, text)
            r["rule"] = MODEL_RULE
            r["reader"] = {"kind": "model", **who, "messages": msgs, "output": output,
                           "messages_sha256": sha(canonical(msgs)), "output_sha256": sha(output)}
            return r
        except Exception as e:  # any failure: the rules read it, and the record says why
            why = f"{type(e).__name__}: {str(e)[:200]}"
    return {**by_rules(text), "reader": {"kind": "rules", "fallback_from": who, "fallback_reason": why}}


def fingerprint(reading: dict) -> str:
    """sha256 of the reading itself (every field but the reader's messages and reply, which have their own)."""
    return sha(canonical({k: v for k, v in reading.items() if k != "reader"}))


def replay(reading: dict, text: str) -> list[tuple[str, bool]]:
    """Checks on a reading, without asking the model again."""
    rd = reading.get("reader", {})
    fields = {k: v for k, v in reading.items() if k != "reader"}
    if rd.get("kind") != "model":
        again = by_rules(text)
        return [("re-reading the post by the word-list rules gives the same reading", again == fields)]
    out = [("the messages sent to the model are built from exactly this post's text", messages(text) == rd["messages"]),
           ("the recorded hashes match the recorded messages and reply",
            rd["messages_sha256"] == sha(canonical(rd["messages"])) and rd["output_sha256"] == sha(rd["output"]))]
    try:
        same = {**parse(rd["output"], text), "rule": MODEL_RULE} == fields
    except Exception:
        same = False
    out.append(("the model's recorded reply gives exactly this reading", same))
    return out
