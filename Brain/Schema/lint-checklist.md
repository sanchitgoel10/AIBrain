# Lint Checklist

- Compiled notes live only under `Wiki/`.
- Raw source notes live only under `Raw/Sources/`.
- Compiled notes use exactly one allowed tag.
- `source_count` equals the number of `sources`.
- Every compiled note source points to an existing `Raw/Sources/` file.
- Compiled notes include Obsidian `[[wikilinks]]` back to their Raw source and related Wiki notes.
- Raw notes include `Title`, `Reference`, `Created`, `Processed`, and `tags`.
- A Raw source marked `Processed: true` has at least one compiled Wiki note covering it.
- Generated indexes and `Wiki/catalog.jsonl` are rebuilt before commit.
- `doctor` confirms the folder is still an Obsidian-readable vault.
