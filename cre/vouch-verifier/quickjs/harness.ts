// Runs the workflow's check inside QuickJS (Javy), the engine CRE executes
// workflows in, so parity with Python is shown on the real interpreter and not
// only on Bun's JavaScriptCore. stdin: one JSON line {claims:[...]} then the
// filing's raw bytes. stdout: JSON {raw, text, n, verdicts:[...]}.
import { keccak256 } from "viem"
import { decodeUtf8, toText } from "../check/edgar"
import { auditClaim } from "../check/verifier"

declare const Javy: { IO: { readSync(fd: number, buf: Uint8Array): number; writeSync(fd: number, buf: Uint8Array): void } }

function readAll(): Uint8Array {
  const parts: Uint8Array[] = []
  let total = 0
  for (;;) {
    const buf = new Uint8Array(65536)
    const n = Javy.IO.readSync(0, buf)
    if (n === 0) break
    parts.push(buf.subarray(0, n))
    total += n
  }
  const all = new Uint8Array(total)
  let o = 0
  for (const p of parts) {
    all.set(p, o)
    o += p.length
  }
  return all
}

function utf8(s: string): Uint8Array {
  const out: number[] = []
  for (const ch of s) {
    const c = ch.codePointAt(0)!
    if (c < 0x80) out.push(c)
    else if (c < 0x800) out.push(0xc0 | (c >> 6), 0x80 | (c & 63))
    else if (c < 0x10000) out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63))
    else out.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63))
  }
  return new Uint8Array(out)
}

const input = readAll()
const nl = input.indexOf(10)
const header = JSON.parse(decodeUtf8(input.subarray(0, nl)))
const raw = input.subarray(nl + 1)
const text = toText(decodeUtf8(raw))
const verdicts = header.claims.map((c: any) => {
  const v = auditClaim(c.value, c.quote, text, c.summary, c.metric)
  return { fraudulent: v.fraudulent, reason: v.reason, method: v.quoteCheck.method, score: v.quoteCheck.score }
})
Javy.IO.writeSync(1, utf8(JSON.stringify({ raw: keccak256(raw), text: keccak256(utf8(text)), n: text.length, verdicts })))
