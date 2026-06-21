from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import remote_ask_server


class RemoteAskServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.web_root = Path(self.tmp.name)
        (self.web_root / "index.html").write_text("<h1>Ask My Brain</h1>", encoding="utf-8")
        (self.web_root / "app.js").write_text("console.log('ask');", encoding="utf-8")
        (self.web_root / "styles.css").write_text("body { color: black; }", encoding="utf-8")
        (self.web_root / "manifest.webmanifest").write_text("{}", encoding="utf-8")

        def fake_answer(query: str, limit: int) -> dict:
            return {
                "answer": f"Answer for {query}",
                "sources": [
                    {
                        "title": "Source",
                        "path": "Wiki/Concepts/source.md",
                        "snippet": "Grounded evidence.",
                    }
                ],
                "results": [],
                "engine": "test",
                "model": "test-model",
                "warnings": [],
            }

        self.server = remote_ask_server.create_server(
            "127.0.0.1",
            0,
            web_root=self.web_root,
            answer_fn=fake_answer,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def get_json(self, path: str) -> dict:
        with urllib.request.urlopen(f"{self.base_url}{path}", timeout=3) as response:
            return json.loads(response.read())

    def test_serves_mobile_app_and_health(self) -> None:
        self.assertEqual(self.get_json("/health")["service"], "aibrain-remote-ask")
        with urllib.request.urlopen(f"{self.base_url}/", timeout=3) as response:
            html = response.read().decode("utf-8")
            self.assertIn("Ask My Brain", html)
            self.assertIn("no-store", response.headers["Cache-Control"])

    def test_post_ask_returns_existing_brain_answer_shape(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/api/ask",
            data=json.dumps({"query": "What did I save?", "limit": 5}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            payload = json.loads(response.read())

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["answer"], "Answer for What did I save?")
        self.assertEqual(payload["sources"][0]["path"], "Wiki/Concepts/source.md")

    def test_remote_server_does_not_expose_capture_or_file_opening_routes(self) -> None:
        for path in ("/capture", "/open-source", "/source-status"):
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(f"{self.base_url}{path}", timeout=3)
            self.assertEqual(raised.exception.code, 404)

    def test_rejects_empty_and_oversized_questions(self) -> None:
        for query in ("", "x" * (remote_ask_server.MAX_QUERY_CHARS + 1)):
            request = urllib.request.Request(
                f"{self.base_url}/api/ask",
                data=json.dumps({"query": query}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(request, timeout=3)
            self.assertEqual(raised.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
