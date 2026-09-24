# Vouch, demo script

Target 2:45, hard ceiling 3:00. Judges often stop at ninety seconds, so the
caught lie has to be on screen before the first minute is out.

Record at 1920x1080, browser full screen, no face cam, no music. One voice:
yours, unhurried. Everything on screen is real: real 10-Qs, real claims, real
transactions. Before recording, run `bash scripts/testnet.sh` so the feed shows
Robinhood Chain testnet transactions with explorer links, not the local devnet.

For Colosseum, which asks for a pitch video and a demo video: the pitch is
slides 1 to 4 and 6 to 9 of `docs/slides.pdf` read over, 2 minutes; the demo
is this script.

---

## 0:00 to 0:20, the lie

**On screen:** slide 2, the two sentences, red $1.47 billion over green $1.37
billion.

**Say:**

> This is a sentence from Tesla's last quarterly filing. And this is the same
> sentence as an AI summary wrote it. One digit is different. They read exactly
> the same, and nobody pays for the difference.
>
> Vouch makes being wrong about a stock cost money.

---

## 0:20 to 1:05, it gets caught

**On screen:** vouch-feed.vercel.app. It opens on a slashed claim. Let the
inspector sit for a beat.

**Say:**

> This is the feed. Every row is a claim about one of the stock tokens on
> Robinhood Chain: Tesla, Amazon, Palantir, Netflix, AMD, each checked against
> the company's real 10-Q from the SEC.
>
> This analyst claimed capital expenditures of eight point two nine billion. Its
> quote is ninety-nine point five percent identical to the filing. Any fuzzy
> citation check passes that. But the filing says eight point two eight, and
> Vouch requires every figure to match exactly. So the stake is gone: half to
> whoever caught it, half to a pool that backs readers. Here is the transaction.

**Point at:** the diff (red in the quote, green in the filing), the similarity
bar sitting past the 95% line, "figures: differ from the filing", the money
flow, the explorer link. Click the link and show the transaction on the
Robinhood Chain explorer for two seconds, then come back.

---

## 1:05 to 1:35, every way research goes wrong

**On screen:** click a Misreader row, then a Fabricator row, then a Diligent
row.

**Say:**

> A misreader quotes the right sentence and claims the wrong number from it.
> Slashed. A fabricator writes a sentence the filing never contained; the
> closest passage in the whole document is a quarter similar. Slashed. And an
> analyst that quotes the filing word for word keeps its stake.

Then click Qwen's claim #6, marked "Right number, wrong quarter":

> And this one is a language model, running locally on an open model. Its quote
> is real, word for word. But it told readers the figure was for Q3, and the
> quarter ended in June. When we first ran it, its quotes were real ten times out
> of ten and half its summaries still got the period wrong. So Vouch checks the
> claim as written, not just the quote. The model pays like anyone else.

---

## 1:35 to 1:55, agents that refuse

**On screen:** still on claim #6, point at "The trading agent" box and click its
"refused trade" link: a reverted transaction on the Robinhood Chain explorer.

**Say:**

> This is who it's for. A trading agent tried to act on that claim. It trades
> through a desk that asks Vouch first, and the desk refused, on-chain. It acted
> on every cleared claim and refused all the others. Any agent can ask the same
> question before it acts: through the contract, an API, or an MCP tool.

---

## 1:55 to 2:15, the mechanism

**On screen:** scroll to "How it works" and the analyst leaderboard.

**Say:**

> Analysts bond a stablecoin before they can publish. Each claim puts part of
> that bond at stake and commits its words by hash, so it cannot be edited
> after it is checked. Claims are optimistic: anyone can challenge within the
> window, and because the check is deterministic, every dispute has one right
> answer. A challenger who is wrong loses their deposit to the analyst, so
> challenging is not free either.
>
> After one round the leaderboard says it all: the analyst that told the truth
> still has everything it bonded. The ones that didn't have half.

---

## 2:15 to 2:40, why this is a business

**On screen:** slide 7, then slide 8.

**Say:**

> Venues and trading agents that list tokenised stocks need facts they can rely
> on, and more of that research will be written by models every month. Vouch is
> the layer where being right is worth something and being wrong costs
> something. Next is mainnet on Robinhood Chain with USDG as the bond, and the
> check itself moving on-chain in Stylus.

---

## 2:40 to 2:50, close

**On screen:** slide 9.

**Say:**

> If it's wrong, it costs you. If it's right, it's on the record.

Cut.

---

## Things to get right

- The explorer click proves it is on a real chain. Do it once, fast.
- Say the similarity number out loud. "Ninety-nine point five percent, and
  still a lie" is the line people remember.
- Do not call it an oracle. It checks claims against filings; it does not
  report prices.
- Show the trust assumption if asked: one verifier key records outcomes today,
  and the check is open for anyone to re-run.
