"""Alert helpers for startup stock health and sync events."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass
class AlertEvent:
    severity: str  # info | warning | critical
    title: str
    message: str
    source: str = "startup_stock"
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if not data["created_at"]:
            data["created_at"] = datetime.now(timezone.utc).isoformat()
        return data


def build_alert_from_health(health_result: Dict[str, Any]) -> Optional[AlertEvent]:
    """Create an alert from a health check result when unhealthy."""
    if health_result.get("healthy", True):
        return None
    unhealthy = [c.get("component", "?") for c in health_result.get("checks", []) if not c.get("healthy", True)]
    return AlertEvent(
        severity="critical",
        title="Startup stock health check failed",
        message=f"Unhealthy components: {', '.join(unhealthy) or 'unknown'}",
        metadata=health_result,
    )


def build_alert_from_sync(sync_result: Dict[str, Any]) -> Optional[AlertEvent]:
    """Create an alert when sync detects drift or failures."""
    drifted = sync_result.get("drifted", 0)
    failed = sync_result.get("failed", 0)
    if drifted == 0 and failed == 0:
        return None
    severity = "critical" if drifted > 0 else "warning"
    return AlertEvent(
        severity=severity,
        title="Cap table sync issues detected",
        message=f"drifted={drifted} failed={failed}",
        metadata=sync_result,
    )


def deliver_webhook_alert(
    webhook_url: str,
    alert: AlertEvent,
    http_post_fn: Optional[Callable[[str, Dict[str, Any]], tuple[int, str]]] = None,
) -> Dict[str, Any]:
    """Deliver an alert payload to an HTTP webhook."""
    payload = alert.to_dict()
    if http_post_fn:
        status_code, body = http_post_fn(webhook_url, payload)
        return {"delivered": status_code < 400, "status_code": status_code, "body": body}

    data = json.dumps(payload).encode("utf-8")
    request = Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            return {
                "delivered": True,
                "status_code": response.status,
                "body": response.read().decode("utf-8", errors="replace")[:500],
            }
    except URLError as e:
        return {"delivered": False, "error": str(e)}


def evaluate_and_alert(
    health_result: Optional[Dict[str, Any]] = None,
    sync_result: Optional[Dict[str, Any]] = None,
    webhook_url: Optional[str] = None,
    http_post_fn: Optional[Callable[[str, Dict[str, Any]], tuple[int, str]]] = None,
) -> Dict[str, Any]:
    """Evaluate health/sync results and optionally deliver alerts."""
    alerts: List[Dict[str, Any]] = []
    deliveries: List[Dict[str, Any]] = []

    for builder, payload in (
        (build_alert_from_health, health_result),
        (build_alert_from_sync, sync_result),
    ):
        if not payload:
            continue
        alert = builder(payload)
        if not alert:
            continue
        alerts.append(alert.to_dict())
        if webhook_url:
            deliveries.append(deliver_webhook_alert(webhook_url, alert, http_post_fn=http_post_fn))

    return {
        "alert_count": len(alerts),
        "alerts": alerts,
        "deliveries": deliveries,
    }
