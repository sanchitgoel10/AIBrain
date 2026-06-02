# Ask My Brain

Use `/ask` in Codex when you want an answer from this Obsidian AI Brain.

```text
/ask which company was the secretive trading one?
```

The agent should:

1. Search the compiled Wiki first.
2. Open only the most relevant notes.
3. Open Raw sources only when needed for verification.
4. Answer with citations to the files used.
5. Say clearly when the brain does not contain the answer.

Deterministic helper:

```bash
python3 scripts/wiki_tool.py ask --query "which company was the secretive trading one?"
```

This command uses the local Ask My Brain engine. It builds an ignored SQLite FTS5 index under `.aibrain/`, retrieves relevant Wiki and Raw chunks locally, and uses one hosted OpenAI-compatible model call to synthesize an answer from the retrieved evidence.

Defaults:

```text
AIBRAIN_LLM_MODE=hosted
AIBRAIN_HOSTED_BASE_URL=https://provider.example/v1
AIBRAIN_HOSTED_API_KEY=...
AIBRAIN_HOSTED_MODEL=provider-model-name
AIBRAIN_ASK_INDEX=.aibrain/ask-index.sqlite
```

If the hosted model is unavailable or not configured, the command still returns deterministic source matches and says it cannot synthesize the answer yet. To use local Ollama instead, set `AIBRAIN_LLM_MODE=ollama` and `AIBRAIN_ASK_MODEL` to an installed local model.
