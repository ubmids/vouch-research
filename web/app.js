// Vouch feed. Reads feed.json, written by `python -m vouchrh.publish`, and
// shows it. Nothing here decides a verdict: the page displays what the
// deterministic check found and what the chain did about it. The one thing it
// asks the server is the live check, POST /api/verify, the same check again.
"use strict";
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const short = (h, a = 6, b = 4) => h ? `${h.slice(0, a)}…${h.slice(-b)}` : "";
// Who an author is, said the same way everywhere: a scripted analyst, a language model, or (KOL mode) a market voice.
const KIND = { kol: "a market voice (a written fixture post, not a real account)" };
// A model claim re-posted from an earlier round, word for word (its words hash to the same claim hash).
const replayed = (c) => c.replayed_from ? `replayed: the model wrote these words in ${c.replayed_from.round} (claim #${c.replayed_from.claim} there); posted again here word for word` : "";
const money = (n) => Number(n).toLocaleString("en-US", { maximumFractionDigits: 2 });
const NAMES = { TSLA: "Tesla", AMZN: "Amazon", PLTR: "Palantir", NFLX: "Netflix", AMD: "AMD" };
let F, filter = "all", ticker = null, analyst = "", query = "", selected = null;

// ?feed=feed-local.json shows another published round (same page, another file).
const FEED = (new URLSearchParams(location.search).get("feed") || "").match(/^[\w.-]+\.json$/) ? new URLSearchParams(location.search).get("feed") : "feed.json";
fetch(FEED, { cache: "no-store" }).then((r) => r.json()).then((d) => { F = d; boot(); })
  .catch(() => { $("#inspect").innerHTML = `<p class="sub">The feed could not be loaded.</p>`; });

// ---- plain words for every verdict -----------------------------------------
// The check's reasons are exact; these are what a reader needs at a glance.
function plain(c) {
  const r = c.reason || "", src = c.source;
  if (c.verdict === "cleared") return { short: "matches the filing", title: `In the filing, as claimed. <em class="c">Cleared.</em>`,
    why: "The quote is a whole sentence of the company's 10-Q, the figure is in it, and nothing in the summary contradicts it." };
  const rules = [
    ["wrong period", "wrong period", "Right number, wrong period.", "The quote is real and the figure is in it, but the filing gives that figure for a different period than the claim states."],
    ["wrong quarter", "wrong quarter", "Right number, wrong quarter.", "The quote is real, but the period it covers ends in a different quarter from the one the claim names."],
    ["wrong date", "wrong date", "Right number, wrong date.", "The sentence gives two balances at two dates. The claim paired this figure with the wrong one."],
    ["the summary states", "summary adds a number", "The summary adds a number.", "Every figure a reader sees must be in the cited sentence, or be simple arithmetic on it. This one is not."],
    ["the summary reverses", "summary says the opposite", "The summary says the opposite.", "The summary reverses its own quote: up for down, or gain for loss."],
    ["the quote is a fragment", "quote is a fragment", "A fragment, not a sentence.", "A quote must be a whole sentence of the filing. A fragment can drop the words that change its meaning."],
    ["claimed value not grounded", "claims another number", "Real quote, wrong number.", "The sentence is genuinely in the filing, but it does not say the figure the claim asserts."],
  ];
  for (const [k, s, t, w] of rules) if (r.startsWith(k)) return { short: s, title: `${t} <em>Slashed.</em>`, why: w, rule: r };
  if (c.check.method === "figures-differ") return { short: "a figure was changed", title: `One figure off the filing. <em>Slashed.</em>`,
    why: `The quote is ${(c.check.score * 100).toFixed(1)}% identical to the filing, close enough to pass any fuzzy match. But a figure in it is not the filing's, and figures must match exactly.` };
  if (src) return { short: "quote was altered", title: `The quote was altered. <em>Slashed.</em>`, why: "No sentence in the filing matches the quote closely enough." };
  return { short: "not in the filing", title: `Not in the filing at all. <em>Slashed.</em>`,
    why: `The closest passage in the whole 10-Q is only ${(c.similarity * 100).toFixed(0)}% similar. The sentence was invented.` };
}

// ---- boot -------------------------------------------------------------------
function boot() {
  const cs = F.claims, cleared = cs.filter((c) => c.verdict === "cleared").length;
  const lost = cs.filter((c) => c.verdict === "slashed").reduce((a, c) => a + c.stake, 0);
  const J = F.journal || [], trades = J.filter((j) => j.status === "opened").length;
  const refusals = J.reduce((a, j) => a + j.attempts.length, 0);
  $("#net").textContent = F.chain.name;
  $("#net").title = `chain id ${F.chain_id}`;
  $("#footChain").textContent = F.chain.name;
  $("#footSettle").textContent = F.settled_by || "one verifier key (this round predates the Chainlink CRE workflow)";
  if (F.fixture) $("#footChain").textContent = `${F.chain.name}. ${F.fixture}`;
  const k = (cls, label, val, tip) => `<span class="${cls}" title="${esc(tip)}">${label}<b>${val}</b></span>`;
  $("#kpis").innerHTML =
    k("", "claims", cs.length, "Claims posted in this round, each with USDG at stake") +
    k("c", "true", cleared, "Checked against the SEC filing and found true: cleared") +
    k("s", "wrong", cs.length - cleared, "Wrong in a way the check can prove: the analyst lost its stake (slashed)") +
    k("opt", "lost by wrong claims", `${money(lost)} USDG`, F.settled_by ? "Stake taken from wrong claims, to the pool that backs readers" : "Stake taken from wrong claims: half to whoever caught them, half to the reader pool") +
    (J.length ? k("opt", "agent", `${trades} trades · ${refusals} refused`, "A trading agent read every claim. The desk refused every trade that cited a wrong one; each trade it made is in the journal below") : "");
  // On a phone, three numbers under the bar rather than six in it.
  $("#mkpis").innerHTML = `<span>claims<b>${cs.length}</b></span><span class="c">true<b>${cleared}</b></span><span class="s">wrong<b>${cs.length - cleared}</b></span>`;
  $("#mkpis").hidden = !matchMedia("(max-width: 720px)").matches;
  const tape = cs.slice().reverse().map((c) =>
    `<span><b>${esc(c.ticker)}</b>${esc(c.value)} <span class="${c.verdict[0]}">${c.verdict === "cleared" ? "TRUE" : "WRONG · " + plain(c).short}</span></span>`).join("");
  $("#tape").innerHTML = tape + tape;
  const names = [...new Set(cs.map((c) => c.analyst))];
  $("#who").innerHTML = `<option value="">Every analyst</option>` +
    names.map((n) => `<option value="${esc(n)}">${esc(n)}${cs.find((c) => c.analyst === n).analyst_kind === "model" ? " (AI)" : ""}</option>`).join("");
  watch(); board(); rows(); journal();
  const addr = F.contracts, ex = F.chain.explorer;
  const link = (a, label) => ex ? `<a href="${ex}/address/${a}" target="_blank" rel="noopener">${label} ${esc(a)} ↗</a>` : `<span>${label} ${esc(a)}</span>`;
  $("#addr").innerHTML = link(addr.market, "BondedClaims") + (addr.desk ? link(addr.desk, "AgentDesk") : "") + link(addr.usdg, "Bond token");
  $("#gen").textContent = `round of ${new Date(F.generated * 1000).toUTCString().slice(5, 22)} UTC`;

  // Open on the most instructive claim: the AI's own mistake if it made one,
  // else a near-perfect quote with one figure changed.
  const refusedOnChain = (c) => c.verdict === "slashed" && c.desk && !c.desk.acted;
  const lead = cs.find((c) => c.analyst_kind === "model" && refusedOnChain(c)) || cs.find((c) => c.analyst_kind === "model" && c.verdict === "slashed")
    || cs.find((c) => c.check.method === "figures-differ" && refusedOnChain(c))
    || cs.find((c) => c.check.method === "figures-differ") || cs.find((c) => c.verdict === "slashed") || cs[0];
  select(lead.id);

  $("#tabs").onclick = (e) => {
    const b = e.target.closest("button"); if (!b) return;
    filter = b.dataset.f;
    document.querySelectorAll("#tabs button").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
    rows();
  };
  $("#who").onchange = (e) => { analyst = e.target.value; rows(); };
  $("#q").oninput = (e) => { query = e.target.value.trim().toLowerCase(); rows(); };
  $("#openCheck").onclick = $("#devCheck").onclick = openCheck;
  checkPanel();
  story(lead);
  const qs = new URLSearchParams(location.search);
  if (qs.has("journal")) openEntry(lead.ticker);
  // ?claim (the lead) or ?claim=<id>: open on one claim, no tour (for links and the video)
  if (qs.has("claim")) { const id = Number(qs.get("claim")); select(qs.get("claim") && cs.some((c) => c.id === id) ? id : lead.id, true); }
}

