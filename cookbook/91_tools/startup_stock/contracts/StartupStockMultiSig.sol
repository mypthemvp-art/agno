// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title StartupStockMultiSig
/// @notice M-of-N multisig for executing privileged calls on startup stock contracts.
contract StartupStockMultiSig {
    event Confirmation(address indexed owner, uint256 indexed txId);
    event Revocation(address indexed owner, uint256 indexed txId);
    event Submission(uint256 indexed txId);
    event Execution(uint256 indexed txId);
    event ExecutionFailure(uint256 indexed txId);
    event OwnerAddition(address indexed owner);
    event OwnerRemoval(address indexed owner);
    event RequirementChange(uint256 required);

    uint256 public transactionCount;
    address[] public owners;
    mapping(address => bool) public isOwner;
    uint256 public required;

    struct Transaction {
        address target;
        uint256 value;
        bytes data;
        bool executed;
    }

    mapping(uint256 => Transaction) public transactions;
    mapping(uint256 => mapping(address => bool)) public confirmations;

    modifier onlyOwner() {
        require(isOwner[msg.sender], "NOT_OWNER");
        _;
    }

    modifier txExists(uint256 txId) {
        require(txId < transactionCount, "TX_NOT_EXISTS");
        _;
    }

    modifier notExecuted(uint256 txId) {
        require(!transactions[txId].executed, "TX_EXECUTED");
        _;
    }

    modifier notConfirmed(uint256 txId) {
        require(!confirmations[txId][msg.sender], "TX_CONFIRMED");
        _;
    }

    constructor(address[] memory _owners, uint256 _required) {
        require(_owners.length > 0 && _required > 0 && _required <= _owners.length, "INVALID_SETUP");
        for (uint256 i = 0; i < _owners.length; i++) {
            address ownerAddr = _owners[i];
            require(ownerAddr != address(0), "ZERO_OWNER");
            require(!isOwner[ownerAddr], "DUPLICATE_OWNER");
            isOwner[ownerAddr] = true;
            owners.push(ownerAddr);
        }
        required = _required;
    }

    function submitTransaction(address target, uint256 value, bytes calldata data)
        external
        onlyOwner
        returns (uint256 txId)
    {
        txId = transactionCount;
        transactions[txId] = Transaction({target: target, value: value, data: data, executed: false});
        transactionCount += 1;
        emit Submission(txId);
    }

    function confirmTransaction(uint256 txId)
        external
        onlyOwner
        txExists(txId)
        notExecuted(txId)
        notConfirmed(txId)
    {
        confirmations[txId][msg.sender] = true;
        emit Confirmation(msg.sender, txId);
        if (_confirmationCount(txId) >= required) {
            _executeTransaction(txId);
        }
    }

    function revokeConfirmation(uint256 txId)
        external
        onlyOwner
        txExists(txId)
        notExecuted(txId)
    {
        require(confirmations[txId][msg.sender], "TX_NOT_CONFIRMED");
        confirmations[txId][msg.sender] = false;
        emit Revocation(msg.sender, txId);
    }

    function executeTransaction(uint256 txId) external onlyOwner txExists(txId) notExecuted(txId) {
        require(_confirmationCount(txId) >= required, "INSUFFICIENT_CONFIRMATIONS");
        _executeTransaction(txId);
    }

    function _executeTransaction(uint256 txId) internal notExecuted(txId) {
        Transaction storage txn = transactions[txId];
        txn.executed = true;
        (bool success, ) = txn.target.call{value: txn.value}(txn.data);
        if (success) {
            emit Execution(txId);
        } else {
            emit ExecutionFailure(txId);
            txn.executed = false;
        }
    }

    function _confirmationCount(uint256 txId) internal view returns (uint256 count) {
        count = 0;
        for (uint256 i = 0; i < owners.length; i++) {
            if (confirmations[txId][owners[i]]) {
                count += 1;
            }
        }
    }

    function getOwners() external view returns (address[] memory) {
        return owners;
    }

    function getConfirmationCount(uint256 txId) external view returns (uint256) {
        return _confirmationCount(txId);
    }

    function isConfirmed(uint256 txId, address ownerAddr) external view returns (bool) {
        return confirmations[txId][ownerAddr];
    }
}
