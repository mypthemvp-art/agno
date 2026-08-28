"""Continuous cap table sync daemon with dry-run and live modes."""

from __future__ import annotations

import signal
import time
from typing import Any, Callable, Dict, Optional

from agno.utils.log import log_debug, log_info


class CapTableSyncDaemon:
    """Background daemon that periodically syncs the cap table to the blockchain."""

    def __init__(
        self,
        sync_fn: Callable[[bool], Dict[str, Any]],
        poll_interval_seconds: float = 300.0,
        dry_run: bool = True,
        on_sync: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.sync_fn = sync_fn
        self.poll_interval_seconds = poll_interval_seconds
        self.dry_run = dry_run
        self.on_sync = on_sync
        self._running = False

    def run_once(self) -> Dict[str, Any]:
        result = self.sync_fn(self.dry_run)
        if self.on_sync:
            self.on_sync(result)
        return result

    def run(self, max_iterations: Optional[int] = None) -> None:
        """Run the daemon loop. Set max_iterations for testing."""
        self._running = True
        iterations = 0
        mode = "DRY RUN" if self.dry_run else "LIVE"

        def handle_signal(signum, frame) -> None:
            log_info(f"Sync daemon received signal {signum}, shutting down")
            self._running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        log_info(f"Sync daemon started: mode={mode} interval={self.poll_interval_seconds}s")

        while self._running:
            try:
                result = self.run_once()
                log_debug(
                    f"Sync poll: synced={result.get('synced', 0)} "
                    f"failed={result.get('failed', 0)} drifted={result.get('drifted', 0)}"
                )
            except Exception as e:
                log_debug(f"Sync poll error: {e}")

            iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                break

            if self._running:
                time.sleep(self.poll_interval_seconds)

        log_info("Sync daemon stopped")

    def stop(self) -> None:
        self._running = False
