// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {BondedClaims, IERC20} from "../src/BondedClaims.sol";
import {AgentDesk} from "../src/AgentDesk.sol";
import {MockUSDG} from "../src/MockUSDG.sol";
import {Reports} from "./Reports.sol";

contract AgentDeskTest is Reports {
    MockUSDG usdg;
    BondedClaims vouch;
    AgentDesk desk;
    address analyst = makeAddr("analyst");
    address agent = makeAddr("agent");
    uint256 constant USD = 1e6;
    bytes32 constant WHY = keccak256('{"policy":"vouch-desk-policy/1","side":"long"}');
    uint256 good;
    uint256 good2;
    uint256 bad;
    uint256 open_;
    uint256 other;

    function setUp() public {
        usdg = new MockUSDG();
        vouch = new BondedClaims(IERC20(address(usdg)), 10 * USD, 5 * USD, 1 hours, address(fwd), OWNER, NAME);
        desk = new AgentDesk(vouch);
        usdg.mint(analyst, 1_000 * USD);
        vm.startPrank(analyst);
        usdg.approve(address(vouch), type(uint256).max);
        vouch.bond(500 * USD);
        good = vouch.post("TSLA", "0001628280-26-049270", bytes("true"), 25 * USD);
        bad = vouch.post("TSLA", "0001628280-26-049270", bytes("doctored"), 25 * USD);
        open_ = vouch.post("TSLA", "0001628280-26-049270", bytes("pending"), 25 * USD);
        other = vouch.post("AMD", "0000002488-26-000123", bytes("amd"), 25 * USD);
        good2 = vouch.post("TSLA", "0001628280-26-049270", bytes("also true"), 25 * USD);
        vm.stopPrank();
        _verdict(vouch, good, false, "quote verified and value grounded");
        _verdict(vouch, bad, true, "figures differ from the filing");
        _verdict(vouch, other, false, "quote verified and value grounded");
        _verdict(vouch, good2, false, "quote verified and value grounded");
    }

    function _ids(uint256 a) internal pure returns (uint256[] memory x) {
        x = new uint256[](1);
        x[0] = a;
    }

    function _two(uint256 a, uint256 b) internal pure returns (uint256[] memory x) {
        x = new uint256[](2);
        x[0] = a;
        x[1] = b;
    }

    function test_an_agent_acts_on_cleared_research_and_the_journal_keeps_why() public {
        vm.prank(agent);
        uint256 e = desk.open("TSLA", AgentDesk.Side.Long, 200 * USD, _two(good, good2), WHY);
        AgentDesk.Entry memory j = desk.journal(e);
        assertEq(j.agent, agent);
        assertEq(uint8(j.side), uint8(AgentDesk.Side.Long));
        assertEq(j.notional, 200 * USD);
        assertEq(j.reasoning, WHY);
        assertEq(j.backing.length, 2);
        assertEq(desk.journalLength(), 1);
    }

    function test_each_citation_carries_the_words_hash_and_the_verdict_behind_it() public {
        vm.prank(agent);
        uint256 e = desk.open("TSLA", AgentDesk.Side.Short, 100 * USD, _two(good, good2), WHY);
        AgentDesk.Citation[] memory c = desk.citations(e);
        assertEq(c[0].claimId, good);
        assertEq(c[0].claimHash, keccak256("true"));
        assertEq(c[0].workflowId, WORKFLOW_ID, "cleared by the CRE workflow");
        assertEq(c[0].evidence, FILING_HASH, "against these filing bytes");
        assertEq(c[1].claimHash, keccak256("also true"));
        assertGt(c[1].settledAt, 0);
    }

    function test_the_opened_event_is_the_whole_trail_in_one_log() public {
        AgentDesk.Citation[] memory want = new AgentDesk.Citation[](1);
        want[0] = AgentDesk.Citation(good, keccak256("true"), uint64(block.timestamp), FILING_HASH, WORKFLOW_ID);
        vm.expectEmit(true, true, false, true);
        emit AgentDesk.Opened(0, agent, "TSLA", AgentDesk.Side.Long, 100 * USD, WHY, want);
        vm.prank(agent);
        desk.open("TSLA", AgentDesk.Side.Long, 100 * USD, _ids(good), WHY);
    }

    function test_a_slashed_claim_cannot_back_a_trade() public {
        vm.prank(agent);
        vm.expectRevert(abi.encodeWithSelector(AgentDesk.NotCleared.selector, bad));
        desk.open("TSLA", AgentDesk.Side.Long, 100 * USD, _ids(bad), WHY);
    }

    function test_a_claim_still_in_its_window_cannot_back_a_trade() public {
        vm.prank(agent);
        vm.expectRevert(abi.encodeWithSelector(AgentDesk.NotCleared.selector, open_));
        desk.open("TSLA", AgentDesk.Side.Long, 100 * USD, _ids(open_), WHY);
    }

    function test_a_claim_that_only_cleared_by_default_cannot_back_a_trade() public {
        vm.warp(block.timestamp + 1 hours + 1);
        vouch.finalize(open_); // nobody's verdict came: cleared, but nothing was checked
        assertTrue(vouch.isCleared(open_));
        vm.prank(agent);
        vm.expectRevert(abi.encodeWithSelector(AgentDesk.NotChecked.selector, open_));
        desk.open("TSLA", AgentDesk.Side.Long, 100 * USD, _ids(open_), WHY);
    }

    function test_the_same_words_under_two_ids_count_once() public {
        vm.prank(analyst);
        uint256 copy = vouch.post("TSLA", "0001628280-26-049270", bytes("true"), 25 * USD);
        _verdict(vouch, copy, false, "quote verified and value grounded");
        vm.prank(agent);
        vm.expectRevert(abi.encodeWithSelector(AgentDesk.CitedTwice.selector, copy));
        desk.open("TSLA", AgentDesk.Side.Long, 200 * USD, _two(good, copy), WHY);
    }

    function test_research_about_another_stock_does_not_count() public {
        vm.prank(agent);
        vm.expectRevert(abi.encodeWithSelector(AgentDesk.WrongTicker.selector, other));
        desk.open("TSLA", AgentDesk.Side.Long, 100 * USD, _ids(other), WHY);
    }

    function test_every_cited_claim_must_hold() public {
        vm.prank(agent);
        vm.expectRevert(abi.encodeWithSelector(AgentDesk.NotCleared.selector, bad));
        desk.open("TSLA", AgentDesk.Side.Long, 100 * USD, _two(good, bad), WHY);
    }

    function test_one_claim_cannot_be_cited_twice_to_look_like_more_evidence() public {
        vm.prank(agent);
        vm.expectRevert(abi.encodeWithSelector(AgentDesk.CitedTwice.selector, good));
        desk.open("TSLA", AgentDesk.Side.Long, 100 * USD, _two(good, good), WHY);
    }

    function test_no_research_no_trade() public {
        vm.prank(agent);
        vm.expectRevert(AgentDesk.NoBacking.selector);
        desk.open("TSLA", AgentDesk.Side.Long, 100 * USD, new uint256[](0), WHY);
    }

    function test_no_reasoning_no_trade() public {
        vm.prank(agent);
        vm.expectRevert(AgentDesk.NoReasoning.selector);
        desk.open("TSLA", AgentDesk.Side.Long, 100 * USD, _ids(good), bytes32(0));
    }

    function test_close_records_when_and_why_and_only_for_its_agent() public {
        vm.prank(agent);
        uint256 e = desk.open("TSLA", AgentDesk.Side.Long, 100 * USD, _ids(good), WHY);
        vm.prank(analyst);
        vm.expectRevert(AgentDesk.NotYours.selector);
        desk.close(e, keccak256("not mine"));
        vm.warp(block.timestamp + 1 days);
        vm.prank(agent);
        desk.close(e, keccak256("exit: thesis played out"));
        AgentDesk.Entry memory j = desk.journal(e);
        assertEq(j.closedAt, block.timestamp);
        assertEq(j.exitReasoning, keccak256("exit: thesis played out"));
        vm.prank(agent);
        vm.expectRevert(AgentDesk.AlreadyClosed.selector);
        desk.close(e, keccak256("again"));
    }

    function test_no_money_moves_it_is_a_paper_desk() public {
        vm.prank(agent);
        desk.open("TSLA", AgentDesk.Side.Long, 1_000_000 * USD, _ids(good), WHY);
        assertEq(usdg.balanceOf(address(desk)), 0);
    }
}
