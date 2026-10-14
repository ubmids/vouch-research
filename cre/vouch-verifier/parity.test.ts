// The workflow's check must be the market's check. For each stock token's
// 10-Q, the TypeScript port reads the same bytes into the same text and gives
// the same verdict, reason and score as agent/vouchrh/verifier.py on every
// fixture claim (scripts/cre_fixtures.py writes them; the filings come from the
// repository's EDGAR cache, which `bun run fixtures`, `pytest` or that script fills).
import { describe, expect, test } from "bun:test"
import { existsSync, readdirSync, readFileSync } from "node:fs"
import { join } from "node:path"
import { keccak256 } from "viem"
import { auditClaim } from "./check/verifier"
import { canonical, decodeUtf8, toText } from "./check/edgar"

const FIXTURES = join(import.meta.dir, "fixtures")
const CACHE = join(import.meta.dir, "..", "..", ".cache", "edgar")
const cacheKey = (url: string) => url.split("://")[1].replace(/[^A-Za-z0-9._-]/g, "_")

type Claim = { value: string; quote: string; summary: string; metric: string; want: { fraudulent: boolean; reason: string; method: string; score: number } }
type Fixture = { ticker: string; url: string; evidence_keccak: string; text_sha256: string; text_length: number; claims: Claim[] }

const missing: string[] = []

for (const name of readdirSync(FIXTURES).filter((f) => f.endsWith(".json")).sort()) {
  const fx: Fixture = JSON.parse(readFileSync(join(FIXTURES, name), "utf8"))
  const path = join(CACHE, cacheKey(fx.url))
  const have = existsSync(path)
  if (!have) missing.push(fx.ticker)
  describe(`${fx.ticker} 10-Q`, () => {
    test.skipIf(!have)("the same bytes and the same text as the Python check", () => {
      const raw = new Uint8Array(readFileSync(path))
      // the bytes SEC serves, less the tag its CDN adds (it changes over time)
      expect(keccak256(canonical(raw))).toBe(fx.evidence_keccak)
      const text = toText(decodeUtf8(raw))
      expect(text.length).toBe(fx.text_length)
      expect(new Bun.CryptoHasher("sha256").update(text).digest("hex")).toBe(fx.text_sha256)
    })
    test.skipIf(!have)(`the same verdict on all ${fx.claims.length} claims`, () => {
      const text = toText(decodeUtf8(new Uint8Array(readFileSync(path))))
      const wrong: string[] = []
      for (const c of fx.claims) {
        const v = auditClaim(c.value, c.quote, text, c.summary, c.metric)
        const got = { fraudulent: v.fraudulent, reason: v.reason, method: v.quoteCheck.method, score: v.quoteCheck.score }
        if (JSON.stringify(got) !== JSON.stringify(c.want)) wrong.push(`${JSON.stringify(c)}\n  got ${JSON.stringify(got)}`)
      }
      expect(wrong.slice(0, 3)).toEqual([])
    }, 120_000)
  })
}

if (missing.length) console.log(`\nparity: no cached 10-Q for ${missing.join(", ")}; those tests skip. Run \`bun run fixtures\` first.\n`)
