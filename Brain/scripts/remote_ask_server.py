#!/usr/bin/env python3
"""Read-only mobile web server for Ask My Brain."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import brain_ask
from capture_common import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "apps" / "ask-web"
HOST = os.environ.get("AIBRAIN_REMOTE_ASK_HOST", "127.0.0.1")
PORT = int(os.environ.get("AIBRAIN_REMOTE_ASK_PORT", "8766"))
MAX_BODY_BYTES = 32 * 1024
MAX_QUERY_CHARS = 1000
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
}

AnswerFn = Callable[[str, int], dict[str, Any]]


class RemoteAskHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def answer_question(query: str, limit: int) -> dict[str, Any]:
    return brain_ask.answer(query, root=ROOT, limit=limit)


def create_handler(web_root: Path, answer_fn: AnswerFn) -> type[BaseHTTPRequestHandler]:
    class RemoteAskHandler(BaseHTTPRequestHandler):
        server_version = "AIBrainRemoteAsk/1.0"

        def log_message(self, format_string: str, *args: object) -> None:
            print(f"{self.client_address[0]} - {format_string % args}", flush=True)

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
                "style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'",
            )
            super().end_headers()

        def send_bytes(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_bytes(status, body, "application/json; charset=utf-8")

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/health":
                self.send_json(200, {"ok": True, "service": "aibrain-remote-ask"})
                return
            static = STATIC_FILES.get(path)
            if static:
                filename, content_type = static
                try:
                    body = (web_root / filename).read_bytes()
                except OSError:
                    self.send_json(500, {"ok": False, "error": "Ask interface is unavailable."})
                    return
                self.send_bytes(200, body, content_type)
                return
            self.send_json(404, {"ok": False, "error": "Not found."})

        def do_POST(self) -> None:
            if urlsplit(self.path).path != "/api/ask":
                self.send_json(404, {"ok": False, "error": "Not found."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
                if length <= 0 or length > MAX_BODY_BYTES:
                    raise ValueError("Invalid request size.")
                payload = json.loads(self.rfile.read(length))
                query = str(payload.get("query") or "").strip()
                if not query:
                    raise ValueError("Question is required.")
                if len(query) > MAX_QUERY_CHARS:
                    raise ValueError(f"Question must be {MAX_QUERY_CHARS} characters or fewer.")
                limit = max(1, min(int(payload.get("limit") or 5), 10))
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                self.send_json(400, {"ok": False, "error": str(exc)})
                return

            try:
                result = answer_fn(query, limit)
            except Exception as exc:
                print(f"Ask failed: {exc}", flush=True)
                self.send_json(500, {"ok": False, "error": "Ask failed. Check the Mac service logs."})
                return
            self.send_json(200, {"ok": True, **result})

    return RemoteAskHandler


def create_server(
    host: str = HOST,
    port: int = PORT,
    *,
    web_root: Path = WEB_ROOT,
    answer_fn: AnswerFn = answer_question,
) -> RemoteAskHTTPServer:
    return RemoteAskHTTPServer((host, port), create_handler(web_root, answer_fn))


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    server = create_server(args.host, args.port)
    print(f"Ask My Brain listening at http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Ask My Brain.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
