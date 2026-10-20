# Vouch at BLI Legal Tech Hackathon 2: the plan to 30 October

Written 15 Oct 2026. The aim is first place, or failing that both bounties.
How to run the owner-only steps is in [bli/CHECKLIST.md](bli/CHECKLIST.md). The design spec is
[../design/DESIGN.md](../design/DESIGN.md).

## Status, 15 Oct evening

- **Design:** Exhibit is binding (design/DESIGN.md). The web feed, the claim
  record, the printable record of reliance (`?record=<ticker>`), the README
  cover, the gallery, the video cards (`scripts/build_assets.sh`) and the deck
  (`scripts/build_deck.sh`) are all in it. The name stays Vouch, read from
  `web/brand.js` and `design/assets/brand.json`.
- **Testnet:** the round's market is deployed and its 50 claims are posted on
  Robinhood Chain testnet (docs/bli/TESTNET_ROUND.md). Settling them with the
  CRE CLI simulation is one command after Subomi's `cre login`, before 22 Oct.
- **RYO:** the news checker reads 130 real public Mastodon posts; the
  judge-visible run used Claude Haiku 4.5 as the reader (about $0.11 through
  the relay), replies hashed into the record.
- **Left for Claude:** settle the round and replace the pending lines; redeploy
  prep; the 5-minute pitch; a last asset rebuild from the settled feed.

## 0. Where the entry lives

The brief pointed at `~/Desktop/attestor`. That repo
(`Subomi-olagoke/vouch`, public) is the June Casper entry: an Odra contract
and a Python market with synthetic documents. The BLI entry is **this repo**,
`ubmids/vouch-research` (private), branch `first-place`, which grew out of it
through Arbitrum Open House Singapore. It already has the SEC-filing check,
the Chainlink CRE workflow, the trading agent's journal and the legal brief.
The Casper repo is left untouched and is disclosed as prior work.

State on 15 Oct: 62 pytest pass (1 skipped), plus 57 Foundry and 24 Bun tests
as of 14 Oct. `cre workflow build` works. The CRE CLI simulation has never
run, because the CLI is not logged in. bun 1.4.3 is installed at `~/.bun/bin`.
The testnet wallet holds 0.0062 test ETH, about twice what a round needs.

## 1. The event, checked 15 Oct

These facts come from DoraHacks' public API (hackathon 1904) and bli.tools,
both read today.

- **Deadline:** DoraHacks closes **1 Nov 2026 01:01 UTC**, which is 31 Oct
  21:01 US Eastern. BLI's 11 Oct post says 31 October. We submit on **30 Oct**.
- **Judging criteria:** **none are published for 2026.** Six Q&A posts asking
  for them, the oldest from 18 Jul, are unanswered. The organiser's DoraHacks
  handle is `sparrow_bli`. 2025 had no overall criteria either; its one
  bounty with criteria listed Creativity, Usefulness, Functionality,
  Presentation, Completeness, Demo quality (with a code walkthrough), Code
  quality and Documentation. Last year's panel was mostly lawyers and
  compliance people, and one judge wrote that "legal applicability fell
  short" in most entries. We design for that sentence.
- **Requirements (BLI, 11 Oct):** "public code repositories, architecture
  documentation, and video demos". No video length is published. The BUIDL
  form asks for a Discord, WhatsApp or WeChat contact.
- **Judging** runs 5 Nov to 5 Dec, with awards on 12 Dec. No live pitch is
  announced for 2026; in 2025, 13 finalists pitched at a virtual pitch day.
- **Money:** a $20k headline pool is "still developing", at BLI's discretion.
  Only two bounties are posted:
  - **RYO-CHAN, Autonomous Agents, $6,000:** "Build agents that interpret
    market evidence and record the practice trades they would make. Strong
    entries show cause and effect and preserve a repeatable reasoning trail."
    The spotlight idea is a multi-KOL agent reading up to 20 crypto creators
    on X for tokens, sentiment, conviction and urgency. News Checker is
    another listed idea.
  - **Chainlink, Best workflow with CRE, 2 x $1,000:** "Build, simulate, or
    deploy a CRE Workflow that's used as an orchestration layer within your
    project" and "integrate at least one blockchain with an external API …
    and demonstrate a successful simulation (via the CRE CLI) or a live
    deployment on the CRE network."
