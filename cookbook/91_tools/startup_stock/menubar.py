#!/usr/bin/env python3
"""Startup Stock Menu Bar App for macOS.

Native macOS menu bar app for monitoring tokenized startup equity.
Requires macOS and rumps: pip install rumps

Environment:
    EVM_RPC_URL
    STARTUP_STOCK_CONTRACT_ADDRESS
    EVM_PRIVATE_KEY (optional, for cap table write ops)

Run:
    python menubar.py
"""

from __future__ import annotations

import json
import os
import platform
import sys
import threading


def _require_macos() -> None:
    if platform.system() != "Darwin":
        print("This menu bar app requires macOS.")
        sys.exit(1)


def _require_rumps():
    try:
        import rumps
    except ImportError:
        print("Install rumps: pip install rumps")
        sys.exit(1)
    return rumps


_require_macos()
rumps = _require_rumps()


class StartupStockMenuBarApp(rumps.App):
    def __init__(self) -> None:
        super().__init__("Startup Stock", quit_button="Quit")
        self.token_item = rumps.MenuItem("Token: loading...")
        self.cap_table_item = rumps.MenuItem("Cap table: --")
        self.menu = [
            self.token_item,
            self.cap_table_item,
            None,
            rumps.MenuItem("Refresh", callback=self.refresh),
            rumps.MenuItem("Sync Preview", callback=self.sync_preview),
        ]
        self.refresh(None)

    def _get_reader(self):
        from agno.tools.startup_stock import StartupStockReader

        return StartupStockReader()

    def _get_tools(self):
        from agno.tools.startup_stock import StartupStockTools

        return StartupStockTools(
            enable_read=False, enable_write=False, enable_sync=True
        )

    def _run_async(self, fn, callback) -> None:
        def worker() -> None:
            try:
                result = fn()
                callback(result)
            except Exception as e:
                callback({"error": str(e)})

        threading.Thread(target=worker, daemon=True).start()

    def refresh(self, _) -> None:
        if not os.getenv("STARTUP_STOCK_CONTRACT_ADDRESS"):
            rumps.alert("Missing config", "Set STARTUP_STOCK_CONTRACT_ADDRESS")
            return

        def on_token(result: str) -> None:
            info = json.loads(result)

            def update() -> None:
                if "error" in info:
                    self.token_item.title = "Token: error"
                    rumps.notification(
                        "Startup Stock", "Token info failed", info["error"]
                    )
                else:
                    symbol = info.get("symbol", "?")
                    supply = info.get("total_supply_shares", 0)
                    self.token_item.title = f"Token: {symbol} ({supply:,.0f} shares)"

            rumps.call_on_main_thread(update)

        def on_cap_table(result: str) -> None:
            data = json.loads(result)

            def update() -> None:
                if "error" in data:
                    self.cap_table_item.title = "Cap table: error"
                else:
                    count = data.get("count", 0)
                    self.cap_table_item.title = f"Cap table: {count} investors"

            rumps.call_on_main_thread(update)

        reader = self._get_reader()
        self._run_async(reader.get_token_info, on_token)

        if os.getenv("EVM_PRIVATE_KEY"):
            tools = self._get_tools()
            self._run_async(tools.list_cap_table, on_cap_table)

    def sync_preview(self, _) -> None:
        if not os.getenv("EVM_PRIVATE_KEY"):
            rumps.alert("Private key required", "Set EVM_PRIVATE_KEY for sync preview")
            return

        def on_sync(result: str) -> None:
            data = json.loads(result)

            def notify() -> None:
                if "error" in data:
                    rumps.notification("Sync Preview", "Error", data["error"])
                else:
                    skipped = data.get("skipped", 0)
                    synced = data.get("synced", 0)
                    rumps.notification(
                        "Sync Preview",
                        "Dry run complete",
                        f"Would sync: {skipped} pending, {synced} already synced",
                    )

            rumps.call_on_main_thread(notify)

        tools = self._get_tools()
        self._run_async(lambda: tools.sync_cap_table(dry_run=True), on_sync)


if __name__ == "__main__":
    StartupStockMenuBarApp().run()
