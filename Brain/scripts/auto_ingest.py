#!/usr/bin/env python3
"""Create a deterministic Wiki ingest note for a captured Raw source."""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import wiki_tool

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "Raw" / "Sources"
LOGS = ROOT / "Wiki" / "Logs"
TOPICS = ROOT / "Wiki" / "Topics"
CAPTURE_HUB = TOPICS / "captured-sources.md"


def today() -> str:
    return dt.date.today().isoformat()


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:90] or "captured-source"


def yaml_string(value: str) -> str:
    return json.dumps(value or "")


def excerpt_from_body(body: str, max_chars: int = 900) -> str:
    body = re.sub(r"(?s)^# .+?\n", "", body).strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = body.replace("## Transcript", "Transcript")
    body = body.replace("## Article Text", "Article Text")
    if len(body) <= max_chars:
        return body
    return body[:max_chars].rsplit(" ", 1)[0].strip() + "..."


def raw_wikilink(source_path: Path, title: str) -> str:
    return f"[[{source_path.stem}|{title}]]"


def append_raw_backlink(source_path: Path, wiki_path: Path, title: str) -> None:
    text = source_path.read_text(encoding="utf-8")
    link = f"[[{wiki_path.stem}|Ingested: {title}]]"
    if link in text:
        return
    section = f"\n\n## Wiki Links\n\n- {link}\n"
    if "\n## Wiki Links\n" in text:
        text = text.rstrip() + f"\n- {link}\n"
    else:
        text = text.rstrip() + section
    source_path.write_text(text, encoding="utf-8")


def read_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def write_capture_hub(source_path: Path, source_title: str, ingest_path: Path) -> None:
    TOPICS.mkdir(parents=True, exist_ok=True)
    rel_source = wiki_tool.rel(source_path)
    rel_ingest = wiki_tool.rel(ingest_path)
    sources: list[str] = []
    entries: list[dict[str, str]] = []

    if CAPTURE_HUB.exists():
        fm, body = wiki_tool.read_frontmatter(CAPTURE_HUB)
        sources = read_list(fm.get("sources"))
        for match in re.finditer(r"^- \[\[(.+?)\|(.+?)\]\] from \[\[(.+?)\|(.+?)\]\]$", body, re.MULTILINE):
            entries.append(
                {
                    "ingest_stem": match.group(1),
                    "ingest_title": match.group(2),
                    "source_stem": match.group(3),
                    "source_title": match.group(4),
                }
            )

    if rel_source not in sources:
        sources.append(rel_source)

    entry = {
        "ingest_stem": ingest_path.stem,
        "ingest_title": f"{source_title} Ingest",
        "source_stem": source_path.stem,
        "source_title": source_title,
    }
    entries = [item for item in entries if item["source_stem"] != source_path.stem]
    entries.append(entry)

    frontmatter = [
        "---",
        "tags:",
        '  - "topic"',
        "topics: []",
        "status: seed",
        f"created: {today()}",
        f"updated: {today()}",
        "sources:",
        *[f"  - {yaml_string(source)}" for source in sorted(sources)],
        f"source_count: {len(set(sources))}",
        "aliases:",
        '  - "ATB Captures"',
        '  - "Captured Sources"',
        "---",
        "",
    ]
    lines = [
        "# Captured Sources",
        "",
        "This topic is the automatic graph hub for sources captured through Add to Brain.",
        "",
        "## Captures",
        "",
    ]
    for item in sorted(entries, key=lambda value: value["source_title"].lower()):
        lines.append(
            f"- [[{item['ingest_stem']}|{item['ingest_title']}]] from [[{item['source_stem']}|{item['source_title']}]]"
        )
    lines.append("")
    CAPTURE_HUB.write_text("\n".join(frontmatter) + "\n".join(lines), encoding="utf-8")


def ingest_source(source: str | Path) -> Path:
    source_path = Path(source)
    if not source_path.is_absolute():
        source_path = ROOT / source_path
    if not source_path.exists() or RAW not in source_path.parents:
        raise ValueError(f"source must exist under Raw/Sources: {source}")

    fm, body = wiki_tool.read_frontmatter(source_path)
    title = wiki_tool.title_for(source_path, fm, body)
    rel_source = wiki_tool.rel(source_path)
    LOGS.mkdir(parents=True, exist_ok=True)
    wiki_path = LOGS / f"{slugify(source_path.stem)}-ingest.md"
    summary = excerpt_from_body(body)

    frontmatter = [
        "---",
        "tags:",
        '  - "log"',
        "topics: []",
        "status: seed",
        f"created: {today()}",
        f"updated: {today()}",
        "sources:",
        f"  - {yaml_string(rel_source)}",
        "source_count: 1",
        "aliases: []",
        "---",
        "",
    ]
    note = f"""# {title} Ingest

Source: {raw_wikilink(source_path, title)}

Hub: [[captured-sources|Captured Sources]]

## Captured Summary

{summary}

## Follow-Up

- Promote durable claims into topic, concept, entity, or project notes when reviewing this source.
"""
    wiki_path.write_text("\n".join(frontmatter) + note, encoding="utf-8")
    append_raw_backlink(source_path, wiki_path, title)
    write_capture_hub(source_path, title, wiki_path)
    return wiki_path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: auto_ingest.py Raw/Sources/source.md", file=sys.stderr)
        return 2
    try:
        path = ingest_source(sys.argv[1])
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(wiki_tool.rel(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
