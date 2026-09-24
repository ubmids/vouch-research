// Vouch feed. Reads feed.json, written by `python -m vouchrh.publish`, and
// shows it. Nothing here decides a verdict: the page displays what the
// deterministic check found and what the chain did about it. The one thing it
// asks the server is the live check, POST /api/verify, the same check again.
"use strict";
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const short = (h, a = 6, b = 4) => h ? `${h.slice(0, a)}…${h.slice(-b)}` : "";
const money = (n) => Number(n).toLocaleString("en-US", { maximumFractionDigits: 2 });
const NAMES = { TSLA: "Tesla", AMZN: "Amazon", PLTR: "Palantir", NFLX: "Netflix", AMD: "AMD" };
let F, filter = "all", ticker = null, analyst = "", query = "", selected = null;

fetch("feed.json", { cache: "no-store" }).then((r) => r.json()).then((d) => { F = d; boot(); })
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
  const acted = cs.filter((c) => c.desk && c.desk.acted).length;
  $("#net").textContent = F.chain.name;
  $("#net").title = `chain id ${F.chain_id}`;
  $("#footChain").textContent = F.chain.name;
  const k = (cls, label, val, tip) => `<span class="${cls}" title="${esc(tip)}">${label}<b>${val}</b></span>`;
  $("#kpis").innerHTML =
    k("", "claims", cs.length, "Claims posted in this round, each with USDG at stake") +
    k("c", "true", cleared, "Checked against the SEC filing and found true: cleared") +
    k("s", "wrong", cs.length - cleared, "Wrong in a way the check can prove: the analyst lost its stake (slashed)") +
    k("opt", "lost by wrong claims", `${money(lost)} USDG`, "Stake taken from wrong claims: half to whoever caught them, half to the reader pool") +
    (cs[0] && cs[0].desk ? k("opt", "agent trades", `${acted} / ${cs.length}`, "A trading agent tried to act on every claim. The desk only let it trade on true ones") : "");
  // On a phone, three numbers under the bar rather than six in it.
  $("#mkpis").innerHTML = `<span>claims<b>${cs.length}</b></span><span class="c">true<b>${cleared}</b></span><span class="s">wrong<b>${cs.length - cleared}</b></span>`;
  $("#mkpis").hidden = !matchMedia("(max-width: 720px)").matches;
  const tape = cs.slice().reverse().map((c) =>
    `<span><b>${esc(c.ticker)}</b>${esc(c.value)} <span class="${c.verdict[0]}">${c.verdict === "cleared" ? "TRUE" : "WRONG · " + plain(c).short}</span></span>`).join("");
  $("#tape").innerHTML = tape + tape;
  const names = [...new Set(cs.map((c) => c.analyst))];
  $("#who").innerHTML = `<option value="">Every analyst</option>` +
    names.map((n) => `<option value="${esc(n)}">${esc(n)}${cs.find((c) => c.analyst === n).analyst_kind === "model" ? " (AI)" : ""}</option>`).join("");
  watch(); board(); rows();
  const addr = F.contracts, ex = F.chain.explorer;
  const link = (a, label) => ex ? `<a href="${ex}/address/${a}" target="_blank" rel="noopener">${label} ${esc(a)} ↗</a>` : `<span>${label} ${esc(a)}</span>`;
  $("#addr").innerHTML = link(addr.market, "BondedClaims") + (addr.desk ? link(addr.desk, "AgentDesk") : "") + link(addr.usdg, "Bond token");
  $("#gen").textContent = `round of ${new Date(F.generated * 1000).toUTCString().slice(5, 22)} UTC`;

  // Open on the most instructive claim: the AI's own mistake if it made one,
  // else a near-perfect quote with one figure changed.
  const lead = cs.find((c) => c.analyst_kind === "model" && c.verdict === "slashed")
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
      <td class="an">${esc(c.analyst)}${c.analyst_kind === "model" ? ' <span class="ai" title="A language model, running locally">AI</span>' : ""}</td>
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
  const agent = c.desk ? (c.desk.acted
    ? `<p><span class="good">It traded.</span> A trading agent asked Vouch before acting on this claim. It was cleared, so the desk let the position open.</p>`
    : `<p><span class="bad">It was refused.</span> A trading agent tried to act on this claim. The desk asked Vouch first, and a claim that failed the check cannot back a trade, so the transaction reverted on-chain.</p>`) : "";

  $("#inspect").innerHTML = `
    <div class="sheetClose"><button id="closeSheet">← All claims</button><span>claim #${c.id}</span></div>
    <div class="h"><span>${esc(NAMES[c.ticker] || c.ticker)} · ${esc(f.form || "10-Q")} filed ${esc(f.filed || "")}</span><span>claim #${c.id}</span></div>
    <h2>${p.title}</h2>
    <p class="sub">${p.why}${p.rule ? `<span class="rule">${esc(p.rule)}</span>` : ""}</p>

    <div class="box"><div class="k"><span>What ${esc(c.analyst)}${c.analyst_kind === "model" ? " (AI)" : ""} claimed</span><span>${money(c.stake)} USDG at stake</span></div>
      <div class="v said">${c.summary ? esc(c.summary) : `The figure is <b>${esc(c.value)}</b>.`}</div></div>

    <div class="box"><div class="k"><span>The sentence it quoted</span><span>${src && c.quote !== src.match ? "differences marked" : "as quoted"}</span></div><div class="v">${quoted}</div></div>

    <div class="box"><div class="k"><span>What the SEC filing says</span><a href="${esc(c.filing_url)}" target="_blank" rel="noopener">open the filing ↗</a></div>
      <div class="v">${src ? filed : `<span class="none">Nothing in the filing resembles this sentence.</span>`}</div></div>

    <div class="flow">${bad
      ? `<div class="n">${esc(c.analyst)} lost<b class="s">−${money(c.stake)} USDG</b></div><div class="ar">→</div><div class="n">${money(c.stake / 2)} to whoever caught it · ${money(c.stake / 2)} to readers<b class="c">+${money(c.stake)}</b></div>`
      : `<div class="n">${esc(c.analyst)} staked<b>${money(c.stake)} USDG</b></div><div class="ar">→</div><div class="n">returned to the analyst<b class="c">+${money(c.stake)}</b></div>`}</div>

    ${agent ? `<div class="box desk"><div class="k"><span>What a trading agent did</span><span>AgentDesk</span></div><div class="v">${agent}</div></div>` : ""}

    <details class="tech"><summary>Technical details · the check, the transactions, the hash</summary>
      <div class="meter">
        <div class="row"><span>similarity</span><div class="track2"><i style="width:${(simPct * 100).toFixed(1)}%"></i><span class="floor" style="left:95%"></span></div><b>${(simPct * 100).toFixed(1)}%</b></div>
        <div class="row"><span>figures</span><span class="${figsOk ? "ok" : "no"}">${figsOk ? (src ? "all match the filing" : "not in the filing") : "differ from the filing"}</span><b class="${figsOk && src ? "ok" : "no"}">${figsOk && src ? "✓" : "✕"}</b></div>
        <div class="row"><span>claim as written</span><span class="${claimRule ? "no" : "ok"}">${claimRule ? esc(p.short) : "period, date, direction hold"}</span><b class="${claimRule ? "no" : bad ? "" : "ok"}">${claimRule ? "✕" : bad ? "·" : "✓"}</b></div>
      </div>
      <div class="tx">${txLink(c.tx_post, "posted")}${txLink(c.tx_judge, bad ? "slashed" : "cleared")}${c.desk ? txLink(c.desk.tx, c.desk.acted ? "agent's trade" : "agent's refused trade") : ""}</div>
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
      <div class="nm">${esc(s.analyst)}${s.kind === "model" ? ' <i class="ai">AI</i>' : ""}<span>${s.kind === "model" ? "an open model, running locally" : "a scripted analyst"}</span></div>
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
  const acted = cs.filter((c) => c.desk && c.desk.acted).length, refused = cs.length - acted;
  const company = NAMES[wrong.ticker] || wrong.ticker;
  const bond = Math.max(...F.standings.map((s) => s.bonded));      // what each analyst started with
  const who = (c) => `<div class="who2">${c.analyst_kind === "model" ? '<i class="ai">AI</i>' : ""}<b>${esc(c.analyst)}</b><span>${c.analyst_kind === "model" ? "a language model, running on a laptop" : "a scripted analyst"}</span></div>`;
  const period = (t) => esc(t).replace(/\b((?:three|six|nine|twelve)(?: and (?:three|six|nine|twelve))? months ended [A-Z][a-z]+ \d{1,2}, \d{4})/, '<mark class="g">$1</mark>');
  const said = (c) => c.summary ? esc(c.summary).replace(/\b(Q[1-4](?: \d{4})?)/, c.verdict === "slashed" ? '<mark class="r">$1</mark>' : '$1') : `${esc(company)}'s figure is <b>${esc(c.value)}</b>.`;
  const S = {
    wrong: [
      [`An AI read ${esc(company)}'s quarterly report and wrote this.`,
        `${who(wrong)}<blockquote>${said(wrong)}</blockquote><div class="chip">citing ${esc(company)}'s ${esc(f.form || "10-Q")}, filed ${esc(f.filed || "")}</div>`],
      [`It put ${money(wrong.stake)} USDG of its own money behind that sentence.`,
        `<div class="stakeViz"><div><span>its bond</span><b>${money(bond)} USDG</b></div><div class="arrow">→</div><div class="lockd"><span>locked on this claim</span><b>${money(wrong.stake)} USDG</b></div></div>
         <p class="small">If the claim is true, the money comes back. If it isn't, it's gone. That's the whole idea.</p>${tx(wrong.tx_post, "the stake")}`],
      [`Vouch checked it against the actual filing.`,
        `<div class="vs"><div><span>The claim says</span><p>${said(wrong)}</p></div><div><span>${esc(company)}'s 10-Q says</span><p>${period(wrong.source ? wrong.source.match : wrong.quote)}</p></div></div>
         <p class="small">${specific(wrong)} <b class="r">${esc(plain(wrong).short[0].toUpperCase() + plain(wrong).short.slice(1))}.</b></p>`],
      [`Wrong, so it paid.`,
        `<div class="flow big"><div class="n">${esc(wrong.analyst)}<b class="s">−${money(wrong.stake)} USDG</b></div><div class="ar">→</div><div class="n">${money(wrong.stake / 2)} to whoever caught it<br>${money(wrong.stake / 2)} to a pool that protects readers<b class="c">+${money(wrong.stake)}</b></div></div>
         <p class="small">No moderator decided this. The check is mechanical, so anyone can re-run it and get the same answer.</p>${tx(wrong.tx_judge, "the slash")}`],
      [`A trading agent wanted to act on it. The contract said no.`,
        `<div class="agentViz"><div class="bad">✕ trade refused</div><p>The agent trades through a desk that asks Vouch first. A claim that failed the check can't back a trade, so the transaction reverted on-chain.</p></div>
         <p class="small">Across this round it traded on all <b class="c">${acted}</b> true claims and was refused on all <b class="r">${refused}</b> wrong ones.</p>${tx(wrong.desk && wrong.desk.tx, "the refused trade")}`],
    ],
    right: [
      [`Another analyst read the same report and quoted the same sentence.`,
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
  const KICK = { wrong: "How Vouch works · one real claim", right: "The same sentence, told right" };
  const end = () => which === "wrong"
    ? `<div class="endCard"><h3>That's Vouch: research that costs money to get wrong.</h3>
        <p>AI analysts are fast and fluent, and sometimes wrong about numbers. Here, being wrong has a price, and agents only act on what survived the check.</p>
        <div class="acts"><button class="primary" id="endExplore">Explore all ${cs.length} claims</button><button id="endTry">Check a claim yourself</button><button id="endAgain">See the same sentence told right →</button></div></div>`
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
  if (first || new URLSearchParams(location.search).has("tour")) openTour();
}
