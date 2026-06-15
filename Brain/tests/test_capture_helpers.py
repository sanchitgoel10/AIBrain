from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_defuddle_fallback_is_normalized_to_source_transcript_format(self) -> None:
        data = capture_youtube.normalize_defuddle_fallback(
            {
                "title": "Useful Video",
                "author": "Example Channel",
                "language": "en",
                "currentTime": 15,
                "duration": 125,
                "transcript": (
                    "**0:00** · First caption sentence.\n"
                    "**1:02** · Second caption sentence."
                ),
            },
            "https://www.youtube.com/watch?v=abc123&t=15s",
        )

        self.assertEqual(
            data["transcript"],
            "- [00:00] First caption sentence.\n- [01:02] Second caption sentence.",
        )
        self.assertEqual(data["transcribeSource"], "defuddle-youtube-captions")
        self.assertEqual(data["videoId"], "abc123")

    def test_youtube_capture_uses_defuddle_only_after_usetranscribe_fails(self) -> None:
        fallback = {
            "title": "Fallback Video",
            "author": "Fallback Channel",
            "language": "en",
            "transcript": "**0:00** · Caption recovered by Defuddle.",
        }

        with patch.object(
            capture_youtube,
            "usetranscribe_youtube_data",
            side_effect=capture_common.CaptureError("provider unavailable"),
        ), patch.object(capture_youtube, "youtube_data_from_url") as direct_fallback:
            data = capture_youtube.youtube_data_with_fallback(
                "https://www.youtube.com/watch?v=abc123",
                fallback,
            )

        direct_fallback.assert_not_called()
        self.assertEqual(data["transcribeSource"], "defuddle-youtube-captions")
        self.assertIn("Primary Transcribe API failed", data["captureWarning"])

    def test_provider_read_timeout_still_uses_defuddle_fallback(self) -> None:
        with patch.object(
            capture_youtube,
            "usetranscribe_youtube_data",
            side_effect=TimeoutError("The read operation timed out"),
        ):
            data = capture_youtube.youtube_data_with_fallback(
                "https://www.youtube.com/watch?v=abc123",
                {
                    "title": "Recovered After Timeout",
                    "transcript": "**0:00** · Recovered caption.",
                },
            )

        self.assertEqual(data["transcribeSource"], "defuddle-youtube-captions")
        self.assertIn("read operation timed out", data["captureWarning"])

    def test_youtube_capture_keeps_usetranscribe_as_primary(self) -> None:
        primary = {
            "title": "Primary Video",
            "transcript": "- [00:00] Primary transcript.",
            "transcribeSource": "usetranscribe",
        }

        with patch.object(capture_youtube, "usetranscribe_youtube_data", return_value=primary):
            data = capture_youtube.youtube_data_with_fallback(
                "https://www.youtube.com/watch?v=abc123",
                {"transcript": "**0:00** · Defuddle transcript."},
            )

        self.assertIs(data, primary)

    def test_empty_usetranscribe_response_uses_defuddle_fallback(self) -> None:
        with patch.object(
            capture_youtube,
            "usetranscribe_youtube_data",
            return_value={"title": "Empty Primary", "transcript": ""},
        ):
            data = capture_youtube.youtube_data_with_fallback(
                "https://www.youtube.com/watch?v=abc123",
                {
                    "title": "Recovered Video",
                    "transcript": "**0:00** · Recovered caption.",
                },
            )

        self.assertEqual(data["title"], "Recovered Video")
        self.assertEqual(data["transcribeSource"], "defuddle-youtube-captions")

    def test_video_over_90_minutes_uses_defuddle_before_usetranscribe(self) -> None:
        fallback = {
            "title": "Long Video",
            "duration": 5401,
            "transcript": "**0:00** · Long video caption.",
        }

        with patch.object(capture_youtube, "usetranscribe_youtube_data") as primary:
            data = capture_youtube.youtube_data_with_fallback(
                "https://www.youtube.com/watch?v=long123",
                fallback,
            )

        primary.assert_not_called()
        self.assertEqual(data["transcribeSource"], "defuddle-youtube-captions")
        self.assertIn("longer than 90 minutes", data["captureWarning"])

    def test_video_exactly_90_minutes_keeps_usetranscribe_primary(self) -> None:
        primary = {
            "title": "Ninety Minute Video",
            "transcript": "- [00:00] Primary transcript.",
            "transcribeSource": "usetranscribe",
        }
        with patch.object(
            capture_youtube,
            "usetranscribe_youtube_data",
            return_value=primary,
        ) as provider:
            data = capture_youtube.youtube_data_with_fallback(
                "https://www.youtube.com/watch?v=ninety123",
                {
                    "duration": 5400,
                    "transcript": "**0:00** · Defuddle transcript.",
                },
            )

        provider.assert_called_once()
        self.assertIs(data, primary)

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

    def test_write_source_note_can_replace_the_existing_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original_raw = capture_common.RAW
            capture_common.RAW = Path(tmp) / "Raw" / "Sources"
            self.addCleanup(setattr, capture_common, "RAW", original_raw)
            capture_common.RAW.mkdir(parents=True)
            existing = capture_common.RAW / "original-name.md"
            existing.write_text("old incomplete capture", encoding="utf-8")

            path = capture_common.write_source_note(
                title="A Better Title",
                author="Author",
                reference="https://example.com/source",
                content_types=["article", "markdown"],
                body="# A Better Title\n\nComplete replacement body.",
                replace_path=existing,
            )

            self.assertEqual(path, existing.resolve())
            self.assertIn("Complete replacement body.", path.read_text(encoding="utf-8"))
            self.assertEqual(list(capture_common.RAW.glob("*.md")), [existing])


if __name__ == "__main__":
    unittest.main()
