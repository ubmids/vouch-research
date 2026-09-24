"""An analyst that is a language model.

It reads a passage of a filing and writes one research claim: a plain-English
line, the figure, and the sentence that supports it, which it is told to copy
word for word. It gets no special treatment. Whatever it returns is hashed,
staked and checked by the same deterministic verifier as everybody else, so a
model that paraphrases the filing, or remembers a number instead of reading it,
loses its stake like any other analyst. That is the point of the product.

It runs on an open model through Ollama on the analyst's own machine, so no
hosted API sees the research before it is staked, and nothing needs a key:

    ollama pull qwen2.5:7b-instruct
    VOUCH_LLM_MODEL=qwen2.5:7b-instruct   (the default)
"""
from __future__ import annotations

import json
import os
import urllib.request

from .analysts import Analyst, Fact
from .claims import Claim

HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.environ.get("VOUCH_LLM_MODEL", "qwen2.5:7b-instruct")

SYSTEM = """You are an equity research analyst. You publish one factual claim at a time about a
company, and you put money behind it. The claim is checked mechanically against the filing: if
its figure, its period or its direction is not exactly what the cited sentence says, you lose
your stake.

You are given numbered sentences from the company's latest 10-Q. Pick ONE sentence that states a
dollar figure, and return JSON with these keys:
  "sentence": the number of the sentence you cite
  "value":    one figure from that sentence, exactly as written, e.g. "$1.37 billion"
  "metric":   what the figure measures and for which period, at most 12 words
  "summary":  one plain sentence for a trader, at most 22 words

Rules the check enforces:
- The period must be the sentence's own period for that figure. Write it as the filing does,
  e.g. "three months ended June 30, 2026" or "six months ended June 30, 2026". Do not convert
  to quarter names. When a sentence gives two periods and says "respectively", the first figure
  belongs to the first period and the second to the second.
- Every figure in the summary must appear in the sentence, written the same way.
- Keep the direction: increase/decrease and gain/loss exactly as the sentence says.
- If a figure is a balance "as of" a date, say "as of" that date, not a period."""


def available() -> bool:
    try:
        with urllib.request.urlopen(f"{HOST}/api/tags", timeout=3) as r:
            return any(m.get("name", "").startswith(MODEL.split(":")[0]) for m in json.load(r).get("models", []))
    except Exception:
        return False


def ask(passage: str, company: str) -> dict:
    body = json.dumps({
        "model": MODEL, "stream": False, "format": "json",
        "options": {"temperature": 0.2, "num_ctx": 4096},
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": f"Company: {company}\n\nSentences from its latest 10-Q:\n{passage}"}],
    }).encode()
    req = urllib.request.Request(f"{HOST}/api/chat", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(json.load(r)["message"]["content"])


class Model(Analyst):
    """A language-model analyst, judged like any other."""
    name = "Qwen 2.5 7B"
    kind = "model"

    def claim(self, ticker: str, accession: str, fact: Fact, others: list[Fact]) -> Claim:
        # The analyst cites by pointer: it picks a sentence by number and that
        # sentence, verbatim, is the quote. Everything it writes itself (the
        # figure, the metric, the summary) is what the verifier then judges.
        i = next((k for k, o in enumerate(others) if o.sentence == fact.sentence), 0)
        window = [o.sentence for o in others[max(0, i - 1): i + 3]]
        numbered = "\n".join(f"{n}. {s}" for n, s in enumerate(window, 1))
        out = ask(numbered, ticker)
        try:
            quote = window[int(out.get("sentence", 1)) - 1]
        except (ValueError, IndexError, TypeError):
            quote = ""
        value = str(out.get("value", "")).strip()
        metric = str(out.get("metric", "")).strip() or fact.metric
        return Claim(ticker, accession, metric, value, quote, self.name, str(out.get("summary", "")).strip())
