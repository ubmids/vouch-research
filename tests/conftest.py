"""A real EVM (anvil) for the round and journal tests, built from the current contracts."""
import os, shutil, socket, subprocess, sys, time
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))
os.environ.setdefault("VOUCH_PRICES", "off")      # never call a price endpoint from the tests

ANVIL = shutil.which("anvil") or os.path.expanduser("~/.foundry/bin/anvil")
KEY0 = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


@pytest.fixture(scope="module")
def chain():
    if not os.path.exists(ANVIL):
        pytest.skip("anvil not installed")
    # The Python side loads Foundry's artifacts; build them if a clean (or a
    # tool such as Slither) removed them, so the test never runs stale code.
    root = os.path.join(os.path.dirname(__file__), "..")
    forge = shutil.which("forge") or os.path.expanduser("~/.foundry/bin/forge")
    subprocess.run([forge, "build"], cwd=root, check=True, capture_output=True)
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    proc = subprocess.Popen([ANVIL, "--silent", "--port", str(port)])
    try:
        from vouchrh.chain import Chain
        for _ in range(50):
            try:
                c = Chain(f"http://127.0.0.1:{port}", KEY0); c.w3.eth.block_number; break
            except Exception:
                time.sleep(0.1)
        yield c
    finally:
        proc.terminate(); proc.wait(timeout=10)