- **Competition visible today:** one public BUIDL (PocketChange, RYO bounty)
  and 476 registered hackers.

**Does the plan hold against the rules?** Yes. "Trade journal citing cleared
claims (RYO), verifier as a Chainlink CRE workflow, framed for lawyers (Reg AC
/ FINRA 2241)" breaks no rule and fits the single track (LegalTech and
RegTech, AI x Blockchain). Two weak points remain:

1. **Chainlink's minimum is unmet** until `cre workflow simulate` runs. That
   needs Subomi's CRE account and `cre login`. An API key is not an
   alternative: the docs reserve API-key auth for accounts with deploy
   access.
2. **RYO asks for crypto KOLs on X.** We read posts about tokenised stocks,
   and so far only 20 written fixtures. Section 3 makes them real posts
   without needing an X account.

## 2. The entry, framed for lawyers

**The problem a compliance lawyer has.** A broker-dealer or research
publisher now drafts research with AI. FINRA Rule 2241(c)(1)(A) requires
policies reasonably designed to ensure that "purported facts in its research
reports are based on reliable information". Regulation AC has a natural
person certify the views. FINRA says firms are responsible for their
communications "regardless of whether they are generated by a human or AI",
and its 2026 oversight report asks how firms "track agent actions and
decisions". Meanwhile lawyers have been sanctioned again and again for
AI-invented citations: about 1,600 filings worldwide by June 2026, 1,116 of
them in the US. AI-written research fails the same way. It gets a quarter
wrong, or swaps a six-month figure for a three-month one. The analyst or
compliance officer signing off has no record showing that each figure was
checked, against what, and by whom.

**How Vouch solves it.** Every figure an AI analyst cites is posted as a
claim, with the filing sentence it relies on and the filing's accession
number. A Chainlink CRE workflow fetches that filing from SEC EDGAR and checks
the claim deterministically: the sentence must be in the filing word for word,
and every figure, period and direction must be as filed. A claim that fails
loses its stake. A trading agent cannot act on it, because the desk contract
refuses any trade that cites a failed or unchecked claim. Every trade keeps a
record of reliance: what was read, what was refused, what was relied on, and
how to re-check it. Counsel can keep that record, and anyone can re-run it.

In two sentences: Vouch is a citation check for AI-written financial research.
A Chainlink CRE workflow checks every figure against the SEC filing, and an AI
trading agent can act only on what held, leaving a record of reliance a
compliance officer can show an examiner.

**What it does not claim** (already in [bli/LEGAL.md](bli/LEGAL.md) section
6): it does not prove a view was honestly held, that a recommendation had a
reasonable basis, that the filing is true, or that a record meets Rule 17a-4.

## 3. Reuse and new work

**Reused as is:** `BondedClaims` and `AgentDesk` (Solidity, 57 Foundry tests,
the readers' fund), the CRE workflow `cre/vouch-verifier` (log trigger, HTTP
to EDGAR, the check, identical consensus, report, forwarder), the Python
check and its Bun and QuickJS parity on 3,249 claims, the journal with
Re-verify, `scripts/cre_round.sh`, LEGAL.md, ARCHITECTURE.md and the BUIDL
copy.

**New, in priority order:**

1. **The CRE CLI round on Robinhood Chain testnet.** It is the Chainlink
   minimum, and it gives the video real explorer links. The code exists; it
   waits on `cre login`.
2. **The design pass** to the chosen direction, on every judged surface
   (DESIGN.md section 5 and 6). This includes a fix for the stale
   `docs/cover.png`, which still says "Arbitrum Open House Singapore".
3. **A record of reliance as a printable page.** The audit record is a
   Markdown download today. A print-styled page, which can be saved as a PDF,
   is the artefact a lawyer recognises, and it will be shown in the video.
