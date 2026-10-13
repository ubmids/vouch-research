// Reading an SEC filing the way agent/vouchrh/edgar.py does: the same bytes,
// decoded the same way, stripped to the same text. The workflow checks a claim
// against this text, so it has to be the text the Python check saw.

import { gunzipSync } from "fflate"
import { HTML5, INVALID_CHARREFS, INVALID_CODEPOINTS } from "./entities"
import { WS } from "./pyre"

const INVALID = new Set(INVALID_CODEPOINTS)
const HTML5_MAP = new Map(Object.entries(HTML5))

/** gzip if it is gzip (SEC answers Accept-Encoding: gzip), the bytes as they are otherwise. */
export function inflate(body: Uint8Array): Uint8Array {
  return body.length > 2 && body[0] === 0x1f && body[1] === 0x8b ? gunzipSync(body) : body
}

/** bytes.decode("utf-8", "ignore"): invalid sequences are dropped, not replaced. */
export function decodeUtf8(b: Uint8Array): string {
  const out: string[] = []
  let chunk: number[] = []
  const flush = () => {
    if (chunk.length) out.push(String.fromCodePoint(...chunk))
    chunk = []
  }
  let i = 0
  while (i < b.length) {
    const c = b[i]
    let cp = -1
    let n = 0
    if (c < 0x80) {
      cp = c
      n = 1
    } else if (c >= 0xc2 && c <= 0xdf) {
      n = 2
    } else if (c >= 0xe0 && c <= 0xef) {
      n = 3
    } else if (c >= 0xf0 && c <= 0xf4) {
      n = 4
    }
    if (n > 1) {
      let ok = i + n <= b.length
      let v = c & (0xff >> (n + 1))
      for (let k = 1; ok && k < n; k++) {
        const d = b[i + k]
        if ((d & 0xc0) !== 0x80) ok = false
        else v = (v << 6) | (d & 0x3f)
      }
      // reject overlongs, surrogates and > U+10FFFF, as Python does
      if (ok && ((n === 3 && (v < 0x800 || (v >= 0xd800 && v <= 0xdfff))) || (n === 4 && (v < 0x10000 || v > 0x10ffff))))
        ok = false
      if (ok) cp = v
      else n = 1
    }
    if (cp >= 0) chunk.push(cp)
    if (chunk.length >= 4096) flush()
    i += n || 1
  }
  flush()
  return out.join("")
}

const CHARREF = /&(#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[^\t\n\f <&#;]{1,32};?)/g

function replaceCharref(s: string): string {
  if (s[0] === "#") {
    const num = s[1] === "x" || s[1] === "X" ? parseInt(s.slice(2).replace(/;$/, ""), 16) : parseInt(s.slice(1).replace(/;$/, ""), 10)
    if (num in INVALID_CHARREFS) return INVALID_CHARREFS[num]
    if ((num >= 0xd800 && num <= 0xdfff) || num > 0x10ffff) return "�"
    if (INVALID.has(num)) return ""
    return String.fromCodePoint(num)
  }
  const hit = HTML5_MAP.get(s)
  if (hit !== undefined) return hit
  for (let x = s.length - 1; x > 1; x--) {
    const h = HTML5_MAP.get(s.slice(0, x))
    if (h !== undefined) return h + s.slice(x)
  }
  return "&" + s
}

/** html.unescape */
export function unescape(s: string): string {
  if (!s.includes("&")) return s
  return s.replace(CHARREF, (_m, g: string) => replaceCharref(g))
}

const S = `[${WS}]`
const SCRIPT = /<(script|style|ix:header)\b.*?<\/\1>/gis
const BREAKS = new RegExp(`<br${S}*/?>|</(p|div|tr|li|h[0-9])>`, "giu")
const TAG = /<[^>]+>/g
const BLANKS = new RegExp(`\\n${S}*\\n+`, "gu")
const SPACES = /[ \t]+/g
const DOLLAR = new RegExp(`\\$${S}+(?=[\\d(])`, "gu")
const PAREN = new RegExp(`\\(${S}+(?=\\d)|(?<=\\d)${S}+\\)`, "gu")
const EDGE = new RegExp(`^${S}+|${S}+$`, "gu")

/** edgar.to_text: the words of a filing, as a reader sees them. */
export function toText(rawHtml: string): string {
  let raw = rawHtml.replace(SCRIPT, " ")
  raw = raw.replace(BREAKS, "\n")
  let text = unescape(raw.replace(TAG, " ")).replaceAll("\xa0", " ")
  text = text.replace(BLANKS, "\n").replace(SPACES, " ")
  text = text.replace(DOLLAR, () => "$")
  return text.replace(PAREN, (m) => m.replace(EDGE, "")).replace(EDGE, "")
}

/** The primary document of a filing, from the company's EDGAR submissions index. */
export function primaryDocument(submissions: unknown, cik: string, accession: string): { url: string; form: string } | null {
  const recent = (submissions as { filings?: { recent?: Record<string, string[]> } })?.filings?.recent
  if (!recent) return null
  const i = recent.accessionNumber?.indexOf(accession) ?? -1
  if (i < 0) return null
  const doc = recent.primaryDocument[i]
  return {
    url: `https://www.sec.gov/Archives/edgar/data/${Number(cik)}/${accession.replaceAll("-", "")}/${doc}`,
    form: recent.form[i],
  }
}
