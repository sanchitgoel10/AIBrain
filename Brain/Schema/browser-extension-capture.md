# Browser Extension Capture

This is the reliable capture path for Dia and other Chromium browsers.

The extension runs inside the browser, so it can read the exact active tab URL and title through the browser API. It sends that URL to a local bridge at `http://127.0.0.1:8765`, which writes the source note into `Raw/Sources/` and runs the usual wiki maintenance commands.

## Run The Local Bridge

From the vault root:

```bash
scripts/run_capture_bridge.sh
```

Keep this terminal running while capturing.

Health check:

```bash
curl http://127.0.0.1:8765/health
```

## Install The Extension

In Dia or another Chromium browser:

1. Open the extensions page.
2. Enable developer mode.
3. Load unpacked extension.
4. Select:

```text
/Users/sanchitgoel/Documents/AIBrain/Brain/apps/capture-extension
```

5. Pin `AI Brain Capture` in the toolbar.

## Capture

1. Open the YouTube video or article tab.
2. Click the `AI Brain Capture` extension button.
3. The extension sends the exact active tab URL to the local bridge.
4. The bridge saves the note in `Raw/Sources/`.

Before capturing, the bridge checks `Raw/Sources/` for the same canonical source. YouTube timestamps and share URLs resolve to the same video ID, and common article tracking parameters are ignored. If a match exists, the extension shows the existing file size, captured-content size, and whether the capture looks complete. It does not capture again unless the user explicitly chooses `Replace existing`.

Replacement reuses the existing Raw note path. A failed transcript, screenshot, or OCR attempt does not overwrite the existing note because the new content is validated before it is written.

The extension popup and badge show progress:

```text
ATB blue    queued
ATB purple  capturing transcript or article text
ATB teal    creating the linked Wiki ingest note
ATB amber   updating the AI Brain catalog
ATB amber   duplicate source awaiting Keep or Replace
ATB green   complete
ERR red     failed
```

For YouTube, Transcribe is the primary transcript provider. If no transcript is captured, the bridge returns an error and does not save a metadata-only source.

Uncached YouTube videos can take a few minutes while Transcribe resolves and transcribes them. Keep the bridge terminal running until the badge changes to `OK` or `ERR`.

For articles, the extension first extracts visible page text from the browser tab and sends it to the bridge. This is important for logged-in or subscription pages, because Python fetching the URL directly may only see a logged-out shell.

If browser text extraction is too short, the extension scrolls the active tab and captures screenshots until it detects the article end. The local bridge runs macOS Vision OCR on every captured screenshot and saves the extracted text. This mirrors the way browser-native assistants can reason from the rendered page instead of only from fetchable HTML.

After capture, the bridge automatically creates a deterministic Wiki ingest log under `Wiki/Logs/`, adds an Obsidian backlink in the Raw note, rebuilds indexes, and updates the source manifest with covered sources accepted as processed.

The extension handles capture and Ask only. Semantic compilation runs separately through the daily automation, which processes the complete pending queue regardless of how many sources were added.

The `Ask` tab in the popup currently performs shallow local search over Raw and Wiki Markdown through the bridge. It does not call an LLM yet.

## Why This Replaces The Floater

Dia does not expose the current tab through Chrome's AppleScript API. Reading Dia history or session files can surface stale tabs, so it is not reliable enough for one-click capture. The extension path is the primary path because the browser itself supplies the active tab URL.

# YouTube transcript fallback

YouTube capture keeps UseTranscribe as the primary transcript provider. Before
the bridge starts the job, the extension also prepares an existing-caption
candidate with the MIT-licensed Defuddle YouTube extractor. The bridge consumes
that candidate only when UseTranscribe fails or returns an empty transcript.

Defuddle output is normalized to the same timestamped Markdown format used by
UseTranscribe:

```markdown
- [00:00] First caption sentence.
- [01:02] Second caption sentence.
```

This fallback is loaded only on YouTube pages. Article DOM and screenshot/OCR
capture paths are unchanged.
