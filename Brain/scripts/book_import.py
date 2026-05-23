#!/usr/bin/env python3
"""Import EPUB books into Raw/Sources as deterministic Markdown source notes."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import posixpath
import re
import sys
import urllib.parse
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_SOURCES = ROOT / "Raw" / "Sources"


class BookImportError(RuntimeError):
    pass


@dataclass
class Chapter:
    href: str
    title: str
    text: str


@dataclass
class EpubBook:
    title: str
    author: str
    date: str
    language: str
    identifier: str
    chapters: list[Chapter]


def today() -> str:
    return dt.date.today().isoformat()


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:90] or "book"


def yaml_string(value: str) -> str:
    return json.dumps(value or "")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def elem_text(root: ET.Element, *names: str) -> str:
    wanted = {name.lower() for name in names}
    for elem in root.iter():
        if local_name(elem.tag) in wanted and elem.text:
            return re.sub(r"\s+", " ", elem.text).strip()
    return ""


def rel_or_name(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def opf_path_from_container(epub: zipfile.ZipFile) -> str:
    try:
        raw = epub.read("META-INF/container.xml")
    except KeyError as exc:
        raise BookImportError("EPUB is missing META-INF/container.xml.") from exc
    root = ET.fromstring(raw)
    for elem in root.iter():
        if local_name(elem.tag) == "rootfile":
            path = elem.attrib.get("full-path", "").strip()
            if path:
                return path
    raise BookImportError("EPUB container does not declare an OPF package file.")


def normalize_zip_path(base: str, href: str) -> str:
    href = urllib.parse.unquote(href.split("#", 1)[0])
    return posixpath.normpath(posixpath.join(posixpath.dirname(base), href))


def strip_markup(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style|svg|head)\b.*?</\1>", " ", markup)
    markup = re.sub(r"(?i)<br\s*/?>", "\n", markup)
    markup = re.sub(r"(?i)</(p|div|section|article|li|blockquote|tr|h[1-6])>", "\n", markup)
    markup = re.sub(r"(?i)<(p|div|section|article|li|blockquote|tr|h[1-6])\b[^>]*>", "\n", markup)
    markup = re.sub(r"(?s)<[^>]+>", " ", markup)
    text = html.unescape(markup)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def html_title(markup: str) -> str:
    for tag in ["h1", "h2", "title"]:
        match = re.search(rf"(?is)<{tag}\b[^>]*>(.*?)</{tag}>", markup)
        if match:
            return strip_markup(match.group(1))
    return ""


def drop_repeated_heading(title: str, text: str) -> str:
    if not title:
        return text
    lines = text.splitlines()
    if lines and lines[0].strip().casefold() == title.strip().casefold():
        return "\n".join(lines[1:]).lstrip()
    return text


def read_epub(path: Path) -> EpubBook:
    if not path.exists():
        raise BookImportError(f"EPUB file does not exist: {path}")
    if path.suffix.lower() != ".epub":
        raise BookImportError("Book importer expects a .epub file.")

    with zipfile.ZipFile(path) as epub:
        opf_path = opf_path_from_container(epub)
        try:
            opf = ET.fromstring(epub.read(opf_path))
        except KeyError as exc:
            raise BookImportError(f"EPUB package file is missing: {opf_path}") from exc

        title = elem_text(opf, "title") or path.stem.replace("-", " ").title()
        author = elem_text(opf, "creator")
        date = elem_text(opf, "date")
        language = elem_text(opf, "language")
        identifier = elem_text(opf, "identifier")

        manifest: dict[str, dict[str, str]] = {}
        for elem in opf.iter():
            if local_name(elem.tag) != "item":
                continue
            item_id = elem.attrib.get("id", "")
            href = elem.attrib.get("href", "")
            media_type = elem.attrib.get("media-type", "")
            if item_id and href:
                manifest[item_id] = {"href": normalize_zip_path(opf_path, href), "media_type": media_type}

        spine_ids = [
            elem.attrib.get("idref", "")
            for elem in opf.iter()
            if local_name(elem.tag) == "itemref" and elem.attrib.get("idref")
        ]
        ordered_hrefs = [
            manifest[item_id]["href"]
            for item_id in spine_ids
            if item_id in manifest and "html" in manifest[item_id].get("media_type", "")
        ]
        if not ordered_hrefs:
            ordered_hrefs = [
                item["href"]
                for item in manifest.values()
                if "html" in item.get("media_type", "")
            ]

        chapters: list[Chapter] = []
        seen: set[str] = set()
        for href in ordered_hrefs:
            if href in seen:
                continue
            seen.add(href)
            try:
                markup = epub.read(href).decode("utf-8", errors="replace")
            except KeyError:
                continue
            text = strip_markup(markup)
            if not text:
                continue
            chapter_title = html_title(markup)
            chapters.append(
                Chapter(
                    href=href,
                    title=chapter_title,
                    text=drop_repeated_heading(chapter_title, text),
                )
            )

    if not chapters:
        raise BookImportError("No readable XHTML/HTML chapters were found in the EPUB.")
    return EpubBook(title=title, author=author, date=date, language=language, identifier=identifier, chapters=chapters)


def source_markdown(epub_path: Path, book: EpubBook, *, max_chars: int = 0) -> str:
    reference = rel_or_name(epub_path)
    lines = [
        f"# {book.title}",
        "",
        "Source type: Book",
        "",
        f"Original file: {reference}",
        "",
        f"Author: {book.author}",
        "",
        f"Published: {book.date}",
        "",
        f"Language: {book.language}",
        "",
        f"Identifier: {book.identifier}",
        "",
        "## Book Text",
        "",
    ]
    for index, chapter in enumerate(book.chapters, start=1):
        title = chapter.title or f"Chapter {index}"
        lines.extend([f"### {title}", "", chapter.text, ""])

    body = "\n".join(lines).strip() + "\n"
    if max_chars and len(body) > max_chars:
        body = body[:max_chars].rsplit(" ", 1)[0].strip()
        body += "\n\n[Book text truncated by import max character limit. Re-run without --max-chars for full text.]\n"
    return body


def frontmatter(book: EpubBook, epub_path: Path) -> str:
    return "\n".join(
        [
            "---",
            f"Title: {yaml_string(book.title)}",
            f"Author: {yaml_string(book.author)}",
            f"Reference: {yaml_string(rel_or_name(epub_path))}",
            "ContentType:",
            '  - "epub"',
            '  - "book"',
            '  - "markdown"',
            f"Created: {today()}",
            "Processed: false",
            "tags:",
            '  - "source"',
            "---",
            "",
        ]
    )


def unique_source_path(title: str) -> Path:
    RAW_SOURCES.mkdir(parents=True, exist_ok=True)
    base = slugify(title)
    path = RAW_SOURCES / f"{base}.md"
    if not path.exists():
        return path
    suffix = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return RAW_SOURCES / f"{base}-{suffix}.md"


def import_epub(
    epub_path: str | Path,
    *,
    title: str = "",
    author: str = "",
    max_chars: int = 0,
    dry_run: bool = False,
) -> Path | str:
    path = Path(epub_path).expanduser()
    book = read_epub(path)
    if title:
        book.title = title
    if author:
        book.author = author
    markdown = frontmatter(book, path) + source_markdown(path, book, max_chars=max_chars)
    if dry_run:
        return markdown
    target = unique_source_path(book.title)
    target.write_text(markdown, encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("epub", help="Path to a .epub file, preferably under Raw/Files/.")
    parser.add_argument("--title", default="", help="Override the EPUB title metadata.")
    parser.add_argument("--author", default="", help="Override the EPUB author metadata.")
    parser.add_argument("--max-chars", type=int, default=0, help="Optional maximum body size for very large books.")
    parser.add_argument("--dry-run", action="store_true", help="Print the generated source note instead of writing it.")
    args = parser.parse_args()
    try:
        result = import_epub(
            args.epub,
            title=args.title,
            author=args.author,
            max_chars=args.max_chars,
            dry_run=args.dry_run,
        )
    except (BookImportError, zipfile.BadZipFile, ET.ParseError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.dry_run:
        print(result)
    else:
        print(Path(result).relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
