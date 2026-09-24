// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {BondedClaims, IERC20} from "../src/BondedClaims.sol";
import {AgentDesk} from "../src/AgentDesk.sol";
import {MockUSDG} from "../src/MockUSDG.sol";

contract AgentDeskTest is Test {
    MockUSDG usdg;
    BondedClaims vouch;
    AgentDesk desk;
    address analyst = makeAddr("analyst");
    address agent = makeAddr("agent");
    uint256 constant USD = 1e6;
    uint256 good;
    uint256 bad;
    uint256 open_;
    uint256 other;

    function setUp() public {
        usdg = new MockUSDG();
        vouch = new BondedClaims(IERC20(address(usdg)), 10 * USD, 5 * USD, 1 hours);
        desk = new AgentDesk(vouch);
        usdg.mint(analyst, 1_000 * USD);
        usdg.mint(agent, 1_000 * USD);
        vm.startPrank(analyst);
        usdg.approve(address(vouch), type(uint256).max);
        vouch.bond(500 * USD);
        good = vouch.post("TSLA", "0001628280-26-049270", keccak256("true"), 25 * USD);
        bad = vouch.post("TSLA", "0001628280-26-049270", keccak256("doctored"), 25 * USD);
        open_ = vouch.post("TSLA", "0001628280-26-049270", keccak256("pending"), 25 * USD);
        other = vouch.post("AMD", "0000002488-26-000123", keccak256("amd"), 25 * USD);
        vm.stopPrank();
        vouch.clear(good);
        vouch.slash(bad, address(this), "figures differ from the filing");
        vouch.clear(other);
        vm.prank(agent);
        usdg.approve(address(desk), type(uint256).max);
    }

    function _ids(uint256 a) internal pure returns (uint256[] memory x) { x = new uint256[](1); x[0] = a; }

    function test_an_agent_acts_on_cleared_research() public {
        vm.prank(agent);
        desk.open("TSLA", 100 * USD, _ids(good));
        assertEq(desk.position(agent, keccak256("TSLA")), 100 * USD);
        assertEq(usdg.balanceOf(address(desk)), 100 * USD);
    }

    function test_a_slashed_claim_cannot_back_a_trade() public {
        vm.prank(agent);
        vm.expectRevert(abi.encodeWithSelector(AgentDesk.NotCleared.selector, bad));
        desk.open("TSLA", 100 * USD, _ids(bad));
    }

    function test_a_claim_still_in_its_window_cannot_back_a_trade() public {
        vm.prank(agent);
        vm.expectRevert(abi.encodeWithSelector(AgentDesk.NotCleared.selector, open_));
        desk.open("TSLA", 100 * USD, _ids(open_));
        vm.warp(block.timestamp + 1 hours + 1);
        vouch.finalize(open_);                       // unchallenged: now it counts
        vm.prank(agent);
        desk.open("TSLA", 100 * USD, _ids(open_));
    }

    function test_research_about_another_stock_does_not_count() public {
        vm.prank(agent);
        vm.expectRevert(abi.encodeWithSelector(AgentDesk.WrongTicker.selector, other));
        desk.open("TSLA", 100 * USD, _ids(other));
    }

    function test_every_cited_claim_must_hold() public {
        uint256[] memory both = new uint256[](2);
        both[0] = good; both[1] = bad;
        vm.prank(agent);
        vm.expectRevert(abi.encodeWithSelector(AgentDesk.NotCleared.selector, bad));
        desk.open("TSLA", 100 * USD, both);
    }

    function test_no_research_no_trade() public {
        vm.prank(agent);
        vm.expectRevert(AgentDesk.NoBacking.selector);
        desk.open("TSLA", 100 * USD, new uint256[](0));
    }

    function test_close_returns_the_notional() public {
        vm.startPrank(agent);
        desk.open("TSLA", 100 * USD, _ids(good));
        desk.close("TSLA");
        vm.stopPrank();
        assertEq(usdg.balanceOf(agent), 1_000 * USD);
    }
}
