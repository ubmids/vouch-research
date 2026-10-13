// The trading policy in TypeScript (what the web journal re-runs) reads every
// fixture claim exactly as agent/vouchrh/policy.py does: same signal, same words.
import { expect, test } from "bun:test"
import { readdirSync, readFileSync } from "node:fs"
import { join } from "node:path"
import { canonical, signal, thesis } from "./check/policy"

const FIXTURES = join(import.meta.dir, "fixtures")

test("the same signal and reason as the Python policy on every fixture claim", () => {
  let n = 0
  const wrong: string[] = []
  for (const name of readdirSync(FIXTURES).filter((f) => f.endsWith(".json"))) {
    for (const c of JSON.parse(readFileSync(join(FIXTURES, name), "utf8")).claims) {
      const got = signal({ id: 0, hash: "", analyst: "", ...c })
      if (JSON.stringify(got) !== JSON.stringify(c.signal)) wrong.push(`${c.quote.slice(0, 90)}\n want ${JSON.stringify(c.signal)}\n got  ${JSON.stringify(got)}`)
      n++
    }
  }
  expect(n).toBeGreaterThan(3000)
  expect(wrong.slice(0, 3)).toEqual([])
})

test("canonical JSON is Python's json.dumps(sort_keys, compact, ensure_ascii=False)", () => {
  expect(canonical({ b: [1, null, true], a: { z: "é’", y: "\n" } })).toBe('{"a":{"y":"\\n","z":"é’"},"b":[1,null,true]}')
  const t = thesis("X", [{ id: 2, hash: "0x2", analyst: "A", value: "$5 million", quote: "Revenue increased $5 million." }], 100)
  expect(t.side).toBe("long")
})

test("web/vouch-policy.js is built from this policy (run scripts/build_web.sh)", () => {
  const out = join(import.meta.dir, "..", "..", ".cache", "vouch-policy.check.js")
  const r = Bun.spawnSync(["bash", join(import.meta.dir, "..", "..", "scripts", "build_web.sh"), out])
  expect(r.exitCode).toBe(0)
  expect(readFileSync(out, "utf8")).toBe(readFileSync(join(import.meta.dir, "..", "..", "web", "vouch-policy.js"), "utf8"))
})
