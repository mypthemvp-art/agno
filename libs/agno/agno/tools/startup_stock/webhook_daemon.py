"""Continuous transfer event webhook daemon."""

from __future__ import annotations

import signal
import time
from typing import Any, Callable, Dict, Optional

from agno.tools.startup_stock.webhooks import TransferWebhookWatcher
from agno.utils.log import log_debug, log_info


class TransferWebhookDaemon:
    """Background daemon that polls Transfer events and delivers webhooks."""

    def __init__(
        self,
        watcher: TransferWebhookWatcher,
        poll_interval_seconds: float = 15.0,
        lookback_blocks: int = 50,
        on_poll: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.watcher = watcher
        self.poll_interval_seconds = poll_interval_seconds
        self.lookback_blocks = lookback_blocks
        self.on_poll = on_poll
        self._running = False

    def run_once(self) -> Dict[str, Any]:
        result = self.watcher.poll_and_deliver(lookback_blocks=self.lookback_blocks)
        if self.on_poll:
            self.on_poll(result)
        return result

    def run(self, max_iterations: Optional[int] = None) -> None:
        """Run the daemon loop. Set max_iterations for testing."""
        self._running = True
        iterations = 0

        def handle_signal(signum, frame) -> None:
            log_info(f"Webhook daemon received signal {signum}, shutting down")
            self._running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        log_info(
            f"Webhook daemon started: interval={self.poll_interval_seconds}s lookback={self.lookback_blocks} blocks"
        )

        while self._running:
            try:
                result = self.run_once()
                log_debug(
                    f"Webhook poll: found={result.get('events_found', 0)} "
                    f"delivered={result.get('delivered', 0)} failed={result.get('failed', 0)}"
                )
            except Exception as e:
                log_debug(f"Webhook poll error: {e}")

            iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                break

            if self._running:
                time.sleep(self.poll_interval_seconds)

        log_info("Webhook daemon stopped")

    def stop(self) -> None:
        self._running = False
