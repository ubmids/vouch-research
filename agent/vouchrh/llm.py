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
company, and you put money behind it: if the claim is wrong, or its supporting quote is not in
the filing word for word, you lose your stake.

From the passage you are given, write exactly one claim, as JSON with these keys:
  "summary": one plain-English sentence a trader would read, at most 20 words
  "metric":  what the figure measures, at most 10 words, e.g. "Depreciation expense, Q2 2026"
  "value":   the figure exactly as the filing writes it, e.g. "$1.37 billion"
  "quote":   ONE complete sentence copied character for character from the passage, containing the value

Never round, never convert units, never combine sentences, never add words to the quote."""


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
                     {"role": "user", "content": f"Company: {company}\n\nPassage from its latest 10-Q:\n{passage}"}],
    }).encode()
    req = urllib.request.Request(f"{HOST}/api/chat", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(json.load(r)["message"]["content"])


class Model(Analyst):
    """A language-model analyst, judged like any other."""
    name = "Qwen 2.5 7B"

    def claim(self, ticker: str, accession: str, fact: Fact, others: list[Fact]) -> Claim:
        # The passage is the fact's sentence among its neighbours, so the model
        # has to find and copy the right sentence rather than being handed it.
        i = next((k for k, o in enumerate(others) if o.sentence == fact.sentence), 0)
        passage = " ".join(o.sentence for o in others[max(0, i - 1): i + 3])
        out = ask(passage, ticker)
        quote = str(out.get("quote", "")).strip()
        value = str(out.get("value", "")).strip()
        metric = str(out.get("metric", "")).strip() or fact.metric
        return Claim(ticker, accession, metric, value, quote, self.name, str(out.get("summary", "")).strip())
