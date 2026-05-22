#!/usr/bin/env python3
"""Capture the active Chromium tab into Raw/Sources."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "Raw" / "Sources"
WIKI_TOOL = ROOT / "scripts" / "wiki_tool.py"
SUPPORTED_BROWSERS = {
    "Google Chrome",
    "Google Chrome Canary",
    "Chromium",
    "Brave Browser",
    "Microsoft Edge",
    "Arc",
    "Dia",
}


class CaptureError(RuntimeError):
    pass


def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


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


def frontmost_app() -> str:
    return run_osascript(
        'tell application "System Events" to get name of first application process whose frontmost is true'
    )


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
    if not re.match(r"^https?://", url):
        raise CaptureError("Could not read the active page URL from Dia.")
    return url


def active_window_title() -> str:
    try:
        return run_osascript(
            'tell application "System Events" to get name of front window of first application process whose frontmost is true'
        )
    except CaptureError:
        return ""


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:90] or "captured-source"


def today() -> str:
    return dt.date.today().isoformat()


def yaml_string(value: str) -> str:
    return json.dumps(value or "")


def write_source_note(
    *,
    title: str,
    author: str,
    reference: str,
    content_types: list[str],
    body: str,
    processed: bool = False,
) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    base = slugify(title)
    path = RAW / f"{base}.md"
    if path.exists():
        suffix = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = RAW / f"{base}-{suffix}.md"
    frontmatter = [
        "---",
        f"Title: {yaml_string(title)}",
        f"Author: {yaml_string(author)}",
        f"Reference: {yaml_string(reference)}",
        "ContentType:",
        *[f"  - {yaml_string(item)}" for item in content_types],
        f"Created: {today()}",
        f"Processed: {'true' if processed else 'false'}",
        "tags:",
        '  - "source"',
        "---",
        "",
    ]
    path.write_text("\n".join(frontmatter) + body.strip() + "\n", encoding="utf-8")
    return path


def extract_youtube_id(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.endswith("youtu.be"):
        return parsed.path.strip("/")
    params = urllib.parse.parse_qs(parsed.query)
    return params.get("v", [""])[0]


def youtube_time_from_url(url: str) -> float:
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    raw = params.get("t", ["0"])[0]
    match = re.match(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?$", raw)
    if match and raw:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return float(hours * 3600 + minutes * 60 + seconds)
    try:
        return float(raw)
    except ValueError:
        return 0.0


def extract_json_object(text: str, marker: str) -> dict:
    start = text.find(marker)
    if start == -1:
        raise CaptureError(f"Could not find {marker} in page source.")
    brace_start = text.find("{", start)
    if brace_start == -1:
        raise CaptureError(f"Could not find JSON object for {marker}.")
    depth = 0
    in_string = False
    escape = False
    for index in range(brace_start, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[brace_start : index + 1])
    raise CaptureError(f"Could not parse JSON object for {marker}.")


def fetch_transcript(caption_tracks: list[dict]) -> str:
    if not caption_tracks:
        raise CaptureError("No YouTube transcript/caption track found for this video.")
    preferred = sorted(
        caption_tracks,
        key=lambda item: (
            item.get("languageCode") not in {"en", "en-US", "en-GB"},
            item.get("kind") == "asr",
        ),
    )[0]
    base_url = preferred.get("baseUrl")
    if not base_url:
        raise CaptureError("YouTube caption track did not include a transcript URL.")
    with urllib.request.urlopen(base_url, timeout=15) as response:
        data = response.read()
    root = ET.fromstring(data)
    lines = []
    for node in root.findall(".//text"):
        text = "".join(node.itertext())
        text = html.unescape(re.sub(r"\s+", " ", text)).strip()
        if text:
            start = node.attrib.get("start", "")
            lines.append(f"- [{format_seconds(start)}] {text}")
    if not lines:
        raise CaptureError("Transcript was found but did not contain usable text.")
    return "\n".join(lines)


def youtube_data_from_url(url: str) -> dict:
    page = fetch_text(url)
    response = extract_json_object(page, "ytInitialPlayerResponse")
    details = response.get("videoDetails", {})
    tracks = (
        response.get("captions", {})
        .get("playerCaptionsTracklistRenderer", {})
        .get("captionTracks", [])
    )
    return {
        "kind": "youtube",
        "url": url,
        "title": details.get("title") or active_window_title().replace(" - YouTube", ""),
        "author": details.get("author", ""),
        "videoId": details.get("videoId") or extract_youtube_id(url),
        "currentTime": youtube_time_from_url(url),
        "duration": float(details.get("lengthSeconds") or 0),
        "captionTracks": [
            {
                "baseUrl": track.get("baseUrl", ""),
                "name": track.get("name", {}).get("simpleText", ""),
                "languageCode": track.get("languageCode", ""),
                "kind": track.get("kind", ""),
            }
            for track in tracks
        ],
    }


def text_from_html(page: str) -> str:
    page = re.sub(r"(?is)<script.*?</script>", " ", page)
    page = re.sub(r"(?is)<style.*?</style>", " ", page)
    page = re.sub(r"(?is)<(nav|header|footer|aside).*?</\1>", " ", page)
    page = re.sub(r"(?i)<(p|br|h[1-6]|li|blockquote|div|section|article|main)\b[^>]*>", "\n", page)
    page = re.sub(r"(?s)<[^>]+>", " ", page)
    page = html.unescape(page)
    page = re.sub(r"[ \t]+", " ", page)
    page = re.sub(r"\n\s*\n\s*\n+", "\n\n", page)
    return page.strip()


def meta_content(page: str, *names: str) -> str:
    for name in names:
        patterns = [
            rf'<meta[^>]+(?:name|property)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\']{re.escape(name)}["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, page, re.I)
            if match:
                return html.unescape(match.group(1)).strip()
    return ""


def article_data_from_url(url: str) -> dict:
    page = fetch_text(url)
    text = text_from_html(page)
    title = meta_content(page, "og:title", "twitter:title")
    if not title:
        match = re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
        title = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip() if match else active_window_title()
    return {
        "kind": "article",
        "url": url,
        "title": title or "Article",
        "author": meta_content(page, "author", "article:author"),
        "date": meta_content(page, "article:published_time", "date"),
        "excerpt": meta_content(page, "description", "og:description", "twitter:description") or text[:700],
        "text": text,
    }


def format_seconds(raw: str) -> str:
    try:
        seconds = int(float(raw))
    except ValueError:
        return "00:00"
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"


YOUTUBE_JS = r"""
(() => {
  const player = document.querySelector("video");
  const response = window.ytInitialPlayerResponse || {};
  const details = response.videoDetails || {};
  const tracks = response.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
  const channel =
    document.querySelector("#owner #channel-name a")?.textContent?.trim() ||
    document.querySelector("ytd-channel-name a")?.textContent?.trim() ||
    details.author ||
    "";
  return JSON.stringify({
    kind: "youtube",
    url: location.href,
    title: details.title || document.title.replace(" - YouTube", ""),
    author: channel,
    videoId: details.videoId || new URLSearchParams(location.search).get("v") || "",
    currentTime: player ? player.currentTime : 0,
    duration: player ? player.duration : 0,
    captionTracks: tracks.map(track => ({
      baseUrl: track.baseUrl,
      name: track.name?.simpleText || "",
      languageCode: track.languageCode || "",
      kind: track.kind || ""
    }))
  });
})()
"""


ARTICLE_JS = r"""
(() => {
  const pick = (...selectors) => {
    for (const selector of selectors) {
      const node = document.querySelector(selector);
      const value = node?.content || node?.textContent;
      if (value && value.trim()) return value.trim();
    }
    return "";
  };
  const article =
    document.querySelector("article") ||
    document.querySelector("main") ||
    document.querySelector("[role='main']") ||
    document.body;
  const text = (article?.innerText || document.body.innerText || "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return JSON.stringify({
    kind: "article",
    url: location.href,
    title: pick("meta[property='og:title']", "meta[name='twitter:title']") || document.title,
    author: pick("meta[name='author']", "meta[property='article:author']", "[rel='author']"),
    date: pick("meta[property='article:published_time']", "meta[name='date']", "time[datetime]"),
    excerpt: pick("meta[name='description']", "meta[property='og:description']", "meta[name='twitter:description']") || text.slice(0, 700),
    text
  });
})()
"""


def capture_youtube(browser: str | None = None, data: dict | None = None, url: str | None = None) -> Path:
    if data is None:
        data = youtube_data_from_url(url) if url else active_tab_json(browser or "", YOUTUBE_JS)
    transcript = fetch_transcript(data.get("captionTracks", []))
    title = data.get("title") or "YouTube Video"
    url = data.get("url") or ""
    video_id = data.get("videoId") or extract_youtube_id(url)
    current_time = format_seconds(str(data.get("currentTime", 0)))
    duration = format_seconds(str(data.get("duration", 0)))
    author = data.get("author") or ""
    timestamp_url = f"https://www.youtube.com/watch?v={video_id}&t={int(float(data.get('currentTime', 0) or 0))}s" if video_id else url
    body = f"""# {title}