function watch() {
  const by = {};
  F.claims.forEach((c) => { (by[c.ticker] ||= []).push(c); });
  $("#watch").innerHTML = Object.keys(by).map((t) => {
    const cs = by[t], c = cs.filter((x) => x.verdict === "cleared").length, s = cs.length - c, f = F.filings[t] || {};
    return `<button class="tok" data-t="${t}" aria-pressed="false" title="Show only ${esc(NAMES[t] || t)} claims">
      <div class="t"><b>${t}</b><span>${esc(NAMES[t] || "")}</span></div>
      <div class="f">${esc(f.form || "")} · filed ${esc(f.filed || "")}</div>
      <div class="mix"><i class="c" style="flex:${c}"></i><i class="s" style="flex:${s}"></i></div>
      <div class="nums"><span class="c">${c} true</span><span class="s">${s} wrong</span></div></button>`;
  }).join("");
  $("#watch").onclick = (e) => {
    const b = e.target.closest(".tok"); if (!b) return;
    ticker = ticker === b.dataset.t ? null : b.dataset.t;
    document.querySelectorAll(".tok").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.t === ticker)));
    rows();
  };
}

function rows() {
  const list = F.claims.filter((c) => (filter === "all" || c.verdict === filter) && (!ticker || c.ticker === ticker)
    && (!analyst || c.analyst === analyst)
    && (!query || [c.ticker, NAMES[c.ticker], c.analyst, c.value, c.summary, c.quote].join(" ").toLowerCase().includes(query)));
  $("#rows").innerHTML = list.map((c) => {
    const p = plain(c);
    return `<tr data-id="${c.id}" class="${c.verdict}" aria-selected="${c.id === selected}" tabindex="0">
      <td class="tk">${esc(c.ticker)}<span>${esc(NAMES[c.ticker] || "")}</span></td>
      <td class="an">${esc(c.analyst)}${c.analyst_kind === "model" ? ` <span class="ai" title="${esc(replayed(c) || "A language model, running locally")}">AI${c.replayed_from ? " · replayed" : ""}</span>` : c.analyst_kind === "kol" ? ` <span class="ai" title="${esc(KIND.kol)}">KOL · fixture</span>` : ""}</td>
      <td class="claim"><span class="v">${esc(c.value)}</span><span class="q">${esc(headline(c))}</span></td>
      <td class="vd"><span class="pill ${c.verdict[0]}">${c.verdict === "cleared" ? "TRUE" : "WRONG"}</span><span class="why">${esc(p.short)}</span></td></tr>`;
  }).join("") || `<tr class="none"><td colspan="4">No claims match. <button id="reset">Clear the filters</button></td></tr>`;
  const bits = [];
  if (ticker) bits.push(esc(NAMES[ticker] || ticker));
  if (analyst) bits.push(esc(analyst));
  if (query) bits.push(`"${esc(query)}"`);
  $("#filterNote").innerHTML = `${list.length} of ${F.claims.length}` + (bits.length ? ` · ${bits.join(" · ")} · <button id="clearAll">clear</button>` : "");
  const reset = () => { ticker = null; analyst = ""; query = ""; filter = "all"; $("#q").value = ""; $("#who").value = "";
    document.querySelectorAll(".tok").forEach((x) => x.setAttribute("aria-pressed", "false"));
    document.querySelectorAll("#tabs button").forEach((x) => x.setAttribute("aria-selected", String(x.dataset.f === "all"))); rows(); };
  ["#clearAll", "#reset"].forEach((id) => { const b = $(id); if (b) b.onclick = reset; });
  $("#rows").onclick = (e) => { const r = e.target.closest("tr[data-id]"); if (r) select(+r.dataset.id, true); };
  $("#rows").onkeydown = (e) => { const r = e.target.closest("tr[data-id]"); if (r && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); select(+r.dataset.id, true); } };
}

function headline(c) {
  if (c.summary) return c.summary;
  const q = c.quote.replace(/\s+/g, " ");
  return q.length > 104 ? q.slice(0, 102) + "…" : q;
}

