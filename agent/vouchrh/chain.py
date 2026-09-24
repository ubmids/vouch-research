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

ROOT = Path(__file__).resolve().parents[2]
USD = 10**6


def artifact(name: str) -> dict:
    return json.loads((ROOT / "out" / f"{name}.sol" / f"{name}.json").read_text())


@dataclass
class Deployed:
    usdg: str
    market: str
    desk: str = ""


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
               token: str | None = None) -> Deployed:
        """Deploy the market. With `token`, bond in that ERC-20 (Paxos USDG on
        Robinhood Chain testnet); without, deploy the test stand-in."""
        b = artifact("BondedClaims")
        if token:
            usdg = Web3.to_checksum_address(token)
        else:
            a = artifact("MockUSDG")
            cu = self.w3.eth.contract(abi=a["abi"], bytecode=a["bytecode"]["object"])
            usdg = self.send(self.verifier, (), deploy=cu).contractAddress
        cm = self.w3.eth.contract(abi=b["abi"], bytecode=b["bytecode"]["object"])
        r2 = self.send(self.verifier, (usdg, min_stake, challenge_bond, window), deploy=cm)
        c = artifact("AgentDesk")
        cd = self.w3.eth.contract(abi=c["abi"], bytecode=c["bytecode"]["object"])
        r3 = self.send(self.verifier, (r2.contractAddress,), deploy=cd)
        return self.attach(Deployed(usdg, r2.contractAddress, r3.contractAddress))

    def attach(self, d: Deployed) -> Deployed:
        self.usdg = self.w3.eth.contract(address=d.usdg, abi=artifact("MockUSDG")["abi"])
        # The stand-in can mint; real USDG cannot, so the verifier hands out its own.
        self.mintable = self._can_mint()
        self.market = self.w3.eth.contract(address=d.market, abi=artifact("BondedClaims")["abi"])
        self.desk = self.w3.eth.contract(address=d.desk, abi=artifact("AgentDesk")["abi"]) if d.desk else None
        return d

    # ---- the agent desk -------------------------------------------------------
    def act(self, acct, ticker: str, notional: int, backing: list[int]) -> dict:
        """An agent tries to trade on these claims. If the desk would refuse, the
        attempt is still sent, so the refusal is a transaction anyone can look up."""
        fn = self.desk.functions.open(ticker, notional, backing)
        refusal = self.why(fn, acct.address)
        r = self.send(acct, fn, gas=300_000 if refusal else None, allow_revert=bool(refusal))
        return {"acted": r.status == 1, "error": refusal, "tx": r.transactionHash.hex()}

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

    def post(self, acct, ticker: str, accession: str, digest: bytes, stake: int):
        r = self.send(acct, self.market.functions.post(ticker, accession, digest, stake))
        ev = self.market.events.Posted().process_receipt(r)[0]
        return ev.args.id, r.transactionHash.hex()

    def clear(self, claim_id: int) -> str:
        return self.send(self.verifier, self.market.functions.clear(claim_id)).transactionHash.hex()

    def slash(self, claim_id: int, challenger: str, reason: str) -> str:
        return self.send(self.verifier, self.market.functions.slash(claim_id, challenger, reason)).transactionHash.hex()

    def bonded(self, who: str) -> int:
        return self.market.functions.bonded(who).call()

    def reader_pool(self) -> int:
        return self.market.functions.readerPool().call()
