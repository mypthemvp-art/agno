#!/usr/bin/env python3
"""Startup Stock CLI - macOS/Linux command-line cap table manager.

High-security, fast-sync CLI for startup equity tokenization.

Usage:
    python cli.py info
    python cli.py add --name Alice --wallet 0x742d... --shares 10000
    python cli.py import --file sample_cap_table.csv
    python cli.py list
    python cli.py balance --wallet 0x742d...
    python cli.py reconcile
    python cli.py sync --dry-run
    python cli.py sync --live
    python cli.py deploy --name "Acme Startup" --symbol ACME --max-shares 1000000
"""

import argparse
import json
import os
import sys


def _load_tools(require_contract: bool = True):
    from agno.tools.startup_stock import StartupStockTools

    if require_contract and not os.getenv("STARTUP_STOCK_CONTRACT_ADDRESS"):
        print(
            "Error: Set STARTUP_STOCK_CONTRACT_ADDRESS environment variable.",
            file=sys.stderr,
        )
        print("See README.md for deployment instructions.", file=sys.stderr)
        sys.exit(1)

    return StartupStockTools()


def _load_reader():
    from agno.tools.startup_stock import StartupStockReader

    if not os.getenv("STARTUP_STOCK_CONTRACT_ADDRESS") or not os.getenv("EVM_RPC_URL"):
        print(
            "Error: Set STARTUP_STOCK_CONTRACT_ADDRESS and EVM_RPC_URL.",
            file=sys.stderr,
        )
        sys.exit(1)

    return StartupStockReader()


def cmd_info(args: argparse.Namespace) -> None:
    tools = _load_tools()
    print(json.dumps(json.loads(tools.get_token_info()), indent=2))


def cmd_add(args: argparse.Namespace) -> None:
    tools = _load_tools(require_contract=False)
    result = json.loads(tools.add_investor(args.name, args.wallet, args.shares))
    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
    print(
        f"Added {result['investor_name']}: {result['shares']} shares ({result['status']})"
    )


def cmd_list(args: argparse.Namespace) -> None:
    tools = _load_tools(require_contract=False)
    cap_table = json.loads(tools.list_cap_table())
    entries = cap_table.get("entries", [])
    if not entries:
        print("Cap table is empty.")
        return
    print(f"{'Investor':<25} {'Wallet':<44} {'Shares':>12} {'Status':<10}")
    print("-" * 95)
    for entry in entries:
        print(
            f"{entry['investor_name']:<25} "
            f"{entry['wallet_address']:<44} "
            f"{entry['shares']:>12,.2f} "
            f"{entry['status']:<10}"
        )


def cmd_balance(args: argparse.Namespace) -> None:
    if args.readonly:
        reader = _load_reader()
        result = json.loads(reader.get_investor_balance(args.wallet))
    else:
        tools = _load_tools()
        result = json.loads(tools.get_investor_balance(args.wallet))
    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
    print(f"Wallet: {result['wallet_address']}")
    print(f"Shares: {result['shares']:,.4f}")


def cmd_import(args: argparse.Namespace) -> None:
    tools = _load_tools(require_contract=False)
    result = json.loads(tools.import_cap_table(args.file))
    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
    print(f"Imported {result['imported']} investors from {result['file_path']}")


def cmd_reconcile(args: argparse.Namespace) -> None:
    tools = _load_tools()
    result = json.loads(tools.reconcile_cap_table())
    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
    print(f"Synced:  {result.get('synced', 0)}")
    print(f"Pending: {result.get('pending', 0)}")
    print(f"Drifted: {result.get('drifted', 0)}")
    print(f"Failed:  {result.get('failed', 0)}")


def cmd_deploy(args: argparse.Namespace) -> None:
    tools = _load_tools(require_contract=False)
    result = json.loads(tools.deploy_token(args.name, args.symbol, args.max_shares))
    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
    print(f"Deployed to: {result['contract_address']}")
    print(f"export STARTUP_STOCK_CONTRACT_ADDRESS={result['contract_address']}")


def cmd_sync(args: argparse.Namespace) -> None:
    tools = _load_tools()
    dry_run = not args.live
    result = json.loads(tools.sync_cap_table(dry_run=dry_run))
    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"Sync ({mode}) - run_id: {result['run_id']}")
    print(f"  Synced:  {result['synced']}")
    print(f"  Failed:  {result['failed']}")
    print(f"  Drifted: {result['drifted']}")
    print(f"  Skipped: {result['skipped']}")

    for entry in result.get("entries", []):
        status = entry.get("status", "unknown")
        name = entry.get("investor_name", entry.get("wallet_address", "?"))
        extra = ""
        if entry.get("tx_hash"):
            extra = f" tx={entry['tx_hash']}"
        elif entry.get("mint_delta_wei"):
            extra = f" would_mint={entry['mint_delta_wei']} wei"
        print(f"  {name}: {status}{extra}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Startup Stock CLI - tokenized equity cap table manager",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("info", help="Show token info from blockchain")

    add_parser = subparsers.add_parser("add", help="Add investor to cap table")
    add_parser.add_argument("--name", required=True, help="Investor name")
    add_parser.add_argument("--wallet", required=True, help="Wallet address (0x...)")
    add_parser.add_argument(
        "--shares", type=float, required=True, help="Number of shares"
    )

    subparsers.add_parser("list", help="List cap table entries")

    balance_parser = subparsers.add_parser("balance", help="Check on-chain balance")
    balance_parser.add_argument(
        "--wallet", required=True, help="Wallet address (0x...)"
    )
    balance_parser.add_argument(
        "--readonly", action="store_true", help="Read-only mode (no private key needed)"
    )

    import_parser = subparsers.add_parser(
        "import", help="Import cap table from CSV/JSON"
    )
    import_parser.add_argument("--file", required=True, help="Path to cap table file")

    subparsers.add_parser(
        "reconcile", help="Reconcile cap table with on-chain balances"
    )

    deploy_parser = subparsers.add_parser(
        "deploy", help="Deploy StartupStockToken (requires forge)"
    )
    deploy_parser.add_argument("--name", required=True, help="Token name")
    deploy_parser.add_argument("--symbol", required=True, help="Token symbol")
    deploy_parser.add_argument(
        "--max-shares", type=float, required=True, help="Max supply in shares"
    )

    sync_parser = subparsers.add_parser("sync", help="Sync cap table to blockchain")
    sync_parser.add_argument(
        "--dry-run", action="store_true", default=True, help="Preview only (default)"
    )
    sync_parser.add_argument(
        "--live", action="store_true", help="Execute on-chain minting"
    )

    args = parser.parse_args()
    commands = {
        "info": cmd_info,
        "add": cmd_add,
        "list": cmd_list,
        "balance": cmd_balance,
        "import": cmd_import,
        "reconcile": cmd_reconcile,
        "deploy": cmd_deploy,
        "sync": cmd_sync,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
