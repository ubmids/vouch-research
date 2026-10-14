"""Parity of the CRE workflow's check with the Python check, on QuickJS.

CRE runs TypeScript workflows as WebAssembly: QuickJS compiled by Javy. Bun's
test runner uses JavaScriptCore, so its parity test (parity.test.ts) does not
prove the check behaves the same on the engine that will actually run it. This
builds the check into a Javy module (the Javy binary cre-compile downloads),
runs it under wasmtime over every fixture claim, and compares with the verdicts
the Python check wrote (scripts/cre_fixtures.py).

    PYTHONPATH=agent .venv/bin/python scripts/quickjs_parity.py
Needs bun, javy (~/.cache/javy, installed by `bun install` in cre/vouch-verifier) and wasmtime.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from eth_utils import keccak

from vouchrh import edgar

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / "cre" / "vouch-verifier"


def tool(name: str, *extra: str) -> str:
    found = shutil.which(name) or next((p for p in extra if os.path.exists(os.path.expanduser(p))), None)
    if not found:
        sys.exit(f"{name} not found")
    return os.path.expanduser(found)


def main():
    bun = tool("bun", "~/.bun/bin/bun")
    javy = tool("javy", *sorted(str(p) for p in Path("~/.cache/javy").expanduser().glob("v*/linux-x64/javy")))
    wasmtime = tool("wasmtime", "~/.wasmtime/bin/wasmtime", "~/.local/bin/wasmtime")
    out = Path(tempfile.mkdtemp())
    subprocess.run([bun, "build", "quickjs/harness.ts", "--target=browser", "--format=iife", f"--outfile={out}/h.js"],
                   cwd=WF, check=True, capture_output=True)
    subprocess.run([javy, "build", f"{out}/h.js", "-o", f"{out}/h.wasm"], check=True, capture_output=True)
    ok = True
    for fx_path in sorted((WF / "fixtures").glob("*.json")):
        fx = json.loads(fx_path.read_text())
        f = next(f for f in edgar.filings(fx["ticker"], ("10-Q",), 4) if f.accession == fx["accession"])
        raw, text = f.raw(), f.text()
        claims = [{k: c[k] for k in ("value", "quote", "summary", "metric")} for c in fx["claims"]]
        stdin = json.dumps({"claims": claims}).encode() + b"\n" + raw
        t0 = time.time()
        r = subprocess.run([wasmtime, "run", f"{out}/h.wasm"], input=stdin, capture_output=True, timeout=1800)
        took = time.time() - t0
        if r.returncode:
            print(fx["ticker"], "QuickJS run failed:", r.stderr.decode()[-500:])
            ok = False
            continue
        got = json.loads(r.stdout)
        same_bytes = got["raw"] == fx["evidence_keccak"]      # canonical bytes: SEC's CDN tag dropped, in QuickJS
        same_text = got["text"] == "0x" + keccak(text.encode()).hex() and got["n"] == len(text)
        diffs = [(c, v) for c, v in zip(fx["claims"], got["verdicts"]) if v != c["want"]]
        ok &= same_bytes and same_text and not diffs and len(got["verdicts"]) == len(claims)
        print(f"{fx['ticker']}: bytes {'same' if same_bytes else 'DIFFER'}, text {'same' if same_text else 'DIFFERS'}, "
              f"{len(claims) - len(diffs)}/{len(claims)} verdicts identical on QuickJS ({took:.1f}s)")
        for c, v in diffs[:3]:
            print("   want", c["want"], "\n   got ", v, "\n   for ", c["quote"][:100])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
