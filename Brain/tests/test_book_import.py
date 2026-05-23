from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import book_import


def write_epub(path: Path, *, title: str = "Test Book", author: str = "Local Author") -> None:
    container = """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    opf = f"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:language>en</dc:language>
    <dc:identifier>test-id</dc:identifier>
  </metadata>
  <manifest>
    <item id="c1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="c1"/>
  </spine>
</package>
"""
    chapter = """<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Opening</title></head>
<body>
  <h1>Opening</h1>
  <p>This is a book chapter about durable notes.</p>
  <p>Books should become raw sources before wiki notes.</p>
</body>
</html>
"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OEBPS/content.opf", opf)
        archive.writestr("OEBPS/chapter1.xhtml", chapter)


class BookImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.original_root = book_import.ROOT
        self.original_raw_sources = book_import.RAW_SOURCES
        book_import.ROOT = self.root
        book_import.RAW_SOURCES = self.root / "Raw" / "Sources"
        self.addCleanup(self.restore_globals)

    def restore_globals(self) -> None:
        book_import.ROOT = self.original_root
        book_import.RAW_SOURCES = self.original_raw_sources

    def test_read_epub_extracts_metadata_and_chapters(self) -> None:
        epub = self.root / "Raw" / "Files" / "test-book.epub"
        epub.parent.mkdir(parents=True)
        write_epub(epub)

        book = book_import.read_epub(epub)

        self.assertEqual(book.title, "Test Book")
        self.assertEqual(book.author, "Local Author")
        self.assertEqual(book.language, "en")
        self.assertEqual(len(book.chapters), 1)
        self.assertEqual(book.chapters[0].title, "Opening")
        self.assertFalse(book.chapters[0].text.startswith("Opening\n"))
        self.assertIn("durable notes", book.chapters[0].text)

    def test_import_epub_writes_raw_source_note(self) -> None:
        epub = self.root / "Raw" / "Files" / "test-book.epub"
        epub.parent.mkdir(parents=True)
        write_epub(epub)

        result = book_import.import_epub(epub)

        self.assertEqual(result, self.root / "Raw" / "Sources" / "test-book.md")
        text = result.read_text(encoding="utf-8")
        self.assertIn('Title: "Test Book"', text)
        self.assertIn('  - "epub"', text)
        self.assertIn('  - "book"', text)
        self.assertIn("Original file: Raw/Files/test-book.epub", text)
        self.assertIn("### Opening", text)

    def test_dry_run_does_not_write_source_note(self) -> None:
        epub = self.root / "Raw" / "Files" / "test-book.epub"
        epub.parent.mkdir(parents=True)
        write_epub(epub)

        result = book_import.import_epub(epub, dry_run=True)

        self.assertIsInstance(result, str)
        self.assertIn("# Test Book", result)
        self.assertFalse((self.root / "Raw" / "Sources").exists())


if __name__ == "__main__":
    unittest.main()
