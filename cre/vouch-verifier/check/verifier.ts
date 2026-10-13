// The deterministic claim check, ported line for line from
// agent/vouchrh/verifier.py so that every node of the Chainlink DON reaches the
// verdict the Python market and the hosted API reach. Parity is tested in
// cre/vouch-verifier/parity.test.ts against fixtures the Python check wrote
// (scripts/cre_fixtures.py): same verdict, same reason string, same score.
//
// A claim is fraudulent if its quote is not genuinely in the filing (exact, or
// a near-match with every figure exactly as filed), if its value is not in its
// quote, if the quote is not a whole sentence, or if its summary states a
// figure, period, quarter, date or direction the sentence does not.

import { ratio } from "./difflib"
import { B0, B1, WS, floordiv, pycount, pysplit, pystrip, round } from "./pyre"

export const FUZZY_FLOOR = 0.95

const S = `[${WS}]`
const re = (src: string, flags = "") => new RegExp(src, "u" + flags)
const findall = (r: RegExp, text: string): string[] => Array.from(text.matchAll(new RegExp(r.source, r.flags.includes("g") ? r.flags : r.flags + "g")), (m) => m[0])

const FIGURE = re(`\\d[\\d,]*(?:\\.\\d+)?%?|${B0}(?:thousand|million|billion|trillion)${B1}`, "g")

export function figures(text: string): string[] {
  return findall(FIGURE, text).map((f) => f.replaceAll(",", ""))
}

function figuresHold(quote: string, span: string): boolean {
  const have = figures(span)
  for (const f of figures(quote)) {
    const i = have.indexOf(f)
    if (i < 0) return false
    have.splice(i, 1)
  }
  return true
}

const DEHYPHEN = re(`([\\p{L}\\p{N}_])-${S}*\\n${S}*([\\p{L}\\p{N}_])`, "g")
const WS_RUN = re(`${S}+`, "g")

export function normalize(text: string): string {
  let t = text.replaceAll("‘", "'").replaceAll("’", "'")
  t = t.replaceAll("“", '"').replaceAll("”", '"')
  t = t.replaceAll("–", "-").replaceAll("—", "-")
  t = t.replace(DEHYPHEN, "$1$2")
  t = t.replace(WS_RUN, " ")
  return pystrip(t).toLowerCase()
}

export type QuoteCheck = { verified: boolean; method: "exact" | "fuzzy" | "figures-differ" | "none"; score: number }

export function verifyQuote(quote: string, sourceText: string): QuoteCheck {
  const q = normalize(quote)
  const src = normalize(sourceText)
  if (!q) return { verified: false, method: "none", score: 0.0 }
  if (src.includes(q)) return { verified: true, method: "exact", score: 1.0 }
  const words = pysplit(q)
  if (words.length < 3) return { verified: false, method: "none", score: 0.0 }
  let anchor = words[0]
  let anchorKey = Infinity
  for (const w of words) {
    const n = pycount(src, w)
    const key = n > 0 ? n : 10 ** 6
    if (key < anchorKey) {
      anchor = w
      anchorKey = key
    }
  }
  if (pycount(src, anchor) === 0) return { verified: false, method: "none", score: 0.0 }
  const offset = q.indexOf(anchor)
  let best = 0.0
  let bestSpan = ""
  let start = 0
  for (;;) {
    const i = src.indexOf(anchor, start)
    if (i === -1) break
    const base = Math.max(0, i - offset)
    for (const slack of [0, floordiv(-q.length, 20), floordiv(q.length, 20)]) {
      const span = src.slice(base, Math.max(base, base + q.length + slack))
      const r = ratio(q, span)
      if (r > best) {
        best = r
        bestSpan = span
      }
    }
    start = i + 1
  }
  if (best >= FUZZY_FLOOR) {
    if (!figuresHold(q, bestSpan)) return { verified: false, method: "figures-differ", score: round(best, 4) }
    return { verified: true, method: "fuzzy", score: round(best, 4) }
  }
  return { verified: false, method: "none", score: round(best, 4) }
}

