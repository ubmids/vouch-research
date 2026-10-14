# BLI submission checklist

Deadline: **30 October 2026** (BLI's post says 31 October; DoraHacks closes
1 November 01:01 UTC). Everything below that needs a person, a login, a
wallet or a camera is Subomi's; the rest is done on the `first-place` branch.

## Needs Subomi, in order

The Mac is not needed. Everything runs on mmfarm in `~/hack/vouch-fix/repo`
(already set up: `.venv`, `node_modules`, the CRE CLI v1.38.0 and bun in
`~/.local/bin` and `~/.bun/bin`). Log in from any computer with a browser.

1. **By 20 Oct: a Chainlink account, and the CLI logged in on mmfarm.** Sign up at
   https://app.chain.link (free). Then either:
   - **API key (simplest):** app.chain.link → Account Settings → create an API key; on mmfarm
     `export CRE_API_KEY=<key>` in the shell that runs the round (never commit it); or
   - **Browser login through ssh:** `cre login` waits for a browser callback on
     `http://localhost:53682/callback`, so forward that port from your laptop:
     `ssh -t -L 53682:localhost:53682 subomi@<mmfarm> 'cd ~/hack/vouch-fix/repo && ~/.local/bin/cre login'`.
     Open the `https://login.chain.link/authorize?...` URL it prints in your laptop's browser and sign in;
     the redirect to localhost:53682 reaches the CLI through the tunnel.
   - Check: `cre whoami` prints your account.
2. **By 20 Oct: the testnet wallet.** The round's wallet key was on the Mac (`~/.config/vouch-rh/testnet.key`,
   address `0x950d00BA837cD285e6d8a0F3f02d69434a775808`, 0.0062 test ETH on 14 Oct, enough for a round).
   - If you can copy that file to mmfarm (same path, mode 600), do; or
   - make a new one on mmfarm: `bash scripts/cre_round.sh --new-wallet` prints its address. Fund it at
     https://faucet.testnet.chain.robinhood.com from any browser (the page sits behind a Vercel browser
     check, so a script cannot do it). About 0.003 ETH covers a round: on 14 Oct a verdict transaction cost
     about 0.000001 ETH (106k gas at 0.01 gwei); most of the cost is funding the analysts' wallets.
