// Settles a posted round with the workflow's own handler, in the Chainlink CRE
// SDK's test runtime: the fallback when `cre workflow simulate` cannot run (no
// CRE login). For every claim the round posted it reads the Posted log from the
// chain, runs onPosted (the same code the simulator and a DON run) with the
// SDK's HTTP mock serving SEC's files from the round's EDGAR cache, and keeps
// the report the SDK built. scripts/sdk_round.sh then delivers each report
// through the local forwarder. Run by that script:
//
//   VOUCH_RPC=... VOUCH_MARKET=0x... VOUCH_POSTS=feed.posts.txt VOUCH_SDK_OUT=reports.json bun test ./sdk-round.ts
//
// What this is not: a CRE CLI simulation or a DON. One process plays every
// node; consensus is the SDK's test consensus; nothing is signed.
import { existsSync, readFileSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { TxStatus } from "@chainlink/cre-sdk"
import { EvmMock, HttpActionsMock, newTestRuntime, REPORT_METADATA_HEADER_LENGTH, test } from "@chainlink/cre-sdk/test"
import { gzipSync } from "fflate"
import { bytesToHex, decodeAbiParameters, hexToBytes } from "viem"
import { type Config, POSTED_TOPIC, REPORT, onPosted } from "./workflow"
import staging from "./config.staging.json"

const CACHE = join(import.meta.dir, "..", "..", ".cache", "edgar")
const cacheKey = (url: string) => url.split("://")[1].replace(/[^A-Za-z0-9._-]/g, "_")
const CHAIN = 2032988798112970440n // robinhood-testnet, as in the staging config

async function rpc(url: string, method: string, params: unknown[]) {
  const r = await fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) })
  const j = (await r.json()) as { result?: any; error?: { message: string } }
  if (j.error) throw new Error(`${method}: ${j.error.message}`)
  return j.result
}

test("settle a posted round with the workflow handler in the CRE SDK test runtime", async () => {
  const { VOUCH_RPC, VOUCH_MARKET, VOUCH_POSTS, VOUCH_SDK_OUT } = process.env
  if (!VOUCH_RPC || !VOUCH_MARKET || !VOUCH_POSTS || !VOUCH_SDK_OUT) throw new Error("set VOUCH_RPC, VOUCH_MARKET, VOUCH_POSTS and VOUCH_SDK_OUT")
  const config = { ...staging, market: VOUCH_MARKET } as Config

  // SEC, as the HTTP capability would see it: gzipped, under the 250 KB
  // response limit, and refused without a contact in the User-Agent.
  const fetched: string[] = []
  const http = HttpActionsMock.testInstance()
  http.sendRequest = (req) => {
    fetched.push(req.url)
    const ua = req.multiHeaders?.["User-Agent"]?.values?.[0] ?? ""
    if (!ua.includes("@")) return { statusCode: 403 }
    const path = join(CACHE, cacheKey(req.url))
    if (!existsSync(path)) return { statusCode: 404 }
    const body = gzipSync(new Uint8Array(readFileSync(path)))
    if (body.length > 250_000) return { statusCode: 413 }
    return { statusCode: 200, body: Buffer.from(body).toString("base64") }
  }
  let written: any = null
  const evm = EvmMock.testInstance(CHAIN)
  evm.writeReport = (input) => ((written = input), { txStatus: TxStatus.SUCCESS, txHash: new Uint8Array(32) })

  const out: object[] = []
  for (const line of readFileSync(VOUCH_POSTS, "utf8").split("\n").filter(Boolean)) {
    const [id, tx] = line.trim().split(/\s+/)
    const receipt = await rpc(VOUCH_RPC, "eth_getTransactionReceipt", [tx])
    const log = receipt.logs.find((l: any) => l.address.toLowerCase() === VOUCH_MARKET.toLowerCase() && l.topics[0] === POSTED_TOPIC)
    if (!log) throw new Error(`no Posted log in ${tx}`)
    written = null
    fetched.length = 0
    const runtime = newTestRuntime<Config>(null, {}, config)
    onPosted(runtime as any, { address: hexToBytes(log.address), topics: log.topics.map((t: string) => hexToBytes(t as `0x${string}`)), data: hexToBytes(log.data) } as any)
    const raw: Uint8Array = written.report.rawReport
    const [claimId, , fraudulent, evidence, reason] = decodeAbiParameters(REPORT, bytesToHex(raw.slice(REPORT_METADATA_HEADER_LENGTH)))
    if (claimId !== BigInt(id)) throw new Error(`report for #${claimId}, posted #${id}`)
    out.push({ id: Number(id), tx_post: tx, raw: bytesToHex(raw), fraudulent, reason, evidence, fetched: [...fetched], logs: (runtime as any).getLogs() })
    console.log(`#${id} ${fraudulent ? "SLASH" : "clear"} ${reason}`)
  }
  writeFileSync(VOUCH_SDK_OUT, JSON.stringify(out, null, 1))
})   // the SDK's test() takes no timeout: sdk_round.sh passes --timeout
