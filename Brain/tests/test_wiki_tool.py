from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import wiki_tool


class WikiToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.originals = {
            "ROOT": wiki_tool.ROOT,
            "RAW": wiki_tool.RAW,
            "WIKI": wiki_tool.WIKI,
            "SCHEMA": wiki_tool.SCHEMA,
            "CATALOG": wiki_tool.CATALOG,
            "MANIFEST": wiki_tool.MANIFEST,
        }
        wiki_tool.ROOT = self.root
        wiki_tool.RAW = self.root / "Raw" / "Sources"
        wiki_tool.WIKI = self.root / "Wiki"
        wiki_tool.SCHEMA = self.root / "Schema"
        wiki_tool.CATALOG = wiki_tool.WIKI / "catalog.jsonl"
        wiki_tool.MANIFEST = wiki_tool.SCHEMA / "source-manifest.jsonl"
        self.addCleanup(self.restore_globals)
        for folder in ["Raw/Sources", "Wiki/Concepts", "Wiki/Topics", "Wiki/Entities", "Wiki/Projects", "Wiki/Logs", "Schema"]:
            (self.root / folder).mkdir(parents=True, exist_ok=True)

    def restore_globals(self) -> None:
        for key, value in self.originals.items():
            setattr(wiki_tool, key, value)

    def write_source(self, processed: bool = False) -> Path:
        path = wiki_tool.RAW / "source.md"
        path.write_text(
            f"""---
Title: "Source"
Author: "Author"
Reference: "owned-test"
ContentType:
  - "markdown"
Created: 2026-05-24
Processed: {'true' if processed else 'false'}
tags:
  - "source"
---
# Source

Raw body.
""",
            encoding="utf-8",
        )
        return path

    def write_wiki_note(self, *, source: str = "Raw/Sources/source.md", source_count: int = 1) -> Path:
        path = wiki_tool.WIKI / "Concepts" / "test-concept.md"
        path.write_text(
            f"""---
tags:
  - "concept"
topics: []
status: seed
created: 2026-05-24
updated: 2026-05-24
sources:
  - "{source}"
source_count: {source_count}
aliases: []
---
# Test Concept

Compiled claim.
""",
            encoding="utf-8",
        )
        return path

    def test_build_creates_catalog_and_indexes(self) -> None:
        self.write_source()
        self.write_wiki_note()

        with contextlib.redirect_stdout(io.StringIO()):
            result = wiki_tool.cmd_build(argparse.Namespace())

        self.assertEqual(result, 0)
        rows = [json.loads(line) for line in wiki_tool.CATALOG.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rows[0]["title"], "Test Concept")
        self.assertEqual(rows[0]["tag"], "concept")
        self.assertIn("[[test-concept|Test Concept]]", (wiki_tool.WIKI / "index.md").read_text(encoding="utf-8"))
        self.assertIn("[[test-concept|Test Concept]]", (wiki_tool.WIKI / "Concepts" / "index.md").read_text(encoding="utf-8"))

    def test_lint_flags_wrong_source_count_and_missing_source(self) -> None:
        self.write_source()
        note = self.write_wiki_note(source="Raw/Sources/missing.md", source_count=2)

        errors = wiki_tool.lint_compiled_note(note)

        self.assertIn("source_count must equal number of sources", "\n".join(errors))
        self.assertIn("source does not exist under Raw/Sources", "\n".join(errors))

    def test_source_scan_accepts_covered_sources(self) -> None:
        self.write_source(processed=False)
        self.write_wiki_note()

        with contextlib.redirect_stdout(io.StringIO()):
            result = wiki_tool.cmd_source_scan(argparse.Namespace(update=True, accept_covered=True))

        self.assertEqual(result, 0)
        rows = [json.loads(line) for line in wiki_tool.MANIFEST.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(rows[0]["processed"])
        self.assertEqual(rows[0]["covered_by"], ["Wiki/Concepts/test-concept.md"])

    def test_source_lint_fails_processed_source_without_coverage(self) -> None:
        self.write_source(processed=True)

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = wiki_tool.cmd_source_lint(argparse.Namespace())

        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
