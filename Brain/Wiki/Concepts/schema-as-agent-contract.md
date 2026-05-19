---
tags:
  - "concept"
topics:
  - "llm-wiki"
status: seed
created: 2026-05-19
updated: 2026-05-19
sources:
  - "Raw/Sources/how-to-build-llm-wiki-in-obsidian.md"
source_count: 1
aliases:
  - "agent contract"
  - "schema layer"
---

# Schema As Agent Contract

## Definition

The schema is the contract between the user and future agents. It describes where knowledge belongs, how notes should be structured, and which checks must pass before changes are trusted.

This contract guides [[raw-to-wiki-compilation|Raw To Wiki Compilation]] inside the broader [[llm-wiki|LLM Wiki]].

## Key Points

- Agent rules prevent Raw sources from being overwritten.
- Frontmatter schemas keep notes consistent across Obsidian and tooling.
- Naming conventions and templates make future notes easier to query and connect.
- Linting and source checks provide a repeatable maintenance loop.

## Source Notes

- Source: [[how-to-build-llm-wiki-in-obsidian|How To Build LLM Wiki In Obsidian]]