3. **By 22 Oct: the CRE-settled round on Robinhood Chain testnet.**
   - `cd ~/hack/vouch-fix/repo && git pull`, then `ANALYST_MODEL=replay bash scripts/cre_round.sh --preflight`.
     It checks the tools, wallet balance, CRE login, SEC, and builds the WASM, spending nothing.
   - **The AI analyst.** `ANALYST_MODEL=replay` re-posts the claims Qwen wrote on 24 Sep, word for word
     (their hashes match the v1 market's; the page labels them "replayed"). This is the recommended
     setting: on 14 Oct, mmfarm's Qwen 2.5 7B, asked the exact question behind the hero, wrote a correct
     "Q2" claim instead of the published "Q3", so a live round would likely have no hero.
     `ANALYST_MODEL=live` asks the model again and stops unless it writes the hero claim. On mmfarm, do not use
     the Ollama on port 11434 (it runs on a GPU that is not yours; the script refuses it). Run your own CPU one
     on another port and set `OLLAMA_HOST=http://127.0.0.1:11435`.
   - `ANALYST_MODEL=replay bash scripts/cre_round.sh`. It deploys a market, posts the round, simulates the first
     claim **without** broadcasting (it stops on any error), then runs `cre workflow simulate --broadcast` per
     claim (about 20 to 40 minutes), reads the verdicts back, trades, and re-verifies the journal. A claim with
     no verdict is listed with a retry command; with no verdict at all the round stops before trading.
   - Check `cre/runs/<run>/env.txt` (versions, WASM hash, `verdicts_written: N of N`) and
     `journal-verify.txt` ("N of N checks hold"), and that a few `claim-*.log` files show `verdict: SLASH` /
     `CLEAR` and a transaction hash.
   - **If the workflow fails with a response-size error**, the CRE HTTP capability decompressed SEC's gzip body
     before the 250 KB limit. Note it, re-run one claim with `--limits none` added to the simulate line to show
     the workflow itself works, and say so in the BUIDL text.
   - Commit `cre/runs/<run>/`, `feed/feed.json`, `web/feed.json`, `deployments/46630.json`. Then update the
     claims that say "pending" (README's table, BUIDL's Chainlink paragraph, the deck's slide 5) with the run.
4. **By 23 Oct: publish the page**: `cd web && vercel deploy --prod` (your call; nothing here deploys). Until
   then the live site has no journal and the README/BUIDL journal links say "pending".
5. **By 25 Oct: record the video** to [DEMO_SCRIPT.md](DEMO_SCRIPT.md): round A if step 3 ran, round B
   (`bash scripts/sdk_round.sh`, works today) otherwise, with that round's captions. 2:30, face in a corner
   bubble for the first and last 10 seconds, payoff by 0:20. Upload to YouTube (public or unlisted).
6. **By 27 Oct: make the repository public**, after a last secret sweep. This should print nothing:
   `git log -p --all | grep -nE "(PRIVATE_KEY|private_key)[[:space:]]*[=:][[:space:]]*\"?(0x)?[0-9a-fA-F]{64}|mnemonic[[:space:]]*[=:][[:space:]]*\"?[a-z]+( [a-z]+){11}"`
   (it catches a labelled hex key or a 12-word mnemonic; checked to print nothing on 14 Oct). The anvil test
   key that appears in the README and tests is Foundry's public default and is fine.
   Then make it public and set the default branch to `first-place` in the repository's GitHub settings
   (or with `gh repo edit`), or merge `first-place` into `master`.
7. **By 29 Oct: the DoraHacks BUIDL.** The form needs a Discord, WhatsApp or WeChat contact: have one ready.
   Paste from [BUIDL.md](BUIDL.md). Attach [deck.pdf](deck.pdf) and the video. Select the **RYO-CHAN** and
   **Chainlink CRE** bounties. Links: repo, live feed, `?journal`, LEGAL.md, cre/README.md.
8. **30 Oct: submit** (DoraHacks closes 1 Nov 01:01 UTC). Then check the BUIDL page renders and every link
   opens logged out.

Optional, if time allows:

- Request CRE **deploy access** (early access) and deploy the workflow on a live DON. That needs the
  production problems in [cre/README.md](../../cre/README.md#production) solved first (SEC requires a
  User-Agent; the gateway refuses to send one).
- One outside reader: a compliance lawyer or a research publisher reading LEGAL.md and saying one
  sentence on camera is worth more to a lawyer panel than any feature.
- The name: "Vouch" is taken on HackQuest. Alternatives are in the task report; renaming is your call.

## Bounty requirements, checked

**RYO-CHAN, Autonomous Agents ($6,000):** agents read market evidence and log practice trades with
cause and effect and a repeatable reasoning trail.

- [x] Reads market evidence: every analyst's claim about the stock; in KOL mode, 20 posts by market voices
  (a written fixture by fictional accounts, labelled), read for token, figure, sentiment, conviction, urgency
- [x] A named RYO direction: News Checker ("verify a story, connect it to market evidence"): each post's figure
  is found in the issuer's 10-Q and checked as a staked claim
- [x] Practice trades: `AgentDesk` paper positions, no money moves
- [x] Cause and effect: each entry lists the claims read, the refusals, the claims cited, the signal of each, the decision
- [x] Repeatable reasoning trail: the reasoning record is hashed on-chain with the trade; Re-verify (browser) and `vouchrh.journal verify` (CLI) re-run it
- [x] Shown with the AI analyst's claim on a local devnet (`web/feed-local.json`, replayed 24 Sep words, labelled)
- [ ] Shown on testnet (step 3) and in the video (step 5)

**Chainlink, Best workflow with CRE (2 x $1,000):** CRE is the orchestration layer, connecting at least
one chain to an external API, LLM or agent, with a CRE CLI simulation or a live deployment.

- [x] CRE is the orchestration layer: the verdict exists only as a CRE report (`cre/vouch-verifier/workflow.ts`, `src/BondedClaims.sol`)
- [x] Chain to an external API: Robinhood Chain `Posted` log → SEC EDGAR over the HTTP capability → report back on-chain
- [x] Every file that uses Chainlink is linked from the README
- [x] Compiles with `cre workflow build`; handler tested in the CRE SDK test runtime; a full local round
  settled by reports the handler built in that runtime (not a substitute for the CLI simulation)
- [ ] **CRE CLI simulation run** (`cre workflow simulate --broadcast`): needs the login (step 1) and the round
  (step 3). Without it the entry does not meet this bounty's stated minimum.
- [ ] The CLI output in the video (step 5)

**BLI general (post of 11 Oct):** public repo, architecture docs, video demo.

- [x] Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- [x] Legal applicability: [LEGAL.md](LEGAL.md) (Reg AC, FINRA 2241, what it proves and does not)
- [ ] Public repo (step 6) · [ ] video (step 5) · [ ] contact for the form (step 7)
