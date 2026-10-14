# What is new for BLI Legal Tech Hackathon 2

Vouch was first built for Arbitrum Open House Singapore (from 24 September
2026). Everything below was built for BLI Legal Tech Hackathon 2, on the
`first-place` branch, from 13 October 2026.

| Area | Before | Now |
|---|---|---|
| Who settles a claim | One verifier key called `clear`, `slash`, `resolve` | In the new contract, a **Chainlink CRE workflow**: `BondedClaims` implements `IReceiver.onReport` and accepts a verdict only from the Chainlink forwarder, from the configured workflow owner and name, and, once pinned, one compiled workflow id. There is no verifier key. (Not yet deployed; on a simulation market the forwarder is Chainlink's mock, which anyone can call.) |
| What a verdict records | Cleared or slashed, and a reason | Also *when*, *which workflow*, and the keccak256 of the filing bytes the workflow fetched from SEC EDGAR (less the one script tag SEC's CDN adds, whose path changes over time) |
| Where the claim's words live | Off-chain, committed by hash | In the `Posted` event itself, so the workflow reads them from the chain and the record holds exactly what was said |
| The check | Python, run by the key holder | The same check, ported to TypeScript as the CRE workflow's handler (on a DON every node would run it; so far it has run in Chainlink's SDK test runtime, under QuickJS and as a WASM build, not on a DON); parity with the Python on 3,249 claims, on Bun and on QuickJS |
| Stuck disputes | A challenge waited for the key | A challenge no verdict answers unwinds after 7 days and refunds both sides; a claim that cleared only by default cannot back a trade |
| Where a slashed stake goes | Counted in `readerPool`, never paid out | A **readers' fund** fixed at deploy (payees and shares); each payee withdraws its share with `claimReaderShare()`. On the test market the deployer stands in |
| Challenger bounty | Half the slashed stake | None: the workflow checks every claim, so a bounty would only pay an analyst to challenge their own wrong claim (found in review). The whole stake goes to the readers' fund |
| The trading agent | Opened one position per claim, moving test tokens | Reads every claim about a stock, forms a thesis by fixed rules, is refused on-chain for each failed claim it cites, and opens one **paper** trade on what held |
| The record of a trade | Which claim ids backed it | A **journal**: the cited claims, the verdict on each (workflow, filing hash, transaction), the agent's per-claim reading, the refusals, and the hash of the whole reasoning record stored with the trade |
| Re-verifying | Recompute a claim's hash in the browser | Re-verify a whole trade in the browser (hashes, verdicts, refusals, a re-run of the agent's rules, receipts from the chain's RPC) or from the command line (also re-fetches every filing and re-runs the check) |
| Market voices | None | KOL mode: 20 written fixture posts by fictional accounts, read by fixed rules (token, figure, period, sentiment, conviction, urgency), checked as staked stories against the 10-Q; only the ones that held move the agent |
| Running a round | One script, failures swallowed | `cre_round.sh --preflight` (wallet, login, SEC, the AI's hero claim, the WASM build, before any gas), a dry run without broadcast, no silent failures, `env.txt` in the evidence folder. A fallback round whose verdicts come from the workflow's handler in the CRE SDK test runtime (`sdk_round.sh`) |
| Legal framing | None | [LEGAL.md](LEGAL.md): Regulation AC, FINRA Rules 2241 and 2210, Notice 24-09, the 2026 oversight report on AI agents, Rule 17a-4; what the record proves and does not prove; who is liable |
| Tests | 24 Foundry, 21 pytest | 57 Foundry, 62 pytest (+1 fork test), 24 Bun |

Not done yet, and said so: the CRE-settled contracts are not deployed on
Robinhood Chain testnet, and `cre workflow simulate` has not been run. Both
wait on Subomi's Chainlink account (`cre login` or an API key) and the round
(`scripts/cre_round.sh`). Nothing has run on a DON; a live deployment also
needs answers on the gateway's User-Agent and response-size limits
([cre/README.md](../../cre/README.md#production)).