4. **The RYO lane on real posts.** Mastodon's public tag timelines (`#TSLA`,
   `#AMZN`, `#NFLX`, `#PLTR`, `#AMD`, `#earnings`) answer without an account
   (checked today), and can be paged back to the July and August 10-Q
   season. StockTwits, Reddit and Bluesky all refused scripted access.
   - An LLM reader extracts token, figure, period, sentiment, conviction and
     urgency.
   - The prompt, model and output are hashed into the journal, so the trail
     can be re-run.
   - The agent stakes on each story itself, and paper PnL goes on screen.
   - Development runs on local Qwen 2.5 7B. One final recorded run goes
     through the Haiku relay (estimated under $0.10).
   - If fewer than about 10 real posts carry a checkable figure, we keep the
     labelled fixtures and add the real ones beside them.
5. **Copy:** replace every "pending" line from the run folder, cut the BUIDL
   to about 600 words. The name is Vouch (decided 15 Oct).
6. **The submission assets:** a cover, 4 to 6 gallery images, the deck in the
   new design, the video's title card, lower thirds and end card, and a
   5-minute pitch version in case finalists pitch in November.

**Not doing:** a live DON deployment (the SEC User-Agent problem is
unsolved), Robinhood Chain mainnet, or a model for the post reader beyond the
recorded run.

## 4. Chainlink CRE: the fit and what it needs

**The fit.** The verdict exists only as a CRE report. The flow is:

1. A `Posted` event on Robinhood Chain fires the EVM log trigger.
2. The HTTP capability, in node mode, fetches the filing from SEC EDGAR.
3. The workflow runs the check.
4. Identical-consensus aggregation agrees on the verdict.
5. `runtime.report` and `writeReport` send it to the forwarder.
6. `BondedClaims.onReport` accepts it only from the forwarder (and, in
   production, only from the configured workflow owner, name and pinned
   id), then slashes or clears in the same transaction.

That is exactly "a blockchain integrated with an external API, with CRE as
the orchestration layer".

**Docs (read 15 Oct):**

| Topic | Page |
|---|---|
| Install | docs.chain.link/cre/getting-started/cli-installation/macos-linux |
| Simulating ("You must have a CRE account and be logged in with the CLI") | docs.chain.link/cre/guides/operations/simulating-workflows |
| Account (2FA required) | docs.chain.link/cre/account |
| Authentication (API keys need deploy access) | docs.chain.link/cre/reference/cli/authentication |
| Supported networks (Robinhood Testnet from CLI v1.30.0 and TS SDK v1.19.0, with a mock and a production forwarder) | docs.chain.link/cre/supported-networks-ts |
| Service quotas (HTTP response 250 KB, consensus observation 25 KB, log event 5 KB, report 50 KB, 15 HTTP calls per run, 10 s maximum timeout) | docs.chain.link/cre/service-quotas |
| Deploy access (optional; now has a "Hackathon" purpose option) | docs.chain.link/cre/account/deploy-access |

**Accounts and keys:**

- **A CRE account is needed.** Subomi creates it at app.chain.link with 2FA,
  then runs `~/.cre/bin/cre login` in a browser on this Mac.
- **No API key is needed**, and no deploy access.
- **No faucet trip is needed:** the wallet has enough test ETH. Only
  `--broadcast` spends gas. The dry run is free.
- **Already on this Mac:** CLI v1.38.0 (at least v1.30 is required) and bun
  1.4.3 (at least 1.2.21 is required).

**Size limits.** A gzipped 10-Q (94 to 171 KB) fits the documented 250 KB
response limit. The audit's worry about a 26.4 KB default comes from the
gateway's source code. It matters only on a live DON, and the round's
`--limits none` retry covers the simulator. The 25 KB consensus limit is met
because the check runs inside the node function and only the verdict is
aggregated.

## 5. Day by day

