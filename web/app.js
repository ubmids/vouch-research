// Vouch feed. Reads feed.json, written by `python -m vouchrh.publish`, and
// shows it. Nothing here decides a verdict: the page displays what the
// deterministic check found and what the chain did about it.
"use strict";
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const short = (h, a = 6, b = 4) => h ? `${h.slice(0, a)}…${h.slice(-b)}` : "";
const money = (n) => Number(n).toLocaleString("en-US", { maximumFractionDigits: 2 });
const NAMES = { TSLA: "Tesla", AMZN: "Amazon", PLTR: "Palantir", NFLX: "Netflix", AMD: "AMD" };
let F, filter = "all", ticker = null, selected = null;

fetch("feed.json", { cache: "no-store" }).then((r) => r.json()).then((d) => { F = d; boot(); })
  .catch(() => { $("#inspect").innerHTML = `<p class="sub">The feed could not be loaded.</p>`; });

function boot() {
  const cs = F.claims, cleared = cs.filter((c) => c.verdict === "cleared").length;
  const staked = cs.reduce((a, c) => a + c.stake, 0);
  const slashed = cs.filter((c) => c.verdict === "slashed").reduce((a, c) => a + c.stake, 0);
  $("#net").textContent = `${F.chain.name} · ${F.chain_id}`;
  $("#footChain").textContent = F.chain.name;
  $("#kpis").innerHTML =
    `<span>claims<b>${cs.length}</b></span><span class="c">cleared<b>${cleared}</b></span>` +
    `<span class="s">slashed<b>${cs.length - cleared}</b></span><span class="opt">at stake<b>${money(staked)} USDG</b></span>` +
    `<span class="opt">lost by wrong claims<b>${money(slashed)}</b></span><span>reader pool<b>${money(F.reader_pool)}</b></span>`;
  const tape = cs.slice().reverse().map((c) =>
    `<span><b>${esc(c.ticker)}</b>${esc(c.value)} <span class="${c.verdict[0]}">${c.verdict === "cleared" ? "CLEARED" : "SLASHED −" + c.stake}</span></span>`).join("");
  $("#tape").innerHTML = tape + tape;          // two copies, so the loop is seamless
  watch(); board(); rows();
  const addr = F.contracts;
  $("#addr").innerHTML = `<span>BondedClaims ${esc(addr.market)}</span><span>Bond token (test USDG) ${esc(addr.usdg)}</span>`;
  $("#gen").textContent = `round of ${new Date(F.generated * 1000).toUTCString().slice(5, 22)} UTC`;
  // Open on the most instructive claim: a near-perfect quote with one figure changed.
  const lead = cs.find((c) => c.check.method === "figures-differ") || cs.find((c) => c.verdict === "slashed") || cs[0];
  select(lead.id);
  $("#tabs").onclick = (e) => {
    const b = e.target.closest("button"); if (!b) return;
    filter = b.dataset.f;
    document.querySelectorAll("#tabs button").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
    rows();
  };
}

function watch() {
  const by = {};
  F.claims.forEach((c) => { (by[c.ticker] ||= []).push(c); });
  $("#watch").innerHTML = Object.keys(by).map((t) => {
    const cs = by[t], c = cs.filter((x) => x.verdict === "cleared").length, s = cs.length - c, f = F.filings[t] || {};
    return `<button class="tok" data-t="${t}" aria-pressed="false">
      <div class="t"><b>${t}</b><span>${esc(NAMES[t] || "")}</span></div>
      <div class="f">${esc(f.form || "")} · filed ${esc(f.filed || "")}</div>
      <div class="mix"><i class="c" style="flex:${c}"></i><i class="s" style="flex:${s}"></i></div>
      <div class="nums"><span class="c">${c} cleared</span><span class="s">${s} slashed</span></div></button>`;
  }).join("");
  $("#watch").onclick = (e) => {
    const b = e.target.closest(".tok"); if (!b) return;
    ticker = ticker === b.dataset.t ? null : b.dataset.t;
    document.querySelectorAll(".tok").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.t === ticker)));
    rows();
  };
}

