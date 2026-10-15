# Vouch, the BLI video: script and shot list

**Length: 3:30** (hard ceiling 5:00). **The hero is the record of reliance**: the
one page a compliance officer or counsel keeps. The video opens on it, takes it
apart, and closes on it. Everything on screen is in the Exhibit design
(design/DESIGN.md).

**Record after `bash scripts/after_login.sh` and `bash scripts/deploy_web.sh --go`**, so the
live page shows the testnet round settled by the CRE workflow. If the round
cannot be settled by 22 Oct, record the same shots from the local round
(`?feed=feed-local.json`) and use the SDK caption instead of the simulation one
(see "Captions").

## Before recording

- 1920x1080, browser full screen at 100% zoom, light theme, no bookmarks bar.
- Tabs, in order:
  - **A** `https://vouch-feed.vercel.app/?record=TSLA` (the record of reliance)
  - **B** `/?claim=<hero id>&view=claim` (the AI's wrong-quarter claim; its id is in docs/bli/TESTNET_ROUND.md)
  - **C** `docs/deck/bli.html` slide 3, or docs/bli/LEGAL.md section 2 on GitHub
  - **D** a terminal showing `cre/runs/<run>/claim-<hero id>.log` (the `[USER LOG]` lines), and **E** the explorer tab of the hero's verdict transaction
  - **F** `/?view=journal` (the agent's case files)
  - **G** `/?feed=feed-kol-real.json&view=journal` (the news checker on real posts)
- Your face in a small round corner bubble, bottom left, for the first 10 and last 10 seconds.
- One voice, unhurried. Pause half a second on every stamp.

## Overlays (all in `docs/assets/video/`, 1920x1080, from `bash scripts/build_assets.sh`)

| File | Use |
|---|---|
| `title.png` | the first second, full screen |
| `section-1.png` to `section-6.png` | transparent; a folder tab naming the part, top left, for its first 3 seconds |
| `lower-founder.png` | transparent; over the face bubble, 0:01 to 0:06 |
| `caption-simulation.png` | transparent; top right, whenever testnet CRE output is on screen |
| `caption-replayed.png` | transparent; top right, whenever the AI's claim is on screen |
| `caption-sdk.png` | transparent; replaces the simulation caption if you record the local round |
| `end.png` | the last 4 seconds, full screen |

## Shot list and script

| # | Time | Screen | Overlay | Action | Say |
|---|---|---|---|---|---|
| 1 | 0:00 | `title.png` | | hold 1 s | (nothing) |
| 2 | 0:01 | Tab A, top of the page | section-1, lower-founder, face bubble | slow scroll to "Exhibits refused" | "This is a record of reliance. An AI trading agent read ten claims about Tesla's quarterly report and wanted to trade on all of them. This page shows the three it was allowed to rely on, the seven it was refused, and why." |
| 3 | 0:20 | Tab A, "Exhibits refused", exhibit 6 row | caption-replayed | point at the red ring and the SLASHED stamp | "Exhibit six. An AI analyst wrote that Tesla's depreciation for Q3 was 1.37 billion dollars." |
| 4 | 0:30 | Tab B, the claim record | section-2, caption-replayed | point: statement, then the yellow sentence, then the third finding, then the stamp | "Here is the sentence it cited, from Tesla's own 10-Q. The figure is right. The quarter is not: that sentence covers the three months ended June 30. Ringed in red, the words it got wrong. The check slashed it, and its stake went to the readers' fund." |
| 5 | 0:55 | Tab B, scroll to the chain of custody | | point down the table | "And this is every hand the claim passed through: posted, checked against the filing from SEC EDGAR, slashed, and refused when the agent tried to rely on it." |
| 6 | 1:10 | Tab C, the four rules | section-3 | point at Reg AC, then 2241 | "Why this matters to lawyers. Regulation AC has a natural person certify the views in research. FINRA Rule 2241 requires that the facts in it are based on reliable information. AI now drafts research, and it can't certify a belief. What a firm can do is show that every number was checked, against what, and by a process it doesn't control." |
| 7 | 1:40 | Tab D, then Tab E | section-4, caption-simulation | the `[USER LOG]` lines, then the explorer's Checked and Slashed events | "That process is a Chainlink CRE workflow. Here it runs in the CRE CLI simulation on Robinhood Chain testnet: it fetches the filing, runs the check, and writes the verdict through Chainlink's forwarder, with the hash of the filing it read. The contract takes verdicts from nowhere else." |
| 8 | 2:10 | Tab F, the TSLA case file | section-5 | click **Re-verify this trade**, let the ticks fill | "Every trade keeps its reasons. Re-verify redoes all of it in your browser: every hash, every verdict, every refusal, and the agent's own rules." |
| 9 | 2:30 | Tab G, the tally, then one real post's record | | open the TSLA case file, then click the exhibit | "The same agent reads real public posts. Claude Haiku read a hundred and thirty about these five companies; the agent staked only on figures a sentence of the filing states, and every model reply is hashed into the record." |
| 10 | 2:55 | Tab F, click **Print the record of reliance**, then the print dialog's preview | section-6 | scroll to "What this record does not prove" | "Back to the record. It proves what was said, against which filing, and what was done because of it. It does not prove anyone's honest belief, or that the filing is true. That stays the firm's job. This gives it the evidence." |
| 11 | 3:20 | Tab A, top of the page, face bubble | | hold | "Vouch. If it's wrong, it costs you. If you trade on it, the record shows why." |
| 12 | 3:26 | `end.png` | | hold 4 s | (nothing) |

## Captions

- **SIMULATION** (`caption-simulation.png`): on shot 7, and on any screen showing
  testnet verdicts. Never say "a live network", "every node agreed" or "no admin
  key" over simulation footage: in simulation anyone can call the mock forwarder.
- **REPLAYED** (`caption-replayed.png`): on shots 3 and 4. The page labels the
  claim "replayed" too.
- **SDK test runtime** (`caption-sdk.png`): only if recording the local round;
  then shot 7 shows `bash scripts/sdk_round.sh` output and the script says "the
  workflow's own code in Chainlink's SDK test runtime", never "simulated on testnet".

## Things to get right

- The first words are about the record, not an introduction.
- Say **Chainlink**, **CRE workflow**, **reasoning trail**, **Regulation AC** and
  **FINRA Rule 2241** aloud, once each. Never say Vouch makes a firm "compliant".
- Every stamp you point at is on screen long enough to read (one second).
- Upload to YouTube (public or unlisted). Paste the link into
  `docs/bli/BUIDL.template.md` and run `python3 scripts/round_docs.py`.
- For the RYO and Chainlink bounty pages, cut 60-second clips from shots 8 to 9
  and shot 7 respectively.
