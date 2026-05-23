#!/usr/bin/env python3
"""Article capture helpers."""

from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from pathlib import Path

from capture_browser_legacy import active_tab_json, active_window_title
from capture_common import CaptureError, fetch_text, write_source_note

ARTICLE_JS = r"""
(() => {
  const pick = (...selectors) => {
    for (const selector of selectors) {
      const node = document.querySelector(selector);
      const value = node?.content || node?.textContent;
      if (value && value.trim()) return value.trim();
    }
    return "";
  };
  const article =
    document.querySelector("article") ||
    document.querySelector("main") ||
    document.querySelector("[role='main']") ||
    document.body;
  const text = (article?.innerText || document.body.innerText || "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return JSON.stringify({
    kind: "article",
    url: location.href,
    title: pick("meta[property='og:title']", "meta[name='twitter:title']") || document.title,
    author: pick("meta[name='author']", "meta[property='article:author']", "[rel='author']"),
    date: pick("meta[property='article:published_time']", "meta[name='date']", "time[datetime]"),
    excerpt: pick("meta[name='description']", "meta[property='og:description']", "meta[name='twitter:description']") || text.slice(0, 700),
    text
  });
})()
"""


def text_from_html(page: str) -> str:
    page = re.sub(r"(?is)<script.*?</script>", " ", page)
    page = re.sub(r"(?is)<style.*?</style>", " ", page)
    page = re.sub(r"(?is)<(nav|header|footer|aside).*?</\1>", " ", page)
    page = re.sub(r"(?i)<(p|br|h[1-6]|li|blockquote|div|section|article|main)\b[^>]*>", "\n", page)
    page = re.sub(r"(?s)<[^>]+>", " ", page)
    page = html.unescape(page)
    page = re.sub(r"[ \t]+", " ", page)
    page = re.sub(r"\n\s*\n\s*\n+", "\n\n", page)
    return page.strip()


def meta_content(page: str, *names: str) -> str:
    for name in names:
        patterns = [
            rf'<meta[^>]+(?:name|property)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\']{re.escape(name)}["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, page, re.I)
            if match:
                return html.unescape(match.group(1)).strip()
    return ""


def article_data_from_url(url: str) -> dict:
    page = fetch_text(url)
    text = text_from_html(page)
    title = meta_content(page, "og:title", "twitter:title")
    if not title:
        match = re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
        title = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip() if match else active_window_title()
    return {
        "kind": "article",
        "url": url,
        "title": title or "Article",
        "author": meta_content(page, "author", "article:author"),
        "date": meta_content(page, "article:published_time", "date"),
        "excerpt": meta_content(page, "description", "og:description", "twitter:description") or text[:700],
        "text": text,
    }


def minimal_article_data(url: str, reason: Exception | str) -> dict:
    title = active_window_title().strip() or urllib.parse.urlparse(url).netloc or "Article"
    warning = (
        "Full article text could not be captured automatically.\n\n"
        f"Reason: {reason}\n\n"
        "The URL was saved for follow-up."
    )
    return {
        "kind": "article",
        "url": url,
        "title": title,
        "author": "",
        "date": "",
        "excerpt": warning,
        "text": warning,
    }


def capture_article(browser: str | None = None, data: dict | None = None, url: str | None = None) -> Path:
    if data is None:
        try:
            data = article_data_from_url(url) if url else active_tab_json(browser or "", ARTICLE_JS)
        except (CaptureError, urllib.error.URLError) as exc:
            if not url:
                raise
            data = minimal_article_data(url, exc)
    title = data.get("title") or "Article"
    text = data.get("text") or ""
    if len(text.strip()) < 300 and not data.get("browserExtracted"):
        text = (
            "Full article text could not be captured automatically.\n\n"
            "The metadata and excerpt below were saved for follow-up."
        )
    body = f"""# {title}

Source type: Article

URL: {data.get("url", "")}

Author: {data.get("author", "")}

Published: {data.get("date", "")}

Capture warning: {data.get("captureWarning", "")}

## Excerpt

{data.get("excerpt", "").strip()}

## Article Text

{text}
"""
    content_types = ["article", "markdown"]
    if data.get("browserExtracted"):
        content_types.insert(1, "browser-extracted")
    return write_source_note(
        title=title,
        author=data.get("author", ""),
        reference=data.get("url", ""),
        content_types=content_types,
        body=body,
    )
