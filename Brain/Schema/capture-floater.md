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

1. Opens a confirmation box for the page to capture. The box shows a dropdown of recent Dia/session/history candidates, the detected title, source, and exact editable URL.
2. Captures only the selected or typed URL, so stale clipboard or browser history cannot silently save the wrong page.
3. If the page is YouTube, checks Transcribe's cache and then calls its agent API when needed.
4. Saves title, URL, channel, timestamp from the URL when present, duration, summary, Transcribe permalink, and timestamped transcript.
5. If the page is an article, captures title, URL, author, date, excerpt, and readable page text.
6. Writes a Markdown source note into `Raw/Sources/`.
7. Runs:

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

YouTube captures require an actual transcript. If Transcribe and the local YouTube captions fallback both fail, the script exits with an error and does not save a metadata-only source note.

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

Article test:

```bash
python3 scripts/capture_current_page.py --url "https://example.com/article"
```

## Current Limitation

The floater captures sources deterministically and keeps them visible to Obsidian because they are Markdown files under `Raw/Sources/`. Semantic ingestion into connected Wiki concepts still requires an AI agent/model. Without `AIBRAIN_INGEST_COMMAND`, captured sources remain unprocessed source notes until an agent ingests them.

Because this path avoids active-tab Apple Events, it does not depend on Dia supporting Chrome's AppleScript tab API. For exact current playback time, paste a YouTube URL that includes a `t=` timestamp.

Dia does not expose the active tab through the Chrome AppleScript API, so the floater reads Dia's local session and history files. If the first candidate is not the page you meant, choose another candidate from the dropdown or paste the exact URL into the field before pressing Capture.
