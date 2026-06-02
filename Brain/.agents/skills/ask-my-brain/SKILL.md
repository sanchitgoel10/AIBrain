---
name: ask-my-brain
description: Answer user questions from this Obsidian AI Brain when the user says /ask, asks "question for brain", "ask brain", or asks for knowledge captured in the vault.
---

# Ask My Brain

Use this skill for brain questions inside this project.

## Workflow

1. Treat the user's question as a query against the vault, not as a general knowledge prompt.
2. Run:

```bash
python3 scripts/wiki_tool.py ask --query "user question"
```

3. Treat the command output as the local Brain answer layer. It uses deterministic SQLite FTS retrieval first and a local Ollama model when available for query understanding, reranking, and answer synthesis.
4. Open the cited/highest scoring compiled Wiki notes from the result.
5. If the compiled note is insufficient, open the linked Raw source listed in `sources`.
6. Answer concisely and cite the Wiki note and Raw source used.
7. If there are no relevant matches, say the brain does not currently contain the answer and suggest the likely source to capture or compile.

## Slash Convention

When the user starts with `/ask`, interpret everything after it as the brain query.

Examples:

```text
/ask which company was the secretive trading one?
/ask what did I save about AI infra costs?
/ask what was the MacBook buying advice?
```

Do not invent answers. Prefer compiled `Wiki/` notes over broad `Raw/Sources/` reading. Do not use web search unless the user explicitly asks for current/web verification or approves leaving the Brain after no relevant Brain match.
