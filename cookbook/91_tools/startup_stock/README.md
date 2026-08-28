# Startup Stock Blockchain MVP

High-security, fast-sync startup equity tokenization on EVM blockchains. Tokenize your cap table as an ERC-20 smart contract, manage investors off-chain, and sync to the blockchain with drift detection and automatic retries.

Works on macOS, Linux, and Windows via Python.

## Features

- **Smart Contract** — `StartupStockToken.sol` with capped supply, pausing, and role-based minting
- **Cap Table Sync** — SQLite-backed local cap table with checksum validation and retry logic
- **Agno Toolkit** — `StartupStockTools` for agents to read, mint, transfer, and sync shares
- **Read-Only Reader** — `StartupStockReader` for investors (no private key required)
- **CSV/JSON Import** — Bulk import cap tables from spreadsheets
- **On-Chain Reconcile** — Pull blockchain state and update local sync status
- **Contract Deploy** — Deploy via Foundry (`forge`) from Python or CLI
- **macOS CLI** — Command-line interface for startup founders (`cli.py`)
- **AgentOS API** — Serve founder and investor agents over HTTP
- **Vesting Schedules** — Linear vesting with cliff via `VestingVault.sol`
- **Multi-Sig Owner** — M-of-N multisig for privileged token operations
- **Transfer Webhooks** — HTTP webhook delivery on Transfer/Mint events
- **macOS Menu Bar App** — Native menu bar monitor (`menubar.py`, requires `rumps`)
- **Equity Reports** — Cap table reports with on-chain verification and vesting status
- **Dilution Modeling** — Model ownership dilution across funding scenarios
- **Compliance Export** — Export equity reports to JSON/CSV for audit
- **Webhook Daemon** — Continuous background polling for transfer events
- **Extended Deploy** — Deploy VestingVault and MultiSig via Foundry
- **AI Agent** — Natural-language cap table management with structured output

## Prerequisites

```bash
# Install dependencies
uv pip install "agno[evm]" web3

# Environment variables
export EVM_PRIVATE_KEY=0x<your-private-key>
export EVM_RPC_URL=https://0xrpc.io/sep          # Sepolia testnet
export STARTUP_STOCK_CONTRACT_ADDRESS=0x<deployed-contract>
export OPENAI_API_KEY=sk-...                     # For agent examples
```

## Deploy the Smart Contract

Compile and deploy `contracts/StartupStockToken.sol` using Foundry or Hardhat:

```bash
# Foundry example
forge create contracts/StartupStockToken.sol:StartupStockToken \
  --rpc-url $EVM_RPC_URL \
  --private-key $EVM_PRIVATE_KEY \
  --constructor-args "Acme Startup" "ACME" 1000000000000000000000000
```

Set `STARTUP_STOCK_CONTRACT_ADDRESS` to the deployed address.

## Quick Start

```python
from agno.tools.startup_stock import StartupStockTools

tools = StartupStockTools()

# Read token info
print(tools.get_token_info())

# Add investors to local cap table
tools.add_investor("Alice", "0x742d35Cc6634C0532925a3b8D2A7E1234567890A", 10000.0)
tools.add_investor("Bob", "0x3Dfc53E3C77bb4e30Ce333Be1a66Ce62558bE395", 5000.0)

# Preview sync (dry run)
print(tools.sync_cap_table(dry_run=True))

# Sync to blockchain
print(tools.sync_cap_table(dry_run=False))
```

## macOS CLI

```bash
.venvs/demo/bin/python cookbook/91_tools/startup_stock/cli.py deploy --name "Acme Startup" --symbol ACME --max-shares 1000000
.venvs/demo/bin/python cookbook/91_tools/startup_stock/cli.py import --file sample_cap_table.csv
.venvs/demo/bin/python cookbook/91_tools/startup_stock/cli.py info
.venvs/demo/bin/python cookbook/91_tools/startup_stock/cli.py add --name Alice --wallet 0x742d... --shares 10000
.venvs/demo/bin/python cookbook/91_tools/startup_stock/cli.py list
.venvs/demo/bin/python cookbook/91_tools/startup_stock/cli.py reconcile
.venvs/demo/bin/python cookbook/91_tools/startup_stock/cli.py balance --wallet 0x742d... --readonly
.venvs/demo/bin/python cookbook/91_tools/startup_stock/cli.py sync --dry-run
.venvs/demo/bin/python cookbook/91_tools/startup_stock/cli.py sync --live
.venvs/demo/bin/python cookbook/91_tools/startup_stock/cli.py report
.venvs/demo/bin/python cookbook/91_tools/startup_stock/cli.py export --file report.json
.venvs/demo/bin/python cookbook/91_tools/startup_stock/cli.py dilution --name "Series A" --new-shares 20000
.venvs/demo/bin/python cookbook/91_tools/startup_stock/cli.py vesting create --wallet 0x742d... --shares 10000
.venvs/demo/bin/python cookbook/91_tools/startup_stock/cli.py webhooks poll
.venvs/demo/bin/python cookbook/91_tools/startup_stock/cli.py deploy-vault
.venvs/demo/bin/python cookbook/91_tools/startup_stock/cli.py deploy-multisig --owners 0x111...,0x222... --required 2
```

## Examples

| File | Description |
|------|-------------|
| `01_cap_table_sync.py` | Add investors and sync cap table to blockchain |
| `02_startup_equity_agent.py` | AI agent for natural-language equity management |
| `03_import_and_reconcile.py` | Import CSV cap table and reconcile on-chain |
| `04_deploy_contract.py` | Deploy StartupStockToken via Foundry |
| `05_agentos_startup_stock.py` | AgentOS API for founders and investors |
| `06_vesting_schedule.py` | Create and manage vesting schedules |
| `07_multisig_owner.py` | Multi-sig owner transaction flow |
| `08_transfer_webhooks.py` | Transfer event webhook delivery |
| `09_equity_report.py` | Equity reports, dilution modeling, compliance export |
| `10_webhook_daemon.py` | Continuous webhook polling daemon |
| `menubar.py` | macOS menu bar app (requires `pip install rumps`) |
| `cli.py` | macOS/Linux CLI for cap table operations |
| `sample_cap_table.csv` | Sample CSV cap table for import |
| `contracts/StartupStockToken.sol` | ERC-20 startup equity smart contract |
| `contracts/VestingVault.sol` | Linear vesting vault with cliff |
| `contracts/StartupStockMultiSig.sol` | M-of-N multisig for privileged operations |

## Security

- Private keys stay in environment variables, never in code or agent responses
- Cap table entries are checksum-validated before sync
- Drift detection flags on-chain balances that exceed the cap table
- Automatic retries with exponential backoff for transient RPC failures
- Contract supports pausing for emergency stops

## Architecture

```
Local Cap Table (SQLite)
        |
        v
  CapTableSyncEngine  ----->  EVM Blockchain
        |                    (StartupStockToken)
        v
  StartupStockTools  <----  Agno Agent / CLI
```
