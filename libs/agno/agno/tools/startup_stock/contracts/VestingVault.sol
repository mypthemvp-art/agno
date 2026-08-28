// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20Minimal {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

/// @title VestingVault
/// @notice Linear vesting with optional cliff for startup equity tokens.
contract VestingVault {
    struct Schedule {
        uint256 totalAmount;
        uint256 released;
        uint256 startTime;
        uint256 cliffDuration;
        uint256 vestingDuration;
        bool revoked;
    }

    IERC20Minimal public immutable token;
    address public owner;
    mapping(address => Schedule) public schedules;

    event ScheduleCreated(
        address indexed beneficiary,
        uint256 totalAmount,
        uint256 startTime,
        uint256 cliffDuration,
        uint256 vestingDuration
    );
    event Released(address indexed beneficiary, uint256 amount);
    event ScheduleRevoked(address indexed beneficiary, uint256 returnedAmount);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    modifier onlyOwner() {
        require(msg.sender == owner, "NOT_OWNER");
        _;
    }

    constructor(address _token) {
        require(_token != address(0), "ZERO_TOKEN");
        token = IERC20Minimal(_token);
        owner = msg.sender;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "ZERO_ADDRESS");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    function createSchedule(
        address beneficiary,
        uint256 totalAmount,
        uint256 startTime,
        uint256 cliffDuration,
        uint256 vestingDuration
    ) external onlyOwner {
        require(beneficiary != address(0), "ZERO_ADDRESS");
        require(totalAmount > 0, "ZERO_AMOUNT");
        require(vestingDuration > 0, "ZERO_DURATION");
        require(schedules[beneficiary].totalAmount == 0, "SCHEDULE_EXISTS");

        require(
            token.transferFrom(msg.sender, address(this), totalAmount),
            "TRANSFER_FAILED"
        );

        schedules[beneficiary] = Schedule({
            totalAmount: totalAmount,
            released: 0,
            startTime: startTime,
            cliffDuration: cliffDuration,
            vestingDuration: vestingDuration,
            revoked: false
        });

        emit ScheduleCreated(beneficiary, totalAmount, startTime, cliffDuration, vestingDuration);
    }

    function vestedAmount(address beneficiary) public view returns (uint256) {
        Schedule memory s = schedules[beneficiary];
        if (s.totalAmount == 0 || s.revoked) {
            return s.released;
        }
        if (block.timestamp < s.startTime + s.cliffDuration) {
            return 0;
        }
        if (block.timestamp >= s.startTime + s.cliffDuration + s.vestingDuration) {
            return s.totalAmount;
        }
        uint256 elapsed = block.timestamp - s.startTime - s.cliffDuration;
        return (s.totalAmount * elapsed) / s.vestingDuration;
    }

    function releasable(address beneficiary) public view returns (uint256) {
        Schedule memory s = schedules[beneficiary];
        uint256 vested = vestedAmount(beneficiary);
        if (vested <= s.released) {
            return 0;
        }
        return vested - s.released;
    }

    function release(address beneficiary) external {
        uint256 amount = releasable(beneficiary);
        require(amount > 0, "NOTHING_TO_RELEASE");

        schedules[beneficiary].released += amount;
        require(token.transfer(beneficiary, amount), "TRANSFER_FAILED");
        emit Released(beneficiary, amount);
    }

    function revoke(address beneficiary) external onlyOwner {
        Schedule storage s = schedules[beneficiary];
        require(s.totalAmount > 0, "NO_SCHEDULE");
        require(!s.revoked, "ALREADY_REVOKED");

        uint256 unreleased = s.totalAmount - s.released;
        s.revoked = true;
        s.totalAmount = s.released;

        if (unreleased > 0) {
            require(token.transfer(owner, unreleased), "TRANSFER_FAILED");
        }
        emit ScheduleRevoked(beneficiary, unreleased);
    }
}
