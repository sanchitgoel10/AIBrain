# LLM Wiki Agent Rules

This vault is an LLM Wiki. Treat it as a layered knowledge system, not as a generic notes folder.

## Core Layers

- `Raw/Sources/` contains source material. Do not rewrite Raw sources as if they were compiled notes.
- `Raw/Files/` is for binary or bulky source files. These files are ignored by Git by default.
- EPUB books should be kept in `Raw/Files/` and imported into `Raw/Sources/` with `python3 scripts/wiki_tool.py import-epub Raw/Files/book.epub --ingest`.
- `Wiki/` contains reusable compiled knowledge.
- `Schema/` contains the rules, contracts, manifests, and command references that keep the system coherent.

## Required Workflow

1. Search `Wiki/catalog.jsonl` before opening broad Raw context.
2. Open only relevant compiled Wiki notes first.
3. Open Raw sources only when a compiled note is insufficient, when source-level verification is needed, or when ingesting new material.
4. Write reusable knowledge only under `Wiki/`.
5. Keep every compiled note linked to one or more existing files under `Raw/Sources/`.
6. Add Obsidian `[[wikilinks]]` between Raw sources and compiled Wiki notes so graph connections are visible.
7. Keep `source_count` equal to the number of entries in `sources`.
8. Run `python3 scripts/wiki_tool.py build`, `python3 scripts/wiki_tool.py lint`, and `python3 scripts/wiki_tool.py source-lint` before meaningful commits.
9. Do not invent citations, sources, or unsupported claims.

## Commit Gate

Before committing meaningful changes, run:

```bash
python3 scripts/wiki_tool.py doctor
python3 scripts/wiki_tool.py build
python3 scripts/wiki_tool.py lint
python3 scripts/wiki_tool.py source-lint
python3 scripts/audit_public.py
```

After ingesting sources, also run:

```bash
python3 scripts/wiki_tool.py source-scan --update --accept-covered
python3 scripts/wiki_tool.py source-lint
```

## Obsidian Readiness

This system is built inside the Obsidian vault folder. Agents should keep Markdown, indexes, and templates usable from Obsidian, not only from Git.

- Preserve `.obsidian/app.json`, `.obsidian/appearance.json`, `.obsidian/core-plugins.json`, and `.obsidian/graph.json` unless the user asks to change them.
- Ignore workspace, plugin, cache, and log churn.
- Run `python3 scripts/wiki_tool.py doctor` to confirm vault folders, generated indexes, catalog files, and Obsidian basics are present.
- Prefer ordinary Markdown links and readable filenames so the Wiki remains useful in Obsidian.
