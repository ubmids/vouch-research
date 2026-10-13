# What is new for BLI Legal Tech Hackathon 2

Vouch was first built for Arbitrum Open House Singapore (from 24 September
2026). Everything below was built for BLI Legal Tech Hackathon 2, on the
`first-place` branch, from 13 October 2026.

| Area | Before | Now |
|---|---|---|
| Who settles a claim | One verifier key called `clear`, `slash`, `resolve` | A **Chainlink CRE workflow**. `BondedClaims` implements `IReceiver.onReport` and accepts a verdict only from the Chainlink forwarder, from the configured workflow owner and name, and, once pinned, one compiled workflow id. There is no verifier key. |
| What a verdict records | Cleared or slashed, and a reason | Also *when*, *which workflow*, and the keccak256 of the filing bytes the workflow fetched from SEC EDGAR |
| Where the claim's words live | Off-chain, committed by hash | In the `Posted` event itself, so the workflow reads them from the chain and the record holds exactly what was said |
| The check | Python, run by the key holder | The same check, ported to TypeScript and run on every node of a Chainlink DON; parity with the Python on 3,249 claims, on Bun and on QuickJS |
| Stuck disputes | A challenge waited for the key | A challenge no verdict answers unwinds after 7 days and refunds both sides |
| The trading agent | Opened one position per claim, moving test tokens | Reads every claim about a stock, forms a thesis by fixed rules, is refused on-chain for each failed claim it cites, and opens one **paper** trade on what held |
| The record of a trade | Which claim ids backed it | A **journal**: the cited claims, the verdict on each (workflow, filing hash, transaction), the agent's per-claim reading, the refusals, and the hash of the whole reasoning record stored with the trade |
| Re-verifying | Recompute a claim's hash in the browser | Re-verify a whole trade in the browser (hashes, verdicts, refusals, a re-run of the agent's rules, receipts from the chain's RPC) or from the command line (also re-fetches every filing and re-runs the check) |
| Legal framing | None | [LEGAL.md](LEGAL.md): Regulation AC, FINRA Rules 2241 and 2210, Notice 24-09, the 2026 oversight report on AI agents, Rule 17a-4; what the record proves and does not prove; who is liable |
| Tests | 24 Foundry, 21 pytest | 37 Foundry, 31 pytest (+1 fork test), 19 Bun |

Not done for this event, and said so: the CRE-settled contracts are not yet
deployed on Robinhood Chain testnet, and `cre workflow simulate` has not been
run (it needs a Chainlink account login). `scripts/cre_round.sh` does both.
