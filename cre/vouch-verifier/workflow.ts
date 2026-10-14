// Vouch's verifier as a Chainlink Runtime Environment workflow.
//
//   BondedClaims emits Posted(id, analyst, ticker, filing, claimHash, stake, claim)
//     -> (EVM log trigger) every node of the DON, independently:
//          fetches the company's EDGAR submissions index and the cited filing,
//          runs the deterministic check on the claim's exact words,
//          returns {fraudulent, reason, evidence = keccak256(the filing's canonical bytes)}
//     -> the nodes must agree exactly (identical consensus)
//     -> a signed report abi.encode(id, claimHash, fraudulent, evidence, reason)
//     -> the Chainlink forwarder calls BondedClaims.onReport, which slashes or clears.
//
// Nothing here holds a key that can settle a claim: the verdict is whatever the
// check returns on the filing SEC serves, agreed by the network.

import {
  bytesToHex,
  consensusIdenticalAggregation,
  cre,
  type EVMLog,
  getNetwork,
  type HTTPSendRequester,
  hexToBase64,
  prepareReportRequest,
  type Runtime,
  TxStatus,
} from "@chainlink/cre-sdk"
import { type Hex, decodeEventLog, encodeAbiParameters, hexToBytes, keccak256, parseAbi, parseAbiParameters, toEventSelector } from "viem"
import { z } from "zod"
import { canonical, decodeUtf8, inflate, primaryDocument, toText } from "./check/edgar"
import { auditClaim } from "./check/verifier"

export const configSchema = z.object({
  chainSelectorName: z.string(),
  market: z.string(),                       // BondedClaims: emits Posted, receives verdicts
  userAgent: z.string(),                    // SEC fair access: a contact in every request
  // The CLI simulator sends request headers as given. A DON's HTTP gateway
  // refuses a User-Agent header ("gateway controls its own identification"),
  // so a production config sets this false; see cre/README.md, Production.
  sendUserAgent: z.boolean().default(true),
  ciks: z.record(z.string(), z.string()),   // the stock tokens' SEC registrants, e.g. TSLA -> 0001318605
  gasLimit: z.string().default("1000000"),
})
export type Config = z.infer<typeof configSchema>

export const POSTED = parseAbi([
  "event Posted(uint256 indexed id, address indexed analyst, string ticker, string filing, bytes32 claimHash, uint256 atStake, bytes claim)",
])
export const POSTED_TOPIC = toEventSelector(POSTED[0])
export const REPORT = parseAbiParameters("uint256 claimId, bytes32 claimHash, bool fraudulent, bytes32 evidence, string reason")

/** What each node observes. Small, so it fits consensus (25 KB) with room to spare. */
export type Observation = { fraudulent: boolean; reason: string; evidence: string }

/** The claim as posted: the canonical JSON whose keccak256 is on-chain. */
export const claimSchema = z.object({
  ticker: z.string().min(1),
  accession: z.string().regex(/^\d{10}-\d{2}-\d{6}$/),
  metric: z.string(),
  value: z.string().min(1),
  quote: z.string().min(1),
  analyst: z.string(),
  summary: z.string(),
})
export type ClaimWords = z.infer<typeof claimSchema>

const get = (req: HTTPSendRequester, url: string, config: Config): Uint8Array => {
  // gzip keeps a 1.5 MB 10-Q near 100 KB, under the 250 KB response limit
  const headers: Record<string, { values: string[] }> = { "Accept-Encoding": { values: ["gzip"] } }
  if (config.sendUserAgent) headers["User-Agent"] = { values: [config.userAgent] }
  const r = req
    .sendRequest({ url, method: "GET", timeout: "10s", multiHeaders: headers })
    .result()
  if (r.statusCode !== 200) throw new Error(`EDGAR ${r.statusCode} for ${url}`)
  return inflate(r.body)
}

/** Runs on every node. Network failures throw: no verdict, and the claim can
 * never back a trade (AgentDesk requires filing evidence). A claim that cites a
 * filing this company never filed is a wrong claim. */
