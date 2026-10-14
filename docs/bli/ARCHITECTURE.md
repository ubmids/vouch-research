# Architecture

## Components

| Component | Where | Runs on | Trusted for |
|---|---|---|---|
| `BondedClaims` | [`src/BondedClaims.sol`](../../src/BondedClaims.sol) | Robinhood Chain (Arbitrum Orbit) | Holding stakes; accepting verdicts only from the Chainlink forwarder; moving money in the same transaction as a verdict |
| `AgentDesk` | [`src/AgentDesk.sol`](../../src/AgentDesk.sol) | Robinhood Chain | Refusing any trade that cites a claim that is not cleared; storing each trade's citations and reasoning hash |
| `vouch-verifier` CRE workflow | [`cre/vouch-verifier/`](../../cre/vouch-verifier) | A Chainlink decentralised oracle network in production; one local node in the CRE CLI simulation (not yet run); Chainlink's SDK test runtime in the fallback round (run) | Fetching the filing from SEC EDGAR, running the check, agreeing on the verdict, signing the report (a DON only) |
| Chainlink forwarder | `KeystoneForwarder` (production) / `MockKeystoneForwarder` (simulation) | Robinhood Chain | Delivering only DON-signed reports (production) |
| Analysts | [`agent/vouchrh/analysts.py`](../../agent/vouchrh/analysts.py), [`llm.py`](../../agent/vouchrh/llm.py) | Anywhere (a laptop for the AI analyst) | Nothing: everything they post is checked |
| Trading agent | [`agent/vouchrh/journal.py`](../../agent/vouchrh/journal.py), [`policy.py`](../../agent/vouchrh/policy.py) | Anywhere | Nothing: the desk gates it, and its reasoning is re-runnable |
| Feed | [`web/`](../../web) | Static site (Vercel) | Nothing: it displays what the chain holds and re-verifies it in the browser |
| SEC EDGAR | sec.gov | SEC | The filing text (the source of truth claims are checked against) |

## One claim, end to end

```
Analyst            BondedClaims          CRE workflow (each DON node)          SEC EDGAR        Forwarder        AgentDesk
  │ bond(USDG) ──────►│
  │ post(ticker, accession, words, stake)
  │                    │── Posted(id, …, claimHash, stake, words) ──► log trigger
  │                    │                     │ GET submissions/CIK….json ──────►│
  │                    │                     │ GET Archives/…/10-Q.htm (gzip) ─►│
  │                    │                     │ check(words, filing text) → {fraudulent, reason, keccak256(bytes)}
  │                    │                     │ identical consensus; runtime.report(abi.encode(id, claimHash, fraudulent, evidence, reason))
  │                    │                     │ writeReport ───────────────────────────────────────►│
  │                    │◄──────────────────── onReport(metadata, report) ───────────────────────────┘
  │                    │ checks: sender == forwarder; workflow owner, name (and pinned id); claimHash matches
  │                    │ slash (stake → readers' fund) or clear; Checked + Slashed/Cleared events; verdict stored
  │
Trading agent ── open(ticker, side, notional, [claim ids], reasoningHash) ─────────────────────────────────────────►│
                                                                     every cited claim cleared? same ticker? none twice?
                                                                     no → revert NotCleared(id)   yes → Opened(entry, …, citations)
```

## Data on-chain

**A claim** (`BondedClaims.Claim`): analyst, posted time, status, stake,
keccak256 of the canonical claim JSON, SEC accession, ticker, challenger. The
canonical JSON (`ticker, accession, metric, value, quote, analyst, summary`,
keys sorted, no whitespace, UTF-8) is in the `Posted` event.

**A verdict** (`BondedClaims.Verdict`): when it was written, the keccak256 of
the filing bytes the workflow fetched (`evidence`), and the workflow id from
the forwarder's metadata. A claim that cleared only because nobody
challenged it in time has zero evidence and zero workflow id, and the journal
shows that.

