// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {BondedClaims, IERC20, IReceiver, IERC165} from "../src/BondedClaims.sol";
import {MockUSDG} from "../src/MockUSDG.sol";
import {Reports} from "./Reports.sol";

contract BondedClaimsTest is Reports {
    MockUSDG usdg;
    BondedClaims market;
    address honest = makeAddr("honest");
    address liar = makeAddr("liar");
    address watcher = makeAddr("watcher");
    uint256 constant USD = 1e6;
    string constant FILING = "0001628280-26-049270";
    bytes constant CLAIM = bytes('{"ticker":"TSLA","value":"$1.54 billion"}');

    function setUp() public {
        usdg = new MockUSDG();
        (address[] memory p, uint256[] memory sh) = _fund();
        market = new BondedClaims(IERC20(address(usdg)), 10 * USD, 5 * USD, 1 hours, address(fwd), OWNER, NAME, p, sh);
        for (uint256 i; i < 2; i++) {
            address a = i == 0 ? honest : liar;
            usdg.mint(a, 1_000 * USD);
            vm.startPrank(a);
            usdg.approve(address(market), type(uint256).max);
            market.bond(500 * USD);
            vm.stopPrank();
        }
    }

    function _post(address who, uint256 stake) internal returns (uint256) {
        vm.prank(who);
        return market.post("TSLA", FILING, CLAIM, stake);
    }

    function test_the_chain_holds_the_hash_of_exactly_the_posted_words() public {
        vm.expectEmit(true, true, false, true);
        emit BondedClaims.Posted(0, honest, "TSLA", FILING, keccak256(CLAIM), 50 * USD, CLAIM);
        uint256 id = _post(honest, 50 * USD);
        assertEq(market.claim(id).claimHash, keccak256(CLAIM));
    }

    function test_a_claim_locks_its_stake_until_it_is_judged() public {
        uint256 id = _post(honest, 50 * USD);
        assertEq(market.locked(honest), 50 * USD);
        assertEq(market.freeBond(honest), 450 * USD);
        vm.prank(honest);
        vm.expectRevert(BondedClaims.NotEnoughFreeBond.selector);
        market.withdraw(451 * USD); // cannot pull out money that is behind a live claim
        _verdict(market, id, false, "quote verified and value grounded");
        assertEq(market.locked(honest), 0);
        assertEq(market.cleared(honest), 1);
    }

    function test_a_false_claim_loses_its_stake_to_the_reader_pool() public {
        uint256 id = _post(liar, 100 * USD);
        _verdict(market, id, true, "supporting quote not found in source document");
        assertEq(market.bonded(liar), 400 * USD, "stake at risk is gone");
        assertEq(market.readerPool(), 100 * USD, "nobody challenged: all of it backs readers");
        assertEq(market.slashedCount(liar), 1);
        assertEq(uint8(market.claim(id).status), uint8(BondedClaims.Status.Slashed));
    }

    function test_the_verdict_records_which_workflow_and_which_filing() public {
        uint256 id = _post(honest, 50 * USD);
        vm.warp(block.timestamp + 30);
        _verdict(market, id, false, "quote verified and value grounded");
        BondedClaims.Verdict memory v = market.verdict(id);
        assertEq(v.workflowId, WORKFLOW_ID);
        assertEq(v.evidence, FILING_HASH);
        assertEq(v.settledAt, block.timestamp);
    }

    function test_money_is_conserved() public {
        uint256 a = _post(liar, 100 * USD);
        uint256 b = _post(honest, 30 * USD);
        _verdict(market, a, true, "value not grounded in the quote");
        _verdict(market, b, false, "quote verified");
        vm.prank(honest);
        market.withdraw(500 * USD);
        uint256 held = usdg.balanceOf(address(market));
        assertEq(held, market.bonded(liar) + market.bonded(honest) + market.readerPool() - market.readerPaid());
    }

    // ---- who may settle: no key, only the workflow through the forwarder -----

    function test_nobody_but_the_forwarder_can_deliver_a_verdict() public {
        uint256 id = _post(liar, 20 * USD);
        bytes memory meta = abi.encodePacked(WORKFLOW_ID, NAME, OWNER, bytes2(0x0001));
        bytes memory report = _payload(market, id, false, "self-serving");
        vm.prank(liar);
        vm.expectRevert(abi.encodeWithSelector(BondedClaims.NotForwarder.selector, liar));
        market.onReport(meta, report);
        // not even the deployer: there is no verifier key
        vm.expectRevert(abi.encodeWithSelector(BondedClaims.NotForwarder.selector, address(this)));
        market.onReport(meta, report);
    }

    function test_a_report_from_another_workflow_owner_is_refused() public {
        uint256 id = _post(liar, 20 * USD);
        bytes memory raw = _raw(WORKFLOW_ID, NAME, address(0xBAD), _payload(market, id, false, "forged"));
        vm.expectRevert(BondedClaims.WrongWorkflow.selector);
        fwd.report(address(market), raw, "", new bytes[](0));
    }

    function test_a_report_from_another_workflow_name_is_refused() public {
        uint256 id = _post(liar, 20 * USD);
        // forge-lint: disable-next-line(unsafe-typecast)
        bytes memory raw = _raw(WORKFLOW_ID, bytes10("ffffffffff"), OWNER, _payload(market, id, false, "forged"));
        vm.expectRevert(BondedClaims.WrongWorkflow.selector);
        fwd.report(address(market), raw, "", new bytes[](0));
    }

    function test_once_pinned_only_that_compiled_workflow_counts() public {
        market.pinWorkflow(WORKFLOW_ID);
        vm.expectRevert(BondedClaims.AlreadyPinned.selector);
        market.pinWorkflow(keccak256("a different build"));
        uint256 id = _post(liar, 20 * USD);
        bytes memory raw = _raw(keccak256("a different build"), NAME, OWNER, _payload(market, id, false, "forged"));
        vm.expectRevert(BondedClaims.WrongWorkflow.selector);
        fwd.report(address(market), raw, "", new bytes[](0));
        _verdict(market, id, true, "figures differ from the filing"); // the pinned build still settles
        assertEq(uint8(market.claim(id).status), uint8(BondedClaims.Status.Slashed));
    }

    function test_only_the_deployer_pins_and_only_once() public {
        vm.prank(liar);
        vm.expectRevert(BondedClaims.WrongWorkflow.selector);
        market.pinWorkflow(WORKFLOW_ID);
    }

    function test_a_verdict_must_be_about_the_words_that_were_posted() public {
        uint256 id = _post(liar, 20 * USD);
        bytes memory payload = abi.encode(id, keccak256("other words"), false, FILING_HASH, "checked something else");
        vm.expectRevert(BondedClaims.WrongClaim.selector);
        fwd.report(address(market), _raw(WORKFLOW_ID, NAME, OWNER, payload), "", new bytes[](0));
    }

    function test_a_claim_is_judged_once() public {
        uint256 id = _post(liar, 20 * USD);
        _verdict(market, id, true, "fabricated");
        vm.expectEmit(true, false, false, true);
        emit BondedClaims.ReportIgnored(id, BondedClaims.Status.Slashed);
        _verdict(market, id, false, "a second opinion changes nothing");
        assertEq(market.bonded(liar), 480 * USD);
    }

    function test_a_slow_network_cannot_turn_a_wrong_claim_into_a_cleared_one() public {
        uint256 id = _post(liar, 20 * USD);
        vm.warp(block.timestamp + 1 hours + 1);
        _verdict(market, id, true, "arrived after the window");
        assertEq(uint8(market.claim(id).status), uint8(BondedClaims.Status.Slashed));
        assertEq(market.bonded(liar), 480 * USD);
    }

    function test_a_claim_that_cleared_by_default_is_marked_unchecked() public {
        uint256 id = _post(liar, 20 * USD);
        vm.warp(block.timestamp + 1 hours + 1);
        market.finalize(id);
        assertEq(market.verdict(id).evidence, bytes32(0), "no filing was checked");
        _verdict(market, id, true, "too late: already settled");
        assertEq(uint8(market.claim(id).status), uint8(BondedClaims.Status.Cleared));
    }

    function test_a_claim_cleared_by_default_counts_as_unchecked_not_cleared() public {
        uint256 id = _post(liar, 20 * USD);
        vm.warp(block.timestamp + 1 hours + 1);
        market.finalize(id);
        assertEq(market.cleared(liar), 0, "no verdict, so not on the record as true");
        assertEq(market.clearedUnchecked(liar), 1, "but not hidden either");
    }

    function test_a_claim_the_workflow_cleared_counts_as_checked() public {
        uint256 id = _post(honest, 20 * USD);
        _verdict(market, id, false, "quote verified and value grounded");
        address c = _challenger();
        uint256 disputed = _post(honest, 20 * USD);
        vm.prank(c);
        market.challenge(disputed);
        _verdict(market, disputed, false, "quote verified"); // the upheld path counts too
        assertEq(market.cleared(honest), 2);
        assertEq(market.clearedUnchecked(honest), 0);
    }

    function test_challenging_your_own_wrong_claim_gains_nothing() public {
        address sock = makeAddr("sock puppet");
        usdg.mint(sock, 100 * USD);
        vm.prank(sock);
        usdg.approve(address(market), type(uint256).max);
        uint256 id = _post(liar, 100 * USD);
        vm.prank(sock);
        market.challenge(id);
        _verdict(market, id, true, "figures differ from the filing");
        assertEq(market.bonded(liar), 400 * USD, "the whole stake is lost");
        assertEq(usdg.balanceOf(sock), 100 * USD, "the puppet only gets its deposit back");
        assertEq(market.readerPool(), 100 * USD);
    }

    function test_simulation_market_checks_only_the_forwarder() public {
        (address[] memory p, uint256[] memory sh) = _fund();
        BondedClaims sim = new BondedClaims(
            IERC20(address(usdg)), 10 * USD, 5 * USD, 1 hours, address(fwd), address(0), bytes10(0), p, sh
        );
        vm.startPrank(honest);
        usdg.approve(address(sim), type(uint256).max);
        sim.bond(100 * USD);
        uint256 id = sim.post("TSLA", FILING, CLAIM, 20 * USD);
        vm.stopPrank();
        // Chainlink's mock forwarder fills no identity; the simulation market accepts it
        fwd.report(
            address(sim), _raw(bytes32(0), bytes10(0), address(0), _payload(sim, id, false, "ok")), "", new bytes[](0)
        );
        assertTrue(sim.isCleared(id));
        vm.expectRevert(BondedClaims.WrongWorkflow.selector);
        sim.pinWorkflow(WORKFLOW_ID); // and cannot pretend to be pinned
    }

    function test_it_says_it_takes_reports() public view {
        assertTrue(market.supportsInterface(type(IReceiver).interfaceId));
        assertTrue(market.supportsInterface(type(IERC165).interfaceId));
        assertFalse(market.supportsInterface(0xffffffff));
    }

    function test_a_claim_must_carry_real_stake() public {
        vm.prank(honest);
        vm.expectRevert(BondedClaims.StakeTooSmall.selector);
        market.post("TSLA", FILING, CLAIM, 1 * USD);
    }

    function test_you_cannot_stake_more_than_you_bonded() public {
        _post(honest, 400 * USD);
        vm.prank(honest);
        vm.expectRevert(BondedClaims.NotEnoughFreeBond.selector);
        market.post("TSLA", FILING, CLAIM, 200 * USD);
    }

    // ---- what fits in one Posted log ------------------------------------------

    function _words(uint256 n) internal pure returns (bytes memory w) {
        w = new bytes(n);
        for (uint256 i; i < n; i++) {
            w[i] = "a";
        }
    }

    function test_a_claim_of_exactly_the_longest_allowed_words_posts() public {
        bytes memory words = _words(market.MAX_WORDS());
        vm.prank(honest);
        uint256 id = market.post("TSLA", FILING, words, 20 * USD);
        assertEq(market.claim(id).claimHash, keccak256(words));
    }

    function test_one_byte_more_than_the_longest_allowed_words_is_refused() public {
        bytes memory words = _words(market.MAX_WORDS() + 1);
        vm.prank(honest);
        vm.expectRevert(BondedClaims.ClaimTooLong.selector);
        market.post("TSLA", FILING, words, 20 * USD);
    }

    function test_a_ticker_too_long_for_the_log_is_refused() public {
        vm.prank(honest);
        market.post("ABCDEFGHIJKLMNOP", FILING, CLAIM, 20 * USD); // 16 bytes is fine
        vm.prank(honest);
        vm.expectRevert(BondedClaims.TickerTooLong.selector);
        market.post("ABCDEFGHIJKLMNOPQ", FILING, CLAIM, 20 * USD);
    }

    function test_a_filing_too_long_for_the_log_is_refused() public {
        vm.prank(honest);
        market.post("TSLA", "0001628280-26-049270-0123456789a", CLAIM, 20 * USD); // 32 bytes is fine
        vm.prank(honest);
        vm.expectRevert(BondedClaims.FilingTooLong.selector);
        market.post("TSLA", "0001628280-26-049270-0123456789ab", CLAIM, 20 * USD);
    }

    function test_a_claim_with_no_words_is_refused() public {
        vm.prank(honest);
        vm.expectRevert(BondedClaims.EmptyClaim.selector);
        market.post("TSLA", FILING, "", 20 * USD);
    }

    function testFuzz_slashing_never_touches_other_analysts(uint96 stake) public {
        stake = uint96(bound(stake, 10 * USD, 500 * USD));
        uint256 id = _post(liar, stake);
        _verdict(market, id, true, "fuzz");
        assertEq(market.bonded(honest), 500 * USD);
        assertEq(market.freeBond(honest), 500 * USD);
    }

    // ---- open challenges ----------------------------------------------------

    function _challenger() internal returns (address c) {
        c = makeAddr("challenger");
        usdg.mint(c, 100 * USD);
        vm.prank(c);
        usdg.approve(address(market), type(uint256).max);
    }

    function test_an_unchallenged_claim_clears_itself_after_the_window() public {
        uint256 id = _post(honest, 50 * USD);
        vm.expectRevert(BondedClaims.WindowOpen.selector);
        market.finalize(id);
        vm.warp(block.timestamp + 1 hours + 1);
        vm.prank(watcher); // anyone can finalise
        market.finalize(id);
        assertEq(uint8(market.claim(id).status), uint8(BondedClaims.Status.Cleared));
        assertEq(market.locked(honest), 0);
        assertEq(market.verdict(id).workflowId, bytes32(0), "cleared by default, not by the check");
    }

    function test_a_won_challenge_returns_the_deposit_and_the_stake_backs_readers() public {
        address c = _challenger();
        uint256 id = _post(liar, 100 * USD);
        vm.prank(c);
        market.challenge(id);
        assertEq(usdg.balanceOf(c), 95 * USD);
        _verdict(market, id, true, "figures differ from the filing");
        assertEq(usdg.balanceOf(c), 100 * USD, "deposit back");
        assertEq(market.bonded(liar), 400 * USD);
        assertEq(market.readerPool(), 100 * USD);
    }

    function test_a_lost_challenge_pays_the_analyst() public {
        address c = _challenger();
        uint256 id = _post(honest, 50 * USD);
        vm.prank(c);
        market.challenge(id);
        _verdict(market, id, false, "quote verified");
        assertEq(market.bonded(honest), 505 * USD, "the analyst keeps the stake and takes the deposit");
        assertEq(usdg.balanceOf(c), 95 * USD);
        assertEq(uint8(market.claim(id).status), uint8(BondedClaims.Status.Cleared));
    }

    function test_you_cannot_challenge_after_the_window() public {
        address c = _challenger();
        uint256 id = _post(liar, 20 * USD);
        vm.warp(block.timestamp + 1 hours + 1);
        vm.prank(c);
        vm.expectRevert(BondedClaims.WindowClosed.selector);
        market.challenge(id);
    }

    function test_a_challenged_claim_cannot_be_finalised_around_the_dispute() public {
        address c = _challenger();
        uint256 id = _post(liar, 20 * USD);
        vm.prank(c);
        market.challenge(id);
        vm.warp(block.timestamp + 2 hours);
        vm.expectRevert(BondedClaims.NotPending.selector);
        market.finalize(id);
    }

    function test_a_challenge_no_verdict_answers_unwinds_and_refunds_both() public {
        address c = _challenger();
        uint256 id = _post(liar, 20 * USD);
        vm.prank(c);
        market.challenge(id);
        vm.expectRevert(BondedClaims.WindowOpen.selector);
        market.unwind(id);
        vm.warp(block.timestamp + 7 days + 1);
        vm.prank(watcher);
        market.unwind(id);
        assertEq(usdg.balanceOf(c), 100 * USD, "deposit back");
        assertEq(market.freeBond(liar), 500 * USD, "stake unlocked");
        assertFalse(market.isCleared(id), "an unanswered claim never counts as cleared");
        _verdict(market, id, true, "too late now"); // ignored, not reverted
        assertEq(market.bonded(liar), 500 * USD);
    }

    function testFuzz_money_is_conserved_through_disputes(uint96 stake, bool fraudulent) public {
        stake = uint96(bound(stake, 10 * USD, 500 * USD));
        address c = _challenger();
        uint256 before = usdg.balanceOf(address(market)) + usdg.balanceOf(c);
        uint256 id = _post(liar, stake);
        vm.prank(c);
        market.challenge(id);
        _verdict(market, id, fraudulent, "fuzz");
        uint256 held = usdg.balanceOf(address(market));
        assertEq(held, market.bonded(liar) + market.bonded(honest) + market.readerPool() - market.readerPaid());
        assertEq(held + usdg.balanceOf(c), before);
    }
}
