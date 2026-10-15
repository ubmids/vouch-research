# Vouch, the 5-minute live pitch

For a finalist pitch (last year BLI ran a virtual pitch day for 13 finalists).
Share one browser window: the deck (docs/bli/deck.pdf) and the live feed in a
second tab. Speak to lawyers first; the mechanism comes second.

| Time | On screen | Say |
|---|---|---|
| 0:00 to 0:30 | Deck slide 1 | "Courts have sanctioned lawyers again and again for briefs citing cases an AI invented. Investment research is now drafted by the same models, with the same failure. Vouch is a citation check for AI-written research." |
| 0:30 to 1:15 | Feed, `?claim=6&view=claim` | Exhibit 6. "An AI wrote that Tesla's depreciation for Q3 was $1.37 billion. Here is the sentence it cited, from Tesla's own 10-Q: that figure is for the quarter ended June 30. Ringed in red, the words it got wrong. The verdict: slashed. Its stake went to the readers' fund, and a trading agent that tried to rely on it was refused, on-chain." |
| 1:15 to 2:00 | Deck slide 3 | "The rules are written for people. Regulation AC has a natural person certify the views. FINRA Rule 2241 requires that purported facts in research be based on reliable information. A model cannot certify a belief. A firm can show that every number was checked, against what, and by a process it does not control." |
| 2:00 to 2:45 | Deck slide 5, then the testnet round page | "The check is a Chainlink CRE workflow: it fetches the filing from SEC EDGAR, runs a deterministic check, and writes the verdict through Chainlink's forwarder. The contract accepts no other source; there is no verifier key." Show a verdict transaction on the explorer. |
| 2:45 to 3:30 | Feed, the agent's case file, then **Print the record of reliance** | "Every trade keeps its reasons: what it read, what was refused, what it relied on. This page is the record of reliance, one page counsel can keep, with the steps to re-check every line." |
| 3:30 to 4:15 | Deck slide 7 | "We are careful about what this proves. It proves the exact words, the filing checked, and that a trade relied only on what held. It does not prove a view was honestly held, a reasonable basis, or that the filing is true. That remains the firm's job; Vouch gives it the evidence." |
| 4:15 to 5:00 | Deck slide 8, then 11 | "Compliance teams publish only what cleared. Newsletters show their work. Agent operators get the guardrail and the trace FINRA asks for. Next: a live Chainlink network, mainnet, and one compliance team piloting cleared-only publication." Close: "If it's wrong, it costs you. If you trade on it, the record shows why." |

## Likely questions

- **Why stake, if the check is public?** The stake turns checking into a
  commitment: an AI that checks before it publishes costs nothing; one that
  does not, pays. For a regulated firm the stake is optional; the check and the
  record are the compliance product.
- **Where does a slashed stake go?** To a readers' fund whose payees are fixed
  when the market is deployed; each withdraws its own share. Who those payees
  should be in production is a legal choice we flag, not one we make.
- **Is the stake a security, a swap or a wager?** Open, and flagged in
  docs/bli/LEGAL.md section 8.
- **What can the check not see?** Tables. It reads sentences, so a figure the
  filing gives only in a table is neither confirmed nor refuted, and the agent
  does not stake on it.
- **Is this live on Chainlink?** It runs as a CRE CLI simulation on Robinhood
  Chain testnet. A live network needs deploy access and SEC's User-Agent rule
  solved at the gateway; both are named in cre/README.md.
