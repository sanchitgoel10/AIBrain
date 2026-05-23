#!/usr/bin/env python3
"""Local HTTP bridge for the AI Brain browser extension."""

from __future__ import annotations

import json
import subprocess
import threading
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import capture_current_page as capture
import auto_ingest

HOST = "127.0.0.1"
PORT = 8765
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def set_job(job_id: str, **updates: object) -> None:
    with JOBS_LOCK:
        job = JOBS.setdefault(job_id, {})
        job.update(updates)
        job["updated_at"] = time.time()


def get_job(job_id: str) -> dict | None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        return dict(job) if job else None


def is_youtube_url(url: str) -> bool:
    return "youtube.com/watch" in url or "youtu.be/" in url


def article_data_from_payload(payload: dict) -> dict:
    page = payload.get("page") if isinstance(payload.get("page"), dict) else {}
    return {
        "kind": "article",
        "url": str(payload.get("url", "")).strip(),
        "title": str(page.get("title") or payload.get("title") or "Article").strip(),
        "author": str(page.get("author", "")).strip(),
        "date": str(page.get("date", "")).strip(),
        "excerpt": str(page.get("excerpt", "")).strip(),
        "text": str(page.get("text", "")).strip(),
        "browserExtracted": True,
    }


def run_capture_job(job_id: str, payload: dict) -> None:
    url = str(payload.get("url", "")).strip()
    try:
        if not url:
            raise capture.CaptureError("The extension did not send a URL.")
        if not capture.is_capture_url(url):
            raise capture.CaptureError(f"Not a captureable URL: {url}")

        if is_youtube_url(url):
            set_job(job_id, status="capturing", message="Capturing YouTube transcript. Uncached videos can take a few minutes.")
            path = capture.capture_youtube(url=url)
        elif isinstance(payload.get("page"), dict) and str(payload["page"].get("text", "")).strip():
            set_job(job_id, status="capturing", message="Saving visible article text from the browser tab.")
            path = capture.capture_article(data=article_data_from_payload(payload))
        else:
            set_job(job_id, status="capturing", message="Fetching article page text.")
            path = capture.capture_article(url=url)

        set_job(job_id, status="ingesting", message="Creating linked Wiki ingest note.")
        ingest_path = auto_ingest.ingest_source(path)

        set_job(job_id, status="maintenance", message="Updating AI Brain catalog and source manifest.")
        capture.run_maintenance()
        subprocess.run(
            [
                "python3",
                str(capture.WIKI_TOOL),
                "source-scan",
                "--update",
                "--accept-covered",
            ],
            cwd=capture.ROOT,
            check=True,
        )
        subprocess.run(
            ["python3", str(capture.WIKI_TOOL), "source-lint"],
            cwd=capture.ROOT,
            check=True,
        )
        capture.run_ingest_command(path)
    except (capture.CaptureError, subprocess.CalledProcessError, OSError, ValueError, json.JSONDecodeError) as exc:
        set_job(job_id, status="error", ok=False, error=str(exc), message=str(exc))
        return

    set_job(
        job_id,
        status="done",
        ok=True,
        message="Capture complete.",
        path=path.relative_to(capture.ROOT).as_posix(),
        ingest_path=ingest_path.relative_to(capture.ROOT).as_posix(),
        url=url,
    )


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
        if parsed.path == "/status":
            params = urllib.parse.parse_qs(parsed.query)
            job_id = params.get("job_id", [""])[0]
            job = get_job(job_id)
            if not job:
                self.send_json(404, {"ok": False, "error": "unknown job"})
                return
            self.send_json(200, {"ok": True, "job": job})
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
        except (capture.CaptureError, subprocess.CalledProcessError, OSError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})
            return

        job_id = uuid.uuid4().hex
        set_job(
            job_id,
            ok=True,
            status="queued",
            message="Capture queued.",
            url=url,
            created_at=time.time(),
        )
        thread = threading.Thread(target=run_capture_job, args=(job_id, payload), daemon=True)
        thread.start()

        self.send_json(
            202,
            {
                "ok": True,
                "job_id": job_id,
                "status": "queued",
                "message": "Capture queued.",
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
