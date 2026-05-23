from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import auto_ingest
import wiki_tool


class AutoIngestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.auto_originals = {
            "ROOT": auto_ingest.ROOT,
            "RAW": auto_ingest.RAW,
            "LOGS": auto_ingest.LOGS,
            "TOPICS": auto_ingest.TOPICS,
            "CAPTURE_HUB": auto_ingest.CAPTURE_HUB,
        }
        self.wiki_original_root = wiki_tool.ROOT

        auto_ingest.ROOT = self.root
        auto_ingest.RAW = self.root / "Raw" / "Sources"
        auto_ingest.LOGS = self.root / "Wiki" / "Logs"
        auto_ingest.TOPICS = self.root / "Wiki" / "Topics"
        auto_ingest.CAPTURE_HUB = auto_ingest.TOPICS / "captured-sources.md"
        wiki_tool.ROOT = self.root
        self.addCleanup(self.restore_globals)

    def restore_globals(self) -> None:
        for key, value in self.auto_originals.items():
            setattr(auto_ingest, key, value)
        wiki_tool.ROOT = self.wiki_original_root

    def test_ingest_source_creates_log_hub_and_raw_backlink(self) -> None:
        source_dir = self.root / "Raw" / "Sources"
        source_dir.mkdir(parents=True)
        source = source_dir / "sample-source.md"
        source.write_text(
            """---
Title: "Sample Source"
Author: "Author"
Reference: "owned-test"
ContentType:
  - "markdown"
Created: 2026-05-24
Processed: false
tags:
  - "source"
---
# Sample Source

This source contains a reusable claim about captured knowledge.
""",
            encoding="utf-8",
        )

        ingest_path = auto_ingest.ingest_source(source)

        self.assertEqual(ingest_path, self.root / "Wiki" / "Logs" / "sample-source-ingest.md")
        self.assertIn("Raw/Sources/sample-source.md", ingest_path.read_text(encoding="utf-8"))
        self.assertIn("[[sample-source|Sample Source]]", ingest_path.read_text(encoding="utf-8"))
        self.assertIn("[[sample-source-ingest|Ingested: Sample Source]]", source.read_text(encoding="utf-8"))
        hub = (self.root / "Wiki" / "Topics" / "captured-sources.md").read_text(encoding="utf-8")
        self.assertIn("Raw/Sources/sample-source.md", hub)
        self.assertIn("[[sample-source-ingest|Sample Source Ingest]]", hub)


if __name__ == "__main__":
    unittest.main()
