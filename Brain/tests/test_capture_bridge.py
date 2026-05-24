from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import capture_bridge
import capture_current_page as capture


class CaptureBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.original_state_file = capture_bridge.STATE_FILE
        self.original_root = capture.ROOT
        capture_bridge.STATE_FILE = self.root / ".aibrain" / "capture-state.json"
        capture.ROOT = self.root
        self.addCleanup(self.restore_globals)

    def restore_globals(self) -> None:
        capture_bridge.STATE_FILE = self.original_state_file
        capture.ROOT = self.original_root

    def test_capture_counter_increments_and_resets(self) -> None:
        self.assertEqual(capture_bridge.brain_status()["captures_since_compile"], 0)

        for _ in range(capture_bridge.SEMANTIC_THRESHOLD):
            status = capture_bridge.increment_capture_counter()

        self.assertEqual(status["captures_since_compile"], capture_bridge.SEMANTIC_THRESHOLD)
        self.assertTrue(status["semantic_due"])

        reset = capture_bridge.reset_capture_counter()

        self.assertEqual(reset["captures_since_compile"], 0)
        self.assertFalse(reset["semantic_due"])

    def test_search_brain_returns_raw_and_wiki_matches(self) -> None:
        raw = self.root / "Raw" / "Sources"
        wiki = self.root / "Wiki" / "Concepts"
        raw.mkdir(parents=True)
        wiki.mkdir(parents=True)
        (raw / "source.md").write_text("# Source\n\nA captured note about maritime safety.", encoding="utf-8")
        (wiki / "concept.md").write_text("# Concept\n\nReusable idea about maritime safety.", encoding="utf-8")

        results = capture_bridge.search_brain("maritime")

        paths = {result["path"] for result in results}
        self.assertIn("Raw/Sources/source.md", paths)
        self.assertIn("Wiki/Concepts/concept.md", paths)
        self.assertTrue(all("maritime" in result["snippet"].lower() for result in results))


if __name__ == "__main__":
    unittest.main()