export type Verdict = { fraudulent: boolean; reason: string; quoteCheck: QuoteCheck }

export function auditAttestation(claimedValue: string, quote: string, sourceText: string): Verdict {
  const qc = verifyQuote(quote, sourceText)
  if (!qc.verified) return { fraudulent: true, reason: "supporting quote not found in source document", quoteCheck: qc }
  if (!normalize(quote).includes(normalize(claimedValue)))
    return { fraudulent: true, reason: "claimed value not grounded in the cited quote", quoteCheck: qc }
  return { fraudulent: false, reason: "quote verified and value grounded", quoteCheck: qc }
}

// ---- checking the claim as written, not only its quote ----------------------

const SPAN: Record<string, number> = { three: 3, six: 6, nine: 9, twelve: 12 }
const MONTHS = "january february march april may june july august september october november december".split(" ")
const MONTH = new Map<string, number>(MONTHS.map((m, i) => [m, i + 1]))   // a Map: no prototype keys
const DATE = "([A-Z][a-z]+) (\\d{1,2}), (\\d{4})"
const MULTI = re(`${B0}(three|six|nine|twelve) and (three|six|nine|twelve) months ended ${DATE}`)
const SINGLE = re(`${B0}(three|six|nine|twelve) months ended ${DATE}`, "g")
const AMOUNT = re(
  `\\$${S}?\\(?\\d[\\d,]*(?:\\.\\d+)?\\)?(?:${S}(?:thousand|million|billion|trillion))?|\\d[\\d,]*(?:\\.\\d+)?${S}?%`,
  "g",
)
const SCALE: Record<string, number> = { thousand: 1e3, million: 1e6, billion: 1e9, trillion: 1e12 }

const SENT_SPLIT = re(`(?<=[.;])${S}+(?=[A-Z(])`)

/** The filing's sentences: split per line, then at ". " or "; " before a capital. */
export function sentences(text: string): string[] {
  const out: string[] = []
  for (const line of text.split("\n")) {
    for (const s of pysplit(line).join(" ").split(SENT_SPLIT)) {
      const t = pystrip(s)
      if (t) out.push(t)
    }
  }
  return out
}

const AMOUNT1 = re(`^\\$?${S}?\\(?(\\d[\\d,]*(?:\\.\\d+)?)\\)?${S}?(%|thousand|million|billion|trillion)?`)

/** '$1.37 billion' -> 1.37e9, '43 %' -> 43.0 (percent), '$(48) million' -> 48e6. */
export function amount(text: string): number | null {
  const m = pystrip(text).match(AMOUNT1)
  if (!m) return null
  const n = Number(m[1].replaceAll(",", ""))
  const unit = m[2]
  return unit === "%" ? n : n * (SCALE[unit ?? ""] ?? 1)
}

export function amounts(text: string): number[] {
  return findall(AMOUNT, text)
    .map(amount)
    .filter((a): a is number => a !== null)
}

const close = (a: number, v: number) => Math.abs(a - v) < 1e-6 * Math.max(1, v)

type Span = [number, number | null, number]

function spanOfValue(quote: string, value: string): Span | null {
  const v = amount(value)
  const multi = quote.match(MULTI)
  const single = Array.from(quote.matchAll(SINGLE))
  if (multi && quote.includes("respectively") && v !== null) {
    const spans = [SPAN[multi[1]], SPAN[multi[2]]]
    const end = multi.index! + multi[0].length
    let after = amounts(quote.slice(end))
    if (!after.length) after = amounts(quote.slice(0, multi.index!)).slice(-spans.length)
    const head = after.slice(0, spans.length)
    for (let i = 0; i < head.length; i++)
      if (close(head[i], v)) return [spans[i], MONTH.get(multi[3].toLowerCase()) ?? null, Number(multi[5])]
    return null
  }
  if (!multi && single.length) {
    const seen = new Map<string, Span>()
    for (const m of single) {
      const s: Span = [SPAN[m[1]], MONTH.get(m[2].toLowerCase()) ?? null, Number(m[4])]
      seen.set(s.join("|"), s)
    }
    const spans = Array.from(seen.values())
    let latest = spans[0]
    for (const s of spans) {
      const k = [s[2], s[1] ?? 0]
      const l = [latest[2], latest[1] ?? 0]
      if (k[0] > l[0] || (k[0] === l[0] && k[1] > l[1])) latest = s
    }
    if (new Set(spans.map((s) => s[0])).size === 1) return latest
  }
  return null
}

