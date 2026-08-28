// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title StartupStockToken
/// @notice ERC-20 startup equity token with capped supply, pausing, and role-based minting.
/// @dev Designed for startup cap-table tokenization on EVM chains.
contract StartupStockToken {
    string public name;
    string public symbol;
    uint8 public constant decimals = 18;
    uint256 public totalSupply;
    uint256 public maxSupply;
    bool public paused;

    address public owner;
    mapping(address => bool) public minters;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event Mint(address indexed to, uint256 amount);
    event Burn(address indexed from, uint256 amount);
    event MinterUpdated(address indexed minter, bool allowed);
    event Paused(bool isPaused);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    modifier onlyOwner() {
        require(msg.sender == owner, "NOT_OWNER");
        _;
    }

    modifier onlyMinter() {
        require(minters[msg.sender] || msg.sender == owner, "NOT_MINTER");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "PAUSED");
        _;
    }

    constructor(
        string memory _name,
        string memory _symbol,
        uint256 _maxSupply
    ) {
        require(_maxSupply > 0, "ZERO_MAX_SUPPLY");
        name = _name;
        symbol = _symbol;
        maxSupply = _maxSupply;
        owner = msg.sender;
        minters[msg.sender] = true;
    }

    function setMinter(address account, bool allowed) external onlyOwner {
        minters[account] = allowed;
        emit MinterUpdated(account, allowed);
    }

    function setPaused(bool _paused) external onlyOwner {
        paused = _paused;
        emit Paused(_paused);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "ZERO_ADDRESS");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    function approve(address spender, uint256 amount) external whenNotPaused returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transfer(address to, uint256 amount) external whenNotPaused returns (bool) {
        _transfer(msg.sender, to, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external whenNotPaused returns (bool) {
        uint256 currentAllowance = allowance[from][msg.sender];
        require(currentAllowance >= amount, "INSUFFICIENT_ALLOWANCE");
        unchecked {
            allowance[from][msg.sender] = currentAllowance - amount;
        }
        _transfer(from, to, amount);
        return true;
    }

    function mint(address to, uint256 amount) external onlyMinter whenNotPaused {
        require(to != address(0), "ZERO_ADDRESS");
        require(totalSupply + amount <= maxSupply, "MAX_SUPPLY_EXCEEDED");
        totalSupply += amount;
        balanceOf[to] += amount;
        emit Mint(to, amount);
        emit Transfer(address(0), to, amount);
    }

    function burn(uint256 amount) external whenNotPaused {
        require(balanceOf[msg.sender] >= amount, "INSUFFICIENT_BALANCE");
        balanceOf[msg.sender] -= amount;
        totalSupply -= amount;
        emit Burn(msg.sender, amount);
        emit Transfer(msg.sender, address(0), amount);
    }

    function _transfer(address from, address to, uint256 amount) internal {
        require(from != address(0) && to != address(0), "ZERO_ADDRESS");
        require(balanceOf[from] >= amount, "INSUFFICIENT_BALANCE");
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
    }
}