| Date | Claude | Subomi |
|---|---|---|
| Thu 15 Oct | Plan, design directions, owner list (this commit) | Pick a design direction. Create the CRE account, then `cre login` |
| Fri 16 | Run `cre_round.sh --preflight` once logged in. Start the design pass on the claim view (the hero) | |
| Sat 17 | Design pass: claims list, journal, tour, phone fixes; tests green | |
| Sun 18 | **The CRE round** (if Subomi agrees I run it; otherwise he does). Commit `cre/runs/<run>/` and replace the pending lines | Start the lawyer or compliance quote |
| Mon 19 | Spare day for a failed round. The record of reliance page | |
| Tue 20 | RYO lane: the Mastodon reader, local-model reading, hashed trail, stake per story, PnL on screen | Founder lines for the BUIDL |
| Wed 21 | Deck, cover, gallery images and README hero in the new design | |
| Thu 22 | Final Haiku reader run (at most $0.10). BUIDL cut to about 600 words | The quote, in hand |
| Fri 23 | Video cards, shot list, captions, a 5-minute pitch version. Prepare the deploy | `vercel deploy --prod` |
| Sat 24 | Full dry run of the demo script on the live page; fix what it finds | |
| Sun 25 | Secret sweep. Cut the RYO and CRE 60-second clips from the recording | Record the 2:30 video. Make the repo public |
| Mon 26 to Tue 27 | Buffer. Check every link logged out | Edit and upload the video |
| Wed 28 | Freeze: all tests, final screenshots | |
| Thu 29 | Final BUIDL text | DoraHacks BUIDL draft, with the contact handle |
| Fri 30 | Check the submission | **Submit** |

## 6. Risks

| Risk | What we do |
|---|---|
| `cre login` slips past 18 Oct, so the Chainlink minimum is unmet and the video falls back to round B | This is the only blocker that matters. Ask today. The round takes 20 to 40 minutes, and 19 Oct is spare |
| The simulator decompresses SEC's gzip body, or rejects its size | Retry one claim with `--limits none`, which the script prints. Say so in "What ran" |
| SEC rate-limits or blocks during the round | The preflight checks SEC first. Retry later the same day |
| A live Qwen claim is right, so the round has no wrong-quarter hero | Use `ANALYST_MODEL=replay`, labelled "replayed" |
| Too few real posts carry a figure | Keep the fixtures beside the real posts, both labelled. Never present fixtures as real |
| Real posts name real people as wrong | Show handles shortened, with the link kept in the record. Subomi decides |
| The design pass breaks behaviour | Change markup and styles only. Run pytest, forge and bun after each commit |
| No lawyer quote | The entry stands without it. LEGAL.md does the work; the BUIDL line is deleted |
| No published criteria, and the money is discretionary | Aim at both bounties explicitly, plus legal applicability for the pool |
| A November live pitch | Have a 5-minute version ready by 23 Oct |
| Payout terms and KYC are unpublished | Nothing to do before submission |
| LLM budget | Development runs on local Ollama. Haiku runs only through the relay, capped at $0.30 for this entry (relay at $0.2937 on 15 Oct before any Vouch call) |

## 7. What needs Subomi

| By | What |
|---|---|
| **15 to 16 Oct** | **Create the Chainlink CRE account** (app.chain.link, 2FA), then run `~/.cre/bin/cre login` in a terminal on this Mac. This is the one blocker |
| ~~16 Oct~~ | ~~Pick a design direction~~: done 15 Oct, Exhibit (`design/directions-2.html`, E) |
| 16 Oct | Say whether Claude may run the testnet round itself once you are logged in. It spends only test ETH from the existing test wallet |
| 18 to 22 Oct | One lawyer, compliance officer or research publisher to read LEGAL.md and give one sentence, with name and role |
| 20 Oct | The two founder lines in the BUIDL |
| 20 Oct | Whether real posters' handles are shown in full or shortened |
| 23 Oct | `cd web && vercel deploy --prod` |
| 25 Oct | Record the video (face in a corner for the first and last 10 seconds), and make the repo public |
| 29 Oct | Draft the DoraHacks BUIDL, with a Discord, WhatsApp or WeChat handle |
| 30 Oct | Submit |
| 5 Nov to 5 Dec | Keep mid-November evenings (US Eastern) free in case of a finalist pitch |
