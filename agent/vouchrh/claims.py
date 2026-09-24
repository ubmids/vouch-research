"""A claim, and the hash that commits to it on-chain.

The chain stores who said it, what they staked and what happened; the words
live off-chain. The hash is what binds the two: anybody holding the published
claim can recompute it and see that it is exactly the one that was staked.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from eth_utils import keccak


@dataclass(frozen=True)
class Claim:
    ticker: str
    accession: str     # the SEC filing it cites
    metric: str        # what it is about, e.g. "Services and other revenue, three months to 30 Jun 2026"
    value: str         # the figure asserted, e.g. "$1.54 billion"
    quote: str         # the sentence in the filing that is supposed to say so
    analyst: str       # display name of the agent that wrote it
    summary: str = ""  # the one line a reader sees; not checked, the quote is

    def canonical(self) -> bytes:
        """Sorted keys, no whitespace, UTF-8: one byte string per claim."""
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

    def digest(self) -> bytes:
        return keccak(self.canonical())
