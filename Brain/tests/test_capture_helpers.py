from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import capture_article
import capture_common
import capture_youtube


class CaptureHelperTests(unittest.TestCase):
    def test_capture_url_filter_allows_web_pages_and_blocks_sensitive_surfaces(self) -> None:
        self.assertTrue(capture_common.is_capture_url("https://example.com/article"))
        self.assertTrue(capture_common.is_capture_url("https://www.youtube.com/watch?v=abc"))
        self.assertFalse(capture_common.is_capture_url("chrome://extensions"))
        self.assertFalse(capture_common.is_capture_url("https://mail.google.com/mail/u/0/"))
        self.assertFalse(capture_common.is_capture_url("https://www.netflix.com/watch/123"))
        self.assertFalse(capture_common.is_capture_url("not a url"))

    def test_time_and_youtube_id_helpers(self) -> None:
        self.assertEqual(capture_common.format_seconds("62"), "01:02")
        self.assertEqual(capture_common.format_seconds("3661"), "01:01:01")
        self.assertEqual(capture_youtube.extract_youtube_id("https://youtu.be/abc123"), "abc123")
        self.assertEqual(capture_youtube.extract_youtube_id("https://youtube.com/watch?v=abc123&t=1m2s"), "abc123")
        self.assertEqual(capture_youtube.youtube_time_from_url("https://youtube.com/watch?v=abc&t=1m2s"), 62.0)

    def test_article_html_extraction_removes_page_chrome(self) -> None:
        html = """
        <html>
          <head>
            <meta property="og:title" content="Useful Article">
            <meta name="author" content="Writer">
          </head>
          <body>
            <nav>Navigation</nav>
            <article><h1>Useful Article</h1><p>First point.</p><p>Second point.</p></article>
          </body>
        </html>
        """

        text = capture_article.text_from_html(html)

        self.assertEqual(capture_article.meta_content(html, "og:title"), "Useful Article")
        self.assertEqual(capture_article.meta_content(html, "author"), "Writer")
        self.assertIn("First point.", text)
        self.assertIn("Second point.", text)
        self.assertNotIn("Navigation", text)

    def test_write_source_note_creates_expected_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original_raw = capture_common.RAW
            capture_common.RAW = Path(tmp) / "Raw" / "Sources"
            self.addCleanup(setattr, capture_common, "RAW", original_raw)

            path = capture_common.write_source_note(
                title="My Source",
                author="Author",
                reference="https://example.com/source",
                content_types=["article", "markdown"],
                body="# My Source\n\nBody",
            )

            text = path.read_text(encoding="utf-8")
            self.assertEqual(path.name, "my-source.md")
            self.assertIn('Title: "My Source"', text)
            self.assertIn('Reference: "https://example.com/source"', text)
            self.assertIn("Processed: false", text)
            self.assertIn("# My Source", text)


if __name__ == "__main__":
    unittest.main()
