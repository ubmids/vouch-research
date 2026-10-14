// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {BondedClaims, IERC20} from "../src/BondedClaims.sol";
import {MockUSDG} from "../src/MockUSDG.sol";
import {Reports} from "./Reports.sol";

/// @notice Where a wrong claim's stake goes: the readers' fund named at deploy,
/// paid out by pull, rounded down, once per unit forfeited.
contract ReadersFundTest is Reports {
    MockUSDG usdg;
    BondedClaims market;
    address liar = makeAddr("liar");
    address a = makeAddr("readers fund A");
    address b = makeAddr("readers fund B");
    address c = makeAddr("readers fund C");
    uint256 constant USD = 1e6;
    string constant FILING = "0001628280-26-049270";

    function _market(address[] memory p, uint256[] memory s) internal returns (BondedClaims m) {
        m = new BondedClaims(IERC20(address(usdg)), 10 * USD, 5 * USD, 1 hours, address(fwd), OWNER, NAME, p, s);
        usdg.mint(liar, 1_000 * USD);
        vm.prank(liar);
        usdg.approve(address(m), type(uint256).max);
        vm.prank(liar);
        m.bond(1_000 * USD);
    }

    function _three(uint256 sa, uint256 sb, uint256 sc) internal view returns (address[] memory p, uint256[] memory s) {
        p = new address[](3);
        s = new uint256[](3);
        (p[0], p[1], p[2]) = (a, b, c);
        (s[0], s[1], s[2]) = (sa, sb, sc);
    }

    /// A wrong claim, slashed by the workflow's verdict.
    function _slash(BondedClaims m, uint256 stake, bytes memory words) internal {
        vm.prank(liar);
        uint256 id = m.post("TSLA", FILING, words, stake);
        _verdict(m, id, true, "wrong quarter");
    }

    function setUp() public {
        usdg = new MockUSDG();
        (address[] memory p, uint256[] memory s) = _fund();
        market = _market(p, s);
    }

    function test_a_wrong_claims_stake_is_paid_to_the_readers_fund() public {
        _slash(market, 100 * USD, "Q3 depreciation was $1.37 billion");
        assertEq(market.readerDue(FUND), 100 * USD);
        vm.expectEmit(true, false, false, true);
        emit BondedClaims.ReaderPaid(FUND, 100 * USD);
        vm.prank(FUND);
        assertEq(market.claimReaderShare(), 100 * USD);
        assertEq(usdg.balanceOf(FUND), 100 * USD, "the forfeited stake reached the fund");
        assertEq(market.readerPaid(), 100 * USD);
        assertEq(market.readerDue(FUND), 0);
        assertEq(usdg.balanceOf(address(market)), market.bonded(liar), "only the liar's free bond is left");
    }

    function test_a_payee_cannot_claim_the_same_money_twice() public {
        _slash(market, 40 * USD, "one");
        vm.startPrank(FUND);
        market.claimReaderShare();
        vm.expectRevert(BondedClaims.NothingDue.selector);
        market.claimReaderShare();
        vm.stopPrank();
        _slash(market, 25 * USD, "two");
        vm.prank(FUND);
        assertEq(market.claimReaderShare(), 25 * USD, "only what was forfeited since");
        assertEq(usdg.balanceOf(FUND), 65 * USD);
    }

    function test_nothing_forfeited_means_nothing_to_claim() public {
        assertEq(market.readerPool(), 0);
        vm.prank(FUND);
        vm.expectRevert(BondedClaims.NothingDue.selector);
        market.claimReaderShare();
    }

    function test_someone_not_named_at_deploy_gets_nothing() public {
        _slash(market, 100 * USD, "wrong");
        assertEq(market.readerDue(liar), 0);
        vm.prank(liar); // the slashed analyst cannot route the stake back
        vm.expectRevert(BondedClaims.NothingDue.selector);
        market.claimReaderShare();
    }

    function test_shares_split_the_pool_and_round_down() public {
        (address[] memory p, uint256[] memory s) = _three(1, 1, 1);
        BondedClaims m = _market(p, s);
        _slash(m, 10 * USD + 1, "ten dollars and one unit"); // 10_000_001 does not divide by 3
        for (uint256 i; i < 3; i++) {
            vm.prank(p[i]);
            assertEq(m.claimReaderShare(), 3_333_333);
        }
        assertEq(m.readerPool() - m.readerPaid(), 2, "two units of dust stay in the fund, not lost");
        _slash(m, 10 * USD + 2, "the next forfeit carries the dust"); // pool is now 20_000_003
        uint256 paid;
        for (uint256 i; i < 3; i++) {
            vm.prank(p[i]);
            paid += m.claimReaderShare();
        }
        assertEq(paid, 3 * 3_333_334, "each is topped up to floor(20_000_003 / 3)");
        assertEq(m.readerPool() - m.readerPaid(), 2);
    }

    function test_unequal_shares_are_paid_in_proportion() public {
        (address[] memory p, uint256[] memory s) = _three(5, 3, 2);
        BondedClaims m = _market(p, s);
        _slash(m, 100 * USD, "wrong");
        vm.prank(a);
        assertEq(m.claimReaderShare(), 50 * USD);
        vm.prank(b);
        assertEq(m.claimReaderShare(), 30 * USD);
        vm.prank(c);
        assertEq(m.claimReaderShare(), 20 * USD);
        assertEq(m.readerPaid(), m.readerPool());
    }

    /// Whatever the stakes and shares, the fund never pays out more than was
    /// forfeited, never leaves a payee's share unpaid by more than a unit, and the
    /// contract always holds every bond plus the unpaid pool.
    function testFuzz_payouts_never_exceed_the_pool(uint96 s1, uint96 s2, uint8 x, uint8 y, uint8 z) public {
        (address[] memory p, uint256[] memory s) = _three(uint256(x) + 1, uint256(y) + 1, uint256(z) + 1);
        BondedClaims m = _market(p, s);
        _slash(m, bound(s1, 10 * USD, 400 * USD), "first");
        vm.prank(a);
        m.claimReaderShare();
        _slash(m, bound(s2, 10 * USD, 400 * USD), "second");
        for (uint256 i; i < 3; i++) {
            if (m.readerDue(p[i]) == 0) continue;
            vm.prank(p[i]);
            m.claimReaderShare();
        }
        assertLe(m.readerPaid(), m.readerPool());
        assertLt(m.readerPool() - m.readerPaid(), 3, "under one unit per payee is left over");
        assertEq(usdg.balanceOf(address(m)), m.bonded(liar) + m.readerPool() - m.readerPaid());
    }

    function test_the_fund_is_fixed_and_checked_at_deploy() public {
        (address[] memory p, uint256[] memory s) = _three(1, 1, 1);
        assertEq(_market(p, s).payees().length, 3);
        assertEq(_market(p, s).totalShares(), 3);

        address[] memory none = new address[](0);
        uint256[] memory noShares = new uint256[](0);
        vm.expectRevert(BondedClaims.BadPayees.selector);
        new BondedClaims(IERC20(address(usdg)), 10 * USD, 5 * USD, 1 hours, address(fwd), OWNER, NAME, none, noShares);

        vm.expectRevert(BondedClaims.BadPayees.selector); // lengths differ
        new BondedClaims(IERC20(address(usdg)), 10 * USD, 5 * USD, 1 hours, address(fwd), OWNER, NAME, p, noShares);

        s[1] = 0; // a payee with no share
        vm.expectRevert(BondedClaims.BadPayees.selector);
        new BondedClaims(IERC20(address(usdg)), 10 * USD, 5 * USD, 1 hours, address(fwd), OWNER, NAME, p, s);

        s[1] = 1;
        p[2] = a; // the same payee twice
        vm.expectRevert(BondedClaims.BadPayees.selector);
        new BondedClaims(IERC20(address(usdg)), 10 * USD, 5 * USD, 1 hours, address(fwd), OWNER, NAME, p, s);

        p[2] = address(0);
        vm.expectRevert(BondedClaims.BadPayees.selector);
        new BondedClaims(IERC20(address(usdg)), 10 * USD, 5 * USD, 1 hours, address(fwd), OWNER, NAME, p, s);

        address[] memory many = new address[](17);
        uint256[] memory manyShares = new uint256[](17);
        for (uint256 i; i < 17; i++) {
            many[i] = address(uint160(i + 1));
            manyShares[i] = 1;
        }
        vm.expectRevert(BondedClaims.BadPayees.selector);
        new BondedClaims(IERC20(address(usdg)), 10 * USD, 5 * USD, 1 hours, address(fwd), OWNER, NAME, many, manyShares);
    }

    function test_a_payee_that_reenters_on_transfer_is_paid_once() public {
        HookToken t = new HookToken();
        Greedy g = new Greedy();
        address[] memory p = new address[](1);
        uint256[] memory s = new uint256[](1);
        p[0] = address(g);
        s[0] = 1;
        BondedClaims m =
            new BondedClaims(IERC20(address(t)), 10 * USD, 5 * USD, 1 hours, address(fwd), OWNER, NAME, p, s);
        t.mint(liar, 100 * USD);
        vm.startPrank(liar);
        t.approve(address(m), type(uint256).max);
        m.bond(100 * USD);
        uint256 id = m.post("TSLA", FILING, "wrong", 60 * USD);
        vm.stopPrank();
        _verdict(m, id, true, "wrong");
        g.take(m);
        assertEq(t.balanceOf(address(g)), 60 * USD, "paid exactly its share, once");
        assertEq(g.reentryError(), BondedClaims.Reentrant.selector, "the second call inside the transfer was refused");
        assertEq(t.balanceOf(address(m)), 40 * USD, "the liar's free bond is untouched");
    }
}

/// A token that calls the recipient on every transfer, like ERC-777 hooks: the
/// way a payout could be re-entered.
contract HookToken {
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        if (to.code.length > 0) Greedy(to).onReceive();
        return true;
    }
}

contract Greedy {
    bytes4 public reentryError;
    BondedClaims private _m;

    function take(BondedClaims m) external {
        _m = m;
        m.claimReaderShare();
    }

    function onReceive() external {
        try _m.claimReaderShare() {
            reentryError = bytes4(0);
        } catch (bytes memory err) {
            reentryError = bytes4(err);
        }
    }
}
