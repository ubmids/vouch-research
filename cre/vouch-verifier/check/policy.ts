// The trading agent's policy, ported line for line from agent/vouchrh/policy.py,
// so a reader can re-run the agent's reasoning in a browser and get the trade it
// made (web/journal.js is built from this file). Parity: policy.test.ts.

import { B0, B1, W, WS, pysplit } from "./pyre"
import { amount, amounts, directionNear } from "./verifier"

export const POLICY = "vouch-desk-policy/1"
export const RULE =
  "signal per claim = change x polarity; long if the net signal is above zero, short if below, " +
  "no trade at zero; size = per-claim notional x claims that carry a signal"

const S = `[${WS}]`
const re = (src: string, flags = "") => new RegExp(src, "u" + flags)
const GOOD = re(
  `${B0}(revenues?|sales|net income|operating income|gross (?:profit|margin)|profit|` +
    `cash flows? (?:provided by|from) operat[${W}]*|operating cash flows?|free cash flow|bookings|backlog)${B1}`,
  "gi",
)
const BAD = re(
  `${B0}(loss(?:es)?|expenses?|costs?|debt|borrowings?|impairments?|amortization|` +
    `depreciation|restructuring|liabilit(?:y|ies)|(?:income )?tax(?:es)?|provision)${B1}`,
  "gi",
)
const PRIOR = re(
  `${B0}(?:compared (?:to|with)|from|versus|vs\\.?)${S}+(?:losses of |income of |the )?` +
    `(\\$${S}?\\(?\\d[\\d,]*(?:\\.\\d+)?\\)?(?:${S}(?:thousand|million|billion|trillion))?)`,
  "i",
)
const HYPOTHETICAL = re(`${B0}(would|could|if)${B1}`, "i")
const COST_OF = re(`${B0}costs? of${B1}[^.$]{0,40}$`, "i")
const INCREASE_IN = re(`^${S}*(?:increase|decrease|rise|decline|reduction)s? in (?:the |our )?`, "i")

export type Claim = { id: number; hash: string; analyst: string; value: string; quote: string; summary?: string; metric?: string }

function change(c: Claim): [number, string] {
  if (HYPOTHETICAL.test(c.quote)) return [0, "a hypothetical, not a result"]
  for (const [text, where] of [
    [c.summary || "", "the summary"],
    [c.quote, "the filing's sentence"],
  ] as const) {
    const d = text ? directionNear(text, c.value) : null
    if (d) return [d === "up" ? 1 : -1, `${where} says it went ${d}`]
  }
  const v = amount(c.value)
  const m = c.quote.match(PRIOR)
  if (v !== null && m) {
    const prior = amount(m[1])
    const before = amounts(c.quote.slice(0, m.index!))
    if (prior && before.length && Math.abs(before[before.length - 1] - v) < 1e-6 * Math.max(1, v) && prior !== v)
      return [v > prior ? 1 : -1, `${c.value} against ${m[1]} in the prior period`]
  }
  return [0, "no change stated"]
}

function polarity(c: Claim): [number, string] {
  const q = c.quote
  const v = c.value
  let at = v ? q.indexOf(pysplit(v)[0] ?? "") : -1
  if (at < 0) at = q.length
  const kind = (m: RegExpMatchArray, pol: number): [number, string] =>
    pol === 1 && COST_OF.test(q.slice(0, m.index!)) ? [-1, "cost of " + m[1].toLowerCase()] : [pol, m[1].toLowerCase()]
  const after = v ? q.slice(at + v.length).match(INCREASE_IN) : null
  if (after) {
    const rest = q.slice(at + v.length + after[0].length)
    let first: [number, number, RegExpMatchArray] | null = null
    for (const [pattern, pol] of [
      [GOOD, 1],
      [BAD, -1],
    ] as const)
      for (const m of rest.matchAll(pattern)) if (!first || m.index! < first[0]) first = [m.index!, pol, m]
    if (first) return [first[1], first[2][1].toLowerCase()]
  }
  let best: [number, number, string] | null = null
  const head = q.slice(0, at)
  for (const [pattern, pol] of [
    [GOOD, 1],
    [BAD, -1],
  ] as const)
    for (const m of head.matchAll(pattern)) {
      const d = at - (m.index! + m[0].length)
      if (best === null || d < best[0]) best = [d, ...kind(m, pol)]
    }
  if (best === null) {
    const metric = c.metric || ""
    const good = metric.match(new RegExp(GOOD.source, "iu"))
    const bad = metric.match(new RegExp(BAD.source, "iu"))
    if (good && !bad) return [1, good[1].toLowerCase()]
    if (bad && !good) return [-1, bad[1].toLowerCase()]
    return [0, "neither revenue-like nor cost-like"]
  }
  return [best[1], best[2]]
}

export function signal(c: Claim): { signal: number; why: string } {
  const [ch, whyCh] = change(c)
  const [pol, whyPol] = polarity(c)
  const s = ch * pol
  let why: string
  if (s) why = `${whyPol} ${ch > 0 ? "up" : "down"} (${whyCh}): ${s > 0 ? "bullish" : "bearish"}`
  else if (pol === 0) why = `no signal: ${whyPol}`
  else why = `no signal: ${whyPol}, ${whyCh}`
  return { signal: s === 0 ? 0 : s, why }
}

export function thesis(ticker: string, claims: Claim[], perClaim: number) {
  const evidence = [...claims]
    .sort((a, b) => a.id - b.id)
    .map((c) => ({ claim: c.id, hash: c.hash, analyst: c.analyst, value: c.value, ...signal(c) }))
  const net = evidence.reduce((a, e) => a + e.signal, 0)
  const carrying = evidence.filter((e) => e.signal).length
  const side = net > 0 ? "long" : net < 0 ? "short" : null
  return { ticker, side, net, per_claim: perClaim, notional: side ? perClaim * carrying : 0, evidence }
}

/** json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False) for the
 * values a reasoning record holds (strings, integers, booleans, null, lists, dicts). */
export function canonical(x: unknown): string {
  if (x === null || typeof x !== "object") return JSON.stringify(x)
  if (Array.isArray(x)) return "[" + x.map(canonical).join(",") + "]"
  const o = x as Record<string, unknown>
  return "{" + Object.keys(o).sort().map((k) => JSON.stringify(k) + ":" + canonical(o[k])).join(",") + "}"
}
