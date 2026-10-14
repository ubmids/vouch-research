// The workflow handler, run in the CRE SDK's test runtime with its own HTTP and
// EVM capability mocks. The HTTP mock serves the real SEC files from the
// repository's EDGAR cache, gzipped as SEC sends them. What is asserted is
// what reaches the chain: the report payload the forwarder would hand to
// BondedClaims.onReport.
import { test as bunTest, describe, expect } from "bun:test"
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { TxStatus } from "@chainlink/cre-sdk"
import { EvmMock, HttpActionsMock, newTestRuntime, REPORT_METADATA_HEADER_LENGTH, test } from "@chainlink/cre-sdk/test"
import { gzipSync } from "fflate"
import { bytesToHex, decodeAbiParameters, encodeAbiParameters, encodeEventTopics, hexToBytes, keccak256, toBytes } from "viem"
import { type Config, POSTED, REPORT, initWorkflow, onPosted } from "./workflow"
import { canonical as canonicalFiling } from "./check/edgar"
import config from "./config.staging.json"

const CACHE = join(import.meta.dir, "..", "..", ".cache", "edgar")
const cacheKey = (url: string) => url.split("://")[1].replace(/[^A-Za-z0-9._-]/g, "_")
const TSLA_10Q = "https://www.sec.gov/Archives/edgar/data/1318605/000162828026049270/tsla-20260630.htm"
const TSLA_INDEX = "https://data.sec.gov/submissions/CIK0001318605.json"
const have = existsSync(join(CACHE, cacheKey(TSLA_10Q))) && existsSync(join(CACHE, cacheKey(TSLA_INDEX)))
const CHAIN = 2032988798112970440n // robinhood-testnet
// The SDK's test() sets up its runtime; skip (without the EDGAR cache) through bun's.
const withFilings = (name: string, fn: () => void) => (have ? test(name, fn) : bunTest.skip(name, fn))
const SENTENCE =
  "Depreciation expense during the three and six months ended June 30, 2026 was $1.37 billion and $2.71 billion, respectively."

// The canonical claim JSON, exactly as agent/vouchrh/claims.py writes it: keys sorted, no spaces, UTF-8.
const canonical = (c: Record<string, string>) =>
  JSON.stringify(Object.fromEntries(Object.keys(c).sort().map((k) => [k, c[k]])))

const claimOf = (value: string, quote: string, summary: string) => ({
  accession: "0001628280-26-049270", analyst: "Qwen 2.5 7B", metric: "Depreciation expense", quote, summary, ticker: "TSLA", value,
})

function postedLog(id: bigint, words: string, ticker = "TSLA", filing = "0001628280-26-049270") {
  const claim = toBytes(words)
  const topics = encodeEventTopics({ abi: POSTED, eventName: "Posted", args: { id, analyst: "0x1618A08FA335DBe562526033D839E90E0D2e400b" } })
  const data = encodeAbiParameters(
    [{ type: "string" }, { type: "string" }, { type: "bytes32" }, { type: "uint256" }, { type: "bytes" }],
    [ticker, filing, keccak256(claim), 25_000_000n, bytesToHex(claim)],
  )
  return { address: hexToBytes(config.market as `0x${string}`), topics: topics.map((t) => hexToBytes(t as `0x${string}`)), data: hexToBytes(data) } as any
}

