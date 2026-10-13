// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {BondedClaims} from "./BondedClaims.sol";

/// @title AgentDesk
/// @notice A paper-trading desk for AI agents, with a journal that shows why
/// every trade was made.
///
/// An agent opens a practice position by naming the claims it is acting on and
/// the hash of its written reasoning. Every claim must have been cleared by the
/// check (a verdict with filing evidence) and be about the same stock; a slashed
/// claim, one still unsettled, one that only cleared by default, a claim about
/// another ticker, or the same words cited twice reverts the trade on-chain.
///
/// What the desk keeps is the reasoning trail, in the order a reviewer follows
/// it: the trade, the claims it cites (by id and by the hash of their exact
/// words), the verdict each one received (when it was settled, by which
/// Chainlink CRE workflow, and the filing evidence the check committed to), and the agent's reasoning record.
/// Anyone can walk it backwards to the SEC filing and redo every step.
///
/// No money moves: notional is a paper figure in USD (6 decimals). On mainnet
/// the same gate would sit in front of a venue that trades the stock token.
contract AgentDesk {
    enum Side {
        Long,
        Short
    }

    struct Entry {
        address agent;
        Side side;
        uint64 openedAt;
        uint64 closedAt; // 0 while open
        uint256 notional; // paper USD, 6 decimals
        string ticker;
        bytes32 reasoning; // keccak256 of the agent's reasoning record, published with the journal
        bytes32 exitReasoning;
        uint256[] backing; // the cleared claims the trade cites
    }

    /// @notice One cited claim, as the desk saw it when the trade opened.
    struct Citation {
        uint256 claimId;
        bytes32 claimHash; // keccak256 of the claim's exact words
        uint64 settledAt; // when its verdict was written
        bytes32 evidence; // what the check committed to (filing hash), 0 if it cleared unchallenged
        bytes32 workflowId; // the Chainlink CRE workflow that wrote the verdict, 0 if none
    }

    BondedClaims public immutable vouch;
    Entry[] private _journal;

    event Opened(
        uint256 indexed entry,
        address indexed agent,
        string ticker,
        Side side,
        uint256 notional,
        bytes32 reasoning,
        Citation[] citations
    );
    event Closed(uint256 indexed entry, address indexed agent, bytes32 exitReasoning);

    error NoBacking();
    error NoReasoning();
    error NotCleared(uint256 claimId);
    error WrongTicker(uint256 claimId);
    error CitedTwice(uint256 claimId);
    error NotChecked(uint256 claimId);
    error NotYours();
    error AlreadyClosed();

    constructor(BondedClaims market) {
        vouch = market;
    }

    /// @notice Open a practice position on cleared research. `reasoning` is the
    /// keccak256 of the agent's reasoning record, so the published reasoning
    /// cannot be rewritten after the trade.
    function open(string calldata ticker, Side side, uint256 notional, uint256[] calldata backing, bytes32 reasoning)
        external
        returns (uint256 entry)
    {
        if (backing.length == 0) revert NoBacking();
        if (reasoning == bytes32(0)) revert NoReasoning();
        bytes32 t = keccak256(bytes(ticker));
        Citation[] memory cites = new Citation[](backing.length);
        // Calls in this loop are views on the immutable market; a revert there is the refusal itself.
        // slither-disable-start calls-loop
        for (uint256 i; i < backing.length; i++) {
            uint256 id = backing[i];
            if (!vouch.isCleared(id)) revert NotCleared(id);
            BondedClaims.Claim memory c = vouch.claim(id);
            if (keccak256(bytes(c.ticker)) != t) revert WrongTicker(id);
            // the same words twice (even under two ids) are one piece of evidence
            for (uint256 j; j < i; j++) {
                if (backing[j] == id || cites[j].claimHash == c.claimHash) revert CitedTwice(id);
            }
            BondedClaims.Verdict memory v = vouch.verdict(id);
            // cleared by default (nobody's verdict came) is not cleared by the check
            if (v.evidence == bytes32(0)) revert NotChecked(id);
            cites[i] = Citation(id, c.claimHash, v.settledAt, v.evidence, v.workflowId);
        }
        // slither-disable-end calls-loop
        entry = _journal.length;
        // casting to uint64 is safe: block timestamps fit in 64 bits for the next 500 billion years
        // forge-lint: disable-next-line(unsafe-typecast)
        _journal.push(Entry(msg.sender, side, uint64(block.timestamp), 0, notional, ticker, reasoning, 0, backing));
        emit Opened(entry, msg.sender, ticker, side, notional, reasoning, cites);
    }

    /// @notice Close a practice position, with the hash of why.
    function close(uint256 entry, bytes32 exitReasoning) external {
        Entry storage e = _journal[entry];
        if (e.agent != msg.sender) revert NotYours();
        if (e.closedAt != 0) revert AlreadyClosed();
        // forge-lint: disable-next-line(unsafe-typecast)
        e.closedAt = uint64(block.timestamp);
        e.exitReasoning = exitReasoning;
        emit Closed(entry, msg.sender, exitReasoning);
    }

    // ---- reading ----------------------------------------------------------

    function journal(uint256 entry) external view returns (Entry memory) {
        return _journal[entry];
    }

    function journalLength() external view returns (uint256) {
        return _journal.length;
    }

    /// @notice The citation set of an entry, read live from the market. Verdicts
    /// are final once written, so this is what the desk saw when it opened.
    function citations(uint256 entry) external view returns (Citation[] memory cites) {
        uint256[] storage b = _journal[entry].backing;
        cites = new Citation[](b.length);
        // slither-disable-start calls-loop
        for (uint256 i; i < b.length; i++) {
            BondedClaims.Verdict memory v = vouch.verdict(b[i]);
            cites[i] = Citation(b[i], vouch.claim(b[i]).claimHash, v.settledAt, v.evidence, v.workflowId);
        }
        // slither-disable-end calls-loop
    }
}
