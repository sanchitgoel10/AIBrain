#!/usr/bin/env python3
"""Fail on obvious private material before publishing the vault."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", "Raw/Files", ".obsidian/plugins", ".obsidian/cache", ".obsidian/logs"}
PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bgho_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"/Users/[A-Za-z0-9._-]+/(?!Documents/AIBrain/Brain)"),
]


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return any(rel == part or rel.startswith(part + "/") for part in SKIP_PARTS)


def main() -> int:
    errors = []
    for path in ROOT.rglob("*"):
        if path.is_dir() or should_skip(path):
            continue
        if path.suffix.lower() not in {".md", ".json", ".jsonl", ".py", ".sh", ".gitignore"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in PATTERNS:
            if pattern.search(text):
                errors.append(f"{path.relative_to(ROOT).as_posix()}: matched {pattern.pattern}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("public audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
