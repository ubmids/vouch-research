// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {BondedClaims} from "../src/BondedClaims.sol";
import {LocalForwarder} from "./LocalForwarder.sol";

/// @notice Builds reports the way a CRE workflow's report reaches the chain,
/// so the tests exercise the forwarder path byte for byte.
abstract contract Reports is Test {
    LocalForwarder fwd = new LocalForwarder();
    bytes32 constant WORKFLOW_ID = keccak256("vouch-verifier wasm + config");
    address constant OWNER = address(0xC0FFEE);
    // forge-lint: disable-next-line(unsafe-typecast)
    bytes10 constant NAME = bytes10("a1b2c3d4e5");
    bytes32 constant FILING_HASH = keccak256("the bytes EDGAR served");
    // The readers' fund the test markets are deployed with: one payee, one share.
    address constant FUND = address(0xF00D);

    function _fund() internal pure returns (address[] memory p, uint256[] memory s) {
        p = new address[](1);
        s = new uint256[](1);
        p[0] = FUND;
        s[0] = 1;
    }

    function _raw(bytes32 wid, bytes10 name, address owner, bytes memory payload) internal view returns (bytes memory) {
        return abi.encodePacked(
            uint8(1),
            keccak256(payload),
            uint32(block.timestamp),
            uint32(1),
            uint32(1),
            wid,
            name,
            owner,
            bytes2(0x0001),
            payload
        );
    }

    function _payload(BondedClaims m, uint256 id, bool fraudulent, string memory reason)
        internal
        view
        returns (bytes memory)
    {
        return abi.encode(id, m.claim(id).claimHash, fraudulent, FILING_HASH, reason);
    }

    /// @notice What the workflow does: the check's answer, as a signed report.
    function _verdict(BondedClaims m, uint256 id, bool fraudulent, string memory reason) internal {
        fwd.report(address(m), _raw(WORKFLOW_ID, NAME, OWNER, _payload(m, id, fraudulent, reason)), "", new bytes[](0));
    }
}
