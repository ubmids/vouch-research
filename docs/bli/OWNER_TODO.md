# Owner to-do, by date

Only the things that need Subomi: an account, a browser, a wallet, a camera,
a person, or a decision. Everything else is done on `first-place`. The how for
steps 1 to 4 is in [CHECKLIST.md](CHECKLIST.md). All of it runs on the Mac.

| By | What | Exact steps | Done when |
|---|---|---|---|
| **By 20 Oct** (the posted claims wait until 22 Oct, 16:32 UTC) | **Chainlink CRE login: the one blocker, about 10 minutes** | 1. Open https://app.chain.link in your browser and sign up (free; it asks you to set up 2FA with an authenticator app). 2. On this Mac, in Terminal: `cd ~/Desktop/hackathons/fix-20261014/vouch-research && ~/.cre/bin/cre login`. It opens the browser; sign in and approve. 3. Check: `~/.cre/bin/cre whoami` prints your account. Then tell Claude "logged in": it runs `bash scripts/after_login.sh` (settles the round with test ETH only, then refreshes the docs, images and deck). Nothing else is needed: bun, the CLI, the wallet's test ETH and the posted round are ready | `cre whoami` prints your account |
| ~~16 Oct~~ | ~~Design direction~~ | Done 15 Oct: Exhibit. The name stays Vouch | |
| ~~16 Oct~~ | ~~Who runs the round~~ | Done 15 Oct: you said go. The round is deployed and its 50 claims are posted on Robinhood Chain testnet (docs/bli/TESTNET_ROUND.md); only the settling waits on the login | |
| ~~16 Oct~~ | ~~Faucet~~ | Not needed: the wallet held 0.0062 test ETH on 15 Oct, about twice a round. The preflight still checks it | |
| **18 Oct** | Start the lawyer or compliance quote | Ask one securities or compliance lawyer, or a research publisher, to read [LEGAL.md](LEGAL.md) and give one sentence with name and role, ideally on camera. Cogent Law is a sponsor and BLI offers legal mentors: the event's Discord is the natural place to ask. Your call who to contact | |
| **20 Oct** | Founder bio | Fill the two lines marked `[FOUNDER]` in [BUIDL.template.md](BUIDL.template.md) (who you are, why you can build this), or send them to Claude | No `[FOUNDER]` left |
| **22 Oct** | The quote, in hand | Paste it into BUIDL.md's "Who has read it" line, or delete that line | |
| **23 Oct** | Publish the page | Say go; Claude runs `bash scripts/deploy_web.sh --go` (`bash scripts/deploy_web.sh` alone only checks). Needs the Vercel CLI logged in to the account that owns vouch-feed | `/?journal` opens on the live site |
| **25 Oct** | Video | Record to [DEMO_SCRIPT.md](DEMO_SCRIPT.md), round A. Upload to YouTube (public or unlisted) | Link pasted into BUIDL.md |
| **25 Oct** | Repo public | Secret sweep (CHECKLIST step 7), then make `ubmids/vouch-research` public with `first-place` as default branch | Repo opens logged out |
| **29 Oct** | DoraHacks BUIDL | A Discord, WhatsApp or WeChat handle for the form. Paste BUIDL.md, attach deck.pdf and the video, select the RYO-CHAN and Chainlink CRE bounties | Draft saved |
| **30 Oct** | Submit | Submit, then open every link logged out | Submitted |
| **5 Nov to 5 Dec** | Be free for a live finalist pitch | Judging runs 5 Nov to 5 Dec; last year 13 finalists pitched live (15 Nov 2025). Keep mid-November evenings (US Eastern) free and have a 5-minute version of the demo ready | |
| **12 Dec** | Awards | | |
