"""The narrated BLI video: Subomi's voice (ElevenLabs, cached) over a scripted
screen recording of web/ on the local round, with the Exhibit overlays.

    python3 scripts/video/narrated.py            # everything (needs playwright)
    python3 scripts/video/narrated.py --audio    # only (re)generate and time the voice

Voice lines are in scripts/video/lines.json ("text" is the caption, "tts" what
the voice is sent when it must be spelled out). Audio is cached in VOICE_DIR,
so a rebuild costs no characters. Recordings and segments go to WORK and are
deleted at the end. Outputs: OUT/vouch-narrated.{mp4,srt} and the script.
Records the local round (feed-local.json), so the CRE part carries the SDK
test runtime caption, never the simulation one (docs/bli/DEMO_SCRIPT.md).
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import time
import functools
import http.server

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from voice import line as tts_line, spent  # noqa: E402

HOME = pathlib.Path.home()
VOICE_DIR = pathlib.Path(os.environ.get("VOICE_DIR", HOME / "Desktop/hackathons/vouch-video/voice"))
OUT = pathlib.Path(os.environ.get("OUT", HOME / "Desktop/hackathons/vouch-video"))
WORK = pathlib.Path(os.environ.get("WORK", OUT / "work/build"))
ASSETS = ROOT / "docs/assets/video"
FEED = "feed-local.json"
W, H, FPS = 1920, 1080, 30
GAP, BREAK, LEAD, END_HOLD, IN = 0.4, 0.6, 0.6, 3.0, 0.25

# Which lines play over which recording. Overlays: (png, start, end) in
# seconds from the session start; None = to the end. "replayed" etc. are the
# caption cards, shrunk into the right margin so they never cover the evidence.
SESSIONS = [
    ("title", ["intro"]),
    ("feed", ["problem1", "what"]),
    ("record", ["record", "exh6"]),
    ("claim", ["claim1", "claim2", "custody"]),
    ("deck", ["legal"]),
    ("terminal", ["cre"]),
    ("journal", ["journal1", "journal2"]),
    ("kol", ["kol"]),
    ("limits", ["limits"]),
    ("close", ["close"]),
]


def sh(*a, **k):
    return subprocess.run(a, check=True, capture_output=True, text=True, **k).stdout


def dur(f):
    return float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)))


def load_lines():
    lines = json.loads((HERE / "lines.json").read_text())
    for l in lines:
        l["mp3"] = tts_line(l.get("tts", l["text"]), VOICE_DIR)
        l["dur"] = l.get("cut_at") or dur(l["mp3"])
    return {l["id"]: l for l in lines}, lines


def timeline(L):
    """Absolute start of every line and every session."""
    t, plan = 0.0, []
    for i, (name, ids) in enumerate(SESSIONS):
        start = t
        t += LEAD if i == 0 else IN
        marks = []
        for j, lid in enumerate(ids):
            L[lid]["start"] = t
            marks.append(t - start)
            t += L[lid]["dur"] + (GAP if j < len(ids) - 1 else 0)
        t += BREAK if i < len(SESSIONS) - 1 else END_HOLD
        plan.append({"name": name, "ids": ids, "start": start, "len": t - start, "marks": marks})
    return plan, t


# ---------------------------------------------------------------- the browser

HELPERS = r"""
(() => {
  const d = document.createElement('div'); d.id = '__cur';
  d.innerHTML = '<svg width="34" height="34" viewBox="0 0 24 24"><path d="M4 2.5l6.6 18.2 2.6-7.6 7.6-2.6z" fill="#111" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  d.style.cssText = 'position:fixed;left:1500px;top:1200px;z-index:2147483647;pointer-events:none;transition:left .9s cubic-bezier(.4,0,.2,1),top .9s cubic-bezier(.4,0,.2,1);filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))';
  document.body.appendChild(d);
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  window.__el = (txt, sel = '*', nth = 0) => {
    const hits = [];
    for (const e of document.querySelectorAll(sel)) {
      if (!vis(e)) continue;
      const t = (e.textContent || '').toUpperCase();
      if (t.includes(txt.toUpperCase())) { const r = e.getBoundingClientRect(); hits.push({ e, a: r.width * r.height, y: r.top + scrollY }); }
    }
    // the smallest element holding the text, per place on the page
    const leaves = hits.filter((h) => !hits.some((o) => o !== h && h.e.contains(o.e)));
    leaves.sort((a, b) => a.y - b.y);
    return leaves[nth] ? leaves[nth].e : null;
  };
  window.__point = (txt, sel = '*', dx = 0.5, dy = 0.6, nth = 0) => {
    const e = __el(txt, sel, nth); if (!e) return 'missing: ' + txt;
    const r = e.getBoundingClientRect();
    d.style.left = (r.left + r.width * dx) + 'px'; d.style.top = (r.top + r.height * dy) + 'px'; return 'ok';
  };
  window.__xy = (x, y) => { d.style.left = x + 'px'; d.style.top = y + 'px'; };
  window.__scroll = (y, ms) => new Promise((res) => {
    const y0 = scrollY, t0 = performance.now(), dy = y - y0;
    const step = (now) => { const k = Math.min(1, (now - t0) / ms), e = k < .5 ? 2*k*k : 1 - Math.pow(-2*k + 2, 2) / 2;
      scrollTo(0, y0 + dy * e); k < 1 ? requestAnimationFrame(step) : res(); };
    requestAnimationFrame(step);
  });
  window.__top = (txt, sel = '*', nth = 0) => { const e = __el(txt, sel, nth); return e ? e.getBoundingClientRect().top + scrollY : null; };
})();
"""


class Shot:
    """One browser recording. at(t) waits until t seconds after the page was ready."""

    def __init__(self, browser, url, name):
        self.dir = WORK / f"rec-{name}"
        self.ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(self.dir),
                                       record_video_size={"width": W, "height": H}, color_scheme="light")
        self.ctx.add_init_script("try{localStorage.setItem('tour.seen','1')}catch(e){}")
        self.t0 = time.time()
        self.page = self.ctx.new_page()
        self.page.goto(url)
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(900)
        self.page.evaluate(HELPERS)

    def ready(self):
        self.page.wait_for_timeout(300)
        self.offset = time.time() - self.t0
        self.start = time.time()

    def at(self, t):
        wait = self.start + t - time.time()
        if wait > 0:
            time.sleep(wait)

    def js(self, code):
        r = self.page.evaluate(code)
        if isinstance(r, str) and r.startswith("missing"):
            print("   !", r)
        return r

    def scroll_to(self, txt, sel="*", offset=140, ms=1200, nth=0):
        y = self.page.evaluate(f"__top({json.dumps(txt)}, {json.dumps(sel)}, {nth})")
        if y is None:
            print("   ! no", txt)
            return
        self.page.evaluate(f"__scroll({max(0, y - offset)}, {ms})")

    def finish(self, length):
        self.at(length + 0.6)
        path = self.page.video.path()
        self.ctx.close()
        return pathlib.Path(path), self.offset


def serve_web():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "web"))
    handler.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def terminal_page(feed):
    """The workflow's own log lines for Tesla's ten claims, as the round recorded them."""
    F = json.loads((ROOT / "web" / feed).read_text())
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;")
    rows = []
    for c in sorted(F["claims"], key=lambda c: int(c["id"])):
        if c["ticker"] != "TSLA":
            continue
        slash = c["verdict"] == "slashed"
        for k, lg in enumerate(c.get("workflow_log", [])):
            if "written: 0x000" in lg:
                continue  # the SDK runtime's EVM write is a mock; the report went through the forwarder instead
            cls = "s" if (slash and k == 1) else ("c" if k == 1 else "")
            hl = " hl" if c["id"] in (6, "6") else ""
            rows.append(f'<div class="ln {cls}{hl}" data-claim="{c["id"]}">{esc(lg)}</div>')
        rows.append(f'<div class="ln dim">  forwarder → BondedClaims · verdict tx {esc(c["tx_judge"][:12])}…{esc(c["tx_judge"][-6:])}</div>')
    note = esc(F.get("sdk_runtime", ""))
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700&family=Archivo:wght@800&display=swap" rel="stylesheet">
<style>
html,body{{margin:0;background:#e8d5a3;}}
.win{{position:absolute;left:70px;top:70px;width:1330px;height:940px;background:#14130f;border-radius:10px;box-shadow:0 18px 50px rgba(0,0,0,.35);overflow:hidden}}
.bar{{height:44px;background:#2a2822;display:flex;align-items:center;padding:0 18px;gap:9px;font:700 15px 'Courier Prime',monospace;color:#cfc6ad}}
.dot{{width:13px;height:13px;border-radius:50%;background:#5a564a}}
.bar span{{margin-left:16px}}
.body{{padding:22px 28px;font:400 18px/1.45 'Courier Prime',monospace;color:#e9e4d6;height:860px;overflow:hidden}}
.cmd{{color:#ffd400;font-weight:700}}
.ln{{white-space:pre-wrap;word-break:break-all;opacity:0;transition:opacity .25s}}
.ln.on{{opacity:1}}
.ln.s{{color:#ff5c6c;font-weight:700}} .ln.c{{color:#9fd0ff;font-weight:700}} .dim{{color:#8d8670}}
.ln.hl.on{{background:rgba(255,212,0,.13)}}
.side{{position:absolute;left:1440px;top:300px;width:420px;font:400 17px/1.45 'Courier Prime',monospace;color:#1d1b16}}
.side h3{{font:800 30px/1.05 Archivo,sans-serif;text-transform:uppercase;margin:0 0 12px}}
</style></head><body>
<div class="win"><div class="bar"><i class="dot"></i><i class="dot"></i><i class="dot"></i><span>cre/vouch-verifier · workflow.ts in the CRE SDK test runtime · round of 14 Oct, local devnet</span></div>
<div class="body" id="b"><div class="cmd">$ bash scripts/sdk_round.sh</div>
<div class="dim">== 2. the workflow's handler, in the CRE SDK test runtime, builds a report per claim</div>
{''.join(rows)}</div></div>
<div class="side"><h3>Workflow log, Tesla's ten claims</h3>{note}<br><br>Lines as recorded in web/{esc(feed)}.</div>
<script>const B=document.getElementById('b');
window.__reveal=(ms)=>{{const ls=[...document.querySelectorAll('.ln')];ls.forEach((l,i)=>setTimeout(()=>{{l.classList.add('on');const r=l.getBoundingClientRect(),br=B.getBoundingClientRect();if(r.bottom>br.bottom-10)B.scrollTop+=r.bottom-br.bottom+40;}},i*ms/ls.length));}};
window.__focus=(ms)=>{{const e=document.querySelector('.ln.hl');const y=e.offsetTop-B.offsetTop-260;const y0=B.scrollTop,t0=performance.now();const st=(n)=>{{const k=Math.min(1,(n-t0)/ms);B.scrollTop=y0+(y-y0)*(k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2);if(k<1)requestAnimationFrame(st);}};requestAnimationFrame(st);}};</script>
</body></html>"""


