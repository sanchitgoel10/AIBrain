# Capture Floater

The capture floater is a lightweight Mac tool for saving the active Chromium tab into the AI Brain.

## Scope

- Supported browsers: Chrome, Chrome Canary, Chromium, Brave, Edge, and Arc when their AppleScript tab API is available.
- Supported source types:
  - YouTube video pages
  - Article pages with readable body text

## Behavior

Clicking the floating button:

1. Reads the active Chromium tab.
2. If the page is YouTube, captures title, URL, channel, current timestamp, duration, and transcript captions.
3. If the page is an article, captures title, URL, author, date, excerpt, and readable page text.
4. Writes a Markdown source note into `Raw/Sources/`.
5. Runs:

```bash
python3 scripts/wiki_tool.py build
python3 scripts/wiki_tool.py source-scan --update
python3 scripts/wiki_tool.py source-lint
```

If `AIBRAIN_INGEST_COMMAND` is set, the capture script runs that command after writing the source. The captured source path is available as `AIBRAIN_CAPTURED_SOURCE`.

## Run

From the vault root:

```bash
scripts/run_capture_floater.sh
```

macOS may ask for Automation permission so the script can read the active browser tab.

## Current Limitation

The floater can capture sources deterministically. Semantic ingestion into connected Wiki concepts still requires an AI agent/model. Without `AIBRAIN_INGEST_COMMAND`, captured sources remain in `Raw/Sources/` as unprocessed source notes until an agent ingests them.
