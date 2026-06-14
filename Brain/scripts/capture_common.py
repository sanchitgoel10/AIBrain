#!/usr/bin/env python3
"""Shared capture helpers for AI Brain source capture."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "Raw" / "Sources"
WIKI_TOOL = ROOT / "scripts" / "wiki_tool.py"
CAPTURE_USER_AGENT = "AIBrainCapture/0.1 (+local Obsidian vault)"


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


def is_capture_url(url: str) -> bool:
    if not re.match(r"^https?://", url or ""):
        return False
    parsed = urllib.parse.urlparse(url)
    blocked_prefixes = ("chrome.", "newtab.", "dia.")
    blocked_suffixes = (
        "accounts.google.com",
        "chatgpt.com",
        "contacts.google.com",
        "gemini.google.com",
        "googleusercontent.com",
        "googlevideo.com",
        "mail.google.com",
        "netflix.com",
        "plausible.io",
        "studio.workspace.google.com",
        "usetranscribe.io",
    )
    host = parsed.netloc.lower()
    if any(host.startswith(prefix) for prefix in blocked_prefixes):
        return False
    return not any(host == suffix or host.endswith(f".{suffix}") for suffix in blocked_suffixes)


def hostname_label(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    return host.removeprefix("www.") or "URL"


def load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


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
    replace_path: Path | None = None,
) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    base = slugify(title)
    path = replace_path.resolve() if replace_path else RAW / f"{base}.md"
    if replace_path and (path.parent != RAW.resolve() or path.suffix.lower() != ".md"):
        raise CaptureError("Replacement source must be a Markdown file under Raw/Sources.")
    if not replace_path and path.exists():
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