def deck_page():
    name = json.loads((ROOT / "design/assets/brand.json").read_text())["name"]
    html = (ROOT / "docs/deck/bli.html").read_text().replace("__NAME__", name)
    html = html.replace("<head>", f'<head><base href="{(ROOT / "docs/deck").as_uri()}/">', 1)
    p = WORK / "deck.html"
    p.write_text(html)
    return p.as_uri()


def record_all(plan):
    from playwright.sync_api import sync_playwright
    srv, base = serve_web()
    term = WORK / "terminal.html"
    term.write_text(terminal_page(FEED))
    deck = deck_page()
    clips = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for s in plan:
            n, m, length = s["name"], s["marks"], s["len"]
            if n in ("title",):
                continue
            print(f"recording {n} ({length:.1f}s)")
            if n == "feed":
                sh_ = Shot(b, base + f"?feed={FEED}", n); sh_.ready()
                sh_.js("__xy(1500, 1200)")
                sh_.at(1.5); sh_.page.evaluate("__scroll(520, 9000)")
                sh_.at(m[1] - 1.0); sh_.page.evaluate("__scroll(0, 1800)")
                sh_.at(m[1] + 1.2); sh_.js("__point('Depreciation for', 'td,div,p,span', 0.6, 0.8)")
                sh_.at(m[1] + 5.0); sh_.js("__point('SLASHED', '*', 0.5, 0.9, 1)")
                sh_.at(m[1] + 9.0); sh_.js("__point('agent', 'header *', 0.6, 0.9)")
            elif n == "record":
                sh_ = Shot(b, base + f"?record=TSLA&feed={FEED}", n); sh_.ready()
                sh_.at(0.6); sh_.js("__point('TESLA', 'h1,h2,div', 0.4, 0.8)")
                sh_.at(3.8); sh_.scroll_to("Exhibits relied on", "h2,h3,h4,div", 120, 1600)
                sh_.at(5.6); sh_.js("__point('CLEARED', '*', 0.5, 0.9, 0)")
                sh_.at(8.0); sh_.scroll_to("Exhibits refused", "h2,h3,h4,div", 120, 1500)
                sh_.at(10.0); sh_.js("__point('SLASHED', '*', 0.5, 0.9, 0)")
                sh_.at(m[1] - 0.6); sh_.scroll_to("Depreciation for", "td", 380, 1300)
                sh_.at(m[1] + 1.2); sh_.js("__point('Q3 2026', '*', 0.5, 0.9)")
                sh_.at(m[1] + 5.5); sh_.js("__point('Qwen 2.5', 'td', 0.4, 0.9, 1)")
                sh_.at(m[1] + 8.5); sh_.js("__point('SLASHED', '*', 0.5, 0.9, 3)")
            elif n == "claim":
                sh_ = Shot(b, base + f"?claim=6&view=claim&feed={FEED}", n); sh_.ready()
                sh_.at(0.5); sh_.js("__point('Q3 2026', '*', 0.5, 0.9)")
                sh_.at(2.0); sh_.js("__point('six months ended June 30, 2026 was', 'mark,span,p,div', 0.5, 0.8)")
                sh_.at(5.0); sh_.js("__point('Every figure, including', 'li,div,p', 0.3, 0.7)")
                sh_.at(7.5); sh_.js("__point('three and six months ended June 30, 2026', 'mark,span', 0.42, 0.8)")
                sh_.at(10.0); sh_.js("__point('which is Q2', 'li,div,p', 0.5, 0.7)")
                sh_.at(m[1] + 0.2); sh_.js("__point('SLASHED', '*', 0.5, 0.8, 1)")
                sh_.at(m[1] + 3.5); sh_.js("__point('to the readers', '*', 0.5, 0.7)")
                sh_.at(m[2] - 0.6); sh_.scroll_to("Chain of custody", "h2,h3,h4,div", 220, 1200)
                sh_.at(m[2] + 1.0); sh_.js("__point('Posted, 25 USDG', 'td', 0.3, 0.6)")
                sh_.at(m[2] + 3.0); sh_.js("__point('Fetched the 10-Q', 'td', 0.3, 0.6)")
                sh_.at(m[2] + 5.0); sh_.js("__point('Slashed: wrong quarter', 'td', 0.3, 0.5)")
                sh_.at(m[2] + 7.0); sh_.js("__point('citing exhibit 6 refused', 'td', 0.3, 0.6)")
            elif n == "deck":
                sh_ = Shot(b, deck, n)
                sh_.page.evaluate("document.querySelector('section[data-n=\"03\"]').scrollIntoView()")
                sh_.page.wait_for_timeout(400); sh_.ready()
                sh_.at(1.5); sh_.js("__point('Regulation AC', '.label', 0.3, 0.8)")
                sh_.at(5.5); sh_.js("__point('FINRA Rule 2241', '.label', 0.3, 0.8)")
                sh_.at(11.0); sh_.js("__point('technology neutral', 'q,i', 0.5, 0.8)")
                sh_.at(15.0); sh_.js("__point('track agent actions', 'q,i', 0.5, 0.8)")
            elif n == "terminal":
                sh_ = Shot(b, term.as_uri(), n); sh_.ready()
                sh_.page.evaluate("__reveal(6500)")
                sh_.at(7.0); sh_.page.evaluate("__focus(900)")
                sh_.at(8.4); sh_.js("__point('verdict: SLASH (wrong quarter', '.ln.hl', 0.2, 0.5)")
                sh_.at(12.5); sh_.js("__point('filing keccak256', '.ln.hl', 0.75, 0.8)")
            elif n == "journal":
                sh_ = Shot(b, base + f"?view=journal&feed={FEED}", n); sh_.ready()
                sh_.at(0.8); sh_.scroll_to("READ.", "b,strong,div,p", 230, 1200)
                sh_.at(3.0); sh_.js("__point('READ.', 'b,strong', 0.5, 0.8)")
                sh_.at(4.6); sh_.js("__point('REFUSED.', 'b,strong', 0.5, 0.8)")
                sh_.at(6.4); sh_.js("__point('KEPT WHAT HELD.', 'b,strong', 0.5, 0.8)")
                sh_.at(8.2); sh_.js("__point('DECIDED.', 'b,strong', 0.5, 0.8)")
                sh_.at(10.0); sh_.js("__point('COMMITTED.', 'b,strong', 0.5, 0.8)")
                sh_.at(m[1] - 1.4); sh_.scroll_to("Re-verify this trade", "button", 160, 1000)
                sh_.at(m[1] - 0.2); sh_.js("__point('Re-verify this trade', 'button', 0.5, 0.6)")
                sh_.at(m[1] + 0.9); sh_.page.locator("button[data-verify=TSLA]").click()
                sh_.at(m[1] + 2.2); sh_.page.evaluate("__scroll(document.querySelector('#rv-TSLA').getBoundingClientRect().top + scrollY - 260, 1600)")
                sh_.at(m[1] + 4.2); sh_.js("__point('Every claim the agent read', 'li', 0.3, 0.6)")
            elif n == "kol":
                sh_ = Shot(b, base + f"?feed=feed-kol-real.json&view=journal", n); sh_.ready()
                sh_.at(1.0); sh_.js("__point('130', 'b,strong', 0.5, 0.8)")
                sh_.at(5.0); sh_.js("__point('16', 'b,strong', 0.5, 0.8)")
                sh_.at(9.0); sh_.scroll_to("KEPT WHAT HELD.", "b,strong", 300, 1200)
                sh_.at(10.6); sh_.js("__point('$28.24 billion', 'b,strong', 0.5, 0.8)")
                sh_.at(13.0); sh_.js("__point('CLEARED', '*', 0.5, 0.9, 0)")
            elif n == "limits":
                sh_ = Shot(b, base + f"?record=TSLA&feed={FEED}", n)
                sh_.page.evaluate("__scroll(document.documentElement.scrollHeight, 1)")
                sh_.ready()
                sh_.at(1.0); sh_.js("__point('What this record does not prove', 'h2,h3,h4', 0.3, 0.8)")
                sh_.at(5.5); sh_.js("__point('That any view was honestly held', 'li', 0.3, 0.6)")
                sh_.at(8.0); sh_.js("__point('That the filing itself is accurate', 'li', 0.3, 0.6)")
            elif n == "close":
                sh_ = Shot(b, base + f"?record=TSLA&feed={FEED}", n); sh_.ready()
                sh_.at(0.5); sh_.js("__point('Print or save as PDF', 'button', 0.5, 0.7)")
            clips[n] = sh_.finish(length)
        b.close()
    srv.shutdown()
    return clips


