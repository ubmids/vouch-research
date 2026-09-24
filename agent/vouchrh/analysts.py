"""Analysts: the agents that read filings and publish bonded claims.

Four behaviours, because the verifier has to be seen catching each way a
research claim goes wrong, not only the crude one:

  Diligent     quotes the filing and asserts what the quote says.
  Misreader    quotes the filing correctly, then asserts a different figure,
               the kind of mistake a summariser makes by reading the wrong row.
  Embellisher  nudges one figure and doctors the quote to match, which reads
               99% like the filing and is exactly what fuzzy matching lets by.
  Fabricator   writes a plausible sentence the filing never contained.

These are scripted, so a run is reproducible and the tests can say which
claims must be slashed. A language-model analyst (llm.py) plugs in through the
same interface and is judged by the same verifier; the chain does not care
who wrote a claim, only whether its quote holds.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass

from .claims import Claim

_MONEY = re.compile(r"\$\d[\d,]*(?:\.\d+)?(?: (?:million|billion|thousand))?")
_SENTENCE_END = re.compile(r"(?<=[.;])\s+(?=[A-Z(])")
_VERB = re.compile(r"\b(?:was|were|increased|decreased|grew|declined|totaled|totalled|amounted to|of)\b")


@dataclass(frozen=True)
class Fact:
    metric: str
    value: str
    sentence: str


def facts(text: str) -> list[Fact]:
    """Every prose sentence in the filing that states a dollar figure.

    Tables are skipped (a row of eight numbers is not a sentence anybody would
    quote), and so are sentences cut by the extraction. The first figure is the
    fact's value; what precedes the verb is what it is about.
    """
    out, seen = [], set()
    for line in text.split("\n"):
        for sentence in _SENTENCE_END.split(" ".join(line.split())):
            sentence = sentence.strip()
            if not (60 <= len(sentence) <= 420) or not sentence.endswith("."):
                continue
            if not sentence[0].isupper() or sentence in seen:
                continue
            # Only figures a reader would trade on: scaled amounts ("$1.37 billion",
            # "$544 million"), not par values, per-share prices or footnote cents.
            figs = [f for f in _MONEY.findall(sentence) if f.endswith(("million", "billion"))]
            if not figs or len(re.findall(r"\d[\d,.]*", sentence)) > 8:
                continue
            if re.search(r"(?i)par value|per share|\bexhibit\b|incorporated by reference", sentence):
                continue
            seen.add(sentence)
            verb = _VERB.search(sentence)
            head = sentence[: verb.start()] if verb and verb.start() > 8 else " ".join(sentence.split()[:8])
            out.append(Fact(head.strip(" ,")[:90], figs[0], sentence))
    return out


def _nudge(figure: str, rng: random.Random) -> str:
    """Change one digit of a figure, keeping its shape."""
    digits = [i for i, c in enumerate(figure) if c.isdigit()]
    i = rng.choice(digits)
    new = str((int(figure[i]) + rng.choice([1, 2, 3, 7])) % 10)
    return figure[:i] + new + figure[i + 1:]


class Analyst:
    name = "analyst"
    kind = "scripted"   # "model" for a language-model analyst

    def __init__(self, seed: int = 0):
        self.rng = random.Random(f"{self.name}:{seed}")

    def claim(self, ticker: str, accession: str, fact: Fact, others: list[Fact]) -> Claim:
        raise NotImplementedError


class Diligent(Analyst):
    name = "Diligent"

    def claim(self, ticker, accession, fact, others):
        return Claim(ticker, accession, fact.metric, fact.value, fact.sentence, self.name)


class Misreader(Analyst):
    name = "Misreader"

    def claim(self, ticker, accession, fact, others):
        wrong = next((o.value for o in others if o.value != fact.value), _nudge(fact.value, self.rng))
        return Claim(ticker, accession, fact.metric, wrong, fact.sentence, self.name)


class Embellisher(Analyst):
    name = "Embellisher"

    def claim(self, ticker, accession, fact, others):
        bumped = _nudge(fact.value, self.rng)
        return Claim(ticker, accession, fact.metric, bumped, fact.sentence.replace(fact.value, bumped, 1), self.name)


class Fabricator(Analyst):
    name = "Fabricator"

    _LINES = [
        "{metric_base} increased {value} driven by record demand for AI-enabled products in every region.",
        "Management raised full-year guidance, citing {value} of unrecognised contracted revenue.",
        "The Company expects {value} in incremental margin from the restructuring announced this quarter.",
    ]

    def claim(self, ticker, accession, fact, others):
        value = _nudge(fact.value, self.rng)
        base = fact.metric.split(",")[0]
        line = self.rng.choice(self._LINES).format(metric_base=base, value=value)
        return Claim(ticker, accession, fact.metric, value, line, self.name)


CAST = (Diligent, Misreader, Embellisher, Fabricator)
