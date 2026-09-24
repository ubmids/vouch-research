# Submission copy, Arbitrum Open House Singapore (HackQuest)

Deadline 4 October 2026, 23:59 Singapore time (16:59 Lagos). Register by 2 October.
Judged on innovation, smart-contract quality, product-market fit, solving a real
problem, use of Arbitrum technology and presentation, with a bonus for novelty
and for USDG. Paste whichever of these the form asks for.

---

## Name

Vouch

## Tagline (under 80 characters)

Research on tokenised stocks that costs money to get wrong.

## One-liner

AI analysts stake stablecoin behind every claim about a tokenised stock; a
deterministic check against the SEC filing slashes anyone who gets a figure wrong.

## Short description (about 60 words)

Vouch is a research feed for tokenised stocks where every claim is bonded. An
analyst, usually an AI agent, quotes the company's SEC filing and stakes USDG
behind the figure. Anyone can challenge within a window, and the check is
deterministic: is this quote in this filing, with every figure exact? A wrong
claim loses its stake, half to the challenger, half to readers.

## Description

Tokenised stocks put equities on-chain, around the clock, for a new audience,
and more and more of the research that moves them is written by language
models. Language models are fluent and fast and sometimes wrong about numbers.
A summary that says $1.47 billion where the 10-Q says $1.37 billion reads
exactly like the truth, and today nobody pays for that mistake.

Vouch makes being wrong cost money, automatically.

1. **Bond.** An analyst deposits a stablecoin before it may publish.
2. **Claim.** Each claim cites an SEC filing by accession number, asserts one
   figure, and quotes the sentence that supports it. The words stay off-chain;
   their keccak256 hash goes on-chain with the stake, so a claim cannot be
   edited after it is checked.
3. **Challenge.** Claims are optimistic. Anyone can challenge within the window
   by posting a smaller deposit; an unchallenged claim clears itself.
4. **Settle.** The check is deterministic, so a dispute has one right answer. A
   false claim is slashed: the challenger gets their deposit back plus half the
   stake, and the rest goes to a pool that backs readers. A true claim keeps its
   stake and takes the challenger's deposit, so challenging is not free either.

**The part nobody else does.** Citation checkers accept near-matches to survive
the noise of turning a filing into text. In finance that tolerance is the hole:
change "50%" to "56%" in a real Tesla 10-Q sentence and it is still 99.3% similar
to the filing. Vouch only accepts a near-match when every figure in the quote,
with its scale, is exactly the filing's. In our last round, all ten doctored
quotes were between 99.1% and 99.7% similar to their filings: a 95% fuzzy
match would have passed every one. The figures rule slashed all ten.

**What is live.** Real 10-Qs from SEC EDGAR for the five stock tokens on
Robinhood Chain testnet (TSLA, AMZN, PLTR, NFLX, AMD). Four scripted analysts
that fail the four ways research fails (misreading a row, nudging a digit,
inventing a sentence), plus a language-model analyst on an open model (Qwen 2.5
7B, run locally through Ollama, so no hosted API sees the research before it is
staked), judged exactly like the others. A market round runs end to end on
chain, and the feed shows every claim, the filing passage it is about, a word
diff of the quote against the filing, and where the money went.

**Why Arbitrum and Robinhood Chain.** The stock tokens live on Robinhood Chain,
so research about them should settle where they trade. Settlement is many small
stake movements, which needs Arbitrum's fees. USDG is the bond on mainnet.

**Honest about trust.** Today one verifier key records dispute outcomes. The
check is open source and deterministic, so anyone can re-run it and prove the
verifier wrong, and the roadmap moves it on-chain: filing hashes committed at
first citation, and the check re-executed in Stylus.

## Who pays

Venues and protocols that list tokenised stocks, and the traders on them, pay
for research they can rely on; analysts earn by being right, and lose their
stake by being wrong. The reader pool, funded by slashed stakes, insures
subscribers against cleared claims that later prove wrong. The first customers
are front-ends and trading agents on Robinhood Chain that want a machine-
readable feed of checked facts about the equities they list.

## How it was built

Solidity contract (`BondedClaims`) with Foundry, 15 tests including fuzzed
conservation of money through disputes. Python agent layer with web3.py: an
SEC EDGAR client, the deterministic verifier, fact extraction from real 10-Qs,
five analysts, and a market loop that runs on anvil, Robinhood Chain testnet or
Arbitrum Sepolia. A static web feed on Vercel.

## Challenges

The verifier we carried over accepted near-matches at 95% similarity, but its
comparison window was misaligned, so near-matches almost never reached 95% and
the tolerance quietly did nothing. Fixing the alignment exposed the real
problem: correctly aligned, a quote with one percentage changed scores 99.3%.
The figures rule came out of that. The other was the SEC itself: EDGAR refuses
automated requests without a named contact, and every company phrases its
figures differently, which is exactly the job an AI analyst does best and the
reason it needs checking.

## What's next

Mainnet on Robinhood Chain with USDG; filing hashes on-chain and the check in
Stylus; 8-Ks, 10-Ks and S-1s; a subscriber API that serves only cleared claims,
insured by the reader pool. The KPI we would propose: claims checked per week,
and the share of analyst capital that survives a month.

## Prior work, disclosed

The staking and slashing idea and the first verifier come from Vouch on Casper
(github.com/ubmids/vouch, June 2026). Everything in this repository was built
for this buildathon from 24 September 2026; the README lists what is new.

## Tech

Solidity, Foundry, Python, web3.py, SEC EDGAR, Ollama (Qwen 2.5 7B), Robinhood
Chain testnet, Arbitrum Sepolia, Vercel.

## Links

- Repository: https://github.com/ubmids/vouch-research (public at submission)
- Live feed: https://vouch-feed.vercel.app
- Contract on Robinhood Chain testnet: see `deployments/46630.json` after `scripts/testnet.sh`
- Demo video: (paste once recorded, script in docs/DEMO_SCRIPT.md)

## Before submitting, the checklist

- [ ] Test ETH from faucet.testnet.chain.robinhood.com to 0x950d00BA837cD285e6d8a0F3f02d69434a775808
- [ ] `bash scripts/testnet.sh` (deploys, runs the round, republishes the feed with explorer links)
- [ ] Registered on HackQuest before 2 Oct
- [ ] Demo video recorded to DEMO_SCRIPT.md, uploaded, public
- [ ] Repo flipped public, after a final secret sweep
- [ ] Submitted before 4 Oct 23:59 SGT
