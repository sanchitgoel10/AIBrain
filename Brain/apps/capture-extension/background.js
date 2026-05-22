const BRIDGE_URL = "http://127.0.0.1:8765/capture";
const STATUS_URL = "http://127.0.0.1:8765/status";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function showStatus(text, title, color = "#2563EB") {
  await chrome.action.setBadgeText({ text });
  await chrome.action.setBadgeBackgroundColor({ color });
  await chrome.action.setTitle({ title });
}

function clearStatusSoon(delay = 5000) {
  setTimeout(() => {
    chrome.action.setBadgeText({ text: "" });
    chrome.action.setTitle({ title: "Capture to AI Brain" });
  }, delay);
}

function isCaptureUrl(url) {
  return /^https?:\/\//i.test(url || "");
}

function isYoutubeUrl(url) {
  return /(^https?:\/\/)?([^/]+\.)?(youtube\.com\/watch|youtu\.be\/)/i.test(url || "");
}

function extractVisiblePage() {
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
    .replace(/[ \t]{2,}/g, " ")
    .trim()
    .slice(0, 250000);
  return {
    title: pick("meta[property='og:title']", "meta[name='twitter:title']") || document.title,
    author: pick("meta[name='author']", "meta[property='article:author']", "[rel='author']"),
    date: pick("meta[property='article:published_time']", "meta[name='date']", "time[datetime]"),
    excerpt: pick("meta[name='description']", "meta[property='og:description']", "meta[name='twitter:description']") || text.slice(0, 700),
    text
  };
}

async function articlePayload(tab) {
  if (isYoutubeUrl(tab?.url || "")) return null;
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractVisiblePage
    });
    return results?.[0]?.result || null;
  } catch (_error) {
    return null;
  }
}

function badgeForStatus(status) {
  if (status === "queued") return ["1/3", "#2563EB"];
  if (status === "capturing") return ["2/3", "#7C3AED"];
  if (status === "maintenance") return ["3/3", "#B45309"];
  if (status === "done") return ["OK", "#167C3A"];
  return ["ERR", "#B42318"];
}

async function pollJob(jobId) {
  for (let attempt = 0; attempt < 360; attempt += 1) {
    await sleep(2000);
    const response = await fetch(`${STATUS_URL}?job_id=${encodeURIComponent(jobId)}`);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || `Status returned HTTP ${response.status}`);
    }
    const job = payload.job || {};
    const [badge, color] = badgeForStatus(job.status);
    await showStatus(badge, job.message || "AI Brain capture is running.", color);
    if (job.status === "done") {
      await showStatus("OK", `Captured to AI Brain: ${job.path || job.url || ""}`, "#167C3A");
      clearStatusSoon();
      return;
    }
    if (job.status === "error") {
      throw new Error(job.error || job.message || "Capture failed");
    }
  }
  throw new Error("Capture is still running after 12 minutes. Check the bridge terminal.");
}

chrome.action.onClicked.addListener(async (tab) => {
  const url = tab?.url || "";
  const title = tab?.title || "";

  if (!isCaptureUrl(url)) {
    await showStatus("ERR", "AI Brain capture skipped: this tab has no normal http/https URL.", "#B42318");
    clearStatusSoon();
    return;
  }

  try {
    await showStatus("1/3", "AI Brain capture started.", "#2563EB");
    const page = await articlePayload(tab);
    const response = await fetch(BRIDGE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, title, page })
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || `Bridge returned HTTP ${response.status}`);
    }
    await pollJob(payload.job_id);
  } catch (error) {
    await showStatus("ERR", `AI Brain bridge error: ${error.message}. Start scripts/run_capture_bridge.sh first.`, "#B42318");
    clearStatusSoon(9000);
  }
});
