#!/usr/bin/env python3
"""Local HTTP bridge for the AI Brain browser extension."""

from __future__ import annotations

import json
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import capture_current_page as capture

HOST = "127.0.0.1"
PORT = 8765


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "AIBrainCaptureBridge/0.1"

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def send_json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/health":
            self.send_json(200, {"ok": True, "service": "aibrain-capture-bridge"})
            return
        self.send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/capture":
            self.send_json(404, {"ok": False, "error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body) if body else {}
            url = str(payload.get("url", "")).strip()
            if not url:
                raise capture.CaptureError("The extension did not send a URL.")
            path = capture.capture_url(url)
            capture.run_maintenance()
            capture.run_ingest_command(path)
        except (capture.CaptureError, subprocess.CalledProcessError, OSError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})
            return

        self.send_json(
            200,
            {
                "ok": True,
                "path": path.relative_to(capture.ROOT).as_posix(),
                "url": url,
            },
        )


def main() -> int:
    capture.load_dotenv()
    server = ThreadingHTTPServer((HOST, PORT), BridgeHandler)
    print(f"AI Brain capture bridge listening at http://{HOST}:{PORT}")
    print("Install the browser extension and click it on the active Dia/Chromium tab.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping capture bridge.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