**The report** the workflow signs: `abi.encode(uint256 claimId, bytes32
claimHash, bool fraudulent, bytes32 evidence, string reason)`. The forwarder
passes `metadata` = workflow id (32 bytes), name (10), owner (20), report id (2).

**A journal entry** (`AgentDesk.Entry` and the `Opened` event): agent, side,
paper notional, time, ticker, reasoning hash, and per cited claim: id, claim
hash, verdict time, evidence, workflow id.

## The reasoning record (off-chain, hashed on-chain): an abridged example

```json
{"policy": "vouch-desk-policy/1", "rule": "signal per claim = change x polarity; …",
 "ticker": "AMD", "side": "long", "net_signal": 1, "per_claim": 100000000, "notional": 100000000,
 "evidence": [{"claim": 46, "hash": "0x…", "analyst": "Qwen 2.5 7B", "value": "$1,095 million",
               "signal": 1, "why": "amortization down (the summary says it went down): bullish",
               "verdict_tx": "0x…"}],
 "dropped": [{"claim": 44, "error": "NotCleared", "tx": "0x…", "verdict": "slashed",
              "reason": "supporting quote not found in source document", "side_before": "short"}],
 "price": {"ticker": "AMD", "price": "160.00", "source": "Yahoo Finance chart API (unattested)", "at": 1791909803}}
```

keccak256 of its canonical JSON is the `reasoning` argument of
`AgentDesk.open`. Integers and strings only, so Python and the browser hash
the same bytes.

## Trust boundaries and failure modes

| If… | Then |
|---|---|
| An analyst lies | The check slashes the stake; the desk refuses trades citing it |
| Someone calls `onReport` directly | Reverts `NotForwarder` |
| A report comes from another workflow | Reverts `WrongWorkflow` (owner, name, or pinned id) |
| A report is about different words than were posted | Reverts `WrongClaim` |
| A second verdict arrives for a settled claim | Recorded as `ReportIgnored`; nothing changes |
| The DON never answers | Unchallenged: the claim clears by default after the window, with no filing evidence, and `AgentDesk` refuses it (`NotChecked`). Challenged: `unwind` after 7 days refunds both sides; the claim never counts as cleared |
| An analyst posts malformed words, or words naming another stock or filing | The workflow reports it slashed without fetching anything; it never waits |
| An analyst challenges their own wrong claim | Gains nothing: a slash sends the whole stake to the readers' fund; the challenger only gets the deposit back |
| A slashed analyst tries to get the stake back | Cannot: the fund's payees and shares are fixed in the constructor before any claim; a non-payee's `claimReaderShare()` reverts `NothingDue` |
| A payee claims twice, or re-enters on transfer | Paid once: records are written before the transfer, behind a reentrancy lock; shares round down, so the fund never owes more than it holds |
| The same words are posted twice | The desk treats them as one piece of evidence (`CitedTwice` on the hash) |
| A verdict arrives after the window | A slash still applies while the claim is unsettled |
| SEC EDGAR is down | The workflow throws; no report; the claim waits |
| The analyst cites a filing the company never made | Slashed: "filing … is not one of TSLA's recent filings" |
| The check is wrong on a nuance (limit vs balance) | A human challenger disputes within the window; stated as a limit |
| Simulation | The mock forwarder is permissionless and checks no signatures, and passes on caller-chosen workflow metadata: anyone can settle a claim on the simulation market. It demonstrates the path only |

## Limits of the platform (CRE)

Measured against CRE's published limits: a 10-Q is 1.3 to 1.8 MB, so the
workflow asks SEC for gzip (94 to 113 KB, under the 250 KB response limit)
and inflates it in WASM; two HTTP calls per claim (limit 15); one claim takes
7 to 9 s and under 32 MB of WASM memory on QuickJS (limits: 5 minutes, 100 MB);
the node's observation is three short fields (limit 25 KB).