const ASOF_TWO = re(`${B0}as of ${DATE} and ${DATE}`)

type When = [number | null, number]

function dateOfValue(quote: string, value: string): When | null {
  const m = quote.match(ASOF_TWO)
  const v = amount(value)
  if (!m || v === null) return null
  const dates: When[] = [
    [MONTH.get(m[1].toLowerCase()) ?? null, Number(m[3])],
    [MONTH.get(m[4].toLowerCase()) ?? null, Number(m[6])],
  ]
  const everything = amounts(quote)
  if (everything.length !== 2 && !quote.includes("respectively")) return null
  const vals = (everything.length !== 2 ? amounts(quote.slice(m.index! + m[0].length)) : everything).slice(0, 2)
  if (vals.length === 2 && vals[0] !== vals[1]) {
    for (let i = 0; i < vals.length; i++) if (close(vals[i], v)) return dates[i]
  }
  return null
}

const CLAIMED_DATE = re(`${B0}as of ([A-Z][a-z]+)(?: \\d{1,2},)? (\\d{4})`)

function claimedDate(text: string): When | null {
  const m = text.match(CLAIMED_DATE)
  return m && MONTH.has(m[1].toLowerCase()) ? [MONTH.get(m[1].toLowerCase())!, Number(m[2])] : null
}

type Period = [number, number | null, number | null]

function claimedPeriod(text: string): Period | null {
  const t = text.toLowerCase()
  if (re(`${B0}(three|six|nine|twelve) and (three|six|nine|twelve)${B1}`).test(t)) return null
  const q = t.match(re(`${B0}q([1-4])(?:${S}*(?:fy)?${S}*(\\d{4}))?${B1}`))
  if (q) return [3, Number(q[1]), q[2] ? Number(q[2]) : null]
  const m = t.match(re(`${B0}(three|six|nine|twelve)[- ]months?${B1}`))
  if (m) return [SPAN[m[1]], null, null]
  if (re(`${B0}(first half|half[- ]year|h1)${B1}`).test(t)) return [6, null, null]
  if (re(`${B0}(quarter|quarterly)${B1}`).test(t)) return [3, null, null]
  return null
}

function label(p: Period): string {
  const [months, q, year] = p
  if (q) return `Q${q}${year ? " " + year : ""}`
  return ({ 3: "a quarter", 6: "six months", 9: "nine months", 12: "a year" } as Record<number, string>)[months]
}

const UP = re(`${B0}(increase[sd]?|rose|rise[sn]?|grew|grow(?:th|s)?|higher)${B1}`, "gi")
const DOWN = re(`${B0}(decrease[sd]?|declined?|fell|fall(?:s|en)?|lower|drop(?:ped|s)?)${B1}`, "gi")

/** 'up', 'down' or null: the direction word closest to the figure, within reach. */
export function directionNear(text: string, value: string, reach = 80): "up" | "down" | null {
  const v = amount(value)
  const spots: number[] = []
  if (v !== null)
    for (const m of text.matchAll(AMOUNT)) {
      const a = amount(m[0])
      if (a !== null && close(a, v)) spots.push(m.index!)
    }
  let best: [number, "up" | "down"] | null = null
  for (const pos of spots)
    for (const [word, pattern] of [
      ["up", UP],
      ["down", DOWN],
    ] as const)
      for (const m of text.matchAll(pattern)) {
        const d = Math.abs(m.index! - pos)
        if (d <= reach && (best === null || d < best[0])) best = [d, word]
      }
  return best ? best[1] : null
}

