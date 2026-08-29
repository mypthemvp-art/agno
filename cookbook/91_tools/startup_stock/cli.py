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
    python cli.py report
    python cli.py export --file report.json
    python cli.py dilution --name "Series A" --new-shares 20000
    python cli.py vesting create --wallet 0x742d... --shares 10000
    python cli.py webhooks poll
    python cli.py webhooks daemon --iterations 3
    python cli.py audit
    python cli.py audit record --action board_approval --detail "409A signed"
    python cli.py health
    python cli.py snapshot create --label "pre-series-a"
    python cli.py sync-daemon --iterations 3
    python cli.py pool set --shares 100000
    python cli.py pool grant --name Eve --shares 5000 --strike 0.50
    python cli.py valuation record --fmv 0.50 --firm "Acme Valuation"
    python cli.py safe add --name SeedFund --amount 250000 --cap 5000000 --discount 0.20
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


def _load_advanced(require_contract: bool = True):
    from agno.tools.startup_stock import StartupStockAdvancedTools

    if require_contract and not os.getenv("STARTUP_STOCK_CONTRACT_ADDRESS"):
        print(
            "Error: Set STARTUP_STOCK_CONTRACT_ADDRESS environment variable.",
            file=sys.stderr,
        )
        sys.exit(1)

    return StartupStockAdvancedTools()


def _load_reader():
    from agno.tools.startup_stock import StartupStockReader

    if not os.getenv("STARTUP_STOCK_CONTRACT_ADDRESS") or not os.getenv("EVM_RPC_URL"):
        print(
            "Error: Set STARTUP_STOCK_CONTRACT_ADDRESS and EVM_RPC_URL.",
            file=sys.stderr,
        )
        sys.exit(1)

    return StartupStockReader()


def _print_error(result: dict) -> None:
    print(f"Error: {result['error']}", file=sys.stderr)
    sys.exit(1)


def cmd_info(args: argparse.Namespace) -> None:
    tools = _load_tools()
    print(json.dumps(json.loads(tools.get_token_info()), indent=2))


def cmd_add(args: argparse.Namespace) -> None:
    tools = _load_tools(require_contract=False)
    result = json.loads(tools.add_investor(args.name, args.wallet, args.shares))
    if "error" in result:
        _print_error(result)
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
        _print_error(result)
    print(f"Wallet: {result['wallet_address']}")
    print(f"Shares: {result['shares']:,.4f}")


def cmd_import(args: argparse.Namespace) -> None:
    tools = _load_tools(require_contract=False)
    result = json.loads(tools.import_cap_table(args.file))
    if "error" in result:
        _print_error(result)
    print(f"Imported {result['imported']} investors from {result['file_path']}")


def cmd_reconcile(args: argparse.Namespace) -> None:
    tools = _load_tools()
    result = json.loads(tools.reconcile_cap_table())
    if "error" in result:
        _print_error(result)
    print(f"Synced:  {result.get('synced', 0)}")
    print(f"Pending: {result.get('pending', 0)}")
    print(f"Drifted: {result.get('drifted', 0)}")
    print(f"Failed:  {result.get('failed', 0)}")


def cmd_deploy(args: argparse.Namespace) -> None:
    tools = _load_tools(require_contract=False)
    result = json.loads(tools.deploy_token(args.name, args.symbol, args.max_shares))
    if "error" in result:
        _print_error(result)
    print(f"Deployed to: {result['contract_address']}")
    print(f"export STARTUP_STOCK_CONTRACT_ADDRESS={result['contract_address']}")


def cmd_deploy_vault(args: argparse.Namespace) -> None:
    tools = _load_advanced()
    result = json.loads(tools.deploy_vesting_vault(token_address=args.token))
    if "error" in result:
        _print_error(result)
    print(f"Deployed VestingVault to: {result['contract_address']}")
    print(f"export STARTUP_STOCK_VESTING_VAULT={result['contract_address']}")


def cmd_deploy_multisig(args: argparse.Namespace) -> None:
    tools = _load_advanced()
    result = json.loads(tools.deploy_multisig(args.owners, args.required))
    if "error" in result:
        _print_error(result)
    print(f"Deployed MultiSig to: {result['contract_address']}")
    print(f"export STARTUP_STOCK_MULTISIG_ADDRESS={result['contract_address']}")


