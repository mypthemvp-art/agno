"""Transfer event webhook delivery for startup stock tokens."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib import request as urllib_request
from urllib.error import URLError

from agno.tools.startup_stock.base import wei_to_shares
from agno.utils.log import log_debug, log_error

try:
    import web3  # noqa: F401
except ImportError:
    raise ImportError("`web3` not installed. Please install using `pip install agno[evm]")


@dataclass
class TransferEvent:
    event_type: str
    tx_hash: str
    block_number: int
    from_address: str
    to_address: str
    value_wei: int
    log_index: int

    @property
    def shares(self) -> float:
        return wei_to_shares(self.value_wei)

    @property
    def event_id(self) -> str:
        payload = f"{self.tx_hash}:{self.log_index}"
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    def to_payload(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "tx_hash": self.tx_hash,
            "block_number": self.block_number,
            "from_address": self.from_address.lower(),
            "to_address": self.to_address.lower(),
            "value_wei": self.value_wei,
            "shares": self.shares,
        }


class WebhookDeliveryStore:
    """Tracks delivered webhook events to prevent duplicates."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_deliveries (
                    event_id TEXT PRIMARY KEY,
                    tx_hash TEXT NOT NULL,
                    webhook_url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_code INTEGER,
                    error TEXT,
                    delivered_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_cursor (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    last_block INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute("INSERT OR IGNORE INTO webhook_cursor (id, last_block) VALUES (1, 0)")

    def is_delivered(self, event_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM webhook_deliveries WHERE event_id = ? AND status = 'delivered'",
                (event_id,),
            ).fetchone()
        return row is not None

    def record_delivery(
        self,
        event_id: str,
        tx_hash: str,
        webhook_url: str,
        status: str,
        response_code: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO webhook_deliveries
                (event_id, tx_hash, webhook_url, status, response_code, error, delivered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    tx_hash,
                    webhook_url,
                    status,
                    response_code,
                    error,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def get_last_block(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT last_block FROM webhook_cursor WHERE id = 1").fetchone()
        return int(row["last_block"]) if row else 0

    def set_last_block(self, block_number: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE webhook_cursor SET last_block = ? WHERE id = 1", (block_number,))


class TransferWebhookWatcher:
    """Poll Transfer/Mint events and POST to webhook URLs with retry."""

    def __init__(
        self,
        contract,
        web3_client,
        webhook_url: str,
        store: WebhookDeliveryStore,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
        http_post_fn: Optional[Callable[[str, Dict[str, Any]], tuple[int, str]]] = None,
    ):
        self.contract = contract
        self.web3_client = web3_client
        self.webhook_url = webhook_url
        self.store = store
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.http_post_fn = http_post_fn or self._default_http_post

    def _default_http_post(self, url: str, payload: Dict[str, Any]) -> tuple[int, str]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")

    def fetch_events(self, from_block: int, to_block: str | int = "latest") -> List[TransferEvent]:
        transfer_filter = self.contract.events.Transfer.create_filter(
            fromBlock=from_block,
            toBlock=to_block,
        )
        events: List[TransferEvent] = []
        for entry in transfer_filter.get_all_entries():
            args = entry["args"]
            from_addr = args.get("from", args.get("src", "0x0"))
            to_addr = args.get("to", args.get("dst", "0x0"))
            value = int(args.get("value", 0))
            event_type = "mint" if from_addr == "0x" + "0" * 40 else "transfer"
            if to_addr == "0x" + "0" * 40:
                event_type = "burn"
            events.append(
                TransferEvent(
                    event_type=event_type,
                    tx_hash=entry["transactionHash"].hex(),
                    block_number=entry["blockNumber"],
                    from_address=from_addr,
                    to_address=to_addr,
                    value_wei=value,
                    log_index=entry["logIndex"],
                )
            )
        return events

    def deliver_event(self, event: TransferEvent) -> Dict[str, Any]:
        if self.store.is_delivered(event.event_id):
            return {"event_id": event.event_id, "status": "skipped", "reason": "already_delivered"}

        payload = event.to_payload()
        last_error = "unknown error"
        for attempt in range(1, self.max_retries + 1):
            try:
                status_code, _ = self.http_post_fn(self.webhook_url, payload)
                if 200 <= status_code < 300:
                    self.store.record_delivery(
                        event.event_id, event.tx_hash, self.webhook_url, "delivered", status_code
                    )
                    return {"event_id": event.event_id, "status": "delivered", "response_code": status_code}
                last_error = f"HTTP {status_code}"
            except URLError as e:
                last_error = str(e.reason)
            except Exception as e:
                last_error = str(e)

            if attempt < self.max_retries:
                time.sleep(self.retry_delay_seconds * attempt)

        self.store.record_delivery(event.event_id, event.tx_hash, self.webhook_url, "failed", error=last_error)
        log_error(f"Webhook delivery failed for {event.event_id}: {last_error}")
        return {"event_id": event.event_id, "status": "failed", "error": last_error}

    def poll_and_deliver(self, lookback_blocks: int = 100) -> Dict[str, Any]:
        latest = self.web3_client.eth.block_number
        last_block = self.store.get_last_block()
        from_block = max(0, last_block - lookback_blocks) if last_block > 0 else max(0, latest - lookback_blocks)

        log_debug(f"Polling Transfer events from block {from_block} to {latest}")
        events = self.fetch_events(from_block=from_block, to_block=latest)

        delivered = failed = skipped = 0
        results: List[Dict[str, Any]] = []
        for event in events:
            result = self.deliver_event(event)
            results.append(result)
            status = result.get("status")
            if status == "delivered":
                delivered += 1
            elif status == "failed":
                failed += 1
            else:
                skipped += 1

        self.store.set_last_block(latest)
        return {
            "from_block": from_block,
            "to_block": latest,
            "events_found": len(events),
            "delivered": delivered,
            "failed": failed,
            "skipped": skipped,
            "results": results,
        }
