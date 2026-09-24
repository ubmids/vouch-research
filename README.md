# Vouch

**Research on tokenised stocks that costs money to get wrong.**

AI analysts publish claims about the companies behind the stock tokens on
Robinhood Chain: *Tesla's depreciation was $1.37 billion last quarter.* Every
claim carries a stablecoin stake and the exact sentence from the SEC filing
that supports it. Anyone can challenge it. The check is deterministic, so a
dispute has one right answer: is this quote in this filing, with every figure
exactly as filed? A wrong claim loses its stake, half to whoever caught it and
half to a pool that backs readers.

Live feed: **https://vouch-feed.vercel.app**

## The problem

Tokenised stocks put equities on-chain, 24/7, for a new audience. The research
that moves those markets is increasingly written by language models, and
language models are fluent, fast and sometimes wrong about numbers. A summary
that says $1.47 billion where the filing says $1.37 billion reads exactly like
the truth.

Nobody pays for that mistake today. A research feed has no stake in being right.

## Why it has to be on-chain

The whole product is that being wrong costs something, automatically, without
trusting the publisher:

- the stake is locked by a contract, so an analyst cannot withdraw it while a
  claim is live;
- slashing moves real money to the challenger and the reader pool, in the same
  transaction as the verdict;
- the claim's words are committed by hash when it is posted, so it cannot be
  edited after someone checks it;
- every analyst's record (cleared, slashed, bond left) is public and permanent.

Take the chain away and it is a blog with a moderation policy.

## How it works

```
 SEC EDGAR ──► analyst (AI or human) ──► claim: value + verbatim quote + filing
                                              │ keccak256 → on-chain, with a stake
                                              ▼
          anyone can challenge within the window, with a deposit
                                              ▼
       deterministic check: is the quote in the filing, every figure exact?
             │                                          │
          true: stake back,                      false: stake slashed,
          challenger's deposit to the analyst    half to the challenger,
                                                 half to the reader pool
     unchallenged after the window: clears itself, callable by anyone
```

**The check that matters.** Citation checkers usually accept a near-match, to
survive the noise of turning HTML into text. In a financial filing that
tolerance is the hole: change "50%" to "56%" in a real Tesla sentence and it is
still **99.3% similar** to the filing. Vouch accepts near-matches only when every
figure in the quote, and its scale, appears exactly in the matching passage of
the filing. In a round over five real 10-Qs, all ten doctored quotes scored
between 99.1% and 99.7% similar, so a 95% fuzzy match would have passed every
one; the figures rule slashed all ten. `agent/vouchrh/verifier.py`, tested in `tests/test_verifier.py`.

## What is here

| Path | What |
|---|---|
| `src/BondedClaims.sol` | The market: bond, post, challenge, finalize, resolve, slash, withdraw |
| `src/MockUSDG.sol` | Test stand-in for Paxos USDG on testnets where it is not deployed (6 decimals, like USDG) |
| `test/BondedClaims.t.sol` | 15 Foundry tests, including fuzzed conservation of money through disputes |
| `agent/vouchrh/edgar.py` | SEC EDGAR client: ticker to latest 10-Q, cached, fair-access compliant |
| `agent/vouchrh/verifier.py` | The deterministic check |
| `agent/vouchrh/analysts.py` | Fact extraction, plus four scripted analysts that fail in the four ways research fails |
| `agent/vouchrh/llm.py` | A language-model analyst on an open model (Qwen 2.5 7B via Ollama), judged like everyone else |
| `agent/vouchrh/market.py` | One round, end to end, on any EVM chain |
| `agent/vouchrh/publish.py` | Turns a round into the feed the page shows |
| `web/` | The feed: every claim, the filing passage, a word diff, the check, the money |
| `scripts/testnet.sh` | The real round on Robinhood Chain testnet or Arbitrum Sepolia |

The four scripted analysts exist so the verifier is seen catching each way a
claim goes wrong: **Diligent** quotes and asserts correctly; **Misreader**
quotes correctly and asserts another figure; **Embellisher** nudges one digit
and doctors the quote to match; **Fabricator** writes a plausible sentence the
filing never contained. The language-model analyst gets no special treatment.

## Run it

Needs [Foundry](https://getfoundry.sh) and Python 3.10+.

```bash
forge test                                            # the contract
python3 -m venv .venv && .venv/bin/pip install "web3>=7,<8" pytest
PYTHONPATH=agent .venv/bin/python -m pytest tests     # verifier + a full round on anvil

anvil &                                               # a local chain
PYTHONPATH=agent .venv/bin/python -m vouchrh.market \
  --key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
PYTHONPATH=agent .venv/bin/python -m vouchrh.publish feed/feed.json web/feed.json
python3 -m http.server -d web 8000                    # the feed at localhost:8000
```

EDGAR requires a contact in every request's User-Agent; set
`VOUCH_SEC_CONTACT="Your Name you@example.com"`. Add `--model` to include the
language-model analyst (`ollama pull qwen2.5:7b-instruct` first).

On a public chain, with a funded testnet wallet in `~/.config/vouch-rh/`:

```bash
bash scripts/testnet.sh                          # Robinhood Chain testnet (chain 46630)
CHAIN=arbitrum-sepolia bash scripts/testnet.sh   # Arbitrum Sepolia (421614)
```

## What is trusted, today

Honestly stated, because a trust layer that hides its own trust assumptions is
not one:

- **The verifier key records dispute outcomes.** The check is deterministic and
  open source, so anyone can re-run it and see whether the verifier lied, but
  today one key submits the result. The path out is re-executing the check
  on-chain in Stylus (the check is string matching over a committed filing
  hash) or an optimistic second round that slashes a dishonest verifier.
- **The filing text is fetched off-chain.** Claims cite the SEC accession
  number; the verifier fetches that document from EDGAR. Committing a hash of
  the filing text on-chain at first citation is the next step.
- **The bond token on testnet is a mock.** On mainnet it is Paxos USDG.

## Roadmap

1. Mainnet on Robinhood Chain with USDG, with the market at one address.
2. Filing hashes on-chain at first citation; verifier re-execution in Stylus.
3. More than 10-Qs: 8-K earnings releases, 10-K risk factors, S-1s.
4. A reader API: protocols that list tokenised stocks subscribe to cleared
   claims only, and the reader pool insures them.
5. The KPI we would set: claims checked per week, and the share of analyst
   capital that survives a month.

## Prior work

The staking and slashing idea and the first version of the verifier come from
**Vouch on Casper** ([github.com/ubmids/vouch](https://github.com/ubmids/vouch)),
built by the same author for the Casper Agentic Buildathon in June 2026. That
version attested sample invoice and bond documents, in Rust (Odra) on Casper,
with the verifier's first version and a scripted worker market.

Everything in this repository was built for Arbitrum Open House Singapore,
from 24 September 2026: the Solidity contract with open challenges and
optimistic finalization, SEC EDGAR as the source of truth, the figures rule and
the corrected fuzzy alignment in the verifier, the analysts, the language-model
analyst, the market loop, and the web feed.

## Licence

MIT.
