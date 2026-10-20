# Vouch, the narrated BLI video

Voice: ElevenLabs (Subomi's approved voice). Length 202.5s. Recorded on the local round (web/feed-local.json).

**title**

00:00:00  Hey, I'm Subomi. This is Vouch, my entry for the BLI Legal Tech hackathon.

**feed**

00:00:07  So, here's the problem. AI writes more and more of the research people trade on, and it gets numbers wrong in a really convincing way. Right figure, wrong quarter.

00:00:20  That's what Vouch is for. Every claim, human or AI, gets checked against the company's SEC filing. A wrong claim costs its author a stake, and a trading agent can only act on the claims that held.

**record**

00:00:35  So this is a record of reliance. A trading agent read ten claims about Tesla's quarterly report and tried to trade on all of them. Three passed the check. Seven were refused.

00:00:48  Exhibit six. An AI analyst, Qwen 2.5 7B, wrote that Tesla's depreciation for Q3 was $1.37 billion.

**claim**

00:01:00  The sentence it cited really is in Tesla's 10-Q, and the figure is right. But that sentence covers the three months ended June 30th. That's Q2. The claim says Q3.

00:01:14  So the check slashed it. Its 25 USDG stake, test tokens on a local devnet, went to the readers' fund.

00:01:23  And here's the chain of custody. Posted, checked against the filing from SEC EDGAR, slashed, then refused when the agent tried to cite it.

**deck**

00:01:33  Why does this matter to lawyers? Regulation AC has a natural person certify the views in research. FINRA Rule 2241 wants its facts based on reliable information. A model can't certify a belief. But a firm can show every number was checked, against what, by a process it doesn't control.

**terminal**

00:01:57  That process is a Chainlink CRE workflow. Here its own code ran in Chainlink's SDK test runtime, on a local devnet. For each claim it reads the filing, runs the check, and builds the verdict, with a hash of the filing it read.

**journal**

00:02:16  Every trade keeps its reasons. Here's the agent's case file for Tesla: what it read, what it was refused, what it kept, and its rule. That reasoning trail is hashed into the trade.

00:02:30  And re-verify redoes all of it in the browser. Every hash, every verdict, every refusal.

**kol**

00:02:38  The agent reads real posts too. Claude Haiku read a hundred and thirty public Mastodon posts. Sixteen stated a figure the 10-Q could confirm, and the agent staked only on the three a filing sentence actually states.

**limits**

00:02:55  Back to the record. It shows what was said, against which filing, and what was done because of it. It doesn't prove honest belief, or that the filing is true. That stays the firm's job.

**close**

00:03:09  So that's Vouch. If a claim is wrong, whoever made it pays. If you trade on it, the record shows why. Thanks for watching.

## Rebuild

`python3 scripts/video/narrated.py` (a Python with playwright). Lines live in `scripts/video/lines.json`: `text` is the caption, `tts` what the voice is sent when a word needs spelling out. Audio is cached outside git in `~/Desktop/hackathons/vouch-video/voice/`, so a rebuild spends no ElevenLabs characters. Outputs `vouch-narrated.mp4` and `.srt` in `~/Desktop/hackathons/vouch-video/`.

Recorded on the local round (`web/feed-local.json`), so the CRE part carries the SDK test runtime caption. If the testnet round is settled by the CRE CLI simulation before submitting, the CRE line and caption must change (docs/bli/DEMO_SCRIPT.md, "Captions").
