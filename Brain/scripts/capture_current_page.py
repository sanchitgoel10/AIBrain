#!/usr/bin/env python3
"""Capture a URL into Raw/Sources.

The browser extension is the primary capture path. This module remains as the
stable facade imported by the local bridge and older helper scripts.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

from capture_article import (
    ARTICLE_JS,
    article_data_from_url,
    capture_article,
    meta_content,
    minimal_article_data,
    text_from_html,
)
from capture_browser_legacy import (
    BROWSER_HISTORY_PATHS,
    BROWSER_SESSION_PATHS,
    SUPPORTED_BROWSERS,
    active_tab_json,
    active_url_fallback,
    active_url_via_clipboard,
    active_window_title,
    candidate_page,
    candidate_pages,
    candidate_url,
    clean_session_url,
    clipboard_capture_url,
    dedupe_candidates,
    history_title_lookup,
    latest_history_entry,
    latest_history_entry_any_browser,
    latest_history_entries,
    latest_history_url,
    run_osascript,
    session_url_entries,
)
from capture_common import (
    CAPTURE_USER_AGENT,
    RAW,
    ROOT,
    WIKI_TOOL,
    CaptureError,
    fetch_text,
    format_seconds,
    hostname_label,
    is_capture_url,
    load_dotenv,
    run_ingest_command,
    run_maintenance,
    slugify,
    today,
    write_source_note,
    yaml_string,
)
from capture_youtube import (
    USETRANSCRIBE_BASE_URL,
    YOUTUBE_JS,
    absolutize_transcribe_permalink,
    capture_youtube,
    extract_json_object,
    extract_youtube_id,
    fetch_transcript,
    fetch_usetranscribe_cached,
    fetch_usetranscribe_sse,
    minimal_youtube_data,
    normalize_usetranscribe_cached,
    normalize_usetranscribe_done,
    request_json,
    transcript_from_segments,
    transcript_or_warning,
    usetranscribe_base_url,
    usetranscribe_youtube_data,
    youtube_data_from_url,
    youtube_time_from_url,
)


def capture_current_page() -> Path:
    entry = latest_history_entry_any_browser()
    return capture_url(entry["url"])


def capture_url(url: str) -> Path:
    if not is_capture_url(url):
        raise CaptureError(f"Not a captureable URL: {url}")
    if "youtube.com/watch" in url or "youtu.be/" in url:
        return capture_youtube(url=url)
    return capture_article(url=url)


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-maintenance", action="store_true")
    parser.add_argument("--url", help="Capture a specific URL instead of reading the active browser.")
    parser.add_argument("--candidate-url", action="store_true", help="Print a best-effort URL candidate and exit.")
    parser.add_argument("--candidate-json", action="store_true", help="Print a best-effort URL candidate with title and exit.")
    parser.add_argument("--candidate-list-json", action="store_true", help="Print recent URL candidates with titles and exit.")
    parser.add_argument("--from-history", action="store_true", help="Capture the newest local Chromium history URL.")
    args = parser.parse_args()
    if args.candidate_list_json:
        print(json.dumps(candidate_pages()))
        return 0
    if args.candidate_json:
        print(json.dumps(candidate_page()))
        return 0
    if args.candidate_url:
        print(candidate_url())
        return 0
    try:
        if args.url:
            path = capture_url(args.url)
        elif args.from_history:
            path = capture_current_page()
        else:
            raise CaptureError("Pass --url, or use the browser extension. History capture is available with --from-history.")
        if not args.skip_maintenance:
            run_maintenance()
        run_ingest_command(path)
    except (CaptureError, subprocess.CalledProcessError, urllib.error.URLError, ET.ParseError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(path.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
