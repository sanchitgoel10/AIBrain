import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "apps" / "capture-extension"


class CaptureExtensionManifestTests(unittest.TestCase):
    def test_persistent_window_can_access_new_http_pages(self):
        manifest = json.loads((EXTENSION / "manifest.json").read_text())
        permissions = set(manifest.get("host_permissions", []))

        self.assertIn("<all_urls>", permissions)
        self.assertIn("http://127.0.0.1:8765/*", permissions)

    def test_popup_exposes_capture_stop_control(self):
        popup = (EXTENSION / "popup.html").read_text()
        background = (EXTENSION / "background.js").read_text()

        self.assertIn('id="stopCapture"', popup)
        self.assertIn('"stop-capture"', background)

    def test_popup_does_not_show_semantic_compile_status(self):
        popup = (EXTENSION / "popup.html").read_text()
        background = (EXTENSION / "background.js").read_text()

        self.assertNotIn("Semantic compile", popup)
        self.assertNotIn("brain-status", background)

    def test_youtube_capture_supplies_defuddle_fallback_without_touching_articles(self):
        manifest = json.loads((EXTENSION / "manifest.json").read_text())
        background = (EXTENSION / "background.js").read_text()
        content_scripts = manifest.get("content_scripts", [])

        self.assertTrue((EXTENSION / "vendor" / "defuddle.js").exists())
        self.assertEqual(len(content_scripts), 1)
        self.assertTrue(all("youtube.com" in pattern for pattern in content_scripts[0]["matches"]))
        self.assertIn("vendor/defuddle.js", content_scripts[0]["js"])
        self.assertIn("getYoutubeDefuddlePayload", background)
        self.assertIn("youtubeFallback", background)
        self.assertIn("if (!isYoutubeUrl", background)


if __name__ == "__main__":
    unittest.main()
