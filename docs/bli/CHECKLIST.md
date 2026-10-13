# BLI submission checklist

Deadline: **30 October 2026** (BLI's post says 31 October; DoraHacks closes
1 November 01:01 UTC). Everything below that needs a person, a login, a
wallet or a camera is Subomi's; the rest is done on the `first-place` branch.

## Needs Subomi, in order

1. **By 20 Oct: a Chainlink CRE account, on the Mac.**
   - Sign up at https://app.chain.link/cre/discover (free, 2FA). Install the CLI:
     `curl -sSL https://app.chain.link/cre/install.sh | bash`. Install bun:
     `curl -fsSL https://bun.sh/install | bash`. Then `cre login`.
   - `cd cre/vouch-verifier && bun install && bun test`: expect 19 pass.
   - Dry run against the old testnet market is not possible (old ABI). The next step deploys the new one.
2. **By 22 Oct: the CRE-settled round on Robinhood Chain testnet.**
   - Wallet `0x950d00BA837cD285e6d8a0F3f02d69434a775808` needs test ETH (faucet.testnet.chain.robinhood.com).
     About 0.01 ETH covers a 50-claim round: posts, about 50 forwarder transactions, about 30 refusals and the trades.
   - Start Ollama with `qwen2.5:7b-instruct`, so the AI analyst is in the round. The hero claim (the AI's
     wrong quarter) only exists if the model runs.
   - `bash scripts/cre_round.sh`. It deploys, posts, runs `cre workflow simulate --broadcast` once per
     claim (about 20 to 40 minutes), reads the verdicts back, trades, and re-verifies the journal.
   - Check `cre/runs/<run>/journal-verify.txt` ends with "N of N checks hold", and that a few
     `claim-*.log` files show `verdict: SLASH` / `CLEAR` and a transaction hash.
   - **If the workflow fails with a response-size error**, the CRE HTTP capability decompressed
     SEC's gzip body before the 250 KB limit. Note it, then re-run one claim with
     `--limits none` added to the `cre workflow simulate` line to show the workflow itself works, and
     say so in the BUIDL text.
   - Commit `cre/runs/<run>/` (logs and the wasm hash), `feed/feed.json`, `web/feed.json`,
     `deployments/46630.json`, `cre/vouch-verifier/config.staging.json`. Then publish the page:
     `cd web && vercel deploy --prod` (your call; nothing here deploys it).
3. **By 25 Oct: record the video** to [DEMO_SCRIPT.md](DEMO_SCRIPT.md). 2:30, face in a corner bubble
   for the first and last 10 seconds, payoff by 0:20. Upload to YouTube (public or unlisted).
4. **By 27 Oct: make the repository public**, after a last secret sweep:
   `git log -p --all | grep -iE "private[_ ]?key|0x[0-9a-f]{64}"` should show only the well-known anvil
   test key. Decide whether to merge `first-place` into `master` (the README links work from either).
5. **By 29 Oct: the DoraHacks BUIDL.** Paste from [BUIDL.md](BUIDL.md). Attach [deck.pdf](deck.pdf) and
   the video. Select the **RYO-CHAN** and **Chainlink CRE** bounties. Links: repo, live feed,
   `?journal`, LEGAL.md, cre/README.md.
6. **30 Oct: submit.** Then check the BUIDL page renders and every link opens logged out.

Optional, if time allows:

- Request CRE **deploy access** (early access) and deploy the workflow on a live DON; redeploy the market
  with `--forwarder 0x8E6E6A1f2B2D4dF503bfd67951CF28F27BF3AF19 --workflow-owner <your CRE owner address>
  --workflow-name vouch-verifier`, then pin the workflow id. That is the production trust model.
- One outside reader: a compliance lawyer or a research publisher reading LEGAL.md and saying one
  sentence on camera is worth more to a lawyer panel than any feature.
- The name: "Vouch" is taken on HackQuest. Alternatives are in the task report; renaming is your call.

## Bounty requirements, checked

**RYO-CHAN, Autonomous Agents ($6,000):** agents read market evidence and log practice trades with
cause and effect and a repeatable reasoning trail.

- [x] Reads market evidence: every analyst's claim about the stock (several "KOLs")
- [x] Practice trades: `AgentDesk` paper positions, no money moves
- [x] Cause and effect: each entry lists the claims read, the refusals, the claims cited, the signal of each, the decision
- [x] Repeatable reasoning trail: the reasoning record is hashed on-chain with the trade; Re-verify (browser) and `vouchrh.journal verify` (CLI) re-run it
- [ ] Shown on testnet with the AI analyst (step 2) and in the video (step 3)

**Chainlink, Best workflow with CRE (2 x $1,000):** CRE is the orchestration layer, connecting at least
one chain to an external API, LLM or agent, with a CRE CLI simulation or a live deployment.

- [x] CRE is the orchestration layer: the verdict exists only as a CRE report (`cre/vouch-verifier/workflow.ts`, `src/BondedClaims.sol`)
- [x] Chain to an external API: Robinhood Chain `Posted` log → SEC EDGAR over the HTTP capability → report back on-chain
- [x] Every file that uses Chainlink is linked from the README
- [x] Compiles with `cre workflow build`; handler tested in the CRE SDK test runtime
- [ ] **CRE CLI simulation run** (`cre workflow simulate --broadcast`): needs `cre login`, step 2
- [ ] The CLI output in the video (step 3)

**BLI general (post of 11 Oct):** public repo, architecture docs, video demo.

- [x] Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- [x] Legal applicability: [LEGAL.md](LEGAL.md) (Reg AC, FINRA 2241, what it proves and does not)
- [ ] Public repo (step 4) · [ ] video (step 3)
