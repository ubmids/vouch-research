# DoraHacks BUIDL: BLI Legal Tech Hackathon 2

Paste-ready. This file is generated: edit `BUIDL.template.md` and run
`python3 scripts/round_docs.py` (the testnet round's status is filled in from
its evidence). Submit by **30 October 2026** (DoraHacks closes 1 November,
01:01 UTC).

**Track:** All BUIDLs (LegalTech and RegTech)
**Bounties to select:** RYO-CHAN "Autonomous Agents" · Chainlink "Best workflow with CRE"
**Contact for the form:** [OWNER: a Discord, WhatsApp or WeChat handle]

---

## Name

Vouch

## Tagline

A citation check for AI-written research, run as a Chainlink CRE workflow.

## Short description

Courts have caught over a thousand AI-invented citations in US filings. AI now
drafts investment research, with the same failure. Vouch checks every figure
an AI cites against the SEC filing through a Chainlink CRE workflow, makes a
wrong claim lose its stake, and keeps a record of reliance a compliance officer
can show an examiner.

## Description

**The problem lawyers already know.** Lawyers have been sanctioned for briefs
citing cases an AI made up: 1,116 US court filings by June 2026 (Charlotin
database, reported by AFP). Investment research is drafted by the same models
and fails the same way. An AI wrote "Depreciation for Q3 2026 was $1.37
billion" about Tesla; the 10-Q sentence it cited gives that figure for the
quarter ended June 30. FINRA Rule 2241(c)(1)(A) requires that "purported facts
in its research reports are based on reliable information". Regulation AC has a
natural person certify the views. A model cannot certify a belief. A firm can
show that every number was checked.

**What Vouch does.**

1. **Exhibit.** Each claim is one figure, the filing sentence behind it and the
   filing's accession number, posted on-chain with a stake.
2. **Check.** A Chainlink CRE workflow fetches the filing from SEC EDGAR and
   checks the claim deterministically: the sentence must be in the filing, and
   every figure, period and direction as filed.
3. **Verdict.** A wrong claim loses its stake to a readers' fund fixed at
   deploy, in the same transaction as the verdict. A right one keeps it.
4. **Reliance.** A trading agent trades through a desk that refuses, on-chain,
   any trade citing a claim that failed or was never checked.
5. **Record.** Every trade keeps a record of reliance: what was read, what was
   refused, what was relied on, and how to re-check each line. It prints as one
   page counsel can keep.

**Why stake, if the check is public?** The stake turns checking into a
commitment: an AI that checks before it publishes costs nothing; one that does
not, pays. For a regulated firm the stake is optional; the check and the record
are the compliance product.

**What it does not prove.** That a view was honestly held, that a
recommendation had a reasonable basis, that the filing is true, or that a
record meets Rule 17a-4. That stays the firm's job; Vouch gives it evidence.
The one-page brief for lawyers is docs/bli/LEGAL.md.

**For RYO-CHAN: an autonomous news checker with a reasoning trail.** The agent
read 130 real public posts about five companies (a Mastodon snapshot, with
urls and hashes). Claude Haiku 4.5 read each post for ticker, figure, period,
sentiment, conviction and urgency; its exact messages and replies are hashed
into the record, so Re-verify can check each reply gives exactly the reading.
The agent stakes on a story itself only where a sentence of the filing states
the figure, trades only on what held, and commits its reasoning on-chain with
every paper trade. Re-verify re-runs every step in the browser.

**For Chainlink: CRE is the orchestration layer.** EVM log trigger on Robinhood
Chain, HTTP to SEC EDGAR, the deterministic check, identical consensus, a
report through the forwarder to `BondedClaims.onReport`, which accepts verdicts
from the forwarder alone and, in production, only from the configured workflow
owner, name and pinned id. The TypeScript check matches the Python one on 3,249
claims, on Bun and on QuickJS.

> **What ran, and what is trusted**
> - {{ROUND}}
> - The same claims settled end to end on a local chain by the workflow's own
>   code in Chainlink's SDK test runtime; the real-post rounds the same way.
> - Tests: 57 Foundry, 76 Python and 24 Bun, all passing.
> - In simulation, Chainlink's mock forwarder checks no signatures: it proves
>   the path, not the security. A live DON also needs SEC's User-Agent rule
>   solved at the gateway.
> - The hero AI claim is Qwen 2.5 7B's words from 24 Sep, replayed word for
>   word and labelled. The check reads sentences, not tables, and the agent
>   does not stake on figures it cannot see.

**Team.** [FOUNDER: Subomi Olagoke, one line on who you are.] [FOUNDER: one line
on why you can build this.]

**Built with:** Solidity (Foundry), Chainlink CRE (TypeScript SDK, CLI), Python,
SEC EDGAR, Robinhood Chain testnet, test USDG, Claude Haiku 4.5 (post reader),
Qwen 2.5 7B (an analyst), a static web page.

## What's next

A live DON with a pinned workflow id; Robinhood Chain mainnet with USDG; 8-Ks
and 10-Ks; one compliance team piloting cleared-only publication.

## Prior work, disclosed

First built for Arbitrum Open House Singapore (from 24 September 2026), from an
earlier Vouch on Casper (June 2026). New for this hackathon: CRE settlement
replacing the verifier key, the record of reliance, the real-post news checker,
and the legal framing (docs/bli/WHATS_NEW.md).

## Links

- Repository: https://github.com/ubmids/vouch-research
- Live feed: https://vouch-feed.vercel.app · one claim: `/?claim=6&view=claim` · a record of reliance: `/?record=TSLA&feed=feed-local.json`
- For lawyers: docs/bli/LEGAL.md · Architecture: docs/bli/ARCHITECTURE.md · CRE workflow: cre/README.md
- Demo video: [OWNER: the YouTube link]
- Deck: docs/bli/deck.pdf
- Court figures: AFP, June 2026, on Damien Charlotin's AI Hallucination Cases database
