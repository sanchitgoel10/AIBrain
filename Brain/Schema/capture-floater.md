# Capture Floater

The capture floater is a lightweight Mac tool for saving a YouTube video or article URL into the AI Brain.

## Scope

- Supported browsers: Chrome, Chrome Canary, Chromium, Brave, Edge, Arc, and Dia through local Chromium history.
- Supported source types:
  - YouTube video pages
  - Article pages with readable body text
- Primary YouTube transcript provider: `https://www.usetranscribe.io` agent API.

## Behavior

Clicking the floating button:

1. Finds the most recent captureable URL from local Chromium browser history, or accepts an explicit `--url`.
2. If the page is YouTube, checks Transcribe's cache and then calls its agent API when needed.
3. Saves title, URL, channel, timestamp from the URL when present, duration, summary, Transcribe permalink, and timestamped transcript.
4. If the page is an article, captures title, URL, author, date, excerpt, and readable page text.
5. Writes a Markdown source note into `Raw/Sources/`.
6. Runs:

```bash
python3 scripts/wiki_tool.py build
python3 scripts/wiki_tool.py source-scan --update
python3 scripts/wiki_tool.py source-lint
```

If `AIBRAIN_INGEST_COMMAND` is set, the capture script runs that command after writing the source. The captured source path is available as `AIBRAIN_CAPTURED_SOURCE`.

Transcribe configuration lives in `.env` if needed:

```bash
USETRANSCRIBE_BASE_URL=https://www.usetranscribe.io
```

Transcribe's published agent API does not require an API key today. It is rate-limited by IP/session, so the script checks the cache before triggering a new transcription.

## Run

From the vault root:

```bash
scripts/run_capture_floater.sh
```

This primary path should not require macOS Automation permission because it does not ask Dia or System Events for the active tab.

Direct URL test:

```bash
python3 scripts/capture_current_page.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Current Limitation

The floater captures sources deterministically and keeps them visible to Obsidian because they are Markdown files under `Raw/Sources/`. Semantic ingestion into connected Wiki concepts still requires an AI agent/model. Without `AIBRAIN_INGEST_COMMAND`, captured sources remain unprocessed source notes until an agent ingests them.

Because this path avoids active-tab Apple Events, it does not depend on Dia supporting Chrome's AppleScript tab API. The tradeoff is that it uses the most recent URL recorded in browser history; for exact current playback time, open or copy a URL that includes a YouTube `t=` timestamp.