function serveEdgar(seen: string[], cdnPath?: string) {
  const http = HttpActionsMock.testInstance()
  http.sendRequest = (req) => {
    seen.push(req.url)
    const ua = req.multiHeaders?.["User-Agent"]?.values?.[0] ?? ""
    const gz = req.multiHeaders?.["Accept-Encoding"]?.values?.[0] ?? ""
    if (!ua.includes("@") || gz !== "gzip") return { statusCode: 403 }
    const path = join(CACHE, cacheKey(req.url))
    if (!existsSync(path)) return { statusCode: 404 }
    let file = new Uint8Array(readFileSync(path))
    // SEC's CDN tags each document with a script whose path changes over time
    if (cdnPath) file = new TextEncoder().encode(new TextDecoder().decode(file).replace(/src="\/[^"]*"><\/script>/, `src="/${cdnPath}"></script>`))
    const body = gzipSync(file)
    if (body.length > 250_000) return { statusCode: 413 } // CRE's response limit
    return { statusCode: 200, body: Buffer.from(body).toString("base64") }
  }
  return http
}

function run(id: bigint, value: string, quote: string, summary: string, cdnPath?: string) {
  const seen: string[] = []
  serveEdgar(seen, cdnPath)
  const evm = EvmMock.testInstance(CHAIN)
  let written: any = null
  evm.writeReport = (input) => {
    written = input
    return { txStatus: TxStatus.SUCCESS, txHash: new Uint8Array(32).fill(7) }
  }
  const runtime = newTestRuntime<Config>(null, {}, { ...config, gasLimit: "1000000" } as Config)
  const words = canonical(claimOf(value, quote, summary))
  const out = onPosted(runtime as any, postedLog(id, words))
  const raw: Uint8Array = written.report.rawReport
  const [claimId, claimHash, fraudulent, evidence, reason] = decodeAbiParameters(REPORT, bytesToHex(raw.slice(REPORT_METADATA_HEADER_LENGTH)))
  return { out, seen, written, raw, words, claimId, claimHash, fraudulent, evidence, reason }
}

describe("the Vouch verifier workflow", () => {
  test("listens for Posted on the market", () => {
    const handlers = initWorkflow(config as Config)
    expect(handlers).toHaveLength(1)
    expect(handlers[0].fn).toBe(onPosted)
  })

  withFilings("clears a claim that says what the filing says", () => {
    const r = run(4n, "$1.37 billion", SENTENCE, "Tesla's depreciation was $1.37 billion in Q2 2026.")
    expect(r.fraudulent).toBe(false)
    expect(r.reason).toBe("quote verified and value grounded")
    expect(r.claimId).toBe(4n)
    expect(r.claimHash).toBe(keccak256(toBytes(r.words)))
    // the evidence is the keccak256 of the bytes EDGAR serves for this accession, less the CDN's tag
    expect(r.evidence).toBe(keccak256(canonicalFiling(new Uint8Array(readFileSync(join(CACHE, cacheKey(TSLA_10Q)))))))
    expect(r.seen).toEqual([TSLA_INDEX, TSLA_10Q])
    expect(bytesToHex(r.written.receiver)).toBe(config.market.toLowerCase())
  })

  withFilings("slashes the AI's wrong quarter, with the reason on-chain", () => {
    const r = run(6n, "$1.37 billion", SENTENCE, "Depreciation for Q3 2026 was $1.37 billion.")
    expect(r.fraudulent).toBe(true)
    expect(r.reason).toBe("wrong quarter: the period ended in June, the claim says Q3 2026")
    if (process.env.VOUCH_REPORT_OUT) {
      // for tests/test_cre_report.py: the SDK-built report, delivered to the contract on anvil
      mkdirSync(process.env.VOUCH_REPORT_OUT, { recursive: true })
      writeFileSync(join(process.env.VOUCH_REPORT_OUT, "wrong-quarter.json"), JSON.stringify({ raw: bytesToHex(r.raw), claim: r.words }))
    }
  })

  withFilings("every node reports the same evidence, whatever script SEC's CDN adds", () => {
    const a = run(4n, "$1.37 billion", SENTENCE, "", "AAAA/one/path")
    const b = run(4n, "$1.37 billion", SENTENCE, "", "zz/another/path/9")
    expect(a.evidence).toBe(b.evidence)
    expect(a.fraudulent).toBe(false)
  })

  withFilings("slashes a quote with one figure changed", () => {
    const r = run(8n, "$1.47 billion", SENTENCE.replace("$1.37", "$1.47"), "")
    expect(r.fraudulent).toBe(true)
    expect(r.reason).toBe("supporting quote not found in source document")
  })

  withFilings("slashes a claim citing a filing the company never made", () => {
    const seen: string[] = []
    serveEdgar(seen)
    const evm = EvmMock.testInstance(CHAIN)
    let written: any = null
    evm.writeReport = (input) => ((written = input), { txStatus: TxStatus.SUCCESS, txHash: new Uint8Array(32) })
    const runtime = newTestRuntime<Config>(null, {}, config as Config)
    const words = canonical({ ...claimOf("$1.37 billion", SENTENCE, ""), accession: "0000000000-26-000000" })
    onPosted(runtime as any, postedLog(9n, words, "TSLA", "0000000000-26-000000"))
    const [, , fraudulent, , reason] = decodeAbiParameters(REPORT, bytesToHex(written.report.rawReport.slice(REPORT_METADATA_HEADER_LENGTH)))
    expect(fraudulent).toBe(true)
    expect(reason).toBe("filing 0000000000-26-000000 is not one of TSLA's recent filings")
    expect(seen).toEqual([TSLA_INDEX]) // never fetched a document for it
  })

  // A claim that can never be checked must not be left waiting: it is slashed, with no fetch.
  const reportFor = (log: any) => {
    const seen: string[] = []
    serveEdgar(seen)
    const evm = EvmMock.testInstance(CHAIN)
    let written: any = null
    evm.writeReport = (input) => ((written = input), { txStatus: TxStatus.SUCCESS, txHash: new Uint8Array(32) })
    onPosted(newTestRuntime<Config>(null, {}, config as Config) as any, log)
    const [, , fraudulent, , reason] = decodeAbiParameters(REPORT, bytesToHex(written.report.rawReport.slice(REPORT_METADATA_HEADER_LENGTH)))
    return { fraudulent, reason, seen }
  }

  test("slashes words that are not a well-formed claim, without fetching anything", () => {
    for (const words of ["{not json", JSON.stringify({ ticker: "TSLA", value: 137 }), canonical({ ...claimOf("$1.37 billion", SENTENCE, ""), accession: "x" })]) {
      const r = reportFor(postedLog(10n, words))
      expect(r.fraudulent).toBe(true)
      expect(r.reason).toBe("the posted words are not a well-formed claim")
      expect(r.seen).toEqual([])
    }
  })

  test("slashes words about another stock than the one posted under", () => {
    const words = canonical({ ...claimOf("$1.37 billion", SENTENCE, ""), ticker: "AMD" })
    const r = reportFor(postedLog(11n, words)) // the log says TSLA
    expect(r.fraudulent).toBe(true)
    expect(r.reason).toBe("the claim's words name another stock or filing than the one it was posted under")
  })

  test("a ticker named like an object property is just an unknown company", () => {
    const words = canonical({ ...claimOf("$1.37 billion", SENTENCE, ""), ticker: "constructor" })
    const log = postedLog(12n, words, "constructor")
    const r = reportFor(log)
    expect(r.fraudulent).toBe(true)
    expect(r.reason).toBe("no SEC registrant on record for constructor")
    expect(r.seen).toEqual([])
  })

  test("refuses words that do not match their hash", () => {
    serveEdgar([])
    const runtime = newTestRuntime<Config>(null, {}, config as Config)
    const log = postedLog(1n, canonical(claimOf("$1.37 billion", SENTENCE, "")))
    log.data[log.data.length - 40] ^= 1 // flip a bit in the claim words
    expect(() => onPosted(runtime as any, log)).toThrow()
  })
})
