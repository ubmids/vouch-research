# Vouch, demo script

Target 2:45, hard ceiling 3:00. The page is built to be the demo: the
"Follow one claim" story at the top is the video's spine, so you mostly read
the headline and press Next. Judges often stop at ninety seconds; by then they
have seen an AI caught and a trade refused.

Record at 1920x1080, browser full screen at https://vouch-feed.vercel.app, no
face cam, no music. One voice: yours, unhurried. Everything on screen is real:
Tesla's actual 10-Q, a claim a language model actually wrote, transactions on
Robinhood Chain testnet.

For Colosseum, which asks for a pitch video and a demo video: the pitch is the
deck (`docs/slides.pdf`) read over in about 2 minutes; the demo is this script.

---

## 0:00 to 0:15, the hook

**On screen:** the page as it loads, story on step 1.

**Say:**

> AI now writes a lot of the research people trade on. It's fast, it's fluent,
> and sometimes it's wrong about the numbers. Vouch makes being wrong cost money.
> Let me follow one claim.

---

## 0:15 to 1:15, one wrong claim, five steps

Press **Next** after each line. Let each step's headline sit for a beat.

**Step 1, "An AI read Tesla's quarterly report and wrote this."**

> This is Qwen, an open AI model running on my laptop. It read Tesla's latest
> quarterly report and wrote: depreciation for Q3 2026 was 1.37 billion.

**Step 2, "It put 25 USDG of its own money behind that sentence."**

> Every claim on Vouch has money behind it. Twenty-five dollars, locked in a
> contract on Robinhood Chain. True, it comes back. Wrong, it's gone.

**Step 3, "Vouch checked it against the actual filing."**

> Here's the claim, and here's the sentence from the filing. The number is
> right. But the filing's quarter ended in June. That's Q2, not Q3. The quote
> was real, word for word. The claim built on it wasn't.

**Step 4, "Wrong, so it paid."**

> So it lost the stake. Half to whoever caught it, half to a pool that protects
> readers. No moderator decided that. The check is mechanical, so anyone can
> re-run it and get the same answer.

Click the **"the slash on Robinhood Chain testnet"** link, show the transaction
on the explorer for two seconds, come back.

**Step 5, "A trading agent wanted to act on it. The contract said no."**

> And this is who it's for. A trading agent wanted to act on that claim. It
> trades through a desk that asks Vouch first, and the desk refused, on-chain.
> In this round it traded on all eighteen true claims and none of the
> thirty-two wrong ones.

---

## 1:15 to 1:35, the same sentence, told right

**On screen:** click **"The same sentence, told right"**, then Next through
steps 3 to 5 quickly.

**Say:**

> Same filing, same sentence, another analyst. This time the claim matches the
> filing exactly. It keeps its money, and the trading agent acts on it.

---

## 1:35 to 1:55, check one yourself

**On screen:** click **"Check a claim"** (top right). Click **"The AI's wrong
quarter"**, then **Check it**. Then click **"A true claim"**, **Check it**.

**Say:**

> Anyone can run the same check. This goes to Tesla's real 10-Q at the SEC,
> right now. Wrong quarter: slashed. The true version: cleared. Any AI agent can
> call this before it acts, through the contract, an API, or an MCP tool.

---

## 1:55 to 2:15, the whole round

**On screen:** close the dialog, click **"Skip to all 50 claims"**, scroll the
table briefly, then scroll to **The scoreboard**.

**Say:**

> Fifty claims across Tesla, Amazon, Palantir, Netflix and AMD, every one with
> its verdict in plain words. And the scoreboard: the analyst that told the
> truth kept everything. The ones that bent the numbers lost half. The AI got
> two wrong and paid for both.

---

## 2:15 to 2:40, why this is a business

**On screen:** deck slides 7 and 9 (For AI agents, Who pays).

**Say:**

> People are building AI agents that read research and trade on it. Those
> agents are only as safe as what they read. Vouch is the check they run first,
> and the place where being right is worth something. Next: mainnet on
> Robinhood Chain with USDG as the bond.

---

## 2:40 to 2:50, close

**On screen:** the story's end card, "That's Vouch."

**Say:**

> If it's wrong, it costs you. If it's right, it's on the record.

Cut.

---

## Things to get right

- Hit the explorer link once in step 4. It proves this is a real chain.
- Say "the quote was real, word for word" in step 3. That's the surprise: the
  AI didn't make up a sentence, it got the period wrong.
- Don't call it an oracle. It checks claims against filings; it doesn't report
  prices.
- If a judge asks what's trusted: one verifier key records dispute outcomes
  today, and the check is open for anyone to re-run.
