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

function articleScrollPlan() {
  const height = Math.max(
    document.body?.scrollHeight || 0,
    document.documentElement?.scrollHeight || 0
  );
  const viewport = Math.max(window.innerHeight || 800, 500);
  const maxY = Math.max(height - viewport, 0);
  const step = Math.max(Math.floor(viewport * 0.82), 350);
  const positions = [];
  for (let y = 0; y <= maxY; y += step) {
    positions.push(y);
    if (positions.length >= 10) break;
  }
  if (!positions.includes(maxY) && positions.length < 10) {
    positions.push(maxY);
  }
  return {
    originalY: window.scrollY || 0,
    positions: [...new Set(positions)],
    title: document.title
  };
}

function scrollToCapturePosition(y) {
  window.scrollTo(0, y);
  return { y: window.scrollY || y };
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0] || null;
}

async function captureArticleScreenshots(tab) {
  const planResults = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: articleScrollPlan
  });
  const plan = planResults?.[0]?.result || { positions: [0], originalY: 0 };
  const screenshots = [];
  const positions = (plan.positions || [0]).slice(0, 10);
  for (let index = 0; index < positions.length; index += 1) {
    const y = positions[index];
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: scrollToCapturePosition,
      args: [y]
    });
    await sleep(450);
    setProgress("capturing", `Capturing article screenshot ${index + 1}/${positions.length} for OCR.`);
    const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
    screenshots.push({ y, dataUrl });
  }
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: scrollToCapturePosition,
    args: [plan.originalY || 0]
  });
  return screenshots;
}

async function getArticlePayload(tab) {
  if (isYoutubeUrl(tab?.url || "")) return null;
  let page = null;
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractVisiblePage
    });
    page = results?.[0]?.result || null;
  } catch (error) {
    page = {
      title: tab.title || "Article",
      author: "",
      date: "",
      excerpt: "",
      text: "",
      textLength: 0,
      extractionError: error.message
    };
  }
  if (page?.text && page.text.trim().length >= 800) {
    page.extractionMethod = "browser-dom";
    return page;
  }
  setProgress("capturing", "Visible article text is limited. Capturing screenshots for OCR.");
  page = page || { title: tab.title || "Article", author: "", date: "", excerpt: "", text: "", textLength: 0 };
  page.screenshots = await captureArticleScreenshots(tab);
  page.extractionMethod = "screenshot-ocr";
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
