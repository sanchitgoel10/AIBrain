# Frontmatter Schema

## Raw Source Notes

Raw source notes live in `Raw/Sources/` and must include:

```yaml
---
Title: ""
Author: ""
Reference: ""
ContentType:
  - "markdown"
Created: YYYY-MM-DD
Processed: false
tags:
  - "source"
---
```

Required fields: `Title`, `Reference`, `Created`, `Processed`, `tags`.

## Compiled Wiki Notes

Compiled notes live under `Wiki/Topics/`, `Wiki/Concepts/`, `Wiki/Entities/`, `Wiki/Projects/`, or `Wiki/Logs/`.

```yaml
---
tags:
  - "concept"
topics: []
status: seed
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: []
source_count: 0
aliases: []
---
```

Allowed compiled tags:

- `topic`
- `concept`
- `entity`
- `project`
- `log`

Every compiled note must cite one or more Raw source files in `sources`.

