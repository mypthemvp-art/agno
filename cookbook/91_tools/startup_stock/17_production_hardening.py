"""Production hardening: health alerts and circuit breaker demo."""

import json
import os

from agno.tools.startup_stock import StartupStockAdvancedTools
from agno.tools.startup_stock.circuit_breaker import CircuitBreaker


def main() -> None:
    if not os.getenv("EVM_PRIVATE_KEY") or not os.getenv("EVM_RPC_URL"):
        print("Set EVM_PRIVATE_KEY and EVM_RPC_URL to run this example")
        return

    tools = StartupStockAdvancedTools(
        enable_webhooks=False,
        enable_deploy_extended=False,
        enable_option_pool=False,
        enable_transfer_policy=False,
    )

    print("=== Health Check ===")
    health = json.loads(tools.run_health_check())
    print(json.dumps(health, indent=2))

    print("\n=== Circuit Breaker Status ===")
    print(json.dumps(json.loads(tools.get_circuit_breaker_status()), indent=2))

    print("\n=== Simulate RPC Failures ===")
    breaker = CircuitBreaker(
        failure_threshold=3, recovery_timeout_seconds=1, name="demo"
    )
    for i in range(3):
        try:
            breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("RPC timeout")))
        except RuntimeError as e:
            print(f"  failure {i + 1}: {e}")
    print(json.dumps(breaker.status(), indent=2))

    print("\n=== Evaluate Alerts (no webhook delivery in demo) ===")
    alerts = json.loads(tools.evaluate_alerts(include_sync_preview=True))
    print(json.dumps(alerts, indent=2))


if __name__ == "__main__":
    main()
