# GENERATED from agent/vouchrh/edgar.py by scripts/sync_api.sh. Do not edit.
"""SEC EDGAR, the source of truth every claim is checked against.

Filings are public and free, but the SEC's fair-access policy requires every
automated request to name a contact, and caps traffic at ten requests a second.
Everything fetched is cached on disk, so a demo, a test run or a judge's
re-check never depends on the SEC being reachable, and so the same filing text
is what both the analyst quoted and the verifier checked.
"""
from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CONTACT = os.environ.get("VOUCH_SEC_CONTACT", "Vouch research prototype admin@vouch-feed.vercel.app")
CACHE = Path(os.environ.get("VOUCH_CACHE", Path(__file__).resolve().parents[2] / ".cache" / "edgar"))
_last = 0.0


def _get(url: str) -> bytes:
    global _last
    key = CACHE / re.sub(r"[^A-Za-z0-9._-]", "_", url.split("://", 1)[-1])
    if key.exists():
        return key.read_bytes()
    wait = 0.15 - (time.monotonic() - _last)          # stay well under 10 req/s
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": CONTACT, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    _last = time.monotonic()
    key.parent.mkdir(parents=True, exist_ok=True)
    key.write_bytes(body)
    return body


@dataclass(frozen=True)
class Filing:
    ticker: str
    cik: str
    form: str
    accession: str        # "0001628280-26-049270", what goes on-chain
    filed: str            # ISO date
    period: str
    url: str

    def raw(self) -> bytes:
        """The document as EDGAR serves it. A verdict commits to the keccak256
        of canonical(raw): anyone can download the document, drop the one tag
        SEC's CDN adds, and get the same hash."""
        return _get(self.url)

    def text(self) -> str:
        return to_text(self.raw().decode("utf-8", "ignore"))


# SEC's CDN appends a bot-check script to every document it serves, and its path
# changes over time (seen 13-14 Oct 2026: two paths for the same 10-Q, 45
# minutes apart), so the raw bytes of a filing do not hash the same twice.
# The canonical bytes are the document without that tag. Filings themselves
# carry no scripts; to_text drops every script anyway, so the text is unchanged.
_CDN_SCRIPT = re.compile(rb'<script type="text/javascript"[ \t\n\r\f\v]+src="/[^"<>]*"></script>')


def canonical(raw: bytes) -> bytes:
    return _CDN_SCRIPT.sub(b"", raw)


def to_text(raw_html: str) -> str:
    """The words of a filing, as a reader sees them. Scripts, styles and the
    hidden inline-XBRL header go; tags become spaces; entities are decoded."""
    raw = re.sub(r"(?is)<(script|style|ix:header)\b.*?</\1>", " ", raw_html)
    raw = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h[0-9])>", "\n", raw)
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw)).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", text))
    # A tag between the currency sign and the number leaves "$ 3.3 billion";
    # rejoin it so quotes read the way the filing reads.
    text = re.sub(r"\$\s+(?=[0-9(])", "$", text)
    return re.sub(r"\(\s+(?=[0-9])|(?<=[0-9])\s+\)", lambda m: m.group(0).strip(), text).strip()


def cik_for(ticker: str) -> str:
    table = json.loads(_get("https://www.sec.gov/files/company_tickers.json"))
    for row in table.values():
        if row["ticker"].upper() == ticker.upper():
            return str(row["cik_str"]).zfill(10)
    raise KeyError(f"no SEC registrant for ticker {ticker!r}")


def filings(ticker: str, forms: tuple[str, ...] = ("10-Q", "10-K"), limit: int = 4) -> list[Filing]:
    cik = cik_for(ticker)
    recent = json.loads(_get(f"https://data.sec.gov/submissions/CIK{cik}.json"))["filings"]["recent"]
    out = []
    for i, form in enumerate(recent["form"]):
        if form not in forms:
            continue
        acc = recent["accessionNumber"][i]
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{recent['primaryDocument'][i]}"
        out.append(Filing(ticker.upper(), cik, form, acc, recent["filingDate"][i], recent["reportDate"][i], url))
        if len(out) == limit:
            break
    return out


def latest(ticker: str, form: str = "10-Q") -> Filing:
    found = filings(ticker, (form,), 1)
    if not found:
        raise LookupError(f"{ticker} has no recent {form}")
    return found[0]
