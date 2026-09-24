// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {BondedClaims, IERC20} from "../src/BondedClaims.sol";
import {MockUSDG} from "../src/MockUSDG.sol";

contract BondedClaimsTest is Test {
    MockUSDG usdg;
    BondedClaims market;
    address verifier = address(this);
    address honest = makeAddr("honest");
    address liar = makeAddr("liar");
    address watcher = makeAddr("watcher");
    uint256 constant USD = 1e6;
    string constant FILING = "0001628280-26-049270";
    bytes32 constant H = keccak256("TSLA services revenue +$1.54 billion, Q2 2026");

    function setUp() public {
        usdg = new MockUSDG();
        market = new BondedClaims(IERC20(address(usdg)), 10 * USD, 5 * USD, 1 hours);
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
        return market.post("TSLA", FILING, H, stake);
    }

    function test_a_claim_locks_its_stake_until_it_is_judged() public {
        uint256 id = _post(honest, 50 * USD);
        assertEq(market.locked(honest), 50 * USD);
        assertEq(market.freeBond(honest), 450 * USD);
        vm.prank(honest);
        vm.expectRevert(BondedClaims.NotEnoughFreeBond.selector);
        market.withdraw(451 * USD);   // cannot pull out money that is behind a live claim
        market.clear(id);
        assertEq(market.locked(honest), 0);
        assertEq(market.cleared(honest), 1);
    }

    function test_a_false_claim_costs_its_author_and_pays_the_challenger() public {
        uint256 id = _post(liar, 100 * USD);
        market.slash(id, watcher, "supporting quote not found in the filing");
        assertEq(market.bonded(liar), 400 * USD, "stake at risk is gone");
        assertEq(usdg.balanceOf(watcher), 50 * USD, "half to the challenger");
        assertEq(market.readerPool(), 50 * USD, "half backs readers");
        assertEq(market.slashedCount(liar), 1);
        assertEq(uint8(market.claim(id).status), uint8(BondedClaims.Status.Slashed));
    }

    function test_money_is_conserved() public {
        uint256 a = _post(liar, 100 * USD);
        uint256 b = _post(honest, 30 * USD);
        market.slash(a, watcher, "value not grounded in the quote");
        market.clear(b);
        vm.prank(honest);
        market.withdraw(500 * USD);
        uint256 held = usdg.balanceOf(address(market));
        assertEq(held, market.bonded(liar) + market.bonded(honest) + market.readerPool());
    }

    function test_only_the_verifier_judges() public {
        uint256 id = _post(liar, 20 * USD);
        vm.prank(liar);
        vm.expectRevert(BondedClaims.NotVerifier.selector);
        market.clear(id);
    }

    function test_a_claim_is_judged_once() public {
        uint256 id = _post(liar, 20 * USD);
        market.slash(id, watcher, "fabricated");
        vm.expectRevert(BondedClaims.NotPending.selector);
        market.slash(id, watcher, "again");
    }

    function test_a_claim_must_carry_real_stake() public {
        vm.prank(honest);
        vm.expectRevert(BondedClaims.StakeTooSmall.selector);
        market.post("TSLA", FILING, H, 1 * USD);
    }

    function test_you_cannot_stake_more_than_you_bonded() public {
        _post(honest, 400 * USD);
        vm.prank(honest);
        vm.expectRevert(BondedClaims.NotEnoughFreeBond.selector);
        market.post("TSLA", FILING, H, 200 * USD);
    }

    function testFuzz_slashing_never_touches_other_analysts(uint96 stake) public {
        stake = uint96(bound(stake, 10 * USD, 500 * USD));
        uint256 id = _post(liar, stake);
        market.slash(id, watcher, "fuzz");
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
        vm.prank(watcher);                       // anyone can finalise
        market.finalize(id);
        assertEq(uint8(market.claim(id).status), uint8(BondedClaims.Status.Cleared));
        assertEq(market.locked(honest), 0);
    }

    function test_a_won_challenge_returns_the_deposit_and_pays_the_bounty() public {
        address c = _challenger();
        uint256 id = _post(liar, 100 * USD);
        vm.prank(c);
        market.challenge(id);
        assertEq(usdg.balanceOf(c), 95 * USD);
        market.resolve(id, true, "figures differ from the filing");
        assertEq(usdg.balanceOf(c), 100 * USD + 50 * USD, "deposit back plus half the stake");
        assertEq(market.bonded(liar), 400 * USD);
        assertEq(market.readerPool(), 50 * USD);
    }

    function test_a_lost_challenge_pays_the_analyst() public {
        address c = _challenger();
        uint256 id = _post(honest, 50 * USD);
        vm.prank(c);
        market.challenge(id);
        market.resolve(id, false, "quote verified");
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

    function test_only_the_verifier_resolves() public {
        address c = _challenger();
        uint256 id = _post(liar, 20 * USD);
        vm.prank(c);
        market.challenge(id);
        vm.prank(c);
        vm.expectRevert(BondedClaims.NotVerifier.selector);
        market.resolve(id, true, "self-serving");
    }

    function testFuzz_money_is_conserved_through_disputes(uint96 stake, bool fraudulent) public {
        stake = uint96(bound(stake, 10 * USD, 500 * USD));
        address c = _challenger();
        uint256 before = usdg.balanceOf(address(market)) + usdg.balanceOf(c);
        uint256 id = _post(liar, stake);
        vm.prank(c);
        market.challenge(id);
        market.resolve(id, fraudulent, "fuzz");
        uint256 held = usdg.balanceOf(address(market));
        assertEq(held, market.bonded(liar) + market.bonded(honest) + market.readerPool());
        assertEq(held + usdg.balanceOf(c), before);
    }

    function test_the_verifier_cannot_slash_after_the_window_either() public {
        uint256 id = _post(liar, 20 * USD);
        vm.warp(block.timestamp + 1 hours + 1);
        vm.expectRevert(BondedClaims.WindowClosed.selector);
        market.slash(id, watcher, "too late");
        market.finalize(id);                     // the window passed: it stands
        assertEq(market.bonded(liar), 500 * USD);
    }

    function test_the_verifier_role_cannot_be_burned() public {
        vm.expectRevert(BondedClaims.NotVerifier.selector);
        market.setVerifier(address(0));
    }
}
