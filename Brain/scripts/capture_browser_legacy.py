#!/usr/bin/env python3
"""Legacy browser discovery helpers for the old floater/history capture path."""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
import tempfile
import urllib.parse
from pathlib import Path

from capture_common import CaptureError, hostname_label, is_capture_url

SUPPORTED_BROWSERS = {
    "Google Chrome",
    "Google Chrome Canary",
    "Chromium",
    "Brave Browser",
    "Microsoft Edge",
    "Arc",
    "Dia",
}
BROWSER_HISTORY_PATHS = {
    "Dia": [
        "~/Library/Application Support/Dia/User Data/Default/History",
        "~/Library/Application Support/Comet/Default/History",
    ],
    "Google Chrome": ["~/Library/Application Support/Google/Chrome/Default/History"],
    "Google Chrome Canary": ["~/Library/Application Support/Google/Chrome Canary/Default/History"],
    "Chromium": ["~/Library/Application Support/Chromium/Default/History"],
    "Brave Browser": ["~/Library/Application Support/BraveSoftware/Brave-Browser/Default/History"],
    "Microsoft Edge": ["~/Library/Application Support/Microsoft Edge/Default/History"],
    "Arc": ["~/Library/Application Support/Arc/User Data/Default/History"],
}
BROWSER_SESSION_PATHS = {
    "Dia": ["~/Library/Application Support/Dia/User Data/Default/Sessions"],
}


def run_osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript"],
        input=script,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise CaptureError(result.stderr.strip() or result.stdout.strip() or "AppleScript failed")
    return result.stdout.strip()


def active_tab_json(browser: str, js: str) -> dict:
    quoted_js = json.dumps(js)
    quoted_browser = json.dumps(browser)
    script = f"""
tell application {quoted_browser}
  if not (exists front window) then error "No browser window is open."
  set tabUrl to URL of active tab of front window
  set tabTitle to title of active tab of front window
  set jsResult to execute active tab of front window javascript {quoted_js}
  return jsResult
end tell
"""
    raw = run_osascript(script)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CaptureError(f"Could not parse browser capture result: {exc}") from exc


def active_url_via_clipboard() -> str:
    script = r'''
tell application "System Events"
  keystroke "l" using command down
  delay 0.08
  keystroke "c" using command down
  delay 0.12
end tell
'''
    run_osascript(script)
    result = subprocess.run(["pbpaste"], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise CaptureError(result.stderr.strip() or "Could not read the clipboard text.")
    url = result.stdout.strip()
    if not is_capture_url(url):
        raise CaptureError("Clipboard did not contain a captureable URL.")
    return url


def clipboard_capture_url() -> str:
    result = subprocess.run(["pbpaste"], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return ""
    text = result.stdout.strip()
    if is_capture_url(text):
        return text
    return ""


def clean_session_url(raw_url: str) -> str:
    url = raw_url.strip().rstrip(".,);]")
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return urllib.parse.urlunparse(parsed)


def history_title_lookup() -> dict[str, str]:
    titles: dict[str, str] = {}
    for browser in BROWSER_HISTORY_PATHS:
        for entry in latest_history_entries(browser, limit=250):
            titles.setdefault(entry["url"], entry.get("title", ""))
    return titles


def latest_history_url(browser: str) -> str:
    entry = latest_history_entry(browser)
    if not entry:
        raise CaptureError(f"Could not find a recent captureable URL in {browser} history.")
    return entry["url"]


def latest_history_entry(browser: str) -> dict | None:
    entries = latest_history_entries(browser, limit=50)
    return entries[0] if entries else None


def latest_history_entries(browser: str, *, limit: int = 50) -> list[dict]:
    entries = []
    for raw_path in BROWSER_HISTORY_PATHS.get(browser, []):
        history_path = Path(raw_path).expanduser()
        if not history_path.exists():
            continue
        with tempfile.NamedTemporaryFile(prefix="aibrain-history-", suffix=".sqlite") as tmp:
            shutil.copy2(history_path, tmp.name)
            with sqlite3.connect(tmp.name) as db:
                rows = db.execute(
                    """
                    SELECT url, title, last_visit_time
                    FROM urls
                    WHERE url LIKE 'http%'
                    ORDER BY last_visit_time DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        for url, title, last_visit_time in rows:
            if is_capture_url(url):
                entries.append({"browser": browser, "url": url, "title": title or "", "last_visit_time": last_visit_time})
    return sorted(entries, key=lambda item: item["last_visit_time"], reverse=True)


def session_url_entries(browser: str, *, limit: int = 25) -> list[dict]:
    titles = history_title_lookup()
    entries = []
    for raw_dir in BROWSER_SESSION_PATHS.get(browser, []):
        session_dir = Path(raw_dir).expanduser()
        if not session_dir.exists():
            continue
        session_files = sorted(
            [path for path in session_dir.iterdir() if path.is_file() and path.name.startswith(("Session_", "Tabs_"))],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:4]
        for session_file in session_files:
            try:
                text = session_file.read_bytes().decode("latin-1", errors="ignore")
            except OSError:
                continue
            raw_urls = re.findall(r"https?://[^\x00\s\"'<>{}]+", text)
            for raw_url in reversed(raw_urls):
                url = clean_session_url(raw_url)
                if not is_capture_url(url):
                    continue
                entries.append(
                    {
                        "browser": browser,
                        "url": url,
                        "title": titles.get(url, "") or hostname_label(url),
                        "last_visit_time": int(session_file.stat().st_mtime * 1_000_000),
                        "source": "session",
                    }
                )
                if len(entries) >= limit:
                    return dedupe_candidates(entries)
    return dedupe_candidates(entries)


def latest_history_entry_any_browser() -> dict:
    entries = [entry for browser in BROWSER_HISTORY_PATHS for entry in [latest_history_entry(browser)] if entry]
    if not entries:
        raise CaptureError("Could not find a recent captureable URL in local Chromium browser history.")
    return sorted(entries, key=lambda item: item["last_visit_time"], reverse=True)[0]


def dedupe_candidates(entries: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for entry in entries:
        url = entry.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(entry)
    return unique


def candidate_pages(limit: int = 12) -> list[dict]:
    entries = []
    for browser in BROWSER_SESSION_PATHS:
        entries.extend(session_url_entries(browser, limit=limit))
    for browser in BROWSER_HISTORY_PATHS:
        for entry in latest_history_entries(browser, limit=40):
            entry = dict(entry)
            entry["source"] = "history"
            entries.append(entry)
    clipboard_url = clipboard_capture_url()
    if clipboard_url:
        entries.append(
            {
                "url": clipboard_url,
                "title": "Clipboard URL",
                "browser": "",
                "source": "clipboard",
                "last_visit_time": 0,
            }
        )
    normalized = []
    for entry in dedupe_candidates(entries):
        normalized.append(
            {
                "url": entry.get("url", ""),
                "title": entry.get("title", "") or hostname_label(entry.get("url", "")),
                "browser": entry.get("browser", ""),
                "source": entry.get("source", "history"),
            }
        )
        if len(normalized) >= limit:
            break
    return normalized


def candidate_page() -> dict:
    pages = candidate_pages(limit=1)
    return pages[0] if pages else {"url": "", "title": "", "browser": "", "source": ""}


def candidate_url() -> str:
    return candidate_page()["url"]


def active_url_fallback(browser: str) -> str:
    try:
        return active_url_via_clipboard()
    except CaptureError:
        return latest_history_url(browser)


def active_window_title() -> str:
    try:
        return run_osascript(
            'tell application "System Events" to get name of front window of first application process whose frontmost is true'
        )
    except CaptureError:
        return ""
