---
name: llm-wiki-ingest
description: Compile Raw source notes into concise, cited Wiki notes.
---

# LLM Wiki Ingest

Use this skill when new material appears in `Raw/Sources/`.

1. Run `python3 scripts/wiki_tool.py source-delta`.
2. Search `Wiki/catalog.jsonl` for related compiled knowledge before opening broad Raw context.
3. Read the new Raw source.
4. Create or update focused notes under `Wiki/Topics/`, `Wiki/Concepts/`, `Wiki/Entities/`, `Wiki/Projects/`, or `Wiki/Logs/`.
5. Link each compiled note to one or more Raw source paths in `sources`.
6. Keep `source_count` accurate.
7. Run the build and lint checks before committing.

Do not invent citations or unsupported claims.

