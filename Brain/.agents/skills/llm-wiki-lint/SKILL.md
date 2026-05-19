---
name: llm-wiki-lint
description: Run deterministic LLM Wiki health checks and fix schema drift.
---

# LLM Wiki Lint

Run:

```bash
python3 scripts/wiki_tool.py doctor
python3 scripts/wiki_tool.py build
python3 scripts/wiki_tool.py lint
python3 scripts/wiki_tool.py source-lint
python3 scripts/audit_public.py
```

Fix any reported issues before committing.

