// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {BondedClaims, IERC20} from "../src/BondedClaims.sol";
import {MockUSDG} from "../src/MockUSDG.sol";
import {LocalForwarder} from "../test/LocalForwarder.sol";

/// Deploys the market and runs one honest and one false claim through it on a
/// real chain, so "it works on Robinhood Chain" is a transaction hash, not a claim.
/// Verdicts go through a local forwarder laid out like Chainlink's; the real
/// path is the CRE workflow in cre/ (see cre/README.md).
///
///   forge script script/GoNoGo.s.sol --rpc-url $RPC --private-key $(cat ~/.config/vouch-rh/testnet.key) --broadcast
contract GoNoGo is Script {
    uint256 constant USD = 1e6;

    function run() external {
        address me = msg.sender;
        address challenger = address(uint160(uint256(keccak256("vouch go/no-go challenger"))));
        vm.startBroadcast();
        MockUSDG usdg = new MockUSDG();
        LocalForwarder fwd = new LocalForwarder();
        // the readers' fund: the deployer stands in for it on this test market
        address[] memory fund = new address[](1);
        uint256[] memory fundShares = new uint256[](1);
        fund[0] = me;
        fundShares[0] = 1;
        BondedClaims market = new BondedClaims(
            IERC20(address(usdg)), 10 * USD, 5 * USD, 1 hours, address(fwd), address(0), bytes10(0), fund, fundShares
        );
        usdg.mint(me, 1_000 * USD);
        usdg.approve(address(market), type(uint256).max);
        market.bond(500 * USD);
        bytes memory h = bytes("Services and other revenue increased $1.54 billion, or 50%");
        bytes memory d = bytes("Services and other revenue increased $2.54 billion, or 50%");
        uint256 honest = market.post("TSLA", "0001628280-26-049270", h, 50 * USD);
        uint256 doctored = market.post("TSLA", "0001628280-26-049270", d, 100 * USD);
        fwd.report(address(market), _raw(abi.encode(honest, keccak256(h), false, bytes32(0), "ok")), "", new bytes[](0));
        fwd.report(
            address(market),
            _raw(abi.encode(doctored, keccak256(d), true, bytes32(0), "supporting quote not found in the filing")),
            "",
            new bytes[](0)
        );
        vm.stopBroadcast();

        console.log("MockUSDG     ", address(usdg));
        console.log("BondedClaims ", address(market));
        console.log("bonded after ", market.bonded(me));
        console.log("reader pool  ", market.readerPool());
        console.log("challenger   ", usdg.balanceOf(challenger));
    }

    function _raw(bytes memory payload) internal view returns (bytes memory) {
        return abi.encodePacked(
            uint8(1),
            keccak256(payload),
            uint32(block.timestamp),
            uint32(0),
            uint32(0),
            bytes32(0),
            bytes10(0),
            address(0),
            bytes2(0),
            payload
        );
    }
}