def cmd_sync(args: argparse.Namespace) -> None:
    tools = _load_tools()
    dry_run = not args.live
    result = json.loads(tools.sync_cap_table(dry_run=dry_run))
    if "error" in result:
        _print_error(result)

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


def cmd_report(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(tools.generate_equity_report())
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_export(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(tools.export_compliance_report(args.file, fmt=args.format))
    if "error" in result:
        _print_error(result)
    print(
        f"Exported {result['investor_count']} investors to {result['file_path']} ({result['format']})"
    )


def cmd_dilution(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(
        tools.calculate_dilution(
            scenario_name=args.name,
            new_shares=args.new_shares,
            option_pool_increase=args.option_pool,
        )
    )
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_vesting_create(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(
        tools.create_vesting_schedule(
            beneficiary=args.wallet,
            total_shares=args.shares,
            cliff_days=args.cliff_days,
            vesting_days=args.vesting_days,
        )
    )
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_vesting_get(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(tools.get_vesting_schedule(args.wallet))
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_vesting_list(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(tools.list_vesting_schedules())
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_vesting_release(args: argparse.Namespace) -> None:
    tools = _load_advanced()
    result = json.loads(tools.release_vested_shares(args.wallet))
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_multisig_info(args: argparse.Namespace) -> None:
    tools = _load_advanced()
    result = json.loads(tools.get_multisig_info())
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_webhooks_poll(args: argparse.Namespace) -> None:
    tools = _load_advanced()
    result = json.loads(tools.poll_transfer_webhooks(lookback_blocks=args.lookback))
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_webhooks_daemon(args: argparse.Namespace) -> None:
    from agno.tools.startup_stock.webhook_daemon import TransferWebhookDaemon

    tools = _load_advanced()
    if not tools.webhook_url:
        print("Error: Set STARTUP_STOCK_WEBHOOK_URL.", file=sys.stderr)
        sys.exit(1)

    daemon = TransferWebhookDaemon(
        watcher=tools._build_webhook_watcher(),
        poll_interval_seconds=args.interval,
        lookback_blocks=args.lookback,
        on_poll=lambda r: print(json.dumps(r)),
    )
    daemon.run(max_iterations=args.iterations)


def cmd_audit(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(tools.get_audit_log(limit=args.limit, action=args.action))
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_audit_log(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(
        tools.log_audit_event(
            action=args.action, target=args.target, detail=args.detail
        )
    )
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_health(args: argparse.Namespace) -> None:
    tools = _load_advanced()
    result = json.loads(tools.run_health_check())
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_snapshot_create(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(tools.create_cap_table_snapshot(args.label))
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_snapshot_list(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(tools.list_cap_table_snapshots(limit=args.limit))
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_snapshot_compare(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(
        tools.compare_cap_table_snapshots(args.snapshot_a, args.snapshot_b)
    )
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_sync_daemon(args: argparse.Namespace) -> None:
    from agno.tools.startup_stock.sync_daemon import CapTableSyncDaemon

    tools = _load_advanced()

    def sync_fn(dry_run: bool) -> dict:
        return json.loads(tools.sync_cap_table(dry_run=dry_run))

    daemon = CapTableSyncDaemon(
        sync_fn=sync_fn,
        poll_interval_seconds=args.interval,
        dry_run=not args.live,
        on_sync=lambda r: print(json.dumps(r)),
    )
    daemon.run(max_iterations=args.iterations)


def cmd_pool_set(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(tools.set_option_pool(args.shares))
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_pool_get(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(tools.get_option_pool())
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_pool_grant(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(
        tools.grant_options(
            recipient_name=args.name,
            shares=args.shares,
            strike_price=args.strike,
            recipient_wallet=args.wallet,
            cliff_days=args.cliff_days,
            vesting_days=args.vesting_days,
            notes=args.notes,
        )
    )
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_pool_list(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(tools.list_option_grants(status=args.status))
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_pool_exercise(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(tools.exercise_options(args.grant_id, args.shares))
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_valuation_record(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(
        tools.record_409a_valuation(
            fair_market_value=args.fmv,
            firm=args.firm,
            valuation_date=args.date,
            methodology=args.methodology,
            share_class=args.share_class,
            validity_days=args.validity_days,
            notes=args.notes,
        )
    )
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_valuation_latest(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(tools.get_latest_409a(share_class=args.share_class))
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_valuation_status(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(tools.check_409a_status(share_class=args.share_class))
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_safe_add(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(
        tools.add_safe_instrument(
            investor_name=args.name,
            investment_amount=args.amount,
            instrument_type=args.type,
            valuation_cap=args.cap,
            discount_rate=args.discount,
            notes=args.notes,
        )
    )
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_safe_list(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(tools.list_safe_instruments(status=args.status))
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_safe_preview(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(
        tools.preview_safe_conversion(
            instrument_id=args.instrument_id,
            priced_round_price_per_share=args.price,
            pre_money_shares=args.pre_money_shares,
        )
    )
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


def cmd_safe_convert(args: argparse.Namespace) -> None:
    tools = _load_advanced(require_contract=False)
    result = json.loads(
        tools.convert_safe_instrument(
            instrument_id=args.instrument_id,
            priced_round_price_per_share=args.price,
            pre_money_shares=args.pre_money_shares,
        )
    )
    if "error" in result:
        _print_error(result)
    print(json.dumps(result, indent=2))


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

    deploy_vault_parser = subparsers.add_parser(
        "deploy-vault", help="Deploy VestingVault (requires forge)"
    )
    deploy_vault_parser.add_argument(
        "--token", help="Token address (defaults to STARTUP_STOCK_CONTRACT_ADDRESS)"
    )

    deploy_multisig_parser = subparsers.add_parser(
        "deploy-multisig", help="Deploy StartupStockMultiSig (requires forge)"
    )
    deploy_multisig_parser.add_argument(
        "--owners", required=True, help="Comma-separated owner addresses"
    )
    deploy_multisig_parser.add_argument(
        "--required", type=int, required=True, help="Required confirmations (M)"
    )

    sync_parser = subparsers.add_parser("sync", help="Sync cap table to blockchain")
    sync_parser.add_argument(
        "--dry-run", action="store_true", default=True, help="Preview only (default)"
    )
    sync_parser.add_argument(
        "--live", action="store_true", help="Execute on-chain minting"
    )

    subparsers.add_parser("report", help="Generate equity report")

    export_parser = subparsers.add_parser("export", help="Export compliance report")
    export_parser.add_argument("--file", required=True, help="Output file path")
    export_parser.add_argument(
        "--format", choices=["json", "csv"], default="json", help="Export format"
    )

    dilution_parser = subparsers.add_parser("dilution", help="Model ownership dilution")
    dilution_parser.add_argument("--name", required=True, help="Scenario name")
    dilution_parser.add_argument(
        "--new-shares", type=float, required=True, help="New shares issued"
    )
    dilution_parser.add_argument(
        "--option-pool", type=float, default=0.0, help="Option pool increase"
    )

    vesting_parser = subparsers.add_parser("vesting", help="Vesting schedule commands")
    vesting_sub = vesting_parser.add_subparsers(dest="vesting_command", required=True)

    vesting_create = vesting_sub.add_parser("create", help="Create vesting schedule")
    vesting_create.add_argument("--wallet", required=True)
    vesting_create.add_argument("--shares", type=float, required=True)
    vesting_create.add_argument("--cliff-days", type=int, default=365)
    vesting_create.add_argument("--vesting-days", type=int, default=1460)

    vesting_get = vesting_sub.add_parser("get", help="Get vesting schedule")
    vesting_get.add_argument("--wallet", required=True)

    vesting_sub.add_parser("list", help="List vesting schedules")

    vesting_release = vesting_sub.add_parser("release", help="Release vested shares")
    vesting_release.add_argument("--wallet", required=True)

    multisig_parser = subparsers.add_parser("multisig", help="Multi-sig commands")
    multisig_sub = multisig_parser.add_subparsers(
        dest="multisig_command", required=True
    )
    multisig_sub.add_parser("info", help="Show multi-sig configuration")

    webhooks_parser = subparsers.add_parser(
        "webhooks", help="Transfer webhook commands"
    )
    webhooks_sub = webhooks_parser.add_subparsers(
        dest="webhooks_command", required=True
    )

    webhooks_poll = webhooks_sub.add_parser(
        "poll", help="Poll and deliver webhooks once"
    )
    webhooks_poll.add_argument("--lookback", type=int, default=100)

    webhooks_daemon = webhooks_sub.add_parser("daemon", help="Run webhook daemon")
    webhooks_daemon.add_argument("--iterations", type=int, default=None)
    webhooks_daemon.add_argument("--interval", type=float, default=15.0)
    webhooks_daemon.add_argument("--lookback", type=int, default=50)

    audit_parser = subparsers.add_parser("audit", help="Audit log commands")
    audit_sub = audit_parser.add_subparsers(dest="audit_command", required=True)

    audit_list = audit_sub.add_parser("list", help="List audit log entries")
    audit_list.add_argument("--limit", type=int, default=50)
    audit_list.add_argument("--action", help="Filter by action name")

    audit_record = audit_sub.add_parser("record", help="Record a manual audit event")
    audit_record.add_argument("--action", required=True)
    audit_record.add_argument("--target", help="Target wallet or resource")
    audit_record.add_argument("--detail", help="Optional detail text")

    subparsers.add_parser("health", help="Run infrastructure health checks")

    snapshot_parser = subparsers.add_parser(
        "snapshot", help="Cap table snapshot commands"
    )
    snapshot_sub = snapshot_parser.add_subparsers(
        dest="snapshot_command", required=True
    )

    snapshot_create = snapshot_sub.add_parser("create", help="Create a snapshot")
    snapshot_create.add_argument("--label", required=True, help="Snapshot label")

    snapshot_list = snapshot_sub.add_parser("list", help="List snapshots")
    snapshot_list.add_argument("--limit", type=int, default=20)

    snapshot_compare = snapshot_sub.add_parser("compare", help="Compare two snapshots")
    snapshot_compare.add_argument("--snapshot-a", required=True)
    snapshot_compare.add_argument("--snapshot-b", required=True)

    sync_daemon_parser = subparsers.add_parser(
        "sync-daemon", help="Run cap table sync daemon"
    )
    sync_daemon_parser.add_argument("--iterations", type=int, default=None)
    sync_daemon_parser.add_argument("--interval", type=float, default=300.0)
    sync_daemon_parser.add_argument(
        "--live", action="store_true", help="Live sync (default dry-run)"
    )

    pool_parser = subparsers.add_parser("pool", help="Option pool commands")
    pool_sub = pool_parser.add_subparsers(dest="pool_command", required=True)

    pool_set = pool_sub.add_parser("set", help="Set authorized option pool size")
    pool_set.add_argument("--shares", type=float, required=True)

    pool_sub.add_parser("get", help="Show option pool summary")

    pool_grant = pool_sub.add_parser("grant", help="Grant options from the pool")
    pool_grant.add_argument("--name", required=True)
    pool_grant.add_argument("--shares", type=float, required=True)
    pool_grant.add_argument("--strike", type=float, required=True)
    pool_grant.add_argument("--wallet", default=None)
    pool_grant.add_argument("--cliff-days", type=int, default=365)
    pool_grant.add_argument("--vesting-days", type=int, default=1460)
    pool_grant.add_argument("--notes", default=None)

    pool_list = pool_sub.add_parser("list", help="List option grants")
    pool_list.add_argument("--status", default=None)

    pool_exercise = pool_sub.add_parser("exercise", help="Exercise vested options")
    pool_exercise.add_argument("--grant-id", required=True)
    pool_exercise.add_argument("--shares", type=float, required=True)

    valuation_parser = subparsers.add_parser(
        "valuation", help="409A valuation commands"
    )
    valuation_sub = valuation_parser.add_subparsers(
        dest="valuation_command", required=True
    )

    valuation_record = valuation_sub.add_parser(
        "record", help="Record a 409A valuation"
    )
    valuation_record.add_argument("--fmv", type=float, required=True)
    valuation_record.add_argument("--firm", required=True)
    valuation_record.add_argument("--date", default=None)
    valuation_record.add_argument("--methodology", default="market_approach")
    valuation_record.add_argument("--share-class", default="common")
    valuation_record.add_argument("--validity-days", type=int, default=365)
    valuation_record.add_argument("--notes", default=None)

    valuation_latest = valuation_sub.add_parser("latest", help="Show latest 409A")
    valuation_latest.add_argument("--share-class", default="common")

    valuation_status = valuation_sub.add_parser("status", help="Check 409A validity")
    valuation_status.add_argument("--share-class", default="common")

    safe_parser = subparsers.add_parser("safe", help="SAFE/SAFT instrument commands")
    safe_sub = safe_parser.add_subparsers(dest="safe_command", required=True)

    safe_add = safe_sub.add_parser("add", help="Add a SAFE or SAFT")
    safe_add.add_argument("--name", required=True)
    safe_add.add_argument("--amount", type=float, required=True)
    safe_add.add_argument("--type", default="safe", choices=["safe", "saft"])
    safe_add.add_argument("--cap", type=float, default=None)
    safe_add.add_argument("--discount", type=float, default=0.0)
    safe_add.add_argument("--notes", default=None)

    safe_list = safe_sub.add_parser("list", help="List SAFE/SAFT instruments")
    safe_list.add_argument("--status", default=None)

    safe_preview = safe_sub.add_parser("preview", help="Preview SAFE conversion")
    safe_preview.add_argument("--instrument-id", required=True)
    safe_preview.add_argument("--price", type=float, required=True)
    safe_preview.add_argument("--pre-money-shares", type=float, default=None)

    safe_convert = safe_sub.add_parser("convert", help="Convert a SAFE/SAFT")
    safe_convert.add_argument("--instrument-id", required=True)
    safe_convert.add_argument("--price", type=float, required=True)
    safe_convert.add_argument("--pre-money-shares", type=float, default=None)

    args = parser.parse_args()

    if args.command == "vesting":
        vesting_commands = {
            "create": cmd_vesting_create,
            "get": cmd_vesting_get,
            "list": cmd_vesting_list,
            "release": cmd_vesting_release,
        }
        vesting_commands[args.vesting_command](args)
        return

    if args.command == "multisig":
        if args.multisig_command == "info":
            cmd_multisig_info(args)
        return

    if args.command == "webhooks":
        if args.webhooks_command == "poll":
            cmd_webhooks_poll(args)
        elif args.webhooks_command == "daemon":
            cmd_webhooks_daemon(args)
        return

    if args.command == "audit":
        if args.audit_command == "list":
            cmd_audit(args)
        elif args.audit_command == "record":
            cmd_audit_log(args)
        return

    if args.command == "snapshot":
        if args.snapshot_command == "create":
            cmd_snapshot_create(args)
        elif args.snapshot_command == "list":
            cmd_snapshot_list(args)
        elif args.snapshot_command == "compare":
            cmd_snapshot_compare(args)
        return

    if args.command == "sync-daemon":
        cmd_sync_daemon(args)
        return

    if args.command == "pool":
        pool_commands = {
            "set": cmd_pool_set,
            "get": cmd_pool_get,
            "grant": cmd_pool_grant,
            "list": cmd_pool_list,
            "exercise": cmd_pool_exercise,
        }
        pool_commands[args.pool_command](args)
        return

    if args.command == "valuation":
        valuation_commands = {
            "record": cmd_valuation_record,
            "latest": cmd_valuation_latest,
            "status": cmd_valuation_status,
        }
        valuation_commands[args.valuation_command](args)
        return

    if args.command == "safe":
        safe_commands = {
            "add": cmd_safe_add,
            "list": cmd_safe_list,
            "preview": cmd_safe_preview,
            "convert": cmd_safe_convert,
        }
        safe_commands[args.safe_command](args)
        return

    commands = {
        "info": cmd_info,
        "add": cmd_add,
        "list": cmd_list,
        "balance": cmd_balance,
        "import": cmd_import,
        "reconcile": cmd_reconcile,
        "deploy": cmd_deploy,
        "deploy-vault": cmd_deploy_vault,
        "deploy-multisig": cmd_deploy_multisig,
        "sync": cmd_sync,
        "report": cmd_report,
        "export": cmd_export,
        "dilution": cmd_dilution,
        "health": cmd_health,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
