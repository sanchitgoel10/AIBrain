# Command Reference

Run commands from the Obsidian vault root: `Brain/`.

```bash
python3 scripts/wiki_tool.py doctor
```

Checks required folders, Python version, Obsidian vault basics, catalog, source manifest, and note counts.

```bash
python3 scripts/wiki_tool.py build
```

Generates `Wiki/catalog.jsonl`, `Wiki/index.md`, and per-folder index files.

```bash
python3 scripts/wiki_tool.py lint
```

Validates compiled Wiki note frontmatter, allowed tags, source links, and `source_count`.

```bash
python3 scripts/wiki_tool.py source-scan
python3 scripts/wiki_tool.py source-scan --update --accept-covered
```

Lists Raw sources and optionally updates `Schema/source-manifest.jsonl`.

```bash
python3 scripts/wiki_tool.py source-lint
```

Validates source note frontmatter and processed-source coverage.

```bash
python3 scripts/wiki_tool.py source-delta
python3 scripts/wiki_tool.py source-coverage
```

Shows manifest deltas and Raw-source coverage by compiled Wiki notes.

```bash
python3 scripts/wiki_tool.py search-catalog --query "llm wiki"
```

Searches compiled notes through the catalog.

```bash
python3 scripts/wiki_tool.py log --title "title" --details "details"
```

Appends a short maintenance entry to `Wiki/log.md`.

```bash
python3 scripts/audit_public.py
```

Fails on obvious secrets, machine-local paths, private keys, and Obsidian plugin/cache state.
