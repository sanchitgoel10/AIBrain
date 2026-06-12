#!/usr/bin/env python3
"""Local HTTP bridge for the AI Brain browser extension."""

from __future__ import annotations

import base64
import json
import subprocess
import tempfile
import threading
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import capture_current_page as capture
import auto_ingest
import brain_ask

HOST = "127.0.0.1"
PORT = 8765
RECENT_JOB_TTL_SECONDS = 60 * 60
RUNNING_JOB_TIMEOUT_SECONDS = 4 * 60
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
INGEST_LOCK = threading.Lock()


def set_job(job_id: str, **updates: object) -> None:
    with JOBS_LOCK:
        job = JOBS.setdefault(job_id, {})
        if job.get("timed_out") and updates.get("status") != "error":
            return
        if job.get("cancelled") and updates.get("status") != "cancelled":
            return
        job.update(updates)
        job["updated_at"] = time.time()


def cancel_job(job_id: str) -> dict | None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return None
        job.update(
            status="cancelled",
            ok=False,
            cancelled=True,
            message="Capture stopped by the user.",
            updated_at=time.time(),
        )
        return dict(job)


def job_is_cancelled(job_id: str) -> bool:
    with JOBS_LOCK:
        return bool(JOBS.get(job_id, {}).get("cancelled"))


def stop_if_cancelled(job_id: str) -> None:
    if job_is_cancelled(job_id):
        raise InterruptedError("Capture stopped by the user.")


def get_job(job_id: str) -> dict | None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job and is_timed_out(job):
            mark_job_timed_out(job)
        return dict(job) if job else None


def recent_job_for_url(url: str) -> tuple[str, dict] | None:
    cutoff = time.time() - RECENT_JOB_TTL_SECONDS
    with JOBS_LOCK:
        matches = [
            (job_id, job)
            for job_id, job in JOBS.items()
            if job.get("url") == url and float(job.get("updated_at", job.get("created_at", 0)) or 0) >= cutoff
        ]
        if not matches:
            return None
        job_id, job = max(matches, key=lambda item: float(item[1].get("updated_at", item[1].get("created_at", 0)) or 0))
        if is_timed_out(job):
            mark_job_timed_out(job)
        result = dict(job)
        result["job_id"] = job_id
        return job_id, result


def is_running_job(job: dict) -> bool:
    return job.get("status") in {"queued", "capturing", "ingesting", "maintenance"}


def is_timed_out(job: dict) -> bool:
    started = float(job.get("created_at", 0) or 0)
    return is_running_job(job) and started > 0 and time.time() - started > RUNNING_JOB_TIMEOUT_SECONDS


def mark_job_timed_out(job: dict) -> None:
    job["status"] = "error"
    job["ok"] = False
    job["timed_out"] = True
    job["error"] = "Capture timed out. Try again; the transcript provider may be slow or unavailable."
    job["message"] = job["error"]
    job["updated_at"] = time.time()


def is_youtube_url(url: str) -> bool:
    return "youtube.com/watch" in url or "youtu.be/" in url


def search_brain(query: str, *, limit: int = 8) -> list[dict]:
    return brain_ask.search(query, root=capture.ROOT, limit=limit)


def ask_brain(query: str, *, limit: int = 5) -> dict:
    return brain_ask.answer(query, root=capture.ROOT, limit=limit)


def brain_path_from_request(path_value: str) -> Path:
    if not path_value.strip():
        raise capture.CaptureError("Source path is required.")
    raw_path = Path(path_value)
    if raw_path.is_absolute():
        raise capture.CaptureError("Source path must be relative to the Brain vault.")
    root = capture.ROOT.resolve()
    target = (root / raw_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise capture.CaptureError("Source path is outside the Brain vault.") from exc
    if not target.exists():
        raise capture.CaptureError(f"Source path does not exist: {path_value}")
    return target


def reveal_brain_path(path_value: str) -> dict:
    target = brain_path_from_request(path_value)
    args = ["open", str(target)] if target.is_dir() else ["open", "-R", str(target)]
    subprocess.Popen(args, cwd=capture.ROOT)
    return {"path": target.relative_to(capture.ROOT).as_posix()}


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
        "captureWarning": str(page.get("captureWarning", "")).strip(),
    }


def data_url_bytes(data_url: str) -> bytes:
    if "," not in data_url:
        raise capture.CaptureError("Screenshot payload was not a data URL.")
    header, encoded = data_url.split(",", 1)
    if "base64" not in header:
        raise capture.CaptureError("Screenshot payload was not base64 encoded.")
    return base64.b64decode(encoded)


def ocr_screenshots(screenshots: list[dict]) -> str:
    if not screenshots:
        return ""
    script = capture.ROOT / "scripts" / "ocr_images.swift"
    with tempfile.TemporaryDirectory(prefix="aibrain-ocr-") as tmp_dir:
        paths: list[str] = []
        for index, screenshot in enumerate(screenshots):
            data_url = str(screenshot.get("dataUrl", ""))
            if not data_url:
                continue
            path = Path(tmp_dir) / f"capture-{index:02d}.png"
            path.write_bytes(data_url_bytes(data_url))
            paths.append(str(path))
        if not paths:
            return ""
        result = subprocess.run(
            ["/usr/bin/swift", str(script), *paths],
            cwd=capture.ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=180,
        )
    if result.returncode != 0:
        raise capture.CaptureError(result.stderr.strip() or "Screenshot OCR failed.")
    lines = []
    previous = ""
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line or line == previous:
            continue
        lines.append(line)
        previous = line
    return "\n".join(lines).strip()


