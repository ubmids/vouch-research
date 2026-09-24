"""Vouch as a tool any AI agent can call before it acts on research.

An MCP server (Model Context Protocol, the standard way agents such as Claude
plug in tools) with one tool, verify_claim. It runs the same deterministic
check the market settles stakes with, locally, against the company's SEC
filing. No key, no hosted model.

    PYTHONPATH=agent .venv/bin/python -m vouchrh.mcp_server

In an agent's MCP config:

    {"mcpServers": {"vouch": {"command": "/path/to/vouch/.venv/bin/python",
       "args": ["-m", "vouchrh.mcp_server"], "env": {"PYTHONPATH": "/path/to/vouch/agent"}}}}
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from . import edgar
from .verifier import audit_claim

server = MCPServer(
    name="vouch",
    title="Vouch",
    instructions=("Before you repeat or act on a figure from a company's SEC filing, check it with "
                  "verify_claim. Cite one whole sentence from the filing as the quote. A slashed verdict "
                  "means the claim as written is not what the filing says: do not act on it."),
    website_url="https://vouch-feed.vercel.app",
)


@server.tool(description=(
    "Check a research claim about a US-listed company against its latest 10-Q (or a given filing). "
    "Deterministic: the quote must be a whole sentence of the filing, the value must be in it, and "
    "the summary's figures, period, quarter, date and direction must match what the sentence says."))
def verify_claim(ticker: str, value: str, quote: str, summary: str = "", accession: str = "") -> dict:
    pool = edgar.filings(ticker, ("10-Q", "10-K"), 8)
    filing = next((f for f in pool if f.accession == accession), None) if accession else \
        next((f for f in pool if f.form == "10-Q"), pool[0] if pool else None)
    if filing is None:
        return {"verdict": "unknown", "reason": f"no filing found for {ticker}"}
    v = audit_claim(value, quote, filing.text(), summary)
    return {"verdict": "slashed" if v.fraudulent else "cleared", "reason": v.reason,
            "filing": {"form": filing.form, "accession": filing.accession, "filed": filing.filed, "url": filing.url}}


if __name__ == "__main__":
    server.run("stdio")
