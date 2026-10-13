// difflib.SequenceMatcher(None, a, b).ratio(), ported from CPython.
//
// The fuzzy half of the quote check scores a near-match with Python's
// SequenceMatcher, including its "autojunk" heuristic (when b has 200 or more
// characters, characters that make up more than 1% of it are not used to seed
// matches). The ratio has to be the same number in both languages, so this
// follows CPython's find_longest_match and get_matching_blocks line by line.

export function ratio(a: string, b: string): number {
  const la = a.length
  const lb = b.length
  if (la + lb === 0) return 1.0
  // chain_b
  const b2j = new Map<string, number[]>()
  for (let i = 0; i < lb; i++) {
    const ch = b[i]
    let idx = b2j.get(ch)
    if (!idx) b2j.set(ch, (idx = []))
    idx.push(i)
  }
  if (lb >= 200) {
    const ntest = Math.floor(lb / 100) + 1
    const popular: string[] = []
    for (const [ch, idx] of b2j) if (idx.length > ntest) popular.push(ch)
    for (const ch of popular) b2j.delete(ch)
  }
  const NOTHING: number[] = []

  const longest = (alo: number, ahi: number, blo: number, bhi: number): [number, number, number] => {
    let besti = alo
    let bestj = blo
    let bestsize = 0
    let j2len = new Map<number, number>()
    for (let i = alo; i < ahi; i++) {
      const next = new Map<number, number>()
      for (const j of b2j.get(a[i]) ?? NOTHING) {
        if (j < blo) continue
        if (j >= bhi) break
        const k = (j2len.get(j - 1) ?? 0) + 1
        next.set(j, k)
        if (k > bestsize) {
          besti = i - k + 1
          bestj = j - k + 1
          bestsize = k
        }
      }
      j2len = next
    }
    // isjunk is None, so bjunk is empty: extend over anything equal, popular or not
    while (besti > alo && bestj > blo && a[besti - 1] === b[bestj - 1]) {
      besti--
      bestj--
      bestsize++
    }
    while (besti + bestsize < ahi && bestj + bestsize < bhi && a[besti + bestsize] === b[bestj + bestsize]) bestsize++
    return [besti, bestj, bestsize]
  }

  let matches = 0
  const queue: [number, number, number, number][] = [[0, la, 0, lb]]
  while (queue.length) {
    const [alo, ahi, blo, bhi] = queue.pop()!
    const [i, j, k] = longest(alo, ahi, blo, bhi)
    if (k) {
      matches += k
      if (alo < i && blo < j) queue.push([alo, i, blo, j])
      if (i + k < ahi && j + k < bhi) queue.push([i + k, ahi, j + k, bhi])
    }
  }
  return (2.0 * matches) / (la + lb)
}
