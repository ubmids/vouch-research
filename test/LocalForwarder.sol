// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IReceiver} from "../src/BondedClaims.sol";

/// @notice A local stand-in for Chainlink's forwarder, for anvil and tests.
///
/// It takes a raw report laid out exactly as the CRE forwarders take it
/// (version 1, execution id 32, timestamp 4, DON id 4, config version 4,
/// workflow id 32, workflow name 10, workflow owner 20, report id 2, then the
/// workflow's payload) and calls the receiver's onReport with the same slices
/// Chainlink's MockKeystoneForwarder passes. Like that mock it checks no
/// signatures: on a public chain the real KeystoneForwarder does.
contract LocalForwarder {
    uint256 internal constant FORWARDER_METADATA_LENGTH = 45;
    uint256 internal constant METADATA_LENGTH = 109;

    event ReportProcessed(
        address indexed receiver, bytes32 indexed workflowExecutionId, bytes2 indexed reportId, bool result
    );

    error InvalidReport();

    function report(address receiver, bytes calldata rawReport, bytes calldata, bytes[] calldata) external {
        if (rawReport.length < METADATA_LENGTH) revert InvalidReport();
        bytes32 executionId = bytes32(rawReport[1:33]);
        bytes2 reportId = bytes2(rawReport[107:109]);
        IReceiver(receiver).onReport(rawReport[FORWARDER_METADATA_LENGTH:METADATA_LENGTH], rawReport[METADATA_LENGTH:]);
        emit ReportProcessed(receiver, executionId, reportId, true);
    }
}
