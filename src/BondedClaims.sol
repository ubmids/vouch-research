// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice The slice of ERC-20 this contract needs. USDG, the bond token on
/// mainnet, is a standard ERC-20 that returns a bool.
interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address who) external view returns (uint256);
}

/// @title BondedClaims
/// @notice Research claims about public companies that cost the author money
/// when they are false.
///
/// An analyst (usually an AI agent) bonds a stablecoin, then publishes a claim
/// about a company with the exact quote from an SEC filing that supports it.
/// Part of the bond is put at risk on each claim. The verifier checks the quote
/// against the filing off-chain, deterministically, and either clears the claim
/// or slashes the stake at risk: half to whoever raised the challenge, half to
/// a pool that backs readers of the feed.
///
/// Research is optimistic. A claim clears by itself once its challenge window
/// passes unchallenged. Within the window anyone may challenge it by posting a
/// smaller deposit. Because the check is deterministic (is this quote, with
/// these figures, in this filing?), a dispute has one right answer, which the
/// verifier records: a false claim loses its stake, and the challenger gets
/// their deposit back plus half of it; a true claim keeps its stake and takes
/// the challenger's deposit, so challenging costs something to get wrong too.
///
/// What lives on-chain is what has to be trusted: who said it, what they put
/// at risk, and what happened to that money. The claim text and quote are kept
/// off-chain and committed to by hash, so anyone can re-run the check.
contract BondedClaims {
    enum Status { None, Pending, Challenged, Cleared, Slashed }

    struct Claim {
        address analyst;
        uint64 postedAt;
        Status status;
        uint256 atStake;
        bytes32 claimHash;   // keccak256 of the canonical claim JSON (value + quote + filing)
        string filing;       // SEC accession number, e.g. "0001628280-26-049270"
        string ticker;
        address challenger;  // set once challenged
    }

    IERC20 public immutable bondToken;
    address public verifier;
    uint256 public immutable minStake;
    uint256 public immutable challengeBond;
    // Seconds a claim can be challenged. Compared with block.timestamp, which a
    // sequencer can skew by seconds; the window is an hour, so it cannot matter.
    uint64 public immutable window;

    mapping(address => uint256) public bonded;     // everything an analyst has deposited
    mapping(address => uint256) public locked;     // the part currently at stake on pending claims
    mapping(address => uint32) public cleared;
    mapping(address => uint32) public slashedCount;
    Claim[] private _claims;
    uint256 public readerPool;

    event Bonded(address indexed analyst, uint256 amount, uint256 total);
    event Posted(uint256 indexed id, address indexed analyst, string ticker, string filing, bytes32 claimHash, uint256 atStake);
    event Cleared(uint256 indexed id, address indexed analyst);
    event Slashed(uint256 indexed id, address indexed analyst, address indexed challenger, uint256 amount, string reason);
    event Withdrawn(address indexed analyst, uint256 amount);
    event VerifierChanged(address indexed from, address indexed to);
    event Challenged(uint256 indexed id, address indexed challenger, uint256 deposit);
    event Upheld(uint256 indexed id, address indexed challenger, uint256 deposit);

    error NotVerifier();
    error StakeTooSmall();
    error NotEnoughFreeBond();
    error NotPending();
    error TransferFailed();
    error WindowOpen();
    error WindowClosed();
    error NotChallenged();

    modifier onlyVerifier() {
        if (msg.sender != verifier) revert NotVerifier();
        _;
    }

    constructor(IERC20 token, uint256 minimumStake, uint256 challengeDeposit, uint64 challengeWindow) {
        bondToken = token;
        minStake = minimumStake;
        challengeBond = challengeDeposit;
        window = challengeWindow;
        verifier = msg.sender;
        emit VerifierChanged(address(0), msg.sender);
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
    function post(string calldata ticker, string calldata filing, bytes32 claimHash, uint256 atStake)
        external
        returns (uint256 id)
    {
        if (atStake < minStake) revert StakeTooSmall();
        if (freeBond(msg.sender) < atStake) revert NotEnoughFreeBond();
        locked[msg.sender] += atStake;
        id = _claims.length;
        // casting to uint64 is safe: block timestamps fit in 64 bits for the next 500 billion years
        // forge-lint: disable-next-line(unsafe-typecast)
        _claims.push(Claim(msg.sender, uint64(block.timestamp), Status.Pending, atStake, claimHash, filing, ticker, address(0)));
        emit Posted(id, msg.sender, ticker, filing, claimHash, atStake);
    }

    function withdraw(uint256 amount) external {
        if (freeBond(msg.sender) < amount) revert NotEnoughFreeBond();
        bonded[msg.sender] -= amount;
        emit Withdrawn(msg.sender, amount);
        if (!bondToken.transfer(msg.sender, amount)) revert TransferFailed();
    }

    // ---- anyone -----------------------------------------------------------

    /// @notice Dispute a pending claim inside its window, with a deposit.
    function challenge(uint256 id) external {
        Claim storage c = _pending(id);
        if (block.timestamp > c.postedAt + window) revert WindowClosed();
        c.status = Status.Challenged;
        c.challenger = msg.sender;
        emit Challenged(id, msg.sender, challengeBond);
        if (!bondToken.transferFrom(msg.sender, address(this), challengeBond)) revert TransferFailed();
    }

    /// @notice A claim nobody challenged in time clears itself. Anyone may call.
    function finalize(uint256 id) external {
        Claim storage c = _pending(id);
        if (block.timestamp <= c.postedAt + window) revert WindowOpen();
        _clear(id, c);
    }

    // ---- the verifier -----------------------------------------------------

    /// @notice Settle a challenge. `fraudulent` is the deterministic check's
    /// answer; the verifier only records it.
    function resolve(uint256 id, bool fraudulent, string calldata reason) external onlyVerifier {
        Claim storage c = _claims[id];
        if (c.status != Status.Challenged) revert NotChallenged();
        address who = c.challenger;
        if (fraudulent) {
            // records first, then the money: the deposit comes back with the bounty
            _slash(id, c, who, reason);
            if (!bondToken.transfer(who, challengeBond)) revert TransferFailed();
        } else {
            // a true claim keeps its stake and is paid for the trouble
            bonded[c.analyst] += challengeBond;
            emit Upheld(id, who, challengeBond);
            _clear(id, c);
        }
    }

    /// @notice The quote was found in the filing and the value is in the quote.
    function clear(uint256 id) external onlyVerifier {
        _clear(id, _pending(id));
    }

    /// @notice The claim failed the check. The stake at risk is taken: half to
    /// the challenger who raised it, the rest to the reader pool.
    /// The verifier as the default challenger: it may slash directly, but only
    /// inside the same window anyone else would have had.
    function slash(uint256 id, address challenger, string calldata reason) external onlyVerifier {
        Claim storage c = _pending(id);
        if (block.timestamp > c.postedAt + window) revert WindowClosed();
        _slash(id, c, challenger, reason);
    }

    function _clear(uint256 id, Claim storage c) private {
        c.status = Status.Cleared;
        locked[c.analyst] -= c.atStake;
        cleared[c.analyst] += 1;
        emit Cleared(id, c.analyst);
    }

    function _slash(uint256 id, Claim storage c, address challenger, string calldata reason) private {
        c.status = Status.Slashed;
        uint256 amount = c.atStake;
        locked[c.analyst] -= amount;
        bonded[c.analyst] -= amount;
        slashedCount[c.analyst] += 1;
        uint256 bounty = challenger == address(0) ? 0 : amount / 2;
        readerPool += amount - bounty;
        emit Slashed(id, c.analyst, challenger, amount, reason);
        if (bounty > 0 && !bondToken.transfer(challenger, bounty)) revert TransferFailed();
    }

    function setVerifier(address next) external onlyVerifier {
        if (next == address(0)) revert NotVerifier();
        emit VerifierChanged(verifier, next);
        verifier = next;
    }

    // ---- reading ----------------------------------------------------------

    function freeBond(address analyst) public view returns (uint256) {
        return bonded[analyst] - locked[analyst];
    }

    function claim(uint256 id) external view returns (Claim memory) {
        return _claims[id];
    }

    /// @notice For other contracts: did this claim survive the check? Pending
    /// and challenged claims are not cleared; only a settled truth is.
    function isCleared(uint256 id) external view returns (bool) {
        return id < _claims.length && _claims[id].status == Status.Cleared;
    }

    function claimCount() external view returns (uint256) {
        return _claims.length;
    }

    function _pending(uint256 id) private view returns (Claim storage c) {
        c = _claims[id];
        if (c.status != Status.Pending) revert NotPending();
    }
}
