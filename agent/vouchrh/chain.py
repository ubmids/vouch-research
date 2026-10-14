"""The contract, from Python.

Reads the ABIs and bytecode Foundry writes to out/, so the Python side can
never drift from the Solidity it talks to. One Chain object holds a web3
connection and a set of local accounts (the verifier plus one wallet per
analyst), and signs everything itself: no node-managed accounts, so the same
code runs against anvil and against Robinhood Chain.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from eth_account import Account
from web3 import Web3
from web3.logs import DISCARD

ROOT = Path(__file__).resolve().parents[2]
USD = 10**6


def artifact(name: str) -> dict:
    return json.loads((ROOT / "out" / f"{name}.sol" / f"{name}.json").read_text())


@dataclass
class Deployed:
    usdg: str
    market: str
    desk: str = ""
    forwarder: str = ""     # Chainlink's forwarder on a public chain; a local stand-in on anvil


def workflow_name_bytes(name: str) -> bytes:
    """A CRE workflow name as the forwarder's metadata carries it: the first ten
    hex characters of its SHA-256, as bytes (Chainlink's ReceiverTemplate rule)."""
    import hashlib
    return hashlib.sha256(name.encode()).hexdigest()[:10].encode()


# The header a CRE forwarder puts in front of a workflow's report (see
# test/LocalForwarder.sol and Chainlink's MockKeystoneForwarder): version,
# execution id, timestamp, DON id, config version, workflow id, name, owner,
# report id. The receiver is handed bytes 45..109 as metadata, the rest as the report.
def raw_report(payload: bytes, workflow_id: bytes = bytes(32), name: bytes = bytes(10), owner: str = "0x" + "00" * 20,
               timestamp: int = 0) -> bytes:
    from eth_utils import keccak
    return (b"\x01" + keccak(payload) + timestamp.to_bytes(4, "big") + (0).to_bytes(4, "big") + (0).to_bytes(4, "big")
            + workflow_id + name + bytes.fromhex(owner[2:]) + b"\x00\x01" + payload)


class Chain:
    def __init__(self, rpc: str, verifier_key: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 60}))
        self.verifier = Account.from_key(verifier_key)
        self.chain_id = self.w3.eth.chain_id
        self.usdg = self.market = None

    # ---- plumbing -----------------------------------------------------------
    def send(self, acct, fn=None, *, deploy=None, value=0, gas=None, allow_revert=False):
        params = {"from": acct.address, "nonce": self.w3.eth.get_transaction_count(acct.address, "pending"),
                  "chainId": self.chain_id, "value": value}
        if gas:
            params["gas"] = gas          # a transaction meant to revert cannot be estimated
        tx = (deploy.constructor(*fn) if deploy else fn).build_transaction(params)
        signed = acct.sign_transaction(tx)
        h = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(h, timeout=120)
        if receipt.status != 1 and not allow_revert:
            raise RuntimeError(f"transaction reverted: {h.hex()}")
        return receipt

    def why(self, fn, sender) -> str | None:
        """The custom error a call would revert with, by name, or None if it succeeds."""
        try:
            fn.call({"from": sender})
            return None
        except Exception as e:  # web3 raises with the revert data attached
            data = getattr(e, "data", None) or (e.args[1] if len(e.args) > 1 else None) or str(e)
            data = data if isinstance(data, str) else str(data)
            for item in self.desk.abi + self.market.abi:
                if item.get("type") == "error":
                    sig = f"{item['name']}({','.join(i['type'] for i in item['inputs'])})"
                    if self.w3.keccak(text=sig)[:4].hex() in data.replace("0x", ""):
                        return item["name"]
            return "reverted"

    def fund(self, to: str, wei: int):
        tx = {"to": to, "value": wei, "from": self.verifier.address, "chainId": self.chain_id,
              "nonce": self.w3.eth.get_transaction_count(self.verifier.address, "pending"),
              "maxFeePerGas": self.w3.eth.gas_price * 2, "maxPriorityFeePerGas": 0}
        # Not a flat 21,000: an Arbitrum chain also charges for the data it posts to Ethereum.
        tx["gas"] = self.w3.eth.estimate_gas(tx)
        h = self.w3.eth.send_raw_transaction(self.verifier.sign_transaction(tx).raw_transaction)
        self.w3.eth.wait_for_transaction_receipt(h)

    # ---- deploy -------------------------------------------------------------
    def deploy(self, min_stake: int = 10 * USD, challenge_bond: int = 5 * USD, window: int = 3600,
               token: str | None = None, forwarder: str | None = None, owner: str | None = None,
               name: bytes = bytes(10), readers_fund: list[tuple[str, int]] | None = None) -> Deployed:
        """Deploy the market. With `token`, bond in that ERC-20 (Paxos USDG on
        Robinhood Chain testnet); without, deploy the test stand-in. Verdicts
        are accepted from `forwarder` only: Chainlink's on a public chain, a
        local stand-in laid out the same way when none is given.

        `readers_fund` is who a wrong claim's stake is paid to, as (address,
        shares) pairs fixed for the life of the market. Without one, the
        deployer's own address stands in for the fund (a test market only; the
        feed labels it so)."""
        if not forwarder:
            f = artifact("LocalForwarder")
            cf = self.w3.eth.contract(abi=f["abi"], bytecode=f["bytecode"]["object"])
            forwarder = self.send(self.verifier, (), deploy=cf).contractAddress
        b = artifact("BondedClaims")
        if token:
            usdg = Web3.to_checksum_address(token)
        else:
            a = artifact("MockUSDG")
            cu = self.w3.eth.contract(abi=a["abi"], bytecode=a["bytecode"]["object"])
            usdg = self.send(self.verifier, (), deploy=cu).contractAddress
        cm = self.w3.eth.contract(abi=b["abi"], bytecode=b["bytecode"]["object"])
        fund = readers_fund or [(self.verifier.address, 1)]
        args = (usdg, min_stake, challenge_bond, window, Web3.to_checksum_address(forwarder),
                Web3.to_checksum_address(owner or "0x" + "00" * 20), name,
                [Web3.to_checksum_address(a) for a, _ in fund], [int(n) for _, n in fund])
        r2 = self.send(self.verifier, args, deploy=cm)
        c = artifact("AgentDesk")
        cd = self.w3.eth.contract(abi=c["abi"], bytecode=c["bytecode"]["object"])
        r3 = self.send(self.verifier, (r2.contractAddress,), deploy=cd)
        return self.attach(Deployed(usdg, r2.contractAddress, r3.contractAddress, forwarder))

    def attach(self, d: Deployed) -> Deployed:
        self.usdg = self.w3.eth.contract(address=d.usdg, abi=artifact("MockUSDG")["abi"])
        # The stand-in can mint; real USDG cannot, so the verifier hands out its own.
        self.mintable = self._can_mint()
        self.market = self.w3.eth.contract(address=d.market, abi=artifact("BondedClaims")["abi"])
        self.desk = self.w3.eth.contract(address=d.desk, abi=artifact("AgentDesk")["abi"]) if d.desk else None
        # Chainlink's MockKeystoneForwarder takes report() with the same arguments as the local one.
        self.forwarder = self.w3.eth.contract(address=d.forwarder, abi=artifact("LocalForwarder")["abi"]) if d.forwarder else None
        return d

    # ---- the agent desk -------------------------------------------------------
    def act(self, acct, ticker: str, side: int, notional: int, backing: list[int], reasoning: bytes) -> dict:
        """An agent tries to open a paper position on these claims. If the desk
        would refuse, the attempt is still sent, so the refusal is a transaction
        anyone can look up; the error names the claim that was refused."""
        fn = self.desk.functions.open(ticker, side, notional, backing, reasoning)
        refusal, refused = self.why(fn, acct.address), None
        # Only the desk's own refusals name a claim: NotCleared, NotChecked,
        # WrongTicker and CitedTwice take the claim id as their one argument.
        if refusal in ("NotCleared", "NotChecked", "WrongTicker", "CitedTwice"):
            try:
                fn.call({"from": acct.address})
            except Exception as e:
                data = getattr(e, "data", None) or ""
                data = (data if isinstance(data, str) else str(data)).removeprefix("0x")
                try:
                    refused = int(data[8:8 + 64], 16) if len(data) >= 8 + 64 else None
                except ValueError:
                    refused = None
        r = self.send(acct, fn, gas=600_000 if refusal else None, allow_revert=bool(refusal))
        out = {"acted": r.status == 1, "error": refusal, "claim": refused, "tx": "0x" + r.transactionHash.hex().removeprefix("0x")}
        if r.status == 1:
            out["entry"] = self.desk.events.Opened().process_receipt(r, errors=DISCARD)[0].args.entry
        return out

    # ---- the market ---------------------------------------------------------
    def _can_mint(self) -> bool:
        try:
            self.usdg.functions.mint(self.verifier.address, 0).estimate_gas({"from": self.verifier.address})
            return True
        except Exception:
            return False

    def give(self, to: str, amount: int):
        """Put `amount` of the bond token in a wallet: minted on the stand-in,
        transferred from the verifier's faucet balance on real USDG."""
        fn = self.usdg.functions.mint(to, amount) if self.mintable else self.usdg.functions.transfer(to, amount)
        self.send(self.verifier, fn)

    def onboard(self, acct, amount: int):
        self.give(acct.address, amount)
        self.send(acct, self.usdg.functions.approve(self.market.address, 2**256 - 1))
        self.send(acct, self.market.functions.bond(amount))

    def post(self, acct, ticker: str, accession: str, words: bytes, stake: int):
        """Post a claim: its canonical words go on-chain in the event, their hash in storage."""
        r = self.send(acct, self.market.functions.post(ticker, accession, words, stake))
        ev = self.market.events.Posted().process_receipt(r, errors=DISCARD)[0]
        return ev.args.id, "0x" + r.transactionHash.hex().removeprefix("0x")

    def report(self, claim_id: int, claim_hash: bytes, fraudulent: bool, evidence: bytes, reason: str) -> str:
        """Deliver a verdict the way a CRE workflow's report arrives: through the
        forwarder, which calls the market's onReport. Used on anvil, and as the
        fallback when the CRE simulation is not run (see cre/README.md)."""
        from eth_abi import encode
        payload = encode(["uint256", "bytes32", "bool", "bytes32", "string"], [claim_id, claim_hash, fraudulent, evidence, reason])
        fn = self.forwarder.functions.report(self.market.address, raw_report(payload), b"", [])
        return "0x" + self.send(self.verifier, fn).transactionHash.hex().removeprefix("0x")

    def logs(self, event, from_block: int | None = None, span: int = 5_000_000, **filters) -> list:
        """An event's logs, queried in chunks: public RPCs cap the block range
        (Robinhood Chain testnet's at 10M blocks, about a month of blocks)."""
        latest = self.w3.eth.block_number
        start = max(0, latest - 2_000_000) if from_block is None else from_block
        out = []
        while start <= latest:
            end = min(latest, start + span - 1)
            out += event().get_logs(from_block=start, to_block=end, argument_filters=filters or None)
            start = end + 1
        return out

    def settlement(self, claim_id: int, from_block: int | None = None) -> dict:
        """How the chain settled a claim, read back from the chain itself: status,
        the verdict record, and the transaction that wrote it."""
        c = self.market.functions.claim(claim_id).call()
        v = self.market.functions.verdict(claim_id).call()
        status = ["none", "pending", "challenged", "cleared", "slashed", "void"][c[2]]
        tx = None
        for ev in (self.market.events.Cleared, self.market.events.Slashed):
            logs = self.logs(ev, from_block, id=claim_id)
            if logs:
                tx = "0x" + logs[-1].transactionHash.hex().removeprefix("0x")
        reason = None
        for ev in self.logs(self.market.events.Checked, from_block, id=claim_id):
            reason = ev.args.reason
        return {"status": status, "settled_at": v[0], "evidence": "0x" + v[1].hex(), "workflow_id": "0x" + v[2].hex(),
                "tx": tx, "reason": reason}

    def bonded(self, who: str) -> int:
        return self.market.functions.bonded(who).call()

    def reader_pool(self) -> int:
        return self.market.functions.readerPool().call()

    def readers_fund(self) -> dict:
        """Who the forfeited stakes are paid to, and how much each is owed and has taken."""
        f = self.market.functions
        payees = f.payees().call()
        return {"payees": [{"address": a, "shares": f.shares(a).call(), "due": f.readerDue(a).call() / USD,
                            "paid": f.readerReleased(a).call() / USD} for a in payees],
                "total_shares": f.totalShares().call(), "paid": f.readerPaid().call() / USD,
                "stand_in": payees == [self.verifier.address]}

    def claim_reader_share(self, acct) -> dict:
        """A payee of the readers' fund withdraws what it is owed."""
        return self.send(acct, self.market.functions.claimReaderShare())
