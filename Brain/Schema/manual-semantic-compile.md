# Manual Semantic Compile

Use this workflow when the extension says semantic compile is due, or whenever a captured source deserves deeper notes.

## Scheduled Compile

A Codex automation named `AI Brain Semantic Compile` runs this vault daily. It uses `python3 scripts/wiki_tool.py semantic-pending --json` as its source of truth and compiles every pending source found when the run starts.

There is no capture counter, threshold, or batch limit. After the existing backlog is cleared, the daily pending queue naturally consists of every source added since the previous successful run.

## Prompt For Codex

```text
Use my AI Brain. Run `python3 scripts/wiki_tool.py semantic-pending --json` and treat its pending list as the only semantic compile queue. Search Wiki/catalog.jsonl first. Compile every pending source into durable Wiki notes under Wiki/Concepts, Wiki/Topics, Wiki/Entities, or Wiki/Projects. Keep every claim linked to the Raw source in sources, keep source_count accurate, add Obsidian wikilinks between Raw and Wiki notes, rebuild indexes, update the source manifest, run lint/source-lint/audit, rerun semantic-pending, and summarize what changed.
```

## Manual Steps

1. Ask Codex to run the prompt above.
2. Review the created or updated Wiki notes in Obsidian.
3. Run:

```bash
python3 scripts/wiki_tool.py build
python3 scripts/wiki_tool.py source-scan --update --accept-covered
python3 scripts/wiki_tool.py lint
python3 scripts/wiki_tool.py source-lint
python3 scripts/audit_public.py
python3 scripts/wiki_tool.py semantic-pending
```

The run is complete only when the final semantic pending count is zero.

## Result

Raw captures remain preserved in `Raw/Sources/`. Reusable knowledge moves into focused Wiki notes that future agents and the Ask UI can search before opening broad Raw context.
