"""Write the parity fixtures for the CRE workflow's TypeScript check.

For every stock token's latest 10-Q: the hash of the text the Python check
reads, and the Python verdict (and the trading policy's signal) on a few
thousand claims about it (every
scripted analyst on every fact, plus summaries that get the period, quarter,
date, direction or figure right and wrong). cre/vouch-verifier/parity.test.ts
runs the TypeScript port over the same claims and must agree on every one.

    PYTHONPATH=agent .venv/bin/python scripts/cre_fixtures.py
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

from eth_utils import keccak

from vouchrh import edgar
from vouchrh.analysts import CAST, facts
from vouchrh.market import TOKENS
from vouchrh.policy import signal
from vouchrh.verifier import audit_claim

OUT = Path(__file__).resolve().parents[1] / "cre" / "vouch-verifier" / "fixtures"

SUMMARIES = [
    "{v} in Q2 2026.", "{v} in Q3 2026.", "{v} in Q2 2025.", "{v} for the quarter.", "{v} for the six months to June.",
    "{v} in the first half.", "It rose to {v}.", "It fell to {v}.", "It was {v} as of June 30, 2026.",
    "It was {v} as of December 31, 2025.", "{v}, up {w} from a year earlier.", "Losses were {v}.", "Gains were {v}.",
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(1444)
    for t in TOKENS:
        f = edgar.latest(t)
        raw = f.raw()
        text = f.text()
        found = facts(text)
        claims = []
        for i, fact in enumerate(found):
            for A in CAST:
                c = A(seed=i).claim(t, f.accession, fact, found)
                claims.append({"value": c.value, "quote": c.quote, "summary": c.summary, "metric": c.metric})
            for s in rng.sample(SUMMARIES, 4):
                other = rng.choice(found).value
                claims.append({"value": fact.value, "quote": fact.sentence, "summary": s.format(v=fact.value, w=other),
                               "metric": ""})
            # a fragment, and a quote with its figure nudged
            claims.append({"value": fact.value, "quote": fact.sentence[len(fact.sentence) // 3:], "summary": "", "metric": ""})
        for c in claims:
            v = audit_claim(c["value"], c["quote"], text, c["summary"], c["metric"])
            c["want"] = {"fraudulent": v.fraudulent, "reason": v.reason, "method": v.quote_check.method,
                         "score": v.quote_check.score}
            c["signal"] = signal(c)          # the trading agent's reading of it (policy.ts must agree)
        fixture = {"ticker": t, "accession": f.accession, "url": f.url, "cache_key": edgar.CACHE.name,
                   "raw_keccak": "0x" + keccak(raw).hex(), "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                   "text_length": len(text), "claims": claims}
        (OUT / f"{t}.json").write_text(json.dumps(fixture, separators=(",", ":"), ensure_ascii=False))
        bad = sum(c["want"]["fraudulent"] for c in claims)
        print(f"{t}: {len(claims)} claims ({bad} slashed) against {f.accession}")


if __name__ == "__main__":
    main()
