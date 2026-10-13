// The browser build of the trading policy: web/vouch-policy.js (scripts/build_web.sh).
// The journal page re-runs the agent's reasoning with exactly the code below.
import { canonical, POLICY, RULE, signal, thesis } from "./check/policy"
;(globalThis as any).VouchPolicy = { canonical, POLICY, RULE, signal, thesis }
