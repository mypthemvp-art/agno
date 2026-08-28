"""Transfer event webhook example."""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from agno.tools.startup_stock import StartupStockAdvancedTools


class WebhookHandler(BaseHTTPRequestHandler):
    received: list = []

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        WebhookHandler.received.append(json.loads(body))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args) -> None:
        return


def start_test_server(port: int = 8765) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), WebhookHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    if not os.getenv("STARTUP_STOCK_CONTRACT_ADDRESS"):
        print("Set STARTUP_STOCK_CONTRACT_ADDRESS")
        return

    port = 8765
    server = start_test_server(port)
    os.environ["STARTUP_STOCK_WEBHOOK_URL"] = f"http://127.0.0.1:{port}/webhook"

    tools = StartupStockAdvancedTools(enable_vesting=False, enable_multisig=False)

    print("=== Poll Transfer Webhooks ===")
    result = json.loads(tools.poll_transfer_webhooks(lookback_blocks=1000))
    print(json.dumps(result, indent=2))

    print(f"\nReceived {len(WebhookHandler.received)} webhook payloads")
    server.shutdown()


if __name__ == "__main__":
    main()
