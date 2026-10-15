// Fills the repository's EDGAR cache with the five 10-Qs the parity fixtures
// were written against, and the submissions index of each company, so
// `bun test` runs every test on a fresh clone:
//
//   bun run fixtures && bun test
//
// The cache is the one agent/vouchrh/edgar.py uses (same file names), so
// pytest and the CRE tests read the same bytes. SEC's fair-access policy:
// a contact in the User-Agent, well under ten requests a second.
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import config from "./config.staging.json"

const FIXTURES = join(import.meta.dir, "fixtures")
const CACHE = join(import.meta.dir, "..", "..", ".cache", "edgar")
const cacheKey = (url: string) => url.split("://")[1].replace(/[^A-Za-z0-9._-]/g, "_")

const urls: string[] = []
for (const name of readdirSync(FIXTURES).filter((f) => f.endsWith(".json")).sort())
  urls.push(JSON.parse(readFileSync(join(FIXTURES, name), "utf8")).url)
for (const cik of Object.values(config.ciks)) urls.push(`https://data.sec.gov/submissions/CIK${cik}.json`)

// SEC wants a contact in the User-Agent; the one place it is set is agent/vouchrh/edgar.py.
const UA = process.env.VOUCH_SEC_CONTACT ?? new TextDecoder().decode(Bun.spawnSync(
  ["python3", "-c", "from vouchrh.edgar import CONTACT; print(CONTACT)"],
  { cwd: join(import.meta.dir, "../.."), env: { ...process.env, PYTHONPATH: "agent" } }).stdout).trim()
if (!UA.includes("@")) throw new Error("no SEC contact: set VOUCH_SEC_CONTACT, or check agent/vouchrh/edgar.py")

mkdirSync(CACHE, { recursive: true })
let fetched = 0
for (const url of urls) {
  const path = join(CACHE, cacheKey(url))
  if (existsSync(path)) continue
  await Bun.sleep(200)
  const r = await fetch(url, { headers: { "User-Agent": UA, "Accept-Encoding": "identity" } })
  if (!r.ok) throw new Error(`EDGAR ${r.status} for ${url}`)
  writeFileSync(path, new Uint8Array(await r.arrayBuffer()))
  fetched++
  console.log(`fetched ${url}`)
}
console.log(`${fetched} fetched, ${urls.length - fetched} already cached, in ${CACHE}`)
