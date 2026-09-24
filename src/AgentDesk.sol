// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {BondedClaims, IERC20} from "./BondedClaims.sol";

/// @title AgentDesk
/// @notice A trading desk for AI agents that will not act on research that
/// failed the check.
///
/// An agent opens a position by naming the claims it is acting on. Every one
/// must be cleared by Vouch and be about the same stock. A slashed claim, one
/// still inside its challenge window, or a claim about another ticker reverts
/// the trade on-chain. This is the reason the check lives on-chain at all:
/// other contracts can depend on it without trusting anybody's API.
///
/// Positions are a ledger here. On mainnet the notional is routed to a venue
/// that trades the stock token; the gate in front of it is the point.
contract AgentDesk {
    BondedClaims public immutable vouch;
    IERC20 public immutable cash;

    mapping(address => mapping(bytes32 => uint256)) public position;   // agent => ticker => notional

    event Opened(address indexed agent, string ticker, uint256 notional, uint256[] backing);
    event Closed(address indexed agent, string ticker, uint256 notional);

    error NoBacking();
    error NotCleared(uint256 claimId);
    error WrongTicker(uint256 claimId);
    error NothingOpen();
    error TransferFailed();

    constructor(BondedClaims market) {
        vouch = market;
        cash = market.bondToken();
    }

    function open(string calldata ticker, uint256 notional, uint256[] calldata backing) external {
        if (backing.length == 0) revert NoBacking();
        bytes32 t = keccak256(bytes(ticker));
        for (uint256 i; i < backing.length; i++) {
            uint256 id = backing[i];
            if (!vouch.isCleared(id)) revert NotCleared(id);
            if (keccak256(bytes(vouch.claim(id).ticker)) != t) revert WrongTicker(id);
        }
        position[msg.sender][t] += notional;
        emit Opened(msg.sender, ticker, notional, backing);
        if (!cash.transferFrom(msg.sender, address(this), notional)) revert TransferFailed();
    }

    function close(string calldata ticker) external {
        bytes32 t = keccak256(bytes(ticker));
        uint256 n = position[msg.sender][t];
        if (n == 0) revert NothingOpen();
        position[msg.sender][t] = 0;
        emit Closed(msg.sender, ticker, n);
        if (!cash.transfer(msg.sender, n)) revert TransferFailed();
    }
}
