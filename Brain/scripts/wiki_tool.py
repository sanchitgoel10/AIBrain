#!/usr/bin/env python3
"""Deterministic maintenance tool for the LLM Wiki."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

import brain_ask
from capture_common import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "Raw" / "Sources"
WIKI = ROOT / "Wiki"
SCHEMA = ROOT / "Schema"
CATALOG = WIKI / "catalog.jsonl"
MANIFEST = SCHEMA / "source-manifest.jsonl"
CAPTURE_STATE = ROOT / ".aibrain" / "capture-state.json"
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


def yaml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[]"
    return json.dumps(str(value), ensure_ascii=False)


def format_frontmatter(frontmatter: dict) -> str:
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            if value:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {json.dumps(str(item), ensure_ascii=False)}")
            else:
                lines.append(f"{key}: []")
        else:
            lines.append(f"{key}: {yaml_value(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def write_note(path: Path, frontmatter: dict, body: str) -> None:
    path.write_text(format_frontmatter(frontmatter) + "\n" + body.lstrip("\n"), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def reset_capture_counter() -> dict:
    state: dict = {}
    if CAPTURE_STATE.exists():
        try:
            state = json.loads(CAPTURE_STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}
    state["captures_since_compile"] = 0
    state["last_compile_reset_at"] = dt.datetime.now().timestamp()
    CAPTURE_STATE.parent.mkdir(parents=True, exist_ok=True)
    CAPTURE_STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return state


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


def cmd_reset_capture_counter(_args) -> int:
    state = reset_capture_counter()
    print(json.dumps(state, sort_keys=True))
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


def tokens(text: str) -> set[str]:
    stop = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "what",
        "which",
        "with",
    }
    return {token for token in re.findall(r"[a-z0-9][a-z0-9-]+", text.lower()) if token not in stop}


def note_excerpt(body: str, query_tokens: set[str], max_chars: int = 240) -> str:
    body = re.sub(r"\s+", " ", body).strip()
    if not body:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", body)
    best = max(
        sentences,
        key=lambda sentence: len(tokens(sentence) & query_tokens),
        default=body[:max_chars],
    )
    if len(best) <= max_chars:
        return best
    return best[: max_chars - 1].rstrip() + "..."


def ask_matches(query: str, limit: int = 5) -> list[dict]:
    results = brain_ask.search(query, root=ROOT, limit=limit)
    matches = []
    for result in results:
        matches.append(
            {
                "path": result.get("path", ""),
                "title": result.get("title", ""),
                "tag": result.get("kind", ""),
                "sources": [],
                "score": result.get("score", 0),
                "matched_terms": sorted(tokens(query)),
                "excerpt": result.get("snippet", ""),
            }
        )
    return matches


def cmd_ask(args) -> int:
    payload = brain_ask.answer(args.query, root=ROOT, limit=args.limit)
    if not payload["results"]:
        print("no brain matches")
        return 0
    print(json.dumps(payload, sort_keys=True))
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


def cmd_import_epub(args) -> int:
    import book_import

    try:
        result = book_import.import_epub(
            args.epub,
            title=args.title,
            author=args.author,
            max_chars=args.max_chars,
            dry_run=args.dry_run,
        )
    except (
        book_import.BookImportError,
        book_import.zipfile.BadZipFile,
        book_import.ET.ParseError,
        OSError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.dry_run:
        print(result)
        return 0

    source_path = Path(result)
    print(rel(source_path))
    if not args.ingest:
        return 0

    import auto_ingest

    ingest_path = auto_ingest.ingest_source(source_path)
    print(rel(ingest_path))
    cmd_build(argparse.Namespace())
    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "source-scan",
            "--update",
            "--accept-covered",
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "source-lint"],
        cwd=ROOT,
        check=True,
    )
    return 0


def source_rel_from_arg(source: str) -> str:
    path = Path(source)
    if path.is_absolute():
        try:
            return path.relative_to(ROOT).as_posix()
        except ValueError as exc:
            raise ValueError(f"source must be inside this vault: {source}") from exc
    value = path.as_posix()
    if value.startswith("Raw/Sources/"):
        return value
    return f"Raw/Sources/{path.name}"


def purge_plan(source: str) -> dict:
    source_rel = source_rel_from_arg(source)
    source_path = ROOT / source_rel
    if not source_rel.startswith("Raw/Sources/"):
        raise ValueError("source must be under Raw/Sources")
    delete_notes: list[str] = []
    update_notes: list[dict] = []
    for path in wiki_note_paths():
        fm, body = read_frontmatter(path)
        sources = fm.get("sources", [])
        if not isinstance(sources, list) or source_rel not in sources:
            continue
        remaining = [item for item in sources if item != source_rel]
        if remaining:
            update_notes.append(
                {
                    "path": rel(path),
                    "remaining_sources": remaining,
                    "source_count": len(remaining),
                }
            )
        else:
            delete_notes.append(rel(path))
    return {
        "source": source_rel,
        "source_exists": source_path.exists(),
        "delete_source": source_path.exists(),
        "delete_notes": sorted(delete_notes),
        "update_notes": sorted(update_notes, key=lambda item: item["path"]),
    }


def remove_source_links_from_body(body: str, source_stem: str, deleted_note_stems: set[str]) -> str:
    lines = []
    stems = {source_stem, *deleted_note_stems}
    for line in body.splitlines():
        stripped = line.lstrip()
        is_list_line = stripped.startswith(("- ", "* "))
        if is_list_line and any(f"[[{stem}" in line for stem in stems):
            continue
        for stem in stems:
            line = re.sub(rf"\s*(?:and\s+)?\[\[{re.escape(stem)}(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]", "", line)
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def apply_purge(plan: dict) -> None:
    source_rel = plan["source"]
    source_path = ROOT / source_rel
    source_stem = source_path.stem
    deleted_note_stems = {Path(path).stem for path in plan["delete_notes"]}

    for note_rel in plan["delete_notes"]:
        note_path = ROOT / note_rel
        if note_path.exists():
            note_path.unlink()

    for item in plan["update_notes"]:
        note_path = ROOT / item["path"]
        fm, body = read_frontmatter(note_path)
        fm["sources"] = item["remaining_sources"]
        fm["source_count"] = item["source_count"]
        fm["updated"] = today()
        write_note(note_path, fm, remove_source_links_from_body(body, source_stem, deleted_note_stems))

    for path in list(wiki_note_paths()) + [WIKI / "index.md"]:
        if not path.exists():
            continue
        fm, body = read_frontmatter(path)
        new_body = remove_source_links_from_body(body, source_stem, deleted_note_stems)
        if new_body != body:
            if fm:
                write_note(path, fm, new_body)
            else:
                path.write_text(new_body, encoding="utf-8")

    if source_path.exists():
        source_path.unlink()


def cmd_purge_source(args) -> int:
    try:
        plan = purge_plan(args.source)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(plan, indent=2, sort_keys=True))
    if not args.apply:
        print("dry run only; rerun with --apply to delete/update these files")
        return 0
    apply_purge(plan)
    cmd_build(argparse.Namespace())
    cmd_source_scan(argparse.Namespace(update=True, accept_covered=True))
    result = cmd_source_lint(argparse.Namespace())
    if result == 0:
        print(f"purged {plan['source']}")
    return result


def fail(errors: list[str], ok_message: str = "doctor passed") -> int:
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(ok_message)
    return 0


def main() -> int:
    load_dotenv()
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
    sub.add_parser("reset-capture-counter").set_defaults(func=cmd_reset_capture_counter)
    search = sub.add_parser("search-catalog")
    search.add_argument("--query", required=True)
    search.set_defaults(func=cmd_search_catalog)
    ask = sub.add_parser("ask")
    ask.add_argument("--query", required=True)
    ask.add_argument("--limit", type=int, default=5)
    ask.set_defaults(func=cmd_ask)
    log = sub.add_parser("log")
    log.add_argument("--title", required=True)
    log.add_argument("--details", required=True)
    log.set_defaults(func=cmd_log)
    epub = sub.add_parser("import-epub")
    epub.add_argument("epub", help="Path to a .epub file, preferably under Raw/Files/.")
    epub.add_argument("--title", default="", help="Override the EPUB title metadata.")
    epub.add_argument("--author", default="", help="Override the EPUB author metadata.")
    epub.add_argument("--max-chars", type=int, default=0, help="Optional maximum body size for very large books.")
    epub.add_argument("--dry-run", action="store_true", help="Print the generated Raw source note without writing it.")
    epub.add_argument("--ingest", action="store_true", help="Create a linked Wiki ingest note and update indexes.")
    epub.set_defaults(func=cmd_import_epub)
    purge = sub.add_parser("purge-source")
    purge.add_argument("source", help="Raw source path or filename to remove from the brain.")
    purge.add_argument("--apply", action="store_true", help="Actually delete/update files. Without this, only prints the plan.")
    purge.set_defaults(func=cmd_purge_source)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
