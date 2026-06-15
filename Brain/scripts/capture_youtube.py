#!/usr/bin/env python3
"""YouTube capture and Transcribe integration."""

from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from capture_browser_legacy import active_tab_json, active_window_title
from capture_common import (
    CAPTURE_USER_AGENT,
    CaptureError,
    fetch_text,
    format_seconds,
    write_source_note,
)

USETRANSCRIBE_BASE_URL = "https://www.usetranscribe.io"
USETRANSCRIBE_REQUEST_TIMEOUT_SECONDS = int(os.environ.get("USETRANSCRIBE_REQUEST_TIMEOUT_SECONDS", "30"))
USETRANSCRIBE_STREAM_TIMEOUT_SECONDS = int(os.environ.get("USETRANSCRIBE_STREAM_TIMEOUT_SECONDS", "180"))

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


def usetranscribe_base_url() -> str:
    return os.environ.get("USETRANSCRIBE_BASE_URL", USETRANSCRIBE_BASE_URL).rstrip("/")


def request_json(url: str, *, timeout: int = USETRANSCRIBE_REQUEST_TIMEOUT_SECONDS) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": CAPTURE_USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise CaptureError(f"Transcribe API error {exc.code}: {detail}") from exc
    return json.loads(raw) if raw.strip() else {}


def absolutize_transcribe_permalink(permalink: str) -> str:
    if permalink.startswith("http"):
        return permalink
    return f"{usetranscribe_base_url()}{permalink}"


def transcript_from_segments(segments: list[dict]) -> str:
    lines = []
    for segment in segments:
        start = segment.get("start", segment.get("start_seconds", 0))
        speaker = str(segment.get("speaker", "")).strip()
        text = re.sub(r"\s+", " ", str(segment.get("text", ""))).strip()
        if not text:
            continue
        prefix = f"{speaker}: " if speaker else ""
        lines.append(f"- [{format_seconds(str(start))}] {prefix}{text}")
    return "\n".join(lines)


def normalize_defuddle_transcript(transcript: str) -> str:
    lines = []
    pattern = re.compile(
        r"^\*\*(?P<timestamp>\d{1,2}:\d{2}(?::\d{2})?)\*\*\s*[·\-–—]\s*(?P<text>.+)$"
    )
    for raw_line in str(transcript or "").splitlines():
        match = pattern.match(raw_line.strip())
        if not match:
            continue
        parts = [int(part) for part in match.group("timestamp").split(":")]
        seconds = parts[-1] + (parts[-2] * 60)
        if len(parts) == 3:
            seconds += parts[0] * 3600
        text = re.sub(r"\s+", " ", match.group("text")).strip()
        if text:
            lines.append(f"- [{format_seconds(str(seconds))}] {text}")
    return "\n".join(lines)


def normalize_defuddle_fallback(data: dict, original_url: str) -> dict:
    transcript = normalize_defuddle_transcript(str(data.get("transcript") or ""))
    if not transcript:
        raise CaptureError("Defuddle did not find a usable YouTube caption transcript.")
    return {
        "kind": "youtube",
        "url": original_url,
        "title": data.get("title") or "YouTube Video",
        "author": data.get("author") or "",
        "videoId": extract_youtube_id(original_url),
        "currentTime": float(data.get("currentTime") or youtube_time_from_url(original_url)),
        "duration": float(data.get("duration") or 0),
        "transcript": transcript,
        "summary": "",
        "language": data.get("language") or "",
        "transcribePermalink": "",
        "transcribeSource": "defuddle-youtube-captions",
        "captionTracks": [],
    }


def normalize_usetranscribe_cached(data: dict, original_url: str) -> dict:
    transcript = data.get("transcript") or {}
    segments = transcript.get("segments") or []
    return {
        "kind": "youtube",
        "url": data.get("source_url") or original_url,
        "title": data.get("title") or "YouTube Video",
        "author": data.get("creator") or "",
        "videoId": data.get("external_id") or extract_youtube_id(original_url),
        "currentTime": youtube_time_from_url(original_url),
        "duration": float(data.get("duration_seconds") or 0),
        "transcript": transcript_from_segments(segments),
        "summary": data.get("summary") or "",
        "language": transcript.get("language") or "",
        "transcribePermalink": data.get("permalink") or "",
        "transcribeSource": data.get("pipeline_version") or "cached",
        "captionTracks": [],
    }


def normalize_usetranscribe_done(data: dict, original_url: str) -> dict:
    metadata = data.get("metadata") or {}
    permalink = absolutize_transcribe_permalink(str(data.get("permalink") or ""))
    return {
        "kind": "youtube",
        "url": metadata.get("source_url") or original_url,
        "title": metadata.get("title") or "YouTube Video",
        "author": metadata.get("creator") or metadata.get("channel") or "",
        "videoId": metadata.get("external_id") or extract_youtube_id(original_url),
        "currentTime": youtube_time_from_url(original_url),
        "duration": float(metadata.get("duration_seconds") or 0),
        "transcript": transcript_from_segments(data.get("segments") or []),
        "summary": data.get("summary_md") or "",
        "language": data.get("language") or "",
        "transcribePermalink": permalink,
        "transcribeSource": data.get("source") or "",
        "captionTracks": [],
    }