Source type: YouTube video

URL: {url}

Timestamp at capture: [{current_time}]({timestamp_url})

Duration: {duration}

Channel: {author}

## Transcript

{transcript}
"""
    return write_source_note(
        title=title,
        author=author,
        reference=url,
        content_types=["youtube", "transcript", "markdown"],
        body=body,
    )


def capture_article(browser: str | None = None, data: dict | None = None, url: str | None = None) -> Path:
    if data is None:
        data = article_data_from_url(url) if url else active_tab_json(browser or "", ARTICLE_JS)
    title = data.get("title") or "Article"
    text = data.get("text") or ""
    if len(text.strip()) < 300:
        raise CaptureError("Could not extract enough article text from this page.")
    body = f"""# {title}

Source type: Article

URL: {data.get("url", "")}

Author: {data.get("author", "")}

Published: {data.get("date", "")}

## Excerpt

{data.get("excerpt", "").strip()}

## Article Text

{text}
"""
    return write_source_note(
        title=title,
        author=data.get("author", ""),
        reference=data.get("url", ""),
        content_types=["article", "markdown"],
        body=body,
    )


def run_maintenance() -> None:
    commands = [
        [sys.executable, str(WIKI_TOOL), "build"],
        [sys.executable, str(WIKI_TOOL), "source-scan", "--update"],
        [sys.executable, str(WIKI_TOOL), "source-lint"],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)


def run_ingest_command(source_path: Path) -> None:
    command = os.environ.get("AIBRAIN_INGEST_COMMAND", "").strip()
    if not command:
        return
    env = os.environ.copy()
    env["AIBRAIN_CAPTURED_SOURCE"] = source_path.relative_to(ROOT).as_posix()
    subprocess.run(command, cwd=ROOT, shell=True, check=True, env=env)


def capture_current_page() -> Path:
    browser = frontmost_app()
    if browser not in SUPPORTED_BROWSERS:
        raise CaptureError(f"Frontmost app is {browser}. Bring a Chromium browser tab forward first.")
    try:
        probe = active_tab_json(browser, 'JSON.stringify({url: location.href, title: document.title})')
    except CaptureError:
        url = active_url_via_clipboard()
        if "youtube.com/watch" in url or "youtu.be/" in url:
            return capture_youtube(url=url)
        return capture_article(url=url)
    url = probe.get("url", "")
    if "youtube.com/watch" in url or "youtu.be/" in url:
        return capture_youtube(browser)
    return capture_article(browser)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-maintenance", action="store_true")
    args = parser.parse_args()
    try:
        path = capture_current_page()
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
