# Manual Semantic Compile

Use this workflow when the extension says semantic compile is due, or whenever a captured source deserves deeper notes.

## Scheduled Compile

A Codex automation named `AI Brain Semantic Compile` runs this vault daily. It uses `python3 scripts/wiki_tool.py semantic-pending --json` as its source of truth and compiles up to 10 pending sources per run. It reads `.aibrain/capture-state.json` only to report `captures_since_compile`.

The counter is a reminder/manual-run signal, not a measure of uncompiled files and not a scheduled automation gate. Repeated clicks and manual resets cannot remove a source from the semantic queue.

The automation resets `captures_since_compile` only when all checks pass and `semantic-pending` reports zero remaining sources.

## Prompt For Codex

```text
Use my AI Brain. Run `python3 scripts/wiki_tool.py semantic-pending --json` and treat its pending list as the only semantic compile queue. Search Wiki/catalog.jsonl first. Compile up to 10 pending sources into durable Wiki notes under Wiki/Concepts, Wiki/Topics, Wiki/Entities, or Wiki/Projects. Keep every claim linked to the Raw source in sources, keep source_count accurate, add Obsidian wikilinks between Raw and Wiki notes, rebuild indexes, update the source manifest, run lint/source-lint/audit, rerun semantic-pending, and summarize what changed. Reset the capture counter only when the final pending count is zero.
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

Run `python3 scripts/wiki_tool.py reset-capture-counter` only if the final semantic pending count is zero.

## Result

Raw captures remain preserved in `Raw/Sources/`. Reusable knowledge moves into focused Wiki notes that future agents and the Ask UI can search before opening broad Raw context.
