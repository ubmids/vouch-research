"""Regenerate check/entities.ts from Python's html module (run with the repo's venv)."""
import json, sys
import html as h
from html.entities import html5
from pathlib import Path

out = ["// GENERATED from Python %s's html module by cre/vouch-verifier/gen_entities.py. Do not edit." % sys.version.split()[0],
       "// html.unescape semantics, so the workflow reads a filing exactly as the Python check does.",
       "export const HTML5: Record<string, string> = " + json.dumps(html5, ensure_ascii=True, sort_keys=True) + ";",
       "export const INVALID_CHARREFS: Record<number, string> = "
       + json.dumps({str(k): v for k, v in h._invalid_charrefs.items()}, ensure_ascii=True) + ";",
       "export const INVALID_CODEPOINTS: number[] = " + json.dumps(sorted(h._invalid_codepoints)) + ";", ""]
Path(__file__).with_name("check").joinpath("entities.ts").write_text("\n".join(out))
