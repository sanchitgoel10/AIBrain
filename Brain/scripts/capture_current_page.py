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
}


class CaptureError(RuntimeError):
    pass


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


def capture_youtube(browser: str) -> Path:
    data = active_tab_json(browser, YOUTUBE_JS)
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


def capture_article(browser: str) -> Path:
    data = active_tab_json(browser, ARTICLE_JS)
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
    probe = active_tab_json(browser, 'JSON.stringify({url: location.href, title: document.title})')
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
