# Vouch, BLI demo script (2:30)

Hard ceiling 3:00; aim for 2:30. **The payoff is on screen by 0:20**: an AI's
wrong claim, slashed by the check, and a trading agent refused, on-chain.
Then why lawyers should care, then the Chainlink CRE workflow, then the journal.

**Which round you film decides two captions.** Everything said aloud below is
true for both; the captions say which one is on screen.

| | Round **A** (after `cre login` and `scripts/cre_round.sh`) | Round **B** (fallback, works today) |
|---|---|---|
| Feed | `https://vouch-feed.vercel.app/?journal` after `vercel deploy --prod` | `web/` served locally (`python3 -m http.server -d web 8000`), `http://localhost:8000/?feed=feed-local.json&journal` |
| Caption, whole video | "Robinhood Chain testnet · Chainlink CRE CLI simulation" | "Local devnet · the CRE workflow's code in Chainlink's SDK test runtime" |
| 0:45 terminal | `cre/runs/<run>/claim-<id>.log` (the `[USER LOG]` lines) | `bash scripts/sdk_round.sh` output, then `cre workflow build` (the WASM hash) |
| 0:45 caption | **SIMULATION** | **SDK TEST RUNTIME, NOT A CRE SIMULATION** |
| The AI's claim | written live by Qwen if the preflight dry run reproduced it; otherwise re-posted from 24 Sep (the page labels it "replayed") | re-posted from 24 Sep, labelled "replayed" |

**Before recording**

- Round A: `bash scripts/cre_round.sh --preflight`, then `bash scripts/cre_round.sh`,
  then publish (`cd web && vercel deploy --prod`). Round B: `bash scripts/sdk_round.sh`.
- Have three tabs ready: **A** the feed above with `?journal`, **B** (round A
  only) the explorer tab of the lead claim's verdict transaction, **C**
  `docs/bli/LEGAL.md` on GitHub, scrolled to section 6.
- A terminal with the 0:45 output from the table.
- 1920x1080, browser full screen. **Your face in a small corner bubble for the
  first 10 seconds and the last 10** (a real person on camera). One voice, unhurried.

---

## 0:00 to 0:20, the payoff first

**On screen:** tab A. It opens on the AI's claim in the inspector: the claim
says Q3, the filing's sentence says June, **Slashed**, and "It was refused"
in the trading-agent box. Point at each as you say it.

**Say:**

> An AI analyst wrote that Tesla's depreciation for Q3 was 1.37 billion
> dollars. Tesla's own filing says that quarter ended in June. Vouch's check,
> a Chainlink CRE workflow, caught it against the SEC filing and took the AI's
> 25-dollar stake. And the trading agent that tried to act on it? Refused, on-chain.

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

**On screen:** the terminal output from the table, with the caption from the
table (**SIMULATION**, or **SDK TEST RUNTIME, NOT A CRE SIMULATION**) for the
whole segment. Round A: the `[USER LOG]` lines (claim, "verdict: SLASH (wrong
quarter …)", "verdict for claim … written: 0x…"), then tab B, the verdict
transaction on the Robinhood Chain explorer with the `Checked` and `Slashed`
events (the explorer shows Chainlink's mock forwarder: that is expected).

**Say (round A):**

> This is the check as a Chainlink Runtime Environment workflow, in the CRE
> CLI simulation: one node runs the exact workflow, fetches the filing from SEC
> EDGAR, and writes the verdict through Chainlink's test forwarder, with the
> hash of the filing it read. On a live network, the forwarder only accepts
> reports the nodes signed, and the contract checks the workflow's owner, name
> and pinned id.

**Say (round B):**

> This is the check as a Chainlink Runtime Environment workflow. Here its own
> code runs in Chainlink's SDK test runtime, on a local chain: it fetches the
> filing, runs the check, and builds the report the contract takes. The CLI
> simulation on testnet is the next step. On a live network, the forwarder
> only accepts reports the nodes signed, and the contract checks the
> workflow's owner, name and pinned id.

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

> Vouch. Every claim checked against the SEC filing. Every trade with its
> receipts. If it's wrong, it costs you. If you trade on it, the record shows why.

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
- Never say "every node", "the network agreed" or "no admin key" over a
  simulation: on a simulation market anyone can call the mock forwarder.
- Round B is not a CRE CLI simulation and does not meet the Chainlink bounty's
  minimum on its own; say "SDK test runtime", never "simulated on testnet".
  Never show a local-devnet screen and call it testnet.
- Optional, for the RYO judges (10 s, cut from 1:55 if needed):
  `?feed=feed-kol.json`, one wrong post refused. Say: "The same agent works as a
  news checker on posts by market voices. These twenty are written fixtures;
  a loud post with the wrong quarter moves nothing."
