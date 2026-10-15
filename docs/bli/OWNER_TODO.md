# Owner to-do, by date

Only the things that need Subomi: an account, a browser, a wallet, a camera,
a person, or a decision. Everything else is done on `first-place`. The how for
steps 1 to 4 is in [CHECKLIST.md](CHECKLIST.md). All of it runs on the Mac.

| By | What | Exact steps | Done when |
|---|---|---|---|
| **15 to 16 Oct** | Chainlink CRE account, and the CLI logged in (**the one blocker**) | Create a free account at https://app.chain.link (2FA is required), then in the repo run `~/.cre/bin/cre login` and sign in in the browser it opens. An API key is not an alternative: the docs reserve API keys for accounts with deploy access. bun is already installed (`~/.bun/bin`, 1.4.3) | `~/.cre/bin/cre whoami` prints your account |
| ~~16 Oct~~ | ~~Design direction~~ | Done 15 Oct: Exhibit. The name stays Vouch | |
| **16 Oct** | Who runs the round | Say whether Claude may run `scripts/cre_round.sh` itself once you are logged in. It spends only test ETH from the existing test wallet | Yes or no |
| ~~16 Oct~~ | ~~Faucet~~ | Not needed: the wallet held 0.0062 test ETH on 15 Oct, about twice a round. The preflight still checks it | |
| **18 Oct** | The CRE round on Robinhood Chain testnet | `ANALYST_MODEL=replay bash scripts/cre_round.sh` (20 to 40 min). Commit `cre/runs/<run>/`, `feed/feed.json`, `web/feed.json`, `deployments/46630.json`, push, and hand the run folder back so the "pending" lines get replaced | `env.txt` says `verdicts_written: N of N` |
| **18 Oct** | Start the lawyer or compliance quote | Ask one securities or compliance lawyer, or a research publisher, to read [LEGAL.md](LEGAL.md) and give one sentence with name and role, ideally on camera. Cogent Law is a sponsor and BLI offers legal mentors: the event's Discord is the natural place to ask. Your call who to contact | |
| **20 Oct** | Founder bio | Fill the two lines marked `[FOUNDER]` in [BUIDL.md](BUIDL.md) (who you are, why you can build this) | No `[FOUNDER]` left |
| **22 Oct** | The quote, in hand | Paste it into BUIDL.md's "Who has read it" line, or delete that line | |
| **23 Oct** | Publish the page | `cd web && vercel deploy --prod` | `/?journal` opens on the live site |
| **25 Oct** | Video | Record to [DEMO_SCRIPT.md](DEMO_SCRIPT.md), round A. Upload to YouTube (public or unlisted) | Link pasted into BUIDL.md |
| **25 Oct** | Repo public | Secret sweep (CHECKLIST step 7), then make `ubmids/vouch-research` public with `first-place` as default branch | Repo opens logged out |
| **29 Oct** | DoraHacks BUIDL | A Discord, WhatsApp or WeChat handle for the form. Paste BUIDL.md, attach deck.pdf and the video, select the RYO-CHAN and Chainlink CRE bounties | Draft saved |
| **30 Oct** | Submit | Submit, then open every link logged out | Submitted |
| **5 Nov to 5 Dec** | Be free for a live finalist pitch | Judging runs 5 Nov to 5 Dec; last year 13 finalists pitched live (15 Nov 2025). Keep mid-November evenings (US Eastern) free and have a 5-minute version of the demo ready | |
| **12 Dec** | Awards | | |
