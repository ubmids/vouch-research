"""How the trading agent decides: by the fixed rules in policy.py (the
default), or by a language model behind any OpenAI-compatible endpoint.

    VOUCH_DECIDER=rules             the default: policy.thesis, re-runnable by anyone
    VOUCH_DECIDER=model             ask a model, fall back to the rules on any failure
    VOUCH_DECIDER_URL=http://host/v1   an OpenAI-compatible base URL (POST {url}/chat/completions)
    VOUCH_DECIDER_MODEL=<name>      the model to ask
    VOUCH_DECIDER_KEY=<key>         optional bearer key; never written to the record
    VOUCH_DECIDER_TIMEOUT=60        seconds

Either way the desk is the gate: a model can choose a side, but it cannot cite
a claim that failed the check, because AgentDesk reverts the trade.

A model cannot be re-run to the same answer, so for a model decision the
reasoning record keeps the exact messages sent and the exact text returned.
The record's hash goes on-chain with the trade, so neither can be changed
afterwards, and anyone can check that (a) the messages are built from exactly
the claims the trade cites and (b) the returned text gives exactly the side,
size and per-claim readings recorded. `replay` does both. What nobody can check
is that the model would say the same thing again; the record says so.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from . import policy

MODEL_POLICY = "vouch-desk-model/1"
MODEL_RULE = ("a language model reads every claim and returns a reading per claim (bullish, bearish, neutral) "
              "and a side; size = per-claim notional x claims it read as bullish or bearish; the messages and "
              "the model's reply are recorded and hashed with the trade")
READING = {"bullish": 1, "bearish": -1, "neutral": 0}
SYSTEM = """You are a trading agent's analyst. You get research claims about one stock. Every figure in them
quotes the company's own SEC filing. Decide whether, taken together, they support a long position, a
short position, or no trade.

Reply with JSON only, exactly this shape:
{"claims": [{"id": <claim id>, "reading": "bullish" | "bearish" | "neutral", "why": "<one short sentence>"}],
 "side": "long" | "short" | "none", "why": "<one short sentence>"}
List every claim id you were given, once each."""


def config(env=os.environ) -> dict:
    kind = env.get("VOUCH_DECIDER", "rules").strip().lower() or "rules"
    if kind not in ("rules", "model"):
        raise ValueError(f"VOUCH_DECIDER must be 'rules' or 'model', not {kind!r}")
    return {"kind": kind, "url": env.get("VOUCH_DECIDER_URL", "").rstrip("/"),
            "model": env.get("VOUCH_DECIDER_MODEL", ""), "key": env.get("VOUCH_DECIDER_KEY", ""),
            "timeout": float(env.get("VOUCH_DECIDER_TIMEOUT", "60"))}


def messages(ticker: str, claims: list[dict]) -> list[dict]:
    """The exact messages the model gets: rebuilt from the claims by `replay`."""
    rows = [{"id": c["id"], "analyst": c["analyst"], "metric": c.get("metric", ""), "value": c["value"],
             "summary": c.get("summary", ""), "filing_sentence": c["quote"]}
            for c in sorted(claims, key=lambda c: c["id"])]
    user = f"Stock: {ticker}\nClaims:\n" + json.dumps(rows, ensure_ascii=False, indent=1)
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _parse(text: str, ids: list[int]) -> dict:
    """The model's reply as a decision, or ValueError if it is not one."""
    body = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text)
    out = json.loads(body)
    side = out.get("side")
    if side not in ("long", "short", "none"):
        raise ValueError(f"side {side!r} is not long, short or none")
    readings = {}
    for r in out.get("claims", []):
        cid, reading = r.get("id"), r.get("reading")
        if cid not in ids or cid in readings or reading not in READING:
            raise ValueError(f"bad claim reading {r!r}")
        readings[cid] = (READING[reading], str(r.get("why", ""))[:300])
    if sorted(readings) != sorted(ids):
        raise ValueError("the reply does not read every claim exactly once")
    return {"side": None if side == "none" else side, "readings": readings, "why": str(out.get("why", ""))[:500]}