// Word-level diff of the analyst's quote against the filing's sentence, so
// the one changed figure is what lights up.
function diff(a, b) {
  const A = a.split(/(\s+)/), B = b.split(/(\s+)/), n = A.length, m = B.length;
  const L = Array.from({ length: n + 1 }, () => new Int32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
    L[i][j] = A[i] === B[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const out = []; let i = 0, j = 0;
  while (i < n && j < m) {
    if (A[i] === B[j]) { out.push(["=", A[i]]); i++; j++; }
    else if (L[i + 1][j] >= L[i][j + 1]) out.push(["-", A[i++]]); else out.push(["+", B[j++]]);
  }
  while (i < n) out.push(["-", A[i++]]); while (j < m) out.push(["+", B[j++]]);
  return out;
}

// Where a slashed stake went. Rounds settled through the forwarder (v2) have no
// challenger, so all of it backs readers; v1 rounds paid half to a challenger.
function split(c, sep = " · ") {
  return F.settled_by ? `all ${money(c.stake)} to the pool that backs readers`
    : `${money(c.stake / 2)} to whoever caught it${sep}${money(c.stake / 2)} to a pool that protects readers`;
}

// ---- the inspector: in the order a reader asks ------------------------------
function select(id, scroll) {
  selected = id;
  document.querySelectorAll("#rows tr").forEach((r) => r.setAttribute("aria-selected", String(+r.dataset.id === id)));
  const c = F.claims.find((x) => x.id === id), f = F.filings[c.ticker] || {}, bad = c.verdict === "slashed";
  const src = c.source, ex = F.chain.explorer, p = plain(c);
  const claimRule = !!p.rule;

  let quoted = esc(c.quote), filed = "";
  if (src) {
    const d = diff(src.match, c.quote);
    quoted = d.filter(([k]) => k !== "-").map(([k, w]) => k === "+" && w.trim() ? `<del>${esc(w)}</del>` : esc(w)).join("");
    const fixed = d.filter(([k]) => k !== "+").map(([k, w]) => k === "-" && w.trim() ? `<ins>${esc(w)}</ins>` : esc(w)).join("");
    const val = c.check.verified && bad && !claimRule ? fixed.replace(esc(c.value), `<span class="bad">${esc(c.value)}</span>`) : fixed;
    filed = `<span class="ctx">${esc(src.before)}</span><span class="hit">${val}</span><span class="ctx">${esc(src.after)}</span>`;
  }
  const figsOk = c.check.method !== "figures-differ" && (c.check.verified || !src);
  const simPct = Math.max(0, Math.min(1, c.check.score || c.similarity));
  const txLink = (h, label) => ex ? `<a href="${ex}/tx/${h}" target="_blank" rel="noopener">${label} ↗</a>` : `<span>${label} ${short(h, 10, 6)} · local devnet</span>`;
  const je = (F.journal || []).find((j) => j.ticker === c.ticker);
  const SIG = { 1: "bullish", "-1": "bearish", 0: "no signal" };
  const toEntry = je ? ` <button class="linkish" data-entry="${esc(c.ticker)}">See the journal entry →</button>` : "";
  const agent = c.desk && c.desk.acted
    ? `<p><span class="good">It backs a trade.</span> The agent's ${esc(c.desk.side.toUpperCase())} ${esc(c.ticker)} paper position cites this claim (journal entry #${c.desk.entry}); it read it as ${SIG[c.desk.signal]}.${toEntry}</p>`
    : c.desk
    ? `<p><span class="bad">It was refused.</span> The trading agent cited this claim. The desk asked Vouch first, and a claim that failed the check cannot back a trade, so the transaction reverted on-chain.${toEntry}</p>`
    : je ? `<p>The trading agent read it${je.status === "opened" ? ", but the trade did not need it" : `. What it was left with on ${esc(NAMES[c.ticker] || c.ticker)} pointed nowhere, so it did not trade`}.${toEntry}</p>`
    : "";

  $("#inspect").innerHTML = `
    <div class="sheetClose"><button id="closeSheet">← All claims</button><span>claim #${c.id}</span></div>
    <div class="h"><span>${esc(NAMES[c.ticker] || c.ticker)} · ${esc(f.form || "10-Q")} filed ${esc(f.filed || "")}</span><span>claim #${c.id}</span></div>
    <h2>${p.title}</h2>
    <p class="sub">${p.why}${p.rule ? `<span class="rule">${esc(p.rule)}</span>` : ""}</p>

    <div class="box"><div class="k"><span>What ${esc(c.analyst)}${c.analyst_kind === "model" ? " (AI)" : ""} claimed</span><span>${money(c.stake)} USDG at stake</span></div>
      <div class="v said">${c.summary ? esc(c.summary) : `The figure is <b>${esc(c.value)}</b>.`}</div>${c.replayed_from ? `<div class="hash">${esc(replayed(c))} · claim hash ${esc(short(c.replayed_from.hash, 10, 6))}</div>` : ""}</div>
    ${c.post ? `<div class="box"><div class="k"><span>The post it came from (${esc(c.post.handle)})</span><span>written fixture, not a real account</span></div>
      <div class="v">${esc(c.post.text)}</div>
      <div class="hash">the agent's reading: ${esc(c.reading.ticker)} · ${esc(c.reading.value || "no figure")} · ${esc(c.reading.sentiment)} · ${esc(c.reading.conviction)} conviction · ${esc(c.reading.urgency)}. What it checked is the story above, with each figure written as the filing writes it.</div></div>` : ""}

    <div class="box"><div class="k"><span>The sentence it quoted</span><span>${src && c.quote !== src.match ? "differences marked" : "as quoted"}</span></div><div class="v">${quoted}</div></div>

    <div class="box"><div class="k"><span>What the SEC filing says</span><a href="${esc(c.filing_url)}" target="_blank" rel="noopener">open the filing ↗</a></div>
      <div class="v">${src ? filed : `<span class="none">Nothing in the filing resembles this sentence.</span>`}</div></div>

    <div class="flow">${bad
      ? `<div class="n">${esc(c.analyst)} lost<b class="s">−${money(c.stake)} USDG</b></div><div class="ar">→</div><div class="n">${split(c)}<b class="c">+${money(c.stake)}</b></div>`
      : `<div class="n">${esc(c.analyst)} staked<b>${money(c.stake)} USDG</b></div><div class="ar">→</div><div class="n">returned to the analyst<b class="c">+${money(c.stake)}</b></div>`}</div>

    <div class="by">${c.workflow_id && !/^0x0+$/.test(c.workflow_id) ? `<b>Checked by Chainlink CRE</b> · workflow ${esc(short(c.workflow_id, 8, 4))}`
      : `<b>Checked by</b> ${esc(F.settled_by || "the verifier key (before Chainlink CRE)")}`} · against the filing SEC EDGAR serves${txLink(c.tx_judge, " · the verdict")}</div>

    ${agent ? `<div class="box desk"><div class="k"><span>What a trading agent did</span><span>AgentDesk</span></div><div class="v">${agent}</div></div>` : ""}

    <details class="tech"><summary>Technical details · the check, the transactions, the hash</summary>
      <div class="meter">
        <div class="row"><span>similarity</span><div class="track2"><i style="width:${(simPct * 100).toFixed(1)}%"></i><span class="floor" style="left:95%"></span></div><b>${(simPct * 100).toFixed(1)}%</b></div>
        <div class="row"><span>figures</span><span class="${figsOk ? "ok" : "no"}">${figsOk ? (src ? "all match the filing" : "not in the filing") : "differ from the filing"}</span><b class="${figsOk && src ? "ok" : "no"}">${figsOk && src ? "✓" : "✕"}</b></div>
        <div class="row"><span>claim as written</span><span class="${claimRule ? "no" : "ok"}">${claimRule ? esc(p.short) : "period, date, direction hold"}</span><b class="${claimRule ? "no" : bad ? "" : "ok"}">${claimRule ? "✕" : bad ? "·" : "✓"}</b></div>
      </div>
      <div class="tx">${txLink(c.tx_post, "posted")}${txLink(c.tx_judge, bad ? "slashed" : "cleared")}${c.desk ? txLink(c.desk.tx, c.desk.acted ? "agent's trade" : "agent's refused trade") : ""}</div>
      <div class="hash">verdict by ${c.workflow_id && !/^0x0+$/.test(c.workflow_id) ? `Chainlink CRE workflow ${esc(short(c.workflow_id, 10, 6))}` : esc(F.settled_by || "the verifier key")}${c.evidence && !/^0x0+$/.test(c.evidence) ? ` · against filing bytes keccak256 ${esc(short(c.evidence, 10, 6))}` : ""}</div>
      <div class="hash">accession ${esc(c.accession)} · on-chain hash ${esc(c.hash)}</div>
      <div class="verify"><button id="rehash">Verify it yourself</button><span id="rehashOut">Recompute the hash from the words shown, in your browser.</span></div>
    </details>`;
  $("#rehash").onclick = () => {
    const got = rehash(c), ok = got === c.hash;
    $("#rehashOut").innerHTML = ok
      ? `<span class="ok">✓ ${short(got, 10, 6)} matches the chain.</span> These are exactly the words that were staked.`
      : `<span class="no">✕ ${short(got, 10, 6)} does not match.</span> The words shown are not the ones staked.`;
  };
  $("#closeSheet").onclick = closeSheet;
  const go = $("#inspect [data-entry]"); if (go) go.onclick = () => openEntry(go.dataset.entry);
  // On a phone the claim opens as a sheet over the list; on a tablet it sits below it.
  if (scroll && matchMedia("(max-width: 720px)").matches) { document.body.classList.add("sheet"); $("#inspect").scrollTop = 0; history.pushState({ sheet: 1 }, ""); }
  else if (scroll && innerWidth < 1100) $("#inspect").scrollIntoView({ behavior: "smooth", block: "start" });
}

function closeSheet() {
  if (!document.body.classList.contains("sheet")) return;
  document.body.classList.remove("sheet");
  if (history.state && history.state.sheet) history.back();
}
// The phone's back gesture closes the sheet rather than leaving the page.
addEventListener("popstate", () => document.body.classList.remove("sheet"));
addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });

// The claim's canonical form, byte for byte what claims.py hashes: its seven
// fields, keys sorted, no whitespace, UTF-8. keccak256 of it is what post()
// stored. If the page showed different words, this would not match.
function rehash(c) {
  const fields = { accession: c.accession, analyst: c.analyst, metric: c.metric, quote: c.quote,
                   summary: c.summary || "", ticker: c.ticker, value: c.value };
  return "0x" + keccak256(JSON.stringify(fields));
}

function board() {
  const st = F.standings, top = Math.max(...st.map((s) => s.bonded));
  const honest = st.filter((s) => s.slashed === 0), liars = st.filter((s) => s.cleared === 0);
  const ai = st.find((s) => s.kind === "model");
  $("#boardLine").innerHTML = `Everyone started with ${money(top)} USDG. ` +
    (honest.length ? `<span class="c">${esc(honest.map((s) => s.analyst).join(", "))} told the truth every time and kept all of it.</span> ` : "") +
    (liars.length ? `<span class="s">The ${liars.length} that bent the numbers lost half.</span> ` : "") +
    (ai ? `The AI got ${ai.slashed} of ${ai.cleared + ai.slashed} wrong and paid for each.` : "");
  const max = Math.max(...F.standings.map((s) => s.bonded), 1);
  $("#board").innerHTML = F.standings.slice().sort((a, b) => b.bonded - a.bonded).map((s) => {
    const lost = s.slashed > 0;
    return `<button class="ana" data-a="${esc(s.analyst)}" title="Show ${esc(s.analyst)}'s claims">
      <div class="nm">${esc(s.analyst)}${s.kind === "model" ? ' <i class="ai">AI</i>' : ""}<span>${s.kind === "model" ? (F.claims.some((c) => c.analyst === s.analyst && c.replayed_from) ? "an open model; its claims replayed from an earlier round" : "an open model, running locally") : KIND[s.kind] || "a scripted analyst"}</span></div>
      <div class="bb"><i style="width:${(s.bonded / max * 100).toFixed(1)}%;background:${lost ? "var(--flare)" : "var(--volt)"}"></i></div>
      <div class="val">${money(s.bonded)}<span>${s.cleared} true · ${s.slashed} wrong</span></div></button>`;
  }).join("");
  $("#board").onclick = (e) => {
    const b = e.target.closest(".ana"); if (!b) return;
    analyst = b.dataset.a; $("#who").value = analyst; rows();
    $(".book").scrollIntoView({ behavior: "smooth", block: "start" });
  };
}

// ---- check a claim yourself ---------------------------------------------------
const EXAMPLES = {
  true: { ticker: "TSLA", value: "$1.37 billion", summary: "Tesla's depreciation was $1.37 billion in Q2 2026.",
    quote: "Depreciation expense during the three and six months ended June 30, 2026 was $1.37 billion and $2.71 billion, respectively." },
  quarter: { ticker: "TSLA", value: "$1.37 billion", summary: "Depreciation for Q3 2026 was $1.37 billion.",
    quote: "Depreciation expense during the three and six months ended June 30, 2026 was $1.37 billion and $2.71 billion, respectively." },
  doctored: { ticker: "TSLA", value: "$1.47 billion", summary: "Tesla's depreciation was $1.47 billion in Q2 2026.",
    quote: "Depreciation expense during the three and six months ended June 30, 2026 was $1.47 billion and $2.71 billion, respectively." },
};

function openCheck() {
  const d = $("#check");
  if (typeof d.showModal === "function") d.showModal(); else d.setAttribute("open", "");
  $("#checkForm").elements.value.focus();
}

function checkPanel() {
  const form = $("#checkForm"), d = $("#check");
  $("#closeCheck").onclick = () => d.close();
  d.addEventListener("click", (e) => { if (e.target === d) d.close(); });
  document.querySelectorAll(".examples button").forEach((b) => b.onclick = () => {
    const ex = EXAMPLES[b.dataset.ex];
    for (const k of Object.keys(ex)) form.elements[k].value = ex[k];
    $("#result").hidden = true;
  });
  form.onsubmit = async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(form).entries());
    $("#runCheck").disabled = true; $("#checkState").textContent = "Reading the filing…"; $("#result").hidden = true;
    try {
      const r = await fetch("api/verify", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
      const out = await r.json();
      if (!r.ok) throw new Error(out.error || `the check said ${r.status}`);
      const ok = out.verdict === "cleared";
      const p = plain({ verdict: out.verdict, reason: out.reason, check: { method: out.match, score: out.similarity },
                        similarity: out.similarity, source: out.match !== "none" });
      $("#result").className = "result " + (ok ? "ok" : "no");
      $("#result").innerHTML = `<b>${ok ? "True: this claim would be cleared." : "Wrong: this claim would be slashed."}</b>
        <span>${esc(p.why)}</span>
        ${!ok ? `<code>${esc(out.reason)}</code>` : ""}
        <a href="${esc(out.filing.url)}" target="_blank" rel="noopener">checked against ${esc(out.filing.ticker)} ${esc(out.filing.form)} filed ${esc(out.filing.filed)} ↗</a>`;
      $("#result").hidden = false;
      $("#checkState").textContent = "";
    } catch (err) {
      $("#checkState").textContent = location.protocol === "file:" || location.hostname === "127.0.0.1"
        ? "The live check runs on vouch-feed.vercel.app." : `Could not check it: ${err.message}`;
    } finally { $("#runCheck").disabled = false; }
  };
}


// ---- the agent's journal ------------------------------------------------------
// Every paper trade, the claims it cites, the verdict on each and the rules that
// turned them into a trade. Re-verify recomputes all of it in the browser with
// the agent's own policy (vouch-policy.js) and, on a public chain, reads the
// transactions back from the chain's RPC.
const SIDE = { long: "LONG", short: "SHORT" };
const byId = () => Object.fromEntries(F.claims.map((c) => [c.id, c]));

function journal() {
  const J = F.journal || [], el = $("#entries");
  if (!J.length) {
    el.innerHTML = `<p class="jnote">This round was published before the agent kept a journal. <a href="?feed=feed-local.json&journal">See a round with one</a> (run on a local devnet).</p>`;
    return;
  }
  const order = J.slice().sort((a, b) => (b.status === "opened") - (a.status === "opened"));
  el.innerHTML = order.map(entryHtml).join("");
  el.onclick = (e) => {
    const c = e.target.closest("[data-claim]");
    if (c) { select(+c.dataset.claim, true); if (innerWidth >= 1100) $(".main").scrollIntoView({ behavior: "smooth", block: "start" }); return; }
    const v = e.target.closest("[data-verify]");
    if (v) reverify(v.dataset.verify, v);
    const d = e.target.closest("[data-record]");
    if (d) download(`vouch-audit-${d.dataset.record}-${F.chain_id}.md`, auditRecord(F.journal.find((x) => x.ticker === d.dataset.record)));
  };
}

function openEntry(ticker) {
  const d = document.getElementById(`je-${ticker}`);
  if (!d) return;
  d.open = true;
  d.scrollIntoView({ behavior: "smooth", block: "start" });
}

function entryHtml(j) {
  const ex = F.chain.explorer, r = j.reasoning || {}, by = byId(), company = NAMES[j.ticker] || j.ticker;
  const tx = (h, label) => !h ? "" : ex ? `<a class="txl" href="${ex}/tx/${h}" target="_blank" rel="noopener">${label} ↗</a>`
    : `<span class="txl" title="${esc(h)}">${label} ${short(h, 8, 4)}</span>`;
  const opened = j.status === "opened";
  const analysts = new Set(j.read.map((id) => by[id] && by[id].analyst)).size;
  const price = r.price ? `entry ${esc(r.price.price)} USD` : "no price recorded";
  const pnl = j.pnl != null ? `<span class="pnl ${j.pnl >= 0 ? "c" : "s"}">${j.pnl >= 0 ? "+" : "−"}${money(Math.abs(j.pnl))} USD</span> paper, marked at ${esc(j.mark.price)} (${price})` : price;
  const refused = j.attempts.map((a) => {
    const c = by[a.claim];
    return `<li><button class="cid" data-claim="${a.claim}">#${a.claim}</button><span class="who">${esc(c.analyst)}</span><span class="s">${esc(plain(c).short)}</span>${tx(a.tx, "refused on-chain")}</li>`;
  }).join("");
  const cited = (r.evidence || []).map((e) => {
    const c = by[e.claim], tone = e.signal > 0 ? "c" : e.signal < 0 ? "s" : "";
    return `<tr><td><button class="cid" data-claim="${e.claim}">#${e.claim}</button></td><td class="who">${esc(e.analyst)}</td>
      <td class="cl"><span class="v">${esc(e.value)}</span> ${esc(headline(c))}</td>
      <td class="vd"><span class="pill ${c.verdict[0]}">${c.verdict === "cleared" ? "CLEARED" : "SLASHED"}</span>${tx(e.verdict_tx || c.tx_judge, "verdict")}</td>
      <td class="sig ${tone}"><b>${e.signal > 0 ? "bullish" : e.signal < 0 ? "bearish" : "no signal"}</b><span>${esc(e.why.replace(/: (bullish|bearish)$/, ""))}</span></td></tr>`;
  }).join("");
  const decision = opened
    ? `Net signal <b>${r.net_signal > 0 ? "+" : ""}${r.net_signal}</b>, so <b class="${j.side === "long" ? "c" : "s"}">${SIDE[j.side]} ${money(j.notional / 1e6)} USD</b> (${money(r.per_claim / 1e6)} per claim that carries a signal).`
    : `Net signal <b>0</b>, so <b>no trade</b>. The agent does not guess.`;
  return `<details class="jentry ${opened ? j.side : "flat"}" id="je-${esc(j.ticker)}"${opened ? " open" : ""}>
    <summary><span class="side ${opened ? j.side : "none"}">${opened ? SIDE[j.side] : "NO TRADE"}</span><b class="tk">${esc(j.ticker)}</b><span class="co">${esc(company)}</span>
      <span class="what">${opened ? `${money(j.notional / 1e6)} USD paper · cites ${r.evidence.length} cleared claims · ${j.attempts.length} refusals` : `${j.attempts.length} refusals · nothing left that points anywhere`}</span>
      <span class="when">${opened ? `entry #${j.entry}` : ""}</span></summary>
    <ol class="trail">
      <li><div><b>Read.</b> ${j.read.length} claims about ${esc(company)} from ${analysts} analysts, each citing ${esc(company)}'s 10-Q.</div></li>
      ${j.attempts.length ? `<li><div><b>Refused.</b> It tried to trade citing everything it read. The desk asked Vouch about each claim and reverted the trade ${j.attempts.length} time${j.attempts.length > 1 ? "s" : ""}, each time naming a claim that failed the check:<ul class="refused">${refused}</ul></div></li>` : ""}
      <li><div><b>${opened ? "Kept what held." : "What was left."}</b> ${opened ? "The desk accepted every one of these: each cleared the check." : "Read by the agent's rules, these point nowhere, so it stopped before testing the rest against the desk."}<div class="scrollx"><table class="cited"><thead><tr><th>Claim</th><th>Analyst</th><th>What it says</th><th>Verdict</th><th>Read as</th></tr></thead><tbody>${cited || `<tr><td colspan="5" class="none">nothing left</td></tr>`}</tbody></table></div></div></li>
      <li><div><b>Decided.</b> ${decision} <span class="rule">${esc(r.rule || "")}</span></div></li>
      ${opened ? `<li><div><b>Committed.</b> All of the above, with the transaction of every verdict and refusal, hashes to <code>${esc(short(j.reasoning_hash, 12, 8))}</code>. The desk stored that hash with the trade ${tx(j.tx, "in this transaction")}, so the reasons cannot be rewritten afterwards. ${pnl}.</div></li>` : ""}
    </ol>
    <div class="verify jv"><button data-verify="${esc(j.ticker)}">Re-verify this ${opened ? "trade" : "decision"}</button><button data-record="${esc(j.ticker)}">Download the audit record</button><span>Recomputes every hash and verdict link, and re-runs the agent's rules, in your browser. The record is one file an examiner or counsel can keep.</span></div>
    <ul class="checks" id="rv-${esc(j.ticker)}"></ul>
  </details>`;
}

async function rpc(method, params) {
  const r = await fetch(F.chain.rpc, { method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) });
  const out = await r.json();
  if (out.error) throw new Error(out.error.message);
  return out.result;
}

async function reverify(ticker, button) {
  const j = F.journal.find((x) => x.ticker === ticker), r = j.reasoning, by = byId(), list = $(`#rv-${ticker}`);
  const rows = [], add = (ok, text) => { rows.push(`<li class="${ok ? "ok" : "no"}">${ok ? "✓" : "✕"} ${text}</li>`); list.innerHTML = rows.join(""); };
  button.disabled = true; list.innerHTML = "";
  const company = NAMES[ticker] || ticker;
  if (j.status === "opened") {
    const h = "0x" + keccak256(VouchPolicy.canonical(r));
    add(h === j.reasoning_hash, `The reasoning record hashes to <code>${esc(short(h, 10, 6))}</code>, the hash the trade carries.`);
  }
  for (const e of r.evidence) {
    const c = by[e.claim];
    add(rehash(c) === c.hash && c.hash === e.hash, `Claim #${e.claim}: its words hash to the hash staked on-chain.`);
    if (j.status === "opened")
      add(c.verdict === "cleared" && (!e.verdict_tx || e.verdict_tx === c.tx_judge), `Claim #${e.claim}: cleared by the check against ${esc(company)}'s 10-Q, in the verdict transaction cited.`);
  }
  for (const a of j.attempts) {
    const c = by[a.claim], unchecked = c.verdict === "cleared" && /^0x0*$/.test(c.evidence || "");
    add(c.verdict === "slashed" || unchecked, unchecked ? `Claim #${a.claim} was refused because no verdict ever checked it.`
      : `Claim #${a.claim} was refused because it failed the check: ${esc(c.reason)}.`);
  }
  const accounted = [...r.evidence.map((e) => e.claim), ...r.dropped.map((d) => d.claim)].sort((x, y) => x - y);
  add(JSON.stringify([...j.read].sort((x, y) => x - y)) === JSON.stringify(accounted), "Every claim the agent read is either cited or refused: none was quietly left out.");
  const again = VouchPolicy.thesis(ticker, r.evidence.map((e) => by[e.claim]), r.per_claim);
  const same = again.side === r.side && again.notional === r.notional && again.evidence.every((e, i) => e.signal === r.evidence[i].signal && e.why === r.evidence[i].why);
  add(same, `Re-running the agent's rules on these claims gives the same ${j.status === "opened" ? `trade: ${SIDE[again.side] || "no trade"} ${money(again.notional / 1e6)} USD` : "decision: no trade"}.`);
  if (!F.chain.rpc) {
    rows.push(`<li class="na">· On-chain: this round ran on a local devnet the browser cannot reach. <code>python -m vouchrh.journal verify</code> checks the chain and re-fetches the filing.</li>`);
    list.innerHTML = rows.join("");
  } else {
    try {
      if (j.status === "opened") {
        const rc = await rpc("eth_getTransactionReceipt", [j.tx]);
        const log = rc.logs.find((l) => l.address.toLowerCase() === F.contracts.desk.toLowerCase());
        const stored = log ? "0x" + log.data.slice(2 + 64 * 3, 2 + 64 * 4) : "";
        add(rc.status === "0x1" && stored === j.reasoning_hash, `On ${esc(F.chain.name)}: the trade's Opened event carries exactly this hash.`);
      }
      const CLEARED = "0x" + keccak256("Cleared(uint256,address)");
      for (const e of j.status === "opened" ? r.evidence.filter((e) => e.verdict_tx) : []) {
        const rc = await rpc("eth_getTransactionReceipt", [e.verdict_tx]);
        const hit = rc.logs.some((l) => l.address.toLowerCase() === F.contracts.market.toLowerCase() && l.topics[0] === CLEARED && BigInt(l.topics[1]) === BigInt(e.claim));
        add(rc.status === "0x1" && hit, `On ${esc(F.chain.name)}: claim #${e.claim}'s verdict transaction cleared it.`);
      }
      for (const a of j.attempts) {
        const rc = await rpc("eth_getTransactionReceipt", [a.tx]);
        add(rc.status === "0x0", `On ${esc(F.chain.name)}: the trade citing claim #${a.claim} reverted.`);
      }
    } catch (err) { add(false, `Could not reach ${esc(F.chain.name)} from the browser (${esc(err.message)}).`); }
  }
  const bad = list.querySelectorAll(".no").length;
  rows.push(`<li class="sum ${bad ? "no" : "ok"}">${bad ? `${bad} check${bad > 1 ? "s" : ""} failed.` : F.chain.rpc ? "Every link in the chain of reasons holds, on-chain too." : "Every link checked here holds. The on-chain links need the command line."}</li>`);
  list.innerHTML = rows.join("");
  button.disabled = false;
}

