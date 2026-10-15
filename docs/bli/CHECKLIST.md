# BLI submission checklist

Deadline: **30 October 2026** (BLI's post says 31 October; DoraHacks closes
1 November 01:01 UTC). Everything below that needs a person, a login, a
wallet or a camera is Subomi's; the rest is done on the `first-place` branch.

## Needs Subomi, in order

Everything runs on **this Mac**, in the repo checkout (`git pull` on the
`first-place` branch first). No other machine is needed. The dated list of
owner-only tasks is [OWNER_TODO.md](OWNER_TODO.md); this is the how.

Already set up on the Mac (14 Oct): Foundry (`~/.foundry/bin`), the CRE CLI
v1.38.0 (`~/.cre/bin`, from Chainlink's official installer), and the Python
venv (`.venv`, web3 + pytest). `scripts/cre_round.sh` puts those directories on
its own `PATH`. The testnet wallet key is already at
`~/.config/vouch-rh/testnet.key` (address `0x950d00BA837cD285e6d8a0F3f02d69434a775808`,
0.0062 test ETH on 14 Oct). Never print or commit that file.

1. **bun: done.** bun 1.4.3 is installed at `~/.bun/bin` (checked 15 Oct); `scripts/cre_round.sh`
   puts it on its own `PATH`.
2. **By 16 Oct: a Chainlink account and the CLI logged in.** Sign up at https://app.chain.link (free, 2FA
   required), then in the repo run `~/.cre/bin/cre login` and sign in in the browser it opens. (An API
   key is not an alternative: Chainlink's docs reserve API-key auth for accounts with deploy access.) Check: `~/.cre/bin/cre whoami` prints your account. Checked 14 Oct: without
   this, `cre workflow simulate` stops with "Authentication required"; nothing else is missing.
3. **By 16 Oct: the wallet's balance.** The preflight checks it. If it says the wallet is short, fund
   `0x950d00BA837cD285e6d8a0F3f02d69434a775808` at https://faucet.testnet.chain.robinhood.com in your browser
   (it sits behind a browser check, so a script cannot). About 0.003 ETH covers a round.
4. **By 18 Oct: the CRE-settled round on Robinhood Chain testnet.** In the repo:
   ```
   ANALYST_MODEL=replay bash scripts/cre_round.sh --preflight   # spends nothing: tools, wallet, login, SEC, WASM build
   ANALYST_MODEL=replay bash scripts/cre_round.sh                # about 20 to 40 minutes
   ```
   - `ANALYST_MODEL=replay` re-posts, word for word, the claims the Qwen analyst wrote on 24 Sep (the page
     labels them "replayed"). Use it: no model server is needed, and the hero claim is guaranteed. A live
     model on 14 Oct wrote a correct claim instead of the wrong one, so a live round may have no hero.
   - The round deploys the current contracts (with the readers' fund; the deployer stands in for it),
     posts the claims, runs `cre workflow simulate` once **without** broadcasting on the first claim (it
     stops on any error), then `cre workflow simulate --broadcast` per claim, reads the verdicts back,
     trades, and re-verifies the journal. A claim with no verdict is listed with a retry command.
   - Check `cre/runs/<run>/env.txt` (`verdicts_written: N of N`), `journal-verify.txt` ("N of N checks
     hold"), and that a few `claim-*.log` files show `verdict: SLASH` / `CLEAR` and a transaction hash.
   - **If the workflow fails with a response-size error**, SEC's gzip body was decompressed before the
     limit. Re-run one claim with `--limits none` added to the simulate line (the retry command the
     script prints), and say so in the BUIDL's "What ran" box.
   - Commit `cre/runs/<run>/`, `feed/feed.json`, `web/feed.json`, `deployments/46630.json` and push. Then
     tell Claude the run folder: the "pending" lines in README, BUIDL and the deck get replaced from it.
5. **By 23 Oct: publish the page**: `cd web && vercel deploy --prod` (your call; nothing here deploys).
6. **By 25 Oct: record the video** to [DEMO_SCRIPT.md](DEMO_SCRIPT.md), round A. 2:30, face in a corner
   bubble for the first and last 10 seconds. Upload to YouTube (public or unlisted).
7. **By 25 Oct: make the repository public**, after a last secret sweep. This should print nothing:
   `git log -p --all | grep -nE "(PRIVATE_KEY|private_key)[[:space:]]*[=:][[:space:]]*\"?(0x)?[0-9a-fA-F]{64}|mnemonic[[:space:]]*[=:][[:space:]]*\"?[a-z]+( [a-z]+){11}"`
   Also check `git status` does not list `cre/.env` (the round writes the key there for the CLI; it is
   git-ignored). The anvil test key in the README and tests is Foundry's public default and is fine.
   Then make it public and set the default branch to `first-place` (`gh repo edit`), or merge it into `master`.
8. **By 29 Oct: the DoraHacks BUIDL.** The form needs a Discord, WhatsApp or WeChat contact. Paste from
   [BUIDL.md](BUIDL.md) (fill in the founder line first). Attach [deck.pdf](deck.pdf) and the video. Select
   the **RYO-CHAN** and **Chainlink CRE** bounties.
9. **30 Oct: submit.** Then check the BUIDL page renders and every link opens logged out.

Optional, if time allows:

- Request CRE **deploy access** (early access) and deploy the workflow on a live DON. That needs the
  production problems in [cre/README.md](../../cre/README.md#production) solved first (SEC requires a
  User-Agent; the gateway refuses to send one).
- One outside reader: a compliance lawyer or a research publisher reading LEGAL.md and saying one
  sentence on camera is worth more to a lawyer panel than any feature.
- The name: "Vouch" is taken on HackQuest. The audit recommends "AsFiled"; see OWNER_TODO.md.

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
- [ ] Shown on testnet (step 4) and in the video (step 6)

**Chainlink, Best workflow with CRE (2 x $1,000):** CRE is the orchestration layer, connecting at least
one chain to an external API, LLM or agent, with a CRE CLI simulation or a live deployment.

- [x] CRE is the orchestration layer: the verdict exists only as a CRE report (`cre/vouch-verifier/workflow.ts`, `src/BondedClaims.sol`)
- [x] Chain to an external API: Robinhood Chain `Posted` log → SEC EDGAR over the HTTP capability → report back on-chain
- [x] Every file that uses Chainlink is linked from the README
- [x] Compiles with `cre workflow build`; handler tested in the CRE SDK test runtime; a full local round
  settled by reports the handler built in that runtime (not a substitute for the CLI simulation)
- [ ] **CRE CLI simulation run** (`cre workflow simulate --broadcast`): needs bun and the login (steps 1 and 2) and the round
  (step 4). Without it the entry does not meet this bounty's stated minimum.
- [ ] The CLI output in the video (step 6)

**BLI general (post of 11 Oct):** public repo, architecture docs, video demo.

- [x] Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- [x] Legal applicability: [LEGAL.md](LEGAL.md) (Reg AC, FINRA 2241, what it proves and does not)
- [ ] Public repo (step 7) · [ ] video (step 6) · [ ] contact for the form (step 8)
