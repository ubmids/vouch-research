# Vouch, BLI demo script (2:30)

Hard ceiling 3:00; aim for 2:30. **The payoff is on screen by 0:20**: an AI's
wrong claim, slashed by Chainlink, and a trading agent refused, on-chain.
Then why lawyers should care, then Chainlink, then the journal.

**Before recording**

- Run `bash scripts/cre_round.sh` so the live feed is a round settled by the
  CRE workflow on Robinhood Chain testnet, with a journal. Publish it
  (`cd web && vercel deploy --prod`).
- Have three tabs ready: **A** `https://vouch-feed.vercel.app/?journal`,
  **B** the explorer tab of the lead claim's verdict transaction, **C**
  `docs/bli/LEGAL.md` on GitHub, scrolled to section 6.
- A terminal with one claim's log from `cre/runs/<run>/claim-<id>.log`, or run
  one simulation live (about 20 s): the `cre workflow simulate ... --evm-tx-hash` line is in
  `scripts/cre_round.sh`.
- 1920x1080, browser full screen. **Your face in a small corner bubble for the
  first 10 seconds and the last 10** (a real person on camera). One voice, unhurried.

---

## 0:00 to 0:20, the payoff first

**On screen:** tab A. It opens on the AI's claim in the inspector: the claim
says Q3, the filing's sentence says June, **Slashed**, and "It was refused"
in the trading-agent box. Point at each as you say it.

**Say:**

> An AI analyst wrote that Tesla's depreciation for Q3 was 1.37 billion
> dollars. Tesla's own filing says that quarter ended in June. A Chainlink workflow
> checked it against the SEC filing and took the AI's 25-dollar stake. And
> the trading agent that tried to act on it? Refused, on-chain.

## 0:20 to 0:45, why a lawyer should care

**On screen:** tab C, section 2 (the Reg AC and FINRA 2241 quotes), then
section 3 (the table).

**Say:**

> Research rules were written for people. Regulation AC has a natural person
> certify their personal views. FINRA Rule 2241 says the facts in research
> must be based on reliable information. AI now drafts research, and it can't
> certify a belief. What a firm can do is show every number was checked
> against the filing, by a process it doesn't control. That record is Vouch.

## 0:45 to 1:15, the check is a Chainlink CRE workflow

**On screen:** the terminal: the `cre workflow simulate` run for the lead claim,
the `[USER LOG]` lines (claim, "verdict: SLASH (wrong quarter …)", "verdict
for claim … written: 0x…"). Then tab B: the verdict transaction on the
Robinhood Chain explorer, the `Checked` and `Slashed` events.

**Say:**

> This is the check, running as a Chainlink Runtime Environment workflow. When
> a claim is posted, every node fetches the filing from SEC EDGAR, runs the
> same deterministic check, and they have to agree. The verdict goes through
> Chainlink's forwarder to the contract, with the hash of the exact filing it
> read. The contract takes verdicts from nowhere else. There's no admin key
> that can settle a dispute.

## 1:15 to 1:55, the agent's reasoning trail

**On screen:** back to tab A, scroll to **The agent's journal**. Open the
entry for the lead claim's stock. Walk the steps: Read, Refused (point at
the AI's claim in the list), Kept what held, Decided, Committed. Click
**Re-verify this trade** and let the green ticks fill in, ending with the
on-chain checks.

**Say:**

> The trading agent read every claim about this stock. It tried to trade on
> all of them, and the desk refused it each time it cited one that failed,
> naming the claim. What's left are claims that held. Its rules turn those
> into a position, and the whole reasoning, with every verdict and every
> refusal, is hashed on-chain with the trade. Re-verify redoes all of it in
> the browser and checks it against the chain. Cause, effect, and receipts.

## 1:55 to 2:15, what it proves, and what it doesn't

**On screen:** tab C, section 6, both lists.

**Say:**

> We're careful about what this proves. It proves exactly what was said,
> against which filing, what the check found, and what was done because of it.
> It doesn't prove anyone's honest belief, or that the filing itself is true.
> That's still the firm's job. Vouch gives the compliance officer the evidence.

## 2:15 to 2:30, close

**On screen:** the top of the live feed (the KPIs: claims, true, wrong,
agent trades and refusals), then the end card of the tour: "That's Vouch."

**Say:**

> Vouch. Every claim checked by Chainlink against the SEC filing. Every trade
> with its receipts. If it's wrong, it costs you. If you trade on it, the
> record shows why.

Cut.

---

## Things to get right

- **The first sentence is the claim, not an introduction.** No "Hi, I'm…"
  before 0:20; the face bubble is enough.
- Say **"Chainlink"** and **"CRE workflow"** out loud; show the CLI output.
  That is the Chainlink bounty's required evidence (CLI simulation).
- Say **"reasoning trail"** and click **Re-verify**. That is the RYO bounty's
  wording.
- Name **Regulation AC** and **FINRA Rule 2241**, once each, correctly. Don't say Vouch
  makes a firm "compliant"; say it is evidence for the firm's procedures.
- If the CRE round has not been run, record the same flow on
  `?feed=feed-local.json&journal` (a local devnet round) and, for 0:45, the
  `cre workflow build` output plus `bun test`. Say "simulated locally". Never
  show a local-devnet screen and call it testnet.
