---
name: llm-wiki-query
description: Answer questions by searching compiled Wiki notes before broad Raw context.
---

# LLM Wiki Query

1. Start with `Wiki/index.md`.
2. Search the catalog:

```bash
python3 scripts/wiki_tool.py search-catalog --query "user topic"
```

3. Open the most relevant compiled Wiki notes.
4. Open Raw sources only when the compiled note is insufficient or source-level verification is requested.
5. Cite the compiled note and Raw source when the answer depends on source material.