function rows() {
  const list = F.claims.filter((c) => (filter === "all" || c.verdict === filter) && (!ticker || c.ticker === ticker));
  $("#rows").innerHTML = list.map((c) => `
    <tr data-id="${c.id}" class="${c.verdict}" aria-selected="${c.id === selected}">
      <td class="id">${c.id}</td><td class="tk">${esc(c.ticker)}</td><td class="an">${esc(c.analyst)}</td>
      <td class="claim"><span class="v">${esc(c.value)}</span><span class="q">${esc(headline(c))}</span></td><td class="n">${c.stake}</td>
      <td class="vd"><span class="pill ${c.verdict[0]}">${c.verdict.toUpperCase()}</span></td></tr>`).join("");
  $("#filterNote").innerHTML = ticker ? `${esc(ticker)} only · <button id="clearT">show all tokens</button>` : `${list.length} claims`;
  const ct = $("#clearT"); if (ct) ct.onclick = () => { ticker = null; document.querySelectorAll(".tok").forEach((x) => x.setAttribute("aria-pressed", "false")); rows(); };
  $("#rows").onclick = (e) => { const r = e.target.closest("tr"); if (r) select(+r.dataset.id, true); };
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

function select(id, scroll) {
  selected = id;
  document.querySelectorAll("#rows tr").forEach((r) => r.setAttribute("aria-selected", String(+r.dataset.id === id)));
  const c = F.claims.find((x) => x.id === id), f = F.filings[c.ticker] || {}, bad = c.verdict === "slashed";
  const src = c.source, ex = F.chain.explorer;
  const title = !bad ? `In the filing, word for word. <em class="c">Cleared.</em>`
    : c.check.method === "figures-differ" ? `One figure off the filing. <em>Slashed.</em>`
    : c.check.verified ? `Real quote, wrong number. <em>Slashed.</em>`
    : src ? `The quote was altered. <em>Slashed.</em>` : `Not in the filing at all. <em>Slashed.</em>`;
  const why = {
    "exact": "The supporting sentence appears in the 10-Q exactly, and the figure claimed is the one it states.",
    "figures-differ": `The quote is ${(c.check.score * 100).toFixed(1)}% similar to the filing, close enough to pass any fuzzy match. But a figure in it is not the filing's, and figures must match exactly.`,
    "none": src ? "No sentence in the filing matches the quote closely enough." : `The closest passage in the whole 10-Q is only ${(c.similarity * 100).toFixed(0)}% similar. The sentence was invented.`,
    "fuzzy": "A near-match with every figure identical to the filing: extraction noise, not a change of fact.",
  }[c.check.method] || c.reason;
  const reason = c.check.verified && bad ? `The sentence is genuinely in the filing, but it does not say ${esc(c.value)}. The claim asserts a figure its own quote does not contain.` : why;

  let quoted = esc(c.quote), filed = "";
  if (src) {
    const d = diff(src.match, c.quote);
    quoted = d.filter(([k]) => k !== "-").map(([k, w]) => k === "+" && w.trim() ? `<del>${esc(w)}</del>` : esc(w)).join("");
    const fixed = d.filter(([k]) => k !== "+").map(([k, w]) => k === "-" && w.trim() ? `<ins>${esc(w)}</ins>` : esc(w)).join("");
    const val = c.check.verified && bad ? fixed.replace(esc(c.value), `<span class="bad">${esc(c.value)}</span>`) : fixed;
    filed = `<span class="ctx">${esc(src.before)}</span><span class="hit">${val}</span><span class="ctx">${esc(src.after)}</span>`;
  }
  const figsOk = c.check.method !== "figures-differ" && (c.check.verified || !src);
  const simPct = Math.max(0, Math.min(1, c.check.score || c.similarity));
  const txLink = (h, label) => ex ? `<a href="${ex}/tx/${h}" target="_blank" rel="noopener">${label} ${short(h, 10, 6)} ↗</a>` : `<span>${label} ${short(h, 10, 6)} · local devnet</span>`;
  const stakeOut = bad
    ? `<div class="flow"><div class="n">${esc(c.analyst)} stake<b class="s">−${money(c.stake)}</b></div><div class="ar">→</div><div class="n">challenger ${money(c.stake / 2)} · readers ${money(c.stake / 2)}<b class="c">+${money(c.stake)}</b></div></div>`
    : `<div class="flow"><div class="n">${esc(c.analyst)} stake<b>${money(c.stake)}</b></div><div class="ar">→</div><div class="n">released to the analyst<b class="c">+${money(c.stake)}</b></div></div>`;

  $("#inspect").innerHTML = `
    <div class="h"><span>Claim #${c.id} · ${esc(c.ticker)} · ${esc(c.analyst)}</span><span>${esc(f.form || "")} ${esc(c.accession)}</span></div>
    <h2>${title}</h2>
    <p class="sub">${reason}</p>
    <div class="box"><div class="k"><span>The analyst's quote</span><span>claims ${esc(c.value)}</span></div><div class="v">${quoted}</div></div>
    <div class="box"><div class="k"><span>SEC filing says</span><a href="${esc(c.filing_url)}" target="_blank" rel="noopener">${esc((c.filing_url || "").split("/").pop())} ↗</a></div>
      <div class="v">${src ? filed : `<span class="none">No passage in the filing resembles this sentence.</span>`}</div></div>
    <div class="box"><div class="k"><span>The check</span><span>deterministic · no model</span></div><div class="meter">
      <div class="row"><span>similarity</span><div class="track2"><i style="width:${(simPct * 100).toFixed(1)}%"></i><span class="floor" style="left:95%"></span></div><b>${(simPct * 100).toFixed(1)}%</b></div>
      <div class="row"><span>figures</span><span class="${figsOk ? "ok" : "no"}">${figsOk ? (src ? "all match the filing" : "not in the filing") : "differ from the filing"}</span><b class="${figsOk && !bad ? "ok" : "no"}">${figsOk && !bad ? "✓" : "✕"}</b></div>
      <div class="row"><span>value in quote</span><span class="${c.check.verified && bad ? "no" : "ok"}">${c.check.verified && bad ? `${esc(c.value)} is not in it` : "grounded"}</span><b class="${bad ? "no" : "ok"}">${bad ? "✕" : "✓"}</b></div>
    </div></div>
    ${stakeOut}
    <div class="tx">${txLink(c.tx_post, "posted")}${txLink(c.tx_judge, bad ? "slashed" : "cleared")}</div>
    <div class="hash">claim hash ${esc(c.hash)}</div>`;
  if (scroll && innerWidth < 1100) $("#inspect").scrollIntoView({ behavior: "smooth", block: "start" });
}

function board() {
  const max = Math.max(...F.standings.map((s) => s.bonded), 1);
  $("#board").innerHTML = F.standings.slice().sort((a, b) => b.bonded - a.bonded).map((s) => {
    const lost = s.slashed > 0;
    return `<div class="ana"><div class="nm">${esc(s.analyst)}<span>${short(s.address, 6, 4)}</span></div>
      <div class="bb"><i style="width:${(s.bonded / max * 100).toFixed(1)}%;background:${lost ? "var(--flare)" : "var(--volt)"}"></i></div>
      <div class="val">${money(s.bonded)}<span>${s.cleared} ✓ · ${s.slashed} ✕</span></div></div>`;
  }).join("");
}
