#!/usr/bin/env python3
"""Deterministic maintenance tool for the LLM Wiki."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "Raw" / "Sources"
WIKI = ROOT / "Wiki"
SCHEMA = ROOT / "Schema"
CATALOG = WIKI / "catalog.jsonl"
MANIFEST = SCHEMA / "source-manifest.jsonl"
ALLOWED_TAGS = {"topic", "concept", "entity", "project", "log"}
WIKI_FOLDERS = ["Topics", "Concepts", "Entities", "Projects", "Logs"]
REQUIRED_FOLDERS = [
    "Raw/Sources",
    "Raw/Files",
    "Wiki/Topics",
    "Wiki/Concepts",
    "Wiki/Entities",
    "Wiki/Projects",
    "Wiki/Logs",
    "Schema",
    "_templates",
    ".agents/skills",
    "scripts",
    "tutorial",
]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def today() -> str:
    return dt.date.today().isoformat()


def read_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].splitlines()
    body = text[end + 4 :].lstrip("\n")
    data: dict[str, object] = {}
    i = 0
    while i < len(raw):
        line = raw[i]
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            i += 1
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            items: list[str] = []
            i += 1
            while i < len(raw) and raw[i].startswith("  - "):
                items.append(clean_scalar(raw[i][4:].strip()))
                i += 1
            data[key] = items
            continue
        data[key] = parse_scalar(value)
        i += 1
    return data, body


def clean_scalar(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_scalar(value: str):
    value = clean_scalar(value)
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [clean_scalar(part.strip()) for part in inner.split(",")]
    if value.isdigit():
        return int(value)
    return value


def title_for(path: Path, frontmatter: dict, body: str) -> str:
    for key in ("title", "Title"):
        if frontmatter.get(key):
            return str(frontmatter[key])
    match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return path.stem.replace("-", " ").title()


def wiki_note_paths() -> list[Path]:
    paths: list[Path] = []
    for folder in WIKI_FOLDERS:
        paths.extend((WIKI / folder).glob("*.md"))
    return sorted(path for path in paths if path.name != "index.md")


def source_paths() -> list[Path]:
    return sorted(RAW.glob("*.md"))


def catalog_rows() -> list[dict]:
    rows = []
    for path in wiki_note_paths():
        fm, body = read_frontmatter(path)
        tags = fm.get("tags", [])
        tag = tags[0] if isinstance(tags, list) and tags else ""
        rows.append(
            {
                "path": rel(path),
                "title": title_for(path, fm, body),
                "tag": tag,
                "topics": fm.get("topics", []),
                "sources": fm.get("sources", []),
                "updated": fm.get("updated", ""),
            }
        )
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def build_indexes(rows: list[dict]) -> None:
    grouped = {folder: [] for folder in WIKI_FOLDERS}
    for row in rows:
        parts = row["path"].split("/")
        if len(parts) > 2 and parts[1] in grouped:
            grouped[parts[1]].append(row)

    lines = ["# Wiki Index", "", f"Updated: {today()}", ""]
    for folder in WIKI_FOLDERS:
        lines.append(f"## {folder}")
        if grouped[folder]:
            for row in sorted(grouped[folder], key=lambda item: item["title"].lower()):
                lines.append(f"- [[{Path(row['path']).stem}|{row['title']}]]")
        else:
            lines.append("- No notes yet.")
        lines.append("")
    (WIKI / "index.md").write_text("\n".join(lines), encoding="utf-8")

    for folder, folder_rows in grouped.items():
        folder_path = WIKI / folder
        lines = [f"# {folder} Index", "", f"Updated: {today()}", ""]
        if folder_rows:
            for row in sorted(folder_rows, key=lambda item: item["title"].lower()):
                lines.append(f"- [[{Path(row['path']).stem}|{row['title']}]]")
        else:
            lines.append("- No notes yet.")
        lines.append("")
        (folder_path / "index.md").write_text("\n".join(lines), encoding="utf-8")


def cmd_build(_args) -> int:
    rows = catalog_rows()
    write_jsonl(CATALOG, rows)
    build_indexes(rows)
    print(f"built catalog with {len(rows)} notes")
    return 0


def cmd_doctor(_args) -> int:
    errors = []
    print(f"vault: {ROOT}")
    print(f"python: {platform.python_version()}")
    for folder in REQUIRED_FOLDERS:
        status = "ok" if (ROOT / folder).is_dir() else "missing"
        print(f"folder {folder}: {status}")
        if status != "ok":
            errors.append(f"missing folder: {folder}")
    obsidian = ROOT / ".obsidian"
    print(f"obsidian vault: {'ok' if obsidian.is_dir() else 'missing'}")
    for name in ["app.json", "appearance.json", "core-plugins.json", "graph.json"]:
        path = obsidian / name
        print(f"obsidian {name}: {'ok' if path.exists() else 'missing'}")
    print(f"catalog: {'ok' if CATALOG.exists() else 'missing'}")
    print(f"source manifest: {'ok' if MANIFEST.exists() else 'missing'}")
    print(f"raw sources: {len(source_paths())}")
    print(f"compiled notes: {len(wiki_note_paths())}")
    return fail(errors)


def lint_compiled_note(path: Path) -> list[str]:
    errors = []
    fm, _body = read_frontmatter(path)
    if not fm:
        return [f"{rel(path)}: missing frontmatter"]
    tags = fm.get("tags", [])
    if not isinstance(tags, list) or len(tags) != 1 or tags[0] not in ALLOWED_TAGS:
        errors.append(f"{rel(path)}: must use exactly one allowed tag")
    sources = fm.get("sources", [])
    if not isinstance(sources, list) or not sources:
        errors.append(f"{rel(path)}: sources must contain at least one Raw source")
        sources = []
    if fm.get("source_count") != len(sources):
        errors.append(f"{rel(path)}: source_count must equal number of sources")
    for source in sources:
        source_path = ROOT / source
        if not str(source).startswith("Raw/Sources/") or not source_path.exists():
            errors.append(f"{rel(path)}: source does not exist under Raw/Sources: {source}")
    return errors


def cmd_lint(_args) -> int:
    errors = []
    for path in wiki_note_paths():
        errors.extend(lint_compiled_note(path))
    if not CATALOG.exists():
        errors.append("Wiki/catalog.jsonl is missing; run build")
    return fail(errors, "lint passed")


def source_record(path: Path, coverage: dict[str, list[str]] | None = None) -> dict:
    fm, body = read_frontmatter(path)
    covered_by = sorted((coverage or {}).get(rel(path), []))
    return {
        "path": rel(path),
        "title": title_for(path, fm, body),
        "processed": bool(fm.get("Processed", False)),
        "covered_by": covered_by,
        "updated": today(),
    }


def coverage_map() -> dict[str, list[str]]:
    coverage: dict[str, list[str]] = {}
    for path in wiki_note_paths():
        fm, _body = read_frontmatter(path)
        sources = fm.get("sources", [])
        if not isinstance(sources, list):
            continue
        for source in sources:
            coverage.setdefault(source, []).append(rel(path))
    return coverage


def cmd_source_scan(args) -> int:
    coverage = coverage_map()
    rows = []
    for path in source_paths():
        record = source_record(path, coverage)
        if args.accept_covered and record["covered_by"]:
            record["processed"] = True
        rows.append(record)
    for row in rows:
        print(json.dumps(row, sort_keys=True))
    if args.update:
        write_jsonl(MANIFEST, rows)
        print(f"updated {rel(MANIFEST)}")
    return 0


def cmd_source_lint(_args) -> int:
    errors = []
    coverage = coverage_map()
    for path in source_paths():
        fm, _body = read_frontmatter(path)
        for key in ["Title", "Reference", "Created", "Processed", "tags"]:
            if key not in fm:
                errors.append(f"{rel(path)}: missing {key}")
        tags = fm.get("tags", [])
        if not isinstance(tags, list) or "source" not in tags:
            errors.append(f"{rel(path)}: tags must include source")
        if fm.get("Processed") is True and not coverage.get(rel(path)):
            errors.append(f"{rel(path)}: processed source has no Wiki coverage")
    if source_paths() and not MANIFEST.exists():
        errors.append("Schema/source-manifest.jsonl is missing; run source-scan --update")
    return fail(errors, "source lint passed")


def cmd_source_delta(_args) -> int:
    manifest_paths = {row["path"] for row in read_jsonl(MANIFEST)}
    delta = [rel(path) for path in source_paths() if rel(path) not in manifest_paths]
    for path in delta:
        print(path)
    if not delta:
        print("no source delta")
    return 0


def cmd_source_coverage(_args) -> int:
    coverage = coverage_map()
    for path in source_paths():
        covered_by = coverage.get(rel(path), [])
        print(json.dumps({"path": rel(path), "covered_by": covered_by}, sort_keys=True))
    return 0


def cmd_search_catalog(args) -> int:
    query = args.query.lower()
    matches = []
    for row in read_jsonl(CATALOG):
        haystack = " ".join(
            [
                row.get("path", ""),
                row.get("title", ""),
                row.get("tag", ""),
                " ".join(row.get("topics", [])),
            ]
        ).lower()
        if query in haystack:
            matches.append(row)
    for row in matches:
        print(json.dumps(row, sort_keys=True))
    if not matches:
        print("no matches")
    return 0


def cmd_log(args) -> int:
    path = WIKI / "log.md"
    entry = f"\n## {today()} - {args.title}\n\n{args.details}\n"
    if not path.exists():
        path.write_text("# Wiki Log\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(entry)
    print(f"appended {rel(path)}")
    return 0


def fail(errors: list[str], ok_message: str = "doctor passed") -> int:
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(ok_message)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor").set_defaults(func=cmd_doctor)
    sub.add_parser("build").set_defaults(func=cmd_build)
    sub.add_parser("lint").set_defaults(func=cmd_lint)
    scan = sub.add_parser("source-scan")
    scan.add_argument("--update", action="store_true")
    scan.add_argument("--accept-covered", action="store_true")
    scan.set_defaults(func=cmd_source_scan)
    sub.add_parser("source-lint").set_defaults(func=cmd_source_lint)
    sub.add_parser("source-delta").set_defaults(func=cmd_source_delta)
    sub.add_parser("source-coverage").set_defaults(func=cmd_source_coverage)
    search = sub.add_parser("search-catalog")
    search.add_argument("--query", required=True)
    search.set_defaults(func=cmd_search_catalog)
    log = sub.add_parser("log")
    log.add_argument("--title", required=True)
    log.add_argument("--details", required=True)
    log.set_defaults(func=cmd_log)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
