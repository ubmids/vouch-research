# Vouch verifier: a Chainlink CRE workflow

The check that settles every Vouch claim runs as a **Chainlink Runtime
Environment (CRE) workflow**. No Vouch key can settle a dispute: the market
contract accepts a verdict only as a report from the Chainlink forwarder.

```
BondedClaims.post()  ──Posted(id, ticker, filing, claimHash, stake, claim words)──►  CRE EVM log trigger
                                                                                         │
           every node of the DON, independently (HTTP capability, node mode):            ▼
             GET data.sec.gov/submissions/CIK….json      → the cited accession's primary document
             GET www.sec.gov/Archives/edgar/data/…/….htm  → the filing bytes (gzip, ~100 KB)
             the deterministic check on the claim's exact words     → {fraudulent, reason, keccak256(filing)}
                                                                                         │
                                         identical consensus across nodes               ▼
           report = abi.encode(claimId, claimHash, fraudulent, evidence, reason), signed by the DON
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
| [`../scripts/cre_round.sh`](../scripts/cre_round.sh) | A full round on Robinhood Chain testnet settled by `cre workflow simulate --broadcast` |

## What has been run, and what has not

Run on this repository's build machine (13 Oct 2026, CRE CLI v1.38.0, `@chainlink/cre-sdk` 1.23.0, Javy 8.1.0):

- `cre workflow build ./vouch-verifier`: compiles to WASM (2.8 MB). Login is not needed to build.
- `bun test`: the workflow handler in the SDK test runtime (6 tests) and Python parity (3,249 claims, 5 filings).
- `scripts/quickjs_parity.py`: all 3,249 verdicts identical on QuickJS under wasmtime. One claim on a 1.5 MB
  10-Q takes 7 to 9 s and under 32 MB of WASM memory (CRE limits: 5 minutes, 100 MB).
- `pytest tests/test_cre_report.py` (with `VOUCH_FORK=1`): the report the SDK built is accepted by
  Chainlink's MockKeystoneForwarder deployed on Robinhood Chain testnet, on a local fork.

**Not run here: `cre workflow simulate`.** The CLI requires `cre login` (a browser sign-in to a free
Chainlink account) for simulation, and this machine has no browser. `scripts/cre_round.sh` runs it, per
claim, with `--broadcast`, from the machine that holds the testnet wallet. Two things only that run can
confirm: that the CRE HTTP capability passes SEC's gzip body through undecoded (the workflow
decompresses it; if the capability inflates it first, the 1.5 MB body exceeds the 250 KB response
limit), and the simulator's own runtime limits.

## Run it

```bash
curl -sSL https://app.chain.link/cre/install.sh | bash      # the CRE CLI
curl -fsSL https://bun.sh/install | bash                    # bun >= 1.2.21
cre login
cd cre/vouch-verifier && bun install && bun test && cd ..
cre workflow build ./vouch-verifier                         # WASM, prints its hash

# One claim, by the transaction that posted it (market address in config.staging.json):
cre workflow simulate ./vouch-verifier --target staging-settings --non-interactive \
  --trigger-index 0 --evm-tx-hash 0x<post tx> --evm-event-index 0            # dry run
#   ... add --broadcast (and CRE_ETH_PRIVATE_KEY in cre/.env) to write the verdict on Robinhood Chain testnet

bash ../scripts/cre_round.sh                                # the whole round, end to end
```

## Trust, stated plainly

- **Simulation** (`--broadcast`) writes through Chainlink's *mock* forwarder
  (`0x0b93082D9b3C7C97fAcd250082899BAcf3af3885` on Robinhood Chain testnet). The mock checks no signatures
  and fills no workflow identity, so a market wired to it is deployed with no workflow owner and trusts
  whoever calls the mock. It demonstrates the path; it is not the security model.
- **Production** wires the market to the `KeystoneForwarder` (`0x8E6E6A1f2B2D4dF503bfd67951CF28F27BF3AF19`),
  which only forwards reports signed by the DON, and to a workflow owner and name
  (`--workflow-owner`, `--workflow-name` in `python -m vouchrh.market`). The deployer may then pin one
  workflow id, once (`pinWorkflow`); after that only that compiled workflow can settle, and nobody,
  including the deployer, can change it. Deploying a workflow needs CRE deploy access (early access).
- **What the DON attests**: that its nodes fetched these bytes from SEC EDGAR, ran this check on these
  words, and agreed on the answer. Anyone can repeat all three: the evidence on-chain is the keccak256 of
  the filing exactly as SEC serves it.
