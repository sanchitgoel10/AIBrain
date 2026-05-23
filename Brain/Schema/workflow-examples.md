# Workflow Examples

## Ingest A New Source

1. Put cleaned Markdown in `Raw/Sources/`.
2. Search the catalog for related compiled notes:

```bash
python3 scripts/wiki_tool.py search-catalog --query "topic"
```

3. Create or update focused notes under `Wiki/`.
4. Add Raw source paths to `sources`.
5. Keep `source_count` accurate.
6. Rebuild and validate:

```bash
python3 scripts/wiki_tool.py build
python3 scripts/wiki_tool.py lint
python3 scripts/wiki_tool.py source-scan --update --accept-covered
python3 scripts/wiki_tool.py source-lint
```

## Ingest An EPUB Book

1. Put the `.epub` file in `Raw/Files/`.
2. Convert it into a Raw source and connect it to the graph:

```bash
python3 scripts/wiki_tool.py import-epub Raw/Files/book.epub --ingest
```

3. Promote durable claims from the generated ingest log into focused `Wiki/Topics/`, `Wiki/Concepts/`, `Wiki/Entities/`, or `Wiki/Projects/` notes when reviewing the book.

## Answer From The Wiki

1. Start with `Wiki/index.md`.
2. Search `Wiki/catalog.jsonl` with `search-catalog`.
3. Open relevant compiled Wiki notes.
4. Open Raw sources only when the compiled note does not provide enough support.
5. Cite both the compiled note and Raw source when source material affects the answer.
