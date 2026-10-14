# Owner to-do, by date

Only the things that need Subomi: an account, a browser, a wallet, a camera,
a person, or a decision. Everything else is done on `first-place`. The how for
steps 1 to 4 is in [CHECKLIST.md](CHECKLIST.md). All of it runs on the Mac.

| By | What | Exact steps | Done when |
|---|---|---|---|
| **15 Oct** | Chainlink sign-up | Create a free account at https://app.chain.link | You can log in there |
| **16 Oct** | bun, and the CRE CLI logged in | `curl -fsSL https://bun.sh/install \| bash`, new terminal, then in the repo `~/.cre/bin/cre login` (or `export CRE_API_KEY=<key>` from app.chain.link → Account Settings; never commit it) | `~/.cre/bin/cre whoami` prints your account |
| **16 Oct** | Faucet, only if needed | `ANALYST_MODEL=replay bash scripts/cre_round.sh --preflight` says whether the wallet is short. If so, fund `0x950d00BA837cD285e6d8a0F3f02d69434a775808` at https://faucet.testnet.chain.robinhood.com | The preflight prints only ✓ lines |
| **18 Oct** | The CRE round on Robinhood Chain testnet | `ANALYST_MODEL=replay bash scripts/cre_round.sh` (20 to 40 min). Commit `cre/runs/<run>/`, `feed/feed.json`, `web/feed.json`, `deployments/46630.json`, push, and hand the run folder back so the "pending" lines get replaced | `env.txt` says `verdicts_written: N of N` |
| **18 Oct** | Start the lawyer or compliance quote | Ask one securities or compliance lawyer, or a research publisher, to read [LEGAL.md](LEGAL.md) and give one sentence with name and role, ideally on camera. Cogent Law is a sponsor and BLI offers legal mentors: the event's Discord is the natural place to ask. Your call who to contact | |
| **20 Oct** | The name | Keep "Vouch" (taken on HackQuest) or rename; the audit recommends **AsFiled**, runner-up CiteBond. Search the DoraHacks BUIDL list by hand first (scripts are blocked there). If renaming, say so and it is one pass: `grep -rln "Vouch" docs/bli web README.md` lists every file | Name chosen |
| **20 Oct** | Founder bio | Fill the two lines marked `[FOUNDER]` in [BUIDL.md](BUIDL.md) (who you are, why you can build this) | No `[FOUNDER]` left |
| **22 Oct** | The quote, in hand | Paste it into BUIDL.md's "Who has read it" line, or delete that line | |
| **23 Oct** | Publish the page | `cd web && vercel deploy --prod` | `/?journal` opens on the live site |
| **25 Oct** | Video | Record to [DEMO_SCRIPT.md](DEMO_SCRIPT.md), round A. Upload to YouTube (public or unlisted) | Link pasted into BUIDL.md |
| **25 Oct** | Repo public | Secret sweep (CHECKLIST step 7), then make `ubmids/vouch-research` public with `first-place` as default branch | Repo opens logged out |
| **29 Oct** | DoraHacks BUIDL | A Discord, WhatsApp or WeChat handle for the form. Paste BUIDL.md, attach deck.pdf and the video, select the RYO-CHAN and Chainlink CRE bounties | Draft saved |
| **30 Oct** | Submit | Submit, then open every link logged out | Submitted |
| **5 Nov to 5 Dec** | Be free for a live finalist pitch | Judging runs 5 Nov to 5 Dec; last year 13 finalists pitched live (15 Nov 2025). Keep mid-November evenings (US Eastern) free and have a 5-minute version of the demo ready | |
| **12 Dec** | Awards | | |
