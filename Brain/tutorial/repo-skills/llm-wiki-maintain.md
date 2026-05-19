# LLM Wiki Maintain

Canonical file: `.agents/skills/llm-wiki-maintain/SKILL.md`

Use this skill after meaningful changes to `Raw/`, `Wiki/`, or `Schema/`.

1. Run `python3 scripts/wiki_tool.py build`.
2. Run `python3 scripts/wiki_tool.py source-scan --update --accept-covered`.
3. Run `python3 scripts/wiki_tool.py lint`.
4. Run `python3 scripts/wiki_tool.py source-lint`.
5. Add a short log entry with `python3 scripts/wiki_tool.py log --title "title" --details "details"` when the maintenance changed user-facing knowledge.

