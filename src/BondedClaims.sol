// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice The slice of ERC-20 this contract needs. USDG, the bond token on
/// mainnet, is a standard ERC-20 that returns a bool.
interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address who) external view returns (uint256);
}

/// @notice What a Chainlink CRE forwarder calls with a verified report.
interface IReceiver {
    function onReport(bytes calldata metadata, bytes calldata report) external;
}

/// @notice ERC-165, so the forwarder can confirm this contract takes reports.
interface IERC165 {
    function supportsInterface(bytes4 interfaceId) external view returns (bool);
}

/// @title BondedClaims
/// @notice Research claims about public companies that cost the author money
/// when they are false, settled by a Chainlink CRE workflow rather than by any
/// one key.
///
/// An analyst (usually an AI agent) bonds a stablecoin, then publishes a claim
/// about a company with the exact sentence from an SEC filing that supports it.
/// The claim's words go into the Posted event and their keccak256 into storage,
/// so the record holds exactly what was said and it cannot be edited.
///
/// Posting a claim is what triggers the check. A Chainlink Runtime Environment
/// workflow listens for Posted, fetches the cited filing from SEC EDGAR, runs
/// the deterministic check on every node of a decentralised oracle network, and
/// writes the verdict back through the Chainlink forwarder, which only delivers
/// a report the network's nodes signed. This contract accepts verdicts from that
/// forwarder, from that workflow, and from nobody else: there is no verifier key.
/// (Until the deployer pins one compiled workflow id, the workflow owner can
/// replace the workflow's code under the same name; once pinned, nobody can.)
///
/// A false claim loses its whole stake to the readers' fund. The fund's payees
/// and their shares are fixed when the market is deployed (in production, a
/// restitution or investor-protection account named in the deployment; on a test
/// market, a labelled stand-in) and nobody can change them afterwards. Each payee
/// withdraws its own share whenever it likes (claimReaderShare). A true claim keeps
/// its stake, and takes the deposit of anyone who challenged it. A challenge stops the
/// clock: a challenged claim cannot clear by default. If no verdict comes, an
/// unchallenged claim clears itself once its window passes, but it is marked
/// unchecked (no filing evidence) and AgentDesk will not let an agent cite it.
/// A challenge that no verdict ever answers unwinds after seven days, refunding
/// both sides.
contract BondedClaims is IReceiver, IERC165 {
    enum Status {
        None,
        Pending,
        Challenged,
        Cleared,
        Slashed,
        Void
    }

    struct Claim {
        address analyst;
        uint64 postedAt;
        Status status;
        uint256 atStake;
        bytes32 claimHash; // keccak256 of the canonical claim JSON (value + quote + filing), as posted
        string filing; // SEC accession number, e.g. "0001628280-26-049270"
        string ticker;
        address challenger; // set once challenged
    }

    /// @notice How a claim was settled, so anything that relies on it can say
    /// which check it relied on.
    struct Verdict {
        uint64 settledAt; // when it was written (the transaction is the Cleared or Slashed event for this id)
        bytes32 evidence; // keccak256 of the filing bytes the workflow fetched from EDGAR; 0 if unchecked
        bytes32 workflowId; // the CRE workflow that wrote it; 0 if it cleared unchallenged
    }

    /// @notice The report a workflow writes, one claim per report:
    /// abi.encode(claimId, claimHash, fraudulent, evidence, reason). The hash
    /// must match: the workflow checked these words and no others.
    struct Report {
        uint256 claimId;
        bytes32 claimHash;
        bool fraudulent;
        bytes32 evidence;
        string reason;
    }

    IERC20 public immutable bondToken;
    uint256 public immutable minStake;
    uint256 public immutable challengeBond;
    // Seconds a claim can be challenged. Compared with block.timestamp, which a
    // sequencer can skew by seconds; the window is an hour, so it cannot matter.
    uint64 public immutable window;
    // A challenge nobody's verdict answers in this long can be unwound.
    uint64 public constant UNWIND_AFTER = 7 days;
    // Posted carries the ticker, the filing and the words, and the workflow
    // only sees a claim through that log. A Chainlink CRE log trigger takes
    // logs up to about 5 KB, so a longer claim would never be checked. These
    // caps keep the whole event under 4 KB. An SEC accession is 20 characters.
    uint256 public constant MAX_WORDS = 3500;
    uint256 public constant MAX_TICKER = 16;
    uint256 public constant MAX_FILING = 32;

    // Who may settle: the Chainlink forwarder on this chain, carrying a report
    // from this owner's workflow of this name, and, once pinned, only the
    // workflow with this id (a hash of its compiled code and config).
    // A market built for CRE simulation points at Chainlink's mock forwarder,
    // which signs nothing and fills no workflow identity, so it is deployed
    // with no owner (0) and checks only the forwarder. That market is for
    // demonstrating the path; it trusts whoever calls the mock.
    address public immutable forwarder;
    address public immutable workflowOwner;
    bytes10 public immutable workflowName;
    bytes32 public workflowId;
    address private immutable _deployer;

    mapping(address => uint256) public bonded; // everything an analyst has deposited
    mapping(address => uint256) public locked; // the part currently at stake on pending claims
    // A claim counts as cleared only when the workflow checked it and found it
    // true. One that cleared by default, with no verdict, is counted apart, so a
    // record of unchecked claims cannot pass for a record of true ones.
    mapping(address => uint32) public cleared;
    mapping(address => uint32) public clearedUnchecked;
    mapping(address => uint32) public slashedCount;
    Claim[] private _claims;
    mapping(uint256 => Verdict) private _verdicts;
    mapping(uint256 => uint64) public challengedAt;

    // The readers' fund. readerPool is everything ever forfeited by wrong claims;
    // readerPaid is how much of it payees have withdrawn. A payee is owed
    // readerPool * its shares / totalShares, less what it already took. That is
    // rounded down, so the contract never owes more than it holds; the remainder
    // (under one unit per payee) is paid out as later forfeits raise the total.
    uint256 public readerPool;
    uint256 public readerPaid;
    uint256 public immutable totalShares;
    uint256 public constant MAX_PAYEES = 16;
    address[] private _payees;
    mapping(address => uint256) public shares;
    mapping(address => uint256) public readerReleased;
    uint256 private _entered = 1;

    event Bonded(address indexed analyst, uint256 amount, uint256 total);
    event Posted(
        uint256 indexed id,
        address indexed analyst,
        string ticker,
        string filing,
        bytes32 claimHash,
        uint256 atStake,
        bytes claim
    );
    event Cleared(uint256 indexed id, address indexed analyst);
    event Slashed(
        uint256 indexed id, address indexed analyst, address indexed challenger, uint256 amount, string reason
    );
    event Checked(uint256 indexed id, bool fraudulent, bytes32 evidence, bytes32 workflowId, string reason);
    event ReportIgnored(uint256 indexed id, Status status);
    event Withdrawn(address indexed analyst, uint256 amount);
    event Challenged(uint256 indexed id, address indexed challenger, uint256 deposit);
    event Upheld(uint256 indexed id, address indexed challenger, uint256 deposit);
    event Unwound(uint256 indexed id, address indexed challenger);
    event WorkflowPinned(bytes32 workflowId);
    event ReaderPayee(address indexed payee, uint256 shares);
    event ReaderPaid(address indexed payee, uint256 amount);

    error StakeTooSmall();
    error NotEnoughFreeBond();
    error NotPending();
    error TransferFailed();
    error WindowOpen();
    error WindowClosed();
    error NotChallenged();
    error NoSuchClaim();
    error NotForwarder(address sender);
    error WrongWorkflow();
    error WrongClaim();
    error AlreadyPinned();
    error ZeroAddress();
    error EmptyClaim();
    error ClaimTooLong();
    error TickerTooLong();
    error FilingTooLong();
    error BadPayees();
    error NothingDue();
    error Reentrant();

    modifier nonReentrant() {
        if (_entered != 1) revert Reentrant();
        _entered = 2;
        _;
        _entered = 1;
    }

    constructor(
        IERC20 token,
        uint256 minimumStake,
        uint256 challengeDeposit,
        uint64 challengeWindow,
        address chainlinkForwarder,
        address owner_,
        bytes10 name_,
        address[] memory fundPayees,
        uint256[] memory payeeShares
    ) {
        if (chainlinkForwarder == address(0)) revert ZeroAddress();
        // The readers' fund is fixed here, in public, before any claim exists: an
        // analyst cannot later route a forfeited stake back to themselves.
        if (fundPayees.length == 0 || fundPayees.length > MAX_PAYEES || fundPayees.length != payeeShares.length) {
            revert BadPayees();
        }
        uint256 total;
        for (uint256 i; i < fundPayees.length; i++) {
            address p = fundPayees[i];
            if (p == address(0) || payeeShares[i] == 0 || shares[p] != 0) revert BadPayees();
            shares[p] = payeeShares[i];
            _payees.push(p);
            total += payeeShares[i];
            emit ReaderPayee(p, payeeShares[i]);
        }
        totalShares = total;
        bondToken = token;
        minStake = minimumStake;
        challengeBond = challengeDeposit;
        window = challengeWindow;
        forwarder = chainlinkForwarder;
        // slither-disable-next-line missing-zero-check
        workflowOwner = owner_; // 0 on purpose: a market for CRE simulation (see above)
        workflowName = name_;
        _deployer = msg.sender;
    }

    /// @notice Bind the market to one compiled workflow, once. The id is
    /// derived from the workflow's code and config, so anyone can rebuild it from
    /// the repository and see it is the check they read. It cannot be changed.
    function pinWorkflow(bytes32 id) external {
        if (msg.sender != _deployer || workflowOwner == address(0)) revert WrongWorkflow();
        if (workflowId != bytes32(0)) revert AlreadyPinned();
        if (id == bytes32(0)) revert WrongWorkflow();
        workflowId = id;
        emit WorkflowPinned(id);
    }

    // ---- analysts ---------------------------------------------------------

    // Every function below updates state and emits before it moves tokens
    // (checks, effects, interactions); a failed transfer reverts all of it.
    function bond(uint256 amount) external {
        bonded[msg.sender] += amount;
        emit Bonded(msg.sender, amount, bonded[msg.sender]);
        if (!bondToken.transferFrom(msg.sender, address(this), amount)) revert TransferFailed();
    }

    /// @notice Publish a claim, putting `atStake` of your free bond behind it.
    /// `words` is the canonical claim JSON; its hash is stored and the words are
    /// emitted, which is what the checking workflow reads.
    function post(string calldata ticker, string calldata filing, bytes calldata words, uint256 atStake)
        external
        returns (uint256 id)
    {
        // a claim the workflow cannot read could only ever clear unchecked
        if (words.length == 0) revert EmptyClaim();
        if (words.length > MAX_WORDS) revert ClaimTooLong();
        if (bytes(ticker).length > MAX_TICKER) revert TickerTooLong();
        if (bytes(filing).length > MAX_FILING) revert FilingTooLong();
        if (atStake < minStake) revert StakeTooSmall();
        if (freeBond(msg.sender) < atStake) revert NotEnoughFreeBond();
        locked[msg.sender] += atStake;
        id = _claims.length;
        bytes32 h = keccak256(words);
        // casting to uint64 is safe: block timestamps fit in 64 bits for the next 500 billion years
        // forge-lint: disable-next-line(unsafe-typecast)
        _claims.push(Claim(msg.sender, uint64(block.timestamp), Status.Pending, atStake, h, filing, ticker, address(0)));
        emit Posted(id, msg.sender, ticker, filing, h, atStake, words);
    }

    function withdraw(uint256 amount) external {
        if (freeBond(msg.sender) < amount) revert NotEnoughFreeBond();
        bonded[msg.sender] -= amount;
        emit Withdrawn(msg.sender, amount);
        if (!bondToken.transfer(msg.sender, amount)) revert TransferFailed();
    }

    // ---- the readers' fund ---------------------------------------------------

    /// @notice What `payee` can withdraw now: its share of everything forfeited,
    /// less what it already took. Zero for anyone who is not a payee.
    function readerDue(address payee) public view returns (uint256) {
        return readerPool * shares[payee] / totalShares - readerReleased[payee];
    }

    /// @notice A payee withdraws its share of the forfeited stakes. Pull, not
    /// push: a payee that cannot receive blocks nobody else. Records first, then
    /// the transfer, behind a reentrancy lock; a second call with nothing new
    /// forfeited reverts with NothingDue.
    function claimReaderShare() external nonReentrant returns (uint256 amount) {
        amount = readerDue(msg.sender);
        if (amount == 0) revert NothingDue();
        readerReleased[msg.sender] += amount;
        readerPaid += amount;
        emit ReaderPaid(msg.sender, amount);
        if (!bondToken.transfer(msg.sender, amount)) revert TransferFailed();
    }

    /// @notice The fund's payees, in deployment order.
    function payees() external view returns (address[] memory) {
        return _payees;
    }

    // ---- anyone -----------------------------------------------------------

    /// @notice Dispute a pending claim inside its window, with a deposit. The
    /// workflow's verdict settles it: a wrong claim is slashed and the deposit
    /// returned; a right one keeps its stake and takes the deposit.
    function challenge(uint256 id) external {
        Claim storage c = _pending(id);
        if (block.timestamp > c.postedAt + window) revert WindowClosed();
        c.status = Status.Challenged;
        c.challenger = msg.sender;
        // forge-lint: disable-next-line(unsafe-typecast)
        challengedAt[id] = uint64(block.timestamp);
        emit Challenged(id, msg.sender, challengeBond);
        if (!bondToken.transferFrom(msg.sender, address(this), challengeBond)) revert TransferFailed();
    }

    /// @notice A claim nobody challenged in time clears itself. Anyone may call.
    function finalize(uint256 id) external {
        Claim storage c = _pending(id);
        if (block.timestamp <= c.postedAt + window) revert WindowOpen();
        _clear(id, c, Verdict(_now(), bytes32(0), bytes32(0)), false);
    }

    /// @notice If no verdict ever answers a challenge, nobody's money stays
    /// stuck: after UNWIND_AFTER both sides get theirs back and the claim counts
    /// for nothing.
    function unwind(uint256 id) external {
        Claim storage c = _claims[id];
        if (c.status != Status.Challenged) revert NotChallenged();
        if (block.timestamp <= challengedAt[id] + UNWIND_AFTER) revert WindowOpen();
        c.status = Status.Void;
        locked[c.analyst] -= c.atStake;
        emit Unwound(id, c.challenger);
        if (!bondToken.transfer(c.challenger, challengeBond)) revert TransferFailed();
    }

    // ---- the workflow's verdict ---------------------------------------------

    /// @notice Called by the Chainlink forwarder with a report the workflow's
    /// nodes agreed on and signed. Metadata is the forwarder's standard header:
    /// workflow id (32 bytes), workflow name (10 bytes), workflow owner (20).
    function onReport(bytes calldata metadata, bytes calldata report) external override {
        if (msg.sender != forwarder) revert NotForwarder(msg.sender);
        (bytes32 wid, bytes10 name, address owner_) = _decodeMetadata(metadata);
        if (workflowOwner != address(0) && (owner_ != workflowOwner || name != workflowName)) revert WrongWorkflow();
        if (workflowId != bytes32(0) && wid != workflowId) revert WrongWorkflow();
        (uint256 id, bytes32 claimHash, bool fraudulent, bytes32 evidence, string memory reason) =
            abi.decode(report, (uint256, bytes32, bool, bytes32, string));
        Report memory r = Report(id, claimHash, fraudulent, evidence, reason);
        if (r.claimId >= _claims.length) revert NoSuchClaim();
        Claim storage c = _claims[r.claimId];
        if (c.claimHash != r.claimHash) revert WrongClaim();
        _settle(r, c, wid);
    }

    function _settle(Report memory r, Claim storage c, bytes32 wid) private {
        uint256 id = r.claimId;
        Verdict memory v = Verdict(_now(), r.evidence, wid);
        // A verdict for a claim that is already settled changes nothing. It is
        // recorded rather than reverted, so the forwarder's delivery succeeds. A
        // slash is applied whenever it arrives while the claim is unsettled: a
        // slow network must not turn a wrong claim into a cleared one.
        if (c.status == Status.Challenged) {
            address who = c.challenger;
            emit Checked(id, r.fraudulent, r.evidence, wid, r.reason);
            if (r.fraudulent) {
                // records first, then the money: the challenger's deposit comes back
                _slash(id, c, who, r.reason, v);
                if (!bondToken.transfer(who, challengeBond)) revert TransferFailed();
            } else {
                // a true claim keeps its stake and is paid for the trouble
                bonded[c.analyst] += challengeBond;
                emit Upheld(id, who, challengeBond);
                _clear(id, c, v, true);
            }
        } else if (c.status == Status.Pending) {
            emit Checked(id, r.fraudulent, r.evidence, wid, r.reason);
            if (r.fraudulent) _slash(id, c, address(0), r.reason, v);
            else _clear(id, c, v, true);
        } else {
            emit ReportIgnored(id, c.status);
        }
    }

    /// `checked` is true when a workflow verdict cleared the claim, false when
    /// it cleared by default because its window passed with no verdict.
    function _clear(uint256 id, Claim storage c, Verdict memory v, bool checked) private {
        c.status = Status.Cleared;
        _verdicts[id] = v;
        locked[c.analyst] -= c.atStake;
        if (checked) cleared[c.analyst] += 1;
        else clearedUnchecked[c.analyst] += 1;
        emit Cleared(id, c.analyst);
    }

    function _slash(uint256 id, Claim storage c, address challenger, string memory reason, Verdict memory v) private {
        c.status = Status.Slashed;
        _verdicts[id] = v;
        uint256 amount = c.atStake;
        locked[c.analyst] -= amount;
        bonded[c.analyst] -= amount;
        slashedCount[c.analyst] += 1;
        // All of it goes to the readers' fund. No bounty: the workflow checks every
        // claim, so a bounty would only pay an analyst to challenge their own wrong claim.
        readerPool += amount;
        emit Slashed(id, c.analyst, challenger, amount, reason);
    }

    function _decodeMetadata(bytes calldata m) private pure returns (bytes32 wid, bytes10 name, address owner_) {
        if (m.length < 62) revert WrongWorkflow();
        wid = bytes32(m[0:32]);
        name = bytes10(m[32:42]);
        owner_ = address(bytes20(m[42:62]));
    }

    // ---- reading ----------------------------------------------------------

    function supportsInterface(bytes4 interfaceId) external pure override returns (bool) {
        return interfaceId == type(IReceiver).interfaceId || interfaceId == type(IERC165).interfaceId;
    }

    function freeBond(address analyst) public view returns (uint256) {
        return bonded[analyst] - locked[analyst];
    }

    function claim(uint256 id) external view returns (Claim memory) {
        return _claims[id];
    }

    function verdict(uint256 id) external view returns (Verdict memory) {
        return _verdicts[id];
    }

    /// @notice For other contracts: did this claim survive the check? Pending
    /// and challenged claims are not cleared; only a settled truth is.
    function isCleared(uint256 id) external view returns (bool) {
        // compares a status, not a time (slither reads it as a timestamp check)
        // slither-disable-next-line incorrect-equality,timestamp
        return id < _claims.length && _claims[id].status == Status.Cleared;
    }

    function claimCount() external view returns (uint256) {
        return _claims.length;
    }

    function _pending(uint256 id) private view returns (Claim storage c) {
        c = _claims[id];
        if (c.status != Status.Pending) revert NotPending();
    }

    function _now() private view returns (uint64) {
        // forge-lint: disable-next-line(unsafe-typecast)
        return uint64(block.timestamp);
    }
}
