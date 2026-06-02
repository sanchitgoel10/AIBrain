# Manual Semantic Compile

Use this workflow when the extension says semantic compile is due, or whenever a captured source deserves deeper notes.

## Scheduled Compile

A Codex automation named `AI Brain Semantic Compile` runs this vault daily. It reads `.aibrain/capture-state.json`, reports `captures_since_compile`, and runs the deep semantic compile workflow regardless of the counter value.

The counter is a reminder/manual-run signal, not a scheduled automation gate. If the count reaches 10, it means there is enough new capture volume to consider running a manual semantic compile before the next scheduled run.

If compile succeeds and all checks pass, the automation resets `captures_since_compile` to 0.

## Prompt For Codex

```text
Use my AI Brain. Search Wiki/catalog.jsonl first. Find recently captured Raw sources that only have ingest-log coverage or shallow capture-hub coverage. For each selected source, read the Raw source and create or update durable Wiki notes under Wiki/Concepts, Wiki/Topics, Wiki/Entities, or Wiki/Projects. Keep every claim linked to the Raw source in sources, keep source_count accurate, add Obsidian wikilinks between Raw and Wiki notes, rebuild indexes, update the source manifest, run lint/source-lint/audit, and summarize what changed.
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
python3 scripts/wiki_tool.py reset-capture-counter
```

Do not reset the counter until the semantic compile pass has completed and checks have passed.

## Result

Raw captures remain preserved in `Raw/Sources/`. Reusable knowledge moves into focused Wiki notes that future agents and the Ask UI can search before opening broad Raw context.