def article_payload_with_ocr(payload: dict) -> dict:
    page = dict(payload.get("page") if isinstance(payload.get("page"), dict) else {})
    text = str(page.get("text", "")).strip()
    screenshots = page.get("screenshots") if isinstance(page.get("screenshots"), list) else []
    force_ocr = bool(page.get("extractionMethod") == "screenshot-ocr")
    discard_dom_text = bool(page.get("discardDomTextForOcr"))
    if discard_dom_text:
        text = ""
        page["text"] = ""
    if (force_ocr or len(text) < 800) and screenshots:
        ocr_text = ocr_screenshots(screenshots)
        if ocr_text:
            if text:
                text = f"{text}\n\n## OCR Extracted Text\n\n{ocr_text}"
            else:
                text = ocr_text
            page["text"] = text
            page["excerpt"] = str(page.get("excerpt") or ocr_text[:700])
            if discard_dom_text:
                page["captureWarning"] = "Article text was extracted from browser screenshots because the page DOM looked stale or mismatched."
            elif force_ocr:
                page["captureWarning"] = "Article text includes browser screenshot OCR because the page DOM looked incomplete."
            else:
                page["captureWarning"] = "Article text was extracted from browser screenshots using local OCR."
    if len(str(page.get("text", "")).strip()) < 120:
        raise capture.CaptureError("Could not read enough article text from DOM or screenshots.")
    updated = dict(payload)
    updated["page"] = page
    return updated


def run_capture_job(job_id: str, payload: dict) -> None:
    url = str(payload.get("url", "")).strip()
    try:
        stop_if_cancelled(job_id)
        if not url:
            raise capture.CaptureError("The extension did not send a URL.")
        if not capture.is_capture_url(url):
            raise capture.CaptureError(f"Not a captureable URL: {url}")

        if is_youtube_url(url):
            set_job(job_id, status="capturing", message="Capturing YouTube transcript. Uncached videos can take a few minutes.")
            path = capture.capture_youtube(url=url)
        elif isinstance(payload.get("page"), dict):
            screenshots = payload["page"].get("screenshots")
            if screenshots:
                set_job(job_id, status="capturing", message=f"Running local OCR over {len(screenshots)} article screenshots.")
            else:
                set_job(job_id, status="capturing", message="Saving visible article text from the browser tab.")
            article_payload = article_payload_with_ocr(payload)
            path = capture.capture_article(data=article_data_from_payload(article_payload))
        else:
            set_job(job_id, status="capturing", message="Fetching article page text.")
            path = capture.capture_article(url=url)

        stop_if_cancelled(job_id)
        with INGEST_LOCK:
            stop_if_cancelled(job_id)
            set_job(job_id, status="ingesting", message="Creating linked Wiki ingest note.")
            ingest_path = auto_ingest.ingest_source(path)

            stop_if_cancelled(job_id)
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
            stop_if_cancelled(job_id)
            subprocess.run(
                ["python3", str(capture.WIKI_TOOL), "source-lint"],
                cwd=capture.ROOT,
                check=True,
            )
        stop_if_cancelled(job_id)
        capture.run_ingest_command(path)
        stop_if_cancelled(job_id)
    except InterruptedError:
        return
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
        if parsed.path == "/ask":
            params = urllib.parse.parse_qs(parsed.query)
            query = params.get("query", params.get("q", [""]))[0]
            try:
                limit = int(params.get("limit", ["5"])[0] or 5)
            except ValueError:
                limit = 5
            answer = ask_brain(query, limit=limit)
            self.send_json(200, {"ok": True, **answer})
            return
        if parsed.path == "/open-source":
            params = urllib.parse.parse_qs(parsed.query)
            path_value = params.get("path", [""])[0]
            try:
                opened = reveal_brain_path(path_value)
            except (capture.CaptureError, OSError) as exc:
                self.send_json(400, {"ok": False, "error": str(exc)})
                return
            self.send_json(200, {"ok": True, **opened})
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
        if parsed.path == "/recent-status":
            params = urllib.parse.parse_qs(parsed.query)
            url = params.get("url", [""])[0]
            match = recent_job_for_url(url)
            if not match:
                self.send_json(200, {"ok": True, "job": None})
                return
            job_id, job = match
            self.send_json(200, {"ok": True, "job_id": job_id, "job": job})
            return
        self.send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/cancel":
            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = self.rfile.read(length).decode("utf-8")
                payload = json.loads(body) if body else {}
                job_id = str(payload.get("job_id", "")).strip()
            except (OSError, ValueError, json.JSONDecodeError):
                job_id = ""
            job = cancel_job(job_id)
            if not job:
                self.send_json(404, {"ok": False, "error": "unknown job"})
                return
            self.send_json(200, {"ok": True, "job": job})
            return
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
            title = str(payload.get("title", "")).strip()
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
            title=title,
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
