# AI Brain Project Rules

This repository contains the Obsidian AI Brain vault in `Brain/`.

## Ask Slash Convention

When the user starts a message with `/ask`, says "question for brain", or asks to use the brain, treat the request as a vault query first.

Run from the repository root:

```bash
python3 Brain/scripts/wiki_tool.py ask --query "user question"
```

Then open the best matching `Brain/Wiki/` note first. Open `Brain/Raw/Sources/` only when the compiled Wiki note is insufficient or source-level verification is needed.

Do not browse the web for `/ask` unless the user explicitly asks for web/current/latest verification or the brain has no relevant answer and the user approves looking outside the vault.

The Brain vault has its own detailed agent rules at `Brain/AGENTS.md`.