def _decision(ticker: str, claims: list[dict], per_claim: int, d: dict) -> dict:
    evidence = [{"claim": c["id"], "hash": c["hash"], "analyst": c["analyst"], "value": c["value"],
                 "signal": d["readings"][c["id"]][0], "why": d["readings"][c["id"]][1]}
                for c in sorted(claims, key=lambda c: c["id"])]
    carrying = sum(1 for e in evidence if e["signal"])
    side = d["side"] if carrying else None
    return {"ticker": ticker, "side": side, "net": sum(e["signal"] for e in evidence), "per_claim": per_claim,
            "notional": per_claim * carrying if side else 0, "evidence": evidence}


def ask(cfg: dict, msgs: list[dict]) -> str:
    """POST to an OpenAI-compatible chat endpoint; the reply's text. Asks for a
    JSON object; an endpoint that refuses that option (Anthropic's compatible
    endpoint accepts only json_schema) is asked again without it: the prompt
    already says to reply with JSON only, and the parser holds the reply to it."""
    headers = {"Content-Type": "application/json"}
    if cfg["key"]:
        headers["Authorization"] = f"Bearer {cfg['key']}"

    def post(extra: dict) -> str:
        body = json.dumps({"model": cfg["model"], "messages": msgs, "temperature": 0, "seed": 7, **extra}).encode()
        req = urllib.request.Request(f"{cfg['url']}/chat/completions", data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=cfg["timeout"]) as r:
            return json.load(r)["choices"][0]["message"]["content"]
    try:
        return post({"response_format": {"type": "json_object"}})
    except urllib.error.HTTPError as e:
        if e.code != 400 or b"response_format" not in e.read():
            raise
        return post({})


def thesis(ticker: str, claims: list[dict], per_claim: int, cfg: dict | None = None) -> dict:
    """The agent's decision on these claims. Same shape as policy.thesis; a
    model decision (or a fallback from one) also carries `decider`."""
    cfg = cfg or config()
    if cfg["kind"] == "rules" or not claims:
        return policy.thesis(ticker, claims, per_claim)
    who = {"model": cfg["model"], "endpoint": urlparse(cfg["url"]).netloc or cfg["url"]}
    if not cfg["url"] or not cfg["model"]:
        why = "VOUCH_DECIDER_URL and VOUCH_DECIDER_MODEL must both be set"
    else:
        msgs = messages(ticker, claims)
        try:
            text = ask(cfg, msgs)
            t = _decision(ticker, claims, per_claim, _parse(text, [c["id"] for c in claims]))
            t["decider"] = {"kind": "model", **who, "messages": msgs, "output": text,
                            "messages_sha256": _sha(json.dumps(msgs, ensure_ascii=False)), "output_sha256": _sha(text)}
            return t
        except Exception as e:  # any failure: the rules decide, and the record says why
            why = f"{type(e).__name__}: {str(e)[:200]}"
    t = policy.thesis(ticker, claims, per_claim)
    t["decider"] = {"kind": "rules", "fallback_from": who, "fallback_reason": why}
    return t


def record(t: dict, price: dict | None, dropped: list[dict]) -> dict:
    """The reasoning record. A rules decision with no model configured is
    byte-for-byte policy.record, so earlier rounds keep their hashes."""
    rec = policy.record(t, price, dropped)
    d = t.get("decider")
    if d:
        rec["decider"] = d
        if d["kind"] == "model":
            rec["policy"], rec["rule"] = MODEL_POLICY, MODEL_RULE
    return rec


def replay(rec: dict, claims: dict[int, dict]) -> list[tuple[str, bool]]:
    """Checks on a model decision's record, without asking the model again."""
    d = rec["decider"]
    cited = [claims[e["claim"]] for e in rec["evidence"]]
    msgs = messages(rec["ticker"], cited)
    out = [("the messages sent to the model are built from exactly the claims cited", msgs == d["messages"]),
           ("the recorded hashes match the recorded messages and reply",
            d["messages_sha256"] == _sha(json.dumps(d["messages"], ensure_ascii=False))
            and d["output_sha256"] == _sha(d["output"]))]
    try:
        again = _decision(rec["ticker"], cited, rec["per_claim"], _parse(d["output"], [c["id"] for c in cited]))
        same = (again["side"], again["notional"], [e["signal"] for e in again["evidence"]]) == \
               (rec["side"], rec["notional"], [e["signal"] for e in rec["evidence"]])
    except Exception:
        same = False
    out.append(("the model's recorded reply gives exactly this side, size and reading per claim", same))
    return out
