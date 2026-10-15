"""Writes the testnet round's status into the docs, from its evidence.

    python3 scripts/round_docs.py cre/runs/<run>

Reads <run>/round.env, <run>/env.txt and the round's feed (feed/feed.json once
settled, else <run>/feed.json). Rewrites docs/bli/TESTNET_ROUND.md and the text
between <!-- round:NAME --> and <!-- /round:NAME --> markers in README.md,
docs/bli/BUIDL.md and docs/deck/bli.html. Before the round is settled it writes
the "pending" wording; after, the verdicts and their transactions. Idempotent.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EX = "https://explorer.testnet.chain.robinhood.com"


def short(h: str, a: int = 10, b: int = 6) -> str:
    return f"{h[:a]}…{h[-b:]}" if h else ""


def link(h: str, label: str | None = None) -> str:
    return f"[{label or short(h)}]({EX}/tx/{h})" if h else "n/a"


def load(run: Path) -> tuple[dict, dict, bool]:
    env = dict(l.split("=", 1) for l in (run / "round.env").read_text().split() if "=" in l)
    settled_feed = ROOT / "feed/feed.json"
    feed = None
    if settled_feed.exists():
        f = json.loads(settled_feed.read_text())
        if f.get("contracts", {}).get("market", "").lower() == env["MARKET"].lower():
            feed = f
    settled = feed is not None and any(c.get("tx_judge") for c in feed["claims"])
    if feed is None:
        feed = json.loads(Path(env["FEED"]).read_text() if Path(env["FEED"]).is_absolute() else (ROOT / env["FEED"]).read_text())
    return env, feed, settled


def facts(run: Path) -> dict:
    env, feed, settled = load(run)
    envtxt = (run / "env.txt").read_text()
    posts = dict(l.split() for l in Path(env["POSTS"]).read_text().split("\n") if l.strip())
    cs = feed["claims"]
    written = re.search(r"verdicts_written: (\d+) of (\d+)", envtxt)
    hero = next((c for c in cs if c.get("analyst_kind") == "model" and "wrong quarter" in (c.get("reason") or "")), None)
    jv = (run / "journal-verify.txt")
    return {
        "run": run.relative_to(ROOT).as_posix(), "settled": settled, "feed": feed, "posts": posts,
        "market": env["MARKET"], "contracts": feed["contracts"],
        "written": written.groups() if written else None,
        "cleared": sum(1 for c in cs if c.get("verdict") == "cleared" and c.get("tx_judge")),
        "slashed": sum(1 for c in cs if c.get("verdict") == "slashed" and c.get("tx_judge")),
        "hero": hero, "journal": jv.read_text().strip().splitlines()[-1] if jv.exists() else "",
        "wasm": re.search(r"wasm_binary_hash: (\S+)", envtxt).group(1),
    }


def blocks(F: dict) -> dict[str, str]:
    m = F["market"]
    if not F["settled"]:
        return {
            "readme": f"**On Robinhood Chain testnet with the CRE CLI simulation:** the round's market is deployed and its 50 claims were posted on 15 Oct ([the round](docs/bli/TESTNET_ROUND.md), market [{short(m, 8, 6)}]({EX}/address/{m})). The verdicts wait on the CRE login; then one command settles them.",
            "buidl": f"On Robinhood Chain testnet the round's market is deployed and its 50 claims are posted (market {short(m, 10, 6)}); the CRE CLI simulation that settles them runs once the CRE login is done.",
            "deck-ran": "Robinhood Chain testnet, 24 Sep (v1, one verifier key) · the same words in a local round settled by the CRE workflow's code in Chainlink's SDK test runtime · testnet round posted 15 Oct, settling by CRE CLI simulation pending.",
            "deck-tile": "<b>50</b><span>claims posted on Robinhood Chain testnet on 15 Oct, waiting for the workflow</span>",
        }
    h, (w, t) = F["hero"], (F["written"] or ("?", "?"))
    hero = (f" The AI's wrong quarter: claim {h['id']}, slashed in {link(h['tx_judge'])}"
            + (f", its trade refused in {link(h['desk']['tx'])}" if h.get("desk") and not h["desk"].get("acted") else "") + ".") if h else ""
    return {
        "readme": f"**On Robinhood Chain testnet, settled by the Chainlink CRE workflow in the CRE CLI simulation** ([the round](docs/bli/TESTNET_ROUND.md), market [{short(m, 8, 6)}]({EX}/address/{m})): {w} of {t} verdicts written, {F['cleared']} cleared, {F['slashed']} slashed.{hero}",
        "buidl": f"On Robinhood Chain testnet the CRE workflow, in the CRE CLI simulation, wrote {w} of {t} verdicts ({F['cleared']} cleared, {F['slashed']} slashed; market {short(m, 10, 6)}); the journal check: {F['journal'] or 'see the run folder'}.",
        "deck-ran": f"Robinhood Chain testnet, settled by the Chainlink CRE workflow in the CRE CLI simulation: {w} of {t} verdicts, {F['cleared']} cleared, {F['slashed']} slashed (market {short(m, 8, 6)}).",
        "deck-tile": f"<b>{w}/{t}</b><span>verdicts written on Robinhood Chain testnet by the CRE workflow in the CRE CLI simulation</span>",
    }


def fill(path: Path, name: str, text: str) -> None:
    s = path.read_text()
    pat = re.compile(rf"(<!-- round:{name} -->)(.*?)(<!-- /round:{name} -->)", re.S)
    if not pat.search(s):
        raise SystemExit(f"{path}: no round:{name} marker")
    path.write_text(pat.sub(lambda mt: mt.group(1) + text + mt.group(3), s))


def round_md(F: dict) -> str:
    c, feed = F["contracts"], F["feed"]
    L = ["# Robinhood Chain testnet round", ""]
    if F["settled"]:
        w, t = F["written"] or ("?", "?")
        L += [f"Settled by the Chainlink CRE workflow in the CRE CLI simulation: **{w} of {t} verdicts written**,",
              f"{F['cleared']} cleared, {F['slashed']} slashed. Journal check: {F['journal'] or 'n/a'}.",
              "Verdicts go through Chainlink's MockKeystoneForwarder (simulation: it checks no signatures).", ""]
    else:
        L += ["The first half of the CRE round: the market is deployed and every claim is posted",
              "on Robinhood Chain testnet (chain id 46630). Nothing is settled yet: the verdicts come",
              "from the Chainlink CRE workflow in the CRE CLI simulation, which needs `cre login`.",
              "The claims wait, pending, for the 7-day window (until 22 Oct 2026, 16:32 UTC). After",
              "the login, one command settles them and rewrites this page:", "",
              "```", "bash scripts/after_login.sh", "```", ""]
    L += [f"Evidence folder: `{F['run']}/`. Workflow WASM: `{F['wasm']}`. The AI analyst's claims are",
          "Qwen 2.5 7B's words from the 24 Sep round, replayed word for word (labelled replayed).", "",
          "## Contracts", "", "| Contract | Address |", "|---|---|",
          f"| BondedClaims (verdicts only from the forwarder) | [{c['market']}]({EX}/address/{c['market']}) |",
          f"| AgentDesk | [{c['desk']}]({EX}/address/{c['desk']}) |",
          f"| Test USDG (tUSDG) | [{c['usdg']}]({EX}/address/{c['usdg']}) |",
          f"| Chainlink MockKeystoneForwarder (simulation) | [{c['forwarder']}]({EX}/address/{c['forwarder']}) |", "",
          "Deployer and funder: `0x950d00BA837cD285e6d8a0F3f02d69434a775808` (test wallet).", "",
          "## The claims", ""]
    if F["settled"]:
        L += ["| Claim | Stock | Analyst | Figure | Verdict | Posted | Verdict tx | Desk |", "|---|---|---|---|---|---|---|---|"]
        for cl in feed["claims"]:
            d = cl.get("desk") or {}
            desk = (("trade " if d.get("acted") else "refused ") + link(d["tx"])) if d.get("tx") else ""
            L.append(f"| {cl['id']} | {cl['ticker']} | {cl['analyst']}{' (AI, replayed)' if cl.get('replayed_from') else ''} | {cl['value']} | "
                     f"{cl.get('verdict', 'pending')} | {link(F['posts'].get(str(cl['id']), cl.get('tx_post', '')))} | {link(cl.get('tx_judge', ''))} | {desk} |")
    else:
        L += ["All 50 posting transactions succeeded (receipts checked 15 Oct). \"Expected\" is what the",
              "same check gives locally before any gas; the on-chain verdict will be the workflow's.", "",
              "| Claim | Stock | Analyst | Figure | Expected | Posted in |", "|---|---|---|---|---|---|"]
        for cl in feed["claims"]:
            L.append(f"| {cl['id']} | {cl['ticker']} | {cl['analyst']}{' (AI, replayed)' if cl.get('replayed_from') else ''} | {cl['value']} | "
                     f"{cl.get('local_verdict') or cl.get('verdict') or ''} | {link(F['posts'][str(cl['id'])])} |")
    return "\n".join(L) + "\n"


def main(argv: list[str]) -> None:
    run = (ROOT / argv[1]).resolve() if len(argv) > 1 else sorted((ROOT / "cre/runs").glob("*-posted"))[-1]
    F = facts(run)
    B = blocks(F)
    fill(ROOT / "README.md", "readme", B["readme"])
    tpl = (ROOT / "docs/bli/BUIDL.template.md").read_text()
    (ROOT / "docs/bli/BUIDL.md").write_text(tpl.replace("{{ROUND}}", B["buidl"]))
    fill(ROOT / "docs/deck/bli.html", "deck-ran", B["deck-ran"])
    fill(ROOT / "docs/deck/bli.html", "deck-tile", B["deck-tile"])
    (ROOT / "docs/bli/TESTNET_ROUND.md").write_text(round_md(F))
    print(f"{'settled' if F['settled'] else 'pending'}: README, BUIDL, deck and docs/bli/TESTNET_ROUND.md written from {F['run']}")


if __name__ == "__main__":
    main(sys.argv)
