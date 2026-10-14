# Vouch verifier: a Chainlink CRE workflow

The check that settles every Vouch claim is a **Chainlink Runtime
Environment (CRE) workflow**. The market contract has no verifier key: it
accepts a verdict only as a report from the Chainlink forwarder it was deployed
with. On a DON that forwarder delivers only reports the nodes signed; in the
CLI simulation it is Chainlink's mock, which anyone can call (see
[Trust](#trust-stated-plainly)).

```
BondedClaims.post()  ──Posted(id, ticker, filing, claimHash, stake, claim words)──►  CRE EVM log trigger
                                                                                         │
           on a DON every node, independently; in simulation one local node (HTTP, node mode): ▼
             GET data.sec.gov/submissions/CIK….json      → the cited accession's primary document
             GET www.sec.gov/Archives/edgar/data/…/….htm  → the filing bytes (gzip, ~100 KB)
             the deterministic check on the claim's exact words     → {fraudulent, reason, keccak256(canonical filing)}
                                                                                         │
                                         identical consensus across nodes               ▼
           report = abi.encode(claimId, claimHash, fraudulent, evidence, reason), signed by the DON (on a DON)
                                                                                         │
     Chainlink forwarder ──► BondedClaims.onReport(metadata, report) ──► slash or clear, in the same transaction
```

| File | What |
|---|---|
| [`vouch-verifier/workflow.ts`](vouch-verifier/workflow.ts) | The workflow: log trigger on `Posted`, EDGAR fetch, check, consensus, `writeReport` |
| [`vouch-verifier/check/verifier.ts`](vouch-verifier/check/verifier.ts) | The check, ported line for line from [`agent/vouchrh/verifier.py`](../agent/vouchrh/verifier.py) |
| [`vouch-verifier/check/difflib.ts`](vouch-verifier/check/difflib.ts) | CPython's `SequenceMatcher.ratio()`, so fuzzy scores are the same number |
| [`vouch-verifier/check/edgar.ts`](vouch-verifier/check/edgar.ts) | SEC HTML to text exactly as [`edgar.py`](../agent/vouchrh/edgar.py) does (Python's own entity tables in `entities.ts`) |
| [`vouch-verifier/workflow.test.ts`](vouch-verifier/workflow.test.ts) | The handler in the CRE SDK's test runtime, with its HTTP and EVM mocks serving real SEC files |
| [`vouch-verifier/parity.test.ts`](vouch-verifier/parity.test.ts) | 3,249 claims on five real 10-Qs: same text, verdict, reason and score as Python |
| [`../scripts/quickjs_parity.py`](../scripts/quickjs_parity.py) | The same parity on **QuickJS via Javy**, the engine CRE runs workflows in |
| [`../src/BondedClaims.sol`](../src/BondedClaims.sol) | The consumer: `IReceiver.onReport`, forwarder-only, workflow owner / name / pinned id |
| [`../tests/test_cre_report.py`](../tests/test_cre_report.py) | The SDK-built report bytes settle a claim through a forwarder on anvil, and through Chainlink's own MockKeystoneForwarder on a fork of Robinhood Chain testnet |
| [`vouch-verifier/sdk-round.ts`](vouch-verifier/sdk-round.ts), [`../scripts/sdk_round.sh`](../scripts/sdk_round.sh) | The fallback round: the handler builds every claim's report in the SDK test runtime; the reports go through a local forwarder on anvil |
| [`vouch-verifier/fetch-filings.ts`](vouch-verifier/fetch-filings.ts) | `bun run fixtures`: the five 10-Qs the parity tests need, into the shared EDGAR cache |
| [`../scripts/cre_round.sh`](../scripts/cre_round.sh) | A full round on Robinhood Chain testnet settled by `cre workflow simulate --broadcast`, after a preflight and a dry run |

## What has been run, and what has not

Run on this repository's build machine (14 Oct 2026, CRE CLI v1.38.0, `@chainlink/cre-sdk` 1.23.0, Javy 8.1.0):

- `cre workflow build ./vouch-verifier`: compiles to WASM (2.8 MB), binary hash
  `077ae634fa6419380c91bba594a9205db996434c427a92005492e9b829fb73eb`. Login is not needed to build.
- `bun test` (24 tests): the workflow handler in the SDK test runtime (11), Python parity on 3,249 claims and
  5 filings (10), policy parity (3).
- `scripts/quickjs_parity.py`: all 3,249 verdicts identical on QuickJS under wasmtime, and the same canonical
  filing hash and text as Python. Earlier measurement (13 Oct): one claim on a 1.5 MB 10-Q takes 7 to 9 s
  and under 32 MB of WASM memory (CRE limits: 5 minutes, 100 MB).
- `pytest tests/test_cre_report.py` (with `VOUCH_FORK=1`): the report the SDK built is accepted by
  Chainlink's MockKeystoneForwarder deployed on Robinhood Chain testnet, on a local fork.
- `bash scripts/sdk_round.sh`: a 50-claim round on anvil in which every verdict is a report the handler
  built in the SDK test runtime (all 50 agree with the Python check). This is **not** a CRE CLI simulation.
- `bash scripts/cre_round.sh --preflight`: runs up to the login check and stops there ("not logged in").

**Not run yet: `cre workflow simulate`.** Simulation needs a Chainlink account: `cre login` (a browser
sign-in; from a headless machine forward its callback port, see docs/bli/CHECKLIST.md) or a `CRE_API_KEY`
from app.chain.link. `scripts/cre_round.sh` runs it once without `--broadcast`, then per claim with
`--broadcast`. Two things only that run can confirm: that the CRE HTTP capability passes SEC's gzip body
through undecoded (the workflow decompresses it; if the capability inflates it first, the 1.5 MB body
exceeds the 250 KB response limit), and the simulator's own runtime limits.

## Run it

```bash
curl -sSL https://app.chain.link/cre/install.sh | bash      # the CRE CLI
curl -fsSL https://bun.sh/install | bash                    # bun >= 1.2.21
cd cre/vouch-verifier && bun install && bun run fixtures && bun test && cd ..
cre workflow build ./vouch-verifier                         # WASM, prints its hash
cre login                                                   # or: export CRE_API_KEY=...

# One claim, by the transaction that posted it (pass a config whose "market" is that market):
cre workflow simulate ./vouch-verifier --target staging-settings --non-interactive \
  --trigger-index 0 --evm-tx-hash 0x<post tx> --evm-event-index 0 --config <config.json>   # dry run
#   ... add --broadcast (and CRE_ETH_PRIVATE_KEY in cre/.env) to write the verdict on Robinhood Chain testnet

bash ../scripts/cre_round.sh --preflight                    # everything but the gas
bash ../scripts/cre_round.sh                                # the whole round, end to end
```

## Trust, stated plainly

- **Simulation** (`--broadcast`) writes through Chainlink's *mock* forwarder
  (`0x0b93082D9b3C7C97fAcd250082899BAcf3af3885` on Robinhood Chain testnet). The mock is permissionless and
  checks no signatures, and the workflow metadata it passes on comes from the caller's report bytes, so
  checking owner or name there would prove nothing. A simulation market is deployed with no workflow owner
  and **anyone can settle its claims** by calling the mock. One local node runs the workflow, and the
  verdict transaction is sent from the operator's wallet. It demonstrates the path; it is not the security
  model.
- **Production** wires the market to the `KeystoneForwarder` (`0x8E6E6A1f2B2D4dF503bfd67951CF28F27BF3AF19`),
  which only forwards reports signed by the DON, and to a workflow owner and name
  (`--workflow-owner`, `--workflow-name` in `python -m vouchrh.market`). The deployer may then pin one
  workflow id, once (`pinWorkflow`); after that only that compiled workflow can settle, and nobody,
  including the deployer, can change it. Deploying a workflow needs CRE deploy access (early access).
- **What the DON attests** (on a live DON; in simulation one local node does this): that its nodes fetched these bytes from SEC EDGAR, ran this check on these
  words, and agreed on the answer. Anyone can repeat all three: the evidence on-chain is the keccak256 of
  the filing as SEC serves it, less the CDN's script tag (below).
- **The evidence** is the keccak256 of the filing as SEC serves it, less the one `<script src="/...">` tag
  SEC's CDN appends: its path changes over time (two paths for the same 10-Q, 45 minutes apart, on 13-14
  Oct), so raw bytes would differ between nodes and between today and a later re-check.

## Production

What a live deployment needs, beyond CRE deploy access. None of this has run.

- **KeystoneForwarder and a pinned workflow.** Redeploy the market with
  `--forwarder 0x8E6E6A1f2B2D4dF503bfd67951CF28F27BF3AF19 --workflow-owner <owner> --workflow-name vouch-verifier`,
  deploy the workflow with the `production-settings` target, then `pinWorkflow(<workflow id>)`.
- **No User-Agent header.** Chainlink's HTTP gateway refuses it (`defaultBlockedHeaders` includes
  `user-agent` in `core/services/gateway/network/httpclient.go`; read 14 Oct). The workflow sends one only
  if `sendUserAgent` is true: `config.staging.json` keeps it for the simulator, `config.production.json` turns
  it off (tested). **Open problem:** SEC answers 403 to a request without a contact in the User-Agent (checked
  14 Oct with no header and with `Go-http-client/1.1`), so on a DON the fetch would fail and the claim gets no
  verdict (and so can never back a trade). It needs either the gateway to send an SEC-acceptable User-Agent,
  or a mirror of EDGAR that the workflow can fetch and still prove against SEC's bytes.
- **Response size.** The same file sets the gateway's default `maxResponseBytes` to 26.4 KB; a gzipped 10-Q
  is 94 to 171 KB (under CRE's documented 250 KB HTTP limit). Whether a DON's configuration raises the
  default is unverified.
- **Log size.** CRE's log trigger takes events up to 5 KB (service quotas page); `BondedClaims.post` caps a
  claim's words at 3,500 bytes, its ticker at 16 and its filing at 32, so a `Posted` event stays under 4 KB.
