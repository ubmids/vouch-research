"""scripts/cre_round.sh gives Subomi one clean shot: it checks everything it
can before spending gas, simulates once without broadcasting, and never lets
a failed simulation pass silently. Run here against anvil, with a stand-in
`cre` that fails in the ways the real one can."""
import os
import stat
import subprocess
import textwrap

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPT = os.path.join(ROOT, "scripts", "cre_round.sh")
KEY0 = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"   # anvil's well-known key

STUB = textwrap.dedent("""\
    #!/bin/bash
    # a stand-in CRE CLI: STUB_DRY / STUB_BROADCAST = ok | fail | silent
    case "$1" in
      version) echo "CRE CLI version v0.0.0-stub" ;;
      whoami) [ -n "$STUB_LOGGED_OUT" ] && { echo "not logged in"; exit 1; }; echo "Email: stub@example.com" ;;
      workflow)
        case "$2" in
          build) while [ $# -gt 0 ]; do [ "$1" = -o ] && echo wasm > "$2"; shift; done
                 echo "Binary hash: 00stub00" ;;
          simulate)
            mode=$STUB_DRY; for a in "$@"; do [ "$a" = --broadcast ] && mode=$STUB_BROADCAST; done
            echo "$@" >> "$STUB_CALLS"
            case "$mode" in
              fail) echo "Error: simulation failed"; exit 1 ;;
              silent) echo "[USER LOG] claim read" ;;
              ok) echo "[USER LOG] verdict: CLEAR (quote verified and value grounded)"
                  echo "[USER LOG] verdict for claim #0 written: 0x0000000000000000000000000000000000000000000000000000000000000000" ;;
            esac ;;
        esac ;;
    esac
    """)


@pytest.fixture
def env(chain, tmp_path):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "cre").write_text(STUB)
    (bin_ / "cre").chmod(stat.S_IRWXU)
    key = tmp_path / "testnet.key"
    key.write_text(KEY0 + "\n")
    e = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "VOUCH_RPC": chain.w3.provider.endpoint_uri,
         "VOUCH_KEYFILE": str(key), "VOUCH_FEED": str(tmp_path / "feed.json"), "VOUCH_RUNS": str(tmp_path / "runs"),
         "VOUCH_SKIP_SEC_CHECK": "1", "ANALYST_MODEL": "replay", "PER_TICKER": "1", "OLLAMA_HOST": "http://127.0.0.1:9",
         "STUB_CALLS": str(tmp_path / "calls.txt"), "STUB_DRY": "ok", "STUB_BROADCAST": "ok"}
    e.pop("STUB_LOGGED_OUT", None)
    return e, tmp_path


def sh(e, *args):
    r = subprocess.run(["bash", SCRIPT, *args], cwd=ROOT, env=e, capture_output=True, text=True, timeout=900)
    return r.returncode, r.stdout + r.stderr


def run_dir(tmp):
    runs = sorted((tmp / "runs").iterdir())
    assert len(runs) == 1
    return runs[0]


def test_preflight_spends_nothing_and_records_the_environment(env):
    e, tmp = env
    code, out = sh(e, "--preflight")
    assert code == 0, out
    assert "preflight passed; nothing was spent" in out
    text = (run_dir(tmp) / "env.txt").read_text()
    for field in ("wasm_binary_hash: 00stub00", "cre: CRE CLI version v0.0.0-stub", "stub@example.com", "wallet: 0xf39F"):
        assert field in text, field
    assert KEY0[2:] not in text and not (tmp / "feed.json").exists()


def test_not_logged_in_stops_at_the_preflight(env):
    e, tmp = env
    code, out = sh(e | {"STUB_LOGGED_OUT": "1"}, "--preflight")
    assert code == 1 and "not logged in to CRE" in out


def test_a_live_model_that_does_not_write_the_hero_stops_the_round(env):
    e, tmp = env
    code, out = sh(e | {"ANALYST_MODEL": "live"}, "--preflight")
    assert code == 1 and "ANALYST_MODEL=replay" in out


def test_a_failed_dry_run_stops_before_any_verdict_is_broadcast(env):
    e, tmp = env
    code, out = sh(e | {"STUB_DRY": "fail"}, )
    assert code == 1, out
    assert "the simulation failed before any verdict was sent" in out
    calls = (tmp / "calls.txt").read_text().splitlines()
    assert len(calls) == 1 and "--broadcast" not in calls[0]
    assert not list(run_dir(tmp).glob("claim-*.log")) and not (run_dir(tmp) / "finish.log").exists()


def test_simulations_that_write_no_verdict_stop_the_round_before_it_finishes(env):
    e, tmp = env
    code, out = sh(e | {"STUB_BROADCAST": "silent"})
    assert code == 1, out
    assert "the workflow wrote no verdict, so the round stops here" in out
    assert "verdicts_written: 0 of 25" in (run_dir(tmp) / "env.txt").read_text()
    assert not (run_dir(tmp) / "finish.log").exists()
    calls = (tmp / "calls.txt").read_text().splitlines()
    assert len(calls) == 26 and all("--config" in c for c in calls)   # one dry run, then each of the 25 claims
