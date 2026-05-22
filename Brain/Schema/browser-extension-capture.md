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

The extension badge shows progress:

```text
1/3 queued
2/3 capturing transcript or article text
3/3 updating the AI Brain catalog
OK  complete
ERR failed
```

For YouTube, Transcribe is the primary transcript provider. If no transcript is captured, the bridge returns an error and does not save a metadata-only source.

Uncached YouTube videos can take a few minutes while Transcribe resolves and transcribes them. Keep the bridge terminal running until the badge changes to `OK` or `ERR`.

For articles, the extension extracts the visible page text from the browser tab and sends it to the bridge. This is important for logged-in or subscription pages, because Python fetching the URL directly may only see a logged-out shell.

## Why This Replaces The Floater

Dia does not expose the current tab through Chrome's AppleScript API. Reading Dia history or session files can surface stale tabs, so it is not reliable enough for one-click capture. The extension path is the primary path because the browser itself supplies the active tab URL.