def fetch_usetranscribe_cached(video_id: str, original_url: str) -> dict | None:
    query = urllib.parse.urlencode({"platform": "youtube", "id": video_id})
    check = request_json(f"{usetranscribe_base_url()}/api/check?{query}")
    if not check.get("cached"):
        return None
    permalink = absolutize_transcribe_permalink(str(check.get("permalink") or ""))
    separator = "&" if "?" in permalink else "?"
    data = request_json(f"{permalink}{separator}format=json")
    return normalize_usetranscribe_cached(data, original_url)


def fetch_usetranscribe_sse(url: str) -> dict:
    query = urllib.parse.urlencode({"url": url, "summarize": "1"})
    request = urllib.request.Request(
        f"{usetranscribe_base_url()}/transcribe?{query}",
        headers={"Accept": "text/event-stream", "User-Agent": CAPTURE_USER_AGENT},
    )
    event = ""
    data_lines: list[str] = []

    def consume_event() -> dict | None:
        nonlocal event, data_lines
        if not event:
            data_lines = []
            return None
        payload = "\n".join(data_lines).strip()
        current_event = event
        event = ""
        data_lines = []
        if not payload:
            return None
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise CaptureError(f"Could not parse Transcribe {current_event} event: {exc}") from exc
        if current_event == "done":
            return data
        if current_event == "error":
            code = data.get("code", "error")
            message = data.get("message", "Transcribe failed.")
            raise CaptureError(f"Transcribe API error {code}: {message}")
        return None

    try:
        with urllib.request.urlopen(request, timeout=USETRANSCRIBE_STREAM_TIMEOUT_SECONDS) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                if not line.strip():
                    result = consume_event()
                    if result is not None:
                        return result
                    continue
                if line.startswith("event:"):
                    event = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data_lines.append(line.split(":", 1)[1].strip())
            result = consume_event()
            if result is not None:
                return result
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise CaptureError(f"Transcribe API error {exc.code}: {detail}") from exc
    raise CaptureError("Transcribe API stream ended before returning a transcript.")


def usetranscribe_youtube_data(url: str) -> dict:
    video_id = extract_youtube_id(url)
    if not video_id:
        raise CaptureError("Could not extract a YouTube video id from the URL.")
    cached = fetch_usetranscribe_cached(video_id, url)
    if cached:
        return cached
    return normalize_usetranscribe_done(fetch_usetranscribe_sse(url), url)


def youtube_data_with_fallback(url: str, defuddle_fallback: dict | None = None) -> dict:
    try:
        primary = usetranscribe_youtube_data(url)
        if str(primary.get("transcript") or "").strip():
            return primary
        raise CaptureError("Transcribe API returned no usable transcript.")
    except (CaptureError, urllib.error.URLError, ET.ParseError, json.JSONDecodeError) as primary_error:
        if defuddle_fallback:
            try:
                data = normalize_defuddle_fallback(defuddle_fallback, url)
                data["captureWarning"] = (
                    "Primary Transcribe API failed; used Defuddle YouTube captions fallback. "
                    f"Reason: {primary_error}"
                )
                return data
            except CaptureError:
                pass
        try:
            data = youtube_data_from_url(url)
            data["captureWarning"] = (
                "Primary Transcribe API and Defuddle fallback failed; used direct YouTube captions fallback. "
                f"Reason: {primary_error}"
            )
            return data
        except (CaptureError, urllib.error.URLError, ET.ParseError, json.JSONDecodeError):
            return minimal_youtube_data(url, primary_error)


def transcript_or_warning(caption_tracks: list[dict]) -> tuple[str, bool]:
    try:
        return fetch_transcript(caption_tracks), True
    except (CaptureError, urllib.error.URLError, ET.ParseError) as exc:
        return f"Transcript could not be captured automatically.\n\nReason: {exc}", False


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


def minimal_youtube_data(url: str, reason: Exception | str) -> dict:
    video_id = extract_youtube_id(url)
    title = active_window_title().replace(" - YouTube", "").strip() or f"YouTube Video {video_id}".strip()
    return {
        "kind": "youtube",
        "url": url,
        "title": title,
        "author": "",
        "videoId": video_id,
        "currentTime": youtube_time_from_url(url),
        "duration": 0,
        "captionTracks": [],
        "captureWarning": str(reason),
    }


def capture_youtube(
    browser: str | None = None,
    data: dict | None = None,
    url: str | None = None,
    replace_path: Path | None = None,
    defuddle_fallback: dict | None = None,
) -> Path:
    if data is None:
        data = (
            youtube_data_with_fallback(url, defuddle_fallback)
            if url
            else active_tab_json(browser or "", YOUTUBE_JS)
        )
    if data.get("transcript"):
        transcript, has_transcript = data["transcript"], True
    else:
        transcript, has_transcript = transcript_or_warning(data.get("captionTracks", []))
    if not has_transcript:
        warning = data.get("captureWarning", "").strip()
        reason = transcript.strip()
        details = "\n\n".join(item for item in [warning, reason] if item)
        raise CaptureError(f"YouTube transcript was not captured, so no source note was saved.\n\n{details}")
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

Transcribe permalink: {data.get("transcribePermalink", "")}

Transcribe source: {data.get("transcribeSource", "")}

Language: {data.get("language", "")}

Capture warning: {data.get("captureWarning", "")}

## Summary

{data.get("summary", "").strip()}

## Transcript

{transcript}
"""
    return write_source_note(
        title=title,
        author=author,
        reference=url,
        content_types=["youtube", "transcript" if has_transcript else "metadata", "markdown"],
        body=body,
        replace_path=replace_path,
    )