// ---- the audit record ------------------------------------------------------------
// One self-contained file per journal entry: the trade, each claim's exact words,
// the filing, the verdict and its evidence, the refusals, the reasoning record,
// how to check every line independently, and what the record does not prove.
function download(name, text) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
  a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function auditRecord(j) {
  const by = byId(), r = j.reasoning, ex = F.chain.explorer, f = F.filings[j.ticker] || {};
  const tx = (h) => !h ? "n/a" : ex ? `${h} (${ex}/tx/${h})` : `${h} (local devnet)`;
  const zero = (h) => !h || /^0x0+$/.test(h);
  const L = [];
  L.push(`# Audit record: ${j.ticker} ${j.status === "opened" ? `${SIDE[j.side]} paper trade, journal entry #${j.entry}` : "no-trade decision"}`, "");
  L.push(`Generated ${new Date().toISOString()} from ${location.origin}${location.pathname} (round of ${new Date(F.generated * 1000).toISOString()}).`, "");
  L.push(`- Chain: ${F.chain.name} (chain id ${F.chain_id})`, `- BondedClaims (the market): ${F.contracts.market}`, `- AgentDesk (the trading desk): ${F.contracts.desk}`,
    `- Verdicts written by: ${F.settled_by || "the verifier key (v1)"}`, `- Trading agent: ${F.trader || "n/a"}`, "");
  if (j.status === "opened") {
    L.push("## The trade", "", `- Side and size: ${SIDE[j.side]} ${money(j.notional / 1e6)} USD, paper (no money moves)`, `- Transaction: ${tx(j.tx)}`,
      `- Reasoning hash stored with the trade: ${j.reasoning_hash}`, `- Reference price: ${r.price ? `${r.price.price} ${r.price.currency} (${r.price.source})` : "none recorded"}`, "");
  } else L.push("## The decision", "", "No trade: under the agent's rules, what was left after the refusals points nowhere.", "");
  L.push(`## The filing`, "", `- ${j.ticker} ${f.form || "10-Q"}, accession ${f.accession || "?"}, filed ${f.filed || "?"}, period ${f.period || "?"}`, `- ${f.url || ""}`, "");
  L.push(j.status === "opened" ? "## Claims the trade cites (each cleared)" : "## Claims left when the agent stopped", "");
  for (const e of r.evidence) {
    const c = by[e.claim];
    L.push(`### Claim #${c.id}, by ${c.analyst}${c.analyst_kind === "model" ? " (a language model)" : ""}`, "",
      ...(c.replayed_from ? [`- Replayed: ${replayed(c)}; the same words hashed to ${c.replayed_from.hash} on market ${c.replayed_from.market} (chain ${c.replayed_from.chain_id})`] : []),
      ...(c.post ? [`- From a post by ${c.post.handle} (a written fixture, not a real account): "${c.post.text}"`,
                    `- The agent's reading: ${c.reading.sentiment}, ${c.reading.conviction} conviction, ${c.reading.urgency} (${c.reading.rule})`] : []),
      `- Analyst wallet: ${c.analyst_address}`, `- Stake: ${money(c.stake)} USDG`, `- Figure claimed: ${c.value}`,
      `- Summary as published: ${c.summary || "(none)"}`, `- Sentence quoted: "${c.quote}"`,
      `- keccak256 of the claim's canonical words (on-chain): ${c.hash}`, `- Posted: ${tx(c.tx_post)}`,
      `- Verdict: ${c.verdict.toUpperCase()}: ${c.reason}`, `- Verdict transaction: ${tx(c.tx_judge)}`,
      `- Filing bytes checked (keccak256): ${zero(c.evidence) ? "not recorded (v1 or unchecked)" : c.evidence}`,
      `- CRE workflow id: ${zero(c.workflow_id) ? "not supplied (simulation forwarder or local)" : c.workflow_id}`,
      `- The agent read it as: ${e.signal > 0 ? "bullish" : e.signal < 0 ? "bearish" : "no signal"} (${e.why.replace(/: (bullish|bearish)$/, "").replace(/^no signal: /, "")})`, "");
  }
  if (j.attempts.length) {
    L.push("## Trades the desk refused, on-chain", "");
    for (const a of j.attempts) { const c = by[a.claim]; L.push(`- Claim #${a.claim} (${c.analyst}): ${c.reason}. Reverted transaction: ${tx(a.tx)}`); }
    L.push("");
  }
  L.push("## The reasoning record", "", `Its keccak256 is ${"0x" + keccak256(VouchPolicy.canonical(r))}. Canonical JSON (keys sorted, no whitespace, UTF-8):`, "", "```json", VouchPolicy.canonical(r), "```", "");
  L.push("## How to check every line yourself", "",
    "1. Download the filing from the URL above and compute keccak256 of the bytes: it equals each verdict's filing hash.",
    "2. Rebuild each claim's canonical JSON (ticker, accession, metric, value, quote, analyst, summary; keys sorted; no whitespace) and hash it: it equals the on-chain claim hash.",
    "3. Look up each transaction above on the explorer: the verdicts emit Checked and Cleared or Slashed for the claim id; the refusals reverted; the trade's Opened event carries the reasoning hash.",
    "4. Re-run the check and the agent's rules: `python -m vouchrh.journal verify feed.json --rpc <chain rpc>` from github.com/ubmids/vouch-research.", "");
  L.push("## What this record does not prove", "",
    "- that any view was honestly held (the Regulation AC certification concerns belief);",
    "- that a recommendation had a reasonable basis (FINRA Rule 2241(c)(1)(B)); Vouch checks facts against the filing, not opinions;",
    "- that the filing itself is accurate, or that a cleared figure is complete or material;",
    "- who controls a wallet, or compliance with SEC Rule 17a-4.", "",
    "See docs/bli/LEGAL.md in the repository. This record is not legal advice.");
  return L.join("\n") + "\n";
}

// The one sentence that says exactly what went wrong, from the check's reason.
function specific(c) {
  const r = c.reason || "", Q = { January: 1, February: 1, March: 1, April: 2, May: 2, June: 2, July: 3, August: 3, September: 3, October: 4, November: 4, December: 4 };
  let m = r.match(/^wrong quarter: the period ended in (\w+), the claim says (.+)$/);
  if (m) return `The filing's quarter ended in ${esc(m[1])}, which is Q${Q[m[1]] || "?"}. The claim says ${esc(m[2])}.`;
  m = r.match(/^wrong period: the filing gives (.+) for (.+), the claim says (.+)$/);
  if (m) return `In the filing, ${esc(m[1])} is the figure for ${esc(m[2])}. The claim says it's for ${esc(m[3])}.`;
  m = r.match(/^wrong date: the filing gives (.+) as of (.+), the claim says (.+)$/);
  if (m) return `In the filing, ${esc(m[1])} is the balance as of ${esc(m[2])}. The claim dates it ${esc(m[3])}.`;
  return esc(plain(c).why);
}

// ---- follow one claim: the story before the data ------------------------------
function story(lead) {
  const cs = F.claims, wrong = lead;
  const right = cs.find((c) => c.verdict === "cleared" && c.quote === wrong.quote && c.id !== wrong.id)
    || cs.find((c) => c.verdict === "cleared" && c.ticker === wrong.ticker) || cs.find((c) => c.verdict === "cleared");
  const ex = F.chain.explorer, f = F.filings[wrong.ticker] || {};
  const tx = (h, label) => ex && h ? `<a class="txl" href="${ex}/tx/${h}" target="_blank" rel="noopener">${label} on ${esc(F.chain.name)} ↗</a>` : "";
  const J = F.journal || [], je = J.find((j) => j.ticker === wrong.ticker);
  const trades = J.filter((j) => j.status === "opened").length, refusals = J.reduce((a, j) => a + j.attempts.length, 0);
  const acted = cs.filter((c) => c.desk && c.desk.acted).length, refused = cs.length - acted;
  const company = NAMES[wrong.ticker] || wrong.ticker;
  const bond = Math.max(...F.standings.map((s) => s.bonded));      // what each analyst started with
  const who = (c) => `<div class="who2">${c.analyst_kind === "model" ? '<i class="ai">AI</i>' : ""}<b>${esc(c.analyst)}</b><span>${c.analyst_kind === "model" ? (c.replayed_from ? `a language model; ${esc(replayed(c))}` : "a language model, running on a laptop") : esc(KIND[c.analyst_kind] || "a scripted analyst")}</span></div>`;
  const period = (t) => esc(t).replace(/\b((?:three|six|nine|twelve)(?: and (?:three|six|nine|twelve))? months ended [A-Z][a-z]+ \d{1,2}, \d{4})/, '<mark class="g">$1</mark>');
  const said = (c) => c.summary ? esc(c.summary).replace(/\b(Q[1-4](?: \d{4})?)/, c.verdict === "slashed" ? '<mark class="r">$1</mark>' : '$1') : `${esc(company)}'s figure is <b>${esc(c.value)}</b>.`;
  const S = {
    wrong: [
      [wrong.analyst_kind === "model" ? `An AI read ${esc(company)}'s quarterly report and wrote this.`
        : wrong.analyst_kind === "kol" ? `A market voice posted this about ${esc(company)}.` : `An analyst read ${esc(company)}'s quarterly report and wrote this.`,
        `${who(wrong)}<blockquote>${said(wrong)}</blockquote><div class="chip">citing ${esc(company)}'s ${esc(f.form || "10-Q")}, filed ${esc(f.filed || "")}</div>`],
      [`It put ${money(wrong.stake)} USDG of its own money behind that sentence.`,
        `<div class="stakeViz"><div><span>its bond</span><b>${money(bond)} USDG</b></div><div class="arrow">→</div><div class="lockd"><span>locked on this claim</span><b>${money(wrong.stake)} USDG</b></div></div>
         <p class="small">If the claim is true, the money comes back. If it isn't, it's gone. That's the whole idea.</p>${tx(wrong.tx_post, "the stake")}`],
      [`Vouch checked it against the actual filing.`,
        `<div class="vs"><div><span>The claim says</span><p>${said(wrong)}</p></div><div><span>${esc(company)}'s 10-Q says</span><p>${period(wrong.source ? wrong.source.match : wrong.quote)}</p></div></div>
         <p class="small">${specific(wrong)} <b class="r">${esc(plain(wrong).short[0].toUpperCase() + plain(wrong).short.slice(1))}.</b></p>`],
      [`Wrong, so it paid.`,
        `<div class="flow big"><div class="n">${esc(wrong.analyst)}<b class="s">−${money(wrong.stake)} USDG</b></div><div class="ar">→</div><div class="n">${split(wrong, "<br>")}<b class="c">+${money(wrong.stake)}</b></div></div>
         <p class="small">No moderator decided this. The check is mechanical, so anyone can re-run it and get the same answer.</p>${tx(wrong.tx_judge, "the slash")}`],
      [`A trading agent wanted to act on it. The contract said no.`,
        `<div class="agentViz"><div class="bad">✕ trade refused</div><p>The agent trades through a desk that asks Vouch first. A claim that failed the check can't back a trade, so the transaction reverted on-chain.</p></div>
         <p class="small">${J.length ? `Across this round the desk refused <b class="r">${refusals}</b> trades that cited a wrong claim. The agent made <b class="c">${trades}</b> paper trades, each on research that held.`
           : `Across this round it traded on all <b class="c">${acted}</b> true claims and was refused on all <b class="r">${refused}</b> wrong ones.`}</p>${tx(wrong.desk && wrong.desk.tx, "the refused trade")}`],
      ...(je ? [[`Every trade it did make keeps its reasons.`,
        `<div class="jmini">${je.attempts.slice(0, 4).map((a) => `<div class="s">✕ #${a.claim} refused · ${esc(plain(cs.find((c) => c.id === a.claim)).short)}</div>`).join("")}
           ${(je.reasoning.evidence || []).map((e) => `<div class="c">✓ #${e.claim} cleared · ${esc(e.value)} · ${e.signal > 0 ? "bullish" : e.signal < 0 ? "bearish" : "no signal"}</div>`).join("")}
           <div class="d">${je.status === "opened" ? `→ ${SIDE[je.side]} ${esc(je.ticker)} ${money(je.notional / 1e6)} USD paper · reasoning hash ${esc(short(je.reasoning_hash, 8, 6))} on-chain` : "→ no trade: what held points nowhere"}</div></div>
         <p class="small">The journal names the claims behind each trade, the verdict on each and who wrote it, and the rules that turned them into a position. Anyone can re-run it.</p>`]] : []),
    ],
    right: [
      [right.analyst_kind === "kol" ? `Another voice posted about the same report.` : `Another analyst read the same report and quoted the same sentence.`,
        `${who(right)}<blockquote>${said(right)}</blockquote><div class="chip">citing the same ${esc(f.form || "10-Q")}</div>`],
      [`It staked ${money(right.stake)} USDG too.`,
        `<div class="stakeViz"><div><span>its bond</span><b>${money(bond)} USDG</b></div><div class="arrow">→</div><div class="lockd"><span>locked on this claim</span><b>${money(right.stake)} USDG</b></div></div>${tx(right.tx_post, "the stake")}`],
      [`Vouch checked it: word for word, figure for figure.`,
        `<div class="vs one"><div><span>${esc(NAMES[right.ticker] || right.ticker)}'s 10-Q says</span><p><mark class="g">${esc(right.source ? right.source.match : right.quote)}</mark></p></div></div>
         <p class="small">The sentence is in the filing, the figure ${esc(right.value)} is in it, and nothing claimed goes beyond it. <b class="c">It matches.</b></p>`],
      [`Right, so it kept its money.`,
        `<div class="flow big"><div class="n">${esc(right.analyst)} staked<b>${money(right.stake)} USDG</b></div><div class="ar">→</div><div class="n">returned in full<b class="c">+${money(right.stake)}</b></div></div>${tx(right.tx_judge, "the clearance")}`],
      [`A trading agent acted on it.`,
        `<div class="agentViz"><div class="good">✓ trade opened</div><p>The desk asked Vouch whether the claim was cleared. It was, so the agent's position opened.</p></div>${tx(right.desk && right.desk.tx, "the trade")}`],
    ],
  };
  let which = "wrong", i = 0, opener = null;
  const KICK = { wrong: F.fixture ? "How Vouch works · one claim (a written fixture post)" : "How Vouch works · one real claim", right: "The same sentence, told right" };
  const end = () => which === "wrong"
    ? `<div class="endCard"><h3>That's Vouch: research that costs money to get wrong.</h3>
        <p>AI analysts are fast and fluent, and sometimes wrong about numbers. Here, being wrong has a price, and agents only act on what survived the check.</p>
        <div class="acts"><button class="primary" id="endExplore">Explore all ${cs.length} claims</button>${J.length ? `<button id="endJournal">Open the agent's journal</button>` : ""}<button id="endTry">Check a claim yourself</button><button id="endAgain">See the same sentence told right →</button></div></div>`
    : `<div class="endCard"><h3>Same filing, same sentence. One claim paid, one got paid.</h3>
        <p>The difference was whether the claim said what the filing says. That's the only thing Vouch checks, and it checks it every time.</p>
        <div class="acts"><button class="primary" id="endExplore">Explore all ${cs.length} claims</button><button id="endTry">Check a claim yourself</button><button id="endAgain">← Back to the wrong one</button></div></div>`;
  const draw = () => {
    const steps = S[which], last = i === steps.length;
    $("#obKicker").textContent = KICK[which];
    $("#stepNum").textContent = last ? "" : `${i + 1} of ${steps.length}`;
    $("#stepBody").innerHTML = last ? end() : `<h2 id="stepTitle">${steps[i][0]}</h2><div class="viz">${steps[i][1]}</div>`;
    $("#dots").innerHTML = [...steps, 0].map((_, k) => `<i class="${k < i ? "done" : k === i ? "on" : ""}"></i>`).join("");
    $("#prev").disabled = i === 0;
    $("#next").hidden = last;
    $("#skipTour").textContent = last ? "Close" : "Skip";
    if (last) {
      $("#endExplore").onclick = () => closeTour(true);
      $("#endTry").onclick = () => { closeTour(false); openCheck(); };
      if ($("#endJournal")) $("#endJournal").onclick = () => { closeTour(false); openEntry(wrong.ticker); };
      $("#endAgain").onclick = () => { which = which === "wrong" ? "right" : "wrong"; i = 0; draw(); };
    }
  };
  const seen = () => { try { localStorage.setItem("vouch.tour", "seen"); } catch (e) {} };
  const openTour = () => {
    opener = document.activeElement;
    which = "wrong"; i = 0; draw();
    $("#story").hidden = false;
    document.body.classList.add("touring");
    $("#next").focus({ preventScroll: true });
  };
  const closeTour = (toClaims) => {
    $("#story").hidden = true;
    document.body.classList.remove("touring");
    seen();
    if (toClaims) $("#claims").scrollIntoView({ behavior: "smooth", block: "start" });
    else if (opener && opener.focus) opener.focus({ preventScroll: true });
  };
  $("#next").onclick = () => { i = Math.min(S[which].length, i + 1); draw(); };
  $("#prev").onclick = () => { i = Math.max(0, i - 1); draw(); };
  $("#skipTour").onclick = () => closeTour(false);
  $("#openTour").onclick = $("#headTour").onclick = openTour;
  $("#story").addEventListener("click", (e) => { if (e.target === $("#story")) closeTour(false); });
  addEventListener("keydown", (e) => {
    if ($("#story").hidden) return;
    if (e.key === "ArrowRight" && !$("#next").hidden) $("#next").click();
    else if (e.key === "ArrowLeft" && !$("#prev").disabled) $("#prev").click();
    else if (e.key === "Escape") closeTour(false);
  });
  // Swipe on a phone: left for next, right for back.
  let x0 = null;
  $("#story").addEventListener("touchstart", (e) => { x0 = e.touches[0].clientX; }, { passive: true });
  $("#story").addEventListener("touchend", (e) => {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0; x0 = null;
    if (Math.abs(dx) < 60) return;
    if (dx < 0 && !$("#next").hidden) $("#next").click(); else if (dx > 0 && !$("#prev").disabled) $("#prev").click();
  }, { passive: true });
  // First visit, or ?tour in the link (for judges and the video): open it.
  let first = true;
  try { first = localStorage.getItem("vouch.tour") !== "seen"; } catch (e) {}
  const qs = new URLSearchParams(location.search);
  if ((first && !qs.has("journal") && !qs.has("claim")) || qs.has("tour")) openTour();
}
