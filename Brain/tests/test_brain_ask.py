from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import brain_ask


class FakeOllama:
    def generate_json(self, prompt: str) -> dict:
        if "Answer the question" in prompt:
            return {"answer": "The country was the Philippines, not Malaysia.", "source_ids": ["S1"], "confidence": "high"}
        return {}


class BadJsonOllama:
    def generate_json(self, _prompt: str) -> dict:
        raise brain_ask.OllamaBadResponse("bad json")


class BrainAskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        for folder in ["Raw/Sources", "Wiki/Concepts", "Wiki/Topics"]:
            (self.root / folder).mkdir(parents=True, exist_ok=True)

    def write_note(self, rel_path: str, text: str) -> None:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_retrieves_stablecoin_country_note_and_answers_with_ollama(self) -> None:
        self.write_note(
            "Wiki/Concepts/stablecoin-payment-rails.md",
            """---
tags:
  - "concept"
sources:
  - "Raw/Sources/stablecoins-are-quietly-changing-how-the-world-sends-money.md"
---
# Stablecoin Payment Rails

Stablecoin payment rails move money across borders more quickly and cheaply.
The source emphasizes remittances rather than trading.
""",
        )
        self.write_note(
            "Raw/Sources/stablecoins-are-quietly-changing-how-the-world-sends-money.md",
            """---
Title: "Stablecoins Are Quietly Changing How the World Sends Money"
---
# Stablecoins Are Quietly Changing How the World Sends Money

Filipinos living abroad sent money back to the Philippines. Coins.ph converts
stablecoins into local pesos in the Philippines. This was not about Malaysia.
""",
        )

        result = brain_ask.BrainAskEngine(self.root, ollama=FakeOllama()).ask(
            "Which country was using stablecoins, was it Malaysia?"
        )

        self.assertIn("Philippines", result["answer"])
        self.assertNotEqual(result["answer"], brain_ask.NO_ANSWER)
        paths = {source["path"] for source in result["sources"] + result["results"]}
        self.assertIn("Wiki/Concepts/stablecoin-payment-rails.md", paths)

    def test_retrieves_deepseek_visual_grounding_note(self) -> None:
        self.write_note(
            "Wiki/Concepts/visual-grounding-in-reasoning-models.md",
            """# Visual Grounding In Reasoning Models

DeepSeek's image reasoning model uses visual grounding so it can reason over an
image by indicating locations instead of only describing the scene in text.
""",
        )

        results = brain_ask.search("deepseek image distillation paper", root=self.root, limit=3)

        self.assertEqual(results[0]["path"], "Wiki/Concepts/visual-grounding-in-reasoning-models.md")

    def test_no_matches_returns_no_answer(self) -> None:
        result = brain_ask.BrainAskEngine(self.root, ollama=BadJsonOllama()).ask("not present")

        self.assertEqual(result["answer"], brain_ask.NO_ANSWER)
        self.assertEqual(result["results"], [])
        self.assertIn("low_confidence", result["warnings"])

    def test_bad_ollama_response_falls_back_to_deterministic_results(self) -> None:
        self.write_note("Wiki/Concepts/test.md", "# Test\n\nCompiled claim about local search.")

        result = brain_ask.BrainAskEngine(self.root, ollama=BadJsonOllama()).ask("compiled claim")

        self.assertIn("Most relevant Brain passage", result["answer"])
        self.assertIn("Compiled claim", result["answer"])
        self.assertEqual(result["engine"], "sqlite-fts5")
        self.assertEqual(result["results"][0]["path"], "Wiki/Concepts/test.md")

    def test_missing_hosted_config_does_not_try_local_model(self) -> None:
        self.write_note("Wiki/Concepts/test.md", "# Test\n\nCompiled claim about local search.")

        config = brain_ask.AskConfig(
            root=self.root,
            index_path=self.root / ".aibrain" / "ask-index.sqlite",
            ollama_url="http://127.0.0.1:11434",
            hosted_base_url="",
            hosted_api_key="",
            hosted_model="",
            llm_mode="hosted",
            model="qwen3:4b",
            timeout_seconds=1,
        )
        result = brain_ask.BrainAskEngine(self.root, config=config).ask("compiled claim")

        self.assertEqual(result["engine"], "sqlite-fts5")
        self.assertIn("llm_not_configured", result["warnings"])
        self.assertIn("Compiled claim", result["answer"])
        self.assertEqual(result["results"][0]["path"], "Wiki/Concepts/test.md")

    def test_specific_query_term_outranks_generic_matches_and_anchors_snippet(self) -> None:
        self.write_note(
            "Raw/Sources/interview.md",
            """# Interview

Do you see parallels between yourself and Oppenheimer?
The figure I most identified with was Leo Szilard, who first had the idea of a chain reaction.
""",
        )
        self.write_note(
            "Raw/Sources/generic.md",
            """# Generic

He thinks of himself as someone who can compare several ordinary options.
""",
        )

        results = brain_ask.search(
            "What did Dario compare himself to when asked whether he thinks of himself as Oppenheimer?",
            root=self.root,
            limit=3,
        )

        self.assertEqual(results[0]["path"], "Raw/Sources/interview.md")
        self.assertIn("Oppenheimer", results[0]["snippet"])
        self.assertIn("Leo Szilard", results[0]["snippet"])

    def test_model_failure_returns_grounded_oppenheimer_passage(self) -> None:
        self.write_note(
            "Raw/Sources/interview.md",
            """# Interview

Do you see parallels between yourself and Oppenheimer?
The figure I most identified with was Leo Szilard, who first had the idea of a chain reaction.
""",
        )

        result = brain_ask.BrainAskEngine(self.root, ollama=BadJsonOllama()).ask(
            "Who did he identify with instead of Oppenheimer?"
        )

        self.assertIn("Leo Szilard", result["answer"])
        self.assertEqual(result["sources"][0]["path"], "Raw/Sources/interview.md")

    def test_misspelled_specific_terms_retrieve_the_exact_passage(self) -> None:
        self.write_note(
            "Raw/Sources/interview.md",
            """# Bloomberg Interview

Do you see parallels between yourself and Oppenheimer?
The figure I most identified with was Leo Szilard, who first had the idea of a chain reaction.
""",
        )
        self.write_note(
            "Raw/Sources/profile.md",
            """# Dario Profile

Dario appeared on Bloomberg and discussed several ideas about artificial intelligence.
""",
        )

        results = brain_ask.search(
            "What did Dario comapre himself to on Bloomberg when asked about Openhiemer?",
            root=self.root,
            limit=3,
        )

        self.assertEqual(results[0]["path"], "Raw/Sources/interview.md")
        self.assertIn("Oppenheimer", results[0]["snippet"])
        self.assertIn("Leo Szilard", results[0]["snippet"])


if __name__ == "__main__":
    unittest.main()