# --------------------------------------------------------------- composition

def caption_small(png, name):
    """A caption card cut from its 1920x1080 overlay and shrunk for the right margin."""
    out = WORK / f"{name}-small.png"
    sh("ffmpeg", "-y", "-v", "error", "-i", str(png), "-vf", "crop=720:210:1150:30,scale=430:-1", str(out))
    return out


def segment(s, clip, overlays):
    """One session as an H.264 segment of exactly s['len'] seconds, overlays burned in."""
    out = WORK / f"seg-{s['name']}.mp4"
    L = s["len"]
    if clip is None:   # a still card
        inputs = ["-loop", "1", "-framerate", str(FPS), "-t", f"{L:.3f}", "-i", str(ASSETS / "title.png")]
    else:
        path, offset = clip
        inputs = ["-ss", f"{offset:.3f}", "-i", str(path)]
    chain = [f"[0:v]scale={W}:{H},fps={FPS},tpad=stop_mode=clone:stop_duration=8,trim=duration={L:.3f},setpts=PTS-STARTPTS[v0]"]
    args = []
    last = "v0"
    for k, (png, a, b, xy) in enumerate(overlays):
        args += ["-loop", "1", "-framerate", str(FPS), "-t", f"{L:.3f}", "-i", str(png)]
        b = L if b is None else b
        x, y = xy
        chain.append(f"[{last}][{k + 1}:v]overlay={x}:{y}:enable='between(t,{a:.2f},{b:.2f})'[v{k + 1}]")
        last = f"v{k + 1}"
    sh("ffmpeg", "-y", "-v", "error", *inputs, *args, "-filter_complex", ";".join(chain), "-map", f"[{last}]",
       "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-t", f"{L:.3f}", str(out))
    return out


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main():
    audio_only = "--audio" in sys.argv
    WORK.mkdir(parents=True, exist_ok=True)
    L, lines = load_lines()
    plan, total = timeline(L)
    print(f"voice: {sum(l['dur'] for l in lines):.1f}s of speech, video {total:.1f}s, characters spent so far {spent(VOICE_DIR)}")
    for s in plan:
        print(f"  {s['name']:9s} {s['start']:6.1f}s  +{s['len']:5.1f}s")
    if audio_only:
        return

    clips = record_all(plan)
    rep = caption_small(ASSETS / "caption-replayed.png", "replayed")
    sdk = caption_small(ASSETS / "caption-sdk.png", "sdk")
    margin = (W - 430 - 24, 112)
    sec = lambda i: (ASSETS / f"section-{i}.png", 0.3, 3.6, (0, 0))
    over = {
        "record": [sec(1)],
        "claim": [sec(2)],
        "deck": [sec(3)],
        "terminal": [sec(4), (sdk, 0, None, margin)],
        "journal": [sec(5)],
        "limits": [sec(6)],
    }
    by = {s["name"]: s for s in plan}
    r = by["record"]
    over["record"].append((rep, r["marks"][1], None, margin))
    c = by["claim"]
    over["claim"].append((rep, 0, c["marks"][2] - 0.3, margin))
    segs = []
    for s in plan:
        segs.append(segment(s, clips.get(s["name"]), over.get(s["name"], [])))
        if s["name"] in clips:
            shutil.rmtree(clips[s["name"]][0].parent, ignore_errors=True)
    # the end card over the last seconds of the close
    cl = by["close"]
    end_from = cl["len"] - END_HOLD + 0.4
    endseg = WORK / "seg-close-end.mp4"
    sh("ffmpeg", "-y", "-v", "error", "-i", str(segs[-1]), "-loop", "1", "-framerate", str(FPS), "-i", str(ASSETS / "end.png"),
       "-filter_complex", f"[1:v]format=rgba,fade=in:st={end_from:.2f}:d=0.5:alpha=1[e];[0:v][e]overlay=0:0:enable='gte(t,{end_from:.2f})'",
       "-t", f"{cl['len']:.3f}", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS), str(endseg))
    segs[-1] = endseg

    lst = WORK / "concat.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in segs))
    silent = WORK / "video.mp4"
    sh("ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent))

    # narration: every line delayed to its start
    ins, mix = [], []
    for k, l in enumerate(lines):
        ins += ["-i", str(l["mp3"])]
        ms = int(round(l["start"] * 1000))
        cut = f"atrim=end={l['cut_at']},afade=t=out:st={l['cut_at'] - 0.12}:d=0.12," if l.get("cut_at") else ""
        mix.append(f"[{k}:a]{cut}aresample=48000,adelay={ms}|{ms}[a{k}]")
    mix.append("".join(f"[a{k}]" for k in range(len(lines))) + f"amix=inputs={len(lines)}:normalize=0,apad,atrim=duration={total:.3f},loudnorm=I=-16:TP=-1.5:LRA=11[a]")
    voice = WORK / "voice.m4a"
    sh("ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(mix), "-map", "[a]", "-ar", "48000", "-c:a", "aac", "-b:a", "160k", str(voice))

    OUT.mkdir(parents=True, exist_ok=True)
    mp4 = OUT / "vouch-narrated.mp4"
    sh("ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(voice), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
       "-c:a", "copy", "-t", f"{total:.3f}", "-movflags", "+faststart", str(mp4))

    srt = []
    for k, l in enumerate(lines, 1):
        srt.append(f"{k}\n{srt_time(l['start'])} --> {srt_time(l['start'] + l['dur'])}\n{l['text']}\n")
    (OUT / "vouch-narrated.srt").write_text("\n".join(srt))
    script = ["# Vouch, the narrated video: final script", "",
              f"Voice: ElevenLabs (Subomi's approved voice). Length {total:.1f}s. Recorded on the local round (web/{FEED}).", ""]
    for name, ids in SESSIONS:
        script.append(f"**{name}**")
        script.append("")
        for lid in ids:
            script.append(f"{srt_time(L[lid]['start'])[:8]}  {L[lid]['text']}")
            script.append("")
    (OUT / "vouch-narrated-script.md").write_text("\n".join(script))
    print("wrote", mp4, f"{mp4.stat().st_size / 1e6:.1f} MB", f"{dur(mp4):.2f}s")
    if "--keep" not in sys.argv:
        shutil.rmtree(WORK, ignore_errors=True)


if __name__ == "__main__":
    main()
