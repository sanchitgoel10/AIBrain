const BRIDGE_URL = "http://127.0.0.1:8765/capture";
const STATUS_URL = "http://127.0.0.1:8765/status";

const state = {
  tab: null
};

const els = {
  capture: document.getElementById("capture"),
  kind: document.getElementById("kind"),
  progress: document.getElementById("progressBar"),
  status: document.getElementById("status"),
  title: document.getElementById("title"),
  url: document.getElementById("url")
};

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isCaptureUrl(url) {
  return /^https?:\/\//i.test(url || "");
}

function isYoutubeUrl(url) {
  return /(^https?:\/\/)?([^/]+\.)?(youtube\.com\/watch|youtu\.be\/)/i.test(url || "");
}

function setProgress(status, message) {
  els.progress.className = `progress-bar ${status || "idle"}`;
  els.status.textContent = message || "Ready.";
  const badgeMap = {
    queued: ["ATB", "#155EEF"],
    capturing: ["ATB", "#7C3AED"],
    ingesting: ["ATB", "#0F766E"],
    maintenance: ["ATB", "#B45309"],
    done: ["ATB", "#16833A"],
    error: ["ERR", "#B42318"]
  };
  const [text, color] = badgeMap[status] || ["ATB", "#155EEF"];
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color });
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
    .slice(0, 300000);
  return {
    title: pick("meta[property='og:title']", "meta[name='twitter:title']") || document.title,
    author: pick("meta[name='author']", "meta[property='article:author']", "[rel='author']"),
    date: pick("meta[property='article:published_time']", "meta[name='date']", "time[datetime]"),
    excerpt: pick("meta[name='description']", "meta[property='og:description']", "meta[name='twitter:description']") || text.slice(0, 700),
    text,
    textLength: text.length
  };
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0] || null;
}

async function getArticlePayload(tab) {
  if (isYoutubeUrl(tab?.url || "")) return null;
  const results = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: extractVisiblePage
  });
  const page = results?.[0]?.result || null;
  if (!page || !page.text || page.text.trim().length < 120) {
    throw new Error("Could not read enough visible article text from this tab.");
  }
  return page;
}

async function pollJob(jobId) {
  for (let attempt = 0; attempt < 360; attempt += 1) {
    await sleep(1500);
    const response = await fetch(`${STATUS_URL}?job_id=${encodeURIComponent(jobId)}`);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || `Status returned HTTP ${response.status}`);
    }
    const job = payload.job || {};
    setProgress(job.status, job.message || "AI Brain capture is running.");
    if (job.status === "done") {
      setProgress("done", `Saved ${job.path || "source note"} and linked ${job.ingest_path || "Wiki note"}.`);
      return;
    }
    if (job.status === "error") {
      throw new Error(job.error || job.message || "Capture failed");
    }
  }
  throw new Error("Capture is still running after 9 minutes. Check the bridge terminal.");
}

async function startCapture() {
  const tab = state.tab;
  const url = tab?.url || "";
  if (!isCaptureUrl(url)) {
    setProgress("error", "This tab does not have a normal http/https URL.");
    return;
  }

  els.capture.disabled = true;
  try {
    setProgress("queued", "Preparing active tab.");
    const page = await getArticlePayload(tab);
    if (page) {
      setProgress("queued", `Read ${page.textLength.toLocaleString()} visible article characters.`);
    }
    const response = await fetch(BRIDGE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, title: tab.title || "", page })
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || `Bridge returned HTTP ${response.status}`);
    }
    await pollJob(payload.job_id);
  } catch (error) {
    setProgress("error", `${error.message} Start scripts/run_capture_bridge.sh and reload the extension if needed.`);
  } finally {
    els.capture.disabled = false;
  }
}

async function init() {
  chrome.action.setBadgeText({ text: "ATB" });
  chrome.action.setBadgeBackgroundColor({ color: "#155EEF" });
  state.tab = await getActiveTab();
  const tab = state.tab;
  els.title.textContent = tab?.title || "No active tab";
  els.url.textContent = tab?.url || "";
  els.kind.textContent = isYoutubeUrl(tab?.url || "") ? "YouTube transcript" : "Article page";
  if (!isCaptureUrl(tab?.url || "")) {
    els.capture.disabled = true;
    setProgress("error", "Open a YouTube video or article tab first.");
  } else {
    setProgress("queued", "Ready to add this active tab.");
  }
}

els.capture.addEventListener("click", startCapture);
init();
