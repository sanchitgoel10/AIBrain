import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "apps" / "capture-extension"


class CaptureExtensionManifestTests(unittest.TestCase):
    def test_persistent_window_can_access_new_http_pages(self):
        manifest = json.loads((EXTENSION / "manifest.json").read_text())
        permissions = set(manifest.get("host_permissions", []))

        self.assertIn("http://*/*", permissions)
        self.assertIn("https://*/*", permissions)
        self.assertIn("http://127.0.0.1:8765/*", permissions)


if __name__ == "__main__":
    unittest.main()