export const checkOnNode = (req: HTTPSendRequester, claim: ClaimWords, config: Config): Observation => {
  const NONE = "0x" + "00".repeat(32)
  const cik = Object.hasOwn(config.ciks, claim.ticker) ? config.ciks[claim.ticker] : undefined
  if (!cik) return { fraudulent: true, reason: `no SEC registrant on record for ${claim.ticker}`, evidence: NONE }
  const index = JSON.parse(decodeUtf8(get(req, `https://data.sec.gov/submissions/CIK${cik}.json`, config)))
  const doc = primaryDocument(index, cik, claim.accession)
  if (!doc) return { fraudulent: true, reason: `filing ${claim.accession} is not one of ${claim.ticker}'s recent filings`, evidence: NONE }
  const raw = get(req, doc.url, config)
  const text = toText(decodeUtf8(raw))
  const v = auditClaim(claim.value, claim.quote, text, claim.summary, claim.metric)
  // Every node must report the same evidence, and SEC's CDN tag varies by time
  // and place, so the hash is of the filing without it.
  return { fraudulent: v.fraudulent, reason: v.reason, evidence: keccak256(canonical(raw)) }
}

export const decodePosted = (log: EVMLog) => {
  const ev = decodeEventLog({
    abi: POSTED,
    data: bytesToHex(log.data),
    topics: log.topics.map((t) => bytesToHex(t)) as [Hex, ...Hex[]],
  })
  return ev.args
}

export const onPosted = (runtime: Runtime<Config>, log: EVMLog): string => {
  const config = runtime.config
  const posted = decodePosted(log)
  if (keccak256(posted.claim) !== posted.claimHash) throw new Error("claim words do not match their hash")
  // Words that are not a well-formed claim, or that name another stock or filing
  // than the one the contract stored, are wrong claims, decided here without a
  // fetch. Throwing instead would leave the claim waiting for a verdict that never
  // comes, which is the one outcome an analyst could exploit.
  const NONE = ("0x" + "00".repeat(32)) as Hex
  let parsed: unknown = null
  try {
    parsed = JSON.parse(decodeUtf8(hexToBytes(posted.claim)))
  } catch {}
  const ok = claimSchema.safeParse(parsed)
  let seen: Observation
  if (!ok.success) seen = { fraudulent: true, reason: "the posted words are not a well-formed claim", evidence: NONE }
  else if (ok.data.ticker !== posted.ticker || ok.data.accession !== posted.filing)
    seen = { fraudulent: true, reason: "the claim's words name another stock or filing than the one it was posted under", evidence: NONE }
  else {
    const claim = ok.data
    runtime.log(`claim #${posted.id} ${claim.ticker} ${claim.value} by ${claim.analyst}, citing ${claim.accession}`)
    seen = new cre.capabilities.HTTPClient()
      .sendRequest(runtime, checkOnNode, consensusIdenticalAggregation<Observation>())(claim, config)
      .result()
  }
  runtime.log(`verdict: ${seen.fraudulent ? "SLASH" : "CLEAR"} (${seen.reason}); filing keccak256 ${seen.evidence}`)

  const payload = encodeAbiParameters(REPORT, [posted.id, posted.claimHash, seen.fraudulent, seen.evidence as Hex, seen.reason])
  const network = getNetwork({ chainFamily: "evm", chainSelectorName: config.chainSelectorName, isTestnet: true })
  if (!network) throw new Error(`unknown chain ${config.chainSelectorName}`)
  const evm = new cre.capabilities.EVMClient(network.chainSelector.selector)
  const report = runtime.report(prepareReportRequest(payload)).result()
  const w = evm.writeReport(runtime, { receiver: config.market, report, gasConfig: { gasLimit: config.gasLimit } }).result()
  if (w.txStatus !== TxStatus.SUCCESS) throw new Error(`verdict write failed: ${w.errorMessage || w.txStatus}`)
  const tx = bytesToHex(w.txHash || new Uint8Array(32))
  // 1 = RECEIVER_CONTRACT_EXECUTION_STATUS_REVERTED: the forwarder's transaction
  // succeeded but onReport refused the report (wrong workflow, wrong claim).
  if (w.receiverContractExecutionStatus === 1) runtime.log(`WARNING: BondedClaims refused the report in ${tx}`)
  runtime.log(`verdict for claim #${posted.id} written: ${tx}`)
  return `#${posted.id} ${seen.fraudulent ? "slashed" : "cleared"} ${tx}`
}

export function initWorkflow(config: Config) {
  const network = getNetwork({ chainFamily: "evm", chainSelectorName: config.chainSelectorName, isTestnet: true })
  if (!network) throw new Error(`unknown chain ${config.chainSelectorName}`)
  const evm = new cre.capabilities.EVMClient(network.chainSelector.selector)
  return [
    cre.handler(
      evm.logTrigger({ addresses: [hexToBase64(config.market)], topics: [{ values: [hexToBase64(POSTED_TOPIC)] }] }),
      onPosted,
    ),
  ]
}
