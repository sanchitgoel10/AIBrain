---
tags:
  - "project"
topics:
  - "llm-wiki"
status: seed
created: 2026-05-19
updated: 2026-05-19
sources:
  - "Raw/Sources/how-to-build-llm-wiki-in-obsidian.md"
source_count: 1
aliases:
  - "AIBrain"
---

# AI Brain Obsidian Vault

## Goal

Build the `Brain/` Obsidian vault into an LLM Wiki that agents can maintain through Raw sources, compiled Wiki notes, schema rules, deterministic tooling, and Git checkpoints.

This project implements [[llm-wiki|LLM Wiki]] using [[schema-as-agent-contract|Schema As Agent Contract]] and [[raw-to-wiki-compilation|Raw To Wiki Compilation]].

## Decisions

- Keep the LLM Wiki inside the existing `Brain/` Obsidian vault.
- Use Git commits as tutorial checkpoints and safety points.
- Add `doctor` checks that report Obsidian vault readiness, not only Git state.
- Use `Wiki/catalog.jsonl` and generated indexes as the first place future agents should search.

## Next Actions

- Continue ingesting user-provided sources into `Raw/Sources/`.
- Compile each source into focused Wiki notes with source links.
- Run maintenance checks before every meaningful commit.

## Source Notes

- Source: [[how-to-build-llm-wiki-in-obsidian|How To Build LLM Wiki In Obsidian]]
