"""Circuit breaker for RPC and on-chain call protection."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, TypeVar

T = TypeVar("T")


@dataclass
class CircuitBreaker:
    """Simple circuit breaker to stop repeated failing RPC calls.

    States: closed (normal) -> open (blocking) -> half_open (probe).
    """

    failure_threshold: int = 5
    recovery_timeout_seconds: float = 30.0
    half_open_max_calls: int = 1
    name: str = "rpc"

    failure_count: int = 0
    success_count: int = 0
    state: str = "closed"
    opened_at: Optional[float] = None
    half_open_calls: int = 0
    last_error: Optional[str] = None
    history: list = field(default_factory=list)

    def status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_seconds": self.recovery_timeout_seconds,
            "opened_at": self.opened_at,
            "last_error": self.last_error,
        }

    def _transition_to_open(self, error: str) -> None:
        self.state = "open"
        self.opened_at = time.time()
        self.last_error = error
        self.half_open_calls = 0
        self.history.append({"event": "open", "error": error, "at": self.opened_at})

    def _maybe_half_open(self) -> None:
        if self.state == "open" and self.opened_at is not None:
            if time.time() - self.opened_at >= self.recovery_timeout_seconds:
                self.state = "half_open"
                self.half_open_calls = 0
                self.history.append({"event": "half_open", "at": time.time()})

    def allow_request(self) -> bool:
        self._maybe_half_open()
        if self.state == "closed":
            return True
        if self.state == "half_open":
            if self.half_open_calls < self.half_open_max_calls:
                self.half_open_calls += 1
                return True
            return False
        return False

    def record_success(self) -> None:
        self.success_count += 1
        self.failure_count = 0
        self.last_error = None
        if self.state in ("half_open", "open"):
            self.state = "closed"
            self.opened_at = None
            self.half_open_calls = 0
            self.history.append({"event": "close", "at": time.time()})

    def record_failure(self, error: str) -> None:
        self.failure_count += 1
        self.last_error = error
        if self.state == "half_open":
            self._transition_to_open(error)
        elif self.failure_count >= self.failure_threshold:
            self._transition_to_open(error)

    def call(self, fn: Callable[[], T]) -> T:
        if not self.allow_request():
            raise RuntimeError(
                f"Circuit breaker '{self.name}' is open" + (f": {self.last_error}" if self.last_error else "")
            )
        try:
            result = fn()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(str(e))
            raise

    def reset(self) -> Dict[str, Any]:
        self.failure_count = 0
        self.success_count = 0
        self.state = "closed"
        self.opened_at = None
        self.half_open_calls = 0
        self.last_error = None
        self.history.append({"event": "reset", "at": time.time()})
        return self.status()
