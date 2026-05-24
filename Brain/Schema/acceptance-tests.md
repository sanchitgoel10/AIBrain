# Acceptance Tests

Run automated tests from the vault root:

```bash
python3 -m unittest discover -s tests
```

Run the maintenance gate:

```bash
python3 scripts/wiki_tool.py doctor
python3 scripts/wiki_tool.py build
python3 scripts/wiki_tool.py lint
python3 scripts/wiki_tool.py source-lint
python3 scripts/audit_public.py
```

## A. Vault Basics

Expected:

- `doctor` prints all required folders as `ok`.
- `Wiki/catalog.jsonl` exists.
- `Wiki/index.md` exists.
- `Schema/source-manifest.jsonl` exists locally.
- `Raw/Files/` and `Raw/Sources/` content is not staged for Git by default.

## B. Browser Extension And Bridge

Start or verify the bridge:

```bash
python3 -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=5).read().decode())"
```

Expected:

```json
{"ok": true, "service": "aibrain-capture-bridge"}
```

Open Dia or another Chromium browser, load the unpacked extension from:

```text
/Users/sanchitgoel/Documents/AIBrain/Brain/apps/capture-extension
```

Expected:

- Extension popup shows the `ATB` action.
- Extension popup has an `Ask` tab.
- Clicking `ATB` changes status while the capture is running.
- Success shows a completed/green state.
- Failure shows an error state with a readable message.
- The semantic compile counter increases after successful captures.
- At 10 captures, the popup shows a manual semantic compile reminder.
- After running manual Codex semantic compile, clicking `Reset` clears the counter.

## C. YouTube Capture

1. Open a YouTube video with a transcript.
2. Click `ATB`.
3. Wait until the extension reports completion.

Expected:

- A new source appears under `Raw/Sources/`.
- The source has `ContentType` containing `youtube`, `transcript`, and `markdown`.
- The source includes title, URL, timestamp at capture, channel, and transcript text.
- A linked ingest note appears under `Wiki/Logs/`.
- The Raw source includes a `Wiki Links` section pointing back to the ingest note.
- `Wiki/Topics/captured-sources.md` links to the ingest note and source.
- In Obsidian graph, the new yellow Raw node is connected to at least the ingest note and capture hub.

## D. Article Capture

1. Open a readable article page.
2. Click `ATB`.
3. Wait until completion.

Expected:

- A new source appears under `Raw/Sources/`.
- The source has `ContentType` containing `article` and `markdown`; browser-extracted captures also include `browser-extracted`.
- The source includes URL, title, author/date when available, excerpt, and article text.
- A linked ingest note appears under `Wiki/Logs/`.
- The source and ingest note are visible as connected nodes in Obsidian graph.

For paywalled or rendered articles:

- If DOM extraction is too short, the extension should capture screenshots.
- The bridge should run local OCR and save extracted text, or return a clear error.

## E. EPUB Book Import

Put a book in:

```text
Raw/Files/book.epub
```

Run:

```bash
python3 scripts/wiki_tool.py import-epub Raw/Files/book.epub --ingest
```

Expected:

- The original `.epub` remains in `Raw/Files/` and is ignored by Git.
- A Markdown source appears in `Raw/Sources/`.
- The source has `ContentType` containing `epub`, `book`, and `markdown`.
- The source includes title, author, original file path, language, identifier, and book text.
- A linked ingest note appears under `Wiki/Logs/`.
- The book source is connected in Obsidian graph through the ingest note and capture hub.

## F. Catalog And Manifest

After any successful source capture or EPUB import, run:

```bash
python3 scripts/wiki_tool.py build
python3 scripts/wiki_tool.py source-scan --update --accept-covered
python3 scripts/wiki_tool.py source-lint
```

Expected:

- `source-lint` passes.
- `Wiki/catalog.jsonl` includes compiled Wiki notes.
- `Schema/source-manifest.jsonl` lists the Raw source.
- Processed sources have at least one `covered_by` Wiki note.

## G. Git Privacy

Run:

```bash
git status --short
```

Expected:

- Code and schema files may appear as tracked changes.
- Raw source content under `Brain/Raw/Sources/` should not be staged by default.
- Binary/private files under `Brain/Raw/Files/` should not be staged by default.
- Wiki content under `Brain/Wiki/` should not be staged by default except `.gitkeep` placeholders.
- `.env`, Obsidian workspace files, plugin state, cache, and logs should not be staged.

Before pushing:

```bash
python3 scripts/audit_public.py
```

Expected:

- `public audit passed`

## H. Ask My Brain

1. Open the extension popup.
2. Switch to `Ask`.
3. Search for a phrase you know exists in a captured source.

Expected:

- Results show matching Raw or Wiki notes.
- Each result includes a title, path, and snippet.
- This is shallow local search until the semantic compiler/LLM answer layer is added.
