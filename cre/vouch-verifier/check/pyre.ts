// Python's regex character classes, for a faithful port.
//
// The check was written in Python, where \s, \w and \b are Unicode-aware and
// str.split() / str.strip() use Python's own whitespace set. JavaScript's
// differ at the edges (\w and \b are ASCII; \s includes U+FEFF but not
// U+001C..U+001F or U+0085). A verdict must not depend on which language ran
// it, so the port spells Python's classes out.

// str.isspace() / re's \s for str patterns
export const WS = "\\t\\n\\x0b\\x0c\\r\\x1c-\\x1f \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000"
// re's \w for str patterns (letters, digits, underscore, any script)
export const W = "\\p{L}\\p{N}_"
// \b before a word character / after one
export const B0 = `(?<![${W}])`
export const B1 = `(?![${W}])`

const WS_RUN = new RegExp(`[${WS}]+`, "gu")
const WS_EDGE = new RegExp(`^[${WS}]+|[${WS}]+$`, "gu")

/** Python's str.split() with no arguments. */
export const pysplit = (s: string): string[] => s.split(WS_RUN).filter((x) => x.length > 0)

/** Python's str.strip() with no arguments. */
export const pystrip = (s: string): string => s.replace(WS_EDGE, "")

/** Python's str.count(sub) for a non-empty sub: non-overlapping occurrences. */
export const pycount = (s: string, sub: string): number => (sub ? s.split(sub).length - 1 : s.length + 1)

/** Python's a // b for integers. */
export const floordiv = (a: number, b: number): number => Math.floor(a / b)

/** Python's round(x, n): the exact decimal value of the double, rounded half to
 * even. Only the displayed score uses it; no verdict depends on it. */
export function round(x: number, n: number): number {
  if (!Number.isFinite(x) || x < 0) return Math.round(x * 10 ** n) / 10 ** n
  const exact = x.toFixed(100) // exact for the scores this is used on (0..1)
  const [int, frac] = exact.split(".")
  const keep = frac.slice(0, n)
  const rest = frac.slice(n)
  let digits = BigInt(int + keep)
  const half = "5" + "0".repeat(rest.length - 1)
  if (rest > half || (rest === half && digits % 2n === 1n)) digits += 1n
  return Number(digits) / 10 ** n
}
