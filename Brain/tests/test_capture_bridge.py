from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import capture_bridge
import capture_current_page as capture


class CaptureBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.original_root = capture.ROOT
        capture.ROOT = self.root
        self.addCleanup(self.restore_globals)

    def restore_globals(self) -> None:
        capture.ROOT = self.original_root

    def test_search_brain_returns_raw_and_wiki_matches(self) -> None:
        raw = self.root / "Raw" / "Sources"
        wiki = self.root / "Wiki" / "Concepts"
        raw.mkdir(parents=True, exist_ok=True)
        wiki.mkdir(parents=True, exist_ok=True)
        (raw / "source.md").write_text("# Source\n\nA captured note about maritime safety.", encoding="utf-8")
        (wiki / "concept.md").write_text("# Concept\n\nReusable idea about maritime safety.", encoding="utf-8")

        results = capture_bridge.search_brain("maritime")

        paths = {result["path"] for result in results}
        self.assertIn("Raw/Sources/source.md", paths)
        self.assertIn("Wiki/Concepts/concept.md", paths)
        self.assertTrue(all("maritime" in result["snippet"].lower() for result in results))

    def test_ask_brain_returns_answer_json_shape(self) -> None:
        wiki = self.root / "Wiki" / "Concepts"
        wiki.mkdir(parents=True, exist_ok=True)
        (wiki / "concept.md").write_text("# Concept\n\nReusable idea about maritime safety.", encoding="utf-8")

        original_answer = capture_bridge.brain_ask.answer
        capture_bridge.brain_ask.answer = lambda query, root, limit: {
            "answer": "Maritime safety was the saved topic.",
            "sources": [{"path": "Wiki/Concepts/concept.md", "title": "Concept", "kind": "wiki", "snippet": "maritime safety", "score": 1}],
            "results": [],
            "model": "test-model",
            "engine": "sqlite-fts5",
            "warnings": [],
        }
        self.addCleanup(setattr, capture_bridge.brain_ask, "answer", original_answer)

        payload = capture_bridge.ask_brain("maritime", limit=3)

        self.assertEqual(payload["answer"], "Maritime safety was the saved topic.")
        self.assertEqual(payload["sources"][0]["path"], "Wiki/Concepts/concept.md")
        self.assertIn("engine", payload)

    def test_recent_job_for_url_returns_latest_matching_job(self) -> None:
        capture_bridge.JOBS.clear()
        self.addCleanup(capture_bridge.JOBS.clear)
        capture_bridge.set_job("old", url="https://example.com/a", status="done", message="old")
        capture_bridge.set_job("new", url="https://example.com/a", status="capturing", message="new")
        capture_bridge.set_job("other", url="https://example.com/b", status="done", message="other")

        match = capture_bridge.recent_job_for_url("https://example.com/a")

        self.assertIsNotNone(match)
        job_id, job = match
        self.assertEqual(job_id, "new")
        self.assertEqual(job["message"], "new")
        self.assertEqual(job["job_id"], "new")

    def test_canonical_source_identity_ignores_youtube_timestamps_and_tracking(self) -> None:
        self.assertEqual(
            capture_bridge.canonical_source_identity("https://www.youtube.com/watch?v=abc123&t=90s"),
            capture_bridge.canonical_source_identity("https://youtu.be/abc123?si=share-token"),
        )
        self.assertEqual(
            capture_bridge.canonical_source_identity("https://example.com/story/?utm_source=newsletter&id=7"),
            capture_bridge.canonical_source_identity("https://www.example.com/story?id=7&utm_medium=email"),
        )

    def test_existing_source_reports_transcript_size_and_quality(self) -> None:
        raw = self.root / "Raw" / "Sources"
        raw.mkdir(parents=True, exist_ok=True)
        transcript = "\n".join(
            [
                "- [00:00] First transcript line with enough useful context.",
                "- [00:10] Second transcript line with more useful context.",
                "- [00:20] Third transcript line with still more useful context.",
                "- [00:30] Fourth transcript line that makes this clearly complete.",
            ]
        )
        (raw / "video.md").write_text(
            f"""---
Title: "Useful Video"
Reference: "https://www.youtube.com/watch?v=abc123&t=30s"
---

# Useful Video

## Transcript

{transcript}
""",
            encoding="utf-8",
        )

        source = capture_bridge.existing_source_for_url("https://youtu.be/abc123")

        self.assertIsNotNone(source)
        self.assertEqual(source["path"], "Raw/Sources/video.md")
        self.assertEqual(source["quality"], "complete")
        self.assertGreater(source["content_chars"], 200)
        self.assertEqual(source["duplicate_count"], 1)

    def test_existing_small_transcript_is_marked_suspect(self) -> None:
        raw = self.root / "Raw" / "Sources"
        raw.mkdir(parents=True, exist_ok=True)
        (raw / "video.md").write_text(
            """---
Title: "Broken Video"
Reference: "https://www.youtube.com/watch?v=broken123"
---

# Broken Video

## Transcript

Transcript could not be captured automatically.
""",
            encoding="utf-8",
        )

        source = capture_bridge.existing_source_for_url("https://www.youtube.com/watch?v=broken123")

        self.assertEqual(source["quality"], "suspect")
        self.assertIn("incomplete", source["quality_message"])

    def test_get_job_marks_stale_running_job_as_timed_out(self) -> None:
        capture_bridge.JOBS.clear()
        self.addCleanup(capture_bridge.JOBS.clear)
        capture_bridge.set_job("stale", url="https://example.com/a", status="capturing", message="working", created_at=0)
        capture_bridge.JOBS["stale"]["created_at"] = capture_bridge.time.time() - capture_bridge.RUNNING_JOB_TIMEOUT_SECONDS - 1

        job = capture_bridge.get_job("stale")

        self.assertEqual(job["status"], "error")
        self.assertTrue(job["timed_out"])
        self.assertIn("timed out", job["message"])

    def test_cancelled_job_cannot_return_to_running_state(self) -> None:
        capture_bridge.JOBS.clear()
        self.addCleanup(capture_bridge.JOBS.clear)
        capture_bridge.set_job("job", status="capturing", message="working")

        cancelled = capture_bridge.cancel_job("job")
        capture_bridge.set_job("job", status="ingesting", message="should not resume")

        self.assertEqual(cancelled["status"], "cancelled")
        self.assertTrue(cancelled["cancelled"])
        self.assertEqual(capture_bridge.get_job("job")["status"], "cancelled")

    def test_ocr_uses_every_captured_screenshot(self) -> None:
        original_run = capture_bridge.subprocess.run
        observed = {}

        def fake_run(args, **_kwargs):
            observed["args"] = args
            return SimpleNamespace(returncode=0, stdout="article text", stderr="")

        capture_bridge.subprocess.run = fake_run
        self.addCleanup(setattr, capture_bridge.subprocess, "run", original_run)
        screenshots = [{"dataUrl": "data:image/png;base64,AA=="} for _ in range(35)]

        text = capture_bridge.ocr_screenshots(screenshots)

        self.assertEqual(text, "article text")
        self.assertEqual(len(observed["args"][2:]), 35)

    def test_ocr_preserves_jpeg_screenshot_extension(self) -> None:
        original_run = capture_bridge.subprocess.run
        observed = {}

        def fake_run(args, **_kwargs):
            observed["args"] = args
            return SimpleNamespace(returncode=0, stdout="article text", stderr="")

        capture_bridge.subprocess.run = fake_run
        self.addCleanup(setattr, capture_bridge.subprocess, "run", original_run)

        text = capture_bridge.ocr_screenshots([{"dataUrl": "data:image/jpeg;base64,AA=="}])

        self.assertEqual(text, "article text")
        self.assertTrue(str(observed["args"][2]).endswith(".jpg"))

    def test_forced_ocr_replaces_stale_dom_text(self) -> None:
        original_ocr = capture_bridge.ocr_screenshots
        capture_bridge.ocr_screenshots = lambda screenshots: (
            "Cipla had one of its worst quarters. Investors still rewarded it because they cared "
            "more about the future drug pipeline than the recent quarterly profit drop."
        )
        self.addCleanup(setattr, capture_bridge, "ocr_screenshots", original_ocr)
        payload = {
            "page": {
                "text": "Mamaearth stale text. " * 80,
                "screenshots": [{"dataUrl": "data:image/png;base64,AA=="}],
                "forceOcr": True,
                "discardDomTextForOcr": True,
            }
        }

        updated = capture_bridge.article_payload_with_ocr(payload)

        self.assertIn("Cipla had one of its worst quarters.", updated["page"]["text"])
        self.assertNotIn("Mamaearth", updated["page"]["text"])
        self.assertIn("DOM looked stale", updated["page"]["captureWarning"])

    def test_screenshot_method_appends_ocr_even_when_dom_text_is_long(self) -> None:
        original_ocr = capture_bridge.ocr_screenshots
        capture_bridge.ocr_screenshots = lambda screenshots: "OCR article continuation."
        self.addCleanup(setattr, capture_bridge, "ocr_screenshots", original_ocr)
        payload = {
            "page": {
                "text": "Visible article text. " * 80,
                "screenshots": [{"dataUrl": "data:image/png;base64,AA=="}],
                "extractionMethod": "screenshot-ocr",
            }
        }

        updated = capture_bridge.article_payload_with_ocr(payload)

        self.assertIn("Visible article text.", updated["page"]["text"])
        self.assertIn("## OCR Extracted Text", updated["page"]["text"])
        self.assertIn("OCR article continuation.", updated["page"]["text"])


if __name__ == "__main__":
    unittest.main()