const GAIN = re(`${B0}gains?${B1}`, "i")
const LOSS = re(`${B0}loss(es)?${B1}`, "i")
const monthName = (i: number | null) => {
  const m = MONTHS[(i ?? 0) - 1] ?? ""
  return m.charAt(0).toUpperCase() + m.slice(1)
}

/** The whole claim: its quote, its value, and what its summary says about them. */
export function auditClaim(value: string, quote: string, sourceText: string, summary = "", metric = ""): Verdict {
  const v = auditAttestation(value, quote, sourceText)
  if (v.fraudulent) return v
  const q = normalize(quote)
  const whole = new Set(sentences(sourceText).map(normalize))
  let isWhole = whole.has(q)
  if (!isWhole && v.quoteCheck.method === "fuzzy") {
    for (const s of whole) {
      if (Math.abs(s.length - q.length) < 30 && ratio(q, s) >= FUZZY_FLOOR) {
        isWhole = true
        break
      }
    }
  }
  if (!isWhole) return { fraudulent: true, reason: "the quote is a fragment, not a whole sentence of the filing", quoteCheck: v.quoteCheck }
  const said = summary || ""
  if (said) {
    const quoted = amounts(quote)
    const derived: number[] = []
    for (let i = 0; i < quoted.length; i++)
      for (let j = i + 1; j < quoted.length; j++) derived.push(Math.abs(quoted[i] - quoted[j]), quoted[i] + quoted[j])
    for (const a of amounts(said)) {
      if (![...quoted, ...derived].some((b) => Math.abs(a - b) < 1e-6 * Math.max(1, b)))
        return { fraudulent: true, reason: "the summary states a figure its quote does not contain", quoteCheck: v.quoteCheck }
    }
    if (
      (GAIN.test(said) && LOSS.test(quote) && !GAIN.test(quote)) ||
      (LOSS.test(said) && GAIN.test(quote) && !LOSS.test(quote))
    )
      return { fraudulent: true, reason: "the summary reverses what the quote says", quoteCheck: v.quoteCheck }
    const nearS = directionNear(said, value)
    const nearQ = directionNear(quote, value)
    if (nearS && nearQ && nearS !== nearQ)
      return { fraudulent: true, reason: "the summary reverses what the quote says", quoteCheck: v.quoteCheck }
  }
  const ownMetric = !!metric && !q.includes(normalize(metric))
  const claimed = claimedPeriod(said) ?? (ownMetric ? claimedPeriod(metric) : null)
  const owns = dateOfValue(quote, value)
  const says = claimedDate(said) ?? (ownMetric ? claimedDate(metric) : null)
  if (owns && says && (owns[0] !== says[0] || owns[1] !== says[1])) {
    const name = (d: When) => `${monthName(d[0])} ${d[1]}`
    return {
      fraudulent: true,
      reason: `wrong date: the filing gives ${value} as of ${name(owns)}, the claim says ${name(says)}`,
      quoteCheck: v.quoteCheck,
    }
  }
  const actual = spanOfValue(quote, value)
  if (claimed && actual) {
    const [months, endMonth, endYear] = actual
    if (claimed[0] !== months)
      return {
        fraudulent: true,
        reason: `wrong period: the filing gives ${value} for ${label([months, null, null])}, the claim says ${label(claimed)}`,
        quoteCheck: v.quoteCheck,
      }
    if (claimed[1] && endMonth && claimed[1] !== floordiv(endMonth - 1, 3) + 1)
      return {
        fraudulent: true,
        reason: `wrong quarter: the period ended in ${monthName(endMonth)}, the claim says ${label(claimed)}`,
        quoteCheck: v.quoteCheck,
      }
    if (claimed[2] && endYear && claimed[2] !== endYear)
      return {
        fraudulent: true,
        reason: `wrong year: the period ended in ${endYear}, the claim says ${claimed[2]}`,
        quoteCheck: v.quoteCheck,
      }
  }
  return v
}
