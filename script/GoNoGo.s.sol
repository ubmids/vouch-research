// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {BondedClaims, IERC20} from "../src/BondedClaims.sol";
import {MockUSDG} from "../src/MockUSDG.sol";

/// Deploys the market and runs one honest and one false claim through it on a
/// real chain, so "it works on Robinhood Chain" is a transaction hash, not a claim.
///
///   forge script script/GoNoGo.s.sol --rpc-url $RPC --private-key $(cat ~/.config/vouch-rh/testnet.key) --broadcast
contract GoNoGo is Script {
    uint256 constant USD = 1e6;

    function run() external {
        address me = msg.sender;
        address challenger = address(uint160(uint256(keccak256("vouch go/no-go challenger"))));
        vm.startBroadcast();
        MockUSDG usdg = new MockUSDG();
        BondedClaims market = new BondedClaims(IERC20(address(usdg)), 10 * USD, 5 * USD, 1 hours);
        usdg.mint(me, 1_000 * USD);
        usdg.approve(address(market), type(uint256).max);
        market.bond(500 * USD);
        uint256 honest = market.post("TSLA", "0001628280-26-049270",
            keccak256("Services and other revenue increased $1.54 billion, or 50%"), 50 * USD);
        uint256 doctored = market.post("TSLA", "0001628280-26-049270",
            keccak256("Services and other revenue increased $2.54 billion, or 50%"), 100 * USD);
        market.clear(honest);
        market.slash(doctored, challenger, "supporting quote not found in the filing");
        vm.stopBroadcast();

        console.log("MockUSDG     ", address(usdg));
        console.log("BondedClaims ", address(market));
        console.log("bonded after ", market.bonded(me));
        console.log("reader pool  ", market.readerPool());
        console.log("challenger   ", usdg.balanceOf(challenger));
    }
}
