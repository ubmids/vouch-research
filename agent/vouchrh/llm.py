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
        "options": {"temperature": 0, "seed": 7, "num_ctx": 4096},   # reproducible: same filing, same claim
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


# The claim that opens the demo: on 24 September Qwen 2.5 7B, given Tesla's
# depreciation sentence, wrote "Depreciation for Q3 2026 was $1.37 billion."
# for a quarter that ended in June (claim #6 on the v1 market). A round only
# has that moment if the model writes it again.
HERO_TICKER = "TSLA"
HERO_SENTENCE = ("Depreciation expense during the three and six months ended June 30, 2026 was "
                 "$1.37 billion and $2.71 billion, respectively.")
HERO_REASON = "wrong quarter: the period ended in June, the claim says Q3 2026"


def dry_run(per_ticker: int = 2, seed: int = 7, log=print) -> bool:
    """Ask the model exactly what the round will ask it about Tesla's
    depreciation sentence (same facts, same window, same options) and say
    whether it writes the published wrong-quarter claim again. Spends no gas;
    scripts/cre_round.sh runs it before deploying anything."""
    from .market import choose_facts
    from .verifier import audit_claim
    if not available():
        log(f"no {MODEL} at {HOST}: start Ollama with it (ollama pull {MODEL}), or set OLLAMA_HOST")
        return False
    (t, filing, text, found, picks), = choose_facts((HERO_TICKER,), per_ticker, seed, pool="all")
    fact = next((f for f in picks if f.sentence == HERO_SENTENCE), None)
    if fact is None:
        log("the round would not ask about the depreciation sentence (facts or seed changed)")
        return False
    c = Model(seed=seed).claim(t, filing.accession, fact, found)
    v = audit_claim(c.value, c.quote, text, c.summary, c.metric)
    log(f"model {MODEL} at {HOST} wrote: value {c.value!r}, summary {c.summary!r}")
    log(f"  the check: {'SLASH' if v.fraudulent else 'clear'} ({v.reason})")
    hero = c.value == "$1.37 billion" and c.quote == HERO_SENTENCE and v.fraudulent and v.reason == HERO_REASON
    log("  the hero claim reproduces" if hero else "  NOT the published claim: the round would have no wrong-quarter hero")
    return hero


def replayed(feed_path: str, label: str = "the published testnet round of 24 September 2026"):
    """The language model's claims from a recorded round, posted again word for
    word, for a round that runs without the model. Each one keeps its
    provenance: the round, the claim id there, and the hash the market stored
    for it then, which the same words must still produce."""
    feed = json.loads(open(feed_path).read())
    recorded: dict[str, list] = {}
    for r in feed["claims"]:
        if r.get("analyst_kind") == "model":
            recorded.setdefault(r["ticker"], []).append(r)
    if not recorded:
        raise ValueError(f"{feed_path} has no language-model claims to replay")

    class Replayed(Analyst):
        name = next(iter(recorded.values()))[0]["analyst"]
        kind = "model"

        def __init__(self, seed: int = 0):
            super().__init__(seed)
            self.asked: dict[str, int] = {}
            self.last = None

        def claim(self, ticker, accession, fact, others):
            # The recorded claims are in the order that round asked for them:
            # one per fact, per stock. choose_facts(pool="all") asks the same.
            k = self.asked.get(ticker, 0)
            self.asked[ticker] = k + 1
            r = self.last = recorded[ticker][k]
            if r["accession"] != accession:
                raise ValueError(f"recorded claim #{r['id']} cites {r['accession']}, the round cites {accession}")
            c = Claim(ticker, accession, r["metric"], r["value"], r["quote"], r["analyst"], r.get("summary", ""))
            if "0x" + c.digest().hex() != r["hash"]:
                raise ValueError(f"recorded claim #{r['id']} no longer hashes to {r['hash']}")
            return c

        def provenance(self, claim: Claim) -> dict:
            r = self.last
            return {"round": label, "claim": r["id"], "hash": r["hash"], "tx_post": r.get("tx_post"),
                    "market": feed.get("contracts", {}).get("market"), "chain_id": feed.get("chain_id")}

    return Replayed


def main(argv=None):
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="python -m vouchrh.llm")
    ap.add_argument("--dry-run", action="store_true", help="check the model writes the hero claim again; no gas")
    args = ap.parse_args(argv)
    if args.dry_run:
        sys.exit(0 if dry_run() else 1)
    ap.print_help()


if __name__ == "__main__":
    main()
