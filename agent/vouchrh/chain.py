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


class Chain:
    def __init__(self, rpc: str, verifier_key: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 60}))
        self.verifier = Account.from_key(verifier_key)
        self.chain_id = self.w3.eth.chain_id
        self.usdg = self.market = None

    # ---- plumbing -----------------------------------------------------------
    def send(self, acct, fn=None, *, deploy=None, value=0):
        tx = (deploy.constructor(*fn) if deploy else fn).build_transaction({
            "from": acct.address, "nonce": self.w3.eth.get_transaction_count(acct.address, "pending"),
            "chainId": self.chain_id, "value": value,
        })
        signed = acct.sign_transaction(tx)
        h = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(h, timeout=120)
        if receipt.status != 1:
            raise RuntimeError(f"transaction reverted: {h.hex()}")
        return receipt

    def fund(self, to: str, wei: int):
        tx = {"to": to, "value": wei, "from": self.verifier.address, "chainId": self.chain_id, "gas": 21000,
              "nonce": self.w3.eth.get_transaction_count(self.verifier.address, "pending"),
              "maxFeePerGas": self.w3.eth.gas_price * 2, "maxPriorityFeePerGas": 0}
        h = self.w3.eth.send_raw_transaction(self.verifier.sign_transaction(tx).raw_transaction)
        self.w3.eth.wait_for_transaction_receipt(h)

    # ---- deploy -------------------------------------------------------------
    def deploy(self, min_stake: int = 10 * USD, challenge_bond: int = 5 * USD, window: int = 3600) -> Deployed:
        a, b = artifact("MockUSDG"), artifact("BondedClaims")
        cu = self.w3.eth.contract(abi=a["abi"], bytecode=a["bytecode"]["object"])
        r1 = self.send(self.verifier, (), deploy=cu)
        cm = self.w3.eth.contract(abi=b["abi"], bytecode=b["bytecode"]["object"])
        r2 = self.send(self.verifier, (r1.contractAddress, min_stake, challenge_bond, window), deploy=cm)
        return self.attach(Deployed(r1.contractAddress, r2.contractAddress))

    def attach(self, d: Deployed) -> Deployed:
        self.usdg = self.w3.eth.contract(address=d.usdg, abi=artifact("MockUSDG")["abi"])
        self.market = self.w3.eth.contract(address=d.market, abi=artifact("BondedClaims")["abi"])
        return d

    # ---- the market ---------------------------------------------------------
    def onboard(self, acct, amount: int):
        self.send(self.verifier, self.usdg.functions.mint(acct.address, amount))
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
